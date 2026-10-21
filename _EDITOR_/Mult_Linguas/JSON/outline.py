# _EDITOR_/Mult_Linguas/JSON/outline.py
"""
Funções de análise de outline para JSON.
Extraídas de _EDITOR_/Outline/painel_outline.py na Fase 2.
"""
import json
import re


def analisar_json(codigo: str) -> list:
    """Analisa JSON e retorna lista de itens para _popular_arvore_dict()."""
    try:
        return _json_para_itens(json.loads(codigo))
    except json.JSONDecodeError:
        return _analisar_json_regex(codigo)


def _json_para_itens(dados, nome: str = "raiz") -> list:
    itens = []
    if isinstance(dados, dict):
        pai = {"tipo": "objeto", "nome": nome, "linha": 1, "filhos": []}
        for chave, valor in dados.items():
            if isinstance(valor, (dict, list)):
                pai["filhos"].extend(_json_para_itens(valor, chave))
            else:
                pai["filhos"].append({
                    "tipo": "chave",
                    "nome": chave,
                    "valor": repr(valor)[:30],
                    "linha": 1,
                })
        itens.append(pai)
    elif isinstance(dados, list):
        for i, item in enumerate(dados[:50]):
            if isinstance(item, (dict, list)):
                itens.extend(_json_para_itens(item, f"[{i}]"))
            else:
                itens.append({
                    "tipo": "item",
                    "nome": f"[{i}]",
                    "valor": repr(item)[:50],
                    "linha": 1,
                })
    return itens


def _analisar_json_regex(codigo: str) -> list:
    """Fallback por regex quando o JSON é inválido."""
    itens = []
    for i, linha in enumerate(codigo.splitlines(), 1):
        m = re.search(r'"(\w+)":', linha)
        if m:
            itens.append({
                "tipo": "chave",
                "nome": m.group(1),
                "valor": linha.strip(),
                "linha": i,
            })
    return itens
