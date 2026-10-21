# 📁 _UTILITARIOS_/hein_migrador_venv.py
# -*- coding: utf-8 -*-
"""
Migra o .venv do projeto para um novo interpretador Python.

Fluxo:
  1. pip freeze  → salva lista de pacotes instalados
  2. shutil.rmtree(.venv)
  3. new_python -m venv .venv
  4. pip install -r freeze.txt  (reinstala pacotes anteriores)

Uso (de hein_python_picker.py):
    from _UTILITARIOS_.hein_migrador_venv import DialogoMigracao
    dlg = DialogoMigracao(projeto, novo_python_exe, parent=janela)
    if dlg.exec():          # QDialog.Accepted → migração ok
        ...
"""
from __future__ import annotations
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from PySide6.QtCore    import QThread, Signal, Qt
from _THREADS_.thread_segura import _ThreadSegura
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton
from PySide6.QtGui     import QFont, QColor
from _LOG_.log import log
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console
_ARQ = "hein_migrador_venv.py"

# ── helpers ───────────────────────────────────────────────────────────────────

def _pip_exe(pasta_venv: str) -> str:
    if platform.system() == "Windows":

        return os.path.join(pasta_venv, "Scripts", "pip.exe")

    return os.path.join(pasta_venv, "bin", "pip")

# ── thread ────────────────────────────────────────────────────────────────────

class _ThreadMigracao(_ThreadSegura):
    """
    Realiza a migração em background — nunca bloqueia a UI thread.
    Emite progresso(str) a cada etapa e concluido(bool, str) ao final.
    """
    progresso = Signal(str)
    concluido = Signal(bool, str)

    def __init__(self, projeto: str, novo_python: str, parent=None):
        super().__init__(parent)
        self._projeto     = projeto
        self._novo_python = novo_python

    # ⚠️  função grande (89 linhas) | except genérico vazio
    def run(self):
        venv_path = os.path.join(self._projeto, ".venv")
        pip_atual = _pip_exe(venv_path)
        opcoes_processo = opcoes_processo_sem_console()

        # 1. pip freeze
        reqs = ""
        try:
            self.progresso.emit("1/4  pip freeze — salvando pacotes atuais…")
            if os.path.isfile(pip_atual):
                r = subprocess.run(
                    [pip_atual, "freeze"],
                    capture_output=True, text=True,
                    timeout=60, **opcoes_processo,
                )
                reqs = r.stdout.strip()
                log.info(_ARQ, "run", f"freeze: {len(reqs.splitlines())} pacote(s)")
            else:
                log.aviso(_ARQ, "run", "pip não encontrado — freeze ignorado")
                self.progresso.emit("   ⚠  pip não encontrado; pacotes não preservados.")
        except Exception as e:
            log.aviso(_ARQ, "run", f"freeze falhou: {e}")
            self.progresso.emit(f"   ⚠  freeze falhou: {e}")

        # 2. remover .venv
        try:
            self.progresso.emit("2/4  Removendo .venv existente…")
            shutil.rmtree(venv_path, ignore_errors=True)
        except Exception as e:
            self.concluido.emit(False, f"Erro ao remover .venv:\n{e}")

            return

        # 3. criar nova venv
        try:
            self.progresso.emit(
                f"3/4  Criando nova .venv com "
                f"{os.path.basename(self._novo_python)}…"
            )
            subprocess.run(
                [self._novo_python, "-m", "venv", venv_path],
                check=True, capture_output=True,
                timeout=120, **opcoes_processo,
            )
        except Exception as e:
            self.concluido.emit(False, f"Erro ao criar .venv:\n{e}")

            return

        # 4. reinstalar pacotes
        if reqs:
            try:
                n = len(reqs.splitlines())
                self.progresso.emit(f"4/4  Reinstalando {n} pacote(s)…")
                pip_novo = _pip_exe(venv_path)
                tmp = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False, encoding="utf-8"
                )
                tmp.write(reqs)
                tmp.close()
                proc = subprocess.Popen(
                    [pip_novo, "install", "-r", tmp.name],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, **opcoes_processo,
                )
                for linha in proc.stdout:
                    self.progresso.emit(linha.rstrip())
                proc.wait(timeout=300)
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
                if proc.returncode != 0:
                    self.concluido.emit(
                        False,
                        f"pip install -r retornou código {proc.returncode}",
                    )

                    return

            except Exception as e:
                self.concluido.emit(False, f"Erro ao reinstalar pacotes:\n{e}")

                return

        else:
            self.progresso.emit("4/4  Sem pacotes anteriores para reinstalar.")

        self.concluido.emit(True, "Migração concluída com sucesso!")

