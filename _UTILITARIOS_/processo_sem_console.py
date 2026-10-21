"""Opções comuns para subprocessos internos da hein IDE.

Processos auxiliares não devem abrir uma janela de console no Windows.
As opções são criadas a cada chamada porque STARTUPINFO é um objeto de
configuração específico daquela criação de processo.
"""
from __future__ import annotations

import subprocess
import sys


def opcoes_processo_sem_console() -> dict:
    """Retorna opções portáveis para iniciar processo auxiliar oculto."""
    if sys.platform != "win32":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }