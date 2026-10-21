# 📁 _PAINEL_ESQUERDO_/Git/c__git_ui_projeto/_projeto.py
"""
Tela 3 — GitUIProjeto
Exibida quando há um projeto aberto com Git configurado.
"""
import os
import re
import webbrowser
from urllib.parse import urlparse
from PySide6.QtCore    import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QInputDialog, QTabWidget, QTextEdit, QDialog, QDialogButtonBox,
    QPushButton, QMenu, QSplitter, QSizePolicy,
    QListWidget, QListWidgetItem,
    QLineEdit,
)
from PySide6.QtGui import QColor, QFont
from ..git_config   import config_github
from ..git_api      import GitHubAPI
from ..git_gerente  import GerenciadorGit
from ..git_terminal import GitTerminal
from ..git_ui_utils import _em_thread, _botao, _sep
from _LOG_.log import log
from _UTILITARIOS_.icones       import icone_tema
from _UTILITARIOS_.hein_pou_pap import HeinPopup
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import VERDE, COR_INFO, COR_GIT_TEXTO_NEUTRO
from ._paineis_status_diff        import _PainelStatus, _PainelDiferencas
from ._paineis_branches_guardados import _PainelRamificacoes, _PainelGuardados
from ._paineis_historico          import _PainelHistoricoVersoes, _PainelHistoricoArquivo

_ARQ = "c__git_ui_projeto/_projeto.py"


def _push_bloqueado_por_segredo(erro: str) -> bool:
    """Identifica bloqueios do GitHub Push Protection (GH013)."""
    texto = (erro or "").casefold()
    marcadores = (
        "gh013",
        "push protection",
        "secret scanning",
        "cannot contain secrets",
        "secrets detected",
        "repository rule violations",
        "não foi possível conter segredos",
        "segredos detectados",
    )
    return any(marcador in texto for marcador in marcadores)


def _push_rejeitado_por_historico_divergente(erro: str) -> bool:
    """Só oferece pull/force quando a rejeição é realmente de histórico."""
    texto = (erro or "").casefold()
    marcadores = (
        "non-fast-forward",
        "fetch first",
        "tip of your current branch is behind",
        "updates were rejected because the remote contains work",
        "avanço não rápido",
        "histórico remoto contém alterações",
    )
    return any(marcador in texto for marcador in marcadores)


def _locais_segredos_detectados(erro: str) -> list[str]:
    """Extrai só caminhos/linhas do diagnóstico, nunca links de desbloqueio."""
    locais = []
    for linha in (erro or "").splitlines():
        match = re.search(r"\b(?:path|caminho)\s*:\s*([^\r\n]+)", linha, re.I)
        if not match:
            continue
        local = match.group(1).strip()
        if local and "://" not in local and local not in locais:
            locais.append(local)
        if len(locais) == 5:
            break
    return locais


def _popup_falha_git(parent, titulo: str, mensagem: str) -> None:
    HeinPopup.escolher(
        titulo,
        mensagem,
        opcoes=["Fechar"],
        parent=parent,
    )


