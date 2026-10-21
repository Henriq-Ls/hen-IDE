"""Geração do modelo PySide6 completo para projetos novos."""
from __future__ import annotations

import os
import re
import shutil
import unicodedata
from pathlib import Path

_ARQUIVOS_DE_INSTRUCAO = {"LEIA_ISSO_PRIMEIRO.txt"}
_ARQUIVOS_TEXTO = {
    ".py", ".txt", ".md", ".json", ".toml", ".ini", ".yaml", ".yml",
    ".cfg", ".gitignore",
}


def slug_projeto(nome: str) -> str:
    """Converte o nome visível em identificador seguro para pastas/config."""
    normalizado = unicodedata.normalize("NFKD", nome)
    ascii_nome = normalizado.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_nome).strip("_")
    return slug or "projeto"


def caminho_template() -> Path:
    """Localiza o template versionado ao lado da pasta hein-basic-ide."""
    raiz_workspace = Path(__file__).resolve().parents[3]
    pasta = raiz_workspace / "_template_pyside6"
    if not pasta.is_dir():
        raise FileNotFoundError(
            f"Template PySide6 não encontrado no caminho esperado: {pasta}"
        )
    return pasta


def gerar_projeto_pyside6(destino: str | os.PathLike, nome: str) -> str:
    """Copia o esqueleto, substitui os identificadores e devolve main.py.

    Arquivos que já existem no destino são substituídos; arquivos não
    relacionados ao template são preservados. A confirmação para reutilizar
    uma pasta existente é responsabilidade da tela de criação.
    """
    origem = caminho_template()
    raiz_destino = Path(destino)
    identificadores = {
        "__PROJECT_NAME__": nome.strip(),
        "__PROJECT_SLUG__": slug_projeto(nome),
    }

    for raiz_atual, diretorios, arquivos in os.walk(origem):
        diretorios[:] = sorted(
            pasta for pasta in diretorios
            if pasta not in {"__pycache__", ".git"}
        )
        relativo = Path(raiz_atual).relative_to(origem)
        destino_atual = raiz_destino / relativo
        destino_atual.mkdir(parents=True, exist_ok=True)

        for nome_arquivo in arquivos:
            if (
                nome_arquivo in _ARQUIVOS_DE_INSTRUCAO
                or nome_arquivo.endswith((".pyc", ".pyo"))
            ):
                continue
            arquivo_origem = Path(raiz_atual) / nome_arquivo
            arquivo_destino = destino_atual / nome_arquivo
            arquivo_destino.parent.mkdir(parents=True, exist_ok=True)

            if arquivo_origem.suffix.lower() in _ARQUIVOS_TEXTO or nome_arquivo == ".gitignore":
                conteudo = arquivo_origem.read_text(encoding="utf-8")
                for marcador, valor in identificadores.items():
                    conteudo = conteudo.replace(marcador, valor)
                arquivo_destino.write_text(conteudo, encoding="utf-8", newline="")
            else:
                shutil.copy2(arquivo_origem, arquivo_destino)

    main_py = raiz_destino / "main.py"
    if not main_py.is_file():
        raise FileNotFoundError("O template foi copiado, mas main.py não foi criado.")
    return str(main_py)


__all__ = ["caminho_template", "gerar_projeto_pyside6", "slug_projeto"]
