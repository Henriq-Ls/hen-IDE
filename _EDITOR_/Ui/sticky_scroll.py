# 📁 _EDITOR_/Ui/sticky_scroll.py
# -*- coding: utf-8 -*-
"""
StickyScroll — overlay de contexto (def/class atual) no topo do editor.

╔══════════════════════════════════════════════════════════════════════════╗
║  ⚠️  ZONA CRÍTICA — NÃO MEXA SEM LER ESTE AVISO                         ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  _ultima_altura_margem (int, init=-1)                                    ║
║     Cache da última altura usada em setViewportMargins. ESSENCIAL para   ║
║     evitar a cascade de scroll:                                          ║
║       valueChanged → _ao_rolar → _atualizar → setViewportMargins         ║
║       → viewport resize → ensureCursorVisible → valueChanged → loop      ║
║     _pos_mostrar só chama atualizar_margem se a altura MUDOU.            ║
║     O path de hide() também só chama se não estava já em 0.             ║
║     Remover ou ignorar esse cache REINTRODUZ o bug de salto no scroll.  ║
║                                                                          ║
║  _ultima_linha_visivel (int, init=-1)                                    ║
║     Guard que impede _atualizar de rodar se firstVisibleBlock não mudou. ║
║     Sem ele, qualquer cursorPositionChanged (ex: digitação) recalcula    ║
║     o contexto inteiro desnecessariamente.                               ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
import re
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from _CONFIGURA_.gerenciador_tema import tema_global
_RE_CONTEXTO = re.compile(r"^\s*(async\s+def|def|class)\s+(\w+)")

class StickyScroll(QWidget):
    def __init__(self, editor):
        super().__init__(editor)          # filho do editor, não do viewport
        self._editor = editor
        self._labels: list[QLabel] = []

        t = tema_global().dados()
        fundo = t.get("editor", {}).get("fundo_calha", "#0d0d0d")
        self.setAttribute(Qt.WA_StyledBackground, True)
        r = int(fundo[1:3], 16)
        g = int(fundo[3:5], 16)
        b = int(fundo[5:7], 16)

        cor_borda = t.get("interface", {}).get("fundo_aba_ativa", "#2a2a3a")
        self.setStyleSheet(f"""
                    StickyScroll {{
                        background-color: rgba({r},{g},{b},220);
                        border-top: none;
                        border-left: none;
                        border-right: none;
                        border-bottom: 2px solid {cor_borda};
                    }}
                """)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 2, 8, 2)
        self._layout.setSpacing(0)
        self.hide()
        self._ultima_linha_visivel: int = -1
        self._ultima_altura_margem: int = -1  # cache: evita setViewportMargins redundante
        editor.cursorPositionChanged.connect(self._atualizar)
        editor.updateRequest.connect(lambda rect, dy: self._reposicionar())
        editor.verticalScrollBar().valueChanged.connect(self._ao_rolar)

    def _reposicionar(self): # Largura: até o outline (não passa por cima dele).
        largura = self._editor.width()
        if hasattr(self._editor, '_outline') and self._editor._outline.isVisible():
            outline_x = self._editor._outline.x()
            if outline_x > 0:
                largura = outline_x
        self.setGeometry(0, 0, largura, self.height())
        self.raise_()

    # ⚠️  função grande (104 linhas)
    def _atualizar(self):
        editor = self._editor
        if not editor.isVisible():

            return

        if editor.document().blockCount() <= 1 and not editor.toPlainText().strip():

            return

        linha_atual = editor.firstVisibleBlock().blockNumber()
        if linha_atual == self._ultima_linha_visivel:

            return  # posição de scroll não mudou — pula recálculo

        self._ultima_linha_visivel = linha_atual

        contextos = []
        bloco = editor.document().findBlockByNumber(0)
        ultimo_indent = -1

        while bloco.isValid() and bloco.blockNumber() < linha_atual:
            texto = bloco.text()
            m = _RE_CONTEXTO.match(texto)
            if m:
                indent = len(texto) - len(texto.lstrip())
                entrada = (indent, texto.strip(), bloco.blockNumber())
                if indent > ultimo_indent:
                    contextos.append(entrada)
                    ultimo_indent = indent
                else:
                    contextos = [c for c in contextos if c[0] < indent]
                    contextos.append(entrada)
                    ultimo_indent = indent
            bloco = bloco.next()

        # limpa labels antigos
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self._labels.clear()

        if not contextos:
            self.hide()
            if self._ultima_altura_margem != 0:
                self._ultima_altura_margem = 0
                self._editor.metricas.atualizar_margem(topo=0)
            self._editor._atualizar_geometria_outline()

            return

        fonte = QFont(editor.font())
        fonte.setPointSize(max(8, editor.font().pointSize() + 1))

        sintaxe = tema_global().dados().get("editor", {}).get("sintaxe", {})
        cor_kw  = sintaxe.get("palavra_chave", "#c678dd")
        cor_fn  = sintaxe.get("funcao", "#61afef")
        cor_txt = sintaxe.get("variavel", "#e0e0e0")

        for indent, texto, num in contextos[:3]:
            m2   = _RE_CONTEXTO.match(texto)
            kw   = m2.group(1) if m2 else ""
            nome = m2.group(2) if m2 else texto
            resto = texto[len(kw) + len(nome):] if m2 else ""
            pad  = '  ' * (indent // 4)

            lbl = QLabel()
            lbl.setFont(fonte)
            cor_nome = cor_kw if kw.strip() == "class" else cor_fn
            lbl.setText(f'{pad}<span style="color:{cor_kw}">{kw} </span>'
                        f'<span style="color:{cor_nome}">{nome}</span>'
                        f'<span style="color:{cor_txt}">{resto}</span>')
            lbl.setTextFormat(Qt.RichText)
            lbl.setStyleSheet("background: transparent; padding: 1px 0; border: none;")
            lbl.setCursor(Qt.PointingHandCursor)
            lbl.setToolTip(f"Ir para linha {num + 1}")
            def _clicar(e, n=num): # ir_para_linha agora usa scroll-to-top (não centerCursor), # portanto não precisamos mais esconder o StickyScroll antes # de navegar — o widget atualiza sozinho via cursorPositionChanged.
                self._editor.ir_para_linha(n + 1)
            lbl.mousePressEvent = _clicar
            self._layout.addWidget(lbl)
            self._labels.append(lbl)

        self._reposicionar()
        self.setVisible(True)
        self.raise_()

        def _pos_mostrar():
            self.adjustSize()
            self._reposicionar()
            self.raise_()
            nova_h = self.height()
            # Só chama setViewportMargins se a altura realmente mudou.
            # Chamadas redundantes redimensionam o viewport, disparam
            # ensureCursorVisible e causam saltos no scroll (BUG 3).
            if nova_h != self._ultima_altura_margem:
                self._ultima_altura_margem = nova_h
                self._editor.metricas.atualizar_margem(topo=nova_h)
            self._editor._atualizar_geometria_outline()

        QTimer.singleShot(0, _pos_mostrar)
        editor.viewport().update()

    def _ao_rolar(self):
        if self._editor.isVisible():
            self._atualizar()
