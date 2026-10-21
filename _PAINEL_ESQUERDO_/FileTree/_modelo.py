# 📁 _PAINEL_ESQUERDO_/FileTree/_modelo.py
"""
Modelos Qt para a árvore de arquivos:
  _IconProvider  — QFileSystemModel com ícones qtawesome
  _ProxyOrdem    — proxy que pina .venv / .hein no topo
  _DelegateGit   — pintua badge de status git à esquerda do ícone
"""

import os

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFileSystemModel, QStyledItemDelegate

import _CONFIGURA_ as _CFG
from _CONFIGURA_ import (
    _ICONE_EXT,
    _ICONE_PADRAO,
    _ICONE_PASTA,
    _TOOLTIP_GIT,
    PACKS_ICONES,
    VERDE,
    COR_OUTLINE_OBJETO_JSON,
    COR_SINTAXE_VARIAVEL_ESPECIAL,
    COR_GIT_FUNDO_DELETADO,
    COR_GIT_FUNDO_MODIFICADO,
)
from _CONFIGURA_.gerenciador_tema import tema_global

from ._auxiliares import _qicon


# ══════════════════════════════════════════════════════════════════════
# _IconProvider — ícones qtawesome por extensão
# ══════════════════════════════════════════════════════════════════════

class _IconProvider(QFileSystemModel):
    """
    Subclasse do QFileSystemModel que sobrescreve data() para
    injetar ícones qtawesome por extensão, usando o pack ativo.
    """

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if role == Qt.DecorationRole and index.column() == 0:
            info = self.fileInfo(index)
            if info.isDir():
                if info.fileName() == ".venv":
                    icone = _qicon("mdi.package-variant", "#8BC34A")
                    if icone:
                        return icone

                if info.fileName() == ".hein":
                    icone = _qicon("mdi.skip-next", "#E59400")
                    if icone:
                        return icone

                nome_qicon, cor = _ICONE_PASTA
                icone = _qicon(nome_qicon, cor)
                if icone:
                    return icone

            else:
                pack_ativo = PACKS_ICONES.get(_CFG._PACK_ATIVO, _ICONE_EXT)
                ext = (
                    ("." + info.suffix()).lower()
                    if info.suffix()
                    else info.fileName().lower()
                )
                if not info.suffix():
                    ext = info.fileName().lower()
                nome_qicon, cor = pack_ativo.get(ext, _ICONE_PADRAO)
                icone = _qicon(nome_qicon, cor)
                if icone:
                    return icone

        return super().data(index, role)


# ══════════════════════════════════════════════════════════════════════
# _ProxyOrdem — pina .venv e .hein no topo da árvore
# ══════════════════════════════════════════════════════════════════════

class _ProxyOrdem(QSortFilterProxyModel):
    # Menor número = mais acima. Pastas não listadas ficam abaixo.
    _PRIORIDADE: dict[str, int] = {".venv": 0, ".hein": 1}
    _IGNORADOS_NOMES: frozenset = frozenset({"__pycache__"})
    _IGNORADOS_SUFIXOS: tuple = (".bak",)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filtrar_gerados: bool = False

    def set_filtrar_gerados(self, ativo: bool) -> None:
        self._filtrar_gerados = ativo
        self.invalidateFilter()

    def filterAcceptsRow(self, row: int, parent: QModelIndex) -> bool:
        if self._filtrar_gerados:
            modelo = self.sourceModel()
            idx    = modelo.index(row, 0, parent)
            nome   = modelo.fileName(idx)
            if nome in self._IGNORADOS_NOMES:
                return False
            for suf in self._IGNORADOS_SUFIXOS:
                if nome.endswith(suf):
                    return False
        return super().filterAcceptsRow(row, parent)

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        modelo  = self.sourceModel()
        nome_e  = modelo.fileName(left)
        nome_d  = modelo.fileName(right)

        rank_e = self._PRIORIDADE.get(nome_e, 999)
        rank_d = self._PRIORIDADE.get(nome_d, 999)

        if rank_e != rank_d:
            return rank_e < rank_d

        eh_dir_e = modelo.isDir(left)
        eh_dir_d = modelo.isDir(right)
        if eh_dir_e != eh_dir_d:
            return eh_dir_e

        return super().lessThan(left, right)


# ══════════════════════════════════════════════════════════════════════
# _DelegateGit — símbolo / cor de status git à direita do item
# ══════════════════════════════════════════════════════════════════════

