# _EDITOR_/Mult_Linguas/JavaScript/__init__.py
"""
JavaScriptProvider — suporte para JS/TS/JSX/TSX.

Extensões CSS/SCSS removidas deste provider (agora em CSS/__init__.py)
para que tenham outline_mode='none' em vez de 'tree_js'.
"""
from __future__ import annotations
import re

from PySide6.QtGui import QSyntaxHighlighter, QTextDocument

from _EDITOR_.Mult_Linguas.Base.provider import LanguageProvider

# Linha é dobrável se termina em { ou [ (bloco de função, objeto, array)
_RE_JS_FOLD = re.compile(r"[{\[]\s*$")


class JavaScriptProvider(LanguageProvider):
    extensions    = ['.js', '.ts', '.jsx', '.tsx']
    name          = 'JavaScript'

    outline_mode  = 'tree_js'
    lint          = False
    autocomplete  = 'none'

    # Execução — apenas JS/TS/JSX/TSX
    can_run       = True
    run_extensoes = ['.js', '.jsx', '.ts', '.tsx']

    # barra inferior do Outline
    status_rotulo_a = 'Função'
    status_rotulo_b = ''
    mostrar_erros   = False
    rotulo_erros    = ''

    def create_highlighter(self, document: QTextDocument) -> QSyntaxHighlighter:
        from _EDITOR_.Mult_Linguas.JavaScript.realce import RealceSintaxeJS
        from _CONFIGURA_ import gerenciador_tema
        return RealceSintaxeJS(document, gerenciador_tema.tema_global().dados())

    def folding_fn(self, texto: str, ext: str) -> bool:
        return bool(_RE_JS_FOLD.search(texto))


LANGUAGE_PROVIDER = JavaScriptProvider()
