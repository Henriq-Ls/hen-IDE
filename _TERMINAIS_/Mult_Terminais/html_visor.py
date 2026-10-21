# 📁 _TERMINAIS_/Mult_Terminais/html_visor.py
"""
HTMLVisorTerminal — painel de execução dedicado para arquivos HTML.

Abre quando o usuário pressiona F1 em um .html/.htm.
Não roda processo — abre o arquivo no navegador padrão do sistema.

Recursos:
  - Botão "Abrir no navegador" → QDesktopServices.openUrl (file://)
  - Toggle "Auto-atualizar" → QFileSystemWatcher dispara reabertura no browser
    a cada salvamento detectado
  - Log de eventos (hora, status, erros)
"""
from __future__ import annotations
import os
from PySide6.QtCore import (
    QFileSystemWatcher,
    QSize,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from _CONFIGURA_ import FONTE_MONO
from _UTILITARIOS_.icones import icone_tema
from _CONFIGURA_.gerenciador_tema import tema_global
from _LOG_.log import log

class HTMLVisorTerminal(QWidget):
    """
    Painel dedicado para arquivos HTML.

    Ciclo de vida:
      1. TerminalTabWidget cria a aba com __init__(arquivo).
      2. Abre automaticamente no navegador (QTimer 120 ms).
      3. set_arquivo(novo) reutiliza a aba para outro .html.
    """

    def __init__(self, arquivo: str = "", parent=None) -> None:
        super().__init__(parent)
        # _nome é lido por TerminalTabWidget para identificar a aba
        self._nome    = 'HTML'
        self._arquivo = arquivo
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._ao_arquivo_mudar)

        self._build_ui()
        self._aplicar_tema()

        if arquivo:
            self._atualizar_info()
            QTimer.singleShot(120, self.abrir_no_navegador)

    # ══════════════════════════════════════════════════════════════════════
    # Construção da UI (estrutura)
    # ══════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ── Barra superior ───────────────────────────────────────────────
        self._barra = QWidget()
        self._barra.setFixedHeight(34)
        hb = QHBoxLayout(self._barra)
        hb.setContentsMargins(10, 0, 10, 0)
        hb.setSpacing(6)

        self._lbl_ico = QLabel("🌐")
        self._lbl_ico.setStyleSheet("background: transparent; font-size: 14px;")
        hb.addWidget(self._lbl_ico)

        self._lbl_nome = QLabel("HTML")
        hb.addWidget(self._lbl_nome)
        hb.addStretch()

        self._btn_limpar = QPushButton()
        self._btn_limpar.setIcon(icone_tema("mdi.delete-sweep"))
        self._btn_limpar.setIconSize(QSize(14, 14))
        self._btn_limpar.setFixedSize(24, 24)
        self._btn_limpar.setToolTip("Limpar log")
        self._btn_limpar.clicked.connect(self._output.clear if hasattr(self, "_output") else lambda: None)
        hb.addWidget(self._btn_limpar)

        raiz.addWidget(self._barra)

        # ── Área central ─────────────────────────────────────────────────
        self._centro = QWidget()
        vc = QVBoxLayout(self._centro)
        vc.setContentsMargins(32, 24, 32, 24)
        vc.setSpacing(16)
        vc.setAlignment(Qt.AlignTop)

        self._lbl_arquivo = QLabel()
        self._lbl_arquivo.setAlignment(Qt.AlignCenter)
        self._lbl_arquivo.setWordWrap(True)
        vc.addWidget(self._lbl_arquivo)

        self._lbl_caminho = QLabel()
        self._lbl_caminho.setAlignment(Qt.AlignCenter)
        self._lbl_caminho.setWordWrap(True)
        vc.addWidget(self._lbl_caminho)

        # Botão principal
        self._btn_abrir = QPushButton("🌐   Abrir no navegador")
        self._btn_abrir.setFixedHeight(40)
        self._btn_abrir.setMinimumWidth(220)
        self._btn_abrir.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._btn_abrir.clicked.connect(self.abrir_no_navegador)
        hbtn = QHBoxLayout()
        hbtn.setAlignment(Qt.AlignCenter)
        hbtn.addWidget(self._btn_abrir)
        vc.addLayout(hbtn)

        # Toggle auto-atualizar
        self._chk_auto = QCheckBox("♻  Auto-atualizar no navegador ao salvar")
        self._chk_auto.toggled.connect(self._ao_toggle_auto)
        hchk = QHBoxLayout()
        hchk.setAlignment(Qt.AlignCenter)
        hchk.addWidget(self._chk_auto)
        vc.addLayout(hchk)

        self._lbl_status = QLabel("Nunca aberto")
        self._lbl_status.setAlignment(Qt.AlignCenter)
        vc.addWidget(self._lbl_status)

        self._sep = QWidget()
        self._sep.setFixedHeight(1)
        vc.addWidget(self._sep)

        # Log de eventos
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setMaximumHeight(160)
        self._output.setPlaceholderText("Log de eventos…")
        vc.addWidget(self._output)

        raiz.addWidget(self._centro)

        # Reconectar limpar agora que _output existe
        self._btn_limpar.clicked.disconnect()
        self._btn_limpar.clicked.connect(self._output.clear)

    # ══════════════════════════════════════════════════════════════════════
    # Tema — separa estrutura de cor/fonte
    # ══════════════════════════════════════════════════════════════════════

    def _aplicar_tema(self) -> None:
        t      = tema_global()
        fundo  = t.cor("terminal_run.fundo",             "#000000")
        fundo2 = t.cor("interface.fundo_painel_central", "#0A1210")
        txt    = t.cor("terminal_run.texto_saida",       "#e0e0e0")
        txt2   = t.cor("terminal_run.texto_separador",   "#555555")
        acento = t.cor("terminal_run.texto_sucesso",     "#98c379")
        sep    = t.cor("terminal_run.texto_separador",   "#1a2a1a")

        self.setStyleSheet(f"background-color: {fundo};")

        self._barra.setStyleSheet(f"background-color: {fundo2};")
        self._lbl_nome.setStyleSheet(
            f"font-size: 11px; font-weight: bold; color: {txt}; background: transparent;"
        )

        self._centro.setStyleSheet(f"background-color: {fundo};")
        self._lbl_arquivo.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {txt}; background: transparent;"
        )
        self._lbl_caminho.setStyleSheet(
            f"font-size: 10px; color: {txt2}; background: transparent;"
        )
        self._btn_abrir.setStyleSheet(
            f"QPushButton {{ background: {fundo2}; color: {acento}; border: 1px solid {acento}; "
            "padding: 8px 24px; font-size: 13px; font-weight: bold; border-radius: 4px; }"
            f"QPushButton:hover {{ background: {acento}; color: {fundo}; }}"
            f"QPushButton:pressed {{ background: {fundo2}; }}"
        )
        self._chk_auto.setStyleSheet(
            f"QCheckBox {{ font-size: 11px; color: {txt2}; background: transparent; spacing: 6px; }}"
            "QCheckBox::indicator { width: 14px; height: 14px; }"
            f"QCheckBox::indicator:unchecked {{ border: 1px solid {txt2}; border-radius: 2px; background: {fundo}; }}"
            f"QCheckBox::indicator:checked   {{ border: 1px solid {acento}; border-radius: 2px; background: {fundo2}; }}"
        )
        self._lbl_status.setStyleSheet(
            f"font-size: 10px; color: {txt2}; background: transparent;"
        )
        self._sep.setStyleSheet(f"background-color: {sep};")
        self._output.setStyleSheet(
            f"QPlainTextEdit {{ background-color: {fundo}; color: {txt2}; "
            f"font-family: '{FONTE_MONO}', 'Consolas', monospace; "
            "font-size: 10px; border: none; }}"
        )

        # Botão mini de limpar
        self._btn_limpar.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; }}"
            f"QPushButton:hover {{ background: rgba(255,255,255,0.08); border-radius: 3px; }}"
        )

    # ══════════════════════════════════════════════════════════════════════
    # API pública
    # ══════════════════════════════════════════════════════════════════════

    def set_arquivo(self, arquivo: str) -> None:
        """Reutiliza o painel para outro arquivo HTML."""
        self._parar_watch()
        self._arquivo = arquivo
        self._atualizar_info()
        QTimer.singleShot(80, self.abrir_no_navegador)

    def abrir_no_navegador(self) -> None:
        """Abre o arquivo HTML no navegador padrão do sistema."""
        if not self._arquivo or not os.path.isfile(self._arquivo):
            self._log(f"Arquivo não encontrado: {self._arquivo or '(nenhum)'}", erro=True)

            return

        url = QUrl.fromLocalFile(self._arquivo)
        ok  = QDesktopServices.openUrl(url)

        from datetime import datetime
        hora = datetime.now().strftime("%H:%M:%S")

        if ok:
            self._lbl_status.setText(f"Última abertura: {hora}")
            self._log(f"[{hora}]  Aberto no navegador: {os.path.basename(self._arquivo)}")
        else:
            self._log(f"[{hora}]  Falha ao abrir no navegador.", erro=True)
            log.erro(f"HTMLVisorTerminal: QDesktopServices.openUrl falhou — {self._arquivo}")

    def parar(self) -> None:
        """Chamado pelo TerminalTabWidget ao fechar a aba."""
        self._parar_watch()

    def atualizar_tema(self, _tema: dict = None) -> None:
        """Chamado pela MainWindow ao trocar tema — reaplica todas as cores."""
        self._aplicar_tema()

    # ══════════════════════════════════════════════════════════════════════
    # Internos
    # ══════════════════════════════════════════════════════════════════════

    def _atualizar_info(self) -> None:
        nome = os.path.basename(self._arquivo) if self._arquivo else "—"
        self._lbl_nome.setText(nome)
        self._lbl_arquivo.setText(nome)
        self._lbl_caminho.setText(self._arquivo or "")
        self._lbl_status.setText("Nunca aberto")
        self._output.clear()
        if self._chk_auto.isChecked():
            self._iniciar_watch()

    def _ao_toggle_auto(self, ativo: bool) -> None:
        if ativo:
            self._iniciar_watch()
            self._log("Auto-atualizar ATIVADO — abre no navegador a cada salvamento.")
        else:
            self._parar_watch()
            self._log("Auto-atualizar desativado.")

    def _iniciar_watch(self) -> None:
        if self._arquivo and os.path.isfile(self._arquivo):
            if self._arquivo not in self._watcher.files():
                self._watcher.addPath(self._arquivo)

    def _parar_watch(self) -> None:
        if self._watcher.files():
            self._watcher.removePaths(self._watcher.files())

    def _ao_arquivo_mudar(self, caminho: str) -> None:
        """Disparado pelo QFileSystemWatcher quando o arquivo muda em disco."""
        if not self._chk_auto.isChecked():

            return

        # Alguns editores deletam+recriam ao salvar — re-adiciona o watch
        QTimer.singleShot(200, lambda: self._watcher.addPath(caminho))
        self._log("Alteração detectada — atualizando navegador…")
        QTimer.singleShot(250, self.abrir_no_navegador)

    # ══════════════════════════════════════════════════════════════════════
    # Log colorido
    # ══════════════════════════════════════════════════════════════════════

    def _log(self, msg: str, erro: bool = False) -> None:
        t   = tema_global()
        cor = (
            t.cor("terminal_run.texto_erro", "#e06c75")
            if erro
            else t.cor("terminal_run.texto_separador", "#555555")
        )
        cursor = self._output.textCursor()
        fmt    = QTextCharFormat()
        fmt.setForeground(QColor(cor))
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(msg + "\n", fmt)
        self._output.setTextCursor(cursor)
        self._output.verticalScrollBar().setValue(
            self._output.verticalScrollBar().maximum()
        )
