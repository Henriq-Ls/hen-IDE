# 📁 _EDITOR_/Editor/__init__.py
"""
Editor completo — versão final hein.
Pacote Editor/ — CodeEditor e helpers extraídos em sub-arquivos.

Ações de teclado / texto  → _EDITOR_/Core/editor_acoes.py
Dobramento + projeto       → _EDITOR_/Core/editor_dobramento.py
"""
import os
import re as _re
import threading
import time
from PySide6.QtWidgets import (
    QPlainTextEdit, QFileDialog, QMessageBox, QTextEdit,
    QWidget, QHBoxLayout, QPushButton, QToolButton,QLabel
)
from PySide6.QtGui     import QFont, QColor, QTextCursor, QPainter
from PySide6.QtCore    import Signal, QRect, QTimer, QObject, QEvent, Qt, QThread
from ..Core.editor_acoes      import _EditorAcoesMixin, _fonte_padrao
from ..Core.editor_dobramento import _EditorDobramentoMixin
from ..Core.estado_editor     import EstadoEditor
from ..Ui.numeros_linha       import AreaNumerosLinha, ReguaErros
from ..Ui.metricas_editor     import MetricasEditor
from ..Outline                import PainelOutline
from ..Funcionalidades.auto_indentacao    import AutoIndentacao
from ..Funcionalidades.realce_sintaxe     import RealceSintaxePython
from ..Autocomplete.autocomplete          import GerenciadorAutocomplete
from ..Funcionalidades.ir_para_definicao  import IrParaDefinicao
from ..Funcionalidades.multiplos_cursores import GerenciadorMultiplosCursores
from ..Funcionalidades.find_references    import FindReferences
from ..Funcionalidades.barra_status       import BarraStatus
from ..Funcionalidades.busca_substituicao import PainelBuscaSubstituicao
from _CONFIGURA_ import FONTE_EDITOR, FONTE_EDITOR_PADRAO, FONTE_EDITOR_MIN, FONTE_EDITOR_MAX, OUTLINE_LARGURA_MIN, FONTE_UI
from _CONFIGURA_.gerenciador_tema import tema_global
from _LOG_.log import log
from _THREADS_.diagnostico_workers import (
    attach_editor, check_live_without_reference, edit_generation, event,
    new_task, reference,
)
_RE_DEF_CLASS_LENS = _re.compile(r"^\s*(def |async def |class )")
_HANDLE_OUTLINE_LARGURA = 4   # largura da alça de redimensionamento (px)

# _RunnableLint: QThread→QRunnable (Fase 1 de QThread→QRunnable).
from _EDITOR_.Mult_Linguas.Python.lint import _RunnableLint  # noqa: F401, E402

def _ler_arquivo(caminho: str) -> tuple[str, str]:
    for enc in ('utf-8', 'utf-8-sig', 'cp1252', 'latin-1'):
        try:
            with open(caminho, 'r', encoding=enc) as f:

                return f.read(), enc

        except (UnicodeDecodeError, LookupError):
            continue
    with open(caminho, 'rb') as f:

        return f.read().decode('latin-1', errors='replace'), 'latin-1'

# ── Sub-arquivos deste pacote ──────────────────────────────────────────────────
from ._code_lens           import _CodeLensOverlay, _extrair_nome_lens  # noqa: F401
from ._handle_outline      import _HandleOutline                         # noqa: F401
from ._barra_salto         import _BarraSalto                           # noqa: F401
from ._scroll_bar_fold     import _ScrollBarFold                         # noqa: F401
from ._cursor_personalizado import _GerenciadorCursorPersonalizado       # noqa: F401

# ══════════════════════════════════════════════════════════════════════
# CodeEditor
# ══════════════════════════════════════════════════════════════════════

