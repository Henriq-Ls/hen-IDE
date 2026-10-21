# 📁 _UTILITARIOS_/hein_python_picker.py
"""
Botão de seleção de interpreter Python para a status bar da hein IDE.
Exibe o ambiente ativo e abre um popup para trocar — igual ao Zed/VS Code.

Uso (em main_window.py, dentro de _montar_ui, após self.statusBar().showMessage("Pronto")):

    from _UTILITARIOS_.hein_python_picker import HeinPythonPicker
    self._python_picker = HeinPythonPicker(janela=self)
    self.statusBar().addPermanentWidget(self._python_picker)

Para atualizar o projeto ativo quando o usuário abre/troca de projeto:

    self._python_picker.set_projeto(caminho)
"""

from __future__ import annotations
import glob
import os
import platform
import shutil
import subprocess
import sys
from PySide6.QtCore    import QPoint, Qt
from PySide6.QtWidgets import QLabel, QWidget
from _CONFIGURA_.gerenciador_tema import tema_global
from _UTILITARIOS_.hein_context_menu import heinContextMenu
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console
# ── helpers ───────────────────────────────────────────────────────────────────

def _executavel(pasta_venv: str) -> str:
    """Caminho do python.exe / python dentro de uma venv."""
    if platform.system() == "Windows":

        return os.path.join(pasta_venv, "Scripts", "python.exe")

    return os.path.join(pasta_venv, "bin", "python")

def _versao(exe: str) -> str:
    """Retorna '3.12.2' ou '' se falhar."""
    try:
        out = subprocess.check_output(
            [exe, "--version"],
            stderr=subprocess.STDOUT,
            timeout=3,
            **opcoes_processo_sem_console(),
        )

        return out.decode().strip().replace("Python ", "")

    except Exception:

        return ""

# ⚠️  função grande (67 linhas)
def _descobrir_ambientes(projeto: str | None) -> list[dict]:
    """
    Retorna lista de dicts:
        {"label": str, "tipo": str, "exe": str, "versao": str}
    Ordem: venv do projeto → pyenv → conda → sistema.
    """
    ambientes: list[dict] = []

    # 1. .venv do projeto atual
    if projeto:
        exe = _executavel(os.path.join(projeto, ".venv"))
        if os.path.isfile(exe):
            ambientes.append({
                "label":  os.path.basename(projeto),
                "tipo":   "venv (projeto)",
                "exe":    exe,
                "versao": _versao(exe),
            })

    # 2. pyenv versions
    pyenv_root = os.environ.get("PYENV_ROOT") or os.path.expanduser("~/.pyenv")
    for exe in sorted(glob.glob(os.path.join(pyenv_root, "versions", "*", "bin", "python"))):
        versao = _versao(exe)
        if versao:
            ambientes.append({
                "label":  os.path.basename(os.path.dirname(os.path.dirname(exe))),
                "tipo":   "pyenv",
                "exe":    exe,
                "versao": versao,
            })

    # 3. conda envs
    conda_base = os.environ.get("CONDA_PREFIX") or os.path.expanduser("~/miniconda3")
    for exe in sorted(glob.glob(os.path.join(conda_base, "envs", "*",
                                              "python.exe" if sys.platform == "win32" else "bin/python"))):
        versao = _versao(exe)
        if versao:
            nome = os.path.basename(
                os.path.dirname(os.path.dirname(exe))
                if sys.platform != "win32"
                else os.path.dirname(exe)
            )
            ambientes.append({
                "label":  nome,
                "tipo":   "conda",
                "exe":    exe,
                "versao": versao,
            })

    # 4. python do sistema
    for candidato in ("python", "python3", "python3.12", "python3.11", "python3.10"):
        exe_sys = shutil.which(candidato)
        if exe_sys:
            # Ignora se já está na lista
            if any(a["exe"] == exe_sys for a in ambientes):
                continue
            versao = _versao(exe_sys)
            if versao:
                ambientes.append({
                    "label":  "sistema",
                    "tipo":   "sistema",
                    "exe":    exe_sys,
                    "versao": versao,
                })
            break  # só o primeiro válido do sistema

    return ambientes

# ── widget ────────────────────────────────────────────────────────────────────

