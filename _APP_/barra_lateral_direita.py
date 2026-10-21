# 📁 _APP_/barra_lateral_direita.py
"""
Barra vertical estreita no lado direito da janela principal.
Contém os botões de controle da janela (fechar, maximizar, minimizar)
e a bandeira do Brasil semitransparente como fundo (imagem).

Coloque o arquivo  brasil.png  na mesma pasta (_APP_/).
"""

import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFrame
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap, QPen, QColor
from _CONFIGURA_ import (
    COR_MENU_HOVER_BG,
    COR_MENU_HOVER_TEXTO,IMAGEM_BAND
)
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import COR_BTN_ICONE_TEXTO_qta

_LARGURA = 30    # largura fixa da barra em pixels
_OP      = 0.35  # opacidade da imagem — 0.0 invisível, 1.0 totalmente opaco


class _FundoBandeira(QWidget):
    """Widget de fundo que carrega a imagem da bandeira estilizada
    e a desenha com opacidade configurável, cobrindo toda a barra."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)

        self._pixmap = QPixmap(IMAGEM_BAND)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setOpacity(_OP)
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaledToHeight(self.height(), Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            painter.drawPixmap(x, 0, scaled)
        painter.end()


class BarraLateralDireita(QWidget):
    """
    Barra vertical estreita com os botões [ ✕ ] [ □ ] [ ─ ]
    e bandeira do Brasil semitransparente no fundo.

    Ordem dos botões (cima → baixo): fechar · maximizar · minimizar
    Separador horizontal divide a zona de controle do restante.
    Borda vertical à direita na altura da zona de controle.
    """

    def __init__(self, janela, parent=None):
        super().__init__(parent)
        self._janela     = janela
        self._maximizado = False

        self._borda_cor    = "transparent"
        self._borda_larg   = 0
        self._borda_estilo = "solid"

        self.setFixedWidth(_LARGURA)
        self.setObjectName("BarraLateralDireita")

        self._fundo = _FundoBandeira(self)
        self._fundo.lower()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 0, 0, 2)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        _cor       = tema_global().cor("interface.icone", COR_BTN_ICONE_TEXTO_qta)
        _cor_fundo = tema_global().cor("interface.fundo_painel", "#020202")
        _base      = self._style(_cor)

        # ── Zona de controle (X / □ / ─) com fundo opaco igual à BarraTitulo ──
        self._zona_ctrl = QFrame()
        self._zona_ctrl.setObjectName("zona_ctrl_bld")
        self._zona_ctrl.setStyleSheet(
            f"QFrame#zona_ctrl_bld {{ background: {_cor_fundo}; border: none; }}"
        )
        _ctrl_lay = QVBoxLayout(self._zona_ctrl)
        _ctrl_lay.setContentsMargins(0, 0, 0, 0)
        _ctrl_lay.setSpacing(2)
        _ctrl_lay.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # ordem: ✕ · □ · ─
        self._btn_fec = QPushButton("✕")
        self._btn_fec.setToolTip("Fechar")
        self._btn_fec.setCursor(Qt.PointingHandCursor)
        self._btn_fec.setStyleSheet(
            _base + "QPushButton:hover { background:#c0392b; color:#ffffff; }"
        )
        self._btn_fec.clicked.connect(self._janela.close)

        self._btn_max = QPushButton("□")
        self._btn_max.setToolTip("Maximizar / Restaurar")
        self._btn_max.setCursor(Qt.PointingHandCursor)
        self._btn_max.setStyleSheet(
            _base + f"QPushButton:hover {{ background:{COR_MENU_HOVER_BG}; color:{COR_MENU_HOVER_TEXTO}; }}"
        )
        self._btn_max.clicked.connect(self._toggle_maximizar)

        self._btn_min = QPushButton("─")
        self._btn_min.setToolTip("Minimizar")
        self._btn_min.setCursor(Qt.PointingHandCursor)
        self._btn_min.setStyleSheet(
            _base + f"QPushButton:hover {{ background:{COR_MENU_HOVER_BG}; color:{COR_MENU_HOVER_TEXTO}; }}"
        )
        self._btn_min.clicked.connect(self._janela.showMinimized)

        _ctrl_lay.addWidget(self._btn_fec)
        _ctrl_lay.addWidget(self._btn_max)
        _ctrl_lay.addWidget(self._btn_min)

        layout.addWidget(self._zona_ctrl)

        # Separador horizontal entre controles e área inferior
        self._sep = QFrame()
        self._sep.setFrameShape(QFrame.HLine)
        self._sep.setFixedHeight(1)
        self._sep.setStyleSheet(
            f"background: {tema_global().cor('interface.borda_externa', tema_global().cor('interface.borda', '#333'))};"
            "border: none;"
        )
        layout.addWidget(self._sep)
        layout.addStretch()

    # ── helpers ──────────────────────────────────────────────────────────

    def _style(self, cor: str) -> str:
        return f"""
            QPushButton {{
                background: transparent;
                color: {cor};
                border: none;
                font-size: 11px;
                min-width: {_LARGURA}px;
                max-width: {_LARGURA}px;
                height: 22px;
                padding: 0px;
            }}
        """

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fundo.setGeometry(self.rect())
        self.update()

    def paintEvent(self, event):
        from PySide6.QtCore import Qt as _Qt
        _mapa = {
            "solid":        _Qt.SolidLine,
            "dashed":       _Qt.DashLine,
            "dotted":       _Qt.DotLine,
            "dash-dot":     _Qt.DashDotLine,
            "dash-dot-dot": _Qt.DashDotDotLine,
        }
        if not self._borda_cor or self._borda_cor == "transparent":
            return
        if self._borda_larg <= 0:
            return

        zona_h = self._sep.geometry().bottom() if self._sep else 80
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(self._borda_cor))
        pen.setWidthF(float(self._borda_larg))
        pen.setStyle(_mapa.get(self._borda_estilo, _Qt.SolidLine))
        painter.setPen(pen)
        painter.drawLine(0, 0, 0, zona_h)
        painter.drawLine(0, zona_h, self.width(), zona_h)
        painter.end()

    def atualizar_borda_direita(self, cor: str, larg: int, estilo: str):
        """Chamado por aplicar_bordas_paineis para sincronizar cor/estilo."""
        self._borda_cor    = cor
        self._borda_larg   = larg
        self._borda_estilo = estilo
        self.update()

    # ── Tema ─────────────────────────────────────────────────────────────

    def atualizar_tema(self):
        _cor       = tema_global().cor("interface.icone", COR_BTN_ICONE_TEXTO_qta)
        _cor_fundo = tema_global().cor("interface.fundo_painel", "#020202")
        _base      = self._style(_cor)
        _cor_sep   = tema_global().cor("interface.borda_externa",
                                       tema_global().cor("interface.borda", "#333"))
        self._zona_ctrl.setStyleSheet(
            f"QFrame#zona_ctrl_bld {{ background: {_cor_fundo}; border: none; }}"
        )
        self._btn_fec.setStyleSheet(
            _base + "QPushButton:hover { background:#c0392b; color:#ffffff; }"
        )
        self._btn_max.setStyleSheet(
            _base + f"QPushButton:hover {{ background:{COR_MENU_HOVER_BG}; color:{COR_MENU_HOVER_TEXTO}; }}"
        )
        self._btn_min.setStyleSheet(
            _base + f"QPushButton:hover {{ background:{COR_MENU_HOVER_BG}; color:{COR_MENU_HOVER_TEXTO}; }}"
        )
        self._sep.setStyleSheet(f"background: {_cor_sep}; border: none;")
        self.update()

    # ── Maximizar ────────────────────────────────────────────────────────

    def _toggle_maximizar(self):
        if self._janela.isMaximized():
            self._janela.showNormal()
            self._btn_max.setText("□")
            self._maximizado = False
        else:
            self._janela.showMaximized()
            self._btn_max.setText("❐")
            self._maximizado = True

    def sincronizar_estado_max(self, maximizado: bool):
        self._maximizado = maximizado
        self._btn_max.setText("❐" if maximizado else "□")
