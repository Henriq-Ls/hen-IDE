# 📁 _TERMINAIS_/json_explorer.py
"""
JSON Explorer — visualiza estrutura de dicts/JSON e gera código pronto.
Ativado automaticamente pelo RunOutputWidget quando detecta JSON no output.
"""
import ast
import json
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QPlainTextEdit,
    QLabel, QPushButton, QApplication, QLineEdit,
    QMenu, QFileDialog, QDialog, QScrollArea,
    QGridLayout, QColorDialog, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui  import QFont, QColor, QTextCursor, QPainter
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import (
    FONTE_MONO, COR_FALLBACK, COR_INFO, COR_OUTLINE_CHAVE_JSON,
    COR_OUTLINE_OBJETO_JSON, COR_SINTAXE_PALAVRA_CHAVE, COR_OUTLINE_CLASSE,
    COR_OUTLINE_PASTA, COR_SINTAXE_NUMERO,
)
# ── Regex para detectar cor hex ───────────────────────────────────────
_RE_HEX = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')

def _is_cor(valor: str) -> bool:

    return bool(_RE_HEX.match(str(valor).strip()))

def _cores_do_projeto() -> list[tuple[str, str]]:
    """
    Lê as constantes de cor do _CONFIGURA_/__init__.py e retorna
    lista de (nome, hex). Só retorna as que são hex válidas.
    """
    try:
        from _CONFIGURA_ import __file__ as cfg_file
        import importlib, _CONFIGURA_ as cfg_mod
        pares = []
        for nome in dir(cfg_mod):
            if nome.startswith('_'):
                continue
            val = getattr(cfg_mod, nome)
            if isinstance(val, str) and _is_cor(val):
                pares.append((nome, val))

        return pares

    except Exception:

        return []

# ═════════════════════════════════════════════════════════════════════
# Diálogo de seleção de cor
# ═════════════════════════════════════════════════════════════════════

