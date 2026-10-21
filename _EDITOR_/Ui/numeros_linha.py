# 📁 _EDITOR_/Ui/numeros_linha.py
# -*- coding: utf-8 -*-
"""
Widget de numeração de linhas — calha completa da IDE hein.

╔══════════════════════════════════════════════════════════════════════════╗
║  ⚠️  ZONAS CRÍTICAS — NÃO MEXA SEM LER ESTE AVISO                       ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  1. wheelEvent                                                           ║
║     Redireciona o scroll para editor.viewport() via QCoreApplication.    ║
║     Sem isso, o mouse sobre a calha não scrolla o editor (Qt consome     ║
║     o evento silenciosamente). NÃO remova nem troque por wheelEvent do   ║
║     editor — tem que ir pro viewport(), não pro editor pai.              ║
║                                                                          ║
║  2. mousePressEvent — zona da seta de dobramento                         ║
║     USA _y_para_linha + zona X calculada na hora, NÃO _fold_rects.      ║
║     Motivo: _fold_rects armazena coordenadas Y do paintEvent. Após um    ║
║     scroll sem repaint, esses valores ficam desatualizados e os cliques  ║
║     na seta falham. NUNCA substitua por iteração de _fold_rects aqui.   ║
║                                                                          ║
║  3. _hover_seta (bool)                                                   ║
║     Flag que indica se o mouse está ESPECIFICAMENTE sobre a zona X da    ║
║     seta (não apenas na linha dobrável). Usada para pintar o background  ║
║     arredondado no hover. Deve ser resetada em leaveEvent.               ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝

Zonas (esquerda → direita):
  [git] [pad] [BP/BM] [pad] [números auto] [seta] [pad] | código

Recursos:
  ✅ Números de linha (linha atual em negrito/azul)
  ✅ Code Folding — setas ▼▶ visíveis só no hover ou quando recolhidas
  ✅ Breakpoints — clique na zona esquerda → bolinha vermelha
  ✅ Bookmarks   — Ctrl+F2 toggle, F2 próximo, Shift+F2 anterior
  ✅ Git changes  — barra colorida mais larga na borda direita
  ✅ Erros/Avisos — indicados APENAS na ReguaErros (barra lateral direita)
  ✅ Hover        — fundo diferenciado ao passar o mouse
  ✅ Fold p/ .py .pyw .json .html .htm .xml .yaml .yml .js .ts .jsx .tsx .css .scss
"""
import os
import re
from .regua_erros import ReguaErros
from PySide6.QtCore    import Qt, Signal, QRect
from PySide6.QtGui     import QPainter, QFont, QColor, QCursor, QPen, QBrush, QPainterPath
from PySide6.QtWidgets import QWidget
from _LOG_.log import log
from _CONFIGURA_ import (
    LARGURA_GIT,    # fallback
    PADDINGS,       # fallback
    LARGURA_GUITER, # fallback
    LARGURA_SETA,   # fallback
    SETA_ESTILO,    # fallback
)

_RE_FOLDABLE = re.compile(
    r"^\s*(def |async def |class |if |elif |else\s*:|for |while |try\s*:|"
    r"except|finally\s*:|with )"
)

_ARQ = "numeros_linha.py"

_ESTILOS_SETA = {
    "triangulo": ("▸", "▾"),
    "chevron":   ("›", "∨"),
    "classico":  ("+", "−"),
}

