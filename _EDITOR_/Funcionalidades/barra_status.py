# 📁 _EDITOR_/Funcionalidades/barra_status.py
"""
BarraStatus  — rodapé horizontal do CodeEditor, colado na borda inferior.
BarraOutline — rodapé horizontal do PainelOutline, usa as mesmas cores/altura.

BarraStatus exibe (esquerda → direita):
  [●] [ Ln : Col ] [N Linhas] [N Ch]  ...stretch...  [LF/CRLF] [UTF-8] [Python] [1.2 KB]

BarraOutline exibe:
  [⊗ N erros] [△ N avisos]  ...stretch...  [⌨] [?]

Ambas usam a mesma chave de cor (editor.busca_match_ativo), altura (22 px),
borda e fonte — garantindo consistência visual sem duplicar código.

Posicionamento de BarraStatus: QWidget filho direto do editor, altura fixa,
largura = editor.width() menos o espaço do outline+handle.
Reposicionado em cada resizeEvent via posicionar().

BarraOutline é adicionada diretamente ao layout do PainelOutline.
"""
import os
import subprocess
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                                QPushButton, QFrame, QPlainTextEdit)
from PySide6.QtCore    import Qt
from PySide6.QtGui     import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import FONTE_UI

# Deve bater com _HANDLE_OUTLINE_LARGURA em Editor.py — evitamos importar
# a constante direto pra não criar import circular (Editor.py já importa
# BarraStatus no topo do arquivo).
_HANDLE_OUTLINE_LARGURA = 4


# ──────────────────────────────────────────────────────────────────────────────
# Highlighter de diff (+ verde, - vermelho, @@ azul, cabeçalhos dim)
# ──────────────────────────────────────────────────────────────────────────────

class _DiffHighlighter(QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)
        def _fmt(cor):
            f = QTextCharFormat()
            f.setForeground(QColor(cor))
            return f
        self._add  = _fmt("#89d185")   # verde — linha adicionada
        self._del  = _fmt("#f48771")   # vermelho — linha removida
        self._hdr  = _fmt("#61afef")   # azul — hunk @@ ... @@
        self._meta = _fmt("#5a6a7a")   # cinza — diff/index/---/+++

    def highlightBlock(self, text):
        if text.startswith('+') and not text.startswith('+++'):
            self.setFormat(0, len(text), self._add)
        elif text.startswith('-') and not text.startswith('---'):
            self.setFormat(0, len(text), self._del)
        elif text.startswith('@@'):
            self.setFormat(0, len(text), self._hdr)
        elif text.startswith(('diff ', 'index ', '---', '+++')):
            self.setFormat(0, len(text), self._meta)


