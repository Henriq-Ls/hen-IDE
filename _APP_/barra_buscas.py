# 📁 _APP_/barra_buscas.py
# -*- coding: utf-8 -*-
"""
Três barras de busca independentes — uma por painel da IDE hein.

  BarraEsquerda  → painel esquerdo (FileTree) — filtro de arquivos

  BarraCentral   → painel central — linha única com campo + controles embutidos.
                   Largura direita limitada pelo outline (setRightReserva).
                   Modos:
                     • Sem prefixo   → busca no arquivo atual (Ctrl+F)
                     • @termo        → busca universal no projeto
                     • *nome         → busca arquivo por nome
                     • :42           → vai para linha 42
                     • #marcação     → lista marcações do projeto
                     • >cmd          → command palette

  BarraDireita   → painel direito (Outline) — reservado
"""
from _UTILITARIOS_.icones import icone_tema
from _UTILITARIOS_._ajuda_ import criar_botao_ajuda
from _UTILITARIOS_._ajuda_.conteudos import busca as _ajuda_busca
from PySide6.QtGui     import QTextCursor
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPlainTextEdit,
    QToolButton, QLabel, QSizePolicy, QPushButton, QCheckBox,
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import ( BORDA_TOPO,
)

# ── paleta interna ────────────────────────────────────────────────────────────

def _c(chave: str, fb: str) -> str:
    try:
        return tema_global().cor(chave, fb)

    except Exception:
        return fb

def _estilo_campo() -> str:
    fundo = _c("interface.inputs",     "#0d1a0d")
    texto = _c("interface.texto",      "#e8f5e8")
    borda = _c("interface.borda",      "#1f3d1f")
    foco  = _c("interface.borda_foco", "#6B8E23")

    return (

        f"QPlainTextEdit {{"
        f"  background: {fundo}; color: {texto};"
        f"  border: 0px solid {borda}; border-radius: 3px;"
        f"  padding: 1px 6px; font-size: 11px;"
        f"}}"
        f"QPlainTextEdit:focus {{ border-color: {foco}; }}"
    )

def _estilo_btn_icone() -> str:
    hover = _c("interface.fundo_item_hover", "#1a3a1a")
    texto = _c("interface.texto_fraco",      "#6b8f6b")
    ativo = _c("interface.texto",            "#e8f5e8")

    return (

        f"QPushButton {{"
        f"  background: transparent; color: {texto};"
        f"  border: none; border-radius: 3px;"
        f"  padding: 0 4px; font-size: 11px;"
        f"}}"
        f"QPushButton:hover {{ background: {hover}; color: {ativo}; }}"
        f"QPushButton:checked {{ color: {ativo}; background: {hover}; }}"
    )

def _estilo_campo_inner() -> str:
    texto = _c('interface.texto', '#e8f5e8')

    return (

        f"QPlainTextEdit {{"
        f"  background: transparent; color: {texto};"
        f"  border: none;"
        f"  padding: 1px 6px; font-size: 11px;"
        f"}}"
    )

def _estilo_barra() -> str: # Mesma cor do gutter do editor — TESTANDO_IA fica "acima" da borda
    fundo = _c("editor.fundo_calha", "#020202")

    return f"background-color: {fundo};"

# ══════════════════════════════════════════════════════════════════════════════
# _CampoBarraBusca  —  QPlainTextEdit expansível
# ══════════════════════════════════════════════════════════════════════════════

