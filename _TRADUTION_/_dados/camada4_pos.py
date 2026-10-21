# 📁 _TRADUTION_/_dados/camada4_pos.py
#
# CAMADA 4 — Pós-processamento
# Roda DEPOIS de todas as outras camadas.
#
# RESPONSABILIDADES:
#   1. Restaurar TODO conteúdo protegido pela Camada 0
#   2. Remover redundâncias geradas pela tradução em cascata
#   3. Corrigir capitalização
#   4. Limpar artefatos de formatação

import re
from .camada0_pre import _Cofre
# ── Redundâncias ──────────────────────────────────────────────────────────────
# Quando a Camada 3 traduz o nome da exceção E a Camada 1 já traduziu
# a mensagem, gera duplicação. Ex: "Divisão por zero: divisão por zero"
# Mantemos o nome original da exceção + mensagem traduzida.

_REDUNDANCIAS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'Divisão por zero:\s*divisão por zero',                  re.I), 'ZeroDivisionError: divisão por zero'),
    (re.compile(r'Divisão por zero:\s*divisão de ponto flutuante',        re.I), 'ZeroDivisionError: divisão de ponto flutuante por zero'),
    (re.compile(r'Divisão por zero:\s*divisão inteira',                   re.I), 'ZeroDivisionError: divisão inteira por zero'),
    (re.compile(r'Erro de memória:\s*memória insuficiente',               re.I), 'MemoryError: memória insuficiente'),
    (re.compile(r'Erro de memória:\s*erro de memória',                    re.I), 'MemoryError: erro de memória'),
    (re.compile(r'Arquivo não encontrado:\s*arquivo não encontrado',      re.I), 'FileNotFoundError: arquivo não encontrado'),
    (re.compile(r'Arquivo não encontrado:\s*arquivo ou diretório',        re.I), 'FileNotFoundError: arquivo ou diretório inexistente'),
    (re.compile(r'Módulo não encontrado:\s*módulo',                       re.I), 'ModuleNotFoundError: módulo'),
    (re.compile(r'Erro de índice:\s*índice de',                           re.I), 'IndexError: índice de'),
    (re.compile(r'Erro de sintaxe:\s*sintaxe inválida',                   re.I), 'SyntaxError: sintaxe inválida'),
    (re.compile(r'Erro de sintaxe:\s*string não terminada',               re.I), 'SyntaxError: string não terminada'),
    (re.compile(r'Erro de indentação:\s*indentação inesperada',           re.I), 'IndentationError: indentação inesperada'),
    (re.compile(r'Erro de indentação:\s*desindentação não corresponde',   re.I), 'IndentationError: desindentação não corresponde'),
    (re.compile(r'Erro de indentação:\s*esperado um bloco indentado',     re.I), 'IndentationError: esperado um bloco indentado'),
    (re.compile(r'Erro de tabulação:\s*tabs e espaços misturados',        re.I), 'TabError: tabs e espaços misturados'),
    (re.compile(r'Erro de atributo:\s*objeto',                            re.I), 'AttributeError: objeto'),
    (re.compile(r'Erro de tipo:\s*objeto',                                re.I), 'TypeError: objeto'),
    (re.compile(r'Erro de tipo:\s*tipos? de operando',                    re.I), 'TypeError: tipos de operando'),
    (re.compile(r'Erro de tipo:\s*não aceita argumentos',                 re.I), 'TypeError: não aceita argumentos'),
    (re.compile(r'Erro de tipo:\s*deve ser str',                          re.I), 'TypeError: deve ser str'),
    (re.compile(r'Erro de nome:\s*nome',                                  re.I), 'NameError: nome'),
    (re.compile(r'Erro de valor:\s*literal inválido',                     re.I), 'ValueError: literal inválido'),
    (re.compile(r'Erro de valor:\s*não foi possível converter',           re.I), 'ValueError: não foi possível converter'),
    (re.compile(r'Erro de chave:\s*chave',                                re.I), 'KeyError: chave'),
    (re.compile(r'Erro de permissão:\s*(?:permissão negada|acesso negado)',re.I), 'PermissionError: acesso negado'),
    (re.compile(r'Erro de permissão:\s*operação não permitida',           re.I), 'PermissionError: operação não permitida'),
    (re.compile(r'É um diretório:\s*é um diretório',                      re.I), 'IsADirectoryError: é um diretório'),
    (re.compile(r'Não é um diretório:\s*não é um diretório',              re.I), 'NotADirectoryError: não é um diretório'),
    (re.compile(r'Arquivo já existe:\s*arquivo já existe',                re.I), 'FileExistsError: arquivo já existe'),
    (re.compile(r'Erro do sistema operacional:\s*arquivo ou diretório',   re.I), 'OSError: arquivo ou diretório inexistente'),
    (re.compile(r'Erro de E/S:\s*erro de E/S',                            re.I), 'IOError: erro de E/S'),
    (re.compile(r'Erro de fim de arquivo:\s*erro de fim de arquivo',      re.I), 'EOFError: fim de arquivo inesperado'),
    (re.compile(r'Erro de decodificação Unicode:\s*erro de decodificação',re.I), 'UnicodeDecodeError: erro de decodificação unicode'),
    (re.compile(r'Erro de codificação Unicode:\s*erro de codificação',    re.I), 'UnicodeEncodeError: erro de codificação unicode'),
    (re.compile(r'Erro de estouro:\s*erro de estouro',                    re.I), 'OverflowError: resultado muito grande'),
    (re.compile(r'Erro de recursão:\s*profundidade máxima',               re.I), 'RecursionError: profundidade máxima de recursão excedida'),
    (re.compile(r'Erro em tempo de execução:\s*erro em tempo de execução',re.I), 'RuntimeError: erro em tempo de execução'),
    (re.compile(r'Variável local não vinculada:\s*variável local',        re.I), 'UnboundLocalError: variável local usada antes de ser definida'),
    (re.compile(r'Conexão recusada:\s*conexão recusada',                  re.I), 'ConnectionRefusedError: conexão recusada'),
    (re.compile(r'Conexão resetada:\s*conexão resetada',                  re.I), 'ConnectionResetError: conexão resetada'),
    (re.compile(r'Conexão abortada:\s*conexão abortada',                  re.I), 'ConnectionAbortedError: conexão abortada'),
    (re.compile(r'Pipe quebrado:\s*pipe quebrado',                        re.I), 'BrokenPipeError: pipe quebrado'),
    (re.compile(r'Tempo esgotado:\s*(?:tempo esgotado|expirou)',          re.I), 'TimeoutError: tempo esgotado'),
    (re.compile(r'Iteração encerrada:\s*iteração encerrada',              re.I), 'StopIteration'),
    (re.compile(r'Não implementado:\s*não implementado',                  re.I), 'NotImplementedError: não implementado'),
    (re.compile(r'Interrupção pelo teclado:\s*interrupção pelo teclado',  re.I), 'KeyboardInterrupt'),
    (re.compile(r'Saída do sistema:\s*saída do sistema',                  re.I), 'SystemExit'),
    (re.compile(r'Exceção:\s*exceção',                                    re.I), 'Exception'),
    (re.compile(r'Aviso de descontinuação:\s*aviso de descontinuação',    re.I), 'DeprecationWarning'),
    (re.compile(r'Aviso de tempo de execução:\s*aviso de',                re.I), 'RuntimeWarning: aviso de'),
    (re.compile(r'Aviso do usuário:\s*aviso',                             re.I), 'UserWarning'),
    # Rastreamento duplicado
    (re.compile(r'Rastreamento de erro:\s*rastreamento de erro',          re.I), 'Rastreamento de erro'),
    # "erro de importação: erro de importação"
    (re.compile(r'Erro de importação:\s*erro de importação',              re.I), 'ImportError: erro de importação'),
]

