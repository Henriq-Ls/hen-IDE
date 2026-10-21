# 📁 _APP_/dialogo_novo_projeto.py
"""
Painel de criação de novo projeto da hein IDE.
Abre no TabWidget como aba especial — não é QDialog flutuante.
"""

import os
import subprocess
import sys
import uuid
from PySide6.QtCore import Qt, QObject, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton,
    QFrame, QScrollArea, QMessageBox, QProgressBar, QComboBox,
    QTextEdit,
)

from _CONFIGURA_ import (
    CINZA_ESCURO,
    BRANCO,
    VERDE,
    VERDE_AZULADO,
    VERDE_PETROLEO,
    COR_CINZA_TEXTO,
    COR_SUCESSO,
    COR_SEPARADOR,
    FONTE_UI,
    FONTE_UI_FALLBACK,
    TAMANHO_FONTE_UI,
    BORDA_GERAL,
    PRETO_FOSCO,
)
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_.gerenciador_templates import (
    carregar as _carregar_templates,
    salvar as _salvar_templates,
)
from _THREADS_.thread_segura import _ThreadSegura
from _THREADS_.diagnostico_workers import ensure_task, event

# ── helper de log ─────────────────────────────────────────────────────────────
def _log(funcao: str, msg: str) -> None:
    try:
        from _LOG_.log import log as _l
        _l.info("dialogo_novo_projeto.py", funcao, msg)
    except Exception:
        pass


def _tema_cor(chave: str, fallback: str) -> str:
    """Lê uma cor do mesmo tema usado pela JanelaPicker."""
    try:
        return tema_global().cor(chave, fallback)
    except Exception:
        return fallback


# ──────────────────────────────────────────────────────────────────────────────
# Thread: cria a .venv
# ──────────────────────────────────────────────────────────────────────────────

