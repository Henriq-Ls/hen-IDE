# 📁 _EDITOR_/Outline/painel_outline.py
# -*- coding: utf-8 -*-
import ast
import gc
import json
import logging
import os
import re
import warnings
import weakref

log = logging.getLogger("hein")
from PySide6.QtCore    import Qt, Signal, QTimer, QThread, QRegularExpression, QEvent
from _THREADS_.thread_segura import _ThreadSegura
from PySide6.QtGui     import QColor, QTextCursor, QTextCharFormat, QTextDocument
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QSizePolicy, QLineEdit, QPushButton, QLabel, QCheckBox,
    QPlainTextEdit, QTextEdit, QTextBrowser, QFrame,
)
from _UTILITARIOS_.icones import icone_tema
from _TRADUTION_.tradutor_erros import traduzir
from _CONFIGURA_ import (
    OUTLINE_LARGURA_MIN, OUTLINE_LARGURA_MAX, OUTLINE_TIMER_MS,
    FONTE_OUTLINE, TAMANHO_FONTE_OUTLINE,
    COR_OUTLINE_CLASSE, COR_OUTLINE_FUNCAO, COR_OUTLINE_METODO,
    COR_OUTLINE_METODO_PRIV, COR_OUTLINE_ARQUIVO, COR_OUTLINE_PASTA,
    COR_OUTLINE_CHAVE_JSON, COR_OUTLINE_OBJETO_JSON,
    COR_OUTLINE_TAG_XML, COR_OUTLINE_ITEM,
    COR_SINTAXE_VARIAVEL_ESPECIAL,
    COR_BUSCA_NORMAL,FONTE_UI
)
from _CONFIGURA_.gerenciador_tema import tema_global
from _LOG_.log import log
from _THREADS_.ciclo_vida import encerrar_thread
from _THREADS_.diagnostico_workers import (
    active_tasks, bind, edit_generation, event, new_task, reference,
    start_requested, thread_finished, weak_editor,
)
from .worker_busca     import _WorkerBusca, _MODO_OUTLINE, _MODO_TAREFAS, _MODO_BUSCA, _MODO_ARQUIVO_NOME
from _CONFIGURA_.gerenciador_tema import tema_global
t   = tema_global()

_MODO_ARQUIVO_INLINE = "ARQUIVO_INLINE"
_MODO_SUBSTITUICAO   = "SUBSTITUICAO"
_MODO_LINHA          = "LINHA"
_MODO_CURSORES       = "CURSORES"   # IMP-15: multi-cursor ativo
from .delegate_outline import _DelegateOutline
from .item_outline     import ItemOutline
_ARQ = "painel_outline.py"

# Mantém referências a _ThreadOutlinePy até finished — evita GC prematuro
# quando PainelOutline é destruído antes de run() retornar (BUG-202807-12).
_threads_vivas_outline: set = set()

# ── Helpers e thread para parsing Python em background ────────────────────────

def _formatar_args_py(args) -> str:
    nomes = [a.arg for a in args.args]
    if args.vararg:  nomes.append(f"*{args.vararg.arg}")
    if args.kwarg:   nomes.append(f"**{args.kwarg.arg}")

    return ", ".join(nomes)

def _nome_call_py(node) -> str:
    func = node.func
    if isinstance(func, ast.Name):

        return func.id

    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name):

            return f"{func.value.id}.{func.attr}"

        return func.attr

    return ""

def _extrair_chamadas_py(no_func) -> list:
    chamadas, vistas = [], set()
    for sub in ast.walk(no_func):
        if sub is no_func:
            continue
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub is not no_func:
            continue
        if isinstance(sub, ast.Call):
            nome = _nome_call_py(sub)
            if nome and nome not in vistas:
                vistas.add(nome)
                chamadas.append({"texto": f"  └─ {nome}()", "linha": getattr(sub, "lineno", 0)})

    return chamadas

def _extrair_no_py(no, pai_tipo: str):
    if isinstance(no, (ast.Import, ast.ImportFrom)):
        # Retorna marcador para ser agrupado em "Imports" pelo chamador
        if isinstance(no, ast.ImportFrom):
            mod = no.module or ""
            nomes = ", ".join(a.name for a in no.names)
            texto = f"from {mod} import {nomes}"
        else:
            nomes = ", ".join(a.name for a in no.names)
            texto = f"import {nomes}"

        return {"tipo": "import", "texto": texto, "linha": no.lineno,

                "filhos": [], "chamadas": []}
    if isinstance(no, ast.ClassDef):
        filhos = []
        for f in ast.iter_child_nodes(no):
            d = _extrair_no_py(f, "classe")
            if d:
                filhos.append(d)

        return {"tipo": "classe", "texto": f"class {no.name}", "linha": no.lineno,

                "filhos": filhos, "chamadas": []}
    if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
        prefix = "async def " if isinstance(no, ast.AsyncFunctionDef) else "def "
        tipo   = "metodo" if pai_tipo == "classe" else "funcao"
        if tipo == "metodo" and no.name.startswith("_"):
            tipo = "metodo_priv"

        return {"tipo": tipo,

                "texto": f"{prefix}{no.name}({_formatar_args_py(no.args)})",
                "linha": no.lineno, "filhos": [],
                "chamadas": _extrair_chamadas_py(no)}

    return None

class _ThreadOutlinePy(_ThreadSegura):
    """Roda ast.parse() em background para não bloquear a UI."""
    concluido = Signal(list, str)   # (nos: list[dict], erro_msg: str)

    def __init__(self, codigo: str, caminho: str, task: str = "",
                 editor=None, edit_generation: int = 0):
        super().__init__()
        self._codigo  = codigo
        self._caminho = caminho
        self._hein_diag_task = task
        self._hein_diag_component = "OUTLINE"
        self._hein_diag_editor = weak_editor(editor)
        self._hein_diag_edit_generation = edit_generation

    def run(self):
        event("RUN_ENTER", "OUTLINE", self._hein_diag_task, obj=self,
              editor=self._hein_diag_editor)
        try:
            gc.disable()
            try:
                arvore = ast.parse(self._codigo, filename=self._caminho or "<editor>")
            finally:
                gc.enable()
        except SyntaxError as e:
            self.concluido.emit([], f"linha {e.lineno}: {e.msg}")
            event("RESULT_EMITTED", "OUTLINE", self._hein_diag_task, obj=self,
                  editor=self._hein_diag_editor, result_count=0, syntax_error=True)
            event("RUN_EXIT", "OUTLINE", self._hein_diag_task, obj=self,
                  editor=self._hein_diag_editor)

            return

        nos = []
        imports = []
        for n in ast.iter_child_nodes(arvore):
            d = _extrair_no_py(n, "")
            if d:
                if d["tipo"] == "import":
                    imports.append(d)
                else:
                    nos.append(d)
        # Agrupa imports como nó pai colapsado (apenas se existirem)
        if imports:
            grupo = {"tipo": "import_grupo", "texto": f"imports  ({len(imports)})",
                     "linha": imports[0]["linha"], "filhos": imports, "chamadas": []}
            nos.insert(0, grupo)
        self.concluido.emit(nos, "")
        event("RESULT_EMITTED", "OUTLINE", self._hein_diag_task, obj=self,
              editor=self._hein_diag_editor, result_count=len(nos))
        event("RUN_EXIT", "OUTLINE", self._hein_diag_task, obj=self,
              editor=self._hein_diag_editor)

class PainelOutline(QWidget):
    navegar_solicitado = Signal(str, int)
    navegar_para_linha = Signal(int)

