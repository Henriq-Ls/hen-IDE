"""Editor de texto simples para arquivos que não são documentos ``.hen``.

Este editor é deliberadamente separado do :mod:`Editor_Hein`.  O Editor Hein
possui regras próprias para o formato ``.hen`` (estado, blocos embutidos,
diff e ferramentas de código); este widget atende arquivos de texto comuns
sem reutilizar nem alterar essas regras.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette, QTextCursor
from PySide6.QtWidgets import QFileDialog, QMessageBox, QPlainTextEdit


class EditorTexto(QPlainTextEdit):
    """Editor genérico para arquivos de texto do projeto."""

    arquivo_salvo = Signal(str)
    navegar_arquivo = Signal(str, int)
    arquivo_exportado = Signal(str)

    def __init__(self, parent=None, tema: dict | None = None):
        super().__init__(parent)
        self.file_path: str | None = None
        self.original_text = ""
        self._encoding = "utf-8"
        self._caminho_projeto: str | None = None
        self._projeto_path: str | None = None
        self._tamanho_fonte = 12
        self._FONTE_MIN = 6
        self._FONTE_MAX = 48
        self._tab_tamanho = 4
        self._tema_pendente = None
        self._fechar_pares = False

        self.setFocusPolicy(Qt.ClickFocus)
        self._aplicar_tema(tema)
        self.document().setModified(False)

    # ------------------------------------------------------------------
    # Arquivo
    # ------------------------------------------------------------------

    def set_file_path(self, caminho: str):
        if not caminho:
            return False
        self.file_path = os.path.abspath(caminho)
        self.original_text = self.toPlainText()
        self.document().setModified(False)
        return True

    def is_modified(self) -> bool:
        return self.toPlainText() != self.original_text

    @staticmethod
    def _decodificar(conteudo: bytes) -> tuple[str, str]:
        """Decodifica texto sem aceitar bytes nulos típicos de binários."""
        if b"\x00" in conteudo:
            raise UnicodeError("o arquivo contém bytes nulos e parece ser binário")

        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                return conteudo.decode(encoding), encoding
            except UnicodeDecodeError:
                continue
        raise UnicodeError("não foi possível decodificar o arquivo como texto")

    def load_file(self, caminho: str) -> bool:
        if not caminho:
            return False
        caminho = os.path.abspath(caminho)
        try:
            with open(caminho, "rb") as arquivo:
                conteudo, encoding = self._decodificar(arquivo.read())
        except Exception as erro:
            QMessageBox.critical(self, "Erro ao abrir", str(erro))
            return False

        self.setPlainText(conteudo)
        self._encoding = encoding
        self.set_file_path(caminho)
        self.document().setModified(False)
        return True

    def save_file(self, caminho: str | None = None) -> bool:
        """Salva no caminho atual; só mostra ``Salvar como`` para uma aba nova."""
        if caminho is None:
            caminho = self.file_path

        if not caminho:
            caminho, _ = QFileDialog.getSaveFileName(
                self,
                "Salvar Como",
                self._diretorio_inicial_salvar(),
                "Todos os arquivos (*)",
            )
            if not caminho:
                return False
            try:
                from PySide6.QtCore import QSettings

                QSettings("hen", "hen_IDE").setValue(
                    "ultima_pasta_salvar_editor", os.path.dirname(caminho)
                )
            except Exception:
                pass

        caminho = os.path.abspath(caminho)
        encoding = self._encoding or "utf-8"
        try:
            dados = self.toPlainText().encode(encoding)
            with open(caminho, "wb") as arquivo:
                arquivo.write(dados)
        except (OSError, UnicodeEncodeError) as erro:
            QMessageBox.critical(self, "Erro ao salvar", str(erro))
            return False

        self.set_file_path(caminho)
        self.arquivo_salvo.emit(caminho)
        return True

    def _diretorio_inicial_salvar(self) -> str:
        try:
            from PySide6.QtCore import QSettings

            settings = QSettings("hen", "hen_IDE")
            return (
                getattr(self.window(), "current_project_path", "")
                or settings.value("ultima_pasta_salvar_editor", "")
                or ""
            )
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Integração com a janela principal
    # ------------------------------------------------------------------

    def set_projeto(self, caminho: str | None):
        self._caminho_projeto = caminho
        self._projeto_path = caminho

    def encerrar_threads_bg(self):
        """Compatibilidade com o ciclo de vida dos editores da IDE."""

    def atualizar_tema(self, tema: dict | None = None):
        self._aplicar_tema(tema)

    def _aplicar_tema(self, tema: dict | None = None):
        """Aplica uma aparência escura neutra, sem depender do Editor Hein."""
        paleta = self.palette()
        paleta.setColor(QPalette.Base, QColor("#10151c"))
        paleta.setColor(QPalette.Text, QColor("#d7dde8"))
        paleta.setColor(QPalette.Highlight, QColor("#264f78"))
        paleta.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        self.setPalette(paleta)
        self.setStyleSheet(
            "QPlainTextEdit { border: 0; padding: 8px; "
            "selection-background-color: #264f78; }"
        )

    # ------------------------------------------------------------------
    # Operações comuns dos atalhos. O editor genérico não possui recursos
    # específicos do formato .hen, mas continua utilizável pelo menu Editar.
    # ------------------------------------------------------------------

    def ir_para_linha(self, linha: int):
        bloco = self.document().findBlockByNumber(max(0, int(linha) - 1))
        if not bloco.isValid():
            return
        cursor = QTextCursor(bloco)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def centralizar_linha_cursor(self):
        self.centerCursor()

    def aumentar_fonte(self):
        self._alterar_fonte(1)

    def diminuir_fonte(self):
        self._alterar_fonte(-1)

    def resetar_fonte(self):
        self._tamanho_fonte = 12
        self._aplicar_fonte()

    def _alterar_fonte(self, delta: int):
        self._tamanho_fonte = max(
            self._FONTE_MIN, min(self._FONTE_MAX, self._tamanho_fonte + delta)
        )
        self._aplicar_fonte()

    def _aplicar_fonte(self):
        fonte = QFont(self.font())
        fonte.setPointSize(self._tamanho_fonte)
        self.setFont(fonte)

    def comentar_linha(self):
        """Comenta linhas usando ``#``, adequado para texto de código comum."""
        cursor = self.textCursor()
        inicio = cursor.selectionStart()
        fim = cursor.selectionEnd()
        cursor.setPosition(inicio)
        cursor.movePosition(QTextCursor.StartOfBlock)
        inicio = cursor.position()
        cursor.setPosition(fim)
        cursor.movePosition(QTextCursor.EndOfBlock)
        fim = cursor.position()
        cursor.setPosition(inicio)
        cursor.beginEditBlock()
        while cursor.position() <= fim:
            cursor.movePosition(QTextCursor.StartOfBlock)
            cursor.insertText("# ")
            if not cursor.movePosition(QTextCursor.NextBlock):
                break
        cursor.endEditBlock()

    def duplicar_linha(self):
        cursor = self.textCursor()
        texto = cursor.block().text()
        cursor.movePosition(QTextCursor.EndOfBlock)
        cursor.insertText("\n" + texto)

    def deletar_linha(self):
        cursor = self.textCursor()
        cursor.select(QTextCursor.LineUnderCursor)
        cursor.removeSelectedText()
        if not cursor.atEnd():
            cursor.deleteChar()

    def mover_linha_cima(self):
        self._mover_linha(-1)

    def mover_linha_baixo(self):
        self._mover_linha(1)

    def _mover_linha(self, direcao: int):
        cursor = self.textCursor()
        bloco = cursor.block()
        alvo = bloco.previous() if direcao < 0 else bloco.next()
        if not alvo.isValid():
            return
        texto_atual = bloco.text()
        texto_alvo = alvo.text()
        pos_coluna = cursor.positionInBlock()
        cursor.beginEditBlock()
        if direcao < 0:
            cursor.setPosition(alvo.position())
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            cursor.insertText(texto_atual)
            cursor.setPosition(bloco.position())
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            cursor.insertText(texto_alvo)
            novo = alvo.position() + min(pos_coluna, len(texto_atual))
        else:
            cursor.setPosition(bloco.position())
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            cursor.insertText(texto_alvo)
            cursor.setPosition(alvo.position())
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            cursor.insertText(texto_atual)
            novo = bloco.position() + min(pos_coluna, len(texto_atual))
        cursor.endEditBlock()
        cursor.setPosition(max(0, novo))
        self.setTextCursor(cursor)

    def recolher_bloco(self):
        return None

    def expandir_bloco(self):
        return None

    def recolher_tudo(self):
        return None

    def expandir_tudo(self):
        return None

    def adicionar_cursor_acima(self):
        return None

    def adicionar_cursor_abaixo(self):
        return None

    def selecionar_todas_ocorrencias(self):
        return None

    def selecionar_proxima_ocorrencia(self):
        return None

    def _atualizar_code_lens(self):
        return None


__all__ = ["EditorTexto"]