# 📁 _PAINEL_ESQUERDO_/Git/git_autentica.py
"""
Autenticação GitHub via Device Flow.
Sem servidor de callback. Sem CLIENT_SECRET. Sem SSH. Sem token manual.
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
from .git_config import config_github
from _LOG_.log import log
_ARQ = "git_autentica.py"

_CLIENT_ID = "Ov23ligOtXutc2fHkw9W"
# ``delete_repo`` não é concedido pelo escopo ``repo``. Ele precisa ser
# solicitado explicitamente para a ação destrutiva de apagar um repositório.
_ESCOPO    = "repo,delete_repo,read:user,user:email"

_URL_DEVICE  = "https://github.com/login/device/code"
_URL_TOKEN   = "https://github.com/login/oauth/access_token"
_URL_USUARIO = "https://api.github.com/user"

def _post_form(url: str, dados: dict) -> dict:
    corpo = urllib.parse.urlencode(dados).encode()
    req = urllib.request.Request(
        url, data=corpo,
        headers={
            "Accept":       "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        log.info(_ARQ, "_post_form", f"Enviando POST para {url}", dados)
        with urllib.request.urlopen(req, timeout=15) as resp:
            resultado = json.loads(resp.read())
            log.ok(_ARQ, "_post_form", f"Resposta recebida de {url}", {
                "ok": "error" not in resultado,
                "error": resultado.get("error", ""),
            })

            return resultado

    except urllib.error.HTTPError as e:
        corpo_erro = e.read().decode(errors="ignore")
        log.erro(
            _ARQ,
            "_post_form",
            f"HTTP {e.code} em {url}",
            {"erro_http": e.code},
        )

        return {"error": f"http_{e.code}", "detalhe": "resposta HTTP não disponível"}

    except urllib.error.URLError as e:
        log.erro(_ARQ, "_post_form", f"Sem conexão: {url}", str(e.reason))

        return {"error": "sem_conexao", "detalhe": str(e.reason)}

    except Exception as e:
        log.excecao(_ARQ, "_post_form", f"Erro inesperado em {url}", str(e))

        return {"error": str(e)}

class GerenciadorAuth:
    def __init__(self):
        self._device_code : str  = ""
        self._intervalo   : int  = 5
        self._expiracao   : int  = 0
        self._cancelado   : bool = False

    # ──────────────────────────────────────────────────────────────────

    def solicitar_codigo_device(self) -> tuple[str, str] | None:
        self._cancelado = False
        log.info(_ARQ, "solicitar_codigo_device", "solicitando código ao GitHub",
                 {"client_id": _CLIENT_ID, "scope": _ESCOPO})

        resposta = _post_form(_URL_DEVICE, {
            "client_id": _CLIENT_ID,
            "scope":     _ESCOPO,
        })
        log.info(_ARQ, "solicitar_codigo_device", "resposta do GitHub", {
            "ok": "error" not in resposta,
            "error": resposta.get("error", ""),
        })

        if "error" in resposta:
            log.erro(
                _ARQ,
                "solicitar_codigo_device",
                "GitHub retornou erro",
                {"error": resposta.get("error", "")},
            )

            return None

        self._device_code = resposta.get("device_code", "")
        self._intervalo   = int(resposta.get("interval", 5))
        expires_in        = int(resposta.get("expires_in", 900))
        self._expiracao   = int(time.time()) + expires_in

        user_code        = resposta.get("user_code", "")
        verification_uri = resposta.get("verification_uri", "https://github.com/login/device")

        log.ok(_ARQ, "solicitar_codigo_device",
               f"código obtido: {user_code} | expira em {expires_in}s | url: {verification_uri}")

        return (user_code, verification_uri) if user_code else None

    # ──────────────────────────────────────────────────────────────────

    # ⚠️  função grande (74 linhas)
    def verificar_autenticacao(self) -> bool:
        if self._cancelado or not self._device_code:
            log.aviso(_ARQ, "verificar_autenticacao", "cancelado ou sem device_code")

            return False

        log.info(_ARQ, "verificar_autenticacao", "polling para verificar token", {
            "client_id": _CLIENT_ID,
            "device_code_presente": bool(self._device_code)
        })

        resposta = _post_form(_URL_TOKEN, {
            "client_id":   _CLIENT_ID,
            "device_code": self._device_code,
            "grant_type":  "urn:ietf:params:oauth:grant-type:device_code",
        })
        log.info(_ARQ, "verificar_autenticacao", "resposta do GitHub", {
            "ok": "error" not in resposta,
            "error": resposta.get("error", ""),
        })

        erro = resposta.get("error", "")

        if erro == "authorization_pending":
            log.info(_ARQ, "verificar_autenticacao", "aguardando usuário confirmar no site")

            return False

        if erro == "slow_down":
            self._intervalo += 5
            log.aviso(_ARQ, "verificar_autenticacao",
                      f"GitHub pediu para aguardar mais — novo intervalo: {self._intervalo}s")

            return False

        if erro == "expired_token":
            log.erro(_ARQ, "verificar_autenticacao", "código expirado")

            return False

        if erro == "access_denied":
            self._cancelado = True
            log.aviso(_ARQ, "verificar_autenticacao", "usuário negou acesso")

            return False

        token = resposta.get("access_token", "")
        if not token:
            log.erro(
                _ARQ,
                "verificar_autenticacao",
                "token não veio na resposta",
                {"error": resposta.get("error", "")},
            )

            return False

        log.ok(_ARQ, "verificar_autenticacao", "token recebido — buscando dados do usuário")

        usuario = self._buscar_usuario(token)
        if usuario:
            config = config_github()
            login = usuario.get("login", "")
            nome = usuario.get("name", "") or login
            config.registrar_sessao(token, login, nome)

            log.ok(
                _ARQ,
                "verificar_autenticacao",
                f"autenticado como @{config.login} ({config.nome})"
            )
            log.ok(_ARQ, "verificar_autenticacao", "retornando TRUE para a UI")

            return True

        else:
            log.aviso(_ARQ, "verificar_autenticacao",
                      "token salvo mas não conseguiu buscar dados do usuário")

        return True

    # ──────────────────────────────────────────────────────────────────

    def expirou(self) -> bool:
        comum = self._expiracao > 0 and int(time.time()) > self._expiracao
        if comum:
            log.aviso(_ARQ, "expirou", "autenticação expirada")

        return comum

    def cancelar(self):
        log.aviso(_ARQ, "cancelar", "autenticação cancelada pelo usuário")
        self._cancelado = True

    @property
    def intervalo_poll(self) -> int:
        return self._intervalo

    @staticmethod
    def _buscar_usuario(token: str) -> dict | None:
        try:
            log.info(_ARQ, "_buscar_usuario", "buscando dados do usuário no GitHub")
            req = urllib.request.Request(
                _URL_USUARIO,
                headers={
                    "Authorization": f"token {token}",
                    "Accept":        "application/vnd.github+json",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                dados = json.loads(resp.read())
                log.ok(_ARQ, "_buscar_usuario", "dados do usuário recebidos", {
                    "login": dados.get("login"),
                    "name": dados.get("name"),
                    "id": dados.get("id")
                })

                return dados

        except urllib.error.HTTPError as e:
            corpo_erro = e.read().decode(errors="ignore")
            log.erro(_ARQ, "_buscar_usuario", f"HTTP {e.code} ao buscar usuário", corpo_erro)

            return None

        except urllib.error.URLError as e:
            log.erro(_ARQ, "_buscar_usuario", f"Sem conexão ao buscar usuário", str(e.reason))

            return None

        except Exception as e:
            log.excecao(_ARQ, "_buscar_usuario", "falha ao buscar usuário", str(e))

            return None
