# 📁 _CONFIGURA_/gerenciador_configurar.py
#
# ██████████████████████████████████████████████████████████████████████
# ATENCAO — LEIA ANTES DE MEXER NESSE ARQUIVO
# ██████████████████████████████████████████████████████████████████████
#
# Este arquivo e o GERENCIADOR DE CONFIGURACOES da hen IDE.
# Ele le o arquivo configurar.json e aplica fonte, tamanho, wrap,
# espacamento e outros ajustes em TODOS os widgets da IDE.
#
# ── FONTES ────────────────────────────────────────────────────────────
#
#   TODOS os nomes de fonte e tamanhos padrao vem do __init__.py.
#   NAO coloque strings de fonte hardcoded aqui.
#   Para mudar qualquer fonte padrao, edite apenas o __init__.py.
#
# ── REGRA DE OURO — NAO QUEBRE ISSO ──────────────────────────────────
#
#   A fonte e aplicada via stylesheet do proprio widget:
#       widget.setStyleSheet(ss + f" font-family: '{nome}'; font-size: {tamanho}pt;")
#
#   MOTIVO: o Qt tem uma hierarquia de prioridade onde o stylesheet do
#   pai (QMainWindow, containers) sobrescreve qualquer setFont() chamado
#   no filho. A unica forma de garantir que a fonte do JSON seja aplicada
#   e forcar font-family e font-size no stylesheet do PROPRIO widget.
#
#   NAO faca isso:
#       widget.setFont(QFont(nome, tamanho))   <- pai sobrescreve, nao funciona sozinho
#
#   NAO faca isso:
#       widget.setStyleSheet("font-size: 11px")  <- px vs pt causa bug de tamanho=0
#                                                   a cada hot-reload
#
#   SEMPRE use pt (pontos), nunca px, no stylesheet de fonte.
#
# ── HOT-RELOAD ────────────────────────────────────────────────────────
#
#   O arquivo configurar.json e monitorado em tempo real por
#   QFileSystemWatcher + QTimer (1s de intervalo).
#   Quando o usuario salva o JSON, a IDE detecta a mudanca e reaplicar
#   tudo automaticamente sem precisar reiniciar.
#
# ── CURSOR ────────────────────────────────────────────────────────────
#
#   cursor_forma    : "barra" | "bloco" | "sublinhado" | "linha"
#   cursor_largura  : inteiro (pixels) — so aplicado em "barra" e "linha"
#   cursor_piscar   : true | false
#   cursor_piscar_estilo : "suave" | "normal" | "fase" | "fixo"
#
#   _aplicar_cursor_widget(widget, forma, largura) — aplica em um widget
#   _aplicar_cursor_global()                       — aplica piscar via QApplication
#
#   Nota: "sublinhado" nao e suportado nativamente pelo Qt em QPlainTextEdit.
#   A largura e definida como 1px como aproximacao. Para cursor de bloco,
#   a largura e calculada automaticamente pela metrica da fonte.
#
# ██████████████████████████████████████████████████████████████████████

import re
from PySide6.QtCore import QFileSystemWatcher, QTimer
from PySide6.QtGui import QFont, QFontMetrics, QTextBlockFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import (
    ARQUIVO_CONFIG, _ler_json,
    FONTE_UI,        TAMANHO_FONTE_UI,
    FONTE_EDITOR,    FONTE_EDITOR_PADRAO, FONTE_EDITOR_MIN, FONTE_EDITOR_MAX,
    FONTE_TERMINAL,  TAMANHO_FONTE_TERMINAL,
    FONTE_OUTLINE,   TAMANHO_FONTE_OUTLINE,
    FONTE_ARQUIVOS,  TAMANHO_FONTE_ARQUIVOS,
    FONTE_IA,        TAMANHO_FONTE_IA,
    FONTE_GIT,       TAMANHO_FONTE_GIT,
)
from _LOG_.log import log
_ARQ = "gerenciador_configurar.py"

_instancia = None
def config_global() -> "GerenciadorConfigurar":
    global _instancia
    if _instancia is None:
        _instancia = GerenciadorConfigurar()
        _instancia.carregar()

    return _instancia

