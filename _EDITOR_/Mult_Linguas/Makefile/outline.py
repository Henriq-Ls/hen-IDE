# _EDITOR_/Mult_Linguas/Makefile/outline.py
"""
Outline para Makefile — lista todos os targets.
Separa: targets especiais .PHONY etc., targets de build (%.o), targets normais.
Retorna lista de dicts compatíveis com _popular_arvore_dict().
"""
import re

_RE_TARGET     = re.compile(r'^([^\t#\s][^:=\n]*):\s*(.*)$')
_RE_PHONY_DECL = re.compile(r'^\s*\.PHONY\s*:\s*(.+)')


def analisar_make(codigo: str) -> list:
    """Analisa Makefile e retorna targets para o outline."""
    linhas  = codigo.splitlines()
    itens   = []
    phonys  = set()

    # Primeiro passo: coletar .PHONY
    for linha in linhas:
        m = _RE_PHONY_DECL.match(linha)
        if m:
            for t in m.group(1).split():
                phonys.add(t.strip())

    # Segundo passo: coletar targets
    especiais  = {"tipo": "objeto", "nome": "Especiais",  "linha": 1, "filhos": []}
    phony_grp  = {"tipo": "objeto", "nome": "PHONY",      "linha": 1, "filhos": []}
    build_grp  = {"tipo": "objeto", "nome": "Build",      "linha": 1, "filhos": []}
    normal_grp = {"tipo": "objeto", "nome": "Targets",    "linha": 1, "filhos": []}

    visto = set()
    for n, linha in enumerate(linhas, 1):
        m = _RE_TARGET.match(linha)
        if not m:
            continue
        target = m.group(1).strip()
        if not target or target in visto:
            continue
        visto.add(target)

        item = {"tipo": "funcao", "nome": target, "linha": n}

        if target.startswith('.'):
            item["tipo"] = "item"
            especiais["filhos"].append(item)
        elif '%' in target or '$' in target:
            item["tipo"] = "item"
            build_grp["filhos"].append(item)
        elif target in phonys:
            phony_grp["filhos"].append(item)
        else:
            normal_grp["filhos"].append(item)

    resultado = []
    for grp in (normal_grp, phony_grp, build_grp, especiais):
        if grp["filhos"]:
            resultado.append(grp)
    return resultado
