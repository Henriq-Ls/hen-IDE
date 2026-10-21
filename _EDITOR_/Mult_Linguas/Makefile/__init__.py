# _EDITOR_/Mult_Linguas/Makefile/__init__.py
"""
MakefileProvider — suporte para Makefile.

Realce: RealceSintaxeMakefile (targets, variáveis $(VAR), comentários #).
Outline: tree_make — lista todos os targets disponíveis.
Execução: can_run=True — executa com make -f $ARQUIVO.

NOTA: O arquivo bare 'Makefile'/'GNUmakefile' (sem extensão) não é
      reconhecido automaticamente — requer matching por nome (futuro).
      Cobertura atual: .mk e .makefile
"""
from __future__ import annotations
import re

from PySide6.QtGui import QSyntaxHighlighter, QTextDocument

from _EDITOR_.Mult_Linguas.Base.provider import LanguageProvider

# Linha é dobrável se é um target Makefile:
#   - não começa com TAB (não é receita)
#   - não é comentário
#   - termina com : (com ou sem dependências)
_RE_MAKE_FOLD = re.compile(r"^[^\t#\s][^#]*:\s*(\S.*)?$")


class MakefileProvider(LanguageProvider):
    extensions    = ['.mk', '.makefile']
    name          = 'Makefile'

    outline_mode  = 'tree_make'
    lint          = False
    autocomplete  = 'none'

    can_run       = True
    run_extensoes = ['.mk', '.makefile']

    # barra inferior do Outline
    status_rotulo_a = 'Target'
    status_rotulo_b = ''
    mostrar_erros   = False
    rotulo_erros    = ''

    def create_highlighter(self, document: QTextDocument) -> QSyntaxHighlighter:
        from _EDITOR_.Mult_Linguas.Makefile.realce import RealceSintaxeMakefile
        from _CONFIGURA_ import gerenciador_tema
        return RealceSintaxeMakefile(document, gerenciador_tema.tema_global().dados())

    def folding_fn(self, texto: str, ext: str) -> bool:
        return bool(_RE_MAKE_FOLD.search(texto))


LANGUAGE_PROVIDER = MakefileProvider()
