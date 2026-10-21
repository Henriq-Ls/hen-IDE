# 📁 _EDITOR_/Funcionalidades/find_references.py
# -*- coding: utf-8 -*-
"""
Find References — mostra todos os usos de um símbolo no projeto.
Atalhos: Shift+F12 / Ctrl+F12
Também ativado pelo clique em "N usos" no CodeLens da calha.
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton
)
from PySide6.QtCore import Qt, QObject, Signal, QTimer
from PySide6.QtGui  import QTextCursor, QKeySequence, QShortcut
from _LOG_.log import log
_ARQ = "find_references.py"

class _PainelReferencias(QWidget):
    navegar = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PainelReferencias")
        self._montar_ui()
        self._aplicar_estilo()
        self.hide()
        self._timer_auto = QTimer(self)
        self._timer_auto.setSingleShot(True)
        self._timer_auto.setInterval(30_000)
        self._timer_auto.timeout.connect(self.fechar)

    def _montar_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        cab = QHBoxLayout()
        self._label = QLabel("Referências")
        self._label.setStyleSheet("color: #ccc; font-weight: bold; font-size: 12px;")
        btn_fechar = QPushButton("✕")
        btn_fechar.setFixedSize(20, 20)
        btn_fechar.setStyleSheet(
            "QPushButton { background: transparent; color: #888; border: none; }"
            "QPushButton:hover { color: #fff; }"
        )
        btn_fechar.clicked.connect(self.fechar)
        cab.addWidget(self._label)
        cab.addStretch()
        cab.addWidget(btn_fechar)
        layout.addLayout(cab)

        self._lista = QListWidget()
        self._lista.itemDoubleClicked.connect(self._ao_duplo_clique)
        self._lista.itemClicked.connect(self._ao_clique)
        layout.addWidget(self._lista)

    def _aplicar_estilo(self):
        self.setStyleSheet("""
            QWidget#PainelReferencias {
                background-color: #111;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
            }
        """)
        self._lista.setStyleSheet("""
            QListWidget {
                background-color: #111;
                color: #ccc;
                border: none;
                font-family: Consolas;
                font-size: 12px;
            }
            QListWidget::item { padding: 3px 6px; }
            QListWidget::item:hover    { background-color: #1e1e2e; }
            QListWidget::item:selected { background-color: #2a4a7a; color: #fff; }
        """)

    def mostrar(self, nome: str, resultados: list[dict]):
        """
        resultados: [{"arquivo": str, "linha": int, "trecho": str}, ...]
        """
        self._lista.clear()
        total = len(resultados)
        self._label.setText(f"Referências: {nome} ({total})")

        for r in resultados:
            arquivo  = r.get("arquivo", "")
            linha    = r.get("linha", 0)
            trecho   = r.get("trecho", "").strip()
            nome_arq = os.path.basename(arquivo)

            item = QListWidgetItem(f"  {nome_arq}  linha {linha}  →  {trecho}")
            item.setData(Qt.UserRole, (arquivo, linha))
            item.setToolTip(arquivo)
            self._lista.addItem(item)

        if not resultados:
            item = QListWidgetItem(f"  Nenhuma referência encontrada para '{nome}'")
            item.setForeground(Qt.gray)
            self._lista.addItem(item)

        self.show()
        self.raise_()
        self._timer_auto.start()

    def fechar(self):
        self._timer_auto.stop()
        self.hide()

    def _ao_clique(self, item: QListWidgetItem):
        dado = item.data(Qt.UserRole)
        if dado:
            arquivo, linha = dado
            self.navegar.emit(arquivo, linha)

    def _ao_duplo_clique(self, item: QListWidgetItem):
        self._ao_clique(item)

class FindReferences(QObject):
    """
    Gerencia o painel de Find References.
    Instanciado dentro do CodeEditor.

    Ativado por:
      - Shift+F12 / Ctrl+F12  → busca a palavra sob o cursor
      - CodeLens "N usos"     → buscar_com_arquivo(nome, arquivo, linha)
    """

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor
        self._painel = _PainelReferencias(editor)
        self._painel.navegar.connect(self._navegar)

        # WindowShortcut garante prioridade sobre event filters
        sc1 = QShortcut(QKeySequence("Shift+F12"), editor)
        sc1.setContext(Qt.WindowShortcut)
        sc1.activated.connect(self.buscar_no_cursor)

        sc2 = QShortcut(QKeySequence("Ctrl+F12"), editor)
        sc2.setContext(Qt.WindowShortcut)
        sc2.activated.connect(self.buscar_no_cursor)

        sc_esc = QShortcut(QKeySequence("Escape"), editor)
        sc_esc.setContext(Qt.WidgetWithChildrenShortcut)
        sc_esc.activated.connect(self._painel.fechar)

        log.info(_ARQ, "__init__", "FindReferences inicializado (Shift+F12 / Ctrl+F12)")
        self._editor.viewport().installEventFilter(self)

    # ── API pública ────────────────────────────────────────────────────

    # ── Filtro de eventos ────────────────────────────────

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        try:
            if obj is self._editor.viewport() and self._painel.isVisible():
                if event.type() == QEvent.MouseButtonPress:
                    # Fecha o painel se o clique foi fora dele
                    pos_editor = self._editor.viewport().mapTo(self._editor, event.pos())
                    if not self._painel.geometry().contains(pos_editor):
                        self._painel.fechar()
        except RuntimeError:
            pass  # C++ CodeEditor ja destruido durante shutdown

        return False

    def buscar_no_cursor(self):
        """Shift+F12 / Ctrl+F12 — busca referências da palavra sob o cursor."""
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)

        nome = cursor.selectedText().strip()
        if not nome:
            log.info(_ARQ, "buscar_no_cursor", "nenhuma palavra selecionada")

            return

        arquivo_atual = getattr(self._editor, "file_path", None) or ""
        log.info(_ARQ, "buscar_no_cursor", f"buscando '{nome}'", arquivo_atual)
        self._buscar(nome, arquivo_atual)

    def buscar_com_arquivo(self, nome: str, arquivo_definicao: str, linha_definicao: int):
        """
        Chamado pelo CodeLens ao clicar em 'N usos'.
        Recebe nome, arquivo e linha da definição diretamente da calha.
        """
        log.info(_ARQ, "buscar_com_arquivo",
                 f"CodeLens: '{nome}'",
                 f"{os.path.basename(arquivo_definicao)}:{linha_definicao}")
        self._buscar(nome, arquivo_definicao)

    # ── Busca interna ──────────────────────────────────────────────────

    def _buscar(self, nome: str, arquivo_definicao: str):
        indexador = self._pegar_indexador()
        if not indexador:
            log.aviso(_ARQ, "_buscar", "indexador não disponível — projeto aberto?")
            self._painel.mostrar(nome, [])
            self._redimensionar_painel()
            self._status("Indexador não disponível — abra um projeto primeiro")

            return

        # ✅ CORREÇÃO: normaliza para forward slash para bater com char(92) do SQL
        arquivo_norm = arquivo_definicao.replace("\\", "/") if arquivo_definicao else ""

        try:
            refs = indexador.consultas.buscar_referencias(nome, arquivo_norm)
        except Exception as e:
            log.erro(_ARQ, "_buscar", "erro ao buscar referências", str(e))
            self._painel.mostrar(nome, [])
            self._redimensionar_painel()

            return

        log.ok(_ARQ, "_buscar", f"encontradas {len(refs)} referências para '{nome}'")

        resultados = []
        for r in refs:
            arquivo = r.get("arquivo", "")
            linha   = r.get("linha", 0)
            trecho  = self._pegar_trecho(arquivo, linha)
            # Só inclui se for uma chamada real: nome( ou nome (
            trecho_limpo = trecho.lstrip()
            if f"{nome}(" in trecho or f"{nome} (" in trecho:
                resultados.append({"arquivo": arquivo, "linha": linha, "trecho": trecho})

        self._painel.mostrar(nome, resultados)
        self._redimensionar_painel()

    def _pegar_trecho(self, arquivo: str, linha: int) -> str:
        """Retorna o texto da linha especificada no arquivo."""
        try:
            with open(arquivo, encoding="utf-8", errors="replace") as f:
                linhas = f.readlines()
            if 1 <= linha <= len(linhas):

                return linhas[linha - 1].strip()

        except OSError:
            pass

        return ""

    def _redimensionar_painel(self):
        """
        Posiciona o painel no canto inferior ESQUERDO do editor.
        Fica longe do Outline (que ocupa a borda direita).
        """
        try:
            from _CONFIGURA_ import OUTLINE_LARGURA_MIN
            margem_dir = OUTLINE_LARGURA_MIN
        except ImportError:
            margem_dir = 200

        editor    = self._editor
        area_util = editor.width() - margem_dir
        w = min(550, max(300, area_util // 2))
        h = min(220, max(120, editor.height() // 3))
        x = 10
        y = editor.height() - h - 10
        self._painel.setGeometry(x, y, w, h)

    # ── Navegação ─────────────────────────────────────────────────────

    def _navegar(self, arquivo: str, linha: int):
        log.info(_ARQ, "_navegar", f"{os.path.basename(arquivo)}:{linha}")
        janela = self._editor.window()
        if not hasattr(janela, "tabs"):

            return

        norm = lambda p: os.path.normcase(os.path.normpath(p)) if p else ""

        # Procura uma aba já aberta com esse arquivo
        for indice, editor in janela.tabs.editores.items():
            caminho = getattr(editor, "file_path", None)
            if caminho and norm(caminho) == norm(arquivo):
                janela.tabs.setCurrentIndex(indice)
                editor.ir_para_linha(linha)

                return

        # Não estava aberto — abre numa nova aba
        novo = janela.tabs.add_new_tab(arquivo)
        if novo:
            novo.ir_para_linha(linha)

    # ── Utilitários ───────────────────────────────────────────────────

    def _pegar_indexador(self):
        return getattr(self._editor.window(), "_indexador", None)

    def _status(self, mensagem: str):
        janela = self._editor.window()
        if hasattr(janela, "statusBar"):
            janela.statusBar().showMessage(mensagem, 5000)
