"""Publica arquivos e tag usando a autenticação segura já existente na aba Git."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from PySide6.QtCore import Signal
from _THREADS_.thread_segura import _ThreadSegura
from _LOG_.log import log

_ARQ = "executavel.processo_release"


class ProcessoReleaseThread(_ThreadSegura):
    linha = Signal(str)
    concluido = Signal(bool, str)

    def __init__(self, caminho_projeto: str, tag: str, arquivos: list[str], parent=None):
        super().__init__(parent)
        self._raiz = caminho_projeto
        self._tag = tag
        self._arquivos = list(dict.fromkeys(arquivos))

    def parar(self):
        self.requestInterruption()

    def _verificar_cancelamento(self):
        if self.isInterruptionRequested():
            raise RuntimeError("Publicação cancelada.")

    def _resultado(self, resultado, etapa: str):
        texto = (resultado.saida or resultado.erro or "").strip()
        if texto:
            self.linha.emit(texto)
        if not resultado.ok:
            raise RuntimeError(f"{etapa} falhou: {texto or 'Git retornou erro.'}")

    def run(self):
        try:
            from _PAINEL_ESQUERDO_.Git.git_config import config_github
            from _PAINEL_ESQUERDO_.Git.git_gerente import GerenciadorGit

            token = config_github().token
            if not token:
                raise RuntimeError(
                    "Entre no GitHub pela aba Git antes de publicar o release."
                )
            git = GerenciadorGit()
            if not git.tem_git(self._raiz):
                raise RuntimeError("O projeto não possui um repositório Git.")
            remoto = git._executar(["config", "--get", "remote.origin.url"], self._raiz)
            origem = (remoto.saida or "").strip()
            if not remoto.ok:
                raise RuntimeError("Não foi possível ler o remoto origin.")
            # Converte HTTPS ou SSH em uma URL limpa: o token nunca entra no
            # argumento do Git e credenciais continuam no helper temporário.
            url_sem_credencial = re.sub(r"^https://[^/@]+@", "https://", origem)
            partes = urlsplit(url_sem_credencial)
            if partes.hostname and partes.hostname.lower() == "github.com":
                repo_url = f"https://github.com{partes.path}"
            else:
                ssh = re.fullmatch(r"git@github\.com:(.+)", origem)
                if not ssh:
                    raise RuntimeError("O remoto origin não é um repositório do GitHub.")
                repo_url = f"https://github.com/{ssh.group(1)}"
            repo_url = repo_url.removesuffix(".git").rstrip("/") + ".git"
            if not repo_url.startswith("https://github.com/"):
                raise RuntimeError("O remoto origin não é um repositório do GitHub.")

            remoto_tag = git.executar_autenticado(
                ["ls-remote", "--tags", repo_url, f"refs/tags/{self._tag}"],
                self._raiz, token,
            )
            self._resultado(remoto_tag, "Consulta da tag remota")
            if remoto_tag.saida.strip():
                raise RuntimeError(
                    f"A tag {self._tag} já existe no GitHub. Ela não será sobrescrita."
                )

            local_tag = git._executar(["tag", "--list", self._tag], self._raiz)
            self._resultado(local_tag, "Consulta da tag local")
            ja_existe_local = bool(local_tag.saida.strip())
            if ja_existe_local:
                tag_commit = git._executar(
                    ["rev-parse", f"{self._tag}^{{commit}}"], self._raiz
                )
                head = git._executar(["rev-parse", "HEAD"], self._raiz)
                self._resultado(tag_commit, "Leitura da tag local")
                self._resultado(head, "Leitura do commit atual")
                arquivos_tag = git._executar(
                    ["ls-tree", "-r", "--name-only", self._tag, "--", *self._arquivos],
                    self._raiz,
                )
                self._resultado(arquivos_tag, "Verificação dos arquivos da tag")
                rastreados = {linha.strip() for linha in arquivos_tag.saida.splitlines() if linha.strip()}
                alteracoes = git._executar(
                    ["diff", "--name-only", self._tag, "--", *self._arquivos],
                    self._raiz,
                )
                self._resultado(alteracoes, "Verificação dos arquivos de release")
                ausentes = set(self._arquivos) - rastreados
                if (tag_commit.saida.strip() != head.saida.strip()
                        or alteracoes.saida.strip() or ausentes):
                    raise RuntimeError(
                        f"A tag local {self._tag} não representa os arquivos atuais. "
                        "Nenhum arquivo foi sobrescrito."
                    )
                self.linha.emit(
                    f"A tag local {self._tag} já aponta para o commit atual; retomando o envio."
                )
            else:
                self._verificar_cancelamento()
                self._resultado(
                    git._executar(["add", "-f", "--", *self._arquivos], self._raiz),
                    "Preparação dos arquivos",
                )
                diff = git._executar(
                    ["diff", "--cached", "--name-only", "--", *self._arquivos],
                    self._raiz,
                )
                self._resultado(diff, "Verificação dos arquivos preparados")
                if diff.saida.strip():
                    self._verificar_cancelamento()
                    self._resultado(
                        git._executar(
                            ["commit", "--only", "-m", f"release: {self._tag}",
                             "--", *self._arquivos],
                            self._raiz,
                        ),
                        "Commit dos arquivos de release",
                    )
                self._verificar_cancelamento()
                self._resultado(
                    git._executar(
                        ["tag", "-a", self._tag, "-m", f"Release {self._tag}"],
                        self._raiz,
                    ),
                    "Criação da tag",
                )

            branch = git.branch_atual(self._raiz) or "main"
            self._verificar_cancelamento()
            self.linha.emit(f"Enviando branch {branch}...")
            self._resultado(
                git.executar_autenticado(
                    ["push", "-u", repo_url, branch], self._raiz, token
                ),
                "Push da branch",
            )
            self._verificar_cancelamento()
            self.linha.emit(f"Enviando tag {self._tag}...")
            self._resultado(
                git.executar_autenticado(
                    ["push", repo_url, self._tag], self._raiz, token
                ),
                "Push da tag",
            )
            self.concluido.emit(True, f"Release {self._tag} enviado. O GitHub Actions iniciará o build.")
        except Exception as exc:
            log.erro(_ARQ, "run", str(exc))
            self.concluido.emit(False, str(exc))
