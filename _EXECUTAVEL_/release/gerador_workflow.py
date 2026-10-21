"""Gera no projeto os arquivos de build necessários ao GitHub Actions."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console
from _LOG_.log import log

_ARQ = "executavel.gerador_workflow"

_BUILD_CI = r'''"""Build Windows do executável; gerado pela hein Basic IDE."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / ".hein" / "executavel" / "executavel.json"
DIST = ROOT / "dist"


def _falhar(mensagem: str, codigo: int = 1) -> None:
    sys.stderr.write(mensagem + "\n")
    raise SystemExit(codigo)


def _relativo(valor: str, campo: str) -> Path:
    caminho = Path(str(valor or ""))
    if caminho.is_absolute():
        _falhar(f"{campo} deve ser relativo à pasta do projeto.")
    resolvido = (ROOT / caminho).resolve()
    try:
        resolvido.relative_to(ROOT.resolve())
    except ValueError:
        _falhar(f"{campo} não pode sair da pasta do projeto.")
    if not resolvido.exists():
        _falhar(f"{campo} não existe: {valor}")
    return resolvido


def _destino_seguro(valor: str, campo: str) -> str:
    destino = str(valor or ".").replace("\\", "/").strip()
    caminho = Path(destino)
    if caminho.is_absolute() or ".." in caminho.parts:
        _falhar(f"{campo} não pode sair da pasta do executável.")
    return destino or "."


def main() -> None:
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        _falhar(f"Não foi possível ler executavel.json: {exc}")

    nome = str(config.get("nome") or "").strip()
    if not nome or nome in {".", ".."} or any(c in nome for c in '<>:"/\\|?*'):
        _falhar("O nome do executável contém caracteres inválidos.")
    entrada = _relativo(config.get("ponto_entrada", "main.py"), "Ponto de entrada")
    if entrada.suffix.lower() != ".py":
        _falhar("O ponto de entrada precisa ser um arquivo .py.")

    comando = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--name", nome, "--distpath", str(DIST),
        "--workpath", str(ROOT / ".hein" / "executavel" / "build" / "work"),
    ]
    comando.append("--onefile" if config.get("onefile") else "--onedir")
    comando.append("--console" if config.get("console") else "--windowed")
    icone = config.get("icone")
    if icone:
        comando += ["--icon", str(_relativo(icone, "Ícone"))]
    for item in (config.get("add_data", []) or []) + (config.get("arquivos_extra", []) or []):
        if isinstance(item, dict) and item.get("origem"):
            origem = _relativo(item["origem"], "Arquivo de dados")
            destino = _destino_seguro(item.get("destino"), "Destino dos dados")
            comando += ["--add-data", f"{origem};{destino}"]
    for item in config.get("hidden_imports", []) or []:
        if str(item).strip():
            comando += ["--hidden-import", str(item).strip()]
    for item in config.get("collect_submodules", []) or []:
        if str(item).strip():
            comando += ["--collect-submodules", str(item).strip()]
    for item in config.get("collect_all", []) or []:
        if str(item).strip():
            comando += ["--collect-all", str(item).strip()]

    versao = str(config.get("versao") or "0.1.0").strip().lstrip("vV")
    versao_partes = versao.replace("-", ".").split(".")
    versao_partes = (versao_partes + ["0", "0", "0"])[:4]
    versao_partes = [parte if parte.isdigit() else "0" for parte in versao_partes]
    pasta_build = ROOT / ".hein" / "executavel" / "build"
    pasta_build.mkdir(parents=True, exist_ok=True)
    metadata = pasta_build / "versioninfo.yml"
    metadata.write_text(
        "Version: " + ".".join(versao_partes) + "\n"
        + "FileDescription: " + json.dumps(nome, ensure_ascii=False) + "\n"
        + "InternalName: " + json.dumps(nome, ensure_ascii=False) + "\n"
        + "OriginalFilename: " + json.dumps(nome + ".exe", ensure_ascii=False) + "\n"
        + "ProductName: " + json.dumps(nome, ensure_ascii=False) + "\n"
        + "Translation: 1033, 1200\n",
        encoding="utf-8",
    )
    version_file = pasta_build / "versionfile.txt"
    gerador = subprocess.run(
        [sys.executable, "-m", "pyinstaller_versionfile",
         "--metadata-file", str(metadata), "--outfile", str(version_file)],
        cwd=ROOT, check=False,
    )
    if gerador.returncode == 0 and version_file.is_file():
        comando += ["--version-file", str(version_file)]

    comando.append(str(entrada))
    concluido = subprocess.run(comando, cwd=ROOT, check=False)
    if concluido.returncode:
        _falhar("PyInstaller falhou.", concluido.returncode)

    if config.get("onefile"):
        artefato = DIST / f"{nome}.exe"
        if not artefato.is_file():
            _falhar(f"Executável não encontrado: {artefato}")
    else:
        pasta = DIST / nome
        if not pasta.is_dir():
            _falhar(f"Pasta de build não encontrada: {pasta}")
        artefato = DIST / f"{nome}-windows.zip"
        with zipfile.ZipFile(artefato, "w", zipfile.ZIP_DEFLATED) as arquivo_zip:
            for arquivo in pasta.rglob("*"):
                if arquivo.is_file():
                    arquivo_zip.write(arquivo, arquivo.relative_to(DIST))
    sys.stdout.write(f"Artefato pronto: {artefato}\n")


