# _EDITOR_/Mult_Linguas/C_CPP/outline.py
"""
Outline para C/C++ — regex-based (sem compilador).
Detecta: funções, ponteiros de retorno, structs, classes, enums, namespaces.
Não entra em #ifdef/#include — só analisa definições top-level.
Retorna lista de dicts compatíveis com _popular_arvore_dict().

BUG-C-1 FIX: _RE_FUNC agora captura funções C puro com retorno ponteiro,
  ex.: Node *criar_no(, char *get_nome(, struct Lista *new_lista(.
"""
import re

# ─── Função / método ──────────────────────────────────────────────────────────
# Não começa com keyword de controle.
# Suporta qualquer combinação de qualificadores e tipos, incluindo:
#   - retorno por ponteiro: No *criar(, char *buscar(
#   - retorno de struct C: struct No *novo(
#   - métodos C++: virtual void foo(, ClassName::metodo(
_RE_FUNC = re.compile(
    r'^(?!(?:if|for|while|switch|else|do|return|case|typedef)\b)'
    r'(?:(?:static|inline|extern|virtual|explicit|constexpr|override|final|'
    r'const|unsigned|signed|long|short)\s+)*'
    r'(?:[\w:*&<>~]+\s+)*'     # zero ou mais tokens de tipo (int, struct X, etc.)
    r'\**([a-zA-Z_]\w*)\s*\('   # * opcional + nome da função + (
    r'[^;]*$'                   # parâmetros — linha não termina com ; (evita declarações)
)
# ─── Struct / class / enum / union ────────────────────────────────────────────
_RE_STRUCT = re.compile(
    r'^\s*(?:typedef\s+)?(?:(struct|class|enum(?:\s+class)?|union)\s+([a-zA-Z_]\w*))\s*(?:\{|:.*\{|$)'
)
# ─── Namespace ────────────────────────────────────────────────────────────────
_RE_NS = re.compile(r'^\s*namespace\s+([a-zA-Z_][\w:]*)\s*(?:\{|$)')


def analisar_c(codigo: str) -> list:
    """Analisa C/C++ e retorna definições para o outline."""
    linhas = codigo.splitlines()
    itens  = []
    visto  = set()

    for n, linha in enumerate(linhas, 1):
        stripped = linha.strip()
        if not stripped or stripped.startswith('//') or stripped.startswith('*') or stripped.startswith('#'):
            continue

        # Namespace
        m = _RE_NS.match(linha)
        if m:
            nome = m.group(1)
            if nome not in visto:
                visto.add(nome)
                itens.append({"tipo": "objeto", "nome": f"namespace {nome}", "linha": n, "filhos": []})
            continue

        # Struct / class / enum / union
        m = _RE_STRUCT.match(linha)
        if m:
            kw, nome = m.group(1), m.group(2)
            if nome and nome not in visto:
                visto.add(nome)
                tipo_item = "classe" if kw in ("class", "struct") else "objeto"
                itens.append({"tipo": tipo_item, "nome": f"{kw} {nome}", "linha": n, "filhos": []})
            continue

        # Função / método
        m = _RE_FUNC.match(linha)
        if m:
            nome = m.group(1)
            if nome:
                chave = f"{nome}:{n}"
                if chave not in visto:
                    visto.add(chave)
                    prefixo = "main()" if nome == "main" else f"{nome}()"
                    itens.append({"tipo": "funcao", "nome": prefixo, "linha": n})

    return itens