class _CampoBarraBusca(QPlainTextEdit):
    """
    Campo da BarraCentral.
    - Uma linha em repouso; expande até MAX_LINHAS quando o conteúdo cresce.
    - Enter     → emite confirmado.
    - Shift+Enter → nova linha (busca de bloco).
    - Esc       → emite fechar_pressionado.
    """

    confirmado         = Signal()
    fechar_pressionado = Signal()

    MAX_LINHAS = 6

    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        # AsNeeded (nao AlwaysOff): quando o texto passar de MAX_LINHAS, o
        # campo para de crescer (ver setMaximumHeight abaixo) e o usuario
        # rola dentro dele em vez de perder o conteudo excedente.
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Fixed (nao Preferred): o campo nunca deve reivindicar espaco
        # vertical extra do layout -- so a largura acompanha a janela.
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setTabChangesFocus(True)
        self.document().contentsChanged.connect(self._agendar_ajuste)
        # Ajusta a altura JA, de forma sincrona -- sem isso o Qt usa o
        # sizeHint() nativo do QPlainTextEdit (enorme) ate o primeiro timer
        # disparar, e e esse instante que aparece como campo GIGANTE antes
        # de encolher (bug Ctrl+F GIGANTE).
        self._ajustar_altura()
        # setMaximumHeight = teto fisico: mesmo que algum recalculo futuro
        # (redimensionamento, tema, timer atrasado) erre a conta, o Qt
        # nunca deixa o campo passar desse valor.
        self.setMaximumHeight(self._linha_altura() * self.MAX_LINHAS)
        QTimer.singleShot(0, self._ajustar_altura)

    def _linha_altura(self) -> int:
        fm = self.fontMetrics()
        m  = self.contentsMargins()

        return fm.lineSpacing() + m.top() + m.bottom() + int(self.document().documentMargin()) * 2 + 6

    def _agendar_ajuste(self):
        QTimer.singleShot(0, self._ajustar_altura)

    def _ajustar_altura(self):
        # documentSize() depende do viewport ter sido layoutado com a largura
        # correta. Como o campo nasce oculto (width=0), o layout fica errado
        # e trava em MAX_LINHAS mesmo com timers -- bug Ctrl+F GIGANTE.
        # Solucao: contar linhas pelo texto real (\ n), nao pelo layout.
        lh = self.fontMetrics().lineSpacing()
        if lh <= 0:
            return

        texto = self.toPlainText()
        linhas_texto = max(1, texto.count('\n') + 1) if texto else 1
        linhas = min(linhas_texto, self.MAX_LINHAS)
        doc = self.document()
        m = self.contentsMargins()
        overhead = m.top() + m.bottom() + int(doc.documentMargin()) * 2 + 6
        nova_h = lh * linhas + overhead
        if nova_h != self.height():
            self.setFixedHeight(nova_h)
            self.updateGeometry()
            # propaga o novo tamanho para a BarraCentral
            pai = self.parent()
            while pai:
                pai.updateGeometry()
                if pai.parent() is None:
                    break
                pai = pai.parent()
                if hasattr(pai, '_barra_central') or pai.__class__.__name__ == 'BarraCentral':
                    break

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # A altura do documento depende da largura (quebra por WidgetWidth).
        # Sem isto, a 1a medicao - feita com largura 0, pois a barra nasce
        # oculta - trava o campo no MAX_LINHAS para sempre, ja que
        # _ajustar_altura so e reagendado quando o TEXTO muda, nao quando a
        # LARGURA muda (bug do Ctrl+F GIGANTE).
        if event.oldSize().width() != event.size().width():
            self._agendar_ajuste()

    def sizeHint(self) -> QSize:
        return QSize(200, self._linha_altura())

    def minimumSizeHint(self) -> QSize:
        return QSize(80, self._linha_altura())

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, t: str):
        self.setPlainText(t)

    def keyPressEvent(self, event):
        key  = event.key()
        mods = event.modifiers()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if mods & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.confirmado.emit()

            return

        if key == Qt.Key_Escape:
            self.fechar_pressionado.emit()

            return

        super().keyPressEvent(event)

# ══════════════════════════════════════════════════════════════════════════════
# BarraCentral
# ══════════════════════════════════════════════════════════════════════════════

MODO_GLOBAL  = "global"
MODO_ARQUIVO = "arquivo"

MODO_PROJETO = "projeto"
MODO_LEMBRAR = "lembrar"

