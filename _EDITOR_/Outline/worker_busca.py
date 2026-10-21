# 📁 _EDITOR_/Outline/worker_busca.py
# -*- coding: utf-8 -*-
import os
from PySide6.QtCore import Signal, QObject
from _THREADS_.diagnostico_workers import event, weak_editor
_IGNORAR = {".venv", "__pycache__", ".git", ".hein", "node_modules",
            ".mypy_cache", ".pytest_cache", "dist", "build"}

_EXT_BUSCA = {
    ".py", ".json", ".txt", ".md", ".yaml", ".yml",
    ".html", ".htm", ".xml", ".csv", ".ini", ".toml",
}

_MODO_OUTLINE = "OUTLINE"
_MODO_TAREFAS = "TAREFAS"
_MODO_BUSCA        = "BUSCA"
_MODO_ARQUIVO_NOME = "ARQUIVO_NOME"  # busca por nome de arquivo

class _WorkerBusca(QObject):
    resultado = Signal(list)
    concluido = Signal()

    def __init__(self, projeto_path: str, termo: str, modo: str,
                 task: str = "", editor=None, edit_generation: int = 0):
        super().__init__()
        self._projeto = projeto_path
        self._termo   = termo.lower()
        self._modo    = modo
        self._parar   = False
        self._hein_diag_task = task
        self._hein_diag_component = "OUTLINEBUSCA"
        self._hein_diag_editor = weak_editor(editor)
        self._hein_diag_edit_generation = edit_generation

    def parar(self):
        self._parar = True
        event("CANCEL_REQUESTED", "OUTLINEBUSCA", self._hein_diag_task,
              obj=self, editor=self._hein_diag_editor)

    # ⚠️  função grande (52 linhas) | except genérico vazio
    def executar(self):
        event("RUN_ENTER", "OUTLINEBUSCA", self._hein_diag_task,
              obj=self, editor=self._hein_diag_editor)
        if not self._projeto or not os.path.isdir(self._projeto):
            self.concluido.emit()
            event("RESULT_EMITTED", "OUTLINEBUSCA", self._hein_diag_task,
                  obj=self, editor=self._hein_diag_editor, result_count=0)
            event("RUN_EXIT", "OUTLINEBUSCA", self._hein_diag_task,
                  obj=self, editor=self._hein_diag_editor)

            return

        resultados = []
        for raiz, pastas, arquivos in os.walk(self._projeto):
            pastas[:] = [p for p in pastas if p not in _IGNORAR]

            if self._parar:
                break

            for nome_arq in arquivos:
                if self._parar:
                    break

                caminho_abs = os.path.join(raiz, nome_arq)
                ext = os.path.splitext(nome_arq)[1].lower()

                if self._modo == _MODO_TAREFAS:
                    if ext != ".py":
                        continue
                elif self._modo == _MODO_ARQUIVO_NOME:
                    # busca por nome de arquivo — não lê conteúdo
                    if self._termo in nome_arq.lower():
                        caminho_rel = os.path.relpath(caminho_abs, self._projeto)
                        resultados.append((caminho_rel, caminho_abs, 1, nome_arq))
                    continue
                else:
                    if ext not in _EXT_BUSCA:
                        continue

                try:
                    with open(caminho_abs, "r", encoding="utf-8", errors="ignore") as f:
                        for num, linha in enumerate(f, 1):
                            if self._parar:
                                break
                            if self._termo in linha.lower():
                                caminho_rel = os.path.relpath(caminho_abs, self._projeto)
                                resultados.append((
                                    caminho_rel,
                                    caminho_abs,
                                    num,
                                    linha.rstrip()
                                ))
                except Exception:
                    pass

        if not self._parar:
            self.resultado.emit(resultados)
            event("RESULT_EMITTED", "OUTLINEBUSCA", self._hein_diag_task,
                  obj=self, editor=self._hein_diag_editor,
                  result_count=len(resultados))
        self.concluido.emit()
        event("RUN_EXIT", "OUTLINEBUSCA", self._hein_diag_task,
              obj=self, editor=self._hein_diag_editor,
              cancelled=self._parar)
