# _EDITOR_/Mult_Linguas/Shell/__init__.py
from __future__ import annotations
from PySide6.QtGui import QTextDocument

from PySide6.QtGui import QSyntaxHighlighter, QTextDocument
from _EDITOR_.Mult_Linguas.Base.provider import LanguageProvider


class ShellProvider(LanguageProvider):
    extensions    = [
        '.ps1', '.psm1', '.psd1',   # PowerShell
        '.sh', '.bash', '.zsh',     # Shell Unix
        '.bat', '.cmd',             # Batch Windows
    ]
    name          = 'Shell'
    outline_mode  = 'tree_sh'
    lint          = False
    autocomplete  = 'none'

    # barra inferior do Outline
    status_rotulo_a = 'Função'
    status_rotulo_b = ''
    mostrar_erros   = False
    rotulo_erros    = ''

    # Execução — .psd1 é manifesto (não executa); .sh/.bash/.zsh são Unix
    can_run       = True
    run_extensoes = ['.ps1', '.psm1', '.bat', '.cmd', '.sh', '.bash', '.zsh']

    def create_highlighter(self, document: QTextDocument) -> QSyntaxHighlighter:
        from _EDITOR_.Mult_Linguas.Shell.realce import RealceSintaxeShell
        from _CONFIGURA_ import gerenciador_tema
        return RealceSintaxeShell(document, gerenciador_tema.tema_global().dados())


LANGUAGE_PROVIDER = ShellProvider()
