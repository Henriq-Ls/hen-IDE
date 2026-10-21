# 📁 _UTILITARIOS_/dialogo_update.py
"""
Diálogo de atualização da hein IDE.

Exibe release notes do novo release, barra de progresso de download,
e substitui o .exe atual via .bat gerado em %TEMP% (necessário porque
o Windows não permite sobrescrever um .exe em execução).
"""
import os
import subprocess
import sys
import tempfile
import webbrowser

from PySide6.QtCore    import QThread, Signal
from _THREADS_.thread_segura import _ThreadSegura
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QTextBrowser,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Worker de download
# ─────────────────────────────────────────────────────────────────────────────

class _WorkerDownload(_ThreadSegura):
    progresso = Signal(int)   # 0–100
    concluido = Signal(str)   # caminho do arquivo baixado
    erro      = Signal(str)   # mensagem de erro

    def __init__(self, url: str, destino: str):
        super().__init__()
        self._url     = url
        self._destino = destino

    def run(self):
        try:
            import urllib.request

            def _hook(count, block_size, total_size):
                if total_size > 0:
                    pct = min(100, int(count * block_size * 100 / total_size))
                    self.progresso.emit(pct)

            urllib.request.urlretrieve(self._url, self._destino, reporthook=_hook)
            self.concluido.emit(self._destino)
        except Exception as e:
            self.erro.emit(str(e))


# ─────────────────────────────────────────────────────────────────────────────
#  Diálogo principal
# ─────────────────────────────────────────────────────────────────────────────

class DialogoUpdate(QDialog):
    """
    Uso:
        dlg = DialogoUpdate(versao, url_html, url_exe, body, parent=self)
        dlg.exec()
    """

    def __init__(
        self,
        versao:   str,
        url_html: str,
        url_exe:  str,
        body:     str,
        parent=None,
    ):
        super().__init__(parent)
        self._versao   = versao
        self._url_html = url_html
        self._url_exe  = url_exe
        self._worker: _WorkerDownload | None = None

        self._setup_ui(body)

    # ── UI ───────────────────────────────────────────────────────────────────

    def _setup_ui(self, body: str) -> None:
        self.setWindowTitle(f"hein IDE {self._versao} disponível")
        self.setMinimumSize(640, 440)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Título
        lbl_titulo = QLabel(f"↑  Nova versão disponível: <b>{self._versao}</b>")
        lbl_titulo.setStyleSheet(
            "font-size: 13px; color: #7ecf7e; padding: 4px 0;"
        )
        layout.addWidget(lbl_titulo)

        # Release notes
        self._txt = QTextBrowser()
        self._txt.setOpenExternalLinks(True)
        self._txt.setMarkdown(body.strip() if body.strip() else "_Sem notas de release._")
        layout.addWidget(self._txt, 1)

        # Barra de progresso (oculta até iniciar download)
        self._barra = QProgressBar()
        self._barra.setRange(0, 100)
        self._barra.setValue(0)
        self._barra.setVisible(False)
        layout.addWidget(self._barra)

        # Label de status
        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("color: #aaa; font-size: 11px;")
        self._lbl_status.setVisible(False)
        layout.addWidget(self._lbl_status)

        # Botões
        btn_row = QHBoxLayout()

        self._btn_browser = QPushButton("Ver no GitHub")
        self._btn_browser.clicked.connect(lambda: webbrowser.open(self._url_html))

        self._btn_fechar = QPushButton("Fechar")
        self._btn_fechar.clicked.connect(self.reject)

        self._btn_baixar = QPushButton(f"Baixar e instalar {self._versao}")
        self._btn_baixar.setDefault(True)
        self._btn_baixar.setEnabled(bool(self._url_exe))
        if not self._url_exe:
            self._btn_baixar.setToolTip("URL de download não encontrada neste release.")
        self._btn_baixar.clicked.connect(self._iniciar_download)

        btn_row.addWidget(self._btn_browser)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_fechar)
        btn_row.addWidget(self._btn_baixar)
        layout.addLayout(btn_row)

    # ── Download ─────────────────────────────────────────────────────────────

    def _iniciar_download(self) -> None:
        self._btn_baixar.setEnabled(False)
        self._btn_fechar.setEnabled(False)
        self._barra.setVisible(True)
        self._lbl_status.setVisible(True)
        self._lbl_status.setText("Baixando nova versão...")

        destino = os.path.join(tempfile.gettempdir(), "hein-IDE-update.exe")

        self._worker = _WorkerDownload(self._url_exe, destino)
        self._worker.progresso.connect(self._barra.setValue)
        self._worker.concluido.connect(self._ao_concluir)
        self._worker.erro.connect(self._ao_erro)
        self._worker.start()

    def _ao_concluir(self, caminho: str) -> None:
        self._lbl_status.setText("Download completo. Aplicando atualização...")
        self._substituir_e_reiniciar(caminho)

    def _ao_erro(self, msg: str) -> None:
        self._lbl_status.setText(f"Erro no download: {msg}")
        self._btn_baixar.setEnabled(True)
        self._btn_fechar.setEnabled(True)

    # ── Substituição via .bat ─────────────────────────────────────────────────

    def _substituir_e_reiniciar(self, caminho_novo: str) -> None:
        """
        Gera um .bat em %TEMP% que:
          1. Aguarda 3 s (processo da IDE fechar)
          2. Substitui o .exe atual pelo baixado
          3. Reinicia a IDE
          4. Apaga o próprio .bat
        """
        exe_atual = sys.executable   # no .exe congelado: caminho do hein-IDE.exe

        bat = (
            "@echo off\n"
            "timeout /t 3 /nobreak > nul\n"
            f'move /Y "{caminho_novo}" "{exe_atual}"\n'
            f'start "" "{exe_atual}"\n'
            'del "%~f0"\n'
        )

        bat_path = os.path.join(tempfile.gettempdir(), "hein_update.bat")
        with open(bat_path, "w", encoding="cp1252") as f:
            f.write(bat)

        subprocess.Popen(
            ["cmd.exe", "/C", bat_path],
            close_fds=True,
            **opcoes_processo_sem_console(),
        )

        from PySide6.QtWidgets import QApplication
        QApplication.quit()
