# 📁 _PAINEL_ESQUERDO_/Git/git_api.py

"""
Comunicação com a API REST do GitHub v3.
Apenas stdlib — sem dependências externas.
"""
import json
import urllib.request
import urllib.parse
import urllib.error
from _LOG_.log import log
_ARQ = "git_api.py"
from .git_config import config_github
_BASE = "https://api.github.com"

class GitHubAPI:
    def __init__(self):
        self.ultimo_status_http: int | None = None

    def _headers(self) -> dict:
        return {

            "Authorization":        f"token {config_github().token}",
            "Accept":               "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type":         "application/json",
        }

    def _get(self, endpoint: str) -> dict | list | None:
        try:
            req = urllib.request.Request(
                f"{_BASE}{endpoint}", headers=self._headers()
            )
            with urllib.request.urlopen(req, timeout=15) as resp:

                return json.loads(resp.read())

        except urllib.error.HTTPError as e:
            log.erro(_ARQ, "_get", f"GET {endpoint} → {e.code}")

            return None

        except Exception as e:
            log.erro(_ARQ, "_get", f"Erro: {e}")

            return None

    def _post(self, endpoint: str, corpo: dict) -> dict | None:
        try:
            req = urllib.request.Request(
                f"{_BASE}{endpoint}",
                data=json.dumps(corpo).encode(),
                headers=self._headers(),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:

                return json.loads(resp.read())

        except urllib.error.HTTPError as e:
            log.erro(_ARQ, "_post", f"POST {endpoint} → {e.code}")

            return None

        except Exception as e:
            log.erro(_ARQ, "_post", f"Erro: {e}")

            return None

    def _delete(self, endpoint: str) -> bool:
        """Executa uma exclusão na API e retorna apenas sucesso/falha."""
        self.ultimo_status_http = None
        try:
            req = urllib.request.Request(
                f"{_BASE}{endpoint}", headers=self._headers(), method="DELETE"
            )
            with urllib.request.urlopen(req, timeout=15):
                return True

        except urllib.error.HTTPError as e:
            self.ultimo_status_http = e.code
            log.erro(_ARQ, "_delete", f"DELETE {endpoint} → {e.code}")
            return False

        except Exception as e:
            log.erro(_ARQ, "_delete", f"Erro: {e}")
            return False

    # ------------------------------------------------------------------

    def buscar_usuario(self) -> dict | None:
        return self._get("/user")

    def criar_repositorio( self, nome: str, descricao: str = "", privado: bool = False ) -> dict | None:
        """Retorna dict com clone_url e html_url, ou None se falhar."""
        nome = nome.strip().replace(" ", "-")

        return self._post("/user/repos", {

            "name":        nome,
            "description": descricao,
            "private":     privado,
            "auto_init":   False,
        })

    def listar_repositorios(self) -> list[dict]:
        dados = self._get("/user/repos?per_page=50&sort=updated")

        return dados if isinstance(dados, list) else []

    def repositorio_existe(self, login: str, nome: str) -> bool:
        return self._get(f"/repos/{login}/{nome}") is not None

    def deletar_repositorio(self, login: str, nome: str) -> bool:
        """Apaga um repositório remoto do GitHub após confirmação da UI."""
        login = urllib.parse.quote(login.strip(), safe="")
        nome = urllib.parse.quote(nome.strip(), safe="")
        if not login or not nome:
            return False
        return self._delete(f"/repos/{login}/{nome}")
