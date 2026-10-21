# _EDITOR_/Mult_Linguas/CSS/__init__.py
"""
CSSProvider — suporte para CSS/SCSS/SASS/LESS.

Realce: reutiliza RealceSintaxeJS (cores de seletores, propriedades e valores).
Outline: 'none' — tree_js não captura sintaxe CSS; outline CSS planejado para futuro.
Execução: can_run=False — arquivos CSS não são executáveis diretamente.

Pendente futuro: 'tree_css' extraindo seletores, @keyframes, @media, @mixin.
"""
from __future__ import annotations
import re

from PySide6.QtGui import QSyntaxHighlighter, QTextDocument

from _EDITOR_.Mult_Linguas.Base.provider import LanguageProvider

# Linha é dobrável se termina em { (regra CSS, @media, @keyframe, etc.)
_RE_CSS_FOLD = re.compile(r"\{\s*$")


class CSSProvider(LanguageProvider):
    extensions    = ['.css', '.scss', '.sass', '.less']
    name          = 'CSS'

    outline_mode  = 'none'
    lint          = False
    autocomplete  = 'none'

    can_run       = False
    run_extensoes = []

    # barra inferior do Outline — tudo oculto
    status_rotulo_a = ''
    status_rotulo_b = ''
    mostrar_erros   = False
    rotulo_erros    = ''

    def create_highlighter(self, document: QTextDocument) -> QSyntaxHighlighter:
        # Reutiliza o realce JS — cobre variáveis $, strings, comentários //
        from _EDITOR_.Mult_Linguas.JavaScript.realce import RealceSintaxeJS
        from _CONFIGURA_ import gerenciador_tema
        return RealceSintaxeJS(document, gerenciador_tema.tema_global().dados())

    def folding_fn(self, texto: str, ext: str) -> bool:
        return bool(_RE_CSS_FOLD.search(texto))


LANGUAGE_PROVIDER = CSSProvider()
