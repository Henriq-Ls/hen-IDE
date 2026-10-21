# 📁 _BUSCA_/busca_arquivos.py
# coding: utf-8
import os
from .modelo_resultado import ResultadoBusca, TipoBusca
_IGNORAR = {".git", "__pycache__", ".venv", "node_modules", ".idea", ".mypy_cache"}

def fuzzy_score(termo: str, nome_arquivo: str) -> float:
    """
    Pontuação de relevância para busca fuzzy por nome de arquivo.
    Retorna 0.0 se o termo não é subsequência do nome.
    Maior = mais relevante. Bônus para início de palavra/separador.
    """
    t = termo.lower()
    n = nome_arquivo.lower()
    score = 0.0
    prev = -1
    for c in t:
        idx = n.find(c, prev + 1)
        if idx == -1:
            return 0.0
        score += 1.0
        if idx == 0 or not n[idx - 1].isalnum():
            score += 3.0        # bônus: início de palavra ou após separador
        if prev != -1:
            score -= 0.5 * (idx - prev - 1)   # penalidade por gap
        prev = idx
    return score

def buscar_arquivos(termo: str, raiz: str, limite: int = 20) -> list[ResultadoBusca]:
    if not raiz or not os.path.isdir(raiz):

        return []

    termo_lower = termo.lower()
    resultados: list[ResultadoBusca] = []
    for dirpath, dirnames, filenames in os.walk(raiz):
        dirnames[:] = [d for d in dirnames if d not in _IGNORAR]
        for nome in filenames:
            if termo_lower in nome.lower():
                caminho = os.path.join(dirpath, nome)
                rel = os.path.relpath(caminho, raiz)
                resultados.append(ResultadoBusca(
                    tipo=TipoBusca.ARQUIVO,
                    titulo=nome,
                    subtitulo=rel,
                    caminho=caminho,
                    icone="fa5s.file-code",
                ))
                if len(resultados) >= limite:

                    return resultados

    return resultados

def buscar_recentes(recentes: list[str], raiz: str = "") -> list[ResultadoBusca]:
    resultados = []
    for caminho in recentes:
        if os.path.isfile(caminho):
            rel = os.path.relpath(caminho, raiz) if raiz else caminho
            resultados.append(ResultadoBusca(
                tipo=TipoBusca.RECENTE,
                titulo=os.path.basename(caminho),
                subtitulo=rel,
                caminho=caminho,
                icone="fa5s.history",
            ))

    return resultados
