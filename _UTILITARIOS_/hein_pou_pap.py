# 📁 _UTILITARIOS_/hein_pou_pap.py
"""
HeinPopup — popup estilizado universal da hein IDE.

Mesmas cores e visual do heinContextMenu:
  Cores → thema.json > "menu_contexto"  |  fallback → _CONFIGURA_ COR_MENU_CONTEXTO_*
  Fonte → FONTE_UI / FONTE_UI_FALLBACK  |  tamanho  → TAMANHO_FONTE_UI

Substitui QMessageBox em toda a IDE — alterar aqui muda o visual de todos os popups.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
USO:
    from _UTILITARIOS_.hein_pou_pap import HeinPopup
    # Aviso simples (só OK)
    HeinPopup.aviso("Atenção", "Algo aconteceu.", parent=self)

    # Erro
    HeinPopup.erro("Falha", "Não foi possível salvar.", parent=self)

    # Informativo
    HeinPopup.info("Concluído", "Operação realizada com sucesso.", parent=self)

    # Confirmação Sim/Não → retorna bool
    if HeinPopup.confirmar("Apagar arquivo?", "Essa ação não pode ser desfeita.", parent=self):
        apagar()

    # Pacote ausente da _venv_hein_ → retorna True se clicou "Abrir _venv_hein_"
    if HeinPopup.pacote("Microfone", "sounddevice==0.5.5", parent=self):
        abrir_venv_hein()

    # Totalmente customizado
    dlg = HeinPopup(
        "Meu título",
        "Meu texto <b>com HTML</b>.",
        informativo="Texto menor abaixo.",
        botoes=[("Confirmar", "sim"), ("Cancelar", None)],
        tipo="aviso",
        parent=self,
    )
    dlg.exec()
    resultado = dlg.resultado   # valor do botão clicado
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,QLineEdit
)
from PySide6.QtCore import Qt
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import (
    COR_MENU_CONTEXTO_FUNDO,
    COR_MENU_CONTEXTO_TEXTO,
    COR_MENU_CONTEXTO_HOVER,
    COR_MENU_CONTEXTO_BORDA,
    MENU_CONTEXTO_RAIO,
    FONTE_UI,
    FONTE_UI_FALLBACK,
    TAMANHO_FONTE_UI,
    FUNDO_PAINEL,
)
from _LOG_.log import log
_ARQ = "hein_pou_pap.py"

# ── Ícone e cor de acento por tipo ────────────────────────────────────────────
_ICONE_TIPO: dict[str, str] = {
    "aviso":    "⚠",
    "erro":     "✖",
    "info":     "ℹ",
    "pacote":   "📦",
    "confirmar":"?",
}

_COR_ACENTO_TIPO: dict[str, str] = {
    "aviso":    "#ffda0a",   # amarelo
    "erro":     "#e06c75",   # vermelho
    "info":     "#61afef",   # azul
    "pacote":   "#4ec994",   # verde hein
    "confirmar":"#c678dd",   # roxo
}

# ─────────────────────────────────────────────────────────────────────────────
class HeinPopup(QDialog):
    """
    Popup estilizado universal da hein IDE.
    Visual idêntico ao heinContextMenu — editável via thema.json > "menu_contexto".
    """

    # 💡 tipo_opc = Literal["aviso"] ← defina os valores válidos
    def __init__( self, titulo: str, texto: str, informativo: str | None = None, botoes: list[tuple[str, object]] | None = None, tipo: str = "aviso", parent=None, ):
        """
        Parâmetros:
            titulo      — título da barra e cabeçalho visual
            texto       — texto principal (suporta HTML)
            informativo — linha secundária menor (opcional, suporta HTML)
            botoes      — [(label, valor), ...] — 1º botão é o primário (realçado)
                          valor fica disponível em self.resultado após exec()
            tipo        — "aviso" | "erro" | "info" | "pacote" | "confirmar"
            parent      — widget pai
        """
        super().__init__(parent)
        self.resultado = None
        self._mapa_btns: dict[QPushButton, object] = {}

        self.setWindowTitle(titulo)
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setSizePolicy(
            self.sizePolicy().horizontalPolicy(),
            self.sizePolicy().verticalPolicy(),
        )

        t = tema_global()
        fundo_cab = t.cor("interface.fundo_painel", FUNDO_PAINEL)
        self._aplicar_qss(fundo_cab)
        self._montar(titulo, texto, informativo, botoes or [("OK", True)], tipo, fundo_cab)

    # ── Estilo ────────────────────────────────────────────────────────────────

    def _aplicar_qss(self, fundo_cab: str):
        """Mesmas chaves de tema do heinContextMenu — fallback nos mesmos defaults."""
        t = tema_global()
        fundo  = t.cor("menu_contexto.fundo",            COR_MENU_CONTEXTO_FUNDO)
        texto  = t.cor("menu_contexto.texto",            COR_MENU_CONTEXTO_TEXTO)
        borda  = t.cor("menu_contexto.borda",            COR_MENU_CONTEXTO_BORDA)
        hover  = t.cor("menu_contexto.item_hover",       COR_MENU_CONTEXTO_HOVER)
        raio   = MENU_CONTEXTO_RAIO
        fonte  = FONTE_UI
        fb     = FONTE_UI_FALLBACK
        tam    = TAMANHO_FONTE_UI

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {fundo};
                border: 1px solid {borda};
            }}
            QFrame#cab_frame {{
                background-color: {fundo_cab};
                border-radius: 3px;
            }}
            QLabel {{
                color: {texto};
                font-family: "{fonte}", "{fb}";
                font-size: {tam};
                background: transparent;
            }}
            QPushButton {{
                color: {texto};
                font-family: "{fonte}", "{fb}";
                font-size: {tam};
                background-color: transparent;
                border: 1px solid {borda};
                border-radius: {raio};
                padding: 5px 18px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton#btn_primario {{
                border-color: #4ec994;
                color: #4ec994;
            }}
            QPushButton#btn_primario:hover {{
                background-color: #0d2e1e;
            }}
        """)

    # ── Montagem ──────────────────────────────────────────────────────────────

    # ⚠️  função grande (84 linhas)
    def _montar(self, titulo, texto, informativo, botoes, tipo, fundo_cab: str):
        t     = tema_global()
        borda = t.cor("menu_contexto.borda", COR_MENU_CONTEXTO_BORDA)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(20, 16, 20, 16)
        raiz.setSpacing(0)

        # ── Cabeçalho: fundo_painel + ícone colorido + título ────────────────
        icone_char = _ICONE_TIPO.get(tipo, "ℹ")
        cor_acento = _COR_ACENTO_TIPO.get(tipo, "#4ec994")

        frame_cab = QFrame()
        frame_cab.setObjectName("cab_frame")   # estilizado via QFrame#cab_frame no QSS pai
        cab = QHBoxLayout(frame_cab)
        cab.setContentsMargins(10, 8, 10, 8)
        cab.setSpacing(8)

        lbl_icone = QLabel(icone_char)
        lbl_icone.setStyleSheet(
            f"color: {cor_acento}; font-size: 20px; font-weight: bold; background: transparent;"
        )
        lbl_icone.setFixedWidth(26)
        lbl_icone.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet("font-weight: bold; background: transparent;")
        lbl_titulo.setWordWrap(True)

        cab.addWidget(lbl_icone)
        cab.addWidget(lbl_titulo, 1)
        raiz.addWidget(frame_cab)
        raiz.addSpacing(10)

        # ── Separador ────────────────────────────────────────────────────────
        sep1 = QFrame()
        sep1.setFixedHeight(1)
        sep1.setStyleSheet(f"background-color: {borda};")
        raiz.addWidget(sep1)
        raiz.addSpacing(12)

        # ── Texto principal ───────────────────────────────────────────────────
        lbl_texto = QLabel()
        lbl_texto.setText(texto)
        lbl_texto.setWordWrap(True)
        lbl_texto.setTextFormat(Qt.RichText)
        raiz.addWidget(lbl_texto)

        # ── Texto informativo (secundário) ────────────────────────────────────
        if informativo:
            raiz.addSpacing(8)
            lbl_info = QLabel()
            lbl_info.setText(informativo)
            lbl_info.setWordWrap(True)
            lbl_info.setTextFormat(Qt.RichText)
            lbl_info.setStyleSheet(
                f"color: {t.cor('menu_contexto.texto', COR_MENU_CONTEXTO_TEXTO)};"
                "font-size: 11px;"
            )
            raiz.addWidget(lbl_info)

        raiz.addSpacing(14)

        # ── Separador inferior ────────────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background-color: {borda};")
        raiz.addWidget(sep2)
        raiz.addSpacing(12)

        # ── Botões (alinhados à direita; 1º = primário) ───────────────────────
        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(8)
        btn_lay.addStretch()

        for i, (label, valor) in enumerate(botoes):
            btn = QPushButton(label)
            if i == 0:
                btn.setObjectName("btn_primario")
            self._mapa_btns[btn] = valor
            btn.clicked.connect(lambda checked=False, b=btn: self._ao_clicar(b))
            btn_lay.addWidget(btn)

        raiz.addLayout(btn_lay)

    # ── Interação ─────────────────────────────────────────────────────────────

    def _ao_clicar(self, btn: QPushButton):
        self.resultado = self._mapa_btns.get(btn)
        log.info(_ARQ, "_ao_clicar", f"resultado={self.resultado!r}")
        self.accept()

    # ── API estática ──────────────────────────────────────────────────────────

    @staticmethod
    def aviso( titulo: str, texto: str, informativo: str | None = None, parent=None, ) -> None:
        """Popup de aviso — botão OK."""
        HeinPopup(titulo, texto, informativo,
                  botoes=[("OK", True)], tipo="aviso", parent=parent).exec()

    @staticmethod
    def erro( titulo: str, texto: str, informativo: str | None = None, parent=None, ) -> None:
        """Popup de erro — botão OK."""
        HeinPopup(titulo, texto, informativo,
                  botoes=[("OK", True)], tipo="erro", parent=parent).exec()

    @staticmethod
    def info( titulo: str, texto: str, informativo: str | None = None, parent=None, ) -> None:
        """Popup informativo — botão OK."""
        HeinPopup(titulo, texto, informativo,
                  botoes=[("OK", True)], tipo="info", parent=parent).exec()

    @staticmethod
    # 💡 sim_opc = Literal["Sim"] ← defina os valores válidos
    # 💡 nao_opc = Literal["Não"] ← defina os valores válidos
    def confirmar( titulo: str, texto: str, informativo: str | None = None, sim: str = "Sim", nao: str = "Não", parent=None, ) -> bool:
        """Popup de confirmação → True se clicou Sim."""
        dlg = HeinPopup(titulo, texto, informativo,
                        botoes=[(sim, True), (nao, False)],
                        tipo="confirmar", parent=parent)
        dlg.exec()

        return bool(dlg.resultado)

    @staticmethod
    def pacote( nome_exibicao: str, nome_pip: str, parent=None, ) -> bool:
        """
        Popup de pacote ausente da _venv_hein_.
        → True  se clicou "Abrir _venv_hein_"
        → False se cancelou
        """
        titulo = "Pacote necessário"
        texto  = (
            f"<b>{nome_exibicao}</b> precisa do pacote "
            f"<code>{nome_pip}</code> instalado na <b>_venv_hein_</b>."
        )
        informativo = (
            "Deseja abrir o painel <b>_venv_hein_</b> para instalar agora?"
        )
        dlg = HeinPopup(
            titulo, texto, informativo,
            botoes=[("Abrir _venv_hein_", True), ("Cancelar", False)],
            tipo="pacote",
            parent=parent,
        )
        dlg.exec()

        return bool(dlg.resultado)

    @staticmethod
    def escolher(
        titulo: str,
        texto: str,
        opcoes: list[str],
        informativo: str | None = None,
        parent=None,
    ) -> int | None:
        """
        Popup de múltipla escolha.
        → índice (0-based) da opção clicada
        → None se fechado sem escolha
        """
        botoes = [(label, i) for i, label in enumerate(opcoes)]
        dlg = HeinPopup(
            titulo, texto, informativo,
            botoes=botoes,
            tipo="confirmar",
            parent=parent,
        )
        dlg.exec()
        return dlg.resultado  # int | None


