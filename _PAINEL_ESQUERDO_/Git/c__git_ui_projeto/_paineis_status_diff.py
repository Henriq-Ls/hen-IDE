# 📁 _PAINEL_ESQUERDO_/Git/c__git_ui_projeto/_paineis_status_diff.py
"""
Painéis de Status (arquivos modificados) e Diferenças (diff viewer).
Compartilha _ESTILO_TREE e _COR_STATUS com os demais painéis.
"""
from PySide6.QtCore    import Qt, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTreeWidget, QTreeWidgetItem,
    QPushButton, QMenu, QLineEdit, QTextEdit, QSplitter,
)
from PySide6.QtGui import QColor
from ..git_gerente      import GerenciadorGit
from ..git_terminal     import GitTerminal
from ..git_ui_utils     import _botao
from _UTILITARIOS_.icones       import icone_tema
from _UTILITARIOS_.hein_pou_pap import HeinPopup
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import (
    VERDE, COR_INFO, COR_OUTLINE_OBJETO_JSON, COR_SINTAXE_VARIAVEL_ESPECIAL,
    COR_SINTAXE_PALAVRA_CHAVE, COR_GIT_TEXTO_NEUTRO, FONTE_MONO,
)

# ══════════════════════════════════════════════════════════════════════
# Constantes compartilhadas
# ══════════════════════════════════════════════════════════════════════

_ESTILO_TREE = (
    "QTreeWidget { background:#0d0d0d; color:#c9d1d9; border:none; font-size:10px;"
    " font-family:'" + FONTE_MONO + "','Consolas',monospace; }"
    " QTreeWidget::item { padding:2px 4px; }"
    " QTreeWidget::item:hover { background:#1a1a2e; }"
    " QTreeWidget::item:selected { background:#1e3a5f; }"
    " QHeaderView::section { background:#0d0d0d; color:#555;"
    " border:none; font-size:10px; padding:2px 4px; }"
)

_COR_STATUS = {
    "modificado": COR_OUTLINE_OBJETO_JSON,
    "novo":       VERDE,
    "deletado":   COR_SINTAXE_VARIAVEL_ESPECIAL,
    "renomeado":  COR_INFO,
    "copiado":    COR_SINTAXE_PALAVRA_CHAVE,
}

# ══════════════════════════════════════════════════════════════════════
# Painel de Status (arquivos modificados)
# ══════════════════════════════════════════════════════════════════════