# ── diálogo ───────────────────────────────────────────────────────────────────

class DialogoMigracao(QDialog):
    """
    Diálogo de progresso/resultado da migração de .venv.
    Retorna Accepted se a migração foi bem-sucedida; Rejected se cancelada ou falhou.
    """

    # ⚠️  except genérico vazio
    def __init__(self, projeto: str, novo_python: str, parent=None):
        super().__init__(parent)
        self._sucesso = False

        self.setWindowTitle("Migrar .venv do projeto")
        self.setMinimumSize(580, 340)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)

        lay = QVBoxLayout(self)

        versao = ""
        try:
            r = subprocess.run(
                [novo_python, "--version"],
                capture_output=True, text=True, timeout=3,
                **opcoes_processo_sem_console(),
            )
            versao = (r.stdout or r.stderr).strip()
        except Exception:
            pass

        lay.addWidget(QLabel(
            f"<b>Migrar .venv para:</b>  {versao or novo_python}<br>"
            "<small>Os pacotes atualmente instalados serão preservados.</small>"
        ))

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont(FONTE_MONO, 9))
        lay.addWidget(self._log)

        self._btn = QPushButton("Cancelar")
        self._btn.clicked.connect(self._cancelar_ou_fechar)
        lay.addWidget(self._btn)

        self._thread = _ThreadMigracao(projeto, novo_python, self)
        self._thread.progresso.connect(self._ao_progresso)
        self._thread.concluido.connect(self._ao_concluir)
        self._thread.start()

    # ── slots ──────────────────────────────────────────────────────────

    def _ao_progresso(self, msg: str):
        self._log.append(msg)

    def _ao_concluir(self, sucesso: bool, msg: str):
        self._sucesso = sucesso
        if sucesso:
            self._log.append(
                f"<span style='color:#4ec994; font-weight:bold'>✓  {msg}</span>"
            )
        else:
            self._log.setTextColor(QColor(COR_SINTAXE_VARIAVEL_ESPECIAL))
            self._log.append(f"\n✗  {msg}")
            self._log.setTextColor(QColor(COR_CINZA_TEXTO))
        self._btn.setText("Fechar")

    def _cancelar_ou_fechar(self):
        if self._thread.isRunning():
            self._thread.terminate()
            self._thread.wait(2000)
        if self._sucesso:
            self.accept()
        else:
            self.reject()

# ── API não-bloqueante (sem QDialog) ─────────────────────────────────────────

def iniciar_migracao( projeto: str, novo_python: str, janela, callback=None, ):
    """Inicia migração de .venv em background com log na aba do terminal.

    Sem QDialog — abre aba de log no TerminalTabWidget.
    callback(sucesso: bool, novo_exe: str) chamado ao terminar.
    """
    import os as _os

    def _python_venv():
        is_win = _os.name == "nt"
        exe = _os.path.join(projeto, ".venv", "Scripts" if is_win else "bin",
                            "python.exe" if is_win else "python")

        return exe

    try:
        aba = janela.terminal_tabs.abrir_aba_pip("⚙ Migrar .venv")
    except Exception:
        aba = None

    thread = _ThreadMigracao(projeto, novo_python)

    if aba:
        thread.progresso.connect(aba.append_log)

    def _done(sucesso: bool, msg: str):
        novo_exe = _python_venv() if sucesso else novo_python
        if aba:
            aba.ao_concluir(sucesso, msg)
        if callback:
            callback(sucesso, novo_exe)

    thread.concluido.connect(_done)
    # Guardar referência para evitar garbage collection
    if not hasattr(janela, "_threads_hein"):
        janela._threads_hein = []
    janela._threads_hein.append(thread)
    def _cleanup():
        try:
            janela._threads_hein.remove(thread)
        except (ValueError, AttributeError):
            pass
    thread.finished.connect(_cleanup)
    thread.start()
