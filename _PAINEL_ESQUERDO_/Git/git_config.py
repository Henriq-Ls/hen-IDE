# 📁 _PAINEL_ESQUERDO_/Git/git_config.py

"""
Salva token, usuário e projetos recentes em JSON local.
"""
import json
import os
from _LOG_.log import log
_ARQ = "git_config.py"
from pathlib import Path
_PASTA   = Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "hein"
_ARQUIVO = _PASTA / "github_config.json"

_PADRAO = {
    "token": "",
    "login": "",
    "nome":  "",
    "contas": [],
    "conta_ativa": "",
    "projetos_recentes": [],
}

class ConfiguracaoGitHub:
    def __init__(self):
        self._dados: dict = {}
        self.carregar()

    def carregar(self):
        try:
            if _ARQUIVO.exists():
                with open(_ARQUIVO, "r", encoding="utf-8") as f:
                    self._dados = json.load(f)
            else:
                self._dados = dict(_PADRAO)
            self._migrar_conta_legada()
        except Exception:
            self._dados = dict(_PADRAO)

    def _migrar_conta_legada(self):
        """Converte a sessão antiga de uma conta para a lista de contas."""
        contas = self._dados.get("contas", [])
        if not isinstance(contas, list):
            contas = []

        login = self._dados.get("login", "")
        token = self._dados.get("token", "")
        nome = self._dados.get("nome", "") or login
        if login and token and not any(c.get("login") == login for c in contas):
            contas.append({"login": login, "nome": nome, "token": token})

        self._dados["contas"] = contas
        ativa = self._dados.get("conta_ativa", "") or login
        self._dados["conta_ativa"] = ativa
        if ativa:
            self._carregar_conta(ativa, salvar=False)

    def _carregar_conta(self, login: str, salvar: bool = True) -> bool:
        for conta in self._dados.get("contas", []):
            if conta.get("login") == login:
                self._dados["token"] = conta.get("token", "")
                self._dados["login"] = conta.get("login", "")
                self._dados["nome"] = conta.get("nome", "") or conta.get("login", "")
                self._dados["conta_ativa"] = conta.get("login", "")
                if salvar:
                    self.salvar()
                return True
        return False

    def salvar(self):
        try:
            _PASTA.mkdir(parents=True, exist_ok=True)
            with open(_ARQUIVO, "w", encoding="utf-8") as f:
                json.dump(self._dados, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.erro(_ARQ, "salvar", f"Erro ao salvar config: {e}")

    def get(self, chave: str, padrao=None):
        return self._dados.get(chave, padrao)

    def set(self, chave: str, valor):
        self._dados[chave] = valor
        self.salvar()

    @property
    def token(self) -> str:
        return self._dados.get("token", "")

    @token.setter
    def token(self, v: str):
        self._dados["token"] = v
        self.salvar()

    @property
    def login(self) -> str:
        return self._dados.get("login", "")

    @login.setter
    def login(self, v: str):
        self._dados["login"] = v
        self.salvar()

    @property
    def nome(self) -> str:
        return self._dados.get("nome", "")

    @nome.setter
    def nome(self, v: str):
        self._dados["nome"] = v
        self.salvar()

    def esta_logado(self) -> bool:
        return bool(self.token and self.login)

    def limpar_sessao(self):
        self._dados.update({"token": "", "login": "", "nome": "", "conta_ativa": ""})
        self.salvar()

    def registrar_sessao(self, token: str, login: str, nome: str):
        """Salva ou atualiza uma conta sem apagar as outras."""
        contas = self._dados.setdefault("contas", [])
        contas = [c for c in contas if c.get("login") != login]
        contas.insert(0, {"token": token, "login": login, "nome": nome or login})
        self._dados["contas"] = contas
        self._dados.update({
            "token": token,
            "login": login,
            "nome": nome or login,
            "conta_ativa": login,
        })
        self.salvar()

    def contas(self) -> list[dict]:
        """Retorna contas salvas sem expor tokens para a interface."""
        return [
            {"login": c.get("login", ""), "nome": c.get("nome", "")}
            for c in self._dados.get("contas", [])
            if c.get("login")
        ]

    def ativar_conta(self, login: str) -> bool:
        return self._carregar_conta(login)

    def adicionar_projeto_recente(self, nome: str, caminho: str, url: str):
        lst = self._dados.get("projetos_recentes", [])
        lst = [p for p in lst if p.get("caminho") != caminho]
        lst.insert(0, {
            "nome": nome,
            "caminho": caminho,
            "url": url,
            "conta": self.login,
        })
        self._dados["projetos_recentes"] = lst[:10]
        self.salvar()

    def projetos_recentes(self) -> list[dict]:
        return self._dados.get("projetos_recentes", [])

_inst: ConfiguracaoGitHub | None = None

def config_github() -> ConfiguracaoGitHub:
    global _inst
    if _inst is None:
        _inst = ConfiguracaoGitHub()

    return _inst
