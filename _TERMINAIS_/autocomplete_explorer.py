# 📁 _TERMINAIS_/autocomplete_explorer.py
"""
AutocompleteExplorer — painel visual para autocomplete.json.

Painel esquerdo:
  • Ambiente do Projeto — pasta_venv, site_packages_*
  • Snippets de Código  — pares (nome → código) editáveis

Painel direito:
  • Fontes da Pasta AppData — listas de arquivos por tipo
    (palavras .txt, símbolos .json, emojis .json)
    lidos de %APPDATA%/hein/autocompletar/

Salvar grava direto no arquivo; o gerenciador detecta via QFileSystemWatcher.
"""

import json
import os
import re
import subprocess
import sys
from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QScrollArea, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from _CONFIGURA_ import ARQUIVO_CONFIG
from _CONFIGURA_.gerenciador_tema import tema_global
from _LOG_.log import log
_ARQ = "autocomplete_explorer.py"
ARQUIVO_AUTOCOMPLETE = os.path.join(os.path.dirname(ARQUIVO_CONFIG), "autocomplete.json")

# ─── helpers JSON ─────────────────────────────────────────────────────────────

def _carregar_json(caminho: str) -> dict:
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            texto = f.read()
        texto = re.sub(
            r'"(?:[^"\\]|\\.)*"|//[^\n]*',
            lambda m: m.group(0) if m.group(0).startswith('"') else '',
            texto,
        )

        return json.loads(texto)

    except Exception as e:
        log.erro(_ARQ, "_carregar_json", str(e))

        return {}

def _salvar_json(caminho: str, dados: dict) -> bool:
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

        return True

    except Exception as e:
        log.erro(_ARQ, "_salvar_json", str(e))

        return False

# ─── widgets de suporte ───────────────────────────────────────────────────────

def _titulo_secao(texto: str, cor: str) -> QLabel:
    lbl = QLabel(texto)
    lbl.setStyleSheet(
        f"font-size:11px; font-weight:bold; color:{cor};"
        f" font-family:Consolas; padding-bottom:2px;"
    )

    return lbl

def _separador() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFixedHeight(1)

    return f

class _SnippetRow(QWidget):
    """Uma linha de snippet: [nome QLineEdit] → [código QPlainTextEdit] [×]."""

    def __init__(self, nome: str, codigo: str, on_remover, parent=None):
        super().__init__(parent)
        self._on_remover = on_remover
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(8)

        self.w_nome = QLineEdit(nome)
        self.w_nome.setFixedWidth(160)
        self.w_nome.setFixedHeight(70)
        self.w_nome.setAlignment(Qt.AlignTop)
        self.w_nome.setPlaceholderText("nome do snippet")
        self.w_nome.setStyleSheet(
            "QLineEdit{background:#0e1a0e;color:#e0e0e0;border:1px solid #1a3a1a;"
            "border-radius:3px;padding:4px 6px;font-size:10px;font-family:Consolas;}"
            "QLineEdit:focus{border-color:#4ec994;}"
        )
        lay.addWidget(self.w_nome)

        seta = QLabel("→")
        seta.setStyleSheet("color:#4ec994; font-size:12px;")
        seta.setFixedWidth(16)
        seta.setAlignment(Qt.AlignVCenter)
        lay.addWidget(seta)

        self.w_codigo = QPlainTextEdit(codigo)
        self.w_codigo.setFixedHeight(70)
        self.w_codigo.setPlaceholderText("código do snippet (use \\n para quebras de linha)")
        self.w_codigo.setStyleSheet(
            "QPlainTextEdit{background:#0e1a0e;color:#e0e0e0;border:1px solid #1a3a1a;"
            "border-radius:3px;padding:4px 6px;font-size:10px;font-family:Consolas;}"
            "QPlainTextEdit:focus{border-color:#4ec994;}"
        )
        lay.addWidget(self.w_codigo, 1)

        btn_x = QPushButton("×")
        btn_x.setFixedSize(22, 22)
        btn_x.setStyleSheet(
            "QPushButton{background:transparent;color:#e06c75;border:none;font-size:14px;}"
            "QPushButton:hover{color:#ff6b6b;}"
        )
        btn_x.clicked.connect(self._remover)
        lay.addWidget(btn_x)

    def _remover(self):
        self._on_remover(self)

    def dados(self) -> tuple[str, str]:

        return self.w_nome.text().strip(), self.w_codigo.toPlainText()

