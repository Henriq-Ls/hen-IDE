"""Gera uma representação compacta dos arquivos relevantes do projeto."""
from __future__ import annotations

import json
import os
from pathlib import Path

_IGNORAR = {
    ".git", ".hg", ".svn", ".venv", "venv", "__pycache__", "node_modules",
    "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache",
}
_EXTENSOES_DADOS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".txt", ".md",
    ".qss", ".css", ".ui", ".db", ".sqlite", ".ttf", ".otf", ".wav",
    ".mp3", ".mp4", ".pdf", ".html", ".xml",
}


def gerar_arvore(caminho_projeto: str, segundo=None,
                 caminho_txt: str | None = None, *, caminho_json: str | None = None) -> list[dict]:
    """Aceita tanto padrões de exclusão (API do Explorer) quanto destinos de saída."""
    raiz = Path(caminho_projeto).resolve()
    padroes = set()
    if isinstance(segundo, (set, list, tuple)):
        padroes = {str(item) for item in segundo}
    elif segundo and caminho_json is None:
        caminho_json = str(segundo)
    elif segundo:
        padroes = {str(item) for item in segundo}
    resultado = []
    for atual, diretorios, arquivos in os.walk(raiz):
        diretorios[:] = sorted(
            nome for nome in diretorios
            if nome not in _IGNORAR
            and nome not in padroes
            and not nome.startswith(".")
            and not any(Path(nome).match(padrao) for padrao in padroes)
        )
        pasta = Path(atual)
        relativos = sorted(
            nome for nome in arquivos
            if not nome.startswith(".") or nome in {".env.example"}
            if not any(Path(nome).match(padrao) for padrao in padroes)
        )
        if not relativos:
            continue
        rel_pasta = pasta.relative_to(raiz).as_posix()
        resultado.append({
            "pasta": rel_pasta or ".",
            "arquivos": relativos,
            "tem_init": "__init__.py" in relativos,
            "tem_dados": any(Path(nome).suffix.lower() in _EXTENSOES_DADOS
                             for nome in relativos),
        })
    if caminho_json:
        destino = Path(caminho_json)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    if caminho_txt:
        destino = Path(caminho_txt)
        destino.parent.mkdir(parents=True, exist_ok=True)
        linhas = []
        for item in resultado:
            linhas.append(f"{item['pasta']}/")
            linhas.extend(f"  {nome}" for nome in item["arquivos"])
        destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return resultado
