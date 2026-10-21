# 📁 _APP_/barra_aba_topo.py
"""
Barra de título customizada para a janela principal (FramelessWindowHint).
Contém:
  - Botão hein (esquerda) → abre menu único com Tema + todos os menus da IDE
  - Abas centralizadas com ícones por extensão (mesmo esquema do FileTree)
  - Botões [ _ ] [ □ ] [ X ] (direita)

As escolhas são salvas em PASTA_APPDATA/layout.json e restauradas na próxima abertura.
"""

import json
import os
import logging
from _UTILITARIOS_.icones import icone_tema
from PySide6.QtWidgets import (
    QPushButton, QMenu,
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QListWidget, QListWidgetItem)
from PySide6.QtGui  import QAction, QActionGroup, QPainter, QColor, QPen, QPainterPath, QIcon
from PySide6.QtCore import Qt, QTimer, QSize, QPointF, QPoint
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import (
    TITULO_APP,    VERSAO_APP,
    COR_MENU_BG,    COR_MENU_HOVER_BG,
    COR_MENU_HOVER_TEXTO,    COR_MENU_ITEM,
    COR_MENU_ITEM_HOVER,    TEMAS_QT_DISPONIVEIS,
    TEMA_QT_PADRAO,    PASTA_APPDATA,
    BORDA_GERAL, BordaCompleta,
    FONTE_UI,    FONTE_UI_FALLBACK,
    IMAGEM_LOGO,
    FUNDO_PAINEL,    PACKS_ICONES,
    _ICONE_EXT,    _ICONE_PADRAO,CINZA_ESCURO,VERDE)
from _THREADS_ import diagnostico_foco_temporario as _focus_trace

import _CONFIGURA_ as _CFG
_ARQUIVO_LAYOUT   = os.path.join(PASTA_APPDATA, "layout.json")
_ARQUIVO_RECENTES = os.path.join(PASTA_APPDATA, "recentes.json")
_MAX_RECENTES     = 10

_cache_icones_aba: dict = {}

def _icone_aba(nome: str, cor: str, tamanho: int = 14):
    chave = f"{nome}:{cor}:{tamanho}"
    if chave in _cache_icones_aba:
        return _cache_icones_aba[chave]

    try:
        import qtawesome as qta
        icone = qta.icon(nome, color=cor, scale_factor=1.0)  # usa cor do pack de arquivos, não do tema
        _cache_icones_aba[chave] = icone

        return icone

    except Exception:
        _cache_icones_aba[chave] = None

        return None