class GerenciadorConfigurar:
    def __init__(self):
        self._dados: dict = {}
        self._janela = None
        self._ultimo_mtime: float = 0.0

        self._watcher = QFileSystemWatcher()
        self._watcher.fileChanged.connect(self._ao_arquivo_alterado)

        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._verificar_mudanca)

        self._timer_debounce = QTimer()
        self._timer_debounce.setSingleShot(True)
        self._timer_debounce.setInterval(400)
        self._timer_debounce.timeout.connect(self._recarregar_e_aplicar)
        self._erro_json: str = ""  # mensagem do último erro de JSON

    # ─────────────────────────────────────────────────────────────────
    # Carregamento
    # ─────────────────────────────────────────────────────────────────

    # ⚠️  função grande (55 linhas) | except genérico vazio
    def carregar(self, caminho: str = None) -> bool:
        """
        Carrega configurar.json com cadeia de fallback — nunca levanta exceção.

        Cadeia:
            1. Parse + auto-repair via _ler_json()
            2. Backup (.bak) do último load bem-sucedido
            3. Dados vazios — cada obter() devolve seu padrao hardcoded
        """
        import os
        caminho = caminho or ARQUIVO_CONFIG
        caminho_bak = caminho + ".bak"

        # ── Tentativa 1: parse normal + auto-repair ───────────────────────────
        try:
            self._dados = _ler_json(caminho)
            self._erro_json = ""
            self._ultimo_mtime = os.path.getmtime(caminho)
            if caminho not in self._watcher.files():
                self._watcher.addPath(caminho)
            log.ok(_ARQ, "carregar", "configurar.json carregado", caminho)
            self._salvar_backup(caminho, caminho_bak)

            return True

        except Exception as e:
            self._erro_json = str(e)
            log.erro(_ARQ, "carregar", "erro ao carregar (tentando backup)", str(e))
            # Atualiza mtime mesmo em falha — sem isso _verificar_mudanca() fica em loop
            try:
                self._ultimo_mtime = os.path.getmtime(caminho)
            except Exception:
                pass

        # ── Tentativa 2: backup do último estado válido ───────────────────────
        if os.path.isfile(caminho_bak):
            try:
                self._dados = _ler_json(caminho_bak)
                self._ultimo_mtime = os.path.getmtime(caminho_bak)
                if caminho not in self._watcher.files():
                    self._watcher.addPath(caminho)
                log.aviso(_ARQ, "carregar", f"usando backup: {caminho_bak}")

                return True

            except Exception as e2:
                log.erro(_ARQ, "carregar", "backup também inválido", str(e2))

        # ── Tentativa 3: dados vazios — obter() usa fallback hardcoded ────────
        self._dados = {}
        log.aviso(_ARQ, "carregar", "usando fallbacks hardcoded — modo degradado")
        if caminho not in self._watcher.files():
            self._watcher.addPath(caminho)

        return False

    def _salvar_backup(self, origem: str, destino: str) -> None:
        try:
            import shutil as _sh
            _sh.copy2(origem, destino)
        except Exception as e:
            log.aviso(_ARQ, "_salvar_backup", str(e))

    def dados(self) -> dict:

        return self._dados

    def obter(self, secao: str, chave: str, padrao=None):
        try:

            return self._dados[secao][chave]

        except (KeyError, TypeError):

            return padrao

    # ─────────────────────────────────────────────────────────────────
    # Hot-reload
    # ─────────────────────────────────────────────────────────────────

    def iniciar_hot_reload(self, janela):
        self._janela = janela
        if ARQUIVO_CONFIG not in self._watcher.files():
            self._watcher.addPath(ARQUIVO_CONFIG)
        self._timer.start()
        log.info(_ARQ, "iniciar_hot_reload", "hot-reload ativo")

    def _ao_arquivo_alterado(self, caminho: str):
        if caminho not in self._watcher.files():
            self._watcher.addPath(caminho)
        self._timer_debounce.start()

    # ⚠️  except genérico vazio
    def _verificar_mudanca(self):
        import os
        try:
            mtime_atual = os.path.getmtime(ARQUIVO_CONFIG)
            if mtime_atual != self._ultimo_mtime:
                log.info(_ARQ, "_verificar_mudanca", "mudanca detectada — recarregando")
                self._timer_debounce.start()
        except Exception:
            pass

    def _recarregar_e_aplicar(self):
        self.carregar()
        try:
            self._aplicar_em_tudo()
        except Exception as e:
            log.erro(_ARQ, "_recarregar_e_aplicar", "erro ao aplicar configurações", str(e))
        if not self._janela:

            return

        sb = self._janela.statusBar()
        if self._erro_json:
            sb.setStyleSheet(
                "QStatusBar { color: #e06c75; font-weight: bold; background: #1a0505; }"
            )
            sb.showMessage(
                f"⚠ configurar.json inválido — usando backup.  {self._erro_json}", 10000
            )
            QTimer.singleShot(10100, lambda: sb.setStyleSheet("") if sb else None)
        else:
            sb.setStyleSheet("")
            sb.showMessage("✓ Configurações recarregadas!", 3000)

    # ─────────────────────────────────────────────────────────────────
    # Aplicacao em tudo
    # ─────────────────────────────────────────────────────────────────

    def _aplicar_em_tudo(self):
        if not self._janela:
            log.aviso(_ARQ, "_aplicar_em_tudo", "janela nao definida — abortando")

            return

        log.info(_ARQ, "_aplicar_em_tudo", "iniciando aplicacao em todos os componentes")
        self.aplicar_na_ui(self._janela)
        self.aplicar_nos_editores(self._janela)
        self.aplicar_nos_terminais(self._janela)
        self.aplicar_no_outline(self._janela)
        self.aplicar_no_painel_arquivos(self._janela)
        self.aplicar_no_painel_ia(self._janela)
        self.aplicar_no_git(self._janela)
        self._aplicar_cursor_global()
        self.aplicar_bordas_paineis(self._janela)
        self.aplicar_margem_paineis(self._janela)
        log.ok(_ARQ, "_aplicar_em_tudo", "aplicacao concluida em todos os componentes")

    # ─────────────────────────────────────────────────────────────────
    # Helper fonte — NUCLEO DO SISTEMA, NAO ALTERE SEM ENTENDER
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _fonte(nome: str, tamanho: int, mono: bool = False) -> QFont:
        f = QFont(nome, tamanho)
        if mono:
            f.setFixedPitch(True)

        return f

    @staticmethod
    def _aplicar_fonte_widget(widget, nome: str, tamanho_pt: int):
        """
        Aplica fonte garantindo que fique DENTRO do seletor correto no stylesheet.
        Sempre use pt, nunca px.
        """
        from PySide6.QtGui import QFont
        import re
        fonte = QFont(nome, tamanho_pt)
        widget.setFont(fonte)

        ss = widget.styleSheet() or ""

        ss = re.sub(r"\bfont-family\s*:[^;]+;", "", ss)
        ss = re.sub(r"\bfont-size\s*:[^;]+;", "", ss)

        bloco = re.search(r'(\w[\w:>\s#.]*)\s*\{([^}]*)\}', ss)
        if bloco:
            novo_ss = re.sub(
                r'(\w[\w:>\s#.]*)\s*\{([^}]*)\}',
                lambda m: f"{m.group(1)} {{ {m.group(2).strip()} "
                          f"font-family: '{nome}'; font-size: {tamanho_pt}pt; }}",
                ss
            )
            widget.setStyleSheet(novo_ss)
        else:
            widget.setStyleSheet(
                ss + f" font-family: '{nome}'; font-size: {tamanho_pt}pt;"
            )

    # ─────────────────────────────────────────────────────────────────
    # Helpers de cursor
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    # 💡 estilo_opc = Literal["normal"] ← defina os valores válidos
    # 💡 cor_opc = Literal["#aeafad"] ← defina os valores válidos
    def _aplicar_cursor_widget(widget, forma: str, largura: int, piscar: bool = True, estilo: str = "normal", cor: str = "#aeafad"):
        """
        Aplica cursor em qualquer widget de texto.
        Se o widget tem configurar_cursor() (CodeEditor), delega para ele.
        Se nao tem mas e QPlainTextEdit, usa CursorTerminal.
        Fallback: setCursorWidth nativo.
        """
        # CodeEditor — usa o gerenciador proprio
        if hasattr(widget, "configurar_cursor"):
            widget.configurar_cursor(forma, max(1, int(largura)), piscar, estilo, cor)

            return

        # Terminal sem CursorTerminal ainda — anexa agora
        from PySide6.QtWidgets import QPlainTextEdit as _QPT, QTextEdit as _QTE
        if isinstance(widget, (_QPT, _QTE)):
            mgr = getattr(widget, "_cursor_terminal", None)
            if mgr is None:
                try:
                    from _TERMINAIS_.cursor_terminal import CursorTerminal
                    mgr = CursorTerminal(widget)
                    widget._cursor_terminal = mgr
                except Exception:
                    mgr = None
            if mgr is not None:
                mgr.configurar(forma, max(1, int(largura)), piscar, estilo, cor)

                return

        # Fallback puro (widgets sem viewport, ex: QLineEdit)
        if not hasattr(widget, "setCursorWidth"):

            return

        if forma == "bloco":
            fm = QFontMetrics(widget.font())
            widget.setCursorWidth(max(2, fm.horizontalAdvance("M")))
        elif forma == "sublinhado":
            widget.setCursorWidth(1)
        else:
            widget.setCursorWidth(max(1, int(largura)))

    def _aplicar_cursor_global(self):
        """
        Aplica velocidade/estilo de piscar via QApplication.setCursorFlashTime().

        Valores de cursor_piscar_estilo:
          "normal"  -> 1000ms (padrao do sistema)
          "suave"   -> 1400ms (mais lento, percebido como suave)
          "fase"    ->  700ms (mais rapido, ciclo curto)
          "fixo"    ->    0   (sem piscar, mesmo que cursor_piscar=false)

        cursor_piscar=false desliga o piscar independente do estilo.
        """
        from PySide6.QtWidgets import QApplication
        piscar = bool(self.obter("editor", "cursor_piscar",        True))
        estilo =  str(self.obter("editor", "cursor_piscar_estilo", "normal"))

        if not piscar or estilo == "fixo":
            QApplication.setCursorFlashTime(0)
            log.info(_ARQ, "_aplicar_cursor_global", "cursor fixo (sem piscar)")
        elif estilo == "suave":
            QApplication.setCursorFlashTime(1400)
            log.info(_ARQ, "_aplicar_cursor_global", "cursor piscar suave (1400ms)")
        elif estilo == "fase":
            QApplication.setCursorFlashTime(700)
            log.info(_ARQ, "_aplicar_cursor_global", "cursor piscar fase (700ms)")
        else:
            QApplication.setCursorFlashTime(1000)
            log.info(_ARQ, "_aplicar_cursor_global", "cursor piscar normal (1000ms)")

    # ─────────────────────────────────────────────────────────────────
    # Interface geral (ui)
    # ─────────────────────────────────────────────────────────────────

    def aplicar_na_ui(self, janela):
        import re as _re
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import (
            QApplication, QMenuBar, QStatusBar, QTabBar, QToolBar,
            QLabel, QPushButton,
        )

        fonte_nome  = self.obter("ui", "fonte",         FONTE_UI)
        tamanho_raw = self.obter("ui", "tamanho_fonte", TAMANHO_FONTE_UI)
        if isinstance(tamanho_raw, str):
            tamanho = int(_re.sub(r'[^0-9]', '', tamanho_raw) or 12)
        else:
            tamanho = int(tamanho_raw)

        log.info(_ARQ, "aplicar_na_ui", f"fonte={fonte_nome} tamanho={tamanho}")

        app = QApplication.instance()
        if app:
            app.setFont(QFont(fonte_nome, tamanho))

        total = 0
        for cls in (QMenuBar, QStatusBar, QTabBar, QToolBar):
            for w in janela.findChildren(cls):
                self._aplicar_fonte_widget(w, fonte_nome, tamanho)
                total += 1

        for attr in ("barra_aba_topo", "barra_buscas"):
            painel = getattr(janela, attr, None)
            if painel:
                for cls in (QLabel, QPushButton):
                    for w in painel.findChildren(cls):
                        self._aplicar_fonte_widget(w, fonte_nome, tamanho)
                        total += 1

        log.ok(_ARQ, "aplicar_na_ui", f"{total} widget(s) da interface geral configurados")

    # ─────────────────────────────────────────────────────────────────
    # Editor
    # ─────────────────────────────────────────────────────────────────

    def aplicar_nos_editores(self, janela):
        tabs = getattr(janela, "tabs", None)
        if not tabs:
            log.aviso(_ARQ, "aplicar_nos_editores", "tabs nao encontrado na janela")

            return

        total = len(tabs.editores)
        log.info(_ARQ, "aplicar_nos_editores", f"{total} editor(es) encontrado(s)")
        for idx, editor in tabs.editores.items():
            log.info(_ARQ, "aplicar_nos_editores", f"aplicando no editor indice {idx}")
            self.aplicar_no_editor(editor)

    # ⚠️  função grande (74 linhas)
    def aplicar_no_editor(self, editor):
        if editor is None:
            log.aviso(_ARQ, "aplicar_no_editor", "editor e None — ignorando")

            return

        fonte_nome  = self.obter("editor", "fonte",          FONTE_EDITOR)
        tamanho     = int(self.obter("editor", "tamanho_fonte",  FONTE_EDITOR_PADRAO))
        tamanho_min = int(self.obter("editor", "tamanho_minimo", FONTE_EDITOR_MIN))
        tamanho_max = int(self.obter("editor", "tamanho_maximo", FONTE_EDITOR_MAX))
        wrap        = bool(self.obter("editor", "wrap_linha",     False))
        destacar    = bool(self.obter("editor", "destacar_linha", True))
        numeros     = bool(self.obter("editor", "numeros_linha",  True))
        tab_tam_config = int(self.obter("editor", "tab_tamanho", 2))
        # Preferência específica do Editor_Hein, quando já foi carregada.
        tab_tam = int(getattr(editor, "_tab_tamanho", None) or tab_tam_config)
        tab_tam = max(1, min(16, tab_tam))
        espacamento = int(self.obter("editor", "espacamento_linha", 100))

        # Cursor
        cursor_forma   =  str(self.obter("editor", "cursor_forma",   "barra"))
        cursor_largura = int(self.obter("editor", "cursor_largura",  2))

        log.info(_ARQ, "aplicar_no_editor",
                 f"fonte={fonte_nome} tamanho={tamanho} wrap={wrap} "
                 f"numeros={numeros} tab={tab_tam} espacamento={espacamento} "
                 f"cursor={cursor_forma}/{cursor_largura}px")

        self._aplicar_fonte_widget(editor, fonte_nome, tamanho)
        editor._tamanho_fonte = tamanho
        editor._FONTE_MIN = tamanho_min
        editor._FONTE_MAX = tamanho_max

        editor.setLineWrapMode(
            QPlainTextEdit.WidgetWidth if wrap else QPlainTextEdit.NoWrap
        )

        fonte = QFont(fonte_nome, tamanho)
        fm = QFontMetrics(fonte)
        editor._tab_tamanho = tab_tam
        editor.setTabStopDistance(float(fm.horizontalAdvance(" ") * tab_tam))

        fmt = QTextBlockFormat()
        fmt.setLineHeight(float(espacamento), 4)  # tipo 4 = LineDistanceHeight (px extras entre linhas)
        _pos = editor.textCursor().position()
        cur = QTextCursor(editor.document())
        cur.select(QTextCursor.Document)
        cur.mergeBlockFormat(fmt)
        cur.clearSelection()
        _cur_restaurado = QTextCursor(editor.document())
        _max = max(0, editor.document().characterCount() - 1)
        _cur_restaurado.setPosition(min(_pos, _max))
        editor.setTextCursor(_cur_restaurado)
        log.info(_ARQ, "aplicar_no_editor", f"espacamento aplicado: {espacamento}%")

        area = getattr(editor, "area_numeros", None)
        if area:
            area.setVisible(numeros)
            area._recarregar_gutter()
            area.update()
        else:
            log.aviso(_ARQ, "aplicar_no_editor", "area_numeros nao encontrado no editor")

        if destacar and hasattr(editor, "_destacar_linha_atual"):
            editor._destacar_linha_atual()

        # fechar_pares — lido do config e exposto como atributo para editor_acoes.py
        editor._fechar_pares = bool(self.obter("editor", "fechar_pares", True))

        if hasattr(editor, "metricas"):
            editor.metricas.atualizar_margem()

        # Aplica cursor — feito depois da fonte para o bloco calcular largura correta
        cursor_piscar = bool(self.obter("editor", "cursor_piscar",        True))
        cursor_estilo =  str(self.obter("editor", "cursor_piscar_estilo", "normal"))
        cursor_cor    =  str(tema_global().cor("interface.cursor_cor", "#aeafad"))
        log.info(_ARQ, "aplicar_no_editor", f"cursor_cor={cursor_cor}")
        self._aplicar_cursor_widget(editor, cursor_forma, cursor_largura, cursor_piscar, cursor_estilo, cursor_cor)

        # O Editor_Hein possui preferências próprias no menu flutuante.
        # Elas devem prevalecer sobre a configuração global depois que a
        # configuração comum da IDE terminar de ser aplicada.
        if hasattr(editor, "aplicar_preferencias_locais"):
            editor.aplicar_preferencias_locais()

        log.ok(_ARQ, "aplicar_no_editor", "editor configurado com sucesso")

    # ─────────────────────────────────────────────────────────────────
    # Terminais
    # ─────────────────────────────────────────────────────────────────

    def aplicar_nos_terminais(self, janela):
        terminal_tabs = getattr(janela, "terminal_tabs", None)
        if not terminal_tabs:
            log.aviso(_ARQ, "aplicar_nos_terminais", "terminal_tabs nao encontrado")

            return

        fonte_nome = self.obter("terminal", "fonte",          FONTE_TERMINAL)
        tamanho    = int(self.obter("terminal", "tamanho_fonte", TAMANHO_FONTE_TERMINAL))

        cursor_forma   =  str(self.obter("editor", "cursor_forma",   "barra"))
        cursor_largura = int(self.obter("editor", "cursor_largura",  2))

        total = len(terminal_tabs.terminais)
        log.info(_ARQ, "aplicar_nos_terminais",
                 f"{total} terminal(is) — fonte={fonte_nome} tamanho={tamanho} "
                 f"cursor={cursor_forma}/{cursor_largura}px")

        for idx, terminal in terminal_tabs.terminais.items():
            console = getattr(terminal, "console", None)
            cursor_piscar = bool(self.obter("editor", "cursor_piscar",        True))
            cursor_estilo =  str(self.obter("editor", "cursor_piscar_estilo", "normal"))
            cursor_cor    =  str(tema_global().cor("interface.cursor_cor", "#aeafad"))

            if console:
                self._aplicar_fonte_widget(console, fonte_nome, tamanho)
                self._aplicar_cursor_widget(console, cursor_forma, cursor_largura, cursor_piscar, cursor_estilo, cursor_cor)
                log.ok(_ARQ, "aplicar_nos_terminais", f"terminal[{idx}] console aplicado")

            ui = getattr(terminal, "ui", None)
            if ui:
                self._aplicar_fonte_widget(ui, fonte_nome, tamanho)
                self._aplicar_cursor_widget(ui, cursor_forma, cursor_largura, cursor_piscar, cursor_estilo, cursor_cor)
                log.ok(_ARQ, "aplicar_nos_terminais", f"terminal[{idx}] ui aplicado")

            if not console and not ui:
                log.aviso(_ARQ, "aplicar_nos_terminais",
                          f"terminal[{idx}] sem console nem ui — tipo: {type(terminal).__name__}")

    # ─────────────────────────────────────────────────────────────────
    # Outline
    # ─────────────────────────────────────────────────────────────────

    def aplicar_no_outline(self, janela):
        tabs = getattr(janela, "tabs", None)
        if not tabs:

            return

        fonte_nome = self.obter("outline", "fonte",          FONTE_OUTLINE)
        tamanho    = int(self.obter("outline", "tamanho_fonte", TAMANHO_FONTE_OUTLINE))

        for editor in tabs.editores.values():
            outline = getattr(editor, "_outline", None)
            if outline and hasattr(outline, "_arvore"):
                self._aplicar_fonte_widget(outline._arvore, fonte_nome, tamanho)
                log.ok(_ARQ, "aplicar_no_outline", "outline do editor aplicado")

    def aplicar_no_painel_arquivos(self, janela):
        painel = getattr(janela, "painel_arquivos", None)
        if not painel:
            log.aviso(_ARQ, "aplicar_no_painel_arquivos", "painel_arquivos nao encontrado")

            return

        fonte_nome = self.obter("painel_arquivos", "fonte",          FONTE_ARQUIVOS)
        tamanho    = int(self.obter("painel_arquivos", "tamanho_fonte", TAMANHO_FONTE_ARQUIVOS))

        log.info(_ARQ, "aplicar_no_painel_arquivos", f"fonte={fonte_nome} tamanho={tamanho}")

        arvore = getattr(painel, "_tree", None) or getattr(painel, "_arvore", None)
        if arvore:
            self._aplicar_fonte_widget(arvore, fonte_nome, tamanho)
            log.ok(_ARQ, "aplicar_no_painel_arquivos", "arvore de arquivos fonte aplicada")
        else:
            log.aviso(_ARQ, "aplicar_no_painel_arquivos",
                    "nem _tree nem _arvore encontrados — atributos: "
                    + str([a for a in dir(painel) if not a.startswith("__")]))

    def aplicar_no_painel_ia(self, janela):
        painel = getattr(janela, "painel_ia", None)
        if not painel:
            log.aviso(_ARQ, "aplicar_no_painel_ia", "painel_ia nao encontrado")

            return

        fonte_nome = self.obter("painel_ia", "fonte",          FONTE_IA)
        tamanho    = int(self.obter("painel_ia", "tamanho_fonte", TAMANHO_FONTE_IA))

        log.info(_ARQ, "aplicar_no_painel_ia", f"fonte={fonte_nome} tamanho={tamanho}")

        from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QTextEdit, QPlainTextEdit
        total = 0
        for cls in (QLabel, QLineEdit, QPushButton, QTextEdit, QPlainTextEdit):
            for w in painel.findChildren(cls):
                self._aplicar_fonte_widget(w, fonte_nome, tamanho)
                total += 1
        log.ok(_ARQ, "aplicar_no_painel_ia", f"{total} widget(s) do painel IA configurados")

    def aplicar_no_git(self, janela):
        painel_git = getattr(janela, "painel_git", None)
        if not painel_git:
            log.aviso(_ARQ, "aplicar_no_git", "painel_git nao encontrado")

            return

        fonte_nome = self.obter("git", "fonte",          FONTE_GIT)
        tamanho    = int(self.obter("git", "tamanho_fonte", TAMANHO_FONTE_GIT))

        log.info(_ARQ, "aplicar_no_git", f"fonte={fonte_nome} tamanho={tamanho}")

        from PySide6.QtWidgets import QTextEdit, QPlainTextEdit, QLabel, QLineEdit, QPushButton
        total = 0
        for cls in (QTextEdit, QPlainTextEdit, QLabel, QLineEdit, QPushButton):
            for widget in painel_git.findChildren(cls):
                self._aplicar_fonte_widget(widget, fonte_nome, tamanho)
                total += 1
        log.ok(_ARQ, "aplicar_no_git", f"{total} widget(s) do painel Git configurados")

    def aplicar_margem_paineis(self, janela) -> None:
        """Aplica margem_painel do configurar.json nos splitters e na janela principal."""
        if not janela:

            return

        margem = int(self.obter("ui", "margem_painel", 4))
        log.info(_ARQ, "aplicar_margem_paineis", f"margem={margem}px")

        for attr in ("_splitter_principal", "_splitter_col1", "_splitter_col2"):
            splitter = getattr(janela, attr, None)
            if splitter:
                splitter.setHandleWidth(max(2, margem))

        janela.update()
        log.ok(_ARQ, "aplicar_margem_paineis", f"margem {margem}px aplicada nos splitters")

    # ⚠️  função grande (55 linhas)
    def aplicar_bordas_paineis(self, janela) -> None:
        """Aplica BordaOverlay nos 4 paineis configurados."""
        if not janela:

            return

        t = tema_global()
        cor = t.cor("interface.borda_externa", "transparent")
        estilo  = self.obter("ui", "borda_estilo", "solid")
        larg    = int(self.obter("ui", "borda_larg", 2))
        raio    = int(self.obter("ui", "borda_raio", 10))

        # Atualiza margem do QMainWindow que expõe a borda de contorno.
        # A cor do paintEvent é interface.borda; sem alpha = sem margem.
        if janela:
            from PySide6.QtGui import QColor as _QColor
            _cor_borda = t.cor("interface.contorno_ui", "transparent")
            _margem = larg if _QColor(_cor_borda).alpha() > 0 else 0
            janela.setContentsMargins(_margem, _margem, _margem, _margem)
            janela.update()

        # ✅ NOVO: Atualiza a linha separadora da barra de título
        # (o atributo em MainWindow é "_barra_aba_topo", com underscore —
        # por isso o getattr nunca encontrava o widget e a borda da aba
        # ativa na barra de título nunca era atualizada com cor/largura reais)
        barra_aba_topo = getattr(janela, "_barra_aba_topo", None)
        if barra_aba_topo and hasattr(barra_aba_topo, "atualizar_linha_sep"):
            barra_aba_topo.atualizar_linha_sep(cor, larg, estilo)

        # —— card editor ——————————————————————————————
        #card_ed = getattr(janela, "_card_editor", None)
        #if card_ed and hasattr(card_ed, "atualizar_borda"):
            #card_ed.atualizar_borda(cor, larg, estilo, raio, sem_topo=True)

        # —— card IA ——————————————————————————————
        card_ia = getattr(janela, "_card_ia", None)
        if card_ia and hasattr(card_ia, "atualizar_borda"):
            ia_estilo = self.obter("ui", "borda_estilo", estilo)
            ia_larg   = int(self.obter("ui", "borda_larg", larg))
            ia_raio   = int(self.obter("ui", "borda_raio", raio))
            # card_ia.atualizar_borda(cor, ia_larg, ia_estilo, ia_raio) # COM BORDA DA PARTE SUPERIOR
            card_ia.atualizar_borda(cor, ia_larg, ia_estilo, ia_raio, sem_topo=True, sem_direita=True) # SEM TOPO, SEM DIREITA

        # —— terminal ——————————————————————————————
        terminal_tabs = getattr(janela, "terminal_tabs", None)
        if terminal_tabs and hasattr(terminal_tabs, "atualizar_borda"):
            terminal_tabs.atualizar_borda(cor, larg, estilo, raio)

        # —— git ——————————————————————————————
        painel_git = getattr(janela, "painel_git", None)
        if painel_git and hasattr(painel_git, "atualizar_borda"):
            painel_git.atualizar_borda(cor, larg, estilo, raio)

# —— curva ┐ coluna esquerda ——————————————————————————————
        coluna_esq = getattr(janela, "_coluna_esquerda", None)
        if coluna_esq and hasattr(coluna_esq, "atualizar_curva_esquerda"):
            coluna_esq.atualizar_curva_esquerda(cor, larg, estilo, raio)

        # IMP-10: borda vertical direita na BarraLateralDireita
        barra_dir = getattr(janela, "_barra_lateral_direita", None)
        if barra_dir and hasattr(barra_dir, "atualizar_borda_direita"):
            barra_dir.atualizar_borda_direita(cor, larg, estilo)

        log.ok(_ARQ, "aplicar_bordas_paineis", "bordas aplicadas nos paineis + barra de título + barra direita")
