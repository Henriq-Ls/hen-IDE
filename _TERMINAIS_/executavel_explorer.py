# 📁 _TERMINAIS_/executavel_explorer.py
"""
ExecutavelExplorer — painel visual para executavel.json por projeto.

Layout:
  ┌─ Cabeçalho ─────────────────────────────────────────────────────────┐
  │  🔍 Auto-detectar  |  ⬆ Salvar  |  ▶ Criar exe                    │
  ├──────────────────────────┬──────────────────────────────────────────┤
  │  requirements.txt        │  Formulário                               │
  │  (read-only)             │    BUILD:      Modo / onefile / console   │
  ├──────────────────────────┤    AUTO-GERADO: deps / add_data / hidden  │
  │  Árvore do projeto       │    DEPS EXTRAS: requirements_extra        │
  │  (read-only)             │    ARQUIVOS EXTRAS: arquivos_extra        │
  ├──────────────────────────┴──────────────────────────────────────────┤
  │  Terminal de build (oculto até clicar ▶ Criar exe)                  │
  └─────────────────────────────────────────────────────────────────────┘
  Nota: Nome / Versão / Ícone são gerenciados pelo PainelExecutavel (painel esquerdo).

Sincronização bidirecional via QFileSystemWatcher:
  explorer → JSON: botão Salvar
  JSON → explorer: watcher detecta mudança em disco → recarrega

Build pipeline (botão ▶ Criar exe):
  1. Salva formulário → JSON
  2. pip install pyinstaller pyinstaller-versionfile  (na .venv do projeto)
  3. GerarSpecThread: gera .spec + versionfile
  4. ProcessoThread: roda PyInstaller — output vai para o terminal embutido
"""

import json
import os
import re
import sys

from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher, QUrl
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from _CONFIGURA_.gerenciador_tema import tema_global
from _UTILITARIOS_.icones import icone_tema
from _LOG_.log import log

_ARQ = "executavel_explorer.py"


# ══════════════════════════════════════════════════════════════════════
# Utilitários de JSON
# ══════════════════════════════════════════════════════════════════════

def _carregar_json(caminho: str) -> dict:
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.erro(_ARQ, "_carregar_json", str(e))
        return {}


def _url_repositorio_github(raiz: str) -> str | None:
    """Lê a URL do remoto 'origin' (git config) e devolve a URL https 'limpa'
    do repositório no GitHub (sem token embutido, sem '.git' no final).
    Usado só pra montar os links de 'Ver no GitHub Actions' / 'Ver Releases'
    — não faz nenhuma chamada de rede."""
    import re
    import subprocess
    from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console
    try:
        resultado = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=raiz, capture_output=True, text=True, timeout=5,
            **opcoes_processo_sem_console(),
        )
        url = resultado.stdout.strip()
    except Exception:
        return None
    if not url:
        return None
    # remove token embutido (https://TOKEN@github.com/... ou https://user:TOKEN@github.com/...)
    url = re.sub(r"https://[^@/]+@", "https://", url)
    # git@github.com:owner/repo.git → https://github.com/owner/repo
    m = re.match(r"git@github\.com:(.+?)(\.git)?$", url)
    if m:
        return f"https://github.com/{m.group(1)}"
    if url.startswith("https://github.com/"):
        return url[:-4] if url.endswith(".git") else url
    return None


def _ler_gitignore(raiz: str) -> set[str]:
    """Parseia .gitignore e retorna padrões simples (sem '/' no meio).

    Retorna conjunto vazio se o arquivo não existir ou falhar na leitura.
    Padrões retornados são compatíveis com fnmatch — ex: '*.pyc', '__pycache__'.
    """
    path = os.path.join(raiz, ".gitignore")
    padroes: set[str] = set()
    if not os.path.isfile(path):
        return padroes
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for linha in f:
                linha = linha.strip()
                if not linha or linha.startswith("#") or linha.startswith("!"):
                    continue
                padrao = linha.strip("/")
                # Ignora padrões complexos com separador no meio (ex: subdir/arquivo)
                if "/" in padrao or not padrao:
                    continue
                padroes.add(padrao)
    except Exception:
        pass
    return padroes



def _salvar_json(caminho: str, dados: dict) -> bool:
    try:
        tmp = caminho + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        try:
            os.replace(tmp, caminho)
        except OSError:
            # Fallback Windows: watcher pode travar o rename
            import shutil
            shutil.copy2(tmp, caminho)
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return True
    except Exception as e:
        log.erro(_ARQ, "_salvar_json", str(e))
        return False


# ══════════════════════════════════════════════════════════════════════
# Widget: lista editável de strings (requirements_extra)
# ══════════════════════════════════════════════════════════════════════

class _ListaStrings(QWidget):
    """Lista de strings com botões Adicionar / Remover."""

    def __init__(self, itens: list[str], placeholder: str = "", parent=None):
        super().__init__(parent)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(3)
        self._linhas: list[QWidget] = []
        self._placeholder = placeholder
        for item in itens:
            self._adicionar_linha(item)
        btn_add = QPushButton("＋  Adicionar")
        btn_add.setFixedHeight(24)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(
            "QPushButton { background: transparent; color: #4ec994; border: none;"
            " font-size: 10px; text-align: left; padding-left: 2px; }"
            "QPushButton:hover { text-decoration: underline; }"
        )
        btn_add.clicked.connect(lambda: self._adicionar_linha(""))
        self._lay.addWidget(btn_add)

    def _adicionar_linha(self, texto: str = "") -> None:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        campo = QLineEdit(texto)
        campo.setFixedHeight(24)
        campo.setPlaceholderText(self._placeholder)
        btn_rem = QPushButton("✕")
        btn_rem.setFixedSize(22, 22)
        btn_rem.setCursor(Qt.PointingHandCursor)
        btn_rem.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #555; }"
            "QPushButton:hover { color: #e05252; }"
        )
        btn_rem.clicked.connect(lambda: self._remover_linha(row))
        lay.addWidget(campo, 1)
        lay.addWidget(btn_rem)
        insert_at = self._lay.count() - 1
        self._lay.insertWidget(insert_at, row)
        self._linhas.append(row)

    def _remover_linha(self, row: QWidget) -> None:
        if row in self._linhas:
            self._linhas.remove(row)
        row.setParent(None)
        row.deleteLater()

    def valores(self) -> list[str]:
        resultado = []
        for row in self._linhas:
            le = row.findChild(QLineEdit)
            if le:
                v = le.text().strip()
                if v:
                    resultado.append(v)
        return resultado

    def set_valores(self, itens: list[str]) -> None:
        for row in list(self._linhas):
            row.setParent(None)
            row.deleteLater()
        self._linhas.clear()
        for item in itens:
            self._adicionar_linha(item)


# ══════════════════════════════════════════════════════════════════════
# Widget: lista editável de pares {origem, destino} (arquivos_extra)
# ══════════════════════════════════════════════════════════════════════

