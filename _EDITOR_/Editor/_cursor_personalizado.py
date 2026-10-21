# 📁 _EDITOR_/Editor/_cursor_personalizado.py
"""_GerenciadorCursorPersonalizado — forma, piscar e animação do cursor."""
from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtGui  import QPainter
from _CONFIGURA_.gerenciador_tema import tema_global

class _GerenciadorCursorPersonalizado(QObject):
    """
    Gerencia forma e piscar do cursor para um CodeEditor.
    Ativo quando forma='sublinhado' OU piscar_estilo='suave'.
    Demais combinacoes usam setCursorWidth + CursorFlashTime nativos.

    Formas:  barra | linha | bloco | sublinhado
    Piscar:  normal(500ms) | fase(350ms) | suave(senoidal 16ms) | fixo
    """

    def __init__(self, editor):
        super().__init__(editor)
        self._editor     = editor
        self._forma      = "barra"
        self._largura    = 2
        self._piscar     = True
        self._estilo     = "normal"
        self._cor_hex    = "#aeafad"
        self._opacidade  = 1.0
        self._fase       = 0.0
        self._timer      = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # 💡 cor_opc = Literal["#aeafad"] ← defina os valores válidos
    def configurar(self, forma: str, largura: int, piscar: bool, estilo: str, cor: str = "#aeafad"):
        self._forma   = forma
        self._largura = max(1, largura)
        self._piscar  = piscar
        self._estilo  = estilo
        self._cor_hex = cor or "#aeafad"
        self._fase    = 0.0
        # SEMPRE custom draw — garante que cursor_cor de configurar.json[ui] seja aplicado
        self._editor.setCursorWidth(0)
        if not piscar or estilo == "fixo":
            self._opacidade = 1.0
            self._timer.stop()
        else:
            intervalo = 16 if estilo == "suave" else (350 if estilo == "fase" else 500)
            self._timer.start(intervalo)

    def _tick(self):
        import math
        if not self._editor.hasFocus():
            self._opacidade = 1.0
            self._editor.viewport().update()

            return

        if not self._piscar or self._estilo == "fixo":
            self._opacidade = 1.0
            self._timer.stop()

            return

        if self._estilo == "suave":
            self._fase      += 0.10
            self._opacidade  = (math.sin(self._fase) + 1.0) / 2.0
        else:
            self._opacidade = 0.0 if self._opacidade > 0.5 else 1.0
        self._editor.viewport().update()

    @staticmethod
    def _draw_cursor_shape(painter, forma, largura, cor, rect, char_w, char_sob=None, font=None):
        """
        Pipeline único de desenho de cursor — usado por principal E extras.
        Elimina divergência futura: qualquer mudança de forma/cor aqui
        se aplica automaticamente a todos os cursores.

        painter:  QPainter ativo
        forma:    'bloco' | 'sublinhado' | qualquer outro → barra
        largura:  espessura da barra (px)
        cor:      QColor com alpha já configurado
        rect:     QRect onde desenhar (cursorRect do editor)
        char_w:   largura do caractere M em px
        char_sob: caractere sob o cursor (str ou None) — usado pelo bloco
        font:     QFont do editor — usado pelo bloco para repintar o char
        """
        from PySide6.QtGui import QPen, QBrush, QColor
        from PySide6.QtCore import QRect as _QRect
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, False)
        if forma == "sublinhado":
            painter.setPen(QPen(cor, 2))
            y = rect.bottom() - 1
            painter.drawLine(rect.left(), y, rect.left() + char_w, y)
        elif forma == "bloco":
            painter.setBrush(QBrush(cor))
            painter.setPen(Qt.NoPen)
            painter.drawRect(_QRect(rect.left(), rect.top(), char_w, rect.height()))
            if char_sob and char_sob not in ('\n', '\r', '\x00', '\u2029', '\u2028') and font:
                lum = cor.red() * 299 + cor.green() * 587 + cor.blue() * 114
                cor_txt = QColor(0, 0, 0) if lum > 128000 else QColor(255, 255, 255)
                cor_txt.setAlphaF(cor.alphaF())
                painter.setPen(QPen(cor_txt))
                painter.setFont(font)
                painter.drawText(
                    _QRect(rect.left(), rect.top(), char_w, rect.height()),
                    Qt.AlignLeft | Qt.AlignVCenter, char_sob
                )
        else:  # barra (padrão)
            painter.setPen(QPen(cor, largura))
            x = rect.left() + largura // 2
            painter.drawLine(x, rect.top(), x, rect.bottom())
        painter.restore()

    # ⚠️  except genérico vazio
    def desenhar(self, painter, editor):
        """Cursor principal — respeita opacidade da animação de piscar."""
        if self._opacidade <= 0.01:

            return

        if not editor.hasFocus():

            return

        from PySide6.QtGui import QColor
        try:
            cor = QColor(self._cor_hex)
            if not cor.isValid():
                cor = QColor(tema_global().cor("editor.cursor", "#aeafad"))
        except Exception:
            cor = QColor("#aeafad")
        cor.setAlphaF(self._opacidade)
        rect   = editor.cursorRect()
        fm     = editor.fontMetrics()
        char_w = max(8, fm.horizontalAdvance("M"))
        char_sob = None
        if self._forma == "bloco":
            try:
                char_sob = editor.document().characterAt(editor.textCursor().position())
            except Exception:
                pass
        self._draw_cursor_shape(
            painter, self._forma, self._largura, cor, rect, char_w,
            char_sob, editor.font() if self._forma == "bloco" else None
        )

    # ⚠️  except genérico vazio
    def desenhar_extra(self, painter, editor, cursor):
        """
        Cursor extra — mesmo pipeline de _draw_cursor_shape, alpha fixo 0.85
        (sem animação de piscar). Chamado por _CodeLensOverlay._desenhar_cursor.
        """
        from PySide6.QtGui import QColor
        try:
            cor = QColor(self._cor_hex)
            if not cor.isValid():
                cor = QColor("#aeafad")
        except Exception:
            cor = QColor("#aeafad")
        cor.setAlphaF(0.85)
        try:
            rect = editor.cursorRect(cursor)
        except Exception:

            return

        fm     = editor.fontMetrics()
        char_w = max(8, fm.horizontalAdvance("M"))
        char_sob = None
        if self._forma == "bloco":
            try:
                char_sob = editor.document().characterAt(cursor.position())
            except Exception:
                pass
        self._draw_cursor_shape(
            painter, self._forma, self._largura, cor, rect, char_w,
            char_sob, editor.font() if self._forma == "bloco" else None
        )
