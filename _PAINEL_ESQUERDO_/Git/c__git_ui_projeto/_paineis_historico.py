# 📁 _PAINEL_ESQUERDO_/Git/c__git_ui_projeto/_paineis_historico.py
"""
Painéis de Histórico:
  _PainelHistoricoVersoes  — lista de commits do projeto (restaurar / apagar)
  _PainelHistoricoArquivo  — commits que tocaram o arquivo aberto no editor
"""
import os
from PySide6.QtCore    import Qt, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QListWidget, QListWidgetItem,
    QPushButton, QTextEdit, QSplitter, QLineEdit,
)
from PySide6.QtGui import QColor
from ..git_gerente      import GerenciadorGit
from ..git_terminal     import GitTerminal
from ..git_ui_utils     import _botao, _em_thread
from _UTILITARIOS_.icones       import icone_tema
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import COR_GIT_TEXTO_NEUTRO, FONTE_MONO
from ._paineis_status_diff import _ESTILO_TREE

# ══════════════════════════════════════════════════════════════════════
# Janela de Histórico de Versões
# ══════════════════════════════════════════════════════════════════════

class _PainelHistoricoVersoes(QWidget):
    """
    Painel de histórico de versões — abre como aba no terminal central.
    Exibe commits com botões 'Restaurar' e 'Apagar' em cada linha.
    Recebe callbacks externos para executar as ações sem acoplamento direto.
    """

    def __init__(self, versoes: list[dict], cb_restaurar, cb_apagar, parent=None):
        super().__init__(parent)
        self._versoes      = versoes
        self._cb_restaurar = cb_restaurar
        self._cb_apagar    = cb_apagar

        _t      = tema_global()
        _fundo  = _t.cor("interface.fundo",  "#0d1117")
        _texto  = _t.cor("interface.texto",  "#c9d1d9")
        _dest   = _t.cor("interface.icone",  "#4ec994")

        self.setStyleSheet(f"background:{_fundo}; color:{_texto};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # Cabeçalho
        cab = QWidget()
        cab.setStyleSheet(f"background:#0a0a0a; border-bottom:1px solid #1a1a1a;")
        lay_cab = QHBoxLayout(cab)
        lay_cab.setContentsMargins(10, 6, 10, 6)
        titulo = QLabel("Histórico de Versões")
        titulo.setStyleSheet(f"font-size:11px; font-weight:bold; color:{_dest};")
        lbl_qtd = QLabel(f"{len(versoes)} versão(ões)")
        lbl_qtd.setStyleSheet("font-size:10px; color:#555;")
        lay_cab.addWidget(titulo)
        lay_cab.addStretch()
        lay_cab.addWidget(lbl_qtd)
        raiz.addWidget(cab)

        # Aviso sobre ação destrutiva
        aviso = QLabel(
            "⚠  Apagar reescreve o histórico Git. "
            "Se houver token ativo o GitHub também será atualizado com força."
        )
        aviso.setWordWrap(True)
        aviso.setStyleSheet(
            "font-size:10px; color:#b08020; background:#1a1200;"
            " padding:5px 10px; border-bottom:1px solid #2a2000;"
        )
        raiz.addWidget(aviso)

        # Área com scroll das versões
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"border:none; background:{_fundo};")

        conteudo = QWidget()
        conteudo.setStyleSheet(f"background:{_fundo};")
        lay_conteudo = QVBoxLayout(conteudo)
        lay_conteudo.setContentsMargins(8, 8, 8, 8)
        lay_conteudo.setSpacing(4)

        if not versoes:
            vazio = QLabel("Nenhuma versão encontrada.")
            vazio.setStyleSheet("color:#444; font-size:11px; padding:8px;")
            lay_conteudo.addWidget(vazio)
        else:
            for v in versoes:
                lay_conteudo.addWidget(self._criar_linha(v))

        lay_conteudo.addStretch()
        scroll.setWidget(conteudo)
        raiz.addWidget(scroll, 1)

    def _criar_linha(self, versao: dict) -> QWidget:
        _t   = tema_global()
        _bg  = _t.cor("interface.fundo_painel",    "#161b22")
        _brd = _t.cor("interface.borda",            "#21262d")
        _hov = _t.cor("interface.fundo_item_hover", "#1c2128")

        w = QWidget()
        w.setStyleSheet(f"""
            QWidget {{ background:{_bg}; border:1px solid {_brd};
                      border-radius:4px; }}
            QWidget:hover {{ background:{_hov}; }}
        """)

        lay = QHBoxLayout(w)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(8)

        info = QVBoxLayout()
        info.setSpacing(2)

        lbl_msg = QLabel(versao.get("mensagem", "—"))
        lbl_msg.setStyleSheet("font-size:11px; color:#c9d1d9;")
        lbl_msg.setWordWrap(True)

        hash_quando = f"{versao.get('hash_curto','')}  ·  {versao.get('quando','')}"
        lbl_meta = QLabel(hash_quando)
        lbl_meta.setStyleSheet("font-size:10px; color:#484f58;")

        info.addWidget(lbl_msg)
        info.addWidget(lbl_meta)

        btn_restaurar = _botao("Restaurar")
        btn_restaurar.setFixedWidth(80)
        btn_restaurar.clicked.connect(lambda _, v=versao: self._cb_restaurar(v))

        btn_apagar = QPushButton("Apagar")
        btn_apagar.setFixedWidth(70)
        btn_apagar.setStyleSheet("""
            QPushButton {
                background:#3a0a0a; color:#cc4444; border:1px solid #5a1a1a;
                padding:4px 8px; font-size:10px; border-radius:3px;
            }
            QPushButton:hover { background:#5a1010; color:#ff6060; }
        """)
        btn_apagar.clicked.connect(lambda _, v=versao: self._cb_apagar(v, self))

        lay.addLayout(info, 1)
        lay.addWidget(btn_restaurar)
        lay.addWidget(btn_apagar)

        return w

    def recarregar(self, versoes: list[dict]):
        """Reconstrói o painel com nova lista de versões (após apagar)."""
        self._versoes = versoes
        pass

