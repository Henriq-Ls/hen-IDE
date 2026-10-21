# _APP_/main_window/mixin_projeto.py


"""MixinProjeto — abrir/criar projeto, venv e salvar/abrir arquivo.

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



from .workers import _AnalisadorProjeto, _garantir_hein_no_gitignore, _threads_vivas_analisador


class MixinProjeto:
    """abrir/criar projeto, venv e salvar/abrir arquivo.

    Mixin combinado em MainWindow — depende dos atributos criados por
    MainWindowBase.__init__/_montar_ui (self.tabs, self.painel_arquivos, etc.)."""

    def _abrir_pasta_appdata(self):
        from _CONFIGURA_ import PASTA_APPDATA
        from PySide6.QtWidgets import QFileDialog
        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Pasta de dados hein — abrir arquivo",
            PASTA_APPDATA,
        )
        if caminho:
            self.abrir_arquivo(caminho)

    # ══════════════════════════════════════════════════════════════════

    # Navegação pelo outline (busca global)

    # ══════════════════════════════════════════════════════════════════

    # ⚠️  except genérico vazio

    def abrir_projeto(self, caminho: str = None):
        # ── Guard: impede duplo clique / re-entrada durante carregamento ─────────
        if getattr(self, "_abrindo_projeto", False):
            from _LOG_.log import log
            log.aviso("mixin_projeto.py", "abrir_projeto",
                      "chamada ignorada — já existe um projeto sendo aberto")
            return

        if not caminho:
            _s = QSettings("hein", "hein_IDE")

            _pasta_ini = _s.value("ultima_pasta_abrir_projeto", PASTA_PROJETOS)

            caminho = QFileDialog.getExistingDirectory(

                self, "Abrir Projeto", _pasta_ini

            )

            if caminho:
                _s.setValue("ultima_pasta_abrir_projeto", caminho)

        if not caminho:
            return

        if not os.path.isdir(caminho):
            QMessageBox.warning(

                self, "Projeto não encontrado", f"A pasta não existe mais:\n{caminho}"

            )

            return

        # ── Ativa loading ─────────────────────────────────────────────────────────
        from _LOG_.log import log
        from _UTILITARIOS_.freeze_guard import FreezeGuard
        self._abrindo_projeto = True
        nome_proj = os.path.basename(caminho)
        self.statusBar().showMessage(f"Abrindo {nome_proj}…")
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        QApplication.setOverrideCursor(Qt.WaitCursor)

        # fechar_apos_ms=2000: overlay fica aberto 2s após _abrir_projeto_interno
        # retornar — cobre os callbacks deferred (git, motor_busca, ia) que
        # rodam logo depois via QTimer.singleShot.
        with FreezeGuard(self, f"Abrindo {nome_proj}…", fechar_apos_ms=2000):
            try:
                self._abrir_projeto_interno(caminho)
            finally:
                self._abrindo_projeto = False
                QApplication.restoreOverrideCursor()

    def _abrir_projeto_interno(self, caminho: str):
        """Corpo real de abrir_projeto() — separado para que o guard/loading
        fique limpo e o finally sempre restaure o cursor."""
        from _LOG_.log import log
        log.info("mixin_projeto.py", "_abrir_projeto_interno",
                 f"abrindo projeto: {caminho}")

        self._barra_aba_topo.registrar_projeto_aberto(caminho)

        _projeto_anterior = self.current_project_path  # IMP-02: captura antes de atualizar
        self.current_project_path = caminho

        # terminal: aparece somente ao abrir projeto
        if not self.terminal_tabs.isVisible():
            self.terminal_tabs.show()
        if self.terminal_tabs.count() == 0:
            self.terminal_tabs.add_new_terminal("powershell", project_path=caminho)

        _garantir_hein_no_gitignore(caminho)

        self.tabs.project_path = caminho

        # Invalida cache de I/O do quick-fix ao trocar de projeto
        try:
            from _EDITOR_.Autocomplete.quick_fix import modulo_em_venv
            modulo_em_venv.cache_clear()
        except Exception:
            pass

        # Helper local: dá ciclos ao event loop para o spinner animar.
        # IMPORTANTE: registrar os QTimer.singleShot APENAS no fim da função,
        # depois de todos os _pev() — se registrados antes, o processEvents()
        # os dispara imediatamente, tornando-os síncronos e bloqueando a UI.
        _pev = QApplication.processEvents

        # Primeiro frame: árvore de arquivos — o usuário precisa ver imediatamente
        self.painel_arquivos.set_projeto(caminho)
        _pev()

        if hasattr(self, "_tarefas"):
            self._tarefas.carregar_projeto(caminho)
        _pev()

        if self._indexador:
            self._indexador.parar()
            # Espera o thread terminar antes de soltar a referência;
            # sem isso o GC destrói o QThread ainda em execução.
            if hasattr(self._indexador, 'wait') and self._indexador.isRunning():
                self._indexador.quit()
                self._indexador.wait(2000)
        _pev()

        self._indexador = Indexador(caminho)
        self._indexador.iniciar(callback_concluido=self._ao_indexar_concluido)

        for editor in self.tabs.editores.values():
            editor.set_projeto(caminho)
        _pev()

        for i in range(self.terminal_tabs.count()):
            t = self.terminal_tabs.terminais.get(i)
            if t and hasattr(t, "set_project_path"):
                t.set_project_path(caminho)

        # Atualiza aba Pacotes se estiver aberta (não está no dict terminais)
        self.terminal_tabs.set_project_path_pacotes(caminho)

        # Atualiza python picker para mostrar a venv do novo projeto
        if hasattr(self, "_python_picker"):
            self._python_picker.set_projeto(caminho)
        _pev()

        terminal = self.terminal_tabs.terminal_ativo()

        # IMP-01/02: salva sessão do projeto ANTERIOR antes de limpar as abas
        if hasattr(self, '_gerenciador_abas') and _projeto_anterior:
            try:
                self._gerenciador_abas.salvar_sessao(_projeto_anterior)
            except Exception:
                pass
        _pev()

        self.tabs.clear()
        _pev()

        # Bug #8: fecha abas de explorer do projeto ANTERIOR no painel de
        # terminais (TarefasExplorer, ExecutavelExplorer, JsonExplorer).
        # Essas abas são vinculadas ao projeto e ficavam "presas" ao trocar.
        # Abas de terminal real (PowerShell/Bash) são mantidas e têm o
        # diretório de trabalho atualizado via set_project_path() acima.
        if _projeto_anterior:
            try:
                from _TERMINAIS_.Tarefas.tarefas_explorer import TarefasExplorer as _TE
                from _TERMINAIS_.executavel_explorer import ExecutavelExplorer as _EE
                from _TERMINAIS_.json_explorer import JsonExplorer as _JE
                _proj_norm = os.path.normcase(os.path.abspath(_projeto_anterior))
                _indices_fechar = []
                for _i in range(self.terminal_tabs.count()):
                    _w = self.terminal_tabs.widget(_i)
                    if isinstance(_w, (_TE, _EE, _JE)):
                        # Fecha apenas abas do projeto anterior (não abas globais)
                        _cam = os.path.normcase(os.path.abspath(
                            getattr(_w, "_caminho", "") or ""
                        ))
                        if _cam.startswith(_proj_norm + os.sep) or _cam == _proj_norm:
                            _indices_fechar.append(_i)
                for _i in sorted(_indices_fechar, reverse=True):
                    self.terminal_tabs.removeTab(_i)
            except Exception:
                pass
        _pev()

        # IMP-08: se este projeto tem sessão salva (abas/cursor de quando foi
        # fechado), restaura exatamente do jeito que o usuário deixou — em vez
        # de abrir sempre main.py/primeiro .py. Isso só acontece quando o
        # usuário escolhe abrir o projeto (Recentes/Abrir Projeto), nunca
        # automaticamente ao iniciar a IDE.
        _sessao_restaurada = False
        if hasattr(self, '_gerenciador_abas'):
            try:
                ok, _ = self._gerenciador_abas.restaurar_sessao(projeto_esperado=caminho)  # IMP-02
                _sessao_restaurada = bool(ok)
            except Exception:
                pass
        _pev()

        # ── Callbacks deferred — registrados AQUI, depois de todos os _pev() ──
        # Registrar antes causaria execução síncrona via processEvents() acima,
        # bloqueando a UI por minutos (motor_busca varre o projeto inteiro).
        QTimer.singleShot(0, lambda: self.painel_git.set_projeto(caminho))
        QTimer.singleShot(0, lambda: self._motor_busca.set_projeto(caminho))

        def _set_ia():
            pass
        QTimer.singleShot(10, _set_ia)

        # IMP-01: sem sessão prévia → painel de editor fica vazio.
        # O picker só faz sentido na inicialização sem projeto, não aqui.

        if terminal:
            terminal.append_output(f"=== Projeto ===\n{caminho}\n\n")

        self.statusBar().showMessage(f"Projeto aberto: {os.path.basename(caminho)}")

        # Para o analisador anterior sem destruir QThread em execução.
        # quit() não interrompe os.walk() (sem event loop) — wait() pode timeout.
        # _threads_vivas_analisador garante que o objeto não seja GC'd enquanto
        # a OS thread ainda roda, independente de self._analisador_projeto ser
        # substituído (BUG-202807-13).
        _analisador_ant = getattr(self, '_analisador_projeto', None)
        if _analisador_ant is not None and _analisador_ant.isRunning():
            _analisador_ant.quit()
            _analisador_ant.wait(1000)

        self._analisador_projeto = _AnalisadorProjeto(caminho)
        self._analisador_projeto.concluido.connect(self._ao_analise_projeto_concluida)
        _threads_vivas_analisador.add(self._analisador_projeto)
        self._analisador_projeto.finished.connect(
            lambda t=self._analisador_projeto: _threads_vivas_analisador.discard(t)
        )
        self._analisador_projeto.start()

    # ── extensões reconhecidas como imagem ────────────────────────────

    _EXTENSOES_IMAGEM = {

        ".png", ".jpg", ".jpeg", ".bmp", ".gif",

        ".ico", ".webp", ".tiff", ".tif",

    }

    # ── extensão do editor de anotações hein ──────────────────────────
    _EXTENSOES_HEIN = {".hein"}

    # ── extensões que NÃO abrem no editor (binárias/executáveis) ─────
    _EXTENSOES_BLOQUEADAS = {
        # Executáveis
        ".exe", ".com", ".msi", ".dmg", ".deb", ".rpm",
        ".apk", ".ipa", ".appimage", ".installable", ".exec",
        # Bibliotecas compiladas
        ".dll", ".so", ".dylib", ".pyd",
        # Objetos / arquivos de ligação
        ".o", ".a", ".lib", ".obj",
        # Bytecode Python
        ".pyc", ".pyo",
        # Bytecode JVM
        ".class", ".jar",
        # Imagens de disco / firmware
        ".iso", ".img", ".vmdk", ".vhd", ".qcow2", ".bin",
        # Bancos de dados binários (SQLite e afins)
        ".db", ".db-shm", ".db-wal", ".db-journal",
        ".sqlite", ".sqlite3", ".sqlite-shm", ".sqlite-wal",
    }

    def abrir_arquivo(self, caminho: str = None):
        if not caminho:
            caminho, _ = QFileDialog.getOpenFileName(
                self, "Abrir", "",
                "Todos os arquivos (*);;Python (*.py);;JSON (*.json)",
                "Todos os arquivos (*)"
            )

        if caminho:
            ext = os.path.splitext(caminho)[1].lower()

            if os.path.basename(os.path.normpath(caminho)).lower() in {
                "hein.log", "hein_exception.log", "hein_faulthandler.log",
            }:
                self.statusBar().showMessage("Logs internos nao podem ser abertos no editor", 3000)
                return

            if ext in self._EXTENSOES_BLOQUEADAS:
                self._avisar_extensao_bloqueada(caminho)
            elif ext in self._EXTENSOES_IMAGEM:
                self._abrir_visualizador_imagem(caminho)
            elif ext in self._EXTENSOES_HEIN:
                self._abrir_editor_hein(caminho)
            else:
                self.tabs.add_new_tab(caminho)

    def _abrir_arquivo_selecionado(self, caminho: str):
        if not caminho or not os.path.isfile(caminho):
            return

        if os.path.basename(os.path.normpath(caminho)).lower() in {
            "hein.log", "hein_exception.log", "hein_faulthandler.log",
        }:
            self.statusBar().showMessage("Logs internos nao podem ser abertos no editor", 3000)
            return

        # ── imagem → abre visualizador, não editor de texto ──────────

        ext = os.path.splitext(caminho)[1].lower()

        if ext in self._EXTENSOES_BLOQUEADAS:
            self._avisar_extensao_bloqueada(caminho)
            return

        if ext in self._EXTENSOES_IMAGEM:
            self._abrir_visualizador_imagem(caminho)
            return

        if ext in self._EXTENSOES_HEIN:
            self._abrir_editor_hein(caminho)
            return

        _norm = lambda p: os.path.normcase(os.path.abspath(p)) if p else ""

        for indice, editor in self.tabs.editores.items():
            if _norm(getattr(editor, "file_path", None)) == _norm(caminho):
                # Duplo-clique: converte preview para permanente antes de ativar
                if self.tabs._preview_editor is editor:
                    self.tabs._converter_preview_para_permanente(editor)
                self.tabs.setCurrentIndex(indice)

                return

        self.tabs.add_new_tab(caminho)

    def _avisar_extensao_bloqueada(self, caminho: str):
        """Mostra popup para extensões binárias/executáveis e abre a pasta no Explorer."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from _UTILITARIOS_.hein_pou_pap import HeinPopup
        nome  = os.path.basename(caminho)
        ext   = os.path.splitext(caminho)[1].lower()
        pasta = os.path.dirname(caminho)
        dlg = HeinPopup(
            f"Não é possível abrir  ·  {ext}",
            f"<b>{nome}</b> é um arquivo binário/executável e não pode ser aberto no editor de texto.",
            informativo="Clique em <b>Abrir pasta</b> para ver o arquivo no explorador do sistema.",
            botoes=[("Abrir pasta", True), ("Fechar", False)],
            tipo="aviso",
            parent=self,
        )
        dlg.exec()
        if dlg.resultado:
            QDesktopServices.openUrl(QUrl.fromLocalFile(pasta))

    def _abrir_visualizador_imagem(self, caminho: str):
        """Abre a imagem em aba do editor e os controles no terminal automaticamente."""

        from _TERMINAIS_.visualizador_imagem import VisualizadorImagem
        # reusar aba já aberta para o mesmo arquivo

        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)

            if isinstance(w, VisualizadorImagem) and w.caminho == caminho:
                self.tabs.setCurrentIndex(i)

                self.terminal_tabs.abrir_aba_imagem_controles(caminho)

                return

        viewer = VisualizadorImagem(caminho)

        nome = os.path.basename(caminho)

        self.tabs.add_new_tab_widget(viewer, nome, "mdi.image")

        # controles abrem automaticamente no terminal — igual ao JSON

        self.terminal_tabs.abrir_aba_imagem_controles(caminho)

    def _abrir_editor_hein(self, caminho: str):
        """Abre arquivo .hein no EditorHein dedicado (nunca no Editor.py)."""
        from _EDITOR_.Editor_Hein import EditorHein
        from _CONFIGURA_.gerenciador_tema import tema_global

        _norm = lambda p: os.path.normcase(os.path.abspath(p)) if p else ""

        # reusar aba já aberta para o mesmo arquivo
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, EditorHein) and _norm(getattr(w, 'file_path', None)) == _norm(caminho):
                self.tabs.setCurrentIndex(i)
                return

        # Fecha preview CodeEditor residual com este caminho (ocorre quando
        # clique simples abriu open_preview antes desta correcao estar ativa).
        _prev = self.tabs._preview_editor
        if (_prev is not None
                and _norm(getattr(_prev, 'file_path', None)) == _norm(caminho)):
            for _i in range(self.tabs.count()):
                if self.tabs.widget(_i) is _prev:
                    try:
                        _prev.encerrar_threads_bg()
                    except Exception:
                        pass
                    self.tabs.removeTab(_i)
                    self.tabs._reindexar()
                    self.tabs._preview_editor = None
                    break

        editor = EditorHein()
        if self.current_project_path:
            editor.set_projeto(self.current_project_path)
        editor.navegar_arquivo.connect(self.tabs.navegar_para_arquivo)
        editor.load_file(caminho)
        nome = os.path.basename(caminho)
        self.tabs.add_new_tab_widget(editor, nome, "mdi.note-text-outline",
                                      registrar_como_editor=True)

        # Ctrl+S → statusbar: "Salvo: nome.hein"
        editor.arquivo_salvo.connect(
            lambda cam: self.statusBar().showMessage(
                f"Salvo: {os.path.basename(cam)}", 3000))

        # exportação → abre o .md gerado como nova aba
        editor.arquivo_exportado.connect(self._abrir_arquivo_selecionado)

    def _ao_trocar_aba_imagem(self):
        """Quando o editor troca para uma aba de imagem, atualiza o painel de controles."""

        from _TERMINAIS_.visualizador_imagem import VisualizadorImagem
        widget = self.tabs.currentWidget()

        if isinstance(widget, VisualizadorImagem):
            self.terminal_tabs.abrir_aba_imagem_controles(widget.caminho)

    def abrir_janela_inicial(self):
        """Abre a tela de boas-vindas para ações de projeto."""
        self._abrir_picker_dialog()
    # ⚠️  except genérico vazio

    def salvar_arquivo(self):
        editor = self.tabs.get_current_editor()

        if not editor:
            return

        editor.save_file()

        caminho = getattr(editor, "file_path", None)

        if caminho and self._indexador:
            self._indexador.reindexar_arquivo(caminho)

            for e in self.tabs.editores.values():
                e._atualizar_code_lens()

        # ── Bidirecional: JSON salvo → recarregar TarefasExplorer vinculado ──

        if caminho and caminho.lower().endswith(".json"):
            try:
                from _TERMINAIS_.Tarefas.tarefas_explorer import TarefasExplorer as _TE
                import os as _os2
                for _i in range(self.terminal_tabs.count()):
                    _w = self.terminal_tabs.widget(_i)

                    if (isinstance(_w, _TE)

                            and _os2.path.normpath(getattr(_w, "_caminho", ""))

                            == _os2.path.normpath(caminho)):
                        _w._carregar()

                        break

            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════

    # Execução

    # ══════════════════════════════════════════════════════════════════

    def _pegar_python_projeto(self) -> str:
        """Retorna o python do .venv do projeto, ou '' se não existir."""

        import platform
        proj = self.current_project_path

        if not proj:
            return ""

        nome = "python.exe" if platform.system() == "Windows" else "python"

        pasta = "Scripts" if platform.system() == "Windows" else "bin"

        caminho = os.path.join(proj, ".venv", pasta, nome)

        return caminho if os.path.isfile(caminho) else ""

    def _abrir_pasta_projeto_no_explorer(self):
        """Abre a pasta do projeto atual no explorador de arquivos do SO."""

        caminho = self.current_project_path

        if not caminho or not os.path.isdir(caminho):
            self.statusBar().showMessage("Nenhum projeto aberto.", 3000)

            return

        if sys.platform == "win32":
            os.startfile(caminho)

        elif sys.platform == "darwin":
            subprocess.Popen(["open", caminho])

        else:
            subprocess.Popen(["xdg-open", caminho])

    def _ao_analise_projeto_concluida(self, dados: dict):
        pastas = dados.get("pastas", 0)

        arquivos = dados.get("arquivos", 0)

        extensoes = dados.get("extensao", {})

        ext_str = "  •  ".join(f"{k}({v})" for k, v in sorted(extensoes.items()))

        self._lbl_projeto_info.setText(

            f"Pastas: {pastas}  |  Arq: {arquivos}  |  {ext_str}"

        )
    def _restaurar_ou_picker(self) -> None:  # IMP-08
        """
        Fallback defensivo para uma MainWindow criada sem projeto.

        O caminho normal sem projeto é tratado por main.py, que abre o
        JanelaPicker leve antes de construir a MainWindow. Se algum chamador
        antigo construir a janela diretamente, usa o mesmo picker não-modal.
        """
        self._abrir_picker_dialog()