class AreaNumerosLinha(QWidget):
    """Calha completa com todos os indicadores visuais."""

    code_lens_clicado  = Signal(str, str, int)   # nome, arquivo, linha — emitido pelo overlay
    breakpoint_clicado = Signal(int)

    # ⚠️  função grande (53 linhas)
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

        # Cores — todas lidas do tema; cor_fundo, cor_texto e cor_texto_ativo
        # podem ser sobrescritas por Editor._configurar_tema após a construção (R2).
        try:
            from _CONFIGURA_.gerenciador_tema import tema_global
            _t = tema_global()
            self.cor_fundo        = _t.qcolor("editor.fundo_calha",        "#020202")
            self.cor_texto        = _t.qcolor("editor.numero_linha",        "#7094A1")
            self.cor_texto_ativo  = _t.qcolor("editor.numero_linha_ativo",  "#7B4F1D")
            self.cor_fundo_ativo  = _t.qcolor("editor.linha_ativa_fundo",   "#141414")
            self.cor_fundo_hover  = _t.qcolor("interface.fundo_item_hover", "#1a2e1a")
            self.cor_seta         = _t.qcolor("editor.numero_linha",        "#7094A1")
            self.cor_seta_hover   = _t.qcolor("editor.texto",               "#e0e0e0")
            self.cor_separador    = _t.qcolor("interface.borda",              "#1f3d1f")
            self.cor_git_added    = _t.qcolor("editor.git_adicionado",      "#4ec994")
            self.cor_git_modified = _t.qcolor("editor.git_modificado",      "#e5c07b")
            self.cor_git_deleted  = _t.qcolor("editor.git_deletado",        "#e06c75")
            self.cor_bp           = _t.qcolor("editor.erro",                "#e06c75")
            self.cor_multi        = _t.qcolor("editor.numero_linha_multi",  "#56b6c2")
        except Exception:
            self.cor_fundo        = QColor("#020202")
            self.cor_texto        = QColor("#7094A1")
            self.cor_texto_ativo  = QColor("#7B4F1D")
            self.cor_fundo_ativo  = QColor("#141414")
            self.cor_fundo_hover  = QColor("#1a2e1a")
            self.cor_seta         = QColor("#7094A1")
            self.cor_seta_hover   = QColor("#e0e0e0")
            self.cor_separador    = QColor("#1f3d1f")
            self.cor_git_added    = QColor("#4ec994")
            self.cor_git_modified = QColor("#e5c07b")
            self.cor_git_deleted  = QColor("#e06c75")
            self.cor_bp           = QColor("#e06c75")
            self.cor_multi        = QColor("#56b6c2")

        self._usages:      dict[int, int] = {}
        # IMP-03: breakpoints guardados como QTextBlock (não como número de
        # linha fixo) - blockNumber() é recalculado pelo Qt a cada edição,
        # então a bolinha acompanha a linha mesmo inserindo texto acima.
        self._breakpoints_blocks: list = []
        self._bookmarks:   set[int]       = set()
        self._linhas_multi: set[int]      = set()  # IMP-14: linhas com multi-cursor
        self._erros:       dict[int, str] = {}
        self._git:         dict[int, str] = {}

        self._fold_rects: list = []

        self._hover_fold:     int       = -1
        self._hover_linha:    int       = -1
        self._hover_seta:     bool      = False
        self._hover_git_hunk: list[int] = []

        # Hover popup estilo Zed — mostra linhas removidas do hunk
        self._git_hunks:       list      = []
        self._mapa_linha_hunk: dict      = {}  # linha_1based → índice em _git_hunks

        self._recarregar_gutter()
        self.setMouseTracking(True)

    def _recarregar_gutter(self):
        """Lê as dimensões do gutter do configurar.json (fallback = constantes do init)."""
        try:
            from _CONFIGURA_.gerenciador_configurar import config_global
            cfg = config_global()
            def _g(k, fb):  return int(cfg.obter("gutter", k, fb))
            def _gs(k, fb): return str(cfg.obter("gutter", k, fb))
        except Exception:
            def _g(k, fb):  return fb
            def _gs(k, fb): return fb
        self.larg_git    = _g("largura_git",    LARGURA_GIT)
        self.pad         = _g("paddings",       PADDINGS)
        self.larg_guiter = _g("largura_guiter", LARGURA_GUITER)
        self.larg_seta   = _g("largura_seta",   LARGURA_SETA)
        self.seta_estilo = _gs("seta_estilo",   SETA_ESTILO)

    # ══════════════════════════════════════════════════════════════════
    # API pública
    # ══════════════════════════════════════════════════════════════════

    def atualizar_usages(self, usages: dict[int, int]):
        self._usages = usages
        log.info(_ARQ, "atualizar_usages", f"{len(usages)} símbolos")
        if hasattr(self.editor, 'metricas'):
            self.editor.metricas.atualizar_margem()
        else:
            log.aviso(_ARQ, "atualizar_usages", "editor sem 'metricas'")
        self.update()
        self.editor.viewport().update()

    def set_erros(self, erros: dict[int, str]):
        self._erros = erros
        self.update()

    def set_git_changes(self, mudancas: dict[int, str]):
        self._git = mudancas
        self.update()

    def set_git_hunks(self, hunks: list):
        """Armazena hunks parseados para o popup de hover (estilo Zed)."""
        self._git_hunks = hunks
        self._mapa_linha_hunk = {}
        for i, h in enumerate(hunks):
            for l in h.get("linhas", []):
                self._mapa_linha_hunk[l] = i

    def toggle_bookmark(self, linha_1based: int):
        if linha_1based in self._bookmarks:
            self._bookmarks.discard(linha_1based)
            log.info(_ARQ, "toggle_bookmark", f"removido: linha {linha_1based}")
        else:
            self._bookmarks.add(linha_1based)
            log.info(_ARQ, "toggle_bookmark", f"adicionado: linha {linha_1based}")
        self.update()

    def _indice_bp_do_bloco(self, bloco) -> int:
        """Índice em _breakpoints_blocks que aponta pro mesmo QTextBlock que
        `bloco`, ou -1. blockNumber() é recalculado pelo Qt na hora, então a
        comparação segue a linha certa mesmo após inserir/remover texto acima."""
        self._breakpoints_blocks = [b for b in self._breakpoints_blocks if b.isValid()]
        alvo = bloco.blockNumber()
        for i, b in enumerate(self._breakpoints_blocks):
            if b.blockNumber() == alvo:

                return i

        return -1

    def set_breakpoints(self, bps: set) -> None:
        """Substitui o conjunto de breakpoints (restauro de estado)."""
        doc = self.editor.document()
        blocos = []
        for n in bps:
            b = doc.findBlockByNumber(n - 1)
            if b.isValid():
                blocos.append(b)
        self._breakpoints_blocks = blocos
        self.update()

    def get_breakpoints(self) -> set:
        """Retorna o conjunto de números de linha (1-based) que têm breakpoint
        no momento — recalculado a partir dos QTextBlocks guardados, então já
        reflete qualquer edição feita desde que o breakpoint foi criado."""
        self._breakpoints_blocks = [b for b in self._breakpoints_blocks if b.isValid()]

        return {b.blockNumber() + 1 for b in self._breakpoints_blocks}

    def set_bookmarks(self, bms: set) -> None:
        """Substitui o conjunto de bookmarks (restauro de estado)."""
        self._bookmarks = set(bms)
        self.update()

    # IMP-14 — linhas com cursor de multi-cursor ativo
    def set_linhas_multi(self, linhas: set) -> None:
        """Atualiza as linhas com cursor de multi-cursor (1-based). Passa set() para limpar."""
        self._linhas_multi = set(linhas)
        self.update()

    def get_bookmarks(self) -> set:
        """Retorna cópia do conjunto de bookmarks atual."""

        return set(self._bookmarks)

    def navegar_bookmark(self, direcao: int = 1):
        if not self._bookmarks:

            return

        linha_atual = self.editor.textCursor().blockNumber() + 1
        ordenados   = sorted(self._bookmarks)
        if direcao == 1:
            alvos = [l for l in ordenados if l > linha_atual]
            alvo  = alvos[0] if alvos else ordenados[0]
        else:
            alvos = [l for l in ordenados if l < linha_atual]
            alvo  = alvos[-1] if alvos else ordenados[-1]
        log.info(_ARQ, "navegar_bookmark", f"→ linha {alvo}")
        self.editor.ir_para_linha(alvo)

    # ══════════════════════════════════════════════════════════════════
    # Paint
    # ══════════════════════════════════════════════════════════════════

    # ⚠️  função grande (162 linhas)
    def paintEvent(self, event):
        self._fold_rects.clear()
        painter = QPainter(self)

        painter.fillRect(event.rect(), self.cor_fundo)

        # ── Separador vertical direito (original) ──
        painter.setPen(self.cor_separador)
        painter.drawLine(self.width() - 1, event.rect().top(),
                         self.width() - 1, event.rect().bottom())

        linha_atual = self.editor.textCursor().blockNumber()

        fonte_num       = QFont(self.editor.font()); fonte_num.setBold(False)
        fonte_num_ativo = QFont(fonte_num);          fonte_num_ativo.setBold(True)

        # Fonte da seta derivada da fonte do editor — sem hardcode (R2).
        # +1pt em relação ao editor, mínimo 9pt, para boa visibilidade.
        _fnt_editor = self.editor.font()
        tam_seta    = max(9, _fnt_editor.pointSize() + 1)
        fonte_seta  = QFont(_fnt_editor.family(), tam_seta)

        larg_digit   = self.editor.fontMetrics().horizontalAdvance('0')
        digitos      = max(2, len(str(self.editor.document().blockCount())))
        x_git        = 0
        x_bp_inicio  = self.larg_git + self.pad
        x_num_inicio = x_bp_inicio + self.larg_guiter + self.pad
        x_seta       = self.width() - self.pad - self.larg_seta
        x_num_fim    = x_seta - self.pad

        # Offset vertical do StickyScroll: o viewport começa h_sticky px abaixo
        # do topo do editor widget, mas o gutter começa em Y=0 do editor widget.
        # blockBoundingGeometry usa coords do viewport → precisa somar h_sticky.
        h_sticky = 0
        if hasattr(self.editor, '_sticky') and self.editor._sticky.isVisible():
            h_sticky = self.editor._sticky.height()

        # Extensão do arquivo — calculada uma vez por paintEvent
        ext    = self._extensao_atual(self.editor)
        bloco  = self.editor.firstVisibleBlock()
        numero = bloco.blockNumber()

        while bloco.isValid():
            # Posição real do bloco via blockBoundingGeometry (sem acumulação de drift).
            # Somamos h_sticky para converter coords do viewport → coords do gutter.
            geo          = self.editor.blockBoundingGeometry(bloco).translated(
                               self.editor.contentOffset())
            topo         = int(geo.top()) + h_sticky
            altura_bloco = int(geo.height())
            fundo        = topo + altura_bloco

            if topo > event.rect().bottom():
                break

            if bloco.isVisible() and fundo >= event.rect().top():
                l1    = numero + 1
                ativo = (numero == linha_atual)
                hover = (numero == self._hover_linha)
                texto = bloco.text()

                # Fundo: ativo tem prioridade sobre hover
                if ativo:
                    painter.fillRect(0, topo, self.width() - 1,
                                     altura_bloco, self.cor_fundo_ativo)
                elif hover:
                    painter.fillRect(0, topo, self.width() - 1,
                                     altura_bloco, self.cor_fundo_hover)

                tem_bp = self._indice_bp_do_bloco(bloco) != -1

                # Barra git (borda direita)
                git_tipo = self._git.get(l1)
                if git_tipo == "added":
                    painter.fillRect(x_git, topo, self.larg_git,
                                     altura_bloco, self.cor_git_added)
                elif git_tipo == "modified":
                    painter.fillRect(x_git, topo, self.larg_git,
                                     altura_bloco, self.cor_git_modified)
                elif git_tipo == "deleted":
                    painter.fillRect(x_git, topo, self.larg_git,
                                     3, self.cor_git_deleted)

                # Zona BP/BM: breakpoint (sólido) > ghost hover > bookmark
                cx  = x_bp_inicio + self.larg_guiter // 2
                cy  = topo + altura_bloco // 2
                if tem_bp:
                    r_bp = self.larg_guiter - 4
                    _cor_bp      = QColor(self.cor_bp); _cor_bp.setAlpha(255)
                    _cor_bp_brd  = QColor(self.cor_bp); _cor_bp_brd.setAlpha(180)
                    _cor_bp_brd  = _cor_bp_brd.lighter(130)
                    painter.setRenderHint(QPainter.Antialiasing, True)
                    painter.setBrush(QBrush(_cor_bp))
                    painter.setPen(QPen(_cor_bp_brd, 1))
                    painter.drawEllipse(cx - r_bp // 2, cy - r_bp // 2, r_bp, r_bp)
                    painter.setRenderHint(QPainter.Antialiasing, False)

                elif hover:
                    # Ghost breakpoint: indica que a zona é clicável
                    r_bp  = self.larg_guiter - 6
                    _ghost = QColor(self.cor_bp); _ghost.setAlpha(55)
                    painter.setRenderHint(QPainter.Antialiasing, True)
                    painter.setBrush(QBrush(_ghost))
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(cx - r_bp // 2, cy - r_bp // 2, r_bp, r_bp)
                    painter.setRenderHint(QPainter.Antialiasing, False)

                elif l1 in self._bookmarks:
                    painter.setPen(QColor("#4a9eff"))
                    painter.setFont(fonte_seta)
                    painter.drawText(
                        QRect(x_bp_inicio, topo, self.larg_guiter, altura_bloco),
                        Qt.AlignCenter, "◆"
                    )

                # Número de linha — vermelho bold se tem breakpoint;
                # teal bold se tem cursor de multi-cursor (IMP-14)
                if tem_bp:
                    painter.setFont(fonte_num_ativo)
                    painter.setPen(self.cor_bp)
                elif ativo:
                    painter.setFont(fonte_num_ativo)
                    painter.setPen(self.cor_texto_ativo)
                elif l1 in self._linhas_multi:
                    painter.setFont(fonte_num_ativo)
                    painter.setPen(self.cor_multi)
                else:
                    painter.setFont(fonte_num)
                    painter.setPen(self.cor_texto)
                # Bug #3 (word wrap): limita a rect de desenho à altura de UMA
                # linha para que o número fique alinhado ao topo do bloco
                # (primeira linha visual), mesmo quando o bloco está quebrado.
                _lh = self.editor.fontMetrics().height()
                painter.drawText(
                    QRect(x_num_inicio, topo, x_num_fim - x_num_inicio, _lh),
                    Qt.AlignHCenter | Qt.AlignVCenter,
                    str(l1),
                )

                # ──────────────────────────────────────────────────────────
                # ZONA DA SETA DE DOBRAMENTO
                # ⚠️  NÃO ALTERE os caracteres nem o rect_seta sem ler
                #    mousePressEvent — ele recalcula a zona X independentemente
                #    de _fold_rects para evitar cliques errados após scroll.
                # ──────────────────────────────────────────────────────────
                proximo_txt = bloco.next().text() if bloco.next().isValid() else ''
                if self._es_dobravel(texto, ext, proximo_txt):
                    recolhido  = self._bloco_recolhido(numero)
                    em_hover_f = (numero == self._hover_fold)
                    _sc, _sa   = _ESTILOS_SETA.get(self.seta_estilo, ("▸", "▾"))
                    seta_char  = _sc if recolhido else _sa
                    cor_s      = self.cor_seta_hover if (em_hover_f or recolhido) else self.cor_seta
                    rect_seta  = QRect(x_seta, topo, self.larg_seta, altura_bloco)
                    # Fundo leve quando mouse está sobre a seta
                    if em_hover_f and self._hover_seta:
                        _bg = QColor(self.cor_seta_hover)
                        _bg.setAlpha(40)
                        painter.setRenderHint(QPainter.Antialiasing, True)
                        painter.setBrush(QBrush(_bg))
                        painter.setPen(Qt.NoPen)
                        _r = rect_seta.adjusted(1, 2, -1, -2)
                        painter.drawRoundedRect(_r, 3, 3)
                        painter.setRenderHint(QPainter.Antialiasing, False)
                    painter.setPen(cor_s)
                    painter.setFont(fonte_seta)
                    painter.drawText(rect_seta, Qt.AlignCenter, seta_char)
                    self._fold_rects.append((rect_seta, l1))

            bloco   = bloco.next()
            numero += 1

    # ══════════════════════════════════════════════════════════════════
    # Mouse
    # ══════════════════════════════════════════════════════════════════

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            l1  = self._y_para_linha(pos.y())

            # Clique na barra colorida de diff git → abre/fecha o diff
            # embutido no próprio editor, estilo Zed (IMP — antes era popup).
            if pos.x() < self.larg_git and l1 > 0:
                idx_hunk = self._mapa_linha_hunk.get(l1)
                if idx_hunk is not None:
                    self._alternar_diff_inline(l1, self._git_hunks[idx_hunk])

                    return

            # Zona de breakpoint/bookmark
            _x_bp_press = self.larg_git + self.pad
            if _x_bp_press <= pos.x() <= _x_bp_press + self.larg_guiter:
                if l1 > 0:
                    bloco_clicado = self.editor.document().findBlockByNumber(l1 - 1)
                    idx = self._indice_bp_do_bloco(bloco_clicado)
                    if idx != -1:
                        del self._breakpoints_blocks[idx]
                        log.info(_ARQ, "mousePressEvent", f"breakpoint removido: linha {l1}")
                    else:
                        self._breakpoints_blocks.append(bloco_clicado)
                        log.info(_ARQ, "mousePressEvent", f"breakpoint adicionado: linha {l1}")
                    self.breakpoint_clicado.emit(l1)
                    self.update()

                return

            # ──────────────────────────────────────────────────────────────
            # Seta de dobramento — NÃO usa _fold_rects (stale após scroll).
            # Recalcula a zona X direto e obtém a linha via _y_para_linha.
            # ⚠️  Este é o ponto crítico do BUG da seta: _fold_rects tem
            #    coordenadas Y desatualizadas quando não houve repaint após
            #    scroll. Nunca substitua por iteração de _fold_rects aqui.
            # ──────────────────────────────────────────────────────────────
            x_seta_bp = self.width() - self.pad - self.larg_seta
            if pos.x() >= x_seta_bp:
                l1_fold    = self._y_para_linha(pos.y())
                if l1_fold > 0:
                    bloco_fold = self.editor.document().findBlockByNumber(l1_fold - 1)
                    ext_fold   = self._extensao_atual(self.editor)
                    proximo_fold = bloco_fold.next().text() if bloco_fold.next().isValid() else ''
                    if bloco_fold.isValid() and self._es_dobravel(bloco_fold.text(), ext_fold, proximo_fold):
                        log.info(_ARQ, "mousePressEvent", f"fold clicado: linha {l1_fold}")
                        if hasattr(self.editor, 'toggle_dobramento'):
                            self.editor.toggle_dobramento(l1_fold)

                        return

            # Clique no número de linha → mover cursor para essa linha
            if l1 > 0:
                log.info(_ARQ, "mousePressEvent", f"navegar: linha {l1}")
                self.editor.ir_para_linha(l1)

                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.pos()

        # Linha sob o mouse (para highlight e fold)
        nova_linha  = self._y_para_linha(pos.y())
        novo_bloco  = nova_linha - 1 if nova_linha > 0 else -1

        # Fold hover: linha é dobrável → detecta se mouse está na zona da seta
        novo_fold  = -1
        nova_seta  = False
        if novo_bloco >= 0:
            bloco = self.editor.document().findBlockByNumber(novo_bloco)
            ext   = self._extensao_atual(self.editor)
            if bloco.isValid() and self._es_dobravel(bloco.text(), ext):
                novo_fold = novo_bloco
                # Calcula zona X da seta igual ao paintEvent
                _x_seta_mv = self.width() - self.pad - self.larg_seta
                nova_seta  = pos.x() >= _x_seta_mv

        # Cursor: mão na zona BP ou sobre a seta de dobramento
        _x_bp_mv  = self.larg_git + self.pad
        _em_bp_mv = _x_bp_mv <= pos.x() <= _x_bp_mv + self.larg_guiter
        if _em_bp_mv or nova_seta:
            self.setCursor(QCursor(Qt.PointingHandCursor))
        else:
            self.setCursor(QCursor(Qt.ArrowCursor))

        mudou = False
        if novo_bloco != self._hover_linha:
            self._hover_linha = novo_bloco
            mudou = True
        if novo_fold != self._hover_fold:
            self._hover_fold = novo_fold
            mudou = True
        if nova_seta != self._hover_seta:
            self._hover_seta = nova_seta
            mudou = True

        # Git hover: mouse na barra colorida da esquerda → realça hunk no editor
        novo_git_hunk: list[int] = []
        na_zona_git = pos.x() < self.larg_git and nova_linha > 0
        if na_zona_git:
            novo_git_hunk = self._hunk_em_linha(nova_linha)
        if novo_git_hunk != self._hover_git_hunk:
            self._hover_git_hunk = novo_git_hunk
            self.editor._set_git_hunk_realce(novo_git_hunk)

        if mudou:
            self.update()

        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        """Redireciona scroll da calha para o viewport do editor.
        Sem isso, o wheel event é consumido silenciosamente pelo QWidget
        filho e a rolagem não acontece quando o mouse está sobre a calha.
        """
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.sendEvent(self.editor.viewport(), event)

    def leaveEvent(self, event):
        """Limpa highlight e fold ao mouse sair da calha."""
        if self._hover_git_hunk:
            self._hover_git_hunk = []
            self.editor._set_git_hunk_realce([])
        if self._hover_fold != -1 or self._hover_linha != -1 or self._hover_seta:
            self._hover_fold  = -1
            self._hover_linha = -1
            self._hover_seta  = False
            self.update()
        self.setCursor(QCursor(Qt.ArrowCursor))
        super().leaveEvent(event)

    def _hunk_em_linha(self, l1: int) -> list[int]:
        """Retorna todas as linhas do hunk contíguo que contém l1.
        Um hunk é um bloco de linhas consecutivas com o mesmo tipo git.
        """
        if l1 not in self._git:

            return []

        tipo = self._git[l1]
        hunk = []
        n = l1
        while n in self._git and self._git[n] == tipo:
            hunk.append(n)
            n -= 1
        n = l1 + 1
        while n in self._git and self._git[n] == tipo:
            hunk.append(n)
            n += 1

        return hunk

    # ── Diff embutido no editor (estilo Zed) ────────────────────────────
    # Antes era um popup (Qt.ToolTip) flutuando por cima da tela ao passar
    # o mouse. Agora é um painel filho do próprio viewport do editor,
    # ativado por clique na barra colorida da calha — sem popup nenhum.

    def _alternar_diff_inline(self, linha_1based: int, hunk: dict):
        """Clique na calha git → abre/fecha o diff embutido no editor.
        Clicar de novo na mesma linha fecha; clicar em outro hunk troca."""
        diff = self._obter_diff_inline()
        if diff.hunk_ativo() is hunk:
            diff.fechar()

            return
        diff.mostrar_para_linha(linha_1based, hunk)

    def _obter_diff_inline(self):
        """Cria (uma vez) o painel de diff embutido, filho do viewport do editor."""
        if getattr(self.editor, '_diff_inline', None) is None:
            from _EDITOR_.Editor._inline_diff_hunk import _InlineDiffHunk
            self.editor._diff_inline = _InlineDiffHunk(self.editor)

        return self.editor._diff_inline

    # ══════════════════════════════════════════════════════════════════
    # Utilitários
    # ══════════════════════════════════════════════════════════════════

    def _y_para_linha(self, y: int) -> int:
        """Converte posição Y (em pixels) no número de linha 1-based.
        Usa blockBoundingGeometry por bloco — sem acumulação de drift.

        Quando o StickyScroll está visível, setViewportMargins reserva
        h_sticky px no topo — o mesmo offset usado no paintEvent precisa
        ser aplicado aqui para que cliques do mouse batam na linha certa.
        """
        h_sticky = 0
        if hasattr(self.editor, '_sticky') and self.editor._sticky.isVisible():
            h_sticky = self.editor._sticky.height()

        bloco  = self.editor.firstVisibleBlock()
        numero = bloco.blockNumber()
        while bloco.isValid():
            geo   = self.editor.blockBoundingGeometry(bloco).translated(
                        self.editor.contentOffset())
            topo  = int(geo.top()) + h_sticky
            fundo = topo + int(geo.height())
            if topo <= y < fundo:

                return numero + 1

            if topo > y:
                break
            bloco  = bloco.next()
            numero += 1

        return -1

    def _bloco_recolhido(self, numero_bloco: int) -> bool:
        """
        Retorna True se o bloco de número numero_bloco é o cabeçalho de
        uma FoldRegion collapsed. Usa _fold_regions (list[FoldRegion]).
        """
        fold_regions = getattr(self.editor, '_fold_regions', [])
        if not fold_regions:

            return False

        for r in fold_regions:
            if r.collapsed and r.start_block.blockNumber() == numero_bloco:

                return True

        return False

    @staticmethod
    def _extrair_nome(texto: str) -> str:
        m = re.match(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)", texto)

        return m.group(1) if m else ""

    @staticmethod
    def _extensao_atual(editor) -> str:
        """Retorna a extensão do arquivo aberto no editor (ex: '.py', '.json')."""
        caminho = getattr(editor, 'file_path', '') or ''

        return os.path.splitext(caminho)[1].lower()

    @staticmethod
    def _es_dobravel(texto: str, extensao: str, proximo_texto: str = '') -> bool:
        """Retorna True se a linha pode iniciar um bloco dobrável.
        Cobre Python, JSON, HTML/XML, YAML e JS/TS/CSS."""
        if extensao in ('.py', '.pyw'):
            # Palavras-chave (def/class/if/for...) OU linha abrindo lista/dict
            # multi-linha (termina com [ ou {), ex: icones = [, config = {

            return (bool(_RE_FOLDABLE.match(texto))

                    or texto.rstrip().endswith(('[', '{')))

        if extensao == '.json':

            return texto.rstrip().endswith(('{', '['))

        if extensao in ('.html', '.htm', '.xml'):
            # Tag de abertura (não self-closing, não comentário, não DOCTYPE)

            return bool(re.match(r'^\s*<[a-zA-Z][^/!][^>]*(?<!/)>', texto))

        if extensao in ('.yaml', '.yml'):
            s = texto.rstrip()

            return bool(s) and s.endswith(':') and not s.lstrip().startswith('#')

        if extensao in ('.js', '.ts', '.jsx', '.tsx', '.css', '.scss', '.less'):

            return bool(re.match(

                r'^\s*(function\b|class\b|if\b|for\b|while\b|.*\{\s*$)', texto
            ))

        # Extensão não-hardcodada: delega ao LanguageProvider (folding_fn)
        try:
            from _EDITOR_.Mult_Linguas import get_provider, is_registered
            if extensao and is_registered(extensao):
                return get_provider(extensao).folding_fn(texto, extensao, proximo_texto)
        except Exception:
            pass
        return False