# ══════════════════════════════════════════════════════════════════════
# Painel de Histórico do Arquivo
# ══════════════════════════════════════════════════════════════════════

class _PainelHistoricoArquivo(QWidget):
    """
    Aba "Arquivo" — lista todos os commits que tocaram o arquivo
    atualmente aberto no editor. Clicar num commit exibe o conteúdo
    completo do arquivo naquele momento (somente leitura).
    """

    def __init__(self, git: GerenciadorGit, terminal: GitTerminal, parent=None):
        super().__init__(parent)
        self._git              = git
        self._terminal         = terminal
        self._caminho_projeto  = ""
        self._arquivo_ativo    = ""
        self._pontes: list     = []
        self._construir()

    def _construir(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Label: arquivo em foco
        self._lbl_arquivo = QLabel("  Nenhum arquivo aberto no editor")
        self._lbl_arquivo.setStyleSheet(
            "font-size:10px; color:#555; padding:4px 8px; background:#0a0a0a;"
        )
        lay.addWidget(self._lbl_arquivo)

        # Splitter vertical: lista de commits (cima) + viewer (baixo)
        splitter = QSplitter(Qt.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background:#1a1a1a; height:2px; }")

        # ── Lista de commits ─────────────────────────────────────────
        self._lista = QListWidget()
        self._lista.setStyleSheet(_ESTILO_TREE)
        self._lista.itemClicked.connect(self._ao_selecionar)
        splitter.addWidget(self._lista)

        # ── Painel inferior: barra de busca + viewer ──────────────────
        viewer_panel = QWidget()
        vlay = QVBoxLayout(viewer_panel)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        # Barra de busca
        barra_busca = QWidget()
        barra_busca.setStyleSheet("background:#0d0d0d; border-bottom:1px solid #1a1a1a;")
        lay_busca = QHBoxLayout(barra_busca)
        lay_busca.setContentsMargins(6, 3, 6, 3)
        lay_busca.setSpacing(6)

        self._input_busca = QLineEdit()
        self._input_busca.setPlaceholderText("Buscar no arquivo…")
        self._input_busca.setStyleSheet(
            "QLineEdit { background:#0a0a0a; color:#c9d1d9;"
            " border:1px solid #222; border-radius:3px;"
            " padding:2px 6px; font-size:10px; }"
            "QLineEdit:focus { border-color:#4ec994; }"
        )
        self._input_busca.textChanged.connect(self._ao_buscar)
        lay_busca.addWidget(self._input_busca)

        self._lbl_resultados = QLabel("")
        self._lbl_resultados.setStyleSheet("color:#555; font-size:9px; min-width:60px;")
        lay_busca.addWidget(self._lbl_resultados)

        vlay.addWidget(barra_busca)

        # Viewer (readonly) com numeração de linha embutida
        self._viewer = QTextEdit()
        self._viewer.setReadOnly(True)
        self._viewer.setLineWrapMode(QTextEdit.NoWrap)
        self._viewer.setPlaceholderText(
            "Clique num commit para ver o arquivo naquele momento."
        )
        self._viewer.setStyleSheet(
            "QTextEdit { background:#0a0a0a; color:#c9d1d9; border:none;"
            f" font-family:'{FONTE_MONO}','Consolas',monospace;"
            " font-size:10px; padding:4px; }"
        )
        vlay.addWidget(self._viewer, 1)

        splitter.addWidget(viewer_panel)
        splitter.setSizes([160, 260])

        lay.addWidget(splitter, 1)

        # Barra inferior
        bar = QWidget()
        bar.setStyleSheet("background:#0a0a0a; border-top:1px solid #1a1a1a;")
        lay_bar = QHBoxLayout(bar)
        lay_bar.setContentsMargins(6, 4, 6, 4)
        lay_bar.setSpacing(4)

        btn_att = _botao("Atualizar")
        btn_att.setIcon(icone_tema("mdi.refresh"))
        btn_att.setIconSize(QSize(14, 14))
        btn_att.setFixedHeight(22)
        btn_att.clicked.connect(self._atualizar)
        lay_bar.addWidget(btn_att)
        lay_bar.addStretch()

        lay.addWidget(bar)

    # ── Busca e exibição de conteúdo ─────────────────────────────────

    def _ao_buscar(self, texto: str):
        """Destaca todas as ocorrências do texto buscado no viewer."""
        from PySide6.QtGui import QTextCharFormat
        from PySide6.QtWidgets import QTextEdit as _QTE

        cursor = self._viewer.textCursor()
        cursor.setPosition(0)
        self._viewer.setTextCursor(cursor)

        selecoes = []
        termo = texto.strip()
        if termo:
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#3a3a00"))
            fmt.setForeground(QColor("#ffee44"))
            doc = self._viewer.document()
            c   = doc.find(termo, 0)
            while not c.isNull():
                sel        = _QTE.ExtraSelection()
                sel.cursor = c
                sel.format = fmt
                selecoes.append(sel)
                c = doc.find(termo, c)
            if selecoes:
                self._viewer.setTextCursor(selecoes[0].cursor)
            total = len(selecoes)
            self._lbl_resultados.setText(
                f"{total} resultado{'s' if total != 1 else ''}"
            )
        else:
            self._lbl_resultados.setText("")

        self._viewer.setExtraSelections(selecoes)

    def _set_conteudo(self, cabecalho: str, conteudo: str):
        """
        Exibe o conteúdo no viewer com numeração de linha.
        Cabeçalho (hash/data/mensagem) aparece sem número — separado por ─.
        """
        self._input_busca.clear()
        self._lbl_resultados.setText("")

        linhas = conteudo.splitlines()
        total  = len(linhas)
        larg   = max(len(str(total)), 3)   # mínimo 3 dígitos

        linhas_num = [
            f"{str(i).rjust(larg)} │ {linha}"
            for i, linha in enumerate(linhas, 1)
        ]
        self._viewer.setPlainText(cabecalho + "\n".join(linhas_num))

    # ── API pública ───────────────────────────────────────────────────

    def set_arquivo_ativo(self, caminho_projeto: str, caminho_arquivo: str):
        """
        Chamado por GitUIProjeto.set_arquivo_ativo() e por
        _atualizar_aba_por_indice(4) quando a aba "Arquivo" é selecionada.
        """
        self._caminho_projeto = caminho_projeto
        self._arquivo_ativo   = caminho_arquivo

        if caminho_arquivo:
            nome = os.path.basename(caminho_arquivo)
            self._lbl_arquivo.setText(f"  {nome}")
        else:
            self._lbl_arquivo.setText("  Nenhum arquivo aberto no editor")

        self._atualizar()

    # ── Lógica interna ────────────────────────────────────────────────

    def _atualizar(self):
        self._lista.clear()
        self._viewer.clear()

        if not self._caminho_projeto or not self._arquivo_ativo:
            return

        try:
            rel = os.path.relpath(
                self._arquivo_ativo, self._caminho_projeto
            ).replace("\\", "/")
        except ValueError:
            self._terminal.erro("Arquivo fora do repositório")
            return

        def _buscar():
            return self._git.historico_arquivo(self._caminho_projeto, rel, limite=60)

        def _exibir(versoes):
            if versoes is None:
                self._terminal.erro("Erro ao carregar histórico do arquivo")
                return
            if not versoes:
                vazio = QListWidgetItem("  Nenhum commit encontrado para este arquivo")
                vazio.setForeground(QColor("#444"))
                self._lista.addItem(vazio)
                return
            for v in versoes:
                texto = f"  {v['quando']}   {v['mensagem']}"
                item  = QListWidgetItem(texto)
                item.setData(Qt.UserRole, v)
                item.setForeground(QColor(COR_GIT_TEXTO_NEUTRO))
                self._lista.addItem(item)

        p = _em_thread(_buscar, _exibir, self)
        self._pontes.append(p)

    def _ao_selecionar(self, item: QListWidgetItem):
        versao = item.data(Qt.UserRole)
        if not versao:
            return

        try:
            rel = os.path.relpath(
                self._arquivo_ativo, self._caminho_projeto
            ).replace("\\", "/")
        except ValueError:
            return

        hash_v    = versao.get("hash_completo", "")
        hash_c    = versao.get("hash_curto", "")
        quando    = versao.get("quando", "")
        mensagem  = versao.get("mensagem", "")

        self._viewer.setPlainText("Carregando…")

        def _buscar():
            # usa o caminho do arquivo NAQUELE commit (pode ter sido renomeado)
            caminho_no_commit = versao.get("caminho_no_commit", rel)
            return self._git.conteudo_arquivo_em(
                self._caminho_projeto, hash_v, caminho_no_commit
            )

        def _exibir(conteudo):
            if conteudo is None:
                self._viewer.setPlainText(
                    f"Não foi possível recuperar o arquivo no commit {hash_c}.\n"
                    "O arquivo pode ter sido renomeado ou movido antes desse commit."
                )
                self._terminal.erro(
                    f"Falha ao recuperar {os.path.basename(self._arquivo_ativo)} "
                    f"em {hash_c}"
                )
                return
            cab = (
                f"# {hash_c}  │  {quando}\n"
                f"# {mensagem}\n"
                f"{'─' * 60}\n"
            )
            self._set_conteudo(cab, conteudo)
            self._terminal.ok(
                f"Exibindo {os.path.basename(self._arquivo_ativo)} em {hash_c}"
            )

        p = _em_thread(_buscar, _exibir, self)
        self._pontes.append(p)