# NOVO: Signals pra statusbar
    status_posicao_mudou = Signal(int, int, int)  # linha, coluna, total_linhas
    status_erros_mudaram = Signal(int, int)       # qtd_erros, qtd_avisos

    def __init__(self, parent=None, tema: dict = None):
        super().__init__(parent)
        self.setObjectName("PainelOutline")
        self.setMinimumWidth(OUTLINE_LARGURA_MIN)
        self.setMaximumWidth(OUTLINE_LARGURA_MAX)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._editor_atual   = None
        self._extensao_atual = ".py"
        self._tema           = tema or {}
        self._projeto_path   = ""
        self._modo_painel    = _MODO_OUTLINE

        self._thread_busca  : QThread | None = None
        self._worker_busca  : _WorkerBusca | None = None
        self._thread_outline: _ThreadOutlinePy | None = None
        self._hash_outline  : int = 0
        self._nos_cache     : list | None = None  # última lista de nós do python_ast
        self._busca_pais    : dict = {}  # caminho→ItemOutline (modo BUSCA)
        # Slot guardado para poder desconectar erros_atualizados — lambdas são
        # objetos distintos a cada criação, então disconnect(lambda) nunca bate;
        # guardar a referência permite o disconnect correto em conectar_editor.
        self._slot_erros_atualizados = None

        # ── busca inline (Ctrl+F / Ctrl+H) ───────────────────────────
        self._resultados_inline : list = []
        self._idx_inline        : int  = -1
        self._destaques_inline  : list = []

        # IMP-03: atualiza contador da busca inline quando o editor é editado
        self._timer_rebuscar_inline = QTimer(self)
        self._timer_rebuscar_inline.setSingleShot(True)
        self._timer_rebuscar_inline.setInterval(300)
        self._timer_rebuscar_inline.timeout.connect(self._rebuscar_inline_sem_args)
        self._modo_inline       : str  = ""
        self._n_linha_destino   : int  = 0

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(OUTLINE_TIMER_MS)
        self._timer.timeout.connect(self._atualizar)

        self._timer_busca = QTimer(self)
        self._timer_busca.setSingleShot(True)
        self._timer_busca.setInterval(400)
        self._timer_busca.timeout.connect(self._executar_busca)

        # Timer para sincronizar cursor do editor com o outline
        self._timer_cursor = QTimer(self)
        self._timer_cursor.setSingleShot(True)
        self._timer_cursor.setInterval(200)
        self._timer_cursor.timeout.connect(self._sincronizar_cursor)

        self._construir_ui()
        self._aplicar_tema()

    # ──────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────

    # ⚠️  função grande (56 linhas)
    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # campos ocultos — controlados pela BarraCentral
        self._input_busca = QLineEdit()
        self._input_busca.textChanged.connect(self._ao_digitar_busca)
        self._input_busca.hide()

        # barra de modo contextual (busca inline / substituição / linha)
        self._construir_barra_modo()
        layout.addWidget(self._barra_modo)

        self._btn_outline = QPushButton()
        self._btn_outline.setCheckable(True)
        self._btn_outline.setChecked(True)
        self._btn_outline.clicked.connect(lambda: self._alternar_modo(_MODO_OUTLINE))

        self._btn_tarefas = QPushButton()
        self._btn_tarefas.setCheckable(True)
        self._btn_tarefas.setChecked(False)
        self._btn_tarefas.clicked.connect(lambda: self._alternar_modo(_MODO_TAREFAS))

        # barra de formatação — só visível quando provider.tem_barra_formatacao
        # (hoje: Hein/.hein). Botões inserem marcação na linha do cursor.
        self._construir_barra_formatacao()
        # barra_formatacao e arvore ficam num container horizontal
        self._area_central = QWidget()
        self._area_central.setObjectName("AreaCentralOutline")
        lay_central = QHBoxLayout(self._area_central)
        lay_central.setContentsMargins(0, 0, 0, 0)
        lay_central.setSpacing(0)

        self._arvore = QTreeWidget()
        self._arvore.setHeaderHidden(True)
        self._arvore.setIndentation(14)
        self._arvore.setAnimated(True)
        self._arvore.setItemDelegate(
            _DelegateOutline(self._arvore, fold_state_fn=self._fold_estado)
        )
        self._arvore.viewport().installEventFilter(self)   # 8.1 — clique no ícone
        self._arvore.itemClicked.connect(self._ao_clicar_item)

        self._label_status = QLabel("")          # ← adiciona essa linha
        self._label_status.setObjectName("OutlineLabelStatus")
        self._label_status.setAlignment(Qt.AlignCenter)
        self._label_status.hide()

        # area_conteudo: arvore + status + preview empilhados verticalmente
        self._area_conteudo = QWidget()
        lay_cont = QVBoxLayout(self._area_conteudo)
        lay_cont.setContentsMargins(0, 0, 0, 0)
        lay_cont.setSpacing(0)
        lay_cont.addWidget(self._arvore)
        lay_cont.addWidget(self._label_status)

        self._preview = QTextBrowser()
        self._preview.setOpenExternalLinks(False)
        self._preview.setObjectName("OutlinePreview")
        self._preview.hide()
        lay_cont.addWidget(self._preview)

        lay_central.addWidget(self._area_conteudo, 1)
        lay_central.addWidget(self._barra_formatacao)
        layout.addWidget(self._area_central, 1)

        # ── Barra inferior — instância de BarraOutline (barra_status.py) ────────────
        self.barra_layout = self._construir_barra_atalhos()
        layout.addWidget(self.barra_layout)
        # ──────────────────────────────────────────────────────────────

        # aplica estilos iniciais da barra de modo
        self._aplicar_tema_barra_modo()


    def _construir_barra_formatacao(self):
        """
        Barra de botões de formatação — exclusiva do editor Hein (.hein).
        Cada botão insere a marcação correspondente na linha do cursor
        (ou envolve a seleção, no caso de negrito/link).
        """
        self._barra_formatacao = QWidget()
        self._barra_formatacao.setObjectName("BarraFormatacaoHein")
        self._barra_formatacao.setFixedWidth(68)
        lay = QVBoxLayout(self._barra_formatacao)
        lay.setContentsMargins(3, 4, 3, 4)
        lay.setSpacing(2)

        t        = tema_global()
        fundo    = t.cor("editor.fundo",             "#1e1e2e")
        borda    = t.cor("editor.guia_quebra_linha", "#3a3a4a")
        texto    = t.cor("editor.texto",             "#d0d0d0")
        destaque = t.cor("editor.sintaxe.funcao",    "#61afef")

        def _btn(rotulo, acao):
            b = QPushButton(rotulo)
            b.setObjectName("BtnFormatacaoHein")
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(22)
            b.clicked.connect(lambda _=False, a=acao: self._aplicar_formatacao_hein(a))
            return b

        # ── Tamanho de fonte: input numérico ───────────────────────────
        self._input_tam_fonte = QLineEdit("12")
        self._input_tam_fonte.setObjectName("InputTamFonteHein")
        self._input_tam_fonte.setFixedHeight(22)
        self._input_tam_fonte.setAlignment(Qt.AlignCenter)
        self._input_tam_fonte.setMaxLength(2)
        self._input_tam_fonte.setToolTip("Tamanho da fonte — pressione Enter")
        self._input_tam_fonte.returnPressed.connect(self._aplicar_tam_fonte_input)
        lay.addWidget(self._input_tam_fonte)

        # ── Família de fonte ─────────────────────────────────────────────
        lay.addWidget(_btn("Fonte", "fonte"))

        # ── Separador ────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setMaximumHeight(1)
        sep.setStyleSheet(f"background:{borda};border:none;margin:2px 0;")
        lay.addWidget(sep)

        # ── Botões de marcação ───────────────────────────────────────────
        for rotulo, acao in [
            ("# Título",  "titulo"),
            ("## Sub",    "subtitulo"),
            ("### Tóp",   "topico"),
            ("- Lista",   "lista"),
            ("[ ] Tar",   "checklist"),
            ("🎨 Cor",    "destaque_cor"),
            ("**Neg**",   "negrito"),
            ("[[Link]]",  "link"),
            ("{Ocult}",   "comentario_oculto"),
            ("`·· Cód",   "bloco_codigo"),
            ("→ .md",     "exportar_md"),
        ]:
            lay.addWidget(_btn(rotulo, acao))
        lay.addStretch(1)

        self._barra_formatacao.setStyleSheet(f"""
            #BarraFormatacaoHein {{
                background-color: {fundo};
                border-left: 1px solid {borda};
            }}
            #BtnFormatacaoHein {{
                background-color: transparent;
                color: {texto};
                border: 1px solid {borda};
                border-radius: 3px;
                padding: 1px 3px;
                font-size: 10px;
            }}
            #BtnFormatacaoHein:hover {{
                background-color: {borda};
                color: {destaque};
            }}
            #InputTamFonteHein {{
                background-color: {fundo};
                color: {texto};
                border: 1px solid {borda};
                border-radius: 3px;
                font-size: 10px;
                padding: 0;
            }}
        """)

        self._barra_formatacao.hide()

    def _aplicar_formatacao_hein(self, acao: str):
        """Insere/alterna a marcação .hein na linha atual (ou seleção) do editor conectado."""
        editor = self._editor_atual
        if not editor:
            return

        # ── Exportar → não mexe no cursor ───────────────────────────────
        if acao == "exportar_md":
            self._exportar_hein_para_md()
            return

        cursor = editor.textCursor()

        # ── Ações que envolvem a seleção ou a palavra sob o cursor ───────
        if acao in ("negrito", "link", "comentario_oculto"):
            if not cursor.hasSelection():
                cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            texto = cursor.selectedText()
            if acao == "negrito":
                cursor.insertText(f"**{texto}**" if texto else "****")
            elif acao == "link":
                cursor.insertText(f"[[{texto}]]" if texto else "[[]]")
            else:  # comentario_oculto
                cursor.insertText(f"{{{texto}}}" if texto else "{}")
            editor.setTextCursor(cursor)
            editor.setFocus()
            return

        # ── Bloco de código — toggle ``` na linha atual ──────────────────
        if acao == "bloco_codigo":
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine,
                                QTextCursor.MoveMode.KeepAnchor)
            linha = cursor.selectedText()
            if linha.strip().startswith("```"):
                # Remove o marcador ``` existente
                cursor.insertText(linha.lstrip("`").lstrip())
            else:
                # Insere ``` no início da linha + fecha automaticamente
                cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
                editor.setTextCursor(cursor)
                cursor.insertText("```\n" + linha + "\n```\n")
            editor.setFocus()
            return

        # ── Família de fonte ──────────────────────────────────────────────
        if acao == "fonte":
            from PySide6.QtWidgets import QFontDialog
            ok, nova = QFontDialog.getFont(editor.font(), editor, "Escolher fonte")
            if ok:
                editor.setFont(nova)
                from PySide6.QtGui import QSyntaxHighlighter
                for child in editor.document().children():
                    if isinstance(child, QSyntaxHighlighter) and hasattr(child, "set_zoom"):
                        child.set_zoom(nova.pointSize())
                        break
            editor.setFocus()
            return

        # ── Cor de destaque livre (paleta de cores) ───────────────────────
        if acao == "destaque_cor":
            from PySide6.QtWidgets import QColorDialog
            cor = QColorDialog.getColor(QColor("#e5c07b"), editor, "Cor do destaque")
            if cor.isValid():
                cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
                editor.setTextCursor(cursor)
                cursor.insertText(f"!!{cor.name()} ")
            editor.setFocus()
            return

        # ── Ações que prefixam a linha inteira ───────────────────────────
        prefixos = {
            "titulo":     "# ",
            "subtitulo":  "## ",
            "topico":     "### ",
            "lista":      "- ",
            "checklist":  "[ ] ",
            "destaque":   "!! ",
        }
        prefixo = prefixos.get(acao)
        if not prefixo:
            return

        if cursor.hasSelection():
            # Aplica o prefixo em cada linha da seleção
            sel_start = cursor.selectionStart()
            sel_end   = cursor.selectionEnd()
            c = QTextCursor(editor.document())
            c.setPosition(sel_start)
            c.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            blocos = []
            bloco = c.block()
            while bloco.isValid() and bloco.position() <= sel_end:
                blocos.append(bloco.position())
                bloco = bloco.next()
            # Inserir de trás pra frente para não invalidar posições anteriores
            c.beginEditBlock()
            for pos in reversed(blocos):
                c.setPosition(pos)
                c.insertText(prefixo)
            c.endEditBlock()
        else:
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            editor.setTextCursor(cursor)
            cursor.insertText(prefixo)
        editor.setFocus()

    def _aplicar_tam_fonte_input(self):
        """Lê o valor do QLineEdit e aplica como pointSize no editor atual."""
        editor = self._editor_atual
        if not editor:
            return
        try:
            tam = int(self._input_tam_fonte.text().strip())
            tam = max(6, min(60, tam))
        except ValueError:
            return
        fonte = editor.font()
        fonte.setPointSize(tam)
        editor.setFont(fonte)
        from PySide6.QtGui import QSyntaxHighlighter
        for child in editor.document().children():
            if isinstance(child, QSyntaxHighlighter) and hasattr(child, "set_zoom"):
                child.set_zoom(tam)
                break
        self._input_tam_fonte.setText(str(tam))
        editor.setFocus()

    def _exportar_hein_para_md(self):
        """Converte o arquivo .hein aberto para Markdown (.md) e o abre na IDE."""
        editor = self._editor_atual
        if not editor:
            return
        fp = getattr(editor, 'file_path', None)
        if not fp or not fp.lower().endswith('.hein'):
            return

        texto   = editor.toPlainText()
        linhas  = texto.split('\n')
        saida   = []
        dentro_codigo = False

        for linha in linhas:
            strip = linha.strip()
            # Bloco de código — passa sem alteração
            if strip.startswith('```'):
                dentro_codigo = not dentro_codigo
                saida.append(linha)
                continue
            if dentro_codigo:
                saida.append(linha)
                continue
            # Destaques coloridos → callout Markdown
            if strip.startswith('!!r '):
                saida.append('> 🔴 ' + linha[linha.index('!!r ') + 4:])
            elif strip.startswith('!!g '):
                saida.append('> 🟢 ' + linha[linha.index('!!g ') + 4:])
            elif strip.startswith('!!b '):
                saida.append('> 🔵 ' + linha[linha.index('!!b ') + 4:])
            elif strip.startswith('!! '):
                saida.append('> ⭐ ' + linha[linha.index('!! ') + 3:])
            else:
                # Remove comentários ocultos {texto}
                l = re.sub(r'\{[^}]*\}', '', linha)
                # [[link]] → [link](link.hein)
                l = re.sub(r'\[\[([^\]]+)\]\]',
                           lambda m: f'[{m.group(1)}]({m.group(1)}.hein)', l)
                saida.append(l)

        conteudo_md  = '\n'.join(saida)
        caminho_md   = os.path.splitext(fp)[0] + '.md'
        try:
            with open(caminho_md, 'w', encoding='utf-8') as f:
                f.write(conteudo_md)
            # Abre o .md gerado na IDE
            janela = editor.window() if editor else None
            if janela:
                for nome in ('abrir_arquivo', 'abrir_tab_arquivo', 'abrir_em_nova_aba'):
                    metodo = getattr(janela, nome, None)
                    if callable(metodo):
                        metodo(caminho_md)
                        break
        except Exception as exc:
            log.warning("PainelOutline", "_exportar_hein_para_md", str(exc))

    def _emitir_status_do_editor(self):
        """Chama quando o cursor mexe ou o texto muda"""
        if not self._editor_atual:
            return

        cursor = self._editor_atual.textCursor()
        linha = cursor.blockNumber() + 1
        coluna = cursor.columnNumber() + 1
        total = self._editor_atual.document().blockCount()

        self.status_posicao_mudou.emit(linha, coluna, total)

    # ──────────────────────────────────────────────────────────────
    # Alternância de modo
    # ──────────────────────────────────────────────────────────────

    def _alternar_modo(self, modo: str):
        self._modo_painel = modo
        self._btn_outline.setChecked(modo == _MODO_OUTLINE)
        self._btn_tarefas.setChecked(modo == _MODO_TAREFAS)

        if modo == _MODO_TAREFAS:
            self._input_busca.setText("LEMBRAR:")
            # _ao_digitar_busca dispara automaticamente via textChanged
        else:
            termo = self._input_busca.text().strip()
            if termo:
                self._executar_busca()
            else:
                self._atualizar()

    # ──────────────────────────────────────────────────────────────
    # Busca global
    # ──────────────────────────────────────────────────────────────

    def _ao_digitar_busca(self, texto: str):
        self._timer_busca.start()

    def _executar_busca(self):
        termo = self._input_busca.text().strip()
        log.info(_ARQ, "_executar_busca", f"termo='{termo}' projeto='{self._projeto_path}' modo={self._modo_painel}")

        if not termo:
            self._label_status.hide()
            self._atualizar()

            return

        if not self._projeto_path:
            log.aviso(_ARQ, "_executar_busca", "projeto_path vazio — busca abortada")
            self._label_status.setText("⚠ Nenhum projeto aberto.")
            self._label_status.show()

            return

        self._cancelar_busca()
        self._arvore.clear()
        self._label_status.setText("🔍 Buscando...")
        self._label_status.show()

        _editor = self._editor_atual
        _edit = edit_generation(_editor)
        _task = new_task("OUTLINEBUSCA", _editor, _edit)
        self._worker_busca = _WorkerBusca(
            self._projeto_path, termo, self._modo_painel,
            _task, _editor, _edit,
        )
        self._thread_busca = QThread()   # sem parent — controlamos ciclo de vida manualmente
        bind(self._worker_busca, "OUTLINEBUSCA", _task, _editor, _edit)
        bind(self._thread_busca, "OUTLINEBUSCA", _task, _editor, _edit)
        self._worker_busca.moveToThread(self._thread_busca)
        self._thread_busca.started.connect(self._worker_busca.executar)
        self._worker_busca.resultado.connect(self._ao_receber_resultado)
        self._worker_busca.concluido.connect(self._ao_busca_concluida)
        # Padrão correto moveToThread: thread libera o worker (QObject separado)
        # via deleteLater quando termina. NÃO conectar thread.finished → thread.deleteLater
        # (BUG-202807-07): causa race entre deleteLater e OS thread cleanup → qFatal.
        self._thread_busca.finished.connect(self._worker_busca.deleteLater)
        self._thread_busca.finished.connect(
            lambda t_ref=weakref.ref(self._thread_busca):
            thread_finished(t_ref())
        )
        log.info(_ARQ, "_executar_busca", f"thread iniciada task={_task}")
        start_requested(self._thread_busca, "OUTLINEBUSCA", _task)
        self._thread_busca.start()

    def _ao_busca_concluida(self):
        _thread = self._thread_busca
        _worker = self._worker_busca
        _task = getattr(_thread, "_hein_diag_task", "") if _thread else ""
        log.info(_ARQ, "_ao_busca_concluida", "worker concluiu — encerrando thread")
        thread = self._thread_busca
        reference("ZERO", "OUTLINEBUSCA", self, "_thread_busca",
                  before=thread, after=None, editor=self._editor_atual, task=_task)
        self._thread_busca = None   # zera ANTES de chamar quit/wait — evita RuntimeError
        reference("ZERO", "OUTLINEBUSCA", self, "_worker_busca",
                  before=self._worker_busca, after=None,
                  editor=self._editor_atual, task=_task)
        self._worker_busca = None
        if thread is not None:
            encerrar_thread(thread, 1000)

    def _cancelar_busca(self):
        log.info(_ARQ, "_cancelar_busca", "cancelando busca anterior se existir")
        worker = self._worker_busca
        thread = self._thread_busca
        task = getattr(thread, "_hein_diag_task", "") if thread else getattr(worker, "_hein_diag_task", "")
        event("CANCEL_REQUESTED", "OUTLINEBUSCA", task, obj=worker,
              editor=self._editor_atual)
        # zera refs ANTES de qualquer operação — evita acesso a objeto deletado
        reference("ZERO", "OUTLINEBUSCA", self, "_worker_busca",
                  before=worker, after=None, editor=self._editor_atual, task=task)
        self._worker_busca = None
        reference("ZERO", "OUTLINEBUSCA", self, "_thread_busca",
                  before=thread, after=None, editor=self._editor_atual, task=task)
        self._thread_busca = None

        if worker is not None:
            try:
                worker.parar()
            except Exception as e:
                log.aviso(_ARQ, "_cancelar_busca", f"erro ao parar worker: {e}")

        if thread is not None:
            encerrar_thread(thread, 500)

    def _ao_receber_resultado(self, resultados: list):
        log.info(_ARQ, "_ao_receber_resultado", f"{len(resultados)} ocorrência(s)")
        self._arvore.clear()

        if not resultados:
            self._label_status.setText("Nenhum resultado encontrado.")
            self._label_status.show()

            return

        self._label_status.hide()

        t = tema_global()
        c_arquivo = t.cor("painel_outline.cor_arquivo", COR_OUTLINE_ARQUIVO)
        c_linha   = t.cor("editor.sintaxe.string",      COR_OUTLINE_CHAVE_JSON)

        por_arquivo: dict[str, list] = {}
        for caminho_rel, caminho_abs, num_linha, texto_linha in resultados:
            por_arquivo.setdefault(caminho_rel, []).append((caminho_abs, num_linha, texto_linha))

        for caminho_rel, ocorrencias in por_arquivo.items():
            nome_arq = os.path.basename(caminho_rel)
            pai = ItemOutline(f"{nome_arq}  ({len(ocorrencias)})", "", 0, "arquivo")
            pai.setForeground(0, QColor(c_arquivo))
            pai.setToolTip(0, caminho_rel)

            for caminho_abs, num_linha, texto_linha in ocorrencias:
                texto_item = f"{num_linha}:  {texto_linha.strip()}"
                filho = ItemOutline(texto_item, caminho_abs, num_linha, "item", pai)
                filho.setForeground(0, QColor(c_linha))

            pai.setExpanded(True)
            self._arvore.addTopLevelItem(pai)

        log.ok(_ARQ, "_ao_receber_resultado", f"{len(por_arquivo)} arquivo(s) com resultados")

    # ──────────────────────────────────────────────────────────────
    # Tema
    # ──────────────────────────────────────────────────────────────

    def _c(self, chave_propria: str, chave_fallback: str, default: str) -> str:
        t = tema_global()
        v = t.cor(f"painel_outline.{chave_propria}", "")
        if v:

            return v

        return t.cor(chave_fallback, default)

    # ⚠️  função grande (52 linhas)
    def _aplicar_tema(self):
        fundo       = self._c("fundo",            "editor.fundo",             "#080808")
        texto       = self._c("texto",            "editor.texto",             "#c0c0c0")
        hover       = self._c("item_hover",       "editor.linha_ativa_fundo", "#1a1a2e")
        selecionado = self._c("item_selecionado", "editor.selecao",           "#264f78")
        borda       = self._c("borda",            "interface.borda",          "#222222")
        texto_fraco = self._c("texto_fraco",      "interface.texto_fraco",    "#888888")

        t = tema_global()
        btn_ativo   = t.cor("interface.borda_foco",       "#4a90d9")
        btn_inativo = t.cor("interface.fundo_item_hover", "#1a1a2e")
        btn_texto   = t.cor("interface.texto",            "#e0e0e0")
        input_fundo = t.cor("interface.fundo_item_hover", "#1a1a2e")
        input_borda = t.cor("interface.borda",            "#333333")

        try:
            from _CONFIGURA_.gerenciador_configurar import config_global
            _fonte = config_global().obter("outline", "fonte",          FONTE_OUTLINE)
            _pt    = int(config_global().obter("outline", "tamanho_fonte", TAMANHO_FONTE_OUTLINE))
        except Exception:
            _fonte = FONTE_OUTLINE
            _pt    = TAMANHO_FONTE_OUTLINE

        self._arvore.setStyleSheet(f"""
                    QTreeWidget {{
                        background: {fundo};
                        color: {texto};
                        border: none;
                        font-family: '{_fonte}';
                        font-size: {_pt}pt;
                    }}
                    QTreeWidget::item          {{ padding: 2px 4px; }}
                    QTreeWidget::item:hover    {{ background: {hover}; }}
                    QTreeWidget::item:selected {{ background: {selecionado}; color: #ffffff; }}
                """)
        self._label_status.setStyleSheet(f"""
            QLabel#OutlineLabelStatus {{
                color: {texto_fraco};
                font-family: '{_fonte}';
                font-size: {_pt}pt;
                padding: 8px;
            }}
        """)
        self.setStyleSheet(f"background: {fundo};")
        self._preview.setStyleSheet(
            f"QTextBrowser#OutlinePreview {{"
            f"  background: {fundo}; color: {texto}; border: none;"
            f"  font-family: '{_fonte}'; font-size: {_pt}pt;"
            f"  padding: 6px 8px;"
            f"}}"
        )
        self._aplicar_tema_popup_atalhos()

    def atualizar_tema(self, tema: dict = None):
        if tema is not None:
            self._tema = tema
        self._aplicar_tema()  # já chama _aplicar_tema_popup_atalhos() internamente
        self._atualizar()

    # ──────────────────────────────────────────────────────────────
    # Cores dos símbolos
    # ──────────────────────────────────────────────────────────────

    def _cor_tipo(self, tipo: str) -> QColor:
        t = tema_global()
        mapa = {
            "classe":      ("painel_outline.cor_classe",         "editor.sintaxe.palavra_chave",     COR_OUTLINE_CLASSE),
            "funcao":      ("painel_outline.cor_funcao",         "editor.sintaxe.funcao",            COR_OUTLINE_FUNCAO),
            "metodo":      ("painel_outline.cor_metodo",         "editor.sintaxe.funcao",            COR_OUTLINE_METODO),
            "metodo_priv": ("painel_outline.cor_metodo_privado", "editor.sintaxe.variavel_especial", COR_OUTLINE_METODO_PRIV),
            "arquivo":     ("painel_outline.cor_arquivo",        "editor.texto",                     COR_OUTLINE_ARQUIVO),
            "pasta":       ("painel_outline.cor_pasta",          "interface.texto_fraco",            COR_OUTLINE_PASTA),
            "chave":       ("painel_outline.cor_chave_json",     "editor.sintaxe.string",            COR_OUTLINE_CHAVE_JSON),
            "objeto":      ("painel_outline.cor_objeto_json",    "editor.sintaxe.numero",            COR_OUTLINE_OBJETO_JSON),
            "tag":         ("painel_outline.cor_tag_xml",        "editor.sintaxe.palavra_chave",     COR_OUTLINE_TAG_XML),
            "item":        ("painel_outline.cor_item",           "editor.sintaxe.pontuacao",         COR_OUTLINE_ITEM),
            "import":      ("painel_outline.cor_import",         "editor.sintaxe.palavra_chave",     COR_OUTLINE_ITEM),
            "import_grupo":("painel_outline.cor_import",         "interface.texto_fraco",            "#888888"),
            "titulo":      ("painel_outline.cor_titulo_hein",    "editor.sintaxe.funcao",            COR_OUTLINE_FUNCAO),
            "subtitulo":   ("painel_outline.cor_subtitulo_hein", "editor.sintaxe.chave_json",         COR_OUTLINE_CHAVE_JSON),
        }
        chave_tema, chave_fallback, hardcoded = mapa.get(
            tipo, ("painel_outline.cor_item", "editor.sintaxe.pontuacao", COR_OUTLINE_ITEM)
        )
        v = t.cor(chave_tema, "")
        if v:

            return QColor(v)

        v = t.cor(chave_fallback, "")
        if v:

            return QColor(v)

        return QColor(hardcoded)

    # ──────────────────────────────────────────────────────────────
    # API pública
    # ──────────────────────────────────────────────────────────────

    def conectar_editor(self, editor):
        if self._editor_atual:
            try:
                self._editor_atual.textChanged.disconnect(self._agendar_atualizacao)
            except RuntimeError:
                pass
            try:
                self._editor_atual.cursorPositionChanged.disconnect(self._timer_cursor.start)
            except RuntimeError:
                pass
            # BUG-23-07: contentsChanged nunca era desconectado — cada chamada a
            # conectar_editor acumulava uma conexão extra, fazendo o timer disparar
            # N vezes por evento e triggering N repopulações do outline.
            try:
                self._editor_atual.document().contentsChanged.disconnect(
                    self._timer_rebuscar_inline.start
                )
            except RuntimeError:
                pass
            # BUG-23-07b: erros_atualizados era conectado com lambda anônima que
            # nunca podia ser desconectada (cada lambda é um objeto diferente).
            # Guardamos a referência em _slot_erros_atualizados para poder
            # desconectar corretamente antes de reconectar ao novo editor.
            if self._slot_erros_atualizados is not None:
                try:
                    self._editor_atual.erros_atualizados.disconnect(
                        self._slot_erros_atualizados
                    )
                except (RuntimeError, AttributeError):
                    pass
                self._slot_erros_atualizados = None
        self._editor_atual = editor
        if editor and getattr(editor, "file_path", None):
            self._extensao_atual = os.path.splitext(editor.file_path)[1].lower()
        else:
            self._extensao_atual = ".py"
        if editor:
            # Sincronizar input de tamanho com a fonte atual do editor
            if hasattr(self, '_input_tam_fonte'):
                pt = editor.font().pointSize()
                self._input_tam_fonte.setText(str(pt if pt > 0 else 12))
            editor.textChanged.connect(self._agendar_atualizacao)
            editor.cursorPositionChanged.connect(self._timer_cursor.start)
            editor.document().contentsChanged.connect(self._timer_rebuscar_inline.start)
            if hasattr(editor, 'erros_atualizados'):
                self._slot_erros_atualizados = lambda _: self._atualizar_barra_outline()
                editor.erros_atualizados.connect(self._slot_erros_atualizados)
            self._timer.start(200)
            self._atualizar_barra_outline()
        else:
            if self._modo_painel != _MODO_BUSCA:
                self._arvore.clear()

    def _sincronizar_cursor(self):
        """Seleciona no outline o item mais próximo do cursor no editor."""
        if (not self._editor_atual
                or self._input_busca.text().strip()
                or self._modo_painel != _MODO_OUTLINE
                or self._extensao_atual in (".md", ".markdown", ".html", ".htm")):

            return

        linha_cursor = self._editor_atual.textCursor().blockNumber() + 1

        def _coletar(item, lista):
            for i in range(item.childCount()):
                filho = item.child(i)
                if hasattr(filho, 'linha') and filho.linha > 0:
                    lista.append(filho)
                _coletar(filho, lista)

        todos = []
        for i in range(self._arvore.topLevelItemCount()):
            raiz = self._arvore.topLevelItem(i)
            if hasattr(raiz, 'linha') and raiz.linha > 0:
                todos.append(raiz)
            _coletar(raiz, todos)

        if not todos:

            return

        # Item com maior linha <= cursor
        melhor = None
        for item in todos:
            if item.linha <= linha_cursor:
                if melhor is None or item.linha > melhor.linha:
                    melhor = item

        if melhor is None or self._arvore.currentItem() is melhor:

            return

        self._arvore.blockSignals(True)
        self._arvore.setCurrentItem(melhor)
        self._arvore.scrollToItem(melhor)
        self._arvore.blockSignals(False)
        self._atualizar_barra_outline(melhor)

    def _nome_item_outline(self, item) -> str:
        """Extrai o nome limpo de um ItemOutline (sem prefixo def/class)."""
        if item is None:
            return ""
        t = item.text(0).split("(")[0].strip()
        for p in ("async def ", "def ", "class ", "@"):
            if t.startswith(p):
                t = t[len(p):].strip()
                break
        return t

    def _atualizar_barra_outline(self, item=None):
        """Atualiza os contadores de erros/avisos na barra inferior do outline."""
        if not hasattr(self, "_lbl_ol_erros"):
            return

        from _EDITOR_.Mult_Linguas import get_provider
        provider = get_provider(self._extensao_atual)

        # ── contadores de erros/avisos ──────────────────────────────────
        self._lbl_ol_erros.setVisible(provider.mostrar_erros)
        self._lbl_ol_avisos.setVisible(
            provider.mostrar_erros and provider.rotulo_erros == 'Erros'
        )
        if not provider.mostrar_erros:
            return

        e = self._editor_atual
        if e is None:
            return

        if provider.rotulo_erros == 'Erros':
            erros_lint    = getattr(e, "_erros_lint",   {})
            erros_imports = getattr(e, "_erros_imports", {})
            n_erros  = sum(1 for v in erros_lint.values()    if v == "error")   \
                     + sum(1 for v in erros_imports.values() if v == "error")
            n_avisos = sum(1 for v in erros_lint.values()    if v == "warning") \
                     + sum(1 for v in erros_imports.values() if v == "warning")

            self._lbl_ol_erros.setText(f"\u2297 {n_erros}")
            self._lbl_ol_erros.setStyleSheet(
                f"color: {'#f48771' if n_erros > 0 else '#89d185'}; border: none; padding: 0 5px;"
            )
            self._lbl_ol_avisos.setText(f"\u25b3 {n_avisos}")
            self._lbl_ol_avisos.setStyleSheet(
                f"color: {'#e5c07b' if n_avisos > 0 else '#89d185'}; border: none; padding: 0 5px;"
            )
        else:
            # JSON / YAML: Válido ou Inválido (não tem distinção erro/aviso)
            ok = getattr(provider, '_ultimo_parse_ok', True)
            self._lbl_ol_erros.setText("Válido" if ok else "Inválido")
            self._lbl_ol_erros.setStyleSheet(
                f"color: {'#89d185' if ok else '#f48771'}; border: none; padding: 0 5px;"
            )

    def set_editor(self, editor):
        self.conectar_editor(editor)

    def set_projeto(self, caminho: str):
        log.info(_ARQ, "set_projeto", f"projeto definido: '{caminho}'")
        self._projeto_path = caminho

    def atualizar(self):
        self._atualizar()

    # ──────────────────────────────────────────────────────────────
    # Atualização do outline
    # ──────────────────────────────────────────────────────────────

    def _agendar_atualizacao(self):
        if not self._input_busca.text().strip():
            self._timer.start()

    def _atualizar(self):
        if self._input_busca.text().strip():

            return

        if self._modo_painel == _MODO_BUSCA:

            return  # resultados de busca externa — não interfere

        # ── NÃO fazemos clear() aqui para python_ast ─────────────────────────────────
        # python_ast roda em background thread; limpar agora deixaria a árvore
        # vazia por 50-200 ms (o "piscar"). O clear() fica dentro de
        # _aplicar_arvore_python(), executado imediatamente antes de popular.
        # Para os demais modos síncronos usamos setUpdatesEnabled para que o
        # par clear+popular apareça como um único frame sem flash intermediário.

        self._label_status.hide()

        if self._modo_painel == _MODO_TAREFAS:
            self._arvore.clear()
            return

        if not self._editor_atual:
            self._arvore.clear()
            return

        ext    = self._extensao_atual
        codigo = self._editor_atual.toPlainText()

        from _EDITOR_.Mult_Linguas import get_provider
        mode = get_provider(ext).outline_mode

        if mode == 'python_ast':
            # Async: clear + populate acontecem em _aplicar_arvore_python()
            self._ativar_arvore()
            self._iniciar_thread_outline(codigo)
        else:
            # Modos síncronos: bloqueia repintura até terminar para evitar flash
            self._arvore.setUpdatesEnabled(False)
            try:
                self._arvore.clear()
                if mode == 'preview_md':
                    self._ativar_preview()
                    self._popular_preview_md(codigo)
                elif mode == 'preview_html':
                    self._ativar_preview()
                    self._popular_preview_html(codigo)
                elif mode == 'tree_json':
                    self._ativar_arvore()
                    self._popular_arvore_dict(self._analisar_json(codigo))
                elif mode == 'tree_xml':
                    self._ativar_arvore()
                    self._popular_arvore_dict(self._analisar_xml(codigo))
                elif mode == 'tree_yaml':
                    self._ativar_arvore()
                    self._popular_arvore_dict(self._analisar_yaml(codigo))
                elif mode == 'tree_js':
                    self._ativar_arvore()
                    self._popular_arvore_dict(self._analisar_js(codigo))
                elif mode == 'tree_sh':
                    self._ativar_arvore()
                    self._popular_arvore_dict(self._analisar_sh(codigo))
                elif mode == 'tree_sql':
                    self._ativar_arvore()
                    self._popular_arvore_dict(self._analisar_sql(codigo))
                elif mode == 'tree_c':
                    self._ativar_arvore()
                    self._popular_arvore_dict(self._analisar_c(codigo))
                elif mode == 'tree_make':
                    self._ativar_arvore()
                    self._popular_arvore_dict(self._analisar_make(codigo))
                elif mode == 'tree_lua':
                    self._ativar_arvore()
                    self._popular_arvore_dict(self._analisar_lua(codigo))
                elif mode == 'tree_hein':
                    self._ativar_arvore()
                    try:
                        self._popular_arvore_dict(self._analisar_hein(codigo))
                    except Exception:
                        log.exception("[outline] falha ao analisar .en (tree_hein)")
                else:
                    # 'none' e qualquer mode desconhecido → outline vazio
                    self._ativar_arvore()
            finally:
                self._arvore.setUpdatesEnabled(True)

        # barra de formatacao - so aparece para providers que a pedem (Hein)
        if hasattr(self, '_barra_formatacao'):
            try:
                self._barra_formatacao.setVisible(get_provider(ext).tem_barra_formatacao)
            except Exception:
                log.exception("[outline] falha ao alternar barra de formatacao")

    # ──────────────────────────────────────────────────────────────
    # Python
    # ──────────────────────────────────────────────────────────────

    def _construir_arvore_python(self, codigo: str):
        caminho = getattr(self._editor_atual, "file_path", None) or ""
        try:
            arvore_ast = ast.parse(codigo, filename=caminho or "<editor>")
            self._label_status.hide()
        except SyntaxError as e:
            self._label_status.setText(f"⚠ linha {e.lineno}: {traduzir(e.msg)}")
            self._label_status.show()
            self._construir_arvore_python_regex(codigo, caminho)

            return

        for no in ast.iter_child_nodes(arvore_ast):
            self._adicionar_no(no, self._arvore.invisibleRootItem(), caminho, pai_tipo="")

    def _construir_arvore_python_regex(self, codigo: str, caminho: str):
        """Fallback com regex quando há SyntaxError — mantém outline visível."""
        for i, linha in enumerate(codigo.splitlines(), 1):
            m = re.match(r"^\s*(async\s+def|def|class)\s+(\w+)", linha)
            if not m:
                continue
            tipo_kw = m.group(1).strip()
            nome    = m.group(2)
            tipo    = "classe" if tipo_kw == "class" else "funcao"
            texto   = f"class {nome}" if tipo == "classe" else f"{tipo_kw} {nome}(...)"
            item    = ItemOutline(texto, caminho, i, tipo)
            item.setForeground(0, self._cor_tipo(tipo))
            self._arvore.addTopLevelItem(item)

    def _adicionar_no(self, no: ast.AST, pai: QTreeWidgetItem, caminho: str, pai_tipo: str):
        if isinstance(no, ast.ClassDef):
            texto = f"class {no.name}"
            item  = ItemOutline(texto, caminho, no.lineno, "classe", pai)
            item.setData(0, Qt.UserRole, "classe")
            item.setForeground(0, self._cor_tipo("classe"))
            for filho in ast.iter_child_nodes(no):
                self._adicionar_no(filho, item, caminho, pai_tipo="classe")
            item.setExpanded(True)

        elif isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args_txt = self._formatar_args(no.args)
            prefix   = "async def " if isinstance(no, ast.AsyncFunctionDef) else "def "
            tipo     = "metodo" if pai_tipo == "classe" else "funcao"
            if tipo == "metodo" and no.name.startswith("_"):
                tipo = "metodo_priv"
            texto = f"{prefix}{no.name}({args_txt})"
            item  = ItemOutline(texto, caminho, no.lineno, tipo, pai)
            item.setData(0, Qt.UserRole, tipo)
            item.setForeground(0, self._cor_tipo(tipo))
            self._adicionar_chamadas(no, item, caminho)
            if item.childCount() > 0:
                item.setExpanded(False)  # recolhido por padrão — usuário expande clicando

    def _adicionar_chamadas(self, no_func: ast.AST, pai: QTreeWidgetItem, caminho: str):
        """Popula filhos do item com as funções chamadas dentro do corpo."""
        t = tema_global()
        cor = t.cor("painel_outline.cor_chamada", "")
        if not cor:
            cor = t.cor("interface.texto_fraco", "#666666")

        vistas = set()
        for sub in ast.walk(no_func):
            # pula o próprio nó raiz
            if sub is no_func:
                continue
            # não entra em funções aninhadas
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub is not no_func:
                continue
            if isinstance(sub, ast.Call):
                nome_chamada = self._nome_da_call(sub)
                if not nome_chamada or nome_chamada in vistas:
                    continue
                vistas.add(nome_chamada)
                linha_call = getattr(sub, "lineno", 0)
                filho = ItemOutline(f"  └─ {nome_chamada}()", caminho, linha_call, "chamada", pai)
                filho.setForeground(0, QColor(cor))

    @staticmethod
    def _nome_da_call(node: ast.Call) -> str:
        """Extrai o nome legível de um ast.Call."""
        func = node.func
        if isinstance(func, ast.Name):

            return func.id

        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name):

                return f"{func.value.id}.{func.attr}"

            return func.attr

        return ""

    # ──────────────────────────────────────────────────────────────
    # Outros formatos
    # ──────────────────────────────────────────────────────────────

    def _analisar_json(self, codigo: str) -> list:
        from _EDITOR_.Mult_Linguas.JSON.outline import analisar_json
        return analisar_json(codigo)

    def _json_para_itens(self, dados, nome="raiz") -> list:
        itens = []
        if isinstance(dados, dict):
            pai = {"tipo": "objeto", "nome": nome, "linha": 1, "filhos": []}
            for chave, valor in dados.items():
                if isinstance(valor, (dict, list)):
                    pai["filhos"].extend(self._json_para_itens(valor, chave))
                else:
                    pai["filhos"].append({"tipo": "chave", "nome": chave, "valor": repr(valor)[:30], "linha": 1})
            itens.append(pai)
        elif isinstance(dados, list):
            for i, item in enumerate(dados[:50]):
                if isinstance(item, (dict, list)):
                    itens.extend(self._json_para_itens(item, f"[{i}]"))
                else:
                    itens.append({"tipo": "item", "nome": f"[{i}]", "valor": repr(item)[:50], "linha": 1})

        return itens

    def _analisar_json_regex(self, codigo: str) -> list:
        itens = []
        for i, linha in enumerate(codigo.splitlines(), 1):
            m = re.search(r'"(\w+)":', linha)
            if m:
                itens.append({"tipo": "chave", "nome": m.group(1), "valor": linha.strip(), "linha": i})

        return itens

    def _analisar_xml(self, codigo: str) -> list:
        from _EDITOR_.Mult_Linguas.XML.outline import analisar_xml
        return analisar_xml(codigo)

    def _analisar_yaml(self, codigo: str) -> list:
        from _EDITOR_.Mult_Linguas.YAML.outline import analisar_yaml
        return analisar_yaml(codigo)

    def _analisar_js(self, codigo: str) -> list:
        from _EDITOR_.Mult_Linguas.JavaScript.outline import analisar_js
        return analisar_js(codigo)

    def _analisar_sh(self, codigo: str) -> list:
        from _EDITOR_.Mult_Linguas.Shell.outline import analisar_sh
        return analisar_sh(codigo)

    def _analisar_sql(self, codigo: str) -> list:
        from _EDITOR_.Mult_Linguas.SQL.outline import analisar_sql
        return analisar_sql(codigo)

    def _analisar_c(self, codigo: str) -> list:
        from _EDITOR_.Mult_Linguas.C_CPP.outline import analisar_c
        return analisar_c(codigo)

    def _analisar_make(self, codigo: str) -> list:
        from _EDITOR_.Mult_Linguas.Makefile.outline import analisar_make
        return analisar_make(codigo)

    def _analisar_lua(self, codigo: str) -> list:
        from _EDITOR_.Mult_Linguas.Lua.outline import analisar_lua
        return analisar_lua(codigo)

    def _analisar_hein(self, codigo: str) -> list:
        from _EDITOR_.Mult_Linguas.Hein.outline import analisar_hein
        return analisar_hein(codigo)

    def _popular_arvore_dict(self, itens: list):
        caminho = getattr(self._editor_atual, "file_path", "") or ""
        for item in itens:
            tipo = item.get("tipo", "item")
            texto = (f"{{ {item['nome']} }}"                         if tipo == "objeto"
                     else f"{item['nome']}: {item.get('valor', '')}"  if tipo == "chave"
                     else f"<{item['nome']}>"                         if tipo == "tag"
                     else item.get("nome", "item"))
            item_arv = ItemOutline(texto, caminho, item.get("linha", 1), tipo)
            item_arv.setForeground(0, self._cor_tipo(tipo))
            for filho in item.get("filhos", []):
                self._adicionar_filho_dict(item_arv, filho, caminho)
            self._arvore.addTopLevelItem(item_arv)

    def _adicionar_filho_dict(self, pai, item: dict, caminho: str):
        tipo  = item.get("tipo", "item")
        texto = (f"{item['nome']}: {item.get('valor', '')}" if tipo == "chave"
                 else item.get("nome", "item"))
        filho = ItemOutline(texto, caminho, item.get("linha", 1), tipo, pai)
        filho.setForeground(0, self._cor_tipo(tipo))

    # ──────────────────────────────────────────────────────────────
    # Busca Global — usa a árvore como painel de resultados
    # ──────────────────────────────────────────────────────────────

    def iniciar_busca_global(self, termo: str):
        """Ativa modo BUSCA: limpa árvore e aguarda resultados do MotorBusca."""
        self._modo_painel = _MODO_BUSCA
        self._arvore.clear()
        self._busca_pais.clear()
        t = termo.strip()
        self._label_status.setText(f'🔍 Buscando "{t}"…' if t else "🔍 Buscando…")
        self._label_status.show()

    def contar_resultados_busca(self) -> int:
        """Nº de itens de topo (arquivos) na árvore, quando em modo BUSCA."""
        if self._modo_painel != _MODO_BUSCA:
            return 0
        return self._arvore.topLevelItemCount()

    def focar_arvore(self):
        """Leva o foco de teclado pra árvore de resultados — usado quando há
        múltiplos arquivos batendo com o filtro e o usuário precisa escolher."""
        self._arvore.setFocus()
        if not self._arvore.currentItem() and self._arvore.topLevelItemCount() > 0:
            primeiro = self._arvore.topLevelItem(0)
            self._arvore.setCurrentItem(primeiro)

    def mostrar_busca_motor(self, resultados: list):
        """Recebe list[ResultadoBusca] síncronos do MotorBusca."""
        if self._modo_painel != _MODO_BUSCA:

            return

        from _BUSCA_.modelo_resultado import TipoBusca
        t = tema_global()
        c_arq = t.cor("painel_outline.cor_arquivo", COR_OUTLINE_ARQUIVO)
        c_lin = t.cor("editor.sintaxe.string",      COR_OUTLINE_CHAVE_JSON)
        c_cam = t.cor("interface.texto_fraco",      "#888888")
        for r in resultados:
            if r.tipo in (TipoBusca.LINHA, TipoBusca.COMANDO):
                continue
            if r.tipo in (TipoBusca.ARQUIVO, TipoBusca.RECENTE):
                nome = os.path.basename(r.caminho) if r.caminho else r.titulo
                item = ItemOutline(nome, r.caminho or "", 1, "arquivo")
                item.setForeground(0, QColor(c_arq))
                item.setToolTip(0, r.subtitulo or r.caminho or "")
                self._arvore.addTopLevelItem(item)
            else:
                linha_1 = r.linha + 1
                self._garantir_pai_busca(r.caminho, c_arq, c_cam)
                pai = self._busca_pais.get(r.caminho)
                if pai:
                    filho = ItemOutline(f"  {linha_1}:  {r.titulo.strip()}", r.caminho, linha_1, "item", pai)
                    filho.setForeground(0, QColor(c_lin))
        n = self._arvore.topLevelItemCount()
        self._label_status.setText(f"{n} arquivo(s)" if n else "Nenhum resultado")
        self._label_status.show()

    def adicionar_grep_motor(self, resultado):
        """Adiciona ResultadoBusca de GrepThread (streaming) à árvore."""
        if self._modo_painel != _MODO_BUSCA:

            return

        t = tema_global()
        c_arq = t.cor("painel_outline.cor_arquivo", COR_OUTLINE_ARQUIVO)
        c_lin = t.cor("editor.sintaxe.string",      COR_OUTLINE_CHAVE_JSON)
        c_cam = t.cor("interface.texto_fraco",      "#888888")
        linha_1 = resultado.linha + 1
        self._garantir_pai_busca(resultado.caminho, c_arq, c_cam)
        pai = self._busca_pais.get(resultado.caminho)
        if not pai:

            return

        filho = ItemOutline(f"  {linha_1}:  {resultado.titulo.strip()}", resultado.caminho, linha_1, "item", pai)
        filho.setForeground(0, QColor(c_lin))
        pai.setExpanded(True)
        nome_arq = os.path.basename(resultado.caminho)
        pai.setText(0, f"{nome_arq}  ({pai.childCount()})")
        total = sum(self._arvore.topLevelItem(i).childCount()
                   for i in range(self._arvore.topLevelItemCount()))
        self._label_status.setText(f"{total} resultado(s)…")

    def _garantir_pai_busca(self, caminho: str, c_arq: str, c_cam: str):
        """Cria item de arquivo na árvore se ainda não existir."""
        if caminho in self._busca_pais:

            return

        nome_arq = os.path.basename(caminho)
        rel = ""
        if self._projeto_path:
            try:
                rel = os.path.relpath(caminho, self._projeto_path)
            except ValueError:
                rel = caminho
        pai = ItemOutline(f"{nome_arq}  (0)", caminho, 0, "arquivo")
        pai.setForeground(0, QColor(c_arq))
        pai.setToolTip(0, rel or caminho)
        pai.setExpanded(True)
        self._busca_pais[caminho] = pai
        self._arvore.addTopLevelItem(pai)

    def voltar_outline(self):
        """Cancela modo BUSCA e regenera o outline do arquivo atual."""
        if self._modo_painel == _MODO_OUTLINE:

            return

        self._modo_painel = _MODO_OUTLINE
        self._busca_pais.clear()
        self._label_status.hide()
        self._timer.start(100)

    # ──────────────────────────────────────────────────────────────
    # Preview MD / HTML
    # ──────────────────────────────────────────────────────────────

    def _ativar_preview(self):
        """Mostra o preview (MD/HTML), esconde a arvore."""
        self._arvore.hide()
        self._label_status.hide()
        self._preview.show()

    def _ativar_arvore(self):
        """Mostra a arvore de outline, esconde o preview."""
        self._preview.hide()
        self._arvore.show()

    def _popular_preview_md(self, codigo: str):
        """Converte Markdown para HTML e exibe no preview — delegado a Markdown/outline.py."""
        from _EDITOR_.Mult_Linguas.Markdown.outline import popular_preview_md
        popular_preview_md(self._preview, codigo)

    def _popular_preview_html(self, codigo: str):
        """Exibe HTML renderizado no preview — delegado a HTML/outline.py."""
        from _EDITOR_.Mult_Linguas.HTML.outline import popular_preview_html
        popular_preview_html(self._preview, codigo)

    def _md_para_html(self, md: str, fundo: str, texto: str, link: str, header: str, code_bg: str, hr_cor: str) -> str:
        """Converte Markdown para HTML sem dependencias externas."""

        def _esc(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        def _inline(s: str) -> str:
            s = _esc(s)
            s = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', s)
            s = re.sub(r'___(.+?)___',        r'<b><i>\1</i></b>', s)
            s = re.sub(r'\*\*(.+?)\*\*',      r'<b>\1</b>', s)
            s = re.sub(r'__(.+?)__',          r'<b>\1</b>', s)
            s = re.sub(r'\*([^\*\n]+?)\*',    r'<i>\1</i>', s)
            s = re.sub(r'_([^_\n]+?)_',       r'<i>\1</i>', s)
            s = re.sub(
                r'`([^`\n]+?)`',
                lambda m: (
                    f'<code style="background:{code_bg};padding:1px 3px;'
                    f'border-radius:2px;font-family:monospace;">{m.group(1)}</code>'
                ),
                s
            )
            s = re.sub(
                r'\[([^\]]+?)\]\(([^\)]+?)\)',
                lambda m: f'<a href="{m.group(2)}" style="color:{link};">{m.group(1)}</a>',
                s
            )
            s = re.sub(r'!\[([^\]]*?)\]\([^\)]+?\)', r'[🖼 \1]', s)

            return s

        lines    = md.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        out      = []
        in_code  = False
        code_buf = []
        in_list  = False
        list_tag = 'ul'

        def flush_list():
            nonlocal in_list, list_tag
            if in_list:
                out.append(f'</{list_tag}>')
                in_list = False

        for raw_line in lines:
            line = raw_line.rstrip()

            if line.startswith('```'):
                if not in_code:
                    flush_list()
                    in_code  = True
                    code_buf = []
                else:
                    body = _esc('\n'.join(code_buf))
                    out.append(
                        f'<pre style="background:{code_bg};padding:6px 10px;'
                        f'border-radius:4px;margin:4px 0;'
                        f'font-family:monospace;font-size:11px;'
                        f'white-space:pre-wrap;">{body}</pre>'
                    )
                    in_code = False
                continue

            if in_code:
                code_buf.append(line)
                continue

            m = re.match(r'^(#{1,6})\s+(.*)', line)
            if m:
                flush_list()
                lvl = len(m.group(1))
                ht  = _inline(m.group(2))
                sz  = ['1.5em', '1.3em', '1.15em', '1.05em', '1em', '0.9em'][lvl - 1]
                clr = header if lvl <= 2 else texto
                bdr = (f'border-bottom:1px solid {hr_cor};padding-bottom:4px;'
                       if lvl <= 2 else '')
                out.append(
                    f'<h{lvl} style="color:{clr};font-size:{sz};font-weight:bold;'
                    f'margin:8px 0 4px 0;{bdr}">{ht}</h{lvl}>'
                )
                continue

            if re.match(r'^(-{3,}|\*{3,}|_{3,})\s*$', line):
                flush_list()
                out.append(
                    f'<hr style="border:0;border-top:1px solid {hr_cor};margin:8px 0;">'
                )
                continue

            m = re.match(r'^>\s?(.*)', line)
            if m:
                flush_list()
                out.append(
                    f'<blockquote style="border-left:3px solid {hr_cor};'
                    f'margin:2px 0 2px 4px;padding:2px 8px;opacity:0.8;">'
                    + _inline(m.group(1)) + '</blockquote>'
                )
                continue

            m = re.match(r'^[\-\*\+]\s+(.*)', line)
            if m:
                if not in_list or list_tag != 'ul':
                    flush_list()
                    out.append('<ul style="margin:3px 0;padding-left:20px;">')
                    in_list  = True
                    list_tag = 'ul'
                out.append(f'<li style="margin:1px 0;">{_inline(m.group(1))}</li>')
                continue

            m = re.match(r'^\d+\.\s+(.*)', line)
            if m:
                if not in_list or list_tag != 'ol':
                    flush_list()
                    out.append('<ol style="margin:3px 0;padding-left:20px;">')
                    in_list  = True
                    list_tag = 'ol'
                out.append(f'<li style="margin:1px 0;">{_inline(m.group(1))}</li>')
                continue

            flush_list()

            if not line:
                out.append('<div style="height:4px;"></div>')
                continue

            out.append(f'<p style="margin:1px 0;line-height:1.5;">{_inline(line)}</p>')

        flush_list()

        body = '\n'.join(out)

        return (

            f'<html><body style="background:{fundo};color:{texto};'
            f'font-family:Segoe UI,Arial,sans-serif;font-size:12px;'
            f'padding:8px 10px;margin:0;line-height:1.4;word-wrap:break-word;">'
            f'{body}</body></html>'
        )

    # ──────────────────────────────────────────────────────────────
    # Eventos
    # ──────────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────
    # Outline Python — async (não bloqueia UI)
    # ──────────────────────────────────────────────────────────────

    def _iniciar_thread_outline(self, codigo: str):
        """Lança _ThreadOutlinePy; pula se o código não mudou.
        
        Se o código não mudou mas a árvore foi limpa (ex: _atualizar chamou
        _arvore.clear() antes de chegar aqui), repopula do cache em vez de
        deixar a árvore vazia.
        """
        h = hash(codigo)
        if h == self._hash_outline:
            # Código idêntico ao último parse — repopula do cache sem relançar
            # a thread, mas SOMENTE se a árvore estiver vazia (foi limpa antes
            # de chegar aqui). Se já houver itens, não faz nada: a árvore já
            # está correta e adicionar novamente causaria duplicação.
            # BUG-23-07: faltava essa guarda — cada clique no editor disparava
            # _atualizar → _iniciar_thread_outline → repopulava sem clear(),
            # dobrando os itens na árvore a cada chamada.
            if self._nos_cache is not None and self._arvore.topLevelItemCount() == 0:
                caminho = (getattr(self._editor_atual, "file_path", None) or ""
                           if self._editor_atual else "")
                for nd in self._nos_cache:
                    self._adicionar_no_de_dados(
                        nd, self._arvore.invisibleRootItem(), caminho
                    )
            return

        self._hash_outline = h
        if not hasattr(self, '_threads_outline_antigas'):
            self._threads_outline_antigas = []
        try:
            _esta_rodando = self._thread_outline is not None and self._thread_outline.isRunning()
        except RuntimeError:
            _esta_rodando = False
            reference("ZERO", "OUTLINE", self, "_thread_outline",
                      before=self._thread_outline, after=None,
                      editor=self._editor_atual,
                      task=getattr(self._thread_outline, "_hein_diag_task", ""))
            self._thread_outline = None
        if _esta_rodando:
            try:
                self._thread_outline.concluido.disconnect()
            except RuntimeError:
                pass
            t_antigo = self._thread_outline
            _task_antigo = getattr(t_antigo, "_hein_diag_task", "")
            self._threads_outline_antigas.append(t_antigo)
            def _remover_antiga(t=t_antigo):
                try:
                    self._threads_outline_antigas.remove(t)
                    reference("REMOVE", "OUTLINE", self, "_threads_outline_antigas",
                              before=t, after=None, editor=self._editor_atual,
                              task=getattr(t, "_hein_diag_task", ""))
                except ValueError:
                    pass
            t_antigo.finished.connect(_remover_antiga)
            event("QUIT_REQUESTED", "OUTLINE", _task_antigo, obj=t_antigo,
                  editor=self._editor_atual, reason="replaced_by_new_outline")
            t_antigo.quit()
        caminho = getattr(self._editor_atual, "file_path", None) or ""
        _editor = self._editor_atual
        _edit = edit_generation(_editor)
        _task = new_task("OUTLINE", _editor, _edit)
        _old_outline = self._thread_outline
        _new_outline = _ThreadOutlinePy(codigo, caminho, _task, _editor, _edit)
        reference("REPLACE", "OUTLINE", self, "_thread_outline",
                  before=_old_outline, after=_new_outline,
                  editor=_editor, task=_task)
        self._thread_outline = _new_outline
        bind(self._thread_outline, "OUTLINE", _task, _editor, _edit)
        self._thread_outline.concluido.connect(self._aplicar_arvore_python)
        # NÃO conectar finished → deleteLater (BUG-202807-07/12): crash.
        # _threads_vivas_outline mantém referência viva até finished — evita GC
        # prematuro se PainelOutline for destruído antes de run() retornar.
        _threads_vivas_outline.add(self._thread_outline)
        self._thread_outline.finished.connect(
            lambda t=self._thread_outline: self._on_thread_outline_finalizada(t)
        )
        self._thread_outline.finished.connect(
            lambda t=self._thread_outline: _threads_vivas_outline.discard(t)
        )
        self._thread_outline.start()

    def _on_thread_outline_finalizada(self, thread_finished=None):
        """Anula a referência quando a thread termina — evita RuntimeError shiboken."""
        _thread = thread_finished
        _task = getattr(_thread, "_hein_diag_task", "") if _thread else ""
        _current = self._thread_outline
        _current_task = getattr(_current, "_hein_diag_task", "") if _current else ""
        reference("ZERO", "OUTLINE", self, "_thread_outline",
                  before=_current, after=None, editor=self._editor_atual,
                  task=_task, finished_py_id=id(_thread) if _thread else 0,
                  current_reference_py_id=id(_current) if _current else 0,
                  finished_task=_task,
                  current_reference_task=_current_task,
                  reference_matches=_thread is _current)
        self._thread_outline = None

    def _aplicar_arvore_python(self, nos: list, erro_msg: str):
        """Recebe resultado do _ThreadOutlinePy e monta a árvore (roda na UI thread)."""
        if self._modo_painel == _MODO_BUSCA:

            return  # não sobrescreve resultados de busca global

        # Guarda cache dos nós para repopular sem relançar thread quando o
        # hash bater mas a árvore tiver sido limpa (ver _iniciar_thread_outline).
        self._nos_cache = nos if not erro_msg else None

        self._arvore.clear()
        caminho = getattr(self._editor_atual, "file_path", None) or "" if self._editor_atual else ""
        if erro_msg:
            from _TRADUTION_.tradutor_erros import traduzir as _traduzir
            self._label_status.setText(f"⚠ {_traduzir(erro_msg)}")
            self._label_status.show()
            if self._editor_atual:
                self._construir_arvore_python_regex(self._editor_atual.toPlainText(), caminho)

            return

        self._label_status.hide()
        for nd in nos:
            self._adicionar_no_de_dados(nd, self._arvore.invisibleRootItem(), caminho)

    def _adicionar_no_de_dados(self, dados: dict, pai, caminho: str):
        """Cria QTreeWidgetItem a partir de um dicionário de dados."""
        tipo  = dados["tipo"]
        item  = ItemOutline(dados["texto"], caminho, dados["linha"], tipo, pai)
        item.setData(0, Qt.UserRole, tipo)
        item.setForeground(0, self._cor_tipo(tipo))
        for filho in dados.get("filhos", []):
            self._adicionar_no_de_dados(filho, item, caminho)
        cor = tema_global().cor("painel_outline.cor_chamada", "") or               tema_global().cor("interface.texto_fraco", "#666666")
        for ch in dados.get("chamadas", []):
            c = ItemOutline(ch["texto"], caminho, ch["linha"], "chamada", item)
            c.setForeground(0, QColor(cor))
        if tipo == "classe":
            item.setExpanded(True)
        elif tipo in ("import_grupo",):
            item.setExpanded(False)  # imports colapsados por padrão
        elif dados.get("chamadas"):
            item.setExpanded(False)

    def _ao_clicar_item(self, item: QTreeWidgetItem, _coluna: int = 0):
        if not isinstance(item, ItemOutline) or item.linha <= 0:

            return

        if item.caminho_arquivo:
            self.navegar_solicitado.emit(item.caminho_arquivo, item.linha)
        self.navegar_para_linha.emit(item.linha)

    # ──────────────────────────────────────────────────────────────
    # 8.1 — Fold pelo outline (ícone hover + clique)
    # ──────────────────────────────────────────────────────────────

    def _fold_estado(self, linha: int):
        """True=colapsado, False=expandido, None=não dobrável."""
        if not self._editor_atual:

            return None

        editor = self._editor_atual
        bloco  = editor.document().findBlockByNumber(linha - 1)
        if not bloco.isValid():

            return None

        from _EDITOR_.Core.editor_dobramento import _es_dobravel_para_extensao
        if not _es_dobravel_para_extensao(bloco.text(), self._extensao_atual):

            return None

        reg = editor._get_fold_region(bloco)

        return reg is not None  # True = já colapsado

    def _toggle_fold_outline(self, item_ot):
        """Dobra/expande o bloco no editor sem mover cursor ou scroll."""
        if not self._editor_atual:

            return

        editor = self._editor_atual
        bloco  = editor.document().findBlockByNumber(item_ot.linha - 1)
        if not bloco.isValid():

            return

        if editor._get_fold_region(bloco) is not None:
            editor.expandir_bloco(bloco)
        else:
            editor.recolher_bloco(bloco)
        self._arvore.viewport().update()

    # ──────────────────────────────────────────────────────────────
    # 8.4 — Barra de atalhos fold + popup
    # ──────────────────────────────────────────────────────────────

    def _construir_barra_atalhos(self) -> QWidget:
        """
        Instancia BarraOutline (definida em barra_status.py) e faz a cola
        outline-específica: ícone do botão ajuda, sinal do fold e popup de atalhos.
        Todo o estilo/cores/altura vem de BarraOutline — sem duplicação aqui.
        """
        from _EDITOR_.Funcionalidades.barra_status import BarraOutline

        barra = BarraOutline()

        # ── expõe os widgets como atributos do outline (nomes preservados) ──
        self._lbl_ol_erros     = barra.lbl_erros
        self._lbl_ol_avisos    = barra.lbl_avisos
        self._btn_atalhos_fold = barra.btn_atalhos_fold
        self._btn_ajuda        = barra.btn_ajuda

        # ── detalhes outline-específicos: ícone e sinais ──────────────────
        self._btn_ajuda.setIcon(icone_tema("mdi.help-circle-outline"))
        self._btn_atalhos_fold.clicked.connect(self._toggle_popup_atalhos)

        # ── popup de atalhos de fold (Qt.Popup fecha ao clicar fora) ─────
        self._popup_atalhos = QFrame(None)
        self._popup_atalhos.setObjectName("PopupAtalhosFold")
        self._popup_atalhos.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        lay_pop = QVBoxLayout(self._popup_atalhos)
        lay_pop.setContentsMargins(12, 10, 12, 10)
        lay_pop.setSpacing(0)
        sep_pop = QFrame()
        sep_pop.setFrameShape(QFrame.HLine)
        sep_pop.setObjectName("PopupSep")
        lay_pop.addWidget(sep_pop)
        for tecla, descricao in [
            ("Ctrl + -",       "Dobrar bloco atual / selecionados"),
            ("Ctrl + +",       "Expandir bloco atual / selecionados"),
            ("Ctrl + Alt + -", "Dobrar TODOS os blocos"),
            ("Ctrl + Alt + +", "Expandir TODOS os blocos"),
            ("▶  gutter",      "Clicar seta no gutter"),
            ("▼  outline",     "Ícone no painel outline"),
        ]:
            row = QWidget()
            rl  = QHBoxLayout(row)
            rl.setContentsMargins(0, 3, 0, 3)
            rl.setSpacing(0)
            lk = QLabel(tecla)
            lk.setObjectName("PopupTecla")
            lk.setFixedWidth(118)
            ld = QLabel(descricao)
            ld.setObjectName("PopupDesc")
            rl.addWidget(lk)
            rl.addWidget(ld)
            lay_pop.addWidget(row)
        self._popup_atalhos.adjustSize()
        self._aplicar_tema_popup_atalhos()

        return barra

    def _toggle_popup_atalhos(self):
        """Exibe/oculta o popup de atalhos de fold."""
        if self._popup_atalhos.isVisible():
            self._popup_atalhos.hide()

            return

        self._popup_atalhos.adjustSize()
        pos = self._btn_atalhos_fold.mapToGlobal(
            self._btn_atalhos_fold.rect().topLeft()
        )
        pos.setY(pos.y() - self._popup_atalhos.height() - 4)
        self._popup_atalhos.move(pos)
        self._popup_atalhos.show()
        self._popup_atalhos.raise_()

    # ⚠️  função grande (56 linhas)
    def _aplicar_tema_popup_atalhos(self):
        t = tema_global()
        fundo  = t.cor("interface.fundo_painel",    "#0F1210")
        borda  = t.cor("interface.borda",            "#1f3d1f")
        fraco  = t.cor("interface.texto_fraco",      "#5a7a5a")
        texto  = t.cor("interface.texto",            "#e8f5e8")
        btn_clr = t.cor("editor.numero_linha",       "#7094A1")
        if not hasattr(self, '_popup_atalhos'):

            return

        self._popup_atalhos.setStyleSheet(f"""
            QFrame#PopupAtalhosFold {{
                background: {fundo};
                border: 1px solid {borda};
                border-radius: 5px;
            }}
            QLabel#PopupTitulo {{
                color: {btn_clr};
                font-size: 11px;
                font-weight: bold;
                padding: 0 0 4px 0;
            }}
            QFrame#PopupSep {{
                color: {borda};
                margin: 2px 0 4px 0;
            }}
            QLabel#PopupTecla {{
                color: {btn_clr};
                font-family: monospace;
                font-size: 11px;
            }}
            QLabel#PopupDesc {{
                color: {fraco};
                font-size: 11px;
            }}
        """)
        if hasattr(self, '_barra_atalhos'):
            self._barra_atalhos.setStyleSheet(f"""
                QWidget#BarraAtalhosFold {{
                    background: transparent;
                    border-top: 1px solid {borda};
                }}
                QPushButton#BtnAtalhosFold {{
                    background: transparent;
                    color: {fraco};
                    border: none;
                    border-radius: 3px;
                    padding: 0 5px;
                    font-size: 10px;
                }}
                QPushButton#BtnAtalhosFold:hover {{
                    background: {t.cor("interface.fundo_item_hover", "#1a3a1a")};
                    color: {texto};
                }}
            """)

    # ──────────────────────────────────────────────────────────────
    # Utilitários
    # ──────────────────────────────────────────────────────────────

    # ====================================================================
    # Busca inline (Ctrl+F) e substituicao (Ctrl+H)
    # ====================================================================

    # -- API publica (chamada pelo main_window) --

    def ativar_modo_arquivo_inline(self, termo: str):
        """Ctrl+F / texto sem prefixo -- busca no arquivo atual."""
        if self._editor_atual and not hasattr(self, '_cursor_antes_inline'):
            self._cursor_antes_inline = self._editor_atual.textCursor()
        self._modo_inline = _MODO_ARQUIVO_INLINE
        self._mostrar_barra_modo(_MODO_ARQUIVO_INLINE)
        self._buscar_inline(termo)
        self._conectar_barra_central("arquivo")

    def ativar_modo_substituicao(self, termo: str):
        """Ctrl+H -- busca + substituicao no arquivo atual."""
        self._modo_inline = _MODO_SUBSTITUICAO
        self._mostrar_barra_modo(_MODO_SUBSTITUICAO)
        self._campo_sub.clear()
        self._buscar_inline(termo)
        self._conectar_barra_central("substituicao")

    def ativar_modo_linha(self, n: int):
        """:N -- exibe atalho Ir para linha N na barra de modo."""
        self._modo_inline = _MODO_LINHA
        self._n_linha_destino = n
        self._mostrar_barra_modo(_MODO_LINHA)
        self._lbl_ir_linha.setText(f"Ir para linha  {n}")

    def desativar_modo_busca_inline(self):
        """Esc / campo vazio -- restaura o outline normal."""
        self._modo_inline = ""
        self._barra_modo.hide()
        self._limpar_destaques_inline()
        self._arvore.clear()
        self._atualizar()
        janela = self.window()
        if hasattr(janela, '_barra_central'):
            self._desconectar_barra_central_safe(janela._barra_central)
            janela._barra_central.hide()
        if hasattr(self, '_cursor_antes_inline') and self._editor_atual:
            self._editor_atual.setTextCursor(self._cursor_antes_inline)
            self._editor_atual.ensureCursorVisible()
        try:
            del self._cursor_antes_inline
        except AttributeError:
            pass

    # -- Construcao da barra de modo --

    def _construir_barra_modo(self):
        """Cria o widget de toolbar contextual (escondido por padrao).
        Os controles ▲▼ Aa .* e os botoes Substituir/Sub.tudo ficam na BarraCentral.
        Aqui fica apenas o campo grande de substituicao e o atalho de linha.
        """
        self._barra_modo = QWidget()
        self._barra_modo.setObjectName("BarraModoOutline")
        lay_modo = QVBoxLayout(self._barra_modo)
        lay_modo.setContentsMargins(4, 3, 4, 3)
        lay_modo.setSpacing(2)

        # ── Secao substituicao: campo grande para colar o texto alvo ──
        self._secao_sub = QWidget()
        lay_sub = QVBoxLayout(self._secao_sub)
        lay_sub.setContentsMargins(0, 0, 0, 0)
        lay_sub.setSpacing(2)

        _lbl_sub = QLabel("substituir por:")
        _lbl_sub.setStyleSheet("font-size: 10px;")

        self._campo_sub = QPlainTextEdit()
        self._campo_sub.setPlaceholderText("cole ou escreva o texto de substituicao... (Enter = substituir, Shift+Enter = nova linha)")
        self._campo_sub.setMinimumHeight(54)
        self._campo_sub.setMaximumHeight(320)
        self._campo_sub.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self._campo_sub.installEventFilter(self)

        lay_sub.addWidget(_lbl_sub)
        lay_sub.addWidget(self._campo_sub)
        lay_modo.addWidget(self._secao_sub)

        # ── Secao ir para linha ──────────────────────────────────────
        self._secao_linha = QWidget()
        lay_ln = QHBoxLayout(self._secao_linha)
        lay_ln.setContentsMargins(0, 0, 0, 0)
        lay_ln.setSpacing(4)

        self._lbl_ir_linha = QLabel("Ir para linha")
        self._btn_ir_linha = QPushButton("Ir")
        self._btn_ir_linha.setFixedWidth(40)
        self._btn_ir_linha.clicked.connect(self._ir_para_linha_inline)

        lay_ln.addWidget(self._lbl_ir_linha)
        lay_ln.addStretch()
        lay_ln.addWidget(self._btn_ir_linha)
        lay_modo.addWidget(self._secao_linha)

        self._barra_modo.hide()

    def _aplicar_tema_barra_modo(self):
        """Aplica cores do tema a _barra_modo."""
        t = tema_global()
        fundo = t.cor("interface.fundo_painel",   "#0F1210")
        borda = t.cor("interface.borda",           "#1f3d1f")
        texto = t.cor("interface.texto",           "#e8f5e8")
        fraco = t.cor("interface.texto_fraco",     "#5a7a5a")
        hover = t.cor("interface.fundo_item_hover","#1a3a1a")
        inpt  = t.cor("interface.inputs",          "#0d1a0d")
        self._barra_modo.setStyleSheet(
            f"QWidget#BarraModoOutline {{ background: {fundo}; border-bottom: 1px solid {borda}; }}"
            f"QPushButton {{ background: transparent; color: {fraco}; border: none;"
            f"  border-radius: 3px; padding: 0 4px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {hover}; color: {texto}; }}"
            f"QLabel {{ color: {fraco}; font-size: 11px; background: transparent; }}"
            f"QPlainTextEdit {{ background: {inpt}; color: {texto};"
            f"  border: 1px solid {borda}; border-radius: 3px;"
            f"  padding: 3px 6px; font-size: 11px; }}"
        )

    def _mostrar_barra_modo(self, qual: str):
        """Exibe a barra de modo mostrando apenas a secao relevante."""
        self._secao_sub.setVisible(qual == _MODO_SUBSTITUICAO)
        self._secao_linha.setVisible(qual == _MODO_LINHA)
        self._barra_modo.setVisible(qual in (_MODO_SUBSTITUICAO, _MODO_LINHA))

    # -- Busca e navegacao inline --

    # ⚠️  função grande (81 linhas)
    def _buscar_inline(self, termo: str, mover_cursor: bool = True):
        """Busca termo no arquivo atual; destaca no editor e preenche a arvore."""
        log.info(_ARQ, "_buscar_inline", f"termo='{termo}' mover_cursor={mover_cursor}")
        editor = self._editor_atual
        self._resultados_inline = []
        self._idx_inline = -1

        if not editor or not termo:
            self._limpar_destaques_inline()
            self._atualizar_contador_bc("0/0")
            self._arvore.clear()

            return

        flags = QTextDocument.FindFlags()
        if self._maiuscula_bc():
            flags |= QTextDocument.FindCaseSensitively

        fmt_normal, _ = self._fmts_busca_inline()

        doc = editor.document()
        cur = QTextCursor(doc)

        if self._regex_bc():
            rx = QRegularExpression(termo)
            if not self._maiuscula_bc():
                rx.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
            while True:
                cur = doc.find(rx, cur)
                if cur.isNull():
                    break
                self._resultados_inline.append(QTextCursor(cur))
        else:
            while True:
                cur = doc.find(termo, cur, flags)
                if cur.isNull():
                    break
                self._resultados_inline.append(QTextCursor(cur))

        selecoes = []
        for c in self._resultados_inline:
            sel = QTextEdit.ExtraSelection()
            sel.cursor = c
            sel.format = fmt_normal
            selecoes.append(sel)

        wave = [s for s in editor.extraSelections()
                if s.format.underlineStyle() == QTextCharFormat.WaveUnderline]
        editor.setExtraSelections(wave + selecoes)
        self._destaques_inline = selecoes

        total = len(self._resultados_inline)
        if total == 0:
            self._limpar_destaques_inline()
            self._atualizar_contador_bc("0/0")
            self._label_status.setText("Nenhum resultado.")
            self._label_status.show()
            self._arvore.clear()

            return

        self._label_status.hide()
        pos_atual = editor.textCursor().position()
        idx_prox = min(range(total),
                       key=lambda i: abs(self._resultados_inline[i].selectionStart() - pos_atual))
        self._idx_inline = idx_prox
        self._ir_para_inline(idx_prox, mover_cursor=mover_cursor)
        t = tema_global()
        self._arvore.clear()
        caminho  = getattr(editor, 'file_path', None) or ''
        nome_arq = os.path.basename(caminho) if caminho else 'arquivo atual'
        c_arquivo = t.cor("painel_outline.cor_arquivo", COR_OUTLINE_ARQUIVO)
        c_linha   = t.cor("painel_outline.cor_funcao",  COR_OUTLINE_FUNCAO)

        pai = ItemOutline(f"{nome_arq}  ({total})", caminho, 0, "arquivo")
        pai.setForeground(0, QColor(c_arquivo))
        for i, cur in enumerate(self._resultados_inline):
            num_linha = cur.blockNumber() + 1
            trecho    = cur.block().text().strip()[:80]
            filho     = ItemOutline(f"{num_linha}:  {trecho}", caminho, num_linha, "item", pai)
            filho.setForeground(0, QColor(c_linha))
        pai.setExpanded(True)
        self._arvore.addTopLevelItem(pai)

    def _rebuscar_inline(self):
        """Rebusca quando as opcoes Aa ou .* mudam."""
        janela = self.window()
        if not hasattr(janela, '_barra_central'):

            return

        termo = janela._barra_central.texto().strip()
        if termo and termo[0] not in ('@', '*', '#', '>', ':'):
            log.info(_ARQ, "_rebuscar_inline", f"rebusca automática (contentsChanged) termo='{termo}' — cursor NÃO deve mover")
            self._buscar_inline(termo, mover_cursor=False)

    def _proximo_inline(self):
        if not self._resultados_inline:

            return

        self._idx_inline = (self._idx_inline + 1) % len(self._resultados_inline)
        self._ir_para_inline(self._idx_inline)

    def _anterior_inline(self):
        if not self._resultados_inline:

            return

        self._idx_inline = (self._idx_inline - 1) % len(self._resultados_inline)
        self._ir_para_inline(self._idx_inline)

    def _ir_para_inline(self, idx: int, mover_cursor: bool = True):
        if not self._resultados_inline or not self._editor_atual:

            return

        cursor = self._resultados_inline[idx]
        log.info(_ARQ, "_ir_para_inline", f"idx={idx} mover_cursor={mover_cursor}")
        if mover_cursor:
            self._editor_atual.setTextCursor(cursor)
            self._editor_atual.ensureCursorVisible()
        total = len(self._resultados_inline)
        self._atualizar_contador_bc(f"{idx + 1}/{total}")
        self._atualizar_highlight_ativo_inline(idx)
        if self._arvore.topLevelItemCount() > 0:
            pai = self._arvore.topLevelItem(0)
            if idx < pai.childCount():
                self._arvore.blockSignals(True)
                self._arvore.setCurrentItem(pai.child(idx))
                self._arvore.scrollToItem(pai.child(idx))
                self._arvore.blockSignals(False)

    @staticmethod
    def _fmts_busca_inline():
        """Retorna (fmt_normal, fmt_ativo) derivando da cor editor.selecao do tema.

        Normal → mesma cor da seleção, alpha=60  (transparente, indica ocorrência)
        Ativo  → mesma cor da seleção, alpha=180 (mais forte, indica resultado atual)
        Fallback: COR_BUSCA_NORMAL definido em _CONFIGURA_/__init__.py
        """
        cor_hex = tema_global().dados().get("editor.selecao", COR_BUSCA_NORMAL)
        cor_base = QColor(cor_hex)
        r, g, b = cor_base.red(), cor_base.green(), cor_base.blue()
        fmt_normal = QTextCharFormat()
        fmt_normal.setBackground(QColor(r, g, b, 60))
        fmt_ativo = QTextCharFormat()
        fmt_ativo.setBackground(QColor(r, g, b, 180))

        return fmt_normal, fmt_ativo

    def _atualizar_highlight_ativo_inline(self, idx_ativo: int):
        editor = self._editor_atual
        if not editor or not self._resultados_inline:

            return

        fmt_normal, fmt_ativo = self._fmts_busca_inline()
        novas = []
        for i, cur in enumerate(self._resultados_inline):
            sel = QTextEdit.ExtraSelection()
            sel.cursor = QTextCursor(cur)
            sel.format = fmt_ativo if i == idx_ativo else fmt_normal
            novas.append(sel)
        wave = [s for s in editor.extraSelections()
                if s.format.underlineStyle() == QTextCharFormat.WaveUnderline]
        editor.setExtraSelections(wave + novas)
        self._destaques_inline = novas

    def _limpar_destaques_inline(self):
        if self._editor_atual:
            wave = [s for s in self._editor_atual.extraSelections()
                    if s.format.underlineStyle() == QTextCharFormat.WaveUnderline]
            self._editor_atual.setExtraSelections(wave)
        self._destaques_inline = []

    # -- EventFilter: Enter no _campo_sub dispara substituição --

    def eventFilter(self, obj, event): # 8.1 — clique no ícone ▼/▶ (zona direita do item, nos últimos 24px)
        if (hasattr(self, '_arvore')
                and obj is self._arvore.viewport()
                and event.type() == QEvent.MouseButtonPress
                and event.button() == Qt.LeftButton):
            item_ot = self._arvore.itemAt(event.pos())
            if item_ot and hasattr(item_ot, 'linha') and item_ot.linha > 0:
                rect_it = self._arvore.visualItemRect(item_ot)
                if event.x() >= rect_it.right() - 24:
                    estado = self._fold_estado(item_ot.linha)
                    if estado is not None:
                        self._toggle_fold_outline(item_ot)

                        return True  # consome — não navega para a linha

        if (hasattr(self, '_campo_sub') and obj is self._campo_sub
                and event.type() == QEvent.KeyPress):
            key  = event.key()
            mods = event.modifiers()
            if key in (Qt.Key_Return, Qt.Key_Enter):
                if mods & Qt.ShiftModifier:

                    return False   # Shift+Enter → nova linha normal

                # Enter sem Shift → substituir o resultado atual
                self._substituir_um_inline()

                return True

        return super().eventFilter(obj, event)

    # -- Substituicao inline --

    def _substituir_um_inline(self):
        if not self._resultados_inline or self._idx_inline < 0:

            return

        novo = self._campo_sub.toPlainText()
        self._resultados_inline[self._idx_inline].insertText(novo)
        self._rebuscar_inline()

    def _substituir_tudo_inline(self):
        if not self._resultados_inline:

            return

        novo = self._campo_sub.toPlainText()
        n    = len(self._resultados_inline)
        for cur in reversed(self._resultados_inline):
            cur.insertText(novo)
        janela = self.window()
        if hasattr(janela, 'statusBar'):
            janela.statusBar().showMessage(f"\u2714 {n} ocorrencia(s) substituida(s)", 3000)
        self._rebuscar_inline()

    # -- Ir para linha inline (:N) --

    def _ir_para_linha_inline(self):
        editor = self._editor_atual
        if not editor or not self._n_linha_destino:

            return

        if hasattr(editor, 'ir_para_linha'):
            editor.ir_para_linha(self._n_linha_destino)
        else:
            doc   = editor.document()
            bloco = doc.findBlockByLineNumber(max(0, self._n_linha_destino - 1))
            cur   = QTextCursor(bloco)
            editor.setTextCursor(cur)
            editor.centerCursor()
        editor.setFocus()
        self.desativar_modo_busca_inline()

    # -- Helpers para ler Aa/.* da BarraCentral e atualizar o contador --

    def _maiuscula_bc(self) -> bool:
        janela = self.window()
        if hasattr(janela, '_barra_central'):

            return janela._barra_central.maiuscula

        return False

    def _regex_bc(self) -> bool:
        janela = self.window()
        if hasattr(janela, '_barra_central'):

            return janela._barra_central.regex

        return False

    def _atualizar_contador_bc(self, texto: str):
        janela = self.window()
        if hasattr(janela, '_barra_central'):
            janela._barra_central.atualizar_contador(texto)

    def _rebuscar_inline_sem_args(self, *args):
        """Slot generico para reconectar sinais com argumento da BarraCentral."""
        self._rebuscar_inline()

    # -- Conexao e desconexao dos sinais da BarraCentral --

    # ⚠️  except genérico vazio
    def _conectar_barra_central(self, modo: str):
        """Conecta os sinais relevantes da BarraCentral para o modo dado."""
        janela = self.window()
        if not hasattr(janela, '_barra_central'):

            return

        bc = janela._barra_central
        self._desconectar_barra_central_safe(bc)
        try:
            bc.proximo.connect(self._proximo_inline)
            bc.anterior.connect(self._anterior_inline)
            bc._chk_maiuscula.stateChanged.connect(self._rebuscar_inline_sem_args)
            bc._chk_regex.stateChanged.connect(self._rebuscar_inline_sem_args)
            if modo == "substituicao":
                bc.substituir_um.connect(self._substituir_um_inline)
                bc.substituir_tudo.connect(self._substituir_tudo_inline)
        except Exception:
            pass

    def _desconectar_barra_central_safe(self, bc):
        """Desconecta todos os sinais do outline desta BarraCentral com seguranca."""
        for sinal, slot in [
            (bc.proximo,        self._proximo_inline),
            (bc.anterior,       self._anterior_inline),
            (bc._chk_maiuscula.stateChanged, self._rebuscar_inline_sem_args),
            (bc._chk_regex.stateChanged,     self._rebuscar_inline_sem_args),
            (bc.substituir_um,  self._substituir_um_inline),
            (bc.substituir_tudo, self._substituir_tudo_inline),
        ]:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    sinal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass

    @staticmethod
    def _formatar_args(args: ast.arguments) -> str:
        nomes = [arg.arg for arg in args.args]
        if args.vararg:
            nomes.append(f"*{args.vararg.arg}")
        if args.kwarg:
            nomes.append(f"**{args.kwarg.arg}")

        return ", ".join(nomes)
