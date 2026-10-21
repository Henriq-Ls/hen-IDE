# 📁 _TERMINAIS_/ui.py
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPlainTextEdit
from _CONFIGURA_.gerenciador_configurar import config_global
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import FONTE_MONO_FALLBACK

class TerminalUI(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.ui = self          # ← isso aqui, o gerenciador busca por .ui
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.prompt = ">>> "
        self._aplicar_config()

    def _aplicar_config(self):
        cfg        = config_global()
        fonte_nome = cfg.obter("terminal", "fonte",         FONTE_MONO_FALLBACK)
        tamanho    = int(cfg.obter("terminal", "tamanho_fonte", 11))
        t          = tema_global()
        fundo      = t.cor("terminal.fundo",  "#111111")
        texto      = t.cor("terminal.texto",  "#00ff00")
        self.setFont(QFont(fonte_nome, tamanho))
        self.setStyleSheet(f"background:{fundo}; color:{texto}; border:none;")

    def atualizar_tema(self, tema: dict = None):
        self._aplicar_config()

    def escrever(self, texto):
        self.appendPlainText(texto)

    def input_atual(self):

        return self.toPlainText().split("\n")[-1].replace(self.prompt, "")
