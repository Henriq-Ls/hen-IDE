# _EDITOR_/Mult_Linguas/Texto/__init__.py
from __future__ import annotations
import re
from PySide6.QtGui import QTextDocument

from _EDITOR_.Mult_Linguas.Base.provider import LanguageProvider, _RealceInerte

# Linha de texto pura é dobrável se não tem recuo E tem conteúdo —
# funciona como "título de seção" para o bloco recuado abaixo.
_RE_TXT_FOLD = re.compile(r'^\S.+')


class TextoProvider(LanguageProvider):
    extensions    = [
        '.txt', '.log', '.csv',
        '.ini', '.cfg', '.conf', '.toml',
    ]
    name          = 'Texto'
    outline_mode  = 'none'
    lint          = False
    autocomplete  = 'none'
    spell_check   = True   # verifica texto puro completo em PT-BR

    # barra inferior do Outline — tudo oculto
    status_rotulo_a = ''
    status_rotulo_b = ''
    mostrar_erros   = False
    rotulo_erros    = ''

    def create_highlighter(self, document: QTextDocument) -> None:
        return _RealceInerte(document)

    def folding_fn(self, texto: str, ext: str, proximo_texto: str = '') -> bool:
        """Linhas sem recuo com conteúdo são dobráveis SOMENTE se a próxima
        linha está indentada — evita seta em cada linha do arquivo."""
        if not _RE_TXT_FOLD.match(texto):
            return False
        # Há próximo e ele começa com espaço/tab → bloco indentado abaixo
        return bool(proximo_texto) and (
            proximo_texto.startswith(' ') or proximo_texto.startswith('\t')
        )


LANGUAGE_PROVIDER = TextoProvider()
