# 📁 _BUSCA_/busca_simbolos.py
# coding: utf-8
import ast
import os
from .modelo_resultado import ResultadoBusca, TipoBusca
from _LOG_.log import log
_ARQ = "busca_simbolos.py"
_IGNORAR = {".git", "__pycache__", ".venv", "node_modules"}

def buscar_simbolos(termo: str, raiz: str, limite: int = 30) -> list[ResultadoBusca]:
    if not raiz or not os.path.isdir(raiz):

        return []

    termo_lower = termo.lower()
    resultados: list[ResultadoBusca] = []

    for dirpath, dirnames, filenames in os.walk(raiz):
        dirnames[:] = [d for d in dirnames if d not in _IGNORAR]
        for nome in filenames:
            if not nome.endswith(".py"):
                continue
            caminho = os.path.join(dirpath, nome)
            try:
                with open(caminho, encoding="utf-8", errors="ignore") as f:
                    source = f.read()
                tree = ast.parse(source, filename=caminho)
            except Exception as e:
                log.aviso(_ARQ, "buscar_simbolos", f"ignorado: {caminho} — {e}")
                continue

            rel = os.path.relpath(caminho, raiz)
            for node in ast.walk(tree):
                nome_sim = None
                tipo_sim = ""
                icone    = ""
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    nome_sim = node.name
                    tipo_sim = "def"
                    icone    = "fa5s.code"
                elif isinstance(node, ast.ClassDef):
                    nome_sim = node.name
                    tipo_sim = "class"
                    icone    = "mdi6.shape-outline"

                if nome_sim and termo_lower in nome_sim.lower():
                    resultados.append(ResultadoBusca(
                        tipo=TipoBusca.SIMBOLO,
                        titulo=f"{tipo_sim} {nome_sim}",
                        subtitulo=f"{rel}  linha {node.lineno}",
                        caminho=caminho,
                        linha=node.lineno - 1,
                        icone=icone,
                    ))
                    if len(resultados) >= limite:

                        return resultados

    return resultados
