# 📁 _EDITOR_/Outline/delegate_outline.py
# -*- coding: utf-8 -*-
import re
from PySide6.QtCore    import Qt
from PySide6.QtGui     import QColor, QPainter, QFontMetrics
from PySide6.QtWidgets import QStyledItemDelegate, QApplication, QStyle
from _CONFIGURA_ import (
    COR_OUTLINE_ITEM,
    COR_SINTAXE_PALAVRA_CHAVE, COR_SINTAXE_FUNCAO,
    COR_SINTAXE_VARIAVEL_ESPECIAL, COR_SINTAXE_VARIAVEL, COR_SINTAXE_PONTUACAO,
)
from _CONFIGURA_.gerenciador_tema import tema_global

class _DelegateOutline(QStyledItemDelegate):
    def __init__(self, parent=None, fold_state_fn=None):
        super().__init__(parent)
        self._fold_state_fn = fold_state_fn   # (linha: int) -> True/False/None

    # ⚠️  função grande (110 linhas)
    def paint(self, painter: QPainter, option, index):
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else QApplication.style()
        option.text = ""
        style.drawControl(QStyle.CE_ItemViewItem, option, painter, option.widget)

        texto_completo = index.data(Qt.DisplayRole) or ""

        t = tema_global()

        def cor(chave, fallback):
            v = t.cor(chave, "")

            return v if v else fallback

        c_kw    = cor("editor.sintaxe.palavra_chave",     COR_SINTAXE_PALAVRA_CHAVE)
        c_fn    = cor("editor.sintaxe.funcao",            COR_SINTAXE_FUNCAO)
        c_self  = cor("editor.sintaxe.variavel_especial", COR_SINTAXE_VARIAVEL_ESPECIAL)
        c_arg   = cor("editor.sintaxe.variavel",          COR_SINTAXE_VARIAVEL)
        c_pontu = cor("editor.sintaxe.pontuacao",         COR_SINTAXE_PONTUACAO)

        rect  = option.rect
        fonte = option.font
        fm    = QFontMetrics(fonte)
        x     = rect.x() + 4
        y     = rect.y() + (rect.height() - fm.height()) // 2 + fm.ascent()

        painter.save()
        painter.setFont(fonte)

        def escrever(txt, cor_hex):
            nonlocal x
            if not txt:

                return

            painter.setPen(QColor(cor_hex))
            painter.drawText(x, y, txt)
            x += fm.horizontalAdvance(txt)

        m_class = re.match(r'^(class)\s+(\w+)$', texto_completo)
        m_def   = re.match(r'^(async def|def)\s+(\w+)\(([^)]*)\)$', texto_completo)

        if m_class:
            escrever("class ", c_kw)
            escrever(m_class.group(2), c_kw)

        elif m_def:
            kw     = m_def.group(1)
            nome   = m_def.group(2)
            args_s = m_def.group(3)

            escrever(kw + " ", c_kw)
            escrever(nome, c_fn)
            escrever("(", c_pontu)

            args = [a.strip() for a in args_s.split(",")] if args_s.strip() else []
            for i, arg in enumerate(args):
                if not arg:
                    continue
                virgula = ", " if i < len(args) - 1 else ""
                if arg in ("self", "cls"):
                    escrever(arg, c_self)
                elif ":" in arg:
                    partes = arg.split(":", 1)
                    escrever(partes[0], c_arg)
                    escrever(":", c_pontu)
                    escrever(partes[1].strip(), c_arg)
                elif "=" in arg:
                    partes = arg.split("=", 1)
                    escrever(partes[0], c_arg)
                    escrever("=", c_pontu)
                    escrever(partes[1].strip(), c_arg)
                else:
                    escrever(arg, c_arg)
                if virgula:
                    escrever(virgula, c_pontu)

            escrever(")", c_pontu)

        else:
            brush    = index.data(Qt.ForegroundRole)
            cor_item = brush.color().name() if brush else COR_OUTLINE_ITEM
            escrever(texto_completo, cor_item)

        painter.restore()

        # ── Ícone ▼/▶ de fold no hover (8.1) ──────────────────────────
        if (self._fold_state_fn
                and bool(option.state & QStyle.State_MouseOver)):
            tree    = option.widget
            item_ot = (tree.itemFromIndex(index)
                       if tree and hasattr(tree, 'itemFromIndex') else None)
            if item_ot and hasattr(item_ot, 'linha') and item_ot.linha > 0:
                estado = self._fold_state_fn(item_ot.linha)
                if estado is not None:
                    icone = "▶" if estado else "▼"
                    _fm   = QFontMetrics(option.font)
                    xi    = option.rect.right() - _fm.horizontalAdvance(icone) - 8
                    yi    = (option.rect.y()
                             + (option.rect.height() + _fm.ascent() - _fm.descent()) // 2)
                    painter.save()
                    try:
                        _cor = tema_global().qcolor("editor.numero_linha", "#7094A1")
                    except Exception:
                        _cor = QColor("#7094A1")
                    painter.setFont(option.font)
                    painter.setPen(_cor)
                    painter.drawText(xi, yi, icone)
                    painter.restore()
        # ── fim ícone fold ─────────────────────────────────────────────

    def sizeHint(self, option, index):
        return super().sizeHint(option, index)
