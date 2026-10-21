"""Threads de background (criação de venv, análise de projeto) e helpers.

Parte do pacote main_window/ — ver main_window/__init__.py.
Gerado a partir da divisão de main_window.py (arquivo único de 4607 linhas).
"""


import atexit
import os
import shutil
import subprocess
import sys
import tempfile
from _UTILITARIOS_.icones import icone_tema
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console
from PySide6.QtWidgets import (
    QMainWindow,

    QWidget,

    QVBoxLayout,

    QHBoxLayout,

    QTabWidget,

    QSplitter,

    QPushButton,

    QMenuBar,

    QMenu,

    QFileDialog,

    QMessageBox,

    QInputDialog,

    QLabel,

    QApplication,

    QProgressBar,

    QDockWidget,

)

from _APP_.navegador_abas import NavegadorAbas
from PySide6.QtGui import QTextCursor, QPainter, QColor, QBrush, QPainterPath, QRegion, QAction, QKeySequence, QPen
from PySide6.QtCore import QEvent, QRectF
from PySide6.QtCore import Qt, QTimer, QSize, QThread, Signal, QSettings
from _THREADS_.thread_segura import _ThreadSegura
from _THREADS_.diagnostico_workers import ensure_task, event

# Mantém referências a _AnalisadorProjeto até finished — evita GC prematuro
# quando mixin_projeto substitui a referência antes de run() retornar (BUG-202807-13).
_threads_vivas_analisador: set = set()
from ..tab_widget import TabWidget
from ..terminal_tab_widget import TerminalTabWidget

from _PAINEL_ESQUERDO_.FileTree import PainelArquivos
from _PAINEL_ESQUERDO_.painel_abas_inferior import PainelAbasInferior as PainelGit
from _CONFIGURA_.gerenciador_atalhos import GerenciadorAtalhos
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_.gerenciador_configurar import config_global
from GerenciadorAbas_AutoSalve import GerenciadorAbas_AutoSalve
from _CONFIGURA_ import (
    TITULO_APP,    GEOMETRIA_APP,
    SPLITTER_PRINCIPAL,    SPLITTER_COL1,
    SPLITTER_COL2,    COR_MENU_BG,    COR_MENU_TEXTO,
    COR_MENU_HOVER_BG,    COR_MENU_HOVER_TEXTO,
    COR_MENU_ITEM,    COR_MENU_ITEM_HOVER,
    COR_TOOLBAR_TERM_BG,    COR_BTN_RUN_BG,
    COR_BTN_RUN_HOVER,    ATALHO_NOVO_PROJETO,
    ATALHO_ABRIR_PROJETO,    ATALHO_ABRIR_ARQUIVO,
    ATALHO_SALVAR,    ATALHO_EXECUTAR,
    ATALHO_TAREFAS_PROJETO,    ATALHO_TAREFAS_GLOBAIS,
    ATALHO_EDITAR_TEMA,    ATALHO_EDITAR_ATALHOS,
    ATALHO_EDITOR_CONFIG,    ATALHO_AUTOCOMPLETE,
    PASTA_PROJETOS,    PASTA_APPDATA,
    ARQUIVO_CONFIG,    ARQUIVO_ATALHOS,    ARQUIVO_TEMA,
    COR_SUCESSO,    COR_INFO,    COR_AVISO,    COR_CINZA_TEXTO,
    BORDA_CONTORNO_UI)

from _EDITOR_.Indexador import Indexador
from ..barra_aba_topo import BarraTitulo
from ..barra_lateral_direita import BarraLateralDireita
from _BUSCA_.motor_busca import MotorBusca
from _BUSCA_.painel_busca_global import PainelBuscaGlobal
from _BUSCA_.command_palette import CommandPalette
from _BUSCA_.busca_comandos import buscar_comandos


