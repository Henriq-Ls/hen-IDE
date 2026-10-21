# _EDITOR_/Mult_Linguas/XML/outline.py
"""
Funções de análise de outline para XML.
Extraídas de _EDITOR_/Outline/painel_outline.py na Fase 2.
"""
import re


def analisar_xml(codigo: str) -> list:
    """Analisa XML e retorna lista de itens para _popular_arvore_dict()."""
    itens = []
    for i, linha in enumerate(codigo.splitlines(), 1):
        m = re.match(r"^\s*<(\w+)", linha)
        if m and not re.match(r"^\s*</", linha):
            itens.append({"tipo": "tag", "nome": m.group(1), "linha": i})
    return itens
