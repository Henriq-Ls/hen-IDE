# 📁 _APP_/tab_widget.py
"""
Gerencia as abas de código da IDE hein.
"""
import os
import _CONFIGURA_ as _CFG
from PySide6.QtWidgets import QTabWidget, QMessageBox
from PySide6.QtCore    import Signal, Qt, QSize
from PySide6.QtGui     import QIcon
from _EDITOR_.Editor   import CodeEditor
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import PACKS_ICONES, _ICONE_EXT, _ICONE_PADRAO
# ── Cache de ícones de aba ───────────────────────────────────────────────
_cache_icones_tab: dict[str, QIcon | None] = {}

def _icone_para_extensao(ext: str) -> QIcon | None:
    """
    Retorna QIcon para a extensão dada, usando o pack ativo configurado.
    Usa cache para não recriar o mesmo ícone várias vezes.
    """
    pack_ativo = PACKS_ICONES.get(getattr(_CFG, '_PACK_ATIVO', 'fa5'), _ICONE_EXT)
    nome_qicon, cor = pack_ativo.get(ext, _ICONE_PADRAO)
    chave = f"{nome_qicon}:{cor}"
    if chave in _cache_icones_tab:
        return _cache_icones_tab[chave]

    try:
        from _UTILITARIOS_.icones import icone_tema
        icone = icone_tema(nome_qicon, color=cor, scale_factor=1.0)
        _cache_icones_tab[chave] = icone

        return icone

    except Exception:
        _cache_icones_tab[chave] = None

        return None

def _icone_para_arquivo(caminho: str) -> QIcon | None:
    """Deriva a extensão do caminho e retorna o QIcon correspondente."""
    nome = os.path.basename(caminho)
    if '.' in nome:
        ext = ('.' + nome.rsplit('.', 1)[-1]).lower()
    else:
        ext = nome.lower()  # ex: .gitignore

    return _icone_para_extensao(ext)

