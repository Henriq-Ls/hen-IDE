# 📁 _APP_/zona_drop_split.py
"""
ZonaDropSplit — overlay semi-transparente exibido durante o drag de uma aba.
Mostra as zonas de drop em uma única fileira horizontal, lado a lado,
sempre crescendo para a direita: "Dividir à direita" e "Janela flutuante".

Uso:
    overlay = ZonaDropSplit(parent=area_editor_widget)
    overlay.zona_escolhida.connect(callback)   # callback(zona: str)
    overlay.show_over(area_editor_widget)
    overlay.grabMouse()
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore    import Qt, Signal, QRect, QSize, QPoint
from PySide6.QtGui     import QPainter, QColor, QPen, QFont
# Tamanho dos ícones de zona em px
_ZONA_SZ = 80
# Espaço entre zonas na fileira horizontal
_ZONA_GAP = 14
# Ordem de exibição — sempre da esquerda para a direita
_ORDEM = ['right', 'float']
# Ícone Unicode por zona
_ICONE = {
    'right':  '▶',
    'float':  '⧉',   # janela flutuante
}
# Legenda por zona
_LEGENDA = {
    'right':  'Dividir\nà direita',
    'float':  'Janela\nflutuante',
}

class ZonaDropSplit(QWidget):
    """Overlay de drop zones para dividir o editor em painéis (fileira horizontal)."""

    zona_escolhida = Signal(str)   # 'right' | 'float'
    cancelado      = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.SubWindow)
        self._zona_hover: str | None = None
        self._zonas: dict[str, QRect] = {}

    # ── API pública ─────────────────────────────────────────────────────────
    def show_over(self, target: QWidget):
        """Mostra o overlay cobrindo exatamente target (deve ser um QWidget pai)."""
        self.setParent(target)
        self.resize(target.size())
        self.move(0, 0)
        self._calcular_zonas()
        self.raise_()
        self.show()
        self.grabMouse()
        self.setFocus()

    # ── Zonas ────────────────────────────────────────────────────────────────
    def _calcular_zonas(self):
        w, h = self.width(), self.height()
        sz   = _ZONA_SZ
        n    = len(_ORDEM)
        largura_total = n * sz + (n - 1) * _ZONA_GAP
        x0 = (w - largura_total) // 2
        y0 = (h - sz) // 2
        # Fileira horizontal única — cada zona nova fica sempre à direita da anterior.
        self._zonas = {
            nome: QRect(x0 + i * (sz + _ZONA_GAP), y0, sz, sz)
            for i, nome in enumerate(_ORDEM)
        }

    def _zona_em(self, pos: QPoint) -> str | None:
        for nome, rect in self._zonas.items():
            if rect.contains(pos):
                return nome

        return None

    # ── Eventos de mouse ────────────────────────────────────────────────────
    def mouseMoveEvent(self, event):
        nova = self._zona_em(event.position().toPoint())
        if nova != self._zona_hover:
            self._zona_hover = nova
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.releaseMouse()
            zona = self._zona_em(event.position().toPoint())
            self.hide()
            if zona:
                self.zona_escolhida.emit(zona)
            else:
                self.cancelado.emit()
            self.deleteLater()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.releaseMouse()
            self.cancelado.emit()
            self.hide()
            self.deleteLater()

    # ── Pintura ─────────────────────────────────────────────────────────────
    def resizeEvent(self, event):
        self._calcular_zonas()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Fundo escurecido semi-transparente
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        fonte_icone  = QFont()
        fonte_icone.setPointSize(22)
        fonte_legenda = QFont()
        fonte_legenda.setPointSize(8)

        for nome, rect in self._zonas.items():
            hover = (nome == self._zona_hover)
            alpha = 220 if hover else 160

            # Fundo da zona
            cor_fundo = QColor(40, 120, 220, alpha) if nome != 'float' \
                        else QColor(80, 60, 180, alpha)
            painter.setBrush(cor_fundo)
            pen = QPen(QColor(140, 200, 255, 200), 2)
            if hover:
                pen = QPen(QColor(255, 255, 255, 240), 2)
            painter.setPen(pen)
            painter.drawRoundedRect(rect, 8, 8)

            # Ícone Unicode
            painter.setFont(fonte_icone)
            painter.setPen(QColor(255, 255, 255, 230))
            icone_rect = QRect(rect.x(), rect.y(), rect.width(), rect.height() * 2 // 3)
            painter.drawText(icone_rect, Qt.AlignCenter, _ICONE[nome])

            # Legenda
            painter.setFont(fonte_legenda)
            painter.setPen(QColor(200, 230, 255, 200))
            leg_rect = QRect(rect.x(), rect.y() + rect.height() * 2 // 3,
                             rect.width(), rect.height() // 3)
            painter.drawText(leg_rect, Qt.AlignCenter | Qt.TextWordWrap,
                             _LEGENDA[nome])

        painter.end()
