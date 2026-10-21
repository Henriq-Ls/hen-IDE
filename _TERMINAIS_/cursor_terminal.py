# 📁 _TERMINAIS_/cursor_terminal.py
"""
CursorTerminal — cursor personalizado (forma + piscar + cor) para qualquer
QPlainTextEdit ou QTextEdit de terminal da hein IDE.

SEMPRE usa custom draw para garantir que cursor_cor de configurar.json[ui]
seja aplicado universalmente — nunca usa o cursor nativo do Qt.

Uso:
    ct = CursorTerminal(widget)
    ct.configurar("barra", 2, True, "normal", "#4fc3f7")
"""
import math
from PySide6.QtCore    import QObject, QTimer, QEvent, Qt
from PySide6.QtGui     import QPainter, QColor, QPen, QBrush
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit

class CursorTerminal(QObject):
    """
    Cursor personalizado para widgets de terminal.
    Instala eventFilter no viewport do widget alvo.
    """

    def __init__(self, widget):
        super().__init__(widget)
        self._widget    = widget
        self._forma     = "barra"
        self._largura   = 2
        self._piscar    = True
        self._estilo    = "normal"
        self._cor_hex   = "#aeafad"
        self._opacidade = 1.0
        self._fase      = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        if hasattr(widget, "viewport"):
            widget.viewport().installEventFilter(self)

    # 💡 cor_opc = Literal["#aeafad"] ← defina os valores válidos
    def configurar(self, forma: str, largura: int, piscar: bool, estilo: str, cor: str = "#aeafad"):
        self._forma   = forma
        self._largura = max(1, largura)
        self._piscar  = piscar
        self._estilo  = estilo
        self._cor_hex = cor or "#aeafad"
        self._fase    = 0.0

        # SEMPRE custom draw — garante cursor_cor universal
        self._widget.setCursorWidth(0)
        if not piscar or estilo == "fixo":
            self._opacidade = 1.0
            self._timer.stop()
        else:
            intervalo = 16 if estilo == "suave" else (350 if estilo == "fase" else 500)
            self._timer.start(intervalo)

    def _tick(self):
        if not self._widget.hasFocus():
            self._opacidade = 1.0
            if hasattr(self._widget, "viewport"):
                self._widget.viewport().update()

            return

        if self._estilo == "suave":
            self._fase      += 0.10
            self._opacidade  = (math.sin(self._fase) + 1.0) / 2.0
        else:
            self._opacidade = 0.0 if self._opacidade > 0.5 else 1.0
        if hasattr(self._widget, "viewport"):
            self._widget.viewport().update()

    def eventFilter(self, obj, event):
        try:
            vp = self._widget.viewport()
        except RuntimeError:

            return False

        if obj is not vp:

            return False

        if event.type() == QEvent.Paint:
            if isinstance(self._widget, QPlainTextEdit):
                QPlainTextEdit.paintEvent(self._widget, event)
            else:
                QTextEdit.paintEvent(self._widget, event)
            self._desenhar()

            return True

        return False

    def _desenhar(self):
        if self._opacidade <= 0.01:

            return

        widget = self._widget
        if not widget.hasFocus():

            return

        try:
            cor = QColor(self._cor_hex)
            if not cor.isValid():
                cor = QColor("#aeafad")
        except Exception:
            cor = QColor("#aeafad")
        cor.setAlphaF(self._opacidade)

        rect   = widget.cursorRect()
        fm     = widget.fontMetrics()
        char_w = max(8, fm.horizontalAdvance("M"))

        painter = QPainter(widget.viewport())
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, False)

        if self._forma == "sublinhado":
            painter.setPen(QPen(cor, 2))
            y = rect.bottom() - 1
            painter.drawLine(rect.left(), y, rect.left() + char_w, y)
        elif self._forma == "bloco":
            from PySide6.QtCore import QRect
            painter.setBrush(QBrush(cor))
            painter.setPen(Qt.NoPen)
            painter.drawRect(QRect(rect.left(), rect.top(), char_w, rect.height()))
        else:
            painter.setPen(QPen(cor, self._largura))
            x = rect.left() + self._largura // 2
            painter.drawLine(x, rect.top(), x, rect.bottom())

        painter.restore()
        painter.end()