class BarraStatus(QWidget):
    """Rodapé fino colado na borda inferior do CodeEditor."""

    ALTURA = 22

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor
        self._construir()
        self._conectar()
        self.posicionar()
        self.raise_()
        self.show()

    # ──────────────────────────────────────────────────────────────────
    # Construção da UI
    # ──────────────────────────────────────────────────────────────────

    def _construir(self):
        t      = tema_global()
        fundo  = t.cor("editor.fundo",       "#1e1e2e")
        texto  = t.cor("editor.palavra_chave", "#7094A1")
        
        # Sem isso, o QWidget só pinta o fundo do QSS embaixo dos filhos
        # (os QLabel); o espaço do addStretch() no meio fica transparente,
        # mostrando o fundo escuro do editor por baixo — parecendo duas
        # caixas separadas em vez de uma barra única.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(self.ALTURA)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {fundo};
            }}
            QLabel {{
                color: {texto};
                font-size: 11px;
                font-family: {FONTE_UI};
                border: none;
                padding: 0 8px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(1)

        self._lbl_modificado = QLabel("")
        self._lbl_modificado.setStyleSheet("border: none; padding: 0 2px;")
        self._lbl_modificado.setToolTip("Arquivo salvo — nenhuma alteração pendente")

        self._lbl_posicao = QLabel("[ 1 : 1 ]")
        self._lbl_total   = QLabel("1 Linhas")
        self._lbl_selecao = QLabel("( 0 Ch )")

        self._lbl_line_end = QLabel("LF")
        self._lbl_encoding = QLabel("UTF-8")
        self._lbl_extensao = QLabel("—")
        self._lbl_tamanho  = QLabel("0 B")

        self._lbl_posicao.setToolTip("Posição do cursor (Linha : Coluna)")
        self._lbl_total.setToolTip("Total de linhas do arquivo")
        self._lbl_selecao.setToolTip("Caracteres selecionados no momento")
        self._lbl_line_end.setToolTip(
            "Tipo de quebra de linha do arquivo (LF = Unix/Mac, CRLF = Windows, CR = Mac clássico)"
        )
        self._lbl_encoding.setToolTip("Codificação de caracteres usada para ler/salvar o arquivo")
        self._lbl_extensao.setToolTip("Linguagem/tipo do arquivo, detectado pela extensão")
        self._lbl_tamanho.setToolTip("Tamanho do arquivo em disco")

        # Botão ⎇ Diff — abre painel com git diff do arquivo atual
        self._btn_diff = QPushButton("⎇ Diff")
        self._btn_diff.setObjectName("BtnDiffHein")
        self._btn_diff.setCheckable(False)
        self._btn_diff.setToolTip("Navegar para a próxima alteração git (⎇ Diff)")
        self._btn_diff.setCursor(Qt.PointingHandCursor)
        self._btn_diff.setStyleSheet(f"""
            QPushButton {{
                color: {texto};
                background: transparent;
                border: none;
                font-size: 11px;
                font-family: {FONTE_UI};
                padding: 0 6px;
            }}
            QPushButton:hover   {{ color: #4a90d9; }}
            QPushButton:checked {{
                color: #ffffff;
                background: #1c4a8a;
                border-radius: 3px;
            }}
        """)
        self._btn_diff.clicked.connect(self._toggle_diff)
        self._painel_diff = self._construir_painel_diff()

        # Esquerda: estado do cursor/seleção — dot (salvo/modificado) seguido
        # do total de linhas, depois posição do cursor e seleção. Direita:
        # metadados do arquivo.
        for w in (self._lbl_modificado, self._lbl_total, self._lbl_posicao,
                  self._lbl_selecao, self._btn_diff):
            layout.addWidget(w)
        layout.addStretch()
        for w in (self._lbl_line_end, self._lbl_encoding,
                  self._lbl_extensao, self._lbl_tamanho):
            layout.addWidget(w)

    # ──────────────────────────────────────────────────────────────────
    # Conexão de sinais
    # ──────────────────────────────────────────────────────────────────

    def _conectar(self):
        e = self._editor
        e.cursorPositionChanged.connect(self._atualizar_posicao)
        e.selectionChanged.connect(self._atualizar_selecao)
        e.textChanged.connect(self._atualizar_texto)
        e.document().modificationChanged.connect(self._atualizar_modificado)
        # arquivo salvo → atualizar metadados
        if hasattr(e, 'arquivo_salvo'):
            e.arquivo_salvo.connect(lambda p=None: self.atualizar_arquivo(
                p if isinstance(p, str) else getattr(e, 'file_path', None)
            ))

    # ──────────────────────────────────────────────────────────────────
    # Posicionamento
    # ──────────────────────────────────────────────────────────────────

    def posicionar(self):
        """Reposiciona o rodapé na borda inferior, sem passar por baixo do outline."""
        e               = self._editor
        largura_outline = getattr(e, '_largura_outline', 0)
        reserva_outline = largura_outline + _HANDLE_OUTLINE_LARGURA if largura_outline > 0 else 0
        largura = e.width() - reserva_outline
        y = e.height() - self.ALTURA
        self.setGeometry(0, y, max(largura, 0), self.ALTURA)
        self.raise_()

    # ──────────────────────────────────────────────────────────────────
    # Atualizações internas (slots)
    # ──────────────────────────────────────────────────────────────────

    def _atualizar_posicao(self):
        cur   = self._editor.textCursor()
        ln    = cur.blockNumber() + 1
        col   = cur.columnNumber() + 1
        total = self._editor.document().blockCount()
        self._lbl_posicao.setText(f"[ {ln} : {col} ]")
        self._lbl_total.setText(f"{total} Linhas")

    def _atualizar_selecao(self):
        cur = self._editor.textCursor()
        if cur.hasSelection():
            sel    = cur.selectedText()
            chars  = len(sel)
            linhas = sel.count('\u2029') + 1   # Qt usa U+2029 como quebra de parágrafo
            if linhas > 1:
                self._lbl_selecao.setText(f"( {linhas} Ln, {chars} Ch )")
            else:
                self._lbl_selecao.setText(f"( {chars} Ch )")
        else:
            self._lbl_selecao.setText("( 0 Ch )")

    def _atualizar_texto(self):
        e     = self._editor
        texto = e.toPlainText()

        # tamanho
        if getattr(e, 'file_path', None) and os.path.exists(e.file_path):
            b = os.path.getsize(e.file_path)
        else:
            b = len(texto.encode(getattr(e, '_encoding', 'utf-8'), errors='replace'))
        self._lbl_tamanho.setText(f"{b} B" if b < 1024 else f"{b / 1024:.1f} KB")

    def _atualizar_modificado(self, modificado: bool):
        if modificado:
            self._lbl_modificado.setText("●")
            self._lbl_modificado.setStyleSheet(
                "color: #e5c07b; font-size: 10px; border: none; padding: 0 2px;"
            )
            self._lbl_modificado.setToolTip("Alterações não salvas — o arquivo tem mudanças pendentes")
        else:
            self._lbl_modificado.setText("")
            self._lbl_modificado.setStyleSheet("border: none; padding: 0 2px;")
            self._lbl_modificado.setToolTip("Arquivo salvo — nenhuma alteração pendente")

    # ──────────────────────────────────────────────────────────────────
    # API pública
    # ──────────────────────────────────────────────────────────────────

    def atualizar_arquivo(self, caminho: str | None):
        """
        Chamado quando um arquivo é aberto ou salvo.
        Atualiza extensão, encoding e line ending.
        """
        if not caminho:
            self._lbl_extensao.setText("NOVO")
            self._lbl_line_end.setText("LF")
            return

        # extensão / tipo
        ext = caminho.rsplit('.', 1)[-1].upper() if '.' in caminho else "—"
        ext = ext.replace("PY", "Python").replace("PS1", "PowerShell")
        self._lbl_extensao.setText(ext)

        # encoding que o editor registrou
        self._lbl_encoding.setText(
            getattr(self._editor, '_encoding', 'utf-8').upper()
        )

        # line ending — Qt normaliza para \n; precisa ler o arquivo cru
        try:
            with open(caminho, 'rb') as f:
                amostra = f.read(8192)
            if b'\r\n' in amostra:
                self._lbl_line_end.setText("CRLF")
            elif b'\r' in amostra:
                self._lbl_line_end.setText("CR")
            else:
                self._lbl_line_end.setText("LF")
        except OSError:
            self._lbl_line_end.setText("LF")

    # ──────────────────────────────────────────────────────────────────
    # Painel Git Diff
    # ──────────────────────────────────────────────────────────────────

    def _construir_painel_diff(self) -> QFrame:
        """Cria o painel flutuante que exibe o git diff do arquivo atual."""
        t      = tema_global()

        texto  = t.cor("editor.palavra_chave", "#7094A1")

        
        fundo_pop = t.cor("editor.fundo",    "#1e1e2e")
        borda_pop = t.cor("interface.borda", "#2a2a4a")
        texto_pop = t.cor("editor.texto",    "#d0d0d0")

        painel = QFrame(None)
        painel.setObjectName("PainelDiffHein")
        painel.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        painel.setStyleSheet(f"""
            QFrame#PainelDiffHein {{
                background: {fundo_pop};
                border: 1px solid {borda_pop};
                border-radius: 4px;
            }}
        """)

        lay = QVBoxLayout(painel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── título ────────────────────────────────────────────────────
        topo = QWidget()
        topo.setStyleSheet(
            f"background:{borda_pop}; border-bottom:1px solid {borda_pop};"
        )
        lay_topo = QHBoxLayout(topo)
        lay_topo.setContentsMargins(8, 3, 6, 3)

        self._lbl_diff_titulo = QLabel("Git Diff")
        self._lbl_diff_titulo.setStyleSheet(
            f"color:{texto}; font-size:11px; font-family:{FONTE_UI};"
            "border:none; padding:0;"
        )

        btn_fechar = QPushButton("✕")
        btn_fechar.setFixedSize(16, 16)
        btn_fechar.setCursor(Qt.PointingHandCursor)
        btn_fechar.setStyleSheet(
            "color:#7094A1; background:transparent; border:none; font-size:11px;"
        )
        btn_fechar.clicked.connect(self._fechar_diff)

        lay_topo.addWidget(self._lbl_diff_titulo)
        lay_topo.addStretch()
        lay_topo.addWidget(btn_fechar)
        lay.addWidget(topo)

        # ── área do diff ──────────────────────────────────────────────
        self._txt_diff = QPlainTextEdit()
        self._txt_diff.setReadOnly(True)
        self._txt_diff.setLineWrapMode(QPlainTextEdit.NoWrap)
        fonte = QFont("Consolas", 10)
        fonte.setStyleHint(QFont.Monospace)
        self._txt_diff.setFont(fonte)
        self._txt_diff.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {fundo_pop};
                color: {texto_pop};
                border: none;
                padding: 4px;
            }}
        """)
        self._diff_hl = _DiffHighlighter(self._txt_diff.document())
        lay.addWidget(self._txt_diff)

        return painel

    def _toggle_diff(self):
        """Navega para a próxima (ou primeira) alteração git no arquivo."""
        editor = self._editor
        if editor and hasattr(editor, 'ir_para_proxima_mudanca_git'):
            editor.ir_para_proxima_mudanca_git()

    def _abrir_diff(self):
        self._atualizar_diff()
        self._posicionar_painel_diff()
        self._painel_diff.show()
        self._painel_diff.raise_()
        self._btn_diff.setChecked(True)

    def _fechar_diff(self):
        self._painel_diff.hide()
        self._btn_diff.setChecked(False)

    def _atualizar_diff(self):
        from _EDITOR_.Ui.diff_git_gutter import obter_diff_raw
        caminho = getattr(self._editor, 'file_path', None)
        if not caminho:
            self._txt_diff.setPlainText("Nenhum arquivo aberto.")
            self._lbl_diff_titulo.setText("Git Diff")
            return
        projeto = getattr(self._editor, '_projeto_path', None) or \
                  os.path.dirname(caminho)
        nome = os.path.basename(caminho)
        self._lbl_diff_titulo.setText(f"Git Diff — {nome}")
        raw = obter_diff_raw(caminho, projeto)
        self._txt_diff.setPlainText(
            raw if raw.strip() else "Sem alterações desde o último commit."
        )

    def _posicionar_painel_diff(self):
        e       = self._editor
        largura = max(min(e.width() - 60, 860), 420)
        altura  = max(min(e.height() - self.ALTURA - 50, 450), 200)
        pos     = self.mapToGlobal(self.rect().topLeft())
        self._painel_diff.setGeometry(
            pos.x(), pos.y() - altura - 4, largura, altura
        )

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────

# ══════════════════════════════════════════════════════════════════════════════
# BarraOutline — rodapé do PainelOutline, mesmo estilo da BarraStatus
# ══════════════════════════════════════════════════════════════════════════════

class BarraOutline(QWidget):
    """
    Rodapé do PainelOutline.

    Usa as mesmas cores e altura da BarraStatus (editor.busca_match_ativo),
    centralizado aqui para que qualquer mudança de tema/estilo afete os
    dois rodapés ao mesmo tempo.

    Widgets públicos (conectados pelo PainelOutline após instanciar):
        lbl_erros        — QLabel "⊗ N"
        lbl_avisos       — QLabel "△ N"
        btn_atalhos_fold — QPushButton ⌨  (outline conecta o .clicked)
        btn_ajuda        — QPushButton ?  (outline conecta o .clicked e ícone)
    """

    ALTURA = 22   # mesma constante da BarraStatus

    def __init__(self, parent=None):
        super().__init__(parent)
        self._construir()

    def _construir(self):
        t      = tema_global()
        fundo  = t.cor("editor.fundo",       "#1e1e2e")
        texto  = t.cor("editor.palavra_chave", "#7094A1")
        
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(self.ALTURA)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {fundo};
            }}
            QLabel {{
                color: {texto};
                font-size: 11px;
                font-family: {FONTE_UI};
                border: none;
                padding: 0 5px;
            }}
            QPushButton {{
                background: transparent;
                color: {texto};
                border: none;
                font-size: 11px;
                padding: 0 4px;
            }}
            QPushButton:hover {{
                color: #4a90d9;
            }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 0, 6, 0)
        lay.setSpacing(5)

        # ── lado esquerdo: contadores de erros e avisos ───────────────
        self.lbl_erros = QLabel("\u2297 0")     # ⊗ 0
        self.lbl_erros.setToolTip(
            "Quantidade de erros no arquivo (0 = nenhum erro)"
        )

        self.lbl_avisos = QLabel("\u25b3 0")    # △ 0
        self.lbl_avisos.setToolTip(
            "Quantidade de avisos (warnings) no arquivo (0 = nenhum aviso)"
        )

        lay.addWidget(self.lbl_erros)
        lay.addWidget(self.lbl_avisos)
        lay.addStretch()

        sep = QLabel("|")
        sep.setStyleSheet("color: #2a2a3a; border: none; padding: 0; font-size: 10px;")
        lay.addWidget(sep)

        # ── lado direito: botões (ícones e .clicked conectados pelo outline) ──
        self.btn_atalhos_fold = QPushButton("⌨")
        self.btn_atalhos_fold.setObjectName("BtnAtalhosFold")
        self.btn_atalhos_fold.setToolTip("Atalhos de dobramento de blocos")
        self.btn_atalhos_fold.setFixedSize(20, 20)

        self.btn_ajuda = QPushButton("?")
        self.btn_ajuda.setToolTip("Ajuda — funcionalidades")
        self.btn_ajuda.setCursor(Qt.PointingHandCursor)
        self.btn_ajuda.setFixedSize(20, 20)

        lay.addWidget(self.btn_atalhos_fold)
        lay.addWidget(self.btn_ajuda)
