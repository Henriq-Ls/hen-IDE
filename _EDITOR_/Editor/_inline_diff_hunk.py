# 📁 _EDITOR_/Editor/_inline_diff_hunk.py
"""
_InlineDiffHunk — diff git embutido DENTRO do editor, estilo Zed/VS Code.

Como funciona o "empurrar o texto pra baixo":
  QPlainTextEdit não suporta widgets entre linhas nativamente, mas
  QTextBlockFormat.setBottomMargin(N) adiciona N pixels de espaço vazio
  ABAIXO de um bloco específico do documento — sem inserir texto, sem
  afetar o histórico de undo (desabilitamos undo/redo em torno da
  operação de margem). O widget _InlineDiffHunk fica ancorado nesse
  espaço vazio, filho do próprio viewport, e se move junto com o scroll
  via reposicionar().

  Antes: widget flutuava POR CIMA do texto abaixo da linha clicada.
  Depois: o texto abaixo é empurrado para baixo e o widget ocupa o espaço.

Ativação: clique na barra colorida da calha git.
  - Clicar de novo na mesma linha fecha.
  - Clicar em outro hunk troca (fecha o anterior, abre o novo).
  - Esc fecha (tratado no Editor/__init__.py).
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtGui     import QFont, QTextCursor
from _LOG_.log import log

_ARQ = "_inline_diff_hunk.py"

_COR_FUNDO     = "#1a1a2a"
_COR_BORDA     = "#3a3a5a"
_COR_REMOVIDA  = "#3d1f1f"
_COR_ADICION   = "#1f3d1f"
_COR_TXT_REM   = "#e06c75"
_COR_TXT_ADD   = "#4ec994"
_COR_TXT_HDR   = "#7094A1"
_FONTE_NOME    = "Consolas"
_FONTE_TAM     = 10
_MAX_LINHAS    = 20


class _InlineDiffHunk(QWidget):
    """Painel de diff embutido no viewport — empurra o texto pra baixo."""

    def __init__(self, editor):
        super().__init__(editor.viewport())
        self._editor          = editor
        self._hunk_atual: dict | None = None
        self._linha_atual: int = 0
        # Margem que aplicamos ao bloco atual (px); guardada para restaurar.
        self._margem_aplicada: float = 0.0
        # Margem original do bloco antes de mexermos nela.
        self._margem_original: float = 0.0

        self._fonte = QFont(_FONTE_NOME, _FONTE_TAM)
        self._fonte.setStyleHint(QFont.Monospace)

        self.setObjectName("_inline_diff_hunk")
        self.setStyleSheet(f"""
            QWidget#_inline_diff_hunk {{
                background: {_COR_FUNDO};
                border: 1px solid {_COR_BORDA};
                border-radius: 0px;
            }}
        """)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self.hide()

    # ══════════════════════════════════════════════════════════════════
    # API pública
    # ══════════════════════════════════════════════════════════════════

    def mostrar_para_linha(self, linha_1based: int, hunk: dict):
        """Preenche o painel, reserva espaço no documento e ancora."""
        if not hunk.get("removidas") and not hunk.get("adicionadas"):
            self.fechar()
            return

        # Fecha hunk anterior (limpa margem do bloco antigo) antes de abrir novo
        if self._linha_atual and self._linha_atual != linha_1based:
            self._limpar_margem_bloco()

        self._hunk_atual  = hunk
        self._linha_atual = linha_1based

        # 1. Preenche os labels e mede a altura necessária
        self._preencher(hunk)
        self.setFixedWidth(self._editor.viewport().width())
        self.adjustSize()

        # 2. Reserva espaço no documento: bottom margin = altura do painel
        #    Isso empurra o texto abaixo pra baixo, criando o "slot" vazio.
        self._aplicar_margem_bloco(self.height())

        # 3. Posiciona dentro do slot e exibe
        self._reposicionar()
        self.show()
        self.raise_()

    def hunk_ativo(self) -> dict | None:
        return self._hunk_atual if self.isVisible() else None

    def reposicionar(self):
        """Chamado em resize/scroll — mantém o painel dentro do slot."""
        if not self.isVisible() or not self._linha_atual:
            return
        # Atualiza largura (janela pode ter sido redimensionada)
        nova_largura = self._editor.viewport().width()
        if self.width() != nova_largura:
            self.setFixedWidth(nova_largura)
            self.adjustSize()
            # Se a altura mudou, atualiza a margem do bloco
            if abs(self.height() - self._margem_aplicada) > 1:
                self._aplicar_margem_bloco(self.height())
        self._reposicionar()

    def fechar(self):
        self._limpar_margem_bloco()
        self._hunk_atual  = None
        self._linha_atual = 0
        self.hide()

    # ══════════════════════════════════════════════════════════════════
    # Margem de bloco — cria/remove o espaço vazio no documento
    # ══════════════════════════════════════════════════════════════════

    def _aplicar_margem_bloco(self, altura_px: float):
        """Adiciona bottom-margin ao bloco da linha clicada.

        Usamos setUndoRedoEnabled(False/True) em torno da operação para
        que a mudança de margem NÃO entre no histórico de undo do usuário —
        é metadado de UI, não edição de conteúdo.
        """
        bloco = self._editor.document().findBlockByNumber(self._linha_atual - 1)
        if not bloco.isValid():
            return

        cursor = QTextCursor(bloco)
        fmt = cursor.blockFormat()
        self._margem_original = fmt.bottomMargin()
        fmt.setBottomMargin(altura_px)
        self._margem_aplicada = altura_px

        doc = self._editor.document()
        doc.setUndoRedoEnabled(False)
        cursor.setBlockFormat(fmt)
        doc.setUndoRedoEnabled(True)

    def _limpar_margem_bloco(self):
        """Restaura a margem original do bloco (remove o espaço reservado)."""
        if not self._linha_atual or not self._margem_aplicada:
            return
        bloco = self._editor.document().findBlockByNumber(self._linha_atual - 1)
        if not bloco.isValid():
            self._margem_aplicada = 0.0
            return

        cursor = QTextCursor(bloco)
        fmt = cursor.blockFormat()
        fmt.setBottomMargin(self._margem_original)
        self._margem_aplicada = 0.0

        doc = self._editor.document()
        doc.setUndoRedoEnabled(False)
        cursor.setBlockFormat(fmt)
        doc.setUndoRedoEnabled(True)

    # ══════════════════════════════════════════════════════════════════
    # Posicionamento
    # ══════════════════════════════════════════════════════════════════

    def _reposicionar(self):
        """Ancora o painel no início do espaço reservado (logo abaixo do
        conteúdo da linha, antes da margem que criamos)."""
        editor = self._editor
        bloco  = editor.document().findBlockByNumber(self._linha_atual - 1)
        if not bloco.isValid():
            self.fechar()
            return

        geo = editor.blockBoundingGeometry(bloco).translated(editor.contentOffset())
        # geo.bottom() = fundo do bloco INCLUINDO a bottom-margin que aplicamos.
        # Queremos o INÍCIO do espaço reservado = fundo sem a margem.
        y = int(geo.bottom() - self._margem_aplicada)
        self.move(0, y)

    # ══════════════════════════════════════════════════════════════════
    # Conteúdo
    # ══════════════════════════════════════════════════════════════════

    def _preencher(self, hunk: dict):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        removidas   = hunk.get("removidas", [])
        adicionadas = hunk.get("adicionadas", [])

        for txt in removidas[:_MAX_LINHAS]:
            self._linha_label(f"- {txt}", _COR_REMOVIDA, _COR_TXT_REM)
        if len(removidas) > _MAX_LINHAS:
            self._linha_label(
                f"  … mais {len(removidas) - _MAX_LINHAS} linha(s) removida(s)",
                _COR_FUNDO, _COR_TXT_HDR, negrito=False,
            )

        # Adicionadas só quando é "added puro" — modified já mostra o antes
        # em vermelho; o depois fica visível no próprio texto do editor.
        if not removidas:
            for txt in adicionadas[:_MAX_LINHAS]:
                self._linha_label(f"+ {txt}", _COR_ADICION, _COR_TXT_ADD)
            if len(adicionadas) > _MAX_LINHAS:
                self._linha_label(
                    f"  … mais {len(adicionadas) - _MAX_LINHAS} linha(s)",
                    _COR_FUNDO, _COR_TXT_HDR, negrito=False,
                )

        self.adjustSize()

    def _linha_label(self, texto: str, fundo: str, cor_txt: str, negrito: bool = True):
        lbl = QLabel(texto.rstrip() or " ")
        lbl.setFont(self._fonte)
        lbl.setWordWrap(False)
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lbl.setStyleSheet(
            f"background:{fundo}; color:{cor_txt}; padding:2px 8px;"
            f"{'font-weight:bold;' if negrito else ''}"
            "border:none; border-radius:0px;"
        )
        self._layout.addWidget(lbl)
