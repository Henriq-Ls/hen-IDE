# 📁 _TERMINAIS_/Mult_Terminais/terminal_executor.py
"""
ExecutorTerminal — terminal dedicado para linguagens não-Python com can_run=True.

Estados:
  "sem_ferramenta" — binário não encontrado → instruções + botão de instalação
  "pronto"         — binário ok → campo de comando editável + output do QProcess

Uso (criado por TerminalTabWidget.abrir_executor_terminal):
    t = ExecutorTerminal("JavaScript", arquivo="/caminho/script.js")
    # cria a aba e chama executar() automaticamente se a ferramenta estiver ok
"""
from __future__ import annotations

import os
import shutil
import sys
from PySide6.QtCore import (
    QProcess,
    QProcessEnvironment,
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
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from _CONFIGURA_ import FONTE_MONO
from _UTILITARIOS_.icones import icone_tema
from _CONFIGURA_.gerenciador_tema import tema_global
# ─────────────────────────────────────────────────────────────────────────────
# Mapeamento extensão → comando para sobrepor o comando genérico "Shell".
# .ps1/.psm1 usam o comando configurado em executores.json (powershell).
# .sh/.bash/.zsh precisam de bash; .bat/.cmd precisam de cmd /c.
_CMD_POR_EXT: dict[str, str] = {
    '.sh':   'bash',
    '.bash': 'bash',
    '.zsh':  'zsh',
    '.bat':  'cmd /c',
    '.cmd':  'cmd /c',
}
# ─────────────────────────────────────────────────────────────────────────────
_ESTILO_BTN_MINI = (
    "QPushButton { background: transparent; border: none; }"
    "QPushButton:hover { background: rgba(255,255,255,0.08); border-radius: 3px; }"
    "QPushButton:disabled { opacity: 0.3; }"
)
_ESTILO_BTN_ACAO = (
    "QPushButton { background: #1a3a1a; color: #98c379; border: none; "
    "padding: 5px 16px; font-size: 11px; border-radius: 3px; }"
    "QPushButton:hover { background: #264f78; color: #ffffff; }"
)
_ESTILO_BTN_SECUNDARIO = (
    "QPushButton { background: transparent; color: #666; border: 1px solid #333; "
    "padding: 5px 12px; font-size: 11px; border-radius: 3px; }"
    "QPushButton:hover { color: #98c379; border-color: #98c379; }"
)
# ─────────────────────────────────────────────────────────────────────────────

class ExecutorTerminal(QWidget):
    """
    Terminal dedicado por linguagem para execução de arquivos não-Python.

    Ciclo de vida:
      1. TerminalTabWidget cria a aba com __init__(nome, arquivo).
      2. Se a ferramenta está ok → executa automaticamente.
      3. Se não está → mostra tela de instruções.
      4. set_arquivo(novo_arquivo) reutiliza a aba existente.
    """

    def __init__( self, nome_linguagem: str, arquivo: str = "", parent=None, ) -> None:
        super().__init__(parent)
        self._nome    = nome_linguagem
        self._arquivo = arquivo

        # ── QProcess ──────────────────────────────────────────────────────
        self._proc = QProcess(self)
        self._proc.readyReadStandardOutput.connect(self._ler_stdout)
        self._proc.readyReadStandardError.connect(self._ler_stderr)
        self._proc.finished.connect(self._ao_terminar)

        # ── Layout raiz ───────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_pg_sem())     # índice 0
        self._stack.addWidget(self._build_pg_pronto())  # índice 1

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._stack)

        # ── Estado inicial ────────────────────────────────────────────────
        self._verificar_e_executar(auto=bool(arquivo))

    # ══════════════════════════════════════════════════════════════════════
    # Construção das páginas
    # ══════════════════════════════════════════════════════════════════════

    def _build_pg_sem(self) -> QWidget:
        """Página exibida quando o binário não é encontrado no PATH."""
        t      = tema_global()
        fundo  = t.cor("terminal_run.fundo", "#000000")
        pg     = QWidget()
        pg.setStyleSheet(f"background-color: {fundo};")

        v = QVBoxLayout(pg)
        v.setAlignment(Qt.AlignCenter)
        v.setSpacing(12)
        v.setContentsMargins(32, 32, 32, 32)

        ico = QLabel("⚠")
        ico.setAlignment(Qt.AlignCenter)
        ico.setStyleSheet("font-size: 32px; color: #e5c07b; background: transparent;")
        v.addWidget(ico)

        self._lbl_sem_titulo = QLabel(f"{self._nome}: ferramenta não encontrada")
        self._lbl_sem_titulo.setAlignment(Qt.AlignCenter)
        self._lbl_sem_titulo.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #e5c07b; background: transparent;"
        )
        v.addWidget(self._lbl_sem_titulo)

        self._lbl_sem_dica = QLabel()
        self._lbl_sem_dica.setAlignment(Qt.AlignCenter)
        self._lbl_sem_dica.setWordWrap(True)
        self._lbl_sem_dica.setMaximumWidth(520)
        self._lbl_sem_dica.setStyleSheet(
            "font-size: 11px; color: #888; background: transparent;"
        )
        v.addWidget(self._lbl_sem_dica)

        h = QHBoxLayout()
        h.setAlignment(Qt.AlignCenter)
        h.setSpacing(8)

        self._btn_como_instalar = QPushButton("🌐  Como instalar")
        self._btn_como_instalar.setStyleSheet(_ESTILO_BTN_ACAO)
        self._btn_como_instalar.clicked.connect(self._abrir_url)
        h.addWidget(self._btn_como_instalar)

        self._btn_informar_caminho = QPushButton("Já tenho — informar caminho")
        self._btn_informar_caminho.setStyleSheet(_ESTILO_BTN_SECUNDARIO)
        self._btn_informar_caminho.clicked.connect(self._ir_para_pronto_sem_checar)
        h.addWidget(self._btn_informar_caminho)

        v.addLayout(h)

        return pg

    def _build_pg_pronto(self) -> QWidget:
        """Página principal: barra de comando + área de output."""
        t     = tema_global()
        fundo = t.cor("terminal_run.fundo", "#000000")
        fundo_barra = t.cor("interface.fundo_painel_central", "#0A1210")

        pg = QWidget()
        pg.setStyleSheet(f"background-color: {fundo};")

        # ── Barra superior ─────────────────────────────────────────────
        barra = QWidget()
        barra.setFixedHeight(30)
        barra.setStyleSheet(f"background-color: {fundo_barra};")

        h = QHBoxLayout(barra)
        h.setContentsMargins(8, 0, 8, 0)
        h.setSpacing(6)

        lbl = QLabel("Comando:")
        lbl.setStyleSheet("font-size: 10px; color: #555; background: transparent;")
        h.addWidget(lbl)

        self._fld_cmd = QLineEdit()
        self._fld_cmd.setPlaceholderText("ex: node")
        self._fld_cmd.setFixedHeight(22)
        self._fld_cmd.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._fld_cmd.setStyleSheet(
            f"QLineEdit {{ background: {fundo}; color: #98c379; "
            "border: 1px solid #333; border-radius: 3px; "
            "padding: 1px 6px; font-family: 'Consolas', monospace; font-size: 11px; }}"
            "QLineEdit:focus { border-color: #98c379; }"
        )
        self._fld_cmd.returnPressed.connect(self._ao_salvar_cmd)
        h.addWidget(self._fld_cmd)

        self._btn_run = QPushButton()
        self._btn_run.setIcon(icone_tema("mdi.play"))
        self._btn_run.setIconSize(QSize(14, 14))
        self._btn_run.setFixedSize(24, 24)
        self._btn_run.setToolTip("Executar")
        self._btn_run.setStyleSheet(_ESTILO_BTN_MINI)
        self._btn_run.clicked.connect(self.executar)
        h.addWidget(self._btn_run)

        self._btn_stop = QPushButton()
        self._btn_stop.setIcon(icone_tema("mdi.stop"))
        self._btn_stop.setIconSize(QSize(14, 14))
        self._btn_stop.setFixedSize(24, 24)
        self._btn_stop.setToolTip("Parar execução")
        self._btn_stop.setEnabled(False)
        self._btn_stop.setStyleSheet(_ESTILO_BTN_MINI)
        self._btn_stop.clicked.connect(self._proc.kill)
        h.addWidget(self._btn_stop)

        self._btn_limpar = QPushButton()
        self._btn_limpar.setIcon(icone_tema("mdi.delete-sweep"))
        self._btn_limpar.setIconSize(QSize(14, 14))
        self._btn_limpar.setFixedSize(24, 24)
        self._btn_limpar.setToolTip("Limpar output")
        self._btn_limpar.setStyleSheet(_ESTILO_BTN_MINI)
        self._btn_limpar.clicked.connect(self._output.clear if hasattr(self, "_output") else lambda: None)
        h.addWidget(self._btn_limpar)

        # ── Área de output ─────────────────────────────────────────────
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setStyleSheet(
            f"QPlainTextEdit {{ background-color: {fundo}; color: #e0e0e0; "
            f"font-family: '{FONTE_MONO}', 'Consolas', monospace; "
            "font-size: 11px; border: none; }}"
        )

        # Reconectar limpar depois de criar _output
        self._btn_limpar.clicked.disconnect()
        self._btn_limpar.clicked.connect(self._output.clear)

        v = QVBoxLayout(pg)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(barra)
        v.addWidget(self._output)

        return pg

    # ══════════════════════════════════════════════════════════════════════
    # Lógica de estado
    # ══════════════════════════════════════════════════════════════════════

    def _verificar_e_executar(self, auto: bool = False) -> None:
        """Decide qual página mostrar com base na disponibilidade do binário."""
        from _CONFIGURA_.gerenciador_executores import exec_global
        gex = exec_global()
        cfg = gex.get_config(self._nome)
        cmd = gex.get_comando(self._nome)

        # Atualiza textos da página sem-ferramenta
        dica = cfg.get("instalacao_dica", "Instale a ferramenta necessária.")
        self._lbl_sem_dica.setText(dica)
        url = cfg.get("instalacao_url", "")
        self._btn_como_instalar.setVisible(bool(url))
        self._btn_como_instalar.setProperty("_url", url)

        if gex.ferramenta_disponivel(self._nome):
            self._fld_cmd.setText(cmd)
            self._stack.setCurrentIndex(1)  # pronto
            if auto and self._arquivo:
                QTimer.singleShot(80, self.executar)
        else:
            binario = cmd.split()[0] if cmd else "?"
            self._lbl_sem_titulo.setText(
                f"{self._nome}: '{binario}' não encontrado no sistema"
            )
            self._stack.setCurrentIndex(0)  # sem ferramenta

    # ══════════════════════════════════════════════════════════════════════
    # API pública
    # ══════════════════════════════════════════════════════════════════════

    def set_arquivo(self, arquivo: str) -> None:
        """
        Atualiza o arquivo alvo.
        Chamado quando a aba já existe e o usuário executa outro arquivo
        da mesma linguagem — reutiliza a aba em vez de abrir uma nova.
        """
        self._arquivo = arquivo
        self._verificar_e_executar(auto=True)

    def executar(self) -> None:
        """Executa self._arquivo com o comando configurado."""
        if not self._arquivo:
            self._erro("Nenhum arquivo definido para execução.\n")

            return

        if not os.path.isfile(self._arquivo):
            self._erro(f"Arquivo não encontrado: {self._arquivo}\n")

            return

        # Mata processo anterior se ainda em execução
        if self._proc.state() != QProcess.NotRunning:
            self._proc.kill()
            self._proc.waitForFinished(1000)

        self._output.clear()

        cmd = self._fld_cmd.text().strip()
        if not cmd:
            from _CONFIGURA_.gerenciador_executores import exec_global
            cmd = exec_global().get_comando(self._nome)

        # Sobrepõe o comando configurado se a extensão exige intérprete diferente.
        # Ex.: Shell usa powershell por padrão, mas .sh/.bash/.zsh precisam de bash.
        ext = os.path.splitext(self._arquivo)[1].lower()
        cmd_por_ext = _CMD_POR_EXT.get(ext)
        if cmd_por_ext:
            # Verifica se o intérprete de override está disponível
            override_bin = cmd_por_ext.split()[0]
            if shutil.which(override_bin) is None:
                self._erro(
                    f"Comando '{override_bin}' não encontrado no sistema.\n"
                    f"Para rodar arquivos {ext}, instale '{override_bin}' e "
                    f"certifique-se de que está no PATH do sistema.\n"
                    f"No Windows: instale o Git for Windows (inclui bash) "
                    f"ou ative o WSL.\n"
                )
                return
            cmd = cmd_por_ext

        if not cmd:
            self._erro("Nenhum comando configurado.\n")

            return

        partes   = cmd.split()
        programa = partes[0]
        args     = partes[1:] + [self._arquivo]

        env = QProcessEnvironment.systemEnvironment()
        self._proc.setProcessEnvironment(env)

        nome = os.path.basename(self._arquivo)
        self._colorido(f"▶  {nome}  [{cmd}]\n", "#555555")

        self._btn_run.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._proc.start(programa, args)

    def parar(self) -> None:
        """Para o processo em execução (chamado ao fechar a aba)."""
        if self._proc.state() != QProcess.NotRunning:
            self._proc.kill()

    # ══════════════════════════════════════════════════════════════════════
    # Slots do QProcess
    # ══════════════════════════════════════════════════════════════════════

    def _ler_stdout(self) -> None:
        data = self._proc.readAllStandardOutput().data().decode("utf-8", errors="replace")
        self._colorido(data, tema_global().cor("terminal_run.texto_saida", "#e0e0e0"))

    def _ler_stderr(self) -> None:
        data = self._proc.readAllStandardError().data().decode("utf-8", errors="replace")
        self._colorido(f"[ERRO] {data}", tema_global().cor("terminal_run.texto_erro", "#e06c75"))

    def _ao_terminar(self, exit_code: int, _) -> None:
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)
        t   = tema_global()
        sep = t.cor("terminal_run.texto_separador", "#555555")
        cor = (
            t.cor("terminal_run.texto_sucesso", "#4ec994")
            if exit_code == 0
            else t.cor("terminal_run.texto_erro", "#e06c75")
        )
        self._colorido(f"\n{'---' * 30}Concluído com código {exit_code}\n", sep)
        self._colorido(f"[{'OK' if exit_code == 0 else 'FALHA'}]\n", cor)

    # ══════════════════════════════════════════════════════════════════════
    # Impressão
    # ══════════════════════════════════════════════════════════════════════

    def _colorido(self, texto: str, cor: str) -> None:
        cursor = self._output.textCursor()
        fmt    = QTextCharFormat()
        fmt.setForeground(QColor(cor))
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(texto, fmt)
        self._output.setTextCursor(cursor)
        self._output.verticalScrollBar().setValue(
            self._output.verticalScrollBar().maximum()
        )

    def _erro(self, msg: str) -> None:
        self._colorido(f"[ERRO] {msg}", "#e06c75")

    # ══════════════════════════════════════════════════════════════════════
    # Botões da página sem-ferramenta
    # ══════════════════════════════════════════════════════════════════════

    def _abrir_url(self) -> None:
        url = self._btn_como_instalar.property("_url") or ""
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _ir_para_pronto_sem_checar(self) -> None:
        """Vai para a página 'pronto' para o usuário digitar o caminho manualmente."""
        self._stack.setCurrentIndex(1)
        self._fld_cmd.clear()
        self._fld_cmd.setPlaceholderText("Digite o caminho completo do executável…")
        self._fld_cmd.setFocus()

    def _ao_salvar_cmd(self) -> None:
        cmd = self._fld_cmd.text().strip()
        if cmd:
            from _CONFIGURA_.gerenciador_executores import exec_global
            exec_global().set_comando(self._nome, cmd)

    # ══════════════════════════════════════════════════════════════════════
    # Tema
    # ══════════════════════════════════════════════════════════════════════

    def atualizar_tema(self, _tema: dict = None) -> None:
        t     = tema_global()
        fundo = t.cor("terminal_run.fundo", "#000000")
        self._output.setStyleSheet(
            f"QPlainTextEdit {{ background-color: {fundo}; color: #e0e0e0; "
            f"font-family: '{FONTE_MONO}', 'Consolas', monospace; "
            "font-size: 11px; border: none; }}"
        )