class TabWidget(QTabWidget):
    navegar_para_arquivo = Signal(str, int)
    aba_adicionada       = Signal(object)
    aba_fechada          = Signal(object)   # emite o widget DEPOIS de removido
    split_solicitado     = Signal(object, str)  # (editor, zona: 'right'|'float')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.tabBar().setIconSize(QSize(16, 16))
        self.tabCloseRequested.connect(self.fechar_aba)
        self.currentChanged.connect(self._ao_trocar_aba)
        self.editores: dict[int, CodeEditor] = {}
        self.project_path: str | None = None
        self._preview_editor: CodeEditor | None = None  # aba em modo preview (IMP-14)

    # ⚠️  função grande (57 linhas) | except genérico vazio
    def add_new_tab(self, caminho: str = None) -> CodeEditor: # Se ja esta aberto, so ativa
        if caminho:
            if os.path.basename(os.path.normpath(caminho)).lower() in {
                "hein.log", "hein_exception.log", "hein_faulthandler.log",
            }:
                # O log e escrito continuamente pela propria IDE. Abrí-lo no
                # editor cria um ciclo de textChanged/diff/estado e pode travar.
                return self.get_current_editor()
            _cam_norm = os.path.normcase(os.path.abspath(caminho))
            for indice, editor in self.editores.items():
                fp = getattr(editor, "file_path", None)
                if fp and os.path.normcase(os.path.abspath(fp)) == _cam_norm:
                    self.setCurrentIndex(indice)

                    return editor

            caminho = os.path.abspath(caminho)  # normaliza antes de abrir

        tema   = tema_global().dados()
        editor = CodeEditor(tema=tema)
        editor.setFocusPolicy(Qt.ClickFocus)  # <- só recebe foco quando clicado
        # Aplica configurações persistidas (cursor, fonte, tab, etc.) ao novo editor
        try:
            from _CONFIGURA_.gerenciador_configurar import config_global
            config_global().aplicar_no_editor(editor)
        except Exception:
            pass
        if self.project_path:
            editor.set_projeto(self.project_path)
        editor.navegar_arquivo.connect(self.navegar_para_arquivo)

        if caminho:
            editor.load_file(caminho)
            nome_aba = self._titulo_sem_ambiguidade(caminho)  # IMP-08
        else:
            nome_aba = "Novo"

        self.blockSignals(True)          # silencia currentChanged durante montagem da aba
        indice = self.addTab(editor, nome_aba)
        self.editores[indice] = editor
        self.setCurrentIndex(indice)
        self.blockSignals(False)
        self.currentChanged.emit(indice)  # dispara uma única vez, limpo
        self.setFocusProxy(None)  # <- não repassa foco automaticamente pro editor
        editor.textChanged.connect(
            lambda e=editor: self._atualizar_titulo_por_editor(e)
        )

        # ── ícone da aba baseado na extensão do arquivo ──────────────────────────
        if caminho:
            icone = _icone_para_arquivo(caminho)
            if icone:
                self.setTabIcon(indice, icone)

        self.aba_adicionada.emit(editor)
        from PySide6.QtCore import QTimer
        from PySide6.QtGui import QTextCursor

        def _focar_e_posicionar():
            editor.setFocus()
            # IMP-02: cursor no INICIO do arquivo por padrao. Se houver estado
            # salvo (EstadoEditor), _restaurar_estado_arquivo() roda depois
            # (QTimer 50ms em load_file) e sobrescreve com a posicao real.
            c = editor.textCursor()
            c.movePosition(QTextCursor.Start)
            editor.setTextCursor(c)
        QTimer.singleShot(0, _focar_e_posicionar)

        return editor

    # ⚠️  except genérico vazio
    def add_new_tab_widget(self, widget, titulo: str, icone=None,
                           registrar_como_editor: bool = False):
        indice = self.addTab(widget, titulo)
        if icone:
            # icone pode chegar como str (ex: "mdi6.folder-star") ou QIcon
            if isinstance(icone, str):
                try:
                    from _UTILITARIOS_.icones import icone_tema
                    _qicone = icone_tema(icone, scale_factor=1.0)
                    if _qicone:
                        self.setTabIcon(indice, _qicone)
                except Exception:
                    pass          # sem ícone — não quebra a abertura da aba
            else:
                self.setTabIcon(indice, icone)

        if registrar_como_editor:
            # Registra o widget como editor rastreado: habilita save, is_modified,
            # asterisco no título e diálogo de salvamento ao fechar.
            self.editores[indice] = widget
            widget.setFocusPolicy(Qt.ClickFocus)
            widget.textChanged.connect(
                lambda w=widget: self._atualizar_titulo_por_editor(w)
            )

        self.setCurrentIndex(indice)

        return widget

    def fechar_aba(self, indice: int):
        widget = self.widget(indice)
        editor = None
        for e in self.editores.values():
            if e is widget:
                editor = e
                break

        if editor is None:
            self.removeTab(indice)
            self._reindexar()
            self.aba_fechada.emit(widget)

            return

        if hasattr(editor, "is_modified") and editor.is_modified():
            nome = os.path.basename(editor.file_path) if editor.file_path else "arquivo"
            resposta = QMessageBox.question(
                self,
                "Salvar?",
                f"Salvar '{nome}' antes de fechar?",
                QMessageBox.Yes | QMessageBox.No
            )
            if resposta == QMessageBox.Yes:
                if not editor.save_file():
                    return

            elif resposta == QMessageBox.Cancel:
                return

        editor.encerrar_threads_bg()
        self.removeTab(indice)
        self._reindexar()
        self.aba_fechada.emit(widget)

    def _reindexar(self):
        novos = {}
        for i in range(self.count()):
            widget = self.widget(i)
            for editor in self.editores.values():
                if editor is widget:
                    novos[i] = editor
                    break
        self.editores = novos

    def mover_aba(self, de: int, para_antes_de: int):
        """Move a aba do índice `de` para antes do índice `para_antes_de`.

        Exemplos:
          mover_aba(0, 3)  -> tab 0 vai para a posição 2 (antes do atual 3)
          mover_aba(4, 1)  -> tab 4 vai para a posição 1 (antes do atual 1)
        """
        total = self.count()
        if de < 0 or de >= total:
            return
        # Inserir depois do próprio índice ou do imediatamente seguinte = sem mudança
        if para_antes_de == de or para_antes_de == de + 1:
            return
        # Qt moveTab(from, to): move aba da posição `from` para `to`.
        # Se from < to, todas entre eles recuam 1; se from > to, avançam 1.
        if de < para_antes_de:
            destino = max(0, min(para_antes_de - 1, total - 1))
        else:
            destino = max(0, min(para_antes_de, total - 1))
        if de == destino:
            return
        self.tabBar().moveTab(de, destino)
        self._reindexar()

    def _ao_trocar_aba(self, _indice: int = 0):
        """Aplica tema pendente e devolve o foco ao editor recem-ativado.

        Sem isso, o QTabWidget muda a aba mas nao move o foco de teclado
        (editores usam Qt.ClickFocus + setFocusProxy(None) de proposito, para
        nao roubar foco de outros paineis). Resultado colateral: o cursor
        customizado (_GerenciadorCursorPersonalizado.desenhar) so pinta
        quando editor.hasFocus() e True, entao ele "sumia" ao trocar de aba
        ate o usuario clicar de volta no texto.
        """
        editor = self.get_current_editor()
        if editor and getattr(editor, "_tema_pendente", None):
            # Difere o rehighlight para depois do repaint da aba.
            # atualizar_tema() chama rehighlight() completo do documento
            # -- se chamado direto aqui, bloqueia a UI thread durante a
            # troca de aba e causa lag visivel (pior com arquivos grandes).
            _t = editor._tema_pendente
            editor._tema_pendente = None
            try:
                from shiboken6 import isValid as _cpp_ok
            except ImportError:
                _cpp_ok = lambda _: True
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda e=editor, t=_t: _cpp_ok(e) and e.atualizar_tema(t))
        if editor:
            editor.setFocus()

    def _atualizar_titulo_por_editor(self, editor: CodeEditor):
        for i in range(self.count()):
            if self.widget(i) is editor:
                base = self._titulo_sem_ambiguidade(editor.file_path) if editor.file_path else "Novo"  # IMP-08
                self.setTabText(i, f"*{base}" if editor.is_modified() else base)
                break

    def _atualizar_titulo_aba(self, indice: int):
        if indice not in self.editores:
            return

        editor = self.editores[indice]
        base   = self._titulo_sem_ambiguidade(editor.file_path) if editor.file_path else "Novo"  # IMP-08
        self.setTabText(indice, f"*{base}" if editor.is_modified() else base)

    def get_current_editor(self) -> CodeEditor | None:
        return self.editores.get(self.currentIndex())

    def editor_atual(self) -> CodeEditor | None:
        return self.get_current_editor()

    # 💡 nome_opc = Literal["novo.py"] ← defina os valores válidos
    def add_new_tab_com_conteudo(self, conteudo: str, nome: str = "novo.py") -> CodeEditor:
        """Cria aba nova com conteúdo já preenchido -- usado pelo JSON Explorer."""
        editor = self.add_new_tab()
        editor.setPlainText(conteudo)
        # Atualiza título e ícone da aba
        for i in range(self.count()):
            if self.widget(i) is editor:
                self.setTabText(i, f"*{nome}")
                icone = _icone_para_arquivo(nome)
                if icone:
                    self.setTabIcon(i, icone)
                break

        return editor

    def destacar_aba(self, indice: int):
        """Remove o editor do índice sem diálogo de save — usado no drag-to-float.

        Retorna o CodeEditor destacado, ou None se o índice for inválido ou
        se for a última aba (não é possível destacar a única aba restante).
        """
        if self.count() <= 1:
            return None   # não permite esvaziar a janela principal

        editor = self.editores.get(indice)
        if editor is None:
            return None

        # Cancela modo preview se era este editor
        if self._preview_editor is editor:
            self._preview_editor = None
        self.removeTab(indice)
        self._reindexar()
        # Libera o parent para que JanelaEditorFlutuante assuma a posse
        editor.setParent(None)

        return editor

    def reinserir_editor(self, editor) -> int:
        """Reinsere um editor devolvido por uma JanelaEditorFlutuante.

        Abre como aba normal ao final, ativa-a e retorna o novo índice.
        """
        if editor is None:
            return -1

        fp    = getattr(editor, 'file_path', None)
        titulo = self._titulo_sem_ambiguidade(fp) if fp else "Novo"
        if hasattr(editor, 'is_modified') and editor.is_modified():
            titulo = f"*{titulo}"
        indice = self.addTab(editor, titulo)
        self.editores[indice] = editor
        self.setCurrentIndex(indice)
        editor.setFocus()

        return indice

    def _pedir_split(self, indice: int, pos_global):
        """Chamado por AbaWidget durante drag — mostra ZonaDropSplit sobre o editor.

        Quando o usuário solta sobre uma zona, emite split_solicitado(editor, zona).
        """
        from _APP_.zona_drop_split import ZonaDropSplit
        editor = self.editores.get(indice)
        if editor is None:
            return

        # Encontra o container pai adequado para o overlay
        alvo = self.parent() or self
        overlay = ZonaDropSplit(alvo)
        def _ao_zona(zona, ed=editor, idx=indice):
            self.split_solicitado.emit(ed, zona)
        def _ao_cancelar():
            pass
        overlay.zona_escolhida.connect(_ao_zona)
        overlay.cancelado.connect(_ao_cancelar)
        overlay.show_over(alvo)

    def _titulo_sem_ambiguidade(self, caminho: str) -> str:
        """Retorna o título da aba adicionando sufixo de pasta quando há duplicata (IMP-08).

        Dois arquivos __init__.py de pacotes diferentes mostram:
            __init__.py — models/
            __init__.py — views/
        """
        if not caminho:
            return "Novo"

        base = os.path.basename(caminho)
        duplicatas = [
            e.file_path for e in self.editores.values()
            if (e.file_path
                and os.path.basename(e.file_path) == base
                and os.path.normcase(os.path.abspath(e.file_path))
                   != os.path.normcase(os.path.abspath(caminho)))
        ]
        if not duplicatas:
            return base

        pai = os.path.basename(os.path.dirname(caminho)) or "?"

        return f"{base} — {pai}/"

    def open_preview(self, caminho: str) -> 'CodeEditor | None':
        """Abre arquivo em modo preview (aba com título em itálico).

        Comportamento estilo VS Code (IMP-14):
          - Clique simples no FileTree abre em preview.
          - Clicar outro arquivo fecha o preview atual e abre o novo.
          - Editar o conteúdo converte a aba em permanente (itálico some).
          - Se o arquivo já estiver aberto normalmente, apenas ativa a aba.
        """
        if not caminho:
            return None

        # Se já está aberto (permanente), só ativa
        _cam_norm = os.path.normcase(os.path.abspath(caminho))
        for indice, editor in self.editores.items():
            fp = getattr(editor, "file_path", None)
            if fp and os.path.normcase(os.path.abspath(fp)) == _cam_norm:
                self.setCurrentIndex(indice)

                return editor

        # Fecha preview anterior sem perguntar (não foi editado)
        if self._preview_editor is not None and not self._preview_editor.is_modified():
            for i in range(self.count()):
                if self.widget(i) is self._preview_editor:
                    self._preview_editor.encerrar_threads_bg()
                    self.removeTab(i)
                    self._reindexar()
                    break
        self._preview_editor = None
        # Abre a nova aba (irá disparar currentChanged → BarraTitulo rebuild,
        # mas _preview_editor ainda está None nesse momento)
        editor = self.add_new_tab(caminho)
        self._preview_editor = editor
        # Converte para permanente ao primeiro caractere digitado
        editor.textChanged.connect(
            lambda e=editor: self._converter_preview_para_permanente(e)
        )
        # _preview_editor foi setado DEPOIS de add_new_tab, que já havia
        # disparado currentChanged com o valor None. Re-emite agora que o
        # estado está correto para a BarraTitulo rebuildar com o itálico.
        self.currentChanged.emit(self.currentIndex())

        return editor

    def _converter_preview_para_permanente(self, editor: 'CodeEditor'):
        """Chamado no primeiro textChanged do preview — remove o modo preview."""
        if self._preview_editor is editor:
            self._preview_editor = None
            # Emite currentChanged para BarraTitulo reconstruir sem o itálico
            self.currentChanged.emit(self.currentIndex())

    def clear(self):
        for editor in list(self.editores.values()):
            try:
                editor.encerrar_threads_bg()
            except Exception:
                pass
        while self.count() > 0:
            self.removeTab(0)
        self.editores.clear()