class _PainelStatus(QWidget):
    """
    Aba de Status — lista arquivos modificados com menu de contexto.
    Preparar individual, Remover, Descartar.
    """

    def __init__(self, git: GerenciadorGit, terminal: GitTerminal, parent=None):
        super().__init__(parent)
        self._git           = git
        self._terminal      = terminal
        self._caminho       = ""
        self._ocultar_ruido = True   # oculta _* e __pycache__ por padrão
        self._construir()

    def _construir(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._arvore = QTreeWidget()
        self._arvore.setHeaderHidden(True)
        self._arvore.setStyleSheet(_ESTILO_TREE)
        self._arvore.setContextMenuPolicy(Qt.CustomContextMenu)
        self._arvore.customContextMenuRequested.connect(self._menu_contexto)
        self._arvore.setToolTip("Botão direito no arquivo → preparar, descartar, remover da fila")
        lay.addWidget(self._arvore, 1)

        # Barra: filtro de ruído + expandir/recolher todos
        bar_acao = QWidget()
        bar_acao.setStyleSheet("background:#0a0a0a; border-top:1px solid #1a1a1a;")
        lay_acao = QHBoxLayout(bar_acao)
        lay_acao.setContentsMargins(6, 3, 6, 3)
        lay_acao.setSpacing(4)

        self._btn_ruido = _botao("_arquivos")
        self._btn_ruido.setIcon(icone_tema("mdi.filter-variant"))
        self._btn_ruido.setIconSize(QSize(14, 14))
        self._btn_ruido.setFixedHeight(20)
        self._btn_ruido.setCheckable(True)
        self._btn_ruido.setChecked(self._ocultar_ruido)
        self._btn_ruido.setToolTip(
            "Ocultar/mostrar arquivos que começam com _ e pastas __pycache__"
        )
        self._btn_ruido.clicked.connect(self._toggle_ruido)
        lay_acao.addWidget(self._btn_ruido)
        lay_acao.addStretch()

        btn_exp = _botao("")
        btn_exp.setIcon(icone_tema("mdi.arrow-expand-all"))
        btn_col = _botao("")
        btn_col.setIcon(icone_tema("mdi.arrow-collapse-all"))
        btn_exp.setFixedSize(22, 20)
        btn_col.setFixedSize(22, 20)
        btn_exp.setToolTip("Expandir todos")
        btn_col.setToolTip("Recolher todos")
        btn_exp.clicked.connect(self._arvore.expandAll)
        btn_col.clicked.connect(self._arvore.collapseAll)
        lay_acao.addWidget(btn_exp)
        lay_acao.addWidget(btn_col)
        lay.addWidget(bar_acao)

        # Botões Preparar tudo / Remover tudo
        bar = QWidget()
        bar.setStyleSheet("background:#0a0a0a; border-top:1px solid #111;")
        lay_bar = QHBoxLayout(bar)
        lay_bar.setContentsMargins(6, 4, 6, 4)
        lay_bar.setSpacing(4)

        btn_stage_all   = _botao("Preparar tudo")
        btn_stage_all.setIcon(icone_tema("mdi.check-all"))
        btn_stage_all.setIconSize(QSize(14, 14))
        btn_unstage_all = _botao("Remover tudo")
        btn_unstage_all.setIcon(icone_tema("mdi.minus-circle-outline"))
        btn_unstage_all.setIconSize(QSize(14, 14))

        btn_stage_all.setFixedHeight(22)
        btn_unstage_all.setFixedHeight(22)
        btn_stage_all.clicked.connect(self._stage_tudo)
        btn_unstage_all.clicked.connect(self._unstage_tudo)

        lay_bar.addWidget(btn_stage_all)
        lay_bar.addWidget(btn_unstage_all)
        lay.addWidget(bar)

        # Botão: limpar arquivos que estão no .gitignore mas ainda rastreados
        bar_limpar = QWidget()
        bar_limpar.setStyleSheet("background:#0a0a0a; border-top:1px solid #111;")
        lay_limpar = QHBoxLayout(bar_limpar)
        lay_limpar.setContentsMargins(6, 3, 6, 3)

        btn_limpar = _botao("🧹 Limpar .gitignore")
        btn_limpar.setFixedHeight(22)
        btn_limpar.setToolTip(
            "Remove do Git os arquivos que você colocou no .gitignore mas que\n"
            "já foram enviados antes (ex: __pycache__, *.pyc, .venv).\n"
            "Os arquivos NÃO são apagados do seu computador — o Git só\n"
            "para de rastreá-los. Faça um commit depois para finalizar."
        )
        btn_limpar.clicked.connect(self._limpar_gitignore)
        lay_limpar.addWidget(btn_limpar)
        lay.addWidget(bar_limpar)

    def atualizar(self, caminho: str):
        self._caminho = caminho
        self._arvore.clear()

        if not caminho:

            return

        arquivos = self._git.arquivos_alterados(caminho)

        r_staged = self._git._executar(["diff", "--cached", "--name-status"], caminho)
        staged_set = set()
        for linha in r_staged.saida.splitlines():
            partes = linha.split("\t")
            if len(partes) >= 2:
                staged_set.add(partes[-1].strip())

        if not arquivos:
            item = QTreeWidgetItem(["  Sem alterações"])
            item.setForeground(0, QColor("#444"))
            self._arvore.addTopLevelItem(item)

            return

        staged   = [a for a in arquivos if a["caminho"] in staged_set]
        unstaged = [a for a in arquivos if a["caminho"] not in staged_set]

        if staged:
            cabec = QTreeWidgetItem([f"  ● Prontos para salvar ({len(staged)})"])
            cabec.setForeground(0, tema_global().qcolor("editor.git_adicionado", VERDE))
            cabec.setFlags(Qt.ItemIsEnabled)
            self._arvore.addTopLevelItem(cabec)
            self._preencher_grupo(cabec, staged, staged=True)
            cabec.setExpanded(True)

        if unstaged:
            cabec2 = QTreeWidgetItem([f"  ● Com alterações ({len(unstaged)})"])
            cabec2.setForeground(0, tema_global().qcolor("editor.git_modificado", COR_OUTLINE_OBJETO_JSON))
            cabec2.setFlags(Qt.ItemIsEnabled)
            self._arvore.addTopLevelItem(cabec2)
            self._preencher_grupo(cabec2, unstaged, staged=False)
            cabec2.setExpanded(True)

    def _preencher_grupo(self, pai: QTreeWidgetItem, arquivos: list, staged: bool):
        """
        Agrupa arquivos por pasta recursivamente.
        __pycache__ começa recolhido; demais pastas começam expandidas.
        Arquivos na raiz do grupo ficam diretamente como filhos de `pai`.
        """
        diretos   = []
        subgrupos = {}

        for arq in arquivos:
            partes = arq["caminho"].replace("\\", "/").split("/", 1)
            if len(partes) == 1:
                diretos.append(arq)
            else:
                pasta, resto = partes
                if pasta not in subgrupos:
                    subgrupos[pasta] = []
                subgrupos[pasta].append(dict(arq, caminho=resto))

        for nome_pasta in sorted(subgrupos):
            eh_ruido = nome_pasta.startswith("_")   # inclui __pycache__
            if self._ocultar_ruido and eh_ruido:
                continue
            filhos   = subgrupos[nome_pasta]
            eh_cache = "__pycache__" in nome_pasta
            cor      = "#333" if (eh_cache or eh_ruido) else "#666"
            node = QTreeWidgetItem([f"  {nome_pasta}/   {len(filhos)}"])
            node.setForeground(0, QColor(cor))
            node.setFlags(Qt.ItemIsEnabled)
            pai.addChild(node)
            self._preencher_grupo(node, filhos, staged)
            node.setExpanded(not eh_cache)

        for arq in sorted(diretos, key=lambda a: a["caminho"].lower()):
            if self._ocultar_ruido and (
                arq["caminho"].startswith("_") or arq["caminho"].endswith(".pyc")
            ):
                continue
            self._add_item(pai, arq, staged)

    def _add_item(self, pai, arq: dict, staged: bool):
        status  = arq["status"]
        caminho = arq["caminho"]
        cor     = _COR_STATUS.get(status, "#c9d1d9")
        item = QTreeWidgetItem([f"  {caminho}"])
        item.setForeground(0, QColor(cor))
        item.setData(0, Qt.UserRole, {"caminho": caminho, "staged": staged})
        pai.addChild(item)

    def _menu_contexto(self, pos):
        item = self._arvore.itemAt(pos)
        if not item:

            return

        dados = item.data(0, Qt.UserRole)
        if not dados:

            return

        caminho = dados["caminho"]
        staged  = dados["staged"]

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background:#1a1a1a; color:#c9d1d9;
                    border:1px solid #333; font-size:10px; }
            QMenu::item:selected { background:#1e3a5f; }
        """)

        if not staged:
            a = menu.addAction("Preparar", lambda: self._git_cmd("add", caminho))
            a.setIcon(icone_tema("mdi.plus"))
            a = menu.addAction("Descartar mudanças", lambda: self._descartar(caminho))
            a.setIcon(icone_tema("mdi.undo-variant"))
        else:
            a = menu.addAction("Remover da fila", lambda: self._git_cmd("restore", "--staged", caminho))
            a.setIcon(icone_tema("mdi.minus"))

        menu.exec(self._arvore.viewport().mapToGlobal(pos))

    def _git_cmd(self, *args):
        if not self._caminho:

            return

        w = GerenciadorGit()
        r = w._executar(list(args), self._caminho)
        if r.ok:
            self._terminal.ok(f"{args[0]}: {args[-1]}")
        else:
            self._terminal.erro(f"Falha: {r.erro}")
        self.atualizar(self._caminho)

    def _descartar(self, caminho: str):
        if not HeinPopup.confirmar(
            "Descartar alterações",
            f"Descartar todas as mudanças em <b>{caminho}</b>?",
            parent=self,
        ):
            return
        self._git_cmd("restore", caminho)

    def _stage_tudo(self):
        self._git_cmd("add", "-A")

    def _unstage_tudo(self):
        self._git_cmd("restore", "--staged", ".")

    def _toggle_ruido(self):
        """Alterna filtro de _arquivos e __pycache__ na árvore de status."""
        self._ocultar_ruido = self._btn_ruido.isChecked()
        if self._caminho:
            self.atualizar(self._caminho)

    def _limpar_gitignore(self):
        """Remove do índice Git arquivos rastreados que agora estão no .gitignore."""
        if not self._caminho:
            return
        r = self._git.limpar_cache_gitignore(self._caminho)
        if not r.ok:
            self._terminal.erro(f"Falha ao limpar: {r.erro}")
            return
        if not r.saida and not r.erro:
            self._terminal.ok("Nenhum arquivo rastreado encontrado no .gitignore")
        else:
            self._terminal.ok(
                "✅ Arquivos removidos do rastreamento Git (não apagados do disco).\n"
                "   Faça um commit para finalizar."
            )
        self.atualizar(self._caminho)

# ══════════════════════════════════════════════════════════════════════
# Painel de Diferenças
# ══════════════════════════════════════════════════════════════════════

class _PainelDiferencas(QWidget):
    """Aba de Diferenças — mostra o que mudou em cada arquivo."""

    def __init__(self, git: GerenciadorGit, parent=None):
        super().__init__(parent)
        self._git           = git
        self._caminho       = ""
        self._ocultar_ruido = True
        self._construir()

    def _construir(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        splitter = QSplitter(Qt.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background:#1a1a1a; height:2px; }")

        # ── painel superior: árvore de arquivos + barra de ações ────
        painel_lista = QWidget()
        vlay_lista = QVBoxLayout(painel_lista)
        vlay_lista.setContentsMargins(0, 0, 0, 0)
        vlay_lista.setSpacing(0)

        self._arvore = QTreeWidget()
        self._arvore.setHeaderHidden(True)
        self._arvore.setStyleSheet(_ESTILO_TREE)
        self._arvore.itemClicked.connect(self._ao_selecionar)
        vlay_lista.addWidget(self._arvore, 1)

        # barra de filtro/expandir
        bar_acao = QWidget()
        bar_acao.setStyleSheet("background:#0a0a0a; border-top:1px solid #1a1a1a;")
        lay_acao = QHBoxLayout(bar_acao)
        lay_acao.setContentsMargins(6, 3, 6, 3)
        lay_acao.setSpacing(4)

        self._btn_ruido = _botao("_arquivos")
        self._btn_ruido.setIcon(icone_tema("mdi.filter-variant"))
        self._btn_ruido.setIconSize(QSize(14, 14))
        self._btn_ruido.setFixedHeight(20)
        self._btn_ruido.setCheckable(True)
        self._btn_ruido.setChecked(self._ocultar_ruido)
        self._btn_ruido.setToolTip("Ocultar/mostrar __pycache__ e arquivos _*")
        self._btn_ruido.clicked.connect(self._toggle_ruido)
        lay_acao.addWidget(self._btn_ruido)
        lay_acao.addStretch()

        btn_exp = _botao("")
        btn_exp.setIcon(icone_tema("mdi.arrow-expand-all"))
        btn_col = _botao("")
        btn_col.setIcon(icone_tema("mdi.arrow-collapse-all"))
        btn_exp.setFixedSize(22, 20)
        btn_col.setFixedSize(22, 20)
        btn_exp.setToolTip("Expandir todos")
        btn_col.setToolTip("Recolher todos")
        btn_exp.clicked.connect(self._arvore.expandAll)
        btn_col.clicked.connect(self._arvore.collapseAll)
        lay_acao.addWidget(btn_exp)
        lay_acao.addWidget(btn_col)
        vlay_lista.addWidget(bar_acao)

        splitter.addWidget(painel_lista)

        # ── painel inferior: barra de busca + viewer do diff ─────────
        viewer_panel = QWidget()
        vlay = QVBoxLayout(viewer_panel)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        barra_busca = QWidget()
        barra_busca.setStyleSheet("background:#0d0d0d; border-bottom:1px solid #1a1a1a;")
        lay_busca = QHBoxLayout(barra_busca)
        lay_busca.setContentsMargins(6, 3, 6, 3)
        lay_busca.setSpacing(6)

        self._input_busca_diff = QLineEdit()
        self._input_busca_diff.setPlaceholderText("Buscar no diff…")
        self._input_busca_diff.setStyleSheet(
            "QLineEdit { background:#0a0a0a; color:#c9d1d9;"
            " border:1px solid #222; border-radius:3px;"
            " padding:2px 6px; font-size:10px; }"
            "QLineEdit:focus { border-color:#4ec994; }"
        )
        self._input_busca_diff.textChanged.connect(self._ao_buscar_diff)
        lay_busca.addWidget(self._input_busca_diff)

        self._lbl_res_diff = QLabel("")
        self._lbl_res_diff.setStyleSheet("color:#555; font-size:9px; min-width:60px;")
        lay_busca.addWidget(self._lbl_res_diff)

        vlay.addWidget(barra_busca)

        self._texto = QTextEdit()
        self._texto.setReadOnly(True)
        self._texto.setLineWrapMode(QTextEdit.NoWrap)
        self._texto.setStyleSheet(
            "QTextEdit { background:#0a0a0a; color:#c9d1d9;"
            " border:none; font-size:10px;"
            f" font-family:'{FONTE_MONO}','Consolas',monospace;"
            " padding:4px; }"
        )
        vlay.addWidget(self._texto, 1)

        splitter.addWidget(viewer_panel)
        splitter.setSizes([150, 300])
        lay.addWidget(splitter, 1)

    # ── filtro de ruído ──────────────────────────────────────────────
    def _toggle_ruido(self):
        self._ocultar_ruido = self._btn_ruido.isChecked()
        if self._caminho:
            self.atualizar(self._caminho)

    # ── popular árvore ───────────────────────────────────────────────
    def atualizar(self, caminho: str):
        self._caminho = caminho
        self._arvore.clear()
        self._texto.clear()
        self._input_busca_diff.clear()
        self._lbl_res_diff.setText("")

        if not caminho:
            return

        arquivos = self._git.arquivos_alterados(caminho)

        if not arquivos:
            vazio = QTreeWidgetItem(["  Sem alterações"])
            vazio.setForeground(0, QColor("#444"))
            self._arvore.addTopLevelItem(vazio)
            return

        self._preencher_grupo(None, arquivos)

        # seleciona e mostra o primeiro arquivo real
        def _primeiro_arquivo(pai):
            n = pai.childCount() if pai else self._arvore.topLevelItemCount()
            for i in range(n):
                item = pai.child(i) if pai else self._arvore.topLevelItem(i)
                c = item.data(0, Qt.UserRole)
                if c:
                    return item, c
                res = _primeiro_arquivo(item)
                if res:
                    return res
            return None, None

        item0, cam0 = _primeiro_arquivo(None)
        if item0:
            self._arvore.setCurrentItem(item0)
            self._mostrar_diff(cam0)

    def _preencher_grupo(self, pai, arquivos: list):
        """Agrupa arquivos por pasta na árvore, igual ao painel Status."""
        diretos   = []
        subgrupos: dict[str, list] = {}

        for arq in arquivos:
            partes = arq["caminho"].replace("\\", "/").split("/", 1)
            if len(partes) == 1:
                diretos.append(arq)
            else:
                pasta, resto = partes
                subgrupos.setdefault(pasta, []).append(
                    dict(arq, caminho=resto)
                )

        def _add(node):
            if pai is None:
                self._arvore.addTopLevelItem(node)
            else:
                pai.addChild(node)

        for nome_pasta in sorted(subgrupos):
            eh_ruido = nome_pasta.startswith("_")
            if self._ocultar_ruido and eh_ruido:
                continue
            filhos   = subgrupos[nome_pasta]
            eh_cache = "__pycache__" in nome_pasta
            cor      = "#333" if (eh_cache or eh_ruido) else "#666"
            node = QTreeWidgetItem([f"  {nome_pasta}/   {len(filhos)}"])
            node.setForeground(0, QColor(cor))
            node.setFlags(Qt.ItemIsEnabled)
            _add(node)
            self._preencher_grupo(node, filhos)
            node.setExpanded(not eh_cache)

        for arq in sorted(diretos, key=lambda a: a["caminho"].lower()):
            if self._ocultar_ruido and (
                arq["caminho"].startswith("_") or arq["caminho"].endswith(".pyc")
            ):
                continue
            cor  = _COR_STATUS.get(arq["status"], "#c9d1d9")
            item = QTreeWidgetItem([f"  {arq['caminho']}"])
            item.setForeground(0, QColor(cor))
            item.setData(0, Qt.UserRole, arq["caminho"])
            if pai is None:
                self._arvore.addTopLevelItem(item)
            else:
                pai.addChild(item)

    # ── seleção ──────────────────────────────────────────────────────
    def _ao_selecionar(self, item: QTreeWidgetItem, _col: int = 0):
        caminho = item.data(0, Qt.UserRole)
        if caminho:
            self._mostrar_diff(caminho)

    # ── diff viewer ──────────────────────────────────────────────────
    _SKIP_PREFIXOS = ("diff --git ", "index ", "--- a/", "+++ b/",
                      "old mode", "new mode", "similarity index",
                      "rename from", "rename to")

    def _mostrar_diff(self, arquivo: str):
        if not self._caminho:
            return

        r = self._git._executar(["diff", "HEAD", "--", arquivo], self._caminho)
        if not r.saida:
            r = self._git._executar(["diff", "--cached", "--", arquivo], self._caminho)

        self._texto.clear()
        self._input_busca_diff.clear()
        self._lbl_res_diff.setText("")
        cursor = self._texto.textCursor()

        from PySide6.QtGui import QTextCharFormat
        fmt_add  = QTextCharFormat()
        fmt_add.setForeground(tema_global().qcolor("editor.git_adicionado", VERDE))
        fmt_del  = QTextCharFormat()
        fmt_del.setForeground(tema_global().qcolor("editor.git_deletado", COR_SINTAXE_VARIAVEL_ESPECIAL))
        fmt_hdr  = QTextCharFormat()
        fmt_hdr.setForeground(tema_global().qcolor("editor.info", COR_INFO))
        fmt_ctx  = QTextCharFormat()
        fmt_ctx.setForeground(QColor("#555"))
        fmt_aviso = QTextCharFormat()
        fmt_aviso.setForeground(QColor("#888"))

        saida = r.saida or ""

        # arquivo binário
        if "Binary files" in saida and "differ" in saida:
            cursor.setCharFormat(fmt_aviso)
            cursor.insertText(f"  Arquivo binário — sem diferenças de texto legíveis\n")
            cursor.insertText(f"  ({arquivo})\n")
            self._texto.setTextCursor(cursor)
            return

        tem_conteudo = False
        for linha in saida.splitlines():
            # pula cabeçalhos técnicos do git
            if any(linha.startswith(p) for p in self._SKIP_PREFIXOS):
                continue
            # trecho de localização — mostra limpo
            if linha.startswith("@@"):
                # extrai só o contexto funcional (@@ -10,7 +10,9 @@ nome_funcao)
                partes = linha.split("@@")
                contexto = partes[2].strip() if len(partes) > 2 else ""
                nums     = partes[1].strip() if len(partes) > 1 else linha
                texto_hdr = f"  ┄ linha {nums}"
                if contexto:
                    texto_hdr += f"  {contexto}"
                cursor.setCharFormat(fmt_hdr)
                cursor.insertText(texto_hdr + "\n")
                tem_conteudo = True
                continue
            if linha.startswith("+"):
                cursor.setCharFormat(fmt_add)
            elif linha.startswith("-"):
                cursor.setCharFormat(fmt_del)
            else:
                cursor.setCharFormat(fmt_ctx)
            cursor.insertText(linha + "\n")
            tem_conteudo = True

        if not tem_conteudo:
            cursor.setCharFormat(fmt_aviso)
            cursor.insertText("  Sem diferenças encontradas\n")

        self._texto.setTextCursor(cursor)

    def _ao_buscar_diff(self, texto: str):
        """Destaca ocorrências no diff exibido."""
        from PySide6.QtGui import QTextCharFormat
        from PySide6.QtWidgets import QTextEdit as _QTE

        cursor = self._texto.textCursor()
        cursor.setPosition(0)
        self._texto.setTextCursor(cursor)

        selecoes = []
        termo = texto.strip()
        if termo:
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#3a3a00"))
            fmt.setForeground(QColor("#ffee44"))
            doc = self._texto.document()
            c   = doc.find(termo, 0)
            while not c.isNull():
                sel        = _QTE.ExtraSelection()
                sel.cursor = c
                sel.format = fmt
                selecoes.append(sel)
                c = doc.find(termo, c)
            if selecoes:
                self._texto.setTextCursor(selecoes[0].cursor)
            total = len(selecoes)
            self._lbl_res_diff.setText(
                f"{total} resultado{'s' if total != 1 else ''}"
            )
        else:
            self._lbl_res_diff.setText("")

        self._texto.setExtraSelections(selecoes)