class _DialogSelecionarRepositorio(QDialog):
    """Lista os repositórios da conta ativa para trocar o origin."""

    def __init__(self, repositorio_atual: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Trocar repositório")
        self.setMinimumSize(430, 330)
        self._repositorio_atual = repositorio_atual
        self._repositorios: list[dict] = []

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(14, 14, 14, 14)
        raiz.setSpacing(8)

        titulo = QLabel("Escolha o repositório que este projeto deve usar:")
        titulo.setStyleSheet("font-size:11px; color:#c9d1d9;")
        titulo.setWordWrap(True)
        raiz.addWidget(titulo)

        self._status = QLabel("Carregando repositórios...")
        self._status.setStyleSheet("font-size:10px; color:#777;")
        raiz.addWidget(self._status)

        self._lista = QListWidget()
        self._lista.setStyleSheet("""
            QListWidget {
                background:#0a0a0a; color:#c9d1d9;
                border:1px solid #2a2a2a; font-size:11px;
            }
            QListWidget::item { padding:7px 8px; }
            QListWidget::item:selected { background:#1e3a5f; }
        """)
        self._lista.itemDoubleClicked.connect(lambda _item: self.accept())
        raiz.addWidget(self._lista, 1)

        self._botoes = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self._botoes.button(QDialogButtonBox.Ok).setText("Usar repositório")
        self._botoes.button(QDialogButtonBox.Cancel).setText("Cancelar")
        self._botoes.button(QDialogButtonBox.Ok).setEnabled(False)
        self._botoes.accepted.connect(self._aceitar_selecionado)
        self._botoes.rejected.connect(self.reject)
        raiz.addWidget(self._botoes)

    def definir_repositorios(self, repositorios: list[dict] | None):
        self._repositorios = repositorios or []
        self._lista.clear()

        if not self._repositorios:
            self._status.setText(
                "Nenhum repositório foi encontrado ou não foi possível carregá-los."
            )
            self._botoes.button(QDialogButtonBox.Ok).setEnabled(False)
            return

        for repositorio in self._repositorios:
            nome = str(repositorio.get("name", "")).strip()
            if not nome:
                continue
            visibilidade = "Privado" if repositorio.get("private") else "Público"
            item = QListWidgetItem(f"{nome}  —  {visibilidade}")
            item.setData(Qt.UserRole, repositorio)
            self._lista.addItem(item)

        self._status.setText(
            f"{self._lista.count()} repositório(s) disponível(is)."
        )
        if self._lista.count():
            self._lista.setCurrentRow(0)
            self._botoes.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self._botoes.button(QDialogButtonBox.Ok).setEnabled(False)

    def repositorio_selecionado(self) -> dict | None:
        item = self._lista.currentItem()
        if item is None:
            return None
        valor = item.data(Qt.UserRole)
        return valor if isinstance(valor, dict) else None

    def _aceitar_selecionado(self):
        if self.repositorio_selecionado():
            self.accept()


# ══════════════════════════════════════════════════════════════════════
# Tela 3 — GitUIProjeto
# ══════════════════════════════════════════════════════════════════════

class GitUIProjeto(QWidget):
    """
    Terceira tela do painel GitHub.
    Exibida quando há um projeto aberto com Git configurado.

    Botões em grade 2×2: Salvar / Enviar / Baixar / Histórico.
    Botão "🌿 Ver alterações" abre aba Git no terminal central.
    Clique no nome do projeto abre o GitHub no navegador.
    """

    abrir_painel_git        = Signal()        # sinal para o main_window abrir aba Git
    abrir_historico_terminal = Signal(object) # passa _PainelHistoricoVersoes como aba
    commit_realizado        = Signal()        # sinal para o Núcleo registrar o commit
    push_realizado          = Signal()        # sinal para o Núcleo exportar após push

    def __init__(self, terminal: GitTerminal, parent=None):
        super().__init__(parent)
        self._terminal          = terminal
        self._git               = GerenciadorGit()
        self._api               = GitHubAPI()
        self._caminho           : str = ""
        self._pontes            : list = []
        self._cb_fechar_projeto = None
        self._cb_sair           = None

        self._construir_ui()

    def set_callback_fechar_projeto(self, fn):
        self._cb_fechar_projeto = fn

    def set_callback_sair(self, fn):
        self._cb_sair = fn

    # ── UI ────────────────────────────────────────────────────────────

    def _construir_ui(self):
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        _estilo_menu = """
            QMenu {
                background:#0d0d0d; color:#c9d1d9;
                border:1px solid #2a2a2a; font-size:10px;
            }
            QMenu::item { padding:5px 16px; }
            QMenu::item:selected { background:#1e3a5f; }
            QMenu::separator { height:1px; background:#2a2a2a; margin:2px 8px; }
        """

        # ── Cabeçalho ─────────────────────────────────────────────────
        cab = QWidget()
        cab.setStyleSheet("background:#0d0d0d;")
        lay_cab = QHBoxLayout(cab)
        lay_cab.setContentsMargins(8, 6, 8, 6)
        lay_cab.setSpacing(4)

        lbl_titulo = QLabel("GITHUB")
        lbl_titulo.setStyleSheet("font-size:11px; font-weight:bold; color:#4ec994;")

        # Nome do projeto com seta — clicável, abre menu dropdown
        self._lbl_projeto = QPushButton("▾")
        self._lbl_projeto.setStyleSheet("""
            QPushButton {
                font-size:10px; color:#4ec994;
                background:transparent; border:none;
                text-align:right; padding:0 2px;
            }
            QPushButton:hover { color:#6ef0b4; }
            QPushButton:focus { outline: none; }
        """)
        self._lbl_projeto.setCursor(Qt.PointingHandCursor)
        self._lbl_projeto.clicked.connect(self._abrir_menu_projeto)

        lay_cab.addWidget(lbl_titulo)
        lay_cab.addStretch()
        lay_cab.addWidget(self._lbl_projeto)
        raiz.addWidget(cab)

        # Info de ramificação + hash
        self._lbl_info = QLabel("")
        self._lbl_info.setStyleSheet(
            "font-size:10px; color:#555; background:#0d0d0d; padding:0 8px 4px 8px;"
        )
        raiz.addWidget(self._lbl_info)

        raiz.addWidget(_sep())

        # ── Botão para abrir aba Git no terminal central ───────────────
        corpo = QWidget()
        corpo.setStyleSheet("background:#0d0d0d;")
        lay_corpo = QVBoxLayout(corpo)
        lay_corpo.setContentsMargins(8, 8, 8, 8)
        lay_corpo.setSpacing(6)

        self._btn_ver_alteracoes = _botao("  Ver alterações")
        self._btn_ver_alteracoes.setIcon(icone_tema("mdi.source-branch"))
        self._btn_ver_alteracoes.setIconSize(QSize(14, 14))
        self._btn_ver_alteracoes.clicked.connect(lambda: self.abrir_painel_git.emit())
        lay_corpo.addWidget(self._btn_ver_alteracoes)

        raiz.addWidget(corpo)

        # Subpainéis e botões criados mas não exibidos aqui — usados pela aba Git no terminal
        self._btn_salvar    = _botao("  Salvar no Git")
        self._btn_salvar.setIcon(icone_tema("mdi.content-save"))
        self._btn_salvar.setIconSize(QSize(14, 14))
        self._btn_salvar.setToolTip(
            "Salva um ponto de restauração local do projeto.\n"
            "Não envia nada para a internet."
        )

        self._btn_enviar    = _botao("  Enviar pro GitHub")
        self._btn_enviar.setIcon(icone_tema("mdi.cloud-upload"))
        self._btn_enviar.setIconSize(QSize(14, 14))
        self._btn_enviar.setToolTip(
            "Envia as versões salvas localmente para o GitHub.\n"
            "Requer conexão com a internet."
        )

        self._btn_atualizar = _botao("  Atualizar do GitHub")
        self._btn_atualizar.setIcon(icone_tema("mdi.cloud-download"))
        self._btn_atualizar.setIconSize(QSize(14, 14))
        self._btn_atualizar.setToolTip(
            "Baixa atualizações do GitHub para o seu computador.\n"
            "Use quando outra pessoa enviou mudanças pro mesmo projeto."
        )

        self._btn_historico = _botao("  Histórico")
        self._btn_historico.setIcon(icone_tema("mdi.history"))
        self._btn_historico.setIconSize(QSize(14, 14))
        self._btn_historico.setToolTip(
            "Mostra todas as versões salvas e permite restaurar uma anterior."
        )

        self._btn_salvar.clicked.connect(self._ao_salvar)
        self._btn_enviar.clicked.connect(self._ao_enviar)
        self._btn_atualizar.clicked.connect(self._ao_atualizar)
        self._btn_historico.clicked.connect(self._ao_historico)

        self._painel_status            = _PainelStatus(self._git, self._terminal)
        self._painel_diferencas        = _PainelDiferencas(self._git)
        self._painel_ramificacoes      = _PainelRamificacoes(self._git, self._terminal)
        self._painel_guardados         = _PainelGuardados(self._git, self._terminal)
        self._painel_historico_arquivo = _PainelHistoricoArquivo(self._git, self._terminal)

        # Container do histórico inline (aba "Histórico" dentro do QTabWidget)
        self._painel_historico_inline = QWidget()
        self._painel_historico_inline.setStyleSheet("background:#0d0d0d;")
        _lay_hist_inline = QVBoxLayout(self._painel_historico_inline)
        _lay_hist_inline.setContentsMargins(0, 0, 0, 0)
        _lay_hist_inline.setSpacing(0)

        self._arquivo_ativo = ""   # caminho absoluto do arquivo aberto no editor

        self._estilo_menu = _estilo_menu

        # Labels e botão para o painel GitHub no terminal
        self._gh_lbl_repo_url = QLabel("nenhum")
        self._gh_lbl_repo_url.setStyleSheet(
            "font-size:10px; color:#888; padding:2px 8px; background:transparent;"
        )
        self._gh_lbl_repo_url.setWordWrap(True)

        self._gh_lbl_usuario = QLabel("")
        self._gh_lbl_usuario.setStyleSheet(
            "font-size:10px; color:#4ec994; padding:6px 8px 0 8px;"
        )
        self._gh_lbl_estado = QLabel("")
        self._gh_lbl_estado.setStyleSheet(
            "font-size:10px; color:#555; padding:2px 8px 8px 8px;"
        )
        self._btn_reconectar = _botao("  Trocar repositório")
        self._btn_reconectar.setIcon(icone_tema("mdi.link-variant"))
        self._btn_reconectar.setIconSize(QSize(14, 14))
        self._btn_reconectar.setToolTip(
            "Trocar o repositório remoto deste projeto."
        )
        self._btn_reconectar.clicked.connect(self._acao_trocar_repo)

        self._btn_desvincular = _botao("  Desvincular remoto")
        self._btn_desvincular.setIcon(icone_tema("mdi.link-off"))
        self._btn_desvincular.setIconSize(QSize(14, 14))
        self._btn_desvincular.setToolTip(
            "Remove o vínculo local. Não apaga arquivos nem o repositório no GitHub."
        )
        self._btn_desvincular.clicked.connect(self._acao_desvincular_repo)

        self._btn_deletar_repo = _botao("  Apagar repositório no GitHub")
        self._btn_deletar_repo.setIcon(icone_tema("mdi.delete-forever"))
        self._btn_deletar_repo.setIconSize(QSize(14, 14))
        self._btn_deletar_repo.setToolTip(
            "Apaga permanentemente o repositório remoto no GitHub."
        )
        self._btn_deletar_repo.clicked.connect(self._acao_deletar_repo)

    # ── API pública ───────────────────────────────────────────────────

    def abrir_projeto(self, caminho: str):
        self._caminho = caminho
        nome = os.path.basename(caminho)
        self._lbl_projeto.setText(f"{nome} ▾")

        branch  = self._git.branch_atual(caminho)
        self._btn_ver_alteracoes.setText(f"  {branch}")
        self._lbl_info.setWordWrap(True)
        self._lbl_info.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._lbl_info.setText(
            self._git._executar(["log", "--oneline", "-1", "--format=%h %s"], caminho).saida.strip()
        )

        self._terminal.info(f"Projeto aberto: {nome}")
        self._terminal.info(f"Ramificação: {branch}")

        self._atualizar_estado_remoto()
        tem_remoto = self._verificar_remoto()
        if tem_remoto:
            self._terminal.ok("Repositório conectado ao GitHub")
        else:
            self._terminal.info("Repositório ainda não conectado ao GitHub")

        self._atualizar_aba_atual()

    def _abrir_menu_projeto(self):
        """Abre o menu dropdown do projeto."""
        if not self._caminho:

            return

        menu = QMenu(self)
        menu.setStyleSheet(self._estilo_menu)

        a = menu.addAction("Abrir no GitHub")
        a.setIcon(icone_tema("mdi.github"))
        a.triggered.connect(self._acao_abrir_github)

        menu.addSeparator()

        a = menu.addAction("Sair da conta")
        a.setIcon(icone_tema("mdi.logout"))
        a.triggered.connect(self._acao_sair_conta)

        menu.exec(self._lbl_projeto.mapToGlobal(
            self._lbl_projeto.rect().bottomLeft()
        ))

    def _acao_abrir_github(self):
        if not self._caminho:

            return

        r = self._git._executar(["remote", "get-url", "origin"], self._caminho)
        url = r.saida.strip() if r.ok else ""
        if url.startswith("git@github.com:"):
            url = "https://github.com/" + url[len("git@github.com:"):].removesuffix(".git")
        elif url.endswith(".git"):
            url = url.removesuffix(".git")
        if url.startswith("https://"):
            webbrowser.open(url)
            log.info(_ARQ, "_acao_abrir_github", f"abrindo: {url}")
        else:
            self._terminal.aviso("Repositório remoto não encontrado")

    def _acao_trocar_repo(self):
        if not self._caminho:
            return

        if not config_github().esta_logado():
            self._terminal.erro(
                "Nenhuma sessão ativa — entre no GitHub para escolher um repositório."
            )
            return

        r_atual = self._git._executar(
            ["remote", "get-url", "origin"], self._caminho
        )
        remoto_atual = r_atual.saida.strip() if r_atual.ok else ""
        dialogo = _DialogSelecionarRepositorio(remoto_atual, parent=self)

        def _carregar():
            return self._api.listar_repositorios()

        ponte = _em_thread(
            _carregar,
            dialogo.definir_repositorios,
            dialogo,
        )
        self._pontes.append(ponte)

        if dialogo.exec() != QDialog.Accepted:
            return

        repositorio = dialogo.repositorio_selecionado()
        url_final = str((repositorio or {}).get("clone_url", "")).strip()
        nome = str((repositorio or {}).get("name", "")).strip()
        if not url_final or not nome:
            self._terminal.erro("O repositório selecionado não possui endereço válido")
            return

        if remoto_atual and remoto_atual.rstrip("/").removesuffix(".git") == url_final.rstrip("/").removesuffix(".git"):
            self._terminal.info(f"Este projeto já está vinculado a '{nome}'")
            return

        if not HeinPopup.confirmar(
            "Trocar repositório",
            f"Vincular este projeto a <b>{nome}</b>?",
            informativo=(
                "O vínculo remoto local atual será substituído. "
                "Nenhum arquivo local será apagado."
            ),
            parent=self,
        ):
            return

        self._bloquear_botoes(True)
        r = self._git.definir_remoto(
            self._caminho,
            url_final,
            config_github().token,
        )
        self._bloquear_botoes(False)
        if r.ok:
            self._terminal.ok(f"Repositório vinculado: {nome}")
            self._atualizar_estado_remoto()
        else:
            self._terminal.erro(f"Falha ao vincular repositório: {r.erro}")

    def _acao_desvincular_repo(self):
        if not self._caminho or not self._verificar_remoto():
            self._terminal.info("Este projeto não possui repositório remoto vinculado")
            return

        if not HeinPopup.confirmar(
            "Desvincular repositório",
            "Remover o vínculo remoto deste projeto?",
            informativo=(
                "Os arquivos e o histórico local serão mantidos. "
                "O repositório no GitHub não será apagado."
            ),
            parent=self,
        ):
            return

        r = self._git.remover_remoto(self._caminho)
        if r.ok:
            self._terminal.ok("Repositório desvinculado. Arquivos locais mantidos.")
            self._atualizar_estado_remoto()
        else:
            self._terminal.erro(f"Falha ao desvincular: {r.erro}")

    def _acao_criar_repo(self):
        token = config_github().token
        if not token:
            self._terminal.erro("Nenhuma sessão ativa — faça login primeiro")

            return

        nome, ok = QInputDialog.getText(
            self, "Criar repositório",
            "Nome do novo repositório no GitHub:",
        )
        if not ok or not nome.strip():

            return

        nome = nome.strip()
        self._terminal.info(f"Criando repositório '{nome}' no GitHub...")
        self._bloquear_botoes(True)

        def _criar():
            import urllib.request, json as _json
            dados = _json.dumps({"name": nome, "private": False}).encode()
            req = urllib.request.Request(
                "https://api.github.com/user/repos",
                data=dados,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                info = _json.loads(resp.read())
            clone_url = info.get("clone_url", "")
            self._git.definir_remoto(
                self._caminho,
                clone_url,
                token,
            )

            return clone_url

        def _concluido(clone_url):
            self._bloquear_botoes(False)
            if clone_url is None:
                self._terminal.erro("Falha ao criar repositório — verifique o log")
            else:
                self._terminal.ok(f"Repositório criado: {clone_url}")
                log.ok(_ARQ, "_acao_criar_repo", clone_url)

        p = _em_thread(_criar, _concluido, self)
        self._pontes.append(p)

    def _acao_sair_conta(self):
        if not HeinPopup.confirmar(
            "Sair da conta",
            "Deseja sair da conta do GitHub?",
            informativo="O token local será removido.",
            parent=self,
        ):
            return
        webbrowser.open("https://github.com/settings/tokens")
        config_github().limpar_sessao()
        self._terminal.info("Sessão encerrada — faça login novamente")
        log.info(_ARQ, "_acao_sair_conta", "sessão encerrada")
        if self._cb_sair:
            self._cb_sair()

    def _acao_deletar_repo(self):
        token = config_github().token
        if not token:
            self._terminal.erro("Nenhuma sessão ativa — faça login primeiro")

            return

        r_url = self._git._executar(["remote", "get-url", "origin"], self._caminho)
        url = r_url.saida.strip() if r_url.ok else ""
        if not url:
            self._terminal.erro("Repositório remoto não encontrado")

            return

        if url.startswith("git@github.com:"):
            repo_path = url[len("git@github.com:"):].removesuffix(".git")
        else:
            parsed = urlparse(url)
            if parsed.hostname != "github.com":
                self._terminal.erro("O remoto não é um repositório do GitHub")
                return
            repo_path = parsed.path.strip("/").removesuffix(".git")

        if repo_path.count("/") != 1:
            self._terminal.erro("Endereço do repositório inválido")
            return
        if not HeinPopup.confirmar(
            "Apagar repositório no GitHub",
            f"Apagar permanentemente <b>github.com/{repo_path}</b>?",
            informativo=(
                "Isto apaga o repositório remoto e remove o vínculo local. "
                "Os arquivos do projeto e o histórico Git local serão mantidos."
            ),
            parent=self,
        ):
            return

        proprietario, nome = repo_path.split("/", 1)
        self._terminal.aviso(f"Apagando repositório {repo_path}...")
        self._bloquear_botoes(True)

        def _apagar():
            sucesso = self._api.deletar_repositorio(proprietario, nome)
            return sucesso, self._api.ultimo_status_http

        def _concluido(resultado):
            self._bloquear_botoes(False)
            sucesso, status_http = resultado or (False, None)
            if sucesso:
                self._terminal.ok(f"Repositório apagado no GitHub: {repo_path}")
                r_remoto = self._git.remover_remoto(self._caminho)
                self._atualizar_estado_remoto()
                log.ok(_ARQ, "_acao_deletar_repo", repo_path)
                if not r_remoto.ok:
                    mensagem = (
                        "O repositório foi apagado no GitHub, mas não foi possível "
                        f"remover o vínculo local: {r_remoto.erro}"
                    )
                    self._terminal.erro(mensagem)
                    _popup_falha_git(self, "Vínculo local não removido", mensagem)
            elif status_http == 403:
                mensagem = (
                    "O GitHub recusou a exclusão (403). "
                    "Saia da conta e entre novamente para autorizar "
                    "a permissão de apagar repositórios, e confirme que "
                    "essa conta é proprietária ou administradora do repositório."
                )
                self._terminal.erro(mensagem)
                _popup_falha_git(self, "Não foi possível apagar o repositório", mensagem)
            elif status_http == 404:
                mensagem = (
                    f"O GitHub não encontrou {repo_path} (404). Se você já o apagou "
                    "no site, ele já está ausente; não há nada para apagar novamente. "
                    "Se ele ainda aparece no site, confira a conta e o endereço remoto. "
                    "Você pode remover só o vínculo local; isso não apaga arquivos "
                    "nem histórico Git."
                )
                self._terminal.erro(mensagem)
                resp = HeinPopup.escolher(
                    "Repositório não encontrado",
                    mensagem,
                    opcoes=["Remover vínculo local", "Manter vínculo"],
                    parent=self,
                )
                if resp == 0:
                    r_remoto = self._git.remover_remoto(self._caminho)
                    if r_remoto.ok:
                        self._terminal.ok(
                            "Vínculo local removido; arquivos e histórico Git mantidos."
                        )
                        self._atualizar_estado_remoto()
                    else:
                        erro = f"Falha ao remover o vínculo local: {r_remoto.erro}"
                        self._terminal.erro(erro)
                        _popup_falha_git(self, "Não foi possível desvincular", erro)
            else:
                mensagem = (
                    "Não foi possível apagar o repositório no GitHub. "
                    "Verifique sua conexão e sua permissão e tente novamente."
                )
                self._terminal.erro(mensagem)
                _popup_falha_git(self, "Falha ao apagar o repositório", mensagem)

        p = _em_thread(_apagar, _concluido, self)
        self._pontes.append(p)

    def _ao_trocar_aba(self, idx: int):
        self._atualizar_aba_por_indice(idx)

    def _atualizar_aba_atual(self):
        """Atualiza o painel Status (índice 1) por padrão."""
        self._atualizar_aba_por_indice(1)

    def set_arquivo_ativo(self, caminho_arquivo: str):
        """
        Chamado pelo MainWindow quando o usuário muda de aba no editor.
        Atualiza o painel de histórico do arquivo.
        """
        self._arquivo_ativo = caminho_arquivo
        self._painel_historico_arquivo.set_arquivo_ativo(
            self._caminho, caminho_arquivo
        )

    def _atualizar_aba_por_indice(self, idx: int):
        if not self._caminho:

            return

        if idx == 0:
            pass  # Aba Salvar — sem dados a pré-carregar
        elif idx == 1:
            self._painel_status.atualizar(self._caminho)
        elif idx == 2:
            self._painel_diferencas.atualizar(self._caminho)
        elif idx == 3:
            self._painel_ramificacoes.atualizar(self._caminho)
        elif idx == 4:
            self._painel_guardados.atualizar(self._caminho)
        elif idx == 5:
            self._painel_historico_arquivo.set_arquivo_ativo(
                self._caminho, self._arquivo_ativo
            )
        elif idx == 6:
            self._ao_historico()

    def _verificar_remoto(self) -> bool:
        if not self._caminho:

            return False

        r = self._git._executar(["remote", "-v"], self._caminho)

        return bool(r.saida.strip())

    def _atualizar_estado_remoto(self):
        """
        Atualiza indicadores de conexão no painel GitHub do terminal central.
        """
        cfg   = config_github()
        login = cfg.login or ""
        tem_remoto = self._verificar_remoto()

        self._gh_lbl_usuario.setText(f"@{login}" if login else "não logado")
        if tem_remoto:
            self._gh_lbl_estado.setText("conectado ao GitHub")
            self._gh_lbl_estado.setStyleSheet(
                "font-size:10px; color:#4ec994; padding:2px 8px 8px 8px;"
            )
            self._btn_enviar.setEnabled(True)
            self._btn_atualizar.setEnabled(True)
            r_url = self._git._executar(["remote", "get-url", "origin"], self._caminho)
            url_limpa = r_url.saida.strip() if r_url.ok else "?"
            import re as _re
            url_limpa = _re.sub(r"https://[^@]+@", "https://", url_limpa)
            self._gh_lbl_repo_url.setText(url_limpa)
        else:
            self._gh_lbl_estado.setText("sem repositório remoto")
            self._gh_lbl_estado.setStyleSheet(
                "font-size:10px; color:#e06c75; padding:2px 8px 8px 8px;"
            )
            self._btn_enviar.setEnabled(False)
            self._btn_atualizar.setEnabled(False)
            self._gh_lbl_repo_url.setText("nenhum")

    def atualizar_conta(self):
        """Atualiza a conta exibida sem alterar o remoto da pasta."""
        self._atualizar_estado_remoto()

    def montar_painel_terminal(self) -> "QWidget":
        """
        Retorna o widget completo da aba Git no terminal central,
        com layout lado a lado: GIT LOCAL (esq) | GITHUB (dir).

        Chamado pelo main_window ao abrir a aba Git.
        Pode ser chamado apenas uma vez — retorna o mesmo widget em
        chamadas subsequentes.
        """
        if hasattr(self, "_painel_terminal"):
            return self._painel_terminal

        def _sep_v():
            s = QWidget()
            s.setFixedHeight(1)
            s.setStyleSheet("background:#1a1a1a;")
            return s

        def _cab_secao(texto: str) -> QWidget:
            w = QWidget()
            w.setStyleSheet("background:#0a0a0a;")
            lay = QHBoxLayout(w)
            lay.setContentsMargins(8, 5, 8, 5)
            lbl = QLabel(texto)
            lbl.setStyleSheet(
                "font-size:10px; font-weight:bold; color:#444;"
                " letter-spacing:1px; background:transparent;"
            )
            lay.addWidget(lbl)
            lay.addStretch()
            return w

        raiz = QWidget()
        raiz.setStyleSheet("background:#0d0d0d;")
        lay_raiz = QHBoxLayout(raiz)
        lay_raiz.setContentsMargins(0, 0, 0, 0)
        lay_raiz.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle { background:#1a1a1a; width:2px; }"
        )

        # ══════════════════════════════════════════════════════════════
        # LADO ESQUERDO — GIT LOCAL
        # ══════════════════════════════════════════════════════════════
        lado_git = QWidget()
        lado_git.setStyleSheet("background:#0d0d0d;")
        lay_git = QVBoxLayout(lado_git)
        lay_git.setContentsMargins(0, 0, 0, 0)
        lay_git.setSpacing(0)

        lay_git.addWidget(_cab_secao("GIT LOCAL"))
        lay_git.addWidget(_sep_v())

        # Abas: Salvar | Status | Diferenças | Ramificações | Guardados | Arquivo | Histórico
        abas = QTabWidget()
        abas.setStyleSheet("""
            QTabWidget::pane  { border:none; background:#0d0d0d; }
            QTabBar::tab {
                background:#0a0a0a; color:#555;
                padding:4px 10px; font-size:10px;
                border:none; border-right:1px solid #1a1a1a;
            }
            QTabBar::tab:selected { color:#c9d1d9; background:#0d0d0d; }
            QTabBar::tab:hover    { color:#c9d1d9; }
        """)

        # Aba 0 — Salvar
        painel_salvar = QWidget()
        painel_salvar.setStyleSheet("background:#0d0d0d;")
        lay_salvar = QVBoxLayout(painel_salvar)
        lay_salvar.setContentsMargins(8, 8, 8, 8)
        lay_salvar.setSpacing(6)
        lay_salvar.addWidget(self._btn_salvar)
        lay_salvar.addStretch()

        abas.addTab(painel_salvar,                  "Salvar")
        abas.addTab(self._painel_status,            "Status")
        abas.addTab(self._painel_diferencas,        "Diferenças")
        abas.addTab(self._painel_ramificacoes,      "Ramificações")
        abas.addTab(self._painel_guardados,         "Guardados")
        abas.addTab(self._painel_historico_arquivo, "Arquivo")
        abas.addTab(self._painel_historico_inline,  "Histórico")
        abas.currentChanged.connect(self._ao_trocar_aba)
        self._abas_terminal = abas
        lay_git.addWidget(abas, 1)

        splitter.addWidget(lado_git)

        # ══════════════════════════════════════════════════════════════
        # LADO DIREITO — GITHUB
        # ══════════════════════════════════════════════════════════════
        lado_gh = QWidget()
        lado_gh.setStyleSheet("background:#0d0d0d;")
        lay_gh = QVBoxLayout(lado_gh)
        lay_gh.setContentsMargins(0, 0, 0, 0)
        lay_gh.setSpacing(0)

        lay_gh.addWidget(_cab_secao("GITHUB"))
        lay_gh.addWidget(_sep_v())

        abas_gh = QTabWidget()
        abas_gh.setStyleSheet("""
            QTabWidget::pane  { border:none; background:#0d0d0d; }
            QTabBar::tab {
                background:#0a0a0a; color:#555;
                padding:4px 10px; font-size:10px;
                border:none; border-right:1px solid #1a1a1a;
            }
            QTabBar::tab:selected { color:#c9d1d9; background:#0d0d0d; }
            QTabBar::tab:hover    { color:#c9d1d9; }
        """)

        # Aba 0 — Conta
        painel_conta = QWidget()
        painel_conta.setStyleSheet("background:#0d0d0d;")
        lay_conta = QVBoxLayout(painel_conta)
        lay_conta.setContentsMargins(8, 8, 8, 8)
        lay_conta.setSpacing(6)
        lay_conta.addWidget(self._gh_lbl_usuario)
        lay_conta.addWidget(self._gh_lbl_estado)
        lay_conta.addStretch()

        # Aba 1 — Repositório
        painel_repo = QWidget()
        painel_repo.setStyleSheet("background:#0d0d0d;")
        lay_repo = QVBoxLayout(painel_repo)
        lay_repo.setContentsMargins(8, 8, 8, 8)
        lay_repo.setSpacing(6)
        lbl_repo_titulo = QLabel("Repositório remoto:")
        lbl_repo_titulo.setStyleSheet("font-size:10px; color:#555; background:transparent;")
        lay_repo.addWidget(lbl_repo_titulo)
        lay_repo.addWidget(self._gh_lbl_repo_url)
        lay_repo.addSpacing(6)
        lay_repo.addWidget(self._btn_reconectar)
        lay_repo.addWidget(self._btn_desvincular)
        lay_repo.addWidget(self._btn_deletar_repo)
        self._btn_reconectar.setVisible(True)
        btn_criar = _botao("  Criar no GitHub")
        try:
            from _UTILITARIOS_.icones_tema import icone_tema as _icone
            btn_criar.setIcon(_icone("mdi.github"))
            from PySide6.QtCore import QSize as _QSize
            btn_criar.setIconSize(_QSize(14, 14))
        except Exception:
            pass
        btn_criar.clicked.connect(self._acao_criar_repo)
        lay_repo.addWidget(btn_criar)
        lay_repo.addStretch()

        # Aba 2 — Enviar
        painel_enviar = QWidget()
        painel_enviar.setStyleSheet("background:#0d0d0d;")
        lay_enviar = QVBoxLayout(painel_enviar)
        lay_enviar.setContentsMargins(8, 8, 8, 8)
        lay_enviar.setSpacing(6)
        lbl_env_desc = QLabel("Envia os commits locais para o repositório remoto.")
        lbl_env_desc.setStyleSheet("font-size:10px; color:#555; background:transparent;")
        lbl_env_desc.setWordWrap(True)
        lay_enviar.addWidget(lbl_env_desc)
        lay_enviar.addSpacing(4)
        lay_enviar.addWidget(self._btn_enviar)
        lay_enviar.addStretch()

        # Aba 3 — Baixar
        painel_baixar = QWidget()
        painel_baixar.setStyleSheet("background:#0d0d0d;")
        lay_baixar = QVBoxLayout(painel_baixar)
        lay_baixar.setContentsMargins(8, 8, 8, 8)
        lay_baixar.setSpacing(6)
        lbl_baixar_desc = QLabel(
            "Baixa alterações do GitHub.\n"
            "Salve no Git antes para não perder alterações locais."
        )
        lbl_baixar_desc.setStyleSheet("font-size:10px; color:#555; background:transparent;")
        lbl_baixar_desc.setWordWrap(True)
        lay_baixar.addWidget(lbl_baixar_desc)
        lay_baixar.addSpacing(4)
        lay_baixar.addWidget(self._btn_atualizar)
        lay_baixar.addStretch()

        abas_gh.addTab(painel_conta,   "Conta")
        abas_gh.addTab(painel_repo,    "Repositório")
        abas_gh.addTab(painel_enviar,  "Enviar")
        abas_gh.addTab(painel_baixar,  "Baixar")
        lay_gh.addWidget(abas_gh, 1)

        splitter.addWidget(lado_gh)

        # Proporção inicial: 68% Git | 32% GitHub
        splitter.setSizes([680, 320])

        lay_raiz.addWidget(splitter)
        self._painel_terminal = raiz
        return raiz

    def _bloquear_botoes(self, bloquear: bool):
        for btn in [self._btn_salvar, self._btn_enviar,
                    self._btn_atualizar, self._btn_historico,
                    self._btn_reconectar, self._btn_desvincular,
                    self._btn_deletar_repo]:
            btn.setEnabled(not bloquear)

    def _atualizar_info(self):
        if not self._caminho:

            return

        branch   = self._git.branch_atual(self._caminho)
        r_log    = self._git._executar(
            ["log", "--oneline", "-1", "--format=%h %s"], self._caminho
        )
        hash_msg = r_log.saida.strip() if r_log.ok else ""
        self._btn_ver_alteracoes.setText(f"  {branch}")
        self._lbl_info.setText(f"{branch}   {hash_msg}")

    # ── Utilitários de versão ─────────────────────────────────────────

    def _ler_version(self) -> str:
        arq = os.path.join(self._caminho, "VERSION")
        try:
            if os.path.exists(arq):

                return open(arq, encoding="utf-8").read().strip()

        except Exception:
            pass

        return ""

    def _incrementar_version(self, versao_atual: str, tipo: str) -> str:
        try:
            sem_v  = versao_atual.lstrip("v")
            partes = sem_v.split(".")
            if len(partes) != 3:

                return versao_atual

            major, minor, patch = int(partes[0]), int(partes[1]), int(partes[2])
            if tipo == "minor":
                minor += 1; patch = 0
            else:
                patch += 1

            return f"v{major}.{minor}.{patch}"

        except Exception:

            return versao_atual

    def _salvar_version(self, nova_versao: str):
        arq = os.path.join(self._caminho, "VERSION")
        with open(arq, "w", encoding="utf-8") as f:
            f.write(nova_versao + "\n")

    # ── Ações dos botões principais ───────────────────────────────────

    def _ao_salvar(self):
        if not self._caminho:

            return

        alterados = self._git.arquivos_alterados(self._caminho)
        if not alterados:
            self._terminal.info("Nenhuma alteração para salvar")

            return

        mensagem, ok = QInputDialog.getText(
            self, "Salvar versão",
            "Descreva o que mudou (ou deixe em branco):",
        )
        if not ok:

            return

        if not mensagem.strip():
            mensagem = "Versão salva pelo hein Editor"

        versao_atual = self._ler_version()
        nova_versao  = versao_atual

        if versao_atual:
            nova_versao = self._incrementar_version(versao_atual, "patch")
        else:
            try:
                import subprocess as _sp
                _r = _sp.run(
                    ["git", "describe", "--tags", "--abbrev=0"],
                    cwd=self._caminho, capture_output=True, text=True, timeout=5,
                )
                nova_versao = _r.stdout.strip() if _r.returncode == 0 else "v0.1.0"
            except Exception:
                nova_versao = "v0.1.0"

        try:
            self._salvar_version(nova_versao)
        except Exception as e:
            log.erro(_ARQ, "_ao_salvar", "falha ao salvar VERSION", str(e))
            nova_versao = versao_atual
        if nova_versao:
            mensagem = f"{nova_versao} — {mensagem}"

        self._terminal.info("Salvando versão...")
        self._bloquear_botoes(True)
        log.info(_ARQ, "_ao_salvar", f"commit em {self._caminho}")

        def _salvar():
            return self._git.salvar_versao(self._caminho, mensagem)

        def _concluido(r):
            self._bloquear_botoes(False)
            if r.ok:
                qtd = len(alterados)
                self._terminal.ok(f"{qtd} arquivo{'s' if qtd != 1 else ''} salvo{'s' if qtd != 1 else ''}")
                if nova_versao and nova_versao != versao_atual:
                    self._terminal.versao_incrementada(nova_versao)
                self._atualizar_info()
                self._atualizar_aba_atual()
                self.commit_realizado.emit()
                if nova_versao and nova_versao != versao_atual:
                    try:
                        from _UTILITARIOS_.versionamento import registrar_changelog_commit
                        _msg_limpa = mensagem.split("—", 1)[-1].strip() if "—" in mensagem else mensagem
                        registrar_changelog_commit(self._caminho, _msg_limpa, nova_versao)
                    except Exception:
                        pass
            else:
                self._terminal.erro(f"Falha ao salvar: {r.erro}")
                log.erro(_ARQ, "_ao_salvar", "commit falhou", r.erro)

        p = _em_thread(_salvar, _concluido, self)
        self._pontes.append(p)

    def _ao_enviar(self):
        if not self._caminho:

            return

        token = config_github().token
        if not token:
            self._terminal.erro("Erro: não há sessão ativa")

            return

        if not HeinPopup.confirmar(
            "Enviar para o GitHub",
            "Enviar os commits locais para o repositório remoto?",
            informativo="Esta ação enviará todos os commits não publicados.",
            parent=self,
        ):
            return

        self._terminal.info("Enviando para o GitHub...")
        self._bloquear_botoes(True)
        log.info(_ARQ, "_ao_enviar", f"push de {self._caminho}")

        def _enviar():
            return self._git.enviar_para_github(self._caminho, token)

        def _concluido(r):
            self._bloquear_botoes(False)
            if r.ok:
                self._terminal.ok("Envio concluído")
                log.ok(_ARQ, "_ao_enviar", "push concluído")
                self.push_realizado.emit()
                try:
                    from _UTILITARIOS_.versionamento import registrar_push
                    registrar_push(self._caminho)
                except Exception:
                    pass
            else:
                erro_lower = (r.erro or "").lower()
                if _push_bloqueado_por_segredo(r.erro):
                    locais = _locais_segredos_detectados(r.erro)
                    resumo_locais = (
                        "\n\nArquivos/linhas sinalizados:\n"
                        + "\n".join(f"• {local}" for local in locais)
                        if locais else ""
                    )
                    mensagem = (
                        "O GitHub bloqueou este envio pela proteção contra segredos "
                        "(GH013). O commit contém credenciais reconhecidas pelo GitHub.\n\n"
                        "O arquivo listado pode estar incluído no histórico mesmo que "
                        "tenha sido adicionado ao .gitignore depois."
                        f"{resumo_locais}\n\n"
                        "Forçar o envio ou baixar alterações não remove esses dados: "
                        "o GitHub continuará recusando o commit. O .gitignore também "
                        "não apaga arquivos que já entraram no histórico.\n\n"
                        "Revogue e gere novamente as credenciais expostas. Você pode "
                        "limpar todo o histórico Git local e tentar enviar novamente; "
                        "os arquivos do projeto serão mantidos e o .gitignore será aplicado."
                    )
                    self._terminal.erro(
                        "Envio bloqueado pela proteção de segredos do GitHub (GH013)."
                    )
                    self._terminal.info(
                        "Forçar ou baixar não resolve este bloqueio. "
                        "Veja o caminho e o commit indicados no erro do Git."
                    )
                    resp = HeinPopup.escolher(
                        "GitHub bloqueou o envio",
                        mensagem,
                        opcoes=["Limpar histórico local e reenviar", "Agora não"],
                        parent=self,
                    )
                    if resp == 0:
                        self._ao_reiniciar_historico_e_reenviar()
                    log.erro(_ARQ, "_ao_enviar", "push bloqueado por segredo", r.erro)
                elif _push_rejeitado_por_historico_divergente(erro_lower):
                    self._terminal.erro(
                        "Envio recusado: o GitHub tem alterações que você ainda não baixou."
                    )
                    self._terminal.info(
                        "Escolha: baixar as alterações do GitHub e reenviar (seguro), "
                        "ou forçar o envio descartando o que está no GitHub."
                    )
                    resp = HeinPopup.escolher(
                        "Envio recusado",
                        "O GitHub tem alterações que você não tem localmente.\n"
                        "Como deseja prosseguir?",
                        opcoes=["Baixar e reenviar (seguro)", "Forçar envio (descarta o remoto)"],
                        parent=self,
                    )
                    if resp == 0:
                        self._ao_baixar_e_reenviar()
                    elif resp == 1:
                        self._ao_forcar_envio()
                else:
                    self._terminal.erro(f"Falha ao enviar: {r.erro}")
                    log.erro(_ARQ, "_ao_enviar", "push falhou", r.erro)
                    HeinPopup.escolher(
                        "Falha ao enviar para o GitHub",
                        f"O GitHub não aceitou o envio.\n\nDetalhe:\n{r.erro}",
                        opcoes=["Fechar"],
                        parent=self,
                    )

        p = _em_thread(_enviar, _concluido, self)
        self._pontes.append(p)

    def _ao_reiniciar_historico_e_reenviar(self):
        if not self._caminho:
            return

        token = config_github().token
        if not token:
            self._terminal.erro("Erro: não há sessão ativa")
            return

        if not HeinPopup.confirmar(
            "Limpar histórico e reenviar",
            "Apagar todo o histórico Git local e publicar um commit novo?",
            informativo=(
                "Os arquivos do projeto serão mantidos; arquivos ignorados pelo "
                ".gitignore não serão adicionados ao novo commit. Todos os commits, "
                "branches, tags e stashes locais serão apagados. A branch atual no "
                "GitHub será substituída. Se o GitHub recusar o novo envio, o histórico "
                "local anterior será restaurado."
            ),
            parent=self,
        ):
            return

        self._terminal.aviso(
            "Recriando o histórico local e tentando publicar um commit limpo..."
        )
        self._bloquear_botoes(True)
        log.info(
            _ARQ,
            "_ao_reiniciar_historico_e_reenviar",
            f"reinicializando Git em {self._caminho}",
        )

        def _reiniciar():
            return self._git.reiniciar_historico_e_enviar(
                self._caminho, token
            )

        def _concluido(r):
            self._bloquear_botoes(False)
            if r.ok:
                self._terminal.ok("Histórico limpo e envio concluído.")
                if r.saida.startswith("O envio foi concluído, mas"):
                    self._terminal.aviso(r.saida)
                else:
                    self._terminal.info(r.saida or (
                        "Os arquivos do projeto foram mantidos; o histórico agora começa "
                        "no novo commit."
                    ))
                self.push_realizado.emit()
                self._atualizar_info()
                self._atualizar_aba_atual()
                log.ok(
                    _ARQ,
                    "_ao_reiniciar_historico_e_reenviar",
                    "histórico reiniciado e enviado",
                )
                return

            erro = r.erro or "O Git não retornou detalhes do erro."
            self._terminal.erro(
                "Não foi possível limpar o histórico e publicar o novo commit."
            )
            if _push_bloqueado_por_segredo(erro):
                locais = _locais_segredos_detectados(erro)
                resumo_locais = (
                    "\n\nArquivos/linhas ainda sinalizados:\n"
                    + "\n".join(f"• {local}" for local in locais)
                    if locais else ""
                )
                mensagem = (
                    "O GitHub ainda encontrou credenciais nos arquivos que seriam "
                    "enviados. O histórico local anterior foi restaurado e o envio "
                    "não foi concluído.\n\n"
                    "Revogue e gere novamente as credenciais, confira os caminhos "
                    "sinalizados e verifique se as regras do .gitignore correspondem "
                    "ao caminho completo."
                    f"{resumo_locais}"
                )
            else:
                mensagem = (
                    "A IDE não concluiu a operação. O histórico local anterior foi "
                    "restaurado.\n\nDetalhe:\n"
                    + erro
                )
            HeinPopup.escolher(
                "Não foi possível concluir",
                mensagem,
                opcoes=["Fechar"],
                parent=self,
            )
            log.erro(
                _ARQ,
                "_ao_reiniciar_historico_e_reenviar",
                "reinicialização/envio falhou",
                erro,
            )

        p = _em_thread(_reiniciar, _concluido, self)
        self._pontes.append(p)

    def _ao_forcar_envio(self):
        if not self._caminho:
            return

        token = config_github().token
        if not token:
            self._terminal.erro("Erro: não há sessão ativa")
            return

        if not HeinPopup.confirmar(
            "Forçar envio",
            "Enviar descartando as alterações que estão no GitHub?",
            informativo="O que está no GitHub será substituído pelo que está aqui. Não tem volta.",
            parent=self,
        ):
            return

        self._terminal.info("Forçando envio para o GitHub...")
        self._bloquear_botoes(True)
        log.info(_ARQ, "_ao_forcar_envio", f"force-push de {self._caminho}")

        def _forcar():
            return self._git.enviar_forcado(self._caminho, token)

        def _concluido(r):
            self._bloquear_botoes(False)
            if r.ok:
                self._terminal.ok("Envio forçado concluído")
                log.ok(_ARQ, "_ao_forcar_envio", "force-push concluído")
                self.push_realizado.emit()
            else:
                if _push_bloqueado_por_segredo(r.erro):
                    mensagem = (
                        "O envio forçado também foi bloqueado pela proteção contra "
                        "segredos do GitHub (GH013). Force-push só altera a relação "
                        "entre os históricos local e remoto; não ignora regras de "
                        "segurança.\n\n"
                        "Revogue e gere novamente as credenciais expostas. Depois, "
                        "remova-as dos arquivos e de todos os commits locais que "
                        "serão enviados. O .gitignore não limpa commits existentes."
                    )
                    self._terminal.erro(
                        "Envio forçado bloqueado por proteção de segredos (GH013)."
                    )
                else:
                    mensagem = (
                        "O envio forçado falhou.\n\n"
                        f"Detalhe:\n{r.erro}\n\n"
                        "O force-push não contorna regras de proteção do GitHub."
                    )
                    self._terminal.erro(f"Falha no envio forçado: {r.erro}")
                HeinPopup.escolher(
                    "O GitHub recusou o envio",
                    mensagem,
                    opcoes=["Fechar"],
                    parent=self,
                )
                log.erro(_ARQ, "_ao_forcar_envio", "force-push falhou", r.erro)

        p = _em_thread(_forcar, _concluido, self)
        self._pontes.append(p)

    def _ao_baixar_e_reenviar(self):
        if not self._caminho:
            return

        token = config_github().token
        if not token:
            self._terminal.erro("Erro: não há sessão ativa")
            return

        self._terminal.info("Baixando do GitHub e reenviando...")
        self._bloquear_botoes(True)
        log.info(_ARQ, "_ao_baixar_e_reenviar", f"pull+push de {self._caminho}")

        def _executar():
            return self._git.baixar_e_reenviar(self._caminho, token)

        def _concluido(r):
            self._bloquear_botoes(False)
            if r.ok:
                self._terminal.ok("Baixado e reenviado com sucesso")
                log.ok(_ARQ, "_ao_baixar_e_reenviar", "pull+push concluído")
                self.push_realizado.emit()
                self._atualizar_info()
                self._atualizar_aba_atual()
            else:
                mensagem = (
                    f"Falha ao baixar e reenviar: {r.erro}\n"
                    "Se houver conflito, resolva os arquivos marcados e tente novamente."
                )
                self._terminal.erro(mensagem)
                _popup_falha_git(
                    self, "Não foi possível baixar e reenviar", mensagem
                )
                log.erro(_ARQ, "_ao_baixar_e_reenviar", "pull+push falhou", r.erro)

        p = _em_thread(_executar, _concluido, self)
        self._pontes.append(p)

    def _ao_atualizar(self):
        if not self._caminho:

            return

        token = config_github().token
        if not token:
            self._terminal.erro("Erro: não há sessão ativa para baixar do GitHub")
            return

        if not HeinPopup.confirmar(
            "Baixar do GitHub",
            "Baixar alterações do repositório remoto?",
            informativo="Salve no Git antes para não perder alterações locais.",
            parent=self,
        ):
            return

        self._terminal.info("Verificando atualizações...")
        self._bloquear_botoes(True)
        log.info(_ARQ, "_ao_atualizar", f"pull em {self._caminho}")

        def _atualizar():
            return self._git.atualizar_projeto(self._caminho, token)

        def _concluido(r):
            self._bloquear_botoes(False)
            if r.ok:
                if "Already up to date" in r.saida or "up to date" in r.saida.lower():
                    self._terminal.info("Projeto já está atualizado")
                else:
                    self._terminal.ok("Projeto atualizado")
                self._atualizar_info()
                self._atualizar_aba_atual()
                log.ok(_ARQ, "_ao_atualizar", "pull concluído")
            else:
                mensagem = f"Falha ao baixar do GitHub:\n{r.erro}"
                self._terminal.erro(mensagem)
                _popup_falha_git(self, "Não foi possível baixar", mensagem)
                log.erro(_ARQ, "_ao_atualizar", "pull falhou", r.erro)

        p = _em_thread(_atualizar, _concluido, self)
        self._pontes.append(p)

    def _ao_historico(self):
        if not self._caminho:

            return

        self._terminal.info("Carregando histórico...")
        self._bloquear_botoes(True)
        log.info(_ARQ, "_ao_historico", f"historico de {self._caminho}")

        def _buscar():
            return self._git.historico(self._caminho, limite=30)

        def _exibir(versoes):
            self._bloquear_botoes(False)
            if versoes is None:
                self._terminal.erro("Erro ao carregar histórico")
                log.erro(_ARQ, "_ao_historico", "historico() retornou None")
                return
            self._terminal.info(f"{len(versoes)} versão(ões) encontrada(s)")
            lay = self._painel_historico_inline.layout()
            while lay.count():
                item = lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            painel = _PainelHistoricoVersoes(
                versoes,
                cb_restaurar=self._restaurar,
                cb_apagar=self._apagar_versao,
                parent=self._painel_historico_inline,
            )
            lay.addWidget(painel, 1)

        p = _em_thread(_buscar, _exibir, self)
        self._pontes.append(p)

    def _restaurar(self, versao: dict):
        hash_v = versao.get("hash_completo", "")
        hash_c = versao.get("hash_curto", "")
        msg_v  = versao.get("mensagem", "")

        if not HeinPopup.confirmar(
            "Restaurar versão",
            f"Restaurar para: <b>{msg_v}</b> ({hash_c})?",
            informativo="Alterações não salvas serão perdidas.",
            parent=self,
        ):
            return

        self._terminal.info(f"Restaurando versão {hash_c}...")
        self._bloquear_botoes(True)
        log.info(_ARQ, "_restaurar", f"checkout {hash_v}")

        def _restaurar():
            return self._git.restaurar_versao(self._caminho, hash_v)

        def _concluido(r):
            self._bloquear_botoes(False)
            if r.ok:
                self._terminal.ok("Arquivos restaurados")
                self._atualizar_info()
                self._atualizar_aba_atual()
                log.ok(_ARQ, "_restaurar", "restauração concluída")
            else:
                mensagem = f"Falha ao restaurar a versão {hash_c}:\n{r.erro}"
                self._terminal.erro(mensagem)
                _popup_falha_git(self, "Não foi possível restaurar", mensagem)
                log.erro(_ARQ, "_restaurar", "restauração falhou", r.erro)

        p = _em_thread(_restaurar, _concluido, self)
        self._pontes.append(p)

    def _apagar_versao(self, versao: dict, painel_ref=None):
        """
        Remove um commit do histórico local e, se token ativo, do GitHub também.
        Usa git reset --mixed (HEAD) ou git rebase --onto (commits anteriores).
        """
        hash_c = versao.get("hash_curto", "")
        hash_v = versao.get("hash_completo", "")
        msg_v  = versao.get("mensagem", "")

        if not HeinPopup.confirmar(
            "⚠  Apagar versão do histórico Git",
            f"Apagar permanentemente o commit <b>{msg_v}</b> ({hash_c})?",
            informativo=(
                "Esta ação reescreve o histórico Git e não pode ser desfeita facilmente.\n"
                "Se houver token ativo, o GitHub também será atualizado com force-push."
            ),
            parent=self,
        ):
            return

        token = config_github().token
        self._terminal.aviso(f"Apagando versão {hash_c} do histórico...")
        self._bloquear_botoes(True)
        log.info(_ARQ, "_apagar_versao", f"apagando {hash_v} em {self._caminho}")

        def _apagar():
            return self._git.apagar_versao(self._caminho, hash_v, token)

        def _concluido(r):
            self._bloquear_botoes(False)
            if r.ok:
                self._terminal.ok(f"Versão {hash_c} removida do histórico")
                if r.saida:
                    self._terminal.aviso(r.saida)
                self._atualizar_info()
                self._atualizar_aba_atual()
                log.ok(_ARQ, "_apagar_versao", f"{hash_c} removido")
                self._ao_historico()
            else:
                erro = r.erro or "O Git não retornou detalhes."
                if "head~1" in erro.casefold() or "does not point to a valid commit" in erro.casefold():
                    mensagem = (
                        "Este commit está na raiz do histórico; não existe um commit "
                        "anterior que o painel possa usar como base. Você pode apagar "
                        "todo o histórico Git local e publicar um commit novo, mantendo "
                        "os arquivos do projeto."
                    )
                    resp = HeinPopup.escolher(
                        "Não existe versão anterior",
                        mensagem,
                        opcoes=[
                            "Limpar todo o histórico e reenviar",
                            "Cancelar",
                        ],
                        parent=self,
                    )
                    if resp == 0:
                        self._ao_reiniciar_historico_e_reenviar()
                else:
                    mensagem = f"Falha ao apagar a versão {hash_c}:\n{erro}"
                    self._terminal.erro(mensagem)
                    _popup_falha_git(self, "Não foi possível apagar a versão", mensagem)
                log.erro(_ARQ, "_apagar_versao", r.erro)

        p = _em_thread(_apagar, _concluido, self)
        self._pontes.append(p)

    def _ao_fechar_projeto(self):
        if not HeinPopup.confirmar("Fechar projeto", "Fechar o projeto atual?", parent=self):
            return
        self._caminho = ""
        self._lbl_projeto.setText("")
        self._lbl_info.setText("")
        self._terminal.info("Projeto fechado")
        log.info(_ARQ, "_ao_fechar_projeto", "projeto fechado")
        if self._cb_fechar_projeto:
            self._cb_fechar_projeto()
