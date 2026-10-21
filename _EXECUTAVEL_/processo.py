"""Execução de subprocessos de build sem janelas de console adicionais."""
from __future__ import annotations

import os
import subprocess

from PySide6.QtCore import Signal
from _THREADS_.thread_segura import _ThreadSegura
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console
from _LOG_.log import log

_ARQ = "executavel.processo"


class ProcessoThread(_ThreadSegura):
    linha = Signal(str)
    concluido = Signal(int)

    def __init__(self, comando, cwd, parent=None, env=None):
        super().__init__(parent)
        self._comando = [str(item) for item in comando]
        self._cwd = str(cwd)
        self._env = dict(env) if env is not None else None
        self._processo = None

    def run(self):
        codigo = 1
        try:
            self._processo = subprocess.Popen(
                self._comando,
                cwd=self._cwd,
                env=self._env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **opcoes_processo_sem_console(),
            )
            if self._processo.stdout is not None:
                for linha in self._processo.stdout:
                    self.linha.emit(linha.rstrip("\r\n"))
            codigo = self._processo.wait()
        except Exception as exc:
            log.erro(_ARQ, "run", str(exc))
            self.linha.emit(f"Falha ao executar processo: {exc}")
        finally:
            self.concluido.emit(int(codigo))

    def parar(self):
        processo = self._processo
        if processo is not None and processo.poll() is None:
            try:
                processo.terminate()
            except OSError as exc:
                log.aviso(_ARQ, "parar", str(exc))
