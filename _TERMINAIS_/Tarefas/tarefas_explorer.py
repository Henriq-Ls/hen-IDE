# 📁 _TERMINAIS_/Tarefas/tarefas_explorer.py
"""
TarefasExplorer — painel visual para edição de tarefas F2-F10.

Cada tarefa é um card expansível com:
  ─ Cabeçalho (sempre visível):
      [▼/▲]  [ComboBox atalho]  [nome]  ─────────  [▶ executar]  [✕ remover]
  ─ Corpo (expandido):
      Árvore real estilo file-tree (VS Code):
        F2 — nome
         │
         ├─▸ Executar um comando        (colapsado)
         ├─▾ Arquivo Python (.py)       (expandido → mostra campos recuados)
         │     │
         │     ├─ Arquivo: ...
         │     └─ Argumentos: ...
         ├─▸ Arquivo PowerShell (.ps1)  (colapsado)
         └─▸ Abrir pasta                (colapsado)

      Abaixo da árvore (comum a qualquer tipo escolhido):
      Diretório:  [$PROJETO ───────────────]
      Descrição:  [texto livre]
      [□ Mostrar terminal]   [□ Pausar ao terminar]

Tipos de ação disponíveis:
  "Executar comando"     → campo "Comando" livre
  "Executar Python"      → campo "Arquivo .py" + "Argumentos"
  "Script PowerShell"    → campo "Arquivo .ps1"
  "Abrir pasta"          → campo "Caminho da pasta"

JSON gerado por tarefa:
  {
    "atalho":          "f3",
    "nome":            "▶ Executar",
    "tipo":            "comando",
    "comando":         "python $ARQUIVO",
    "arquivo":         "",
    "argumentos":      "",
    "diretorio":       "$PROJETO",
    "descricao":       "",
    "mostrar_terminal": true,
    "pausar":          false
  }
"""

from __future__ import annotations
import json
import os
import re
import subprocess
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from _CONFIGURA_ import PASTA_TAREFAS, TAREFAS_FKEYS
from _CONFIGURA_.gerenciador_tema import tema_global
from _LOG_.log import log
from _UTILITARIOS_.icones import icone_tema
from _UTILITARIOS_._ajuda_ import criar_botao_ajuda
from _UTILITARIOS_._ajuda_.conteudos import tarefas as _ajuda_tarefas
_ARQ = "tarefas_explorer.py"

_TIPOS_ACAO = [
    ("— Escolha o tipo de ação —",     ""),
    ("Executar um comando",            "comando"),
    ("Executar um arquivo Python (.py)",      "python"),
    ("Executar um arquivo PowerShell (.ps1)", "powershell"),
    ("Abrir uma pasta",                "pasta"),
]
_TIPOS_CHAVE = [t[1] for t in _TIPOS_ACAO]
_TIPOS_LABEL = {chave: label for label, chave in _TIPOS_ACAO if chave}

_FKEYS_EXIB = [k.upper() for k in TAREFAS_FKEYS]  # ["F2","F3",...,"F10"]