class _CriadorVenv(_ThreadSegura):
    concluido = Signal(str)
    erro      = Signal(str)
    progresso = Signal(str)

    def __init__(self, caminho: str, python_exe: str):
        super().__init__()
        self._caminho    = caminho
        self._python_exe = python_exe
        ensure_task(self, "VENV")
        event(
            "TARGET_BOUND",
            "VENV",
            getattr(self, "_hein_diag_task", ""),
            obj=self,
            destination=self._caminho,
            python_executable=self._python_exe,
        )

    def run(self):
        _task = ensure_task(self, "VENV")
        event("RUN_ENTER", "VENV", _task, obj=self)
        _log("_CriadorVenv.run", f"iniciando — python={self._python_exe} caminho={self._caminho}")
        try:
            venv_path = os.path.join(self._caminho, ".venv")
            self.progresso.emit(
                f"python -m venv {os.path.basename(self._caminho)}\\.venv"
            )
            proc = subprocess.Popen(
                [self._python_exe, "-m", "venv", venv_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                **opcoes_processo_sem_console(),
            )
            _log("_CriadorVenv.run", "Popen lançado — aguardando proc.wait(timeout=120)")
            try:
                proc.wait(timeout=120)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                _log("_CriadorVenv.run", "TIMEOUT — processo morto")
                self.erro.emit("Criação do .venv demorou demais (>2 min).")
                return
            _log("_CriadorVenv.run", f"concluído — returncode={proc.returncode}")
            if proc.returncode == 0:
                self.concluido.emit(self._caminho)
                event("RESULT_EMITTED", "VENV", _task, obj=self, success=True)
            else:
                self.erro.emit(f"python -m venv falhou (código {proc.returncode}).")
                event("RESULT_EMITTED", "VENV", _task, obj=self, success=False,
                      returncode=proc.returncode)
        except Exception as e:
            _log("_CriadorVenv.run", f"EXCEÇÃO: {e}")
            self.erro.emit(str(e))
            event("ERROR", "VENV", _task, obj=self, error=str(e))
        finally:
            event("RUN_EXIT", "VENV", _task, obj=self)

# ──────────────────────────────────────────────────────────────────────────────
# Thread: busca Pythons no sistema
# ──────────────────────────────────────────────────────────────────────────────

class _BuscadorPython(_ThreadSegura):
    """
    Busca interpretadores Python instalados em background.

    Usa _ThreadSegura (QThread dedicado) em vez de QRunnable/QThreadPool.
    Motivo: o QThreadPool reutiliza threads entre runnables. Se outro runnable
    (ex: código Git) inicializou COM como STA naquele thread, o próximo
    runnable recebe o thread já em STA — CoInitializeEx(MTA) retorna
    0x8001010d e proc.wait() explode. Thread dedicada garante COM limpo.
    COM é inicializado automaticamente por _ThreadSegura.__init_subclass__.
    """
    encontrado = Signal(str, str)   # (exe, versao)
    concluido  = Signal()

    _LOCAIS_WIN = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python"),
        os.path.expandvars(r"%APPDATA%\Python"),
        r"C:\Python",
        r"C:\Program Files\Python",
        r"C:\Program Files (x86)\Python",
    ]

    def __init__(self):
        super().__init__()
        self._hein_diag_result_count = 0
        self._hein_diag_candidate_count = 0
        ensure_task(self, "PYTHON_SEARCH")
        event(
            "TARGET_BOUND",
            "PYTHON_SEARCH",
            getattr(self, "_hein_diag_task", ""),
            obj=self,
            search_scope="PATH,py --list-paths,known Windows locations",
            ide_python=sys.executable,
        )

    def _localizar_executavel(self, nome: str) -> str:
        """Localiza um executável sem chamar shutil.which no Windows.

        Em algumas instalações do Windows, ``shutil.which`` pode acionar
        uma consulta de shell/COM e retornar 0x8001010d quando executada no
        worker. A busca manual só consulta o PATH e o sistema de arquivos.
        """
        caminhos = os.environ.get("PATH", "").split(os.pathsep)
        extensoes = [""]
        if sys.platform == "win32":
            extensoes = [
                ext for ext in os.environ.get("PATHEXT", ".EXE;.BAT;.CMD").split(";")
                if ext
            ]
        for pasta in caminhos:
            pasta = pasta.strip().strip('"')
            if not pasta:
                continue
            for ext in extensoes:
                candidato = os.path.join(pasta, nome + ext)
                event(
                    "PATH_CANDIDATE",
                    "PYTHON_SEARCH",
                    getattr(self, "_hein_diag_task", ""),
                    obj=self,
                    executable_name=nome,
                    candidate=candidato,
                )
                try:
                    if os.path.isfile(candidato):
                        event(
                            "PATH_MATCH",
                            "PYTHON_SEARCH",
                            getattr(self, "_hein_diag_task", ""),
                            obj=self,
                            executable_name=nome,
                            candidate=candidato,
                        )
                        return candidato
                except OSError:
                    event(
                        "PATH_STAT_ERROR",
                        "PYTHON_SEARCH",
                        getattr(self, "_hein_diag_task", ""),
                        obj=self,
                        executable_name=nome,
                        candidate=candidato,
                    )
                    continue
        return ""

    def run(self):
        _task = ensure_task(self, "PYTHON_SEARCH")
        event(
            "RUN_ENTER",
            "PYTHON_SEARCH",
            _task,
            obj=self,
            search_scope="PATH,py --list-paths,known Windows locations",
        )
        _log("_BuscadorPython.run", "thread iniciada — COM auto-inicializado por _ThreadSegura")
        try:
            self._run_impl()
        except Exception as exc:
            _log("_BuscadorPython.run", f"ERRO inesperado: {exc}")
            event("ERROR", "PYTHON_SEARCH", _task, obj=self, error=str(exc))
        finally:
            event(
                "RESULT_EMITTED",
                "PYTHON_SEARCH",
                _task,
                obj=self,
                result_count=self._hein_diag_result_count,
                candidate_count=self._hein_diag_candidate_count,
            )
            event(
                "RUN_EXIT",
                "PYTHON_SEARCH",
                _task,
                obj=self,
                result_count=self._hein_diag_result_count,
                candidate_count=self._hein_diag_candidate_count,
            )
            _log("_BuscadorPython.run", "thread concluída")
            self.concluido.emit()

    def _run_impl(self):
        # Reutiliza a task criada e associada no __init__. O escopo local é
        # necessário porque _emitir() fecha sobre esta variável.
        _task = getattr(self, "_hein_diag_task", "") or ensure_task(
            self, "PYTHON_SEARCH"
        )
        vistos = set()
        ide_python = os.path.normcase(os.path.abspath(sys.executable))

        def _emitir(exe):
            exe = os.path.normcase(os.path.abspath(exe))
            self._hein_diag_candidate_count += 1
            if exe in vistos:
                event(
                    "CANDIDATE_SKIPPED",
                    "PYTHON_SEARCH",
                    _task,
                    obj=self,
                    candidate=exe,
                    reason="duplicate",
                )
                return
            if not os.path.isfile(exe):
                event(
                    "CANDIDATE_SKIPPED",
                    "PYTHON_SEARCH",
                    _task,
                    obj=self,
                    candidate=exe,
                    reason="not_a_file",
                )
                return
            # A venv da IDE (venv 1) nunca pode ser oferecida para criar a
            # venv do projeto (venv 2). O filtro fica no worker para cobrir
            # PATH, launcher py e varredura de diretórios.
            if exe == ide_python:
                _log("_BuscadorPython._emitir", f"ignorado (Python da IDE): {exe}")
                event(
                    "CANDIDATE_SKIPPED",
                    "PYTHON_SEARCH",
                    _task,
                    obj=self,
                    candidate=exe,
                    reason="ide_python",
                )
                return
            # Stub da Microsoft Store — dispara COM/STA (0x8001010d) em proc.wait()
            if "windowsapps" in exe:
                _log("_BuscadorPython._emitir", f"ignorado (WindowsApps stub): {exe}")
                event(
                    "CANDIDATE_SKIPPED",
                    "PYTHON_SEARCH",
                    _task,
                    obj=self,
                    candidate=exe,
                    reason="windowsapps_stub",
                )
                return
            vistos.add(exe)
            event(
                "CANDIDATE_TEST_BEGIN",
                "PYTHON_SEARCH",
                _task,
                obj=self,
                candidate=exe,
            )
            _log("_BuscadorPython._emitir", f"testando: {exe}")
            versao = self._versao(exe)
            if versao:
                self._hein_diag_result_count += 1
                _log("_BuscadorPython._emitir", f"OK → Python {versao} — {exe}")
                self.encontrado.emit(exe, versao)
                event(
                    "RESULT_EMITTED",
                    "PYTHON_SEARCH",
                    _task,
                    obj=self,
                    candidate=exe,
                    version=versao,
                    result_count=self._hein_diag_result_count,
                )
                event(
                    "CANDIDATE_TEST_END",
                    "PYTHON_SEARCH",
                    _task,
                    obj=self,
                    candidate=exe,
                    accepted=True,
                    version=versao,
                )
            else:
                _log("_BuscadorPython._emitir", f"sem versão válida: {exe}")
                event(
                    "CANDIDATE_TEST_END",
                    "PYTHON_SEARCH",
                    _task,
                    obj=self,
                    candidate=exe,
                    accepted=False,
                )

        for nome in ("python", "python3", "python3.13", "python3.12",
                     "python3.11", "python3.10", "python3.9"):
            found = self._localizar_executavel(nome)
            if found:
                _emitir(found)

        if sys.platform == "win32":
            try:
                py = self._localizar_executavel("py")
                if py:
                    _saida_path = os.path.join(
                        os.path.abspath(os.environ.get("TEMP", ".")),
                        f"hein_py_list_{uuid.uuid4().hex}.txt",
                    )
                    try:
                        event(
                            "SUBPROCESS_START",
                            "PYTHON_SEARCH",
                            _task,
                            obj=self,
                            executable=py,
                            arguments=["--list-paths"],
                            output_file=_saida_path,
                        )
                        with open(_saida_path, "wb") as _f:
                            proc = subprocess.Popen(
                                [py, "--list-paths"],
                                stdout=_f,
                                stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL,
                                **opcoes_processo_sem_console(),
                            )
                        _log("_BuscadorPython._run_impl", "aguardando py --list-paths")
                        try:
                            proc.wait(timeout=5)
                            event(
                                "SUBPROCESS_RETURN",
                                "PYTHON_SEARCH",
                                _task,
                                obj=self,
                                executable=py,
                                arguments=["--list-paths"],
                                returncode=proc.returncode,
                            )
                        except subprocess.TimeoutExpired:
                            event(
                                "SUBPROCESS_TIMEOUT",
                                "PYTHON_SEARCH",
                                _task,
                                obj=self,
                                executable=py,
                                arguments=["--list-paths"],
                                timeout_seconds=5,
                            )
                            proc.kill()
                            proc.wait()
                            _log("_BuscadorPython._run_impl", "py --list-paths timeout — kill")
                        with open(_saida_path, "rb") as _f:
                            out = _f.read().decode(errors="ignore")
                    finally:
                        try:
                            os.unlink(_saida_path)
                        except OSError:
                            pass
                    for linha in out.splitlines():
                        for parte in linha.strip().split():
                            if parte.lower().endswith("python.exe"):
                                _emitir(parte)
            except Exception as exc:
                _log("_BuscadorPython._run_impl", f"ERRO em py --list-paths: {exc}")
                event(
                    "SUBPROCESS_ERROR",
                    "PYTHON_SEARCH",
                    _task,
                    obj=self,
                    executable=locals().get("py", ""),
                    arguments=["--list-paths"],
                    error=str(exc),
                )

            for raiz in self._LOCAIS_WIN:
                if not os.path.isdir(raiz):
                    continue
                for entrada in os.scandir(raiz):
                    if not entrada.is_dir():
                        continue
                    for sub in ("Scripts", ""):
                        _emitir(os.path.join(entrada.path, sub, "python.exe"))
        else:
            for prefixo in ("/usr", "/usr/local",
                            os.path.expanduser("~/.local"),
                            "/opt/homebrew", "/opt/local"):
                for nome in ("python3", "python"):
                    _emitir(os.path.join(prefixo, "bin", nome))

    def _versao(self, exe: str) -> str:
        """Versão do interpretador via proc.wait() — sem sleep, sem threads internas."""
        _task = getattr(self, "_hein_diag_task", "")
        _saida_path = os.path.join(
            os.path.abspath(os.environ.get("TEMP", ".")),
            f"hein_py_version_{uuid.uuid4().hex}.txt",
        )
        try:
            event(
                "SUBPROCESS_START",
                "PYTHON_SEARCH",
                _task,
                obj=self,
                executable=exe,
                arguments=["--version"],
                output_file=_saida_path,
            )
            with open(_saida_path, "wb") as _f:
                proc = subprocess.Popen(
                    [exe, "--version"],
                    stdout=_f,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    **opcoes_processo_sem_console(),
                )
            try:
                proc.wait(timeout=3)
                event(
                    "SUBPROCESS_RETURN",
                    "PYTHON_SEARCH",
                    _task,
                    obj=self,
                    executable=exe,
                    arguments=["--version"],
                    returncode=proc.returncode,
                )
            except subprocess.TimeoutExpired:
                event(
                    "SUBPROCESS_TIMEOUT",
                    "PYTHON_SEARCH",
                    _task,
                    obj=self,
                    executable=exe,
                    arguments=["--version"],
                    timeout_seconds=3,
                )
                proc.kill()
                proc.wait()
                return ""
            with open(_saida_path, "rb") as _f:
                out = _f.read().decode(errors="ignore").strip()
            return out.split()[-1] if out.startswith("Python") else ""
        except Exception as exc:
            event(
                "SUBPROCESS_ERROR",
                "PYTHON_SEARCH",
                _task,
                obj=self,
                executable=exe,
                arguments=["--version"],
                error=str(exc),
            )
            return ""
        finally:
            try:
                os.unlink(_saida_path)
            except OSError:
                pass

