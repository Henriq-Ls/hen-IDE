"""MixinTerminalDebug — execução, debug, breakpoints e terminal.

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

    BORDA_CONTORNO_UI)

from _EDITOR_.Indexador import Indexador
from ..barra_aba_topo import BarraTitulo
from ..barra_lateral_direita import BarraLateralDireita
from _BUSCA_.motor_busca import MotorBusca
from _BUSCA_.painel_busca_global import PainelBuscaGlobal
from _BUSCA_.command_palette import CommandPalette
from _BUSCA_.busca_comandos import buscar_comandos



class MixinTerminalDebug:
    """execução, debug, breakpoints e terminal.

    Mixin combinado em MainWindow — depende dos atributos criados por
    MainWindowBase.__init__/_montar_ui (self.tabs, self.painel_arquivos, etc.)."""

    def executar_codigo(self):
        """Executa o código do editor atual no terminal."""

        editor = self.tabs.get_current_editor()

        if not editor:
            terminal = self.terminal_tabs.obter_ou_criar_saida(nome="Saída")

            terminal.append_output("Erro: nenhum editor aberto!\n")

            return

        codigo = editor.toPlainText()

        if not codigo.strip():
            terminal = self.terminal_tabs.obter_ou_criar_saida(nome="Saída")

            terminal.append_output("Erro: o arquivo está vazio!\n")

            return

        # Definir nome e arquivo_exec ANTES de usar

        if editor.file_path:
            arquivo_exec = editor.file_path

            nome = os.path.basename(arquivo_exec)

        else:
            nome = "temp.py"

            with tempfile.NamedTemporaryFile(

                mode="w", suffix=".py", delete=False, encoding="utf-8"

            ) as f:
                f.write(codigo)

                arquivo_exec = f.name

        # Despacha para ExecutorTerminal se a linguagem suporta execucao nativa

        if editor.file_path:
            _ext_exec = os.path.splitext(arquivo_exec)[1].lower()

            from _EDITOR_.Mult_Linguas import get_provider as _gp
            _pv = _gp(_ext_exec)

            _run_exts = _pv.run_extensoes if _pv.run_extensoes else _pv.extensions

            if _pv.can_run and _ext_exec in _run_exts:
                self.terminal_tabs.abrir_executor_terminal(_pv.name, arquivo_exec)

                self.statusBar().showMessage(f"Executando: {nome}")

                return

            if _pv.name != 'Python':
                return  # linguagem sem executor — F1 silencioso

        # Agora sim: criar/obter terminal com nome definido

        terminal_run = self.terminal_tabs.obter_ou_criar_saida(nome=nome)

        if not getattr(terminal_run, "_nav_conectado", False):
            terminal_run.navegar_para_erro.connect(self._ao_navegar_erro_terminal)

            terminal_run._nav_conectado = True

        terminal_run.clear()

        terminal_run.imprimir_separador(nome)

        try:
            terminal_run.executar_python(

                arquivo_exec, python_path=self._pegar_python_projeto()

            )

            self.statusBar().showMessage(f"Executando: {nome}")

        finally:
            if not editor.file_path:
                atexit.register(

                    lambda p=arquivo_exec: os.path.exists(p) and os.remove(p)

                )

    def _iniciar_debug(self):
        """

        Abre o painel de depuração e inicia uma sessão real com debugpy.

        Chamado ao clicar no botão 🐛 da barra de terminais.

        """

        editor  = self.tabs.get_current_editor()

        arquivo = (editor.file_path or "") if editor else ""

        painel  = self.terminal_tabs.abrir_aba_debug(arquivo=arquivo)

        if not editor:
            self.statusBar().showMessage("Depurador: nenhum editor aberto")

            return

        if not arquivo:
            self.statusBar().showMessage(

                "Depurador: salve o arquivo antes de iniciar uma sessão"

            )

            return

        python_path = self._pegar_python_projeto()

        bps = editor.area_numeros.get_breakpoints() if editor else set()

        painel.iniciar_sessao(arquivo=arquivo, python_path=python_path, breakpoints=bps)

        self.statusBar().showMessage(

            f"Depurador iniciando: {os.path.basename(arquivo)}"

        )

    def _ao_navegar_erro_terminal(self, caminho: str, linha: int):
        """Clique em traceback do terminal Run → abre arquivo na linha do erro."""

        if not caminho:
            return

        for indice, editor in self.tabs.editores.items():
            if getattr(editor, "file_path", None) == caminho:
                self.tabs.setCurrentIndex(indice)

                editor.ir_para_linha(linha)

                editor.setFocus()

                return

        editor = self.tabs.add_new_tab(caminho)

        QTimer.singleShot(450, lambda: (editor.ir_para_linha(linha), editor.setFocus()))

    def _ao_indexar_concluido(self, resumo: dict):
        """CodeLens de todos os editores após indexação completa em background."""

        for editor in self.tabs.editores.values():
            editor._atualizar_code_lens()

    def _ir_para_linha_no_editor(self, linha: int):
        editor = self.tabs.get_current_editor()

        if editor:
            editor.ir_para_linha(linha)

            editor.setFocus()

    # ══════════════════════════════════════════════════════════════════

    # Edição básica

    # ══════════════════════════════════════════════════════════════════

    # ⚠️  except genérico vazio

    def _ao_trocar_aba_cursor(self, _=None):
        """Conecta o signal cursorPositionChanged do editor ativo ao label Ln/Col."""

        # desconecta o editor ANTERIOR antes de trocar

        editor_anterior = getattr(self, "_editor_cursor_ativo", None)

        if editor_anterior is not None:
            try:
                editor_anterior.cursorPositionChanged.disconnect(

                    self._atualizar_lbl_cursor

                )

            except Exception:
                pass

        editor = self.tabs.get_current_editor()

        if not editor:
            self._editor_cursor_ativo = None

            return

        self._editor_cursor_ativo = editor

        editor.cursorPositionChanged.connect(self._atualizar_lbl_cursor)

        self._atualizar_lbl_cursor()

    def _atualizar_lbl_cursor(self):
        editor = self.tabs.get_current_editor()

        if not editor:
            return

        cursor = editor.textCursor()

        linha = cursor.blockNumber() + 1

        col = cursor.columnNumber() + 1

    def _atualizar_gutter_pos_commit(self):
        """Atualiza a barra git do gutter após um commit, re-executando git diff HEAD."""

        editor = getattr(self, "_editor_cursor_ativo", None)

        if editor and hasattr(editor, "_iniciar_diff_gutter"):
            editor._iniciar_diff_gutter()

    # ⚠️  except genérico vazio

    def _ao_trocar_aba_breakpoint(self, _=None):
        """Reconecta o sinal breakpoint_clicado ao trocar de aba do editor."""

        editor_ant = getattr(self, '_editor_bp_ativo', None)

        if editor_ant is not None:
            try:
                editor_ant.area_numeros.breakpoint_clicado.disconnect(

                    self._ao_breakpoint_clicado

                )

            except Exception:
                pass

        editor = self.tabs.get_current_editor()

        if not editor:
            self._editor_bp_ativo = None

            return

        self._editor_bp_ativo = editor

        editor.area_numeros.breakpoint_clicado.connect(self._ao_breakpoint_clicado)

    def _ao_breakpoint_clicado(self, _linha: int):
        """

        Chamado quando o usuario clica na margem da calha para toggle de breakpoint.

        Sincroniza os breakpoints com o depurador ativo (se houver sessao em curso).

        """

        editor = self.tabs.get_current_editor()

        if not editor:
            return

        editor._salvar_estado_arquivo()

        painel_dbg = self.terminal_tabs.painel_debug_ativo()

        if painel_dbg is None:
            return

        arquivo = getattr(editor, 'file_path', '') or ''

        bps = editor.area_numeros.get_breakpoints()

        painel_dbg.sincronizar_breakpoints(arquivo, bps)

    def _abrir_aba_git_no_terminal(self):
        """Abre (ou substitui) a aba '⎇  Git' no terminal central.
        Chamado via sinal abrir_painel_git de GitUIProjeto."""
        ABA_NOME = "⎇  Git"

        # Remove aba antiga se existir (para sempre mostrar dados frescos)
        for i in range(self.terminal_tabs.count()):
            if self.terminal_tabs.tabText(i) == ABA_NOME:
                self.terminal_tabs.removeTab(i)
                break

        tela = self.painel_git._tela_projeto

        widget = tela.montar_painel_terminal()

        tela._atualizar_aba_por_indice(0)

        widget._is_git_terminal = True   # identificador para sair_modo_staging

        idx = self.terminal_tabs.addTab(widget, ABA_NOME)

        self.terminal_tabs.setCurrentIndex(idx)

        self.terminal_tabs.setVisible(True)

    def _abrir_historico_no_terminal(self, painel):
        """
        Abre (ou substitui) a aba 'Histórico Git' no terminal central.
        Chamado via sinal abrir_historico_terminal de GitUIProjeto.
        """
        ABA_NOME = "⏱  Histórico Git"

        # Remove aba antiga se existir (para sempre mostrar dados frescos)
        for i in range(self.terminal_tabs.count()):
            if self.terminal_tabs.tabText(i) == ABA_NOME:
                self.terminal_tabs.removeTab(i)
                break

        idx = self.terminal_tabs.addTab(painel, ABA_NOME)
        self.terminal_tabs.setCurrentIndex(idx)
        self.terminal_tabs.setVisible(True)

    def abrir_executavel_config(self, modo="executavel"):
        """Abre/reutiliza o Explorer de build para o projeto ativo."""
        projeto = getattr(self, "current_project_path", None)
        if not projeto or not os.path.isdir(projeto):
            QMessageBox.warning(self, "Projeto não selecionado", "Abra um projeto primeiro.")
            return

        from _EXECUTAVEL_.config import obter_arquivo_config
        from _TERMINAIS_.executavel_explorer import ExecutavelExplorer

        caminho = obter_arquivo_config(projeto)
        painel = getattr(self.painel_git, "executavel", None)
        self.painel_git.mostrar_executavel()
        for i in range(self.terminal_tabs.count()):
            widget = self.terminal_tabs.widget(i)
            if isinstance(widget, ExecutavelExplorer) and widget._caminho == caminho:
                widget._modo = modo
                widget._recarregar_se_necessario()
                widget._atualizar_botao_principal()
                self.terminal_tabs.setCurrentIndex(i)
                self.terminal_tabs.setVisible(True)
                return

        explorer = ExecutavelExplorer(
            caminho,
            painel_executavel=painel,
        )
        indice = self.terminal_tabs.addTab(
            explorer,
            icone_tema("mdi.package-variant-closed"),
            "Executável",
        )
        self.terminal_tabs.setCurrentIndex(indice)
        self.terminal_tabs.setVisible(True)

    def alternar_terminal(self):
        self.terminal_tabs.setVisible(not self.terminal_tabs.isVisible())

    def novo_terminal(self):
        self.terminal_tabs.add_new_terminal("powershell")

        self.terminal_tabs.setVisible(True)

    def fechar_terminal_ativo(self):
        self.terminal_tabs.fechar_aba(self.terminal_tabs.currentIndex())

    def limpar_terminal_ativo(self):
        terminal = self.terminal_tabs.terminal_ativo()

        if terminal:
            if hasattr(terminal, "clear_terminal"):
                terminal.clear_terminal()

            elif hasattr(terminal, "clear"):
                terminal.clear()

    def abrir_painel_erros(self):
        QMessageBox.information(self, "Em breve", "Painel de erros em breve!")

    # ══════════════════════════════════════════════════════════════════

    # Tarefas

    # ══════════════════════════════════════════════════════════════════

    def tarefa_criar_venv(self):
        if not self.current_project_path:
            QMessageBox.warning(self, "Aviso", "Abra um projeto primeiro.")

            return

        t = self.terminal_tabs.terminal_ativo()

        if t and hasattr(t, "enviar_comando"):
            t.enviar_comando("python -m venv .venv")

            self.statusBar().showMessage("Criando ambiente virtual...")

    def tarefa_ativar_venv(self):
        if not self.current_project_path:
            QMessageBox.warning(self, "Aviso", "Abra um projeto primeiro.")

            return

        t = self.terminal_tabs.terminal_ativo()

        if t and hasattr(t, "enviar_comando"):
            t.enviar_comando(

                ".venv\\Scripts\\activate && python -m pip install --upgrade pip setuptools wheel"

            )
