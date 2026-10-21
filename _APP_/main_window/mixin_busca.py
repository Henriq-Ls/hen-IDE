"""MixinBusca — barra de busca global/local e navegação de resultados.

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



class MixinBusca:
    """barra de busca global/local e navegação de resultados.

    Mixin combinado em MainWindow — depende dos atributos criados por
    MainWindowBase.__init__/_montar_ui (self.tabs, self.painel_arquivos, etc.)."""

    def _ao_navegar_outline(self, caminho: str, linha: int):
        """Abre o arquivo e vai para a linha — chamado pelo outline na busca global."""

        for indice, editor in self.tabs.editores.items():
            if getattr(editor, "file_path", None) == caminho:
                self.tabs.setCurrentIndex(indice)

                editor.ir_para_linha(linha)

                editor.setFocus()

                return

        # Arquivo novo: aguarda o code_lens (400ms) antes de navegar

        editor = self.tabs.add_new_tab(caminho)

        QTimer.singleShot(450, lambda: (editor.ir_para_linha(linha), editor.setFocus()))

    def _ao_buscar_global(self, termo: str):
        """Roteia busca global por prefixo: @ grep, * arquivo, # anotação, > comando."""

        t = termo.strip()

        self._ultimo_termo_global = t

        if t.startswith("@") and len(t) > 1:
            self._painel_busca_global.limpar()

            self.terminal_tabs.abrir_aba_busca_global(self._painel_busca_global)

            self.terminal_tabs.setVisible(True)

            self._motor_busca.buscar(

                t,

                lambda _: None,

                self._painel_busca_global.adicionar_resultado,

                self._painel_busca_global.busca_concluida,

            )

        elif t.startswith("*"):
            self._ultimo_filtro_arvore = t[1:].strip()

            editor = self.tabs.get_current_editor()
            if editor and hasattr(editor, "_outline"):
                editor._outline.iniciar_busca_global(self._ultimo_filtro_arvore)

            self._timer_filtro_arvore.start(300)  # debounce 300ms

        elif t.startswith("#marcação") or t.startswith("#marcacao"):
            self._painel_busca_global.limpar()
            self.terminal_tabs.abrir_aba_busca_global(self._painel_busca_global)
            self.terminal_tabs.setVisible(True)
            self._motor_busca.buscar(
                t,
                lambda _: None,
                self._painel_busca_global.adicionar_resultado,
                self._painel_busca_global.busca_concluida,
            )

        elif t.startswith("#"):
            editor = self.tabs.get_current_editor()

            if editor and hasattr(editor, "_outline"):
                editor._outline._alternar_modo("TAREFAS")

        elif t.startswith("$") and len(t) > 1:
            self._painel_busca_global.limpar()

            self.terminal_tabs.abrir_aba_busca_global(self._painel_busca_global)

            self.terminal_tabs.setVisible(True)

            def _cb_simbolos(resultados):
                for r in resultados:
                    self._painel_busca_global.adicionar_resultado(r)

                self._painel_busca_global.busca_concluida()

            self._motor_busca.buscar(t, _cb_simbolos)

        elif t.startswith(">"):
            # Ctrl+K / digitacao manual de ">" — popup flutuante, nao painel inferior
            from _LOG_.log import log
            log.debug("mixin_busca.py", "_ao_buscar_global", f"prefixo '>': '{t}'")
            self._barra_central.limpar()
            self._command_palette.mostrar(filtro=t[1:].strip())

    def _ao_filtrar_arvore_debounced(self):
        """Disparado 300ms depois da última tecla em '*busca' (debounce).
        Atualiza a árvore de arquivos filtrada E, se houver mais de um
        arquivo com o mesmo padrão em pastas diferentes, lista todos na
        OUTLINE (painel_outline.py, modo BUSCA) pra o usuário escolher —
        sem isso o Enter só abria o primeiro que encontrasse, escondendo
        os outros. NÃO usa mais painel/widget novo — reaproveita a outline
        do editor, que já tem esse modo pronto (iniciar_busca_global /
        mostrar_busca_motor)."""
        from _BUSCA_.modelo_resultado import ResultadoBusca, TipoBusca
        import os as _os

        self.painel_arquivos._filtrar_arvore(self._ultimo_filtro_arvore)

        editor = self.tabs.get_current_editor()
        outline = getattr(editor, "_outline", None)

        if not self._ultimo_filtro_arvore:
            if outline:
                outline._alternar_modo("OUTLINE")
            return

        caminhos = self.painel_arquivos._buscar_todos_resultados()

        if not outline:
            return

        if len(caminhos) > 1:
            resultados = [
                ResultadoBusca(
                    tipo=TipoBusca.ARQUIVO,
                    titulo=_os.path.basename(caminho),
                    subtitulo=_os.path.dirname(caminho),
                    caminho=caminho,
                    linha=-1,
                )
                for caminho in caminhos
            ]

            outline.mostrar_busca_motor(resultados)
        else:
            outline._alternar_modo("OUTLINE")

    def _ao_fechar_busca_global(self):
        self._motor_busca.cancelar_grep()

        self._ultimo_termo_global = ""

        self.painel_arquivos._filtrar_arvore("")

        editor = self.tabs.get_current_editor()

        if editor and hasattr(editor, "_outline"):
            editor._outline.desativar_modo_busca_inline()
            editor._outline._alternar_modo("OUTLINE")

        if editor:
            editor.setFocus()

    def _ao_confirmar_busca_global(self):
        """Enter na BarraCentral — roteia confirmação por prefixo."""

        from _LOG_.log import log
        texto = self._barra_central._campo.toPlainText().strip()

        # ── :N — ir para linha ────────────────────────────────────────

        if texto.startswith(":"):
            try:
                n = int(texto[1:].strip())

            except ValueError:
                return

            editor = self.tabs.get_current_editor()

            if editor:
                log.debug("mixin_busca.py", "_ao_confirmar_busca_global", f":N → linha {n}")

                editor.ir_para_linha(n)

                editor.setFocus()

            self._barra_central.limpar()

            return

        # ── * — abrir primeiro arquivo filtrado ───────────────────────

        if texto.startswith("*"):
            # Se há 2+ arquivos com o mesmo nome/padrão em pastas diferentes,
            # a outline (modo BUSCA) já está listando todos — não abre nenhum
            # "no escuro", só passa o foco pra árvore pro usuário escolher.
            editor = self.tabs.get_current_editor()
            outline = getattr(editor, "_outline", None)

            if outline and outline.contar_resultados_busca() > 1:
                outline.focar_arvore()
                return

            caminho = self.painel_arquivos._abrir_primeiro_resultado()

            if not caminho:
                return

            self._barra_central.limpar()

            self._ao_navegar_outline(caminho, 0)

    def _ao_abrir_resultado_grep(self, caminho: str, linha: int, coluna: int):
        """Abre arquivo na linha — chamado ao clicar no PainelBuscaGlobal."""

        self._ao_navegar_outline(caminho, linha)

    def _ao_trocar_aba_busca_inline(self):
        """Ao mudar de aba com a BarraCentral aberta em busca inline (Ctrl+F),
        reexecuta a busca no editor que ficou em foco agora. Sem isso, o
        contador/realce ficava "preso" no resultado da aba anterior, porque
        trocar de aba só atualizava a referência do editor (set_editor),
        nunca disparava a busca de novo no editor novo."""

        if not self._barra_central.isVisible():
            return

        termo = self._barra_central.texto()

        if not termo or termo[0] in "@*#$>:":
            # prefixos de busca global/linha — não é busca inline por aba
            return

        self._ao_buscar_arquivo(termo)

    def _ao_buscar_arquivo(self, termo: str):
        """Ctrl+F / texto sem prefixo — busca inline no arquivo atual."""

        editor = self.tabs.get_current_editor()

        if not editor or not hasattr(editor, "_outline"):
            return

        if not termo:
            # campo limpo: limpa destaques mas mantém barra central visível

            editor._outline._limpar_destaques_inline()

            editor._outline._atualizar_contador_bc("0/0")

        else:
            editor._outline.ativar_modo_arquivo_inline(termo)

    def _ao_ir_para_linha(self, n: int):
        """:N — pede ao outline que exiba o atalho de ir para linha N."""

        editor = self.tabs.get_current_editor()

        if editor and hasattr(editor, "_outline"):
            editor._outline.ativar_modo_linha(n)

    def _ao_modo_substituicao(self, termo: str):
        """Ctrl+H — exibe campo de substituição no Outline."""

        editor = self.tabs.get_current_editor()

        if editor and hasattr(editor, "_outline"):
            editor._outline.ativar_modo_substituicao(termo)

    # ⚠️  função grande (53 linhas)

    def _ao_selecionar_resultado_busca(self, resultado):
        import os as _os
        from _BUSCA_.modelo_resultado import TipoBusca
        self._barra_central.limpar()

        if resultado.tipo == TipoBusca.COMANDO:
            if callable(resultado.acao):
                resultado.acao()

            return

        if resultado.tipo == TipoBusca.LINHA:
            editor = self.tabs.get_current_editor()

            if editor and resultado.linha >= 0:
                editor.ir_para_linha(resultado.linha)

                editor.centerCursor()

                editor.setFocus()

            return

        if resultado.caminho:
            def _normalizar(p):
                try:
                    return _os.path.normcase(_os.path.abspath(p))

                except Exception:
                    return p

            alvo = _normalizar(resultado.caminho)

            for indice, editor in self.tabs.editores.items():
                ep = getattr(editor, "file_path", None)

                if ep and _normalizar(ep) == alvo:
                    self.tabs.setCurrentIndex(indice)

                    if resultado.linha >= 0:
                        editor.ir_para_linha(resultado.linha)

                        editor.centerCursor()

                    editor.setFocus()

                    return

            editor = self.tabs.add_new_tab(resultado.caminho)

            if editor and resultado.linha >= 0:
                QTimer.singleShot(

                    450,

                    lambda: (

                        editor.ir_para_linha(resultado.linha),

                        editor.centerCursor(),

                        editor.setFocus(),

                    ),

                )

    # ══════════════════════════════════════════════════════════════════

    # Projetos e arquivos

    # ══════════════════════════════════════════════════════════════════

    # ⚠️  função grande (58 linhas)

    def buscar_no_projeto(self):
        """Ctrl+J — abre barra de busca com prefixo @ (grep no projeto)."""

        from _LOG_.log import log
        log.info("mixin_busca.py", "buscar_no_projeto", "abrindo barra com prefixo @")

        self._barra_central.mostrar("arquivo")

        self._barra_central.focar("@")

    # ══════════════════════════════════════════════════════════════════

    # Abas / busca

    # ══════════════════════════════════════════════════════════════════

    def abrir_busca(self, termo: str = ""):
        if not termo:
            editor = self.tabs.get_current_editor()

            if editor:
                cursor = editor.textCursor()

                if cursor.hasSelection():
                    termo = cursor.selectedText()

        self._barra_central.mostrar("arquivo")

        self._barra_central.focar(termo)

    def abrir_substituicao_barra(self):
        editor = self.tabs.get_current_editor()

        if not editor:
            return

        cursor = editor.textCursor()

        termo = cursor.selectedText() if cursor.hasSelection() else ""

        self._barra_central.focar(termo)

        self._barra_central.ativar_substituicao(termo)

    def focar_barra_linha(self):
        self._barra_central.mostrar("linha")

        self._barra_central.focar(":")

    def focar_barra_marcacao(self):
        self._barra_central.mostrar("arquivo")

        self._barra_central.focar("#marcação")

    def focar_barra_arquivo_nome(self):
        """Ctrl+P — foca a barra central com prefixo * (busca por nome de arquivo)."""

        self._barra_central.mostrar("arquivo")

        self._barra_central.focar("*")

    def abrir_command_palette(self):
        """Ctrl+K — abre CommandPalette como popup flutuante."""

        from _LOG_.log import log
        log.info("mixin_busca.py", "abrir_command_palette", "abrindo command palette popup")

        self._command_palette.mostrar()

    def abrir_substituicao(self):
        """Ctrl+H — ativa modo substituição no Outline do editor ativo."""

        editor = self.tabs.get_current_editor()

        termo = ""

        if editor:
            c = editor.textCursor()

            if c.hasSelection():
                termo = c.selectedText()

        self._barra_central.mostrar("substituicao")

        self._barra_central.focar(termo)

        self._barra_central.ativar_substituicao(termo)

    def _ao_buscar_arquivo_central(self, termo: str):
        editor = self.tabs.get_current_editor()

        if editor and hasattr(editor, "_ao_buscar_inline"):
            editor._ao_buscar_inline(termo)

    def _ao_buscar_anterior_central(self):
        editor = self.tabs.get_current_editor()

        if editor and hasattr(editor, "_ao_buscar_inline_anterior"):
            editor._ao_buscar_inline_anterior()

    def _ao_buscar_projeto_central(self, termo: str):
        self.painel_arquivos._filtrar_arvore(termo)

        editor = self.tabs.get_current_editor()

        if editor and hasattr(editor, "_outline"):
            editor._outline._input_busca.setText(termo)

    def _ao_buscar_lembrar_central(self, prefixo: str):
        editor = self.tabs.get_current_editor()

        if editor and hasattr(editor, "_outline"):
            editor._outline._alternar_modo("tarefas")

            editor._outline._input_busca.setText(prefixo)