# ──────────────────────────────────────────────────────────────────────────────
# Thread: git clone (movida de painel_boas_vindas para poder ser importada
# diretamente por janela_picker.py sem depender do módulo que será removido)
# ──────────────────────────────────────────────────────────────────────────────

class _WorkerClone(QObject):
    """Executa git clone em thread separada para não travar a UI."""
    concluido = Signal(bool, str)   # (sucesso, mensagem_erro)
    progresso = Signal(str)         # mensagens intermediárias

    def __init__(self, url: str, destino: str, token: str = ""):
        super().__init__()
        self._url     = url
        self._destino = destino
        self._token   = token or ""
        _task = ensure_task(self, "CLONE")
        event(
            "TARGET_BOUND",
            "CLONE",
            _task,
            obj=self,
            source_url=self._url,
            destination=self._destino,
        )

    def run(self):
        _task = ensure_task(self, "CLONE")
        event("RUN_ENTER", "CLONE", _task, obj=self)
        try:
            from _PAINEL_ESQUERDO_.Git.git_gerente import GerenciadorGit
            resultado = GerenciadorGit().baixar_projeto(
                self._url,
                self._destino,
                self._token,
            )
            self.concluido.emit(
                resultado.ok,
                "" if resultado.ok else (resultado.erro or "Erro desconhecido."),
            )
            event("RESULT_EMITTED", "CLONE", _task, obj=self,
                  success=bool(resultado.ok))
        except Exception as e:
            self.concluido.emit(False, str(e))
            event("ERROR", "CLONE", _task, obj=self, error=str(e))
        finally:
            event("RUN_EXIT", "CLONE", _task, obj=self)


# ──────────────────────────────────────────────────────────────────────────────
# Widget de uma linha de template
# ──────────────────────────────────────────────────────────────────────────────

