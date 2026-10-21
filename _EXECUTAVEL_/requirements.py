"""Leitura de dependências e imports do ambiente virtual do projeto."""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

from _EXECUTAVEL_.venv_projeto import achar_python_projeto
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console

_IGNORAR = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build",
    ".hein", ".pytest_cache", ".mypy_cache",
}


def site_packages_projeto(caminho_projeto: str) -> Path | None:
    python = achar_python_projeto(caminho_projeto)
    if not python:
        return None
    raiz_venv = Path(python).parent.parent
    candidatos = [
        raiz_venv / "Lib" / "site-packages",
        *sorted((raiz_venv / "lib").glob("python*/site-packages")),
    ]
    return next((p for p in candidatos if p.is_dir()), None)


def gerar_requirements(python_venv: str, caminho_projeto: str) -> str:
    resultado = subprocess.run(
        [python_venv, "-m", "pip", "freeze"],
        cwd=caminho_projeto,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        **opcoes_processo_sem_console(),
    )
    if resultado.returncode:
        raise RuntimeError((resultado.stderr or resultado.stdout).strip()
                           or "pip freeze falhou.")
    caminho = Path(caminho_projeto) / ".hein" / "executavel" / "requirements.txt"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(resultado.stdout.rstrip() + "\n", encoding="utf-8")
    return str(caminho)


def _modulos_instalados(site_packages: Path | None) -> set[str]:
    if site_packages is None:
        return set()
    nomes = set()
    for item in site_packages.iterdir():
        if item.name.endswith((".dist-info", ".egg-info")):
            top = item / "top_level.txt"
            if top.is_file():
                try:
                    nomes.update(l.strip() for l in top.read_text(encoding="utf-8").splitlines()
                                 if l.strip().isidentifier())
                except OSError:
                    pass
        elif item.is_dir() and item.name.isidentifier():
            nomes.add(item.name)
        elif item.suffix == ".py" and item.stem.isidentifier():
            nomes.add(item.stem)
    return nomes


def gerar_hidden_imports(caminho_projeto: str, extras=None,
                         padroes_ignorar=None) -> list[str]:
    raiz = Path(caminho_projeto).resolve()
    instalados = _modulos_instalados(site_packages_projeto(str(raiz)))
    stdlib = getattr(sys, "stdlib_module_names", set())
    ignorar = {str(item) for item in (padroes_ignorar or set())}
    encontrados = set()
    for atual, diretorios, arquivos in os.walk(raiz):
        diretorios[:] = [
            d for d in diretorios
            if d not in _IGNORAR and d not in ignorar and not d.startswith(".")
            and not any(Path(d).match(padrao) for padrao in ignorar)
        ]
        for nome in arquivos:
            if not nome.endswith(".py") or any(Path(nome).match(p) for p in ignorar):
                continue
            arquivo = Path(atual) / nome
            try:
                arvore = ast.parse(arquivo.read_text(encoding="utf-8", errors="replace"))
            except (OSError, SyntaxError, ValueError):
                continue
            for no in ast.walk(arvore):
                if isinstance(no, ast.Import):
                    candidatos = [alias.name for alias in no.names]
                elif isinstance(no, ast.ImportFrom) and no.module:
                    candidatos = [no.module]
                else:
                    continue
                for modulo in candidatos:
                    raiz_modulo = modulo.split(".", 1)[0]
                    if raiz_modulo in instalados and raiz_modulo not in stdlib:
                        encontrados.add(modulo)
    encontrados.update(str(x).strip() for x in (extras or []) if str(x).strip())
    return sorted(encontrados)
