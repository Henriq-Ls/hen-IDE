# 📁 _PAINEL_ESQUERDO_/FileTree/_auxiliares.py
"""
Helpers de estilo, cache de ícones e widget MenuRecenteProjeto.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from _CONFIGURA_ import BORDA_TOPO, COR_BTN_ICONE_BG_qta
from _CONFIGURA_.gerenciador_tema import tema_global
from _UTILITARIOS_.icones import icone_tema


# ─── Helpers de cor/estilo ────────────────────────────────────────────────────

def _c(chave: str, fb: str) -> str:
    try:
        return tema_global().cor(chave, fb)
    except Exception:
        return fb


def _estilo_btn_icone() -> str:
    hover = _c("interface.fundo_item_hover", "#1a3a1a")
    texto = _c("interface.texto_fraco", "#6b8f6b")
    ativo = _c("interface.texto", "#e8f5e8")
    return (
        f"QPushButton {{"
        f"  background: transparent; color: {texto};"
        f"  border: none; border-radius: 3px;"
        f"  padding: 0 4px; font-size: 11px;"
        f"}}"
        f"QPushButton:hover {{ background: {hover}; color: {ativo}; }}"
        f"QPushButton:checked {{ color: {ativo}; background: {hover}; }}"
    )


def _estilo_barra() -> str:
    fundo = _c("editor.fundo_calha", "#020202")
    return f"background-color: {fundo};"


def _estilo_btn_id(obj_name: str) -> str:
    return f"""
        QPushButton#{obj_name} {{
            background: transparent;
            border: none;
        }}
        QPushButton#{obj_name}:hover {{
            background: {COR_BTN_ICONE_BG_qta};
        }}
        """


# ─── Cache de ícones ──────────────────────────────────────────────────────────

_cache_icones: dict = {}


def _qicon(nome: str, cor: str, tamanho: int = 14) -> QIcon | None:
    """Retorna QIcon do qtawesome com fallback silencioso."""
    chave = f"{nome}:{cor}:{tamanho}"
    if chave in _cache_icones:
        return _cache_icones[chave]
    try:
        icone = icone_tema(nome, color=cor, scale_factor=1.0)
        _cache_icones[chave] = icone
        return icone
    except Exception:
        _cache_icones[chave] = None
        return None


# ─── Widget de barra superior ─────────────────────────────────────────────────

class MenuRecenteProjeto(QWidget):
    menu_clicado      = Signal()
    recentes_clicado  = Signal()
    abrir_pasta       = Signal()
    projeto_clicado   = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"BarraEsquerda {{ {_estilo_barra()} }}")

        self._lay = QHBoxLayout(self)
        lay = self._lay
        lay.setContentsMargins(5, 2, 5, 2)
        lay.setSpacing(3)

        self._btn_recentes_ide = QToolButton()
        self._btn_recentes_ide.setIcon(icone_tema("mdi6.folder-clock"))
        self._btn_recentes_ide.setFixedSize(24, 24)
        self._btn_recentes_ide.setToolTip("Recentes")
        self._btn_recentes_ide.setCursor(Qt.PointingHandCursor)
        self._btn_recentes_ide.setStyleSheet("""
        QToolButton { background: transparent; border: none; }
        QToolButton:hover { background: #1a1a2e; border-radius: 3px; }
        """)
        self._btn_recentes_ide.clicked.connect(self.recentes_clicado)
        lay.addWidget(self._btn_recentes_ide)

        self._lbl_projeto = QLabel("— projeto —")
        self._lbl_projeto.setStyleSheet(
            f"color: {BORDA_TOPO}; font-size: 13px; font-weight: bold; background: transparent;"
        )
        self._lbl_projeto.setCursor(Qt.PointingHandCursor)
        self._lbl_projeto.mousePressEvent = lambda e: self.projeto_clicado.emit()
        lay.addWidget(self._lbl_projeto)
        lay.addStretch(1)

    def set_projeto(self, nome: str):
        self._lbl_projeto.setText(nome)

    def atualizar_tema(self):
        self.setStyleSheet(f"BarraEsquerda {{ {_estilo_barra()} }}")
        self._btn_recentes_ide.setStyleSheet(_estilo_btn_icone())
        self._btn_recentes_ide.setIcon(icone_tema("mdi6.folder-clock"))
