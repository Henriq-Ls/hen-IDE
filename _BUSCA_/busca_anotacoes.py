# 📁 _BUSCA_/busca_anotacoes.py
# coding: utf-8
import os
import re
from PySide6.QtCore import QThread, Signal
from _THREADS_.thread_segura import _ThreadSegura
from .modelo_resultado import ResultadoBusca, TipoBusca
from _LOG_.log import log
_ARQ = "busca_anotacoes.py"
_IGNORAR   = {".git", "__pycache__", ".venv", "node_modules"}
_EXTENSOES = {".py", ".txt", ".md", ".js", ".ts"}

_TAGS = ("TODO", "LEMBRAR", "CONSERTAR", "FAZER", "GAMBIARRA")
_PATTERN = re.compile(
    r"#\s*(" + "|".join(_TAGS) + r")\s*[:\-]?\s*(.*)",
    re.IGNORECASE,
)
_ICONES = {
    "todo":       "fa5s.check-circle",
    "lembrar":    "fa5s.bookmark",
    "consertar":  "fa5s.wrench",
    "fazer":      "fa5s.list-ul",
    "gambiarra":  "fa5s.exclamation-triangle",
}

def _parsear_filtro(termo: str):
    """Retorna (filtro_tag, filtro_texto) a partir de '#marcação ...' ou '#TODO ...'."""
    t = termo.lstrip("#").strip().lower()
    # "#marcação" ou "#marcacao" sozinho → mostra tudo
    if t in ("marcação", "marcacao", ""):
        return "", ""
    # "#marcação consertar" → filtra pelo texto dentro das marcações
    for prefixo in ("marcação ", "marcacao "):
        if t.startswith(prefixo):
            return "", t[len(prefixo):].strip()
    # tag específica: "#TODO", "#FAZER" etc.
    for tag in (x.lower() for x in _TAGS):
        if t.startswith(tag):
            return tag, t[len(tag):].strip()
    # texto livre
    return "", t


def buscar_anotacoes(termo: str, raiz: str, limite: int = 50) -> list[ResultadoBusca]:
    """
    Varre o projeto procurando marcações (#TODO, #LEMBRAR, #CONSERTAR, #FAZER, #GAMBIARRA).
    termo pode ser '#marcação' (todas), '#marcação consertar' (filtra texto)
    ou '#TODO' / '#FAZER' (filtra por tag específica).
    """
    if not raiz or not os.path.isdir(raiz):
        return []

    filtro_tag, filtro_texto = _parsear_filtro(termo)
    resultados: list[ResultadoBusca] = []

    for dirpath, dirnames, filenames in os.walk(raiz):
        dirnames[:] = [d for d in dirnames if d not in _IGNORAR]
        for nome in filenames:
            if os.path.splitext(nome)[1].lower() not in _EXTENSOES:
                continue
            caminho = os.path.join(dirpath, nome)
            rel     = os.path.relpath(caminho, raiz)
            try:
                with open(caminho, encoding="utf-8", errors="ignore") as f:
                    for num, linha in enumerate(f, 1):
                        m = _PATTERN.search(linha)
                        if not m:
                            continue
                        tag_achada = m.group(1).lower()
                        conteudo   = m.group(2).strip()
                        if filtro_tag and tag_achada != filtro_tag:
                            continue
                        if filtro_texto and filtro_texto not in conteudo.lower():
                            continue
                        icone = _ICONES.get(tag_achada, "fa5s.tag")
                        resultados.append(ResultadoBusca(
                            tipo=TipoBusca.ANOTACAO,
                            titulo=f"#{tag_achada.upper()}  {conteudo}",
                            subtitulo=f"{rel}  linha {num}",
                            caminho=caminho,
                            linha=num - 1,
                            icone=icone,
                        ))
                        if len(resultados) >= limite:
                            return resultados
            except Exception as e:
                log.aviso(_ARQ, "buscar_anotacoes", f"ignorado: {caminho} — {e}")

    return resultados


class AnotacoesThread(_ThreadSegura):
    """Executa varredura de marcações em segundo plano.
    Emite resultado_encontrado(ResultadoBusca) e busca_concluida().
    Usa isInterruptionRequested() para cancelamento cooperativo.
    """
    resultado_encontrado = Signal(object)
    busca_concluida      = Signal()

    def __init__(self, termo: str, raiz: str, limite: int = 500, parent=None):
        super().__init__(parent)
        self._termo  = termo
        self._raiz   = raiz
        self._limite = limite

    def run(self):
        if not self._raiz or not os.path.isdir(self._raiz):
            self.busca_concluida.emit()
            return

        filtro_tag, filtro_texto = _parsear_filtro(self._termo)
        contagem = 0

        for dirpath, dirnames, filenames in os.walk(self._raiz):
            if self.isInterruptionRequested():
                break
            dirnames[:] = [d for d in dirnames if d not in _IGNORAR]
            for nome in filenames:
                if self.isInterruptionRequested():
                    break
                if os.path.splitext(nome)[1].lower() not in _EXTENSOES:
                    continue
                caminho = os.path.join(dirpath, nome)
                rel = os.path.relpath(caminho, self._raiz)
                try:
                    with open(caminho, encoding="utf-8", errors="ignore") as f:
                        for num, linha in enumerate(f, 1):
                            if self.isInterruptionRequested():
                                break
                            m = _PATTERN.search(linha)
                            if not m:
                                continue
                            tag_achada = m.group(1).lower()
                            conteudo   = m.group(2).strip()
                            if filtro_tag and tag_achada != filtro_tag:
                                continue
                            if filtro_texto and filtro_texto not in conteudo.lower():
                                continue
                            icone = _ICONES.get(tag_achada, "fa5s.tag")
                            self.resultado_encontrado.emit(ResultadoBusca(
                                tipo=TipoBusca.ANOTACAO,
                                titulo=f"#{tag_achada.upper()}  {conteudo}",
                                subtitulo=f"{rel}  linha {num}",
                                caminho=caminho,
                                linha=num - 1,
                                icone=icone,
                            ))
                            contagem += 1
                            if contagem >= self._limite:
                                self.busca_concluida.emit()
                                return
                except Exception as e:
                    log.aviso(_ARQ, "AnotacoesThread.run", f"ignorado: {caminho} — {e}")

        self.busca_concluida.emit()
