# 📁 _APP_/janela_flutuante.py
"""
JanelaEditorFlutuante — janela OS independente criada quando o usuário
arrasta uma aba para fora da barra de abas.

Comportamento:
  • Fechar a janela (X) → devolve o editor ao TabWidget principal (não perde o arquivo).
  • Botão "← Principal" → mesmo efeito, mais explícito.
  • O título exibe o nome do arquivo + '*' quando há modificações não salvas.
  • Ctrl+S salva normalmente (o editor já tem o atalho interno).
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui  import QColor, QPalette, QIcon

class JanelaEditorFlutuante(QWidget):
    """Janela separada contendo um editor de código."""

    # Emitido quando a janela deve devolver o editor ao TabWidget principal.
    devolver_editor = Signal(object)   # editor (CodeEditor)

    def __init__(self, editor, caminho: str, tab_widget_ref, parent=None):
        super().__init__(parent, Qt.Window)
        self._editor          = editor
        self._tab_widget_ref  = tab_widget_ref   # referência fraca (não usado para parenting)
        self._fechando        = False

        # ── Título da janela ────────────────────────────────────────────────
        self._atualizar_titulo()
        self.setMinimumSize(400, 300)
        self.resize(820, 600)
        self.setAttribute(Qt.WA_DeleteOnClose, False)   # NÃO deletar ao fechar — editor será reparentado

        # ── Layout ──────────────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Barra topo mínima
        barra = QWidget()
        barra.setFixedHeight(32)
        barra.setObjectName("BarraFlutuante")
        barra.setStyleSheet("""
            QWidget#BarraFlutuante {
                background: #0f1117;
                border-bottom: 1px solid #2a2f3d;
            }
        """)
        barra_lay = QHBoxLayout(barra)
        barra_lay.setContentsMargins(8, 0, 8, 0)
        barra_lay.setSpacing(6)

        self._lbl_nome = QLabel()
        self._lbl_nome.setStyleSheet("color: #c0c8d8; font-size: 12px;")
        barra_lay.addWidget(self._lbl_nome)
        barra_lay.addStretch()

        btn_voltar = QPushButton("← Principal")
        btn_voltar.setFixedHeight(22)
        btn_voltar.setStyleSheet("""
            QPushButton {
                background: #1e2a3a;
                color: #7eb8e8;
                border: 1px solid #2a4060;
                border-radius: 3px;
                padding: 0 8px;
                font-size: 11px;
            }
            QPushButton:hover { background: #264f78; color: #ffffff; }
        """)
        btn_voltar.clicked.connect(self._devolver)
        barra_lay.addWidget(btn_voltar)

        root.addWidget(barra)
        root.addWidget(editor)
        # setParent(None) em destacar_aba() marca o widget como oculto.
        # Sem show() explicito aqui o editor aparece invisivel na janela.
        editor.show()

        # ── Atualiza título quando editor muda ────────────────────────────
        if hasattr(editor, 'textChanged'):
            editor.textChanged.connect(self._ao_texto_mudar)
        if hasattr(editor, 'arquivo_salvo'):
            editor.arquivo_salvo.connect(self._atualizar_titulo)

        self._atualizar_lbl()

    # ── Título da janela (barra do SO) ──────────────────────────────────────
    def _atualizar_titulo(self):
        fp   = getattr(self._editor, 'file_path', None) if hasattr(self, '_editor') else None
        nome = os.path.basename(fp) if fp else "Novo"
        mod  = (hasattr(self._editor, 'is_modified') and self._editor.is_modified()) if hasattr(self, '_editor') else False
        self.setWindowTitle(f"{'*' if mod else ''}{nome} — hein")

    def _atualizar_lbl(self):
        fp   = getattr(self._editor, 'file_path', None)
        nome = os.path.basename(fp) if fp else "Novo"
        mod  = hasattr(self._editor, 'is_modified') and self._editor.is_modified()
        self._lbl_nome.setText(f"{'● ' if mod else ''}{nome}")

    def _ao_texto_mudar(self):
        self._atualizar_titulo()
        self._atualizar_lbl()

    # ── Devolução ao principal ───────────────────────────────────────────────
    def _devolver(self):
        if self._fechando:
            return

        self._fechando = True
        # Retira o editor do layout para evitar que o QWidget o destrua
        layout = self.layout()
        if layout:
            layout.removeWidget(self._editor)
        self._editor.setParent(None)
        self.devolver_editor.emit(self._editor)
        # Fecha a janela (sem pedir devolução de novo)
        self.hide()
        QTimer.singleShot(0, self.close)

    def closeEvent(self, event):
        """Fechar a janela (X do SO) → devolve o editor, não perde o trabalho."""
        if not self._fechando:
            self._devolver()
        event.accept()