# ――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――
class HeinInputDialog(QDialog):
    """
    Dialog de entrada de texto estilizado como HeinPopup.
    Mesmo visual: menu_contexto.* do thema.json.

    Uso rápido:
        nome = HeinInputDialog.pedir(
            "Novo Arquivo",
            placeholder="ex: utils.py",
            parent=self,
        )
        if nome:
            ...  # nome — None se cancelado

    Uso com extensão já definida:
        nome = HeinInputDialog.pedir_nome(
            "Novo arquivo .py",
            descricao="O nome será salvo com a extensão <b>.py</b>.",
            placeholder="ex: utils",
            parent=self,
        )
    """

    def __init__(self, titulo: str, descricao: str = "",
                 placeholder: str = "", parent=None):
        super().__init__(parent)
        self.valor: str | None = None
        self.setWindowTitle(titulo)
        self.setModal(True)
        self.setMinimumWidth(360)

        t = tema_global()
        fundo_cab = t.cor("interface.fundo_painel", FUNDO_PAINEL)
        self._aplicar_qss(fundo_cab)
        self._montar(titulo, descricao, placeholder, fundo_cab)

    # ―― Estilo ――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――

    def _aplicar_qss(self, fundo_cab: str):
        t      = tema_global()
        fundo  = t.cor("menu_contexto.fundo",            COR_MENU_CONTEXTO_FUNDO)
        texto  = t.cor("menu_contexto.texto",            COR_MENU_CONTEXTO_TEXTO)
        borda  = t.cor("menu_contexto.borda",            COR_MENU_CONTEXTO_BORDA)
        hover  = t.cor("menu_contexto.item_hover",       COR_MENU_CONTEXTO_HOVER)
        raio   = MENU_CONTEXTO_RAIO
        fonte  = FONTE_UI
        fb     = FONTE_UI_FALLBACK
        tam    = TAMANHO_FONTE_UI
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {fundo};
                border: 1px solid {borda};
            }}
            QFrame#cab_frame {{
                background-color: {fundo_cab};
                border-radius: 3px;
            }}
            QLabel {{
                color: {texto};
                font-family: "{fonte}", "{fb}";
                font-size: {tam};
                background: transparent;
            }}
            QLineEdit {{
                background-color: #111111;
                color: {texto};
                border: 1px solid {borda};
                border-radius: {raio};
                padding: 5px 8px;
                font-family: "{fonte}", "{fb}";
                font-size: {tam};
            }}
            QLineEdit:focus {{
                border-color: #4ec994;
            }}
            QPushButton {{
                color: {texto};
                font-family: "{fonte}", "{fb}";
                font-size: {tam};
                background-color: transparent;
                border: 1px solid {borda};
                border-radius: {raio};
                padding: 5px 18px;
                min-width: 80px;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
            QPushButton#btn_primario {{
                border-color: #4ec994;
                color: #4ec994;
            }}
            QPushButton#btn_primario:hover {{ background-color: #0d2e1e; }}
        """)

    # ―― Montagem ――――――――――――――――――――――――――――――――――――――――――――――――――――――――――

    def _montar(self, titulo: str, descricao: str, placeholder: str, fundo_cab: str):
        t     = tema_global()
        borda = t.cor("menu_contexto.borda", COR_MENU_CONTEXTO_BORDA)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(20, 16, 20, 16)
        raiz.setSpacing(0)

        # ―― Cabeçalho ――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――
        frame_cab = QFrame()
        frame_cab.setObjectName("cab_frame")
        cab = QHBoxLayout(frame_cab)
        cab.setContentsMargins(10, 8, 10, 8)
        cab.setSpacing(8)
        lbl_icone = QLabel("📄")
        lbl_icone.setStyleSheet("color:#4ec994; font-size:18px; font-weight:bold; background:transparent;")
        lbl_icone.setFixedWidth(26)
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet("font-weight: bold; background: transparent;")
        cab.addWidget(lbl_icone)
        cab.addWidget(lbl_titulo, 1)
        raiz.addWidget(frame_cab)
        raiz.addSpacing(10)

        sep1 = QFrame()
        sep1.setFixedHeight(1)
        sep1.setStyleSheet(f"background-color: {borda};")
        raiz.addWidget(sep1)
        raiz.addSpacing(12)

        if descricao:
            lbl_desc = QLabel(descricao)
            lbl_desc.setWordWrap(True)
            lbl_desc.setTextFormat(Qt.RichText)
            raiz.addWidget(lbl_desc)
            raiz.addSpacing(8)

        self._campo = QLineEdit()
        self._campo.setPlaceholderText(placeholder)
        raiz.addWidget(self._campo)
        raiz.addSpacing(14)

        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background-color: {borda};")
        raiz.addWidget(sep2)
        raiz.addSpacing(12)

        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(8)
        btn_lay.addStretch()

        btn_criar   = QPushButton("Criar")
        btn_cancel  = QPushButton("Cancelar")
        btn_criar.setObjectName("btn_primario")
        btn_criar.setCursor(Qt.PointingHandCursor)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_criar.clicked.connect(self._confirmar)
        btn_cancel.clicked.connect(self.reject)
        btn_lay.addWidget(btn_criar)
        btn_lay.addWidget(btn_cancel)
        raiz.addLayout(btn_lay)

        self._campo.setFocus()
        # Enter confirma
        self._campo.returnPressed.connect(self._confirmar)

    # ―― Interação ――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――

    def _confirmar(self):
        texto = self._campo.text().strip()
        if not texto:
            return
        self.valor = texto
        self.accept()

    # ―― API estática ―――――――――――――――――――――――――――――――――――――――――――――――――――――――――――

    @staticmethod
    def pedir(titulo: str, placeholder: str = "", parent=None) -> str | None:
        """Abre o dialog e retorna o texto digitado, ou None se cancelado."""
        dlg = HeinInputDialog(titulo, placeholder=placeholder, parent=parent)
        if dlg.exec() == QDialog.Accepted:
            return dlg.valor
        return None

    @staticmethod
    def pedir_nome(titulo: str, descricao: str = "",
                   placeholder: str = "", parent=None) -> str | None:
        """Igual a pedir(), com campo de descrição opcional (suporta HTML)."""
        dlg = HeinInputDialog(titulo, descricao=descricao,
                              placeholder=placeholder, parent=parent)
        if dlg.exec() == QDialog.Accepted:
            return dlg.valor
        return None
