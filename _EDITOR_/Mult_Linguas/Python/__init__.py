# _EDITOR_/Mult_Linguas/Python/__init__.py
from __future__ import annotations
import re
from PySide6.QtGui import QSyntaxHighlighter, QTextDocument

from _EDITOR_.Mult_Linguas.Base.provider import LanguageProvider, _RealceInerte

_RE_PY_FOLD = re.compile(
    r"^\s*(def |async def |class |if |elif |else\s*:|for |while |try\s*:|"
    r"except|finally\s*:|with )"
)


class PythonProvider(LanguageProvider):
    extensions       = ['.py', '.pyw']
    name             = 'Python'
    outline_mode     = 'python_ast'
    lint             = True
    autocomplete     = 'jedi'
    spell_check      = True   # clique do meio ou menu → verifica strings/comentários

    # barra inferior do Outline
    status_rotulo_a  = 'Classe'
    status_rotulo_b  = 'Função'
    mostrar_erros    = True
    rotulo_erros     = 'Erros'

    def create_highlighter(self, document: QTextDocument) -> QSyntaxHighlighter:
        from _EDITOR_.Mult_Linguas.Python.realce import RealceSintaxePython
        from _CONFIGURA_.gerenciador_tema import tema_global
        tema = tema_global().dados()
        return RealceSintaxePython(document, tema)

    def folding_fn(self, texto: str, ext: str) -> bool:
        return (
            bool(_RE_PY_FOLD.match(texto))
            or texto.rstrip().endswith(('[', '{'))
        )


LANGUAGE_PROVIDER = PythonProvider()
