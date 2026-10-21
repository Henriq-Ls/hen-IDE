"""Gera um .spec portátil e version resource opcional para o build local."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from PySide6.QtCore import Signal
from _THREADS_.thread_segura import _ThreadSegura
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console
from _LOG_.log import log

_ARQ = "executavel.gerador_spec"


def _relativo_seguro(valor: str, raiz: Path, campo: str) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""
    caminho = Path(texto)
    if caminho.is_absolute():
        raise ValueError(f"{campo} deve ser relativo à pasta do projeto.")
    resolvido = (raiz / caminho).resolve()
    try:
        rel = resolvido.relative_to(raiz.resolve())
    except ValueError as exc:
        raise ValueError(f"{campo} não pode sair da pasta do projeto.") from exc
    if not resolvido.exists():
        raise FileNotFoundError(f"{campo} não existe: {texto}")
    return rel.as_posix()


def _destino_seguro(valor: str, campo: str) -> str:
    destino = str(valor or ".").replace("\\", "/").strip()
    partes = Path(destino).parts
    if Path(destino).is_absolute() or re.match(r"^[A-Za-z]:", destino) or ".." in partes:
        raise ValueError(f"{campo} não pode sair da pasta do executável.")
    return destino or "."


def gerar_spec(python_venv: str, caminho_projeto: str, config: dict,
               hidden_imports=None) -> str:
    raiz = Path(caminho_projeto).resolve()
    nome = str(config.get("nome") or "").strip()
    if not nome or not re.fullmatch(r"[A-Za-z0-9_. -]+", nome) or nome in {".", ".."}:
        raise ValueError("O nome do executável contém caracteres inválidos.")
    entrada = _relativo_seguro(config.get("ponto_entrada", "main.py"), raiz, "Ponto de entrada")
    if not entrada.lower().endswith(".py"):
        raise ValueError("O ponto de entrada deve ser um arquivo Python (.py).")

    pasta_build = raiz / ".hein" / "executavel" / "build"
    pasta_build.mkdir(parents=True, exist_ok=True)
    spec_path = pasta_build / f"{nome}.spec"

    dados = []
    for item in config.get("add_data", []) or []:
        if not isinstance(item, dict):
            continue
        origem = _relativo_seguro(item.get("origem", ""), raiz, "Arquivo de dados")
        destino = _destino_seguro(item.get("destino", "."), "Destino dos dados")
        if origem:
            dados.append((origem, destino))
    for item in config.get("arquivos_extra", []) or []:
        if not isinstance(item, dict):
            continue
        origem = _relativo_seguro(item.get("origem", ""), raiz, "Arquivo extra")
        destino = _destino_seguro(item.get("destino", "."), "Destino do arquivo extra")
        if origem:
            dados.append((origem, destino))

    icone = _relativo_seguro(config.get("icone", ""), raiz, "Ícone") if config.get("icone") else ""
    hidden = sorted({str(x).strip() for x in (hidden_imports or []) if str(x).strip()})
    hidden.extend(str(x).strip() for x in config.get("hidden_imports", []) if str(x).strip())
    hidden = sorted(set(hidden))
    coletar_sub = sorted(set(str(x).strip() for x in config.get("collect_submodules", []) if str(x).strip()))
    coletar_tudo = sorted(set(str(x).strip() for x in config.get("collect_all", []) if str(x).strip()))
    linhas = [
        "from pathlib import Path",
        "from PyInstaller.utils.hooks import collect_all, collect_submodules",
        "ROOT = Path(SPECPATH).resolve().parents[2]",
        f"_data_cfg = {dados!r}",
        "datas = [(str(ROOT / src), dst) for src, dst in _data_cfg]",
        "binaries = []",
        f"hiddenimports = {hidden!r}",
        f"for _pkg in {coletar_sub!r}:",
        "    hiddenimports += collect_submodules(_pkg)",
        f"for _pkg in {coletar_tudo!r}:",
        "    _d, _b, _h = collect_all(_pkg)",
        "    datas += _d",
        "    binaries += _b",
        "    hiddenimports += _h",
        f"_icon_cfg = {icone!r}",
        "_icon_path = str(ROOT / _icon_cfg) if _icon_cfg else None",
        "_version_path = str(Path(SPECPATH) / 'versionfile.txt')",
        "_version_path = _version_path if Path(_version_path).is_file() else None",
        "a = Analysis(",
        f"    [str(ROOT / {entrada!r})],",
        "    pathex=[str(ROOT)],",
        "    binaries=binaries,",
        "    datas=datas,",
        "    hiddenimports=hiddenimports,",
        "    hookspath=[],",
        "    hooksconfig={},",
        "    runtime_hooks=[],",
        "    excludes=[],",
        "    noarchive=False,",
        "    optimize=0,",
        ")",
        "pyz = PYZ(a.pure)",
        f"_name = {nome!r}",
        f"_console = {bool(config.get('console', False))!r}",
        f"_onefile = {bool(config.get('onefile', False))!r}",
        "if _onefile:",
        "    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name=_name,",
        "              console=_console, icon=_icon_path, version=_version_path)",
        "else:",
        "    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=_name,",
        "              console=_console, icon=_icon_path, version=_version_path)",
        "    coll = COLLECT(exe, a.binaries, a.datas, name=_name)",
    ]
    spec_path.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    version = str(config.get("versao") or "0.1.0").strip().lstrip("vV")
    partes = version.replace("-", ".").split(".")
    partes = (partes + ["0", "0", "0"])[:4]
    partes = [parte if parte.isdigit() else "0" for parte in partes]
    metadata = pasta_build / "versioninfo.yml"
    metadata.write_text(
        "Version: " + ".".join(partes) + "\n"
        + f"FileDescription: {json.dumps(nome, ensure_ascii=False)}\n"
        + f"InternalName: {json.dumps(nome, ensure_ascii=False)}\n"
        + f"OriginalFilename: {json.dumps(nome + '.exe', ensure_ascii=False)}\n"
        + f"ProductName: {json.dumps(nome, ensure_ascii=False)}\n"
        + "Translation: 1033, 1200\n",
        encoding="utf-8",
    )
    version_file = pasta_build / "versionfile.txt"
    try:
        version_file.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        subprocess.run(
            [python_venv, "-m", "pyinstaller_versionfile",
             "--metadata-file", str(metadata), "--outfile", str(version_file)],
            cwd=str(raiz), capture_output=True, text=True, timeout=60,
            **opcoes_processo_sem_console(),
        )
    except Exception as exc:
        log.aviso(_ARQ, "gerar_spec", f"Version resource opcional não gerado: {exc}")
    return str(spec_path)


class GerarSpecThread(_ThreadSegura):
    concluido = Signal(str, str)

    def __init__(self, python_venv, caminho_projeto, config, hidden_imports=None, parent=None):
        super().__init__(parent)
        self._python = python_venv
        self._raiz = caminho_projeto
        self._config = dict(config)
        self._hidden = list(hidden_imports or [])

    def run(self):
        try:
            caminho = gerar_spec(self._python, self._raiz, self._config, self._hidden)
            self.concluido.emit(caminho, "")
        except Exception as exc:
            log.erro(_ARQ, "GerarSpecThread.run", str(exc))
            self.concluido.emit("", str(exc))
