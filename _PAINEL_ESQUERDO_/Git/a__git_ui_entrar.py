# 📁 _PAINEL_ESQUERDO_/Git/a__git_ui_entrar.py
import threading
from PySide6.QtCore import Qt, Signal, QTimer, QObject
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFrame,
)
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import ( VERDE, COR_SINTAXE_VARIAVEL_ESPECIAL, COR_FALLBACK)
from .git_terminal import GitTerminal
from .git_config    import config_github
from .git_autentica import GerenciadorAuth
from .git_gerente   import GerenciadorGit
from _LOG_.log import log
_ARQ = "a__git_ui_entrar.py"

# ══════════════════════════════════════════════════════════════════════
# Ponte thread-safe
# ══════════════════════════════════════════════════════════════════════

class _Ponte(QObject):
    _concluido = Signal(object)

    def __init__(self, tarefa, callback, parent=None):
        super().__init__(parent)
        self._tarefa = tarefa
        self._concluido.connect(callback)

    def iniciar(self):
        def _rodar():
            try:
                resultado = self._tarefa()
            except Exception:
                log.excecao(_ARQ, "_Ponte._rodar", "exceção na thread")
                resultado = None
            self._concluido.emit(resultado)
        threading.Thread(target=_rodar, daemon=True).start()

def _em_thread(tarefa, callback, parent: QObject):
    ponte = _Ponte(tarefa, callback, parent)
    ponte.iniciar()

    return ponte

# ══════════════════════════════════════════════════════════════════════
# Utilitários de UI
# ══════════════════════════════════════════════════════════════════════