if __name__ == "__main__":
    main()
'''


def _versao_python_projeto(caminho_projeto: Path) -> str:
    from _EXECUTAVEL_.venv_projeto import achar_python_projeto
    python = achar_python_projeto(str(caminho_projeto))
    if not python:
        return "3.12"
    try:
        resultado = subprocess.run(
            [python, "-c", "import sys; sys.stdout.write(f'{sys.version_info.major}.{sys.version_info.minor}')"],
            cwd=caminho_projeto, capture_output=True, text=True, timeout=10,
            **opcoes_processo_sem_console(),
        )
        if resultado.returncode == 0 and re.fullmatch(r"\d+\.\d+", resultado.stdout.strip()):
            return resultado.stdout.strip()
    except Exception as exc:
        log.aviso(_ARQ, "_versao_python_projeto", str(exc))
    return "3.12"


def gerar_workflow_release(caminho_projeto: str, config: dict | None = None) -> str:
    raiz = Path(caminho_projeto).resolve()
    caminho_ci = raiz / ".hein" / "executavel" / "build_ci.py"
    caminho_ci.parent.mkdir(parents=True, exist_ok=True)
    caminho_ci.write_text(_BUILD_CI, encoding="utf-8")

    nome = str((config or {}).get("nome") or "app").strip()
    nome = re.sub(r"[^A-Za-z0-9_.-]+", "-", nome).strip(".-") or "app"
    onefile = bool((config or {}).get("onefile", False))
    if onefile:
        artefato = f"dist/{nome}.exe"
    else:
        artefato = f"dist/{nome}-windows.zip"
    python_version = _versao_python_projeto(raiz)
    workflow = (
        "name: Build e release do executável\n\n"
        "on:\n"
        "  push:\n"
        "    tags:\n"
        "      - 'v*'\n"
        "  workflow_dispatch:\n\n"
        "permissions:\n"
        "  contents: write\n\n"
        "jobs:\n"
        "  build-windows:\n"
        "    runs-on: windows-latest\n"
        "    steps:\n"
        "      - name: Checkout\n"
        "        uses: actions/checkout@v4\n"
        "      - name: Configurar Python\n"
        "        uses: actions/setup-python@v5\n"
        "        with:\n"
        f"          python-version: {json.dumps(python_version)}\n"
        "      - name: Instalar dependências do projeto\n"
        "        shell: pwsh\n"
        "        run: |\n"
        "          if (Test-Path '.hein/executavel/requirements.txt') { python -m pip install -r '.hein/executavel/requirements.txt' }\n"
        "          python -m pip install pyinstaller pyinstaller-versionfile\n"
        "      - name: Gerar executável\n"
        "        run: python .hein/executavel/build_ci.py\n"
        "      - name: Publicar release\n"
        "        uses: softprops/action-gh-release@v2\n"
        "        with:\n"
        "          token: ${{ secrets.GITHUB_TOKEN }}\n"
        "          files: " + json.dumps(artefato) + "\n"
    )
    destino = raiz / ".github" / "workflows" / "release-executavel.yml"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(workflow, encoding="utf-8")
    log.ok(_ARQ, "gerar_workflow_release", f"Workflow criado em {destino}")
    return str(destino)