class _FonteRow(QWidget):
    """Uma linha de fonte: [nome do arquivo] [×]."""

    def __init__(self, nome_arquivo: str, on_remover, cor_acento: str, parent=None):
        super().__init__(parent)
        self._on_remover = on_remover
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(6)

        self.w_nome = QLineEdit(nome_arquivo)
        self.w_nome.setFixedHeight(26)
        self.w_nome.setStyleSheet(
            f"QLineEdit{{background:#111;color:#e0e0e0;border:1px solid {cor_acento}44;"
            f"border-radius:3px;padding:2px 6px;font-size:10px;font-family:Consolas;}}"
            f"QLineEdit:focus{{border-color:{cor_acento};}}"
        )
        lay.addWidget(self.w_nome, 1)

        btn_x = QPushButton("×")
        btn_x.setFixedSize(22, 22)
        btn_x.setStyleSheet(
            "QPushButton{background:transparent;color:#e06c75;border:none;font-size:14px;}"
            "QPushButton:hover{color:#ff6b6b;}"
        )
        btn_x.clicked.connect(self._remover)
        lay.addWidget(btn_x)

    def _remover(self):
        self._on_remover(self)

    def dados(self) -> str:

        return self.w_nome.text().strip()

# ─── Explorer principal ───────────────────────────────────────────────────────

