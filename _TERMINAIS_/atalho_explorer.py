# 📁 _TERMINAIS_/atalho_explorer.py
"""
AtalhoExplorer — painel visual para atalhos.json.

Exibe cada grupo de contexto (Busca, Global, Editor, Workspace, Terminal)
como uma seção. Cada linha mostra:
  [QLineEdit — tecla editável]  →  [QLabel — ação do sistema]

O usuário edita a TECLA; a ação é somente leitura para preservar a integridade
das chamadas internas. Salvar grava direto no arquivo — o gerenciador_atalhos
detecta a mudança via QFileSystemWatcher e aplica em tempo real.
"""

import json
import os
import re
from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from _CONFIGURA_ import ARQUIVO_ATALHOS
from _CONFIGURA_.gerenciador_tema import tema_global
from _LOG_.log import log
_ARQ = "atalho_explorer.py"

# Cores fixas para badges de contexto
_COR_CONTEXTO = {
    "Busca":     "#4a90d9",
    "Global":    "#4ec994",
    "Editor":    "#e5c07b",
    "Workspace": "#c678dd",
    "Terminal":  "#e06c75",
}
_COR_PADRAO = "#888888"

def _carregar_json(caminho: str) -> list:
    """Lê atalhos.json (array) ignorando comentários //."""
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

        return []

def _salvar_json(caminho: str, dados: list) -> bool:
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

        return True

    except Exception as e:
        log.erro(_ARQ, "_salvar_json", str(e))

        return False

# ═════════════════════════════════════════════════════════════════════
# Widget principal
# ═════════════════════════════════════════════════════════════════════

