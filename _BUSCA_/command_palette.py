# 📁 _BUSCA_/command_palette.py
# coding: utf-8
"""
Command Palette — widget desativado da barra de busca.
NOTA: Este módulo foi desativado. O prefixo ">" agora é tratado diretamente
em main_window._ao_buscar_global() usando buscar_comandos() + PainelBuscaGlobal.
Ctrl+K → abre barra com ">"; ctrl-shift-p foi removido do JSON.
"""
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt
from .busca_comandos import buscar_comandos


class CommandPalette(QFrame):
    """
    Popup flutuante para acionar comandos da IDE.

    Uso (MainWindow):
        palette = CommandPalette(self)
        palette.mostrar(filtro_inicial="")
    """

    def __init__(self, janela):
        super().__init__(janela, Qt.Popup | Qt.FramelessWindowHint)
        self._janela = janela
        self._comandos = []
        self._construir_ui()

    # ── Construção ────────────────────────────────────────────────────

    def _construir_ui(self):
        self.setObjectName("command_palette")
        self.setStyleSheet("""
            #command_palette {
                background-color: #1a1a2e;
                border: 1px solid #4a90d9;
                border-radius: 6px;
            }
            QLineEdit {
                background-color: #0d0d0d;
                color: #e0e0e0;
                border: none;
                border-bottom: 1px solid #333;
                border-radius: 0;
                padding: 8px 12px;
                font-size: 14px;
            }
            QListWidget {
                background-color: #1a1a2e;
                color: #e0e0e0;
                border: none;
                font-size: 13px;
            }
            QListWidget::item { padding: 6px 12px; }
            QListWidget::item:selected { background-color: #264f78; }
            QListWidget::item:hover    { background-color: #2a2a4a; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Digite um comando…")
        self._input.setFixedWidth(420)
        layout.addWidget(self._input)

        self._lista = QListWidget()
        self._lista.setFixedWidth(420)
        self._lista.setMaximumHeight(300)
        layout.addWidget(self._lista)

        self._input.textChanged.connect(self._filtrar)
        self._input.returnPressed.connect(self._executar_selecionado)
        self._lista.itemActivated.connect(self._ao_ativar)

    # ── API pública ───────────────────────────────────────────────────

    def mostrar(self, filtro: str = ""):
        """Posiciona no centro da janela pai, preenche e exibe."""
        self._carregar_comandos()
        self._input.setText(filtro)
        self._filtrar(filtro)
        self._centralizar()
        self.show()
        self._input.setFocus()
        self._input.selectAll()

    # ── Lógica interna ────────────────────────────────────────────────

    def _carregar_comandos(self):
        self._comandos = buscar_comandos("", self._janela)

    def _filtrar(self, texto: str):
        self._lista.clear()
        filtro = texto.lower()
        for cmd in self._comandos:
            if not filtro or filtro in cmd.titulo.lower():
                item = QListWidgetItem(cmd.titulo)
                item.setData(Qt.UserRole, cmd)
                self._lista.addItem(item)
        if self._lista.count():
            self._lista.setCurrentRow(0)
        altura = min(self._lista.count() * 34 + 4, 300)
        self._lista.setFixedHeight(max(altura, 34))
        self.adjustSize()

    def _executar_selecionado(self):
        item = self._lista.currentItem()
        if item:
            self._ao_ativar(item)

    def _ao_ativar(self, item: QListWidgetItem):
        cmd = item.data(Qt.UserRole)
        self.hide()
        if cmd and cmd.acao:
            try:
                cmd.acao()
            except Exception:
                pass

    def _centralizar(self):
        pai = self.parentWidget()
        if not pai:
            return
        centro = pai.mapToGlobal(pai.rect().center())
        self.adjustSize()
        self.move(centro - self.rect().center())

    # ── Navegação por teclado ─────────────────────────────────────────

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.hide()
        elif key == Qt.Key_Down:
            row = min(self._lista.currentRow() + 1, self._lista.count() - 1)
            self._lista.setCurrentRow(row)
        elif key == Qt.Key_Up:
            row = max(self._lista.currentRow() - 1, 0)
            self._lista.setCurrentRow(row)
        else:
            super().keyPressEvent(event)