class _LinhaTemplate(QWidget):
    """
    Uma linha expansível de template de arquivo.
    Linha compacta com nome + extensão + botão remover.
    Clica em "▼ conteúdo" para expandir e editar o conteúdo inicial.
    """
    removido = Signal(object)

    _EXTENSOES = [".py", ".json", ".md", ".txt", ".html", ".css",
                  ".js", ".ts", ".yaml", ".toml", ".sql", ".sh",
                  ".bat", ".xml", ".csv", "(sem extensão)"]

    # ⚠️  função grande (77 linhas)
    # 💡 ext_opc = Literal[".py"] ← defina os valores válidos
    def __init__(self, nome: str = "", ext: str = ".py", conteudo: str = "", parent=None):
        super().__init__(parent)
        self._expandido = False

        lay_externo = QVBoxLayout(self)
        lay_externo.setContentsMargins(0, 2, 0, 2)
        lay_externo.setSpacing(2)

        # ── Linha superior: nome | ext | ▼ | ✕ ──────────────────────────────
        linha_topo = QWidget()
        lay_topo = QHBoxLayout(linha_topo)
        lay_topo.setContentsMargins(0, 0, 0, 0)
        lay_topo.setSpacing(6)

        self._campo = QLineEdit()
        self._campo.setPlaceholderText("nome do arquivo")
        self._campo.setFixedHeight(28)
        if nome:
            self._campo.setText(nome)

        self._combo = QComboBox()
        self._combo.setFixedHeight(28)
        self._combo.setFixedWidth(110)
        for e in self._EXTENSOES:
            self._combo.addItem(e)
        if ext in self._EXTENSOES:
            self._combo.setCurrentText(ext)
        # Atualiza placeholder do conteúdo quando a extensão muda
        self._combo.currentTextChanged.connect(self._ao_mudar_extensao)

        self._btn_expandir = QPushButton("▼ conteúdo")
        self._btn_expandir.setFixedHeight(24)
        self._btn_expandir.setCursor(Qt.PointingHandCursor)
        self._btn_expandir.setToolTip("Editar conteúdo inicial do arquivo")
        self._btn_expandir.setStyleSheet(
            f"QPushButton {{ color: {_tema_cor('interface.texto_fraco', '#7094A1')};"
            " background: transparent; border: none; font-size: 10px; }"
            f"QPushButton:hover {{ color: {_tema_cor('interface.texto_destaque', '#4ec994')};"
            " text-decoration: underline; }"
        )
        self._btn_expandir.clicked.connect(self._toggle_conteudo)

        btn_rem = QPushButton("✕")
        btn_rem.setFixedSize(24, 24)
        btn_rem.setCursor(Qt.PointingHandCursor)
        btn_rem.setToolTip("Remover este arquivo do template")
        btn_rem.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
            f"QPushButton:hover {{ color: {_tema_cor('log.erro', '#e06c75')}; }}"
        )
        btn_rem.clicked.connect(lambda: self.removido.emit(self))

        lay_topo.addWidget(self._campo, 1)
        lay_topo.addWidget(self._combo)
        lay_topo.addWidget(self._btn_expandir)
        lay_topo.addWidget(btn_rem)
        lay_externo.addWidget(linha_topo)

        # ── Área de conteúdo (oculta por padrão) ─────────────────────────────
        self._area_conteudo = QWidget()
        lay_conteudo = QVBoxLayout(self._area_conteudo)
        lay_conteudo.setContentsMargins(0, 0, 0, 4)
        lay_conteudo.setSpacing(2)

        lbl = QLabel("Conteúdo inicial do arquivo:")
        lbl.setStyleSheet(
            f"font-size: 10px; color: {_tema_cor('interface.texto_fraco', '#7094A1')};"
        )
        lay_conteudo.addWidget(lbl)

        self._editor = QTextEdit()
        self._editor.setFixedHeight(120)
        self._editor.setPlaceholderText(self._placeholder_para_ext(ext))
        self._editor.setLineWrapMode(QTextEdit.NoWrap)
        self._editor.setStyleSheet(
            f"QTextEdit {{ background: {_tema_cor('interface.inputs', '#082C3A')};"
            f" color: {_tema_cor('interface.texto', '#EDEEF0')};"
            f" border: 1px solid {_tema_cor('interface.borda', 'transparent')};"
            " font-family: monospace; font-size: 11px; }"
        )
        if conteudo:
            self._editor.setPlainText(conteudo)
        lay_conteudo.addWidget(self._editor)

        self._area_conteudo.setVisible(False)
        lay_externo.addWidget(self._area_conteudo)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _placeholder_para_ext(self, ext: str) -> str:
        placeholders = {
            ".py":   "# código Python inicial...\n\ndef main():\n    pass",
            ".json": '{\n  "chave": "valor"\n}',
            ".md":   "# Título\n\nDescrição do projeto...",
            ".html": "<!DOCTYPE html>\n<html>\n<body>\n</body>\n</html>",
            ".yaml": "chave: valor",
            ".toml": '[projeto]\nnome = "meu_projeto"',
            ".sh":   "#!/bin/bash\nset -e",
            ".bat":  "@echo off",
        }

        return placeholders.get(ext, "Conteúdo inicial do arquivo...")

    def _ao_mudar_extensao(self, ext: str):
        self._editor.setPlaceholderText(self._placeholder_para_ext(ext))

    def _toggle_conteudo(self):
        self._expandido = not self._expandido
        self._area_conteudo.setVisible(self._expandido)
        self._btn_expandir.setText("▲ conteúdo" if self._expandido else "▼ conteúdo")

    # ── dado público ──────────────────────────────────────────────────────────

    def dados(self) -> dict:
        nome = self._campo.text().strip()
        ext  = self._combo.currentText()
        if ext == "(sem extensão)":
            ext = ""
        conteudo = self._editor.toPlainText()

        return {"tipo": "arquivo", "nome": nome, "ext": ext, "conteudo": conteudo}

# ──────────────────────────────────────────────────────────────────────────────
# Widget de pasta (agrupa arquivos filhos)
# ──────────────────────────────────────────────────────────────────────────────

