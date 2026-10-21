# _EDITOR_/Mult_Linguas/Shell/outline.py
"""
Outline para Shell (Bash/Zsh/PowerShell/Batch) — regex-based.
Detecta: definições de função  nome() { ... }  e  function nome { ... }
         (incluindo PowerShell: function Verb-Noun { ... })
Retorna lista de dicts compatíveis com _popular_arvore_dict().
"""
import re

# Bash/Zsh: nome() {  ou  function nome {  ou  function nome() {
_RE_FUNC_BASH = re.compile(
    r'^\s*(?:function\s+)?([a-zA-Z_][\w:\-\.]*)\s*\(\s*\)\s*(?:\{|$)'
)
# PowerShell: function Verb-Noun {
_RE_FUNC_PS = re.compile(
    r'^\s*function\s+([A-Za-z][\w\-]*)(?:\s*\{)?'
)
# Batch: :label
_RE_LABEL_BAT = re.compile(r'^:([a-zA-Z_][\w]*)(?:\s|$)')


def analisar_sh(codigo: str) -> list:
    """Analisa shell script e retorna funções/labels para o outline."""
    linhas = codigo.splitlines()
    itens  = []
    visto  = set()

    for n, linha in enumerate(linhas, 1):
        stripped = linha.strip()
        if not stripped or stripped.startswith('#'):
            continue

        # Função bash/zsh
        m = _RE_FUNC_BASH.match(linha)
        if m:
            nome = m.group(1)
            if nome not in visto:
                visto.add(nome)
                itens.append({"tipo": "funcao", "nome": f"{nome}()", "linha": n})
            continue

        # Função PowerShell
        m = _RE_FUNC_PS.match(linha)
        if m:
            nome = m.group(1)
            if nome not in visto:
                visto.add(nome)
                itens.append({"tipo": "funcao", "nome": nome, "linha": n})
            continue

        # Label batch :nome
        m = _RE_LABEL_BAT.match(linha)
        if m:
            nome = m.group(1)
            if nome.upper() not in ("EOF", "END") and nome not in visto:
                visto.add(nome)
                itens.append({"tipo": "item", "nome": f":{nome}", "linha": n})

    return itens
