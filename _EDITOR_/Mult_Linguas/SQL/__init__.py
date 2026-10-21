# _EDITOR_/Mult_Linguas/SQL/__init__.py
"""
SQLProvider — suporte inicial para SQL.

Fase inicial:
  - Sem realce de sintaxe (_RealceInerte)
  - Sem lint, sem autocomplete
  - Outline vazio (outline_mode='none')
  - Folding em blocos BEGIN...END e abertura de parênteses ( multi-linha

Fase futura:
  - Realce via RealceSintaxeSQL (keywords, strings, comentários)
  - Outline listando CREATE TABLE / VIEW / PROCEDURE por nome
"""
from __future__ import annotations
import re
from PySide6.QtGui import QTextDocument

from PySide6.QtGui import QSyntaxHighlighter, QTextDocument
from _EDITOR_.Mult_Linguas.Base.provider import LanguageProvider

# Linha é dobrável se abre um bloco SQL:
#   BEGIN, CASE, ou linha terminando em ( (início de lista de colunas/parâmetros)
_RE_SQL_FOLD = re.compile(
    r'(?i)^\s*(BEGIN\b|CASE\b|.*\(\s*$)'
)


class SQLProvider(LanguageProvider):
    extensions    = ['.sql']
    name          = 'SQL'

    outline_mode  = 'tree_sql'
    lint          = False
    autocomplete  = 'none'

    can_run       = False
    run_extensoes = []

    # barra inferior do Outline
    status_rotulo_a = 'Objeto'
    status_rotulo_b = ''
    mostrar_erros   = False
    rotulo_erros    = ''

    def create_highlighter(self, document: QTextDocument) -> QSyntaxHighlighter:
        from _EDITOR_.Mult_Linguas.SQL.realce import RealceSintaxeSQL
        from _CONFIGURA_ import gerenciador_tema
        return RealceSintaxeSQL(document, gerenciador_tema.tema_global().dados())

    def folding_fn(self, texto: str, ext: str) -> bool:
        return bool(_RE_SQL_FOLD.match(texto))


LANGUAGE_PROVIDER = SQLProvider()
