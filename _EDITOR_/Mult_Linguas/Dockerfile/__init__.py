# _EDITOR_/Mult_Linguas/Dockerfile/__init__.py
"""
DockerfileProvider — suporte para Dockerfile.

Realce: RealceSintaxeDockerfile (FROM/RUN/COPY/ENV/ARG/etc.).
Outline: 'none' — sem árvore estrutural.
Execução: can_run=False — requer Docker instalado (futuro: IMP-D).

NOTA: A extensão .dockerfile cobre 'app.dockerfile', 'dev.dockerfile' etc.
      O arquivo bare 'Dockerfile' (sem extensão) ainda não é reconhecido
      automaticamente — requer matching por nome de arquivo (futuro).
"""
from __future__ import annotations
import re

from PySide6.QtGui import QSyntaxHighlighter, QTextDocument

from _EDITOR_.Mult_Linguas.Base.provider import LanguageProvider

# Linha é dobrável se termina com backslash (continuação de instrução multi-linha)
_RE_DOCKER_FOLD = re.compile(r"\\+\s*$")


class DockerfileProvider(LanguageProvider):
    extensions    = ['.dockerfile']
    name          = 'Dockerfile'

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
        from _EDITOR_.Mult_Linguas.Dockerfile.realce import RealceSintaxeDockerfile
        from _CONFIGURA_ import gerenciador_tema
        return RealceSintaxeDockerfile(document, gerenciador_tema.tema_global().dados())

    def folding_fn(self, texto: str, ext: str) -> bool:
        return bool(_RE_DOCKER_FOLD.search(texto))


LANGUAGE_PROVIDER = DockerfileProvider()
