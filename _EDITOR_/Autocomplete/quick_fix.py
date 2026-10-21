# 📁 _EDITOR_/Autocomplete/quick_fix.py
# -*- coding: utf-8 -*-
"""
PopupQuickFix — popup interativo de correção rápida de imports.

Aparece ao passar o mouse sobre uma linha com erro e oferece:
  • "➕ import X"   — insere o import no topo do arquivo
  • "📦 Instalar X" — instala o pacote via pip na .venv do projeto

Gatilho: _checar_tooltip_erro() no Editor.py, via mouseMoveEvent.

Casos tratados:
  1. Erro de import (ValidadorImports) — a linha é "import modulo_inexistente"
       → módulo não está na stdlib nem na .venv → botão "Instalar"
  2. Nome indefinido (pyflakes) — "undefined name 'numpy'" etc.
       → se estiver na stdlib / .venv → botão "Adicionar import"
       → se não estiver            → botão "Instalar"
"""
import functools
import os
import re
import sys
import platform

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication
)
from _EDITOR_.popup_base import PopupBase
from PySide6.QtCore import Qt, QProcess, QTimer, Signal
from PySide6.QtGui  import QTextCursor

from _CONFIGURA_.gerenciador_tema import tema_global
from _LOG_.log import log

_ARQ = "quick_fix.py"

# ── stdlib ────────────────────────────────────────────────────────────────────
try:
    _STDLIB: frozenset = sys.stdlib_module_names   # Python 3.10+
except AttributeError:
    _STDLIB = frozenset({
        "os", "sys", "re", "ast", "json", "math", "time", "datetime",
        "pathlib", "typing", "collections", "itertools", "functools",
        "threading", "subprocess", "tempfile", "shutil", "copy", "io",
        "string", "random", "hashlib", "abc", "enum", "dataclasses",
        "contextlib", "inspect", "importlib", "logging", "warnings",
        "traceback", "unittest", "argparse", "struct", "socket",
        "http", "urllib", "email", "html", "xml", "csv", "sqlite3",
        "pickle", "gzip", "zipfile", "tarfile", "base64", "uuid",
        "platform", "signal", "queue", "weakref", "gc", "dis",
        "tokenize", "token", "keyword", "builtins", "types",
        "tkinter", "tkinter.ttk", "ctypes", "array", "binascii",
        "cmath", "decimal", "fractions", "statistics", "textwrap",
        "pprint", "reprlib", "bisect", "heapq", "functools",
    })

# ── helpers puros (sem Qt) ────────────────────────────────────────────────────

