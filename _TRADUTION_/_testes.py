# 📁 _TRADUTION_/_testes.py
#
# Suite de testes de regressão do motor de tradução.
# Detecta quebras causadas por novas entradas em C1, C2 ou C3.
#
# USO:
#     python -m _TRADUTION_._testes
#   ou (da raiz do projeto):
#     python -c "import _TRADUTION_._testes"
#
# SAÍDA:
#     PASS  <entrada>
#     FAIL  <entrada>
#           esperado : <valor>
#           obtido   : <valor>
#
# Exit code 0 = todos passaram. Exit code 1 = algum falhou.

import sys
import os

# Garante que a raiz do projeto está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _TRADUTION_.tradutor_erros import traduzir

# ── Casos de teste: (entrada_inglês, saída_esperada) ──────────────────────────
# Regra: a saída é o que traduzir() DEVE retornar — exato, incluindo capitalização.

CASOS: list[tuple[str, str]] = [

    # ── Python — NameError ────────────────────────────────────────────────────
    ("NameError: name 'x' is not defined",
     "NameError: nome 'x' não está definido"),

    ("NameError: name 'contador' is not defined",
     "NameError: nome 'contador' não está definido"),

    # ── Python — AttributeError ───────────────────────────────────────────────
    ("AttributeError: 'NoneType' object has no attribute 'split'",
     "AttributeError: objeto 'NoneType' não tem atributo 'split'"),

    # ── Python — TypeError ────────────────────────────────────────────────────
    ("TypeError: 'int' object is not subscriptable",
     "TypeError: objeto 'int' não é indexável"),

    ("TypeError: 'str' object is not callable",
     "TypeError: objeto 'str' não é chamável"),

    ("TypeError: unsupported operand type(s) for +: 'int' and 'str'",
     "TypeError: tipos de operando não suportados para +: 'int' e 'str'"),

    # ── Python — IndexError ───────────────────────────────────────────────────
    ("IndexError: list index out of range",
     "IndexError: índice de lista fora do intervalo"),

    # ── Python — KeyError ─────────────────────────────────────────────────────
    ("KeyError: 'nome'",
     "KeyError: chave 'nome' não encontrada"),

    # ── Python — ZeroDivisionError ────────────────────────────────────────────
    ("ZeroDivisionError: division by zero",
     "ZeroDivisionError: divisão por zero"),

    # ── Python — ModuleNotFoundError ──────────────────────────────────────────
    ("ModuleNotFoundError: No module named 'numpy'",
     "ModuleNotFoundError: módulo 'numpy' não encontrado"),

    # ── Python — ImportError ──────────────────────────────────────────────────
    ("ImportError: cannot import name 'DataFrame' from 'pandas'",
     "ImportError: não foi possível importar 'DataFrame' de 'pandas'"),

    # ── Python — SyntaxError ──────────────────────────────────────────────────
    ("SyntaxError: invalid syntax",
     "SyntaxError: sintaxe inválida"),

    ("IndentationError: unexpected indent",
     "IndentationError: indentação inesperada"),

    # ── Python — UnboundLocalError ────────────────────────────────────────────
    ("UnboundLocalError: local variable 'x' referenced before assignment",
     "UnboundLocalError: variável local 'x' usada antes de ser definida"),

    # ── Python — RecursionError ───────────────────────────────────────────────
    ("RecursionError: maximum recursion depth exceeded",
     "RecursionError: profundidade máxima de recursão excedida"),

    # ── Python — FileNotFoundError ────────────────────────────────────────────
    ("FileNotFoundError: [Errno 2] No such file or directory: 'config.json'",
     "FileNotFoundError: arquivo ou diretório inexistente: 'config.json'"),

    # ── Python — PermissionError ──────────────────────────────────────────────
    ("PermissionError: [Errno 13] Permission denied: 'C:\\\\Users\\\\foo'",
     "PermissionError: permissão negada: 'C:\\\\Users\\\\foo'"),

    # ── Python — UnicodeDecodeError ───────────────────────────────────────────
    ("UnicodeDecodeError: 'utf-8' codec can't decode",
     "UnicodeDecodeError: codec 'utf-8' não consegue decodificar"),

    # ── Python — ValueError ───────────────────────────────────────────────────
    ("ValueError: invalid literal for int() with base 10: 'abc'",
     "ValueError: literal inválido para int() na base 10: 'abc'"),

    # ── Python — Traceback ────────────────────────────────────────────────────
    ('File "main.py", line 42, in <module>',
     'Arquivo "main.py", linha 42, in <módulo>'),

    # ── Cofre — caminhos preservados ──────────────────────────────────────────
    # O Cofre deve impedir que caminhos sejam traduzidos pelo C3
    ("no such file or directory: 'C:\\\\Users\\\\joao\\\\projeto.py'",
     "Arquivo ou diretório inexistente: 'C:\\\\Users\\\\joao\\\\projeto.py'"),

    # ── pip — instalação ──────────────────────────────────────────────────────
    ("Successfully installed requests-2.28.0",
     "Instalado com sucesso: requests-2.28.0"),

    ("Requirement already satisfied: numpy",
     "Dependência já satisfeita: numpy"),

    ("Could not find a version that satisfies the requirement flask",
     "Não foi possível encontrar uma versão que satisfaça o requisito flask"),

    # ── pip — progresso (C2) ──────────────────────────────────────────────────
    ("Downloading numpy-1.26.0-cp311-cp311-win_amd64.whl (15.3 MB)",
     "Baixando numpy-1.26.0-cp311-cp311-win_amd64.whl (15.3 MB)"),

    ("Collecting numpy>=1.21",
     "Coletando numpy>=1.21"),

    # ── pip — conflito de dependências (C2) ───────────────────────────────────
    ("ERROR: Cannot install flask and requests because these package versions have conflicting dependencies.",
     "ERRO: Não é possível instalar flask e requests porque essas versões de pacote têm dependências conflitantes."),

    # ── pip — conflito de dependências (C1) ───────────────────────────────────
    ("The conflict is caused by:",
     "O conflito é causado por:"),

    ("To fix this you could try to:",
     "Para corrigir, você pode tentar:"),

    # ── pip help ──────────────────────────────────────────────────────────────
    ("Install packages.",
     "Instalar pacotes."),

    ("List installed packages.",
     "Listar pacotes instalados."),

    ("General Options:",
     "Opções gerais:"),

    ("Show version and exit.",
     "Mostrar versão e sair."),

    # ── Windows / PowerShell ──────────────────────────────────────────────────
    ("'python' is not recognized as an internal or external command",
     "'python' não é reconhecido como comando interno ou externo"),

    ("The term 'activate' is not recognized as the name of a cmdlet",
     "O termo 'activate' não é reconhecido como cmdlet"),

    # ── Rede ──────────────────────────────────────────────────────────────────
    ("connection refused",
     "Conexão recusada"),

    ("ConnectionRefusedError: [Errno 111] Connection refused",
     "ConnectionRefusedError: conexão recusada — [errno 111] conexão recusada"),

    # ── SSL ───────────────────────────────────────────────────────────────────
    ("certificate verify failed",
     "Verificação de certificado falhou"),

    # ── HTTP ──────────────────────────────────────────────────────────────────
    ("404 not found",
     "404 não encontrado"),

    ("500 internal server error",
     "500 erro interno do servidor"),

    # ── Git ───────────────────────────────────────────────────────────────────
    ("fatal: not a git repository",
     "Fatal: não é um repositório git"),

    ("nothing to commit, working tree clean",
     "Nada para fazer commit, árvore de trabalho limpa"),

    # ── pyflakes ──────────────────────────────────────────────────────────────
    ("imported but unused",
     "Importado mas não utilizado"),

    # ── processo ──────────────────────────────────────────────────────────────
    ("Process finished with exit code 1",
     "Processo finalizado com código de saída 1"),

    ("returned non-zero exit status 1",
     "Retornou status de saída 1"),

    # ── numpy / scipy (C2) ────────────────────────────────────────────────────
    ("operands could not be broadcast together with shapes (3,) (4,)",
     "Operandos não podem ser combinados com os formatos (3,) e (4,)"),

    ("cannot reshape array of size 6 into shape (2,4)",
     "Não é possível reformatar array de tamanho 6 para o formato (2,4)"),

    ("index 5 is out of bounds for axis 0 with size 4",
     "Índice 5 fora dos limites para o eixo 0 de tamanho 4"),

    ("shapes (3,3) and (4,4) not aligned",
     "Formatos (3,3) e (4,4) são incompatíveis"),

    # ── numpy / scipy (C1) ────────────────────────────────────────────────────
    ("setting an array element with a sequence",
     "Atribuindo um elemento de array com uma sequência"),

    ("axis out of range",
     "Eixo fora do intervalo"),

    ("array is read-only",
     "Array é somente leitura"),

    ("data type not understood",
     "Tipo de dado não reconhecido"),

    # ── pandas (C1) ───────────────────────────────────────────────────────────
    ("The truth value of a Series is ambiguous. Use a.empty, a.bool(), a.item(), a.any() or a.all()",
     "O valor verdade de uma série é ambíguo. utilize 'a.empty', 'a.bool()', 'a.item()', 'a.any()' ou 'a.all()'"),

    ("cannot reindex from a duplicate axis",
     "Não é possível reindexar de um eixo duplicado"),

    # ── requests (C1) ─────────────────────────────────────────────────────────
    ("too many redirects",
     "Redirecionamentos demais"),

    # ── SQLAlchemy (C1) ───────────────────────────────────────────────────────
    ("This Session's transaction has been rolled back",
     "A transação desta sessão foi revertida"),

    ("ambiguous column name",
     "Nome de coluna ambíguo"),

    # ── pytest (C2) ───────────────────────────────────────────────────────────
    ("collected 12 items",
     "12 teste(s) coletado(s)"),

    ("5 passed in 0.42s",
     "5 aprovado(s)"),

    ("3 failed in 1.05s",
     "3 reprovado(s)"),

    ("3 failed, 2 passed in 1.05s",
     "3 reprovado(s), 2 aprovado(s)"),

    ("4 passed, 2 failed, 1 errors in 2.1s",
     "4 aprovado(s), 2 reprovado(s), 1 erro(s)"),

    # ── pytest (C1) ───────────────────────────────────────────────────────────
    ("short test summary info",
     "Resumo de falhas"),

    ("warnings summary",
     "Resumo de avisos"),

    ("xfailed",
     "Falha esperada"),

    ("xpassed",
     "Passou (era esperado falhar)"),

    ("setup failed",
     "Configuração do teste falhou"),

    ("no tests ran",
     "Nenhum teste foi executado"),

    # ── Cofre — proteção de aspas ─────────────────────────────────────────────
    # Conteúdo entre aspas NÃO deve ser traduzido
    ("no module named 'requests'",
     "Módulo não encontrado: 'requests'"),

    # ── Cofre — proteção de versões ───────────────────────────────────────────
    # Versões numéricas NÃO devem ser alteradas
    ("requires python>=3.11",
     "Requer Python>=3.11"),

    # ── Cofre — linhas indentadas não são traduzidas ───────────────────────────
    # Código do usuário no traceback deve sair intacto
    ("    import numpy",
     "    import numpy"),

    ("    x = foo.bar()",
     "    x = foo.bar()"),

    # ── Normalização de underscores ───────────────────────────────────────────
    # C1 tem entrada explícita para variante com underscore (OS errors)
    ("no_such_file or directory",
     "Arquivo inexistente ou diretório"),

    # ── Entrada vazia / nula ──────────────────────────────────────────────────
    ("",   ""),
    ("  ", "  "),

    # ── Cache — mesma entrada duas vezes deve retornar idêntico ──────────────
    # (testado via chamadas duplicadas no loop abaixo)
]

# ── Runner ────────────────────────────────────────────────────────────────────

def _rodar() -> bool:
    total  = 0
    falhas = 0

    for entrada, esperado in CASOS:
        total += 1
        obtido = traduzir(entrada)

        # Verifica idempotência do cache: segunda chamada deve retornar igual
        obtido2 = traduzir(entrada)
        if obtido2 != obtido:
            print(f"CACHE  {entrada!r}")
            print(f"       1ª chamada : {obtido!r}")
            print(f"       2ª chamada : {obtido2!r}")
            falhas += 1
            continue

        if obtido == esperado:
            print(f"PASS   {entrada!r}")
        else:
            print(f"FAIL   {entrada!r}")
            print(f"       esperado : {esperado!r}")
            print(f"       obtido   : {obtido!r}")
            falhas += 1

    print()
    print(f"{'='*60}")
    print(f"  {total - falhas}/{total} passaram"
          + (f"  —  {falhas} FALHA(S)" if falhas else "  ✅ tudo ok"))
    print(f"{'='*60}")

    return falhas == 0


if __name__ == "__main__":
    ok = _rodar()
    sys.exit(0 if ok else 1)
