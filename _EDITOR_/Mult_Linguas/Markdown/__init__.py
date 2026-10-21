# _EDITOR_/Mult_Linguas/Markdown/__init__.py
from __future__ import annotations
from PySide6.QtGui import QTextDocument

from PySide6.QtGui import QSyntaxHighlighter, QTextDocument
from _EDITOR_.Mult_Linguas.Base.provider import LanguageProvider


class MarkdownProvider(LanguageProvider):
    extensions       = ['.md', '.markdown']
    name             = 'Markdown'
    outline_mode     = 'preview_md'
    lint             = False
    autocomplete     = 'none'
    spell_check      = True   # verifica texto MD em PT-BR (pula blocos de código)

    # barra inferior do Outline
    status_rotulo_a  = 'Seção'
    status_rotulo_b  = ''
    mostrar_erros    = False
    rotulo_erros     = ''

    def create_highlighter(self, document: QTextDocument) -> QSyntaxHighlighter:
        from _EDITOR_.Mult_Linguas.Markdown.realce import RealceSintaxeMD
        from _CONFIGURA_ import gerenciador_tema
        return RealceSintaxeMD(document, gerenciador_tema.tema_global().dados())

    def folding_fn(self, texto: str, ext: str) -> bool:
        # headings (#, ##, ###...) são pontos de dobramento naturais
        return texto.lstrip().startswith('#')


LANGUAGE_PROVIDER = MarkdownProvider()
