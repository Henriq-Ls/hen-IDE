# 📁 _APP_/painel_menu_hein.py
"""
PainelMenuHein — aba de menu da IDE exibida no TerminalTabWidget.
Substitui o QMenu popup do botão 'hein', listando todas as opções
de forma plana e clicável dentro do painel inferior central.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QButtonGroup,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from _UTILITARIOS_.icones import icone_tema
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import (
    FUNDO_PAINEL, VERDE, CINZA_ESCURO,
    TEMAS_QT_DISPONIVEIS, PACKS_ICONES,
    FONTE_UI, FONTE_UI_FALLBACK,
)
import _CONFIGURA_ as _CFG
_OCULTOS = {"Executar", "Editar"}

_CSS_SECAO = """
QLabel#secao_header {
    color: #4ec994;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
    padding: 10px 0 3px 0;
    background: transparent;
}
"""

_CSS_CHIP_ON = f"""
QPushButton {{
    background: #1a3a2a;
    color: {VERDE};
    border: 1px solid {VERDE};
    border-radius: 4px;
    font-size: 11px;
    padding: 3px 10px;
    font-weight: bold;
}}
QPushButton:hover {{
    background: #1f4430;
}}
"""

class PainelMenuHein(QWidget):
    """
    Painel de menu da IDE aberto como aba no TerminalTabWidget.
    Recebe uma referência à BarraTitulo para extrair menus, temas e ícones.
    """

    def __init__(self, barra_aba_topo, parent=None):
        super().__init__(parent)
        self._barra = barra_aba_topo
        self._build_estrutura()
        self._popular()

    # ── Estrutura base ────────────────────────────────────────────────────────

    def _build_estrutura(self):
        self.setStyleSheet(f"background: {tema_global().cor('menu_contexto.fundo', '#070706')};")

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {tema_global().cor('menu_contexto.fundo', '#070706')}; }}"
            f"QScrollBar:vertical {{ background: {CINZA_ESCURO}; width: 8px; }}"
            f"QScrollBar::handle:vertical {{ background: #444; border-radius: 4px; min-height: 20px; }}"
        )

        self._container = QWidget()
        self._container.setStyleSheet(f"background: {tema_global().cor('menu_contexto.fundo', '#070706')};")
        self._corpo = QVBoxLayout(self._container)
        self._corpo.setSpacing(0)
        self._corpo.setContentsMargins(20, 8, 20, 16)
        self._corpo.setAlignment(Qt.AlignTop)

        scroll.setWidget(self._container)
        main.addWidget(scroll)

    # ── Popularização ─────────────────────────────────────────────────────────

    def atualizar(self, barra_aba_topo):
        """Atualiza o conteúdo ao re-abrir a aba (ex: novo projeto abre novos menus)."""
        self._barra = barra_aba_topo
        while self._corpo.count():
            item = self._corpo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._popular()

    # ⚠️  função grande (59 linhas)
    def _popular(self):
        barra = self._barra

        # ── Menus externos (Arquivo, Visualizar, Projeto, Ajuda…) ─────────────
        for qmenu in barra._menus_externos:
            titulo = qmenu.title()
            if titulo in _OCULTOS:
                continue
            acoes = [a for a in qmenu.actions() if not a.menu()]
            if acoes:
                self._adicionar_separador_secao(titulo)
                for acao in acoes:
                    self._adicionar_acao(acao)

        # ── Tema Qt ───────────────────────────────────────────────────────────
        self._adicionar_separador_secao("Tema Qt")
        grp_qt = QButtonGroup(self)
        grp_qt.setExclusive(True)
        chip_row_qt = self._nova_linha_chips()
        for nome_tema in TEMAS_QT_DISPONIVEIS:
            ativo = (nome_tema == barra._tema_atual)
            btn = self._criar_chip(nome_tema, ativo, grp_qt)
            btn.clicked.connect(
                lambda checked=False, n=nome_tema: barra._aplicar_tema_qt(n)
            )
            chip_row_qt.addWidget(btn)
        chip_row_qt.addStretch()

        # ── Tema hein JSON ────────────────────────────────────────────────────
        temas_json = tema_global().listar_temas_json()
        if temas_json:
            self._adicionar_separador_secao("Tema hein (JSON)")
            grp_json = QButtonGroup(self)
            grp_json.setExclusive(True)
            chip_row_json = self._nova_linha_chips()
            for nome_j, caminho_j in temas_json:
                ativo = (caminho_j == barra._tema_json_atual)
                btn = self._criar_chip(nome_j, ativo, grp_json)
                btn.clicked.connect(
                    lambda checked=False, c=caminho_j: barra._aplicar_tema_json(c)
                )
                chip_row_json.addWidget(btn)
            chip_row_json.addStretch()

        # ── Pack de ícones ────────────────────────────────────────────────────
        self._adicionar_separador_secao("Pack de Ícones")
        grp_pack = QButtonGroup(self)
        grp_pack.setExclusive(True)
        chip_row_pack = self._nova_linha_chips()
        for nome_pack in PACKS_ICONES:
            ativo = (nome_pack == _CFG._PACK_ATIVO)
            btn = self._criar_chip(nome_pack, ativo, grp_pack)
            btn.clicked.connect(
                lambda checked=False, p=nome_pack: barra._aplicar_pack_icones(p)
            )
            chip_row_pack.addWidget(btn)
        chip_row_pack.addStretch()

        self._corpo.addStretch()

    # ── Helpers de construção ─────────────────────────────────────────────────

    def _adicionar_separador_secao(self, titulo: str):
        """Linha fina + label de cabeçalho de seção."""
        if self._corpo.count() > 0:
            linha = QFrame()
            linha.setFrameShape(QFrame.HLine)
            linha.setFixedHeight(1)
            linha.setStyleSheet("QFrame { color: #2a2a2a; margin: 4px 0; }")
            self._corpo.addWidget(linha)

        lbl = QLabel(titulo.upper())
        lbl.setObjectName("secao_header")
        lbl.setStyleSheet(_CSS_SECAO)
        self._corpo.addWidget(lbl)

    def _adicionar_acao(self, acao: QAction):
        """Cria um botão plano para um QAction."""
        if acao.isSeparator():
            return

        texto = acao.text().replace("&", "")
        if not texto.strip():
            return

        btn = QPushButton(texto)
        btn.setStyleSheet(self._css_btn_acao())
        btn.setEnabled(acao.isEnabled())
        btn.setFlat(True)

        icone = acao.icon()
        if not icone.isNull():
            btn.setIcon(icone)

        atalho = acao.shortcut()
        if atalho and not atalho.isEmpty():
            btn.setToolTip(f"Atalho: {atalho.toString()}")

        btn.clicked.connect(acao.trigger)
        self._corpo.addWidget(btn)

    def _nova_linha_chips(self) -> QHBoxLayout:
        """Cria um QHBoxLayout para chips e o adiciona ao corpo."""
        row_widget = QWidget()
        row_widget.setStyleSheet("background: transparent;")
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(6)
        self._corpo.addWidget(row_widget)

        return row

    def _css_btn_acao(self) -> str:
        t      = tema_global()
        texto  = t.cor("menu_contexto.texto",      "#e8f5e8")
        hover  = t.cor("menu_contexto.item_hover", "#1a2e1a")
        desativ = t.cor("menu_contexto.texto_desativado", "#3a4d3a")

        return (

            f"QPushButton {{"
            f"  background: transparent; color: {texto}; border: none;"
            f"  border-radius: 4px; font-size: 12pt;"
            f"  font-family: '{FONTE_UI}', '{FONTE_UI_FALLBACK}';"
            f"  text-align: left; padding: 5px 10px; }}"
            f"QPushButton:hover {{ background: {hover}; color: #ffffff; }}"
            f"QPushButton:disabled {{ color: {desativ}; }}"
        )

    def _css_chip_off(self) -> str:
        t      = tema_global()
        texto  = t.cor("menu_contexto.texto",      "#e8f5e8")
        hover  = t.cor("menu_contexto.item_hover", "#1a2e1a")

        return (

            f"QPushButton {{"
            f"  background: {CINZA_ESCURO}; color: {texto};"
            f"  border: 1px solid #333; border-radius: 4px;"
            f"  font-size: 11pt; padding: 3px 10px; }}"
            f"QPushButton:hover {{ background: {hover}; color: #ffffff; }}"
        )

    def _criar_chip(self, texto: str, ativo: bool, grupo: QButtonGroup) -> QPushButton:
        """Cria um botão chip (selecionável, estilo radio horizontal)."""
        btn = QPushButton(texto)
        btn.setCheckable(True)
        btn.setChecked(ativo)
        btn.setStyleSheet(_CSS_CHIP_ON if ativo else self._css_chip_off())
        btn.toggled.connect(
            lambda chk, b=btn: b.setStyleSheet(_CSS_CHIP_ON if chk else self._css_chip_off())
        )
        grupo.addButton(btn)

        return btn
