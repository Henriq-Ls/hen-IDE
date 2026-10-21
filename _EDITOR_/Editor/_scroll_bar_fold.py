# 📁 _EDITOR_/Editor/_scroll_bar_fold.py
"""_ScrollBarFold — overlay transparente no scrollbar vertical com marcas de fold."""
from PySide6.QtWidgets import QWidget
from PySide6.QtGui     import QPainter, QColor
from PySide6.QtCore    import Qt
from _CONFIGURA_.gerenciador_tema import tema_global

class _ScrollBarFold(QWidget):
    """Overlay transparente sobre o scrollbar vertical — marca os folds (8.3)."""

    _MARCA_H = 3

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._cor_marca = QColor("#4a90d9")
        self._aplicar_tema()

    def _aplicar_tema(self):
        try:
            self._cor_marca = tema_global().qcolor("editor.busca_ativa", "#4a90d9")
        except Exception:
            self._cor_marca = QColor("#4a90d9")

    def paintEvent(self, event):
        regs  = getattr(self._editor, '_fold_regions', [])
        if not regs:

            return

        total = max(1, self._editor.document().blockCount())
        proporcoes = [
            r.start_block.blockNumber() / total
            for r in regs if r.collapsed
        ]
        if not proporcoes:

            return

        painter = QPainter(self)
        h = self.height()
        for p in proporcoes:
            y = int(p * h)
            painter.fillRect(2, max(0, y - 1), self.width() - 4, self._MARCA_H, self._cor_marca)
        painter.end()

    def atualizar_e_posicionar(self):
        sb = self._editor.verticalScrollBar()
        if not sb.isVisible():
            self.hide()

            return

        geo = sb.geometry()
        self.setGeometry(geo)
        self.show()
        self.raise_()
        self.update()
