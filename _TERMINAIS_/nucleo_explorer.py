# 📁 _TERMINAIS_/nucleo_explorer.py
"""
NucleoExplorer — painel visual para nucleo.json.

Seções:
  • Formatador  — listas de pastas/arquivos a ignorar, prefixos, stdlib
  • Diagnóstico — limites numéricos + alertas booleanos
  • Índice      — listas de pastas/arquivos a ignorar (separadas do formatador)
  • Ambiente    — pasta_venv
  • IA          — provedor_preferido (dropdown ollama/rede)
  • Documentador— system_prompt (caixa de texto grande)
  • Exportar    — 4 checkboxes de geração

Chaves que começam com _ (como _descricao, _nota) são exibidas como dica de
ferramenta / legenda e não são editáveis, mas são preservadas ao salvar.
"""

import json
import os
import re
from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QVBoxLayout, QWidget,
)

from _CONFIGURA_ import ARQUIVO_NUCLEO
from _CONFIGURA_.gerenciador_tema import tema_global
from _LOG_.log import log
from _UTILITARIOS_.icones import icone_tema
from _UTILITARIOS_._ajuda_ import criar_botao_ajuda

_ARQ = "nucleo_explorer.py"

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
            json.dump(dados, f, ensure_ascii=False, indent=4)

        return True

    except Exception as e:
        log.erro(_ARQ, "_salvar_json", str(e))

        return False

def _sep():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFixedHeight(1)

    return f

# 💡 cor_opc = Literal["#4a90d9"] ← defina os valores válidos
def _titulo(texto: str, cor: str = "#4a90d9") -> QLabel:
    lbl = QLabel(texto)
    lbl.setStyleSheet(
        f"font-size:11px; font-weight:bold; color:{cor};"
        f" font-family:Consolas; padding:4px 0 2px 0;"
    )

    return lbl

def _dica(texto: str) -> QLabel:
    lbl = QLabel(texto)
    fraco = tema_global().cor("editor.numero_linha", "#555555")
    lbl.setStyleSheet(f"font-size:9px; color:{fraco}; padding-bottom:4px;")
    lbl.setWordWrap(True)
    return lbl

def _label_campo(texto: str, largura: int = 200) -> QLabel:
    lbl = QLabel(texto)
    if largura:
        lbl.setFixedWidth(largura)
    fraco = tema_global().cor("editor.numero_linha", "#888888")
    lbl.setStyleSheet(f"font-size:10px; color:{fraco}; font-family:Consolas;")
    return lbl

def _lineedit(valor: str, cor_borda: str = "") -> QLineEdit:
    t      = tema_global()
    fundo  = t.cor("terminal.fundo",  "#0a0e14")
    texto  = t.cor("interface.texto", "#e0e0e0")
    borda  = cor_borda or t.cor("interface.borda", "#1a2e4a")
    foco   = t.cor("grafo.no_texto",  "#4a90d9")
    w = QLineEdit(str(valor))
    w.setFixedHeight(24)
    w.setStyleSheet(
        f"QLineEdit{{background:{fundo};color:{texto};border:1px solid {borda};"
        f"border-radius:3px;padding:2px 6px;font-size:10px;font-family:Consolas;}}"
        f"QLineEdit:focus{{border-color:{foco};}}"
    )
    return w

def _textarea(conteudo: str, altura: int = 80, cor_borda: str = "") -> QPlainTextEdit:
    t      = tema_global()
    fundo  = t.cor("terminal.fundo",  "#0a0e14")
    texto  = t.cor("interface.texto", "#e0e0e0")
    borda  = cor_borda or t.cor("interface.borda", "#1a2e4a")
    foco   = t.cor("grafo.no_texto",  "#4a90d9")
    w = QPlainTextEdit(conteudo)
    w.setFixedHeight(altura)
    w.setStyleSheet(
        f"QPlainTextEdit{{background:{fundo};color:{texto};border:1px solid {borda};"
        f"border-radius:3px;padding:4px 6px;font-size:10px;font-family:Consolas;}}"
        f"QPlainTextEdit:focus{{border-color:{foco};}}"
    )
    return w

