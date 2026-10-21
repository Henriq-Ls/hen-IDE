# 📁 _TRADUTION_/_dados/camada0_pre.py
#
# CAMADA 0 — Pré-processamento
# Roda em DUAS etapas separadas pelo motor:
#
#   Etapa A — normalizar_underscores()       → antes de tudo
#   Etapa B — proteger()                     → depois das Camadas 2 e 1,
#                                              antes da Camada 3
#
# RESPONSABILIDADES:
#   1. Normalizar underscores isolados  (no_such_file → no such file)
#   2. Proteger conteúdo entre aspas    ('config.json' não vira 'configuração.json')
#   3. Proteger caminhos de arquivo     (C:\Users\foo não é traduzido)
#   4. Proteger versões e números       (3.11.2, v2.0.1 não são alterados)
#   5. Proteger nomes de pacotes pip    (requests-2.28.0 não vira requisições)
#   6. Proteger linhas de código        (código do usuário no traceback não é traduzido)
#   7. Proteger nomes de erro Python    (NameError, TypeError etc. são preservados)
#
# A Camada 4 restaura TUDO que foi protegido aqui.

import re
# ── Tokens invisíveis ─────────────────────────────────────────────────────────
# Cada tipo usa um prefixo diferente para facilitar debug e restauração seletiva.
# O caractere \x00 não ocorre em nenhuma mensagem de erro real.

_TOKEN_ASPAS   = "\x00A{i}\x00"   # conteúdo entre aspas
_TOKEN_CAMINHO = "\x00C{i}\x00"   # caminhos de arquivo
_TOKEN_VERSAO  = "\x00V{i}\x00"   # versões numéricas
_TOKEN_PACOTE  = "\x00P{i}\x00"   # nomes de pacotes pip
_TOKEN_LINHA   = "\x00L{i}\x00"   # linhas de código do usuário
_TOKEN_ERRO    = "\x00E{i}\x00"   # nomes de classe de erro Python

# ── Padrões de detecção ───────────────────────────────────────────────────────

# Caminhos Windows e Unix
_RE_CAMINHO_WIN  = re.compile(
    r'[A-Za-z]:\\(?:[^\s\n\r"\'<>|?*]+\\)*[^\s\n\r"\'<>|?*]*'
)
_RE_CAMINHO_UNIX = re.compile(
    r'(?<!\w)/(?:[^\s\n\r"\'<>|?*]+/)*[^\s\n\r"\'<>|?*]+'
)

# Versões semânticas: 3.11.2, v2.0.1, 1.0.0a1, 2.28.0
_RE_VERSAO = re.compile(
    r'\bv?(\d+\.\d+(?:\.\d+)*(?:[a-zA-Z]\d*)?)\b'
)

# Pacotes pip com versão ou especificador: requests-2.28.0, numpy>=1.21
_PACOTES_PIP: frozenset[str] = frozenset({
    "requests", "flask", "django", "fastapi", "uvicorn", "starlette",
    "numpy", "pandas", "scipy", "matplotlib", "seaborn", "plotly",
    "pillow", "pil", "opencv", "cv2", "imageio", "skimage",
    "sqlalchemy", "pymongo", "psycopg2", "pymysql", "aiomysql",
    "aiosqlite", "motor", "tortoise",
    "pytest", "unittest", "coverage", "hypothesis", "faker",
    "black", "flake8", "pylint", "mypy", "ruff", "isort", "autopep8",
    "pyside6", "pyqt6", "pyqt5", "tkinter", "wxpython", "kivy",
    "jedi", "rope", "parso", "pylsp", "pyflakes",
    "cryptography", "paramiko", "httpx", "aiohttp", "websockets",
    "celery", "redis", "kafka", "pika", "kombu",
    "boto3", "botocore", "azure", "google-cloud", "firebase-admin",
    "rich", "click", "typer", "argparse", "docopt",
    "pydantic", "marshmallow", "attrs", "dataclasses",
    "setuptools", "pip", "wheel", "twine", "build", "flit",
    "jupyter", "ipython", "notebook", "jupyterlab",
    "torch", "torchvision", "tensorflow", "keras",
    "sklearn", "scikit-learn", "xgboost", "lightgbm",
    "transformers", "diffusers", "tokenizers", "datasets",
    "yaml", "toml", "dotenv", "decouple", "environs",
    "arrow", "pendulum", "dateutil", "pytz",
    "lxml", "beautifulsoup4", "bs4", "scrapy", "selenium",
    "tqdm", "loguru", "structlog",
    "alembic", "peewee", "ponyorm",
    "grpc", "protobuf", "thrift",
    "watchdog", "schedule", "apscheduler",
    "multiprocessing", "threading", "concurrent",
    "pathlib", "glob", "shutil",
})

