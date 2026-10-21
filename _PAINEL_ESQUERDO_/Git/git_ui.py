# 📁 _PAINEL_ESQUERDO_/Git/git_ui.py
"""
📁 _PAINEL_ESQUERDO_/Git/git_ui.py
Orquestrador do painel GitHub.

Mantém o GitTerminal vivo durante toda a sessão e troca entre as 3 telas:
    Tela 1 — GitUIEntrar    (não logado)
    Tela 2 — GitUIConta     (logado, sem projeto)
    Tela 3 — GitUIProjeto   (projeto aberto)

O App_.py importa apenas PainelGitHub — nada muda lá fora.
"""

from PySide6.QtCore    import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from .git_config        import config_github
from .a__git_ui_entrar  import GitTerminal, GitUIEntrar
from .b__git_ui_conta   import GitUIConta
from .c__git_ui_projeto import GitUIProjeto
from _LOG_.log    import log
from _CONFIGURA_.gerenciador_tema import tema_global
_ARQ = "git_ui.py"

# Índices das telas no QStackedWidget
_TELA_ENTRAR  = 0
_TELA_CONTA   = 1
_TELA_PROJETO = 2

class PainelGitHub(QWidget):
    """
    Widget principal do Git — exposto ao App_.py.

    Sinais:
        projeto_baixado(str)  — caminho local do projeto criado/baixado
    """

    projeto_baixado          = Signal(str)
    criar_projeto_solicitado = Signal()
    commit_realizado         = Signal()
    push_realizado           = Signal()

    def __init__(self, tema: dict = None, parent=None):
        super().__init__(parent)
        self._tema = tema or tema_global().dados()
        self._construir()
        self._aplicar_tema()

    # ── Construção ────────────────────────────────────────────────────

    def _construir(self):
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        self._terminal = GitTerminal()
        self._pilha    = QStackedWidget()

        self._tela_entrar  = GitUIEntrar(self._terminal)
        self._tela_conta   = GitUIConta(self._terminal)
        self._tela_projeto = GitUIProjeto(self._terminal)

        self._tela_entrar.set_callback_autenticado(self._ir_para_conta)

        self._tela_conta.set_callback_projeto_aberto(self._ir_para_projeto)
        self._tela_conta.set_callback_sair(self._ir_para_entrar)
        self._tela_conta.set_callback_criar_projeto(self._ao_criar_projeto)
        self._tela_conta.set_callback_adicionar_conta(self._ao_adicionar_conta)
        self._tela_conta.set_callback_conta_trocada(self._ao_conta_trocada)

        self._tela_projeto.set_callback_fechar_projeto(self._ir_para_conta)
        self._tela_projeto.set_callback_sair(self._ir_para_entrar)
        self._tela_projeto.commit_realizado.connect(self.commit_realizado)
        self._tela_projeto.push_realizado.connect(self.push_realizado)

        self._pilha.addWidget(self._tela_entrar)
        self._pilha.addWidget(self._tela_conta)
        self._pilha.addWidget(self._tela_projeto)

        raiz.addWidget(self._pilha, 1)
        raiz.addWidget(self._terminal)

        if config_github().esta_logado():
            cfg  = config_github()
            nome = cfg.nome or cfg.login or ""
            self._terminal.ja_logado(nome)
            self._pilha.setCurrentIndex(_TELA_CONTA)
            self._tela_conta.atualizar_usuario()
            log.info(_ARQ, "_construir", "sessão ativa — exibindo tela de conta")
        else:
            self._terminal.sistema_iniciado()
            self._pilha.setCurrentIndex(_TELA_ENTRAR)

    # ── Tema ──────────────────────────────────────────────────────────

    # 💡 fallback_opc = Literal["#888888"] ← defina os valores válidos
    def _c(self, chave: str, fallback: str = "#888888") -> str:
        return tema_global().cor(f"painel_git.{chave}", fallback)

    # ⚠️  função grande (74 linhas)
    def _aplicar_tema(self):
        fundo        = self._c("fundo",              "#0a0a0a")
        texto        = self._c("texto",              "#e0e0e0")
        borda        = self._c("borda",              "#1a1a1a")
        hover        = self._c("item_hover",         "#1a1a2e")
        selecionado  = self._c("item_selecionado",   "#264f78")
        btn_fundo    = self._c("botao_fundo",        "#1e3a5f")
        btn_hover    = self._c("botao_hover",        "#264f78")
        btn_texto    = self._c("botao_texto",        "#e0e0e0")
        commit_fundo = self._c("botao_commit_fundo", "#4CAF50")
        commit_hover = self._c("botao_commit_hover", "#45a049")
        commit_texto = self._c("botao_commit_texto", "#ffffff")
        input_fundo  = self._c("input_fundo",        "#1a1a1a")
        input_texto  = self._c("input_texto",        "#e0e0e0")
        input_ph     = self._c("input_placeholder",  "#555555")
        cor_branch   = self._c("cor_branch",         "#c678dd")

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {fundo};
                color: {texto};
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }}
            QLabel {{
                color: {texto};
            }}
            QLabel#label_branch {{
                color: {cor_branch};
                font-weight: bold;
            }}
            QTreeWidget, QListWidget {{
                background-color: {fundo};
                color: {texto};
                border: 1px solid {borda};
                font-family: Consolas;
                font-size: 11px;
            }}
            QTreeWidget::item:hover, QListWidget::item:hover {{
                background-color: {hover};
            }}
            QTreeWidget::item:selected, QListWidget::item:selected {{
                background-color: {selecionado};
            }}
            QLineEdit, QTextEdit, QPlainTextEdit {{
                background-color: {input_fundo};
                color: {input_texto};
                border: 1px solid {borda};
                border-radius: 3px;
                padding: 4px;
            }}
            QPushButton {{
                background-color: {btn_fundo};
                color: {btn_texto};
                border: none;
                padding: 5px 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
            }}
            QPushButton#btn_commit {{
                background-color: {commit_fundo};
                color: {commit_texto};
                font-weight: bold;
            }}
            QPushButton#btn_commit:hover {{
                background-color: {commit_hover};
            }}
        """)

        # Repassa o tema para o terminal Git
        if hasattr(self, "_terminal") and self._terminal:
            self._terminal.atualizar_tema()

    def atualizar_tema(self, tema: dict = None):
        """Chamado pelo hot-reload do gerenciador_tema."""
        self._tema = tema or tema_global().dados()
        self._aplicar_tema()

    # ── Navegação entre telas ─────────────────────────────────────────

    def _ir_para_entrar(self):
        log.info(_ARQ, "_ir_para_entrar", "voltando para tela 1")
        self._pilha.setCurrentIndex(_TELA_ENTRAR)

    def _ir_para_conta(self):
        log.info(_ARQ, "_ir_para_conta", "indo para tela 2")
        self._tela_conta.atualizar_usuario()
        self._pilha.setCurrentIndex(_TELA_CONTA)

    def _ir_para_projeto(self, caminho: str):
        log.ok(_ARQ, "_ir_para_projeto", f"projeto: {caminho}")
        self._tela_projeto.abrir_projeto(caminho)
        self._pilha.setCurrentIndex(_TELA_PROJETO)
        self.projeto_baixado.emit(caminho)

    def _ao_criar_projeto(self):
        log.info(_ARQ, "_ao_criar_projeto", "solicitando criação de projeto")
        self.criar_projeto_solicitado.emit()

    def _ao_adicionar_conta(self):
        self._terminal.info("Faça login na outra conta do GitHub")
        self._pilha.setCurrentIndex(_TELA_ENTRAR)

    def _ao_conta_trocada(self):
        self._tela_projeto.atualizar_conta()

    # ── API pública (chamada pelo App_.py) ────────────────────────────

    def set_arquivo_ativo(self, caminho_arquivo: str):
        """Pass-through: notifica GitUIProjeto sobre o arquivo em foco no editor."""
        if self._pilha.currentIndex() == _TELA_PROJETO:
            self._tela_projeto.set_arquivo_ativo(caminho_arquivo)

    def set_projeto(self, caminho: str):
        from .git_gerente import GerenciadorGit
        log.info(_ARQ, "set_projeto", f"projeto definido externamente: {caminho}")

        if (caminho and
                self._pilha.currentIndex() == _TELA_PROJETO and
                self._tela_projeto._caminho == caminho):
            log.info(_ARQ, "set_projeto", "projeto já na Tela 3 — ignorando chamada duplicada")

            return

        if not caminho:
            self._tela_conta.atualizar_usuario()
            self._tela_conta.set_projeto(None)
            self._pilha.setCurrentIndex(_TELA_CONTA)

            return

        git = GerenciadorGit()
        if git.tem_git(caminho):
            self._tela_projeto.abrir_projeto(caminho)
            self._pilha.setCurrentIndex(_TELA_PROJETO)
            log.ok(_ARQ, "set_projeto", "projeto com .git → tela 3")
        else:
            self._tela_conta.atualizar_usuario()
            self._tela_conta.set_projeto(caminho)
            self._pilha.setCurrentIndex(_TELA_CONTA)
            log.info(_ARQ, "set_projeto", "projeto sem .git → tela 2")