class _ColorPickerDialog(QDialog):
    """
    Janela com:
    - Preview da cor atual
    - Grade com cores do projeto (só aparece se existirem)
    - Botão para abrir o color picker nativo do Qt
    - Confirmar / Cancelar
    """
    cor_escolhida = Signal(str)   # hex string ex: "#4ec994"

    def __init__(self, cor_atual: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Escolher Cor")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setFixedWidth(420)
        self._cor = cor_atual.strip()
        self._construir_ui()
        self._aplicar_tema()

    # ⚠️  função grande (115 linhas)
    def _construir_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # ── Título ────────────────────────────────────────────────────
        tit = QLabel("● Escolher Cor")
        tit.setStyleSheet(
            "font-size:12px; font-weight:bold; font-family:Consolas; color:#e0e0e0;"
        )
        lay.addWidget(tit)

        # ── Preview + hex input ───────────────────────────────────────
        row_prev = QHBoxLayout()
        self._preview = QFrame()
        self._preview.setFixedSize(40, 40)
        self._preview.setStyleSheet(
            f"background:{self._cor}; border:1px solid #444; border-radius:4px;"
        )
        row_prev.addWidget(self._preview)

        self._inp_hex = QLineEdit(self._cor)
        self._inp_hex.setFixedHeight(28)
        self._inp_hex.setStyleSheet("""
            QLineEdit {
                background:#1a1a1a; color:#e0e0e0;
                border:1px solid #444; border-radius:3px;
                padding:2px 8px; font-family:Consolas; font-size:12px;
            }
        """)
        self._inp_hex.textChanged.connect(self._ao_digitar_hex)
        row_prev.addWidget(self._inp_hex, 1)

        btn_picker = QPushButton("⬛ Picker")
        btn_picker.setFixedHeight(28)
        btn_picker.setStyleSheet("""
            QPushButton {
                background:#2a2a2a; color:#aaa;
                border:1px solid #444; border-radius:3px;
                padding:2px 10px; font-size:10px;
            }
            QPushButton:hover { background:#3a3a2a; color:#e0e0e0; }
        """)
        btn_picker.clicked.connect(self._abrir_picker_nativo)
        row_prev.addWidget(btn_picker)
        lay.addLayout(row_prev)

        # ── Cores do projeto ──────────────────────────────────────────
        cores = _cores_do_projeto()
        if cores:
            sep = QLabel("Cores do projeto:")
            sep.setStyleSheet("font-size:10px; color:#666; font-family:Consolas;")
            lay.addWidget(sep)

            scroll = QScrollArea()
            scroll.setFixedHeight(160)
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")

            grid_w = QWidget()
            grid = QGridLayout(grid_w)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(4)

            cols = 10
            for idx, (nome, hex_val) in enumerate(cores):
                btn = QPushButton()
                btn.setFixedSize(28, 28)
                btn.setToolTip(f"{nome}\n{hex_val}")
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background:{hex_val};
                        border:1px solid #333;
                        border-radius:3px;
                    }}
                    QPushButton:hover {{
                        border:2px solid #e0e0e0;
                    }}
                """)
                btn.clicked.connect(lambda _, h=hex_val: self._selecionar(h))
                grid.addWidget(btn, idx // cols, idx % cols)

            scroll.setWidget(grid_w)
            lay.addWidget(scroll)

        # ── Botões OK / Cancelar ──────────────────────────────────────
        row_btns = QHBoxLayout()
        row_btns.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setFixedHeight(26)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background:#2a2a2a; color:#888;
                border:1px solid #444; border-radius:3px;
                padding:2px 14px; font-size:10px;
            }
            QPushButton:hover { color:#e0e0e0; }
        """)
        btn_cancel.clicked.connect(self.reject)
        row_btns.addWidget(btn_cancel)

        btn_ok = QPushButton("Confirmar")
        btn_ok.setFixedHeight(26)
        btn_ok.setStyleSheet("""
            QPushButton {
                background:#1a3a1a; color:#98c379;
                border:none; border-radius:3px;
                padding:2px 14px; font-size:10px;
            }
            QPushButton:hover { background:#264f28; }
        """)
        btn_ok.clicked.connect(self._confirmar)
        row_btns.addWidget(btn_ok)
        lay.addLayout(row_btns)

    def _aplicar_tema(self):
        self.setStyleSheet("""
            QDialog {
                background:#111111;
                border:1px solid #333;
                border-radius:6px;
            }
        """)

    def _ao_digitar_hex(self, texto: str):
        texto = texto.strip()
        if _is_cor(texto):
            self._cor = texto
            self._preview.setStyleSheet(
                f"background:{texto}; border:1px solid #444; border-radius:4px;"
            )

    def _selecionar(self, hex_val: str):
        self._cor = hex_val
        self._inp_hex.setText(hex_val)
        self._preview.setStyleSheet(
            f"background:{hex_val}; border:1px solid #444; border-radius:4px;"
        )

    def _abrir_picker_nativo(self):
        cor = QColorDialog.getColor(QColor(self._cor), self, "Escolher Cor")
        if cor.isValid():
            self._selecionar(cor.name())

    def _confirmar(self):
        if _is_cor(self._cor):
            self.cor_escolhida.emit(self._cor)
            self.accept()

# ═════════════════════════════════════════════════════════════════════
# Funções auxiliares
# ═════════════════════════════════════════════════════════════════════

# ⚠️  except genérico vazio
def _parsear(texto: str):
    texto = texto.strip()
    try:

        return json.loads(texto)

    except Exception:
        pass
    try:

        return ast.literal_eval(texto)

    except Exception:
        pass
    try:
        limpo = re.sub(r'//[^\n]*', '', texto)
        limpo = re.sub(r',\s*([}\]])', r'\1', limpo)

        return json.loads(limpo)

    except Exception:

        return None

def _extrair_json_do_output(texto: str):
    linhas = texto.splitlines()
    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue
        if linha.startswith("{") or linha.startswith("["):
            dados = _parsear(linha)
            if dados is not None:

                return dados, linha

    dados = _parsear(texto)
    if dados is not None:

        return dados, texto

    for inicio in ('{', '['):
        i = texto.find(inicio)
        if i == -1:
            continue
        for j in range(len(texto), i, -1):
            trecho = texto[i:j]
            dados = _parsear(trecho)
            if dados is not None:

                return dados, trecho

    return None, None

# 💡 caminho_opc = Literal["data"] ← defina os valores válidos
def _gerar_codigo(dados, caminho="data", indent=0) -> list[str]:
    linhas = []
    esp = "    " * indent
    if isinstance(dados, dict):
        for k, v in dados.items():
            novo = f"{caminho}['{k}']"
            if isinstance(v, (dict, list)):
                linhas += _gerar_codigo(v, novo, indent)
            else:
                nome_var = str(k).replace("-", "_").replace(" ", "_")
                linhas.append(f"{esp}{nome_var} = {novo}")
    elif isinstance(dados, list):
        linhas.append(f"{esp}for i, item in enumerate({caminho}):")
        if dados:
            linhas += _gerar_codigo(dados[0], "item", indent + 1)

    return linhas