def _botao(texto, cor_fundo=None, cor_texto=None):
    if cor_fundo is None: cor_fundo = tema_global().cor("interface.fundo_painel", "#1e3a5f")
    if cor_texto is None:  cor_texto = COR_FALLBACK
    btn = QPushButton(texto)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {cor_fundo};
            color: {cor_texto};
            border: none;
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 11px;
            text-align: left;
        }}
        QPushButton:hover   {{ background-color: #264f78; }}
        QPushButton:pressed {{ background-color: #1a3550; }}
        QPushButton:disabled {{ background-color: #1a1a1a; color: #444; }}
    """)

    return btn

def _sep():
    linha = QFrame()
    linha.setFrameShape(QFrame.HLine)
    linha.setStyleSheet("color: #1a1a1a; margin: 0;")

    return linha

# ══════════════════════════════════════════════════════════════════════
# Painel Device Flow
# ══════════════════════════════════════════════════════════════════════

class _PainelDeviceFlow(QWidget): # ⚠️ função grande (57 linhas)
    def __init__(self, terminal: GitTerminal, parent=None):
        super().__init__(parent)
        self._terminal = terminal
        self.setVisible(False)
        self.setStyleSheet("background:#0d0d0d; border-top: 1px solid #1a1a1a;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        aviso = QLabel(
            "Para entrar no GitHub:\n"
            "1. Copie o código abaixo\n"
            "2. Abra github.com/login/device\n"
            "3. Cole o código e confirme"
        )
        aviso.setStyleSheet("color:#484f58; font-size:10px; font-family:Consolas,monospace;")
        aviso.setWordWrap(True)
        lay.addWidget(aviso)

        lay_cod = QHBoxLayout()
        self._campo = QLineEdit()
        self._campo.setReadOnly(True)
        self._campo.setAlignment(Qt.AlignCenter)
        self._campo.setPlaceholderText("aguardando...")
        self._campo.setStyleSheet("""
            QLineEdit {
                background:#0a0a0a; color:#4ec994;
                border:1px solid #1a3a1a; border-radius:4px;
                padding:4px 8px; font-size:15px;
                font-weight:bold; letter-spacing:4px;
                font-family:Consolas,monospace;
            }
        """)
        self._btn_copiar = _botao("Copiar", tema_global().cor("interface.fundo_item_hover","#1a2a1a"), VERDE)
        self._btn_copiar.setFixedWidth(60)
        self._btn_copiar.clicked.connect(self._copiar)
        lay_cod.addWidget(self._campo, 1)
        lay_cod.addWidget(self._btn_copiar)
        lay.addLayout(lay_cod)

        self._btn_site = _botao("🌐  Abrir github.com/login/device", tema_global().cor("interface.fundo","#0d1a0d"), VERDE)
        self._btn_site.clicked.connect(self._abrir_site)
        lay.addWidget(self._btn_site)

        self._btn_cancelar = _botao("Cancelar", tema_global().cor("interface.fundo","#1a0d0d"), COR_SINTAXE_VARIAVEL_ESPECIAL)
        self._btn_cancelar.clicked.connect(self._cancelar)
        lay.addWidget(self._btn_cancelar)

        self._auth       : GerenciadorAuth | None = None
        self._url_device : str  = ""
        self._pontes     : list = []
        self._consultando: bool = False

        self._timer_poll = QTimer(self)
        self._timer_poll.setSingleShot(True)
        self._timer_poll.timeout.connect(self._verificar)

    def set_callback_autenticado(self, fn):
        self._cb_autenticado = fn

    def set_callback_cancelado(self, fn):
        self._cb_cancelado = fn

    def iniciar(self, auth: GerenciadorAuth):
        self._auth        = auth
        self._consultando = False
        self._campo.setText("...")
        self._terminal.solicitando_codigo()
        log.info(_ARQ, "_PainelDeviceFlow.iniciar", "solicitando código device")

        def _obter():
            return auth.solicitar_codigo_device()

        def _exibir(resultado):
            if not resultado:
                self._terminal.erro("Erro ao obter código — tente novamente")

                return

            codigo, url = resultado
            self._url_device = url
            self._campo.setText(codigo)
            self._terminal.codigo_recebido(codigo)
            self._armar_timer()

        p = _em_thread(_obter, _exibir, self)
        self._pontes.append(p)

    def _armar_timer(self):
        if not self._auth:

            return

        intervalo_ms = self._auth.intervalo_poll * 1000
        self._timer_poll.start(intervalo_ms)

    def _verificar(self):
        if not self._auth or self._consultando:
            self._armar_timer()

            return

        if self._auth.expirou():
            self._terminal.codigo_expirado()

            return

        self._consultando = True
        self._terminal.aguardando_confirmacao()

        def _checar():
            return self._auth.verificar_autenticacao()

        def _resultado(ok):
            self._consultando = False
            if ok:
                log.ok(_ARQ, "_verificar", "autenticado")
                if hasattr(self, "_cb_autenticado"):
                    self._cb_autenticado()

                return

            if self._auth.expirou():
                self._terminal.codigo_expirado()

                return

            if self._auth.intervalo_poll > 5:
                self._terminal.github_pediu_espera()
            else:
                self._terminal.github_nao_confirmou()
            self._armar_timer()

        p = _em_thread(_checar, _resultado, self)
        self._pontes.append(p)

    def _copiar(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._campo.text())
        self._btn_copiar.setText("✓")
        QTimer.singleShot(1500, lambda: self._btn_copiar.setText("Copiar"))

    def _abrir_site(self):
        import subprocess
        url = self._url_device or "https://github.com/login/device"
        subprocess.Popen(["start", url], shell=True)

    def _cancelar(self):
        self._timer_poll.stop()
        self._consultando = False
        if self._auth:
            self._auth.cancelar()
        self._terminal.login_cancelado()
        self.setVisible(False)
        if hasattr(self, "_cb_cancelado"):
            self._cb_cancelado()

# ══════════════════════════════════════════════════════════════════════
# Tela 1 — GitUIEntrar
# ══════════════════════════════════════════════════════════════════════

class GitUIEntrar(QWidget):
    """
    Primeira tela do painel GitHub.
    Exibida quando o usuário não está logado.
    """

    def __init__(self, terminal: GitTerminal, parent=None):
        super().__init__(parent)
        self._terminal = terminal
        self._auth     : GerenciadorAuth | None = None
        self._pontes   : list = []
        self._cb_autenticado = None

        self._construir_ui()

    def set_callback_autenticado(self, fn):
        self._cb_autenticado = fn

    # ── UI ────────────────────────────────────────────────────────────

    def _construir_ui(self):
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # Cabeçalho — idêntico ao c__git_ui_projeto
        cab = QWidget()
        cab.setStyleSheet("background:#0d0d0d;")
        lay_cab = QHBoxLayout(cab)
        lay_cab.setContentsMargins(8, 4, 8, 4)
        lay_cab.setSpacing(4)

        lbl = QLabel("☁ GITHUB")
        lbl.setStyleSheet("font-size:11px; font-weight:bold; color:#484f58;")
        lay_cab.addWidget(lbl)
        lay_cab.addStretch()
        raiz.addWidget(cab)

        # Corpo
        corpo = QWidget()
        corpo.setStyleSheet("background:#0d0d0d;")
        lay_corpo = QVBoxLayout(corpo)
        lay_corpo.setContentsMargins(8, 6, 8, 6)
        lay_corpo.setSpacing(6)

        self._btn_entrar = _botao("→  Entrar no GitHub", tema_global().cor("interface.fundo","#0d1a0d"), VERDE)
        self._btn_entrar.setStyleSheet("""
            QPushButton {
                background:#0d1a0d; color:#4ec994;
                border:1px solid #1a3a1a; border-radius:4px;
                font-size:10px; padding:4px 8px;
                text-align:left;
            }
            QPushButton:hover { background:#1a2a1a; }
            QPushButton:disabled { background:#0a0a0a; color:#333; border-color:#111; }
        """)
        self._btn_entrar.clicked.connect(self._ao_entrar)
        lay_corpo.addWidget(self._btn_entrar)

        self._device = _PainelDeviceFlow(self._terminal, self)
        self._device.set_callback_autenticado(self._ao_autenticado)
        self._device.set_callback_cancelado(self._ao_cancelado)
        lay_corpo.addWidget(self._device)

        lay_corpo.addStretch()
        raiz.addWidget(corpo, 1)

    # ── Ações ─────────────────────────────────────────────────────────

    def _ao_entrar(self):
        git = GerenciadorGit()

        if not git.git_instalado():
            self._terminal.git_nao_instalado()
            log.aviso(_ARQ, "_ao_entrar", "git não instalado — iniciando instalação")
            self._btn_entrar.setEnabled(False)

            def _instalar():
                return GerenciadorGit.instalar_git_windows(

                    callback_progresso=lambda m: log.info(_ARQ, "_instalar", m)
                )

            def _concluido(ok):
                self._btn_entrar.setEnabled(True)
                if ok:
                    self._terminal.git_instalado()
                    self._iniciar_device_flow()
                else:
                    self._terminal.erro("Falha ao instalar Git — baixe em git-scm.com")

            p = _em_thread(_instalar, _concluido, self)
            self._pontes.append(p)

            return

        self._iniciar_device_flow()

    def _iniciar_device_flow(self):
        self._auth = GerenciadorAuth()
        self._device.setVisible(True)
        self._device.iniciar(self._auth)

    def _ao_autenticado(self):
        self._device.setVisible(False)
        cfg  = config_github()
        nome = cfg.nome or cfg.login
        self._terminal.login_concluido(nome)
        log.ok(_ARQ, "_ao_autenticado", f"logado como @{cfg.login}")

        QTimer.singleShot(600, lambda: (
            self._terminal.conta_conectada(),
            self._cb_autenticado() if self._cb_autenticado else None,
        ))

    def _ao_cancelado(self):
        self._btn_entrar.setEnabled(True)