class _LinhaPasta(QWidget):
    """
    Uma entrada de pasta no template.
    Mostra nome da pasta + lista expansível de arquivos filhos.
    """
    removido = Signal(object)

    def __init__(self, nome: str = "", filhos: list | None = None, parent=None):
        super().__init__(parent)
        self._expandido = True
        self._filhos: list[_LinhaTemplate] = []

        lay_externo = QVBoxLayout(self)
        lay_externo.setContentsMargins(0, 4, 0, 4)
        lay_externo.setSpacing(2)

        # ── Cabeçalho da pasta ────────────────────────────────────────────────
        linha_topo = QWidget()
        lay_topo = QHBoxLayout(linha_topo)
        lay_topo.setContentsMargins(0, 0, 0, 0)
        lay_topo.setSpacing(6)

        lbl_icone = QLabel("📁")
        lbl_icone.setFixedWidth(20)
        lbl_icone.setStyleSheet("background: transparent;")
        lay_topo.addWidget(lbl_icone)

        self._campo = QLineEdit()
        self._campo.setPlaceholderText("nome da pasta")
        self._campo.setFixedHeight(28)
        if nome:
            self._campo.setText(nome)

        self._btn_expandir = QPushButton("▲ arquivos")
        self._btn_expandir.setFixedHeight(24)
        self._btn_expandir.setCursor(Qt.PointingHandCursor)
        self._btn_expandir.setToolTip("Mostrar/ocultar arquivos desta pasta")
        self._btn_expandir.setStyleSheet(
            f"QPushButton {{ color: {_tema_cor('interface.texto_fraco', '#7094A1')};"
            " background: transparent; border: none; font-size: 10px; }"
            f"QPushButton:hover {{ color: {_tema_cor('interface.texto_destaque', '#4ec994')};"
            " text-decoration: underline; }"
        )
        self._btn_expandir.clicked.connect(self._toggle)

        btn_rem = QPushButton("✕")
        btn_rem.setFixedSize(24, 24)
        btn_rem.setCursor(Qt.PointingHandCursor)
        btn_rem.setToolTip("Remover esta pasta do template")
        btn_rem.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
            f"QPushButton:hover {{ color: {_tema_cor('log.erro', '#e06c75')}; }}"
        )
        btn_rem.clicked.connect(lambda: self.removido.emit(self))

        lay_topo.addWidget(self._campo, 1)
        lay_topo.addWidget(self._btn_expandir)
        lay_topo.addWidget(btn_rem)
        lay_externo.addWidget(linha_topo)

        # ── Área interior (arquivos filhos) ───────────────────────────────────
        self._area_filhos = QWidget()
        self._lay_filhos = QVBoxLayout(self._area_filhos)
        self._lay_filhos.setContentsMargins(24, 4, 0, 4)
        self._lay_filhos.setSpacing(2)

        self._btn_add_filho = QPushButton("＋  arquivo")
        self._btn_add_filho.setCursor(Qt.PointingHandCursor)
        self._btn_add_filho.setFixedHeight(24)
        self._btn_add_filho.setStyleSheet(
            f"QPushButton {{ color: {_tema_cor('interface.texto_fraco', '#7094A1')};"
            f" background: transparent; border: 1px dashed "
            f"{_tema_cor('interface.borda', '#3a4a3a')};"
            " border-radius: 3px; font-size: 10px; }"
            f"QPushButton:hover {{ border-color: {_tema_cor('interface.texto_destaque', '#4ec994')};"
            f" color: {_tema_cor('interface.texto_destaque', '#4ec994')}; }}"
        )
        self._btn_add_filho.clicked.connect(lambda _=False: self._adicionar_filho())
        self._lay_filhos.addWidget(self._btn_add_filho)

        lay_externo.addWidget(self._area_filhos)

        # Carrega filhos iniciais
        if filhos:
            for filho in filhos:
                self._adicionar_filho(
                    filho.get("nome", ""),
                    filho.get("ext", ".py"),
                    filho.get("conteudo", ""),
                )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _toggle(self):
        self._expandido = not self._expandido
        self._area_filhos.setVisible(self._expandido)
        self._btn_expandir.setText("▲ arquivos" if self._expandido else "▼ arquivos")

    def _adicionar_filho(self, nome: str = "", ext: str = ".py", conteudo: str = ""):
        filho = _LinhaTemplate(nome, ext, conteudo, self)
        filho.removido.connect(self._remover_filho)
        self._filhos.append(filho)
        # Insere antes do botão "＋ arquivo"
        idx = self._lay_filhos.indexOf(self._btn_add_filho)
        self._lay_filhos.insertWidget(idx, filho)

    def _remover_filho(self, filho: _LinhaTemplate):
        if filho in self._filhos:
            self._filhos.remove(filho)
        self._lay_filhos.removeWidget(filho)
        filho.deleteLater()

    # ── dado público ──────────────────────────────────────────────────────────

    def dados(self) -> dict:
        nome   = self._campo.text().strip()
        filhos = [f.dados() for f in self._filhos if f.dados()["nome"]]
        return {"tipo": "pasta", "nome": nome, "filhos": filhos}

# ──────────────────────────────────────────────────────────────────────────────
# Painel principal
# ──────────────────────────────────────────────────────────────────────────────

