# 📁 _UTILITARIOS_/hein_pacotes_util.py
# -*- coding: utf-8 -*-
"""
Utilitário compartilhado para registrar/remover/listar pacotes instalados
pelo hein (via editor ou terminal). Escreve hein_packages.json na raiz
do projeto ativo — apenas os pacotes explicitamente instalados pelo usuário,
sem as dependências transitivas.
"""
import json
import os
from datetime import datetime
ARQUIVO_JSON = "hein_packages.json"

def _caminho(projeto: str) -> str:
    if not projeto:

        return ""

    return os.path.join(projeto, ARQUIVO_JSON)

# ⚠️  except genérico vazio
def registrar(projeto: str, modulo: str, versao: str = "") -> None:
    """Adiciona ou atualiza um pacote no hein_packages.json."""
    cam = _caminho(projeto)
    if not cam:

        return

    try:
        dados: dict = {}
        if os.path.exists(cam):
            with open(cam, "r", encoding="utf-8") as f:
                dados = json.load(f)
        dados[modulo] = {
            "versao":       versao,
            "instalado_em": datetime.now().isoformat(timespec="seconds"),
        }
        with open(cam, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ⚠️  except genérico vazio
def remover(projeto: str, modulo: str) -> None:
    """Remove um pacote do hein_packages.json."""
    cam = _caminho(projeto)
    if not cam or not os.path.exists(cam):

        return

    try:
        with open(cam, "r", encoding="utf-8") as f:
            dados = json.load(f)
        dados.pop(modulo, None)
        with open(cam, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def listar(projeto: str) -> dict:
    """Retorna dict {nome: {versao, instalado_em}} do hein_packages.json."""
    cam = _caminho(projeto)
    if not cam or not os.path.exists(cam):

        return {}

    try:
        with open(cam, "r", encoding="utf-8") as f:

            return json.load(f)

    except Exception:

        return {}

def extrair_nome_versao(token: str) -> tuple[str, str]:
    """
    'watchdog-3.0.0' → ('watchdog', '3.0.0')
    'requests'       → ('requests', '')
    """
    import re
    m = re.match(r'^([\w.\-]+?)-([\d][\w.]*)$', token)
    if m:

        return m.group(1), m.group(2)

    return token, ""