# ─────────────────────────────────────────────────────────────────────────────
class _CardTarefa(QWidget):
    """
    Card individual de uma tarefa — expansível.
    """

    def __init__(self, dados: dict, idx: int, parent=None):
        super().__init__(parent)
        self._dados  = dados
        self._idx    = idx
        self._aberto = True
        self._construir()
        self._aplicar_dados(dados)

    # ── Construção ────────────────────────────────────────────────────────

    # ⚠️  função grande (207 linhas)
    def _construir(self):
        t      = tema_global()
        fundo  = t.cor("grafo.no_fundo",   "#0d1a0d")
        borda  = t.cor("grafo.no_borda",   "#1a3a1a")
        verde  = t.cor("grafo.no_texto",   "#4ec994")
        texto  = t.cor("interface.texto",  "#e0e0e0")
        inp    = t.cor("interface.inputs", "#070f0a")

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ── Frame externo com borda ───────────────────────────────────────
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        # f"QFrame {{ border: 1px solid {borda}; border-radius: 5px; background: {fundo}; }}" # subtitulos
        frame.setStyleSheet(
            f"QFrame {{ border: transparent; background: transparent; }}"
        )
        lay_frame = QVBoxLayout(frame)
        lay_frame.setContentsMargins(0, 0, 0, 0)
        lay_frame.setSpacing(0)
        raiz.addWidget(frame)

        # ── Cabeçalho ─────────────────────────────────────────────────────
        self._cab = QWidget()
        self._cab.setFixedHeight(34)
        self._cab.setStyleSheet(f"background: transparent;  border: 1px solid {borda}; border-radius: 4px; ")
        self._cab.setCursor(Qt.PointingHandCursor)
        self._cab.mousePressEvent = lambda _: self._toggle()
        lay_cab = QHBoxLayout(self._cab)
        lay_cab.setContentsMargins(8, 0, 6, 0)
        lay_cab.setSpacing(6)

        self._btn_toggle = QPushButton("▼")
        self._btn_toggle.setFixedSize(0, 18)
        self._btn_toggle.setFixedSize(0, 18)
        self._btn_toggle.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {verde}; border: none; font-size: 10px; }}"
        )
        self._btn_toggle.clicked.connect(self._toggle)
        lay_cab.addWidget(self._btn_toggle)

        # ComboBox atalho
        self._cb_atalho = QComboBox()
        self._cb_atalho.addItems(_FKEYS_EXIB)
        self._cb_atalho.setFixedWidth(54)
        self._cb_atalho.setFixedHeight(24)
        self._cb_atalho.setStyleSheet(self._estilo_combo(verde, borda, fundo))
        lay_cab.addWidget(self._cb_atalho)

        # Nome
        self._ed_nome = QLineEdit()
        self._ed_nome.setPlaceholderText("Nome da tarefa")
        self._ed_nome.setFixedHeight(24)
        self._ed_nome.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._ed_nome.setStyleSheet(self._estilo_input(inp, texto, borda))
        lay_cab.addWidget(self._ed_nome)

        # botão ▶
        btn_run = QPushButton()
        btn_run.setIcon(icone_tema("mdi.play"))
        btn_run.setIconSize(QSize(14, 14))
        btn_run.setFixedSize(24, 24)
        btn_run.setToolTip("Executar agora")
        btn_run.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover { background: rgba(78,201,148,.15); border-radius: 3px; }"
        )
        btn_run.clicked.connect(self._executar)
        lay_cab.addWidget(btn_run)

        # botão ✕
        btn_del = QPushButton()
        btn_del.setIcon(icone_tema("mdi.delete-outline"))
        btn_del.setIconSize(QSize(14, 14))
        btn_del.setFixedSize(24, 24)
        btn_del.setToolTip("Remover tarefa")
        btn_del.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover { background: rgba(248,112,112,.15); border-radius: 3px; }"
        )
        btn_del.clicked.connect(self._solicitar_remocao)
        lay_cab.addWidget(btn_del)
        lay_frame.addWidget(self._cab)

        # ── Corpo ─────────────────────────────────────────────────────────
        self._corpo = QWidget()
        self._corpo.setObjectName("card_body")
        self._corpo.setStyleSheet(f"QWidget#card_body {{ background: transparent; border: 1px solid {borda}; }}")
        lay_corpo = QVBoxLayout(self._corpo)
        lay_corpo.setContentsMargins(12, 8, 12, 10)
        lay_corpo.setSpacing(6)

        # ── árvore real: TODO campo do card é galho da mesma raiz. ──────────
        # "O que vai fazer", "Diretório", "Descrição" e "Opções" são 4
        # galhos IRMÃOS, no mesmo nível de recuo, com a mesma linha de
        # conexão — nenhum deles pode virar barra solta sem recuo/linha.

        # ── Galho 1: "O que essa tecla vai fazer?" ──────────────────────────
        container_tipos = QWidget()
        lay_tipos = QVBoxLayout(container_tipos)
        lay_tipos.setContentsMargins(0, 0, 0, 0)
        lay_tipos.setSpacing(2)

        self._btn_tipo   = {}
        self._area_galho = {}   # tipo -> QWidget (área de campos daquele galho)
        self._wrap_galho = {}   # tipo -> QWidget (linha + área, o que é mostrado/escondido)
        self._lay_area_galho = {}  # tipo -> QVBoxLayout interno da área
        self._grupo_tipo = QButtonGroup(self)
        self._grupo_tipo.setExclusive(True)

        for label, chave in _TIPOS_ACAO:
            if chave == "":
                continue
            btn = QPushButton(f"▸  {label}")
            btn.setCheckable(True)
            btn.setMinimumHeight(28)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._estilo_galho_linha(verde, texto, False))
            btn.clicked.connect(lambda _, k=chave: self._escolher_tipo(k))
            self._grupo_tipo.addButton(btn)
            self._btn_tipo[chave] = btn
            lay_tipos.addWidget(btn)

            area = QWidget()
            lay_area = QVBoxLayout(area)
            lay_area.setContentsMargins(0, 4, 0, 4)
            lay_area.setSpacing(4)
            self._area_galho[chave] = area
            self._lay_area_galho[chave] = lay_area

            wrap = self._ramo(area, borda)
            wrap.setVisible(False)
            self._wrap_galho[chave] = wrap
            lay_tipos.addWidget(wrap)

        # dica contextual — muda de texto conforme a ação escolhida
        self._lbl_dica = QLabel("")
        self._lbl_dica.setWordWrap(True)
        self._lbl_dica.setStyleSheet("color: #5a8a6a; font-size: 10px;")
        lay_tipos.addWidget(self._lbl_dica)

        lay_corpo.addWidget(self._galho_raiz("O que essa tecla vai fazer?", container_tipos, verde, borda))

        self._tipo_atual = ""

        # campos dinâmicos (instâncias únicas, movidas entre os galhos conforme o tipo)
        self._ed_comando    = self._linha("Comando:",    "python $ARQUIVO", inp, texto, borda, vars_btn=True)
        self._ed_arquivo    = self._linha("Arquivo:",    "caminho/do/arquivo.py", inp, texto, borda)
        self._ed_args       = self._linha("Argumentos:", "--argumento valor", inp, texto, borda, vars_btn=True)
        self._ed_pasta_path = self._linha("Pasta:",      "caminho/da/pasta", inp, texto, borda, vars_btn=True)

        # ── Galho 2: "Diretório" (mesmo recuo/linha do galho 1) ─────────────
        dir_content = QWidget()
        lay_dir = QVBoxLayout(dir_content)
        lay_dir.setContentsMargins(0, 0, 0, 0)
        lay_dir.setSpacing(4)
        self._ed_diretorio = self._linha("", "$PROJETO", inp, texto, borda, vars_btn=True)
        lay_dir.addWidget(self._ed_diretorio["widget"])
        self._lbl_dica_dir = QLabel(
            "$PROJETO = a pasta do seu projeto atual. Se quiser rodar em "
            "outro lugar, apague e digite o caminho completo da pasta."
        )
        self._lbl_dica_dir.setWordWrap(True)
        self._lbl_dica_dir.setStyleSheet("color: #666; font-size: 9px;")
        lay_dir.addWidget(self._lbl_dica_dir)
        self._galho_diretorio = self._galho_raiz("Diretório", dir_content, verde, borda)
        lay_corpo.addWidget(self._galho_diretorio)

        # ── Galho 3: "Descrição" (mesmo recuo/linha) ────────────────────────
        desc_content = QWidget()
        lay_desc = QVBoxLayout(desc_content)
        lay_desc.setContentsMargins(0, 0, 0, 0)
        lay_desc.setSpacing(4)
        self._ed_descricao = self._linha("", "Descrição opcional", inp, texto, borda)
        lay_desc.addWidget(self._ed_descricao["widget"])
        self._galho_descricao = self._galho_raiz("Descrição", desc_content, verde, borda)
        lay_corpo.addWidget(self._galho_descricao)

        # ── Galho 4: "Opções" (mesmo recuo/linha) ───────────────────────────
        opc_content = QWidget()
        lay_opc = QVBoxLayout(opc_content)
        lay_opc.setContentsMargins(0, 0, 0, 0)
        lay_opc.setSpacing(6)
        self._chk_mostrar = QCheckBox("Mostrar terminal")
        self._chk_mostrar.setChecked(True)
        self._chk_mostrar.setStyleSheet("color: #999; font-size: 10px;")
        lay_opc.addWidget(self._chk_mostrar)
        self._chk_pausar = QCheckBox("Pausar ao terminar")
        self._chk_pausar.setStyleSheet("color: #999; font-size: 10px;")
        lay_opc.addWidget(self._chk_pausar)
        self._galho_opcoes = self._galho_raiz("Opções", opc_content, verde, borda)
        lay_corpo.addWidget(self._galho_opcoes)

        # galhos 2/3/4 só fazem sentido depois que um tipo foi escolhido
        self._campos_pos_escolha = [
            self._galho_diretorio,
            self._galho_descricao,
            self._galho_opcoes,
        ]

        lay_frame.addWidget(self._corpo)
        self._escolher_tipo("")

    # ── Árvore: helpers visuais ──────────────────────────────────────────

    def _galho_raiz(self, titulo: str, corpo: QWidget, verde: str, borda: str) -> QWidget:
        """
        Monta um galho de 1º nível saindo direto da raiz do card (tecla +
        nome): título em cima, conteúdo recuado embaixo — ligados por uma
        linha vertical, exatamente como qualquer outro galho da árvore.
        Usado por igual em "O que essa tecla vai fazer?", "Diretório",
        "Descrição" e "Opções" — nenhum campo do card fica de fora dessa
        estrutura.
        """
        conteudo = QWidget()
        lay = QVBoxLayout(conteudo)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(4)
        lbl = QLabel(titulo)
        lbl.setStyleSheet(f"color: {verde}; font-size: 10px; font-weight: bold;")
        lay.addWidget(lbl)
        lay.addWidget(self._ramo(corpo, borda))

        return self._ramo(conteudo, verde)

    @staticmethod
    def _ramo(conteudo: QWidget, cor: str) -> QWidget:
        """
        Envolve `conteudo` com uma linha vertical contínua à esquerda,
        estilo file-tree (VS Code): o traço acompanha a altura total do
        conteúdo, ligando o pai a todos os filhos recuados.
        """
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(8, 0, 0, 0)
        lay.setSpacing(8)
        linha = QFrame()
        linha.setFixedWidth(2)
        linha.setStyleSheet(f"background: {cor}; border: none; border-radius: 1px;")
        linha.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        lay.addWidget(linha)
        lay.addWidget(conteudo)

        return w

    @staticmethod
    def _estilo_galho_linha(verde: str, texto: str, selecionado: bool) -> str:
        if selecionado:

            return (

                f"QPushButton {{ background: transparent; color: {texto}; "
                f"border: none; border-radius: 4px; font-size: 11px; font-weight: bold; "
                f"text-align: left; padding: 6px 10px; }}"
            )

        return (

            f"QPushButton {{ background: transparent; color: #6a7a6a; border: none; "
            f"border-radius: 4px; font-size: 11px; text-align: left; padding: 6px 10px; }}"
            f"QPushButton:hover {{ background: rgba(255,255,255,.05); color: {texto}; }}"
        )

    # ── Campos dinâmicos ─────────────────────────────────────────────────

    # ⚠️  função grande (57 linhas)
    def _linha(self, label: str, placeholder: str, inp, texto, borda, vars_btn: bool = False) -> dict:
        """Cria linha label + QLineEdit [+ botão de variáveis], retorna dict."""
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        if label:
            lbl = QLabel(label)
            lbl.setFixedWidth(72)
            lbl.setStyleSheet("color: #666; font-size: 10px;")
            lay.addWidget(lbl)
        ed = QLineEdit()
        ed.setPlaceholderText(placeholder)
        ed.setFixedHeight(24)
        ed.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        ed.setStyleSheet(self._estilo_input(inp, texto, borda))
        lay.addWidget(ed)
        if vars_btn:
            _t_v = tema_global()
            _verde_v = _t_v.cor("grafo.no_texto", "#4ec994")
            _fundo_v = _t_v.cor("grafo.no_fundo", "#0d1a0d")
            _borda_v = _t_v.cor("grafo.no_borda", "#2a4a2a")
            _hover_v = _t_v.cor("interface.fundo_item_hover", "#1a3a1a")
            btn_v = QPushButton("Variáveis  ▾")
            btn_v.setFixedHeight(24)
            btn_v.setMinimumWidth(92)
            btn_v.setCursor(Qt.PointingHandCursor)
            btn_v.setToolTip(
                "Clique pra inserir uma variável no campo:\n"
                "$PYTHON — Python do venv\n"
                "$PROJETO — pasta do projeto\n"
                "$ARQUIVO — arquivo do editor\n"
                "$VENV    — pasta .venv\n"
                "$TAREFAS — pasta de tarefas"
            )
            btn_v.setStyleSheet(
                f"QPushButton {{ background: {_fundo_v}; color: {_verde_v}; border: 1px solid {_borda_v}; "
                f"border-radius: 3px; font-size: 10px; font-weight: bold; padding: 2px 8px; }}"
                f"QPushButton:hover {{ background: {_hover_v}; border-color: {_verde_v}; }}"
            )
            from PySide6.QtWidgets import QMenu
            from PySide6.QtCore import QPoint
            _VARS = ["$PYTHON", "$PROJETO", "$ARQUIVO", "$VENV", "$TAREFAS"]
            def _abrir_menu_vars(checked=False, _ed=ed, _btn=btn_v):
                menu = QMenu(_btn)
                menu.setStyleSheet(
                    f"QMenu {{ background: {_fundo_v}; color: {_verde_v}; border: 1px solid {_borda_v}; "
                    f"font-size: 11px; }} QMenu::item:selected {{ background: {_hover_v}; }}"
                )
                for v in _VARS:
                    act = menu.addAction(v)
                    act.triggered.connect(lambda _, var=v, e=_ed: e.insert(var))
                menu.exec(_btn.mapToGlobal(QPoint(0, _btn.height())))
            btn_v.clicked.connect(_abrir_menu_vars)
            lay.addWidget(btn_v)

        return {"widget": w, "ed": ed}

    _DICAS = {
        "":           "Escolha um tipo de ação na lista acima pra continuar.",
        "comando":    "Digite o comando exatamente como digitaria no terminal. "
                      "Ex: python -m uvicorn api.main:app --reload",
        "python":     "Escolha o arquivo .py que quer rodar. "
                      "Argumentos são opcionais.",
        "powershell": "Escolha o arquivo .ps1 que quer executar.",
        "pasta":      "Escolha a pasta que quer abrir no explorador de arquivos do sistema.",
    }

    def _escolher_tipo(self, tipo: str):
        self._tipo_atual = tipo

        # tira os campos dinâmicos de onde quer que estejam (galho anterior)
        for chave, lay_area in self._lay_area_galho.items():
            while lay_area.count():
                item = lay_area.takeAt(0)
                if item and item.widget():
                    item.widget().setParent(None)

        # recoloca os campos certos dentro do galho escolhido
        if tipo == "comando":
            self._lay_area_galho["comando"].addWidget(self._ed_comando["widget"])
        elif tipo == "python":
            self._lay_area_galho["python"].addWidget(self._ed_arquivo["widget"])
            self._lay_area_galho["python"].addWidget(self._ed_args["widget"])
        elif tipo == "powershell":
            self._lay_area_galho["powershell"].addWidget(self._ed_arquivo["widget"])
        elif tipo == "pasta":
            self._lay_area_galho["pasta"].addWidget(self._ed_pasta_path["widget"])

        self._lbl_dica.setText(self._DICAS.get(tipo, ""))

        # abre o galho escolhido (▾, destacado), fecha os demais (▸, apagado)
        for chave, btn in self._btn_tipo.items():
            selecionado = (chave == tipo)
            btn.setChecked(selecionado)
            seta = "▾" if selecionado else "▸"
            btn.setText(f"{seta}  {_TIPOS_LABEL[chave]}")
            _t_e = tema_global()
            btn.setStyleSheet(self._estilo_galho_linha(
                _t_e.cor("grafo.no_texto", "#4ec994"),
                _t_e.cor("interface.texto", "#e0e0e0"),
                selecionado,
            ))
            self._wrap_galho[chave].setVisible(selecionado)

        # campos comuns (diretório, descrição, checkboxes) só aparecem
        # depois que um tipo foi escolhido
        for campo in getattr(self, "_campos_pos_escolha", []):
            campo.setVisible(tipo != "")

    # ── Toggle ────────────────────────────────────────────────────────────

    def _toggle(self):
        self._aberto = not self._aberto
        self._corpo.setVisible(self._aberto)
        self._btn_toggle.setText("▼" if self._aberto else "▶")
        self.adjustSize()
        p = self.parent()
        if p:
            p.adjustSize()

    # ── Leitura / escrita de dados ────────────────────────────────────────

    def _aplicar_dados(self, d: dict):
        atalho = d.get("atalho", "").lower()
        try:
            idx_atalho = TAREFAS_FKEYS.index(atalho)
        except ValueError:
            idx_atalho = 0
        self._cb_atalho.setCurrentIndex(idx_atalho)
        self._ed_nome.setText(d.get("nome", ""))

        tipo = d.get("tipo", "")
        if tipo not in _TIPOS_CHAVE:
            tipo = ""

        self._ed_comando["ed"].setText(d.get("comando", ""))
        self._ed_arquivo["ed"].setText(d.get("arquivo", ""))
        self._ed_args["ed"].setText(d.get("argumentos", ""))
        self._ed_pasta_path["ed"].setText(d.get("caminho_pasta", ""))
        self._ed_diretorio["ed"].setText(d.get("diretorio", "$PROJETO"))
        self._ed_descricao["ed"].setText(d.get("descricao", ""))
        self._chk_mostrar.setChecked(d.get("mostrar_terminal", True))
        self._chk_pausar.setChecked(d.get("pausar", False))

        self._escolher_tipo(tipo)

    def coletar(self) -> dict | None:
        """Retorna o dict da tarefa atual, ou None se vazio."""
        nome    = self._ed_nome.text().strip()
        tipo    = self._tipo_atual
        atalho  = TAREFAS_FKEYS[self._cb_atalho.currentIndex()]

        comando = ""
        arquivo = ""
        args    = ""
        pasta_p = ""
        if tipo == "comando":
            comando = self._ed_comando["ed"].text().strip()
        elif tipo == "python":
            arquivo = self._ed_arquivo["ed"].text().strip()
            args    = self._ed_args["ed"].text().strip()
            comando = f"$PYTHON {arquivo} {args}".strip()
        elif tipo == "powershell":
            arquivo = self._ed_arquivo["ed"].text().strip()
            comando = f"& {arquivo}"
        elif tipo == "pasta":
            pasta_p = self._ed_pasta_path["ed"].text().strip()
            comando = f"explorer {pasta_p}" if os.name == "nt" else f"xdg-open {pasta_p}"

        if not tipo or (not nome and not comando):

            return None

        dados = {
            "atalho":          atalho,
            "nome":            nome,
            "tipo":            tipo,
            "comando":         comando,
            "diretorio":       self._ed_diretorio["ed"].text().strip() or "$PROJETO",
            "descricao":       self._ed_descricao["ed"].text().strip(),
            "mostrar_terminal": self._chk_mostrar.isChecked(),
            "pausar":          self._chk_pausar.isChecked(),
        }
        # só grava a chave extra que o tipo realmente usa — evita
        # campos vazios e irrelevantes poluindo o tarefas.json
        if tipo in ("python", "powershell"):
            dados["arquivo"] = arquivo
        if tipo == "python":
            dados["argumentos"] = args
        if tipo == "pasta":
            dados["caminho_pasta"] = pasta_p

        return dados

    # ── Ações ─────────────────────────────────────────────────────────────

    def _executar(self):
        d = self.coletar()
        if not d:

            return

        try:
            from _CONFIGURA_.gerenciador_tarefas import gerenciador_tarefas
            gt = gerenciador_tarefas()
            if gt:
                gt.executar(d)
        except Exception as e:
            log.aviso(_ARQ, "_executar", f"erro ao executar: {e}")

    def _solicitar_remocao(self):
        explorer = self._encontrar_explorer()
        if explorer:
            explorer._remover_card(self)

    def _encontrar_explorer(self) -> "TarefasExplorer | None":
        p = self.parent()
        while p:
            if isinstance(p, TarefasExplorer):

                return p

            p = p.parent() if hasattr(p, "parent") else None

        return None

    # ── Estilos ───────────────────────────────────────────────────────────

    @staticmethod
    def _estilo_combo(verde, borda, fundo):
        t = tema_global()
        fundo_lista = t.cor("grafo.no_fundo", "#0d1a0d")
        hover       = t.cor("interface.fundo_item_hover", "#1a2e1a")

        return (

            f"QComboBox {{ background: {fundo}; color: {verde}; border: 1px solid {borda}; "
            f"border-radius: 3px; padding: 2px 6px; font-size: 11px; font-weight: bold; }}"
            f"QComboBox::drop-down {{ border: none; width: 16px; }}"
            f"QComboBox QAbstractItemView {{ background: {fundo_lista}; color: {verde}; "
            f"selection-background-color: {hover}; border: 1px solid {borda}; }}"
        )

    @staticmethod
    def _estilo_input(fundo, texto, borda):
        foco = tema_global().cor("interface.borda_foco", "#3a7a3a")

        return (

            f"QLineEdit {{ background: {fundo}; color: {texto}; border: 1px solid {borda}; "
            f"border-radius: 3px; padding: 2px 6px; font-size: 11px; }}"
            f"QLineEdit:focus {{ border-color: {foco}; }}"
        )

