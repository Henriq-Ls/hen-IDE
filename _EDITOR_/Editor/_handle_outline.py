# 📁 _EDITOR_/Editor/_handle_outline.py
"""_HandleOutline — alça de 4 px entre ReguaErros e PainelOutline."""
from PySide6.QtCore    import QObject, QEvent, Qt
from PySide6.QtWidgets import QWidget
from _CONFIGURA_.gerenciador_tema import tema_global

_HANDLE_OUTLINE_LARGURA = 4

class _HandleOutline(QObject):
    """
    Alça de 4px posicionada entre ReguaErros e PainelOutline.
    Arrastar → redimensiona o outline em tempo real.
    Duplo clique → toggle expandir / recolher.
    """

    def __init__(self, editor: "CodeEditor"):
        from PySide6.QtWidgets import QWidget
        super().__init__(editor)
        self._editor = editor
        self._arrastando     = False
        self._x_inicio       = 0.0
        self._largura_inicio = 0

        self._widget = QWidget(editor)
        self._widget.setFixedWidth(_HANDLE_OUTLINE_LARGURA)
        self._widget.setCursor(Qt.SplitHCursor)
        self._widget.setMouseTracking(True)
        self._widget.installEventFilter(self)
        self._atualizar_cor()

    def _atualizar_cor(self):
        try:
            cor = tema_global().cor("interface.borda", "#2a2a3a")
        except Exception:
            cor = "#2a2a3a"
        self._widget.setStyleSheet(f"background: {cor};")

    def setGeometry(self, x: int, y: int, w: int, h: int):
        self._widget.setGeometry(x, y, w, h)

    def raise_(self):
        self._widget.raise_()

    def show(self):
        self._widget.show()

    def hide(self):
        self._widget.hide()

    def eventFilter(self, obj, event):
        if obj is not self._widget:

            return False

        t = event.type()

        if t == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._arrastando     = True
            self._x_inicio       = event.globalPosition().x()
            self._largura_inicio = self._editor._largura_outline

            return True

        if t == QEvent.MouseMove and self._arrastando:
            from _CONFIGURA_ import OUTLINE_LARGURA_MIN, OUTLINE_LARGURA_MAX
            # O drag não pode ir abaixo de OUTLINE_LARGURA_MIN: o PainelOutline
            # tem setMinimumWidth(OUTLINE_LARGURA_MIN), então se _largura_outline
            # ficasse menor que isso (ex: o antigo _DRAG_MIN = 12), o Qt força a
            # largura real do widget de volta pro mínimo (250) SEM avisar essa
            # classe — handle, barra de status e régua de erros continuavam
            # posicionados como se a outline tivesse a largura pequena, enquanto
            # ela renderizava com 250px de verdade, engolindo tudo por cima.
            # Fechar totalmente só existe via duplo-clique/atalho (vai pra 0).
            delta = int(self._x_inicio - event.globalPosition().x())
            nova  = max(OUTLINE_LARGURA_MIN, min(OUTLINE_LARGURA_MAX, self._largura_inicio + delta))
            self._editor._largura_outline = nova
            self._editor._outline.show()
            self._editor._atualizar_geometria_outline()

            return True

        if t == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            self._arrastando = False

            return True

        if t == QEvent.MouseButtonDblClick:
            from _CONFIGURA_ import OUTLINE_LARGURA_MIN
            if self._editor._largura_outline == 0:
                self._editor._largura_outline = OUTLINE_LARGURA_MIN
                self._editor._outline.show()
            else:
                self._editor._largura_outline = 0
                self._editor._outline.hide()
            self._editor._atualizar_geometria_outline()

            return True

        return False
