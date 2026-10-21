"""MixinAtalhos — atalhos de edição/navegação do editor.

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



class MixinAtalhos:
    """atalhos de edição/navegação do editor.

    Mixin combinado em MainWindow — depende dos atributos criados por
    MainWindowBase.__init__/_montar_ui (self.tabs, self.painel_arquivos, etc.)."""

    def desfazer(self):
        e = self.tabs.get_current_editor()

        if e:
            e.undo()

    def refazer(self):
        e = self.tabs.get_current_editor()

        if e:
            e.redo()

    def selecionar_tudo(self):
        e = self.tabs.get_current_editor()

        if e:
            e.selectAll()

    def recortar(self):
        e = self.tabs.get_current_editor()

        if e:
            e.cut()

    def copiar(self):
        e = self.tabs.get_current_editor()

        if e:
            e.copy()

    def colar(self):
        e = self.tabs.get_current_editor()

        if e:
            e.paste()

    # ══════════════════════════════════════════════════════════════════

    # Navegação

    # ══════════════════════════════════════════════════════════════════

    def ir_para_linha_dialogo(self):
        editor = self.tabs.get_current_editor()

        if not editor:
            return

        total = editor.document().blockCount()

        linha, ok = QInputDialog.getInt(

            self,

            "Ir para Linha",

            f"Número da linha (1 – {total}):",

            editor.textCursor().blockNumber() + 1,

            1,

            total,

        )

        if ok:
            editor.ir_para_linha(linha)

            editor.setFocus()

    def ir_para_inicio(self):
        e = self.tabs.get_current_editor()

        if not e:
            return

        c = e.textCursor()

        c.movePosition(QTextCursor.Start)

        e.setTextCursor(c)

        e.ensureCursorVisible()

    def ir_para_fim(self):
        e = self.tabs.get_current_editor()

        if not e:
            return

        c = e.textCursor()

        c.movePosition(QTextCursor.End)

        e.setTextCursor(c)

        e.ensureCursorVisible()

    def ir_para_definicao(self):
        e = self.tabs.get_current_editor()

        if e:
            e._ir_definicao.ir_para_definicao()

    def voltar_definicao(self):
        e = self.tabs.get_current_editor()

        if e:
            e._ir_definicao.voltar()

    def nova_linha_abaixo(self):
        e = self.tabs.get_current_editor()

        if not e:
            return

        cursor = e.textCursor()

        cursor.movePosition(QTextCursor.EndOfBlock)

        cursor.insertText("\n")

        e.setTextCursor(cursor)

        e.setFocus()

    def aumentar_fonte(self):
        e = self.tabs.get_current_editor()

        if e:
            e.aumentar_fonte()

    def diminuir_fonte(self):
        e = self.tabs.get_current_editor()

        if e:
            e.diminuir_fonte()

    def resetar_fonte(self):
        e = self.tabs.get_current_editor()

        if e:
            e.resetar_fonte()

    # ══════════════════════════════════════════════════════════════════

    # Manipulação de linhas

    # ══════════════════════════════════════════════════════════════════

    def mover_linha_cima(self):
        e = self.tabs.get_current_editor()

        if e:
            e.mover_linha_cima()

    def mover_linha_baixo(self):
        e = self.tabs.get_current_editor()

        if e:
            e.mover_linha_baixo()

    def comentar_linha(self):
        e = self.tabs.get_current_editor()

        if e:
            e.comentar_linha()

    def deletar_linha(self):
        e = self.tabs.get_current_editor()

        if e:
            e.deletar_linha()

    def duplicar_linha(self):
        e = self.tabs.get_current_editor()

        if e:
            e.duplicar_linha()

    def centralizar_linha_cursor(self):
        e = self.tabs.get_current_editor()

        if e:
            e.centralizar_linha_cursor()

    # ══════════════════════════════════════════════════════════════════

    # Múltiplos cursores

    # ══════════════════════════════════════════════════════════════════

    def adicionar_cursor_acima(self):
        e = self.tabs.get_current_editor()

        if e:
            e.adicionar_cursor_acima()

    def adicionar_cursor_abaixo(self):
        e = self.tabs.get_current_editor()

        if e:
            e.adicionar_cursor_abaixo()

    def selecionar_todas_ocorrencias(self):
        e = self.tabs.get_current_editor()

        if e:
            e.selecionar_todas_ocorrencias()

    def selecionar_proxima_ocorrencia(self):
        e = self.tabs.get_current_editor()

        if e:
            e.selecionar_proxima_ocorrencia()

    # ══════════════════════════════════════════════════════════════════

    # Dobramento

    # ══════════════════════════════════════════════════════════════════

    def recolher_bloco(self):
        e = self.tabs.get_current_editor()

        if e:
            e.recolher_bloco()

    def expandir_bloco(self):
        e = self.tabs.get_current_editor()

        if e:
            e.expandir_bloco()

    def recolher_tudo(self):
        e = self.tabs.get_current_editor()

        if e:
            e.recolher_tudo()

    def expandir_tudo(self):
        e = self.tabs.get_current_editor()

        if e:
            e.expandir_tudo()

    # ══════════════════════════════════════════════════════════════════

    # Terminal

    # ══════════════════════════════════════════════════════════════════

    # ⚠️  função grande (89 linhas)

    def alternar_outline(self):
        """Ctrl+Shift+O — Abre/fecha o outline do editor com foco atual.

        Usa _editor_focado() em vez de self.tabs.get_current_editor() para
        funcionar corretamente também nos painéis secundários criados por
        split — antes, o atalho sempre agia sobre o painel principal.
        """

        editor = self._editor_focado()

        if editor and hasattr(editor, "toggle_outline"):
            editor.toggle_outline()
            # Foca a arvore do outline ao abrir (setas funcionam)
            if (getattr(editor, "_largura_outline", 0) > 0
                    and hasattr(editor, "_outline")
                    and hasattr(editor._outline, "_arvore")):
                QTimer.singleShot(50, editor._outline._arvore.setFocus)

    def alternar_editor(self):
        """Ctrl+Shift+E — Foca o editor para continuar digitando."""
        editor = self._editor_focado() or self.tabs.get_current_editor()
        if editor:
            editor.setFocus()

    # DEPOIS