# ── Artefatos de formatação ───────────────────────────────────────────────────
# Espaços duplos, linhas com só espaços, etc.
_RE_ESPACOS_DUPLOS = re.compile(r'  +')
_RE_LINHA_SO_ESPACOS = re.compile(r'^\s+$', re.MULTILINE)

def restaurar(texto: str, cofre: "_Cofre | dict") -> str:
    """
    Restaura TODO conteúdo protegido pela Camada 0.
    Aceita tanto o objeto _Cofre quanto um dict legado.
    """
    if isinstance(cofre, _Cofre):

        return cofre.restaurar(texto)

    # compatibilidade com dict antigo
    for chave, valor in cofre.items():
        texto = texto.replace(chave, valor)

    return texto

def remover_redundancias(texto: str) -> str:
    """Remove traduções duplas geradas pela cascata de camadas."""
    for padrao, substituto in _REDUNDANCIAS:
        texto = padrao.sub(substituto, texto)

    return texto

def corrigir_capitalizacao(texto: str) -> str:
    """
    Capitaliza a primeira letra de cada linha quando está em minúsculo.
    Não toca em:
        - linhas que começam com maiúscula
        - linhas que começam com número, símbolo ou aspas
        - linhas indentadas (espaço/tab = código do traceback restaurado pelo cofre)
        - nomes de erro Python (já restaurados)
    """
    linhas = texto.split('\n')
    resultado = []
    for linha in linhas:
        # Linhas indentadas são código do traceback — não capitalizar
        if linha and linha[0].isspace():
            resultado.append(linha)
            continue
        stripped = linha.lstrip()
        if stripped and stripped[0].islower():
            idx = len(linha) - len(stripped)
            linha = linha[:idx] + stripped[0].upper() + linha[idx + 1:]
        resultado.append(linha)

    return '\n'.join(resultado)

def limpar_artefatos(texto: str) -> str:
    """
    Remove artefatos menores gerados pela tradução:
        - Espaços duplos dentro de uma linha
        - Linhas que ficaram só com espaços
    """
    linhas = texto.split('\n')
    resultado = []
    for linha in linhas:
        # espaços duplos — só dentro do conteúdo, preserva indentação
        stripped = linha.lstrip()
        indentacao = linha[: len(linha) - len(stripped)]
        stripped = _RE_ESPACOS_DUPLOS.sub(' ', stripped)
        resultado.append(indentacao + stripped)

    return '\n'.join(resultado)
