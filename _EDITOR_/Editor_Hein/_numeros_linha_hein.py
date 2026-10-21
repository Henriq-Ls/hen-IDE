# 📁 _EDITOR_/Editor_Hein/_numeros_linha_hein.py
"""
AreaNumerosLinhaHein — subclasse de AreaNumerosLinha adaptada ao Editor Caderno.

Modificações em relação à classe pai:
  _es_dobravel() — suporte à extensão .hein (dobramento por indentação).
  paintEvent()   — após o paint do pai, desenha as pautas horizontais sobre
                   o gutter, incluindo as linhas abaixo do último bloco.
"""
from PySide6.QtGui     import QPainter, QPen, QColor
from PySide6.QtWidgets import QPlainTextEdit
from ..Ui.numeros_linha import AreaNumerosLinha
from _CONFIGURA_ import COR_PALTA_PAPEL

class AreaNumerosLinhaHein(AreaNumerosLinha):
    """
    Gutter do Editor Caderno.

    Herda TODO o comportamento de AreaNumerosLinha (pintura, breakpoints,
    bookmarks, git diff, hover, fold arrows) e sobrescreve:
      • _es_dobravel — dobramento .hein por indentação
      • paintEvent   — pautas horizontais sobre o gutter
    """

    # ── Pautas no gutter ──────────────────────────────────────────────────────

    def paintEvent(self, event):
        # 1. Deixa o pai desenhar: números, setas, breakpoints, bookmarks…
        super().paintEvent(event)

        # 2. Sobrepõe as pautas horizontais (mesmo espaçamento do viewport)
        ed      = self.editor
        cor     = QColor(getattr(ed, '_cor_pauta',COR_PALTA_PAPEL))
        largura = self.width()
        altura  = self.height()

        # viewportMargins().top() converte coordenadas de viewport → gutter
        margem_topo = ed.viewportMargins().top()
        offset      = ed.contentOffset()

        painter = QPainter(self)
        pen = QPen(cor)
        pen.setWidth(1)
        painter.setPen(pen)

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

        # Item-6: BP decorativo (ghost) em linhas dobráveis que não têm BP real
        from PySide6.QtGui import QBrush
        x_bp = getattr(self, 'larg_git', 0) + getattr(self, 'pad', 2)
        larg_g = getattr(self, 'larg_guiter', 15)
        cor_bp_ghost = QColor(getattr(self, 'cor_bp', None) or QColor('#e06c75'))
        cor_bp_ghost.setAlpha(45)
        cx = x_bp + larg_g // 2
        r  = larg_g - 6
        ext = '.hein'
        bloco2 = ed.firstVisibleBlock()
        while bloco2.isValid():
            geo2        = ed.blockBoundingGeometry(bloco2).translated(ed.contentOffset())
            topo2       = int(geo2.top()) + margem_topo
            if topo2 > altura:
                break
            if bloco2.isVisible():
                # Dobrável e sem BP real → ghost circle
                prox = bloco2.next()
                prox_txt = prox.text() if prox.isValid() else ""
                tem_bp = self._indice_bp_do_bloco(bloco2) != -1
                if (not tem_bp
                        and self._es_dobravel(bloco2.text(), ext, prox_txt)):
                    h2 = int(geo2.height())
                    cy = topo2 + h2 // 2
                    painter.setBrush(QBrush(cor_bp_ghost))
                    painter.setPen(cor_bp_ghost.lighter(130))
                    painter.drawEllipse(cx - r // 2, cy - r // 2, r, r)
            bloco2 = bloco2.next()

        # Item-1: wrap visual — apaga número do pai nas sub-linhas e deixa em branco
        # (primeira linha lógica já tem número do pai; sub-linhas ficam vazias)
        if ed.lineWrapMode() != QPlainTextEdit.LineWrapMode.NoWrap:
            lh = ed.fontMetrics().lineSpacing()
            if lh > 0:
                x_bp   = getattr(self, 'larg_git', 0) + getattr(self, 'pad', 2)
                x_num  = x_bp + getattr(self, 'larg_guiter', 15) + getattr(self, 'pad', 2)
                x_fim  = self.width()
                painter.setPen(self.cor_fundo)  # mesma cor do fundo = apaga
                painter.setBrush(self.cor_fundo)
                bloco3 = ed.firstVisibleBlock()
                while bloco3.isValid():
                    geo3 = ed.blockBoundingGeometry(bloco3).translated(ed.contentOffset())
                    t3   = int(geo3.top()) + margem_topo
                    if t3 > altura:
                        break
                    if bloco3.isVisible():
                        n_rows = max(1, round(geo3.height() / lh))
                        if n_rows > 1:
                            # Apaga a área de número nas sub-linhas 1..n-1
                            from PySide6.QtCore import QRect as _QR
                            for sub in range(1, n_rows):
                                y_sub = t3 + sub * lh
                                painter.fillRect(_QR(x_num, y_sub, x_fim - x_num, lh),
                                                 self.cor_fundo)
                    bloco3 = bloco3.next()

        # Item-11: '···' no gutter para blocos de FoldRegion colapsada
        fold_regs = getattr(ed, '_fold_regions', [])
        if fold_regs:
            from PySide6.QtCore import QRect as _QR2
            cor_reticencias = QColor(getattr(ed, '_cor_pauta', None) or COR_PALTA_PAPEL)
            painter.setPen(cor_reticencias)
            for reg in fold_regs:
                if not reg.collapsed:
                    continue
                sb = reg.start_block
                if not sb.isValid() or not sb.isVisible():
                    continue
                geo_f = ed.blockBoundingGeometry(sb).translated(ed.contentOffset())
                t_f   = int(geo_f.top()) + margem_topo
                h_f   = int(geo_f.height())
                # Escreve '···' alinhado à direita do gutter
                painter.drawText(_QR2(0, t_f, self.width() - 2, h_f),
                                 0x0002,  # Qt.AlignRight
                                 '···')

        painter.end()

    # ── Dobramento .hein ──────────────────────────────────────────────────────

    def _es_dobravel(self, texto: str, extensao: str, proximo_txt: str = "") -> bool:
        """
        Assinatura compatível com o pai: _es_dobravel(texto, ext, proximo_txt).

        Para extensões != '.hein': delega ao pai integralmente.
        Para '.hein': a linha é dobrável se:
          1. Não é vazia e começa na coluna 0 (é um tópico), E
          2. O proximo_txt não-vazio começa com espaço ou tab (tem recuo maior).
        """
        if extensao != '.hein':
            return super()._es_dobravel(texto, extensao, proximo_txt)

        # Linha vazia nunca inicia um bloco dobrável
        s = texto.rstrip('\r\n')
        if not s:
            return False

        # Col-0 (tópico) ou prefixo ▸ (sub-bloco, Item-7b) são cabeças dobráveis
        stripped = s.lstrip()
        eh_cabeca   = s[0] not in (' ', '	')
        eh_subbloco = bool(stripped) and stripped[0] == '▸'
        if not (eh_cabeca or eh_subbloco):
            return False

        # proximo_txt já vem pronto do pai — sem precisar buscar no documento
        p = proximo_txt.rstrip('\r\n')
        return bool(p) and p[0] in (' ', '	')
