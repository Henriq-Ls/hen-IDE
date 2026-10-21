# 📁 _EDITOR_/Core/gerenciador_arquivo.py
from PySide6.QtWidgets import QMessageBox, QFileDialog

class GerenciadorArquivo:
    def __init__(self, editor):
        self.editor = editor

    def abrir(self, caminho):
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                conteudo = f.read()

            # IMP-01: desabilita undo/redo durante a carga -- Ctrl+Z nao
            # deve desfazer a abertura do arquivo, so edicoes feitas pelo usuario.
            self.editor.setUndoRedoEnabled(False)
            self.editor.setPlainText(conteudo)
            self.editor.setUndoRedoEnabled(True)
            self.editor.estado.definir_caminho(caminho)
            self.editor.estado.definir_texto_original(conteudo)

            return True

        except Exception as e:
            QMessageBox.critical(None, "Erro", f"Erro ao abrir:\n{e}")

            return False

    def salvar(self, caminho=None):
        if caminho is None:
            caminho, _ = QFileDialog.getSaveFileName(
                self.editor, "Salvar Arquivo", "", "Todos (*.*)"
            )
            if not caminho:

                return False

        try:
            with open(caminho, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())

            self.editor.estado.definir_caminho(caminho)

            return True

        except Exception as e:
            QMessageBox.critical(None, "Erro", f"Erro ao salvar:\n{e}")

            return False
