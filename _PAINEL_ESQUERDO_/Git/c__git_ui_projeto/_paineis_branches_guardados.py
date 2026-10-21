# 📁 _PAINEL_ESQUERDO_/Git/c__git_ui_projeto/_paineis_branches_guardados.py
"""
Painéis de Ramificações (branches) e Guardados (stash).
"""
from PySide6.QtCore    import Qt, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem,
    QMenu, QInputDialog,
)
from PySide6.QtGui import QColor
from ..git_gerente      import GerenciadorGit
from ..git_terminal     import GitTerminal
from ..git_ui_utils     import _botao
from _UTILITARIOS_.icones       import icone_tema
from _UTILITARIOS_.hein_pou_pap import HeinPopup
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import VERDE, COR_INFO, COR_GIT_TEXTO_NEUTRO
from ._paineis_status_diff import _ESTILO_TREE

# ══════════════════════════════════════════════════════════════════════
# Painel de Ramificações
# ══════════════════════════════════════════════════════════════════════

class _PainelRamificacoes(QWidget):
    """
    Aba de Ramificações.
    Lista ramificações locais, permite criar nova, fazer checkout e mesclagem.
    """

    def __init__(self, git: GerenciadorGit, terminal: GitTerminal, parent=None):
        super().__init__(parent)
        self._git      = git
        self._terminal = terminal
        self._caminho  = ""
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
        lay.addWidget(self._arvore, 1)

        bar = QWidget()
        bar.setStyleSheet("background:#0a0a0a; border-top:1px solid #1a1a1a;")
        lay_bar = QHBoxLayout(bar)
        lay_bar.setContentsMargins(6, 4, 6, 4)
        lay_bar.setSpacing(4)

        btn_nova = _botao("Nova ramificação", tema_global().cor("interface.fundo_item_hover", "#1a2a1a"), VERDE)
        btn_nova.setFixedHeight(22)
        btn_nova.setIcon(icone_tema("mdi.source-branch-plus"))
        btn_nova.setIconSize(QSize(14, 14))
        btn_nova.clicked.connect(self._nova_branch)
        lay_bar.addWidget(btn_nova)
        lay.addWidget(bar)

    def atualizar(self, caminho: str):
        self._caminho = caminho
        self._arvore.clear()

        if not caminho:

            return

        r = self._git._executar(["branch", "-a"], caminho)

        locais  = []
        remotas = []
        for linha in r.saida.splitlines():
            nome_raw = linha.strip()
            is_atual = nome_raw.startswith("*")
            nome     = nome_raw.lstrip("* ").strip()
            if nome.startswith("remotes/"):
                remotas.append(nome)
            else:
                locais.append((nome, is_atual))

        # ── Locais ──────────────────────────────────────────────────
        if locais:
            cab = QTreeWidgetItem(["  LOCAL"])
            cab.setForeground(0, QColor("#444"))
            cab.setFlags(Qt.ItemIsEnabled)
            self._arvore.addTopLevelItem(cab)
            for nome, is_atual in locais:
                prefixo = "→ " if is_atual else "  "
                item = QTreeWidgetItem([f"    {prefixo}{nome}"])
                item.setData(0, Qt.UserRole, nome)
                cor = tema_global().qcolor("editor.git_adicionado", VERDE) if is_atual \
                      else tema_global().qcolor("interface.texto", COR_GIT_TEXTO_NEUTRO)
                item.setForeground(0, cor)
                cab.addChild(item)
            cab.setExpanded(True)

        # ── Remotas ─────────────────────────────────────────────────
        if remotas:
            cab_r = QTreeWidgetItem([f"  REMOTO  ({len(remotas)})"])
            cab_r.setForeground(0, QColor("#444"))
            cab_r.setFlags(Qt.ItemIsEnabled)
            self._arvore.addTopLevelItem(cab_r)
            for nome in remotas:
                exib = nome.removeprefix("remotes/")
                item = QTreeWidgetItem([f"    {exib}"])
                item.setData(0, Qt.UserRole, None)   # remotas não são checkout direto
                item.setForeground(0, QColor("#555"))
                cab_r.addChild(item)
            cab_r.setExpanded(False)

    def _menu_contexto(self, pos):
        item = self._arvore.itemAt(pos)
        if not item:

            return

        nome = item.data(0, Qt.UserRole)
        if not nome:

            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background:#1a1a1a; color:#c9d1d9;
                    border:1px solid #333; font-size:10px; }
            QMenu::item:selected { background:#1e3a5f; }
        """)
        a = menu.addAction(f"Mudar para '{nome}'", lambda: self._checkout(nome))
        a.setIcon(icone_tema("mdi.source-branch"))
        a = menu.addAction(f"Mesclar '{nome}' na atual", lambda: self._merge(nome))
        a.setIcon(icone_tema("mdi.source-merge"))
        menu.addSeparator()
        a = menu.addAction("Excluir ramificação", lambda: self._deletar(nome))
        a.setIcon(icone_tema("mdi.delete"))
        menu.exec(self._arvore.viewport().mapToGlobal(pos))

    def _checkout(self, nome: str):
        nome_limpo = nome.lstrip("→ ").strip()
        r = self._git._executar(["checkout", nome_limpo], self._caminho)
        if r.ok:
            self._terminal.ok(f"Mudou para ramificação: {nome_limpo}")
        else:
            self._terminal.erro(f"Falha ao mudar: {r.erro}")
        self.atualizar(self._caminho)

    def _merge(self, nome: str):
        nome_limpo = nome.lstrip("→ ").strip()
        r = self._git._executar(["merge", nome_limpo], self._caminho)
        if r.ok:
            self._terminal.ok(f"Mesclagem de '{nome_limpo}' concluída")
        else:
            self._terminal.erro(f"Conflito na mesclagem: {r.erro}")
        self.atualizar(self._caminho)

    def _deletar(self, nome: str):
        nome_limpo = nome.lstrip("→ ").strip()
        if not HeinPopup.confirmar(
            "Excluir ramificação",
            f"Excluir a ramificação <b>{nome_limpo}</b>?",
            parent=self,
        ):
            return
        res = self._git._executar(["branch", "-d", nome_limpo], self._caminho)
        if res.ok:
            self._terminal.ok(f"Ramificação '{nome_limpo}' excluída")
        else:
            self._terminal.erro(f"Falha: {res.erro}")
        self.atualizar(self._caminho)

    def _nova_branch(self):
        nome, ok = QInputDialog.getText(self, "Nova Ramificação", "Nome da nova ramificação:")
        if not ok or not nome.strip():

            return

        nome = nome.strip().replace(" ", "-")
        r = self._git._executar(["checkout", "-b", nome], self._caminho)
        if r.ok:
            self._terminal.ok(f"Ramificação '{nome}' criada e ativada")
        else:
            self._terminal.erro(f"Falha: {r.erro}")
        self.atualizar(self._caminho)

# ══════════════════════════════════════════════════════════════════════
# Painel de Guardados (Stash)
# ══════════════════════════════════════════════════════════════════════

class _PainelGuardados(QWidget):
    """
    Aba de Guardados — guarda e recupera alterações temporariamente.
    Útil quando precisa trocar de ramificação sem salvar versão.
    """

    def __init__(self, git: GerenciadorGit, terminal: GitTerminal, parent=None):
        super().__init__(parent)
        self._git      = git
        self._terminal = terminal
        self._caminho  = ""
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
        lay.addWidget(self._arvore, 1)

        bar = QWidget()
        bar.setStyleSheet("background:#0a0a0a; border-top:1px solid #1a1a1a;")
        lay_bar = QHBoxLayout(bar)
        lay_bar.setContentsMargins(6, 4, 6, 4)

        btn_guardar = _botao("Guardar alterações", tema_global().cor("interface.fundo_item_hover", "#1a1a2e"), COR_INFO)
        btn_guardar.setFixedHeight(22)
        btn_guardar.setIcon(icone_tema("mdi.content-save-edit"))
        btn_guardar.setIconSize(QSize(14, 14))
        btn_guardar.clicked.connect(self._guardar)
        lay_bar.addWidget(btn_guardar)
        lay.addWidget(bar)

    def atualizar(self, caminho: str):
        self._caminho = caminho
        self._arvore.clear()

        if not caminho:

            return

        r = self._git._executar(["stash", "list"], caminho)
        if not r.saida.strip():
            item = QTreeWidgetItem(["  Nenhum item guardado"])
            item.setForeground(0, QColor("#444"))
            self._arvore.addTopLevelItem(item)

            return

        for linha in r.saida.splitlines():
            partes = linha.split(":", 2)
            ref    = partes[0].strip() if partes else linha
            desc   = partes[2].strip() if len(partes) > 2 else linha
            item = QTreeWidgetItem([f"  {desc}"])
            item.setData(0, Qt.UserRole, ref)
            item.setForeground(0, tema_global().qcolor("interface.texto", COR_GIT_TEXTO_NEUTRO))
            self._arvore.addTopLevelItem(item)

    def _menu_contexto(self, pos):
        item = self._arvore.itemAt(pos)
        if not item:

            return

        ref = item.data(0, Qt.UserRole)
        if not ref:

            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background:#1a1a1a; color:#c9d1d9;
                    border:1px solid #333; font-size:10px; }
            QMenu::item:selected { background:#1e3a5f; }
        """)
        a = menu.addAction("Usar e tirar da lista", lambda: self._pop(ref))
        a.setIcon(icone_tema("mdi.check"))
        a = menu.addAction("Usar (manter na lista)", lambda: self._apply(ref))
        a.setIcon(icone_tema("mdi.check-circle-outline"))
        menu.addSeparator()
        a = menu.addAction("Excluir item guardado", lambda: self._drop(ref))
        a.setIcon(icone_tema("mdi.delete"))
        menu.exec(self._arvore.viewport().mapToGlobal(pos))

    def _pop(self, ref: str):
        r = self._git._executar(["stash", "pop", ref], self._caminho)
        if r.ok:
            self._terminal.ok("Item aplicado e removido")
        else:
            self._terminal.erro(f"Falha: {r.erro}")
        self.atualizar(self._caminho)

    def _apply(self, ref: str):
        r = self._git._executar(["stash", "apply", ref], self._caminho)
        if r.ok:
            self._terminal.ok("Item aplicado")
        else:
            self._terminal.erro(f"Falha: {r.erro}")
        self.atualizar(self._caminho)

    def _drop(self, ref: str):
        r = self._git._executar(["stash", "drop", ref], self._caminho)
        if r.ok:
            self._terminal.ok("Item removido")
        else:
            self._terminal.erro(f"Falha: {r.erro}")
        self.atualizar(self._caminho)

    def _guardar(self):
        msg, ok = QInputDialog.getText(
            self, "Guardar alterações",
            "Descrição (opcional):",
        )
        if not ok:

            return

        args = ["stash", "push"]
        if msg.strip():
            args += ["-m", msg.strip()]
        r = self._git._executar(args, self._caminho)
        if r.ok:
            self._terminal.ok("Alterações guardadas")
        else:
            self._terminal.erro(f"Falha: {r.erro}")
        self.atualizar(self._caminho)
