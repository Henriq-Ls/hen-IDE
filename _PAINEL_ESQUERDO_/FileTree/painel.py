# 📁 _PAINEL_ESQUERDO_/FileTree/painel.py
"""
PainelArquivos — widget principal da árvore de arquivos do projeto.
"""

import os
import shutil
import subprocess

from PySide6.QtCore import (
    QDir,
    QEvent,
    QModelIndex,
    QSize,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QKeySequence, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console

import _CONFIGURA_ as _CFG
from _CONFIGURA_ import PACKS_ICONES
from _CONFIGURA_.gerenciador_tema import tema_global
from _UTILITARIOS_.hein_context_menu import heinContextMenu
from _UTILITARIOS_.icones import icone_tema
from _UTILITARIOS_._ajuda_ import criar_botao_ajuda
from _UTILITARIOS_._ajuda_.conteudos import filetree as _ajuda_filetree

from ._auxiliares import MenuRecenteProjeto, _cache_icones
from ._modelo import _DelegateGit, _IconProvider, _ProxyOrdem
from ._workers import _WorkerGit, _WorkerTamanhoPasta
from _THREADS_.ciclo_vida import encerrar_thread


class PainelArquivos(QWidget):
    arquivo_selecionado      = Signal(str)
    executar_arquivo         = Signal(str)
    arquivo_clicado_simples  = Signal(str)

    def __init__(self, parent=None, tema: dict = None):
        super().__init__(parent)
        self._tema            = tema or tema_global().dados()
        self._caminho_atual   = ""
        self._status_git: dict = {}
        self._thread: QThread | None = None
        self._worker: _WorkerGit | None = None
        self._thread_tamanho: QThread | None = None
        self._worker_tamanho: _WorkerTamanhoPasta | None = None
        self._threads_tamanho_antigas: list = []  # threads de projeto anterior ainda drenando
        self._clipboard_caminhos: list[str] = []
        self._clipboard_recortar: bool = False
        self._historico: list = []
        self._estado_expansao_salvo: list = []

        # ── Staging mode ────────────────────────────────────────────────
        self._modo_staging: bool = False
        self._staging_checks: dict[str, bool] = {}   # caminho_lower → marcado

        self._construir_ui()
        self._aplicar_tema()

        self._timer_git = QTimer(self)
        self._timer_git.setInterval(5000)
        self._timer_git.timeout.connect(self._disparar_git_status)

    # ──────────────────────────────────────────────────────────────────
    # Construção da UI
    # ──────────────────────────────────────────────────────────────────

    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        _estilo_icone = (
            "QPushButton { background: transparent; border: none; padding: 0px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.07); border-radius: 3px; }"
        )

        # ─── Barra de topo: só nome do projeto ───
        self._barra_esquerda = MenuRecenteProjeto(self)
        self._barra_esquerda.abrir_pasta.connect(self._abrir_pasta_no_explorador)
        layout.addWidget(self._barra_esquerda)

        # ─── Barra de ações: fica entre a barra de topo e a árvore,
        #     visualmente na mesma linha onde o .venv aparece como 1º item ───
        self._btn_ajuda = criar_botao_ajuda(
            _ajuda_filetree.texto, titulo="Como usar a Árvore do Projeto",
            tooltip="Ajuda — funcionalidades", parent=self,
        )

        self._btn_expandir = QPushButton()
        self._btn_expandir.setFixedSize(20, 20)
        self._btn_expandir.setIcon(icone_tema("mdi.arrow-expand-all"))
        self._btn_expandir.setIconSize(QSize(13, 13))
        self._btn_expandir.clicked.connect(self._expandir_tudo)
        self._btn_expandir.setToolTip("Expandir tudo")
        self._btn_expandir.setStyleSheet(_estilo_icone)

        self._btn_colapsar = QPushButton()
        self._btn_colapsar.setFixedSize(20, 20)
        self._btn_colapsar.setIcon(icone_tema("mdi.arrow-collapse-all"))
        self._btn_colapsar.setIconSize(QSize(13, 13))
        self._btn_colapsar.clicked.connect(self._colapsar_tudo)
        self._btn_colapsar.setToolTip("Colapsar tudo")
        self._btn_colapsar.setStyleSheet(_estilo_icone)

        self._btn_filtrar = QPushButton()
        self._btn_filtrar.setFixedSize(20, 20)
        self._btn_filtrar.setIcon(icone_tema("mdi.eye-off-outline"))
        self._btn_filtrar.setIconSize(QSize(13, 13))
        self._btn_filtrar.setCheckable(True)
        self._btn_filtrar.setChecked(False)
        self._btn_filtrar.setToolTip("Ocultar __pycache__ e .bak")
        self._btn_filtrar.setStyleSheet(
            "QPushButton { background: transparent; border: none; padding: 0px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.07); border-radius: 3px; }"
            "QPushButton:checked { background: rgba(255,200,0,0.15); border-radius: 3px; }"
        )
        self._btn_filtrar.toggled.connect(self._toggle_filtro_gerados)

        self._btn_limpar_patch = QPushButton()
        self._btn_limpar_patch.setFixedSize(20, 20)
        self._btn_limpar_patch.setIcon(icone_tema("mdi.broom"))
        self._btn_limpar_patch.setIconSize(QSize(13, 13))
        self._btn_limpar_patch.setToolTip("Limpar arquivos gerados: __pycache__, .bak, _patch*")
        self._btn_limpar_patch.setStyleSheet(_estilo_icone)
        self._btn_limpar_patch.clicked.connect(self._limpar_arquivos_patch)

        # ─── Botões de staging (ficam na mesma barra, ocultos por padrão) ───
        self._btn_marcar_tudo = QPushButton("✓ Marcar tudo")
        self._btn_desmarcar_tudo = QPushButton("□ Desmarcar tudo")
        _estilo_staging = (
            "QPushButton { background: rgba(255,255,255,0.07); border: none; "
            "border-radius: 3px; color: #aaa; font-size: 10px; padding: 0 6px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.13); color: #ddd; }"
        )
        for btn in (self._btn_marcar_tudo, self._btn_desmarcar_tudo):
            btn.setFixedHeight(18)
            btn.setStyleSheet(_estilo_staging)
            btn.setVisible(False)
        self._btn_marcar_tudo.clicked.connect(lambda: self._staging_marcar_tudo(True))
        self._btn_desmarcar_tudo.clicked.connect(lambda: self._staging_marcar_tudo(False))

        barra_acoes = QHBoxLayout()
        barra_acoes.setContentsMargins(2, 1, 2, 1)
        barra_acoes.setSpacing(2)
        barra_acoes.addWidget(self._btn_ajuda)
        barra_acoes.addWidget(self._btn_expandir)
        barra_acoes.addWidget(self._btn_colapsar)
        barra_acoes.addWidget(self._btn_filtrar)
        barra_acoes.addWidget(self._btn_limpar_patch)
        barra_acoes.addWidget(self._btn_marcar_tudo)
        barra_acoes.addWidget(self._btn_desmarcar_tudo)
        barra_acoes.addStretch()
        layout.addLayout(barra_acoes)

        # ─── Model e Proxy ───
        self._model = _IconProvider()
        self._model.setRootPath("")
        self._model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)

        self._proxy = _ProxyOrdem()
        self._proxy.setSourceModel(self._model)
        self._proxy.setDynamicSortFilter(True)

        # ─── Tree ───
        self._tree = QTreeView()
        self._tree.setModel(self._proxy)
        self._tree.setIconSize(QSize(16, 16))
        self._tree.hideColumn(1)
        self._tree.hideColumn(2)
        self._tree.hideColumn(3)
        self._tree.setRootIndex(self._proxy.mapFromSource(self._model.index("")))
        self._tree.setHeaderHidden(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(12)
        self._tree.setRootIsDecorated(True)
        self._tree.setColumnWidth(0, 200)
        self._tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        self._tree.doubleClicked.connect(self._ao_clicar)
        self._tree.setExpandsOnDoubleClick(False)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.clicked.connect(self._ao_clique_simples)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._menu_contexto)
        self._tree.installEventFilter(self)
        self._tree.viewport().installEventFilter(self)

        # ─── Delegate Git ───
        self._delegate = _DelegateGit(
            self._model, self._proxy, self._status_git, self._staging_checks
        )
        self._tree.setItemDelegate(self._delegate)
        self._proxy.sort(0, Qt.AscendingOrder)

        # ─── Drag-and-drop para mover arquivos/pastas ───
        self._model.setReadOnly(False)
        self._model.fileRenamed.connect(self._ao_renomear_inline)
        self._tree.setDragEnabled(True)
        self._tree.setAcceptDrops(True)
        self._tree.setDropIndicatorShown(True)
        self._tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

        layout.addWidget(self._tree)

        self._status = QLabel("")
        layout.addWidget(self._status)

        self._renomear_caminho: str = ""

        self._aplicar_tema()

    # ──────────────────────────────────────────────────────────────────
    # Eventos / filtros
    # ──────────────────────────────────────────────────────────────────

    def _abrir_pasta_no_explorador(self, event=None):
        if self._caminho_atual and os.path.isdir(self._caminho_atual):
            if os.name == "nt":
                os.startfile(self._caminho_atual)
            elif os.name == "posix":
                subprocess.run(["xdg-open", self._caminho_atual], check=False)

    def _ao_clicar(self, indice):
        caminho = self._model.filePath(self._proxy.mapToSource(indice))
        if os.path.isfile(caminho):
            self.arquivo_selecionado.emit(caminho)

    def _ao_clique_simples(self, indice):
        from PySide6.QtWidgets import QApplication as _QApp
        from PySide6.QtCore import Qt as _Qt

        caminho = self._model.filePath(self._proxy.mapToSource(indice))

        # ── Modo staging: clique em arquivo rastreável togla o checkbox ──
        if self._modo_staging:
            caminho_key = caminho.replace("\\", "/").lower()
            if caminho_key in self._staging_checks:
                self._staging_checks[caminho_key] = not self._staging_checks[caminho_key]
                self._tree.viewport().update()
            # pastas: expande/colapsa normalmente mesmo em staging
            if os.path.isdir(caminho):
                if self._tree.isExpanded(indice):
                    self._tree.collapse(indice)
                else:
                    self._tree.expand(indice)
            return

        # ── Modo normal ──────────────────────────────────────────────────
        # Ctrl ou Shift pressionados → seleção múltipla; não abre preview
        mods = _QApp.keyboardModifiers()
        if mods & (_Qt.ControlModifier | _Qt.ShiftModifier):
            return
        if os.path.isdir(caminho):
            if self._tree.isExpanded(indice):
                self._tree.collapse(indice)
            else:
                self._tree.expand(indice)
        elif os.path.isfile(caminho):
            self.arquivo_clicado_simples.emit(caminho)
            # Devolve foco a arvore para atalhos continuarem funcionando
            QTimer.singleShot(0, self._tree.setFocus)

    def eventFilter(self, obj, event):
        # Enter/Leave monitorados no viewport (área interna dos itens).
        # Usar self._tree causava Leave espúrio ao passar o mouse em itens filhos.
        if obj is self._tree.viewport():
            if event.type() == QEvent.Type.Enter:
                self._tree.verticalScrollBar().setStyleSheet(
                    getattr(self, "_sb_visivel", "")
                )
                return False
            if event.type() == QEvent.Type.Leave:
                self._tree.verticalScrollBar().setStyleSheet(
                    getattr(self, "_sb_oculta", "")
                )
                return False

        if obj is self._tree and event.type() == QEvent.Type.KeyPress:
            indice  = self._tree.currentIndex()
            caminho = (
                self._model.filePath(self._proxy.mapToSource(indice))
                if indice.isValid()
                else ""
            )
            key = event.key()
            mod = event.modifiers()

            if key == Qt.Key.Key_Delete and caminho:
                self._apagar_selecionados()
                return True

            if key == Qt.Key.Key_F2 and caminho:
                self._renomear(caminho)
                return True

            if mod == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_R and caminho:
                self._renomear(caminho)
                return True

            # Shift+F1 → novo arquivo | Shift+F2 → nova pasta | Shift+F3 → renomear
            if mod == Qt.KeyboardModifier.ShiftModifier:
                pasta_ctx = (
                    os.path.dirname(caminho) if caminho and os.path.isfile(caminho)
                    else (caminho or self._caminho_atual)
                )
                if key == Qt.Key.Key_F1 and self._caminho_atual:
                    self._criar_arquivo(pasta_ctx)
                    return True
                if key == Qt.Key.Key_F2 and self._caminho_atual:
                    self._criar_pasta(pasta_ctx)
                    return True

            if mod == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_C and caminho:
                self._copiar(caminho)
                return True

            if mod == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_X and caminho:
                self._recortar(caminho)
                return True

            if mod == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_V and self._clipboard_caminhos:
                self._colar()
                return True

            # Enter -> abre em edicao | Space -> abre em preview
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if caminho:
                    if os.path.isfile(caminho):
                        self.arquivo_selecionado.emit(caminho)
                    elif os.path.isdir(caminho):
                        if self._tree.isExpanded(indice):
                            self._tree.collapse(indice)
                        else:
                            self._tree.expand(indice)
                return True

            if key == Qt.Key.Key_Space:
                if caminho and os.path.isfile(caminho):
                    self.arquivo_clicado_simples.emit(caminho)
                return True

            # Seta direita -> expande pasta / entra no primeiro filho
            if key == Qt.Key.Key_Right and caminho:
                if os.path.isdir(caminho):
                    if not self._tree.isExpanded(indice):
                        self._tree.expand(indice)
                    else:
                        filho = self._proxy.index(0, 0, indice)
                        if filho.isValid():
                            self._tree.setCurrentIndex(filho)
                return True

            # Seta esquerda -> colapsa pasta / sobe para o pai
            if key == Qt.Key.Key_Left and caminho:
                if os.path.isdir(caminho) and self._tree.isExpanded(indice):
                    self._tree.collapse(indice)
                else:
                    pai = indice.parent()
                    if pai.isValid():
                        self._tree.setCurrentIndex(pai)
                return True

        return super().eventFilter(obj, event)

    # ──────────────────────────────────────────────────────────────────
    # Menu de contexto
    # ──────────────────────────────────────────────────────────────────

    def _menu_contexto(self, pos):
        indice  = self._tree.indexAt(pos)
        caminho = (
            self._model.filePath(self._proxy.mapToSource(indice))
            if indice.isValid()
            else self._caminho_atual
        )
        eh_arquivo  = os.path.isfile(caminho)
        pasta_pai   = os.path.dirname(caminho) if eh_arquivo else caminho

        pasta_trash = (
            os.path.join(self._caminho_atual, ".hein", "lixeira")
            if self._caminho_atual
            else ""
        )
        eh_lixeira     = bool(pasta_trash and os.path.normpath(caminho) == os.path.normpath(pasta_trash))
        dentro_lixeira = bool(pasta_trash and caminho.startswith(pasta_trash + os.sep))

        # ── Menu da lixeira ──────────────────────────────────────────
        if eh_lixeira or dentro_lixeira:
            itens_trash = []
            if dentro_lixeira and eh_arquivo:
                itens_trash.append((
                    "Restaurar este arquivo",
                    "mdi.restore",
                    lambda c=caminho: self._restaurar_item_lixeira(c),
                ))
                itens_trash.append(None)
            itens_trash.append(("Restaurar último apagado", "mdi.undo-variant", self._desfazer))
            itens_trash.append(("Esvaziar Lixeira", "mdi.delete-forever-outline", self._esvaziar_lixeira))
            menu = heinContextMenu(parent=self, itens=itens_trash)
            menu.exec(self._tree.viewport().mapToGlobal(pos))
            return

        itens = [
            ("Nova Pasta",    "mdi.folder-plus-outline",  lambda checked=False: self._criar_pasta(pasta_pai)),
            None,
            ("Copiar",        "mdi.content-copy",         lambda checked=False, c=caminho: self._copiar(c)),
            ("Recortar",      "mdi.content-cut",          lambda checked=False, c=caminho: self._recortar(c)),
            ("Colar",         "mdi.content-paste",        self._colar),
            None,
            ("Copiar Caminho", "mdi.link-variant",        lambda checked=False, c=caminho: self._copiar_caminho(c)),
            None,
            ("Renomear",      "mdi.pencil-outline",       lambda checked=False: self._renomear(caminho)),
            ("Apagar",        "mdi.delete-outline",       self._apagar_selecionados),
            ("Desfazer",      "mdi.undo-variant",         self._desfazer),
            None,
            ("Mostrar no Explorador", "mdi.folder-open-outline", lambda checked=False, c=caminho: self._mostrar_no_explorador(c)),
            None,
        ]

        if eh_arquivo and os.path.splitext(caminho)[1].lower() == ".py":
            itens.insert(0, ("Executar", "mdi.play-circle-outline", lambda checked=False, c=caminho: self.executar_arquivo.emit(c)))
            itens.insert(1, None)

        tem_browser = eh_arquivo and os.path.splitext(caminho)[1].lower() in (".html", ".htm")
        tem_git     = eh_arquivo and os.path.isdir(os.path.join(self._caminho_atual, ".git"))

        if tem_browser:
            itens.append(None)
            itens.append(("Abrir no Navegador", "mdi.web", lambda: self._abrir_no_navegador(caminho)))

        if tem_git:
            if not tem_browser:
                itens.append(None)
            itens.append(("Adicionar ao Git", "mdi.source-branch-plus", lambda: self._git_add(caminho)))

        if pasta_trash and os.path.isdir(pasta_trash) and os.listdir(pasta_trash):
            itens.append(None)
            itens.append(("Restaurar último apagado", "mdi.undo-variant", self._desfazer))
            itens.append(("Esvaziar Lixeira", "mdi.delete-forever-outline", self._esvaziar_lixeira))

        menu = heinContextMenu(parent=self, itens=itens)

        # ―― Submenu “Novo Arquivo” com atalhos por extensão ―――――――――――――――――――
        _sub_itens_novo = [
            ("Qualquer tipo...",   "mdi.file-plus-outline",
             lambda checked=False: self._criar_arquivo(pasta_pai)),
            None,
            (".py — Python",       "mdi.language-python",
             lambda checked=False: self._criar_arquivo_ext(pasta_pai, ".py")),
            (".html — HTML",       "mdi.language-html5",
             lambda checked=False: self._criar_arquivo_ext(pasta_pai, ".html")),
            (".js — JavaScript",   "mdi.language-javascript",
             lambda checked=False: self._criar_arquivo_ext(pasta_pai, ".js")),
            (".txt — Texto",       "mdi.text-box-outline",
             lambda checked=False: self._criar_arquivo_ext(pasta_pai, ".txt")),
        ]
        _nova_pasta_acao = menu.acao("Nova Pasta")
        menu.adicionar_submenu(
            "Novo Arquivo", "mdi.file-plus-outline",
            _sub_itens_novo,
            antes_de="Nova Pasta",
        )

        _atalhos_menu = {
            "Novo Arquivo":  "Shift+F1",
            "Nova Pasta":    "Shift+F2",
            "Copiar":        "Ctrl+C",
            "Recortar":      "Ctrl+X",
            "Colar":         "Ctrl+V",
            "Renomear":      "Ctrl+R",
            "Apagar":        "Del",
        }
        for _nome, _seq in _atalhos_menu.items():
            _a = menu.acao(_nome)
            if _a:
                _a.setShortcut(QKeySequence(_seq))
                _a.setShortcutVisibleInContextMenu(True)

        if not indice.isValid():
            menu.acao("Renomear").setEnabled(False)
            menu.acao("Apagar").setEnabled(False)
            menu.acao("Copiar").setEnabled(False)
            menu.acao("Copiar Caminho").setEnabled(False)



        if not self._clipboard_caminhos or not any(os.path.exists(c) for c in self._clipboard_caminhos):
            menu.acao("Colar").setEnabled(False)
        if not indice.isValid():
            menu.acao("Recortar").setEnabled(False)

        if not self._historico:
            menu.acao("Desfazer").setEnabled(False)

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    # ──────────────────────────────────────────────────────────────────
    # Operações de arquivo
    # ──────────────────────────────────────────────────────────────────

    def _criar_arquivo(self, pasta: str):
        """Abre dialog pedindo nome completo (inclui extensão se quiser)."""
        from _UTILITARIOS_.hein_pou_pap import HeinInputDialog as _HID
        nome_final = _HID.pedir_nome(
            "Novo Arquivo",
            descricao="Digite o nome com extensão — ou sem, se preferir.",
            placeholder="ex: utils.py  ou  README.md  ou  notas",
            parent=self,
        )
        if not nome_final:
            return
        self._finalizar_criacao_arquivo(pasta, nome_final)

    def _criar_arquivo_ext(self, pasta: str, ext: str):
        """Abre dialog pedindo só o nome; a extensão já está definida."""
        from _UTILITARIOS_.hein_pou_pap import HeinInputDialog as _HID
        nome = _HID.pedir_nome(
            f"Novo arquivo {ext}",
            descricao=f"O arquivo será criado com a extensão <b>{ext}</b>.",
            placeholder="ex: meu_arquivo",
            parent=self,
        )
        if not nome:
            return
        if not nome.lower().endswith(ext.lower()):
            nome = nome + ext
        self._finalizar_criacao_arquivo(pasta, nome)

    def _finalizar_criacao_arquivo(self, pasta: str, nome_final: str):
        """Cria o arquivo em disco e abre no editor correto."""
        caminho = os.path.join(pasta, nome_final)
        if os.path.exists(caminho):
            from _UTILITARIOS_.hein_pou_pap import HeinPopup as _HP
            _HP.aviso("Já existe",
                      f"<b>{nome_final}</b> já existe nessa pasta.",
                      parent=self)
            return
        ext = os.path.splitext(nome_final)[1].lower()
        try:
            with open(caminho, "w", encoding="utf-8") as f:
                if ext == ".py":
                    rel = os.path.relpath(caminho, self._caminho_atual).replace("\\", "/")
                    f.write(f"# 📁 {rel}\n\n")
            # arquivo_selecionado → _abrir_arquivo_selecionado roteia por extensão
            self.arquivo_selecionado.emit(caminho)
        except Exception as e:
            from _UTILITARIOS_.hein_pou_pap import HeinPopup as _HP
            _HP.erro("Erro ao criar arquivo", str(e), parent=self)

    def _criar_pasta(self, pasta: str):
        from PySide6.QtWidgets import (
            QCheckBox,
            QDialog,
            QHBoxLayout,
            QLineEdit,
            QPushButton,
            QVBoxLayout,
        )
        from PySide6.QtWidgets import QLabel as _QLabel

        dlg = QDialog(self)
        dlg.setWindowTitle("Nova Pasta")
        dlg.setFixedWidth(300)
        t     = tema_global()
        fundo = t.cor("painel_arquivos.fundo", "#0a0a0a")
        texto = t.cor("painel_arquivos.texto", "#e0e0e0")
        borda = t.cor("interface.borda", "#1a1a1a")
        dlg.setStyleSheet(f"background:{fundo}; color:{texto};")

        lay = QVBoxLayout(dlg)
        lay.setSpacing(8)
        lay.setContentsMargins(12, 12, 12, 12)

        lay.addWidget(_QLabel("Nome da pasta:"))
        campo = QLineEdit()
        campo.setStyleSheet(
            f"background:#111; color:{texto}; border:1px solid {borda}; padding:4px; border-radius:3px;"
        )
        lay.addWidget(campo)

        chk = QCheckBox("Criar __init__.py dentro")
        chk.setChecked(True)
        chk.setStyleSheet(f"color:{texto};")
        lay.addWidget(chk)

        btns      = QHBoxLayout()
        btn_ok     = QPushButton("Criar")
        btn_cancel = QPushButton("Cancelar")
        for b in [btn_ok, btn_cancel]:
            b.setStyleSheet(
                f"background:#1e3a5f; color:{texto}; border:none; padding:5px 12px; border-radius:3px;"
            )
            b.setCursor(Qt.PointingHandCursor)
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel.clicked.connect(dlg.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        lay.addLayout(btns)

        campo.setFocus()
        if dlg.exec() != QDialog.Accepted:
            return

        nome = campo.text().strip()
        if not nome:
            return

        caminho = os.path.join(pasta, nome)
        if os.path.exists(caminho):
            QMessageBox.warning(self, "Já existe", f"'{nome}' já existe.")
            return

        try:
            os.makedirs(caminho)
            if chk.isChecked():
                init = os.path.join(caminho, "__init__.py")
                with open(init, "w", encoding="utf-8") as f:
                    rel = os.path.relpath(init, self._caminho_atual).replace("\\", "/")
                    f.write(f"# 📁 {rel}\n")
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))

    def _abrir_no_navegador(self, caminho: str):
        import webbrowser
        webbrowser.open(f"file:///{caminho.replace(chr(92), '/')}")

    def _git_add(self, caminho: str):
        try:
            r = subprocess.run(
                ["git", "add", caminho],
                capture_output=True,
                text=True,
                cwd=self._caminho_atual,
                timeout=10,
                **opcoes_processo_sem_console(),
            )
            if r.returncode == 0:
                self._disparar_git_status()
            else:
                QMessageBox.warning(self, "Git add", r.stderr.strip() or "Erro ao executar git add.")
        except Exception as e:
            QMessageBox.critical(self, "Git add", str(e))

    def _renomear(self, caminho: str):
        """Ativa o editor inline nativo da QTreeView para o item."""
        if not caminho or not os.path.exists(caminho):
            return
        src_idx = self._model.index(caminho)
        if not src_idx.isValid():
            return
        proxy_idx = self._proxy.mapFromSource(src_idx)
        if not proxy_idx.isValid():
            return

        self._renomear_caminho = caminho
        self._tree.setCurrentIndex(proxy_idx)
        self._tree.edit(proxy_idx)

    def _ao_renomear_inline(self, pasta: str, nome_antigo: str, nome_novo: str):
        """Chamado pelo QFileSystemModel.fileRenamed após o rename concluir."""
        if not nome_antigo or not nome_novo or nome_antigo == nome_novo:
            return

        caminho_antigo = os.path.join(pasta, nome_antigo)
        caminho_novo   = os.path.join(pasta, nome_novo)

        self._historico.append(("rename", caminho_novo, caminho_antigo))

        janela = self.window()
        tabs   = getattr(janela, "tabs", None)
        if tabs is not None:
            cam_norm = os.path.normcase(os.path.abspath(caminho_antigo))
            for i, editor in list(tabs.editores.items()):
                fp = getattr(editor, "file_path", None)
                if fp and os.path.normcase(os.path.abspath(fp)) == cam_norm:
                    editor.file_path = caminho_novo
                    tabs._atualizar_titulo_aba(i)

    def _selecionar_no_tree(self, caminho: str):
        """Seleciona e rola até o caminho na árvore (usado após duplicar)."""
        src_idx = self._model.index(caminho)
        if not src_idx.isValid():
            return
        proxy_idx = self._proxy.mapFromSource(src_idx)
        if not proxy_idx.isValid():
            return
        self._tree.setCurrentIndex(proxy_idx)
        self._tree.scrollTo(proxy_idx)

    # ──────────────────────────────────────────────────────────────────
    # Seleção múltipla
    # ──────────────────────────────────────────────────────────────────

    def _caminhos_selecionados(self) -> list[str]:
        """Retorna lista de caminhos de todos os itens selecionados."""
        indices  = self._tree.selectionModel().selectedRows()
        resultado = []
        for idx in indices:
            c = self._model.filePath(self._proxy.mapToSource(idx))
            if c:
                resultado.append(c)
        return resultado

    def _copiar(self, caminho: str):
        """Copia os itens selecionados (ou o caminho passado) para o clipboard interno."""
        selecionados = self._caminhos_selecionados()
        self._clipboard_caminhos = selecionados if selecionados else [caminho]
        self._clipboard_recortar = False

    def _recortar(self, caminho: str):
        """Marca os itens selecionados (ou o caminho passado) para mover ao colar."""
        selecionados = self._caminhos_selecionados()
        self._clipboard_caminhos = selecionados if selecionados else [caminho]
        self._clipboard_recortar = True

    def _copiar_caminho(self, caminho: str):
        """Copia o caminho absoluto para o clipboard do sistema (Ctrl+C normal)."""
        QGuiApplication.clipboard().setText(os.path.abspath(caminho))

    def _duplicar(self, caminho: str):
        """Duplica arquivo ou pasta na mesma pasta de origem."""
        if not caminho or not os.path.exists(caminho):
            return
        pasta = os.path.dirname(caminho)
        nome_base = os.path.basename(caminho)
        nome, ext = os.path.splitext(nome_base)
        destino   = os.path.join(pasta, f"{nome}_copia{ext}")
        contador  = 1
        while os.path.exists(destino):
            destino = os.path.join(pasta, f"{nome}_copia{contador}{ext}")
            contador += 1
        try:
            if os.path.isfile(caminho):
                shutil.copy2(caminho, destino)
            else:
                shutil.copytree(caminho, destino)
            self._historico.append(("colar", destino))
            QTimer.singleShot(250, lambda d=destino: self._selecionar_no_tree(d))
        except Exception as e:
            QMessageBox.critical(self, "Erro ao duplicar", str(e))

    def _colar(self):
        origens = [c for c in self._clipboard_caminhos if os.path.exists(c)]
        if not origens:
            return

        indice      = self._tree.currentIndex()
        caminho_sel = (
            self._model.filePath(self._proxy.mapToSource(indice))
            if indice.isValid()
            else self._caminho_atual
        )
        pasta_dest = caminho_sel if os.path.isdir(caminho_sel) else os.path.dirname(caminho_sel)

        erros = []
        for origem in origens:
            nome_base = os.path.basename(origem)
            nome, ext = os.path.splitext(nome_base)
            destino   = os.path.join(pasta_dest, nome_base)
            contador  = 1
            while os.path.exists(destino):
                destino = os.path.join(pasta_dest, f"{nome} ({contador}){ext}")
                contador += 1
            try:
                if self._clipboard_recortar:
                    shutil.move(origem, destino)
                    self._historico.append(("recortar", origem, destino))
                else:
                    if os.path.isfile(origem):
                        shutil.copy2(origem, destino)
                    else:
                        shutil.copytree(origem, destino)
                    self._historico.append(("colar", destino))
            except Exception as e:
                erros.append(f"{nome_base}: {e}")

        if self._clipboard_recortar:
            # cut é one-shot: limpa clipboard após mover
            self._clipboard_caminhos = []
            self._clipboard_recortar = False

        if erros:
            QMessageBox.critical(self, "Erro ao colar", "\n".join(erros))

    def _apagar_selecionados(self):
        """Apaga todos os itens selecionados. Se apenas um, usa mensagem singular."""
        caminhos = self._caminhos_selecionados()
        if not caminhos:
            # fallback: item com foco
            indice = self._tree.currentIndex()
            if not indice.isValid():
                return
            c = self._model.filePath(self._proxy.mapToSource(indice))
            if c:
                caminhos = [c]
        if not caminhos:
            return

        if len(caminhos) == 1:
            self._apagar(caminhos[0])
            return

        resp = QMessageBox.question(
            self,
            "Apagar",
            f"Apagar {len(caminhos)} itens selecionados?\n(Ctrl+Z desfaz cada um)",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        pasta_trash = os.path.join(self._caminho_atual, ".hein", "lixeira")
        erros = []
        for caminho in caminhos:
            try:
                os.makedirs(pasta_trash, exist_ok=True)
                nome = os.path.basename(caminho)
                base, ext = os.path.splitext(nome)
                destino = os.path.join(pasta_trash, nome)
                contador = 1
                while os.path.exists(destino):
                    destino = os.path.join(pasta_trash, f"{base}_{contador}{ext}")
                    contador += 1
                shutil.move(caminho, destino)
                self._historico.append(("delete", caminho, destino))
            except Exception as e:
                erros.append(f"{os.path.basename(caminho)}: {e}")
        if erros:
            QMessageBox.critical(self, "Erro ao apagar", "\n".join(erros))

    def _apagar(self, caminho: str):
        nome = os.path.basename(caminho)
        tipo = "arquivo" if os.path.isfile(caminho) else "pasta"
        resp = QMessageBox.question(
            self,
            "Apagar",
            f"Apagar {tipo} '{nome}'?\n(Ctrl+Z desfaz)",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        try:
            pasta_trash = os.path.join(self._caminho_atual, ".hein", "lixeira")
            os.makedirs(pasta_trash, exist_ok=True)
            base, ext   = os.path.splitext(nome)
            destino     = os.path.join(pasta_trash, nome)
            contador    = 1
            while os.path.exists(destino):
                destino = os.path.join(pasta_trash, f"{base}_{contador}{ext}")
                contador += 1
            shutil.move(caminho, destino)
            self._historico.append(("delete", caminho, destino))
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        # Bug #5: fecha abas abertas cujo arquivo foi movido para a lixeira.
        # Inclui a pasta inteira se caminho era um diretório.
        janela = self.window()
        tabs   = getattr(janela, "tabs", None)
        if tabs is not None:
            cam_norm = os.path.normcase(os.path.abspath(caminho))
            indices_fechar = []
            for i, editor in list(tabs.editores.items()):
                fp = getattr(editor, "file_path", None)
                if not fp:
                    continue
                fp_norm = os.path.normcase(os.path.abspath(fp))
                # Cobre arquivo direto ou qualquer arquivo dentro da pasta
                if fp_norm == cam_norm or fp_norm.startswith(cam_norm + os.sep):
                    indices_fechar.append(i)
            # Fecha em ordem reversa para não deslocar índices antes da hora
            for i in sorted(indices_fechar, reverse=True):
                try:
                    tabs.fechar_aba(i)
                except Exception:
                    pass

    def _desfazer(self):
        if not self._historico:
            return
        acao = self._historico.pop()
        try:
            if acao[0] == "delete":
                _, origem, trash = acao
                shutil.move(trash, origem)
            elif acao[0] == "rename":
                _, caminho_atual, caminho_original = acao
                os.rename(caminho_atual, caminho_original)
            elif acao[0] == "recortar":
                _, origem, destino = acao
                shutil.move(destino, origem)
            elif acao[0] == "colar":
                _, destino = acao
                if os.path.isfile(destino):
                    os.remove(destino)
                else:
                    shutil.rmtree(destino)
        except Exception as e:
            QMessageBox.critical(self, "Erro ao desfazer", str(e))

    def _mostrar_no_explorador(self, caminho: str):
        if not caminho:
            return
        if os.name == "nt":
            import subprocess as _sp
            if os.path.isfile(caminho):
                _sp.run(["explorer", "/select,", os.path.normpath(caminho)])
            else:
                _sp.run(["explorer", os.path.normpath(caminho)])
        elif os.name == "posix":
            pasta = caminho if os.path.isdir(caminho) else os.path.dirname(caminho)
            import subprocess as _sp
            _sp.run(["xdg-open", pasta], check=False)

    def _restaurar_item_lixeira(self, caminho_trash: str):
        """Restaura um arquivo específico da lixeira — pergunta onde salvar."""
        from PySide6.QtCore import QSettings
        nome      = os.path.basename(caminho_trash)
        _settings = QSettings("hein", "hein_IDE")
        # IMP-11: prioriza a pasta atual do FileTree; sem pasta aberta, cai na
        # última pasta usada para restaurar itens da lixeira (QSettings)
        _dir_inicial = self._caminho_atual or _settings.value("ultima_pasta_filetree", "")
        destino, _ = QFileDialog.getSaveFileName(
            self,
            f"Restaurar '{nome}' para...",
            os.path.join(_dir_inicial or "", nome),
        )
        if not destino:
            return
        _settings.setValue("ultima_pasta_filetree", os.path.dirname(destino))
        try:
            shutil.move(caminho_trash, destino)
            self._historico.append(("delete", destino, caminho_trash))
        except Exception as e:
            QMessageBox.critical(self, "Erro ao restaurar", str(e))

    def _esvaziar_lixeira(self):
        """Apaga permanentemente todos os itens de .hein/lixeira."""
        pasta_trash = (
            os.path.join(self._caminho_atual, ".hein", "lixeira")
            if self._caminho_atual
            else ""
        )
        if not pasta_trash or not os.path.isdir(pasta_trash):
            return

        itens = os.listdir(pasta_trash)
        if not itens:
            return

        resp = QMessageBox.question(
            self,
            "Esvaziar Lixeira",
            f"Apagar permanentemente {len(itens)} item(ns)?\nEsta ação não pode ser desfeita.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        try:
            for nome in itens:
                alvo = os.path.join(pasta_trash, nome)
                if os.path.isfile(alvo):
                    os.remove(alvo)
                else:
                    shutil.rmtree(alvo)
            self._historico = [
                a for a in self._historico
                if not (a[0] == "delete" and a[2].startswith(pasta_trash))
            ]
            try:
                os.rmdir(pasta_trash)
            except OSError:
                pass
        except Exception as e:
            QMessageBox.critical(self, "Erro ao esvaziar lixeira", str(e))

    # ──────────────────────────────────────────────────────────────────
    # Git status via QThread
    # ──────────────────────────────────────────────────────────────────

    def _disparar_git_status(self):
        if not self._caminho_atual:
            return
        if not os.path.isdir(os.path.join(self._caminho_atual, ".git")):
            return
        try:
            if self._thread and self._thread.isRunning():
                return
        except RuntimeError:
            self._thread = None

        self._thread = QThread()
        self._worker = _WorkerGit(self._caminho_atual)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.rodar)
        self._worker.concluido.connect(self._ao_receber_status)
        self._worker.concluido.connect(self._thread.quit)
        self._thread.finished.connect(self._limpar_thread)

        self._thread.start()

    def _limpar_thread(self):
        self._worker = None
        self._thread = None

    def _ao_receber_status(self, novo_status: dict):
        self._status_git.clear()
        self._status_git.update(novo_status)
        self._tree.viewport().update()

    # ──────────────────────────────────────────────────────────────────
    # Tamanho do projeto/.venv via QThread (não pode rodar na UI thread —
    # os.walk() em projeto grande trava a janela)
    # ──────────────────────────────────────────────────────────────────

    def _disparar_calculo_tamanho(self):
        """Dispara o cálculo em background para self._caminho_atual.

        NÃO espera o worker anterior terminar antes de disparar um novo —
        se o usuário trocar de projeto (ou reabrir o mesmo) enquanto o
        os.walk() do projeto anterior ainda está rodando, o pedido mais
        recente precisa "ganhar". QThread.quit() não interrompe um os.walk()
        já em andamento (só afeta o loop de eventos da QThread, não código
        síncrono dentro de rodar()) — então o worker antigo é movido pra
        `_threads_tamanho_antigas` e deixado terminar sozinho; seu resultado
        é descartado em _ao_receber_tamanhos() se não corresponder mais ao
        projeto atual (ver o parâmetro `caminho_alvo`).
        """
        if not self._caminho_atual:
            return

        # Move o worker/thread atual (se ainda rodando) pra lista de
        # "antigos" em vez de simplesmente sobrescrever self._thread_tamanho:
        # se eu apenas reatribuísse, a única referência Python à thread
        # antiga se perderia e o GC destruiria uma QThread ainda em
        # execução (o mesmo bug do ThreadDiffGutter, agora aqui).
        try:
            ainda_rodando = bool(self._thread_tamanho and self._thread_tamanho.isRunning())
        except RuntimeError:
            ainda_rodando = False
            self._thread_tamanho = None

        if ainda_rodando:
            antigo_thread = self._thread_tamanho
            antigo_worker = self._worker_tamanho
            self._threads_tamanho_antigas.append((antigo_thread, antigo_worker))
            antigo_thread.quit()

            def _remover_antigo(t=antigo_thread, w=antigo_worker):
                self._threads_tamanho_antigas = [
                    par for par in self._threads_tamanho_antigas if par[0] is not t
                ]
                # O worker ja recebe deleteLater() pelo finished da thread.
                # Nao tente destruí-lo novamente: o wrapper pode estar morto.

            antigo_thread.finished.connect(_remover_antigo)

        caminho_alvo = self._caminho_atual
        venv_path = os.path.join(caminho_alvo, ".venv")
        thread = QThread()
        worker = _WorkerTamanhoPasta(caminho_alvo, venv_path)
        worker.moveToThread(thread)

        thread.started.connect(worker.rodar)
        worker.concluido.connect(
            lambda tp, tv, alvo=caminho_alvo: self._ao_receber_tamanhos(alvo, tp, tv)
        )
        worker.concluido.connect(thread.quit)
        thread.finished.connect(self._limpar_thread_tamanho)
        thread.finished.connect(worker.deleteLater)
        # BUG-202807-06: NÃO conectar finished → thread.deleteLater.
        # finished é emitido dentro de QThreadPrivate::finish() enquanto
        # d->running ainda pode estar true nos bastidores. deleteLater
        # enfileira ~QThread() no event loop; se processado durante esse
        # janela → qFatal() → abort() → crash.
        # _limpar_thread_tamanho() seta self._thread_tamanho = None; o GC
        # do Python destrói o wrapper só depois que finished foi entregue
        # ao main thread (queued connection = 1 ciclo de atraso), momento
        # em que d->running já é false → sem qFatal. Padrão idêntico ao
        # _disparar_git_status() que nunca usou deleteLater e funciona.

        self._thread_tamanho = thread
        self._worker_tamanho = worker
        thread.start()

    def _limpar_thread_tamanho(self):
        self._worker_tamanho = None
        self._thread_tamanho = None

    @staticmethod
    def _fmt_mb(mb: float) -> str:
        """Converte MB para a unidade mais legível (KB / MB / GB)."""
        if mb < 1.0:
            return f"{mb * 1024:.0f} KB"
        if mb < 1024.0:
            return f"{mb:.1f} MB"
        return f"{mb / 1024:.2f} GB"

    def _ao_receber_tamanhos(self, caminho_alvo: str, tamanho_proj: float, tamanho_venv: float):
        # Descarta resultado de um pedido antigo: o usuário já trocou de
        # projeto enquanto esse os.walk() ainda estava rodando. Sem essa
        # checagem, o worker antigo sobrescreveria o rótulo/tamanho do
        # projeto NOVO com o tamanho do projeto ANTERIOR quando terminasse.
        if caminho_alvo != self._caminho_atual:
            return

        nome = getattr(self, "_nome_projeto_exibicao", "") or os.path.basename(self._caminho_atual)
        self._barra_esquerda.set_projeto(f"{nome} [{self._fmt_mb(tamanho_proj)}]")

        if tamanho_venv > 0:
            venv_path = os.path.join(caminho_alvo, ".venv")
            indice_venv = self._model.index(venv_path)
            if indice_venv.isValid():
                self._model.setData(indice_venv, f".venv [{self._fmt_mb(tamanho_venv)}]", Qt.DisplayRole)

    # ──────────────────────────────────────────────────────────────────
    # Encerramento — chamado pelo MainWindow.closeEvent antes de fechar
    # ──────────────────────────────────────────────────────────────────

    def encerrar_threads_bg(self):
        """Para as QThreads deste painel (git status + tamanho) antes do
        painel ser destruído. PainelArquivos não é janela de topo, então
        seu próprio closeEvent (se existisse) nunca dispararia ao fechar o
        app — precisa ser chamado explicitamente pelo MainWindow.closeEvent.
        """
        for thread, worker in [(self._thread, self._worker), (self._thread_tamanho, self._worker_tamanho)]:
            if thread is None:
                continue
            try:
                encerrar_thread(thread)
            except RuntimeError:
                pass

        antigas_vivas = []
        for thread, worker in list(self._threads_tamanho_antigas):
            try:
                encerrar_thread(thread)
                if thread.isRunning():
                    antigas_vivas.append((thread, worker))
            except RuntimeError:
                pass
        self._threads_tamanho_antigas = antigas_vivas

    # ──────────────────────────────────────────────────────────────────
    # Tema / pintura
    # ──────────────────────────────────────────────────────────────────

    def _aplicar_tema(self):
        t           = tema_global()
        fundo       = t.cor("painel_arquivos.fundo", t.cor("editor.fundo", "#0a0a0a"))
        texto       = t.cor("painel_arquivos.texto", t.cor("editor.texto", "#e0e0e0"))
        texto_fraco = t.cor("painel_arquivos.texto_fraco", t.cor("interface.texto_fraco", "#888888"))
        hover       = t.cor("painel_arquivos.item_hover", t.cor("interface.fundo_item_hover", "#1a1a2e"))
        selecionado = t.cor("painel_arquivos.item_selecionado", t.cor("editor.selecao", "#264f78"))
        rodape      = t.cor("painel_arquivos.rodape_texto", t.cor("interface.texto_fraco", "#555555"))

        self._fundo_cor_ini = fundo
        self._fundo_cor_mei = t.cor("painel_arquivos.fundo_grad_meio", "")
        self._fundo_cor_fim = t.cor("painel_arquivos.fundo_grad_fim", "")
        self.update()

        self._status.setStyleSheet(
            f"color: {rodape}; font-size: 10px; padding: 4px 8px;"
        )

        if self._barra_esquerda:
            self._barra_esquerda.atualizar_tema()

        self.setStyleSheet(f"""
            QWidget   {{ background-color: transparent; }}
            QLabel    {{ color: {texto_fraco}; }}
            QTreeView {{
                background-color: transparent;
                color: {texto};
                border: none;
            }}
            QTreeView::item          {{ padding: 2px; }}
            QTreeView::item:hover    {{ background-color: {hover}; }}
            QTreeView::item:selected {{ background-color: {selecionado}; }}

            QTreeView::branch:has-siblings:!adjoins-item {{
                border-image: none;
                border-left: 1px solid {rodape};
            }}
            QTreeView::branch:has-siblings:adjoins-item {{
                border-image: none;
                border-left: 1px solid {rodape};
            }}
            QTreeView::branch:!has-children:!has-siblings:adjoins-item,
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {{
                image: url(none);
                border-image: none;
            }}

        """)

        self._sb_oculta = "QScrollBar:vertical { width: 0px; background: transparent; }"
        self._sb_visivel = (
            f"QScrollBar:vertical {{ width: 6px; background: transparent; }}"
            f"QScrollBar::handle:vertical {{ background: {selecionado}; "
            f"border-radius: 3px; min-height: 20px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}"
        )
        self._tree.verticalScrollBar().setStyleSheet(self._sb_oculta)

    def paintEvent(self, event):
        painter = QPainter(self)
        cor_ini = getattr(self, "_fundo_cor_ini", "#0a0a0a")
        cor_fim = getattr(self, "_fundo_cor_fim", "")

        if cor_fim:
            cor_mei = getattr(self, "_fundo_cor_mei", "")
            grad    = QLinearGradient(0, 0, 0, self.height())
            grad.setColorAt(0.0, QColor(cor_ini))
            if cor_mei:
                grad.setColorAt(0.5, QColor(cor_mei))
            grad.setColorAt(1.0, QColor(cor_fim))
            painter.fillRect(self.rect(), QBrush(grad))
        else:
            painter.fillRect(self.rect(), QColor(cor_ini))

        painter.end()

    def atualizar_tema(self, tema: dict):
        self._tema = tema
        self._aplicar_tema()

    # ──────────────────────────────────────────────────────────────────
    # API pública
    # ──────────────────────────────────────────────────────────────────

    def set_projeto(self, caminho: str):
        self._caminho_atual = caminho
        self._status_git.clear()
        self._timer_git.stop()

        if not caminho or not os.path.isdir(caminho):
            self._barra_esquerda.set_projeto("— projeto —")
            self._model.setRootPath("")
            self._tree.setRootIndex(self._model.index(""))
            self._status.setText("Sem projeto")
            return

        nome_pasta  = os.path.basename(caminho)
        nome_limpo  = (nome_pasta[:15] + "...") if len(nome_pasta) > 18 else nome_pasta
        self._nome_projeto_exibicao = nome_limpo
        # Mostra o nome sem o tamanho ainda — o cálculo real (os.walk) roda
        # em background e atualiza o rótulo quando terminar (ver
        # _disparar_calculo_tamanho). Fazer isso direto aqui travava a UI.
        self._barra_esquerda.set_projeto(nome_limpo)

        self._model.setRootPath(caminho)
        self._tree.setRootIndex(self._proxy.mapFromSource(self._model.index(caminho)))
        self._tree.setExpanded(self._proxy.mapFromSource(self._model.index(caminho)), True)
        # sort() não é chamado aqui — o proxy já tem sort(0, AscendingOrder) do
        # __init__ e chamar novamente APÓS setRootPath() causa a race condition
        # que dispara "QSortFilterProxyModel: invalid inserted rows reported by
        # source model" (a população async do QFileSystemModel emite
        # rowsAboutToBeInserted/rowsInserted com contagens momentaneamente
        # inconsistentes com o estado interno do proxy durante o resort forçado).
        self._disparar_git_status()
        self._timer_git.start()
        self._disparar_calculo_tamanho()

    def revelar_arquivo(self, caminho: str):
        """Seleciona e revela o arquivo na árvore sem emitir sinais de abertura."""
        if not caminho or not self._caminho_atual:
            return
        src_indice = self._model.index(caminho)
        if not src_indice.isValid():
            return
        indice = self._proxy.mapFromSource(src_indice)

        pai = indice.parent()
        while pai.isValid():
            self._tree.expand(pai)
            pai = pai.parent()

        self._tree.blockSignals(True)
        self._tree.setCurrentIndex(indice)
        self._tree.scrollTo(indice, QTreeView.EnsureVisible)
        self._tree.blockSignals(False)

    # Pastas pesadas/irrelevantes — nunca expandir automaticamente ao filtrar,
    # senão o QFileSystemModel é forçado a ler .venv/site-packages inteiro
    # (milhares de arquivos) e a UI trava a cada tecla digitada em "*busca".
    _PASTAS_EXCLUIDAS_FILTRO = {".venv", ".git", "__pycache__", "node_modules"}

    def _filtrar_arvore(self, texto: str):
        if texto:
            self._model.setNameFilters([f"*{texto}*"])
            self._model.setNameFilterDisables(False)
            # setUpdatesEnabled(False) durante o lote de expand() evita que o
            # Qt rode a animação de abrir/fechar pasta por pasta a cada tecla
            # digitada — só repinta uma vez, no final, com o resultado pronto.
            self._tree.setUpdatesEnabled(False)
            try:
                # Começa na raiz do PROJETO (self._tree.rootIndex()), não na
                # raiz absoluta do disco (QModelIndex()) — senão a varredura
                # procura no lugar errado e nunca alcança os arquivos do projeto.
                self._expandir_filtrado(self._tree.rootIndex())
            finally:
                self._tree.setUpdatesEnabled(True)
        else:
            self._model.setNameFilters([])
            self._model.setNameFilterDisables(False)
            self._colapsar_tudo()

    def _expandir_filtrado(self, indice_pai=QModelIndex()):
        """Expande recursivamente os resultados do filtro ao vivo, pulando
        pastas pesadas (.venv, .git, __pycache__, node_modules) para não
        forçar o QFileSystemModel a ler site-packages inteiro a cada tecla.
        Isso só afeta o que aparece expandido ENQUANTO o usuário digita —
        não impede que um arquivo dentro de .venv seja encontrado no Enter
        (ver _abrir_primeiro_resultado, que varre a árvore inteira)."""
        for row in range(self._proxy.rowCount(indice_pai)):
            idx = self._proxy.index(row, 0, indice_pai)
            src = self._proxy.mapToSource(idx)
            if not self._model.isDir(src):
                continue
            if self._model.fileName(src) in self._PASTAS_EXCLUIDAS_FILTRO:
                continue
            self._tree.expand(idx)
            self._expandir_filtrado(idx)

    def _abrir_primeiro_resultado(self) -> str:
        """Retorna o caminho do primeiro arquivo (não-pasta) que casa com o
        filtro "*", para o Enter na BarraCentral abrir/focar direto.
        Varre a árvore INTEIRA a partir da raiz do PROJETO (inclusive
        .venv/.git/etc) — diferente do filtro ao vivo, isso roda uma vez só
        ao confirmar, então o custo de entrar em pastas pesadas é aceitável."""
        return self._primeiro_arquivo_recursivo(self._tree.rootIndex())

    def _buscar_todos_resultados(self, limite: int = 200) -> list:
        """Retorna TODOS os arquivos que casam com o filtro "*" (até `limite`),
        varrendo a árvore inteira a partir da raiz do projeto. Usado para
        listar na PainelBuscaGlobal quando há mais de um arquivo com o mesmo
        nome em pastas diferentes — sem isso, o Enter só abriria o primeiro
        que encontrasse, escondendo os outros do usuário."""
        resultados = []
        self._coletar_arquivos_recursivo(self._tree.rootIndex(), resultados, limite)
        return resultados

    def _coletar_arquivos_recursivo(self, indice_pai, resultados: list, limite: int):
        for row in range(self._proxy.rowCount(indice_pai)):
            if len(resultados) >= limite:
                return
            idx = self._proxy.index(row, 0, indice_pai)
            src = self._proxy.mapToSource(idx)
            if not src.isValid():
                continue
            if self._model.isDir(src):
                self._coletar_arquivos_recursivo(idx, resultados, limite)
            else:
                resultados.append(self._model.filePath(src))

    def _primeiro_arquivo_recursivo(self, indice_pai) -> str:
        for row in range(self._proxy.rowCount(indice_pai)):
            idx = self._proxy.index(row, 0, indice_pai)
            src = self._proxy.mapToSource(idx)
            if not src.isValid():
                continue
            if self._model.isDir(src):
                encontrado = self._primeiro_arquivo_recursivo(idx)
                if encontrado:
                    return encontrado
            else:
                return self._model.filePath(src)
        return ""

    def packs_disponiveis(self) -> list:
        return list(PACKS_ICONES.keys())

    def trocar_pack_icones(self, nome: str):
        if nome not in PACKS_ICONES:
            return
        _CFG._PACK_ATIVO = nome
        _cache_icones.clear()

        raiz = self._caminho_atual
        self._tree.setItemDelegate(None)

        self._model = _IconProvider()
        self._model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)

        self._proxy = _ProxyOrdem()
        self._proxy.setSourceModel(self._model)
        self._proxy.setDynamicSortFilter(True)
        # sort() configurado ANTES de setRootPath() — evita resort forçado
        # durante a população assíncrona do QFileSystemModel, que causaria
        # "QSortFilterProxyModel: invalid inserted rows reported by source model".
        self._proxy.sort(0, Qt.AscendingOrder)

        self._tree.setModel(self._proxy)
        self._tree.hideColumn(1)
        self._tree.hideColumn(2)
        self._tree.hideColumn(3)
        self._tree.setHeaderHidden(True)

        self._delegate = _DelegateGit(
            self._model, self._proxy, self._status_git, self._staging_checks
        )
        self._delegate.set_modo_staging(self._modo_staging)
        self._tree.setItemDelegate(self._delegate)

        if raiz:
            self._model.setRootPath(raiz)
            self._tree.setRootIndex(self._proxy.mapFromSource(self._model.index(raiz)))
            self._tree.setExpanded(self._proxy.mapFromSource(self._model.index(raiz)), True)
        else:
            self._model.setRootPath("")
            self._tree.setRootIndex(self._proxy.mapFromSource(self._model.index("")))

    def atualizar_status_git(self):
        """Chamada externa — ex: após commit/push/pull no PainelGitHub."""
        self._disparar_git_status()

    # ──────────────────────────────────────────────────────────────────
    # Staging mode — acionado pelo PainelAbasInferior ao entrar/sair
    # da aba Git.
    # ──────────────────────────────────────────────────────────────────

    def entrar_modo_staging(self, status_git: dict | None = None) -> None:
        """Entra no modo staging: exibe checkboxes nos arquivos modificados
        e mostra a barra 'Marcar tudo / Desmarcar tudo'."""
        self._modo_staging = True
        fonte = status_git if status_git is not None else self._status_git

        # Pré-marca todos os arquivos rastreáveis (não pastas)
        self._staging_checks.clear()
        for caminho_lower, status in fonte.items():
            # Exclui as entradas de pasta (adicionadas pelo Feature 2)
            # — pasta não tem extensão E corresponde a um diretório
            # Critério: pasta tem subchave no dict (será pai de algum arquivo)
            # Na prática, basta checar se é um arquivo (tem extensão ou existe no FS)
            if not self._eh_pasta_no_status(caminho_lower):
                self._staging_checks[caminho_lower] = True

        self._delegate.set_modo_staging(True)
        self._btn_marcar_tudo.setVisible(True)
        self._btn_desmarcar_tudo.setVisible(True)
        self._tree.viewport().update()

    def sair_modo_staging(self) -> None:
        """Sai do modo staging: remove checkboxes e esconde a barra."""
        self._modo_staging = False
        self._staging_checks.clear()
        self._delegate.set_modo_staging(False)
        self._btn_marcar_tudo.setVisible(False)
        self._btn_desmarcar_tudo.setVisible(False)
        self._tree.viewport().update()

    def arquivos_staging_selecionados(self) -> list[str]:
        """Retorna lista de caminhos absolutos dos arquivos marcados para stage."""
        return [c for c, marcado in self._staging_checks.items() if marcado]

    def _staging_marcar_tudo(self, marcado: bool) -> None:
        for caminho_lower in list(self._staging_checks):
            self._staging_checks[caminho_lower] = marcado
        self._tree.viewport().update()

    def _eh_pasta_no_status(self, caminho_lower: str) -> bool:
        """Retorna True se a chave do status_git corresponde a uma pasta.
        As entradas de pasta não têm '.' após a última '/' (sem extensão comum)
        mas isso não é 100% confiável. Verificação complementar: se alguma
        chave do dict começa com 'caminho_lower + /', é uma pasta."""
        prefixo = caminho_lower.rstrip("/") + "/"
        return any(k.startswith(prefixo) for k in self._status_git)

    # ──────────────────────────────────────────────────────────────────
    # Helpers internos
    # ──────────────────────────────────────────────────────────────────

    def _toggle_filtro_gerados(self, ativo: bool):
        self._proxy.set_filtrar_gerados(ativo)

    def _expandir_tudo(self):
        self._tree.expandAll()

    def _colapsar_tudo(self):
        self._tree.collapseAll()
        if self._caminho_atual:
            self._tree.setExpanded(
                self._proxy.mapFromSource(self._model.index(self._caminho_atual)), True
            )

    def _limpar_arquivos_patch(self):
        """Remove __pycache__ (recursivo), .bak e _patch* de todo o projeto."""
        if not self._caminho_atual or not os.path.isdir(self._caminho_atual):
            return

        pycaches: list[str] = []
        baks:     list[str] = []
        patches:  list[str] = []

        for raiz, dirs, arquivos in os.walk(self._caminho_atual):
            # nunca entra na lixeira da própria hein
            dirs[:] = [d for d in dirs if d != ".hein"]
            # coleta __pycache__ e impede descida dentro deles
            for d in list(dirs):
                if d == "__pycache__":
                    pycaches.append(os.path.join(raiz, d))
                    dirs.remove(d)
            for f in arquivos:
                if f.endswith(".bak"):
                    baks.append(os.path.join(raiz, f))
                elif f.startswith("_patch"):
                    patches.append(os.path.join(raiz, f))

        total = len(pycaches) + len(baks) + len(patches)
        if total == 0:
            QMessageBox.information(
                self, "Limpar projeto",
                "Nenhum arquivo gerado encontrado.",
            )
            return

        linhas = []
        if pycaches:
            linhas.append(f"• {len(pycaches)} pasta(s) __pycache__  (apagadas permanentemente)")
        if baks:
            linhas.append(f"• {len(baks)} arquivo(s) .bak  → lixeira")
        if patches:
            linhas.append(f"• {len(patches)} arquivo(s) _patch*  → lixeira")

        resp = QMessageBox.question(
            self,
            "Limpar arquivos gerados",
            "Remover do projeto:\n\n" + "\n".join(linhas),
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        erros = []

        # __pycache__ → apaga direto (bytecode, Python recria automaticamente)
        for caminho in pycaches:
            try:
                shutil.rmtree(caminho, ignore_errors=True)
            except Exception as e:
                erros.append(f"{os.path.basename(caminho)}: {e}")

        # .bak e _patch* → lixeira (desfazível com Ctrl+Z)
        pasta_trash = os.path.join(self._caminho_atual, ".hein", "lixeira")
        for caminho in baks + patches:
            try:
                os.makedirs(pasta_trash, exist_ok=True)
                nome      = os.path.basename(caminho)
                base, ext = os.path.splitext(nome)
                destino   = os.path.join(pasta_trash, nome)
                contador  = 1
                while os.path.exists(destino):
                    destino = os.path.join(pasta_trash, f"{base}_{contador}{ext}")
                    contador += 1
                shutil.move(caminho, destino)
                self._historico.append(("delete", caminho, destino))
            except Exception as e:
                erros.append(f"{os.path.basename(caminho)}: {e}")

        if erros:
            QMessageBox.critical(self, "Erro ao limpar", "\n".join(erros))
