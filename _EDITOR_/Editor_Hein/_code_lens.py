# 📁 _EDITOR_/Editor_Hein/_code_lens.py
"""
Gerenciador de Paint do viewport + overlay de pautas sobre o gutter.

Este arquivo foi reescrito do zero para o Editor Caderno.
NÃO é o code lens original (que mostrava "· N usos").

_CodeLensOverlay
  – QObject instalado como eventFilter no viewport.
  – Intercepta QEvent.Paint e executa numa única janela de paint:
      1. QPlainTextEdit.paintEvent()  → texto + fundo (C++ nativo)
      2. _desenhar_pautas()           → linhas horizontais + margem vermelha
      3. _desenhar_cursor()           → cursor personalizado + multi-cursor
  – checar_clique() / checar_hover() → stubs (sem itens de code lens no caderno)

_PautaGutterOverlay
  – QWidget transparente sobre area_numeros (o gutter).
  – Estende as pautas horizontais da esquerda até o gutter.
  – sync_geometry() mantém o overlay colado sobre o gutter.

_extrair_nome_lens
  – Stub de compatibilidade (não usada no caderno).
"""
from __future__ import annotations
from PySide6.QtCore  import QEvent, QObject, QPoint, Qt
from PySide6.QtGui   import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget
from _CONFIGURA_ import COR_GUTER_CURSOR , COR_PALTA_PAPEL, LARGURA_MARGEM_GUTTER, COLUNA_LIMITE_CADERNO

# ──────────────────────────────────────────────────────────────────────────────
# Stub de compatibilidade
# ──────────────────────────────────────────────────────────────────────────────

def _extrair_nome_lens(item) -> str:          # noqa: ANN001
    """Stub — code lens não existe no Editor Caderno."""
    return ""


# ──────────────────────────────────────────────────────────────────────────────
# _CodeLensOverlay
# ──────────────────────────────────────────────────────────────────────────────

class _CodeLensOverlay(QObject):
    """
    Event filter instalado no viewport do Editor Caderno.

    Intercepta QEvent.Paint para desenhar as pautas e a margem vermelha
    DEPOIS do paint nativo do QPlainTextEdit, na mesma janela de paint.
    """

    _COR_MARGEM = QColor(COR_GUTER_CURSOR)   # linha vermelha vertical — fixo, não configurável
    
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor
        editor.viewport().installEventFilter(self)

    # ── Event filter ──────────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self._editor.viewport() and event.type() == QEvent.Paint:
            # 1. Paint nativo (texto + fundo)
            from PySide6.QtWidgets import QPlainTextEdit
            QPlainTextEdit.paintEvent(self._editor, event)

            # 2. Pautas + margem vermelha
            painter = QPainter(self._editor.viewport())
            try:
                self._desenhar_pautas(painter)
                self._desenhar_cursor(painter)
            finally:
                painter.end()

            return True   # evento consumido

        return False

    # ── Pautas ────────────────────────────────────────────────────────────────

    def _desenhar_pautas(self, painter: QPainter):
        ed  = self._editor
        vp  = ed.viewport()
        cor = QColor(getattr(ed, '_cor_pauta', COR_PALTA_PAPEL))

        pen = QPen(cor)
        pen.setWidth(1)
        painter.setPen(pen)

        largura = vp.width()
        altura  = vp.height()

        bloco   = ed.firstVisibleBlock()
        offset  = ed.contentOffset()

        while bloco.isValid():
            geo = ed.blockBoundingGeometry(bloco).translated(offset)
            topo = int(geo.top())
            if topo > altura:
                break
            if bloco.isVisible():
                # Linha de pauta na base de cada bloco
                # Usa geo.height() — mais preciso que fontMetrics quando há line-spacing
                y = topo + int(geo.height()) - 1
                painter.drawLine(0, y, largura, y)
            bloco = bloco.next()

        # Pautas extras abaixo do último bloco até o final do viewport
        if bloco.isValid() is False and 'y' in dir():
            passo = int(ed.fontMetrics().lineSpacing())
            if passo > 0:
                y_extra = y + passo
                while y_extra < altura:
                    painter.drawLine(0, y_extra, largura, y_extra)
                    y_extra += passo

        # Linha vermelha de margem (borda esquerda do viewport — estilo caderno)
        pen_margem = QPen(self._COR_MARGEM)
        pen_margem.setWidth(LARGURA_MARGEM_GUTTER)
        painter.setPen(pen_margem)
        painter.drawLine(0, 0, 0, altura)

        # Item-4: Linha guia cinza fixa na coluna COLUNA_LIMITE_CADERNO (hard wrap).
        # Visível sempre que o arquivo for .hein; cor = mesma das pautas horizontais.
        if getattr(ed, '_eh_hein', lambda: False)():
            _fm_guia = ed.fontMetrics()
            _char_w  = max(1, _fm_guia.averageCharWidth())
            _doc_mar = int(ed.document().documentMargin())
            _scroll  = int(ed.contentOffset().x())
            _x_fixo  = _doc_mar + _scroll + _char_w * COLUNA_LIMITE_CADERNO
            if 0 < _x_fixo < largura:
                _pen_fixo = QPen(cor)   # mesma cor cinza das pautas
                _pen_fixo.setWidth(1)
                painter.setPen(_pen_fixo)
                painter.drawLine(_x_fixo, 0, _x_fixo, altura)
        # Linha guia dinâmica — alinhada com a borda esquerda do menu flutuante.
        # Mantida para indicar quando texto fica coberto pelo menu.
        menu = getattr(ed, '_float_menu', None)
        if menu is not None and menu.isVisible():
            x_guia = menu.x() - 4   # 4 px de folga antes do menu
            if x_guia > 0:
                pen_guia = QPen(cor)   # mesma cor das pautas horizontais
                pen_guia.setWidth(1)
                painter.setPen(pen_guia)
                painter.drawLine(x_guia, 0, x_guia, altura)

    # ── Cursor ────────────────────────────────────────────────────────────────

    def _desenhar_cursor(self, painter: QPainter):
        """Delega ao gerenciador de cursor personalizado, se presente."""
        mgr = getattr(self._editor, '_cursor_mgr', None)
        if mgr is None:
            return
        fn = getattr(mgr, 'desenhar', None) or getattr(mgr, 'paint', None)
        if callable(fn):
            fn(painter, self._editor)

    # ── Stubs de interação (sem code lens no caderno) ─────────────────────────

    def checar_clique(self, pos: QPoint) -> bool:
        """Sem itens de code lens — nunca consome o clique."""
        return False

    def checar_hover(self, pos: QPoint) -> None:
        """Sem itens de code lens — nenhuma ação de hover."""
        pass