# 💡 chave_opc = Literal["raiz"] ← defina os valores válidos
def _popular_arvore(pai, dados, chave="raiz"):
    if isinstance(dados, dict):
        label = f"{chave}  —  {len(dados)} chaves"
        no = QTreeWidgetItem([label, "dict", ""])
        no.setForeground(0, tema_global().qcolor("painel_outline.cor_classe", COR_OUTLINE_CLASSE))
        no.setData(0, Qt.UserRole + 1, dados)
        for k, v in dados.items():
            _popular_arvore(no, v, str(k))
    elif isinstance(dados, list):
        label = f"{chave}  —  {len(dados)} itens"
        no = QTreeWidgetItem([label, "list", ""])
        no.setForeground(0, tema_global().qcolor("editor.git_modificado", COR_OUTLINE_OBJETO_JSON))
        no.setData(0, Qt.UserRole + 1, dados)
        for i, v in enumerate(dados[:50]):
            _popular_arvore(no, v, f"[{i}]")
    else:
        tipo  = type(dados).__name__
        valor = str(dados)[:120]
        no = QTreeWidgetItem([chave, tipo, valor])
        cores = {
            "str": COR_OUTLINE_CHAVE_JSON, "int": COR_SINTAXE_NUMERO, "float": COR_SINTAXE_NUMERO,
            "bool": COR_SINTAXE_PALAVRA_CHAVE, "NoneType": COR_OUTLINE_PASTA
        }
        no.setForeground(2, QColor(cores.get(tipo, "#abb2bf")))
        no.setData(0, Qt.UserRole, chave)
        no.setData(0, Qt.UserRole + 1, dados)

        # Se o valor for cor hex, colore o fundo da célula de valor
        if _is_cor(valor):
            cor = QColor(valor)
            no.setBackground(2, cor)
            lum = 0.299*cor.red() + 0.587*cor.green() + 0.114*cor.blue()
            no.setForeground(2, QColor("#000000" if lum > 128 else "#ffffff"))

    if pai is not None:
        pai.addChild(no)

    return no

# ═════════════════════════════════════════════════════════════════════
# Widget principal
# ═════════════════════════════════════════════════════════════════════