_RE_PACOTE = re.compile(
    r'(?<![\'"\w])(' +
    '|'.join(re.escape(p) for p in sorted(_PACOTES_PIP, key=len, reverse=True)) +
    r')(?:[=\-~><!\^][^\s,\)\'\"]+)?(?![\'"\w])',
    re.IGNORECASE,
)

# Linhas de código do usuário dentro do traceback
# São as linhas com 4+ espaços de indentação que NÃO começam com "File" ou "^"
_RE_LINHA_CODIGO = re.compile(
    r'^( {4,}|\t+)(?!File |[~^])(.+)$',
    re.MULTILINE,
)

# Nomes de classes de erro Python (preservar capitalização original)
_NOMES_ERRO: frozenset[str] = frozenset({
    "AttributeError", "KeyError", "TypeError", "ValueError", "IndexError",
    "NameError", "ImportError", "ModuleNotFoundError", "FileNotFoundError",
    "FileExistsError", "PermissionError", "IsADirectoryError",
    "NotADirectoryError", "OSError", "IOError", "EOFError",
    "UnicodeDecodeError", "UnicodeEncodeError", "UnicodeTranslateError",
    "UnicodeError", "ZeroDivisionError", "OverflowError", "MemoryError",
    "RecursionError", "RuntimeError", "StopIteration", "StopAsyncIteration",
    "GeneratorExit", "SystemExit", "KeyboardInterrupt", "AssertionError",
    "NotImplementedError", "ArithmeticError", "LookupError",
    "SyntaxError", "IndentationError", "TabError", "UnboundLocalError",
    "ConnectionRefusedError", "ConnectionResetError", "ConnectionAbortedError",
    "ConnectionError", "TimeoutError", "BrokenPipeError", "BlockingIOError",
    "InterruptedError", "ChildProcessError", "ProcessLookupError",
    "DeprecationWarning", "FutureWarning", "RuntimeWarning",
    "SyntaxWarning", "ResourceWarning", "UnicodeWarning",
    "BytesWarning", "UserWarning", "PendingDeprecationWarning",
    "Exception", "BaseException", "Warning",
    # Django
    "ImproperlyConfigured", "ObjectDoesNotExist", "MultipleObjectsReturned",
    "FieldError", "ValidationError", "IntegrityError",
    # SQLAlchemy / banco
    "OperationalError", "ProgrammingError", "InterfaceError",
    "DatabaseError", "DataError", "InternalError",
    # requests / httpx
    "ConnectionError", "HTTPError", "Timeout", "TooManyRedirects",
    "RequestException", "ConnectTimeout", "ReadTimeout",
})

_RE_NOME_ERRO = re.compile(
    r'\b(' + '|'.join(re.escape(e) for e in _NOMES_ERRO) + r')\b'
)

# ── Cofre global da sessão de tradução ────────────────────────────────────────
# Cada chamada a proteger() cria um cofre novo e independente.

class _Cofre:
    """Armazena todos os tokens gerados numa única tradução."""
    __slots__ = ("_dados", "_contador")

    def __init__(self):
        self._dados: dict[str, str] = {}
        self._contador = 0

    def _gerar(self, template: str, valor: str) -> str:
        token = template.format(i=self._contador)
        self._dados[token] = valor
        self._contador += 1

        return token

    def token_aspas(self, valor: str) -> str:

        return self._gerar(_TOKEN_ASPAS, valor)

    def token_caminho(self, valor: str) -> str:

        return self._gerar(_TOKEN_CAMINHO, valor)

    def token_versao(self, valor: str) -> str:

        return self._gerar(_TOKEN_VERSAO, valor)

    def token_pacote(self, valor: str) -> str:

        return self._gerar(_TOKEN_PACOTE, valor)

    def token_linha(self, valor: str) -> str:

        return self._gerar(_TOKEN_LINHA, valor)

    def token_erro(self, valor: str) -> str:

        return self._gerar(_TOKEN_ERRO, valor)

    def restaurar(self, texto: str) -> str:
        for token, valor in self._dados.items():
            texto = texto.replace(token, valor)

        return texto

    @property
    def dados(self) -> dict:

        return dict(self._dados)

