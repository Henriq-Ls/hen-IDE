# _EDITOR_/Mult_Linguas/Lua/outline.py
"""
Outline para Lua — regex-based.
Detecta: funções globais, funções locais, métodos de tabela (Classe:metodo),
         módulos/tabelas top-level (local M = {}).
Retorna lista de dicts compatíveis com _popular_arvore_dict().
"""
import re

# function nome(  ou  function Modulo.nome(  ou  function Obj:metodo(
_RE_FUNC_GLOBAL = re.compile(
    r'^\s*function\s+(([a-zA-Z_]\w*)(?:[.:][\w]+)*)\s*\('
)
# local function nome(
_RE_FUNC_LOCAL  = re.compile(
    r'^\s*local\s+function\s+([a-zA-Z_]\w*)\s*\('
)
# Modulo.nome = function(  ou  Obj:metodo = function(
_RE_FUNC_ASSIGN = re.compile(
    r'^\s*([a-zA-Z_]\w*(?:[.:][\w]+)+)\s*=\s*function\s*\('
)
# local nome = function(
_RE_FUNC_LOCAL2 = re.compile(
    r'^\s*local\s+([a-zA-Z_]\w*)\s*=\s*function\s*\('
)
# Tabela top-level: local M = {} ou M = {}
_RE_TABLE = re.compile(
    r'^\s*(?:local\s+)?([A-Z][a-zA-Z_]\w*)\s*=\s*\{'
)


def analisar_lua(codigo: str) -> list:
    """Analisa Lua e retorna estrutura de funções para o outline."""
    linhas = codigo.splitlines()
    itens  = []
    modulos: dict[str, dict] = {}  # nome_modulo → item pai
    visto  = set()

    for n, linha in enumerate(linhas, 1):
        stripped = linha.strip()
        if not stripped or stripped.startswith('--'):
            continue

        # Tabela top-level (possível módulo)
        m = _RE_TABLE.match(linha)
        if m:
            nome = m.group(1)
            if nome not in visto:
                visto.add(nome)
                obj = {"tipo": "objeto", "nome": nome, "linha": n, "filhos": []}
                modulos[nome] = obj
                itens.append(obj)
            continue

        # function global
        m = _RE_FUNC_GLOBAL.match(linha)
        if m:
            nome_full = m.group(1)
            partes    = re.split(r'[.:]', nome_full)
            nome_base = partes[0]
            chave = f"{nome_full}:{n}"
            if chave not in visto:
                visto.add(chave)
                item = {"tipo": "funcao", "nome": f"{nome_full}()", "linha": n}
                if nome_base in modulos and len(partes) > 1:
                    modulos[nome_base]["filhos"].append(item)
                else:
                    itens.append(item)
            continue

        # local function
        m = _RE_FUNC_LOCAL.match(linha)
        if m:
            nome = m.group(1)
            chave = f"{nome}:{n}"
            if chave not in visto:
                visto.add(chave)
                itens.append({"tipo": "metodo", "nome": f"{nome}() [local]", "linha": n})
            continue

        # Modulo.func = function(
        m = _RE_FUNC_ASSIGN.match(linha)
        if m:
            nome_full = m.group(1)
            partes    = re.split(r'[.:]', nome_full)
            nome_base = partes[0]
            chave = f"{nome_full}:{n}"
            if chave not in visto:
                visto.add(chave)
                item = {"tipo": "metodo", "nome": f"{nome_full}()", "linha": n}
                if nome_base in modulos:
                    modulos[nome_base]["filhos"].append(item)
                else:
                    itens.append(item)
            continue

        # local nome = function(
        m = _RE_FUNC_LOCAL2.match(linha)
        if m:
            nome  = m.group(1)
            chave = f"{nome}:{n}"
            if chave not in visto:
                visto.add(chave)
                itens.append({"tipo": "metodo", "nome": f"{nome}() [local]", "linha": n})

    return itens