class HeinPythonPicker(QLabel):
    """
    Botão compacto na status bar.
    Mostra '⬡ Python 3.12.2' e ao clicar abre heinContextMenu com os ambientes.
    """

    def __init__(self, janela=None, parent: QWidget | None = None):
        super().__init__(parent)
        self._janela  = janela       # MainWindow — para pegar current_project_path
        self._projeto: str | None = None
        self._exe_ativo: str = shutil.which("python") or shutil.which("python3") or "python"
        self._ambientes: list[dict] = []

        self.setCursor(Qt.PointingHandCursor)
        self._aplicar_estilo()
        self._atualizar_label()

    # ── estilo ────────────────────────────────────────────────────────

    def _aplicar_estilo(self):
        t    = tema_global()
        bg   = t.cor("interface.fundo_barra_status",  "#1e1e1e")
        txt  = t.cor("interface.texto_barra_status",  "#c8c8c8")
        hov  = t.cor("menu_contexto.item_hover",      "#2a2a2a")
        self.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                color: {txt};
                padding: 0 10px;
                font-size: 11px;
            }}
            QLabel:hover {{
                background: {hov};
            }}
        """)

    # ── label ─────────────────────────────────────────────────────────

    def _atualizar_label(self):
        versao = _versao(self._exe_ativo)
        texto  = f"⬡  Python {versao}" if versao else "⬡  Python"
        self.setText(texto)
        self.setToolTip(self._exe_ativo)

    # ── API pública ───────────────────────────────────────────────────

    def set_projeto(self, caminho: str | None):
        """Chame quando o usuário abre/troca de projeto."""
        self._projeto = caminho

        # Tenta ativar automaticamente o .venv do projeto
        if caminho:
            exe_venv = _executavel(os.path.join(caminho, ".venv"))
            if os.path.isfile(exe_venv):
                self._exe_ativo = exe_venv
                self._atualizar_label()

    # ── popup ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._abrir_popup()
        else:
            super().mousePressEvent(event)

    # ⚠️  função grande (51 linhas)
    def _abrir_popup(self):
        projeto = self._projeto or (
            getattr(self._janela, "current_project_path", None)
            if self._janela else None
        )
        self._ambientes = _descobrir_ambientes(projeto)

        if not self._ambientes:
            # Nada encontrado — mostra aviso simples
            from PySide6.QtWidgets import QToolTip
            QToolTip.showText(
                self.mapToGlobal(QPoint(0, -30)),
                "Nenhum interpreter Python encontrado.",
                self,
            )

            return

        itens = []
        for amb in self._ambientes:
            # Label: "venv (projeto)  •  3.12.2"  +  path resumido
            titulo   = f"{amb['label']}  •  Python {amb['versao']}"
            subtitulo = amb["tipo"]
            # Ícone por tipo
            icone_map = {
                "venv (projeto)": "mdi.language-python",
                "pyenv":          "mdi.language-python",
                "conda":          "mdi.snake",
                "sistema":        "mdi.console",
            }
            icone = icone_map.get(amb["tipo"], "mdi.language-python")

            exe = amb["exe"]           # captura para o lambda
            def _cb(e=exe, t=titulo):
                self._selecionar(e, t)

            itens.append((titulo, icone, _cb))

        # Opção de reconstrução da venv com o Python atual (preserva pacotes)
        proj = self._projeto or (
            getattr(self._janela, "current_project_path", None)
            if self._janela else None
        )
        if proj:
            itens.append(None)  # separador
            itens.append(("Reconstruir .venv (manter pacotes)", "mdi.refresh", self._reconstruir_venv))
        menu = heinContextMenu(parent=self, itens=itens)

        # Abre acima do botão
        pos_global = self.mapToGlobal(QPoint(0, -menu.sizeHint().height() - 4))
        menu.exec(pos_global)

    def _selecionar(self, exe: str, titulo: str):
        if not isinstance(exe, str):

            return

        # Se existe .venv diferente no projeto → migrar de forma não-bloqueante
        import os as _os
        if self._projeto:
            exe_venv = _executavel(_os.path.join(self._projeto, ".venv"))
            if (_os.path.isfile(exe_venv)
                    and _os.path.normcase(exe) != _os.path.normcase(exe_venv)):
                from _UTILITARIOS_.hein_migrador_venv import iniciar_migracao

                def _on_migrado(sucesso: bool, novo_exe: str):
                    alvo = novo_exe if sucesso else exe
                    self._exe_ativo = alvo
                    self._atualizar_label()
                    if (self._janela
                            and hasattr(self._janela, "_ao_python_picker_selecionado")):
                        self._janela._ao_python_picker_selecionado(alvo)

                iniciar_migracao(self._projeto, exe, self._janela, _on_migrado)

                return  # callback cuida da atualização

        self._exe_ativo = exe
        self._atualizar_label()
        if self._janela and hasattr(self._janela, "_ao_python_picker_selecionado"):
            self._janela._ao_python_picker_selecionado(exe)

    def _reconstruir_venv(self):
        """Reconstrói a .venv com o Python atual, preservando pacotes instalados."""
        proj = self._projeto or (
            getattr(self._janela, "current_project_path", None)
            if self._janela else None
        )
        if not proj:

            return

        exe = self._exe_ativo

        def _on_migrado(sucesso: bool, novo_exe: str):
            alvo = novo_exe if sucesso else exe
            self._exe_ativo = alvo
            self._atualizar_label()
            if (self._janela
                    and hasattr(self._janela, "_ao_python_picker_selecionado")):
                self._janela._ao_python_picker_selecionado(alvo)

        from _UTILITARIOS_.hein_migrador_venv import iniciar_migracao
        iniciar_migracao(proj, exe, self._janela, _on_migrado)