class AutocompleteExplorer(QWidget):
    """Painel visual para autocomplete.json — layout com splitter."""

    _COR_PALAVRAS = "#56b6c2"
    _COR_SIMBOLOS = "#c678dd"
    _COR_EMOJIS   = "#e5c07b"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dados: dict = {}
        self._snippet_rows: list[_SnippetRow] = []
        self._fonte_rows: dict[str, list[_FonteRow]] = {
            "palavras": [], "simbolos": [], "emojis": []
        }
        self._lay_fontes_containers: dict[str, QVBoxLayout] = {}
        self._arquivo = ARQUIVO_AUTOCOMPLETE
        self._salvando = False
        self._construir_ui()
        self._carregar()
        self._aplicar_tema()
        self._iniciar_watcher()

    # ── Watcher ───────────────────────────────────────────────────────────────

    def _iniciar_watcher(self):
        self._watcher_ext = QFileSystemWatcher()
        if os.path.isfile(self._arquivo):
            self._watcher_ext.addPath(self._arquivo)
        self._watcher_ext.fileChanged.connect(self._ao_arquivo_alterado_ext)
        self._timer_reload_ext = QTimer()
        self._timer_reload_ext.setSingleShot(True)
        self._timer_reload_ext.setInterval(700)
        self._timer_reload_ext.timeout.connect(self._recarregar_externo)

    def _ao_arquivo_alterado_ext(self, _caminho: str):
        if self._salvando:

            return

        if self._arquivo not in self._watcher_ext.files():
            self._watcher_ext.addPath(self._arquivo)
        self._timer_reload_ext.start()

    def _recarregar_externo(self):
        if self._salvando:

            return

        self._carregar()
        self._notificar("↺  Recarregado (arquivo alterado no editor)", cor="#4a90d9", duracao=3000)

    # ── UI estática ───────────────────────────────────────────────────────────

    # ⚠️  função grande (96 linhas)
    def _construir_ui(self):
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ── Cabeçalho ─────────────────────────────────────────────────────────
        self._cab = QWidget()
        self._cab.setFixedHeight(36)
        lay_cab = QHBoxLayout(self._cab)
        lay_cab.setContentsMargins(12, 0, 10, 0)
        lay_cab.setSpacing(8)

        lbl = QLabel("⚡  Autocomplete — autocomplete.json")
        lbl.setStyleSheet("font-size:12px; font-weight:bold; font-family:Consolas; color:#e0e0e0;")
        lay_cab.addWidget(lbl)
        lay_cab.addStretch()

        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("font-size:10px; color:#666;")
        lay_cab.addWidget(self._lbl_status)

        btn_rec = QPushButton("↺  Recarregar")
        btn_rec.setFixedHeight(24)
        btn_rec.setStyleSheet(
            "QPushButton{background:#1a1a1a;color:#888;border:none;padding:2px 10px;"
            "font-size:10px;border-radius:3px;} QPushButton:hover{color:#e0e0e0;}"
        )
        btn_rec.clicked.connect(self._carregar)
        lay_cab.addWidget(btn_rec)

        btn_pasta = QPushButton("📂  Pasta autocompletar")
        btn_pasta.setFixedHeight(24)
        btn_pasta.setToolTip(
            "Abre a pasta onde você adiciona seus próprios arquivos de autocomplete.\n"
            "Tipos suportados:\n"
            "  • .txt            → palavras no autocomplete normal\n"
            "  • .json (símbolo) → { \"alpha\": \"α\" }  → digite :alpha no editor\n"
            "  • .json (emoji)   → { \"fogo\": \"🔥\" }  → digite :fogo no editor\n"
            "\nEdite, salve e recarregue o explorer."
        )
        btn_pasta.setStyleSheet(
            "QPushButton{background:#1a1a1a;color:#61afef;border:none;padding:2px 10px;"
            "font-size:10px;border-radius:3px;} QPushButton:hover{color:#82c8ff;}"
        )
        btn_pasta.clicked.connect(self._abrir_pasta_autocompletar)
        lay_cab.addWidget(btn_pasta)

        btn_criar = QPushButton("🆕  Criar arquivo")
        btn_criar.setFixedHeight(24)
        btn_criar.setToolTip(
            "Cria um novo arquivo de fonte (.txt de palavras, .json de simbolos\n"
            "ou .json de emojis) direto em AppData/autocompletar/, com um\n"
            "esqueleto inicial valido -- sem precisar sair da IDE."
        )
        btn_criar.setStyleSheet(
            "QPushButton{background:#1a1a1a;color:#61afef;border:none;padding:2px 10px;"
            "font-size:10px;border-radius:3px;} QPushButton:hover{color:#82c8ff;}"
        )
        btn_criar.clicked.connect(self._criar_arquivo_fonte)
        lay_cab.addWidget(btn_criar)

        self._btn_salvar = QPushButton("⬆  Salvar autocomplete.json")
        self._btn_salvar.setFixedHeight(24)
        self._btn_salvar.setStyleSheet(
            "QPushButton{background:#1a3a1a;color:#98c379;border:none;padding:2px 14px;"
            "font-size:10px;border-radius:3px;} QPushButton:hover{background:#264f28;}"
        )
        self._btn_salvar.clicked.connect(self._salvar)
        lay_cab.addWidget(self._btn_salvar)
        raiz.addWidget(self._cab)

        raiz.addWidget(_separador())

        # ── Corpo: splitter horizontal ─────────────────────────────────────────
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setHandleWidth(4)
        self._splitter.setChildrenCollapsible(False)

        # Painel esquerdo — Ambiente + Snippets
        self._scroll_esq = QScrollArea()
        self._scroll_esq.setWidgetResizable(True)
        self._scroll_esq.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._corpo_esq = QWidget()
        self._lay_esq = QVBoxLayout(self._corpo_esq)
        self._lay_esq.setContentsMargins(16, 14, 16, 20)
        self._lay_esq.setSpacing(6)
        self._scroll_esq.setWidget(self._corpo_esq)
        self._splitter.addWidget(self._scroll_esq)

        # Painel direito — Fontes AppData
        self._scroll_dir = QScrollArea()
        self._scroll_dir.setWidgetResizable(True)
        self._scroll_dir.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._corpo_dir = QWidget()
        self._lay_dir = QVBoxLayout(self._corpo_dir)
        self._lay_dir.setContentsMargins(16, 14, 16, 20)
        self._lay_dir.setSpacing(6)
        self._scroll_dir.setWidget(self._corpo_dir)
        self._splitter.addWidget(self._scroll_dir)

        self._splitter.setSizes([620, 360])
        raiz.addWidget(self._splitter, 1)

        self._rodape = QLabel(
            "Snippets: escreva \\n para quebra de linha no código. "
            "O nome vira a palavra-chave que dispara o snippet."
        )
        self._rodape.setFixedHeight(20)
        self._rodape.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        raiz.addWidget(self._rodape)

    # ── Seção Ambiente ────────────────────────────────────────────────────────

    def _construir_secao_ambiente(self, ambiente: dict):
        self._lay_esq.addWidget(_titulo_secao("📁  Ambiente do Projeto", "#4a90d9"))
        self._lay_esq.addWidget(QLabel(
            "Define onde ficam os pacotes instalados pelo usuário (usados no autocomplete Jedi)."
        ))
        self._lay_esq.addWidget(_separador())

        campos = {
            "pasta_venv":             ("Pasta do venv:", "ex: .venv"),
            "site_packages_windows":  ("Pacotes Windows:", "ex: Lib/site-packages"),
            "site_packages_linux":    ("Pacotes Linux/Mac:", "ex: lib/site-packages"),
        }
        self._w_ambiente: dict[str, QLineEdit] = {}
        for chave, (rotulo, placeholder) in campos.items():
            row = QWidget()
            lay = QHBoxLayout(row)
            lay.setContentsMargins(0, 2, 0, 2)
            lay.setSpacing(10)
            lbl = QLabel(rotulo)
            lbl.setFixedWidth(160)
            lbl.setStyleSheet("font-size:10px; color:#888; font-family:Consolas;")
            w = QLineEdit(str(ambiente.get(chave, "")))
            w.setFixedHeight(24)
            w.setPlaceholderText(placeholder)
            w.setStyleSheet(
                "QLineEdit{background:#0e1a2e;color:#e0e0e0;border:1px solid #1a2e4a;"
                "border-radius:3px;padding:2px 6px;font-size:10px;font-family:Consolas;}"
                "QLineEdit:focus{border-color:#4a90d9;}"
            )
            lay.addWidget(lbl)
            lay.addWidget(w, 1)
            self._w_ambiente[chave] = w
            self._lay_esq.addWidget(row)

    # ── Seção Snippets ────────────────────────────────────────────────────────

    # ⚠️  função grande (51 linhas)
    def _construir_secao_snippets(self, snippets: dict):
        self._lay_esq.addSpacing(16)
        cab_row = QWidget()
        cab_lay = QHBoxLayout(cab_row)
        cab_lay.setContentsMargins(0, 0, 0, 0)
        cab_lay.setSpacing(8)
        cab_lay.addWidget(_titulo_secao("⚡  Snippets de Código", "#e5c07b"))

        btn_add = QPushButton("＋  Novo snippet")
        btn_add.setFixedHeight(22)
        btn_add.setStyleSheet(
            "QPushButton{background:#2a2a0a;color:#e5c07b;border:1px solid #3a3a0a;"
            "padding:1px 10px;font-size:10px;border-radius:3px;}"
            "QPushButton:hover{background:#3a3a15;}"
        )
        btn_add.clicked.connect(self._adicionar_snippet)
        cab_lay.addWidget(btn_add)
        cab_lay.addStretch()
        self._lay_esq.addWidget(cab_row)
        self._lay_esq.addWidget(QLabel(
            "Digite a palavra-chave e pressione Tab/Enter no editor para expandir o snippet."
        ))
        self._lay_esq.addWidget(_separador())

        hdr = QWidget()
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(0, 0, 0, 0)
        hdr_lay.setSpacing(8)
        lbl_n = QLabel("Palavra-chave")
        lbl_n.setFixedWidth(160)
        lbl_n.setStyleSheet("font-size:9px; color:#555; font-family:Consolas;")
        lbl_c = QLabel("Código expandido")
        lbl_c.setStyleSheet("font-size:9px; color:#555; font-family:Consolas;")
        hdr_lay.addWidget(lbl_n)
        hdr_lay.addWidget(QLabel(" "))
        hdr_lay.addWidget(lbl_c, 1)
        self._lay_esq.addWidget(hdr)

        self._container_snippets = QWidget()
        self._lay_snippets = QVBoxLayout(self._container_snippets)
        self._lay_snippets.setContentsMargins(0, 0, 0, 0)
        self._lay_snippets.setSpacing(2)
        self._lay_esq.addWidget(self._container_snippets)

        self._snippet_rows.clear()
        for chave, valor in snippets.items():
            if chave.startswith("_"):
                continue
            self._inserir_snippet_row(chave, str(valor))

        self._lay_esq.addStretch()

    def _inserir_snippet_row(self, nome: str, codigo: str):
        row = _SnippetRow(nome, codigo, on_remover=self._remover_snippet)
        self._lay_snippets.addWidget(row)
        self._snippet_rows.append(row)

    def _adicionar_snippet(self):
        self._inserir_snippet_row("", "")

    def _remover_snippet(self, row: "_SnippetRow"):
        if row in self._snippet_rows:
            self._snippet_rows.remove(row)
        row.setParent(None)
        row.deleteLater()

    # ── Seção Fontes AppData (painel direito) ─────────────────────────────────

    # ⚠️  função grande (72 linhas)
    def _construir_secao_fontes(self, fontes: dict):
        self._lay_dir.addWidget(_titulo_secao("📂  Fontes da Pasta Autocompletar", "#61afef"))
        desc = QLabel(
            "Arquivos lidos de AppData\\autocompletar\\\n"
            "Adicione quantos quiser de cada tipo — todos são mesclados."
        )
        desc.setStyleSheet("font-size:10px; color:#888;")
        self._lay_dir.addWidget(desc)
        self._lay_dir.addWidget(_separador())
        self._lay_dir.addSpacing(6)

        cats = [
            ("palavras", "📝  Palavras  (.txt)",  self._COR_PALAVRAS,
             "palavras.txt",
             "Uma palavra por linha.  # = comentário.\n"
             "Aparece no autocomplete normal enquanto digita."),
            ("simbolos", "🔣  Símbolos  (.json)", self._COR_SIMBOLOS,
             "simbolos.json",
             "{ \"alpha\": \"α\", \"pi\": \"π\" }\n"
             "Digite :alpha no editor → insere α"),
            ("emojis",   "😀  Emojis  (.json)",   self._COR_EMOJIS,
             "emojis.json",
             "{ \"fogo\": \"🔥\", \"ok\": \"✅\" }\n"
             "Digite :fogo no editor → insere 🔥"),
        ]

        for tipo in self._fonte_rows:
            self._fonte_rows[tipo].clear()
        self._lay_fontes_containers.clear()

        for tipo, titulo_txt, cor, placeholder, dica in cats:
            # Cabeçalho da categoria
            hdr = QWidget()
            hdr_lay = QHBoxLayout(hdr)
            hdr_lay.setContentsMargins(0, 6, 0, 2)
            hdr_lay.setSpacing(8)
            hdr_lay.addWidget(_titulo_secao(titulo_txt, cor))
            hdr_lay.addStretch()

            btn_add = QPushButton("＋")
            btn_add.setFixedSize(26, 22)
            btn_add.setToolTip(f"Adicionar arquivo à lista de {tipo}")
            btn_add.setStyleSheet(
                f"QPushButton{{background:#111;color:{cor};border:1px solid {cor}55;"
                f"font-size:12px;border-radius:3px;padding:0;}}"
                f"QPushButton:hover{{background:#222;}}"
            )
            btn_add.clicked.connect(
                lambda checked=False, t=tipo, p=placeholder: self._adicionar_fonte_row(t, p)
            )
            hdr_lay.addWidget(btn_add)
            self._lay_dir.addWidget(hdr)

            # Dica de formato
            lbl_dica = QLabel(dica)
            lbl_dica.setStyleSheet("font-size:9px; color:#555; font-family:Consolas;")
            self._lay_dir.addWidget(lbl_dica)

            # Container das linhas desse tipo
            container = QWidget()
            lay_container = QVBoxLayout(container)
            lay_container.setContentsMargins(0, 4, 0, 0)
            lay_container.setSpacing(2)
            self._lay_dir.addWidget(container)
            self._lay_fontes_containers[tipo] = lay_container

            # Linhas iniciais vindas do JSON
            lista = fontes.get(tipo) or [placeholder]
            for nome_arq in lista:
                self._inserir_fonte_row_em(tipo, nome_arq, lay_container, cor)

        self._lay_dir.addStretch()

    def _inserir_fonte_row_em(self, tipo: str, nome_arquivo: str, lay: QVBoxLayout, cor: str):
        row = _FonteRow(
            nome_arquivo,
            on_remover=lambda r, t=tipo: self._remover_fonte_row(t, r),
            cor_acento=cor,
        )
        lay.addWidget(row)
        self._fonte_rows[tipo].append(row)

    def _adicionar_fonte_row(self, tipo: str, placeholder: str):
        cor_map = {
            "palavras": self._COR_PALAVRAS,
            "simbolos": self._COR_SIMBOLOS,
            "emojis":   self._COR_EMOJIS,
        }
        lay = self._lay_fontes_containers.get(tipo)
        if lay is None:

            return

        cor = cor_map.get(tipo, "#888")
        row = _FonteRow(
            "",
            on_remover=lambda r, t=tipo: self._remover_fonte_row(t, r),
            cor_acento=cor,
        )
        row.w_nome.setPlaceholderText(placeholder)
        lay.addWidget(row)
        self._fonte_rows[tipo].append(row)
        row.w_nome.setFocus()

    def _remover_fonte_row(self, tipo: str, row: "_FonteRow"):
        if row in self._fonte_rows[tipo]:
            self._fonte_rows[tipo].remove(row)
        row.setParent(None)
        row.deleteLater()

    # ── Carregar / Salvar ─────────────────────────────────────────────────────

    def _limpar_painel(self, lay: QVBoxLayout):
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _carregar(self):
        self._limpar_painel(self._lay_esq)
        self._limpar_painel(self._lay_dir)
        self._snippet_rows.clear()
        for k in self._fonte_rows:
            self._fonte_rows[k].clear()
        self._lay_fontes_containers.clear()

        self._dados = _carregar_json(self._arquivo)
        self._ultimo_mtime = (
            os.path.getmtime(self._arquivo) if os.path.isfile(self._arquivo) else 0.0
        )
        ambiente = self._dados.get("ambiente", {})
        snippets = self._dados.get("snippets", {})
        fontes   = self._dados.get("fontes_appdata", {})

        self._construir_secao_ambiente(ambiente)
        self._construir_secao_snippets(snippets)
        self._construir_secao_fontes(fontes)
        self._aplicar_tema()
        self._notificar("Carregado.", cor="#555", duracao=2000)
        log.ok(_ARQ, "_carregar", "autocomplete.json carregado")

    def _coletar_dados(self) -> dict:
        ambiente = {"_descricao": self._dados.get("ambiente", {}).get("_descricao", "")}
        for chave, widget in self._w_ambiente.items():
            ambiente[chave] = widget.text().strip()

        snippets = {"_descricao": self._dados.get("snippets", {}).get("_descricao", "")}
        for row in self._snippet_rows:
            nome, codigo = row.dados()
            if nome:
                snippets[nome] = codigo

        fontes_appdata: dict = {}
        for tipo, rows in self._fonte_rows.items():
            nomes = [r.dados() for r in rows if r.dados()]
            if nomes:
                fontes_appdata[tipo] = nomes

        return {

            "_descricao":     self._dados.get("_descricao", ""),
            "_instrucoes":    self._dados.get("_instrucoes", ""),
            "ambiente":       ambiente,
            "snippets":       snippets,
            "fontes_appdata": fontes_appdata,
        }

    def _salvar(self):
        self._salvando = True
        try:
            dados = self._coletar_dados()
            if _salvar_json(self._arquivo, dados):
                self._dados = dados
                self._notificar("✓  Salvo! Autocomplete atualizado.", cor="#98c379")
                log.ok(_ARQ, "_salvar", "autocomplete.json salvo pelo AutocompleteExplorer")
            else:
                self._notificar("⚠  Erro ao salvar.", cor="#e06c75")
        finally:
            QTimer.singleShot(1200, lambda: setattr(self, "_salvando", False))

    # ── Utilitários ───────────────────────────────────────────────────────────

    def _pasta_autocompletar(self) -> str | None:
        """Resolve (e garante que existe) a pasta AppData/autocompletar/."""
        try:
            from _APPDATA_ import appdata
            pasta = appdata.autocompletar
        except Exception:
            try:
                from _CONFIGURA_ import PASTA_APPDATA
                pasta = os.path.join(PASTA_APPDATA, "autocompletar")
            except Exception:

                return None

        os.makedirs(pasta, exist_ok=True)

        return pasta

    def _abrir_pasta_autocompletar(self):
        """Abre AppData/autocompletar/ no gerenciador de arquivos do SO."""
        pasta = self._pasta_autocompletar()
        if not pasta:

            return

        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", pasta])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", pasta])
            else:
                subprocess.Popen(["xdg-open", pasta])
            self._notificar(f"📂  Abrindo: {pasta}", cor="#61afef", duracao=4000)
        except Exception as e:
            log.aviso(_ARQ, "_abrir_pasta_autocompletar", str(e))

    _ESQUELETO = {
        "palavras": "# Uma palavra por linha -- aparecem no autocomplete do editor.\n# Linhas comecando com # sao ignoradas.\n",
        "simbolos": '{\n  "_dica": "Adicione pares nome: caractere. Digite :nome no editor.",\n  "exemplo": "→"\n}\n',
        "emojis":   '{\n  "_dica": "Adicione pares nome: emoji. Digite :nome no editor.",\n  "exemplo": "🚀"\n}\n',
    }
    _EXT_ESPERADA = {"palavras": ".txt", "simbolos": ".json", "emojis": ".json"}

    def _criar_arquivo_fonte(self):
        """
        Pede o tipo e o nome do arquivo, cria fisicamente em AppData/autocompletar/
        com esqueleto inicial valido e insere a linha no painel direito.
        """
        tipo, ok = QInputDialog.getItem(
            self, "Criar arquivo de fonte",
            "Tipo do arquivo:",
            ["palavras  (.txt)", "simbolos  (.json)", "emojis  (.json)"],
            0, False,
        )
        if not ok:

            return

        tipo_chave = tipo.split()[0]   # "palavras", "simbolos" ou "emojis"
        ext        = self._EXT_ESPERADA[tipo_chave]
        sugestao   = f"minhas_{tipo_chave}{ext}"

        nome, ok2 = QInputDialog.getText(
            self, "Nome do arquivo",
            f"Nome do arquivo ({ext}):",
            text=sugestao,
        )
        if not ok2:

            return

        nome = nome.strip()
        if not nome:

            return

        if not nome.lower().endswith(ext):
            nome += ext

        pasta = self._pasta_autocompletar()
        if not pasta:
            self._notificar("⚠  Nao foi possivel localizar a pasta AppData.", cor="#e06c75")

            return

        caminho = os.path.join(pasta, nome)

        if os.path.isfile(caminho):
            self._notificar(f"⚠  Arquivo ja existe: {nome}", cor="#e5c07b", duracao=5000)
        else:
            try:
                with open(caminho, "w", encoding="utf-8") as f:
                    f.write(self._ESQUELETO[tipo_chave])
                self._notificar(f"✓  Criado: {nome}", cor="#98c379", duracao=5000)
                log.ok(_ARQ, "_criar_arquivo_fonte", f"criado {caminho}")
            except Exception as e:
                self._notificar(f"⚠  Erro ao criar: {e}", cor="#e06c75")
                log.erro(_ARQ, "_criar_arquivo_fonte", str(e))

                return

        # Insere linha no painel direito (independente de ter criado ou ja existia)
        cor_map = {
            "palavras": self._COR_PALAVRAS,
            "simbolos": self._COR_SIMBOLOS,
            "emojis":   self._COR_EMOJIS,
        }
        lay = self._lay_fontes_containers.get(tipo_chave)
        if lay is not None:
            cor = cor_map[tipo_chave]
            self._inserir_fonte_row_em(tipo_chave, nome, lay, cor)

    # 💡 cor_opc = Literal["#e0e0e0"] ← defina os valores válidos
    def _notificar(self, msg: str, cor: str = "#e0e0e0", duracao: int = 4000):
        self._lbl_status.setText(msg)
        self._lbl_status.setStyleSheet(f"font-size:10px; color:{cor};")
        QTimer.singleShot(duracao, lambda: self._lbl_status.setText(""))

    def _aplicar_tema(self):
        t       = tema_global()
        fundo   = t.cor("terminal.fundo",            "#020202")
        toolbar = t.cor("interface.fundo_toolbar",   "#0F1210")
        borda   = t.cor("interface.borda",           "#1a2e1a")
        texto   = t.cor("interface.texto",           "#e0e0e0")
        fraco   = t.cor("editor.numero_linha",       "#555555")
        thumb   = t.cor("interface.scrollbar_thumb", "#264f78")

        self._cab.setStyleSheet(f"background:{toolbar}; border-bottom:1px solid {borda};")
        self._rodape.setStyleSheet(
            f"font-size:10px; color:{fraco}; background:{fundo}; padding-right:10px;"
        )
        self._splitter.setStyleSheet(
            f"QSplitter::handle {{ background:{borda}; }}"
        )
        self.setStyleSheet(f"""
            QWidget {{ background:{fundo}; color:{texto}; }}
            QScrollArea {{ border:none; background:{fundo}; }}
            QScrollBar:vertical {{
                background:transparent; width:8px; border:none;
            }}
            QScrollBar::handle:vertical {{
                background:{thumb}; border-radius:4px; min-height:20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
            QLabel {{ background:transparent; }}
            QFrame[frameShape="4"] {{ color:{borda}; }}
        """)

    def atualizar_tema(self, tema: dict = None):
        self._aplicar_tema()
