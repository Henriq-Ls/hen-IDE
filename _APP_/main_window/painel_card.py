"""PainelCard — widget de card com cantos arredondados.

Parte do pacote main_window/ — ver main_window/__init__.py.
Gerado a partir da divisão de main_window.py (arquivo único de 4607 linhas).
"""


import atexit
import os
import shutil
import subprocess
import sys
import tempfile
from _UTILITARIOS_.icones import icone_tema
from PySide6.QtWidgets import (
    QMainWindow,

    QWidget,

    QVBoxLayout,

    QHBoxLayout,

    QTabWidget,

    QSplitter,

    QPushButton,

    QMenuBar,

    QMenu,

    QFileDialog,

    QMessageBox,

    QInputDialog,

    QLabel,

    QApplication,

    QProgressBar,

    QDockWidget,

)

from _APP_.navegador_abas import NavegadorAbas
from PySide6.QtGui import QTextCursor, QPainter, QColor, QBrush, QPainterPath, QRegion, QAction, QKeySequence, QPen
from PySide6.QtCore import QEvent, QRectF
from PySide6.QtCore import Qt, QTimer, QSize, QThread, Signal, QSettings
from ..tab_widget import TabWidget
from ..terminal_tab_widget import TerminalTabWidget

from _PAINEL_ESQUERDO_.FileTree import PainelArquivos
from _PAINEL_ESQUERDO_.painel_abas_inferior import PainelAbasInferior as PainelGit
from _CONFIGURA_.gerenciador_atalhos import GerenciadorAtalhos
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_.gerenciador_configurar import config_global
from GerenciadorAbas_AutoSalve import GerenciadorAbas_AutoSalve
from _CONFIGURA_ import (
    TITULO_APP,
    GEOMETRIA_APP,
    SPLITTER_PRINCIPAL,

    SPLITTER_COL1,

    SPLITTER_COL2,

    COR_MENU_BG,

    COR_MENU_TEXTO,

    COR_MENU_HOVER_BG,

    COR_MENU_HOVER_TEXTO,

    COR_MENU_ITEM,

    COR_MENU_ITEM_HOVER,

    COR_TOOLBAR_TERM_BG,

    COR_BTN_RUN_BG,

    COR_BTN_RUN_HOVER,

    ATALHO_NOVO_PROJETO,

    ATALHO_ABRIR_PROJETO,

    ATALHO_ABRIR_ARQUIVO,

    ATALHO_SALVAR,

    ATALHO_EXECUTAR,

    ATALHO_TAREFAS_PROJETO,

    ATALHO_TAREFAS_GLOBAIS,

    ATALHO_EDITAR_TEMA,

    ATALHO_EDITAR_ATALHOS,

    ATALHO_EDITOR_CONFIG,

    ATALHO_AUTOCOMPLETE,

    PASTA_PROJETOS,

    PASTA_APPDATA,

    ARQUIVO_CONFIG,

    ARQUIVO_ATALHOS,

    ARQUIVO_TEMA,

    COR_SUCESSO,

    COR_INFO,

    COR_AVISO,

    COR_CINZA_TEXTO,

    BORDA_CONTORNO_UI,

)

from _EDITOR_.Indexador import Indexador
from ..barra_aba_topo import BarraTitulo
from ..barra_lateral_direita import BarraLateralDireita
from _BUSCA_.motor_busca import MotorBusca
from _BUSCA_.painel_busca_global import PainelBuscaGlobal
from _BUSCA_.command_palette import CommandPalette
from _BUSCA_.busca_comandos import buscar_comandos


