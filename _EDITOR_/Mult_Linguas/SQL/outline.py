# _EDITOR_/Mult_Linguas/SQL/outline.py
"""
Outline para SQL — regex-based.
Detecta: CREATE TABLE, CREATE VIEW, CREATE INDEX, CREATE PROCEDURE/FUNCTION/TRIGGER,
         CTEs (WITH nome AS), comentários de seção (-- ── Título).
Retorna lista de dicts compatíveis com _popular_arvore_dict().
"""
import re

_FLAGS = re.IGNORECASE

_RE_TABLE     = re.compile(r'^\s*CREATE\s+(?:TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`"\[]?[\w.]+[`"\]]?)', _FLAGS)
_RE_VIEW      = re.compile(r'^\s*CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+([`"\[]?[\w.]+[`"\]]?)', _FLAGS)
_RE_INDEX     = re.compile(r'^\s*CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?([`"\[]?[\w.]+[`"\]]?)', _FLAGS)
_RE_PROC      = re.compile(r'^\s*CREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+([`"\[]?[\w.]+[`"\]]?)', _FLAGS)
_RE_FUNC      = re.compile(r'^\s*CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+([`"\[]?[\w.]+[`"\]]?)', _FLAGS)
_RE_TRIGGER   = re.compile(r'^\s*CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+([`"\[]?[\w.]+[`"\]]?)', _FLAGS)
_RE_CTE       = re.compile(r'^\s*([a-zA-Z_][\w]*)\s+AS\s*\(', _FLAGS)
_RE_WITH      = re.compile(r'^\s*WITH\s+([a-zA-Z_][\w]*)\s+AS\s*\(', _FLAGS)
_RE_SECAO     = re.compile(r'^\s*--+\s*[─━─══─]+\s*(.*?)\s*[─━─══─]*\s*$')


def analisar_sql(codigo: str) -> list:
    """Analisa SQL e retorna estruturas para o outline."""
    linhas = codigo.splitlines()
    itens  = []

    tabelas   = {"tipo": "objeto", "nome": "Tabelas",     "linha": 1, "filhos": []}
    views     = {"tipo": "objeto", "nome": "Views",       "linha": 1, "filhos": []}
    procs     = {"tipo": "objeto", "nome": "Procedures",  "linha": 1, "filhos": []}
    funcs     = {"tipo": "objeto", "nome": "Funções",     "linha": 1, "filhos": []}
    outros    = {"tipo": "objeto", "nome": "Outros",      "linha": 1, "filhos": []}

    for n, linha in enumerate(linhas, 1):
        m = _RE_TABLE.match(linha)
        if m:
            tabelas["filhos"].append({"tipo": "chave", "nome": m.group(1), "linha": n})
            continue

        m = _RE_VIEW.match(linha)
        if m:
            views["filhos"].append({"tipo": "chave", "nome": m.group(1), "linha": n})
            continue

        m = _RE_PROC.match(linha)
        if m:
            procs["filhos"].append({"tipo": "funcao", "nome": f"{m.group(1)}()", "linha": n})
            continue

        m = _RE_FUNC.match(linha)
        if m:
            funcs["filhos"].append({"tipo": "funcao", "nome": f"{m.group(1)}()", "linha": n})
            continue

        m = _RE_INDEX.match(linha)
        if m:
            outros["filhos"].append({"tipo": "item", "nome": f"INDEX {m.group(1)}", "linha": n})
            continue

        m = _RE_TRIGGER.match(linha)
        if m:
            outros["filhos"].append({"tipo": "item", "nome": f"TRIGGER {m.group(1)}", "linha": n})
            continue

        m = _RE_WITH.match(linha)
        if m:
            outros["filhos"].append({"tipo": "item", "nome": f"CTE {m.group(1)}", "linha": n})
            continue

    # Só inclui grupos com itens
    for grupo in (tabelas, views, procs, funcs, outros):
        if grupo["filhos"]:
            itens.append(grupo)

    return itens