# ──────────────────────────────────────────────────────────────────────────────
# _PautaGutterOverlay
# ──────────────────────────────────────────────────────────────────────────────

class _PautaGutterOverlay(QWidget):
    """
    Widget transparente sobre o gutter (area_numeros).

    Desenha as mesmas pautas horizontais do viewport, estendendo-as até
    a borda esquerda do editor (gutter incluso).
    """

    def __init__(self, editor):
        super().__init__(editor.area_numeros)
        self._editor = editor
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.sync_geometry()
        self.show()

    def sync_geometry(self):    
        """Cobre exatamente o gutter (area_numeros)."""
        gutter = self._editor.area_numeros
        self.setGeometry(0, 0, gutter.width(), gutter.height())
        self.raise_()
        self.update()

    def paintEvent(self, event):
        ed     = self._editor
        cor    = QColor(getattr(ed, '_cor_pauta', COR_PALTA_PAPEL))
        largura = self.width()
        altura  = self.height()

        # Offset entre o topo do gutter (y=0 do editor) e o topo do viewport
        # O viewport começa abaixo das margens superiores (sticky scroll, etc.)
        margem_topo = ed.viewportMargins().top()

        painter = QPainter(self)
        pen = QPen(cor)
        pen.setWidth(1)
        painter.setPen(pen)

        bloco  = ed.firstVisibleBlock()
        offset = ed.contentOffset()

        y     = -1
        bloco = ed.firstVisibleBlock()
        while bloco.isValid():
            geo         = ed.blockBoundingGeometry(bloco).translated(offset)
            topo_gutter = int(geo.top()) + margem_topo
            if topo_gutter > altura:
                break
            if bloco.isVisible():
                y = topo_gutter + int(geo.height()) - 1
                painter.drawLine(0, y, largura, y)
            bloco = bloco.next()

        # Pautas extras abaixo do último bloco até o fundo do gutter
        if y >= 0:
            passo = int(ed.fontMetrics().lineSpacing())
            if passo > 0:
                y_extra = y + passo
                while y_extra < altura:
                    painter.drawLine(0, y_extra, largura, y_extra)
                    y_extra += passo

        painter.end()