class _ListaPares(QWidget):
    """Lista de pares origem/destino com botões Adicionar / Remover / Navegar."""

    def __init__(self, itens: list[dict], parent=None):
        super().__init__(parent)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(4)
        self._linhas: list[QWidget] = []
        for item in itens:
            self._adicionar_linha(item.get("origem", ""), item.get("destino", ""))
        btn_add = QPushButton("＋  Adicionar arquivo/pasta")
        btn_add.setFixedHeight(24)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(
            "QPushButton { background: transparent; color: #4ec994; border: none;"
            " font-size: 10px; text-align: left; padding-left: 2px; }"
            "QPushButton:hover { text-decoration: underline; }"
        )
        btn_add.clicked.connect(lambda: self._adicionar_linha("", ""))
        self._lay.addWidget(btn_add)

    def _adicionar_linha(self, origem: str = "", destino: str = "") -> None:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        campo_origem = QLineEdit(origem)
        campo_origem.setFixedHeight(24)
        campo_origem.setPlaceholderText("Origem (ex: assets/logo.png)")
        campo_origem.setToolTip("Caminho relativo ao projeto (arquivo ou pasta)")
        btn_nav = QPushButton()
        btn_nav.setIcon(icone_tema("mdi.folder-search-outline"))
        btn_nav.setFixedSize(24, 24)
        btn_nav.setCursor(Qt.PointingHandCursor)
        btn_nav.setToolTip("Navegar para selecionar arquivo ou pasta de origem")
        btn_nav.setStyleSheet(
            "QPushButton { background: #16321a; border: 1px solid #3a6a3a; border-radius: 3px; }"
            "QPushButton:hover { background: #1e4523; border-color: #4ec994; }"
        )
        btn_nav.clicked.connect(lambda: self._navegar_origem(campo_origem))
        seta = QLabel("→")
        seta.setFixedWidth(14)
        seta.setAlignment(Qt.AlignCenter)
        seta.setStyleSheet("color: #555; font-size: 10px;")
        campo_destino = QLineEdit(destino)
        campo_destino.setFixedHeight(24)
        campo_destino.setPlaceholderText("Destino (ex: assets)")
        campo_destino.setToolTip("Pasta de destino dentro do bundle")
        btn_rem = QPushButton("✕")
        btn_rem.setFixedSize(22, 22)
        btn_rem.setCursor(Qt.PointingHandCursor)
        btn_rem.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #555; }"
            "QPushButton:hover { color: #e05252; }"
        )
        btn_rem.clicked.connect(lambda: self._remover_linha(row))
        lay.addWidget(campo_origem, 2)
        lay.addWidget(btn_nav)
        lay.addWidget(seta)
        lay.addWidget(campo_destino, 1)
        lay.addWidget(btn_rem)
        insert_at = self._lay.count() - 1
        self._lay.insertWidget(insert_at, row)
        self._linhas.append(row)

    def _navegar_origem(self, campo: QLineEdit) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar arquivo de origem")
        if not caminho:
            caminho = QFileDialog.getExistingDirectory(self, "Selecionar pasta de origem")
        if caminho:
            campo.setText(caminho)

    def _remover_linha(self, row: QWidget) -> None:
        if row in self._linhas:
            self._linhas.remove(row)
        row.setParent(None)
        row.deleteLater()

    def valores(self) -> list[dict]:
        resultado = []
        for row in self._linhas:
            campos = row.findChildren(QLineEdit)
            if len(campos) >= 2:
                origem  = campos[0].text().strip()
                destino = campos[1].text().strip()
                if origem:
                    resultado.append({"origem": origem, "destino": destino})
        return resultado

    def set_valores(self, itens: list[dict]) -> None:
        for row in list(self._linhas):
            row.setParent(None)
            row.deleteLater()
        self._linhas.clear()
        for item in itens:
            self._adicionar_linha(item.get("origem", ""), item.get("destino", ""))


# ══════════════════════════════════════════════════════════════════════
# Widget principal
# ══════════════════════════════════════════════════════════════════════