class CodeEditor(_EditorAcoesMixin, _EditorDobramentoMixin, QPlainTextEdit):
    """Editor de código principal da IDE hein."""

    arquivo_salvo      = Signal(str)
    navegar_arquivo    = Signal(str, int)  # (caminho_abs, linha) — vindo do outline busca global
    erros_atualizados  = Signal(int)       # emitido após lint: total de erros+avisos

    def __init__(self, parent=None, tema: dict = None):
        super().__init__(parent)

        self.file_path:    str | None = None
        self.original_text: str       = ""
        self._tamanho_fonte: int      = _fonte_padrao()
        self._encoding: str           = 'utf-8'
        self._salvando_internamente: bool = False
        self._caminho_projeto: str | None = None

        self.estado       = EstadoEditor()
        self.metricas     = MetricasEditor(self)
        self.auto_indent  = AutoIndentacao(self)
        self.area_numeros = AreaNumerosLinha(self)
        self._regua_erros = ReguaErros(self)
        self._regua_erros.show()

        tema_inicial = tema if tema else tema_global().dados()

        self._realce        = RealceSintaxePython(self.document(), tema_inicial)
        self._autocomplete  = GerenciadorAutocomplete(self)
        from ..Autocomplete.quick_fix import PopupQuickFix
        self._popup_quick_fix = PopupQuickFix(self)
        self._ir_definicao  = IrParaDefinicao(self)
        self._find_refs     = FindReferences(self)
        self._multi_cursor  = GerenciadorMultiplosCursores(self)
        self._fold_regions: list = []  # list[FoldRegion] — gerenciado por _EditorDobramentoMixin
        self._lens_overlay     = _CodeLensOverlay(self)
        self._cursor_mgr       = _GerenciadorCursorPersonalizado(self)

        self._erros_lint:      dict = {}
        self._erros_imports:   dict = {}
        self._mensagens_erros: dict = {}

        from ..Funcionalidades.validador_imports import ValidadorImports
        self._validador_imports = ValidadorImports(self)
        self._validador_imports.erros_detectados.connect(self._ao_erros_imports)

        self._configurar()
        self._configurar_tema(tema_inicial)

        # ============== barra de informação
        self._barra_status = BarraStatus(self)
        self._painel_busca = PainelBuscaSubstituicao(self)

        self._corretor = None  # CorretorOrtografico - instanciado em _trocar_realce_por_extensao
        attach_editor(self)



    # ══════════════════════════════════════════════════════════════════
    # Configuração
    # ══════════════════════════════════════════════════════════════════

    # ⚠️  função grande (68 linhas)
    def _configurar(self): # Adiciona no final do método _configurar():
        self.setFocusPolicy(Qt.ClickFocus)  # ← só recebe foco quando CLICADO, não automaticamente
        self._aplicar_fonte()
        try:
            from _CONFIGURA_.gerenciador_configurar import config_global
            if config_global().obter("editor", "wrap_linha", False):
                self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
            else:
                self.setLineWrapMode(QPlainTextEdit.NoWrap)
        except Exception:
            self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.viewport().setMouseTracking(True)
        self.blockCountChanged.connect(self.metricas.atualizar_margem)
        self.updateRequest.connect(self._atualizar_area_numeros)

        self.cursorPositionChanged.connect(self._destacar_linha_atual)
        self.cursorPositionChanged.connect(self.area_numeros.update)
        self.metricas.atualizar_margem()

        self._largura_outline = OUTLINE_LARGURA_MIN
        self._outline = PainelOutline(parent=self)
        self._outline.setMinimumWidth(0)  # permite colapso total
        self._outline.navegar_para_linha.connect(self.ir_para_linha)
        self._outline.navegar_solicitado.connect(self.navegar_arquivo)  # repassa para MainWindow via TabWidget
        self._outline.conectar_editor(self)
        self._handle_outline = _HandleOutline(self)
        self._handle_outline.show()
        self._atualizar_geometria_outline()
        self._outline.show()
        self.area_numeros.code_lens_clicado.connect(self._find_refs.buscar_com_arquivo)
        self._destacar_linha_atual()
        self._diff_gutter_pending_path = None
        self._timer_diff_gutter = QTimer(self)
        self._timer_diff_gutter.setSingleShot(True)
        self._timer_diff_gutter.setInterval(350)
        self._timer_diff_gutter.timeout.connect(self._executar_diff_gutter_pendente)
        self.arquivo_salvo.connect(self._agendar_diff_gutter)

        # Sticky scroll
        from ..Ui.sticky_scroll import StickyScroll
        self._sticky = StickyScroll(self)

        # 8.2 — Barra de salto rápido flutuante
        self._barra_salto = _BarraSalto(self)
        self._barra_salto.posicionar()

        # 8.3 — Overlay de marcas de fold no scrollbar
        self._scrollbar_fold = _ScrollBarFold(self)
        # Debounce 80 ms — updateRequest dispara a cada linha redesenhada
        # (scroll, cursor, Ctrl+A…). Sem debounce, atualizar_e_posicionar()
        # roda dezenas de vezes por segundo e trava o cursor.
        self._timer_scrollbar_fold = QTimer()
        self._timer_scrollbar_fold.setSingleShot(True)
        self._timer_scrollbar_fold.setInterval(80)
        self._timer_scrollbar_fold.timeout.connect(self._scrollbar_fold.atualizar_e_posicionar)
        self.updateRequest.connect(lambda *_: self._timer_scrollbar_fold.start())

        # Debounce 80 ms para checar tooltip/quick-fix de erro.
        # Sem debounce, mouseMoveEvent chamava _checar_tooltip_erro() a cada
        # pixel — que por sua vez chama modulo_em_venv() (I/O no disco) e
        # emitia Signals Qt que re-renderizavam o painel de Saída dezenas de
        # vezes por segundo, afogando o loop de eventos até o app travar.
        self._pos_mouse_tooltip = None
        self._timer_checar_tooltip = QTimer()
        self._timer_checar_tooltip.setSingleShot(True)
        self._timer_checar_tooltip.setInterval(80)
        self._timer_checar_tooltip.timeout.connect(
            lambda: self._pos_mouse_tooltip is not None
                    and self._checar_tooltip_erro(self._pos_mouse_tooltip)
        )

        # Regua de diagnosticos — atualiza posicao do cursor em tempo real
        self.cursorPositionChanged.connect(self._regua_erros.update)

        # Tags de Comentário hein — minimiza o código (#al:/#al;/#:) quando a
        # linha não está em foco; só o realce Python entende esses métodos.
        self.cursorPositionChanged.connect(self._atualizar_linha_cursor_tag)
        # R6-03: debounce 60ms — selectionChanged dispara para CADA linha
        # do gesto de seleção. Sem debounce, _atualizar_selecao_tag() chama
        # rehighlightBlock() por cada linha selecionada na UI thread, congelando
        # a IDE ao selecionar arquivos grandes (Ctrl+A, Shift+Click em 300+ linhas).
        # 60ms: agrupa toda a sequência de eventos num único rehighlight ao final.
        self._timer_selecao_tag = QTimer()
        self._timer_selecao_tag.setSingleShot(True)
        self._timer_selecao_tag.setInterval(60)
        self._timer_selecao_tag.timeout.connect(self._atualizar_selecao_tag)
        self.selectionChanged.connect(self._timer_selecao_tag.start)

        # Lint em tempo real
        self._selecoes_lint: list = []
        self._signals_lint = None         # _SinaisLint do _RunnableLint ativo
        self._signals_diff_gutter = None  # _SinaisDiffGutter do _RunnableDiffGutter ativo
        self._timer_lint = QTimer()
        self._timer_lint.setSingleShot(True)
        self._timer_lint.setInterval(800)
        self._timer_lint.timeout.connect(self._lint_rapido)
        self.textChanged.connect(self._timer_lint.start)

        # Marca a linha e o instante da última edição de texto. Usado pelo
        # quick-fix (ver _avaliar_e_mostrar_quick_fix) pra nunca aparecer
        # sozinho na linha que o usuário ACABOU de digitar — um erro
        # "undefined name" enquanto a palavra ainda está incompleta (ex.:
        # 'pr' no meio de digitar 'print(') é real pro lint naquele
        # instante, mas é ruído: o usuário não terminou de escrever ainda.
        self._ultima_linha_editada = -1
        self._ultimo_edit_ts       = 0.0
        self.textChanged.connect(self._marcar_edicao)

        # IMP-09 — realce de ocorrências da seleção atual (debounced 300 ms)
        self._selecoes_realce: list = []
        self._timer_realce = QTimer()
        self._timer_realce.setSingleShot(True)
        self._timer_realce.setInterval(300)
        self._timer_realce.timeout.connect(self._realcar_ocorrencias)
        self.cursorPositionChanged.connect(self._timer_realce.start)

        # Quick-fix por teclado: equivalente ao hover do mouse, mas
        # disparado quando o cursor de TEXTO fica parado numa linha com
        # erro — cobre quem navega só pelo teclado (setas, Home/End, F12
        # etc.) e nunca passa o mouse sobre a linha. Debounced pra não
        # abrir/fechar o popup a cada tecla enquanto o cursor está em
        # trânsito. Ctrl+. (ver editor_acoes.py) abre na hora, sem esperar.
        self._timer_quick_fix_teclado = QTimer()
        self._timer_quick_fix_teclado.setSingleShot(True)
        self._timer_quick_fix_teclado.setInterval(450)
        self._timer_quick_fix_teclado.timeout.connect(self._checar_quick_fix_por_cursor)
        self.cursorPositionChanged.connect(self._timer_quick_fix_teclado.start)
        # Navegação programática (Outline, busca, definição etc.) também move
        # o cursor e emite cursorPositionChanged. O timer é cancelado em
        # ir_para_linha() para não tratar uma navegação como pausa de teclado.

    def _atualizar_linha_cursor_tag(self):
        """Avisa o realce (se for Python) qual linha deve mostrar por
        completo o código das Tags de Comentário (#al:/#al;/#:)."""
        if hasattr(self._realce, 'definir_linha_cursor_tag'):
            self._realce.definir_linha_cursor_tag(self.textCursor().blockNumber())

    def _atualizar_selecao_tag(self):
        """Avisa o realce (se for Python) qual intervalo de linhas está
        selecionado, pra também mostrar o código das Tags de Comentário."""
        if not hasattr(self._realce, 'definir_selecao_tag'):
            return
        cursor = self.textCursor()
        if cursor.hasSelection():
            doc = self.document()
            bloco_ini = doc.findBlock(cursor.selectionStart()).blockNumber()
            bloco_fim = doc.findBlock(cursor.selectionEnd()).blockNumber()
        else:
            bloco_ini = bloco_fim = -1
        self._realce.definir_selecao_tag(bloco_ini, bloco_fim)

    def abrir_busca(self):
        if getattr(self, '_painel_busca', None):
            self._painel_busca.abrir_busca()

    def _ao_buscar_inline(self, termo: str):
        if not termo:

            return

        if self._painel_busca:
            self._painel_busca._campo_busca.setText(termo)
            self._painel_busca._buscar()

    def _ao_buscar_inline_anterior(self):
        if self._painel_busca:
            self._painel_busca._buscar_anterior()

    def _ao_buscar_projeto(self, termo: str):
        if hasattr(self, '_outline'):
            self._outline._input_busca.setText(termo)

    def _ao_buscar_lembrar(self, termo: str):
        if hasattr(self, '_outline'):
            self._outline._input_busca.setText(termo)

    def _aplicar_fonte(self): # setFont() sozinho é sobrescrito pelo stylesheet aplicado pelo # gerenciador_configurar. Solução: atualizar font-size diretamente # no stylesheet do próprio widget (mesma abordagem do gerenciador).
        tamanho = self._tamanho_fonte
        ss = self.styleSheet() or ""
        ss = _re.sub(r"\bfont-size\s*:[^;]+;", "", ss)
        bloco = _re.search(r'(\w[\w:>\s#.]*)\s*\{([^}]*)\}', ss)
        if bloco:
            ss = _re.sub(
                r'(\w[\w:>\s#.]*)\s*\{([^}]*)\}',
                lambda m: f"{m.group(1)} {{ {m.group(2).strip()} "
                          f"font-size: {tamanho}pt; }}",
                ss
            )
        else:
            ss = ss + f" font-size: {tamanho}pt;"
        self.setFont(QFont(FONTE_EDITOR, tamanho))  # fallback para áreas sem stylesheet
        self.setStyleSheet(ss)
        if hasattr(self, "metricas"):
            self.metricas.atualizar_margem()

    # 💡 cor_opc = Literal["#aeafad"] ← defina os valores válidos
    def configurar_cursor(self, forma: str, largura: int, piscar: bool, estilo: str, cor: str = "#aeafad"):
        """Configura forma, piscar e cor do cursor. Chamado pelo gerenciador_configurar."""
        # Sempre delega — gerenciador aplica cursor_cor universal (setCursorWidth(0) + custom draw)
        self._cursor_mgr.configurar(forma, largura, piscar, estilo, cor)

    def _configurar_tema(self, tema: dict): # 💡 fb_opc = Literal["#e0e0e0"] ← defina os valores válidos
        def c(chave, fb="#e0e0e0"):
            partes = chave.split(".")
            nó = tema
            try:
                for p in partes:
                    nó = nó[p]
                v = str(nó)
                if len(v) == 9 and v.startswith("#"):
                    v = v[:7]

                return v

            except (KeyError, TypeError):

                return tema_global().cor(chave, fb)

        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {c('editor.fundo', '#0d0d0d')};
                color: {c('editor.texto', '#e0e0e0')};
                selection-background-color: {c('editor.selecao', '#264f78')};
                border: none;
            }}
        """)
        self._cor_linha_ativa        = QColor(c("editor.linha_ativa_fundo", "#141414"))
        self._cor_numero_linha       = QColor(c("editor.numero_linha",       "#3a3a3a"))
        self._cor_numero_linha_ativo = QColor(c("editor.numero_linha_ativo", "#4a90d9"))
        self.area_numeros.cor_texto       = self._cor_numero_linha
        self.area_numeros.cor_texto_ativo = self._cor_numero_linha_ativo
        self.area_numeros.cor_fundo       = QColor(c("editor.fundo_calha", "#000000"))

    def atualizar_tema(self, tema: dict):
        self._configurar_tema(tema)
        self._realce.aplicar_tema(tema)

    def _trocar_realce_por_extensao(self, caminho: str):
        from _EDITOR_.Mult_Linguas import get_provider
        from _CONFIGURA_ import OUTLINE_LARGURA_MIN
        ext = os.path.splitext(caminho)[1].lower()
        provider = get_provider(ext)
        self._realce.setDocument(None)
        self._realce = provider.create_highlighter(self.document())
        # Oculta outline para linguagens sem estrutura (outline_mode='none')
        if not hasattr(self, '_outline'):
            return
        if provider.outline_mode == 'none':
            # salva largura atual para restaurar depois
            if getattr(self, '_largura_outline', 0) > 0:
                self._largura_outline_salvo = self._largura_outline
            self._largura_outline = 0
            self._outline.hide()
            if hasattr(self, '_handle_outline'):
                self._handle_outline.hide()
        else:
            if getattr(self, '_largura_outline', -1) == 0:
                self._largura_outline = getattr(self, '_largura_outline_salvo', OUTLINE_LARGURA_MIN)
                self._outline.show()
                if hasattr(self, '_handle_outline'):
                    self._handle_outline.show()
        self._atualizar_geometria_outline()

        # Corretor ortografico: liga/desliga conforme provider.spell_check
        _MODO_CORRETOR = {
            '.py': 'python', '.pyw': 'python',
            '.md': 'markdown', '.markdown': 'markdown',
        }
        if getattr(provider, "spell_check", False):
            modo_corretor = _MODO_CORRETOR.get(ext, "texto")
            if self._corretor is None:
                from ..Funcionalidades.corretor_ortografico import CorretorOrtografico
                self._corretor = CorretorOrtografico(self, modo_corretor)
            else:
                self._corretor.trocar_modo(modo_corretor)
            QTimer.singleShot(1500, self._corretor.verificar_agora)
        elif self._corretor is not None:
            self._corretor.limpar()

    def _marcar_edicao(self):
        """Registra em qual linha e quando a última edição de texto
        aconteceu — usado por _avaliar_e_mostrar_quick_fix pra não abrir o
        popup em cima de uma palavra que o usuário ainda está digitando."""
        self._ultima_linha_editada = self.textCursor().blockNumber() + 1
        self._ultimo_edit_ts       = time.monotonic()

    def _lint_rapido(self):
        """Lança _RunnableLint em background — não bloqueia a UI."""
        from _EDITOR_.Mult_Linguas import get_provider, is_registered
        fp = getattr(self, 'file_path', None)
        ext = os.path.splitext(fp)[1].lower() if fp else ''
        if not fp or not (is_registered(ext) and get_provider(ext).lint):
            # Linguagem sem lint: limpa erros e sai sem rodar AST
            self._erros_lint.clear()
            self._mensagens_erros.clear()
            self._selecoes_lint = []
            self.setExtraSelections([])
            self._atualizar_gutter_erros()

            return

        # Descarta sinais do runnable anterior (ele termina por conta no pool)
        if self._signals_lint is not None:
            try:
                self._signals_lint.concluido.disconnect()
            except RuntimeError:
                pass
        from PySide6.QtCore import QThreadPool
        _edit = edit_generation(self)
        _task = new_task("LINT", self, _edit)
        r = _RunnableLint(self.toPlainText(), _task, self, _edit)
        reference("REPLACE", "LINT", self, "_signals_lint",
                  before=self._signals_lint, after=r.signals,
                  editor=self, task=_task)
        self._signals_lint = r.signals
        self._signals_lint.concluido.connect(self._aplicar_resultados_lint)
        event("START_REQUESTED", "LINT", _task, obj=r.signals,
              editor=self)
        QThreadPool.globalInstance().start(r)

    def _aplicar_resultados_lint(self, erros: dict, mensagens: dict):
        """Recebe resultados do _ThreadLint e aplica na UI (roda na UI thread)."""
        from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor, QTextFormat
        self._mensagens_erros.update(mensagens)
        self._selecoes_lint = []
        for linha, valor in erros.items():
            tipo = valor[0] if isinstance(valor, tuple) else valor
            bloco = self.document().findBlockByNumber(linha - 1)
            if not bloco.isValid():
                continue
            sel = QTextEdit.ExtraSelection()
            fmt = QTextCharFormat()
            fmt.setUnderlineStyle(QTextCharFormat.WaveUnderline)
            fmt.setUnderlineColor(QColor("#e05252") if tipo == "error" else QColor("#e5c07b"))
            fmt.setProperty(QTextFormat.UserProperty + 100, True)
            sel.format = fmt
            sel.cursor = QTextCursor(bloco)
            sel.cursor.select(QTextCursor.LineUnderCursor)
            self._selecoes_lint.append(sel)
        # Aplica lint preservando waves do ValidadorImports e demais seleções
        from PySide6.QtGui import QTextFormat as _QTF
        _MARKER = _QTF.UserProperty + 100
        _preservar = [
            s for s in self.extraSelections()
            if s.format.underlineStyle() != QTextCharFormat.WaveUnderline
            or not s.format.property(_MARKER)
        ]
        self.setExtraSelections(_preservar + self._selecoes_lint)
        self._erros_lint = erros
        self._atualizar_gutter_erros()
        self._destacar_linha_atual()

    # ⚠️  except genérico vazio
    def _lint_pyflakes(self, codigo: str) -> dict:
        erros = {}
        try:
            import ast as _ast
            from pyflakes.checker import Checker
            from pyflakes import messages as pf_msgs
            tree = compile(codigo, "<editor>", "exec", _ast.PyCF_ONLY_AST)
            checker = Checker(tree, "<editor>")
            for msg in checker.messages:
                linha = msg.lineno
                try:
                    texto = msg.message % msg.message_args
                except Exception:
                    texto = str(msg)
                self._mensagens_erros[linha] = texto
                if isinstance(msg, (pf_msgs.UndefinedName, pf_msgs.UndefinedLocal)):
                    erros[linha] = "error"
                else:
                    erros.setdefault(linha, "warning")
        except ImportError:
            pass
        except Exception:
            pass

        return erros

    # ══════════════════════════════════════════════════════════════════
    # Eventos de mouse
    # ══════════════════════════════════════════════════════════════════

    def mousePressEvent(self, event):
        # Dismissal explícito do PopupQuickFix: qualquer clique dentro do
        # editor fecha o popup de import/instalar que estiver aberto. Um
        # clique no próprio botão do popup nunca chega aqui — o popup é uma
        # janela separada e recebe o evento diretamente.
        if self._popup_quick_fix.isVisible():
            self._popup_quick_fix.fechar()

        if self._multi_cursor.ao_click(event):

            return

        # Ctrl+Click em .hein → navegar [[wikilink]] (tem prioridade sobre ir_definicao)
        if (event.button() == Qt.LeftButton
                and event.modifiers() == Qt.ControlModifier
                and self._eh_hein()):
            if self._navegar_wikilink_hein(event.pos()):
                return

        # Ctrl+Click sobre URL/caminho genérico — tem prioridade sobre ir_definicao,
        # que consome TODO Ctrl+Click (mesmo sem achar definição) e nunca devolveria
        # a vez pra esse passo se viesse depois.
        if (event.button() == Qt.LeftButton
                and event.modifiers() == Qt.ControlModifier
                and self._navegar_caminho_generico(event.pos())):

            return

        if self._ir_definicao.ao_click_mouse(event):

            return

        if event.button() == Qt.LeftButton:
            if self._lens_overlay.checar_clique(event.pos()):

                return

        self._autocomplete.fechar()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # Arraste de seleção não deve deixar uma resposta assíncrona de
        # TooltipSignature reabrir o balão no novo contexto do editor.
        if event.buttons() & Qt.LeftButton:
            self._invalidar_popups_interacao()

        if self._multi_cursor.ao_mover_coluna(event.pos()):

            return

        self._ir_definicao.ao_mover_mouse(event)
        self._lens_overlay.checar_hover(event.pos())
        # Debounce: armazena posição e só checa tooltip após 80ms parado.
        # Chamar direto causava I/O de disco + Signals Qt a cada pixel.
        self._pos_mouse_tooltip = event.pos()
        self._timer_checar_tooltip.start()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._multi_cursor.finalizar_arrasto_coluna():
                # Ctrl+Alt click ou drag: não propagar para o Qt para que o cursor
                # principal não seja sobrescrito pelo comportamento padrão de release.

                return

        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """Ctrl + roda do mouse → zoom (aumenta/diminui fonte do editor,
        que já redimensiona a calha/régua via metricas.atualizar_margem())."""
        self._invalidar_popups_interacao()

        if event.modifiers() == Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.aumentar_fonte()
            elif event.angleDelta().y() < 0:
                self.diminuir_fonte()

            event.accept()

            return

        super().wheelEvent(event)

    def leaveEvent(self, event):
        self._ir_definicao._limpar_destaque_hover()

    # ══════════════════════════════════════════════════════════════════════
    # .hein — helpers e ações especiais
    # ══════════════════════════════════════════════════════════════════════

    def _eh_hein(self) -> bool:
        """True quando o arquivo aberto é .hein."""
        fp = getattr(self, 'file_path', None)
        return bool(fp and fp.lower().endswith('.hein'))

    def _inserir_data_hein(self):
        """Ctrl+Shift+T — insere a data de hoje como título # Dia, DD de Mês de AAAA."""
        import datetime
        _DIAS  = ['Segunda', 'Terça', 'Quarta', 'Quinta',
                  'Sexta', 'Sábado', 'Domingo']
        _MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
                  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
        hoje   = datetime.date.today()
        titulo = (f"# {_DIAS[hoje.weekday()]}, {hoje.day} de "
                  f"{_MESES[hoje.month - 1]} de {hoje.year}\n")
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.insertText(titulo)
        self.setTextCursor(cursor)

    def _toggle_modo_leitura_hein(self):
        """F4 — alterna modo leitura: sem gutter, margens laterais largas."""
        self._modo_leitura_hein = not getattr(self, '_modo_leitura_hein', False)
        leitura = self._modo_leitura_hein
        if leitura:
            if hasattr(self, 'area_numeros'): self.area_numeros.hide()
            if hasattr(self, 'regua_erros'):  self.regua_erros.hide()
            self.setViewportMargins(48, 10, 48, 10)
        else:
            if hasattr(self, 'area_numeros'): self.area_numeros.show()
            if hasattr(self, 'regua_erros'):  self.regua_erros.show()
            if hasattr(self, 'metricas'):     self.metricas.atualizar_margem()

    def _navegar_wikilink_hein(self, pos) -> bool:
        """Ctrl+Click sobre [[link]] — abre o arquivo referenciado.
        Retorna True se navegou (evento consumido), False se não havia link."""
        import re as _re_w, os as _os_w
        cursor  = self.cursorForPosition(pos)
        texto   = cursor.block().text()
        pos_col = cursor.positionInBlock()
        for m in _re_w.finditer(r'\[\[([^\]]+)\]\]', texto):
            if m.start() <= pos_col <= m.end():
                nome = m.group(1).strip()
                if not nome:
                    return False
                pasta = _os_w.path.dirname(getattr(self, 'file_path', '') or '') or '.'
                # Tenta extensões: exato, +.hein, +.txt
                for cand in (nome, nome + '.hein', nome + '.txt'):
                    alvo = _os_w.path.join(pasta, cand)
                    if _os_w.path.isfile(alvo):
                        self._abrir_arquivo_hein(alvo)
                        return True
                # Arquivo não existe → cria novo .hein
                self._abrir_arquivo_hein(_os_w.path.join(pasta, nome + '.hein'))
                return True
        return False

    def _navegar_caminho_generico(self, pos) -> bool:
        """Ctrl+Click sobre uma URL (http/https) ou um caminho de arquivo/pasta
        em qualquer linguagem — abre no navegador ou na IDE/explorador do sistema.
        Retorna True se navegou (evento consumido), False se não havia nada."""
        import re as _re_g, os as _os_g
        cursor = self.cursorForPosition(pos)
        texto  = cursor.block().text()
        col    = cursor.positionInBlock()

        # URL http(s) — abre no navegador padrão
        for m in _re_g.finditer(r'https?://[^\s"\'<>\)\]]+', texto):
            if m.start() <= col <= m.end():
                from PySide6.QtGui  import QDesktopServices
                from PySide6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl(m.group(0)))

                return True

        # Caminho de arquivo/pasta — Windows absoluto (C:\...), relativo
        # (./ ../ pasta/arquivo) ou qualquer trecho com barras.
        _RE_CAMINHO = (
            r'[A-Za-z]:[\\/][^\s"\'<>|?*]+'
            r'|\.{1,2}[\\/][^\s"\'<>|?*]+'
            r'|(?:[\w.\-]+[\\/])+[\w.\-]+'
        )
        for m in _re_g.finditer(_RE_CAMINHO, texto):
            if m.start() <= col <= m.end():
                bruto = m.group(0).strip('.,;:()[]')
                if not bruto:
                    continue

                pasta_base = _os_g.path.dirname(getattr(self, 'file_path', '') or '') or '.'
                candidatos = [bruto]
                if not _os_g.path.isabs(bruto):
                    candidatos.append(_os_g.path.join(pasta_base, bruto))
                    proj_path = getattr(self._autocomplete, '_project_path', None)
                    if proj_path:
                        candidatos.append(_os_g.path.join(proj_path, bruto))

                for alvo in candidatos:
                    alvo = _os_g.path.normpath(alvo)
                    if _os_g.path.isdir(alvo):
                        from PySide6.QtGui  import QDesktopServices
                        from PySide6.QtCore import QUrl
                        QDesktopServices.openUrl(QUrl.fromLocalFile(alvo))

                        return True
                    if _os_g.path.isfile(alvo):
                        self._abrir_arquivo_hein(alvo)

                        return True

        return False

    def _abrir_arquivo_hein(self, caminho: str):
        """Tenta abrir um arquivo na IDE pelo método disponível na MainWindow."""
        janela = self.window()
        for nome in ('abrir_arquivo', 'abrir_tab_arquivo', 'abrir_em_nova_aba'):
            metodo = getattr(janela, nome, None)
            if callable(metodo):
                metodo(caminho)
                return
        super().leaveEvent(event)

    def _avaliar_e_mostrar_quick_fix(self, linha: int, cursor) -> bool:
        """
        Núcleo compartilhado entre os dois gatilhos do quick-fix — mouse
        (_checar_tooltip_erro) e teclado (_checar_quick_fix_por_cursor /
        Ctrl+.). Calcula se `linha` oferece um quick-fix (import/instalar)
        e, se sim, mostra o PopupQuickFix ancorado nela. Retorna True
        quando mostrou algo, False quando a linha não tem quick-fix
        disponível (o chamador decide o que fazer nesse caso — mostrar
        tooltip simples, ignorar, etc.).
        """
        from PySide6.QtWidgets import QToolTip
        from _TRADUTION_.tradutor_erros import traduzir
        from _LOG_.log import log as _log
        from ..Autocomplete.quick_fix import (
            extrair_nome_undefined, extrair_modulo_da_linha,
            achar_pip, modulo_em_stdlib, modulo_em_venv,
        )

        erros = {**self._erros_lint, **self._erros_imports}
        if linha not in erros:
            return False

        # Não mostra o quick-fix em cima de uma linha que o usuário ainda
        # está digitando — só porque "pr" (no meio de escrever "print(")
        # bate como nome indefinido pro lint não quer dizer que é um erro
        # de verdade; é só a palavra incompleta. Espera um tempo maior que
        # o debounce do lint (800 ms) depois da última tecla NESSA linha
        # antes de considerar o erro "assentado" o suficiente pra agir.
        LIMIAR_ASSENTAMENTO = 1.2
        if (linha == getattr(self, '_ultima_linha_editada', -1)
                and time.monotonic() - getattr(self, '_ultimo_edit_ts', 0.0) < LIMIAR_ASSENTAMENTO):
            return False

        msgs = getattr(self, '_mensagens_erros', {})
        tipo = erros[linha]
        # Bug A corrigido: fallback restaurado para sempre ter mensagem
        raw  = msgs.get(linha) or ("⚠  Aviso" if tipo == "warning" else "Erro")
        msg_traduzida = traduzir(raw)

        proj          = getattr(self, '_caminho_projeto', None)
        nome_modulo   = None
        pode_importar = False
        pode_instalar = False

        eh_import_invalido = linha in self._erros_imports

        if eh_import_invalido:
            # Linha É um import quebrado → extrai módulo diretamente do texto da linha
            # Bug C corrigido: não depende de _mensagens_erros (ValidadorImports não o popula)
            bloco = self.document().findBlockByNumber(linha - 1)
            texto_linha = bloco.text() if bloco.isValid() else ""
            nome_modulo = extrair_modulo_da_linha(texto_linha)
            if nome_modulo:
                msg_traduzida = f"Módulo '{nome_modulo}' não encontrado"
                if modulo_em_stdlib(nome_modulo) or modulo_em_venv(nome_modulo, proj):
                    # Módulo existe mas não foi importado (warning de nome)
                    pode_importar = True
                else:
                    # Módulo não instalado na .venv
                    pode_instalar = True
        else:
            # Erro de lint — tenta extrair nome indefinido do pyflakes
            nome_modulo = extrair_nome_undefined(raw)
            if nome_modulo:
                if modulo_em_stdlib(nome_modulo) or modulo_em_venv(nome_modulo, proj):
                    pode_importar = True
                else:
                    pode_instalar = True

        if not (nome_modulo and (pode_importar or pode_instalar)):
            return False

        pip_path   = achar_pip(proj)
        rect       = self.cursorRect(cursor)
        pos_global = self.viewport().mapToGlobal(rect.bottomLeft())
        pos_global.setY(pos_global.y() + 4)

        QToolTip.hideText()
        self._popup_quick_fix.mostrar(
            pos_global, msg_traduzida, nome_modulo,
            pode_importar, pode_instalar, pip_path, linha,
        )
        return True

    def _checar_tooltip_erro(self, pos):
        """
        Ao passar o mouse sobre linha com erro:
          • Se há quick-fix disponível (import / install) → exibe PopupQuickFix
          • Caso contrário → QToolTip simples em português (comportamento original)

        Uma vez aberto, o PopupQuickFix permanece visível enquanto o mouse
        se desloca até o botão Importar/Instalar — mesmo que o trajeto
        passe por linhas sem erro, ou com erro de outro tipo, no caminho.
        Ele só troca de conteúdo quando o cursor passa a estar sobre OUTRA
        linha que também ofereça um quick-fix (substituição legítima); fora
        isso, o fechamento é sempre por dismissal explícito — clique em
        outro lugar do editor (mousePressEvent) ou Esc (keyPressEvent) —
        nunca por causa do próprio movimento do mouse.
        """
        from PySide6.QtWidgets import QToolTip
        from _TRADUTION_.tradutor_erros import traduzir

        popup_aberto = self._popup_quick_fix.isVisible()

        # Mouse já está sobre a área do próprio popup (ex.: descendo da linha
        # de erro até o botão Instalar/Importar) → ignora completamente esta
        # chamada.
        if popup_aberto:
            pos_global = self.viewport().mapToGlobal(pos)
            if self._popup_quick_fix.geometry().contains(pos_global):
                return

        cursor = self.cursorForPosition(pos)
        linha  = cursor.blockNumber() + 1
        erros  = {**self._erros_lint, **self._erros_imports}

        if linha not in erros:
            # Linha sem erro no trajeto até o popup: NÃO fecha o quick-fix
            # que já estiver aberto — era essa reavaliação a cada pixel que
            # fazia o popup sumir antes do clique chegar ao botão.
            if not popup_aberto:
                QToolTip.hideText()
            return

        # Popup já visível para esta linha — não reposiciona
        if popup_aberto and self._popup_quick_fix.linha_atual() == linha:
            return

        if self._avaliar_e_mostrar_quick_fix(linha, cursor):
            return

        if not popup_aberto:
            # Sem quick-fix disponível → tooltip simples (comportamento
            # original). Só entra aqui quando NÃO havia popup de quick-fix
            # aberto — evita fechar um popup em uso por causa de uma linha
            # de erro diferente e não relacionada cruzada no trajeto até o
            # botão (mesmo raciocínio do bloco "linha not in erros" acima).
            msgs = getattr(self, '_mensagens_erros', {})
            tipo = erros[linha]
            raw  = msgs.get(linha) or ("⚠  Aviso" if tipo == "warning" else "Erro")
            self._popup_quick_fix.fechar()
            QToolTip.showText(
                self.viewport().mapToGlobal(pos),
                traduzir(raw),
                self.viewport(),
            )

    def _checar_quick_fix_por_cursor(self):
        """
        Gatilho por TECLADO — equivalente ao _checar_tooltip_erro, mas
        ancorado no cursor de texto em vez do mouse. Disparado (com
        debounce de 450ms, ver _configurar) toda vez que o cursor de texto
        muda de posição; se ele fica parado numa linha com erro, mostra o
        mesmo PopupQuickFix — sem precisar do mouse. Mesma regra de nunca
        fechar por conta própria: só substitui o popup por outra linha que
        também tenha quick-fix; do contrário deixa o que já está aberto
        (por mouse ou teclado) em paz.
        """
        from PySide6.QtWidgets import QToolTip
        from _TRADUTION_.tradutor_erros import traduzir

        if not self.hasFocus():
            return  # cursor "mudou" por causa de outra aba/janela, não do usuário navegando aqui

        popup_aberto = self._popup_quick_fix.isVisible()
        cursor = self.textCursor()
        linha  = cursor.blockNumber() + 1
        erros  = {**self._erros_lint, **self._erros_imports}

        if linha not in erros:
            return

        if popup_aberto and self._popup_quick_fix.linha_atual() == linha:
            return

        if self._avaliar_e_mostrar_quick_fix(linha, cursor):
            return

        if not popup_aberto:
            msgs = getattr(self, '_mensagens_erros', {})
            tipo = erros[linha]
            raw  = msgs.get(linha) or ("⚠  Aviso" if tipo == "warning" else "Erro")
            rect = self.cursorRect(cursor)
            QToolTip.showText(
                self.viewport().mapToGlobal(rect.bottomLeft()),
                traduzir(raw),
                self.viewport(),
            )

    def _abrir_quick_fix_no_cursor(self):
        """Ctrl+. — abre o quick-fix na linha do cursor imediatamente,
        sem esperar o debounce do gatilho por teclado. Atalho padrão de
        Quick Fix em IDEs (VS Code, IntelliJ etc.)."""
        self._timer_quick_fix_teclado.stop()
        self._checar_quick_fix_por_cursor()

    def _refresh_layout(self):
        """
        Força o Qt a reprocessar o layout visual do documento após operações
        de fold/unfold. Sem isso, blocos ocultados/revelados não reflectem
        imediatamente no viewport e a calha fica dessincronizada.
        """
        doc = self.document()
        if not doc:

            return

        bloco  = doc.firstBlock()
        inicio = bloco.position()
        fim    = doc.characterCount()
        doc.markContentsDirty(inicio, fim - inicio)
        # layout.update() é sinal Qt, não função — markContentsDirty já dispara o reprocessamento
        self.viewport().update()
        self.updateGeometry()
        self.update()

    def focusOutEvent(self, event):
        """
        Cancela multi-cursor ao perder foco (Alt+Tab, clique em outro painel).
        Sem isso, o estado de multi-cursor fica sujo ao voltar para o editor.
        """
        if hasattr(self, "_multi_cursor"):
            self._multi_cursor.cancelar()
        super().focusOutEvent(event)

    def closeEvent(self, event):
        try:
            self.viewport().removeEventFilter(self._lens_overlay)
        except RuntimeError:
            pass
        super().closeEvent(event)

    # ⚠️  CodeEditor não é janela de topo — closeEvent() acima NUNCA dispara
    # quando a aba é fechada via TabWidget.removeTab() (só em janelas
    # flutuantes de topo). Por isso o TabWidget precisa chamar este método
    # explicitamente ANTES de removeTab(), ou as QThreads de fundo deste
    # editor (lint, diff gutter, busca do outline, autocomplete) continuam
    # rodando enquanto o editor é destruído — 'QThread: Destroyed while
    # thread is still running' no meio do uso normal, sem fechar a IDE.
    def encerrar_threads_bg(self):
        """Para todas as QThreads de fundo deste editor antes da aba fechar."""
        if self._signals_lint is not None:
            try:
                self._signals_lint.concluido.disconnect()
            except RuntimeError:
                pass
            reference("ZERO", "LINT", self, "_signals_lint",
                      before=self._signals_lint, after=None, editor=self,
                      task=getattr(self._signals_lint, "_hein_diag_task", ""))
            self._signals_lint = None

        if self._signals_diff_gutter is not None:
            try:
                self._signals_diff_gutter.diff_pronto.disconnect()
                self._signals_diff_gutter.hunks_prontos.disconnect()
            except RuntimeError:
                pass
            reference("ZERO", "DIFF", self, "_signals_diff_gutter",
                      before=self._signals_diff_gutter, after=None,
                      editor=self,
                      task=getattr(self._signals_diff_gutter, "_hein_diag_task", ""))
            self._signals_diff_gutter = None

        outline = getattr(self, "_outline", None)
        if outline is not None:
            try:
                outline._cancelar_busca()
            except Exception:
                pass
            check_live_without_reference(
                outline, "_thread_outline", "OUTLINE", self
            )

        autocomplete = getattr(self, "_autocomplete", None)
        if autocomplete is not None and hasattr(autocomplete, "encerrar_threads"):
            try:
                autocomplete.encerrar_threads()
            except Exception:
                pass

        validador = getattr(self, "_validador_imports", None)
        if validador is not None and hasattr(validador, "encerrar_threads"):
            try:
                validador.encerrar_threads()
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════
    # Resize / área de números / busca
    # ══════════════════════════════════════════════════════════════════

    # ⚠️  except genérico vazio
    def _atualizar_geometria_outline(self):
        if not hasattr(self, '_outline'):

            return  # outline ainda não criado (pode acontecer no resizeEvent inicial)

        largura  = getattr(self, '_largura_outline', 0)
        hd       = _HANDLE_OUTLINE_LARGURA
        h_sticky = self._sticky.height() if hasattr(self, '_sticky') and self._sticky.isVisible() else 0

        self._outline.setGeometry(self.width() - largura, 0, largura, self.height())
        self._outline.raise_()

        if hasattr(self, '_handle_outline'):
            x_hd = self.width() - largura - hd
            self._handle_outline.setGeometry(x_hd, 0, hd, self.height())
            self._handle_outline.raise_()

        # O rodapé de status (borda inferior do editor, parando antes do
        # outline) depende de _largura_outline pra se posicionar. Sem chamar
        # posicionar() aqui, ele só era recalculado no resizeEvent — ao
        # arrastar o handle (drag) pra redimensionar a outline, a largura
        # mudava mas o rodapé ficava com a posição antiga (stale) e acabava
        # "dentro" da área da outline quando ela crescia por cima da posição
        # velha da barra.
        if hasattr(self, '_barra_status'):
            self._barra_status.posicionar()

        # Notifica a BarraCentral para reservar espaço direito igual ao outline
        try:
            janela = self.window()
            if hasattr(janela, '_barra_central'):
                reserva = (largura + hd) if largura > 0 else 0
                janela._barra_central.setRightReserva(reserva)
        except Exception:
            pass

        altura_status = self._barra_status.ALTURA if hasattr(self, '_barra_status') else 0
        self.setViewportMargins(
            self.metricas.largura_area_numeros(), h_sticky,
            largura + hd + ReguaErros.LARGURA, altura_status
        )

    def toggle_outline(self):
        """Atalho — abre/fecha o outline completamente (Ctrl+Shift+O)."""
        from _CONFIGURA_ import OUTLINE_LARGURA_MIN
        if getattr(self, '_largura_outline', 0) == 0:
            self._largura_outline = OUTLINE_LARGURA_MIN
            self._outline.show()
        else:
            self._largura_outline = 0
            self._outline.hide()
        self._atualizar_geometria_outline()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_barra_status'):
            self._barra_status.posicionar()
        if getattr(self, '_diff_inline', None) is not None:
            self._diff_inline.reposicionar()
        larg_calha = self.metricas.largura_area_numeros()
        self.area_numeros.setGeometry(0, 0, larg_calha, self.height())
        if hasattr(self, '_regua_erros'):
            # Régua de erros agora fica colada direto no handle/outline (antes
            # da barra de status), e a barra de status fica mais pra dentro
            # do editor, do outro lado da régua de erros — pedido do usuário.
            largura_out  = getattr(self, '_largura_outline', 0)
            x = self.width() - largura_out - _HANDLE_OUTLINE_LARGURA - ReguaErros.LARGURA
            self._regua_erros.setGeometry(x, 0, ReguaErros.LARGURA, self.height())
        self._atualizar_geometria_outline()
        if hasattr(self, '_regua_erros'):
            self._regua_erros.raise_()  # raise DEPOIS do outline — fica na frente
        if hasattr(self, '_barra_salto'):
            self._barra_salto.posicionar()
        if hasattr(self, '_scrollbar_fold'):
            self._scrollbar_fold.atualizar_e_posicionar()
        if getattr(self, '_painel_busca', None) and self._painel_busca.isVisible():
            self._painel_busca._reposicionar()

    def showEvent(self, event):
        super().showEvent(event)

    def _atualizar_area_numeros(self, rect: QRect, dy: int):
        if dy:
            self.area_numeros.scroll(0, dy)
        else:
            self.area_numeros.update(0, rect.y(), self.area_numeros.width(), rect.height())
        if getattr(self, '_diff_inline', None) is not None:
            self._diff_inline.reposicionar()

    def _abrir_busca(self): self.abrir_busca()
    def abrir_substituicao(self):
        if getattr(self, '_painel_busca', None):
            self._painel_busca.abrir_substituicao()

    def _abrir_substituicao(self): self.abrir_substituicao()
    def set_projeto(self, caminho: str):
        """Repassa o caminho do projeto para o outline (busca global)."""
        self._caminho_projeto = caminho
        if hasattr(self, '_outline'):
            self._outline.set_projeto(caminho)
        self._autocomplete.set_project_path(caminho)   # ← FALTA ISSO

    # ══════════════════════════════════════════════════════════════════
    # Navegação
    # ══════════════════════════════════════════════════════════════════

    def centralizar_linha_cursor(self):
        """Ctrl+Space — centraliza no viewport a linha onde está o cursor,
        sem mover o cursor nem alterar a seleção."""
        self.centerCursor()

    # ⚠️  função grande (56 linhas)
    def ir_para_linha(self, numero_linha: int):
        """
        Navega para a linha indicada (1-based).

        Comportamento:
          - Linha já visível  → só move o cursor, NÃO altera o scroll.
          - Linha fora da tela → move o cursor E centraliza no viewport.

        IMPORTANTE: verticalScrollBar usa unidades de LINHAS, não pixels.

        ⚠️  ZONA CRÍTICA — NÃO ALTERE A LÓGICA SEM LER:
        ─────────────────────────────────────────────────
        setTextCursor() chama ensureCursorVisible() internamente, que pode
        mover o scroll mesmo quando a linha já está visível. A solução:
          1. Calcula ja_vis ANTES de chamar setTextCursor.
          2. Se já visível: salva o valor do scrollbar e restaura via
             QTimer.singleShot(0) — cancelando o scroll indevido.
          3. Se fora da tela: centraliza via QTimer.singleShot(0).
        O QTimer.singleShot(0) garante que a restauração/centralização
        ocorre APÓS o ensureCursorVisible do Qt processar.
        NÃO use QTimer de delay maior (ex: 10ms) — causa flash visível.
        NÃO use ensureCursorVisible() diretamente — piora o problema.
        """
        bloco = self.document().findBlockByNumber(numero_linha - 1)
        if not bloco.isValid():

            return

        linha_0  = numero_linha - 1
        h_linha  = max(1, self.fontMetrics().height())
        h_sticky = (self._sticky.height()
                    if hasattr(self, '_sticky') and self._sticky.isVisible()
                    else 0)
        h_vp     = max(h_linha, self.viewport().height() - h_sticky)
        n_vis    = max(1, h_vp // h_linha)
        primeiro = self.firstVisibleBlock().blockNumber()
        ultimo   = primeiro + n_vis - 1
        ja_vis   = primeiro <= linha_0 <= ultimo

        sb  = self.verticalScrollBar()
        val = sb.value()

        # A navegação veio de uma ação programática (por exemplo, um clique na
        # Outline), não de uma pausa do usuário digitando/navegando no editor.
        # Fechar/invalidate antes evita que TooltipSignature ou PopupQuickFix
        # sobrevivam à troca de destino; parar também depois do setTextCursor
        # cancela o start provocado pelo sinal cursorPositionChanged emitido
        # durante a movimentação.
        self._invalidar_popups_interacao()
        self._timer_quick_fix_teclado.stop()

        cursor = QTextCursor(bloco)
        self.setTextCursor(cursor)
        self.setFocus()
        self._timer_quick_fix_teclado.stop()

        if ja_vis:
            # Linha já visível: cancela qualquer scroll que ensureCursorVisible
            # possa ter feito e mantém a posição original.
            QTimer.singleShot(0, lambda: sb.setValue(val))
        else:
            # Linha fora da tela: centraliza no viewport.
            def _revelar():
                alvo = max(0, linha_0 - n_vis // 2)
                sb.setValue(alvo)
            QTimer.singleShot(0, _revelar)

    # ══════════════════════════════════════════════════════════════════
    # Arquivo
    # ══════════════════════════════════════════════════════════════════

    def set_file_path(self, caminho: str):
        self.file_path     = caminho
        self.original_text = self.toPlainText()
        self.estado.definir_caminho(caminho)
        self.estado.definir_texto_original(self.original_text)

    def is_modified(self) -> bool:
        return self.toPlainText() != self.original_text

    # ⚠️  função grande (59 linhas)
    def load_file(self, caminho: str) -> bool:
        try:
            conteudo, enc = _ler_arquivo(caminho)

            if conteudo == self.toPlainText():
                self._encoding = enc
                if self.file_path != caminho:
                    self.set_file_path(caminho)
                if hasattr(self, '_barra_status'):
                    self._barra_status.atualizar_arquivo(caminho)
                return True

            # Salva estado do arquivo anterior antes de trocar o conteúdo
            self._salvar_estado_arquivo()

            cursor_atual = self.textCursor()
            linha  = cursor_atual.blockNumber()
            coluna = cursor_atual.positionInBlock()

            # Desabilita undo/redo durante reload — reload do disco nao e desfeito pelo usuario
            self.document().setUndoRedoEnabled(False)
            try:
                doc_cursor = QTextCursor(self.document())
                doc_cursor.beginEditBlock()
                doc_cursor.select(QTextCursor.Document)
                doc_cursor.removeSelectedText()
                doc_cursor.insertText(conteudo)
                doc_cursor.endEditBlock()
            finally:
                self.document().setUndoRedoEnabled(True)

            novo_bloco = self.document().findBlockByNumber(linha)
            if novo_bloco.isValid():
                pos_alvo = novo_bloco.position() + min(coluna, max(0, novo_bloco.length() - 1))
            else:
                pos_alvo = 0
            novo_cursor = QTextCursor(self.document())
            novo_cursor.setPosition(pos_alvo)
            self.setTextCursor(novo_cursor)

            self._encoding = enc
            self.set_file_path(caminho)
            self._trocar_realce_por_extensao(caminho)  # troca para JSON se necessário
            if hasattr(self, '_barra_status'):
                self._barra_status.atualizar_arquivo(caminho)
            if hasattr(self, '_outline'):
                self._outline.conectar_editor(self)
            QTimer.singleShot(500, self._atualizar_sticky_scroll)
            QTimer.singleShot(600, self._atualizar_code_lens)
            _ext = os.path.splitext(caminho)[1].lower()
            from _EDITOR_.Mult_Linguas import get_provider as _gp, is_registered as _ir
            if (_ir(_ext) and _gp(_ext).autocomplete == 'jedi'
                    and hasattr(self, '_validador_imports')):
                QTimer.singleShot(900, self._validador_imports.verificar_agora)
            # Restaura estado persistido (BPs, bookmarks, folds) para o novo arquivo
            QTimer.singleShot(50, self._restaurar_estado_arquivo)
            # IMP-01: diff git na calha
            self._agendar_diff_gutter(caminho)

            return True

        except Exception as e:
            QMessageBox.critical(None, "Erro ao abrir", str(e))

            return False

    def _agendar_diff_gutter(self, caminho: str = None):
        """Agrupa salvamentos/aberturas próximos em uma única consulta Git."""
        self._diff_gutter_pending_path = caminho
        self._timer_diff_gutter.start()

    def _executar_diff_gutter_pendente(self):
        caminho = self._diff_gutter_pending_path
        self._diff_gutter_pending_path = None
        self._iniciar_diff_gutter(caminho)

    def _iniciar_diff_gutter(self, caminho: str = None):
        """IMP-01: lança _RunnableDiffGutter para atualizar a barra git na calha."""
        import os
        from _LOG_.log import log as _log
        # Hunks antigos ficam inválidos depois de salvar — fecha o diff
        # embutido pra não mostrar conteúdo desatualizado.
        if getattr(self, '_diff_inline', None) is not None:
            self._diff_inline.fechar()
        arq  = caminho or getattr(self, "file_path", None)
        if not arq:
            self.area_numeros.set_git_changes({})

            return

        proj = getattr(self, "_caminho_projeto", None) or os.path.dirname(arq)
        if not os.path.exists(os.path.join(proj, ".git")):
            self.area_numeros.set_git_changes({})
            self.area_numeros.set_git_hunks([])

            return
        _log.info("Editor.py", "_iniciar_diff_gutter", f"arquivo={arq!r}  proj={proj!r}")
        try:
            from ..Ui.diff_git_gutter import _RunnableDiffGutter
        except Exception as e:
            _log.erro("Editor.py", "_iniciar_diff_gutter", "import _RunnableDiffGutter falhou", str(e))

            return

        # Descarta sinais do runnable anterior. Pool (autoDelete=True) gerencia
        # destruição do runnable — não há QThread para quit()/wait().
        if self._signals_diff_gutter is not None:
            try:
                self._signals_diff_gutter.diff_pronto.disconnect()
                self._signals_diff_gutter.hunks_prontos.disconnect()
            except RuntimeError:
                pass
            reference("ZERO", "DIFF", self, "_signals_diff_gutter",
                      before=self._signals_diff_gutter, after=None,
                      editor=self,
                      task=getattr(self._signals_diff_gutter, "_hein_diag_task", ""))
            self._signals_diff_gutter = None

        from PySide6.QtCore import QThreadPool
        _edit = edit_generation(self)
        _task = new_task("DIFF", self, _edit)
        r = _RunnableDiffGutter(arq, proj, _task, self, _edit)
        reference("REPLACE", "DIFF", self, "_signals_diff_gutter",
                  before=self._signals_diff_gutter, after=r.signals,
                  editor=self, task=_task)
        self._signals_diff_gutter = r.signals   # mantém ref viva até novo runnable
        self._signals_diff_gutter.diff_pronto.connect(self.area_numeros.set_git_changes)
        self._signals_diff_gutter.hunks_prontos.connect(self.area_numeros.set_git_hunks)
        event("START_REQUESTED", "DIFF", _task, obj=r.signals,
              editor=self, arquivo=arq, projeto=proj)
        QThreadPool.globalInstance().start(r)

    def _set_git_hunk_realce(self, linhas: list[int]):
        """Realça levemente as linhas do hunk git ao hover na barra da calha.
        Usa UserProperty+101 como marker para não conflitar com lint (+100).
        linhas vazia → remove o realce.
        """
        from PySide6.QtGui import QTextCharFormat, QTextCursor, QTextFormat, QColor, QBrush
        _MARKER = QTextFormat.UserProperty + 101
        _preservar = [
            s for s in self.extraSelections()
            if not s.format.property(_MARKER)
        ]
        if not linhas:
            self.setExtraSelections(_preservar)

            return

        area  = self.area_numeros
        _CORES = {
            "added":    area.cor_git_added,
            "modified": area.cor_git_modified,
            "deleted":  area.cor_git_deleted,
        }
        novas = []
        for l1 in linhas:
            bloco = self.document().findBlockByNumber(l1 - 1)
            if not bloco.isValid():
                continue
            tipo     = area._git.get(l1, "added")
            cor_base = QColor(_CORES.get(tipo, area.cor_git_added))
            cor_base.setAlpha(35)
            fmt = QTextCharFormat()
            fmt.setBackground(QBrush(cor_base))
            fmt.setProperty(_MARKER, True)
            sel          = QTextEdit.ExtraSelection()
            sel.format   = fmt
            sel.cursor   = QTextCursor(bloco)
            sel.cursor.select(QTextCursor.LineUnderCursor)
            novas.append(sel)
        self.setExtraSelections(_preservar + novas)

    def ir_para_proxima_mudanca_git(self):
        """Navega para a próxima linha modificada no diff git.
        Cicla: ao chegar no fim volta para a primeira alteração.
        """
        git = getattr(self.area_numeros, '_git', {})
        if not git:
            log.info("Editor/__init__.py", "ir_para_proxima_mudanca_git",
                     "nenhuma mudança git para navegar")
            return
        linhas     = sorted(git.keys())
        linha_atual = self.textCursor().blockNumber() + 1
        # Próxima linha modificada após o cursor atual
        for l in linhas:
            if l > linha_atual:
                self.ir_para_linha(l)
                return
        # Wrap-around: volta à primeira mudança
        self.ir_para_linha(linhas[0])

    def save_file(self, caminho: str = None) -> bool:
        if caminho is None:
            caminho = self.file_path
        if caminho is None:
            # IMP-11: prioriza a raiz do projeto aberto; sem projeto, cai na
            # última pasta usada para salvar no editor (QSettings por contexto)
            from PySide6.QtCore import QSettings
            _settings = QSettings("hein", "hein_IDE")
            _dir_inicial = (
                getattr(self.window(), "current_project_path", "")
                or _settings.value("ultima_pasta_salvar_editor", "")
            )
            caminho, _ = QFileDialog.getSaveFileName(
                self, "Salvar Como", _dir_inicial,
                "Arquivos Python (*.py);;Todos os arquivos (*)"
            )
            if not caminho:

                return False

            _settings.setValue("ultima_pasta_salvar_editor", os.path.dirname(caminho))

        # Captura conteudo na UI thread — toPlainText() nao e thread-safe
        conteudo = self.toPlainText()
        self._salvando_internamente = True
        self._encoding = 'utf-8'
        self.set_file_path(caminho)      # atualiza original_text imediatamente
        self.arquivo_salvo.emit(caminho)  # notifica UI (status bar, reindex) sem esperar disco
        self._salvar_estado_arquivo()     # persiste BPs/bookmarks/folds

        # Escrita em daemon thread — nao bloqueia a UI thread
        def _gravar():
            try:
                with open(caminho, "w", encoding='utf-8') as f:
                    f.write(conteudo)
            except Exception as e:
                from _LOG_.log import log
                log.erro("Editor.py", "save_file._gravar", "falha na escrita", str(e))

        t = threading.Thread(target=_gravar, daemon=True)
        t.start()
        # Mantem flag True ate watcher processar o evento de mudanca do arquivo
        QTimer.singleShot(500, lambda: setattr(self, '_salvando_internamente', False))

        return True

    # ⚠️  except genérico vazio
    def _atualizar_code_lens(self):
        """Atualiza usages do CodeLens reusando o indexador da main_window."""
        caminho = getattr(self, "file_path", None)
        if not caminho:

            return

        try:
            idx = getattr(self.window(), "_indexador", None)
            if idx is None:

                return

            usages = idx.consultas.usages_por_arquivo(caminho)
            self.area_numeros.atualizar_usages(usages)
        except Exception:
            pass

    def _atualizar_sticky_scroll(self):
        if hasattr(self, '_sticky'):
            self._sticky._atualizar()

    def _ao_erros_imports(self, erros: dict):
        self._erros_imports = erros
        self._atualizar_gutter_erros()

    def _atualizar_gutter_erros(self):
        merged = {**self._erros_lint, **self._erros_imports}

        log.info(
            "Editor.py",
            "_atualizar_gutter_erros",
            f"gutter atualizado: total={len(merged)} "
            f"lint={len(self._erros_lint)} imports={len(self._erros_imports)}"
        )
        self.area_numeros.set_erros(merged)
        if hasattr(self, '_regua_erros'):
            self._regua_erros.set_erros(merged)
        if hasattr(self, '_barra_status'):
            self.erros_atualizados.emit(len(merged))

    # ══════════════════════════════════════════════════════════════════
    # Persistência de estado (BPs, bookmarks, folds)
    # ══════════════════════════════════════════════════════════════════

    def _salvar_estado_arquivo(self) -> None:
        """Captura BPs, bookmarks e folds do estado atual e persiste em disco."""
        try:
            if not getattr(self, 'file_path', None):

                return

            cur = self.textCursor()
            self.estado.definir_posicao(
                cur.blockNumber() + 1,
                cur.positionInBlock(),
                self.verticalScrollBar().value(),
            )
            self.estado.definir_breakpoints(self.area_numeros.get_breakpoints())
            self.estado.definir_bookmarks(self.area_numeros.get_bookmarks())
            _folds_salvar = {r.start_block.blockNumber() for r in self._fold_regions if r.collapsed}
            self.estado.definir_folds(_folds_salvar)
            self.estado.salvar()
        except Exception as e:
            log.aviso("Editor.py", "_salvar_estado_arquivo", "falha", str(e))

    def _restaurar_estado_arquivo(self) -> None:
        """Restaura BPs, bookmarks e folds do disco para a UI após load_file."""
        try:
            if not self.estado.carregar():

                return  # nenhum estado salvo — começa limpo

            # Breakpoints
            self.area_numeros.set_breakpoints(self.estado.obter_breakpoints())
            if hasattr(self, '_regua_erros'):
                self._regua_erros.set_breakpoints(self.estado.obter_breakpoints())
            # Bookmarks
            self.area_numeros.set_bookmarks(self.estado.obter_bookmarks())
            # Folds — recria FoldRegions via recolher_bloco (usa QTextBlock real)
            self._fold_regions = []
            for bloco_num in self.estado.obter_folds():
                bloco = self.document().findBlockByNumber(bloco_num)
                if bloco.isValid():
                    self.recolher_bloco(bloco)
            self.area_numeros.update()
            # Cursor e scroll — restaura posição onde o usuário parou
            linha, col, scroll_y = self.estado.obter_posicao()
            bloco_alvo = self.document().findBlockByNumber(max(0, linha - 1))
            if bloco_alvo.isValid():
                pos = bloco_alvo.position() + min(col, max(0, bloco_alvo.length() - 1))
                cur = QTextCursor(self.document())
                cur.setPosition(pos)
                self.setTextCursor(cur)
            self.verticalScrollBar().setValue(scroll_y)
        except Exception as e:
            log.aviso("Editor.py", "_restaurar_estado_arquivo", "falha", str(e))

    # ⚠️  função grande (69 linhas)
    def contextMenuEvent(self, event):
        from _UTILITARIOS_.hein_context_menu import heinContextMenu
        cur     = self.textCursor()
        tem_sel = cur.hasSelection()
        doc     = self.document()

        itens = [
            # ── Execução ─────────────────────────────────────────────
            ("Executar Arquivo",      "mdi.play-circle-outline",     self._executar_via_mainwindow),
            ("Abrir Debugger",        "mdi.bug-outline",             self._abrir_debugger_via_mainwindow),
            None,

            # ── Histórico ────────────────────────────────────────────
            ("Desfazer",              "mdi.undo",                    self.undo),
            ("Refazer",               "mdi.redo",                    self.redo),
            None,
            # ── Área de transferência ────────────────────────────────
            ("Recortar",              "mdi.content-cut",             self.cut),
            ("Copiar",                "mdi.content-copy",            self.copy),
            ("Colar",                 "mdi.content-paste",           self.paste),
            ("Deletar",               "mdi.delete-outline",          cur.removeSelectedText),
            None,
            ("Selecionar Tudo",       "mdi.select-all",              self.selectAll),
            None,
            # ── Manipulação de linhas ────────────────────────────────
            ("Comentar / Descomentar","mdi.comment-outline",         self.comentar_linha),
            ("Duplicar Linha",        "mdi.content-duplicate",       self.duplicar_linha),
            ("Deletar Linha",         "mdi.minus-box-outline",       self.deletar_linha),
            ("Mover Linha Acima",     "mdi.arrow-up-bold-outline",   self.mover_linha_cima),
            ("Mover Linha Abaixo",    "mdi.arrow-down-bold-outline", self.mover_linha_baixo),
            None,
            # ── Busca ────────────────────────────────────────────────
            ("Buscar",                "mdi.magnify",                 self.abrir_busca),
            ("Buscar e Substituir",   "mdi.find-replace",            self.abrir_substituicao),
            None,
            # ── Corretor ortográfico ──────────────────────────────────
            ("Corretor ortográfico",  "mdi.spellcheck",
             lambda: self._corretor.verificar_pagina_inteira()
             if self._corretor else None),
            None,
            # ── Navegação ────────────────────────────────────────────
            ("Ir para Definição",     "mdi.arrow-right-circle-outline", self._ir_definicao.ir_para_definicao),
            ("Voltar Definição",      "mdi.arrow-left-circle-outline",  self._ir_definicao.voltar),
            None,
            # ── Dobramento ───────────────────────────────────────────
            ("Recolher Bloco",        "mdi.chevron-up",              self.recolher_bloco),
            ("Expandir Bloco",        "mdi.chevron-down",            self.expandir_bloco),
            None,

        ]

        # Removido a pedido do usuário: item "Instalar '{modulo}' via pip" no menu
        # de contexto (botão direito). Ficava sobreposto ao editor e travava a
        # seleção/cópia de texto na linha. A instalação via pip agora só acontece
        # pelo popup de hover (PopupQuickFix), que já cobre o mesmo caso de uso.
        cursor_pos   = self.cursorForPosition(event.pos())
        linha_num    = cursor_pos.block().blockNumber() + 1

        # IMP-04: "Adicionar import X" — aparece quando pyflakes detecta nome
        # indefinido E o modulo e importavel (stdlib ou instalado na venv da IDE).
        # Busca em ±3 linhas ao redor do clique: tolera clicar em linha vazia
        # proxima ao erro, o que e comum quando o tooltip aparece abaixo do codigo.
        import re as _re
        _msgs_err = getattr(self, '_mensagens_erros', {})
        _erros_l  = getattr(self, '_erros_lint', {})
        _nome_imp = None
        for _delta in range(4):           # testa 0, 1, 2, 3
            for _ln in ([linha_num] if _delta == 0
                        else [linha_num - _delta, linha_num + _delta]):
                _msg_raw = _msgs_err.get(_ln, "")
                _m_u = _re.search(r"'(\w+)' is not defined", _msg_raw)
                if _m_u and _erros_l.get(_ln) == "error":
                    _nome_imp = _m_u.group(1)
                    break
            if _nome_imp:
                break
        if _nome_imp and self._modulo_existe(_nome_imp):
            itens.append(None)
            itens.append((
                f"Adicionar 'import {_nome_imp}'",
                "mdi.import",
                lambda n=_nome_imp: self._inserir_import_modulo(n),
            ))

        menu = heinContextMenu(parent=self, itens=itens)

        # habilita/desabilita conforme estado
        menu.acao("Desfazer").setEnabled(doc.isUndoAvailable())
        menu.acao("Refazer").setEnabled(doc.isRedoAvailable())
        menu.acao("Recortar").setEnabled(tem_sel)
        menu.acao("Copiar").setEnabled(tem_sel)
        menu.acao("Deletar").setEnabled(tem_sel)

        menu.exec(event.globalPos())

    def _executar_via_mainwindow(self):
        """Sobe na hierarquia de widgets até encontrar a MainWindow e chama executar_codigo."""
        w = self.parent()
        while w is not None:
            if hasattr(w, "executar_codigo"):
                w.executar_codigo()

                return

            w = w.parent()

    def _abrir_debugger_via_mainwindow(self):
        """Sobe na hierarquia de widgets até encontrar a MainWindow e chama _iniciar_debug."""
        w = self.parent()
        while w is not None:
            if hasattr(w, "_iniciar_debug"):
                w._iniciar_debug()

                return

            w = w.parent()

    @staticmethod
    def _modulo_existe(nome: str) -> bool:
        import importlib.util
        try:

            return importlib.util.find_spec(nome) is not None

        except (ModuleNotFoundError, ValueError):

            return False

    def _inserir_import_modulo(self, modulo: str):
        """IMP-04: insere 'import <modulo>' apos os imports existentes no arquivo."""
        import re
        from PySide6.QtGui import QTextCursor
        doc    = self.document()
        linhas = doc.toPlainText().split("\n")

        # Nao duplicar se ja existe
        for l in linhas:
            if re.match(rf"^\s*import\s+{re.escape(modulo)}\b", l) or \
               re.match(rf"^\s*from\s+{re.escape(modulo)}\s+import", l):
                log.info("Editor.py", "_inserir_import_modulo",
                         f"import {modulo} ja existe — nada a fazer")
                return

        # Encontra ultima linha de import para inserir logo apos
        ultima_import = 0
        for i, l in enumerate(linhas):
            if re.match(r"^\s*(import\s|from\s+\w)", l):
                ultima_import = i + 1

        cursor = QTextCursor(doc)
        if ultima_import > 0:
            bloco = doc.findBlockByNumber(ultima_import)
            cursor.setPosition(bloco.position())
        else:
            cursor.movePosition(QTextCursor.Start)

        cursor.insertText(f"import {modulo}\n")
        log.ok("Editor.py", "_inserir_import_modulo", f"import {modulo} inserido")


