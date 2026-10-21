# 📁 _PAINEL_ESQUERDO_/Git/git_terminal.py
"""
📁 _PAINEL_ESQUERDO_/Git/git_terminal.py
Terminal global do GitHub.
Compartilhado entre todas as telas do painel Git.
Nunca é limpo durante a sessão.
"""
from datetime import datetime
from PySide6.QtWidgets import QTextEdit
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import COR_INFO, COR_SEPARADOR, FONTE_MONO
from _TRADUTION_.tradutor_erros import traduzir
from _LOG_.log import log

_ARQ = "git_terminal.py"

class GitTerminal(QTextEdit):
    """
    Terminal de log do painel Git.
    Lê cores de painel_git.terminal_* no thema.json.
    Suporta hot-reload via atualizar_tema().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMinimumHeight(120)
        self.setMaximumHeight(160)
        self._aplicar_estilo()
        log.ok(_ARQ, "__init__", "GitTerminal pronto — tradução ativa via _TRADUTION_")

    # ──────────────────────────────────────────────────────────────
    # Tema
    # ──────────────────────────────────────────────────────────────

    def _c(self, chave: str, fallback: str) -> str:
        return tema_global().cor(f"painel_git.{chave}", fallback)

    def _aplicar_estilo(self):
        fundo = self._c("terminal_fundo", "#0b0f14")
        texto = self._c("terminal_texto", "#8fb3d9")
        borda = self._c("terminal_borda", "#222222")

        self.setStyleSheet(f"""
            QTextEdit {{
                background: {fundo};
                color: {texto};
                border: 1px solid {borda};
                border-top: 1px solid {borda};
                font-size: 10px;
                font-family: Consolas, monospace;
                padding: 4px 6px;
            }}
        """)

    def atualizar_tema(self, tema: dict = None):
        """Chamado pelo hot-reload do gerenciador_tema."""
        self._aplicar_estilo()

    # ──────────────────────────────────────────────────────────────
    # Escrita de mensagens
    # ──────────────────────────────────────────────────────────────

    def _escrever(self, icone: str, mensagem: str, cor: str = None):
        hora     = datetime.now().strftime("%H:%M")
        cor_hora = self._c("terminal_hora",  "#3d5a73")
        cor_txt  = cor or self._c("terminal_texto", "#8fb3d9")
        mensagem = traduzir(mensagem)
        self.append(
            f'<span style="color:{cor_hora};">{hora}</span> '
            f'<span style="color:{cor_txt};">{icone} {mensagem}</span>'
        )
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    # ──────────────────────────────────────────────────────────────
    # API de log
    # ──────────────────────────────────────────────────────────────

    def info(self, mensagem: str):
        self._escrever("ℹ", mensagem)

    def ok(self, mensagem: str):
        cor_ok = tema_global().cor("editor.sucesso", "#4ec994")
        self._escrever("✓", mensagem, cor_ok)

    def aviso(self, mensagem: str):
        cor_aviso = tema_global().cor("editor.aviso", "#e5c07b")
        self._escrever("⚠", mensagem, cor_aviso)

    def erro(self, mensagem: str):
        cor_erro = tema_global().cor("editor.erro", "#e06c75")
        self._escrever("✖", mensagem, cor_erro)

    def git(self, comando: str, resultado: str = ""):
        """Mostra um comando git executado — útil para debug."""
        cor_cmd = tema_global().cor("editor.info", COR_INFO)
        self._escrever("$", f"git {comando}", cor_cmd)
        if resultado:
            self._escrever(" ", resultado)

    def separador(self):
        """Linha divisória visual no terminal."""
        hora     = datetime.now().strftime("%H:%M")
        cor_hora = self._c("terminal_hora", "#3d5a73")
        cor_sep  = tema_global().cor("interface.borda", COR_SEPARADOR)
        self.append(
            f'<span style="color:{cor_hora};">{hora}</span> '
            f'<span style="color:{cor_sep};">────────────────</span>'
        )
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    # ──────────────────────────────────────────────────────────────
    # Mensagens de estado do painel Git
    # ──────────────────────────────────────────────────────────────

    def sistema_iniciado(self):
        self.info("GitHub iniciado")
        self.info("Aguardando login")

    def ja_logado(self, nome: str = ""):
        self.ok("Sessão ativa")
        if nome:
            self.ok(f"Conectado como @{nome}")

    def projeto_reconhecido(self, nome_projeto: str = ""):
        if nome_projeto:
            self.info(f"Projeto: {nome_projeto}")
        self.info("Clique em 'Criar Repositório' para publicar no GitHub")

    def sem_projeto(self):
        self.info("Nenhum projeto aberto")
        self.info("Crie ou abra um projeto para começar")

    def solicitando_codigo(self):
        self.info("Solicitando autorização...")

    def codigo_recebido(self, codigo: str):
        self.info(f"Código: {codigo}")
        self.info("Abra github.com/login/device")

    def aguardando_confirmacao(self):
        self.info("Aguardando confirmação...")

    def github_nao_confirmou(self):
        self.info("Ainda aguardando confirmação...")

    def github_pediu_espera(self):
        self.aviso("GitHub pediu para reduzir a frequência de consulta")

    def login_concluido(self, nome: str):
        self.ok("Login concluído")
        self.ok(f"Conectado como @{nome}")

    def codigo_expirado(self):
        self.erro("Código expirado — clique em Entrar novamente")

    def login_cancelado(self):
        self.aviso("Login cancelado")

    def git_nao_instalado(self):
        self.info("Git não encontrado")
        self.info("Instalando Git...")

    def git_instalado(self):
        self.ok("Git instalado com sucesso")

    def conta_conectada(self):
        self.ok("Conta conectada")
        self.info("Nenhum projeto aberto")

    def publicando_projeto(self):
        self.info("Publicando projeto no GitHub...")

    def projeto_publicado(self):
        self.ok("Projeto publicado no GitHub")
        self.ok("Agora você pode usar Push/Pull normalmente")

    def versao_incrementada(self, versao: str):
        self.ok(f"Versão atualizada para {versao}")

    def branch_trocada(self, nome: str):
        self.ok(f"Branch: {nome}")

    def stash_guardado(self):
        self.ok("Alterações guardadas no stash")
        self.info("Use 'Aplicar' na aba Stash para recuperar")

    def conflito_detectado(self):
        self.erro("Conflito detectado — resolva manualmente e faça commit")
