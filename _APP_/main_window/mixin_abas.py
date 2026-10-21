"""MixinAbas — abas de editor, árvore de arquivos, split de painéis.

Parte do pacote main_window/ — ver main_window/__init__.py.
Gerado a partir da divisão de main_window.py (arquivo único de 4607 linhas).
"""


import atexit
import os
import shutil
import subprocess
import sys
import tempfile
from _UTILITARIOS_.icones import icone_tema
from PySide6.QtWidgets import (
    QMainWindow,

    QWidget,

    QVBoxLayout,

    QHBoxLayout,

    QTabWidget,

    QSplitter,

    QPushButton,

    QMenuBar,

    QMenu,

    QFileDialog,

    QMessageBox,

    QInputDialog,

    QLabel,

    QApplication,

    QProgressBar,

    QDockWidget,

)

from _APP_.navegador_abas import NavegadorAbas
from PySide6.QtGui import QTextCursor, QPainter, QColor, QBrush, QPainterPath, QRegion, QAction, QKeySequence, QPen
from PySide6.QtCore import QEvent, QRectF
from PySide6.QtCore import Qt, QTimer, QSize, QThread, Signal, QSettings
from ..tab_widget import TabWidget
from ..terminal_tab_widget import TerminalTabWidget

from _PAINEL_ESQUERDO_.FileTree import PainelArquivos
from _PAINEL_ESQUERDO_.painel_abas_inferior import PainelAbasInferior as PainelGit
from _CONFIGURA_.gerenciador_atalhos import GerenciadorAtalhos
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_.gerenciador_configurar import config_global
from GerenciadorAbas_AutoSalve import GerenciadorAbas_AutoSalve
from _CONFIGURA_ import (
    TITULO_APP,

    GEOMETRIA_APP,

    SPLITTER_PRINCIPAL,

    SPLITTER_COL1,

    SPLITTER_COL2,

    COR_MENU_BG,

    COR_MENU_TEXTO,

    COR_MENU_HOVER_BG,

    COR_MENU_HOVER_TEXTO,

    COR_MENU_ITEM,

    COR_MENU_ITEM_HOVER,

    COR_TOOLBAR_TERM_BG,

    COR_BTN_RUN_BG,

    COR_BTN_RUN_HOVER,

    ATALHO_NOVO_PROJETO,

    ATALHO_ABRIR_PROJETO,

    ATALHO_ABRIR_ARQUIVO,

    ATALHO_SALVAR,

    ATALHO_EXECUTAR,

    ATALHO_TAREFAS_PROJETO,

    ATALHO_TAREFAS_GLOBAIS,

    ATALHO_EDITAR_TEMA,

    ATALHO_EDITAR_ATALHOS,

    ATALHO_EDITOR_CONFIG,

    ATALHO_AUTOCOMPLETE,

    PASTA_PROJETOS,

    PASTA_APPDATA,

    ARQUIVO_CONFIG,

    ARQUIVO_ATALHOS,

    ARQUIVO_TEMA,

    COR_SUCESSO,

    COR_INFO,

    COR_AVISO,

    COR_CINZA_TEXTO,

    BORDA_CONTORNO_UI,

)

from _EDITOR_.Indexador import Indexador
from ..barra_aba_topo import BarraTitulo
from ..barra_lateral_direita import BarraLateralDireita
from _BUSCA_.motor_busca import MotorBusca
from _BUSCA_.painel_busca_global import PainelBuscaGlobal
from _BUSCA_.command_palette import CommandPalette
from _BUSCA_.busca_comandos import buscar_comandos



from .base import ARQUIVO_AUTOCOMPLETE
from .workers import _recarregar_se_necessario


