# _EDITOR_/Mult_Linguas/YAML/__init__.py
from __future__ import annotations
from PySide6.QtGui import QTextDocument

from PySide6.QtGui import QSyntaxHighlighter, QTextDocument
from _EDITOR_.Mult_Linguas.Base.provider import LanguageProvider


class YAMLProvider(LanguageProvider):
    extensions       = ['.yml', '.yaml']
    name             = 'YAML'
    outline_mode     = 'tree_yaml'
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
        from _EDITOR_.Mult_Linguas.YAML.realce import RealceSintaxeYAML
        from _CONFIGURA_ import gerenciador_tema
        return RealceSintaxeYAML(document, gerenciador_tema.tema_global().dados())

    def folding_fn(self, texto: str, ext: str) -> bool:
        s = texto.rstrip()
        return bool(s) and s.endswith(':') and not s.lstrip().startswith('#')


LANGUAGE_PROVIDER = YAMLProvider()
