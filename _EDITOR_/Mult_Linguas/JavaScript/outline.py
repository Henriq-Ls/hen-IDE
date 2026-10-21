# _EDITOR_/Mult_Linguas/JavaScript/outline.py
"""
Outline para JavaScript/TypeScript — regex-based (sem AST).
Detecta: classes, funções nomeadas, métodos, arrow functions em const/let,
         exports nomeados, interfaces e types TypeScript.
Retorna lista de dicts compatíveis com _popular_arvore_dict().
"""
import re

_RE_CLASS     = re.compile(r'^\s*(?:export\s+)?(?:abstract\s+)?class\s+([A-Z][\w$]*)')
_RE_FUNC      = re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([a-zA-Z_$][\w$]*)\s*\(')
_RE_ARROW     = re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z_$][\w$]*)\s*=>')
_RE_METHOD    = re.compile(r'^\s*(?:(?:async|static|get|set|public|private|protected|override)\s+)*([a-zA-Z_$][\w$]*)\s*\(')
_RE_INTERFACE = re.compile(r'^\s*(?:export\s+)?interface\s+([A-Z][\w$]*)')
_RE_TYPE      = re.compile(r'^\s*(?:export\s+)?type\s+([A-Z][\w$]*)\s*=')
_RE_ENUM      = re.compile(r'^\s*(?:export\s+)?(?:const\s+)?enum\s+([A-Z][\w$]*)')


def analisar_js(codigo: str) -> list:
    """
    Analisa JS/TS e retorna lista de dicts para _popular_arvore_dict().
    Classes são nós pai com seus métodos como filhos.
    """
    linhas   = codigo.splitlines()
    itens    = []
    classe_atual: dict | None = None
    nivel_chave  = 0   # rastreia { } para saber quando a classe terminou

    for n, linha in enumerate(linhas, 1):
        stripped = linha.strip()

        # Rastreia abertura/fechamento de blocos para delimitar classe
        nivel_chave += stripped.count('{') - stripped.count('}')

        # Classe
        m = _RE_CLASS.match(linha)
        if m:
            classe_atual = {
                "tipo":    "classe",
                "nome":    m.group(1),
                "linha":   n,
                "filhos":  [],
                "_nivel":  nivel_chave,
            }
            itens.append(classe_atual)
            continue

        # Fecha classe quando voltamos ao nível original
        if classe_atual and nivel_chave <= classe_atual.get("_nivel", 0) - 1:
            classe_atual = None

        # Interface TypeScript
        m = _RE_INTERFACE.match(linha)
        if m:
            itens.append({"tipo": "objeto", "nome": f"interface {m.group(1)}", "linha": n, "filhos": []})
            continue

        # Type alias TypeScript
        m = _RE_TYPE.match(linha)
        if m:
            itens.append({"tipo": "item", "nome": f"type {m.group(1)}", "linha": n})
            continue

        # Enum
        m = _RE_ENUM.match(linha)
        if m:
            itens.append({"tipo": "objeto", "nome": f"enum {m.group(1)}", "linha": n, "filhos": []})
            continue

        # Função nomeada
        m = _RE_FUNC.match(linha)
        if m:
            item = {"tipo": "funcao", "nome": f"{m.group(1)}()", "linha": n}
            if classe_atual:
                classe_atual["filhos"].append(item)
            else:
                itens.append(item)
            continue

        # Arrow function em const/let/var
        m = _RE_ARROW.match(linha)
        if m:
            item = {"tipo": "metodo", "nome": f"{m.group(1)} =›", "linha": n}
            if classe_atual:
                classe_atual["filhos"].append(item)
            else:
                itens.append(item)
            continue

        # Método dentro de classe
        if classe_atual and not stripped.startswith('//') and not stripped.startswith('*'):
            m = _RE_METHOD.match(linha)
            if m and m.group(1) not in ('if', 'for', 'while', 'switch', 'catch', 'return'):
                classe_atual["filhos"].append({
                    "tipo": "metodo",
                    "nome": f"{m.group(1)}()",
                    "linha": n,
                })

    # Remove _nivel (chave interna, não vai para a UI)
    for item in itens:
        item.pop("_nivel", None)

    return itens