# ── Etapa A — roda antes de tudo ─────────────────────────────────────────────

def normalizar_underscores(texto: str) -> str:
    """
    Converte underscores isolados em espaços.

    Preserva:
        - underscores dentro de identificadores  (win_amd64, __init__, file_name)
        - underscores duplos                     (__init__ → intocado)
        - underscores dentro de aspas            (já protegidos antes)

    Converte:
        - underscores ISOLADOS (sem letra/dígito/_ em nenhum dos lados)
          Exemplo: "erro _ grave" → "erro   grave"

    Nota: underscores em nomes de pacote/arquivo (win_amd64.whl, no_such_file)
    NÃO são convertidos aqui. Variantes com underscore de mensagens do OS são
    tratadas explicitamente na Camada 1.

    Exemplo:
        'a _ b'     → 'a   b'   (underscore isolado)
        '__init__'  → '__init__' (preservado)
        'win_amd64' → 'win_amd64' (preservado — nome de pacote)
    """

    # Mantém conservador: só converte underscores sem caractere de palavra em nenhum lado
    return re.sub(r'(?<!\w)_(?!\w)', ' ', texto)

# ── Etapa B — roda antes da Camada 3 ─────────────────────────────────────────

# ⚠️  função grande (62 linhas)
def proteger(texto: str) -> tuple[str, _Cofre]:
    """
    Protege todo conteúdo que NÃO deve ser traduzido pela Camada 3.

    Ordem de proteção (importa — aspas primeiro):
        1. Aspas simples e duplas   → protege conteúdo e caminhos entre aspas
        2. Caminhos Windows/Unix    → fora de aspas
        3. Linhas de código         → indentadas no traceback
        4. Nomes de erro Python     → NameError, TypeError...
        5. Pacotes pip              → requests-2.28.0 (antes da versão)
        6. Versões numéricas        → 3.11.2, v2.0.1

    Retorna (texto_com_tokens, cofre).
    O cofre é passado para camada4_pos.restaurar().
    """
    cofre = _Cofre()

    # 1. Aspas simples — protege PRIMEIRO para que caminhos dentro de aspas fiquem seguros
    texto = re.sub(
        r"'[^'\n]*'",
        lambda m: cofre.token_aspas(m.group(0)), texto,
    )
    # 1b. Aspas duplas
    texto = re.sub(
        r'"[^"\n]*"',
        lambda m: cofre.token_aspas(m.group(0)), texto,
    )

    # 2. Caminhos Windows fora de aspas
    texto = _RE_CAMINHO_WIN.sub(
        lambda m: cofre.token_caminho(m.group(0)), texto
    )

    # 3. Caminhos Unix fora de aspas (2+ segmentos)
    def _proteger_unix(m: re.Match) -> str:
        v = m.group(0)

        return cofre.token_caminho(v) if v.count("/") >= 2 else v

    texto = _RE_CAMINHO_UNIX.sub(_proteger_unix, texto)

    # 4. Linhas de código indentadas no traceback
    texto = _RE_LINHA_CODIGO.sub(
        lambda m: cofre.token_linha(m.group(0)), texto
    )

    # 5. Nomes de classes de erro Python
    texto = _RE_NOME_ERRO.sub(
        lambda m: cofre.token_erro(m.group(0)), texto
    )

    # 6. Pacotes pip sem aspas (antes da versão para pegar requests-2.28.0 inteiro)
    texto = _RE_PACOTE.sub(
        lambda m: cofre.token_pacote(m.group(0)), texto
    )

    # 7. Versões numéricas soltas
    texto = _RE_VERSAO.sub(
        lambda m: cofre.token_versao(m.group(0)), texto
    )

    return texto, cofre
