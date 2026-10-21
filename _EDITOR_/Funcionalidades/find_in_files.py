# 📁 _EDITOR_/Funcionalidades/find_in_files.py
# -*- coding: utf-8 -*-
"""
Find in Files — pesquisa texto em todos os arquivos do projeto.
Nota: atalho gerenciado pelo atalhos.json (busca::BuscarNoProjeto → Ctrl+J).

Uso:
    from _EDITOR_.Funcionalidades.find_in_files import FindInFiles
    self._find_in_files = FindInFiles(self)          # no __init__ do CodeEditor

    # Em App_.py, para abrir:
    editor._find_in_files.abrir()

Sinal disponível para App_.py:
    editor._find_in_files.navegar_para(arquivo, linha)  → abre arquivo na linha
"""
import os
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QCheckBox, QSizePolicy
)
from _THREADS_.thread_segura import _ThreadSegura
from _THREADS_.diagnostico_workers import ensure_task, event
from PySide6.QtCore  import Qt, QObject, Signal, QThread, QTimer
from PySide6.QtGui   import QKeySequence, QShortcut, QColor
from _LOG_.log import log
_ARQ     = "find_in_files.py"
_IGNORAR = {".venv", "__pycache__", ".git", ".hein", "node_modules",
            ".mypy_cache", ".pytest_cache", "dist", "build"}

# ══════════════════════════════════════════════════════════════════════════════
# Worker — roda em thread separada para não travar a UI
# ══════════════════════════════════════════════════════════════════════════════

# Mantém referências a _WorkerBusca até finished — evita GC prematuro quando
# self._worker é substituído ou zerado antes de run() retornar (BUG-202807-12).
_threads_vivas_worker: set = set()

class _WorkerBusca(_ThreadSegura):
    resultado  = Signal(str, int, str)   # arquivo, linha, trecho
    concluido  = Signal(int)             # total de resultados

    def __init__(self, raiz: str, termo: str, regex: bool, case: bool):
        super().__init__()
        self._raiz  = raiz
        self._termo = termo
        self._regex = regex
        self._case  = case
        ensure_task(self, "FIND_FILES")

    def run(self):
        total = 0
        _task = ensure_task(self, "FIND_FILES")
        event("RUN_ENTER", "FIND_FILES", _task, obj=self)
        flags = 0 if self._case else re.IGNORECASE
        try:
            if self._regex:
                padrao = re.compile(self._termo, flags)
            else:
                padrao = re.compile(re.escape(self._termo), flags)
        except re.error as e:
            log.erro(_ARQ, "_WorkerBusca.run", "regex inválido", str(e))
            self.concluido.emit(0)
            event("RESULT_EMITTED", "FIND_FILES", _task, obj=self,
                  result_count=0, regex_error=True)
            event("RUN_EXIT", "FIND_FILES", _task, obj=self)
            return

        try:
            for raiz, pastas, arquivos in os.walk(self._raiz):
                pastas[:] = [p for p in pastas if p not in _IGNORAR]
                for nome_arq in arquivos:
                    if not nome_arq.endswith((".py", ".txt", ".json", ".md", ".yaml", ".toml", ".cfg", ".ini")):
                        continue
                    caminho = os.path.join(raiz, nome_arq)
                    try:
                        with open(caminho, encoding="utf-8", errors="replace") as f:
                            for i, linha in enumerate(f, 1):
                                if padrao.search(linha):
                                    trecho = linha.rstrip("\n").strip()
                                    self.resultado.emit(caminho, i, trecho)
                                    total += 1
                                    if total >= 2000:
                                        self.concluido.emit(total)
                                        event("RESULT_EMITTED", "FIND_FILES", _task,
                                              obj=self, result_count=total,
                                              limit_reached=True)
                                        return

                    except OSError:
                        pass

            self.concluido.emit(total)
            event("RESULT_EMITTED", "FIND_FILES", _task, obj=self,
                  result_count=total)
        except Exception as exc:
            event("ERROR", "FIND_FILES", _task, obj=self, error=str(exc))
            raise
        finally:
            event("RUN_EXIT", "FIND_FILES", _task,
                  obj=self, result_count=total)

# ══════════════════════════════════════════════════════════════════════════════
# Painel visual
# ══════════════════════════════════════════════════════════════════════════════

