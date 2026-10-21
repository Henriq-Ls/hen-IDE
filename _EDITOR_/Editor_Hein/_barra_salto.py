# 📁 _EDITOR_/Editor/_barra_salto.py
"""_BarraSalto — 3 botões ⤒/⊟/⤓ no canto superior direito do viewport."""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore    import Qt
from _CONFIGURA_.gerenciador_tema import tema_global
from _EDITOR_.Ui.numeros_linha import ReguaErros

_HANDLE_OUTLINE_LARGURA = 4

class _BarraSalto(QWidget):
    """3 botões ⤒/⊟/⤓ no canto superior direito do viewport (8.2)."""

    def __init__(self, editor):
        super().__init__(editor.viewport())
        self._editor = editor
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(1)
        self._btn_topo = self._btn("⤒", "Ir para a primeira linha")
        self._btn_meio = self._btn("⊟", "Ir para o meio do arquivo")
        self._btn_fim  = self._btn("⤓", "Ir para a última linha")
        for b in (self._btn_topo, self._btn_meio, self._btn_fim):
            lay.addWidget(b)
        self._btn_topo.clicked.connect(lambda: editor.ir_para_linha(1))
        self._btn_meio.clicked.connect(self._ir_meio)
        self._btn_fim.clicked.connect(
            lambda: editor.ir_para_linha(editor.document().blockCount())
        )
        self.adjustSize()
        self._aplicar_tema()
        self.raise_()

    def _btn(self, texto: str, tooltip: str) -> QPushButton:
        b = QPushButton(texto, self)
        b.setToolTip(tooltip)
        b.setFixedSize(22, 20)

        return b

    def _ir_meio(self):
        total = self._editor.document().blockCount()
        self._editor.ir_para_linha(max(1, total // 2))

    def _aplicar_tema(self):
        try:
            t      = tema_global()
            fundo  = t.cor("editor.fundo",             "#1e1e2e")
            texto  = t.cor("editor.numero_linha",       "#7094A1")
            hover  = t.cor("editor.linha_ativa_fundo",  "#1a1a2e")
        except Exception:
            fundo, texto, hover = "#1e1e2e", "#7094A1", "#1a1a2e"
        self.setStyleSheet(
            f"QWidget {{ background: {fundo}CC; border-radius: 4px; }}"
            f"QPushButton {{ background: transparent; color: {texto};"
            f"  border: none; font-size: 13px; border-radius: 2px; }}"
            f"QPushButton:hover {{ background: {hover}; }}"
        )

    def posicionar(self):
        vp  = self._editor.viewport()
        out = getattr(self._editor, '_largura_outline', 0)
        hd  = _HANDLE_OUTLINE_LARGURA
        extra = out + hd + ReguaErros.LARGURA
        self.adjustSize()
        x = vp.width() - self.width() - extra - 6
        self.move(max(0, x), 4)
        self.raise_()