# ─────────────────────────────────────────────────────────────────────────────
class TarefasExplorer(QWidget):
    """Painel visual para edição e execução de tarefas.json."""

    # 💡 modo_opc = Literal["projeto"] ← defina os valores válidos
    def __init__(self, caminho: str, modo: str = "projeto", parent=None):
        super().__init__(parent)
        self._caminho = caminho
        self._modo    = modo
        self._cards: list[_CardTarefa] = []
        self._construir_ui()
        self._carregar()

    # ── UI principal ──────────────────────────────────────────────────────

    # ⚠️  função grande (93 linhas)
    def _construir_ui(self):
        t      = tema_global()
        fundo  = t.cor("interface.fundo",        "#070706")
        texto  = t.cor("interface.texto",        "#e0e0e0")
        painel = t.cor("interface.fundo_painel", "#0d0d0d")
        verde  = t.cor("grafo.no_texto",         "#4ec994")
        borda  = t.cor("grafo.no_borda",         "#1a3a1a")
        fundo_no = t.cor("grafo.no_fundo",       "#0d1a0d")
        hover  = t.cor("interface.fundo_item_hover",     "#1a2e1a")
        selecionado = t.cor("interface.fundo_item_selecionado", "#1f3d1f")

        self.setStyleSheet(f"background: {fundo}; color: {texto};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Cabeçalho ─────────────────────────────────────────────────────
        # Barra única: nada de título repetido (a aba já mostra o nome) e
        # nada de emoji — botões-ícone iguais aos de terminal_run.py /
        # terminal_powershell.py (icone_tema + tooltip no hover).
        cab = QWidget()
        cab.setFixedHeight(36)
        cab.setStyleSheet(f"background: {painel};")
        lay_cab = QHBoxLayout(cab)
        lay_cab.setContentsMargins(10, 0, 8, 0)
        lay_cab.setSpacing(10)

        lbl_vars = QLabel(
            "Variáveis:  $PYTHON   $PROJETO   $ARQUIVO   $VENV   $TAREFAS"
        )
        lbl_vars.setStyleSheet(f"color: {t.cor('interface.texto_fraco', '#7094A1')}; font-size: 10px;")
        lay_cab.addWidget(lbl_vars)
        lay_cab.addStretch()

        btn_add = QPushButton("+ Adicionar Tarefa")
        btn_add.setFixedHeight(24)
        btn_add.setStyleSheet(
            f"QPushButton {{ background: {fundo_no}; color: {verde}; "
            f"border: 1px solid {borda}; border-radius: 3px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {hover}; }}"
        )
        btn_add.clicked.connect(self._adicionar)
        lay_cab.addWidget(btn_add)

        _estilo_icone = (
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover { background: rgba(255,255,255,0.07); border-radius: 3px; }"
        )

        btn_pasta = QPushButton()
        btn_pasta.setIcon(icone_tema("mdi.folder-open-outline"))
        btn_pasta.setIconSize(QSize(14, 14))
        btn_pasta.setFixedSize(22, 22)
        btn_pasta.setToolTip(f"Abrir pasta de tarefas\n{PASTA_TAREFAS}")
        btn_pasta.setStyleSheet(_estilo_icone)
        btn_pasta.clicked.connect(self._abrir_pasta)
        lay_cab.addWidget(btn_pasta)

        btn_ajuda = criar_botao_ajuda(
            _ajuda_tarefas.texto, titulo="Como usar Tarefas (F2–F10)",
            tooltip="Como usar tarefas", parent=self,
        )
        lay_cab.addWidget(btn_ajuda)

        btn_salvar = QPushButton("Salvar")
        btn_salvar.setFixedSize(70, 24)
        btn_salvar.setStyleSheet(
            f"QPushButton {{ background: {selecionado}; color: {verde}; "
            f"border: 1px solid {borda}; border-radius: 3px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {hover}; }}"
        )
        btn_salvar.clicked.connect(self._salvar)
        lay_cab.addWidget(btn_salvar)
        layout.addWidget(cab)

        # ── Scroll com os cards ───────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: {fundo}; border: none; }}")

        self._corpo = QWidget()
        self._corpo.setStyleSheet(f"background: {fundo};")
        self._lay_corpo = QVBoxLayout(self._corpo)
        self._lay_corpo.setContentsMargins(10, 10, 10, 10)
        self._lay_corpo.setSpacing(8)
        self._lay_corpo.addStretch()
        scroll.setWidget(self._corpo)
        layout.addWidget(scroll)

    # ── Carregamento ──────────────────────────────────────────────────────

    def _carregar(self): # remove cards existentes
        for card in self._cards:
            self._lay_corpo.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        for idx, dados in enumerate(self._ler_json()):
            self._inserir_card(dados)

    def _ler_json(self) -> list[dict]:
        if not os.path.exists(self._caminho):

            return []

        try:
            with open(self._caminho, encoding="utf-8") as f:
                texto = re.sub(r"//[^\n]*", "", f.read())
            dados = json.loads(texto)
            lista = dados.get("tarefas", dados) if isinstance(dados, dict) else dados
            if not isinstance(lista, list):

                return []

            # Migrar formato antigo (sem campo "atalho") → atribui sequencialmente
            resultado = []
            usados = set()
            for i, item in enumerate(lista):
                if "atalho" not in item and i < len(TAREFAS_FKEYS):
                    item = dict(item)
                    item["atalho"] = TAREFAS_FKEYS[i]
                if "tipo" not in item:
                    item = dict(item)
                    item["tipo"] = "comando"
                resultado.append(item)
                usados.add(item.get("atalho"))

            return resultado

        except Exception as e:
            log.aviso(_ARQ, "_ler_json", f"erro ao ler '{self._caminho}': {e}")

        return []

    # ── Cards ──────────────────────────────────────────────────────────────

    def _inserir_card(self, dados: dict) -> _CardTarefa:
        card = _CardTarefa(dados, len(self._cards), parent=self._corpo)
        pos  = self._lay_corpo.count() - 1   # antes do stretch
        self._lay_corpo.insertWidget(pos, card)
        self._cards.append(card)

        return card

    def _remover_card(self, card: _CardTarefa):
        if card in self._cards:
            self._cards.remove(card)
            self._lay_corpo.removeWidget(card)
            card.deleteLater()
            self._salvar()

    def _adicionar(self):
        if len(self._cards) >= len(TAREFAS_FKEYS):
            log.aviso(_ARQ, "_adicionar", "limite de 9 tarefas atingido")

            return

        # escolhe a primeira f-key ainda não usada
        usados = {TAREFAS_FKEYS[c._cb_atalho.currentIndex()] for c in self._cards}
        livre  = next((k for k in TAREFAS_FKEYS if k not in usados), TAREFAS_FKEYS[0])
        self._inserir_card({
            "atalho": livre,
            "nome":   "",
            "mostrar_terminal": True,
            "pausar": False,
        })

    # ── Salvar ────────────────────────────────────────────────────────────

    def _salvar(self):
        """Grava as tarefas no JSON e notifica o gerenciador de atalhos."""
        # ── coletar dados dos cards ──
        dados = [c.coletar() for c in self._cards]
        dados = [d for d in dados if d]

        # ── validar caminho ──
        pasta = os.path.dirname(self._caminho)
        if pasta:
            os.makedirs(pasta, exist_ok=True)

        # ── gravar JSON ──
        try:
            with open(self._caminho, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.erro(_ARQ, "_salvar", f"erro ao salvar: {e}")
            self._status(f"❌ Erro ao salvar: {e}", erro=True)

            return

        # ── recarregar atalhos ──
        try:
            from _CONFIGURA_.gerenciador_tarefas import gerenciador_tarefas
            gt = gerenciador_tarefas()
            if gt:
                if self._modo == "projeto":
                    gt.carregar_projeto_do_caminho(self._caminho)
                else:
                    gt.carregar_globais()
        except Exception as e:
            log.aviso(_ARQ, "_salvar", f"erro ao notificar gerenciador: {e}")

        log.ok(_ARQ, "_salvar", f"{len(dados)} tarefa(s) salvas → {self._caminho}")
        self._status(f"✓ {len(dados)} tarefa(s) salvas")

    # ⚠️  except genérico vazio
    def _status(self, msg: str, erro: bool = False) -> None:
        """Exibe mensagem de status na janela principal (se disponível)."""
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                wins = [w for w in app.topLevelWidgets() if hasattr(w, "statusBar")]
                if wins:
                    t = tema_global()
                    cor_txt = t.cor("log.erro", "#e06c75") if erro else t.cor("log.ok", "#4ec994")
                    wins[0].statusBar().setStyleSheet(f"color: {cor_txt};")
                    wins[0].statusBar().showMessage(msg, 4000)
        except Exception:
            pass

    def _recarregar_se_necessario(self):
        self._carregar()

    def _abrir_pasta(self):
        os.makedirs(PASTA_TAREFAS, exist_ok=True)
        if os.name == "nt":
            subprocess.Popen(["explorer", PASTA_TAREFAS])
        else:
            subprocess.Popen(["xdg-open", PASTA_TAREFAS])
