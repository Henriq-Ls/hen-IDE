# 📁 _TRADUTION_/_dados/camada2_regex.py
#
# CAMADA 2 — Padrões regex com capture groups
# Preservam nomes de variáveis, módulos, arquivos e outros identificadores.
#
# IMPORTANTE: Esta camada roda ANTES da Camada 1.
# Motivo: a Camada 1 substituiria frases como "is not defined" antes que
# o regex tivesse chance de capturar o nome da variável.
#
# Os padrões já chegam compilados via _motor.py.
# Aqui ficam apenas as tuplas (padrão_str, substituição).

import re
PADROES: list[tuple[re.Pattern, str]] = [

    # ── NameError ─────────────────────────────────────────────────────────────
    (re.compile(r"NameError:\s*name\s+'([^']+)'\s+is not defined", re.I),
     r"NameError: nome '\1' não está definido"),

    # ── AttributeError ────────────────────────────────────────────────────────
    (re.compile(r"AttributeError:\s*'([^']+)'\s+object has no attribute\s+'([^']+)'", re.I),
     r"AttributeError: objeto '\1' não tem atributo '\2'"),

    # ── TypeError — subscriptable / callable / iterable ──────────────────────
    (re.compile(r"TypeError:\s*'([^']+)'\s+object is not subscriptable", re.I),
     r"TypeError: objeto '\1' não é indexável"),

    (re.compile(r"TypeError:\s*'([^']+)'\s+object is not callable", re.I),
     r"TypeError: objeto '\1' não é chamável"),

    (re.compile(r"TypeError:\s*'([^']+)'\s+object is not iterable", re.I),
     r"TypeError: objeto '\1' não é iterável"),

    # ── TypeError — operandos ─────────────────────────────────────────────────
    (re.compile(r"TypeError:\s*unsupported operand type\(s\) for ([^:]+):\s*'([^']+)' and '([^']+)'", re.I),
     r"TypeError: tipos de operando não suportados para \1: '\2' e '\3'"),

    # ── TypeError — argumentos posicionais ───────────────────────────────────
    (re.compile(r"TypeError:\s*(\w+\(\))\s+takes\s+([\w ]+)\s+positional arguments?\s+but\s+(\d+)\s+(?:were|was) given", re.I),
     r"TypeError: \1 aceita \2 argumento(s) posicional(is) mas \3 foram passados"),

    # ── TypeError — argumento deve ser ───────────────────────────────────────
    (re.compile(r"TypeError:\s*argument must be ([^,]+), not '([^']+)'", re.I),
     r"TypeError: argumento deve ser \1, não '\2'"),

    # ── ValueError ────────────────────────────────────────────────────────────
    (re.compile(r"ValueError:\s*invalid literal for int\(\) with base (\d+):\s*'([^']*)'", re.I),
     r"ValueError: literal inválido para int() na base \1: '\2'"),

    (re.compile(r"ValueError:\s*(.+)\s+is not in list", re.I),
     r"ValueError: '\1' não está na lista"),

    # ── IndexError ────────────────────────────────────────────────────────────
    (re.compile(r"IndexError:\s*list index out of range", re.I),
     "IndexError: índice de lista fora do intervalo"),

    (re.compile(r"IndexError:\s*(\w+) index out of range", re.I),
     r"IndexError: índice de \1 fora do intervalo"),

    # ── KeyError ──────────────────────────────────────────────────────────────
    (re.compile(r"KeyError:\s*'([^']*)'", re.I),
     r"KeyError: chave '\1' não encontrada"),

    # ── ModuleNotFoundError ───────────────────────────────────────────────────
    (re.compile(r"ModuleNotFoundError:\s*No module named\s+'([^']+)'", re.I),
     r"ModuleNotFoundError: módulo '\1' não encontrado"),

    # ── ImportError ───────────────────────────────────────────────────────────
    (re.compile(r"ImportError:\s*cannot import name\s+'([^']+)'\s+from\s+'([^']+)'", re.I),
     r"ImportError: não foi possível importar '\1' de '\2'"),

    (re.compile(r"ImportError:\s*cannot import name\s+'([^']+)'", re.I),
     r"ImportError: não foi possível importar '\1'"),

    # ── SyntaxError ───────────────────────────────────────────────────────────
    (re.compile(r"SyntaxError:\s*invalid syntax", re.I),
     "SyntaxError: sintaxe inválida"),

    (re.compile(r"SyntaxError:\s*expected\s+(.+)", re.I),
     r"SyntaxError: esperado \1"),

    # ── IndentationError ──────────────────────────────────────────────────────
    (re.compile(r"IndentationError:\s*unexpected indent", re.I),
     "IndentationError: indentação inesperada"),

    (re.compile(r"IndentationError:\s*expected an indented block", re.I),
     "IndentationError: esperado um bloco indentado"),

    (re.compile(r"IndentationError:\s*unindent does not match", re.I),
     "IndentationError: desindentação não corresponde a nível anterior"),

    # ── ZeroDivisionError ─────────────────────────────────────────────────────
    (re.compile(r"ZeroDivisionError:\s*division by zero", re.I),
     "ZeroDivisionError: divisão por zero"),

    (re.compile(r"ZeroDivisionError:\s*(.+)", re.I),
     r"ZeroDivisionError: \1"),

    # ── RecursionError / RuntimeError ─────────────────────────────────────────
    (re.compile(r"RecursionError:\s*maximum recursion depth exceeded", re.I),
     "RecursionError: profundidade máxima de recursão excedida"),

    (re.compile(r"RuntimeError:\s*maximum recursion depth exceeded", re.I),
     "RuntimeError: profundidade máxima de recursão excedida"),

    # ── MemoryError ───────────────────────────────────────────────────────────
    (re.compile(r"MemoryError", re.I),
     "MemoryError: memória insuficiente"),

    # ── FileNotFoundError ─────────────────────────────────────────────────────
    (re.compile(r"FileNotFoundError:\s*\[Errno \d+\]\s*No such file or directory:\s*'([^']+)'", re.I),
     r"FileNotFoundError: arquivo ou diretório inexistente: '\1'"),

    (re.compile(r"FileNotFoundError:\s*\[WinError \d+\]\s*[^:]+:\s*'([^']+)'", re.I),
     r"FileNotFoundError: arquivo não encontrado: '\1'"),

    # ── PermissionError ───────────────────────────────────────────────────────
    (re.compile(r"PermissionError:\s*\[Errno \d+\]\s*Permission denied:\s*'([^']+)'", re.I),
     r"PermissionError: permissão negada: '\1'"),

    (re.compile(r"PermissionError:\s*\[WinError \d+\]\s*[^:]+:\s*'([^']+)'", re.I),
     r"PermissionError: acesso negado: '\1'"),

    # ── OSError / IOError genérico ────────────────────────────────────────────
    (re.compile(r"(OSError|IOError):\s*\[Errno (\d+)\]\s*([^:]+):\s*'([^']+)'", re.I),
     r"\1: [Errno \2] \3: '\4'"),

    # ── UnicodeError ──────────────────────────────────────────────────────────
    (re.compile(r"UnicodeDecodeError:\s*'([^']+)' codec can't decode", re.I),
     r"UnicodeDecodeError: codec '\1' não consegue decodificar"),

    (re.compile(r"UnicodeEncodeError:\s*'([^']+)' codec can't encode", re.I),
     r"UnicodeEncodeError: codec '\1' não consegue codificar"),

    # ── TimeoutError / ConnectionError ────────────────────────────────────────
    (re.compile(r"TimeoutError:\s*(.+)", re.I),
     r"TimeoutError: tempo esgotado — \1"),

    (re.compile(r"ConnectionRefusedError:\s*(.+)", re.I),
     r"ConnectionRefusedError: conexão recusada — \1"),

    (re.compile(r"ConnectionResetError:\s*(.+)", re.I),
     r"ConnectionResetError: conexão resetada — \1"),

    # ── OverflowError ─────────────────────────────────────────────────────────
    (re.compile(r"OverflowError:\s*(.+)", re.I),
     r"OverflowError: estouro — \1"),

    # ── StopIteration ─────────────────────────────────────────────────────────
    (re.compile(r"\bStopIteration\b"),
     "StopIteration: iteração encerrada"),

    # ── UnboundLocalError ─────────────────────────────────────────────────────
    (re.compile(r"UnboundLocalError:\s*(?:local variable\s+)'([^']+)'\s+referenced before assignment", re.I),
     r"UnboundLocalError: variável local '\1' usada antes de ser definida"),

    # ── AssertionError / NotImplementedError ──────────────────────────────────
    (re.compile(r"AssertionError:\s*(.+)", re.I),
     r"AssertionError: afirmação falhou — \1"),

    (re.compile(r"NotImplementedError:\s*(.+)", re.I),
     r"NotImplementedError: não implementado — \1"),

    # ── pip ───────────────────────────────────────────────────────────────────
    (re.compile(r"Could not find a version that satisfies the requirement\s+(\S+)", re.I),
     r"Não foi possível encontrar uma versão que satisfaça o requisito \1"),

    (re.compile(r"Successfully installed\s+(.+)", re.I),
     r"Instalado com sucesso: \1"),

    (re.compile(r"Requirement already satisfied:\s+(\S+)", re.I),
     r"Dependência já satisfeita: \1"),

    # ── Traceback — frame de arquivo ──────────────────────────────────────────
    (re.compile(r'File "([^"]+)", line (\d+)(, in .+)?'),
     r'Arquivo "\1", linha \2\3'),

    (re.compile(r"\bline (\d+)\b", re.I),
     r"linha \1"),

    # ── PowerShell / CMD ──────────────────────────────────────────────────────
    (re.compile(r"The term '([^']+)' is not recognized as(?: the)?(?: name of)?(?: a)?\s*(cmdlet|function|script file|operable program|command)", re.I),
     r"O termo '\1' não é reconhecido como \2"),

    (re.compile(r"'([^']+)' is not recognized as an internal or external command", re.I),
     r"'\1' não é reconhecido como comando interno ou externo"),

    # ── Códigos de saída ──────────────────────────────────────────────────────
    (re.compile(r"[Ee]xited with (?:error )?code (\d+)"),
     r"Encerrado com código \1"),

    (re.compile(r"returned non-zero exit status (\d+)", re.I),
     r"retornou status de saída \1"),

    (re.compile(r"Process finished with exit code (\d+)", re.I),
     r"Processo finalizado com código de saída \1"),

    # ── pyflakes — import com erro de sintaxe ─────────────────────────────────
    (re.compile(r"'import'\s*\(<unknown>,\s*line\s*(\d+)\)"),
     r"erro de sintaxe na palavra-chave import (linha \1)"),

    # ── pip — conflitos de dependência (nomes de pacote dinâmicos) ────────────
    (re.compile(r"ERROR:\s*Cannot install\s+(\S+)\s+and\s+(\S+)\s+because these package versions have conflicting dependencies\.", re.I),
     r"ERRO: Não é possível instalar \1 e \2 porque essas versões de pacote têm dependências conflitantes."),

    (re.compile(r"ERROR:\s*Cannot install\s+(.+?)\s+because these package versions have conflicting dependencies\.", re.I),
     r"ERRO: Não é possível instalar \1 porque essas versões de pacote têm dependências conflitantes."),

    (re.compile(r"(\S+)\s+(\S+)\s+requires\s+(\S+),\s+but you (?:have|installed)\s+(\S+)\s+which is incompatible\.", re.I),
     r"\1 \2 requer \3, mas você tem \4 instalado, que é incompatível."),

    # ── pip — progresso de download ────────────────────────────────────────────
    (re.compile(r"Downloading\s+(\S+\.whl)\s+\(([^)]+)\)", re.I),
     r"Baixando \1 (\2)"),

    (re.compile(r"Collecting\s+(\S+(?:[><=!~^][^\s,]+)?)\s*$", re.I),
     r"Coletando \1"),

    # ── numpy / scipy — shapes e broadcast ────────────────────────────────────
    (re.compile(r"operands? could not be broadcast together with shapes?\s+(\S+)\s+(\S+)", re.I),
     r"operandos não podem ser combinados com os formatos \1 e \2"),

    (re.compile(r"cannot reshape array of size (\d+) into shape\s+(\S+)", re.I),
     r"não é possível reformatar array de tamanho \1 para o formato \2"),

    (re.compile(r"index (\d+) is out of bounds for axis (\d+) with size (\d+)", re.I),
     r"índice \1 fora dos limites para o eixo \2 de tamanho \3"),

    (re.compile(r"shapes?\s+(\S+)\s+and\s+(\S+)\s+not aligned", re.I),
     r"formatos \1 e \2 são incompatíveis"),

    # ── pytest — sumário de resultados ────────────────────────────────────────
    (re.compile(r"collected (\d+) items?", re.I),
     r"\1 teste(s) coletado(s)"),

    # X passed, Y failed, Z errors in Ns — todos os formatos (do mais específico ao menos)
    # 3 combinados
    (re.compile(r"(\d+) passed,\s*(\d+) failed,\s*(\d+) errors?\s+in\s+[\d.]+s", re.I),
     r"\1 aprovado(s), \2 reprovado(s), \3 erro(s)"),

    (re.compile(r"(\d+) failed,\s*(\d+) passed,\s*(\d+) errors?\s+in\s+[\d.]+s", re.I),
     r"\1 reprovado(s), \2 aprovado(s), \3 erro(s)"),

    # 2 combinados — passed + failed
    (re.compile(r"(\d+) passed,\s*(\d+) failed\s+in\s+[\d.]+s", re.I),
     r"\1 aprovado(s), \2 reprovado(s)"),

    (re.compile(r"(\d+) failed,\s*(\d+) passed\s+in\s+[\d.]+s", re.I),
     r"\1 reprovado(s), \2 aprovado(s)"),

    # 2 combinados — passed + errors / failed + errors
    (re.compile(r"(\d+) passed,\s*(\d+) errors?\s+in\s+[\d.]+s", re.I),
     r"\1 aprovado(s), \2 erro(s)"),

    (re.compile(r"(\d+) failed,\s*(\d+) errors?\s+in\s+[\d.]+s", re.I),
     r"\1 reprovado(s), \2 erro(s)"),

    # Simples
    (re.compile(r"(\d+) passed\s+in\s+[\d.]+s", re.I),
     r"\1 aprovado(s)"),

    (re.compile(r"(\d+) failed\s+in\s+[\d.]+s", re.I),
     r"\1 reprovado(s)"),

    (re.compile(r"(\d+) errors?\s+in\s+[\d.]+s", re.I),
     r"\1 erro(s)"),

    (re.compile(r"(\d+) skipped\s+in\s+[\d.]+s", re.I),
     r"\1 ignorado(s)"),
]
