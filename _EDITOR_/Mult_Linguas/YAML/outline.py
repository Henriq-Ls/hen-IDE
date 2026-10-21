# _EDITOR_/Mult_Linguas/YAML/outline.py
"""
Funções de análise de outline para YAML.
Extraídas de _EDITOR_/Outline/painel_outline.py na Fase 2.
"""
import re


def analisar_yaml(codigo: str) -> list:
    """Analisa YAML e retorna lista de itens para _popular_arvore_dict()."""
    itens = []
    for i, linha in enumerate(codigo.splitlines(), 1):
        m = re.match(r"^(\w+):", linha)
        if m:
            itens.append({
                "tipo": "chave",
                "nome": m.group(1),
                "valor": linha.strip(),
                "linha": i,
            })
        elif linha.strip().startswith("-"):
            itens.append({
                "tipo": "item",
                "nome": linha.strip()[:30],
                "valor": "",
                "linha": i,
            })
    return itens