def extrair_nome_undefined(mensagem: str) -> str | None:
    """
    Extrai o identificador de mensagens de 'nome não definido' do pyflakes.
    Exemplos:
      "undefined name 'numpy'"  → "numpy"
      "'os' is not defined"     → "os"
    """
    m = re.search(r"undefined name '([A-Za-z0-9_]+)'", mensagem, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"'([A-Za-z0-9_]+)' is not defined", mensagem, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def extrair_modulo_da_linha(texto: str) -> str | None:
    """
    Extrai o nome do módulo raiz de uma linha de import.
      "import numpy"            → "numpy"
      "from pandas import DF"   → "pandas"
      "import os.path"          → "os"
    """
    m = re.match(r"^\s*from\s+([A-Za-z0-9_]+)", texto)
    if m:
        return m.group(1)
    m = re.match(r"^\s*import\s+([A-Za-z0-9_]+)", texto)
    if m:
        return m.group(1)
    return None


def achar_pip(project_path: str | None) -> str | None:
    """Localiza o executável pip na .venv do projeto (Windows e Linux)."""
    if not project_path:
        return None
    scripts = "Scripts" if platform.system() == "Windows" else "bin"
    exe     = "pip.exe" if platform.system() == "Windows" else "pip"
    caminho = os.path.join(project_path, ".venv", scripts, exe)
    return caminho if os.path.isfile(caminho) else None


def modulo_em_stdlib(nome: str) -> bool:
    """True se o nome é um módulo da biblioteca padrão do Python."""
    return nome in _STDLIB


@functools.lru_cache(maxsize=512)
def modulo_em_venv(nome: str, project_path: str | None) -> bool:
    """True se o módulo está instalado na .venv do projeto.

    Cache lru_cache(512): evita I/O de disco repetido enquanto o mouse fica
    parado sobre uma linha com erro (o debounce de 80ms dispara continuamente).
    Invalide com modulo_em_venv.cache_clear() ao trocar de projeto.
    """
    if not project_path:
        return False
    sp_candidatos = [
        os.path.join(project_path, ".venv", "Lib",  "site-packages"),  # Windows
        os.path.join(project_path, ".venv", "lib"),                      # Linux
    ]
    for sp in sp_candidatos:
        if not os.path.isdir(sp):
            continue
        # Só conta como instalado se o pacote de fato existe e é importável
        # (pasta ou .py com o nome exato). Não usar correspondência por
        # prefixo aqui: um '.dist-info' deixado por uma instalação via pip
        # que falhou no meio do caminho batia com startswith() e fazia o
        # quick-fix mostrar "importar" para um módulo que não está instalado.
        if os.path.isdir(os.path.join(sp, nome)):
            return True
        if os.path.isfile(os.path.join(sp, nome + ".py")):
            return True
    return False


# ── Widget ────────────────────────────────────────────────────────────────────

class _ToastInstalando(PopupBase):
    """Aviso flutuante e animado de 'instalando pacote', com botão Cancelar.

    Existe pra não depender só da mensagem na status bar — que fica
    escondida atrás dos painéis inferiores (Saída/Terminal/Pacotes) na
    maioria dos layouts. Aparece flutuando por cima do editor, no mesmo
    lugar do popup de quick-fix, com um spinner girando enquanto o pip
    roda — e um botão "Cancelar" pra matar o processo caso o usuário tenha
    clicado errado ou a instalação esteja demorando demais / travada."""

    _FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    cancelado = Signal()

    def __init__(self, editor):
        super().__init__(editor.viewport())

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(8)

        self._lbl_spinner = QLabel(self._FRAMES[0])
        lay.addWidget(self._lbl_spinner)

        self._lbl_texto = QLabel("")
        lay.addWidget(self._lbl_texto)

        self._btn_cancelar = QPushButton("✕  Cancelar")
        self._btn_cancelar.setCursor(Qt.PointingHandCursor)
        self._btn_cancelar.clicked.connect(self.cancelado.emit)
        lay.addWidget(self._btn_cancelar)

        self._frame_i = 0
        self._timer_spinner = QTimer(self)
        self._timer_spinner.setInterval(90)
        self._timer_spinner.timeout.connect(self._tick)

        self._aplicar_tema()
        self.hide()

    def _aplicar_tema(self):
        self._aplicar_estilo_base()
        cor_ok    = tema_global().cor("editor.string",  "#4ec994")
        cor_erro  = tema_global().cor("editor.erro",    "#e06c75")
        self._lbl_spinner.setStyleSheet(
            f"color: {cor_ok}; font-size: 13px; font-weight: bold; background: transparent;"
        )
        self._lbl_texto.setStyleSheet(
            f"color: {self._cor_texto()}; font-size: 11px; background: transparent;"
        )
        self._btn_cancelar.setStyleSheet(f"""
            QPushButton {{
                color: {cor_erro};
                background: transparent;
                border: 1px solid {cor_erro};
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {self._cor_hover()};
            }}
        """)

    def _tick(self):
        self._frame_i = (self._frame_i + 1) % len(self._FRAMES)
        self._lbl_spinner.setText(self._FRAMES[self._frame_i])

    def mostrar(self, texto: str, pos_global):
        self._frame_i = 0
        self._lbl_spinner.setText(self._FRAMES[0])
        self._lbl_texto.setText(texto)
        self._aplicar_tema()
        self._posicionar_e_exibir(pos_global)
        self._timer_spinner.start()

    def fechar(self):
        self._timer_spinner.stop()
        super().fechar()


class PopupQuickFix(PopupBase):
    """
    Popup flutuante de quick-fix.
    Herda flags, tema e ciclo de vida (fechamento por foco/app) de PopupBase.

    Ciclo de vida:
      mostrar(...)  — exibe o popup na posição global indicada
      fechar()      — esconde o popup
      linha_atual() — linha do editor à qual o popup pertence (ou -1)
    """

    def __init__(self, editor):
        # fechar_ao_perder_foco=True: PopupBase conecta focusChanged e
        # applicationStateChanged automaticamente — não precisamos mais
        # fazer isso manualmente aqui.
        super().__init__(editor.viewport(), fechar_ao_perder_foco=True)
        self._editor      = editor
        self._nome_modulo = ""
        self._pip_path: str | None = None
        self._linha       = -1
        self._processo: QProcess | None = None
        self._pos_atual   = None
        self._cancelado   = False

        self._toast = _ToastInstalando(editor)
        self._toast.cancelado.connect(self._ao_cancelar_instalacao)

        self._construir_ui()
        self._aplicar_tema()
        self.hide()

    def _editor_widget(self):
        """Necessário para PopupBase._ao_foco_mudar() não fechar ao clicar no editor."""
        return self._editor

    # ── construção da UI ──────────────────────────────────────────────

    def _construir_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        self._lbl_msg = QLabel("")
        self._lbl_msg.setWordWrap(True)
        self._lbl_msg.setMaximumWidth(380)
        lay.addWidget(self._lbl_msg)

        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(6)
        btn_lay.addStretch()

        self._btn_importar = QPushButton("➕  import …")
        self._btn_importar.setCursor(Qt.PointingHandCursor)
        self._btn_importar.clicked.connect(self._ao_importar)
        btn_lay.addWidget(self._btn_importar)

        self._btn_instalar = QPushButton("📦  Instalar …")
        self._btn_instalar.setCursor(Qt.PointingHandCursor)
        self._btn_instalar.clicked.connect(self._ao_instalar)
        btn_lay.addWidget(self._btn_instalar)

        lay.addLayout(btn_lay)

    def _aplicar_tema(self):
        cor_ok = tema_global().cor("editor.string", "#4ec994")
        self._aplicar_estilo_base()
        # Sobrescreve apenas os widgets filhos — o QFrame já foi estilizado
        # por _aplicar_estilo_base() com as cores corretas do tema.
        self.setStyleSheet(
            self.styleSheet() + f"""
            QLabel {{
                color: {self._cor_texto()};
                font-size: 11px;
                background: transparent;
            }}
            QPushButton {{
                color: {cor_ok};
                background: transparent;
                border: 1px solid {cor_ok};
                border-radius: 3px;
                padding: 3px 10px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {self._cor_hover()};
            }}
        """
        )

    # ── API pública ───────────────────────────────────────────────────

    def mostrar(self, pos_global, msg_traduzida: str, nome_modulo: str,
                pode_importar: bool, pode_instalar: bool,
                pip_path: str | None, linha: int):
        """
        Exibe o popup.

        pos_global    — QPoint em coordenadas globais (abaixo da linha de erro)
        msg_traduzida — mensagem de erro já em pt-BR
        nome_modulo   — "numpy", "os", etc.
        pode_importar — True: só falta o import (módulo já instalado)
        pode_instalar — True: módulo precisa ser instalado via pip
        pip_path      — caminho do pip da .venv (ou None se não houver .venv)
        linha         — número da linha (1-based) para evitar reposição desnecessária
        """
        self._nome_modulo = nome_modulo
        self._pip_path    = pip_path
        self._linha       = linha
        self._aplicar_tema()

        self._lbl_msg.setText(msg_traduzida)
        self._btn_importar.setText(f"➕  import {nome_modulo}")
        self._btn_instalar.setText(f"📦  Instalar {nome_modulo}")

        _mostrar_importar = bool(pode_importar)
        _mostrar_instalar = bool(pode_instalar and pip_path)
        self._btn_importar.setVisible(_mostrar_importar)
        self._btn_instalar.setVisible(_mostrar_instalar)

        # Bug corrigido: não usar isVisible() dos botões aqui — o popup (self)
        # ainda está oculto neste ponto, e isVisible() de um filho é sempre
        # False enquanto qualquer ancestral estiver escondido. Usar as
        # variáveis booleanas diretamente, não o estado de visibilidade do Qt.
        if not _mostrar_importar and not _mostrar_instalar:
            self.hide()
            return

        self._pos_atual = pos_global
        self._posicionar_e_exibir(pos_global)

    def fechar(self):
        super().fechar()
        self._linha = -1

    def linha_atual(self) -> int:
        """Linha do editor à qual o popup atual pertence (-1 = nenhum)."""
        return self._linha

    # ── Ações ─────────────────────────────────────────────────────────

    def _ao_importar(self):
        """Insere 'import <modulo>' após o bloco de imports existentes."""
        if not self._nome_modulo:
            return
        self.fechar()

        editor  = self._editor
        codigo  = editor.toPlainText()
        linhas  = codigo.splitlines()
        nova    = f"import {self._nome_modulo}"

        # Evita duplicata (import X ou from X import ...)
        for l in linhas:
            s = l.strip()
            if s == nova or s.startswith(f"from {self._nome_modulo} import"):
                log.info(_ARQ, "_ao_importar",
                         f"import '{self._nome_modulo}' já existe — nada a fazer")
                return

        # Posição: após o último "import / from" contíguo ao topo
        # (ignora linhas em branco e comentários no início)
        pos_insercao = 0
        for i, linha in enumerate(linhas):
            s = linha.strip()
            if s.startswith(("import ", "from ")):
                pos_insercao = i + 1          # linha logo após este import
            elif s and not s.startswith("#"):
                break                          # primeira linha de código — para

        doc    = editor.document()
        bloco  = doc.findBlockByNumber(pos_insercao)
        cursor = editor.textCursor()
        if bloco.isValid():
            cursor.setPosition(bloco.position())
        else:
            cursor.movePosition(QTextCursor.End)
        cursor.insertText(nova + "\n")
        editor.setTextCursor(cursor)
        log.ok(_ARQ, "_ao_importar",
               f"Inserido '{nova}' na linha {pos_insercao + 1}")

    def _ao_instalar(self):
        """Instala o pacote via pip na .venv do projeto.
        Sem confirmação extra: o clique no botão "Instalar" do popup já é
        a confirmação — pedir de novo aqui era atrito redundante."""
        if not self._nome_modulo or not self._pip_path:
            return
        if self._processo is not None:
            try:
                if self._processo.state() != QProcess.ProcessState.NotRunning:
                    return
            except RuntimeError:
                self._processo = None
        pos_toast = self._pos_atual
        self.fechar()

        self._cancelado = False
        self._processo = QProcess()
        self._processo.setProperty("_modulo", self._nome_modulo)
        self._processo.finished.connect(self._ao_instalar_concluido)
        self._processo.start(self._pip_path, ["install", self._nome_modulo])
        log.info(_ARQ, "_ao_instalar", f"pip install {self._nome_modulo} ...")

        if pos_toast is not None:
            self._toast.mostrar(f"Instalando {self._nome_modulo} …", pos_toast)

    def _ao_cancelar_instalacao(self):
        """Mata o processo do pip em andamento quando o usuário clica em
        'Cancelar' no toast de instalação."""
        if not self._processo:
            return
        self._cancelado = True
        log.info(_ARQ, "_ao_cancelar_instalacao",
                 f"Cancelando instalação de {self._nome_modulo}...")
        self._processo.kill()
        self._processo.waitForFinished(1000)
        self._toast.fechar()

    def _ao_instalar_concluido(self, code, _status):
        self._toast.fechar()
        proc      = self._processo
        modulo    = (proc.property("_modulo") if proc else None) or self._nome_modulo
        cancelado = self._cancelado
        self._cancelado = False
        saida = ""
        if proc:
            try:
                saida = proc.readAllStandardError().data().decode(errors="replace")
            except RuntimeError:
                pass
        self._processo = None
        if cancelado:
            log.info(_ARQ, "_ao_instalar_concluido",
                     f"Instalação de {modulo} cancelada pelo usuário")
            return
        from _UTILITARIOS_.hein_pou_pap import HeinPopup
        if code == 0:
            HeinPopup.info(
                "Pacote instalado",
                f"<b>{modulo}</b> instalado com sucesso!",
                informativo=(
                    "O autocomplete já reconhece o pacote.\n"
                    "Passe o mouse sobre o erro novamente para adicionar o import."
                ),
                parent=self._editor.window(),
            )
            log.ok(_ARQ, "_ao_instalar_concluido", f"{modulo} instalado")
            # Força revalidação para o sublinhado sumir
            try:
                self._editor._validador_imports.verificar_agora()
            except Exception:
                pass
        else:
            HeinPopup.erro(
                "Falha na instalação",
                f"Não foi possível instalar <b>{modulo}</b>.",
                informativo=saida[:300] if saida else None,
                parent=self._editor.window(),
            )
            log.erro(_ARQ, "_ao_instalar_concluido",
                     f"pip install {modulo} saiu com código {code}", saida[:200])
