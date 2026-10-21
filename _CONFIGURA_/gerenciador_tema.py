# 📁 _CONFIGURA_/gerenciador_tema.py
import json
import os
from PySide6.QtCore import QFileSystemWatcher, QTimer
from PySide6.QtGui import QColor, QPalette
from _CONFIGURA_ import (
    ARQUIVO_TEMA, COR_FALLBACK, _ler_json,
    FONTE_UI, FONTE_UI_FALLBACK, TAMANHO_FONTE_UI,
    FONTE_TERMINAL, FONTE_TERMINAL_FALLBACK,
    FONTE_EDITOR, FONTE_EDITOR_FALLBACK,
    FONTE_OUTLINE, FONTE_OUTLINE_FALLBACK,
    FONTE_ARQUIVOS, FONTE_ARQUIVOS_FALLBACK,
    FONTE_IA, FONTE_IA_FALLBACK,
    FONTE_GIT, FONTE_GIT_FALLBACK,
    TAMANHO_FONTE_EDITOR, TAMANHO_FONTE_TERMINAL,
    TAMANHO_FONTE_OUTLINE, TAMANHO_FONTE_ARQUIVOS,
    TAMANHO_FONTE_IA, TAMANHO_FONTE_GIT, FUNDO, FUNDO_PAINEL,
    BORDA_PAINEL, BORDA_GERAL, BORDA_CONTORNO_UI
)
from _LOG_.log import log
from _CONFIGURA_ import PASTA_APPDATA as _APPDATA_BASE  # IMP-04
_PASTA_TEMAS = os.path.join(_APPDATA_BASE, 'temas')    # IMP-04 — temas em AppData

