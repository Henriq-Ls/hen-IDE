# _EDITOR_/Mult_Linguas/JSON/__init__.py
from __future__ import annotations
from PySide6.QtGui import QSyntaxHighlighter, QTextDocument

from _EDITOR_.Mult_Linguas.Base.provider import LanguageProvider


class JSONProvider(LanguageProvider):
    extensions       = ['.json']
    name             = 'JSON'
    outline_mode     = 'tree_json'
    lint             = False
    autocomplete     = 'none'

    # barra inferior do Outline
    status_rotulo_a  = 'Chave'
    status_rotulo_b  = ''
    mostrar_erros    = True
    rotulo_erros     = 'Válido'   # alterna para 'Inválido' via _ultimo_parse_ok

    # estado de parse — lido por _atualizar_barra_outline()
    _ultimo_parse_ok: bool = True

    def create_highlighter(self, document: QTextDocument) -> QSyntaxHighlighter:
        from _EDITOR_.Mult_Linguas.JSON.realce import RealceSintaxeJSON
        from _CONFIGURA_ import gerenciador_tema
        tema = gerenciador_tema.tema_global().dados()
        return RealceSintaxeJSON(document, tema)

    def folding_fn(self, texto: str, ext: str) -> bool:
        return texto.rstrip().endswith(('{', '['))


LANGUAGE_PROVIDER = JSONProvider()
