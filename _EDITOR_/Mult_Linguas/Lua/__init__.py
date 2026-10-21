# _EDITOR_/Mult_Linguas/Lua/__init__.py
from __future__ import annotations
import re
from PySide6.QtGui import QSyntaxHighlighter, QTextDocument

from _EDITOR_.Mult_Linguas.Base.provider import LanguageProvider

_RE_LUA_FOLD = re.compile(
    r'^\s*('
    r'function\b'
    r'|if\b.*\bthen\s*$'
    r'|\bdo\s*$'
    r'|repeat\s*$'
    r'|for\b.*\bdo\s*$'
    r'|while\b.*\bdo\s*$'
    r')'
)


class LuaProvider(LanguageProvider):
    extensions    = ['.lua']
    name          = 'Lua'

    outline_mode  = 'tree_lua'
    lint          = False
    autocomplete  = 'none'

    can_run       = True
    run_extensoes = ['.lua']

    status_rotulo_a = ''
    status_rotulo_b = ''
    mostrar_erros   = False
    rotulo_erros    = ''

    def create_highlighter(self, document: QTextDocument) -> QSyntaxHighlighter:
        from _EDITOR_.Mult_Linguas.Lua.realce import RealceSintaxeLua
        from _CONFIGURA_ import gerenciador_tema
        tema = gerenciador_tema.tema_global().dados()
        return RealceSintaxeLua(document, tema)

    def folding_fn(self, texto: str, ext: str) -> bool:
        return bool(_RE_LUA_FOLD.match(texto))


LANGUAGE_PROVIDER = LuaProvider()
