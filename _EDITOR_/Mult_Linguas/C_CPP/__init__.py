# _EDITOR_/Mult_Linguas/C_CPP/__init__.py
"""
CCppProvider — suporte para C e C++.

Realce: RealceSintaxeC (keywords, tipos, strings, comentários, diretivas #).
Outline: tree_c — funções, structs, classes, enums, namespaces.
Execução: can_run=False — requer compilação via gcc/g++/clang (futuro).
"""
from __future__ import annotations
import re

from PySide6.QtGui import QSyntaxHighlighter, QTextDocument

from _EDITOR_.Mult_Linguas.Base.provider import LanguageProvider

# Linha é dobrável se termina com { (abre bloco C/C++)
_RE_C_FOLD = re.compile(r"\{\s*$")


class CCppProvider(LanguageProvider):
    extensions    = ['.c', '.cpp', '.h', '.hpp', '.cc', '.cxx', '.hh']
    name          = 'C/C++'

    outline_mode  = 'tree_c'
    lint          = False
    autocomplete  = 'none'

    can_run       = False
    run_extensoes = []

    # barra inferior do Outline
    status_rotulo_a = 'Símbolo'
    status_rotulo_b = ''
    mostrar_erros   = False
    rotulo_erros    = ''

    def create_highlighter(self, document: QTextDocument) -> QSyntaxHighlighter:
        from _EDITOR_.Mult_Linguas.C_CPP.realce import RealceSintaxeC
        from _CONFIGURA_ import gerenciador_tema
        return RealceSintaxeC(document, gerenciador_tema.tema_global().dados())

    def folding_fn(self, texto: str, ext: str) -> bool:
        return bool(_RE_C_FOLD.search(texto))


LANGUAGE_PROVIDER = CCppProvider()
