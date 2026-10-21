# _APP_/main_window/base.py

"""MainWindowBase — construção da janela, UI raiz e eventos de janela.

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


from .painel_card import PainelCard
from .workers import _AnalisadorProjeto, _garantir_hein_no_gitignore, _recarregar_se_necessario

ARQUIVO_AUTOCOMPLETE = os.path.join(
    os.path.dirname(ARQUIVO_CONFIG), "autocomplete.json"
)


class MainWindowBase(QMainWindow):
    """Construção da janela principal: __init__, montagem da UI e eventos
    nativos de janela (paint, resize/snap, fechar). As demais
    responsabilidades (projeto, abas, busca, terminal/debug, atalhos e
    layout) vêm dos mixins combinados em MainWindow (ver __init__.py)."""

    def __init__(self, projeto_inicial: str | None = None):
        super().__init__()

        self._projeto_inicial = projeto_inicial
        try:
            from _LOG_.log import log
            log.info(
                "base.py",
                "__init__",
                f"MainWindow iniciando: projeto={projeto_inicial}",
            )
        except Exception:
            pass

        self.setWindowFlags(Qt.FramelessWindowHint)  # ← MUDANÇA 2: remove barra nativa

        self.setWindowTitle(TITULO_APP)

        self.setWindowIcon(QApplication.instance().windowIcon())

        self.setGeometry(*GEOMETRIA_APP)

        self.current_project_path: str | None = None

        # IMP-15b: guarda referência forte às janelas flutuantes (editor
        # destacado). Sem isso, o QWidget top-level (sem parent) é coletado
        # pelo GC do Python assim que _ao_split_solicitado() retorna, e a
        # janela nunca chega a aparecer na tela.
        self._janelas_flutuantes: list = []

        # Guard de loading: impede que abrir_projeto() seja chamado duas vezes
        # ao mesmo tempo (ex.: usuário clica duas vezes em "Recentes").
        self._abrindo_projeto: bool = False
        self._fechando_ide: bool = False

        self._indexador: Indexador | None = None

        self._tema = tema_global()

        self._tema.carregar()

        self._config = config_global()

        self._config.carregar()

        self._montar_ui()

        self._gerenciador_abas = GerenciadorAbas_AutoSalve(self.tabs, parent=self)

        self._tema.aplicar_na_janela(self)

        # IMP-06/12: adiar um frame para o Qt processar o cascade do setStyleSheet

        # antes de repintar o gradiente customizado do FileTree

        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self.painel_arquivos.atualizar_tema(self._tema.dados()))

        self._atalhos = GerenciadorAtalhos(self)

        self._atalhos.carregar()

        from _CONFIGURA_.gerenciador_tarefas import GerenciadorTarefas
        self._tarefas = GerenciadorTarefas(self)

        self._tarefas.carregar_globais()

        self._navegador_abas = NavegadorAbas(self.tabs, self._barra_aba_topo)

        QApplication.instance().installEventFilter(self._navegador_abas)

        # IMP-11: Ctrl+Q — fecha aba ativa com auto-save
        from PySide6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(
            self._fechar_aba_atual_com_save
        )
        self._config._janela = self

        self._config._aplicar_em_tudo()

        self._tema.iniciar_hot_reload(self)

        self._config.iniciar_hot_reload(self)



        self.painel_git.commit_realizado.connect(

            self._atualizar_gutter_pos_commit

        )

        from _UTILITARIOS_.atualizador import (
            verificar_atualizacao,

        )  # chip de versão na barra

        verificar_atualizacao(self._barra_aba_topo, parent=self)

        # IMP-08: Se veio com --projeto, abre direto; sem projeto, usa o picker.
        if self._projeto_inicial:
            QTimer.singleShot(0, lambda p=self._projeto_inicial: self.abrir_projeto(p))
        else:
            QTimer.singleShot(0, self._restaurar_ou_picker)
        try:
            from _LOG_.log import log
            log.info(
                "base.py",
                "__init__",
                f"MainWindow construída: projeto={self._projeto_inicial}",
            )
        except Exception:
            pass

    # ⚠️  função grande (99 linhas)

    def restaurar_padroes(self) -> None:
        """

        Restaura tema, configurações, atalhos e núcleo ao padrão de fábrica
        e recarrega cada um.

        A cópia de fábrica é lida direto de _CONFIGURA_/ (fonte de verdade
        do projeto) através de appdata.restaurar_padrao() — nunca de uma
        cópia pré-extraída em AppData/. Assim o botão sempre reflete a
        versão de fábrica atual, mesmo depois de uma atualização da IDE.
        Único caminho de código para restaurar padrões — o mesmo usado por
        GerenciadorAppData.restaurar_padrao() quando chamado isoladamente.

        """

        from _APPDATA_ import appdata
        from _LOG_.log import log

        # componente → rótulo de exibição
        componentes = {
            "tema": "tema",
            "configurar": "configurar.json",
            "atalhos": "atalhos.json",
        }

        restaurados: list[str] = []

        erros: list[str] = []

        for componente, rotulo in componentes.items():
            if appdata.restaurar_padrao(componente):
                restaurados.append(rotulo)
            else:
                erros.append(rotulo)

        if not restaurados and not erros:
            self.statusBar().showMessage(

                "⚠️  Nada para restaurar.", 6000

            )

            return

        # Recarrega cada gerenciador que teve seu arquivo restaurado

        if "tema" in restaurados:
            from _CONFIGURA_.gerenciador_tema import tema_global
            t = tema_global()

            if t.carregar():
                t.aplicar_na_janela(self)

        if "configurar.json" in restaurados:
            from _CONFIGURA_.gerenciador_configurar import config_global
            c = config_global()

            c.carregar()

            c._aplicar_em_tudo()

        if "atalhos.json" in restaurados:
            if hasattr(self, "_atalhos"):
                self._atalhos.carregar()

        msg_ok = (

            f"✅ Padrões restaurados: {', '.join(restaurados)}" if restaurados else ""

        )

        msg_err = f"  ⚠️ Falhas: {', '.join(erros)}" if erros else ""

        self.statusBar().showMessage((msg_ok + msg_err).strip(), 8000)

        log.ok(

            "main_window.py",

            "restaurar_padroes",

            f"concluído — ok={restaurados} err={erros}",

        )

    def _sobre(self):
        QMessageBox.information(self, "Sobre", f"{TITULO_APP} v1.0")

    # ══════════════════════════════════════════════════════════════════

    # UI

    # ══════════════════════════════════════════════════════════════════

    # ⚠️  função grande (377 linhas) | except genérico vazio

    def _montar_ui(self): # Widget raiz: divide horizontalmente em [conteúdo principal | barra lateral]
        widget_raiz = QWidget()

        self.setCentralWidget(widget_raiz)

        # Margem da janela expõe o paintEvent como borda visível.
        # Valor inicial; aplicar_bordas_paineis() atualiza em runtime.
        _larg_ini = int(self._config.obter("ui", "borda_larg", 2))
        self.setContentsMargins(_larg_ini, _larg_ini, _larg_ini, _larg_ini)

        layout_raiz = QHBoxLayout(widget_raiz)

        layout_raiz.setContentsMargins(0, 0, 0, 0)

        layout_raiz.setSpacing(0)

        # ── Coluna esquerda/central: barra título + splitters ─────────

        widget_principal = QWidget()

        layout = QVBoxLayout(widget_principal)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(0)

        # ── MUDANÇA 3: barra de título customizada no topo ────────────

        self._barra_aba_topo = BarraTitulo(janela=self)

        layout.addWidget(self._barra_aba_topo)

        # ─────────────────────────────────────────────────────────────

        tema = tema_global().dados()

        splitter_principal = QSplitter(Qt.Horizontal)

        splitter_principal.setHandleWidth(1)
        splitter_principal.setStyleSheet("QSplitter::handle { background: transparent; }")

        self._splitter_principal = splitter_principal

        layout.addWidget(splitter_principal)

        layout_raiz.addWidget(widget_principal)

        # ── Barra lateral direita: colada na borda direita da janela ──

        self._barra_lateral_direita = BarraLateralDireita(janela=self)

        layout_raiz.addWidget(self._barra_lateral_direita)

        # Injeta referência na barra de título para sincronizar tema e double-click

        self._barra_aba_topo.injetar_barra_lateral(self._barra_lateral_direita)

        # ── COLUNA 1: menu lateral + arquivos + git ───────────────────

        from _CONFIGURA_.gerenciador_tema import tema_global as _tg
        _cor_esq = _tg().cor("interface.fundo_painel_esquerdo", "#0C1A0C")

        coluna_esquerda = PainelCard(_cor_esq)

        self._coluna_esquerda = coluna_esquerda

        layout_esquerda = coluna_esquerda._layout

        menu_lateral = QMenuBar()

        menu_lateral.setStyleSheet(f"""

            QMenuBar {{

                background-color: {COR_MENU_BG};

                color: {COR_MENU_TEXTO};

            }}

            QMenuBar::item:selected {{

                background-color: {COR_MENU_HOVER_BG};

                color: {COR_MENU_HOVER_TEXTO};

            }}

            QMenu {{

                background-color: {COR_MENU_BG};

                color: {COR_MENU_ITEM};

            }}

            QMenu::item:selected {{

                background-color: {COR_MENU_ITEM_HOVER};

            }}

            QMenu::separator {{

                height: 1px; background: #222; margin: 2px 8px;

            }}

        """)

        arquivo = QMenu("Arquivo")

        arquivo.addAction(

            f"Janela Inicial        {ATALHO_NOVO_PROJETO}", self.abrir_janela_inicial

        )

        arquivo.addAction(

            f"Abrir Projeto         {ATALHO_ABRIR_PROJETO}", self.abrir_projeto

        )

        arquivo.addAction(

            f"Abrir Arquivo         {ATALHO_ABRIR_ARQUIVO}", self.abrir_arquivo

        )

        arquivo.addAction(f"Salvar                {ATALHO_SALVAR}", self.salvar_arquivo)

        arquivo.addSeparator()

        arquivo.addAction("Pasta de dados hein", self._abrir_pasta_appdata)

        arquivo.addSeparator()

        arquivo.addAction("Sair", self.close)

        editar = QMenu("Editar")

        editar.addAction("Desfazer              Ctrl+Z", self.desfazer)

        editar.addAction("Refazer               Ctrl+Y", self.refazer)

        editar.addSeparator()

        editar.addAction("Recortar              Ctrl+X", self.recortar)

        editar.addAction("Copiar                Ctrl+C", self.copiar)

        editar.addAction("Colar                 Ctrl+V", self.colar)

        editar.addAction("Selecionar Tudo       Ctrl+A", self.selecionar_tudo)

        editar.addSeparator()

        editar.addAction("Ir para Linha         Ctrl+G", self.ir_para_linha_dialogo)

        editar.addAction("Ir para Início        Ctrl+Home", self.ir_para_inicio)

        editar.addAction("Ir para Fim           Ctrl+End", self.ir_para_fim)

        editar.addSeparator()

        editar.addAction("Comentar/Descomentar  Ctrl+/", self.comentar_linha)

        editar.addAction("Duplicar Linha        Ctrl+Shift+D", self.duplicar_linha)

        editar.addAction("Deletar Linha         Ctrl+Shift+K", self.deletar_linha)

        editar.addAction("Mover Linha Acima     Alt+↑", self.mover_linha_cima)

        editar.addAction("Mover Linha Abaixo    Alt+↓", self.mover_linha_baixo)

        editar.addSeparator()

        editar.addAction("Buscar                Ctrl+F", self.abrir_busca)

        editar.addAction("Buscar e Substituir   Ctrl+H", self.abrir_substituicao)

        editar.addAction("Buscar no Projeto     Ctrl+J", self.buscar_no_projeto)

        editar.addSeparator()

        editar.addAction("Recolher Bloco        Ctrl+Alt++", self.recolher_bloco)

        editar.addAction("Expandir Bloco        Ctrl+Alt+-", self.expandir_bloco)

        editar.addAction("Recolher Tudo", self.recolher_tudo)

        editar.addAction("Expandir Tudo", self.expandir_tudo)

        executar = QMenu("Executar")

        executar.addAction(

            f"Executar             {ATALHO_EXECUTAR}", self.executar_codigo

        )

        executar.addAction("Novo Terminal        Ctrl+Shift+T", self.novo_terminal)

        executar.addAction("Alternar Terminal    Ctrl+T", self.alternar_terminal)

        executar.addAction("Limpar Terminal", self.limpar_terminal_ativo)

        visualizar = QMenu("Visualizar")

        visualizar.addAction("Tela Cheia              F11",          self.alternar_tela_cheia)

        self._acao_painel_arquivos = visualizar.addAction(

            "Árvore de Arquivos      Ctrl+P", self.alternar_painel_arquivos)

        self._acao_painel_arquivos.setCheckable(True)

        self._acao_painel_arquivos.setChecked(True)

        self._acao_painel_git = visualizar.addAction(

            "Painel Git              Ctrl+Shift+G", self.alternar_painel_git)

        self._acao_painel_git.setCheckable(True)

        self._acao_painel_git.setChecked(True)

        visualizar.addAction("Aumentar Fonte          Ctrl+=",       self.aumentar_fonte)

        visualizar.addAction("Diminuir Fonte          Ctrl+-",       self.diminuir_fonte)

        visualizar.addAction("Resetar Fonte           Ctrl+0",       self.resetar_fonte)

        # ── Menu "Projeto": ações específicas do projeto aberto ────────────
        # (Tarefas Globais fica aqui por afinidade com Tarefas do Projeto,
        # ainda que seja compartilhada entre projetos.)

        projeto = QMenu("Projeto")

        _act_tarefas_proj = QAction(

            f"Tarefas do Projeto   {ATALHO_TAREFAS_PROJETO}", self

        )

        _act_tarefas_proj.setShortcut(QKeySequence(ATALHO_TAREFAS_PROJETO))  # Bug #4
        _act_tarefas_proj.triggered.connect(self.abrir_tarefas_projeto)

        projeto.addAction(_act_tarefas_proj)

        _act_tarefas_glob = QAction(

            f"Tarefas Globais      {ATALHO_TAREFAS_GLOBAIS}", self

        )

        _act_tarefas_glob.setShortcut(QKeySequence(ATALHO_TAREFAS_GLOBAIS))  # Bug #4
        _act_tarefas_glob.triggered.connect(self.abrir_tarefas)

        projeto.addAction(_act_tarefas_glob)

        projeto.addSeparator()

        projeto.addAction(

            "Criar Venv         Ctrl+Alt+A", self.tarefa_criar_venv)

        projeto.addAction(

            "Ativar Venv/Pip    Ctrl+Alt+Z", self.tarefa_ativar_venv)

        projeto.addSeparator()

        projeto.addAction(

            "Painel de Erros    Alt+6", self.abrir_painel_erros)

        # ── Menu "Configurações": ajustes da IDE, valem para todo projeto ──
        # Antes vinham misturados no menu "Projeto", apesar de não serem
        # específicos de projeto nenhum (Ctrl+3 a Ctrl+9).

        configuracoes = QMenu("Configurações")

        configuracoes.addAction(

            f"Tema              {ATALHO_EDITAR_TEMA}",

            self.abrir_arquivo_configuracoes,

        )

        configuracoes.addAction(

            f"Editar Atalhos    {ATALHO_EDITAR_ATALHOS}", self.abrir_arquivo_atalhos

        )

        configuracoes.addAction(

            f"Config do Editor  {ATALHO_EDITOR_CONFIG}", self.abrir_configurar

        )

        configuracoes.addAction(

            f"Autocomplete      {ATALHO_AUTOCOMPLETE}", self.abrir_autocomplete

        )


        configuracoes.addSeparator()

        configuracoes.addAction(

            "⚙ Restaurar Padrões", self.restaurar_padroes)

        visualizar.addSeparator()

        visualizar.addAction("Picker", self._abrir_picker_dialog)

        ajuda = QMenu("Ajuda")

        ajuda.addAction("Sobre", self._sobre)

        ajuda.addAction("Ver Atalhos", self.abrir_arquivo_atalhos)

        from _UTILITARIOS_.hein_context_menu import aplicar_estilo_menu
        for _m in [arquivo, editar, executar, visualizar, projeto, configuracoes, ajuda]:
            aplicar_estilo_menu(_m)

        self._barra_aba_topo.injetar_menus(

            [arquivo, editar, executar, visualizar, projeto, configuracoes, ajuda]

        )

        splitter_col1 = QSplitter(Qt.Vertical)

        splitter_col1.setHandleWidth(6)

        self._splitter_col1 = splitter_col1

        self.painel_arquivos = PainelArquivos(tema=tema)

        self._barra_aba_topo.injetar_painel_arquivos(self.painel_arquivos)

        self._barra_esquerda = self.painel_arquivos._barra_esquerda

        self._barra_esquerda.menu_clicado.connect(self._barra_aba_topo._abrir_menu)

        self._barra_esquerda.recentes_clicado.connect(

            self._barra_aba_topo._abrir_menu_recentes

        )

        self._barra_esquerda.projeto_clicado.connect(

            self._abrir_pasta_projeto_no_explorer

        )

        self.painel_arquivos.arquivo_selecionado.connect(

            self._abrir_arquivo_selecionado

        )

        self.painel_arquivos.executar_arquivo.connect(

            self._executar_arquivo_do_tree

        )

        self.painel_arquivos.arquivo_clicado_simples.connect(

                    self._ao_clique_simples_arvore

        )

        splitter_col1.addWidget(self.painel_arquivos)

        splitter_col1.setCollapsible(0, False)

        self.painel_arquivos.setMinimumHeight(32)

        self.painel_git = PainelGit()
        self.painel_git.conectar_painel_arquivos(self.painel_arquivos)

        # Checkboxes de staging aparecem quando o terminal Git abre (botão "Main")
        self.painel_git._tela_projeto.abrir_painel_git.connect(
            self.painel_arquivos.entrar_modo_staging
        )
        # Abre (ou substitui) a aba Git no terminal central
        self.painel_git._tela_projeto.abrir_painel_git.connect(
            self._abrir_aba_git_no_terminal
        )
        # Histórico de versões abre como aba no terminal central
        self.painel_git._tela_projeto.abrir_historico_terminal.connect(
            self._abrir_historico_no_terminal
        )
        self.painel_git.abrir_executavel_config.connect(
            self.abrir_executavel_config
        )

        splitter_col1.addWidget(self.painel_git)

        splitter_col1.setSizes(SPLITTER_COL1)

        layout_esquerda.addWidget(splitter_col1)

        splitter_principal.addWidget(coluna_esquerda)

        # Overlay ┐ criado DEPOIS de todos os filhos para ficar acima de tudo

        # topo   = posição Y real da base do _barra_esquerda (botão "— projeto —")

        #          dentro da coluna_esquerda — é exatamente onde a árvore/scrollbar começa

        # limite = posição Y real da base do painel_arquivos dentro da coluna_esquerda

        def _topo_abaixo_botao():
            from PySide6.QtCore import QPoint
            pos = self._barra_esquerda.mapTo(coluna_esquerda, QPoint(0, self._barra_esquerda.height()))

            return pos.y()

        def _limite_base_arquivos():
            from PySide6.QtCore import QPoint
            pos = self.painel_arquivos.mapTo(coluna_esquerda, QPoint(0, self.painel_arquivos.height()))

            return pos.y()

        coluna_esquerda.ativar_curva_esquerda(

            obter_limite_y=_limite_base_arquivos,

            obter_topo_y=_topo_abaixo_botao,

        )

        splitter_col1.splitterMoved.connect(

            lambda *_: coluna_esquerda._curva_overlay.update()

        )

        # ── COLUNA 2: editor + terminal ───────────────────────────────

        splitter_col2 = QSplitter(Qt.Vertical)

        splitter_col2.setHandleWidth(6)

        self._splitter_col2 = splitter_col2

        from _APP_.barra_buscas import BarraCentral, MODO_ARQUIVO
        self._barra_central = BarraCentral(self)

        _cor_cen = _tg().cor("interface.fundo_painel_central", "#0A1210")

        coluna_central = PainelCard(_cor_cen)

        layout_central = coluna_central._layout

        self.tabs = TabWidget()

        self.tabs.project_path = self.current_project_path

        self.tabs.navegar_para_arquivo.connect(self._ao_navegar_outline)

        # DEPOIS

        self._barra_aba_topo.injetar_tab_widget(self.tabs)
        self.tabs.split_solicitado.connect(self._ao_split_solicitado)

        self.tabs.currentChanged.connect(

            lambda: self._barra_central.set_editor(self.tabs.get_current_editor())

        )

        # reexecuta a busca inline (Ctrl+F) no editor que ganhou foco ao trocar de aba

        self.tabs.currentChanged.connect(self._ao_trocar_aba_busca_inline)

        # ▼ NOVO — quando a aba ativa muda, revela o arquivo no FileTree

        self.tabs.currentChanged.connect(self._ao_revelar_aba_no_tree)

        self.tabs.currentChanged.connect(self._sync_arvore_com_aba)

        layout_central.addWidget(self._barra_central)

        # Split editor: self.tabs fica dentro de um QSplitter horizontal
        # para suportar painéis secundários via drag (IMP-15)
        self._splitter_editor = QSplitter(Qt.Horizontal)
        self._splitter_editor.setHandleWidth(4)
        self._splitter_editor.setChildrenCollapsible(False)
        self._splitter_editor.addWidget(self.tabs)
        self._paineis_secundarios: list = []   # TabWidget extras
        layout_central.addWidget(self._splitter_editor)

        self._card_editor = coluna_central

        splitter_col2.addWidget(coluna_central)

        # ── motor de busca ────────────────────────────────────────────

        self._motor_busca = MotorBusca(self)

        self._ultimo_termo_global = ""

        self._ultimo_filtro_arvore = ""

        # ── debounce para filtro * da árvore (evita freeze por keystroke) ──

        self._timer_filtro_arvore = QTimer(self)

        self._timer_filtro_arvore.setSingleShot(True)

        self._timer_filtro_arvore.timeout.connect(

            self._ao_filtrar_arvore_debounced

        )

        # ── painel resultados grep (@) ────────────────────────────────

        self._painel_busca_global = PainelBuscaGlobal()

        self._painel_busca_global.abrir_resultado.connect(self._ao_abrir_resultado_grep)

        # ── command palette (>) ───────────────────────────────────────

        self._command_palette = CommandPalette(self)

        self._barra_central.instalar_atalhos(self)

        self._barra_central.buscar_global.connect(self._ao_buscar_global)

        self._barra_central.buscar_arquivo.connect(self._ao_buscar_arquivo)

        self._barra_central.ir_para_linha.connect(self._ao_ir_para_linha)

        self._barra_central.modo_substituicao.connect(self._ao_modo_substituicao)

        self._barra_central.fechar.connect(self._ao_fechar_busca_global)

        self._barra_central.proximo.connect(self._ao_confirmar_busca_global)

        self.terminal_tabs = TerminalTabWidget()

        self.terminal_tabs.navegar_para_erro.connect(self._ao_navegar_erro_terminal)
        self.terminal_tabs.abrir_arquivo_solicitado.connect(self.abrir_arquivo)

        self.terminal_tabs.executar_solicitado.connect(self.executar_codigo)

        self.terminal_tabs.debug_solicitado.connect(self._iniciar_debug)

        self.terminal_tabs.aba_vai_fechar.connect(self._ao_fechar_aba_terminal)

        splitter_col2.addWidget(self.terminal_tabs)
        self.terminal_tabs.hide()  # só aparece ao abrir projeto

        splitter_col2.setSizes(SPLITTER_COL2)

        _cor_cen2 = _tg().cor("interface.fundo_painel_central", "#0A1210")

        card_central = PainelCard(_cor_cen2)

        card_central._layout.addWidget(splitter_col2)

        splitter_principal.addWidget(card_central)

        self.tabs.currentChanged.connect(self._ao_trocar_aba_editor_json)

        self.tabs.currentChanged.connect(self._ao_trocar_aba_imagem)

        self.tabs.currentChanged.connect(self._ao_trocar_aba_breakpoint)

        self.tabs.aba_fechada.connect(self._ao_fechar_aba_editor)

        splitter_principal.setSizes(SPLITTER_PRINCIPAL)

        # Injeta splitters na barra de título agora que todos existem

        self._barra_aba_topo.injetar_splitters(

            {

                "principal": self._splitter_principal,

                "col1": self._splitter_col1,

                "col2": self._splitter_col2,

            }

        )

        # IMP-09: restaura visibilidade dos painéis (arquivos/git/terminal/IA)
        # e tamanhos de todos os splitters, salvos da última vez que a IDE
        # fechou. Não depende de projeto aberto.
        # projeto aberto.
        QTimer.singleShot(100, self._restaurar_layout_paineis)

        self.statusBar().showMessage("Pronto")

        # ── widgets permanentes da statusbar (direita → esquerda) ─────

        from _UTILITARIOS_.hein_python_picker import HeinPythonPicker
        from _CONFIGURA_ import PASTA_APPDATA
        self._python_picker = HeinPythonPicker(janela=self)

        self._lbl_projeto_info = QLabel("informa ")

        self._lbl_projeto_info.setStyleSheet(

            f"color: {tema_global().cor('interface.texto_fraco', '#6b8f6b')};"

            f" font-size: 11px; padding: 0 8px;"

        )

        btn_appdata = QPushButton()

        btn_appdata.setIcon(icone_tema("mdi.folder-cog-outline"))

        btn_appdata.setIconSize(QSize(16, 16))

        btn_appdata.setToolTip(f"Abrir pasta de configuracao\n{PASTA_APPDATA}")

        btn_appdata.setFixedSize(22, 22)

        btn_appdata.setCursor(Qt.PointingHandCursor)

        btn_appdata.setStyleSheet(

            "QPushButton { background: transparent; border: none; padding: 0; }"

            "QPushButton:hover { background: #1a2a1a; border-radius: 3px; }"

        )

        btn_appdata.clicked.connect(self._abrir_pasta_appdata)

        # ordem: projeto_info | cursor | python_picker | btn_appdata

        self.statusBar().addPermanentWidget(self._lbl_projeto_info)

        self.statusBar().addPermanentWidget(self._python_picker)

        self.statusBar().addPermanentWidget(btn_appdata)

        # log_print → status bar (output do usuário aparece aqui também)

        try:
            from _UTILITARIOS_.log_print import log_print
            log_print.status_msg.connect(

                lambda msg, ms: self.statusBar().showMessage(msg, ms)

            )

        except Exception:
            pass

        self.tabs.currentChanged.connect(self._ao_trocar_aba_cursor)

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QColor
        painter = QPainter(self)

        cor = tema_global().cor("interface.contorno_ui", "transparent")
        qc  = QColor(cor)
        if qc.isValid() and qc.alpha() > 0:
            painter.fillRect(self.rect(), qc)

        painter.end()

    # ── Sincronização de estado da janela ───────────────────────────────────

    def changeEvent(self, event):
        """Sincroniza botão maximizar quando o Windows muda o estado da janela
        (snap, Win+↑, duplo-clique no título nativo, etc.)."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.WindowStateChange:
            _max = self.isMaximized()
            bld  = getattr(self, '_barra_lateral_direita', None)
            if bld is not None:
                bld.sincronizar_estado_max(_max)
            bat  = getattr(self, '_barra_aba_topo', None)
            if bat is not None:
                bat._maximizado = _max
        super().changeEvent(event)

    def nativeEvent(self, event_type, message):
        """WM_NCHITTEST: bordas de resize + HTCAPTION para Windows Snap via drag."""
        import sys
        if sys.platform != 'win32':
            return super().nativeEvent(event_type, message)

        import ctypes
        import ctypes.wintypes as _wt
        WM_NCHITTEST = 0x0084
        msg = ctypes.cast(int(message), ctypes.POINTER(_wt.MSG)).contents
        if msg.message == WM_NCHITTEST:
            from PySide6.QtCore import QPoint
            from PySide6.QtWidgets import QApplication
            x = ctypes.c_int16(msg.lParam & 0xFFFF).value
            y = ctypes.c_int16((msg.lParam >> 16) & 0xFFFF).value
            pos = self.mapFromGlobal(QPoint(x, y))
            pw, ph = self.width(), self.height()
            brd = 6   # px da borda de resize
            maximizado = self.isMaximized()

            # Bordas de resize (só quando não maximizado)
            if not maximizado:
                esq    = pos.x() < brd
                dir_   = pos.x() > pw - brd
                topo   = pos.y() < brd
                baixo  = pos.y() > ph - brd
                if topo  and esq:   return True, 13  # HTTOPLEFT
                if topo  and dir_:  return True, 14  # HTTOPRIGHT
                if baixo and esq:   return True, 16  # HTBOTTOMLEFT
                if baixo and dir_:  return True, 17  # HTBOTTOMRIGHT
                if topo:            return True, 12  # HTTOP
                if baixo:           return True, 15  # HTBOTTOM
                if esq:             return True, 10  # HTLEFT
                if dir_:            return True, 11  # HTRIGHT

            # HTCAPTION na barra de título → Windows Snap ao arrastar
            barra   = getattr(self, '_barra_aba_topo', None)
            barra_h = barra.height() if barra else 28
            bld_w   = 30   # largura fixa da BarraLateralDireita
            if pos.y() < barra_h and pos.x() < pw - bld_w:
                widget_sob = QApplication.widgetAt(QPoint(x, y))
                def _widget_interativo(w):
                    """Retorna True se w ou qualquer ancestral é interativo (botão, input, aba)."""
                    from PySide6.QtWidgets import QAbstractButton, QLineEdit
                    try:
                        from _APP_.barra_aba_topo import AbaWidget, MaisAbasWidget
                    except Exception:
                        AbaWidget = type(None)
                        MaisAbasWidget = type(None)
                    tipos = (QAbstractButton, QLineEdit, AbaWidget, MaisAbasWidget)
                    while w is not None:
                        if isinstance(w, tipos):
                            return True

                        w = w.parent()

                    return False

                if not _widget_interativo(widget_sob):
                    return True, 2   # HTCAPTION

            return True, 1   # HTCLIENT

        return super().nativeEvent(event_type, message)

    # ⚠️  except genérico vazio

    def closeEvent(self, event):
        try:
            from _LOG_.log import log
            log.info("base.py", "closeEvent", "\n")
            log.info("base.py", "closeEvent", "═" * 70)
            log.info(
                "base.py",
                "closeEvent",
                f">>> FECHAMENTO DA MAINWINDOW: projeto={self.current_project_path} <<<",
            )
            log.info("base.py", "closeEvent", "═" * 70)
            log.info("base.py", "closeEvent", "\n")
        except Exception:
            pass
        try:
            from _LOG_.log import log
            log.info(
                "base.py",
                "closeEvent",
                f"MainWindow fechando: projeto={self.current_project_path}",
            )
        except Exception:
            pass
        if self._fechando_ide:
            event.accept()
            return

        self._fechando_ide = True
        _fg_close = None

        try:
            # ── Overlay de fechamento ─────────────────────────────────────────────
            # O guard é aberto manualmente aqui, portanto precisa ser fechado
            # explicitamente no finally. Sem __exit__(), o overlay fica preso
            # na janela e o processo não conclui visualmente o shutdown.
            try:
                from _UTILITARIOS_.freeze_guard import FreezeGuard as _FG
                _fg_close = _FG(self, "Fechando hein IDE…")
                _fg_close.__enter__()
            except Exception:
                _fg_close = None

            from _THREADS_.ciclo_vida import executar_shutdown

            # A ordem é centralizada: cada etapa falha isoladamente para que um
            # editor problemático não impeça os demais recursos de encerrarem.
            executar_shutdown(
                "terminal_tabs.encerrar_todos_processos",
                self.terminal_tabs.encerrar_todos_processos,
            )
            executar_shutdown(
                "indexador.parar",
                lambda: self._indexador.parar()
                if getattr(self, "_indexador", None) else None,
            )
            for editor in list(self.tabs.editores.values()):
                executar_shutdown(
                    "editor.encerrar_threads_bg",
                    editor.encerrar_threads_bg,
                )
            executar_shutdown(
                "painel_arquivos.encerrar_threads_bg",
                lambda: self.painel_arquivos.encerrar_threads_bg()
                if hasattr(self, "painel_arquivos") else None,
            )

            try:
                from _APPDATA_.backup import fazer_backup
                fazer_backup()
            except Exception:
                pass

            if hasattr(self, "_gerenciador_abas"):
                try:
                    self._gerenciador_abas.salvar_sessao(
                        self.current_project_path or ""
                    )
                except Exception:
                    pass

            try:
                self._salvar_layout_paineis()  # IMP-09
            except Exception:
                pass

            # O picker em modo dialog pertence a este mesmo processo. Não
            # deixá-lo manter o QApplication vivo depois que o editor fechou.
            picker = getattr(self, "_picker_dialog", None)
            if picker is not None:
                try:
                    if picker.isVisible():
                        try:
                            from _LOG_.log import log
                            log.info(
                                "base.py",
                                "closeEvent",
                                "fechando JanelaPicker dialog junto com MainWindow",
                            )
                        except Exception:
                            pass
                        picker.close()
                except RuntimeError:
                    # WA_DeleteOnClose já pode ter destruído o C++ object,
                    # mantendo apenas o wrapper Python em _picker_dialog.
                    try:
                        from _LOG_.log import log
                        log.erro(
                            "base.py",
                            "closeEvent",
                            "JanelaPicker dialog já estava destruída ao fechar MainWindow",
                        )
                    except Exception:
                        pass
                    self._picker_dialog = None

            event.accept()
        finally:
            if _fg_close is not None:
                try:
                    _fg_close.__exit__(None, None, None)
                except Exception:
                    pass

            try:
                from _LOG_.log import log
                log.info("base.py", "closeEvent", "shutdown concluído — encerrando QApplication")
            except Exception:
                pass

            super().closeEvent(event)
            app = QApplication.instance()
            if app is not None:
                QTimer.singleShot(0, app.quit)

    # ── Picker dialog ─────────────────────────────────────────────────────────

    def _abrir_picker_dialog(self):
        """Abre o JanelaPicker em modo não-modal — permite selecionar/clonar
        projetos sem fechar a janela de editor atual."""
        picker_atual = getattr(self, "_picker_dialog", None)
        if picker_atual is not None:
            try:
                if picker_atual.isVisible():
                    picker_atual.raise_()
                    picker_atual.activateWindow()
                    return
            except RuntimeError:
                # A janela foi fechada com WA_DeleteOnClose. A referência
                # Python pode sobreviver ao C++ object destruído.
                self._picker_dialog = None

        from _APP_.Boas_Vindas.janela_picker import JanelaPicker
        picker = JanelaPicker(modo="dialog", parent=None)
        self._picker_dialog = picker
        try:
            from _LOG_.log import log
            log.info("base.py", "_abrir_picker_dialog", "JanelaPicker criada: modo=dialog")
        except Exception:
            pass
        picker.destroyed.connect(
            lambda _obj=None, p=picker: (
                setattr(self, "_picker_dialog", None)
                if getattr(self, "_picker_dialog", None) is p else None
            )
        )
        picker.show()
        try:
            from _LOG_.log import log
            log.info("base.py", "_abrir_picker_dialog", "JanelaPicker.show() chamado: modo=dialog")
        except Exception:
            pass
