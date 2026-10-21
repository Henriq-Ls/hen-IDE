# _EDITOR_/Mult_Linguas/HTML/__init__.py
from __future__ import annotations
import re
from PySide6.QtGui import QSyntaxHighlighter, QTextDocument

from _EDITOR_.Mult_Linguas.Base.provider import LanguageProvider

_RE_HTML_FOLD = re.compile(r'^\s*<[a-zA-Z][^/!][^>]*(?<!/)>')


class HTMLProvider(LanguageProvider):
    extensions       = ['.html', '.htm']
    name             = 'HTML'
    outline_mode     = 'preview_html'
    lint             = False
    autocomplete     = 'none'

    # F1 abre HTMLVisorTerminal (botão de abrir no navegador + auto-atualizar)
    can_run       = True
    run_extensoes = ['.html', '.htm']

    # barra inferior do Outline — tudo oculto (outline em modo preview)
    status_rotulo_a  = ''
    status_rotulo_b  = ''
    mostrar_erros    = False
    rotulo_erros     = ''

    def create_highlighter(self, document: QTextDocument) -> QSyntaxHighlighter:
        from _EDITOR_.Mult_Linguas.HTML.realce import RealceSintaxeHTML
        from _CONFIGURA_ import gerenciador_tema
        tema = gerenciador_tema.tema_global().dados()
        return RealceSintaxeHTML(document, tema)

    def folding_fn(self, texto: str, ext: str) -> bool:
        return bool(_RE_HTML_FOLD.match(texto))


LANGUAGE_PROVIDER = HTMLProvider()
