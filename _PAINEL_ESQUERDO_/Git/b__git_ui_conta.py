    # 📁 _PAINEL_ESQUERDO_/Git/b__git_ui_conta.py

import os
import threading
from PySide6.QtCore    import Qt, Signal, QObject
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QInputDialog, QFileDialog, QMenu,
)
from _UTILITARIOS_.hein_pou_pap import HeinPopup
from _CONFIGURA_ import ( VERDE, COR_SINTAXE_VARIAVEL_ESPECIAL, COR_INFO,
    COR_FALLBACK)
from _CONFIGURA_.gerenciador_tema import tema_global
from .git_config  import config_github
from .git_gerente import GerenciadorGit
from .git_api     import GitHubAPI
from .git_terminal import GitTerminal
from .git_ui_utils import _Ponte, _em_thread, _botao, _sep
from _LOG_.log import log
_ARQ = "b__git_ui_conta.py"

# ── Diálogo de publicação ─────────────────────────────────────────────────────

from PySide6.QtWidgets import QDialog, QFormLayout, QRadioButton, QButtonGroup, QDialogButtonBox, QLineEdit

class _DialogPublicar(QDialog):
    """Formulário exibido antes de criar o repositório no GitHub."""

    # ⚠️  função grande (69 linhas)
    def __init__(self, nome_sugerido: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Criar Repositório no GitHub")
        self.setMinimumWidth(380)
        self.setStyleSheet("background:#0d0d0d; color:#c9d1d9;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        titulo = QLabel("Novo repositório no GitHub")
        titulo.setStyleSheet("font-size:12px; font-weight:bold; color:#4ec994;")
        lay.addWidget(titulo)

        form = QFormLayout()
        form.setSpacing(8)

        estilo_campo = """
            QLineEdit {
                background:#0a0a0a; color:#c9d1d9;
                border:1px solid #1a3a1a; border-radius:4px;
                padding:4px 8px; font-size:11px;
                font-family:Consolas,monospace;
            }
            QLineEdit:focus { border-color:#4ec994; }
        """

        lbl_nome = QLabel("Nome do repositório:")
        lbl_nome.setStyleSheet("font-size:10px; color:#484f58;")
        self._campo_nome = QLineEdit(nome_sugerido)
        self._campo_nome.setStyleSheet(estilo_campo)
        form.addRow(lbl_nome, self._campo_nome)

        lbl_desc = QLabel("Descrição:")
        lbl_desc.setStyleSheet("font-size:10px; color:#484f58;")
        self._campo_desc = QLineEdit()
        self._campo_desc.setPlaceholderText("Opcional")
        self._campo_desc.setStyleSheet(estilo_campo)
        form.addRow(lbl_desc, self._campo_desc)

        lay.addLayout(form)

        # Público / Privado
        lay_vis = QHBoxLayout()
        self._rb_publico = QRadioButton("🌐  Público")
        self._rb_privado = QRadioButton("🔒  Privado")
        self._rb_publico.setChecked(True)
        for rb in (self._rb_publico, self._rb_privado):
            rb.setStyleSheet("color:#c9d1d9; font-size:10px;")
        lay_vis.addWidget(self._rb_publico)
        lay_vis.addWidget(self._rb_privado)
        lay_vis.addStretch()
        lay.addLayout(lay_vis)

        # Botões
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Criar repositório")
        btns.button(QDialogButtonBox.Cancel).setText("Cancelar")
        btns.setStyleSheet("""
            QPushButton {
                background:#0d1a0d; color:#4ec994;
                border:1px solid #1a3a1a; border-radius:4px;
                font-size:10px; padding:5px 12px;
            }
            QPushButton:hover { background:#1a2a1a; }
        """)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def nome(self) -> str:
        return self._campo_nome.text().strip()

    def descricao(self) -> str:
        return self._campo_desc.text().strip()

    def privado(self) -> bool:
        return self._rb_privado.isChecked()

# ── Fim do diálogo ────────────────────────────────────────────────────────────

# ══════════════════════════════════════════════════════════════════════
# Tela 2 — GitUIConta
# ══════════════════════════════════════════════════════════════════════

class GitUIConta(QWidget):
    """
    Segunda tela do painel GitHub.
    Exibida quando o usuário está logado.
    """

    def __init__(self, terminal: GitTerminal, parent=None):
        super().__init__(parent)
        self._terminal      = terminal
        self._git           = GerenciadorGit()
        self._api           = GitHubAPI()
        self._pontes        : list = []
        self._caminho_local : str  = ""

        self._cb_projeto_aberto = None
        self._cb_sair           = None
        self._cb_criar_projeto  = None
        self._cb_adicionar_conta = None
        self._cb_conta_trocada  = None

        self._construir_ui()

    def set_callback_projeto_aberto(self, fn):
        self._cb_projeto_aberto = fn

    def set_callback_sair(self, fn):
        self._cb_sair = fn

    def set_callback_criar_projeto(self, fn):
        self._cb_criar_projeto = fn

    def set_callback_adicionar_conta(self, fn):
        self._cb_adicionar_conta = fn

    def set_callback_conta_trocada(self, fn):
        self._cb_conta_trocada = fn

    # ── UI ────────────────────────────────────────────────────────────

    # ⚠️  função grande (91 linhas)
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



        cfg = config_github()
        nome = cfg.nome or cfg.login or ""
        self._lbl_usuario = QLabel(f"@{nome}" if nome else "")
        self._lbl_usuario.setStyleSheet("font-size:10px; color:#4ec994;")

        lay_cab.addStretch()
        lay_cab.addWidget(self._lbl_usuario)
        self._btn_contas = QPushButton("Contas ▾")
        self._btn_contas.setCursor(Qt.PointingHandCursor)
        self._btn_contas.setStyleSheet(
            "QPushButton { color:#4ec994; background:transparent; border:none;"
            " font-size:10px; padding:2px 4px; }"
            "QPushButton:hover { color:#6ef0b4; }"
        )
        self._btn_contas.clicked.connect(self._abrir_menu_contas)
        lay_cab.addWidget(self._btn_contas)
        raiz.addWidget(cab)

        # Corpo
        corpo = QWidget()
        corpo.setStyleSheet("background:#0d0d0d;")
        lay_corpo = QVBoxLayout(corpo)
        lay_corpo.setContentsMargins(8, 6, 8, 6)
        lay_corpo.setSpacing(4)

        _estilo_btn = """
            QPushButton {{
                background:{bg}; color:{fg};
                border:1px solid {borda}; border-radius:4px;
                font-size:10px; padding:4px 6px;
                text-align:center;
            }}
            QPushButton:hover {{ background:{hover}; }}
            QPushButton:disabled {{ background:#0a0a0a; color:#333; border-color:#111; }}
        """

        self._btn_criar = QPushButton("✚ Novo Projeto")
        self._btn_criar.setCursor(Qt.PointingHandCursor)
        self._btn_criar.setStyleSheet(_estilo_btn.format(
            bg=tema_global().cor("interface.fundo_painel","#0d1117"), fg=COR_INFO, borda=tema_global().cor("interface.borda","#1a2a3a"), hover=tema_global().cor("interface.fundo_item_hover","#1a1a2e")
        ))
        self._btn_criar.clicked.connect(self._ao_criar_projeto)
        self._btn_criar.setVisible(True)

        self._btn_publicar = QPushButton("⬆ Publicar")
        self._btn_publicar.setCursor(Qt.PointingHandCursor)
        self._btn_publicar.setStyleSheet(_estilo_btn.format(
            bg=tema_global().cor("interface.fundo","#0d1a0d"), fg=VERDE, borda=tema_global().cor("interface.fundo_item_selecionado","#1a3a1a"), hover=tema_global().cor("interface.fundo_item_hover","#1a2a1a")
        ))
        self._btn_publicar.clicked.connect(self._ao_publicar_projeto)
        self._btn_publicar.setVisible(False)

        self._btn_baixar = QPushButton("⬇ Baixar")
        self._btn_baixar.setCursor(Qt.PointingHandCursor)
        self._btn_baixar.setStyleSheet(_estilo_btn.format(
            bg=tema_global().cor("interface.fundo","#0d0d0d"), fg=COR_FALLBACK, borda=tema_global().cor("interface.borda","#21262d"), hover=tema_global().cor("interface.fundo_item_hover","#1a1a1a")
        ))
        self._btn_baixar.clicked.connect(self._ao_baixar_projeto)

        self._btn_sair = QPushButton("← Sair")
        self._btn_sair.setCursor(Qt.PointingHandCursor)
        self._btn_sair.setStyleSheet(_estilo_btn.format(
            bg=tema_global().cor("interface.fundo","#0d0d0d"), fg=COR_SINTAXE_VARIAVEL_ESPECIAL, borda=tema_global().cor("interface.borda","#2a1a1a"), hover=tema_global().cor("interface.fundo_item_hover","#1a0d0d")
        ))
        self._btn_sair.clicked.connect(self._ao_sair)

        # Linha 1: Criar (ou Publicar) + Baixar
        lay_linha1 = QHBoxLayout()
        lay_linha1.setSpacing(4)
        lay_linha1.addWidget(self._btn_criar)
        lay_linha1.addWidget(self._btn_publicar)
        lay_linha1.addWidget(self._btn_baixar)
        lay_corpo.addLayout(lay_linha1)

        # Linha 2: Sair (alinhado à esquerda, não estica)
        lay_linha2 = QHBoxLayout()
        lay_linha2.setSpacing(4)
        lay_linha2.addWidget(self._btn_sair)
        lay_linha2.addStretch()
        lay_corpo.addLayout(lay_linha2)

        lay_corpo.addStretch()

        raiz.addWidget(corpo, 1)

    def atualizar_usuario(self):
        cfg  = config_github()
        nome = cfg.nome or cfg.login or ""
        self._lbl_usuario.setText(f"@{nome}" if nome else "")
        self._btn_contas.setText(f"Contas ({len(cfg.contas())}) ▾")

    def _abrir_menu_contas(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background:#0d0d0d; color:#c9d1d9; border:1px solid #2a2a2a; }
            QMenu::item { padding:6px 16px; }
            QMenu::item:selected { background:#1e3a5f; }
        """)
        cfg = config_github()
        for conta in cfg.contas():
            login = conta["login"]
            nome = conta.get("nome") or login
            acao = menu.addAction(f"@{login} — {nome}")
            acao.setCheckable(True)
            acao.setChecked(login == cfg.login)
            acao.triggered.connect(lambda _checked=False, l=login: self._trocar_conta(l))

        if cfg.contas():
            menu.addSeparator()
        adicionar = menu.addAction("Adicionar outra conta")
        adicionar.triggered.connect(self._adicionar_conta)
        menu.addSeparator()
        sair = menu.addAction("Sair da conta atual")
        sair.triggered.connect(self._ao_sair)
        menu.exec(self._btn_contas.mapToGlobal(
            self._btn_contas.rect().bottomLeft()
        ))

    def _trocar_conta(self, login: str):
        if not config_github().ativar_conta(login):
            self._terminal.erro("Conta salva não encontrada")
            return
        self.atualizar_usuario()
        self._terminal.ok(f"Conta ativa: @{login}")
        if self._cb_conta_trocada:
            self._cb_conta_trocada()

    def _adicionar_conta(self):
        if self._cb_adicionar_conta:
            self._cb_adicionar_conta()

    def set_projeto(self, caminho: str | None):
        self._caminho_local = caminho or ""
        tem_projeto = bool(self._caminho_local)

        self._btn_criar.setVisible(not tem_projeto)
        self._btn_publicar.setVisible(tem_projeto)

        if tem_projeto:
            nome = os.path.basename(self._caminho_local)
            self._terminal.projeto_reconhecido(nome)
        else:
            self._terminal.sem_projeto()

    # ── Ações ─────────────────────────────────────────────────────────

    def _ao_criar_projeto(self):
        if self._cb_criar_projeto:
            self._cb_criar_projeto()

    # ⚠️  função grande (84 linhas)
    def _ao_publicar_projeto(self):
        if not self._caminho_local:

            return

        nome_sugerido = os.path.basename(self._caminho_local)
        dialogo = _DialogPublicar(nome_sugerido, parent=self)
        if dialogo.exec() != QDialog.Accepted:

            return

        nome_repo = dialogo.nome() or nome_sugerido
        priv      = dialogo.privado()
        descricao = dialogo.descricao()

        self._terminal.publicando_projeto()
        self._btn_publicar.setEnabled(False)
        self._btn_baixar.setEnabled(False)
        log.info(_ARQ, "_ao_publicar_projeto", f"publicando '{nome_repo}' privado={priv}")

        caminho = self._caminho_local

        def _publicar():
            cfg   = config_github()
            token = cfg.token

            repo = self._api.criar_repositorio(nome_repo, privado=priv)
            if not repo:

                return None, "Falha ao criar repositório no GitHub"

            clone_url = repo.get("clone_url", "")

            arq_version = os.path.join(caminho, "VERSION")
            if not os.path.exists(arq_version):
                with open(arq_version, "w", encoding="utf-8") as f:
                    f.write("v0.1.0\n")

            # Cria CHANGELOG.md junto com o VERSION na publicação inicial
            try:
                from _UTILITARIOS_.versionamento import criar_changelog_inicial
                criar_changelog_inicial(caminho)
            except Exception as _e_cl:
                log.aviso(_ARQ, "_ao_publicar_projeto",
                          f"criar_changelog_inicial falhou: {_e_cl}")

            arq_readme = os.path.join(caminho, "README.md")
            if not os.path.exists(arq_readme):
                with open(arq_readme, "w", encoding="utf-8") as f:
                    f.write(f"# {nome_repo}\n\nProjeto criado com hein IDE.\n")

            if not self._git.tem_git(caminho):
                self._git.inicializar(caminho)
            self._git.configurar_usuario(
                cfg.nome or cfg.login,
                f"{cfg.login}@users.noreply.github.com",
            )
            self._git.definir_remoto(caminho, clone_url, token)

            r_commit = self._git.salvar_versao(caminho, "v0.1.0 — Projeto publicado")
            if not r_commit.ok:

                return None, f"Falha no commit: {r_commit.erro}"

            r_push = self._git.enviar_para_github(caminho, token)
            if not r_push.ok:

                return None, f"Falha no push: {r_push.erro}"

            config_github().adicionar_projeto_recente(nome_repo, caminho, clone_url)

            return caminho, None

        def _concluido(resultado):
            self._btn_publicar.setEnabled(True)
            self._btn_baixar.setEnabled(True)

            caminho_ok, erro = resultado if resultado else (None, "Erro desconhecido")

            if erro:
                self._terminal.erro(f"Falha ao publicar: {erro}")
                log.erro(_ARQ, "_ao_publicar_projeto", erro)

                return

            self._terminal.projeto_publicado()
            log.ok(_ARQ, "_ao_publicar_projeto", f"publicado: {caminho_ok}")
            if self._cb_projeto_aberto:
                self._cb_projeto_aberto(caminho_ok)

        p = _em_thread(_publicar, _concluido, self)
        self._pontes.append(p)

    def _ao_baixar_projeto(self):
        url, ok = QInputDialog.getText(
            self, "Baixar Projeto",
            "Cole o endereço do projeto no GitHub:",
        )
        if not ok or not url.strip():

            return

        url = url.strip().rstrip("/")
        if not url.endswith(".git"):
            url += ".git"
        nome_repo = url.split("/")[-1].replace(".git", "")

        pasta_base = os.path.expanduser("~\\Documents\\hein_Projects")
        base = QFileDialog.getExistingDirectory(self, "Onde salvar?", pasta_base)
        if not base:

            return

        destino = os.path.join(base, nome_repo)
        token   = config_github().token

        self._terminal.info("Conectando ao repositório...")
        self._btn_publicar.setEnabled(False)
        self._btn_baixar.setEnabled(False)
        log.info(_ARQ, "_ao_baixar_projeto", f"clonando {url} → {destino}")

        def _clonar():
            return self._git.baixar_projeto(url, destino, token)

        def _concluido(r):
            self._btn_publicar.setEnabled(True)
            self._btn_baixar.setEnabled(True)

            if r.ok:
                self._terminal.info("Baixando arquivos...")
                self._terminal.ok(f"Projeto baixado em {os.path.basename(destino)}/")
                config_github().adicionar_projeto_recente(nome_repo, destino, url)
                log.ok(_ARQ, "_ao_baixar_projeto", "clone concluído")
                if self._cb_projeto_aberto:
                    self._cb_projeto_aberto(destino)
            else:
                self._terminal.erro(f"Falha ao baixar: {r.erro}")
                log.erro(_ARQ, "_ao_baixar_projeto", "clone falhou", r.erro)

        p = _em_thread(_clonar, _concluido, self)
        self._pontes.append(p)

    def _ao_sair(self):
        if not HeinPopup.confirmar(
            "Sair da conta",
            "Deseja sair da conta GitHub?",
            parent=self,
        ):
            return
        config_github().limpar_sessao()
        self._terminal.info("Sessão encerrada")
        log.info(_ARQ, "_ao_sair", "sessão encerrada")
        if self._cb_sair:
            self._cb_sair()