class _DelegateGit(QStyledItemDelegate):
    def __init__(
        self,
        model: QFileSystemModel,
        proxy: _ProxyOrdem,
        status_git: dict,
        staging_checks: dict = None,
        parent=None,
    ):
        super().__init__(parent)
        self._model          = model
        self._proxy          = proxy
        self._status_git     = status_git
        self._staging_checks = staging_checks if staging_checks is not None else {}
        self._staging_ativo  = False

    def set_modo_staging(self, ativo: bool) -> None:
        self._staging_ativo = ativo

    def _caminho_src(self, index: QModelIndex) -> str:
        src = self._proxy.mapToSource(index)
        return self._model.filePath(src).replace("\\", "/").lower()

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if editor is not None:
            editor.setStyleSheet(
                "QLineEdit {"
                "  background: #111111;"
                "  color: #e0e0e0;"
                "  border: 1px solid #1e3a5f;"
                "  padding: 2px 4px;"
                "  selection-background-color: #264f78;"
                "}"
            )
        return editor

    def paint(self, painter: QPainter, option, index: QModelIndex):
        from PySide6.QtWidgets import QStyle
        if option.state & QStyle.StateFlag.State_Editing:
            return  # editor inline está visível — não desenha texto por baixo

        caminho_key = self._caminho_src(index)
        status      = self._status_git.get(caminho_key)

        if status:
            from PySide6.QtGui import QPalette
            from PySide6.QtWidgets import QStyleOptionViewItem

            _COR_TEXTO = {
                "novo":       "#e5c07b",
                "modificado": "#e8a44a",
                "deletado":   "#e06c75",
                "renomeado":  "#e5c07b",
            }
            cor_txt = _COR_TEXTO.get(status, "#abb2bf")
            option  = QStyleOptionViewItem(option)
            option.palette.setColor(QPalette.ColorRole.Text, QColor(cor_txt))
            option.palette.setColor(QPalette.ColorRole.HighlightedText, QColor(cor_txt))

        super().paint(painter, option, index)

        if not status:
            return

        # ── Modo staging: desenha checkbox em vez do badge ──────────
        if self._staging_ativo and caminho_key in self._staging_checks:
            from PySide6.QtCore import QRect
            from PySide6.QtWidgets import QStyleOptionButton, QApplication

            marcado = self._staging_checks.get(caminho_key, True)
            rect    = option.rect
            cb_size = 13
            cb_x    = rect.left() - 2
            cb_y    = rect.top() + (rect.height() - cb_size) // 2
            cb_rect = QRect(cb_x, cb_y, cb_size, cb_size)

            opt_cb = QStyleOptionButton()
            opt_cb.rect  = cb_rect
            opt_cb.state = QStyle.StateFlag.State_Enabled | (
                QStyle.StateFlag.State_On if marcado else QStyle.StateFlag.State_Off
            )
            QApplication.style().drawPrimitive(
                QStyle.PrimitiveElement.PE_IndicatorCheckBox, opt_cb, painter
            )
            return   # não desenha o badge dot

        # ── Modo normal: badge circular com símbolo ──────────────────
        _cfg = {
            "novo":       (VERDE, tema_global().cor("interface.fundo_item_hover", "#1a3a1a"), "+"),
            "modificado": (COR_OUTLINE_OBJETO_JSON, COR_GIT_FUNDO_MODIFICADO, "~"),
            "deletado":   (COR_SINTAXE_VARIAVEL_ESPECIAL, COR_GIT_FUNDO_DELETADO, "\u00d7"),
            "renomeado":  (COR_OUTLINE_OBJETO_JSON, COR_GIT_FUNDO_MODIFICADO, "~"),
        }
        cor_borda, cor_fundo, simbolo = _cfg.get(
            status, (COR_OUTLINE_OBJETO_JSON, COR_GIT_FUNDO_MODIFICADO, "~")
        )

        from PySide6.QtCore import QPointF, QRectF

        rect = option.rect
        R    = 4
        cx   = float(rect.left() + 11 - R)
        cy   = float(rect.top() + rect.height() // 2 + 4)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(cor_fundo)))
        painter.setPen(QPen(QColor(cor_borda), 1.2))
        painter.drawEllipse(QPointF(cx, cy), float(R), float(R))

        f = QFont(option.font)
        f.setPixelSize(7)
        f.setBold(True)
        painter.setFont(f)
        painter.setPen(QColor(cor_borda))
        painter.drawText(
            QRectF(cx - R, cy - R, R * 2, R * 2),
            Qt.AlignCenter,
            simbolo,
        )
        painter.restore()

    @staticmethod
    def _info_arquivo(caminho_real: str) -> str:
        """Retorna 'N linhas  •  X.X KB' para arquivos; '' para pastas/erros."""
        if not os.path.isfile(caminho_real):
            return ""
        try:
            tamanho_kb = os.path.getsize(caminho_real) / 1024
            with open(caminho_real, "r", encoding="utf-8", errors="ignore") as f:
                linhas = sum(1 for _ in f)
            return f"{linhas} linhas  •  {tamanho_kb:.1f} KB"
        except OSError:
            return ""

    def helpEvent(self, event, view, option, index):
        src          = self._proxy.mapToSource(index)
        caminho_real = self._model.filePath(src)
        caminho_key  = caminho_real.replace("\\", "/").lower()
        status       = self._status_git.get(caminho_key)

        partes = []
        if status:
            partes.append(_TOOLTIP_GIT.get(status, ""))
        info = self._info_arquivo(caminho_real)
        if info:
            partes.append(info)

        if partes:
            from PySide6.QtWidgets import QToolTip
            QToolTip.showText(event.globalPos(), "\n".join(partes), view)
            return True
        return super().helpEvent(event, view, option, index)