class AbaWidget(QWidget):
    H = 28  # fallback; use _altura() / _padding_h() / _padding_v() em runtime

    @classmethod
    def _altura(cls) -> int:
        try:
            from _CONFIGURA_.gerenciador_configurar import config_global

            return int(config_global().obter("ui", "altura_aba", cls.H))

        except Exception:
            return cls.H

    @classmethod
    def _padding_h(cls) -> int:
        try:
            from _CONFIGURA_.gerenciador_configurar import config_global

            return int(config_global().obter("ui", "padding_aba_h", 10))

        except Exception:
            return 10

    @classmethod
    def _padding_v(cls) -> int:
        try:
            from _CONFIGURA_.gerenciador_configurar import config_global

            return int(config_global().obter("ui", "padding_aba_v", 0))

        except Exception:
            return 0

    @classmethod
    def _tamanho_fonte(cls) -> int:
        """Tamanho de fonte para o texto da aba (configurável via 'tamanho_fonte_aba')."""
        try:
            from _CONFIGURA_.gerenciador_configurar import config_global
            default = max(10, int(cls._altura() * 0.37))

            return int(config_global().obter("ui", "tamanho_fonte_aba", default))

        except Exception:
            return max(10, int(cls._altura() * 0.37))

    # ⚠️  função grande (60 linhas)
    # 💡 borda_estilo_opc = Literal["solid"] ← defina os valores válidos
    def __init__(self, indice, texto, ativo, tab_widget, borda_cor=BORDA_GERAL, borda_larg=0, borda_estilo="solid", preview=False, parent=None):
        super().__init__(parent)
        self._indice       = indice
        self._ativo        = ativo
        self._tab_widget   = tab_widget
        self._borda_cor    = borda_cor
        self._borda_larg   = borda_larg
        self._borda_estilo = borda_estilo
        self._reordenando  = False   # True durante drag de reorder

        _h  = AbaWidget._altura()
        _ph = AbaWidget._padding_h()
        _pv = AbaWidget._padding_v()

        self.setFixedHeight(_h)
        self.setCursor(Qt.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(_ph, _pv, max(4, _ph - 2), _pv)
        lay.setSpacing(5)

        # ícone customizado (aba especial) tem prioridade sobre extensão
        _tab_data  = tab_widget.tabBar().tabData(indice)
        if isinstance(_tab_data, dict) and "icone" in _tab_data:
            nome_qicon = _tab_data["icone"]
            cor_icone  = tema_global().cor("interface.icone", "#ffffff")
        else:
            # ícone por extensão — mesmo esquema do FileTree
            ext        = ("." + texto.rsplit(".", 1)[-1]).lower() if "." in texto else ""
            pack_ativo = PACKS_ICONES.get(_CFG._PACK_ATIVO, _ICONE_EXT)
            nome_qicon, cor_icone = pack_ativo.get(ext, _ICONE_PADRAO)

        self._lbl_icone = QLabel()
        icone = _icone_aba(nome_qicon, cor_icone, 14)
        if icone:
            self._lbl_icone.setPixmap(icone.pixmap(QSize(14, 14)))
        self._lbl_icone.setFixedSize(16, 16)
        self._lbl_icone.setStyleSheet("background: transparent;")

        _t   = tema_global()
        _cor = _t.cor("interface.texto", "#e0e0e0") if ativo else _t.cor("interface.texto_fraco", "#666666")
        _fs = AbaWidget._tamanho_fonte()
        self._label = QLabel(texto)
        _italico = " font-style: italic;" if preview else ""
        self._label.setStyleSheet(f"color: {_cor}; font-size: {_fs}px;{_italico} background: transparent;")

        self._btn_x = QPushButton("\u2715")
        self._btn_x.setFixedSize(QSize(16, 16))
        self._btn_x.setStyleSheet("""
            QPushButton { background: transparent; color: #555; border: none; font-size: 9px; padding: 0; }
            QPushButton:hover { color: #e06c75; }
        """)
        self._btn_x.clicked.connect(lambda: self._tab_widget.fechar_aba(self._indice))

        lay.addWidget(self._lbl_icone)
        lay.addWidget(self._label)
        lay.addSpacing(6)
        lay.addWidget(self._btn_x)

        fm = self._label.fontMetrics()
        self.setFixedWidth(max(fm.horizontalAdvance(texto) + _ph + max(4, _ph - 2) + 16 + 5 + 6 + 5 + 16, 80))


    @staticmethod
    def largura_estimada(texto: str, fonte) -> int:
        """
        Calcula a largura que um AbaWidget teria para `texto`, sem precisar
        instanciar o widget — usado para planejar a distribuição em linhas.
        Reflete exatamente a fórmula usada no __init__ acima.
        """
        from PySide6.QtGui import QFontMetrics
        ph = AbaWidget._padding_h()
        fm = QFontMetrics(fonte)

        return max(fm.horizontalAdvance(texto) + ph + max(4, ph - 2) + 16 + 5 + 6 + 5 + 16, 80)

    def _caminho(self):
        """Retângulo com cantos superiores arredondados e pés em S (tipo aba de navegador)."""
        w, h = self.width(), self.height()
        r = 4    # raio dos cantos superiores
        f = 8    # largura/altura do pé em S (reduzido para dar mais espaço ao conteúdo)

        path = QPainterPath()

        path.moveTo(0, h)
        path.cubicTo(f * 0.5, h, f, h - f * 0.5, f, h - f)
        path.lineTo(f, r)
        path.quadTo(f, 0, f + r, 0)
        path.lineTo(w - f - r, 0)
        path.quadTo(w - f, 0, w - f, r)
        path.lineTo(w - f, h - f)
        path.cubicTo(w - f, h - f * 0.5, w - f * 0.5, h, w, h)
        path.closeSubpath()

        return path

    def _caminho_borda(self):
        """Mesmo contorno de _caminho mas sem fechar (open path) — só topo e laterais."""
        w, h = self.width(), self.height()
        r = 4
        f = 8
        path = QPainterPath()
        path.moveTo(0, h)
        path.cubicTo(f * 0.5, h, f, h - f * 0.5, f, h - f)
        path.lineTo(f, r)
        path.quadTo(f, 0, f + r, 0)
        path.lineTo(w - f - r, 0)
        path.quadTo(w - f, 0, w - f, r)
        path.lineTo(w - f, h - f)
        path.cubicTo(w - f, h - f * 0.5, w - f * 0.5, h, w, h)

        return path

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        t = tema_global()
        if self._ativo:
            cor = t.cor("interface.fundo_aba_ativa",   "#1a1f2e")
        else:
            cor = t.cor("interface.fundo_aba_inativa", "#1b242d")
        painter.fillPath(self._caminho(), QColor(cor))
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_origin: QPoint | None = event.position().toPoint()
            self._tab_widget.setCurrentIndex(self._indice)
            event.accept()   # impede propagação para BarraTitulo (que moveria a janela)

    def mouseMoveEvent(self, event):
        event.accept()   # sempre impede que BarraTitulo mova a janela
        if not (event.buttons() & Qt.LeftButton):
            return

        if self._reordenando:
            pos_global = event.globalPosition().toPoint()
            bt = self._get_barra_topo()
            if bt:
                pos_local = bt.mapFromGlobal(pos_global)
                if pos_local.y() > bt.height() + AbaWidget._altura():
                    self.releaseMouse()
                    self._reordenando = False
                    self.unsetCursor()
                    bt._esconder_indicador_reorder()
                    self._iniciar_tear_off(pos_global)
                    return
                bt._atualizar_indicador_reorder(self._indice, pos_global)
            return

        origin = getattr(self, '_drag_origin', None)
        if origin is None:
            return

        dist = (event.position().toPoint() - origin).manhattanLength()
        # threshold: 1× startDragDistance (~10px) para drag responsivo
        if dist < QApplication.startDragDistance():
            return

        self._drag_origin = None
        pos_global = event.globalPosition().toPoint()

        bt = self._get_barra_topo()
        if bt:
            pos_local = bt.mapFromGlobal(pos_global)
            if pos_local.y() <= bt.height() + AbaWidget._altura():
                self._reordenando = True
                self.setCursor(Qt.ClosedHandCursor)
                self.grabMouse()
                bt._atualizar_indicador_reorder(self._indice, pos_global)
                return

        self._iniciar_tear_off(pos_global)

    def mouseReleaseEvent(self, event):
        if self._reordenando:
            self.releaseMouse()
            self._reordenando = False
            self.unsetCursor()
            bt = self._get_barra_topo()
            if bt:
                bt._finalizar_reorder(self._indice, event.globalPosition().toPoint())
        self._drag_origin = None
        event.accept()

    def _get_barra_topo(self):
        p = self.parent()   # _container_abas
        if p:
            pp = p.parent()  # BarraTitulo
            if isinstance(pp, BarraTitulo):
                return pp
        return None

    def _iniciar_tear_off(self, pos_global: QPoint):
        """Mostra o ZonaDropSplit para dividir o editor ou destacar para janela flutuante."""
        self._tab_widget._pedir_split(self._indice, pos_global)

    def event(self, e):
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QToolTip
        if e.type() == QEvent.Type.ToolTip:
            try:
                editor = self._tab_widget.widget(self._indice)
                caminho = getattr(editor, "file_path", None) or ""
                QToolTip.showText(e.globalPos(), caminho, self)
            except Exception:
                pass
            return True
        return super().event(e)

# ── Quantas linhas de abas no máximo antes de agrupar o excedente ──────────
MAX_LINHAS_ABAS = 2

class MaisAbasWidget(QWidget):
    """
    Botão '+N' mostrado ao final da última linha quando há mais abas do
    que cabem nas MAX_LINHAS_ABAS linhas disponíveis. Clicar abre um popup
    de lista (mesmo padrão visual do NavegadorAbas) com as abas escondidas;
    clicar num item ativa aquela aba.
    """
    H = AbaWidget.H  # fallback estático

    def __init__(self, indices_escondidos, tab_widget, barra_aba_topo, parent=None):
        super().__init__(parent)
        self._indices    = indices_escondidos
        self._tab_widget = tab_widget
        self._barra      = barra_aba_topo
        self._popup      = None

        self.setFixedHeight(AbaWidget._altura())
        self.setCursor(Qt.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(0)

        _cor = tema_global().cor("interface.texto_fraco", "#888888")
        self._label = QLabel(f"+{len(indices_escondidos)}")
        self._label.setStyleSheet(f"color: {_cor}; font-size: {AbaWidget._tamanho_fonte()}px; background: transparent;")
        lay.addWidget(self._label)

        fm = self._label.fontMetrics()
        self.setFixedWidth(fm.horizontalAdvance(self._label.text()) + 20 + 10)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        cor = tema_global().cor("interface.fundo_aba_ativa", "#1a1f2e")
        path = QPainterPath()
        w, h = self.width(), self.height()
        r = 4
        path.moveTo(0, h)
        path.lineTo(0, r)
        path.quadTo(0, 0, r, 0)
        path.lineTo(w - r, 0)
        path.quadTo(w, 0, w, r)
        path.lineTo(w, h)
        path.closeSubpath()
        cor_obj = QColor(cor)
        cor_obj.setAlpha(120)
        painter.fillPath(path, cor_obj)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._abrir_popup()

    # ⚠️  função grande (60 linhas)
    def _abrir_popup(self):
        if self._popup is not None:
            return

        self._popup = QWidget(self._tab_widget, Qt.Tool | Qt.FramelessWindowHint)
        self._popup.setObjectName("MaisAbasPopup")
        _t      = tema_global()
        _fundo  = _t.cor("menu_contexto.fundo",       "#1a1a2e")
        _borda  = _t.cor("menu_contexto.borda",       "#4a90d9")
        _texto  = _t.cor("menu_contexto.texto",       "#e0e0e0")
        _hover  = _t.cor("menu_contexto.hover",       "#1e3a5f")
        _sel    = _t.cor("menu_contexto.selecionado", "#264f78")
        self._popup.setStyleSheet(f"""
            QWidget#MaisAbasPopup {{
                background: {_fundo};
                border: 1px solid {_borda};
                border-radius: 6px;
            }}
            QListWidget {{
                background: transparent;
                color: {_texto};
                border: none;
                font-size: 12px;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 6px 12px;
                border-radius: 3px;
            }}
            QListWidget::item:selected {{
                background: {_sel};
                color: #ffffff;
            }}
            QListWidget::item:hover {{
                background: {_hover};
                cursor: pointer;
            }}
        """)

        layout = QVBoxLayout(self._popup)
        layout.setContentsMargins(4, 4, 4, 4)

        lista = QListWidget()
        lista.setMouseTracking(True)
        for idx in self._indices:
            texto = self._tab_widget.tabText(idx).lstrip("*").strip()
            item  = QListWidgetItem(f"  {texto}")
            lista.addItem(item)
        lista.itemClicked.connect(self._ao_clicar_item)

        layout.addWidget(lista)
        self._popup.setFixedWidth(260)
        self._popup.setFixedHeight(min(40 + len(self._indices) * 32, 400))

        ponto = self.mapToGlobal(self.rect().bottomLeft())
        self._popup.move(ponto.x() - self._popup.width() + self.width(), ponto.y() + 4)
        self._popup.show()

        app = QApplication.instance()
        _focus_trace.install(app)
        app.focusChanged.connect(self._ao_perder_foco)

    def _ao_clicar_item(self, item):
        lista = item.listWidget()
        row = lista.row(item)
        if 0 <= row < len(self._indices):
            indice_real = self._indices[row]
            self._fechar_popup()
            self._tab_widget.setCurrentIndex(indice_real)
            self._barra._reconstruir_abas()

    def _ao_perder_foco(self, antigo, novo):
        _focus_trace.enter("barra_aba_topo", antigo, novo)
        try:
            if self._popup is None:
                return

            # fecha o popup quando o foco vai para fora dele (e de seus filhos)
            foco_dentro_popup = novo is not None and (
                novo is self._popup or self._popup.isAncestorOf(novo)
            )
            if not foco_dentro_popup:
                _focus_trace.reaction("barra_aba_topo", "_fechar_popup")
                self._fechar_popup()
        finally:
            _focus_trace.exit("barra_aba_topo")

    def _fechar_popup(self):
        if self._popup is None:
            return

        try:
            QApplication.instance().focusChanged.disconnect(self._ao_perder_foco)
        except (RuntimeError, TypeError):
            pass
        self._popup.close()
        self._popup.deleteLater()
        self._popup = None

class _LinhaSep(QWidget):
    """Linha separadora customizável — solid, dashed, dotted."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cor    = "#444444"
        self._larg   = 2
        self._estilo = "solid"
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedHeight(self._larg)

    def atualizar(self, cor: str, larg: int, estilo: str):
        self._cor    = cor
        self._larg   = max(1, larg)
        self._estilo = estilo
        self.setFixedHeight(self._larg)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(self._cor))
        pen.setWidth(self._larg)
        _mapa = {"dashed": Qt.DashLine, "dotted": Qt.DotLine, "dot-dash": Qt.DashDotLine}
        pen.setStyle(_mapa.get(self._estilo, Qt.SolidLine))
        painter.setPen(pen)
        y = self.height() / 2.0
        painter.drawLine(QPointF(0, y), QPointF(self.width(), y))
        painter.end()

class _IndicadorReorder(QWidget):
    """Linha vertical de 3 px que marca o ponto de insercao durante drag de aba."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedWidth(3)
        self.hide()

    def mover_para(self, x: int, y: int, h: int):
        self.setGeometry(max(0, x - 1), y, 3, max(h, 4))
        self.raise_()
        self.show()

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QColor
        p = QPainter(self)
        cor = QColor(tema_global().cor("interface.destaque", "#4ade80"))
        p.fillRect(self.rect(), cor)
        p.end()


class BarraTitulo(QWidget):
    _ALTURA_BASE = 32   # fallback; use _altura_base() em runtime

    @classmethod
    def _altura_base(cls) -> int:
        """Altura de 1 linha de abas + margem interna."""

        return AbaWidget._altura() + 4

    # ⚠️  função grande (87 linhas)
    def __init__(self, janela, parent=None):
        super().__init__(parent)
        self.setObjectName("BarraTitulo")
        self._janela         = janela
        self._splitters      = {}
        self._tema_atual     = TEMA_QT_PADRAO
        self._tema_json_atual = ''
        self._drag_pos       = None
        self._maximizado     = False
        self._menus_externos = []
        self._tab_widget     = None
        self._tab_botoes     = []
        self._painel_arquivos = None
        self._linhas_abas    = []   # lista de QHBoxLayout, uma por linha de abas
        self._reconstruindo_abas = False  # trava contra recursão no resizeEvent
        self._ultima_largura_reconstruida = -1  # última largura do container usada em _reconstruir_abas
        self._borda_cor    = BORDA_GERAL
        self._borda_larg   = 0
        self._borda_estilo = "solid"

        self.setFixedHeight(BarraTitulo._altura_base())
        self._aplicar_borda()

        self._linha_sep = _LinhaSep(self)
        self._atualizar_cor_linha_sep()

        def _obter_tab_titulo():
            from PySide6.QtCore import QRect, QPoint
            for aba in self._tab_botoes:
                if (isinstance(aba, AbaWidget) and aba._ativo
                        and aba.parent() is not None and aba.isVisible()):
                    pos = aba.mapTo(self, QPoint(0, 0))

                    return QRect(pos.x(), pos.y(), aba.width(), aba.height())

            return None

        self._borda_completa = BordaCompleta.criar(self, _obter_tab_titulo, sem_base=True)

        self._layout_interno = QHBoxLayout(self)
        self._layout_interno.setContentsMargins(1, 0, 1, 0)
        self._layout_interno.setSpacing(0)

        _caminho_logo = IMAGEM_LOGO

        self._lbl_titulo = QPushButton()
        self._lbl_titulo.setIcon(QIcon(_caminho_logo))
        self._lbl_titulo.setIconSize(QSize(30, 22))
        self._lbl_titulo.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 0 20px;  /* imagem — regula largura dos dois lados */
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.08); }
        """)

        self._lbl_titulo.setCursor(Qt.PointingHandCursor)
        self._lbl_titulo.clicked.connect(self._abrir_menu)
        self._layout_interno.addWidget(self._lbl_titulo)

        self._container_abas = QWidget()
        self._container_abas.setStyleSheet("background: transparent;")
        self._layout_interno.addWidget(self._container_abas, 1)

        # —— chip de versão ————————————————————————————————
        self._url_update = None
        self._btn_versao = QPushButton(VERSAO_APP)
        self._btn_versao.setObjectName("btn_versao")
        self._btn_versao.setCursor(Qt.PointingHandCursor)
        self._btn_versao.setEnabled(False)
        self._btn_versao.setFixedHeight(18)
        self._btn_versao.setStyleSheet(f"""
            QPushButton#btn_versao {{
                background: {CINZA_ESCURO}; color: #3a5a3a;
                border: 1px solid #1f2f1f; border-radius: 3px;
                font-size: 10px; padding: 0 8px;
                margin-left: 8px; margin-right: 5px;
                }}
        """)
        self._layout_interno.addWidget(self._btn_versao)
        # Botões min/max/fec foram movidos para BarraLateralDireita

        self._restaurar_tema()

    def injetar_tab_widget(self, tab_widget):
        self._tab_widget = tab_widget
        self._tab_botoes = []

        # layout vertical contendo até MAX_LINHAS_ABAS layouts horizontais
        layout_vertical = QVBoxLayout()
        layout_vertical.setContentsMargins(0, 4, 0, 0)
        layout_vertical.setSpacing(2)

        self._linhas_abas = []
        for _ in range(MAX_LINHAS_ABAS):
            linha = QHBoxLayout()
            linha.setContentsMargins(0, 0, 0, 0)
            linha.setSpacing(0)
            self._linhas_abas.append(linha)
            layout_vertical.addLayout(linha)

        self._container_abas.setLayout(layout_vertical)

        tab_widget.tabBar().hide()
        tab_widget.currentChanged.connect(self._sincronizar_abas)
        tab_widget.tabCloseRequested.connect(self._fechar_aba_barra)

        # No momento em que o tab_widget é injetado, a janela ainda pode não
        # ter terminado de calcular sua geometria final (largura "real" da
        # tela do usuário). Por isso fazemos uma reconstrução imediata
        # (melhor que nada) e agendamos outra(s) para depois que o event
        # loop processar o resize/show definitivo da janela.
        self._reconstruir_abas()
        QTimer.singleShot(0, self._reconstruir_abas)
        QTimer.singleShot(150, self._reconstruir_abas)

    # ⚠️  função grande (92 linhas)
    def _reconstruir_abas(self):
        _cache_icones_aba.clear()
        for b in self._tab_botoes:
            b.deleteLater()
        self._tab_botoes.clear()

        for linha in self._linhas_abas:
            while linha.count():
                item = linha.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        tw = self._tab_widget
        total_abas = tw.count()
        if total_abas == 0:
            self._ajustar_altura(1)
            # IMP-04b: sem isso, a ultima pintura do overlay (com N abas) fica
            # fantasma na tela quando a ultima aba e fechada -- o overlay so
            # e atualizado no ramo total_abas>0 mais abaixo.
            if hasattr(self, "_borda_completa"):
                from _LOG_.log import log
                log.aviso("barra_aba_topo.py", "_reconstruir_abas",
                           "ultima aba fechada -- forcando update() do overlay para evitar borda fantasma")
                self._borda_completa.update()

            return

        largura_disponivel = max(self._container_abas.width(), 100)
        self._ultima_largura_reconstruida = largura_disponivel
        fonte_label = QApplication.font()
        fonte_label.setPixelSize(AbaWidget._tamanho_fonte())  # espelha font-size do stylesheet do QLabel da aba

        textos    = [tw.tabText(i) for i in range(total_abas)]
        larguras  = [AbaWidget.largura_estimada(t, fonte_label) for t in textos]

        # ── Distribui os índices nas linhas disponíveis ─────────────────────
        linhas_indices: list[list[int]] = [[] for _ in range(MAX_LINHAS_ABAS)]
        linha_atual       = 0
        largura_acumulada = 0
        indice_overflow    = None   # primeira posição que não coube em lugar nenhum

        for i in range(total_abas):
            largura_aba = larguras[i]
            cabe_na_linha_atual = (largura_acumulada + largura_aba) <= largura_disponivel

            if not cabe_na_linha_atual:
                if linha_atual < MAX_LINHAS_ABAS - 1:
                    # passa pra próxima linha
                    linha_atual += 1
                    largura_acumulada = 0
                else:
                    # já estamos na última linha permitida e não coube mais nada
                    indice_overflow = i

                    break

            linhas_indices[linha_atual].append(i)
            largura_acumulada += largura_aba

        # ── Se houver overflow, talvez seja necessário liberar espaço na ────
        # última linha para o botão "+N" caber também.
        if indice_overflow is not None:
            largura_botao_mais = AbaWidget.largura_estimada(
                f"+{total_abas - indice_overflow}", fonte_label
            )
            ultima = linhas_indices[MAX_LINHAS_ABAS - 1]
            largura_ultima = sum(larguras[i] for i in ultima)
            while ultima and (largura_ultima + largura_botao_mais) > largura_disponivel:
                removido = ultima.pop()
                largura_ultima -= larguras[removido]
                indice_overflow = removido

        # ── Monta os widgets reais nas linhas ────────────────────────────────
        for num_linha, indices in enumerate(linhas_indices):
            layout_linha = self._linhas_abas[num_linha]
            for i in indices:
                _is_prev = (getattr(tw, '_preview_editor', None) is not None
                            and tw.widget(i) is tw._preview_editor)
                aba = AbaWidget(i, textos[i], i == tw.currentIndex(), tw,
                              borda_cor=self._borda_cor, borda_larg=self._borda_larg,
                              borda_estilo=self._borda_estilo, preview=_is_prev,
                              parent=self._container_abas)
                self._tab_botoes.append(aba)
                layout_linha.addWidget(aba)

        # ── Widget "+N" para as abas que não couberam ────────────────────────
        if indice_overflow is not None:
            indices_escondidos = list(range(indice_overflow, total_abas))
            mais = MaisAbasWidget(indices_escondidos, tw, self, parent=self._container_abas)
            self._tab_botoes.append(mais)
            self._linhas_abas[MAX_LINHAS_ABAS - 1].addWidget(mais)

        for layout_linha in self._linhas_abas:
            layout_linha.addStretch()

        linhas_usadas = sum(1 for indices in linhas_indices if indices) or 1
        self._ajustar_altura(linhas_usadas)
        # IMP-04: força repaint do overlay para evitar bordas fantasmas
        if hasattr(self, "_borda_completa"):
            self._borda_completa.update()

    def _ajustar_altura(self, linhas_usadas: int):
        """Recalcula a altura total da barra: base + linhas extras de abas."""
        linhas_usadas = max(1, min(linhas_usadas, MAX_LINHAS_ABAS))
        altura_extra  = (linhas_usadas - 1) * (AbaWidget._altura() + 2)
        altura_nova   = BarraTitulo._altura_base() + altura_extra
        if self.height() != altura_nova:
            self.setFixedHeight(altura_nova)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_linha_sep"):
            h_sep = self._linha_sep.height()
            self._linha_sep.setGeometry(0, self.height() - h_sep, self.width(), h_sep)
        if hasattr(self, "_borda_completa"):
            self._borda_completa.setGeometry(self.rect())
            self._borda_completa.raise_()
        if self._tab_widget is None:
            return

        if getattr(self, "_reconstruindo_abas", False):
            return  # evita recursão: setFixedHeight() dentro daqui dispara outro resizeEvent

        # Se a largura do container de abas não mudou desde a última vez que
        # reconstruímos (ex.: o resize foi só de altura, causado pelo nosso
        # próprio _ajustar_altura), não há necessidade de recalcular — e mais
        # importante: não perdemos nenhum resize de largura real, porque só
        # ignoramos quando a largura realmente é a mesma.
        largura_atual = self._container_abas.width()
        if largura_atual == self._ultima_largura_reconstruida:
            return

        self._reconstruindo_abas = True
        try:
            self._reconstruir_abas()
        finally:
            self._reconstruindo_abas = False

    def _adicionar_botao_aba(self, indice, texto):
        pass

    def atualizar_tema(self):
        self._aplicar_borda()
        self.update()  # força repaint das abas com as novas cores
        # Botões min/max/fec agora vivem em BarraLateralDireita;
        # delega a atualização de tema para ela se estiver disponível.
        if hasattr(self, "_barra_lateral") and self._barra_lateral is not None:
            self._barra_lateral.atualizar_tema()

    def injetar_barra_lateral(self, barra_lateral):
        """Recebe referência à BarraLateralDireita para sincronizar tema."""
        self._barra_lateral = barra_lateral

    def _sincronizar_abas(self, indice: int):
        if self._tab_widget is None:
            return

        tw = self._tab_widget
        n_tabs = tw.count()
        n_bots = sum(1 for b in self._tab_botoes if isinstance(b, AbaWidget))
        # Detecta mudança de estado de preview (itálico) para forçar rebuild
        _prev_ed = getattr(tw, '_preview_editor', None)
        _prev_idx = None
        if _prev_ed is not None:
            for _pi in range(tw.count()):
                if tw.widget(_pi) is _prev_ed:
                    _prev_idx = _pi
                    break
        _ultimo_prev = getattr(self, '_ultimo_preview_idx', -1)
        _agora_prev  = _prev_idx if _prev_idx is not None else -1
        self._ultimo_preview_idx = _agora_prev
        _preview_mudou = (_agora_prev != _ultimo_prev)
        if n_bots != n_tabs or _preview_mudou:
            self._reconstruir_abas()
        else:
            self._atualizar_estado_abas(indice)

    def _atualizar_estado_abas(self, indice_ativo: int):
        """Atualiza estado visual (ativa/inativa) sem recriar os AbaWidget.

        Chamado por _sincronizar_abas() quando o número de abas não mudou —
        apenas a aba ativa trocou. Evita o flickering de _reconstruir_abas().
        Preserva font-style: italic para abas em modo preview.
        """
        t   = tema_global()
        tw  = self._tab_widget
        fs  = AbaWidget._tamanho_fonte()
        cor_ativo   = t.cor("interface.texto",       "#e0e0e0")
        cor_inativo = t.cor("interface.texto_fraco", "#666666")
        _prev_ed = getattr(tw, '_preview_editor', None) if tw else None
        for aba in self._tab_botoes:
            if not isinstance(aba, AbaWidget):
                continue
            eh_ativo = (aba._indice == indice_ativo)
            if aba._ativo == eh_ativo:
                continue
            aba._ativo = eh_ativo
            _cor     = cor_ativo if eh_ativo else cor_inativo
            _is_prev = (_prev_ed is not None and tw is not None
                        and tw.widget(aba._indice) is _prev_ed)
            _italico = " font-style: italic;" if _is_prev else ""
            aba._label.setStyleSheet(
                f"color: {_cor}; font-size: {fs}px;{_italico} background: transparent;"
            )
            aba.update()
        if hasattr(self, "_borda_completa"):
            self._borda_completa.update()

    def _calcular_drop(self, idx_origem, pos_global):
        from PySide6.QtCore import QRect, QPoint
        pos = self._container_abas.mapFromGlobal(pos_global)
        abas = [b for b in self._tab_botoes if isinstance(b, AbaWidget)]
        if not abas:
            return idx_origem, None
        for aba in abas:
            r = QRect(aba.mapTo(self._container_abas, QPoint(0, 0)), aba.size())
            if pos.x() < r.x() + r.width() // 2:
                return aba._indice, (max(0, r.x() - 2), r.y(), r.height())
        ultimo = abas[-1]
        r = QRect(ultimo.mapTo(self._container_abas, QPoint(0, 0)), ultimo.size())
        return ultimo._indice + 1, (r.right(), r.y(), r.height())

    def _atualizar_indicador_reorder(self, idx_origem, pos_global):
        if not hasattr(self, '_indicador_reorder'):
            self._indicador_reorder = _IndicadorReorder(self._container_abas)
        _, geom = self._calcular_drop(idx_origem, pos_global)
        if geom:
            x, y, h = geom
            self._indicador_reorder.mover_para(x, y, h)

    def _esconder_indicador_reorder(self):
        if hasattr(self, '_indicador_reorder'):
            self._indicador_reorder.hide()

    def _finalizar_reorder(self, idx_origem, pos_global):
        self._esconder_indicador_reorder()
        idx_destino, _ = self._calcular_drop(idx_origem, pos_global)
        if idx_destino != idx_origem and idx_destino != idx_origem + 1:
            self._tab_widget.mover_aba(idx_origem, idx_destino)
        self._reconstruir_abas()

    def _fechar_aba_barra(self, indice):
        if self._tab_widget:
            self._tab_widget.fechar_aba(indice)
        self._reconstruir_abas()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.LeftButton:
            # Se estiver maximizado, restaura antes de mover
            _lateral = getattr(self, "_barra_lateral", None)
            _max = _lateral._maximizado if _lateral else self._maximizado
            if _max:
                self._janela.showNormal()
                self._maximizado = False
                if _lateral:
                    _lateral.sincronizar_estado_max(False)
            delta = event.globalPosition().toPoint() - self._drag_pos
            self._janela.move(self._janela.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Delega o toggle para a BarraLateralDireita se disponível
            if hasattr(self, "_barra_lateral") and self._barra_lateral is not None:
                self._barra_lateral._toggle_maximizar()

    def _toggle_maximizar(self):
        """Mantido por compatibilidade — delega para a barra lateral."""
        if hasattr(self, "_barra_lateral") and self._barra_lateral is not None:
            self._barra_lateral._toggle_maximizar()

    def injetar_menus(self, menus: list):
        self._menus_externos = menus

    def injetar_painel_arquivos(self, painel):
        self._painel_arquivos = painel

    def injetar_splitters(self, splitters: dict):
        self._splitters = splitters
        self._splitters["principal"].splitterMoved.connect(
            lambda: QTimer.singleShot(500, self._salvar)
        )
        QTimer.singleShot(80, self._restaurar_larguras)

    # ⚠️  except genérico vazio
    def _salvar(self):
        if not self._splitters:
            return

        # Merge, NÃO sobrescreve: layout.json também guarda "paineis" e
        # "splitters" (visibilidade de File Tree/Git/Terminal/IA — ver
        # MainWindow._salvar_layout_paineis, IMP-09). Sobrescrever o arquivo
        # inteiro aqui apagaria esse estado toda vez que o usuário arrasta o
        # splitter principal.
        dados = {}
        if os.path.isfile(_ARQUIVO_LAYOUT):
            try:
                with open(_ARQUIVO_LAYOUT, encoding="utf-8") as f:
                    _existente = json.load(f)
                if isinstance(_existente, dict):
                    dados = _existente
            except Exception:
                dados = {}

        os.makedirs(PASTA_APPDATA, exist_ok=True)
        dados["tema"]      = self._tema_atual
        dados["tema_json"] = self._tema_json_atual
        dados["larguras"]  = self._splitters["principal"].sizes()
        try:
            with open(_ARQUIVO_LAYOUT, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=2)
        except Exception as e:
            logging.warning("hein layout: falha ao salvar %s: %s", _ARQUIVO_LAYOUT, e)

    # ⚠️  except genérico vazio

    def _restaurar_tema(self):
        try:
            with open(_ARQUIVO_LAYOUT, encoding="utf-8") as f:
                dados = json.load(f)
        except FileNotFoundError:
            # Primeira execucao -- pre-seleciona tema_padrao.json
            _TEMA_PADRAO = os.path.join(PASTA_APPDATA, "temas", "tema_padrao.json")
            if os.path.isfile(_TEMA_PADRAO):
                self._tema_json_atual = _TEMA_PADRAO
                from _CONFIGURA_.gerenciador_tema import tema_global
                tema_global().carregar(_TEMA_PADRAO)
                QTimer.singleShot(0, self._salvar)

            return

        except Exception as e:
            logging.warning("hein layout: falha ao carregar %s: %s", _ARQUIVO_LAYOUT, e)

            return

        tema = dados.get("tema", TEMA_QT_PADRAO)
        if tema != TEMA_QT_PADRAO:
            self._aplicar_tema_qt(tema, salvar=False)

        _TEMA_PADRAO = os.path.join(PASTA_APPDATA, "temas", "tema_padrao.json")
        tema_json = dados.get("tema_json", "")

        # Se nao ha tema salvo ou o arquivo nao existe, usa tema_padrao.json
        if not tema_json or not os.path.isfile(tema_json):
            tema_json = _TEMA_PADRAO

        if os.path.isfile(tema_json):
            self._tema_json_atual = tema_json
            from _CONFIGURA_.gerenciador_tema import tema_global
            tema_global().carregar(tema_json)  # pre-carrega; aplicar_na_janela usara esses dados
            # Se nao havia tema_json em layout.json, persiste a escolha do padrao
            if not dados.get("tema_json"):
                QTimer.singleShot(0, self._salvar)

    def _restaurar_larguras(self):
        try:
            with open(_ARQUIVO_LAYOUT, encoding="utf-8") as f:
                dados = json.load(f)
        except Exception:
            return

        if not isinstance(dados, dict):
            return

        larguras = dados.get("larguras")
        if not larguras:
            # Compatibilidade com o schema "splitters" salvo por
            # MainWindow._salvar_layout_paineis (IMP-09).
            _splitters_salvos = dados.get("splitters")
            if isinstance(_splitters_salvos, dict):
                larguras = _splitters_salvos.get("principal")
        try:
            if (isinstance(larguras, (list, tuple)) and len(larguras) == 3
                    and all(isinstance(v, (int, float)) for v in larguras)):
                self._splitters["principal"].setSizes([int(v) for v in larguras])
        except Exception as e:
            logging.warning("hein layout: falha ao restaurar larguras: %s", e)

    # ⚠️  função grande (92 linhas) | except genérico vazio
    def _abrir_menu(self):
        from _UTILITARIOS_.hein_context_menu import heinContextMenu
        from _CONFIGURA_.gerenciador_tema import tema_global
        _ICONES_MENU = {
            "Arquivo":    "mdi.file-outline",
            "Editar":     "mdi.pencil-outline",
            "Executar":   "mdi.play-circle-outline",
            "Visualizar": "mdi.eye-outline",
            "Projeto":    "mdi.view-dashboard",
            "Ajuda":      "mdi.help-circle-outline",
        }
        _OCULTOS  = {"Executar", "Editar"}
        menu = heinContextMenu(parent=self)
        for m in self._menus_externos:
            if m.title() in _OCULTOS:
                continue
            nome_icone = _ICONES_MENU.get(m.title())
            if nome_icone:
                try:
                    m.setIcon(icone_tema(nome_icone))
                except Exception:
                    pass
            m.setStyleSheet(menu.styleSheet())
            menu.addMenu(m)

        menu.addSeparator()

        # — Submenu: Tema Qt ——————————————————————————————
        sub_tema = QMenu("Temas UI", menu)
        sub_tema.setStyleSheet(menu.styleSheet())
        try:
            sub_tema.setIcon(icone_tema("mdi.palette-outline"))
        except Exception:
            pass

        grupo_tema = QActionGroup(sub_tema)
        grupo_tema.setExclusive(True)
        for nome_tema in TEMAS_QT_DISPONIVEIS:
            acao = QAction(nome_tema, sub_tema)
            acao.setCheckable(True)
            acao.setChecked(nome_tema == self._tema_atual)
            acao.triggered.connect(lambda checked=False, n=nome_tema: self._aplicar_tema_qt(n))
            grupo_tema.addAction(acao)
            sub_tema.addAction(acao)
        menu.addMenu(sub_tema)

        # — Submenu: Tema hein (JSON) ———————————————————
        sub_json = QMenu("Temas hein", menu)
        sub_json.setStyleSheet(menu.styleSheet())
        try:
            sub_json.setIcon(icone_tema("mdi.palette-advanced"))
        except Exception:
            pass
        temas_json = tema_global().listar_temas_json()
        if temas_json:
            grupo_json = QActionGroup(sub_json)
            grupo_json.setExclusive(True)
            for nome_tema_j, caminho_j in temas_json:
                acao_j = QAction(nome_tema_j, sub_json)
                acao_j.setCheckable(True)
                acao_j.setChecked(caminho_j == self._tema_json_atual)
                acao_j.triggered.connect(
                    lambda checked=False, c=caminho_j, n=nome_tema_j:
                        self._aplicar_tema_json(c)
                )
                grupo_json.addAction(acao_j)
                sub_json.addAction(acao_j)
        else:
            acao_vazio = QAction("Nenhum tema em temas/", sub_json)
            acao_vazio.setEnabled(False)
            sub_json.addAction(acao_vazio)
        menu.addMenu(sub_json)

        # — Submenu: Pack de ícones ——————————————————————
        sub_pack = QMenu("Temas Ícones", menu)
        sub_pack.setStyleSheet(menu.styleSheet())
        try:
            sub_pack.setIcon(icone_tema("mdi.palette-swatch-outline"))
        except Exception:
            pass
        grupo_pack = QActionGroup(sub_pack)
        grupo_pack.setExclusive(True)
        for nome_pack in PACKS_ICONES:
            acao = QAction(nome_pack, sub_pack)
            acao.setCheckable(True)
            acao.setChecked(nome_pack == _CFG._PACK_ATIVO)
            acao.triggered.connect(lambda checked=False, p=nome_pack: self._aplicar_pack_icones(p))
            grupo_pack.addAction(acao)
            sub_pack.addAction(acao)
        menu.addMenu(sub_pack)
        pos = self._lbl_titulo.mapToGlobal(self._lbl_titulo.rect().bottomLeft())
        menu.exec(pos)

    def _aplicar_tema_json(self, caminho: str) -> None:
        """Aplica um tema JSON da pasta temas/ e persiste a escolha."""
        from _CONFIGURA_.gerenciador_tema import tema_global
        if tema_global().aplicar_tema_json(caminho):
            self._tema_json_atual = caminho
            self._salvar()
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self._janela, "Tema inválido",
                f"Não foi possível carregar o tema:\n{caminho}",
            )

    def _aplicar_pack_icones(self, nome: str):
        """Troca o pack de ícones ativo e reconstrói as abas abertas."""
        _CFG._PACK_ATIVO = nome
        _cache_icones_aba.clear()
        if self._tab_widget:
            self._reconstruir_abas()
        if self._painel_arquivos and hasattr(self._painel_arquivos, "atualizar_icones"):
            self._painel_arquivos.atualizar_icones()

    def _nao_instalado(self, pacote: str):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(
            self._janela, "Tema não encontrado",
            f"O pacote '{pacote}' não está instalado.\nInstale com:  pip install {pacote}",
        )

    def _aplicar_borda(self):
        self.setStyleSheet("")
        self.update()

    # ⚠️  função grande (51 linhas)
    def _aplicar_tema_qt(self, nome: str, salvar: bool = True):
        """Aplica um tema Qt por nome e salva a escolha em layout.json."""
        self._tema_atual = nome
        app = QApplication.instance()
        app.setStyleSheet("")
        nome_lower = nome.lower()
        if nome_lower == "fusion":
            app.setStyle("Fusion")
        elif nome_lower == "windows":
            app.setStyle("Windows")
        elif nome_lower == "windowsvista":
            app.setStyle("WindowsVista")
        elif nome_lower == "qdarkstyle":
            try:
                import qdarkstyle
                app.setStyleSheet(qdarkstyle.load_stylesheet())
            except ImportError:
                self._nao_instalado("qdarkstyle")
        elif nome_lower == "qtmaterial":
            try:
                from qt_material import apply_stylesheet
                apply_stylesheet(app, theme="dark_teal.xml")
            except ImportError:
                self._nao_instalado("qt-material")
        elif nome_lower == "qtmodern":
            try:
                import qtmodern.styles
                qtmodern.styles.dark(app)
            except ImportError:
                self._nao_instalado("qtmodern")
        elif nome_lower == "pydracula":
            try:
                qss_path = os.path.join(os.path.dirname(__file__), "PyDracula.qss")
                with open(qss_path, encoding="utf-8") as f:
                    app.setStyleSheet(f.read())
            except FileNotFoundError:
                self._nao_instalado("PyDracula.qss")
        elif nome_lower == "pyqtdarktheme":
            try:
                import qdarktheme
                app.setStyleSheet(qdarktheme.load_stylesheet("dark"))
            except ImportError:
                self._nao_instalado("pyqtdarktheme")
        elif nome_lower == "pyqtdarktheme_light":
            try:
                import qdarktheme
                app.setStyleSheet(qdarktheme.load_stylesheet("light"))
            except ImportError:
                self._nao_instalado("pyqtdarktheme")
        if salvar:
            self._salvar()

    def _atualizar_cor_linha_sep(self):
        if not hasattr(self, "_linha_sep"):
            return

        t   = tema_global()
        cor = t.cor("interface.borda_externa", t.cor("interface.fundo_aba_ativa", BORDA_GERAL))
        self._linha_sep.atualizar(cor, self._linha_sep._larg, self._linha_sep._estilo)
        self._linha_sep.setVisible(False)  # IMP-03: nunca visível quando gerenciado por borda

    def atualizar_linha_sep(self, cor: str, larg: int, estilo: str):
        """Chamado por gerenciador_configurar para aplicar estilo da borda.

        Quando há borda tracejada/colorida ativa (larg > 0), o contorno
        completo (_borda_completa) já desenha o rodapé inteiro da barra
        — inclusive contornando a aba ativa. Manter a _linha_sep visível
        nesse caso desenhava uma segunda linha quase sobreposta no mesmo
        lugar, dando a impressão de "linha duplicada". Por isso a
        _linha_sep só fica visível quando NÃO há borda configurada
        (larg == 0), servindo de separador simples de fallback.
        """
        if not hasattr(self, "_linha_sep"):
            return

        self._linha_sep.atualizar(cor, larg, estilo)
        self._linha_sep.setVisible(False)  # IMP-03: some sempre, com ou sem borda
        self._borda_cor    = cor
        self._borda_larg   = larg
        self._borda_estilo = estilo
        if hasattr(self, "_borda_completa"):
            self._borda_completa.atualizar(cor, larg, estilo)
        self._reconstruir_abas()

    def paintEvent(self, event):
        t      = tema_global()
        fundo  = t.cor("interface.fundo_painel", FUNDO_PAINEL)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(fundo))
        painter.end()

    def _carregar_recentes(self) -> list:
        try:
            with open(_ARQUIVO_RECENTES, encoding="utf-8") as f:
                dados = json.load(f)

            return [p for p in dados if isinstance(p, str)]

        except Exception:
            return []

    # ⚠️  except genérico vazio
    def _salvar_recentes(self, caminhos: list):
        os.makedirs(PASTA_APPDATA, exist_ok=True)
        try:
            with open(_ARQUIVO_RECENTES, "w", encoding="utf-8") as f:
                json.dump(caminhos[:_MAX_RECENTES], f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def registrar_projeto_aberto(self, caminho: str):
        caminho  = os.path.normpath(caminho)
        recentes = self._carregar_recentes()
        if caminho in recentes:
            recentes.remove(caminho)
        recentes.insert(0, caminho)
        self._salvar_recentes(recentes[:_MAX_RECENTES])

    def _abrir_menu_recentes(self):
        from _UTILITARIOS_.hein_context_menu import heinContextMenu
        recentes = self._carregar_recentes()

        if not recentes:
            itens = [("(nenhum projeto recente)", "mdi.folder-off-outline", None)]
        else:
            itens = []
            for caminho in recentes:
                nome  = os.path.basename(caminho)
                label = f"{nome}  —  {caminho}"
                itens.append((label, "mdi.folder-outline",
                               lambda checked=False, p=caminho: self._abrir_projeto_recente(p)))
            itens.append(None)
            itens.append(("Limpar histórico", "mdi.trash-can-outline", self._limpar_recentes))

        menu = heinContextMenu(parent=self, itens=itens)
        if not recentes:
            menu.acao("(nenhum projeto recente)").setEnabled(False)
        menu.exec(self._lbl_titulo.mapToGlobal(self._lbl_titulo.rect().bottomLeft()))

    def _abrir_projeto_recente(self, caminho: str):
        """Abre um recente em uma nova IDE e encerra esta instância.

        A troca de projeto dentro da mesma MainWindow deixa terminais,
        processos e estado de execução do projeto anterior vivos. Recentes
        deve ter o mesmo isolamento da JanelaPicker: uma instância completa
        por projeto.
        """
        if not os.path.isdir(caminho):
            self._salvar_recentes(
                [p for p in self._carregar_recentes() if p != caminho]
            )
            return

        from _APP_.Boas_Vindas.lancador_projeto import abrir_projeto_novo_processo

        janela = self._janela
        janela.hide()
        QApplication.processEvents()
        abrir_projeto_novo_processo(caminho)

        # Deixa o menu terminar o callback antes de disparar o closeEvent
        # completo da MainWindow (terminais, threads, overlay e QApplication).
        QTimer.singleShot(0, janela.close)

    def _limpar_recentes(self):
        self._salvar_recentes([])

    def notificar_update(self, versao: str, url_html: str, url_exe: str, body: str):
        """Acende o chip de versão indicando que há update disponível."""
        self._url_update     = url_html
        self._url_exe_update = url_exe
        self._body_update    = body
        self._versao_update  = versao
        self._btn_versao.setText(f"↑ v{versao}")
        self._btn_versao.setEnabled(True)
        self._btn_versao.setStyleSheet("""
            QPushButton#btn_versao {
                background: #1a2e1a; color: #7ecf7e;
                border: 1px solid #3d7a3d; border-radius: 3px;
                font-size: 10px; padding: 0 8px;
                margin-left: 8px; margin-right: 5px;
            }
            QPushButton#btn_versao:hover {
                background: #203820; color: #9eff9e;
                border-color: #4d8a4d;
            }
        """)
        self._btn_versao.clicked.connect(self._abrir_update)
        self._layout_interno.addWidget(self._btn_versao)

    def _abrir_update(self):
        """Abre o diálogo de atualização com release notes e download."""
        from _UTILITARIOS_.dialogo_update import DialogoUpdate
        dlg = DialogoUpdate(
            self._versao_update,
            self._url_update,
            self._url_exe_update,
            self._body_update,
            parent=self,
        )
        dlg.exec()