class AtalhoExplorer(QWidget):
    """
    Painel visual para atalhos.json.
    Cada grupo de contexto vira uma seção com linhas [tecla ↔ ação].
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dados: list = []
        # [{contexto, descricao, linhas: [{acao, widget_tecla}]}]
        self._grupos: list = []
        self._arquivo = ARQUIVO_ATALHOS
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

    # ── UI estática ───────────────────────────────────────────────────

    # ⚠️  função grande (64 linhas)
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

        lbl = QLabel("⌨  Atalhos de Teclado — atalhos.json")
        lbl.setStyleSheet("font-size:12px; font-weight:bold; font-family:Consolas; color:#e0e0e0;")
        lay_cab.addWidget(lbl)
        lay_cab.addStretch()

        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("font-size:10px; color:#666;")
        lay_cab.addWidget(self._lbl_status)

        btn_recarregar = QPushButton("↺  Recarregar")
        btn_recarregar.setFixedHeight(24)
        btn_recarregar.setStyleSheet(
            "QPushButton{background:#1a1a1a;color:#888;border:none;padding:2px 10px;"
            "font-size:10px;border-radius:3px;} QPushButton:hover{color:#e0e0e0;}"
        )
        btn_recarregar.clicked.connect(self._carregar)
        lay_cab.addWidget(btn_recarregar)

        self._btn_salvar = QPushButton("⬆  Salvar atalhos.json")
        self._btn_salvar.setFixedHeight(24)
        self._btn_salvar.setStyleSheet(
            "QPushButton{background:#1a3a1a;color:#98c379;border:none;padding:2px 14px;"
            "font-size:10px;border-radius:3px;} QPushButton:hover{background:#264f28;}"
        )
        self._btn_salvar.clicked.connect(self._salvar)
        lay_cab.addWidget(self._btn_salvar)
        raiz.addWidget(self._cab)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        raiz.addWidget(sep)

        # Scroll
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._corpo = QWidget()
        self._lay_corpo = QVBoxLayout(self._corpo)
        self._lay_corpo.setContentsMargins(12, 10, 12, 20)
        self._lay_corpo.setSpacing(14)
        self._lay_corpo.addStretch()
        self._scroll.setWidget(self._corpo)
        raiz.addWidget(self._scroll, 1)

        # Rodapé
        self._rodape = QLabel(
            "Edite a tecla à esquerda e clique em 'Salvar' — teclas duplicadas são permitidas pelo sistema."
        )
        self._rodape.setFixedHeight(20)
        self._rodape.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        raiz.addWidget(self._rodape)

    # ── Construção dinâmica das seções ────────────────────────────────

    def _construir_secoes(self):
        while self._lay_corpo.count() > 1:
            item = self._lay_corpo.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._grupos.clear()

        for grupo in self._dados:
            contexto = str(grupo.get("contexto", "?"))
            descricao = str(grupo.get("descricao", ""))
            atalhos   = grupo.get("atalhos", {})
            if not isinstance(atalhos, dict):
                continue

            bloco, linhas = self._criar_bloco(contexto, descricao, atalhos)
            self._lay_corpo.insertWidget(self._lay_corpo.count() - 1, bloco)
            self._grupos.append({"contexto": contexto, "descricao": descricao, "linhas": linhas})

    # ⚠️  função grande (57 linhas)
    def _criar_bloco(self, contexto: str, descricao: str, atalhos: dict):
        cor = _COR_CONTEXTO.get(contexto, _COR_PADRAO)
        frame = QFrame()
        frame.setObjectName("BlocoSecao")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(4)

        # Título com badge colorido
        cab_row = QWidget()
        cab_lay = QHBoxLayout(cab_row)
        cab_lay.setContentsMargins(0, 0, 0, 0)
        cab_lay.setSpacing(8)

        badge = QLabel(f" {contexto} ")
        badge.setStyleSheet(
            f"background:{cor}; color:#000; font-size:10px; font-weight:bold;"
            f" border-radius:3px; padding:1px 4px; font-family:Consolas;"
        )
        badge.setFixedHeight(18)
        cab_lay.addWidget(badge)

        lbl_desc = QLabel(descricao)
        lbl_desc.setStyleSheet("font-size:10px; color:#666;")
        cab_lay.addWidget(lbl_desc)
        cab_lay.addStretch()
        lay.addWidget(cab_row)

        # Linha separadora
        linha = QFrame()
        linha.setFrameShape(QFrame.HLine)
        linha.setStyleSheet(f"color:{cor}22;")
        linha.setFixedHeight(1)
        lay.addWidget(linha)

        # Cabeçalho das colunas
        hdr = QWidget()
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(0, 2, 0, 2)
        hdr_lay.setSpacing(8)
        lbl_t  = QLabel("Tecla")
        lbl_t.setFixedWidth(160)
        lbl_t.setStyleSheet("font-size:9px; color:#444; font-family:Consolas;")
        lbl_a  = QLabel("Ação do sistema")
        lbl_a.setStyleSheet("font-size:9px; color:#444; font-family:Consolas;")
        hdr_lay.addWidget(lbl_t)
        hdr_lay.addWidget(QLabel(""))   # seta placeholder
        hdr_lay.addWidget(lbl_a, 1)
        lay.addWidget(hdr)

        linhas = []
        for tecla, acao in atalhos.items():
            row, w_tecla = self._criar_row_atalho(tecla, str(acao), cor)
            lay.addWidget(row)
            linhas.append({"acao": str(acao), "widget": w_tecla})

        return frame, linhas

    def _criar_row_atalho(self, tecla: str, acao: str, cor: str):
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 1, 0, 1)
        lay.setSpacing(8)

        # Campo da tecla (editável)
        w_tecla = QLineEdit(tecla)
        w_tecla.setFixedWidth(160)
        w_tecla.setFixedHeight(24)
        w_tecla.setPlaceholderText("ex: ctrl-s")
        w_tecla.setStyleSheet(
            "QLineEdit{background:#1a1a1a;color:#e0e0e0;border:1px solid #1a2e1a;"
            "border-radius:3px;padding:2px 6px;font-size:10px;font-family:Consolas;}"
            "QLineEdit:focus{border-color:#4ec994;}"
        )
        lay.addWidget(w_tecla)

        seta = QLabel("→")
        seta.setStyleSheet(f"color:{cor}; font-size:10px;")
        seta.setFixedWidth(16)
        lay.addWidget(seta)

        # Ação (somente leitura)
        lbl_acao = QLabel(acao)
        lbl_acao.setStyleSheet(
            "font-size:10px; color:#888; font-family:Consolas;"
        )
        lay.addWidget(lbl_acao, 1)

        return row, w_tecla

    # ── Carregar / Salvar ─────────────────────────────────────────────

    def _carregar(self):
        self._dados = _carregar_json(self._arquivo)
        self._construir_secoes()
        self._aplicar_tema()
        self._notificar("Carregado.", cor="#555", duracao=2000)
        self._ultimo_mtime = os.path.getmtime(self._arquivo) if os.path.isfile(self._arquivo) else 0.0
        log.ok(_ARQ, "_carregar", "atalhos.json carregado no AtalhoExplorer")

    def _coletar_dados(self) -> list:
        """Reconstrói o array a partir dos widgets, preservando estrutura."""
        resultado = []
        for i, grupo in enumerate(self._grupos):
            atalhos_novos = {}
            for linha in grupo["linhas"]:
                tecla_nova = linha["widget"].text().strip()
                if tecla_nova:
                    atalhos_novos[tecla_nova] = linha["acao"]
            resultado.append({
                "contexto":  grupo["contexto"],
                "descricao": grupo["descricao"],
                "atalhos":   atalhos_novos,
            })

        return resultado

    def _salvar(self):
        self._salvando = True
        try:
            dados = self._coletar_dados()
            if _salvar_json(self._arquivo, dados):
                self._dados = dados
                self._notificar("✓  Salvo! Atalhos aplicados em tempo real.", cor="#98c379")
                log.ok(_ARQ, "_salvar", "atalhos.json salvo pelo AtalhoExplorer")
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

        self._cab.setStyleSheet(
            f"background:{toolbar}; border-bottom:1px solid {borda};"
        )
        self._rodape.setStyleSheet(
            f"font-size:10px; color:{fraco}; background:{fundo}; padding-right:10px;"
        )
        self.setStyleSheet(f"""
            QWidget {{ background:{fundo}; color:{texto}; }}
            QFrame#BlocoSecao {{
                background:{t.cor('terminal.fundo','#010108')};
                border:1px solid {borda}; border-radius:5px;
            }}
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