class _CriadorVenv(_ThreadSegura):
    """Cria a .venv do novo projeto em background, sem bloquear a UI."""

    concluido = Signal(str)

    erro = Signal(str)

    progresso = Signal(str)  # etapa atual para exibir na status bar

    def __init__(self, caminho: str, python_exe: str = ""):
        super().__init__()

        self._caminho = caminho

        self._python_exe = python_exe
        ensure_task(self, "VENV")

    def run(self):
        _task = ensure_task(self, "VENV")
        event("RUN_ENTER", "VENV", _task, obj=self)
        try:
            venv_path = os.path.join(self._caminho, ".venv")

            self.progresso.emit(

                f"python -m venv {os.path.basename(self._caminho)}\\.venv"

            )

            if sys.platform == "win32":
                python_real = shutil.which("python") or shutil.which("python3")

                if not python_real and sys.platform == "win32":
                    python_real = shutil.which("py")

                if not python_real:
                    raise RuntimeError(

                        "Python não encontrado no PATH. Instale o Python e tente novamente."

                    )

                subprocess.run(

                    [python_real, "-m", "venv", venv_path],

                    check=True,

                    stdout=subprocess.DEVNULL,

                    stderr=subprocess.DEVNULL,

                    **opcoes_processo_sem_console(),

                )

            self.concluido.emit(self._caminho)
            event("RESULT_EMITTED", "VENV", _task, obj=self, success=True)

        except Exception as e:
            self.erro.emit(str(e))
            event("ERROR", "VENV", _task, obj=self, error=str(e))
        finally:
            event("RUN_EXIT", "VENV", _task, obj=self)

class _AnalisadorProjeto(_ThreadSegura):
    """Varre o projeto em background e retorna estatísticas para a statusbar."""

    concluido = Signal(dict)

    def __init__(self, caminho: str):
        super().__init__()

        self._caminho = caminho
        ensure_task(self, "ANALISE")

    def run(self):
        _task = ensure_task(self, "ANALISE")
        event("RUN_ENTER", "ANALISE", _task, obj=self)
        try:
            from collections import defaultdict
            from pathlib import Path
            _excluidos = {

                ".hein",

                "venv",

                ".venv",

                "env",

                ".git",

                "__pycache__",

                ".idea",

                ".nox",

                ".tox",

                "__pypackages__",

            }

            caminho = Path(self._caminho)

            total_pastas = 0

            total_arquivos = 0

            por_extensao = defaultdict(int)

            for root, dirs, files in os.walk(caminho):
                dirs[:] = [d for d in dirs if d not in _excluidos]

                total_pastas += len(dirs)

                for f in files:
                    total_arquivos += 1

                    ext = Path(f).suffix.lower() or "SEM"

                    por_extensao[ext] += 1

                    #print()

            self.concluido.emit(

                {

                    "pastas": total_pastas,

                    "arquivos": total_arquivos,

                    "extensao": dict(por_extensao),

                }

            )
            event("RESULT_EMITTED", "ANALISE", _task, obj=self,
                  total_files=total_arquivos, total_dirs=total_pastas)
        except Exception as e:
            from _LOG_.log import log
            log.erro("workers.py", "_AnalisadorProjeto.run", "excecao nao tratada na thread", str(e))
            self.concluido.emit({})
            event("ERROR", "ANALISE", _task, obj=self, error=str(e))
        finally:
            event("RUN_EXIT", "ANALISE", _task, obj=self)

def _recarregar_se_necessario(explorer, caminho: str) -> None:
    """Recarrega o explorer se o arquivo foi modificado desde o último load.

    Evita recarregar quando o explorer salvou o arquivo (flag _salvando já

    cuida disso no watcher), mas garante sync ao refocalizar uma aba JSON

    cujo arquivo foi editado enquanto outro tab estava ativo.

    """

    import os
    try:
        mtime_disco = os.path.getmtime(caminho)

    except OSError:
        return

    mtime_explorer = getattr(explorer, "_ultimo_mtime", 0.0)

    if mtime_disco > mtime_explorer + 0.5:
        explorer._carregar()

def _garantir_hein_no_gitignore(caminho_projeto: str) -> None:
    """Garante que .hein/ está no .gitignore do projeto sem sobrescrever regras existentes."""
    gitignore = os.path.join(caminho_projeto, ".gitignore")
    try:
        conteudo = open(gitignore, encoding="utf-8").read() if os.path.isfile(gitignore) else ""
        linhas = {l.strip() for l in conteudo.splitlines()}
        if ".hein/" not in linhas and ".hein" not in linhas:
            with open(gitignore, "a", encoding="utf-8") as f:
                if conteudo and not conteudo.endswith("\n"):
                    f.write("\n")
                f.write(".hein/\n")
    except Exception:
        pass