class PainelCard(QWidget):
    """

    Container com cantos arredondados.

    paintEvent pinta o rounded-rect; setMask recorta todos os widgets filhos

    ao mesmo shape — assim nenhum filho "vaza" para fora dos cantos.

    BordaOverlay desenha a borda SOBRE os filhos (sempre visível).

    """

    RAIO = 12

    # 💡 cor_fundo_opc = Literal["#0A1210"] ← defina os valores válidos

    def __init__(self, cor_fundo: str = "#0A1210", parent=None):
        super().__init__(parent)

        self._cor = QColor(cor_fundo)

        self._layout = QVBoxLayout(self)

        self._layout.setContentsMargins(0, 0, 0, 0)

        self._layout.setSpacing(0)

        self._borda_overlay = None

        self._curva_overlay = None  # overlay ┐ tracejado — só coluna_esquerda

    def _garantir_overlay(self):
        if self._borda_overlay is None:
            from _CONFIGURA_ import BordaOverlay
            self._borda_overlay = BordaOverlay.criar(self)

    def atualizar_borda(self, cor: str, larg: int, estilo: str, raio: int = None, sem_topo: bool = False, sem_direita: bool = False):
        self._garantir_overlay()

        self._borda_overlay.atualizar(cor, larg, estilo, raio if raio is not None else self.RAIO, sem_topo=sem_topo, sem_direita=sem_direita)

    # ⚠️  função grande (105 linhas) | except genérico vazio

    def ativar_curva_esquerda(self, obter_limite_y=None, obter_topo_y=None):
        """Cria e eleva o overlay ┐ do file tree — cor/estilo vêm do tema (aplicar_bordas_paineis).

        obter_limite_y: callback opcional que retorna a altura (y) onde a lateral

        direita deve parar de descer — normalmente a base do painel_arquivos,

        pra não invadir o painel git/núcleo logo abaixo (que já tem borda própria).

        obter_topo_y: callback opcional que retorna o y onde a curva deve COMEÇAR —

        normalmente abaixo da barra "— projeto —", deixando o botão de fora da moldura.

        Se None, mantém o comportamento antigo (y=32 fixo / desce até a base).

        """

        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QWidget
        from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath

        class _CurvaImpl(QWidget):
            def __init__(self, parent, fn_limite=None, fn_topo=None):
                super().__init__(parent)

                self.setAttribute(Qt.WA_TransparentForMouseEvents)

                self.setAttribute(Qt.WA_NoSystemBackground)

                self._cor       = "#2d5a2d"

                self._larg      = 1.5

                self._qt_est    = Qt.SolidLine

                self._raio      = 10            # IMP-02: raio configurável

                self._fn_limite = fn_limite

                self._fn_topo   = fn_topo

            def atualizar(self, cor: str, larg: float, qt_est, raio: int = 10):
                self._cor    = cor

                self._larg   = larg

                self._qt_est = qt_est

                self._raio   = max(1, int(raio))  # IMP-02

                self.update()

                self.raise_()

            # ⚠️  função grande (57 linhas) | except genérico vazio

            def paintEvent(self, ev):
                if not self._cor or self._cor == "transparent":
                    return

                if self._larg <= 0:             # IMP-01: larg=0 → sem borda

                    return

                painter = QPainter(self)

                painter.setRenderHint(QPainter.Antialiasing)

                w = float(self.width())     # largura real; usa w-1 no path

                h = float(self.height())

                topo = 32.0

                if self._fn_topo is not None:
                    try:
                        topo = float(self._fn_topo())

                    except Exception:
                        pass

                if self._fn_limite is not None:
                    try:
                        limite = float(self._fn_limite())

                        if limite > topo + self._raio:
                            h = limite

                    except Exception:
                        pass

                pen = QPen(QColor(self._cor))

                pen.setWidthF(self._larg)

                pen.setStyle(self._qt_est)

                r  = float(self._raio)          # IMP-02: raio variável

                # ── Pinta o "canto externo" da curva com a cor de fundo ───────

                # Isso clipa visualmente o background do file tree, sem setMask.

                # O "triângulo/fatia" no topo-direito da curva recebe a mesma cor

                # que fica FORA da coluna (janela principal), criando a ilusão de

                # canto arredondado onde a barra de projeto termina.

                try:
                    from _CONFIGURA_.gerenciador_tema import tema_global as _tg_c
                    _ext = QColor(_tg_c().cor("interface.fundo", "#000000"))

                    _corner = QPainterPath()

                    _corner.moveTo(w - 1, topo)

                    _corner.lineTo(w - 1, topo + r)

                    _corner.arcTo(w - 1 - 2 * r, topo,

                                  2 * r, 2 * r, 0.0, 90.0)

                    _corner.closeSubpath()

                    painter.fillPath(_corner, _ext)

                except Exception:
                    pass

                path = QPainterPath()

                path.moveTo(w - 1, h)           # começa na base do file tree

                path.lineTo(w - 1, topo + r)    # sobe pela borda direita

                path.arcTo(w - 1 - r * 2, topo, # curva ┐ logo abaixo do botão

                           r * 2, r * 2, 0.0, 90.0)

                path.lineTo(0.0, topo)          # vai reto até x=0

                painter.strokePath(path, pen)

                painter.end()

        self._curva_overlay = _CurvaImpl(self, obter_limite_y, obter_topo_y)

        self._curva_overlay.setGeometry(self.rect())

        self._curva_overlay.raise_()

        # Inicializa com o tema atual (antes de aplicar_bordas_paineis ser chamado)

        try:
            from _CONFIGURA_.gerenciador_tema import tema_global as _tg2
            _t2 = _tg2()

            _cor_init = _t2.cor("interface.borda_externa",

                                _t2.cor("interface.borda", "#2d5a2d"))

            self._curva_overlay.atualizar(_cor_init, 1.5, Qt.SolidLine)

        except Exception:
            pass

    def atualizar_curva_esquerda(self, cor: str, larg: float, estilo: str, raio: int = 10):
        """Chamado por gerenciador_configurar.aplicar_bordas_paineis para sincronizar."""

        if self._curva_overlay is None:
            return

        from PySide6.QtCore import Qt
        _mapa = {

            "solid":        Qt.SolidLine,

            "dashed":       Qt.DashLine,

            "dotted":       Qt.DotLine,

            "dash-dot":     Qt.DashDotLine,

            "dash-dot-dot": Qt.DashDotDotLine,

            "none":         Qt.NoPen,

        }

        self._curva_overlay.atualizar(cor, float(larg), _mapa.get(estilo, Qt.SolidLine), raio)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        path = QPainterPath()

        path.addRoundedRect(QRectF(self.rect()), self.RAIO, self.RAIO)

        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

        if self._borda_overlay is not None:
            self._borda_overlay.setGeometry(self.rect())

            self._borda_overlay.raise_()

        if self._curva_overlay is not None:
            self._curva_overlay.setGeometry(self.rect())

            self._curva_overlay.raise_()    # sempre acima de tudo

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(QPainter.Antialiasing)

        painter.setBrush(QBrush(self._cor))

        painter.setPen(Qt.NoPen)

        painter.drawRoundedRect(QRectF(self.rect()), self.RAIO, self.RAIO)

        painter.end()