class JsonExplorer(QWidget):
    abrir_no_editor = Signal(str)
    # ── NOVO: emite (caminho_arquivo, conteudo_json) para quem salva ──
    json_salvar     = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dados        = None
        self._texto_json   = ""   # JSON cru original (como foi recebido)
        self._arquivo_origem = ""  # caminho do arquivo de origem, se conhecido
        self._caminhos     = {}
        self._historico    = []
        self._hist_idx     = -1
        self._construir_ui()
        self._aplicar_tema()

    # ⚠️  função grande (153 linhas)
    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Cabeçalho ─────────────────────────────────────────────────
        cab = QWidget()
        cab.setFixedHeight(30)
        lay_cab = QHBoxLayout(cab)
        lay_cab.setContentsMargins(10, 0, 8, 0)
        lay_cab.setSpacing(6)

        self._btn_voltar = QPushButton("←")
        self._btn_voltar.setFixedSize(22, 22)
        self._btn_voltar.setToolTip("JSON anterior")
        self._btn_voltar.setFlat(True)
        self._btn_voltar.clicked.connect(self._historico_voltar)
        lay_cab.addWidget(self._btn_voltar)

        self._btn_avancar = QPushButton("→")
        self._btn_avancar.setFixedSize(22, 22)
        self._btn_avancar.setToolTip("JSON seguinte")
        self._btn_avancar.setFlat(True)
        self._btn_avancar.clicked.connect(self._historico_avancar)
        lay_cab.addWidget(self._btn_avancar)

        self._lbl_info = QLabel("{ } JSON Explorer")
        self._lbl_info.setStyleSheet(
            f"font-size:11px;font-weight:bold;font-family:'{FONTE_MONO}','Consolas',monospace;"
        )
        lay_cab.addWidget(self._lbl_info)
        lay_cab.addStretch()

        self._campo_busca = QLineEdit()
        self._campo_busca.setPlaceholderText("buscar chave...")
        self._campo_busca.setFixedWidth(160)
        self._campo_busca.setFixedHeight(22)
        self._campo_busca.textChanged.connect(self._filtrar_arvore)
        lay_cab.addWidget(self._campo_busca)

        self._lbl_dica = QLabel("clique numa chave para copiar o caminho")
        self._lbl_dica.setStyleSheet("font-size: 10px;")
        lay_cab.addWidget(self._lbl_dica)

        # ── Botão: Salvar no arquivo de origem ────────────────────────
        self._btn_salvar_origem = QPushButton("⬆ Salvar no arquivo")
        self._btn_salvar_origem.setFixedHeight(22)
        self._btn_salvar_origem.setToolTip("Sobrescreve o arquivo JSON de origem com as edições")
        self._btn_salvar_origem.setStyleSheet("""
            QPushButton { background:#3a1a3a; color:#c678dd; border:none;
                padding:2px 10px; font-size:10px; border-radius:3px; }
            QPushButton:hover { background:#4f2860; }
            QPushButton:disabled { background:#1a1a1a; color:#444; }
        """)
        self._btn_salvar_origem.clicked.connect(self._salvar_no_arquivo_origem)
        self._btn_salvar_origem.setEnabled(False)  # ativa só quando há caminho

        # ── Botão: Copiar JSON original ───────────────────────────────
        btn_copiar_original = QPushButton("Copiar original")
        btn_copiar_original.setFixedHeight(22)
        btn_copiar_original.setToolTip("Copia o JSON cru como foi recebido, sem edições")
        btn_copiar_original.setStyleSheet("""
            QPushButton { background:#2a2a1a; color:#e5c07b; border:none;
                padding:2px 10px; font-size:10px; border-radius:3px; }
            QPushButton:hover { background:#3a3a20; }
        """)
        btn_copiar_original.clicked.connect(self._copiar_json_original)

        # ── Botão: Copiar JSON editado ────────────────────────────────
        btn_copiar_editado = QPushButton("Copiar editado")
        btn_copiar_editado.setFixedHeight(22)
        btn_copiar_editado.setToolTip("Copia o JSON atual com todas as edições feitas")
        btn_copiar_editado.setStyleSheet("""
            QPushButton { background:#1a2a3a; color:#61afef; border:none;
                padding:2px 10px; font-size:10px; border-radius:3px; }
            QPushButton:hover { background:#1e3a50; }
        """)
        btn_copiar_editado.clicked.connect(self._copiar_json_editado)

        # ── Botão: Salvar JSON (dialog) ───────────────────────────────
        btn_salvar = QPushButton("Salvar JSON")
        btn_salvar.setFixedHeight(22)
        btn_salvar.setStyleSheet("""
            QPushButton { background:#1a2a1a; color:#98c379; border:none;
                padding:2px 10px; font-size:10px; border-radius:3px; }
            QPushButton:hover { background:#264f28; }
        """)
        btn_salvar.clicked.connect(self._salvar_json)

        btn_editor = QPushButton("Abrir no Editor")
        btn_editor.setFixedHeight(22)
        btn_editor.setStyleSheet("""
            QPushButton { background:#1a3a5f; color:#61afef; border:none;
                padding:2px 10px; font-size:10px; border-radius:3px; }
            QPushButton:hover { background:#264f78; }
        """)
        btn_editor.clicked.connect(self._ao_abrir_no_editor)

        btn_copiar = QPushButton("Copiar código")
        btn_copiar.setFixedHeight(22)
        btn_copiar.setStyleSheet("""
            QPushButton { background:#1a3a1a; color:#98c379; border:none;
                padding:2px 10px; font-size:10px; border-radius:3px; }
            QPushButton:hover { background:#264f28; }
        """)
        btn_copiar.clicked.connect(self._copiar_codigo)

        layout.addWidget(cab)

        # ── Splitter: árvore | código | botões ──────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        self._arvore = QTreeWidget()
        self._arvore.setHeaderLabels(["Chave", "Tipo", "Valor"])
        self._arvore.setColumnWidth(0, 200)
        self._arvore.setColumnWidth(1, 65)
        self._arvore.setAnimated(True)
        self._arvore.setIndentation(14)
        self._arvore.setContextMenuPolicy(Qt.CustomContextMenu)
        self._arvore.itemClicked.connect(self._ao_clicar_chave)
        self._arvore.itemDoubleClicked.connect(self._ao_duplo_clique)
        self._arvore.customContextMenuRequested.connect(self._menu_contexto)
        self._arvore.currentItemChanged.connect(self._ao_selecionar_item)
        splitter.addWidget(self._arvore)

        self._codigo = QPlainTextEdit()
        self._codigo.setReadOnly(True)
        self._codigo.setFont(QFont(FONTE_MONO, 11))
        self._codigo.setLineWrapMode(QPlainTextEdit.NoWrap)
        splitter.addWidget(self._codigo)

        # ── Coluna de botões (à direita do código) ──────────────────────
        col_botoes = QWidget()
        lay_botoes = QVBoxLayout(col_botoes)
        lay_botoes.setContentsMargins(6, 6, 6, 6)
        lay_botoes.setSpacing(6)
        lay_botoes.addWidget(self._btn_salvar_origem)
        lay_botoes.addWidget(btn_copiar_original)
        lay_botoes.addWidget(btn_copiar_editado)
        lay_botoes.addWidget(btn_salvar)
        lay_botoes.addWidget(btn_editor)
        lay_botoes.addWidget(btn_copiar)
        lay_botoes.addStretch()
        splitter.addWidget(col_botoes)

        splitter.setSizes([380, 380, 130])
        layout.addWidget(splitter, 1)

        # ── Rodapé ─────────────────────────────────────────────────────
        self._rodape = QLabel("")
        self._rodape.setFixedHeight(20)
        self._rodape.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._rodape)

    # ⚠️  função grande (54 linhas)
    def _aplicar_tema(self):
        t       = tema_global()
        fundo   = t.cor("terminal.fundo",             "#0d0d0d")
        texto   = t.cor("editor.texto",               "#e0e0e0")
        borda   = t.cor("interface.borda",            "#222222")
        fraco   = t.cor("editor.numero_linha",        "#666666")
        hover   = t.cor("interface.fundo_item_hover", "#1a1a2e")
        selecao = t.cor("editor.selecao",             "#264f78")

        self.setStyleSheet(f"background:{fundo};")
        self._lbl_info.setStyleSheet(
            f"font-size:11px;font-weight:bold;font-family:Consolas;color:{texto};"
        )
        self._lbl_dica.setStyleSheet(f"font-size:10px;color:{fraco};")
        self._rodape.setStyleSheet(
            f"font-size:10px;padding-right:8px;color:{fraco};"
        )
        self._campo_busca.setStyleSheet(f"""
            QLineEdit {{
                background:{hover}; color:{texto};
                border:1px solid {borda}; border-radius:3px;
                padding:2px 6px; font-size:10px; font-family:Consolas;
            }}
        """)
        nav = f"""
            QPushButton {{
                background:transparent; color:{fraco};
                border:none; font-size:13px; font-weight:bold;
            }}
            QPushButton:hover {{ color:{texto}; }}
        """
        self._btn_voltar.setStyleSheet(nav)
        self._btn_avancar.setStyleSheet(nav)
        self._arvore.setStyleSheet(f"""
            QTreeWidget {{
                background:{fundo}; color:{texto};
                border:none; font-family:Consolas; font-size:11px;
            }}
            QTreeWidget::item {{ padding:2px; }}
            QTreeWidget::item:hover    {{ background:{hover}; }}
            QTreeWidget::item:selected {{ background:{selecao}; }}
            QHeaderView::section {{
                background:{fundo}; color:{fraco};
                border:none; border-bottom:1px solid {borda};
                font-size:10px; padding:2px 4px;
            }}
        """)
        self._codigo.setStyleSheet(f"""
            QPlainTextEdit {{
                background:{fundo}; color:{texto};
                border:none; border-left:1px solid {borda};
                font-family:Consolas; font-size:11px;
            }}
        """)

    # ── API pública ────────────────────────────────────────────────────

    def carregar(self, texto: str, arquivo_origem: str = ""):
        """
        Carrega JSON a partir de texto.
        arquivo_origem: caminho do arquivo de origem (opcional).
        Se fornecido, habilita o botão "Salvar no arquivo".
        """
        dados, trecho = _extrair_json_do_output(texto)
        if dados is None:
            self._lbl_info.setText("{ } JSON Explorer  —  nenhum JSON encontrado")

            return

        # Atualiza caminho de origem
        if arquivo_origem:
            self._arquivo_origem = arquivo_origem
            self._btn_salvar_origem.setEnabled(True)
            nome = arquivo_origem.split("/")[-1].split("\\")[-1]
            self._btn_salvar_origem.setToolTip(f"Sobrescrever {nome} com as edições")

        if not self._historico or self._historico[self._hist_idx][0] != dados:
            self._historico = self._historico[:self._hist_idx + 1]
            self._historico.append((dados, trecho))
            self._hist_idx = len(self._historico) - 1
        self._carregar_dados(dados, trecho)

    def carregar_arquivo(self, caminho: str):
        """Carrega JSON diretamente de um arquivo .json no disco."""
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                texto = f.read()
            self.carregar(texto, arquivo_origem=caminho)
        except Exception as e:
            self._lbl_info.setText(f"{{}} JSON Explorer  —  erro ao ler: {e}")

    def _carregar_dados(self, dados, trecho):
        self._dados      = dados
        self._texto_json = trecho  # guarda o original cru
        self._arvore.clear()
        self._campo_busca.clear()

        raiz = _popular_arvore(None, dados)
        self._arvore.addTopLevelItem(raiz)
        raiz.setExpanded(True)

        total = self._contar_folhas(dados)
        tipo  = type(dados).__name__
        self._lbl_info.setText(
            f"{{ }} JSON Explorer  —  {tipo}  —  {total} chaves"
        )
        self._rodape.setText(f"{total} chaves encontradas")

        linhas = ["# === CÓDIGO GERADO AUTOMATICAMENTE ===",
                  "data = response.json()", ""]
        linhas += _gerar_codigo(dados)
        self._codigo.setPlainText("\n".join(linhas))
        self._atualizar_botoes_historico()

    # ── Salvar no arquivo de origem (via signal) ───────────────────────

    def _salvar_no_arquivo_origem(self):
        """
        Emite json_salvar(caminho, conteudo) para o componente pai salvar.
        Também tenta salvar direto se o caminho existir e for acessível.
        """
        if not self._dados or not self._arquivo_origem:

            return

        conteudo = json.dumps(self._dados, ensure_ascii=False, indent=2)

        # Emite signal para o pai (ex: RunOutputWidget) tratar
        self.json_salvar.emit(self._arquivo_origem, conteudo)

        # Também salva diretamente (a IDE pode já ter permissão)
        try:
            with open(self._arquivo_origem, "w", encoding="utf-8") as f:
                f.write(conteudo)
            nome = self._arquivo_origem.split("/")[-1].split("\\")[-1]
            self._notificar(f"✓ {nome} atualizado", COR_OUTLINE_CHAVE_JSON)
        except Exception as e:
            self._notificar(f"⚠ signal emitido — salvar via editor ({e})", COR_OUTLINE_OBJETO_JSON)

    # ── Copiar JSON original (cru, como recebeu) ───────────────────────

    def _copiar_json_original(self):
        if not self._texto_json:

            return

        QApplication.clipboard().setText(self._texto_json)
        self._notificar("✓ JSON original copiado", COR_OUTLINE_OBJETO_JSON)

    # ── Copiar JSON editado (estado atual com todas as mudanças) ───────

    def _copiar_json_editado(self):
        if not self._dados:

            return

        conteudo = json.dumps(self._dados, ensure_ascii=False, indent=2)
        QApplication.clipboard().setText(conteudo)
        self._notificar("✓ JSON editado copiado", COR_INFO)

    # ── Notificação no rodapé com auto-reset ──────────────────────────

    def _notificar(self, msg: str, cor: str = COR_FALLBACK, duracao_ms: int = 3000):
        self._rodape.setText(msg)
        self._rodape.setStyleSheet(
            f"font-size:10px; padding-right:8px; color:{cor}; font-weight:bold;"
        )
        QTimer.singleShot(duracao_ms, self._resetar_rodape)

    def _resetar_rodape(self):
        t = tema_global()
        fraco = t.cor("editor.numero_linha", "#666666")
        total = self._contar_folhas(self._dados) if self._dados else 0
        self._rodape.setText(f"{total} chaves encontradas")
        self._rodape.setStyleSheet(
            f"font-size:10px; padding-right:8px; color:{fraco};"
        )

    # ── Busca ──────────────────────────────────────────────────────────

    def _filtrar_arvore(self, termo: str):
        termo = termo.strip().lower()
        raiz = self._arvore.topLevelItem(0)
        if not raiz:

            return

        if not termo:
            self._mostrar_todos(raiz)
            raiz.setExpanded(True)

            return

        self._filtrar_no(raiz, termo)

    def _filtrar_no(self, item: QTreeWidgetItem, termo: str) -> bool:
        chave = item.text(0).split("  —  ")[0].strip().lower()
        valor = item.text(2).lower()
        bate  = termo in chave or termo in valor
        filho_visivel = False
        for i in range(item.childCount()):
            if self._filtrar_no(item.child(i), termo):
                filho_visivel = True
        visivel = bate or filho_visivel
        item.setHidden(not visivel)
        if filho_visivel:
            item.setExpanded(True)

        return visivel

    def _mostrar_todos(self, item: QTreeWidgetItem):
        item.setHidden(False)
        for i in range(item.childCount()):
            self._mostrar_todos(item.child(i))

    # ── Menu de contexto ───────────────────────────────────────────────

    def _menu_contexto(self, pos):
        item = self._arvore.itemAt(pos)
        if not item:

            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background:#1a1a1a; color:#e0e0e0;
                border:1px solid #333; font-size:10px; font-family:Consolas;
            }
            QMenu::item:selected { background:#264f78; }
        """)

        caminho = self._montar_caminho(item)
        valor   = item.data(0, Qt.UserRole + 1)

        menu.addAction("Copiar caminho",
            lambda: self._copiar_e_exibir(caminho, f"copiado: {caminho}"))
        menu.addAction("Copiar valor",
            lambda: self._copiar_e_exibir(str(valor), "valor copiado"))
        menu.addAction("Copiar como JSON",
            lambda: self._copiar_e_exibir(
                json.dumps(valor, ensure_ascii=False, indent=2), "JSON copiado"))

        # Opção de cor só aparece se o valor for hex
        if isinstance(valor, str) and _is_cor(valor):
            menu.addSeparator()
            menu.addAction("🎨  Trocar cor...",
                lambda: self._abrir_color_picker(item, valor))

        menu.exec(self._arvore.viewport().mapToGlobal(pos))

    def _copiar_e_exibir(self, texto: str, msg: str):
        QApplication.clipboard().setText(texto)
        self._lbl_dica.setText(msg)

    # ── Color Picker ───────────────────────────────────────────────────

    def _abrir_color_picker(self, item: QTreeWidgetItem, cor_atual: str):
        dlg = _ColorPickerDialog(cor_atual, self)
        dlg.cor_escolhida.connect(lambda nova: self._aplicar_nova_cor(item, nova))
        dlg.exec()

    def _aplicar_nova_cor(self, item: QTreeWidgetItem, nova_cor: str):
        """Atualiza o item na árvore e o dado interno."""
        item.setText(2, nova_cor)

        cor = QColor(nova_cor)
        item.setBackground(2, cor)
        lum = 0.299*cor.red() + 0.587*cor.green() + 0.114*cor.blue()
        item.setForeground(2, QColor("#000000" if lum > 128 else "#ffffff"))

        caminho = self._montar_caminho(item)
        self._atualizar_dado_por_caminho(caminho, nova_cor)

        linhas = ["# === CÓDIGO GERADO AUTOMATICAMENTE ===",
                  "data = response.json()", ""]
        linhas += _gerar_codigo(self._dados)
        self._codigo.setPlainText("\n".join(linhas))
        self._notificar(f"cor alterada → {nova_cor}", COR_SINTAXE_PALAVRA_CHAVE)

    # ── Duplo clique: editar valor ─────────────────────────────────────

    def _ao_duplo_clique(self, item: QTreeWidgetItem, coluna: int):
        if item.childCount() > 0:

            return

        valor = item.data(0, Qt.UserRole + 1)
        if coluna == 2 and isinstance(valor, str) and _is_cor(valor):
            self._abrir_color_picker(item, valor)

            return

        if coluna != 2:

            return

        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self._arvore.editItem(item, 2)
        self._arvore.itemChanged.connect(self._ao_editar_valor)

    def _ao_editar_valor(self, item: QTreeWidgetItem, coluna: int):
        self._arvore.itemChanged.disconnect(self._ao_editar_valor)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        caminho  = self._montar_caminho(item)
        novo_val = item.text(2)
        self._atualizar_dado_por_caminho(caminho, novo_val)
        linhas = ["# === CÓDIGO GERADO AUTOMATICAMENTE ===",
                  "data = response.json()", ""]
        linhas += _gerar_codigo(self._dados)
        self._codigo.setPlainText("\n".join(linhas))

    def _atualizar_dado_por_caminho(self, caminho: str, valor: str):
        try:
            valor_conv = json.loads(valor)
        except Exception:
            valor_conv = valor
        partes = re.findall(r"\['(.+?)'\]|\[(\d+)\]", caminho)
        ref = self._dados
        for k_str, k_int in partes[:-1]:
            k = k_str if k_str else int(k_int)
            ref = ref[k]
        if partes:
            k_str, k_int = partes[-1]
            k = k_str if k_str else int(k_int)
            ref[k] = valor_conv

    # ── Highlight no código ────────────────────────────────────────────

    def _ao_selecionar_item(self, item: QTreeWidgetItem, _anterior):
        if not item:

            return

        chave = item.text(0).split("  —  ")[0].strip()
        linhas = self._codigo.toPlainText().splitlines()
        for i, linha in enumerate(linhas):
            if f"['{chave}']" in linha or f"[{chave}]" in linha:
                cursor = self._codigo.textCursor()
                cursor.movePosition(QTextCursor.Start)
                for _ in range(i):
                    cursor.movePosition(QTextCursor.NextBlock)
                cursor.select(QTextCursor.LineUnderCursor)
                self._codigo.setTextCursor(cursor)
                self._codigo.ensureCursorVisible()
                break

    # ── Histórico ──────────────────────────────────────────────────────

    def _historico_voltar(self):
        if self._hist_idx > 0:
            self._hist_idx -= 1
            self._carregar_dados(*self._historico[self._hist_idx])

    def _historico_avancar(self):
        if self._hist_idx < len(self._historico) - 1:
            self._hist_idx += 1
            self._carregar_dados(*self._historico[self._hist_idx])

    def _atualizar_botoes_historico(self):
        self._btn_voltar.setEnabled(self._hist_idx > 0)
        self._btn_avancar.setEnabled(self._hist_idx < len(self._historico) - 1)

    # ── Salvar JSON (dialog) ───────────────────────────────────────────

    def _salvar_json(self):
        if not self._dados:

            return

        # IMP-11: lembra a ultima pasta usada para exportar JSON deste painel
        import os
        from PySide6.QtCore import QSettings
        _settings = QSettings("hein", "hein_IDE")
        _dir_inicial = _settings.value("ultima_pasta_salvar_json_explorer", "")
        _sugestao = os.path.join(_dir_inicial, "dados.json") if _dir_inicial else "dados.json"
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar JSON", _sugestao, "JSON (*.json)"
        )
        if caminho:
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(self._dados, f, ensure_ascii=False, indent=2)
            _settings.setValue("ultima_pasta_salvar_json_explorer", os.path.dirname(caminho))
            self._notificar(f"✓ salvo em {caminho}", COR_OUTLINE_CHAVE_JSON)

    # ── Internos ───────────────────────────────────────────────────────

    def _ao_clicar_chave(self, item: QTreeWidgetItem, coluna: int):
        caminho = self._montar_caminho(item)
        QApplication.clipboard().setText(caminho)
        self._lbl_dica.setText(f"copiado: {caminho}")

    def _montar_caminho(self, item: QTreeWidgetItem) -> str:
        partes = []
        atual  = item
        while atual is not None:
            texto = atual.text(0).split("  —  ")[0].strip()
            partes.append(texto)
            atual = atual.parent()
        partes.reverse()
        if partes and partes[0] == "raiz":
            partes = partes[1:]
        caminho = "data"
        for p in partes:
            if p.startswith("[") and p.endswith("]"):
                caminho += p
            else:
                caminho += f"['{p}']"

        return caminho

    def _copiar_codigo(self):
        QApplication.clipboard().setText(self._codigo.toPlainText())
        self._notificar("código copiado!", COR_OUTLINE_CHAVE_JSON)

    def _ao_abrir_no_editor(self):
        self.abrir_no_editor.emit(self._codigo.toPlainText())

    @staticmethod
    def _contar_folhas(dados) -> int:
        if isinstance(dados, dict):

            return sum(JsonExplorer._contar_folhas(v) for v in dados.values())

        elif isinstance(dados, list):

            return sum(JsonExplorer._contar_folhas(v) for v in dados)

        return 1
