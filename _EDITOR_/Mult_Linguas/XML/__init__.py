# _EDITOR_/Mult_Linguas/XML/__init__.py
from __future__ import annotations
import re
from PySide6.QtGui import QTextDocument

from PySide6.QtGui import QSyntaxHighlighter, QTextDocument
from _EDITOR_.Mult_Linguas.Base.provider import LanguageProvider

_RE_XML_FOLD = re.compile(r'^\s*<[a-zA-Z][^/!][^>]*(?<!/)>')


class XMLProvider(LanguageProvider):
    extensions       = ['.xml']
    name             = 'XML'
    outline_mode     = 'tree_xml'
    lint             = False
    autocomplete     = 'none'

    # barra inferior do Outline
    status_rotulo_a  = 'Tag'
    status_rotulo_b  = ''
    mostrar_erros    = False
    rotulo_erros     = ''

    def create_highlighter(self, document: QTextDocument) -> QSyntaxHighlighter:
        from _EDITOR_.Mult_Linguas.XML.realce import RealceSintaxeXML
        from _CONFIGURA_ import gerenciador_tema
        return RealceSintaxeXML(document, gerenciador_tema.tema_global().dados())

    def folding_fn(self, texto: str, ext: str) -> bool:
        return bool(_RE_XML_FOLD.match(texto))


LANGUAGE_PROVIDER = XMLProvider()
