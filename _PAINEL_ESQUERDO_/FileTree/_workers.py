# 📁 _PAINEL_ESQUERDO_/FileTree/_workers.py
"""
Worker Git — executa `git status --porcelain` em QThread separada.
"""

import os
import subprocess

from PySide6.QtCore import QObject, Signal
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console


class _WorkerTamanhoPasta(QObject):
    """Calcula o tamanho (MB) do projeto e da .venv em background.

    os.walk() sobre a pasta do projeto (e da .venv) é uma varredura de
    disco que pode levar segundos em projetos grandes — rodar isso direto
    na thread da UI trava a janela inteira (o Windows chega a mostrar a
    tela em branco/"não está respondendo" se o usuário clicar durante a
    varredura). Por isso roda aqui, fora da thread da UI.
    """

    concluido = Signal(float, float)  # tamanho_projeto_mb, tamanho_venv_mb

    def __init__(self, caminho_projeto: str, caminho_venv: str | None):
        super().__init__()
        self._caminho_projeto = caminho_projeto
        self._caminho_venv = caminho_venv

    def _tamanho_pasta(self, caminho: str) -> float:
        """Calcula tamanho recursivo usando os.scandir (mais rápido que os.walk)."""
        total = 0
        pilha = [caminho]
        while pilha:
            atual = pilha.pop()
            try:
                with os.scandir(atual) as it:
                    for entry in it:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                pilha.append(entry.path)
                            elif entry.is_file(follow_symlinks=False):
                                total += entry.stat(follow_symlinks=False).st_size
                        except OSError:
                            pass
            except OSError:
                pass
        return total / 1024 / 1024

    def rodar(self):
        tamanho_proj = self._tamanho_pasta(self._caminho_projeto)
        tamanho_venv = 0.0
        if self._caminho_venv and os.path.isdir(self._caminho_venv):
            tamanho_venv = self._tamanho_pasta(self._caminho_venv)
        self.concluido.emit(tamanho_proj, tamanho_venv)


class _WorkerGit(QObject):
    concluido = Signal(object)

    def __init__(self, pasta: str):
        super().__init__()
        self._pasta = pasta

    def rodar(self):
        mapa = {
            " M": "modificado",
            "M ": "modificado",
            "MM": "modificado",
            "AM": "modificado",
            " D": "deletado",
            "D ": "deletado",
            "A ": "novo",
            "??": "novo",
            "R ": "renomeado",
            "RM": "renomeado",
        }
        resultado = {}
        try:
            r = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self._pasta,
                timeout=10,
                **opcoes_processo_sem_console(),
            )
            for linha in r.stdout.splitlines():
                if len(linha) < 4:
                    continue
                codigo  = linha[:2]
                arquivo = linha[3:].strip()
                if " -> " in arquivo:
                    arquivo = arquivo.split(" -> ")[-1]
                caminho_abs = (
                    self._pasta.replace("\\", "/") + "/" + arquivo.replace("\\", "/")
                )
                status = mapa.get(codigo, "modificado")
                resultado[caminho_abs.lower()] = status
        except Exception:
            pass

        # ── Feature 2: propagar status dos arquivos para as pastas pai ──
        # Prioridade: deletado(3) > modificado(2) > renomeado(2) > novo(1)
        _PRIO = {"deletado": 3, "modificado": 2, "renomeado": 2, "novo": 1}
        _PRIO_PARA_STATUS = {3: "deletado", 2: "modificado", 1: "novo"}
        raiz_lower = self._pasta.replace("\\", "/").lower().rstrip("/")

        pastas_prio: dict[str, int] = {}
        for caminho_lower, status in list(resultado.items()):
            prio = _PRIO.get(status, 1)
            pasta = caminho_lower.rsplit("/", 1)[0] if "/" in caminho_lower else ""
            while pasta and len(pasta) > len(raiz_lower):
                prio_atual = pastas_prio.get(pasta, 0)
                if prio > prio_atual:
                    pastas_prio[pasta] = prio
                pasta = pasta.rsplit("/", 1)[0] if "/" in pasta else ""

        for pasta, prio in pastas_prio.items():
            resultado[pasta] = _PRIO_PARA_STATUS.get(prio, "modificado")

        self.concluido.emit(resultado)