class GerenciadorTema:
    def __init__(self):
        self._dados: dict = {}
        self._janela = None
        self._watcher = QFileSystemWatcher()
        self._watcher.fileChanged.connect(self._ao_arquivo_alterado)
        self._timer_reload = QTimer()
        self._timer_reload.setSingleShot(True)
        self._timer_reload.setInterval(400)  # aguarda 400ms apos ultima mudanca
        self._timer_reload.timeout.connect(self._aplicar_reload)
        self._caminho_pendente: str = ""
        self._erro_json:        str = ""   # mensagem do último erro de JSON

    def iniciar_hot_reload(self, janela) -> None:
        self._janela = janela
        # O arquivo ativo ja foi adicionado ao watcher por carregar().
        # Nao monitoramos thema.json diretamente -- ele e backup de fabrica,
        # nao o tema ativo.

    def _ao_arquivo_alterado(self, caminho: str) -> None:
        if caminho not in self._watcher.files():
            self._watcher.addPath(caminho)
        self._caminho_pendente = caminho
        self._timer_reload.start()  # debounce 400ms -- ignora saves parciais

    # ⚠️  função grande (80 linhas) | except genérico vazio
    def _aplicar_reload(self) -> None:
        """Lê o JSON e aplica o tema. Roda na UI thread (obrigatório para Qt)."""
        caminho = self._caminho_pendente
        if not self.carregar(caminho):

            return

        if self._janela is None:

            return

        tema = self._dados

        # ── 0. Overlay anti-clique — bloqueia interação enquanto o tema aplica ──
        from _UTILITARIOS_.loading_overlay import LoadingOverlay
        from PySide6.QtWidgets import QApplication as _QApp
        _overlay = LoadingOverlay(self._janela, mensagem="Aplicando tema...")
        _overlay.show()
        _QApp.processEvents()   # garante 1 frame antes do trabalho pesado

        # ── 1. Aplica QSS na janela (cores, fontes globais) ────────────────────
        self.aplicar_na_janela(self._janela)

        # ── 2 + 3. Atualiza painéis e bordas — DIFERIDO (R6-02) ────
        # aplicar_na_janela() acima já aplicou as cores globais de forma
        # síncrona (obrigatório para o repaint imediato). Os painéis
        # individuais — especialmente painel_git com ~52 widgets internos —
        # são diferidos para o próximo tick do event loop via singleShot(0).
        # Isso elimina o freeze de 40-55s sem mudança visual perceptível:
        # o QSS global já pintou tudo certo; atualizar_tema() apenas refina
        # widgets customizados que não herdam o QSS cascateado da janela.
        _janela  = self._janela
        _tema    = tema
        _ov_ref  = _overlay   # captura na closure para fechar após paineis

        def _atualizar_paineis():
            for attr in ("painel_arquivos", "painel_ia", "painel_git",
                         "painel_abas_inferior", "_barra_central"):
                # _barra_central: BarraCentral tem atualizar_tema() mas não
                # recebia hot-reload antes de ser adicionada aqui
                w = getattr(_janela, attr, None)
                if w and hasattr(w, "atualizar_tema"):
                    try:
                        w.atualizar_tema(_tema)
                    except Exception:
                        try:
                            w.atualizar_tema()
                        except Exception:
                            pass

            terminal_tabs = getattr(_janela, "terminal_tabs", None)
            if terminal_tabs:
                if hasattr(terminal_tabs, "atualizar_tema"):
                    terminal_tabs.atualizar_tema(_tema)
                for terminal in terminal_tabs.terminais.values():
                    if hasattr(terminal, "atualizar_tema"):
                        terminal.atualizar_tema(_tema)

            # IMP-08/09/10: barra direita e barra de título
            barra_dir = getattr(_janela, "_barra_lateral_direita", None)
            if barra_dir and hasattr(barra_dir, "atualizar_tema"):
                barra_dir.atualizar_tema()

            barra = getattr(_janela, "_barra_aba_topo", None)
            if barra and hasattr(barra, "atualizar_tema"):
                barra.atualizar_tema()

            # ── 3. Borda externa dos painéis (também diferida) ────
            from _CONFIGURA_.gerenciador_configurar import config_global
            config_global().aplicar_bordas_paineis(_janela)

            # ── fecha overlay ao término de todo o trabalho diferido ──────────
            try:
                _ov_ref.fechar()
            except Exception:
                pass

        QTimer.singleShot(0, _atualizar_paineis)
        # ── 3. Borda externa dos painéis ────────────────────────────────────────────────────
        from _CONFIGURA_.gerenciador_configurar import config_global
        config_global().aplicar_bordas_paineis(self._janela)

        # ── 4. Rehighlight do editor ativo diferido (evita freeze na UI thread)
        #       O QSS já foi aplicado — o highlight pode esperar um frame.
        tabs = getattr(self._janela, "tabs", None)
        if tabs:
            editor_ativo = tabs.get_current_editor()
            for editor in tabs.editores.values():
                if hasattr(editor, "atualizar_tema"):
                    if editor is editor_ativo:
                        # Difere para depois do repaint do QSS — sem freeze visível.
                        # Guard: editor pode ter sido fechado entre o agendamento e a
                        # execução; shiboken6.isValid() evita RuntimeError C++ deleted.
                        try:
                            from shiboken6 import isValid as _cpp_ok
                        except ImportError:
                            _cpp_ok = lambda _: True
                        QTimer.singleShot(0, lambda e=editor, t=tema: _cpp_ok(e) and e.atualizar_tema(t))
                    else:
                        editor._tema_pendente = tema  # lazy -- aplica ao ativar a aba
            for editor in tabs.editores.values():
                outline = getattr(editor, "_outline", None)
                if outline and hasattr(outline, "atualizar_tema"):
                    outline.atualizar_tema(tema)

        self._janela.statusBar().showMessage("🎨  Tema recarregado!", 3000)
        log.ok("gerenciador_tema.py", "hot_reload", f"tema reaplicado: {caminho}")

    # Temas dinamicos (JSON da pasta temas/)

    # ⚠️  except genérico vazio
    def listar_temas_json(self) -> list:
        """Varre _RAIZ_IDE/temas/ e retorna [(nome_sem_ext, caminho_abs)].
        Cria a pasta se nao existir. Retorna lista vazia se nao houver arquivos.
        """
        if not os.path.isdir(_PASTA_TEMAS):
            try:
                os.makedirs(_PASTA_TEMAS, exist_ok=True)
            except Exception:
                pass
        if not os.path.isdir(_PASTA_TEMAS):

            return []

        resultado = []
        for nome in sorted(os.listdir(_PASTA_TEMAS)):
            if nome.lower().endswith('.json'):
                resultado.append((nome[:-5], os.path.join(_PASTA_TEMAS, nome)))

        return resultado

    def aplicar_tema_json(self, caminho: str) -> bool:
        """Carrega o JSON e o aplica em toda a IDE via hot-reload.
        Retorna True em sucesso, False se o arquivo nao puder ser lido.
        """
        if not self.carregar(caminho):

            return False

        self._caminho_pendente = caminho
        # IMP-06: defer -- deixa o clique do botao 'Salvar' soltar visualmente
        # antes do setStyleSheet (sincrono, custoso) rodar em _aplicar_reload().
        QTimer.singleShot(0, self._aplicar_reload)

        return True

    # ⚠️  função grande (60 linhas)
    def carregar(self, caminho: str = None) -> bool:
        """
        Carrega o tema com cadeia de fallback — NUNCA trava a IDE.

        Cadeia:
            1. Parse normal + auto-repair via _ler_json()
            2. Backup (.bak) do último load bem-sucedido
            3. Dados vazios — todos os cor() devolvem seus fallbacks hardcoded

        A cada load bem-sucedido salva thema.json.bak automaticamente.
        self._erro_json guarda a mensagem do erro para exibir no Outdoor.
        """
        caminho = caminho or ARQUIVO_TEMA
        caminho_bak = caminho + ".bak"

        # ── Tentativa 1: parse normal + auto-repair ───────────────────────────
        try:
            self._dados   = _ler_json(caminho)
            self._erro_json = ""
            log.ok("gerenciador_tema.py", "carregar", caminho)
            if caminho not in self._watcher.files():
                self._watcher.addPath(caminho)
            self._salvar_backup(caminho, caminho_bak)

            return True

        except json.JSONDecodeError as e:
            self._erro_json = str(e)
            log.aviso("gerenciador_tema.py", "carregar",
                      f"JSON inválido (tentando backup): {e}")
        except Exception as e:
            self._erro_json = str(e)
            log.erro("gerenciador_tema.py", "carregar",
                     f"falha ao ler: {caminho}", str(e))

        # ── Tentativa 2: backup do último estado válido ───────────────────────
        if os.path.isfile(caminho_bak):
            try:
                self._dados = _ler_json(caminho_bak)
                log.aviso("gerenciador_tema.py", "carregar",
                          f"usando backup: {caminho_bak}")
                if caminho not in self._watcher.files():
                    self._watcher.addPath(caminho)

                return True   # dados do backup — IDE funciona normalmente

            except Exception as e2:
                log.erro("gerenciador_tema.py", "carregar",
                         "backup também inválido", str(e2))

        # ── Tentativa 3: fallback total — dicionário vazio ────────────────────
        # cor() já tem fallback hardcoded para cada chave; a IDE abre normalmente
        # com as cores do __init__.py mesmo sem nenhum JSON.
        self._dados = {}
        log.aviso("gerenciador_tema.py", "carregar",
                  "usando fallbacks do __init__.py — modo degradado")
        if caminho not in self._watcher.files():
            self._watcher.addPath(caminho)

        return False   # False = avisa ao chamador, mas não levanta exceção

    def _salvar_backup(self, origem: str, destino: str) -> None:
        """Copia o arquivo JSON para .bak após cada load bem-sucedido.

        A cópia é feita em thread daemon para não bloquear a UI thread antes
        do setStyleSheet (que já é pesado por si só).
        """
        import threading, shutil as _shutil
        def _copiar():
            try:
                _shutil.copy2(origem, destino)
            except Exception as e:
                log.aviso("gerenciador_tema.py", "_salvar_backup", str(e))
        threading.Thread(target=_copiar, daemon=True).start()

    def recarregar(self) -> bool:

        return self.carregar()

    def dados(self) -> dict:

        return self._dados

    def cor(self, caminho: str, fallback: str = COR_FALLBACK) -> str:
        partes = caminho.split(".")
        no = self._dados
        try:
            for p in partes:
                no = no[p]
            valor = str(no)
            if len(valor) == 9 and valor.startswith("#"):
                valor = valor[:7]

            return valor

        except (KeyError, TypeError):

            return fallback

    def qcolor(self, caminho: str, fallback: str = COR_FALLBACK) -> QColor:

        return QColor(self.cor(caminho, fallback))

    # ⚠️  função grande (239 linhas) | except genérico vazio
    def aplicar_na_janela(self, janela) -> None:
        from _CONFIGURA_.gerenciador_configurar import config_global
        cfg = config_global()

        # -- UI geral: le do JSON secao "ui", fallback = __init__
        _fonte_ui = cfg.obter("ui", "fonte",        FONTE_UI)
        _pt_ui    = cfg.obter("ui", "tamanho_fonte", TAMANHO_FONTE_UI)

        # -- Demais paineis
        _fonte_editor   = cfg.obter("editor",         "fonte",        FONTE_EDITOR)
        _pt_editor      = int(cfg.obter("editor",         "tamanho_fonte", TAMANHO_FONTE_EDITOR))
        _fonte_terminal = cfg.obter("terminal",       "fonte",        FONTE_TERMINAL)
        _pt_terminal    = int(cfg.obter("terminal",       "tamanho_fonte", TAMANHO_FONTE_TERMINAL))
        _fonte_outline  = cfg.obter("outline",        "fonte",        FONTE_OUTLINE)
        _pt_outline     = int(cfg.obter("outline",        "tamanho_fonte", TAMANHO_FONTE_OUTLINE))
        _fonte_arquivos = cfg.obter("painel_arquivos","fonte",        FONTE_ARQUIVOS)
        _pt_arquivos    = int(cfg.obter("painel_arquivos","tamanho_fonte", TAMANHO_FONTE_ARQUIVOS))
        _fonte_ia       = cfg.obter("painel_ia",      "fonte",        FONTE_IA)
        _pt_ia          = int(cfg.obter("painel_ia",      "tamanho_fonte", TAMANHO_FONTE_IA))
        _fonte_git      = cfg.obter("git",            "fonte",        FONTE_GIT)
        _pt_git         = int(cfg.obter("git",            "tamanho_fonte", TAMANHO_FONTE_GIT))

        c = self.cor

        qss = f"""
        QWidget {{
            background-color: {c('interface.fundo')};
            color: {c('interface.texto')};
            font-family: '{_fonte_ui}', '{FONTE_UI_FALLBACK}', sans-serif;
            font-size: {_pt_ui};
        }}
        QWidget#BarraTitulo {{
            background-color: {c('interface.fundo_painel', FUNDO_PAINEL)};
            border-bottom: 1px solid {c('interface.fundo_aba_ativa', BORDA_GERAL)};
        }}

        QMenuBar {{
            background-color: {c('interface.fundo_toolbar')};
            color: {c('interface.texto')};
            font-family: '{_fonte_ui}', '{FONTE_UI_FALLBACK}', sans-serif;
            font-size: {_pt_ui};
            border-bottom: 1px solid {c('interface.borda')};
        }}

        QMenuBar::item {{ background: transparent; padding: 4px 10px; }}

        QMenuBar::item:selected {{
            background-color: {c('interface.fundo_item_hover')};
            border-radius: 3px;
        }}

        QMenu {{
            background-color: {c('menu_contexto.fundo',            '#070706')};
            color: {c('menu_contexto.texto',                       '#e8f5e8')};
            font-family: '{_fonte_ui}', '{FONTE_UI_FALLBACK}', sans-serif;
            font-size: {_pt_ui};
            border: 1px solid {c('menu_contexto.borda',            '#252530')};
        }}
        QMenu::item {{ padding: 5px 24px 5px 12px; }}
        QMenu::item:selected {{
            background-color: {c('menu_contexto.item_hover',       '#1a2e1a')};
            color: {c('menu_contexto.texto_hover',                 '#ffffff')};
        }}
        QMenu::item:disabled {{ color: {c('menu_contexto.texto_desativado', '#3a4d3a')}; }}
        QMenu::separator {{ height: 1px; background: {c('menu_contexto.separador', '#222222')}; margin: 3px 0; }}

        QToolBar {{
            background-color: {c('interface.fundo_toolbar')};
            border-bottom: 1px solid {c('interface.borda')};
            padding: 2px 4px; spacing: 4px;
        }}

        QToolBar QToolButton {{
            background: transparent;
            color: {c('interface.texto')};
            font-family: '{_fonte_ui}', '{FONTE_UI_FALLBACK}', sans-serif;
            font-size: {_pt_ui};
            padding: 4px 8px; border-radius: 4px;
        }}

        QToolBar QToolButton:hover {{ background-color: {c('interface.fundo_item_hover')}; }}
        QTabWidget::pane {{
                    border: 1px solid {c('interface.borda')};
                    background-color: {c('interface.fundo_corpo', FUNDO)};
                }}
        QTabBar::tab {{
            background-color: transparent;
            color: {c('interface.texto_fraco')};
            font-family: '{_fonte_ui}', '{FONTE_UI_FALLBACK}', sans-serif;
            font-size: {_pt_ui};
            padding: 6px 14px;
            border: 1px solid {c('interface.borda')};
            border-bottom: none; border-radius: 3px 3px 0 0; margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background-color: {c('interface.fundo_aba_ativa')};
            color: {c('interface.texto')};
            border-bottom: 2px solid {c('interface.fundo_aba_ativa')};
        }}

        QTabBar::tab:hover:!selected {{ background-color: {c('interface.fundo_item_hover')}; }}
        QPushButton {{
            background-color: {c('interface.botao_padrao_fundo', c('interface.fundo_item_hover'))};
            color: {c('interface.botao_padrao_texto', c('interface.texto'))};
            font-family: '{_fonte_ui}', '{FONTE_UI_FALLBACK}', sans-serif;
            font-size: {_pt_ui};
            border: 1px solid {c('interface.borda')};
            padding: 5px 12px; border-radius: 4px;
        }}

        QPushButton:hover {{
            background-color: {c('interface.fundo_item_selecionado')};
        }}
        QPushButton#btn_run {{
            background-color: {c('interface.botao_run_fundo')};
            color: {c('interface.botao_run_texto')};
            font-family: '{_fonte_ui}', '{FONTE_UI_FALLBACK}', sans-serif;
            font-weight: bold; font-size: 14px;
            padding: 8px 20px; border-radius: 5px; border: none;
        }}
        QPushButton#btn_run:hover {{ background-color: {c('interface.botao_run_hover')}; }}
        QLabel {{
            font-family: '{_fonte_ui}', '{FONTE_UI_FALLBACK}', sans-serif;
            font-size: {_pt_ui};
            color: {c('interface.texto')}; background: transparent;
        }}
        QLineEdit {{
            background-color: {c('interface.inputs', c('interface.fundo_item_hover'))};
            color: {c('interface.texto')};
            font-family: '{_fonte_ui}', '{FONTE_UI_FALLBACK}', sans-serif;
            font-size: {_pt_ui};
            border: 1px solid {c('interface.borda')};
            border-radius: 3px; padding: 4px;
        }}
        QLineEdit:focus {{ border-color: {c('interface.borda')}; }}
        QTreeWidget, QTreeView {{
            background-color: {c('interface.fundo')};
            color: {c('interface.texto')};
            font-family: '{_fonte_arquivos}', '{FONTE_ARQUIVOS_FALLBACK}', sans-serif;
            font-size: {_pt_arquivos}pt;
            border: none;
        }}
        QTreeWidget::item, QTreeView::item {{ padding: 2px 4px; }}
        QTreeWidget::item:hover, QTreeView::item:hover {{ background-color: {c('interface.fundo_item_hover')}; }}
        QTreeWidget::item:selected, QTreeView::item:selected {{
            background-color: {c('interface.fundo_item_selecionado')}; color: #ffffff;
        }}
        QPlainTextEdit {{
            background-color: {c('editor.fundo')};
            color: {c('editor.texto')};
            font-family: '{_fonte_editor}', '{FONTE_EDITOR_FALLBACK}', monospace;
            font-size: {_pt_editor}pt;
            border: none;
            selection-background-color: {c('editor.selecao')};
        }}
        QTextEdit {{
            background-color: {c('interface.inputs', c('terminal.fundo'))};
            color: {c('interface.texto')};
            font-family: '{_fonte_ui}', '{FONTE_UI_FALLBACK}', sans-serif;
            font-size: {_pt_ui};
            border: none;
        }}
        QScrollBar:vertical {{
            background: {c('interface.scrollbar_trilha', 'transparent')};
            width: 10px; border: none;
        }}
        QScrollBar::handle:vertical {{
            background: {c('interface.scrollbar_thumb')};
            border-radius: 5px; min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {c('interface.scrollbar_thumb_hover')}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{
            background: {c('interface.scrollbar_trilha', 'transparent')};
            height: 10px; border: none;
        }}
        QScrollBar::handle:horizontal {{
            background: {c('interface.scrollbar_thumb')};
            border-radius: 5px; min-width: 20px;
        }}
        QScrollBar::handle:horizontal:hover {{ background: {c('interface.scrollbar_thumb_hover')}; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        QStatusBar {{
            background-color: {c('interface.fundo_toolbar')};
            color: {c('interface.texto_fraco')};
            font-family: '{_fonte_ui}', '{FONTE_UI_FALLBACK}', sans-serif;
            font-size: {_pt_ui};
            border-top: 2px solid {c('interface.borda_rodape', '#c0392b')};
        }}
        QDialog, QMessageBox, QInputDialog {{
            background-color: {c('interface.fundo')};
            color: {c('interface.texto')};
            font-family: '{_fonte_ui}', '{FONTE_UI_FALLBACK}', sans-serif;
            font-size: {_pt_ui};
        }}
        QSplitter::handle {{ background-color: {c('interface.borda_painel', BORDA_PAINEL)}; }}
        QSplitter::handle:hover {{ background-color: {c('interface.borda_foco')}; }}
        QComboBox {{
            background-color: {c('interface.fundo_item_hover')};
            color: {c('interface.texto')};
            font-family: '{_fonte_ui}', '{FONTE_UI_FALLBACK}', sans-serif;
            font-size: {_pt_ui};
            border: 1px solid {c('interface.borda')};
            border-radius: 3px; padding: 3px 8px;
        }}
        QComboBox::drop-down {{ border: none; }}
        QComboBox QAbstractItemView {{
            background-color: {c('interface.fundo')};
            color: {c('interface.texto')};
            selection-background-color: {c('interface.fundo_item_hover')};
            border: 1px solid {c('interface.borda')};
        }}
        QToolTip {{
            background-color: {c('menu_contexto.fundo', '#070706')};
            color: {c('menu_contexto.texto', '#e8f5e8')};
            font-family: '{_fonte_ui}', '{FONTE_UI_FALLBACK}', sans-serif;
            font-size: 11px;
            border: 1px solid {c('menu_contexto.borda', '#252530')};
            border-radius: 4px;
            padding: 4px 8px;
        }}
        """

        # IMP-07: removido QApplication.setStyleSheet global (causava re-cômputo
        # de estilo em todos os QDialog do processo e era a principal causa do
        # travamento de 30 s no hot-reload). A janela principal já engloba todos
        # os painéis; QDialogs herdam o tema pelo palette, não pelo QSS global.
        janela.setStyleSheet(qss)

        # Aplica QToolTip também no QApplication (tooltips são top-level widgets)
        try:
            from _UTILITARIOS_.hen_context_menu import aplicar_estilo_tooltip
            aplicar_estilo_tooltip()
        except Exception:
            pass

_instancia: GerenciadorTema | None = None

def tema_global() -> GerenciadorTema:
    global _instancia
    if _instancia is None:
        _instancia = GerenciadorTema()
        _instancia.carregar()

    return _instancia