def _lista_para_texto(lst: list) -> str:

    return "\n".join(str(x) for x in lst) if lst else ""

def _texto_para_lista(texto: str) -> list:

    return [x.strip() for x in texto.splitlines() if x.strip()]

def _row(label_texto: str, widget: QWidget, largura_label: int = 200) -> QWidget:
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 2, 0, 2)
    lay.setSpacing(10)
    lay.addWidget(_label_campo(label_texto, largura_label))
    lay.addWidget(widget, 1)

    return row

# ═════════════════════════════════════════════════════════════════════
# Widget principal
# ═════════════════════════════════════════════════════════════════════

class NucleoExplorer(QWidget):
    """Painel visual para nucleo.json — configurações avançadas do núcleo da IDE."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dados: dict = {}
        self._w: dict = {}          # chave_flat → widget
        self._arquivo = ARQUIVO_NUCLEO
        self._salvando = False
        self._construir_ui()
        self._carregar()
        self._aplicar_tema()
        self._iniciar_watcher()

    # ─────────────────────────────────────────────────────────────────
    # Watcher — sincroniza controles quando o arquivo muda no editor
    # ─────────────────────────────────────────────────────────────────

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

    # ── UI estática (cabeçalho + scroll) ─────────────────────────────

    # ⚠️  função grande (61 linhas)
    def _construir_ui(self):
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # Cabeçalho
        self._cab = QWidget()
        self._cab.setFixedHeight(36)
        lay_cab = QHBoxLayout(self._cab)
        lay_cab.setContentsMargins(12, 0, 10, 0)
        lay_cab.setSpacing(8)

        lbl = QLabel("Núcleo — nucleo.json")
        lbl.setPixmap(icone_tema("mdi.cog").pixmap(16,16))
        lbl.setStyleSheet("font-size:12px; font-weight:bold; font-family:Consolas; color:#e0e0e0;")
        lay_cab.addWidget(lbl)
        lay_cab.addStretch()

        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("font-size:10px; color:#666;")
        lay_cab.addWidget(self._lbl_status)

        btn_ajuda = criar_botao_ajuda(
            _ajuda_nucleo.texto,
            titulo="Como usar — nucleo.json",
            tooltip="Como funciona o Núcleo",
            parent=self,
        )
        lay_cab.addWidget(btn_ajuda)

        btn_rec = QPushButton("Recarregar")
        btn_rec.setIcon(icone_tema("mdi.refresh"))
        btn_rec.setFixedHeight(24)
        btn_rec.setStyleSheet(
            "QPushButton{background:#1a1a1a;color:#888;border:none;padding:2px 10px;"
            "font-size:10px;border-radius:3px;} QPushButton:hover{color:#e0e0e0;}"
        )
        btn_rec.clicked.connect(self._carregar)
        lay_cab.addWidget(btn_rec)

        self._btn_salvar = QPushButton("Salvar nucleo.json")
        self._btn_salvar.setIcon(icone_tema("mdi.upload"))
        self._btn_salvar.setFixedHeight(24)
        self._btn_salvar.setStyleSheet(
            "QPushButton{background:#1a3a1a;color:#98c379;border:none;padding:2px 14px;"
            "font-size:10px;border-radius:3px;} QPushButton:hover{background:#264f28;}"
        )
        self._btn_salvar.clicked.connect(self._salvar)
        lay_cab.addWidget(self._btn_salvar)
        raiz.addWidget(self._cab)

        raiz.addWidget(_sep())

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._corpo = QWidget()
        self._lay_corpo = QVBoxLayout(self._corpo)
        self._lay_corpo.setContentsMargins(16, 14, 16, 24)
        self._lay_corpo.setSpacing(4)
        self._scroll.setWidget(self._corpo)
        raiz.addWidget(self._scroll, 1)

        self._rodape = QLabel(
            "Listas: um item por linha. Alterações aplicadas após reiniciar a operação em andamento."
        )
        self._rodape.setFixedHeight(20)
        self._rodape.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        raiz.addWidget(self._rodape)

    # ── Seção: Formatador ─────────────────────────────────────────────

    # ⚠️  função grande (56 linhas)
    def _secao_formatador(self, dados: dict):
        lbl_ico = QLabel()
        lbl_ico.setPixmap(icone_tema("mdi.wrench").pixmap(14, 14))
        self._lay_corpo.addWidget(lbl_ico)
        self._lay_corpo.addWidget(_titulo("Formatador de Código", "#4a90d9"))
        self._lay_corpo.addWidget(_dica(dados.get("_descricao", "")))
        self._lay_corpo.addWidget(_sep())

        for chave, rotulo, alt in [
            ("pastas_ignorar",          "Pastas a ignorar:",         80),
            ("arquivos_ignorar",        "Arquivos a ignorar:",       80),
            ("palavras_pulo_linha",     "Palavras de pulo de linha:", 56),
            ("prefixos_modulos_locais", "Prefixos módulos locais:",  56),
        ]:
            valor = dados.get(chave, [])
            w = _textarea(_lista_para_texto(valor), altura=alt)
            self._w[f"formatar.{chave}"] = w
            col = QWidget()
            lay = QVBoxLayout(col)
            lay.setContentsMargins(0, 4, 0, 4)
            lay.setSpacing(2)
            lay.addWidget(_label_campo(rotulo, 0))
            lay.addWidget(w)
            self._lay_corpo.addWidget(col)

        # stdlib — grande, um pouco mais alto
        stdlib = dados.get("stdlib_modulos", [])
        w_std = _textarea(_lista_para_texto(stdlib), altura=120)
        self._w["formatar.stdlib_modulos"] = w_std
        col_std = QWidget()
        lay_std = QVBoxLayout(col_std)
        lay_std.setContentsMargins(0, 4, 0, 4)
        lay_std.setSpacing(2)
        lay_std.addWidget(_label_campo(
            "Módulos tratados como stdlib:", 0))
        lay_std.addWidget(_dica(
            "Use para forçar um pacote de terceiros a ser ordenado como stdlib nos imports."))
        lay_std.addWidget(w_std)
        self._lay_corpo.addWidget(col_std)

        # pastas_fixas_ignorar — somente leitura (defaults do sistema)
        fixas = dados.get("pastas_fixas_ignorar", [])
        w_fixas = _textarea(_lista_para_texto(fixas), altura=56)
        w_fixas.setReadOnly(True)
        w_fixas.setToolTip("Pastas sempre ignoradas pelo sistema — não editável aqui.")
        self._w["formatar.pastas_fixas_ignorar"] = w_fixas
        col_f = QWidget()
        lay_f = QVBoxLayout(col_f)
        lay_f.setContentsMargins(0, 4, 0, 4)
        lay_f.setSpacing(2)
        lbl_f = _label_campo("Pastas fixas (sistema):", 0)
        lbl_f.setStyleSheet("font-size:10px; color:#444; font-family:Consolas;")
        lay_f.addWidget(lbl_f)
        lay_f.addWidget(_dica("Sempre ignoradas — .venv, .git, __pycache__, etc. (somente leitura)"))
        lay_f.addWidget(w_fixas)
        self._lay_corpo.addWidget(col_f)

    # ── Seção: Diagnóstico ────────────────────────────────────────────

    def _secao_diagnostico(self, dados: dict):
        self._lay_corpo.addSpacing(12)
        lbl_ico = QLabel()
        lbl_ico.setPixmap(icone_tema("mdi.magnify").pixmap(14, 14))
        self._lay_corpo.addWidget(lbl_ico)
        self._lay_corpo.addWidget(_titulo("Diagnóstico AST", "#c678dd"))
        self._lay_corpo.addWidget(_dica(dados.get("_descricao", "")))
        self._lay_corpo.addWidget(_sep())

        for chave, rotulo, maximo in [
            ("limite_linhas_funcao",  "Limite de linhas por função:",  9999),
            ("limite_linhas_arquivo", "Limite de linhas por arquivo:", 9999),
            ("limite_arquivos_pasta", "Limite de arquivos por pasta:", 9999),
        ]:
            spin = QSpinBox()
            spin.setRange(1, maximo)
            spin.setValue(int(dados.get(chave, 50)))
            spin.setFixedHeight(24)
            spin.setFixedWidth(100)
            spin.setStyleSheet(
                "QSpinBox{background:#0a0e14;color:#e0e0e0;border:1px solid #2a1a4a;"
                "border-radius:3px;padding:2px 6px;font-size:10px;font-family:Consolas;}"
            )
            self._w[f"diagnostico.{chave}"] = spin
            self._lay_corpo.addWidget(_row(rotulo, spin))

        for chave, rotulo in [
            ("alertar_funcoes_nao_chamadas",    "Alertar funções não chamadas"),
            ("alertar_dependencias_circulares", "Alertar dependências circulares"),
            ("alertar_modulos_sem_init",        "Alertar módulos sem __init__"),
        ]:
            cb = QCheckBox(rotulo)
            cb.setChecked(bool(dados.get(chave, True)))
            cb.setStyleSheet(
                "QCheckBox{font-size:10px;color:#c678dd;font-family:Consolas;}"
                "QCheckBox::indicator{width:14px;height:14px;}"
            )
            self._w[f"diagnostico.{chave}"] = cb
            self._lay_corpo.addWidget(cb)

    # ── Seção: Índice ─────────────────────────────────────────────────

    def _secao_indice(self, dados: dict):
        self._lay_corpo.addSpacing(12)
        lbl_ico = QLabel()
        lbl_ico.setPixmap(icone_tema("mdi.folder-multiple").pixmap(14, 14))
        self._lay_corpo.addWidget(lbl_ico)
        self._lay_corpo.addWidget(_titulo("Índice AST", "#e5c07b"))
        self._lay_corpo.addWidget(_dica(
            "Se vazio, usa os mesmos valores do Formatador. "
            "Liste aqui só se quiser comportamento diferente para o índice."))
        self._lay_corpo.addWidget(_sep())

        for chave, rotulo, alt in [
            ("pastas_ignorar",   "Pastas a ignorar:", 56),
            ("arquivos_ignorar", "Arquivos a ignorar:", 56),
        ]:
            valor = dados.get(chave, [])
            w = _textarea(_lista_para_texto(valor), altura=alt, cor_borda="#2e2a0a")
            self._w[f"indice.{chave}"] = w
            col = QWidget()
            lay = QVBoxLayout(col)
            lay.setContentsMargins(0, 4, 0, 4)
            lay.setSpacing(2)
            lay.addWidget(_label_campo(rotulo, 0))
            lay.addWidget(w)
            self._lay_corpo.addWidget(col)

        # extensoes_texto
        ext_txt = dados.get("extensoes_texto", [])
        w_ext = _textarea(_lista_para_texto(ext_txt), altura=80, cor_borda="#2e2a0a")
        self._w["indice.extensoes_texto"] = w_ext
        col_ext = QWidget()
        lay_ext = QVBoxLayout(col_ext)
        lay_ext.setContentsMargins(0, 4, 0, 4)
        lay_ext.setSpacing(2)
        lay_ext.addWidget(_label_campo("Extensões de texto:", 0))
        lay_ext.addWidget(_dica(
            "Extensões contadas na soma total de linhas — altera o número de 'Analisar projeto'."))
        lay_ext.addWidget(w_ext)
        self._lay_corpo.addWidget(col_ext)

    # ── Seção: Ambiente ───────────────────────────────────────────────

    def _secao_ambiente(self, dados: dict):
        self._lay_corpo.addSpacing(12)
        lbl_ico = QLabel()
        lbl_ico.setPixmap(icone_tema("mdi.package-variant").pixmap(14, 14))
        self._lay_corpo.addWidget(lbl_ico)
        self._lay_corpo.addWidget(_titulo("Ambiente do Projeto", "#4ec994"))
        self._lay_corpo.addWidget(_dica(dados.get("_descricao", "")))
        self._lay_corpo.addWidget(_sep())

        w = _lineedit(str(dados.get("pasta_venv", ".venv")), cor_borda="#0a3a1a")
        self._w["ambiente.pasta_venv"] = w
        self._lay_corpo.addWidget(_row("Pasta do ambiente virtual:", w))

    # ── Seção: IA ─────────────────────────────────────────────────────

    def _secao_ia(self, dados: dict):
        self._lay_corpo.addSpacing(12)
        lbl_ico = QLabel()
        lbl_ico.setPixmap(icone_tema("mdi.robot").pixmap(14, 14))
        self._lay_corpo.addWidget(lbl_ico)
        self._lay_corpo.addWidget(_titulo("IA — Configurações", "#e06c75"))
        self._lay_corpo.addWidget(_dica(
            "Escolha o provedor de IA que o Núcleo usa para análises e documentação."))
        self._lay_corpo.addWidget(_sep())

        combo = QComboBox()
        combo.addItems(["ollama", "rede"])
        provedor = str(dados.get("provedor_preferido", "ollama"))
        idx = combo.findText(provedor)
        combo.setCurrentIndex(max(idx, 0))
        combo.setFixedHeight(24)
        combo.setFixedWidth(120)
        combo.setStyleSheet(
            "QComboBox{background:#0a0e14;color:#e0e0e0;border:1px solid #2e0a0a;"
            "border-radius:3px;padding:2px 6px;font-size:10px;font-family:Consolas;}"
            "QComboBox::drop-down{border:none;}"
            "QComboBox QAbstractItemView{background:#0a0e14;color:#e0e0e0;}"
        )
        self._w["ia.provedor_preferido"] = combo

        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(10)
        lay.addWidget(_label_campo("Provedor preferido:"))
        lay.addWidget(combo)
        lay.addWidget(_dica("ollama = IA local no computador   |   rede = provedor configurado na IDE"))
        lay.addStretch()
        self._lay_corpo.addWidget(row)

    # ── Seção: Documentador ───────────────────────────────────────────

    def _secao_documentador(self, dados: dict):
        self._lay_corpo.addSpacing(12)
        lbl_ico = QLabel()
        lbl_ico.setPixmap(icone_tema("mdi.file-document").pixmap(14, 14))
        self._lay_corpo.addWidget(lbl_ico)
        self._lay_corpo.addWidget(_titulo("Documentador com IA", "#4a90d9"))
        self._lay_corpo.addWidget(_dica(dados.get("_descricao", "")))
        self._lay_corpo.addWidget(_sep())

        w = _textarea(str(dados.get("system_prompt", "")), altura=80, cor_borda="#0a1a2e")
        self._w["documentador.system_prompt"] = w
        col = QWidget()
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(2)
        lay.addWidget(_label_campo("Instrução de sistema para a IA:", 0))
        lay.addWidget(w)
        self._lay_corpo.addWidget(col)

        # min_arquivos_pasta
        spin_min = QSpinBox()
        spin_min.setRange(1, 999)
        spin_min.setValue(int(dados.get("min_arquivos_pasta", 1)))
        spin_min.setFixedHeight(24)
        spin_min.setFixedWidth(80)
        t = tema_global()
        spin_min.setStyleSheet(
            f"QSpinBox{{background:{t.cor('terminal.fundo','#0a0e14')};"
            f"color:{t.cor('interface.texto','#e0e0e0')};border:1px solid #0a1a2e;"
            "border-radius:3px;padding:2px 6px;font-size:10px;font-family:Consolas;}"
        )
        self._w["documentador.min_arquivos_pasta"] = spin_min
        self._lay_corpo.addWidget(_row("Mínimo de arqs. por pasta:", spin_min))
        self._lay_corpo.addWidget(_dica(
            "Pastas com menos arquivos que esse valor são ignoradas pelo documentador."))

        # extensoes_docaveis
        ext_doc = dados.get("extensoes_docaveis", [])
        w_ext_doc = _textarea(_lista_para_texto(ext_doc), altura=100, cor_borda="#0a1a2e")
        self._w["documentador.extensoes_docaveis"] = w_ext_doc
        col_ext = QWidget()
        lay_ext = QVBoxLayout(col_ext)
        lay_ext.setContentsMargins(0, 4, 0, 4)
        lay_ext.setSpacing(2)
        lay_ext.addWidget(_label_campo("Extensões documentáveis:", 0))
        lay_ext.addWidget(_dica(
            "Extensões que o documentador considera ao varrer pastas sem Python."))
        lay_ext.addWidget(w_ext_doc)
        self._lay_corpo.addWidget(col_ext)

    # ── Seção: Exportar ───────────────────────────────────────────────

    def _secao_exportar(self, dados: dict):
        self._lay_corpo.addSpacing(12)
        lbl_ico = QLabel()
        lbl_ico.setPixmap(icone_tema("mdi.export").pixmap(14, 14))
        self._lay_corpo.addWidget(lbl_ico)
        self._lay_corpo.addWidget(_titulo("Exportar (pasta NUCLEO/)", "#98c379"))
        self._lay_corpo.addWidget(_dica(dados.get("_descricao", "")))
        self._lay_corpo.addWidget(_sep())

        opcoes = [
            ("gerar_readme",        "Gerar README do projeto"),
            ("gerar_arquitetura",   "Gerar mapa de arquitetura"),
            ("gerar_documentacao",  "Gerar documentação das funções"),
            ("gerar_antes_do_push", "Regenerar automaticamente antes de cada push pro GitHub"),
        ]
        for chave, rotulo in opcoes:
            cb = QCheckBox(rotulo)
            cb.setChecked(bool(dados.get(chave, True)))
            cb.setStyleSheet(
                "QCheckBox{font-size:10px;color:#98c379;font-family:Consolas;padding:2px 0;}"
                "QCheckBox::indicator{width:14px;height:14px;}"
            )
            self._w[f"exportar.{chave}"] = cb
            self._lay_corpo.addWidget(cb)

    # ── Carregar / Salvar ─────────────────────────────────────────────

    def _limpar_corpo(self):
        while self._lay_corpo.count():
            item = self._lay_corpo.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._w.clear()

    def _carregar(self):
        self._limpar_corpo()
        self._dados = _carregar_json(self._arquivo)

        self._secao_formatador(self._dados.get("formatar",     {}))
        self._secao_diagnostico(self._dados.get("diagnostico", {}))
        self._secao_indice(self._dados.get("indice",           {}))
        self._secao_ambiente(self._dados.get("ambiente",       {}))
        self._secao_ia(self._dados.get("ia",                   {}))
        self._secao_documentador(self._dados.get("documentador",{}))
        self._secao_exportar(self._dados.get("exportar",       {}))
        self._lay_corpo.addStretch()

        self._aplicar_tema()
        self._notificar("Carregado.", cor="#555", duracao=2000)
        self._ultimo_mtime = os.path.getmtime(self._arquivo) if os.path.isfile(self._arquivo) else 0.0
        log.ok(_ARQ, "_carregar", "nucleo.json carregado no NucleoExplorer")

    # ⚠️  função grande (78 linhas)
    def _coletar_dados(self) -> dict:
        dados = {}

        # Preserva a _descricao raiz
        if "_descricao" in self._dados:
            dados["_descricao"] = self._dados["_descricao"]

        # ── formatar ──
        f_orig = self._dados.get("formatar", {})
        formatar = {k: v for k, v in f_orig.items() if k.startswith("_")}
        for chave in ("pastas_ignorar", "arquivos_ignorar", "palavras_pulo_linha",
                      "prefixos_modulos_locais", "stdlib_modulos"):
            w = self._w.get(f"formatar.{chave}")
            if w:
                formatar[chave] = _texto_para_lista(w.toPlainText())
        # pastas_fixas_ignorar — preserva o original (read-only)
        if "pastas_fixas_ignorar" in f_orig:
            formatar["pastas_fixas_ignorar"] = f_orig["pastas_fixas_ignorar"]
        dados["formatar"] = formatar

        # ── diagnostico ──
        d_orig = self._dados.get("diagnostico", {})
        diagnostico = {k: v for k, v in d_orig.items() if k.startswith("_")}
        for chave in ("limite_linhas_funcao", "limite_linhas_arquivo", "limite_arquivos_pasta"):
            w = self._w.get(f"diagnostico.{chave}")
            if w:
                diagnostico[chave] = w.value()
        for chave in ("alertar_funcoes_nao_chamadas", "alertar_dependencias_circulares",
                      "alertar_modulos_sem_init"):
            w = self._w.get(f"diagnostico.{chave}")
            if w:
                diagnostico[chave] = w.isChecked()
        dados["diagnostico"] = diagnostico

        # ── indice ──
        i_orig = self._dados.get("indice", {})
        indice = {k: v for k, v in i_orig.items() if k.startswith("_")}
        for chave in ("pastas_ignorar", "arquivos_ignorar", "extensoes_texto"):
            w = self._w.get(f"indice.{chave}")
            if w:
                indice[chave] = _texto_para_lista(w.toPlainText())
        dados["indice"] = indice

        # ── ambiente ──
        a_orig = self._dados.get("ambiente", {})
        ambiente = {k: v for k, v in a_orig.items() if k.startswith("_")}
        w = self._w.get("ambiente.pasta_venv")
        if w:
            ambiente["pasta_venv"] = w.text().strip()
        dados["ambiente"] = ambiente

        # ── ia ──
        ia_orig = self._dados.get("ia", {})
        ia = {k: v for k, v in ia_orig.items() if k.startswith("_")}
        w = self._w.get("ia.provedor_preferido")
        if w:
            ia["provedor_preferido"] = w.currentText()
        dados["ia"] = ia

        # ── documentador ──
        doc_orig = self._dados.get("documentador", {})
        documentador = {k: v for k, v in doc_orig.items() if k.startswith("_")}
        w = self._w.get("documentador.system_prompt")
        if w:
            documentador["system_prompt"] = w.toPlainText()
        w_min = self._w.get("documentador.min_arquivos_pasta")
        if w_min:
            documentador["min_arquivos_pasta"] = w_min.value()
        w_ext = self._w.get("documentador.extensoes_docaveis")
        if w_ext:
            documentador["extensoes_docaveis"] = _texto_para_lista(w_ext.toPlainText())
        dados["documentador"] = documentador

        # ── exportar ──
        e_orig = self._dados.get("exportar", {})
        exportar = {k: v for k, v in e_orig.items() if k.startswith("_")}
        for chave in ("gerar_readme", "gerar_arquitetura", "gerar_documentacao",
                      "gerar_antes_do_push"):
            w = self._w.get(f"exportar.{chave}")
            if w:
                exportar[chave] = w.isChecked()
        dados["exportar"] = exportar

        return dados

    def _salvar(self):
        self._salvando = True
        try:
            dados = self._coletar_dados()
            if _salvar_json(self._arquivo, dados):
                self._dados = dados
                self._notificar("✓  Salvo! Reinicie a operação para aplicar.", cor="#98c379")
                log.ok(_ARQ, "_salvar", "nucleo.json salvo pelo NucleoExplorer")
            else:
                self._notificar("⚠  Erro ao salvar — verifique o log.", cor="#e06c75")
        finally:
            QTimer.singleShot(1200, lambda: setattr(self, "_salvando", False))

    # ── Utilitários ───────────────────────────────────────────────────

    # 💡 cor_opc = Literal["#e0e0e0"] ← defina os valores válidos
    def _notificar(self, msg: str, cor: str = "#e0e0e0", duracao: int = 4000):
        self._lbl_status.setText(msg)
        self._lbl_status.setStyleSheet(f"font-size:10px; color:{cor};")
        QTimer.singleShot(duracao, lambda: self._lbl_status.setText(""))

    def _aplicar_tema(self):
        t      = tema_global()
        fundo  = t.cor("terminal.fundo",             "#020202")
        toolbar= t.cor("interface.fundo_toolbar",    "#0F1210")
        borda  = t.cor("interface.borda",            "#1a2e1a")
        texto  = t.cor("interface.texto",            "#e0e0e0")
        fraco  = t.cor("editor.numero_linha",        "#555555")
        thumb  = t.cor("interface.scrollbar_thumb",  "#264f78")

        self._cab.setStyleSheet(f"background:{toolbar}; border-bottom:1px solid {borda};")
        self._rodape.setStyleSheet(
            f"font-size:10px; color:{fraco}; background:{fundo}; padding-right:10px;"
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
