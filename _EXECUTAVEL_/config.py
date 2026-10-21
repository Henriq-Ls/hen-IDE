"""Configuração do build guardada dentro de cada projeto."""
from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path

from _LOG_.log import log

_ARQ = "executavel.config"
_PADRAO = {
    "nome": "",
    "versao": "0.1.0",
    "icone": "",
    "ponto_entrada": "main.py",
    "modo": "executavel",
    "onefile": False,
    "console": False,
    "dependencias": [],
    "add_data": [],
    "hidden_imports": [],
    "collect_submodules": [],
    "collect_all": [],
    "requirements_extra": [],
    "arquivos_extra": [],
}


def obter_arquivo_config(caminho_projeto: str) -> str:
    return str(Path(caminho_projeto).resolve() / ".hein" / "executavel" / "executavel.json")


def _defaults(caminho_projeto: str) -> dict:
    dados = copy.deepcopy(_PADRAO)
    dados["nome"] = Path(caminho_projeto).resolve().name or "app"
    return dados


def ler_config_executavel_se_existir(caminho_projeto: str) -> dict:
    """Lê a configuração sem criar arquivos ao apenas abrir/trocar de projeto."""
    arquivo = Path(obter_arquivo_config(caminho_projeto))
    dados = _defaults(caminho_projeto)
    if not arquivo.is_file():
        return dados
    try:
        salvo = json.loads(arquivo.read_text(encoding="utf-8"))
        if isinstance(salvo, dict):
            dados.update(salvo)
    except (OSError, json.JSONDecodeError) as exc:
        log.erro(_ARQ, "ler_config_executavel_se_existir", str(exc))
    return dados


def ler_config_executavel(caminho_projeto: str) -> dict:
    return ler_config_executavel_se_existir(caminho_projeto)


def salvar_config_executavel(caminho_projeto: str, dados: dict) -> str:
    """Grava JSON atomicamente; caminhos de arquivos permanecem relativos ao projeto."""
    if not isinstance(dados, dict):
        raise TypeError("A configuração do executável deve ser um objeto.")
    arquivo = Path(obter_arquivo_config(caminho_projeto))
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(prefix=".executavel-", suffix=".json", dir=arquivo.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(dados, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporario, arquivo)
    except Exception:
        try:
            os.unlink(temporario)
        except OSError:
            pass
        raise
    log.ok(_ARQ, "salvar_config_executavel", f"Configuração salva em {arquivo}")
    return str(arquivo)


def salvar_campos_auto(caminho_projeto: str, campos: dict) -> dict:
    """Atualiza somente os campos calculados pela análise do projeto."""
    permitidos = {
        "dependencias", "add_data", "hidden_imports",
        "collect_submodules", "collect_all",
    }
    config = ler_config_executavel(caminho_projeto)
    config.update({chave: valor for chave, valor in campos.items() if chave in permitidos})
    salvar_config_executavel(caminho_projeto, config)
    return config
