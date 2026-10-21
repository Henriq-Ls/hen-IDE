# 📁 _PAINEL_ESQUERDO_/Git/git_gerente.py

"""
Detecta se Git está instalado, instala automaticamente se não estiver,
e executa todas as operações Git locais via subprocess.
Sem terminal visível para o usuário.
"""
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import tempfile
from urllib.parse import quote
from pathlib import Path
from dataclasses import dataclass
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console
@dataclass
class ResultadoGit:
    ok: bool
    saida: str
    erro: str

    def __bool__(self):
        return self.ok

class GerenciadorGit:
    """
    Executa operações Git locais de forma simples.
    Detecta e instala Git automaticamente se necessário.
    """

    # ------------------------------------------------------------------
    # Detecção e instalação do Git
    # ------------------------------------------------------------------

    @staticmethod
    def git_instalado() -> bool:
        import shutil
        try:
            # tenta pelo PATH normal
            resultado = subprocess.run(
                ["git", "--version"],
                capture_output=True, text=True, timeout=5,
                **opcoes_processo_sem_console(),
            )
            if resultado.returncode == 0:

                return True

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # fallback: caminhos comuns do Git no Windows
        caminhos = [
            r"C:\Program Files\Git\cmd\git.exe",
            r"C:\Program Files (x86)\Git\cmd\git.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Git\cmd\git.exe"),
        ]

        return any(os.path.exists(c) for c in caminhos)

    @staticmethod
    def versao_git() -> str:
        # BUG-202807-09b: capture_output=True cria reader thread (PIPE) que
        # dispara 0x8001010d no Windows. Usar TemporaryFile elimina o PIPE.
        try:
            with tempfile.TemporaryFile() as _f:
                subprocess.run(
                    ["git", "--version"],
                    stdout=_f,
                    stderr=subprocess.DEVNULL,
                    **opcoes_processo_sem_console(),
                )
                _f.seek(0)
                return _f.read().decode(errors="ignore").strip()

        except Exception:

            return ""

    @staticmethod
    def instalar_git_windows(callback_progresso=None) -> bool:
        """
        Baixa e instala o Git para Windows silenciosamente.
        callback_progresso(mensagem: str) é chamado durante o processo.
        """
        if callback_progresso:
            callback_progresso("Verificando versão mais recente do Git...")

        # URL do instalador oficial do Git para Windows (64-bit)
        url = "https://github.com/git-for-windows/git/releases/download/v2.45.2.windows.1/Git-2.45.2-64-bit.exe"

        try:
            with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp:
                caminho_instalador = tmp.name

            if callback_progresso:
                callback_progresso("Baixando Git (pode demorar alguns minutos)...")

            urllib.request.urlretrieve(url, caminho_instalador)

            if callback_progresso:
                callback_progresso("Instalando Git silenciosamente...")

            resultado = subprocess.run(
                [caminho_instalador, "/VERYSILENT", "/NORESTART", "/NOCANCEL"],
                capture_output=True, timeout=300,
                **opcoes_processo_sem_console(),
            )

            os.unlink(caminho_instalador)

            if resultado.returncode == 0:
                if callback_progresso:
                    callback_progresso("Git instalado com sucesso!")

                return True

            else:
                if callback_progresso:
                    callback_progresso("Falha na instalação do Git.")

                return False

        except Exception as e:
            if callback_progresso:
                callback_progresso(f"Erro: {e}")

            return False

    # ------------------------------------------------------------------
    # Configuração inicial do Git
    # ------------------------------------------------------------------

    @staticmethod
    def configurar_usuario(nome: str, email: str) -> bool:
        try:
            subprocess.run(["git", "config", "--global", "user.name", nome],
                           capture_output=True, **opcoes_processo_sem_console())
            subprocess.run(["git", "config", "--global", "user.email", email],
                           capture_output=True, **opcoes_processo_sem_console())

            return True

        except Exception:

            return False

    # ------------------------------------------------------------------
    # Operações Git locais
    # ------------------------------------------------------------------

    def _executar(self, args: list[str], pasta: str = None, env: dict = None) -> ResultadoGit:
        """Executa um comando git e retorna ResultadoGit."""
        try:
            ambiente = os.environ.copy()
            if env:
                ambiente.update(env)

            resultado = subprocess.run(
                [self._cmd_git()] + args,
                capture_output=True,
                encoding='utf-8',
                errors='replace',
                cwd=pasta or os.getcwd(),
                env=ambiente,
                timeout=60,
                **opcoes_processo_sem_console(),
            )
            ok = resultado.returncode == 0

            return ResultadoGit(

                ok=ok,
                saida=resultado.stdout.strip(),
                erro=resultado.stderr.strip(),
            )
        except subprocess.TimeoutExpired:

            return ResultadoGit(ok=False, saida="", erro="Operação demorou demais.")

        except Exception as e:

            return ResultadoGit(ok=False, saida="", erro=str(e))

    def _cmd_git(self) -> str:
        # BUG-202807-09b: capture_output=True cria reader thread (PIPE).
        # Não precisamos da saída aqui — DEVNULL evita o PIPE.
        try:
            subprocess.run(
                ["git", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                **opcoes_processo_sem_console(),
            )

            return "git"

        except FileNotFoundError:
            for c in [
                r"C:\Program Files\Git\cmd\git.exe",
                r"C:\Program Files (x86)\Git\cmd\git.exe",
            ]:
                if os.path.exists(c):

                    return c

            return "git"

    def inicializar(self, pasta: str) -> ResultadoGit:
        """Inicializa repositório Git na pasta."""
        r = self._executar(["init", "-b", "main"], pasta)
        if not r.ok:
            # Git antigo não tem -b, tenta sem
            r = self._executar(["init"], pasta)

        return r

    def reiniciar_historico_e_enviar(
        self, pasta: str, token: str
    ) -> "ResultadoGit":
        """Cria um histórico local novo, mantém os arquivos e substitui a branch remota.

        O `.git` antigo é guardado temporariamente para restauração caso qualquer
        etapa falhe. Só é removido definitivamente depois que o novo push conclui.
        `git add -A` respeita o `.gitignore` do projeto.
        """
        raiz = Path(pasta).resolve()
        git_dir = raiz / ".git"
        if not git_dir.is_dir():
            return ResultadoGit(
                ok=False, saida="",
                erro="Não foi possível reiniciar: o projeto não tem uma pasta .git válida.",
            )

        r_remote = self._executar(["remote", "get-url", "origin"], str(raiz))
        remoto = r_remote.saida.strip() if r_remote.ok else ""
        if not remoto:
            return ResultadoGit(
                ok=False, saida="",
                erro="Não foi possível reiniciar: o repositório não tem origin configurado.",
            )

        branch = self.branch_atual(str(raiz))
        r_branch = self._executar(["check-ref-format", "--branch", branch], str(raiz))
        if not r_branch.ok:
            return ResultadoGit(
                ok=False, saida="",
                erro="Não foi possível reiniciar: o nome da branch atual é inválido.",
            )

        # Preserve configurações locais do autor, que ficam dentro do .git.
        autor = self._executar(["config", "--get", "user.name"], str(raiz))
        email = self._executar(["config", "--get", "user.email"], str(raiz))

        backup_dir = Path(tempfile.mkdtemp(
            prefix=".hein_git_reset_", dir=str(raiz.parent)
        ))
        backup_git = backup_dir / ".git"

        def _restaurar_antigo() -> None:
            if git_dir.exists():
                if git_dir.is_dir():
                    shutil.rmtree(git_dir)
                else:
                    git_dir.unlink(missing_ok=True)
            if backup_git.exists():
                os.replace(backup_git, git_dir)

        try:
            os.replace(git_dir, backup_git)

            r_init = self._executar(
                ["init", "--initial-branch", branch], str(raiz)
            )
            if not r_init.ok:
                # Compatibilidade com versões antigas do Git.
                r_init = self._executar(["init"], str(raiz))
                if not r_init.ok:
                    _restaurar_antigo()
                    return r_init
                r_head = self._executar(
                    ["symbolic-ref", "HEAD", f"refs/heads/{branch}"], str(raiz)
                )
                if not r_head.ok:
                    _restaurar_antigo()
                    return r_head

            r_config = self._executar(
                ["remote", "add", "origin", remoto], str(raiz)
            )
            if not r_config.ok:
                _restaurar_antigo()
                return r_config

            if autor.ok and autor.saida:
                r_config = self._executar(
                    ["config", "user.name", autor.saida], str(raiz)
                )
                if not r_config.ok:
                    _restaurar_antigo()
                    return r_config
            if email.ok and email.saida:
                r_config = self._executar(
                    ["config", "user.email", email.saida], str(raiz)
                )
                if not r_config.ok:
                    _restaurar_antigo()
                    return r_config

            r_add = self._executar(["add", "-A"], str(raiz))
            if not r_add.ok:
                _restaurar_antigo()
                return r_add

            r_commit = self._executar(
                ["commit", "-m", "Início limpo do histórico"], str(raiz)
            )
            if not r_commit.ok:
                _restaurar_antigo()
                return r_commit

            r_push = self._executar_autenticado(
                ["push", "--force", "-u", "origin", branch],
                str(raiz),
                token,
            )
            if not r_push.ok:
                try:
                    _restaurar_antigo()
                except OSError as e:
                    return ResultadoGit(
                        ok=False,
                        saida="",
                        erro=(
                            f"{r_push.erro}\n\n"
                            "O envio falhou e a restauração automática do Git local "
                            f"também falhou. O histórico anterior continua guardado em: {backup_git}\n"
                            f"Detalhe da restauração: {e}"
                        ),
                    )
                return ResultadoGit(
                    ok=False,
                    saida="",
                    erro=(
                        f"{r_push.erro}\n\n"
                        "O histórico Git anterior foi restaurado localmente; "
                        "o GitHub não confirmou o novo envio."
                    ),
                )

            try:
                shutil.rmtree(backup_dir)
            except OSError as e:
                return ResultadoGit(
                    ok=True,
                    saida=(
                        "O envio foi concluído, mas o backup temporário do histórico "
                        f"local não pôde ser removido: {backup_dir}. Detalhe: {e}"
                    ),
                    erro="",
                )
            return ResultadoGit(
                ok=True,
                saida="Histórico local reiniciado e novo envio concluído.",
                erro="",
            )
        except Exception as e:
            if backup_git.exists():
                try:
                    _restaurar_antigo()
                except OSError as erro_restauracao:
                    return ResultadoGit(
                        ok=False,
                        saida="",
                        erro=(
                            f"Falha ao reiniciar o histórico Git: {e}\n"
                            "A restauração automática também falhou. O histórico "
                            f"anterior continua guardado em: {backup_git}\n"
                            f"Detalhe da restauração: {erro_restauracao}"
                        ),
                    )
            return ResultadoGit(
                ok=False, saida="",
                erro=f"Falha ao reiniciar o histórico Git: {e}",
            )
        finally:
            if backup_dir.exists() and not backup_git.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)

    def tem_git(self, pasta: str) -> bool:
        """Verifica se a pasta já tem Git inicializado."""

        return (Path(pasta) / ".git").exists()

    def definir_remoto(self, pasta: str, url: str, token: str = "") -> ResultadoGit:
        """Define o remoto com a URL original, sem incluir credenciais."""
        # Remove remoto antigo se existir
        self._executar(["remote", "remove", "origin"], pasta)

        return self._executar(
            ["remote", "add", "origin", url], pasta
        )

    def remover_remoto(self, pasta: str, nome: str = "origin") -> ResultadoGit:
        """Remove somente o vínculo remoto local; não apaga arquivos nem o Git."""
        return self._executar(["remote", "remove", nome], pasta)

    def arquivos_alterados(self, pasta: str) -> list[dict]:
        """
        Retorna lista de arquivos alterados com status simplificado.
        [{"caminho": "...", "status": "modificado"|"novo"|"deletado"}]
        """
        r = self._executar(["status", "--porcelain"], pasta)
        if not r.ok:

            return []

        arquivos = []
        mapa_status = {
            "M": "modificado", " M": "modificado",
            "A": "novo",       "??": "novo",
            "D": "deletado",   " D": "deletado",
            "R": "renomeado",  "C":  "copiado",
        }

        for linha in r.saida.splitlines():
            if not linha.strip():
                continue
            codigo = linha[:2].rstrip() or linha[:2]
            caminho = linha[3:].strip()
            status = mapa_status.get(codigo, "modificado")
            arquivos.append({"caminho": caminho, "status": status})

        return arquivos

    def salvar_versao(self, pasta: str, mensagem: str, arquivos: list[str] = None) -> ResultadoGit:
        """
        Equivalente a: git add [arquivos] + git commit -m mensagem
        Se arquivos=None, faz git add . (todos)
        """
        if not mensagem.strip():
            mensagem = "Versão salva pelo hein Editor"

        # git add
        if arquivos:
            for arq in arquivos:
                r = self._executar(["add", arq], pasta)
                if not r.ok:

                    return r

        else:
            r = self._executar(["add", "."], pasta)
            if not r.ok:

                return r

        # git commit

        return self._executar(["commit", "-m", mensagem], pasta)

    def enviar_para_github(self, pasta: str, token: str) -> ResultadoGit:
        """Envia usando helper temporário, sem token na URL ou nos argumentos."""
        branch = self.branch_atual(pasta)

        # Retry apenas em timeout de rede — não em rejeição (não alterar histórico)
        r = self._executar_autenticado(
            ["push", "-u", "origin", branch], pasta, token
        )
        for tentativa in range(2):
            if r.ok or "Operação demorou demais" not in r.erro:
                break
            time.sleep(1)
            r = self._executar_autenticado(
                ["push", "-u", "origin", branch], pasta, token
            )

        return r

    def enviar_forcado(self, pasta: str, token: str) -> ResultadoGit:
        """git push --force origin <branch_atual>.
        Usa --force (não --force-with-lease) porque o ref local pode estar
        desatualizado — o usuário já confirmou que quer sobrescrever o remoto.
        """
        branch = self.branch_atual(pasta)

        return self._executar_autenticado(
            ["push", "--force", "-u", "origin", branch],
            pasta, token,
        )

    def baixar_e_reenviar(self, pasta: str, token: str) -> ResultadoGit:
        """git pull --rebase origin <branch_atual> e depois push."""
        branch = self.branch_atual(pasta)

        r_pull = self._executar_autenticado(
            ["pull", "--rebase", "origin", branch], pasta, token
        )
        if not r_pull.ok:
            return r_pull

        return self._executar_autenticado(
            ["push", "-u", "origin", branch], pasta, token
        )

    def atualizar_projeto(self, pasta: str, token: str = "") -> ResultadoGit:
        """git pull origin <branch_atual> com a sessão ativa, quando houver."""
        branch = self.branch_atual(pasta)

        return self._executar_autenticado(
            ["pull", "origin", branch], pasta, token
        )

    def baixar_projeto(self, url: str, destino: str, token: str) -> ResultadoGit:
        """Clona preservando a URL original e usando helper temporário."""
        return self._executar_autenticado(
            ["clone", url, destino], None, token
        )

    def executar_autenticado(
        self,
        args: list[str],
        pasta: str | None,
        token: str,
    ) -> ResultadoGit:
        """Executa uma operação Git adicional sem expor a credencial.

        Consumidores internos que precisam de comandos não cobertos por um
        método específico (por exemplo, publicar uma tag) devem usar esta API
        em vez de montar URL/ambiente com token.
        """
        return self._executar_autenticado(args, pasta, token)

    def _executar_autenticado(
        self,
        args: list[str],
        pasta: str | None,
        token: str,
    ) -> ResultadoGit:
        """Executa Git com uma credencial temporária isolada por operação.

        O token fica somente no arquivo temporário do credential helper durante
        o processo filho. Ele não entra na URL, nos argumentos nem no remoto
        persistido em `.git/config`.
        """
        if not token:
            return self._executar(
                args,
                pasta,
                {"GIT_TERMINAL_PROMPT": "0"},
            )

        credencial_path = ""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix="hein_git_",
                suffix=".credentials",
                delete=False,
            ) as credencial:
                credencial.write(
                    "https://x-access-token:"
                    f"{quote(token, safe='')}@github.com\n"
                )
                credencial_path = credencial.name
            try:
                os.chmod(credencial_path, 0o600)
            except OSError:
                pass

            helper = f'credential.helper=store --file="{credencial_path}"'
            resultado = self._executar(
                ["-c", helper, *args],
                pasta,
                {"GIT_TERMINAL_PROMPT": "0"},
            )
            return ResultadoGit(
                ok=resultado.ok,
                saida=resultado.saida.replace(token, "[credencial omitida]"),
                erro=resultado.erro.replace(token, "[credencial omitida]"),
            )
        finally:
            if credencial_path:
                try:
                    os.unlink(credencial_path)
                except OSError:
                    pass

    def historico(self, pasta: str, limite: int = 20) -> list[dict]:
        """
        Retorna lista de versões salvas.
        [{"hash": ..., "mensagem": ..., "autor": ..., "data": ...}]
        """
        formato = "%H|%h|%s|%an|%ar"
        r = self._executar(
            ["log", f"--max-count={limite}", f"--format={formato}"],
            pasta
        )
        if not r.ok or not r.saida:

            return []

        versoes = []
        for linha in r.saida.splitlines():
            partes = linha.split("|", 4)
            if len(partes) == 5:
                versoes.append({
                    "hash_completo": partes[0],
                    "hash_curto":    partes[1],
                    "mensagem":      partes[2],
                    "autor":         partes[3],
                    "quando":        partes[4],  # ex: "3 hours ago"
                })

        return versoes

    def historico_arquivo(self, pasta: str, arquivo_relativo: str, limite: int = 50) -> list[dict]:
        """
        Retorna commits que tocaram um arquivo específico.
        Usa --name-only para capturar o caminho REAL do arquivo em cada
        commit (necessário quando o arquivo foi renomeado ou movido).
        """
        formato = "%H|%h|%s|%ar|%ad"
        r = self._executar(
            ["log", "--follow", f"--max-count={limite}",
             f"--format={formato}", "--date=format:%d/%m/%Y %H:%M",
             "--name-only",
             "--", arquivo_relativo],
            pasta,
        )
        if not r.ok or not r.saida.strip():
            return []

        versoes = []
        # --name-only intercala linhas de commit com linhas de filename:
        #   <hash40>|<hash_curto>|<mensagem>|<relativo>|<data>   ← linha de commit
        #   (linha em branco)
        #   <caminho/do/arquivo/naquele/commit>                   ← filename
        #   (linha em branco)
        #   <próximo commit...>
        # Parser linha a linha: identifica linha de commit pelo hash de 40 hex chars.
        commit_atual = None
        for linha in r.saida.splitlines():
            linha = linha.strip()
            if not linha:
                continue
            partes = linha.split("|", 4)
            if (len(partes) == 5
                    and len(partes[0]) == 40
                    and all(c in "0123456789abcdef" for c in partes[0])):
                # nova linha de commit — salva o anterior
                if commit_atual:
                    versoes.append(commit_atual)
                commit_atual = {
                    "hash_completo":     partes[0],
                    "hash_curto":        partes[1],
                    "mensagem":          partes[2],
                    "quando":            partes[4],
                    "caminho_no_commit": arquivo_relativo,  # padrão; sobrescrito abaixo
                }
            elif commit_atual:
                # primeira linha não-vazia após o commit = caminho do arquivo naquele momento
                commit_atual["caminho_no_commit"] = linha.replace("\\", "/")
        if commit_atual:
            versoes.append(commit_atual)
        return versoes

    def conteudo_arquivo_em(self, pasta: str, hash_completo: str, arquivo_relativo: str):
        """
        Retorna o conteúdo de um arquivo em um commit específico.
        Usa: git show <hash>:<arquivo_relativo>
        Retorna None em caso de falha.
        """
        r = self._executar(
            ["show", f"{hash_completo}:{arquivo_relativo}"],
            pasta,
        )
        if r.ok:
            return r.saida
        return None

    def restaurar_versao(self, pasta: str, hash_versao: str) -> ResultadoGit:
        """Restaura para uma versão anterior (git checkout <hash> .)"""

        return self._executar(["checkout", hash_versao, "--", "."], pasta)

    def tem_conflitos(self, pasta: str) -> bool:
        r = self._executar(["diff", "--name-only", "--diff-filter=U"], pasta)

        return bool(r.saida.strip())

    def branch_atual(self, pasta: str) -> str:
        r = self._executar(["branch", "--show-current"], pasta)

        return r.saida.strip() or "main"

    def limpar_cache_gitignore(self, pasta: str) -> ResultadoGit:
        """
        Remove do índice Git os arquivos rastreados que agora estão no .gitignore.
        Não apaga os arquivos físicos — só para o Git de rastreá-los.
        Após isso, o usuário deve fazer commit para registrar a remoção.
        """
        r = self._executar(["ls-files", "-i", "--exclude-standard"], pasta)
        if not r.ok:
            return ResultadoGit(ok=False, saida="", erro=r.erro)

        arquivos = [a for a in r.saida.strip().splitlines() if a.strip()]
        if not arquivos:
            return ResultadoGit(ok=True, saida="", erro="")

        return self._executar(["rm", "--cached", "-r", "--"] + arquivos, pasta)

    def apagar_versao(self, pasta: str, hash_versao: str, token: str = "") -> "ResultadoGit":
        """
        Remove um commit específico do histórico local.
        - Se for o commit mais recente (HEAD): usa git reset --mixed HEAD~1
          (arquivos voltam para não-staged, não são apagados do disco)
        - Se for um commit anterior: usa git rebase --onto para pular o commit
        Após remover localmente, se token fornecido faz force-push para GitHub.
        """
        # Descobre o HEAD atual
        r_head = self._executar(["rev-parse", "HEAD"], pasta)
        if not r_head.ok:
            return ResultadoGit(ok=False, saida="", erro="Não foi possível obter HEAD")

        head_hash = r_head.saida.strip()

        # Verifica se o commit a apagar é o HEAD
        eh_head = (
            head_hash == hash_versao
            or head_hash.startswith(hash_versao)
            or hash_versao.startswith(head_hash[:len(hash_versao)])
        )

        if eh_head:
            r = self._executar(["reset", "--mixed", "HEAD~1"], pasta)
        else:
            branch = self.branch_atual(pasta)
            # git rebase --onto <commit>^ <commit> — pula o commit alvo
            r = self._executar(
                ["rebase", "--onto", f"{hash_versao}^", hash_versao, branch],
                pasta,
            )
            if not r.ok:
                self._executar(["rebase", "--abort"], pasta)
                return ResultadoGit(
                    ok=False, saida="",
                    erro=f"Rebase falhou (possível conflito): {r.erro}",
                )

        if not r.ok:
            return r

        # Force-push se token fornecido
        if token:
            branch = self.branch_atual(pasta)
            r_push = self._executar_autenticado(
                ["push", "--force-with-lease", "origin", branch],
                pasta, token,
            )
            if not r_push.ok:
                return ResultadoGit(
                    ok=True,
                    saida=f"Commit removido localmente, mas falha ao atualizar GitHub: {r_push.erro}",
                    erro="",
                )

        return ResultadoGit(ok=True, saida="Versão removida com sucesso", erro="")