class _PainelFindInFiles(QWidget):
    navegar = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PainelFindInFiles")
        self._worker: _WorkerBusca | None = None
        self._montar_ui()
        self.hide()

    # ⚠️  função grande (91 linhas)
    def _montar_ui(self):
        self.setStyleSheet("""
            QWidget#PainelFindInFiles {
                background-color: #111;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(6)

        # ── Cabeçalho ────────────────────────────────────────────────
        cab = QHBoxLayout()
        self._lbl_titulo = QLabel("🔍 Buscar no Projeto")
        self._lbl_titulo.setStyleSheet("color: #ccc; font-weight: bold; font-size: 12px;")
        btn_fechar = QPushButton("✕")
        btn_fechar.setFixedSize(20, 20)
        btn_fechar.setStyleSheet(
            "QPushButton { background: transparent; color: #888; border: none; }"
            "QPushButton:hover { color: #fff; }"
        )
        btn_fechar.clicked.connect(self.fechar)
        cab.addWidget(self._lbl_titulo)
        cab.addStretch()
        cab.addWidget(btn_fechar)
        layout.addLayout(cab)

        # ── Barra de busca ────────────────────────────────────────────
        linha_busca = QHBoxLayout()
        self._campo = QLineEdit()
        self._campo.setPlaceholderText("Buscar no projeto... (Enter para buscar)")
        self._campo.setStyleSheet("""
            QLineEdit {
                background: #1a1a1a;
                color: #ddd;
                border: 1px solid #333;
                border-radius: 3px;
                padding: 4px 8px;
                font-family: Consolas;
                font-size: 12px;
            }
            QLineEdit:focus { border: 1px solid #4a90d9; }
        """)
        self._campo.returnPressed.connect(self._iniciar_busca)

        btn_buscar = QPushButton("Buscar")
        btn_buscar.setFixedWidth(70)
        btn_buscar.setStyleSheet(
            "QPushButton { background: #2a4a7a; color: #fff; border: none; "
            "border-radius: 3px; padding: 4px 8px; font-size: 11px; }"
            "QPushButton:hover { background: #3a5a8a; }"
        )
        btn_buscar.clicked.connect(self._iniciar_busca)

        linha_busca.addWidget(self._campo)
        linha_busca.addWidget(btn_buscar)
        layout.addLayout(linha_busca)

        # ── Opções ────────────────────────────────────────────────────
        opts = QHBoxLayout()
        self._chk_case  = QCheckBox("Aa")
        self._chk_regex = QCheckBox(".*")
        for chk in (self._chk_case, self._chk_regex):
            chk.setStyleSheet("color: #888; font-size: 11px;")
        opts.addWidget(self._chk_case)
        opts.addWidget(self._chk_regex)
        opts.addStretch()
        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("color: #666; font-size: 11px;")
        opts.addWidget(self._lbl_status)
        layout.addLayout(opts)

        # ── Lista de resultados ────────────────────────────────────────
        self._lista = QListWidget()
        self._lista.setStyleSheet("""
            QListWidget {
                background-color: #0d0d0d;
                color: #ccc;
                border: 1px solid #222;
                font-family: Consolas;
                font-size: 11px;
            }
            QListWidget::item { padding: 2px 6px; }
            QListWidget::item:hover    { background-color: #1e1e2e; }
            QListWidget::item:selected { background-color: #2a4a7a; color: #fff; }
        """)
        self._lista.itemClicked.connect(self._ao_clique)
        self._lista.itemDoubleClicked.connect(self._ao_clique)
        layout.addWidget(self._lista)

    # ── API pública ───────────────────────────────────────────────────

    def abrir(self, raiz: str):
        """Mostra o painel e foca no campo de busca."""
        self._raiz = raiz
        self.show()
        self.raise_()
        self._campo.setFocus()
        self._campo.selectAll()

    def fechar(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            # Mantém ref até finished — evita GC prematuro (BUG-202807-12)
            _threads_vivas_worker.add(self._worker)
            self._worker.finished.connect(
                lambda t=self._worker: _threads_vivas_worker.discard(t)
            )
            self._worker = None
        self.hide()

    # ── Busca ─────────────────────────────────────────────────────────

    def _iniciar_busca(self):
        termo = self._campo.text().strip()
        if not termo:

            return

        if not hasattr(self, '_raiz') or not self._raiz:
            self._lbl_status.setText("⚠ Abra um projeto primeiro")

            return

        # Para worker anterior (mantém ref até finished — evita GC prematuro)
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            _threads_vivas_worker.add(self._worker)
            self._worker.finished.connect(
                lambda t=self._worker: _threads_vivas_worker.discard(t)
            )

        self._lista.clear()
        self._lbl_status.setText("Buscando...")
        log.info(_ARQ, "_iniciar_busca", f"buscando '{termo}'", self._raiz)

        self._worker = _WorkerBusca(
            raiz  = self._raiz,
            termo = termo,
            regex = self._chk_regex.isChecked(),
            case  = self._chk_case.isChecked(),
        )
        self._worker.resultado.connect(self._adicionar_resultado)
        self._worker.concluido.connect(self._ao_concluir)
        self._worker.start()

    def _adicionar_resultado(self, arquivo: str, linha: int, trecho: str):
        nome_arq  = os.path.basename(arquivo)
        pasta_rel = os.path.dirname(arquivo)
        # Tenta mostrar caminho relativo
        if hasattr(self, '_raiz') and self._raiz:
            try:
                pasta_rel = os.path.relpath(os.path.dirname(arquivo), self._raiz)
            except ValueError:
                pass

        texto = f"  {nome_arq}:{linha}  {pasta_rel}  →  {trecho}"
        item  = QListWidgetItem(texto)
        item.setData(Qt.UserRole, (arquivo, linha))
        item.setToolTip(arquivo)

        # Alterna cor das linhas para facilitar leitura
        if self._lista.count() % 2 == 0:
            item.setBackground(QColor("#0d0d0d"))

        self._lista.addItem(item)
        total = self._lista.count()
        self._lbl_status.setText(f"{total} resultado{'s' if total != 1 else ''}...")

    def _ao_concluir(self, total: int):
        log.ok(_ARQ, "_ao_concluir", f"{total} resultados encontrados")
        if total == 0:
            item = QListWidgetItem("  Nenhum resultado encontrado")
            item.setForeground(Qt.gray)
            self._lista.addItem(item)
        if total >= 2000:
            self._lbl_status.setText(f"≥2000 resultados (limitado) ⚠")
        else:
            self._lbl_status.setText(f"{total} resultado{'s' if total != 1 else ''}")
        self._worker = None

    def _ao_clique(self, item: QListWidgetItem):
        dado = item.data(Qt.UserRole)
        if dado:
            arquivo, linha = dado
            log.info(_ARQ, "_ao_clique",
                     f"{os.path.basename(arquivo)}:{linha}")
            self.navegar.emit(arquivo, linha)

# ══════════════════════════════════════════════════════════════════════════════
# Controlador
# ══════════════════════════════════════════════════════════════════════════════

class FindInFiles(QObject):
    """
    Controlador do Find in Files.
    Instanciado no App_.py (MainWindow), não no CodeEditor.

    Uso no App_.py:
        self._find_in_files = FindInFiles(self)
        # E no menu ou atalho:
        self._find_in_files.abrir()
    """

    def __init__(self, janela):
        super().__init__(janela)
        self._janela = janela

        self._painel = _PainelFindInFiles(janela.centralWidget() or janela)
        self._painel.navegar.connect(self._navegar)

        # Atalho removido — agora em atalhos.json (ctrl-j → busca::BuscarNoProjeto)
        log.info(_ARQ, "__init__", "FindInFiles inicializado")

    def abrir(self):
        """Abre o painel de busca posicionado na janela."""
        raiz = getattr(self._janela, "current_project_path", None) or ""
        if not raiz:
            log.aviso(_ARQ, "abrir", "nenhum projeto aberto")

        # Redimensiona e posiciona no centro-superior da janela
        cw = self._janela.centralWidget() or self._janela
        w  = min(700, max(400, cw.width()  - 40))
        h  = min(500, max(300, cw.height() - 80))
        x  = (cw.width()  - w) // 2
        y  = 20
        self._painel.setParent(cw)
        self._painel.setGeometry(x, y, w, h)
        self._painel.abrir(raiz)

    # ── Navegação ─────────────────────────────────────────────────────

    def _navegar(self, arquivo: str, linha: int):
        log.info(_ARQ, "_navegar",
                 f"{os.path.basename(arquivo)}:{linha}")
        janela = self._janela
        if not hasattr(janela, "tabs"):

            return

        norm = lambda p: os.path.normcase(os.path.normpath(p)) if p else ""

        for indice, editor in janela.tabs.editores.items():
            caminho = getattr(editor, "file_path", None)
            if caminho and norm(caminho) == norm(arquivo):
                janela.tabs.setCurrentIndex(indice)
                editor.ir_para_linha(linha)

                return

        novo = janela.tabs.add_new_tab(arquivo)
        if novo:
            novo.ir_para_linha(linha)