class BarraCentral(QWidget):
    """
    Barra de busca universal — layout em linha única:
      [🔍 campo expansível] [▲][▼][0/0] [Substituir][Sub.tudo] [Aa][.*] [✕] [  reserva outline  ]

    Começa oculta. Aparece via mostrar(modo).

    Sinais:
        buscar_global(str)      — prefixos @, *, #, >
        buscar_arquivo(str)     — sem prefixo (str vazia = limpar resultados)
        ir_para_linha(int)      — :N
        modo_substituicao(str)  — texto para substituição
        fechar()                — X ou Esc
        proximo()               — ▼
        anterior()              — ▲
        substituir_um()         — Substituir
        substituir_tudo()       — Sub. tudo
    """

    buscar_global     = Signal(str)
    buscar_arquivo    = Signal(str)
    ir_para_linha     = Signal(int)
    modo_substituicao = Signal(str)
    fechar            = Signal()

    proximo         = Signal()
    anterior        = Signal()
    substituir_um   = Signal()
    substituir_tudo = Signal()

    # ⚠️  função grande (115 linhas)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._editor_ref = None

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"BarraCentral {{ {_estilo_barra()} }}")
        # Fixed (nao Preferred): quando o splitter do terminal libera
        # espaco vertical, esse espaco deve ir para o editor, nunca para
        # a barra de busca -- e Preferred deixava o layout "aceitar" essa
        # sobra (bug: campo esticando ao encolher o terminal).
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # ── Layout principal: linha única ─────────────────────────────
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(6, 3, 4, 3)
        self._lay.setSpacing(4)

        # ── ícone de busca ────────────────────────────────────────────
        self._icone_label = QLabel()
        self._icone_label.setStyleSheet("background: transparent;")
        try:
            self._icone_label.setPixmap(
                icone_tema("fa5s.search", color=_c("interface.icone", "#6B8E23")).pixmap(13, 13)
            )
        except Exception:
            self._icone_label.setText("🔍")
        self._lay.addWidget(self._icone_label)

        # ── container com background inputs ao redor do campo ────────
        _fundo   = _c("interface.inputs", "#082C3A")
        _borda   = _c("interface.borda",  "#1f3d1f")
        _foco    = _c("interface.borda_foco", "#6B8E23")
        _campo_wrap = QWidget()
        _campo_wrap.setObjectName("CampoWrap")
        _campo_wrap.setStyleSheet(
            f"QWidget#CampoWrap {{ background: {_fundo}; border: 1px solid {_borda};"
            f" border-radius: 3px; }}"
        )
        _wrap_lay = QHBoxLayout(_campo_wrap)
        _wrap_lay.setContentsMargins(2, 1, 2, 1)
        _wrap_lay.setSpacing(0)
        # mesmo motivo do BarraCentral acima: nunca aceitar altura extra.
        _campo_wrap.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # ── campo de texto expansível ─────────────────────────────────
        self._campo = _CampoBarraBusca(
            "buscar...   @universal   *arquivo   :linha   #marcação"
        )
        texto_c = _c('interface.texto', '#e8f5e8')
        self._campo.setStyleSheet(
            f"QPlainTextEdit {{ background: transparent; color: {texto_c};"
            f" border: none; padding: 1px 4px; font-size: 11px; }}"
        )
        self._campo.document().contentsChanged.connect(self._ao_digitar)
        self._campo.fechar_pressionado.connect(self._ao_fechar)
        self._campo.confirmado.connect(self.proximo.emit)
        _wrap_lay.addWidget(self._campo)
        self._campo_wrap = _campo_wrap
        self._lay.addWidget(_campo_wrap, 1)

        # ── navegação ▲ ▼ 0/0 ────────────────────────────────────────
        self._btn_anterior_ctrl = QPushButton("▲")
        self._btn_proximo_ctrl  = QPushButton("▼")
        for _b in (self._btn_anterior_ctrl, self._btn_proximo_ctrl):
            _b.setFixedSize(22, 18)
        self._btn_anterior_ctrl.clicked.connect(self.anterior.emit)
        self._btn_proximo_ctrl.clicked.connect(self.proximo.emit)

        self._lbl_contador = QLabel("0/0")
        self._lbl_contador.setMinimumWidth(34)

        self._lay.addWidget(self._btn_anterior_ctrl)
        self._lay.addWidget(self._btn_proximo_ctrl)
        self._lay.addWidget(self._lbl_contador)

        # ── substituição (visíveis só em modo substituicao) ───────────
        self._btn_sub_ctrl      = QPushButton("Substituir")
        self._btn_sub_tudo_ctrl = QPushButton("Sub. tudo")
        self._btn_sub_ctrl.clicked.connect(self.substituir_um.emit)
        self._btn_sub_tudo_ctrl.clicked.connect(self.substituir_tudo.emit)
        self._btn_sub_ctrl.hide()
        self._btn_sub_tudo_ctrl.hide()
        self._lay.addWidget(self._btn_sub_ctrl)
        self._lay.addWidget(self._btn_sub_tudo_ctrl)

        # ── opções Aa .* ──────────────────────────────────────────────
        self._chk_maiuscula = QCheckBox("Aa")
        self._chk_maiuscula.setToolTip("Diferenciar maiúsculas")
        self._chk_regex = QCheckBox(".*")
        self._chk_regex.setToolTip("Expressão regular")
        self._lay.addWidget(self._chk_maiuscula)
        self._lay.addWidget(self._chk_regex)

        # ── ajuda ? ──────────────────────────────────────────────────
        self._btn_ajuda = criar_botao_ajuda(
            _ajuda_busca.texto, titulo="Como usar a busca",
            tooltip="Como usar a busca", parent=self,
        )
        self._lay.addWidget(self._btn_ajuda)

        # ── fechar ✕ ─────────────────────────────────────────────────
        self._btn_fechar = QPushButton("✕")
        self._btn_fechar.setFixedSize(18, 18)
        self._btn_fechar.setStyleSheet(
            "QPushButton { background: transparent; color: #555; border: none;"
            " font-size: 9px; padding: 0; }"
            "QPushButton:hover { color: #e06c75; }"
        )
        self._btn_fechar.clicked.connect(self._ao_fechar)
        self._lay.addWidget(self._btn_fechar)

        # ── spacer direito = reserva do outline ───────────────────────
        # Ocupa o mesmo espaço que o outline + alça para a barra não
        # sobrepor visualmente o outline (atualizado via setRightReserva).
        self._spacer_outline = QWidget()
        self._spacer_outline.setFixedWidth(0)
        self._spacer_outline.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._lay.addWidget(self._spacer_outline)

        # esconde controles de busca e nav no estado inicial
        self._controles_visiveis = False
        self._ocultar_controles_nav()

        self._aplicar_tema_controles()

        # começa oculta
        self.hide()

    # ── API pública ────────────────────────────────────────────────────

    @property
    def maiuscula(self) -> bool:
        return self._chk_maiuscula.isChecked()

    @property
    def regex(self) -> bool:
        return self._chk_regex.isChecked()

    # 💡 modo_opc = Literal["arquivo"] ← defina os valores válidos
    def mostrar(self, modo: str = "arquivo"):
        """Exibe a barra e ajusta controles para o modo.
        modo: 'arquivo' | 'substituicao' | 'linha'
        """
        modo_com_nav = modo in ("arquivo", "substituicao")
        if modo_com_nav:
            self._mostrar_controles_nav()
        else:
            self._ocultar_controles_nav()
        self._btn_sub_ctrl.setVisible(modo == "substituicao")
        self._btn_sub_tudo_ctrl.setVisible(modo == "substituicao")
        self.show()
        # _campo._ajustar_altura() conta linhas pelo texto (nao documentSize),
        # entao pode rodar sincrono. adjustSize() em seguida forca a BarraCentral
        # a redimensionar para o sizeHint() real do layout -- sem isso ela expande
        # para preencher o espaco que o pai oferece, ignorando o filho.
        self._campo._ajustar_altura()
        self.adjustSize()

    def setRightReserva(self, largura: int):
        """Ajusta o spacer direito para não sobrepor o outline.
        O spacer recebe a cor de fundo do painel do outline para criar a
        ilusão visual de que o outline sobe até o topo da coluna central.
        """
        largura = max(0, largura)
        if self._spacer_outline.width() != largura:
            self._spacer_outline.setFixedWidth(largura)
        # cor do painel outline para ilusão visual de "outline até o topo"
        try:
            from _CONFIGURA_.gerenciador_tema import tema_global as _tg
            cor = _tg().cor("interface.fundo_painel", "#0F1210")
        except Exception:
            cor = "#0F1210"
        self._spacer_outline.setStyleSheet(f"background: {cor}; border: none;")
        self._spacer_outline.setAttribute(Qt.WA_StyledBackground, True)

    def atualizar_contador(self, texto: str):
        self._lbl_contador.setText(texto)

    def instalar_atalhos(self, janela: QWidget):
        pass

    def focar(self, texto: str = ""):
        self._campo.setFocus()
        if texto:
            self._campo.setPlainText(texto)
            cursor = self._campo.textCursor()
            cursor.movePosition(QTextCursor.End)
            self._campo.setTextCursor(cursor)
        else:
            self._campo.selectAll()

    def set_editor(self, editor):
        self._editor_ref = editor

    def texto(self) -> str:
        return self._campo.toPlainText()

    def limpar(self):
        self._campo.clear()

    def ativar_substituicao(self, termo: str = ""):
        self._campo.setFocus()
        if termo:
            self._campo.setPlainText(termo)
        self.modo_substituicao.emit(self._campo.toPlainText())

    # ── helpers internos ───────────────────────────────────────────────

    def _mostrar_controles_nav(self):
        for w in (self._btn_anterior_ctrl, self._btn_proximo_ctrl,
                  self._lbl_contador, self._chk_maiuscula, self._chk_regex):
            w.show()
        self._controles_visiveis = True

    def _ocultar_controles_nav(self):
        for w in (self._btn_anterior_ctrl, self._btn_proximo_ctrl,
                  self._lbl_contador, self._chk_maiuscula, self._chk_regex,
                  self._btn_sub_ctrl, self._btn_sub_tudo_ctrl):
            w.hide()
        self._controles_visiveis = False

    def _aplicar_tema_controles(self):
        t = _c("interface.texto_fraco",      "#5a7a5a")
        h = _c("interface.fundo_item_hover", "#1a3a1a")
        a = _c("interface.texto",            "#e8f5e8")
        estilo = (
            f"QPushButton {{ background: transparent; color: {t}; border: none;"
            f" border-radius: 3px; padding: 0 4px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {h}; color: {a}; }}"
            f"QCheckBox {{ color: {t}; font-size: 11px; }}"
            f"QLabel {{ color: {t}; font-size: 11px; background: transparent; }}"
        )
        for w in (self._btn_anterior_ctrl, self._btn_proximo_ctrl,
                  self._lbl_contador, self._chk_maiuscula, self._chk_regex,
                  self._btn_sub_ctrl, self._btn_sub_tudo_ctrl):
            w.setStyleSheet(estilo)

    # ⚠️  except genérico vazio
    def atualizar_tema(self):
        self.setStyleSheet(f"BarraCentral {{ {_estilo_barra()} }}")
        _fundo = _c("interface.inputs", "#082C3A")
        _borda = _c("interface.borda",  "#1f3d1f")
        self._campo_wrap.setStyleSheet(
            f"QWidget#CampoWrap {{ background: {_fundo}; border: 1px solid {_borda};"
            f" border-radius: 3px; }}"
        )
        texto_c = _c('interface.texto', '#e8f5e8')
        self._campo.setStyleSheet(
            f"QPlainTextEdit {{ background: transparent; color: {texto_c};"
            f" border: none; padding: 1px 4px; font-size: 11px; }}"
        )
        self._aplicar_tema_controles()
        try:
            self._icone_label.setPixmap(
                icone_tema("fa5s.search", color=_c("interface.icone", "#6B8E23")).pixmap(13, 13)
            )
        except Exception:
            pass

    # ── digitação ──────────────────────────────────────────────────────

    def _ao_digitar(self):
        termo = self._campo.toPlainText().strip()
        if not termo:
            self.buscar_arquivo.emit("")

            return

        if termo.startswith(':'):
            resto = termo[1:].strip()
            try:
                n = int(resto)
                self.ir_para_linha.emit(n)
            except ValueError:
                pass
        elif termo[0] in ('@', '*', '#', '>'):
            self.buscar_global.emit(termo)
        else:
            self.buscar_arquivo.emit(termo)

    def _ao_fechar(self):
        self._campo.clear()
        self.fechar.emit()

