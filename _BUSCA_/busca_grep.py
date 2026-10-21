# 📁 _BUSCA_/busca_grep.py
# coding: utf-8
import os
from .modelo_resultado import ResultadoBusca, TipoBusca
from PySide6.QtCore import QThread, Signal
from _THREADS_.thread_segura import _ThreadSegura
from _LOG_.log import log
_ARQ = "busca_grep.py"
_IGNORAR  = {".git", "__pycache__", ".venv", "node_modules", ".idea"}
_EXTENSOES = {".py", ".txt", ".md", ".json", ".yaml", ".yml",
              ".toml", ".cfg", ".ini", ".csv", ".js", ".ts", ".html"}

class GrepThread(_ThreadSegura):
    resultado_encontrado = Signal(object)   # emite ResultadoBusca
    busca_concluida      = Signal()

    def __init__(self, termo: str, raiz: str, limite: int = 50, parent=None):
        super().__init__(parent)
        self._termo  = termo
        self._raiz   = raiz
        self._limite = limite

    # ⚠️  except genérico vazio
    def run(self):
        if not self._raiz or not os.path.isdir(self._raiz):
            self.busca_concluida.emit()

            return

        termo_lower = self._termo.lower()
        contagem    = 0

        for dirpath, dirnames, filenames in os.walk(self._raiz):
            if self.isInterruptionRequested():
                return
            dirnames[:] = [d for d in dirnames if d not in _IGNORAR]
            for nome in filenames:
                if self.isInterruptionRequested():
                    return
                if os.path.splitext(nome)[1].lower() not in _EXTENSOES:
                    continue
                caminho = os.path.join(dirpath, nome)
                try:
                    with open(caminho, encoding="utf-8", errors="ignore") as f:
                        for num, linha in enumerate(f, 1):
                            if termo_lower in linha.lower():
                                col = linha.lower().index(termo_lower)
                                rel = os.path.relpath(caminho, self._raiz)
                                self.resultado_encontrado.emit(ResultadoBusca(
                                    tipo=TipoBusca.GREP,
                                    titulo=linha.strip()[:80],
                                    subtitulo=f"{rel}  linha {num}",
                                    caminho=caminho,
                                    linha=num - 1,
                                    coluna=col,
                                    termo=self._termo,
                                    icone="fa5s.search",
                                ))
                                contagem += 1
                                if contagem >= self._limite:
                                    self.busca_concluida.emit()

                                    return

                except Exception as e:
                    log.aviso(_ARQ, "run", f"ignorado: {caminho} — {e}")

        self.busca_concluida.emit()
