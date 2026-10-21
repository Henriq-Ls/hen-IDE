# 📁 _TERMINAIS_/core.py
from PySide6.QtCore import QProcess

class GerenciadorProcesso:
    def __init__(self, saida_callback):
        self.processo = QProcess()
        self.saida_callback = saida_callback
        self.processo.readyReadStandardOutput.connect(self.ler_saida)
        self.processo.readyReadStandardError.connect(self.ler_saida)
        self.processo.finished.connect(self.finalizado)

    def executar(self, comando):
        if self.processo.state() != QProcess.NotRunning:
            self.processo.kill()

        self.processo.start("cmd", ["/c", comando])

    def ler_saida(self):
        saida = self.processo.readAllStandardOutput().data().decode()
        erro = self.processo.readAllStandardError().data().decode()
        if saida:
            self.saida_callback(saida)
        if erro:
            self.saida_callback(erro)

    def finalizado(self):
        self.saida_callback("\n[processo finalizado]\n")
