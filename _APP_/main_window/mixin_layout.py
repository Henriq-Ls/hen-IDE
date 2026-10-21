"""MixinLayout — toggles de painéis, persistência de layout e menu Projeto.

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


class MixinLayout:
    """toggles de painéis, persistência de layout e menu Projeto.

    Mixin combinado em MainWindow — depende dos atributos criados por
    MainWindowBase.__init__/_montar_ui (self.tabs, self.painel_arquivos, etc.)."""

    def alternar_painel_arquivos(self):
        """Ctrl+P — Mostra/oculta a árvore de arquivos do projeto."""

        visivel = not self.painel_arquivos.isVisible()

        self.painel_arquivos.setVisible(visivel)

        # Recolhe/expande a coluna esquerda inteira conforme ambos os painéis

        git_vis = self.painel_git.isVisible()

        self._coluna_esquerda.setVisible(visivel or git_vis)

        if hasattr(self, "_acao_painel_arquivos"):
            self._acao_painel_arquivos.setChecked(visivel)
        # Foca a arvore de arquivos ao abrir (setas funcionam)
        if visivel and hasattr(self.painel_arquivos, "_tree"):
            QTimer.singleShot(50, self.painel_arquivos._tree.setFocus)

    def alternar_painel_git(self):
        """Ctrl+Shift+G — Mostra/oculta o painel do Git (controle de versão)."""

        visivel = not self.painel_git.isVisible()

        self.painel_git.setVisible(visivel)

        # Recolhe/expande a coluna esquerda inteira conforme ambos os painéis

        arq_vis = self.painel_arquivos.isVisible()

        self._coluna_esquerda.setVisible(visivel or arq_vis)

        if hasattr(self, "_acao_painel_git"):
            self._acao_painel_git.setChecked(visivel)

    # ══════════════════════════════════════════════════════════════════
    # IMP-09: Persistência de layout (visibilidade dos painéis + splitters)
    # ══════════════════════════════════════════════════════════════════

    def _restaurar_layout_paineis(self) -> None:
        """
        Restaura visibilidade de File Tree / Git / Terminal / IA e os
        tamanhos dos 3 splitters, salvos em layout.json na última vez que a
        IDE fechou. Chamado sempre no boot (Página Inicial ou não) — a
        disposição dos painéis é do usuário, não do projeto.
        """
        import json
        from _CONFIGURA_ import ARQUIVO_LAYOUT
        if not os.path.isfile(ARQUIVO_LAYOUT):
            return

        try:
            with open(ARQUIVO_LAYOUT, encoding="utf-8") as f:
                dados = json.load(f)
        except Exception:
            return

        paineis = dados.get("paineis")
        if isinstance(paineis, dict):
            try:
                if bool(paineis.get("arquivos", True)) != self.painel_arquivos.isVisible():
                    self.alternar_painel_arquivos()
                if bool(paineis.get("git", True)) != self.painel_git.isVisible():
                    self.alternar_painel_git()
                if bool(paineis.get("terminal", True)) != self.terminal_tabs.isVisible():
                    self.alternar_terminal()
            except Exception:
                pass

        splitters = dados.get("splitters")
        if isinstance(splitters, dict):
            for chave, splitter in (
                ("principal", self._splitter_principal),
                ("col1", self._splitter_col1),
                ("col2", self._splitter_col2),
            ):
                tamanhos = splitters.get(chave)
                if isinstance(tamanhos, list) and len(tamanhos) == splitter.count():
                    try:
                        splitter.setSizes([int(v) for v in tamanhos])
                    except Exception:
                        pass

    # ⚠️  except genérico vazio
    def _salvar_layout_paineis(self) -> None:
        """
        Persiste visibilidade dos painéis + tamanhos dos splitters em
        layout.json — chamado no closeEvent, junto com salvar_sessao().
        Faz merge com o conteúdo existente (tema/tema_json salvos pela
        barra de título) em vez de sobrescrever o arquivo inteiro.
        """
        import json
        from _CONFIGURA_ import ARQUIVO_LAYOUT, PASTA_APPDATA
        dados = {}
        if os.path.isfile(ARQUIVO_LAYOUT):
            try:
                with open(ARQUIVO_LAYOUT, encoding="utf-8") as f:
                    _lido = json.load(f)
                if isinstance(_lido, dict):
                    dados = _lido
            except Exception:
                dados = {}

        try:
            dados["paineis"] = {
                "arquivos": self.painel_arquivos.isVisible(),
                "git":      self.painel_git.isVisible(),
                "terminal": self.terminal_tabs.isVisible(),
                }
            dados["splitters"] = {
                "principal": self._splitter_principal.sizes(),
                "col1":      self._splitter_col1.sizes(),
                "col2":      self._splitter_col2.sizes(),
            }
            os.makedirs(PASTA_APPDATA, exist_ok=True)
            with open(ARQUIVO_LAYOUT, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def alternar_tela_cheia(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    # ══════════════════════════════════════════════════════════════════

    # Menu Projeto — Ctrl+1 a Ctrl+6

    # ══════════════════════════════════════════════════════════════════

    def abrir_tarefas_projeto(self):
        if not self.current_project_path:
            QMessageBox.information(self, "Aviso", "Nenhum projeto aberto.")

            return

        pasta = os.path.join(self.current_project_path, ".hein")

        os.makedirs(pasta, exist_ok=True)

        caminho = os.path.join(pasta, "tarefas.json")

        if not os.path.exists(caminho):
            import json as _json
            with open(caminho, "w", encoding="utf-8") as _f:
                _json.dump([], _f)

        # O atalho deve abrir as duas interfaces: o JSON no editor e o
        # Explorer no painel inferior. A troca para o JSON dispara o
        # roteamento automático, que reutiliza o Explorer se ele já existir.
        self.tabs.add_new_tab(caminho)
        self._abrir_tarefas_explorer(caminho, "projeto")

    def abrir_arquivo_atalhos(self):
        self.tabs.add_new_tab(ARQUIVO_ATALHOS)

    def abrir_arquivo_configuracoes(self):
        barra = getattr(self, "_barra_aba_topo", None)
        tema_ativo = getattr(barra, "_tema_json_atual", "") if barra else ""
        if not tema_ativo or not os.path.isfile(tema_ativo):
            tema_ativo = os.path.join(PASTA_APPDATA, "temas", "tema_padrao.json")
        self.tabs.add_new_tab(tema_ativo)

    def abrir_tarefas(self):
        from _CONFIGURA_ import ARQUIVO_TAREFAS_GLOBAIS
        caminho = ARQUIVO_TAREFAS_GLOBAIS

        os.makedirs(os.path.dirname(caminho), exist_ok=True)

        if not os.path.exists(caminho):
            import json as _json
            with open(caminho, "w", encoding="utf-8") as _f:
                _json.dump([], _f)

        # Mesmo fluxo das tarefas locais: editor + Explorer, sem duplicar
        # a aba do Explorer quando o roteamento automático já a criou.
        self.tabs.add_new_tab(caminho)
        self._abrir_tarefas_explorer(caminho, "global")

    def _abrir_tarefas_explorer(self, caminho: str, modo: str) -> None:
        """Abre (ou foca) o TarefasExplorer no painel de terminal.

        O JSON é aberto pelo handler do atalho antes desta função. A troca
        para a aba do editor pode criar o Explorer pelo roteamento automático;
        por isso esta função sempre procura e reutiliza a instância vinculada
        ao mesmo caminho antes de criar uma nova.
        """

        from _TERMINAIS_.Tarefas.tarefas_explorer import TarefasExplorer
        from _UTILITARIOS_.icones import icone_tema as _icone_te
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

        nome_aba = "Tarefas Globais" if modo == "global" else "Tarefas Locais"

        explorer = TarefasExplorer(caminho=caminho, modo=modo)

        idx = self.terminal_tabs.addTab(

            explorer, _icone_te("mdi.lightning-bolt-outline"), nome_aba

        )

        self.terminal_tabs.setCurrentIndex(idx)

        self.terminal_tabs.setVisible(True)

    def abrir_autocomplete(self):
        if not os.path.exists(ARQUIVO_AUTOCOMPLETE):
            QMessageBox.warning(

                self,

                "Arquivo não encontrado",

                f"autocomplete.json não encontrado em:\n{ARQUIVO_AUTOCOMPLETE}",

            )

            return

        self.tabs.add_new_tab(ARQUIVO_AUTOCOMPLETE)

    def abrir_configurar(self):
        if not os.path.exists(ARQUIVO_CONFIG):
            QMessageBox.warning(

                self,

                "Arquivo não encontrado",

                f"configurar.json não encontrado em:\n{ARQUIVO_CONFIG}",

            )

            return

        self.tabs.add_new_tab(ARQUIVO_CONFIG)
