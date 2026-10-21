"""Localiza o interpretador virtual do projeto selecionado."""
from pathlib import Path


def achar_python_projeto(caminho_projeto: str) -> str | None:
    raiz = Path(caminho_projeto).resolve()
    candidatos = (
        raiz / ".venv" / "Scripts" / "python.exe",
        raiz / ".venv" / "bin" / "python",
        raiz / "venv" / "Scripts" / "python.exe",
        raiz / "venv" / "bin" / "python",
    )
    for candidato in candidatos:
        if candidato.is_file():
            return str(candidato)
    return None