class ExecutavelExplorer(QWidget):
    """
    Painel visual para executavel.json — formulário + terminal de build embutido.

    Abre no terminal_tabs (painel inferior) quando o arquivo é ativado.
    Fluxo: editar campos → Salvar → ▶ Criar exe → terminal mostra output.
    """

    def __init__(self, caminho: str, parent=None, painel_executavel=None):
        super().__init__(parent)
        self._caminho        = caminho
        self._painel_executavel = painel_executavel
        self._salvando       = False
        self._ultimo_mtime   = 0.0
        self._config_auto: dict = {}   # campos auto-gerados preservados ao salvar

        # threads de build
        self._thread_pip:  object | None = None
        self._thread_spec: object | None = None
        self._thread_pi:   object | None = None
        self._thread_release: object | None = None
        self._python_venv_build: str | None = None
        self._config_build: dict | None = None

        # modo do painel: "executavel" (build local) ou "release" (GitHub) —
        # lido do JSON a cada _carregar(), controla o botão principal.
        self._modo: str = "executavel"
        self._url_repo_github: str | None = None
        self._lbl_titulo: QLabel | None = None

        # painéis de texto (coluna esquerda)
        self._txt_requirements: QPlainTextEdit | None = None
        self._txt_arvore:       QPlainTextEdit | None = None

        # widgets de formulário
        self._chk_onefile:   QCheckBox  | None = None
        self._chk_console:   QCheckBox  | None = None
        self._lista_reqs:         _ListaStrings | None = None
        self._lista_extras:       _ListaPares   | None = None
        self._lista_hidden:       _ListaStrings | None = None
        self._lista_collect_sub:  _ListaStrings | None = None

        # widgets de build
        self._btn_build:          QPushButton    | None = None
        self._btn_stop:           QPushButton    | None = None
        self._lbl_build_status:   QLabel         | None = None
        self._terminal_output:    QPlainTextEdit | None = None
        self._frame_terminal:     QWidget        | None = None

        self._construir_ui()
        self._carregar()
        self._aplicar_tema()
        self._iniciar_watcher()

    # ──────────────────────────────────────────────────────────────────
    # Watcher — JSON → explorer
    # ──────────────────────────────────────────────────────────────────

    def _iniciar_watcher(self) -> None:
        self._watcher = QFileSystemWatcher()
        if os.path.isfile(self._caminho):
            self._watcher.addPath(self._caminho)
        self._watcher.fileChanged.connect(self._ao_arquivo_alterado)
        self._timer_reload = QTimer()
        self._timer_reload.setSingleShot(True)
        self._timer_reload.setInterval(700)
        self._timer_reload.timeout.connect(self._recarregar_externo)

    def _ao_arquivo_alterado(self, _: str) -> None:
        if self._salvando:
            return
        if self._caminho not in self._watcher.files():
            self._watcher.addPath(self._caminho)
        self._timer_reload.start()

    def _recarregar_externo(self) -> None:
        if self._salvando:
            return
        self._carregar()
        self._notificar("↺  Recarregado (arquivo alterado no editor)", cor="#4a90d9", duracao=3000)

    def _recarregar_se_necessario(self) -> None:
        """Chamado por main_window ao focar a aba deste explorer."""
        try:
            mtime = os.path.getmtime(self._caminho) if os.path.isfile(self._caminho) else 0.0
        except OSError:
            return
        if mtime > self._ultimo_mtime + 0.5:
            self._carregar()

    # ──────────────────────────────────────────────────────────────────
    # UI estática
    # ──────────────────────────────────────────────────────────────────

    def _construir_ui(self) -> None:
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ── Cabeçalho ─────────────────────────────────────────────────
        cab = QWidget()
        cab.setFixedHeight(36)
        lay_cab = QHBoxLayout(cab)
        lay_cab.setContentsMargins(12, 0, 10, 0)
        lay_cab.setSpacing(8)

        self._lbl_titulo = QLabel("⚙  executavel.json")
        self._lbl_titulo.setStyleSheet(
            "font-size:12px; font-weight:bold; font-family:Consolas; color:#e0e0e0;"
        )
        lay_cab.addWidget(self._lbl_titulo)
        lay_cab.addStretch()

        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("font-size:10px; color:#666;")
        lay_cab.addWidget(self._lbl_status)

        btn_auto = QPushButton("🔍 Auto-detectar")
        btn_auto.setFixedHeight(24)
        btn_auto.setToolTip(
            "Analisa o projeto (requirements, imports, assets) e atualiza\n"
            "os campos AUTO-GERADO do executavel.json automaticamente."
        )
        btn_auto.setStyleSheet(
            "QPushButton { background:#1a2a3a; color:#4a9fd9; border:none;"
            " padding:2px 10px; font-size:10px; border-radius:3px; }"
            "QPushButton:hover { background:#1e3a50; }"
        )
        btn_auto.clicked.connect(self._auto_detectar)
        lay_cab.addWidget(btn_auto)

        btn_salvar = QPushButton("⬆  Salvar")
        btn_salvar.setFixedHeight(24)
        btn_salvar.setStyleSheet(
            "QPushButton { background:#1a3a1a; color:#98c379; border:none;"
            " padding:2px 14px; font-size:10px; border-radius:3px; }"
            "QPushButton:hover { background:#264f28; }"
        )
        btn_salvar.clicked.connect(self._salvar)
        lay_cab.addWidget(btn_salvar)

        self._btn_build = QPushButton("▶  Criar executável")
        self._btn_build.setFixedHeight(24)
        self._btn_build.setToolTip(
            "Salva o JSON, instala PyInstaller na .venv do projeto,\n"
            "gera o .spec e roda o build. Output aparece no terminal abaixo."
        )
        self._btn_build.setStyleSheet(
            "QPushButton { background:#2a1a3a; color:#c792ea; border:none;"
            " padding:2px 14px; font-size:10px; border-radius:3px; font-weight:bold; }"
            "QPushButton:hover { background:#3d2a52; }"
            "QPushButton:disabled { background:#1a1a1a; color:#444; }"
        )
        self._btn_build.clicked.connect(self._ao_clicar_principal)
        lay_cab.addWidget(self._btn_build)

        self._btn_stop = QPushButton("■  Parar")
        self._btn_stop.setFixedHeight(24)
        self._btn_stop.setEnabled(False)
        self._btn_stop.setToolTip("Cancela o build em andamento (pip, .spec, PyInstaller ou git).")
        self._btn_stop.setStyleSheet(
            "QPushButton { background:#3a1a1a; color:#e08a8a; border:none;"
            " padding:2px 14px; font-size:10px; border-radius:3px; font-weight:bold; }"
            "QPushButton:hover { background:#522a2a; }"
            "QPushButton:disabled { background:#1a1a1a; color:#444; }"
        )
        self._btn_stop.clicked.connect(self._parar_build)
        lay_cab.addWidget(self._btn_stop)

        raiz.addWidget(cab)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        raiz.addWidget(sep)

        # ── Splitter vertical: conteúdo (cima) + terminal (baixo) ─────────
        splitter_v = QSplitter(Qt.Vertical)
        splitter_v.setHandleWidth(4)
        splitter_v.setStyleSheet("QSplitter::handle { background: #1a3a1a; }")

        # ── Splitter horizontal: árvore | formulário | requirements ─────
        splitter_h = QSplitter(Qt.Horizontal)
        splitter_h.setHandleWidth(4)
        splitter_h.setStyleSheet("QSplitter::handle { background: #1a3a1a; }")

        # ── Coluna 1 (esquerda): Árvore do projeto ───────────────────────
        col_arvore = QWidget()
        lay_arv = QVBoxLayout(col_arvore)
        lay_arv.setContentsMargins(0, 0, 0, 0)
        lay_arv.setSpacing(0)

        lbl_arv_hdr = QLabel("  ÁRVORE DO PROJETO")
        lbl_arv_hdr.setFixedHeight(22)
        lbl_arv_hdr.setStyleSheet(
            "background:#0a1a0a; color:#4a7a4a; font-size:9px; font-weight:bold;"
            " letter-spacing:1px; border-bottom:1px solid #1a3a1a;"
        )
        lay_arv.addWidget(lbl_arv_hdr)

        self._txt_arvore = QPlainTextEdit()
        self._txt_arvore.setReadOnly(True)
        self._txt_arvore.setFont(QFont("Consolas", 8))
        self._txt_arvore.setPlaceholderText("Árvore do projeto")
        self._txt_arvore.setStyleSheet(
            "QPlainTextEdit { background: #050d05; color: #aaaaaa; border: none; padding: 4px; }"
        )
        lay_arv.addWidget(self._txt_arvore, 1)
        splitter_h.addWidget(col_arvore)

        # ── Coluna 2 (centro): Formulário scrollável ─────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._corpo = QWidget()
        self._lay_corpo = QVBoxLayout(self._corpo)
        self._lay_corpo.setContentsMargins(14, 12, 14, 20)
        self._lay_corpo.setSpacing(10)
        scroll.setWidget(self._corpo)
        splitter_h.addWidget(scroll)

        # ── Coluna 3 (direita): Requirements + status ────────────────────
        col_reqs = QWidget()
        lay_reqs = QVBoxLayout(col_reqs)
        lay_reqs.setContentsMargins(0, 0, 0, 0)
        lay_reqs.setSpacing(0)

        lbl_reqs_hdr = QLabel("  DEPENDÊNCIAS (pip freeze)")
        lbl_reqs_hdr.setFixedHeight(22)
        lbl_reqs_hdr.setStyleSheet(
            "background:#0a1a0a; color:#4a7a4a; font-size:9px; font-weight:bold;"
            " letter-spacing:1px; border-bottom:1px solid #1a3a1a;"
        )
        lay_reqs.addWidget(lbl_reqs_hdr)

        self._txt_requirements = QPlainTextEdit()
        self._txt_requirements.setReadOnly(True)
        self._txt_requirements.setFont(QFont("Consolas", 8))
        self._txt_requirements.setPlaceholderText(
            "requirements.txt ainda não gerado\n\n"
            "Clique  🔍 Auto-detectar  para\n"
            "rodar pip freeze e preencher."
        )
        self._txt_requirements.setStyleSheet(
            "QPlainTextEdit { background: #050d05; color: #98c379; border: none; padding: 4px; }"
        )
        lay_reqs.addWidget(self._txt_requirements, 1)

        lbl_reqs_rodape = QLabel("  gerado por pip freeze da .venv")
        lbl_reqs_rodape.setFixedHeight(18)
        lbl_reqs_rodape.setStyleSheet(
            "font-size:8px; color:#2a4a2a; background:#050d05;"
            " border-top:1px solid #0a1f0a;"
        )
        lay_reqs.addWidget(lbl_reqs_rodape)
        splitter_h.addWidget(col_reqs)

        # proporção: árvore 200 | form 500 | requirements 220
        splitter_h.setSizes([200, 500, 220])

        splitter_v.addWidget(splitter_h)

        # Terminal de build (oculto inicialmente)
        self._frame_terminal = QWidget()
        self._frame_terminal.setVisible(False)
        lay_term = QVBoxLayout(self._frame_terminal)
        lay_term.setContentsMargins(0, 0, 0, 0)
        lay_term.setSpacing(0)

        term_header = QWidget()
        term_header.setFixedHeight(26)
        term_header.setStyleSheet("background: #0a1a0a; border-top: 1px solid #1a3a1a;")
        lay_th = QHBoxLayout(term_header)
        lay_th.setContentsMargins(10, 0, 6, 0)
        lay_th.setSpacing(8)
        self._lbl_build_status = QLabel("▶  Build")
        self._lbl_build_status.setStyleSheet(
            "font-size:10px; color:#888; font-family:Consolas; background:transparent;"
        )
        lay_th.addWidget(self._lbl_build_status)
        lay_th.addStretch()

        _estilo_btn_link = (
            "QPushButton { background:#0a1a0a; color:#6fae6f; border:1px solid #1a3a1a;"
            " padding:2px 8px; font-size:9px; border-radius:3px; }"
            "QPushButton:hover { background:#1a3a1a; color:#98e698; }"
            "QPushButton:disabled { color:#333; border-color:#1a1a1a; }"
        )
        self._btn_ver_actions = QPushButton("🔗 Ver Actions")
        self._btn_ver_actions.setFixedHeight(20)
        self._btn_ver_actions.setCursor(Qt.PointingHandCursor)
        self._btn_ver_actions.setStyleSheet(_estilo_btn_link)
        self._btn_ver_actions.setToolTip("Abre a aba Actions do repositório — onde o .exe está sendo fabricado.")
        self._btn_ver_actions.setVisible(False)
        self._btn_ver_actions.clicked.connect(
            lambda: self._abrir_link_github("actions")
        )
        lay_th.addWidget(self._btn_ver_actions)

        self._btn_ver_releases = QPushButton("📦 Ver Releases")
        self._btn_ver_releases.setFixedHeight(20)
        self._btn_ver_releases.setCursor(Qt.PointingHandCursor)
        self._btn_ver_releases.setStyleSheet(_estilo_btn_link)
        self._btn_ver_releases.setToolTip("Abre a aba Releases do repositório — onde fica o .exe pronto pra baixar/enviar.")
        self._btn_ver_releases.setVisible(False)
        self._btn_ver_releases.clicked.connect(
            lambda: self._abrir_link_github("releases")
        )
        lay_th.addWidget(self._btn_ver_releases)

        btn_fechar_term = QPushButton("✕")
        btn_fechar_term.setFixedSize(18, 18)
        btn_fechar_term.setCursor(Qt.PointingHandCursor)
        btn_fechar_term.setStyleSheet(
            "QPushButton { background:transparent; border:none; color:#444; font-size:10px; }"
            "QPushButton:hover { color:#e05252; }"
        )
        btn_fechar_term.setToolTip("Fechar terminal de build")
        btn_fechar_term.clicked.connect(
            lambda: self._frame_terminal.setVisible(False)
        )
        lay_th.addWidget(btn_fechar_term)
        lay_term.addWidget(term_header)

        self._terminal_output = QPlainTextEdit()
        self._terminal_output.setReadOnly(True)
        self._terminal_output.setFont(QFont("Consolas", 8))
        self._terminal_output.setStyleSheet(
            "QPlainTextEdit { background: #000000; color: #98c379; border: none;"
            " padding: 4px; }"
        )
        lay_term.addWidget(self._terminal_output, 1)
        splitter_v.addWidget(self._frame_terminal)

        # proporção inicial: conteúdo 400, terminal 150
        splitter_v.setSizes([400, 150])
        raiz.addWidget(splitter_v, 1)

        # Rodapé
        rodape = QLabel(
            "Revise os campos e clique em 'Salvar' antes de '▶ Criar executável'."
        )
        rodape.setFixedHeight(20)
        rodape.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        rodape.setStyleSheet("font-size:9px; color:#444; padding-right:8px;")
        raiz.addWidget(rodape)

    # ──────────────────────────────────────────────────────────────────
    # Construção dinâmica dos campos
    # ──────────────────────────────────────────────────────────────────

    def _limpar_corpo(self) -> None:
        while self._lay_corpo.count():
            item = self._lay_corpo.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._chk_onefile        = None
        self._chk_console        = None
        self._lista_reqs         = None
        self._lista_extras       = None
        self._lista_hidden       = None
        self._lista_collect_sub  = None

    def _construir_campos(self, dados: dict) -> None:
        self._limpar_corpo()

        # salva apenas os campos auto-gerados que NÃO são editáveis no formulário
        self._config_auto = {
            k: dados.get(k, [])
            for k in ("dependencias", "add_data", "collect_all")
        }

        # ── Build ──────────────────────────────────────────────────────
        self._lay_corpo.addWidget(self._bloco_titulo("BUILD"))

        row_chk = QWidget()
        lay_chk = QHBoxLayout(row_chk)
        lay_chk.setContentsMargins(0, 0, 0, 0)
        lay_chk.setSpacing(24)
        _estilo_checkbox = (
            "QCheckBox { color: #c8c8c8; background: transparent; font-size: 10px; }"
            "QCheckBox::indicator { width: 13px; height: 13px;"
            " border: 1px solid #4a7a4a; border-radius: 2px; background: #0a140a; }"
            "QCheckBox::indicator:hover { border-color: #6fae6f; }"
            "QCheckBox::indicator:checked { background: #4ec994; border-color: #4ec994; }"
        )

        self._chk_onefile = QCheckBox("Um único arquivo (--onefile)")
        self._chk_onefile.setChecked(bool(dados.get("onefile", False)))
        self._chk_onefile.setStyleSheet(_estilo_checkbox)
        self._chk_onefile.setToolTip(
            "Marcado → --onefile (1 .exe, mais lento pra iniciar)\n"
            "Desmarcado → --onedir (pasta dist/<nome>/, mais rápido)"
        )
        self._chk_console = QCheckBox("Mostrar console")
        self._chk_console.setChecked(bool(dados.get("console", False)))
        self._chk_console.setStyleSheet(_estilo_checkbox)
        self._chk_console.setToolTip(
            "Marcado → janela do console visível (depuração)\n"
            "Desmarcado → sem console (app gráfico)"
        )
        lay_chk.addWidget(self._chk_onefile)
        lay_chk.addWidget(self._chk_console)
        lay_chk.addStretch()
        self._lay_corpo.addWidget(row_chk)

        self._lay_corpo.addWidget(self._separador())

        # ── AUTO-GERADO — só leitura (dependencias + add_data) ───────────
        self._lay_corpo.addWidget(self._bloco_titulo("AUTO-GERADO"))
        lbl_auto_info = QLabel(
            "Atualizado automaticamente pelo 🔍 Auto-detectar."
        )
        lbl_auto_info.setStyleSheet("font-size:9px; color:#4a5a4a;")
        self._lay_corpo.addWidget(lbl_auto_info)

        for rotulo, chave in [
            ("Dependências:", "dependencias"),
            ("add_data:",     "add_data"),
        ]:
            itens = dados.get(chave, [])
            n     = len(itens)
            if n == 0:
                resumo = "—  nenhum (clique Auto-detectar)"
            elif chave == "add_data":
                origens = [i.get("origem", "?") if isinstance(i, dict) else str(i)
                           for i in itens[:3]]
                sufixo  = f"  (+{n-3} mais)" if n > 3 else ""
                resumo  = ",  ".join(origens) + sufixo
            else:
                nomes   = itens[:5]
                sufixo  = f"  (+{n-5} mais)" if n > 5 else ""
                resumo  = ",  ".join(str(x) for x in nomes) + sufixo

            lbl_val = QLabel(resumo)
            lbl_val.setStyleSheet("font-size:9px; color:#607060; font-family:Consolas;")
            lbl_val.setWordWrap(True)
            self._lay_corpo.addWidget(self._row_campo(rotulo, lbl_val))

        self._lay_corpo.addWidget(self._separador())

        # ── Hidden Imports (editável) ─────────────────────────────────
        self._lay_corpo.addWidget(self._bloco_titulo("HIDDEN IMPORTS"))
        lbl_hi_info = QLabel(
            "Módulos que o PyInstaller não detecta automaticamente.\n"
            "Preenchido pelo Auto-detectar — edite se precisar ajustar."
        )
        lbl_hi_info.setStyleSheet("font-size:9px; color:#555;")
        self._lay_corpo.addWidget(lbl_hi_info)
        self._lista_hidden = _ListaStrings(
            dados.get("hidden_imports", []),
            placeholder="Ex: PIL",
        )
        self._lay_corpo.addWidget(self._lista_hidden)

        self._lay_corpo.addWidget(self._separador())

        # ── Collect Submodules (editável) ─────────────────────────────
        self._lay_corpo.addWidget(self._bloco_titulo("COLLECT SUBMODULES"))
        lbl_cs_info = QLabel(
            "Pacotes locais do projeto incluídos completos no bundle.\n"
            "Preenchido pelo Auto-detectar — edite se precisar ajustar."
        )
        lbl_cs_info.setStyleSheet("font-size:9px; color:#555;")
        self._lay_corpo.addWidget(lbl_cs_info)
        self._lista_collect_sub = _ListaStrings(
            dados.get("collect_submodules", []),
            placeholder="Ex: _MEU_MODULO_",
        )
        self._lay_corpo.addWidget(self._lista_collect_sub)

        self._lay_corpo.addWidget(self._separador())

        # ── Dependências extras (manual) ──────────────────────────────
        self._lay_corpo.addWidget(self._bloco_titulo("DEPENDÊNCIAS EXTRAS"))
        lbl_req_info = QLabel(
            "Pacotes que o scanner de imports não detecta automaticamente\n"
            "(ex: plugins carregados dinamicamente, extensões do PySide6)."
        )
        lbl_req_info.setStyleSheet("font-size:9px; color:#555;")
        self._lay_corpo.addWidget(lbl_req_info)
        self._lista_reqs = _ListaStrings(
            dados.get("requirements_extra", []),
            placeholder="Ex: sounddevice",
        )
        self._lay_corpo.addWidget(self._lista_reqs)

        self._lay_corpo.addWidget(self._separador())

        # ── Arquivos/Pastas extras (manual) ───────────────────────────
        self._lay_corpo.addWidget(self._bloco_titulo("ARQUIVOS / PASTAS EXTRAS"))
        lbl_ext_info = QLabel(
            "Arquivos não detectados pelo Auto-detectar que o app usa em runtime.\n"
            "Origem: caminho relativo ao projeto. Destino: pasta dentro do bundle."
        )
        lbl_ext_info.setStyleSheet("font-size:9px; color:#555;")
        self._lay_corpo.addWidget(lbl_ext_info)
        self._lista_extras = _ListaPares(dados.get("arquivos_extra", []))
        self._lay_corpo.addWidget(self._lista_extras)

        self._lay_corpo.addStretch()

    # ──────────────────────────────────────────────────────────────────
    # Helpers de UI
    # ──────────────────────────────────────────────────────────────────

    def _bloco_titulo(self, texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setStyleSheet(
            "font-size:9px; font-weight:700; color:#4a5a4a; letter-spacing:1.6px;"
        )
        return lbl

    def _separador(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setFixedHeight(1)
        f.setStyleSheet("color:#1a3a1a;")
        return f

    def _row_campo(self, rotulo: str, widget: QWidget) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lbl = QLabel(rotulo)
        lbl.setFixedWidth(120)
        lbl.setStyleSheet("font-size:10px; color:#aaa;")
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(lbl)
        lay.addWidget(widget, 1)
        return row

    def _raiz_projeto(self) -> str:
        """Raiz do projeto: 3 níveis acima de executavel.json
        (<proj>/.hein/executavel/executavel.json)."""
        return os.path.dirname(os.path.dirname(os.path.dirname(self._caminho)))

    def _pasta_exe(self) -> str:
        """Pasta do executável: <proj>/.hein/executavel/ — pasta autossuficiente
        que contém executavel.json, requirements.txt gerado e arvore.txt."""
        return os.path.dirname(self._caminho)

    # ──────────────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────────────
    # Auto-detectar
    # ──────────────────────────────────────────────────────────────────

    def _auto_detectar(self) -> None:
        """Analisa o projeto e salva campos auto-gerados no JSON + atualiza UI."""
        raiz = self._raiz_projeto()
        if not os.path.isdir(raiz):
            self._notificar("✘ Raiz do projeto não encontrada.", cor="#e05252", duracao=4000)
            return
        try:
            from _EXECUTAVEL_.arvore import gerar_arvore
            from _EXECUTAVEL_.requirements import gerar_requirements
            from _EXECUTAVEL_.exec_local.analise import analisar_projeto
            from _EXECUTAVEL_.config import salvar_campos_auto
            from _EXECUTAVEL_.venv_projeto import achar_python_projeto

            reqs_extra  = self._lista_reqs.valores() if self._lista_reqs else []
            padroes_git = _ler_gitignore(raiz)
            python_venv = self._python_venv_build or achar_python_projeto(raiz)

            # Pipeline: árvore → requirements → análise → JSON
            # FreezeGuard cobre o bloco inteiro: gerar_requirements roda `pip freeze`
            # (~5-10s síncronos na main thread) e trava a UI sem aviso.
            from _UTILITARIOS_.freeze_guard import FreezeGuard
            with FreezeGuard(self, "Analisando projeto…"):
                gerar_arvore(raiz, padroes_git)
                gerar_requirements(python_venv, raiz)
                campos_auto = analisar_projeto(
                    raiz,
                    reqs_extra,
                    python_venv=python_venv,
                    padroes_ignorar=padroes_git,
                )
                salvar_campos_auto(raiz, campos_auto)
            # força recarga do formulário com novos dados (também regrava arvore.txt)
            self._carregar()
            n_deps   = len(campos_auto.get("dependencias", []))
            n_assets = len(campos_auto.get("add_data", []))
            n_hidden = len(campos_auto.get("hidden_imports", []))
            self._notificar(
                f"✔  Auto-detectado: {n_deps} dep(s), {n_assets} asset(s), "
                f"{n_hidden} hidden_import(s). Confira e salve.",
                cor="#4a9fd9", duracao=7000
            )
        except Exception as e:
            log.erro(_ARQ, "_auto_detectar", str(e))
            self._notificar(f"✘ Erro na auto-detecção: {e}", cor="#e05252", duracao=6000)

    # ──────────────────────────────────────────────────────────────────
    # Carregamento / Salvamento
    # ──────────────────────────────────────────────────────────────────

    def _carregar(self) -> None:
        dados = _carregar_json(self._caminho)
        self._ultimo_mtime = (
            os.path.getmtime(self._caminho) if os.path.isfile(self._caminho) else 0.0
        )
        self._modo = dados.get("modo", "executavel")
        self._construir_campos(dados)
        self._atualizar_botao_principal()
        self._atualizar_botoes_link_github()
        self._aplicar_tema()
        self._popular_paineis_esquerda()
        self._notificar("Carregado.", cor="#555", duracao=2000)

    def _atualizar_botao_principal(self) -> None:
        """Alterna o botão principal e o título conforme o 'modo' salvo no
        JSON (gerenciado pelo PainelExecutavel: 'Executável local' vs
        'Release pro GitHub' escrevem modos diferentes antes de abrir este
        explorer). Mesmo formulário/JSON pros dois — só muda a ação final."""
        if self._lbl_titulo is not None:
            self._lbl_titulo.setText(
                "🚀  executavel.json (release)" if self._modo == "release"
                else "⚙  executavel.json"
            )
        if self._btn_build is None:
            return
        if self._modo == "release":
            self._btn_build.setText("🚀  Enviar release")
            self._btn_build.setToolTip(
                "Salva o JSON, gera .github/workflows/release.yml, cria a tag\n"
                "da versão e dá git push — o GitHub Actions builda o .exe e\n"
                "publica o release. Output aparece no terminal abaixo."
            )
        else:
            self._btn_build.setText("▶  Criar executável")
            self._btn_build.setToolTip(
                "Salva o JSON, instala PyInstaller na .venv do projeto,\n"
                "gera o .spec e roda o build. Output aparece no terminal abaixo."
            )

    def _ao_clicar_principal(self) -> None:
        if self._modo == "release":
            self._iniciar_release()
        else:
            self._iniciar_build()

    def _abrir_link_github(self, aba: str) -> None:
        """aba: 'actions' ou 'releases'. Abre no navegador padrão."""
        if not self._url_repo_github:
            self._url_repo_github = _url_repositorio_github(self._raiz_projeto())
        if not self._url_repo_github:
            from _UTILITARIOS_.hein_pou_pap import HeinPopup
            HeinPopup.aviso(
                "Repositório não encontrado",
                "Não consegui identificar a URL do repositório remoto (origin).\n"
                "Conecte o projeto pela aba Git primeiro.",
                parent=self,
            )
            return
        QDesktopServices.openUrl(QUrl(f"{self._url_repo_github}/{aba}"))

    def _atualizar_botoes_link_github(self) -> None:
        """Mostra os atalhos 'Ver Actions' / 'Ver Releases' só no modo release
        (não fazem sentido pro build local, que não sobe nada pro GitHub)."""
        mostrar = (self._modo == "release")
        self._btn_ver_actions.setVisible(mostrar)
        self._btn_ver_releases.setVisible(mostrar)

    def _popular_paineis_esquerda(self) -> None:
        """Popula requirements.txt e árvore na coluna esquerda.

        Lê ambos os arquivos da pasta do executável (.hein/executavel/).
        NÃO gera a árvore em disco — só lê o arvore.txt se já existir.
        A geração da árvore só acontece via "🔍 Auto-detectar" ou botões de build.
        """
        pasta = self._pasta_exe()

        # ── requirements.txt (da pasta executável) ───────────────────────
        if self._txt_requirements is not None:
            req_path = os.path.join(pasta, "requirements.txt")
            if os.path.isfile(req_path):
                try:
                    with open(req_path, "r", encoding="utf-8") as f:
                        self._txt_requirements.setPlainText(f.read())
                except Exception:
                    self._txt_requirements.setPlainText(
                        "(erro ao ler requirements.txt)")
            else:
                self._txt_requirements.setPlainText(
                    "# requirements.txt ainda não gerado\n"
                    "# Clique  🔍 Auto-detectar  para criar.")

        # ── árvore (lê o arquivo que acabou de ser gravado) ──────────────
        if self._txt_arvore is not None:
            arv_path = os.path.join(pasta, "arvore.txt")
            if os.path.isfile(arv_path):
                try:
                    with open(arv_path, "r", encoding="utf-8") as f:
                        self._txt_arvore.setPlainText(f.read())
                except Exception:
                    self._txt_arvore.setPlainText("(erro ao ler arvore.txt)")
            else:
                self._txt_arvore.setPlainText("(raiz do projeto não encontrada)")

    def _salvar(self) -> None:
        dados = self._ler_controles()
        if dados is None:
            return
        self._salvando = True
        try:
            ok = _salvar_json(self._caminho, dados)
        finally:
            QTimer.singleShot(1200, lambda: setattr(self, "_salvando", False))
        if ok:
            self._ultimo_mtime = (
                os.path.getmtime(self._caminho) if os.path.isfile(self._caminho) else 0.0
            )
            # mantém requirements.txt em sincronia via pip freeze
            try:
                from _EXECUTAVEL_.requirements import gerar_requirements
                from _EXECUTAVEL_.venv_projeto import achar_python_projeto
                raiz_s = self._raiz_projeto()
                python_venv_s = self._python_venv_build or achar_python_projeto(raiz_s)
                gerar_requirements(python_venv_s, raiz_s)
            except Exception as _e:
                log.aviso(_ARQ, "_salvar", f"gerar_requirements falhou: {_e}")
            self._notificar("✔  Salvo.", cor="#4ec994", duracao=3000)
            log.ok(_ARQ, "_salvar", f"executavel.json salvo: {self._caminho}")
        else:
            self._notificar("✘  Erro ao salvar.", cor="#e05252", duracao=5000)

    def _ler_controles(self) -> dict | None:
        """Lê todos os campos editáveis + preserva nome/versao/icone do JSON (gerenciados
        pelo PainelExecutavel) e campos auto-gerados."""
        try:
            # preserva nome/versao/icone que são gerenciados pelo painel esquerdo
            dados_existentes = _carregar_json(self._caminho)
            dados = {
                "nome":               dados_existentes.get("nome", ""),
                "versao":             dados_existentes.get("versao", "0.1.0"),
                "icone":              dados_existentes.get("icone", ""),
                "ponto_entrada":      dados_existentes.get("ponto_entrada", "main.py"),
                "modo":               dados_existentes.get("modo", "executavel"),
                "onefile":            (self._chk_onefile.isChecked()           if self._chk_onefile       else False),
                "console":            (self._chk_console.isChecked()           if self._chk_console      else False),
                "hidden_imports":     (self._lista_hidden.valores()            if self._lista_hidden      else []),
                "collect_submodules": (self._lista_collect_sub.valores()       if self._lista_collect_sub else []),
                "requirements_extra": (self._lista_reqs.valores()              if self._lista_reqs        else []),
                "arquivos_extra":     (self._lista_extras.valores()            if self._lista_extras      else []),
            }
            # preserva campos auto-gerados somente leitura (dependencias, add_data, collect_all)
            dados.update(self._config_auto)
            return dados
        except Exception as e:
            log.erro(_ARQ, "_ler_controles", str(e))
            return None

    # ──────────────────────────────────────────────────────────────────
    # Build pipeline
    # ──────────────────────────────────────────────────────────────────

    def _escrever_build(self, texto: str) -> None:
        """Escreve linha no terminal de build embutido."""
        if self._terminal_output is None:
            return
        try:
            cursor = self._terminal_output.textCursor()
            from PySide6.QtGui import QTextCursor
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(texto + "\n")
            self._terminal_output.setTextCursor(cursor)
            self._terminal_output.verticalScrollBar().setValue(
                self._terminal_output.verticalScrollBar().maximum()
            )
        except RuntimeError:
            pass

    def _mostrar_terminal_build(self) -> None:
        if self._frame_terminal:
            if self._terminal_output:
                self._terminal_output.clear()
            self._frame_terminal.setVisible(True)

    def _set_status_build(self, msg: str, cor: str = "#888") -> None:
        if self._lbl_build_status:
            self._lbl_build_status.setText(msg)
            self._lbl_build_status.setStyleSheet(
                f"font-size:10px; color:{cor}; font-family:Consolas; background:transparent;"
            )

    def _travar_btn_build(self, travado: bool) -> None:
        if self._btn_build:
            self._btn_build.setEnabled(not travado)
        if self._btn_stop:
            self._btn_stop.setEnabled(travado)

    def _parar_build(self) -> None:
        """Botão ■ Parar: cancela a etapa de build ativa (pip ou PyInstaller).
        A etapa de geração do .spec é rápida e local — não roda subprocesso
        cancelável, então segue até concluir mesmo com o Parar pressionado."""
        cancelado = False
        for atributo in ("_thread_pip", "_thread_pi", "_thread_release"):
            thread = getattr(self, atributo, None)
            if thread is not None:
                thread.parar()
                cancelado = True
        if cancelado:
            self._escrever_build("\n■  Build cancelado pelo usuário")
            self._set_status_build("■  Build cancelado pelo usuário", "#e08a8a")
            log.aviso(_ARQ, "_parar_build", "build cancelado pelo usuário")
        self._travar_btn_build(False)

    def _finalizar_thread(self, atributo: str) -> None:
        thread = getattr(self, atributo, None)
        if thread is not None:
            try:
                thread.disconnect()
            except (RuntimeError, TypeError):
                pass
            thread.deleteLater()
            setattr(self, atributo, None)

    def _iniciar_build(self) -> None:
        """Botão ▶ Criar executável: salva → valida → inicia pipeline."""
        from _EXECUTAVEL_.venv_projeto import achar_python_projeto
        from _UTILITARIOS_.hein_pou_pap import HeinPopup

        raiz = self._raiz_projeto()

        # Valida nome (lido do JSON — gerenciado pelo PainelExecutavel)
        nome = _carregar_json(self._caminho).get("nome", "").strip()
        if not nome:
            HeinPopup.aviso("Campo obrigatório",
                            "Preencha o campo 'Nome' no painel esquerdo (aba Exe) "
                            "antes de criar o executável.",
                            parent=self)
            return

        # Verifica .venv
        python_venv = achar_python_projeto(raiz)
        if not python_venv:
            HeinPopup.aviso(
                "Sem ambiente virtual",
                "Nenhuma .venv encontrada no projeto.\n"
                "Crie o projeto pela hein IDE (ou rode 'python -m venv .venv' na raiz) "
                "e tente novamente.",
                parent=self,
            )
            return

        # Salva formulário primeiro
        self._salvar()

        self._python_venv_build = python_venv
        from _EXECUTAVEL_.config import ler_config_executavel
        self._config_build = ler_config_executavel(raiz)

        self._travar_btn_build(True)
        self._mostrar_terminal_build()
        nome_versao = f"{self._config_build.get('nome')} {self._config_build.get('versao')}"
        self._set_status_build(f"▶  Build: {nome_versao}", "#c792ea")
        self._escrever_build(f"=== Build: {nome_versao} ===")
        self._escrever_build(f"Python: {python_venv}\n")

        # Etapa 1: pip install pyinstaller + pyinstaller-versionfile
        self._set_status_build("Instalando PyInstaller...", "#c792ea")
        from _EXECUTAVEL_.processo import ProcessoThread
        self._thread_pip = ProcessoThread(
            [python_venv, "-m", "pip", "install", "-q",
             "pyinstaller", "pyinstaller-versionfile"],
            raiz, self,
        )
        self._thread_pip.linha.connect(self._escrever_build)
        self._thread_pip.concluido.connect(self._ao_pip_concluido)
        self._thread_pip.start()
        log.info(_ARQ, "_iniciar_build", "pip install iniciado")

    def _ao_pip_concluido(self, codigo: int) -> None:
        self._finalizar_thread("_thread_pip")
        if codigo != 0:
            self._travar_btn_build(False)
            self._set_status_build(f"✘  pip falhou (código {codigo})", "#e05252")
            self._escrever_build(f"\n✘ Falha ao instalar PyInstaller (código {codigo}).")
            log.erro(_ARQ, "_ao_pip_concluido", f"código {codigo}")
            return

        self._escrever_build("\nPyInstaller pronto. Gerando .spec...\n")
        self._set_status_build("Gerando .spec...", "#c792ea")

        # Etapa 2: gerar .spec + versionfile
        from _EXECUTAVEL_.exec_local.gerador_spec import GerarSpecThread
        self._thread_spec = GerarSpecThread(
            self._python_venv_build,
            self._raiz_projeto(),
            self._config_build,
            self._config_build.get("hidden_imports", []),
            self,
        )
        self._thread_spec.concluido.connect(self._ao_spec_gerado)
        self._thread_spec.start()
        log.info(_ARQ, "_ao_pip_concluido", "GerarSpecThread iniciada")

    def _ao_spec_gerado(self, caminho_spec: str, erro: str) -> None:
        self._finalizar_thread("_thread_spec")
        if erro:
            self._travar_btn_build(False)
            self._set_status_build("✘  Falha ao gerar .spec", "#e05252")
            self._escrever_build(f"\n✘ Falha ao gerar .spec:\n{erro}")
            log.erro(_ARQ, "_ao_spec_gerado", erro)
            return

        self._escrever_build(f".spec gerado: {os.path.basename(caminho_spec)}")
        self._escrever_build("Rodando PyInstaller...\n")
        self._set_status_build("Rodando PyInstaller...", "#c792ea")

        raiz = self._raiz_projeto()
        dist = os.path.join(raiz, "dist")
        work = os.path.join(raiz, ".hein", "executavel", "build", "work")

        from _EXECUTAVEL_.processo import ProcessoThread
        self._thread_pi = ProcessoThread(
            [self._python_venv_build, "-m", "PyInstaller", caminho_spec,
             "--noconfirm", "--distpath", dist, "--workpath", work],
            raiz, self,
        )
        self._thread_pi.linha.connect(self._escrever_build)
        self._thread_pi.concluido.connect(self._ao_pyinstaller_concluido)
        self._thread_pi.start()
        log.info(_ARQ, "_ao_spec_gerado", "PyInstaller iniciado")

    def _ao_pyinstaller_concluido(self, codigo: int) -> None:
        self._finalizar_thread("_thread_pi")
        self._travar_btn_build(False)
        nome    = self._config_build.get("nome", "app") if self._config_build else "app"
        onefile = self._config_build.get("onefile") if self._config_build else False
        destino = os.path.join("dist", f"{nome}.exe" if onefile else nome)
        if codigo == 0:
            self._set_status_build(f"✔  {destino}", "#4ec994")
            self._escrever_build(f"\n✔ Executável gerado em {destino}")
            log.ok(_ARQ, "_ao_pyinstaller_concluido", f"build ok: {destino}")
            # build concluído — nenhuma ação extra no painel esquerdo
        else:
            self._set_status_build(f"✘  Build falhou (código {codigo})", "#e05252")
            self._escrever_build(f"\n✘ Build falhou (código {codigo}).")
            log.erro(_ARQ, "_ao_pyinstaller_concluido", f"código {codigo}")
        self._config_build = None

    # ──────────────────────────────────────────────────────────────────
    # Release pipeline (GitHub) — mesmo JSON/formulário do build local,
    # só troca o que o botão principal faz quando modo == "release".
    # ──────────────────────────────────────────────────────────────────

    def _iniciar_release(self) -> None:
        """Gera workflow/build e publica sem gravar credenciais no remoto."""
        from _UTILITARIOS_.hein_pou_pap import HeinPopup
        from _PAINEL_ESQUERDO_.Git.git_gerente import GerenciadorGit
        from _EXECUTAVEL_.venv_projeto import achar_python_projeto

        raiz = self._raiz_projeto()
        dados_iniciais = _carregar_json(self._caminho)
        nome = str(dados_iniciais.get("nome", "")).strip()
        if not nome:
            HeinPopup.aviso(
                "Campo obrigatório", "Preencha o nome na aba Executável.", parent=self
            )
            return
        versao = str(dados_iniciais.get("versao") or "0.1.0").strip()
        if not re.fullmatch(r"v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", versao):
            HeinPopup.aviso("Versão inválida", "Use uma versão como 1.2.3.", parent=self)
            return
        python_venv = achar_python_projeto(raiz)
        if not python_venv:
            HeinPopup.aviso(
                "Sem ambiente virtual",
                "Crie a .venv do projeto antes de publicar o executável.",
                parent=self,
            )
            return
        if not GerenciadorGit.git_instalado():
            HeinPopup.aviso("Git não encontrado", "Instale o Git e tente novamente.", parent=self)
            return
        git = GerenciadorGit()
        if not git.tem_git(raiz):
            HeinPopup.aviso(
                "Sem repositório Git",
                "Conecte o projeto pela aba Git antes de publicar o release.",
                parent=self,
            )
            return

        self._salvar()
        config = _carregar_json(self._caminho)
        tag = versao if versao.lower().startswith("v") else f"v{versao}"
        try:
            from _UTILITARIOS_.versionamento import checar_regressao_versao
            from _UTILITARIOS_.hein_pou_pap import HeinPopup as _HeinPopup
            if checar_regressao_versao(raiz, tag):
                if not _HeinPopup.confirmar(
                    "Versão menor que a atual",
                    f"A versão <b>{tag}</b> é menor que a versão atual. Deseja continuar?",
                    informativo="A versão será sincronizada após o envio.",
                    parent=self,
                ):
                    return
        except Exception as exc:
            log.aviso(_ARQ, "_iniciar_release", f"Falha ao validar versão: {exc}")

        try:
            from _EXECUTAVEL_.release.gerador_workflow import gerar_workflow_release
            caminho_yml = gerar_workflow_release(raiz, config)
            req_rel = os.path.join(".hein", "executavel", "requirements.txt")
            if not os.path.isfile(os.path.join(raiz, req_rel)):
                from _EXECUTAVEL_.requirements import gerar_requirements
                gerar_requirements(python_venv, raiz)
        except Exception as exc:
            HeinPopup.aviso(
                "Erro ao preparar release",
                f"Não foi possível gerar os arquivos do build:\n{exc}",
                parent=self,
            )
            log.erro(_ARQ, "_iniciar_release", str(exc))
            return

        yml_rel = os.path.relpath(caminho_yml, raiz).replace(os.sep, "/")
        json_rel = os.path.relpath(self._caminho, raiz).replace(os.sep, "/")
        req_rel = ".hein/executavel/requirements.txt"
        build_ci_rel = ".hein/executavel/build_ci.py"
        branch = git.branch_atual(raiz) or "main"
        self._url_repo_github = _url_repositorio_github(raiz)
        self._atualizar_botoes_link_github()
        self._travar_btn_build(True)
        self._mostrar_terminal_build()
        self._set_status_build(f"🚀  Release: {nome} {tag}", "#4ec994")
        self._escrever_build(f"=== Release: {nome} {tag} ===")
        self._escrever_build(f"Branch: {branch}")
        self._escrever_build(f"Workflow gerado: {yml_rel}")
        self._escrever_build(
            "A autenticação será fornecida pela sessão da aba Git, sem expor o token."
        )

        from _EXECUTAVEL_.release.processo_release import ProcessoReleaseThread
        self._thread_release = ProcessoReleaseThread(
            raiz, tag, [yml_rel, req_rel, json_rel, build_ci_rel], self
        )
        self._thread_release.linha.connect(self._escrever_build)
        self._thread_release.concluido.connect(self._ao_release_concluido)
        self._thread_release.start()
        log.info(_ARQ, "_iniciar_release", f"release iniciado: {nome} {tag}")

    def _ao_release_concluido(self, sucesso: bool, mensagem: str) -> None:
        self._finalizar_thread("_thread_release")
        self._travar_btn_build(False)
        if not sucesso:
            self._set_status_build("✘  Release falhou", "#e05252")
            self._escrever_build(f"\n✘ {mensagem}")
            log.erro(_ARQ, "_ao_release_concluido", mensagem)
            return
        self._set_status_build("✔  Release enviado", "#4ec994")
        self._escrever_build(f"\n✔ {mensagem} Acompanhe o build na aba Actions do GitHub.")
        log.ok(_ARQ, "_ao_release_concluido", mensagem)
        try:
            from _UTILITARIOS_.versionamento import registrar_release
            dados = _carregar_json(self._caminho)
            registrar_release(
                self._raiz_projeto(),
                dados.get("versao", ""),
                f"Release {dados.get('nome', '')} publicado no GitHub.",
            )
        except Exception as exc:
            log.aviso(_ARQ, "_ao_release_concluido", f"Não foi possível sincronizar VERSION: {exc}")

    # ──────────────────────────────────────────────────────────────────
    # Tema / status
    # ──────────────────────────────────────────────────────────────────

    def _aplicar_tema(self) -> None:
        try:
            t = tema_global()
            fundo = t.cor("interface.fundo_painel", "#0f1f0f")
            texto = t.cor("interface.texto", "#c0c0c0")
            borda = t.cor("interface.borda", "#1a3a1a")
            self.setStyleSheet(
                f"QWidget {{ background: {fundo}; color: {texto}; }}"
                f"QLineEdit, QComboBox, QSpinBox {{"
                f"  background: #0a140a; color: {texto};"
                f"  border: 1px solid {borda}; border-radius: 3px;"
                f"  padding: 0 4px;"
                f"}}"
                f"QScrollArea {{ border: none; }}"
                f"QFrame[frameShape='4'] {{ background: {borda}; }}"
            )
        except Exception:
            pass

    def _notificar(self, msg: str, cor: str = "#888", duracao: int = 2000) -> None:
        if self._lbl_status:
            self._lbl_status.setText(msg)
            self._lbl_status.setStyleSheet(f"font-size:10px; color:{cor};")
            QTimer.singleShot(duracao, lambda: (
                self._lbl_status.setText("") if self._lbl_status else None
            ))