class MixinAbas:
    """abas de editor, árvore de arquivos, split de painéis.

    Mixin combinado em MainWindow — depende dos atributos criados por
    MainWindowBase.__init__/_montar_ui (self.tabs, self.painel_arquivos, etc.)."""

    def _sync_arvore_com_aba(self, index):
        editor = self.tabs.widget(index)

        if hasattr(editor, 'file_path') and editor.file_path:
            self.painel_arquivos.revelar_arquivo(editor.file_path)

        # Notifica o painel Git sobre qual arquivo está em foco agora
        if hasattr(self, 'painel_git') and hasattr(self.painel_git, 'set_arquivo_ativo'):
            caminho = getattr(editor, 'file_path', '') or ''
            self.painel_git.set_arquivo_ativo(caminho)

    def _executar_arquivo_do_tree(self, caminho: str):
        """Executar arquivo clicado com botão direito na árvore."""

        if not caminho or not os.path.isfile(caminho):
            return

        # Abre o arquivo no editor se ainda não estiver aberto

        editor = None

        for idx, e in self.tabs.editores.items():
            if getattr(e, "file_path", None) == caminho:
                self.tabs.setCurrentIndex(idx)

                editor = e

                break

        if not editor:
            editor = self.tabs.add_new_tab(caminho)

        # Executa direto pelo caminho, sem depender do editor ativo

        # Despacha para ExecutorTerminal se a linguagem suporta execucao nativa

        _ext_t = os.path.splitext(caminho)[1].lower()

        from _EDITOR_.Mult_Linguas import get_provider as _gp_t
        _pv_t = _gp_t(_ext_t)

        _run_exts_t = _pv_t.run_extensoes if _pv_t.run_extensoes else _pv_t.extensions

        if _pv_t.can_run and _ext_t in _run_exts_t:
            self.terminal_tabs.abrir_executor_terminal(_pv_t.name, caminho)

            nome = os.path.basename(caminho)

            self.statusBar().showMessage(f"Executando: {nome}")

            return

        if _pv_t.name != 'Python':
            return  # linguagem sem executor — F1 silencioso

        nome = os.path.basename(caminho)

        terminal_run = self.terminal_tabs.obter_ou_criar_saida(nome=nome)

        if not getattr(terminal_run, "_nav_conectado", False):
            terminal_run.navegar_para_erro.connect(self._ao_navegar_erro_terminal)

            terminal_run._nav_conectado = True

        terminal_run.clear()

        terminal_run.imprimir_separador(nome)

        terminal_run.executar_python(

            caminho, python_path=self._pegar_python_projeto()

        )

        self.statusBar().showMessage(f"Executando: {nome}")

    def _ao_split_solicitado(self, editor, zona: str):
        """Recebe drag de aba e cria painel à direita ou janela flutuante (IMP-15).

        Zonas suportadas: 'right' (novo painel à direita) e 'float' (destaca
        para uma janela independente). Ambas atuam sobre o `editor` que foi
        efetivamente arrastado — nunca sobre a aba atualmente em foco.
        """
        if zona == 'float':
            from _LOG_.log import log
            from _APP_.janela_flutuante import JanelaEditorFlutuante
            log.info("mixin_abas.py", "_ao_split_solicitado", "zona=float — iniciando destaque de aba")
            try:
                indice = self._indice_do_editor(editor)
                if indice is None:
                    log.aviso("mixin_abas.py", "_ao_split_solicitado", "editor arrastado não encontrado nas abas do painel principal")
                    return

                ed = self.tabs.destacar_aba(indice)
                if ed is None:
                    log.aviso("mixin_abas.py", "_ao_split_solicitado", "destacar_aba() não retornou editor")
                    return

                fp = getattr(ed, 'file_path', None) or ''
                janela = JanelaEditorFlutuante(ed, fp, self.tabs)
                # IMP-15b: guarda referência forte em self._janelas_flutuantes —
                # sem isso o Python coleta esse QWidget top-level assim que esta
                # função retorna e a janela nunca aparece (só a aba some).
                self._janelas_flutuantes.append(janela)

                def _ao_devolver(editor_devolvido, _janela=janela):
                    if _janela in self._janelas_flutuantes:
                        self._janelas_flutuantes.remove(_janela)
                    log.info("mixin_abas.py", "_ao_split_solicitado", "janela flutuante devolveu o editor ao painel principal")
                    self.tabs.reinserir_editor(editor_devolvido)

                janela.devolver_editor.connect(_ao_devolver)
                janela.move(self.geometry().center())
                janela.show()
                log.ok("mixin_abas.py", "_ao_split_solicitado", f"janela flutuante aberta para {os.path.basename(fp) if fp else '(sem arquivo)'}")
            except Exception:
                log.excecao("mixin_abas.py", "_ao_split_solicitado", "falha ao abrir janela flutuante")
                raise

            return

        self._criar_painel_split(editor, zona)

    def _indice_do_editor(self, editor):
        """Localiza o índice de `editor` entre as abas do painel principal."""
        for i, ed in self.tabs.editores.items():
            if ed is editor:
                return i
        return None

    def _editor_focado(self):
        """Retorna o CodeEditor com foco de teclado, considerando painéis
        secundários criados por split (não apenas o painel principal).

        Sem isso, atalhos como Ctrl+Shift+O agiam sempre sobre
        self.tabs.get_current_editor() — ou seja, sempre sobre o painel
        principal, ignorando qual painel o usuário realmente focou depois
        de dividir a tela.
        """
        from PySide6.QtWidgets import QApplication
        from _EDITOR_.Editor import CodeEditor

        w = QApplication.focusWidget()
        while w is not None:
            if isinstance(w, CodeEditor):
                return w
            w = w.parentWidget()

        return self.tabs.get_current_editor()

    def _criar_painel_split(self, editor, zona: str):
        """Cria um novo painel e o encaixa sempre à direita do splitter.

        O layout é uma única fileira horizontal — cada split novo é
        adicionado à direita do último painel existente, nunca acima/abaixo.
        """
        from _APP_.tab_widget import TabWidget as _TW
        from PySide6.QtCore import Qt as _Qt

        if self._splitter_editor.orientation() != _Qt.Horizontal:
            self._splitter_editor.setOrientation(_Qt.Horizontal)

        indice = self._indice_do_editor(editor)
        if indice is None:
            return

        ed = self.tabs.destacar_aba(indice)
        if ed is None:
            return

        # Cria TabWidget secundário e o encaixa à direita do último painel
        tw2 = _TW()
        tw2.project_path = self.current_project_path
        tw2.aba_fechada.connect(
            lambda w, _tw=tw2: self._ao_painel_secundario_vazio(_tw)
        )
        self._splitter_editor.addWidget(tw2)

        # Divide igualmente a largura entre todos os painéis
        total = self._splitter_editor.count()
        parte = max(self._splitter_editor.width() // total, 100)
        self._splitter_editor.setSizes([parte] * total)

        # Adiciona o editor no novo painel
        tw2.reinserir_editor(ed)
        self._paineis_secundarios.append(tw2)

    def _ao_painel_secundario_vazio(self, tw):
        """Remove o painel secundário quando sua última aba for fechada."""
        from PySide6.QtCore import QTimer as _QT

        def _remover():
            if tw.count() == 0 and tw in self._paineis_secundarios:
                self._paineis_secundarios.remove(tw)
                tw.setParent(None)
                tw.deleteLater()
        _QT.singleShot(0, _remover)

    def _fechar_aba_atual_com_save(self):
        """Ctrl+Q — fecha a aba de editor ativa com auto-save silencioso (IMP-11).

        Arquivo com file_path e modificações: salva silenciosamente (sem diálogo).
        Arquivo "Novo" (sem file_path): abre QFileDialog de Salvar Como normalmente.
        """
        editor = self.tabs.get_current_editor()
        if not editor:
            return

        if hasattr(editor, 'is_modified') and editor.is_modified():
            if getattr(editor, 'file_path', None):
                editor.save_file()   # salva silenciosamente
            else:
                if not editor.save_file():   # abre diálogo só para "Novo"

                    return

        self.tabs.fechar_aba(self.tabs.currentIndex())

    def _ao_fechar_aba_editor(self, widget):
        """Quando aba do editor é fechada: fecha o painel vinculado no terminal."""

        if getattr(self, "_guard_fechando_terminal", False):
            return

        import os as _os
        from _TERMINAIS_.visualizador_imagem import VisualizadorImagem
        # ── Imagem: fecha painel de controles ──────────────────────────────────

        if isinstance(widget, VisualizadorImagem):
            for i in range(self.tabs.count()):
                if isinstance(self.tabs.widget(i), VisualizadorImagem):
                    return

            self.terminal_tabs.fechar_aba_imagem_controles()

            return

        # ── Última aba fechada → fica sem nada ─────────────────────────────────

        # ── JSON: fecha o painel explorer vinculado ─────────────────────────────

        caminho = getattr(widget, "file_path", None)

        if not caminho or not caminho.lower().endswith(".json"):
            return

        _tipos = [

            ("_TERMINAIS_.Tarefas.tarefas_explorer", "TarefasExplorer"),

            ("_TERMINAIS_.configurar_explorer",  "ConfigurarExplorer"),

            ("_TERMINAIS_.atalho_explorer",      "AtalhoExplorer"),

            ("_TERMINAIS_.thema_explorer",       "ThemaExplorer"),

            ("_TERMINAIS_.autocomplete_explorer","AutocompleteExplorer"),

            ("_TERMINAIS_.json_explorer",        "JsonExplorer"),


        ]

        for modulo, classe in _tipos:
            try:
                import importlib
                mod = importlib.import_module(modulo)

                cls = getattr(mod, classe)

            except Exception:
                continue

            for i in range(self.terminal_tabs.count() - 1, -1, -1):
                w = self.terminal_tabs.widget(i)

                if isinstance(w, cls):
                    # verifica vínculo pelo caminho

                    w_cam = getattr(w, "_caminho", None) or getattr(w, "_arquivo", None)

                    if w_cam is None or _os.path.normpath(w_cam) == _os.path.normpath(caminho):
                        self.terminal_tabs.fechar_aba(i)

                        break


    def _ao_fechar_aba_terminal(self, widget):
        """Quando aba do terminal fecha: fecha tambem o JSON vinculado no editor.
        Se for o terminal Git, desativa o modo staging na FileTree."""
        # ── Terminal Git fechado → sai do modo staging ──────────────────────────
        if getattr(widget, "_is_git_terminal", False):
            painel_arq = getattr(self, "painel_arquivos", None)
            if painel_arq and hasattr(painel_arq, "sair_modo_staging"):
                painel_arq.sair_modo_staging()
            return

        caminho = getattr(widget, "_caminho", None) or getattr(widget, "_arquivo", None)
        if not caminho:
            return
        self._guard_fechando_terminal = True
        try:
            for i in range(self.tabs.count() - 1, -1, -1):
                editor = self.tabs.widget(i)
                editor_cam = getattr(editor, "file_path", None)
                if editor_cam and os.path.normpath(editor_cam) == os.path.normpath(caminho):
                    self.tabs.fechar_aba(i)
                    break
        finally:
            self._guard_fechando_terminal = False

    # ▼ NOVO — clique simples no FileTree: só troca aba, nunca abre arquivo novo

    def _ao_clique_simples_arvore(self, caminho: str):
        _norm = lambda p: os.path.normcase(os.path.abspath(p)) if p else ""
        for indice, editor in self.tabs.editores.items():
            if _norm(getattr(editor, "file_path", None)) == _norm(caminho):
                self.tabs.setCurrentIndex(indice)  # troca para aba já aberta

                return

        # Arquivo não está aberto ainda: verifica extensão antes de preview
        ext = os.path.splitext(caminho)[1].lower()
        if ext in self._EXTENSOES_BLOQUEADAS:
            self._avisar_extensao_bloqueada(caminho)
        elif ext in self._EXTENSOES_IMAGEM:
            self._abrir_visualizador_imagem(caminho)
        elif ext in self._EXTENSOES_HEIN:
            # EditorHein é tipo diferente de CodeEditor — open_preview usaria
            # CodeEditor como preview e _abrir_editor_hein abriria uma 2ª aba.
            # Solucao: trata clique simples igual ao duplo para .hein.
            self._abrir_editor_hein(caminho)
        else:
            self.tabs.open_preview(caminho)

    def _ao_revelar_aba_no_tree(self, _indice: int):
        editor = self.tabs.get_current_editor()

        if not editor:
            return

        caminho = getattr(editor, "file_path", None)

        if caminho:
            self.painel_arquivos.revelar_arquivo(caminho)  # scroll + seleção na árvore

    # ⚠️  except genérico vazio

    def _recarregar_gutter_todos(self):
        """BUG-01: recarrega config da calha em todos os editores abertos."""

        for editor in self.tabs.editores.values():
            try:
                editor.area_numeros._recarregar_gutter()

                editor.metricas.atualizar_margem()

                editor.area_numeros.update()

            except Exception:
                pass

    # ⚠️  função grande (155 linhas)

    def _ao_trocar_aba_editor_json(self):
        """Quando o editor muda para uma aba .json, abre o explorer adequado."""

        from _TERMINAIS_.json_explorer import JsonExplorer
        from _UTILITARIOS_.icones import icone_tema
        import os
        editor = self.tabs.get_current_editor()

        if not editor:
            return

        caminho = getattr(editor, "file_path", None)

        if not caminho or not caminho.lower().endswith(".json"):
            return

        # ── configurar.json → ConfigurarExplorer ──────────────────────────────

        from _CONFIGURA_ import ARQUIVO_CONFIG, ARQUIVO_ATALHOS, ARQUIVO_NUCLEO
        if os.path.normpath(caminho) == os.path.normpath(ARQUIVO_CONFIG):
            from _TERMINAIS_.configurar_explorer import ConfigurarExplorer
            for i in range(self.terminal_tabs.count()):
                w = self.terminal_tabs.widget(i)

                if isinstance(w, ConfigurarExplorer):
                    self.terminal_tabs.setCurrentIndex(i)

                    _recarregar_se_necessario(w, caminho)

                    return

            explorer = ConfigurarExplorer()

            explorer.configuracao_salva.connect(self._recarregar_gutter_todos)

            idx = self.terminal_tabs.addTab(

                explorer, icone_tema("mdi.tune-vertical"), "configurar.json"

            )

            self.terminal_tabs.setCurrentIndex(idx)

            return

        # ── atalhos.json → AtalhoExplorer ─────────────────────────────────

        if os.path.normpath(caminho) == os.path.normpath(ARQUIVO_ATALHOS):
            from _TERMINAIS_.atalho_explorer import AtalhoExplorer
            for i in range(self.terminal_tabs.count()):
                w = self.terminal_tabs.widget(i)

                if isinstance(w, AtalhoExplorer):
                    self.terminal_tabs.setCurrentIndex(i)

                    _recarregar_se_necessario(w, caminho)

                    return

            explorer = AtalhoExplorer()

            idx = self.terminal_tabs.addTab(

                explorer, icone_tema("mdi.keyboard-outline"), "atalhos.json"

            )

            self.terminal_tabs.setCurrentIndex(idx)

            return

        # ── autocomplete.json → AutocompleteExplorer ──────────────────────────

        if os.path.normpath(caminho) == os.path.normpath(ARQUIVO_AUTOCOMPLETE):
            from _TERMINAIS_.autocomplete_explorer import AutocompleteExplorer
            for i in range(self.terminal_tabs.count()):
                w = self.terminal_tabs.widget(i)

                if isinstance(w, AutocompleteExplorer):
                    self.terminal_tabs.setCurrentIndex(i)

                    _recarregar_se_necessario(w, caminho)

                    return

            explorer = AutocompleteExplorer()

            idx = self.terminal_tabs.addTab(

                explorer, icone_tema("mdi.auto-fix"), "autocomplete.json"

            )

            self.terminal_tabs.setCurrentIndex(idx)

            return

        # ── thema.json / temas/*.json → ThemaExplorer ──────────────────────

        _PASTA_TEMAS_APP = os.path.join(PASTA_APPDATA, "temas")
        _eh_tema = (
            os.path.normpath(caminho) == os.path.normpath(ARQUIVO_TEMA)
            or os.path.normpath(os.path.dirname(caminho)) == os.path.normpath(_PASTA_TEMAS_APP)
        )
        if _eh_tema:
            from _TERMINAIS_.thema_explorer import ThemaExplorer
            for i in range(self.terminal_tabs.count()):
                w = self.terminal_tabs.widget(i)

                if isinstance(w, ThemaExplorer):
                    self.terminal_tabs.setCurrentIndex(i)

                    w.abrir(caminho)
                    self.terminal_tabs.setTabText(i, os.path.basename(caminho))

                    return

            explorer = ThemaExplorer(caminho=caminho)

            idx = self.terminal_tabs.addTab(

                explorer, icone_tema("mdi.palette-outline"), os.path.basename(caminho)

            )

            self.terminal_tabs.setCurrentIndex(idx)

            return

        # ── executores.json → ExecutorExplorer ───────────────────────────

        from _CONFIGURA_ import ARQUIVO_EXECUTORES
        if os.path.normpath(caminho) == os.path.normpath(ARQUIVO_EXECUTORES):
            from _TERMINAIS_.Mult_Terminais.executor_explorer import ExecutorExplorer
            for i in range(self.terminal_tabs.count()):
                w = self.terminal_tabs.widget(i)

                if isinstance(w, ExecutorExplorer):
                    self.terminal_tabs.setCurrentIndex(i)

                    w._recarregar_se_necessario()

                    return

            explorer = ExecutorExplorer()

            idx = self.terminal_tabs.addTab(

                explorer, icone_tema("mdi.console-network-outline"), "executores.json"

            )

            self.terminal_tabs.setCurrentIndex(idx)

            return

        # ── tarefas.json (projeto ou global) → TarefasExplorer ───────────

        from _CONFIGURA_ import ARQUIVO_TAREFAS_GLOBAIS
        _nome_arq = os.path.basename(caminho).lower()

        _pasta_hein = os.path.join(os.path.dirname(caminho), "").lower().rstrip(os.sep + "/")

        _eh_tarefas_global  = os.path.normpath(caminho) == os.path.normpath(ARQUIVO_TAREFAS_GLOBAIS)

        _eh_tarefas_projeto = (

            _nome_arq == "tarefas.json"

            and os.path.basename(os.path.dirname(caminho)).lower() == ".hein"

        )

        if _eh_tarefas_global or _eh_tarefas_projeto:
            from _TERMINAIS_.Tarefas.tarefas_explorer import TarefasExplorer
            modo = "global" if _eh_tarefas_global else "projeto"

            for i in range(self.terminal_tabs.count()):
                w = self.terminal_tabs.widget(i)

                if (
                    isinstance(w, TarefasExplorer)
                    and os.path.normcase(os.path.abspath(getattr(w, "_caminho", "")))
                    == os.path.normcase(os.path.abspath(caminho))
                ):
                    self.terminal_tabs.setCurrentIndex(i)

                    w._recarregar_se_necessario()

                    return

            _icone_tar = icone_tema("mdi.lightning-bolt-outline")

            explorer = TarefasExplorer(caminho=caminho, modo=modo)

            _tab_nome = "Tarefas Globais" if modo == "global" else "Tarefas Locais"

            idx = self.terminal_tabs.addTab(explorer, _icone_tar, _tab_nome)

            self.terminal_tabs.setCurrentIndex(idx)

            return

        # ── executavel.json → ExecutavelExplorer ─────────────────────

        _nome_exec = os.path.basename(caminho).lower()
        _pai_exec  = os.path.basename(os.path.dirname(caminho)).lower()
        _avo_exec  = os.path.basename(os.path.dirname(os.path.dirname(caminho))).lower()
        if _nome_exec == "executavel.json" and _pai_exec == "executavel" and _avo_exec == ".hein":
            from _TERMINAIS_.executavel_explorer import ExecutavelExplorer
            for i in range(self.terminal_tabs.count()):
                w = self.terminal_tabs.widget(i)
                if isinstance(w, ExecutavelExplorer) and os.path.normpath(getattr(w, "_caminho", "")) == os.path.normpath(caminho):
                    self.terminal_tabs.setCurrentIndex(i)
                    w._recarregar_se_necessario()
                    return
            explorer = ExecutavelExplorer(caminho=caminho)
            idx = self.terminal_tabs.addTab(
                explorer, icone_tema("mdi.file-cog-outline"), "executavel.json"
            )
            self.terminal_tabs.setCurrentIndex(idx)
            return

        # ── Qualquer outro .json → JsonExplorer genérico ──────────────────

        for i in range(self.terminal_tabs.count()):
            w = self.terminal_tabs.widget(i)

            if isinstance(w, JsonExplorer):
                w.carregar_arquivo(caminho)

                self.terminal_tabs.setCurrentIndex(i)

                return

        explorer = JsonExplorer()

        idx = self.terminal_tabs.addTab(

            explorer, icone_tema("mdi.code-braces"), os.path.basename(caminho)

        )

        self.terminal_tabs.setCurrentIndex(idx)

        explorer.carregar_arquivo(caminho)

    # DEPOIS

    def novo_arquivo_aba(self):
        self.tabs.add_new_tab()
