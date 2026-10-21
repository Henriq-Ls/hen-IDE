# 📁 _EDITOR_/Editor/_code_lens.py
"""_CodeLensOverlay — desenha "· N usos" inline após def/class no viewport."""
import re as _re
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtGui     import QPainter, QFont, QColor, QCursor
from PySide6.QtCore    import QObject, QEvent, Qt
from _CONFIGURA_.gerenciador_tema import tema_global

_RE_DEF_CLASS_LENS = _re.compile(r"^\s*(def |async def |class )")

class _CodeLensOverlay(QObject):
    """
    Instala eventFilter no viewport do editor.
    Desenha o label "· N usos" na mesma linha da def/class, após o texto.
    Clique e hover tratados pelo CodeEditor via checar_clique/checar_hover.
    """

    def __init__(self, editor: "CodeEditor"):
        super().__init__(editor)
        self._editor = editor
        self._lens_rects: list = []   # (x1, y1, x2, y2, nome, arquivo, linha)
        editor.viewport().installEventFilter(self)

    # DEPOIS
    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        try:
            editor = self._editor
            if obj is not editor.viewport():

                return False

        except RuntimeError:

            return False

        if event.type() == QEvent.Paint:
            QPlainTextEdit.paintEvent(editor, event)
            self._desenhar(event)
            self._desenhar_cursor()

            return True

        return False

    # ⚠️  except genérico vazio
    def _desenhar_cursor(self):
        """
        Desenha:
          1) cursor principal personalizado (via _GerenciadorCursorPersonalizado)
          2) barras de cursor em cada posição extra do multi-cursor
        """
        editor     = self._editor
        cursor_mgr = getattr(editor, "_cursor_mgr", None)
        multi      = getattr(editor, "_multi_cursor", None)
        has_multi  = (multi is not None and multi.esta_ativo()
                      and getattr(multi, "_cursores_extras", None))

        if cursor_mgr is None and not has_multi:

            return

        painter = QPainter(editor.viewport())

        # ── cursor principal ──────────────────────────────────────────
        if cursor_mgr is not None:
            cursor_mgr.desenhar(painter, editor)

        # ── cursores extras — mesmo pipeline do principal ─────────────
        if has_multi:
            painter.save()
            for c_extra in multi._cursores_extras:
                try:
                    if cursor_mgr is not None:
                        cursor_mgr.desenhar_extra(painter, editor, c_extra)
                    else:
                        from PySide6.QtGui import QBrush, QColor as _QColor
                        rect = editor.cursorRect(c_extra)
                        fm   = editor.fontMetrics()
                        w    = max(8, fm.averageCharWidth())
                        painter.setPen(Qt.NoPen)
                        painter.setBrush(QBrush(_QColor("#ff9800")))
                        painter.drawRect(rect.x(), rect.top(), w, rect.height())
                except Exception:
                    pass
            painter.restore()

        painter.end()

    def checar_clique(self, pos) -> bool:
        """Retorna True se o clique foi num label CodeLens e abre Find References."""
        for x1, y1, x2, y2, nome, arquivo, linha in self._lens_rects:
            if x1 <= pos.x() <= x2 and y1 <= pos.y() <= y2:
                self._editor._find_refs.buscar_com_arquivo(nome, arquivo, linha)

                return True

        return False

    def checar_hover(self, pos):
        """Atualiza cursor só quando está em cima de um label CodeLens."""
        from PySide6.QtGui import QCursor
        em_lens = any(
            x1 <= pos.x() <= x2 and y1 <= pos.y() <= y2
            for x1, y1, x2, y2, *_ in self._lens_rects
        )
        if em_lens:
            self._editor.viewport().setCursor(QCursor(Qt.PointingHandCursor))
        elif getattr(self, '_estava_em_lens', False):
            self._editor.viewport().setCursor(QCursor(Qt.IBeamCursor))
        self._estava_em_lens = em_lens

    # ⚠️  função grande (148 linhas)
    def _desenhar(self, event):
        editor  = self._editor
        painter = QPainter(editor.viewport())

        # Régua visual — sempre na borda direita do viewport (= borda esquerda da ReguaErros)
        _x_regua = editor.viewport().width() - 1
        painter.setPen(QColor(tema_global().cor("editor.guia_quebra_linha", "#2a2a3a")))
        painter.drawLine(_x_regua, 0, _x_regua, editor.viewport().height())

        # ── Linhas de caderno (papel pautado) — só quando o provider pede ──
        # Hoje: HeinProvider (.hein) tem estilo_visual='caderno'.
        try:
            from _EDITOR_.Mult_Linguas import get_provider
            import os as _os_caderno
            _fp_caderno  = getattr(editor, 'file_path', None) or ''
            _ext_caderno = _os_caderno.path.splitext(_fp_caderno)[1].lower()
            _eh_caderno  = get_provider(_ext_caderno).estilo_visual == 'caderno'
        except Exception:
            _eh_caderno = False

        if _eh_caderno:
            painter.setPen(QColor(tema_global().cor("editor.guia_quebra_linha", "#3a3a4a")))
            _bloco_cd = editor.firstVisibleBlock()
            _geo_cd   = editor.blockBoundingGeometry(_bloco_cd).translated(editor.contentOffset())
            _topo_cd  = int(_geo_cd.top())
            while _bloco_cd.isValid() and _topo_cd <= editor.viewport().height():
                _alt_cd = int(editor.blockBoundingRect(_bloco_cd).height())
                if _bloco_cd.isVisible():
                    _y_base = _topo_cd + _alt_cd - 1
                    painter.drawLine(0, _y_base, editor.viewport().width(), _y_base)
                _topo_cd += _alt_cd
                _bloco_cd = _bloco_cd.next()

        # ── Indent guides ─────────────────────────────────────────────
        # Desabilitado para o editor .hein (estilo caderno / texto corrido).
        # Guias APENAS em linhas com conteúdo real (não vazia, não só-espaço).
        # Linhas completamente vazias ou com apenas whitespace NÃO recebem guia.
        if _eh_caderno:
            painter.end()
            return
        fm_ig          = editor.fontMetrics()
        largura_espaco = fm_ig.horizontalAdvance(' ')
        try:
            from _CONFIGURA_.gerenciador_configurar import config_global
            tab_size = int(config_global().obter("editor", "tab_tamanho", 4))
        except Exception:
            tab_size = 4
        cor_guide = tema_global().qcolor("editor.guia_quebra_linha", "#2d3d2d")
        painter.setPen(cor_guide)

        bloco_ig = editor.firstVisibleBlock()
        geo_ig   = editor.blockBoundingGeometry(bloco_ig).translated(editor.contentOffset())
        topo_ig  = int(geo_ig.top())
        offset_x = int(editor.contentOffset().x())

        while bloco_ig.isValid() and topo_ig <= editor.viewport().height():
            altura_ig = int(editor.blockBoundingRect(bloco_ig).height())
            if bloco_ig.isVisible():
                texto_ig = bloco_ig.text()
                # Só desenha em linhas que têm conteúdo real (ignora vazias e só-espaço)
                if texto_ig.strip():
                    leading = texto_ig[: len(texto_ig) - len(texto_ig.lstrip())]
                    col = 0
                    for _ch in leading:
                        col = (col // tab_size + 1) * tab_size if _ch == '\t' else col + 1
                    nivel = col // tab_size
                    for n in range(nivel):
                        x_guide = offset_x + int(n * tab_size * largura_espaco)
                        painter.drawLine(x_guide, topo_ig, x_guide, topo_ig + altura_ig)
            topo_ig  += altura_ig
            bloco_ig  = bloco_ig.next()
        # ── fim indent guides ──────────────────────────────────────────

        # ── Reticências (...) nos cabeçalhos colapsados (2.1) ─────────
        _fold_regs = getattr(editor, '_fold_regions', [])
        if _fold_regs:
            _colapsados = {
                r.start_block.blockNumber()
                for r in _fold_regs if r.collapsed
            }
            if _colapsados:
                _fonte_ret = QFont(editor.font())
                _fonte_ret.setItalic(True)
                painter.setFont(_fonte_ret)
                _fm_ret  = painter.fontMetrics()
                try:
                    _cor_ret = tema_global().qcolor(
                        "editor.numero_linha", "#7094A1"
                    )
                except Exception:
                    _cor_ret = QColor("#7094A1")
                painter.setPen(_cor_ret)
                _fm_ed   = editor.fontMetrics()
                _bloco_r = editor.firstVisibleBlock()
                _geo_r   = editor.blockBoundingGeometry(_bloco_r).translated(
                    editor.contentOffset()
                )
                _topo_r  = int(_geo_r.top())
                _ox      = int(editor.contentOffset().x())
                while _bloco_r.isValid() and _topo_r <= editor.viewport().height():
                    _alt_r = int(editor.blockBoundingRect(_bloco_r).height())
                    if (_bloco_r.isVisible()
                            and _bloco_r.blockNumber() in _colapsados):
                        _txt_r = _bloco_r.text()
                        _x_r   = _ox + _fm_ed.horizontalAdvance(_txt_r) + 6
                        _y_r   = _topo_r + (
                            _alt_r + _fm_ret.ascent() - _fm_ret.descent()
                        ) // 2
                        painter.drawText(_x_r, _y_r, "  ···")
                    _topo_r  += _alt_r
                    _bloco_r  = _bloco_r.next()
                painter.setFont(editor.font())  # restaura fonte do editor
        # ── fim reticências ───────────────────────────────────────────

        usages = getattr(editor.area_numeros, '_usages', {})
        if not usages:
            self._lens_rects.clear()
            painter.end()

            return

        self._lens_rects.clear()

        #painter = QPainter(editor.viewport())
        fonte   = QFont("Consolas", 8)
        fonte.setItalic(True)
        painter.setFont(fonte)
        fm = painter.fontMetrics()

        cor_normal = QColor("#4a4a6a")
        cor_hover  = QColor("#8888aa")

        from PySide6.QtGui import QCursor
        mouse_pos = editor.viewport().mapFromGlobal(QCursor.pos())

        bloco  = editor.firstVisibleBlock()
        numero = bloco.blockNumber()
        geo    = editor.blockBoundingGeometry(bloco).translated(editor.contentOffset())
        topo   = int(geo.top())

        fm_editor = editor.fontMetrics()

        while bloco.isValid() and topo <= editor.viewport().height():
            altura = int(editor.blockBoundingRect(bloco).height())
            l1     = numero + 1
            texto  = bloco.text()

            if bloco.isVisible() and _RE_DEF_CLASS_LENS.match(texto) and l1 in usages:
                cnt   = usages[l1]
                label = f"  ·  {cnt} uso{'s' if cnt != 1 else ''}"

                largura_linha = fm_editor.horizontalAdvance(texto)
                x  = int(editor.contentOffset().x()) + largura_linha + 6
                y1 = topo
                y2 = topo + altura
                largura_label = fm.horizontalAdvance(label)
                x2 = x + largura_label

                em_hover = (x <= mouse_pos.x() <= x2 and y1 <= mouse_pos.y() <= y2)
                painter.setPen(cor_hover if em_hover else cor_normal)

                y_texto = topo + (altura + fm.ascent() - fm.descent()) // 2
                painter.drawText(x, y_texto, label)

                nome_fn = _extrair_nome_lens(texto)
                arquivo = getattr(editor, "file_path", None) or ""
                self._lens_rects.append((x, y1, x2, y2, nome_fn, arquivo, l1))

            topo   += altura
            bloco   = bloco.next()
            numero += 1

        painter.end()

def _extrair_nome_lens(texto: str) -> str:
    m = _re.match(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)", texto)

    return m.group(1) if m else ""
