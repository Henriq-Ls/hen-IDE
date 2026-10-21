"""Descobre dependências e arquivos do projeto para o PyInstaller."""
from __future__ import annotations

import os
from pathlib import Path

from _EXECUTAVEL_.arvore import gerar_arvore
from _EXECUTAVEL_.requirements import gerar_hidden_imports

_EXTENSOES_DADOS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".txt", ".md", ".qss",
    ".css", ".ui", ".db", ".sqlite", ".ttf", ".otf", ".wav", ".mp3",
    ".mp4", ".pdf", ".html", ".xml",
}


def _dependencias(caminho: Path) -> list[str]:
    if not caminho.is_file():
        return []
    resultado = []
    for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith(("#", "-")):
            resultado.append(linha)
    return resultado


def analisar_projeto(caminho_projeto: str, requirements_extra=None,
                     python_venv: str | None = None, padroes_ignorar=None) -> dict:
    raiz = Path(caminho_projeto).resolve()
    pasta_cfg = raiz / ".hein" / "executavel"
    arvore = gerar_arvore(
        str(raiz),
        padroes_ignorar or set(),
        str(pasta_cfg / "arvore.txt"),
        caminho_json=str(pasta_cfg / "arvore.json"),
    )
    add_data = []
    collect_submodules = set()
    for item in arvore:
        rel_pasta = item["pasta"]
        if item["tem_init"] and rel_pasta != ".":
            pacote_raiz = rel_pasta.split("/")[0]
            if (raiz / pacote_raiz / "__init__.py").is_file():
                collect_submodules.add(pacote_raiz)
        for nome in item["arquivos"]:
            if Path(nome).suffix.lower() not in _EXTENSOES_DADOS:
                continue
            origem = (Path(rel_pasta) / nome).as_posix() if rel_pasta != "." else nome
            destino = rel_pasta if rel_pasta != "." else "."
            add_data.append({"origem": origem, "destino": destino})
    campos = {
        "dependencias": _dependencias(pasta_cfg / "requirements.txt"),
        "add_data": add_data,
        "hidden_imports": gerar_hidden_imports(str(raiz), padroes_ignorar=padroes_ignorar),
        "collect_submodules": sorted(collect_submodules),
        "collect_all": sorted({
            str(item).strip() for item in (requirements_extra or []) if str(item).strip()
        }),
    }
    return campos