class PainelNovoProjeto(QWidget):
    criar_projeto = Signal(str, str, str)   # nome, destino, python_exe
    voltar        = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._python_selecionado: str = ""
        self._exigir_python = True
        self._linhas_template: list[_LinhaTemplate] = []
        self._montar_ui()
        self._carregar_templates()

    def _cor(self, chave: str, fallback: str) -> str:
        return tema_global().cor(chave, fallback)

    def definir_config(
        self,
        pasta_destino: str,
        python_exe: str,
        python_versao: str = "",
    ) -> None:
        """Recebe a configuração escolhida na coluna de configuração do picker.

        O picker é a fonte dessa configuração; o painel de criação apenas
        recebe os valores e não deve pedir novamente uma pasta ou interpretador.
        A segunda tela apenas exibe um resumo dessas escolhas.
        Quando ``python_exe`` está vazio, a criação é deliberadamente manual e
        não pode ser bloqueada pela validação do interpretador.
        """
        self._campo_destino.setText(pasta_destino or "—")
        self._python_selecionado = (python_exe or "").strip()
        self._python_versao = (python_versao or "").strip()
        self._exigir_python = bool(self._python_selecionado)

        if self._python_selecionado:
            nome_python = (
                f"Python {self._python_versao}"
                if self._python_versao
                else "Interpretador Python selecionado"
            )
            self._label_config_python_nome.setText(nome_python)
            self._label_config_python_path.setText(self._python_selecionado)
            self._label_config_python_path.setVisible(True)
        else:
            self._label_config_python_nome.setText("Criação automática desativada")
            self._label_config_python_path.setText(
                "A .venv poderá ser configurada manualmente depois."
            )
            self._label_config_python_path.setVisible(True)

    # ── UI ───────────────────────────────────────────────────────────────────

    # ⚠️  função grande (204 linhas)
    def _montar_ui(self):
        self._init_cores()
        self.setStyleSheet(
            f"""
            QWidget {{
                background: {self._cf};
                color: {self._ctx};
                font-family: "{FONTE_UI}", "{FONTE_UI_FALLBACK}";
                font-size: {TAMANHO_FONTE_UI};
            }}
            QLineEdit, QComboBox, QTextEdit {{
                background: {self._cinput};
                color: {self._ctx};
                border: 1px solid {self._cbd};
                border-radius: 4px;
            }}
            QPushButton {{
                color: {self._ctx};
                background: {self._cbutton};
                border: 1px solid {self._cbd};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: {self._chv};
                color: {self._cvd};
            }}
            QScrollArea {{
                background: {self._cf};
                border: none;
            }}
            """
        )
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ── Barra de topo com botão voltar ────────────────────────────────────
        barra_topo = QWidget()
        barra_topo.setFixedHeight(40)
        lay_topo = QHBoxLayout(barra_topo)
        lay_topo.setContentsMargins(12, 0, 12, 0)

        btn_voltar = QPushButton("← Voltar")
        btn_voltar.setCursor(Qt.PointingHandCursor)
        btn_voltar.setFixedWidth(90)
        btn_voltar.clicked.connect(self.voltar.emit)

        lbl_titulo = QLabel("Novo Projeto")

        lay_topo.addWidget(btn_voltar)
        lay_topo.addSpacing(12)
        lay_topo.addWidget(lbl_titulo)
        lay_topo.addStretch()
        raiz.addWidget(barra_topo)

        sep_topo = QFrame()
        sep_topo.setFrameShape(QFrame.HLine)
        sep_topo.setFixedHeight(1)
        raiz.addWidget(sep_topo)

        # ── Scroll principal ──────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        corpo = QWidget()
        scroll.setWidget(corpo)
        raiz.addWidget(scroll, 1)

        # ── Duas colunas: configuração herdada + templates ───────────────────
        lay_corpo = QHBoxLayout(corpo)
        lay_corpo.setContentsMargins(54, 34, 54, 34)
        lay_corpo.setSpacing(34)
        lay_corpo.setAlignment(Qt.AlignTop)

        # ── COLUNA ESQUERDA ───────────────────────────────────────────────────
        col_esq = QVBoxLayout()
        col_esq.setSpacing(10)
        col_esq.setAlignment(Qt.AlignTop)

        col_esq.addWidget(self._rotulo_secao("PROJETO"))
        col_esq.addSpacing(12)

        col_esq.addWidget(self._rotulo_campo("Nome do projeto"))
        col_esq.addSpacing(4)
        self._campo_nome = QLineEdit()
        self._campo_nome.setPlaceholderText("Ex: meu_projeto")
        self._campo_nome.setFixedHeight(30)
        col_esq.addWidget(self._campo_nome)

        col_esq.addSpacing(18)
        col_esq.addWidget(self._rotulo_secao("CONFIGURAÇÃO HERDADA"))
        col_esq.addSpacing(12)

        col_esq.addWidget(self._rotulo_campo("Destino escolhido na janela inicial"))
        col_esq.addSpacing(4)
        self._campo_destino = QLabel("—")
        self._campo_destino.setWordWrap(True)
        self._campo_destino.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._campo_destino.setStyleSheet(
            f"color: {self._cfr}; background: transparent;"
            " padding: 6px 0; font-size: 11px;"
        )
        col_esq.addWidget(self._campo_destino)

        col_esq.addSpacing(10)
        col_esq.addWidget(self._rotulo_campo("Python usado para criar a .venv"))
        col_esq.addSpacing(4)
        bloco_python = QFrame()
        bloco_python.setObjectName("blocoPythonHerdado")
        bloco_python.setStyleSheet(
            f"QFrame#blocoPythonHerdado {{ background: {self._cinput};"
            f" border: 1px solid {self._cvd}; border-radius: 5px; }}"
        )
        lay_python = QVBoxLayout(bloco_python)
        lay_python.setContentsMargins(10, 7, 10, 7)
        lay_python.setSpacing(3)
        self._label_config_python_nome = QLabel("—")
        self._label_config_python_nome.setStyleSheet(
            f"color: {self._ctx}; background: transparent; font-size: 12px;"
            " font-weight: 700;"
        )
        self._label_config_python_path = QLabel("—")
        self._label_config_python_path.setWordWrap(True)
        self._label_config_python_path.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )
        self._label_config_python_path.setStyleSheet(
            f"color: {self._cvd}; background: transparent; font-size: 10px;"
        )
        lay_python.addWidget(self._label_config_python_nome)
        lay_python.addWidget(self._label_config_python_path)
        col_esq.addWidget(bloco_python)

        col_esq.addSpacing(12)
        aviso_config = QLabel(
            "Essas configurações vêm da janela inicial e não podem ser alteradas aqui."
        )
        aviso_config.setWordWrap(True)
        aviso_config.setStyleSheet(
            f"color: {self._cfr}; background: transparent; font-size: 10px;"
        )
        col_esq.addWidget(aviso_config)

        col_esq.addSpacing(20)
        col_esq.addWidget(self._separador())
        col_esq.addSpacing(14)

        self._btn_criar = QPushButton("✦  Criar Projeto")
        self._btn_criar.setFixedHeight(36)
        self._btn_criar.setCursor(Qt.PointingHandCursor)
        self._btn_criar.setStyleSheet(
            f"QPushButton {{ background: {self._cvd}; color: {self._cf};"
            " border: none; border-radius: 5px; font-size: 12px; font-weight: 700;"
            " padding: 0 14px; }"
            f"QPushButton:hover {{ background: {self._chv}; color: {self._ctx}; }}"
            f"QPushButton:disabled {{ background: {self._cbd};"
            f" color: {self._cfr}; }}"
        )
        self._btn_criar.clicked.connect(self._ao_criar)
        col_esq.addWidget(self._btn_criar)

        # Progresso
        self._area_progresso = QWidget()
        self._area_progresso.setVisible(False)
        lay_prog = QVBoxLayout(self._area_progresso)
        lay_prog.setContentsMargins(0, 12, 0, 0)
        lay_prog.setSpacing(4)
        self._label_progresso = QLabel("⏳ Iniciando...")
        self._progressbar = QProgressBar()
        self._progressbar.setRange(0, 0)
        self._progressbar.setFixedHeight(5)
        self._progressbar.setTextVisible(False)
        self._label_resultado = QLabel("")
        self._label_resultado.setStyleSheet(
            f"color: {self._cvd}; font-size: 11px;"
        )
        lay_prog.addWidget(self._label_progresso)
        lay_prog.addWidget(self._progressbar)
        lay_prog.addWidget(self._label_resultado)
        col_esq.addWidget(self._area_progresso)
        col_esq.addStretch()

        # ── SEPARADOR VERTICAL ────────────────────────────────────────────────
        vsep = QFrame()
        vsep.setFrameShape(QFrame.VLine)
        vsep.setFixedWidth(1)

        # ── COLUNA DIREITA: templates ─────────────────────────────────────────
        col_dir = QVBoxLayout()
        col_dir.setSpacing(10)
        col_dir.setAlignment(Qt.AlignTop)

        col_dir.addWidget(self._rotulo_secao("ARQUIVOS DO PROJETO"))
        col_dir.addSpacing(6)

        lbl_desc = QLabel(
            "Arquivos criados em todo novo projeto.\n"
            "Clique em ▼ conteúdo para definir o conteúdo inicial de cada arquivo.\n"
            "Salvo permanentemente."
        )
        col_dir.addWidget(lbl_desc)
        col_dir.addSpacing(12)

        self._container_templates = QWidget()
        self._lay_templates = QVBoxLayout(self._container_templates)
        self._lay_templates.setContentsMargins(0, 0, 0, 0)
        self._lay_templates.setSpacing(2)
        col_dir.addWidget(self._container_templates)

        col_dir.addSpacing(8)

        row_add = QHBoxLayout()
        row_add.setSpacing(6)

        btn_add = QPushButton("＋  Arquivo")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setFixedHeight(28)
        btn_add.clicked.connect(lambda _=False: self._adicionar_linha())
        row_add.addWidget(btn_add)

        btn_add_pasta = QPushButton("📁  Pasta")
        btn_add_pasta.setCursor(Qt.PointingHandCursor)
        btn_add_pasta.setFixedHeight(28)
        btn_add_pasta.clicked.connect(lambda _=False: self._adicionar_pasta())
        row_add.addWidget(btn_add_pasta)

        col_dir.addLayout(row_add)

        col_dir.addSpacing(16)
        col_dir.addWidget(self._separador())
        col_dir.addSpacing(12)

        btn_salvar_tmpl = QPushButton("💾  Salvar templates")
        btn_salvar_tmpl.setFixedHeight(30)
        btn_salvar_tmpl.setCursor(Qt.PointingHandCursor)
        btn_salvar_tmpl.clicked.connect(self._salvar_templates)
        col_dir.addWidget(btn_salvar_tmpl)

        self._lbl_tmpl_ok = QLabel("")
        self._lbl_tmpl_ok.setStyleSheet(
            f"color: {self._cvd}; font-size: 10px;"
        )
        col_dir.addWidget(self._lbl_tmpl_ok)
        col_dir.addStretch()

        lay_corpo.addLayout(col_esq, 1)
        lay_corpo.addWidget(vsep)
        lay_corpo.addLayout(col_dir, 1)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _init_cores(self):
        # O painel deve usar exatamente o mesmo mapa de cores da janela
        # principal/picker. As constantes antigas ficam apenas como fallback
        # para instalações que ainda não carregaram um tema válido.
        self._cf = _tema_cor("interface.fundo", CINZA_ESCURO)
        self._cp = _tema_cor("interface.fundo_painel", self._cf)
        self._ctx = _tema_cor("interface.texto", BRANCO)
        self._cfr = _tema_cor("interface.texto_fraco", COR_CINZA_TEXTO)
        self._cvd = _tema_cor("interface.texto_destaque", COR_SUCESSO)
        self._cbd = _tema_cor("interface.borda", BORDA_GERAL)
        self._chv = _tema_cor("interface.fundo_item_hover", self._cp)
        self._cinput = _tema_cor("interface.inputs", self._cp)
        self._cbutton = _tema_cor(
            "interface.botao_padrao_fundo",
            _tema_cor("interface.inputs", self._cp),
        )

    def _rotulo_secao(self, texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setStyleSheet(
            f"font-size: 9px; font-weight: 700;"
            f" color: {_tema_cor('interface.texto_fraco', COR_SEPARADOR)};"
            " letter-spacing: 1.8px;"
        )

        return lbl

    def _rotulo_campo(self, texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setStyleSheet(
            f"color: {_tema_cor('interface.texto', BRANCO)};"
            " font-size: 11px; font-weight: 500;"
        )

        return lbl

    def _separador(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setFixedHeight(1)

        return f

    # ── Templates ─────────────────────────────────────────────────────────────

    def _carregar_templates(self):
        for linha in list(self._linhas_template):
            self._lay_templates.removeWidget(linha)
            linha.deleteLater()
        self._linhas_template.clear()
        for tmpl in _carregar_templates():
            if tmpl.get("tipo") == "pasta":
                self._adicionar_pasta(
                    tmpl.get("nome", ""),
                    tmpl.get("filhos", []),
                )
            else:
                self._adicionar_linha(
                    tmpl.get("nome", ""),
                    tmpl.get("ext", ".py"),
                    tmpl.get("conteudo", ""),
                )

    def _adicionar_linha(
        self,
        nome: str = "",
        ext: str = ".py",
        conteudo: str = "",
    ):
        linha = _LinhaTemplate(nome, ext, conteudo, self)
        linha.removido.connect(self._remover_linha)
        self._linhas_template.append(linha)
        self._lay_templates.addWidget(linha)

    def _adicionar_pasta(self, nome: str = "", filhos: list | None = None):
        pasta = _LinhaPasta(nome, filhos or [], self)
        pasta.removido.connect(self._remover_linha)
        self._linhas_template.append(pasta)
        self._lay_templates.addWidget(pasta)

    def _remover_linha(self, linha):
        if linha in self._linhas_template:
            self._linhas_template.remove(linha)
        self._lay_templates.removeWidget(linha)
        linha.deleteLater()

    def _salvar_templates(self):
        dados = [l.dados() for l in self._linhas_template if l.dados()["nome"]]
        _salvar_templates(dados)
        self._lbl_tmpl_ok.setText("✔  Salvo")
        QTimer.singleShot(2500, lambda: self._lbl_tmpl_ok.setText(""))

    def _templates_atuais(self) -> list[dict]:
        return [l.dados() for l in self._linhas_template if l.dados()["nome"]]

    # ── Criação do projeto ────────────────────────────────────────────────────

    # ⚠️  função grande (88 linhas)
    def _ao_criar(self):
        nome    = self._campo_nome.text().strip()
        destino = self._campo_destino.text().strip()
        python  = self._python_selecionado.strip()

        erros = []
        if not nome:
            erros.append("• Informe o nome do projeto.")
        if not destino:
            erros.append("• Escolha a pasta de destino.")
        if self._exigir_python and not python:
            erros.append("• Selecione ou informe um interpretador Python.")
        elif python and not os.path.isfile(python):
            erros.append(f"• Interpretador não encontrado:\n  {python}")

        if erros:
            QMessageBox.warning(self, "Campos obrigatórios", "\n".join(erros))

            return

        caminho = os.path.join(destino, nome)

        if os.path.exists(caminho):
            resp = QMessageBox.question(
                self, "Já existe",
                "Já existe uma pasta com esse nome. Sobrescrever?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if resp == QMessageBox.No:
                return

        os.makedirs(caminho, exist_ok=True)
        with open(os.path.join(caminho, ".gitignore"), "w", encoding="utf-8") as f:
            f.write(".venv/\n__pycache__/\n*.pyc\n.env\n.hein/\n")

        # Cria arquivos e pastas dos templates
        primeiro_py = None

        def _criar_arquivo(base: str, tmpl: dict) -> None:
            nonlocal primeiro_py
            nome_arq    = tmpl["nome"] + tmpl["ext"]
            caminho_arq = os.path.join(base, nome_arq)
            conteudo    = tmpl.get("conteudo", "").strip()
            with open(caminho_arq, "w", encoding="utf-8") as f:
                if conteudo:
                    f.write(conteudo)
                    if not conteudo.endswith("\n"):
                        f.write("\n")
                elif tmpl["ext"] == ".py":
                    f.write(f"# 📁 {nome_arq}\n")
                    if primeiro_py is None:
                        f.write(
                            "\n\ndef main():\n"
                            '    print("Olá, mundo!")\n\n\n'
                            'if __name__ == "__main__":\n'
                            "    main()\n"
                        )
                # outros tipos sem conteúdo ficam vazios
            if tmpl["ext"] == ".py" and primeiro_py is None:
                primeiro_py = caminho_arq

        for tmpl in self._templates_atuais():
            if tmpl.get("tipo") == "pasta":
                pasta_path = os.path.join(caminho, tmpl["nome"])
                os.makedirs(pasta_path, exist_ok=True)
                for filho in tmpl.get("filhos", []):
                    if filho.get("nome"):
                        _criar_arquivo(pasta_path, filho)
            else:
                _criar_arquivo(caminho, tmpl)

        if primeiro_py is None:
            main_py = os.path.join(caminho, "main.py")
            with open(main_py, "w", encoding="utf-8") as f:
                f.write(
                    "# 📁 main.py\n\n\n"
                    "def main():\n"
                    '    print("Olá, mundo!")\n\n\n'
                    'if __name__ == "__main__":\n'
                    "    main()\n"
                )
            primeiro_py = main_py

        self._main_py         = primeiro_py
        self._caminho_projeto = caminho

        self._btn_criar.setEnabled(False)
        self._campo_nome.setReadOnly(True)

        self._area_progresso.setVisible(True)
        self._label_resultado.setText("")

        self.criar_projeto.emit(nome, destino, python)

    def _ao_venv_criado(self, caminho: str):
        self._label_progresso.setText("✔  Ambiente virtual criado.")
        self._progressbar.setRange(0, 1)
        self._progressbar.setValue(1)
        self._label_resultado.setText(f"Projeto pronto em: {caminho}")

    def _ao_venv_erro(self, msg: str):
        self._label_progresso.setText("⚠️  Ambiente virtual não criado.")
        self._progressbar.setRange(0, 1)
        self._progressbar.setValue(1)
        self._label_resultado.setText(
            "Projeto aberto sem .venv — crie manualmente depois (Ctrl+Alt+A)."
        )
        from _LOG_.log import log
        log.warning(f"[PainelNovoProjeto] venv falhou: {msg}")
