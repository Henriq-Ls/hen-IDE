# 📁 _CONFIGURA_/gerenciador_tarefas.py
"""
GerenciadorTarefas — singleton de gerenciamento de tarefas F2–F10.

Carrega tarefas.json (global e do projeto ativo), registra QShortcuts
ApplicationShortcut na MainWindow e executa comandos via PowerShell.

Slot de tarefa = índice na lista combinada (projeto primeiro, global depois).
  índice 0 → F2, índice 1 → F3, ..., índice 8 → F10

Variáveis expandidas no campo "comando":
  $PROJETO  → raiz do projeto aberto
  $ARQUIVO  → caminho completo do arquivo ativo no editor
  $VENV     → python.exe da venv do projeto
  $SCRIPTS  → AppData/Roaming/hein/scripts/
"""

import json
import os
import re
import sys
from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from _CONFIGURA_ import PASTA_SCRIPTS, TAREFAS_FKEYS
from _LOG_.log import log
_ARQ = "gerenciador_tarefas.py"

_instancia: "GerenciadorTarefas | None" = None

def gerenciador_tarefas() -> "GerenciadorTarefas | None":
    """Retorna a instância singleton do GerenciadorTarefas."""

    return _instancia

class GerenciadorTarefas(QObject):
    """Gerencia as tarefas da IDE hein."""

    def __init__(self, janela):
        global _instancia
        super().__init__(janela)
        self._janela = janela
        self._shortcuts: list[QShortcut] = []
        self._tarefas_projeto: list[dict] = []
        self._tarefas_globais: list[dict] = []
        _instancia = self

    # ── Carregamento ──────────────────────────────────────────────────────

    def carregar_globais(self) -> None:
        """Lê AppData/hein/tarefas.json e re-registra atalhos."""
        from _CONFIGURA_ import ARQUIVO_TAREFAS_GLOBAIS
        self._tarefas_globais = self._ler(ARQUIVO_TAREFAS_GLOBAIS)
        self._registrar_shortcuts()

    def carregar_projeto(self, projeto_path: str) -> None:
        """Lê <projeto>/.hein/tarefas.json e re-registra atalhos."""
        self._tarefas_projeto = []
        if projeto_path:
            caminho = os.path.join(projeto_path, ".hein", "tarefas.json")
            self._tarefas_projeto = self._ler(caminho)
        self._registrar_shortcuts()

    def carregar_projeto_do_caminho(self, caminho: str) -> None:
        """Recarrega tarefas do projeto a partir do caminho direto do arquivo."""
        self._tarefas_projeto = self._ler(caminho)
        self._registrar_shortcuts()

    def _ler(self, caminho: str) -> list[dict]:
        if not os.path.exists(caminho):

            return []

        try:
            with open(caminho, encoding="utf-8") as f:
                texto = re.sub(r"//[^\n]*", "", f.read())
            dados = json.loads(texto)
            if isinstance(dados, dict):

                return dados.get("tarefas", [])

            if isinstance(dados, list):

                return dados

        except Exception as e:
            log.aviso(_ARQ, "_ler", f"erro ao ler '{caminho}': {e}")

        return []

    def _todos(self) -> list[dict]:
        """Combina projeto + global; projeto tem prioridade em colisão de atalho."""
        vistos: set[str] = set()
        resultado: list[dict] = []
        for tarefa in self._tarefas_projeto + self._tarefas_globais:
            chave = tarefa.get("atalho", "").lower().strip()
            if chave and chave not in vistos:
                vistos.add(chave)
                resultado.append(tarefa)

        return resultado

    # ── Registro de atalhos ───────────────────────────────────────────────

    def _registrar_shortcuts(self) -> None:
        for sc in self._shortcuts:
            sc.setEnabled(False)
            sc.deleteLater()
        self._shortcuts.clear()

        for tarefa in self._todos():
            fkey = tarefa.get("atalho", "").strip()
            if not fkey:
                continue
            sc = QShortcut(QKeySequence(fkey), self._janela)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(lambda t=tarefa: self.executar(t))
            self._shortcuts.append(sc)

        n = len(self._shortcuts)
        log.ok(_ARQ, "_registrar_shortcuts", f"{n} atalho(s) registrado(s)")

    # ── Execução ──────────────────────────────────────────────────────────

    def executar(self, tarefa: dict) -> None:
        """Expande variáveis e envia o comando ao terminal de tarefa."""
        nome    = tarefa.get("nome", "Tarefa").strip() or "Tarefa"
        comando = tarefa.get("comando", "").strip()
        mostrar = tarefa.get("mostrar_terminal", True)
        pausar  = tarefa.get("pausar", False)

        if not comando:
            log.aviso(_ARQ, "executar", "tarefa sem comando — ignorada")

            return

        projeto = getattr(self._janela, "current_project_path", "") or ""
        arquivo = ""
        if hasattr(self._janela, "tabs"):
            ed      = self._janela.tabs.get_current_editor()
            arquivo = getattr(ed, "file_path", "") or ""

        # diretorio da tarefa, expande variáveis
        diretorio_raw = tarefa.get("diretorio", "$PROJETO").strip()
        diretorio     = self._expandir(diretorio_raw, projeto, arquivo) if diretorio_raw else projeto
        if not diretorio or not os.path.isdir(diretorio):
            diretorio = projeto

        cmd_exp = self._expandir(comando, projeto, arquivo)
        log.ok(_ARQ, "executar", f"'{nome}' → {cmd_exp}")

        if mostrar and hasattr(self._janela, "terminal_tabs"):
            self._janela.terminal_tabs.abrir_aba_tarefa(nome, cmd_exp, diretorio)

    def _expandir(self, cmd: str, projeto: str, arquivo: str) -> str:
        """Substitui $PYTHON, $TAREFAS/$SCRIPTS, $PROJETO, $ARQUIVO e $VENV."""
        if os.name == "nt":
            venv_py = os.path.join(projeto, ".venv", "Scripts", "python.exe") if projeto else ""
        else:
            venv_py = os.path.join(projeto, ".venv", "bin", "python") if projeto else ""

        # $PYTHON = python do venv do projeto se existir, senão o da IDE
        python_ativo = venv_py if (venv_py and os.path.isfile(venv_py)) else sys.executable

        from _CONFIGURA_ import PASTA_TAREFAS

        return (

            cmd
            .replace("$PYTHON",  python_ativo)
            .replace("$TAREFAS", PASTA_TAREFAS)
            .replace("$SCRIPTS", PASTA_TAREFAS)   # alias retrocompatível
            .replace("$PROJETO", projeto)
            .replace("$ARQUIVO", arquivo)
            .replace("$VENV",    venv_py)
        )
