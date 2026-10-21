# _APP_/janela_picker.py
"""
JanelaPicker — tela de boas-vindas e seleção de projeto da hein IDE.
Substitui Outdoor + PainelBoasVindas como ponto de entrada standalone.

Modos:
  "boot"   — janela inicial sem projeto (boot do app sem --projeto)
  "dialog" — painel não-modal aberto de dentro do editor (mesmo processo)

Regras de threading (spec item 3):
  - ZERO threads pesadas no __init__: sem PainelGit, sem Indexador,
    sem TerminalTabWidget, sem verificar_atualizacao.
  - Rede (Clonar, Carregar repos) só dispara sob clique do usuário.
  - _BuscadorPython só dispara quando o usuário clica em ↺.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSettings, QUrl, QTimer, QThread, QObject, QSize
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QLineEdit, QScrollArea, QApplication, QFileDialog, QListWidget,
    QListWidgetItem, QCheckBox, QStackedWidget, QMenu,
)
from PySide6.QtGui import QDesktopServices, QMovie, QPixmap

from _CONFIGURA_ import (
    PASTA_APPDATA,  VERSAO_APP,
    TITULO_APP,  PASTA_PROJETOS,
    FONTE_UI,  FONTE_UI_FALLBACK,
    TAMANHO_FONTE_UI,IMAGEM_ZAP,
    IMAGEM_PIX,  IMAGEM_GIF
)
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_.gerenciador_perfil import obter_nome_usuario
from _APP_.utilitarios_perfil import gerar_saudacao
from _UTILITARIOS_.icones import icone_tema

# Reutiliza workers já existentes em dialogo_novo_projeto
from _APP_.Boas_Vindas.dialogo_novo_projeto import (
    PainelNovoProjeto,
    _BuscadorPython,
    _CriadorVenv,
    _WorkerClone,
)
from _PAINEL_ESQUERDO_.Git.a__git_ui_entrar import (
    _PainelDeviceFlow,
)
from _PAINEL_ESQUERDO_.Git.git_autentica import GerenciadorAuth
from _PAINEL_ESQUERDO_.Git.git_config import config_github
from _PAINEL_ESQUERDO_.Git.git_terminal import GitTerminal
from _THREADS_.diagnostico_workers import bind, event

_ARQUIVO_RECENTES   = os.path.join(PASTA_APPDATA, "recentes.json")
_MAX_RECENTES       = 8
_SK_PASTA           = "janela_picker/pasta_destino"
_SK_VENV            = "janela_picker/criar_venv"
_SK_PYTHON          = "janela_picker/python_exe"


# ── helpers ───────────────────────────────────────────────────────────────────

def _carregar_recentes() -> list[str]:
    try:
        with open(_ARQUIVO_RECENTES, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return [p for p in dados if os.path.isdir(p)][:_MAX_RECENTES]
    except Exception:
        return []


def _log(func: str, msg: str) -> None:
    try:
        from _LOG_.log import log as _l
        _l.info("janela_picker.py", func, msg)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# JanelaPicker
# ══════════════════════════════════════════════════════════════════════════════

class JanelaPicker(QWidget):
    """
    Tela leve de boas-vindas e seleção/criação de projeto.

    Emite `projeto_escolhido(caminho)` ao clicar num projeto, criar um
    novo ou concluir um clone. No boot, `main.py` usa o sinal para criar a
    MainWindow no mesmo processo. Em modo dialog, o handler interno chama
    `lancador_projeto.abrir_projeto_novo_processo`.
    """

    projeto_escolhido = Signal(str)

    def __init__(self, modo: str = "boot", parent=None):
        super().__init__(parent)
        _log("__init__", f"JanelaPicker iniciando: modo={modo}; parent={parent!r}")
        # O picker pode ser encerrado enquanto o processo do projeto novo
        # ainda está sendo criado. O Qt deve destruir o widget de forma
        # explícita para não deixar frame/ícone órfão no Windows.
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self._modo                  = modo          # "boot" | "dialog"
        self._python_selecionado    = ""
        self._python_versao         = ""
        self._thread_buscador: _BuscadorPython | None = None
        self._thread_criador_venv: _CriadorVenv | None = None
        self._thread_clone          = None
        self._worker_clone          = None
        self._pasta_clone           = ""
        self._overlay_clone         = None
        self._overlay_venv          = None
        self._gh_terminal           = None
        self._gh_device_flow        = None
        self._gh_auth               = None
        self._gh_repos_generation   = 0

        self._montar_ui()
        self._restaurar_config()

        # O picker de boot entrega o projeto ao main.py para que a primeira
        # MainWindow seja criada no mesmo processo. O modo dialog, aberto a
        # partir de uma IDE já existente, mantém o isolamento por processo
        # para a ação "abrir outro projeto".
        if self._modo == "dialog":
            self.projeto_escolhido.connect(self._ao_projeto_escolhido)
        _log("__init__", f"JanelaPicker construída: modo={self._modo}")

    # ── cores ─────────────────────────────────────────────────────────────────

    def _c(self, chave: str, fallback: str) -> str:
        return tema_global().cor(chave, fallback)

    def _init_cores(self):
        t = tema_global()
        # Estes são os nomes existentes no tema_padrao.json. Não usar
        # "interface.destaque" ou "interface.hover": essas chaves não existem
        # no mecanismo de temas e faziam o picker cair nos fallbacks.
        self._cf  = t.cor("interface.fundo",                "#000000")
        self._cca = t.cor("interface.fundo_painel",         "#000000")
        self._ctx = t.cor("interface.texto",                "#EDEEF0")
        self._cfr = t.cor("interface.texto_fraco",          "#7094A1")
        self._cvd = t.cor("interface.texto_destaque",       "#4ec994")
        self._cbd = t.cor("interface.borda",                "transparent")
        self._chv = t.cor("interface.fundo_item_hover",     "#1a2e1a")
        self._csel = t.cor("interface.fundo_item_selecionado", "#1f3d1f")
        self._cinput = t.cor("interface.inputs",             "#082C3A")
        self._cbutton = t.cor("interface.botao_padrao_fundo", "#082C3A")
        self._cthumb = t.cor("interface.scrollbar_thumb",    "#2196f3")
        self._cthumb_hover = t.cor("interface.scrollbar_thumb_hover", "#ffff00")
        self._cbright = t.cor("terminal.cores_ansi.verde_brilhante", "#6ee7b7")

    # ── config persistida (coluna 3) ──────────────────────────────────────────

    def _restaurar_config(self):
        s = QSettings("hein", "hein_IDE")
        pasta = s.value(_SK_PASTA, "")
        if pasta and os.path.isdir(pasta):
            self._campo_pasta.setText(pasta)
        else:
            default = s.value("ultima_pasta_destino", PASTA_PROJETOS)
            if default and os.path.isdir(default):
                self._campo_pasta.setText(default)

        # O padrão é criar a .venv automaticamente. Depois que o usuário
        # escolher outra opção, a preferência persistida deve ser respeitada.
        criar_venv = s.value(_SK_VENV, True)
        if isinstance(criar_venv, str):
            criar_venv = criar_venv.lower() != "false"
        self._toggle_venv.setChecked(bool(criar_venv))
        # A restauração da configuração não é uma ação do usuário. Não
        # dispare busca de interpretadores durante o boot: além de tornar a
        # inicialização pesada, isso reabre o caminho do erro COM no Windows.
        self._ao_toggle_venv(bool(criar_venv), iniciar_busca=False)

        python = s.value(_SK_PYTHON, "")
        if python and not self._python_eh_da_ide(str(python)):
            self._python_selecionado = python
        elif python:
            _log(
                "_restaurar_config",
                f"configuração antiga ignorada: Python da IDE ({python})",
            )
            self._python_selecionado = ""

        # Quando a preferência já restaura o checkbox como marcado, o Qt pode
        # não emitir `toggled` porque o estado inicial do widget já era ON.
        # Agendar a busca após a montagem/restauração da janela garante que a
        # lista de interpretadores apareça sem exigir que o usuário alterne o
        # checkbox manualmente.
        if bool(criar_venv):
            QTimer.singleShot(0, self._buscar_pythons)

    def _salvar_config(self):
        s = QSettings("hein", "hein_IDE")
        pasta = self._campo_pasta.text().strip()
        s.setValue(_SK_PASTA, pasta)
        s.setValue(_SK_VENV,  self._toggle_venv.isChecked())
        if self._python_selecionado:
            s.setValue(_SK_PYTHON, self._python_selecionado)
        if pasta:
            s.setValue("ultima_pasta_destino", pasta)   # compat dialogo_novo_projeto

    # ── montagem da UI ────────────────────────────────────────────────────────

    def _montar_ui(self):
        self._init_cores()
        self.setStyleSheet(f"""
            QWidget {{
                background: {self._cf};
                color: {self._ctx};
                font-family: "{FONTE_UI}", "{FONTE_UI_FALLBACK}";
                font-size: {TAMANHO_FONTE_UI};
            }}
        """)
        self.setMinimumSize(960, 620)
        self.setWindowTitle(TITULO_APP)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        # ── página principal (3 colunas) ──────────────────────────────────────
        pagina = QWidget()
        pagina.setStyleSheet(f"background: {self._cf};")
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(self._montar_cabecalho())

        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {self._cbd};")
        lay.addWidget(sep)

        corpo = QWidget(); corpo.setStyleSheet(f"background: {self._cf};")
        lay_corpo = QHBoxLayout(corpo)
        lay_corpo.setContentsMargins(64, 36, 64, 36)
        lay_corpo.setSpacing(40)
        lay.addWidget(corpo, 1)

        lay_corpo.addWidget(self._montar_coluna1(), 3, Qt.AlignTop)
        lay_corpo.addWidget(self._vsep())
        # A coluna central precisa ocupar toda a altura disponível para que a
        # área expansível dos repositórios use o espaço restante. O layout
        # interno da coluna mantém o cabeçalho e os controles no topo.
        lay_corpo.addWidget(self._montar_coluna2(), 3)
        lay_corpo.addWidget(self._vsep())
        lay_corpo.addWidget(self._montar_coluna3(), 2, Qt.AlignTop)

        lay.addWidget(self._montar_card_apoio())

        sep2 = QFrame(); sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background: {self._cbd};")
        lay.addWidget(sep2)

        rodape = QLabel(f"{VERSAO_APP}  ·  Python + PySide6  ·  por HenriqLs")
        rodape.setAlignment(Qt.AlignCenter)
        rodape.setFixedHeight(28)
        rodape.setStyleSheet(
            f"color: {self._cfr}; font-size: 10px; background: {self._cf};"
        )
        lay.addWidget(rodape)

        self._stack.addWidget(pagina)
        self._pagina_principal = pagina

        # ── página Novo Projeto ───────────────────────────────────────────────
        self._painel_novo = PainelNovoProjeto()
        self._painel_novo.voltar.connect(self._voltar_principal)
        self._painel_novo.criar_projeto.connect(self._ao_criar_projeto)
        self._stack.addWidget(self._painel_novo)

        self._stack.setCurrentWidget(self._pagina_principal)

    # ── cabeçalho ─────────────────────────────────────────────────────────────

    def _montar_cabecalho(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(110)
        header.setStyleSheet(f"background: {self._cf};")
        lay = QVBoxLayout(header)
        lay.setContentsMargins(64, 26, 64, 0)
        lay.setSpacing(2)

        # bandeira + subtítulo
        sub_w = QWidget(); sub_w.setStyleSheet("background: transparent;")
        sub_l = QHBoxLayout(sub_w)
        sub_l.setContentsMargins(0, 0, 0, 0); sub_l.setSpacing(6)

        lbl_flag = QLabel()
        lbl_flag.setFixedSize(20, 14); lbl_flag.setScaledContents(True)
        lbl_flag.setStyleSheet("background: transparent;")
        px_br = self._bandeira_brasil()
        if px_br:
            lbl_flag.setPixmap(px_br)
        sub_l.addWidget(lbl_flag)

        lbl_sub = QLabel("Sua IDE Python, em português")
        lbl_sub.setStyleSheet(
            f"color: {self._cfr}; font-size: 13px; background: transparent;"
        )
        sub_l.addWidget(lbl_sub)
        sub_l.addStretch()

        # saudação grande
        saudacao = gerar_saudacao()
        partes    = saudacao.split(", ", 1)
        cumprimento = partes[0] + ","
        nome        = partes[1] if len(partes) > 1 else saudacao

        saud_w = QWidget(); saud_w.setStyleSheet("background: transparent;")
        saud_l = QHBoxLayout(saud_w)
        saud_l.setContentsMargins(0, 0, 0, 0); saud_l.setSpacing(10)
        saud_l.setAlignment(Qt.AlignVCenter)

        lbl_cum = QLabel(cumprimento)
        lbl_cum.setStyleSheet(
            f"color: {self._cfr}; font-size: 22px; background: transparent;"
        )
        lbl_nome = QLabel(nome)
        lbl_nome.setStyleSheet(
            f"color: {self._cvd}; font-size: 52px; font-weight: bold;"
            f" background: transparent; letter-spacing: 1px;"
        )
        saud_l.addWidget(lbl_cum)
        saud_l.addWidget(lbl_nome)
        saud_l.addStretch()

        lay.addWidget(sub_w)
        lay.addWidget(saud_w)
        return header

    # ── coluna 1: Abrir / Recentes ────────────────────────────────────────────

    def _montar_coluna1(self) -> QWidget:
        col = QWidget(); col.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(6)
        lay.setAlignment(Qt.AlignTop)

        lbl = QLabel("Recentes")
        lbl.setStyleSheet(
            f"color: {self._ctx}; font-size: 13px; font-weight: bold; background: transparent;"
        )
        lay.addWidget(lbl)
        lay.addSpacing(4)

        # botões de ação no topo da coluna
        for label, icone_nome, slot in [
            ("  Abrir Projeto",  "mdi.folder-open-outline",   self._ao_abrir_projeto),
            ("  Abrir Arquivo",  "mdi.file-document-outline", self._ao_abrir_arquivo),
        ]:
            btn = self._btn_acao(label)
            btn.setIcon(icone_tema(icone_nome))
            btn.clicked.connect(slot)
            lay.addWidget(btn)

        lay.addSpacing(6)
        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {self._cbd};")
        lay.addWidget(sep)
        lay.addSpacing(6)

        # lista de recentes
        self._container_recentes = QWidget()
        self._container_recentes.setStyleSheet("background: transparent;")
        self._lay_recentes = QVBoxLayout(self._container_recentes)
        self._lay_recentes.setContentsMargins(0, 0, 0, 0)
        self._lay_recentes.setSpacing(4)
        self._popular_recentes()
        lay.addWidget(self._container_recentes)
        lay.addStretch()
        return col

    # ── coluna 2: GitHub ──────────────────────────────────────────────────────

    def _montar_coluna2(self) -> QWidget:
        col = QWidget(); col.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(6)

        # Área superior compacta: permanece fixa no topo da coluna.
        topo = QWidget()
        topo.setStyleSheet("background: transparent;")
        lay_topo = QVBoxLayout(topo)
        lay_topo.setContentsMargins(0, 0, 0, 0)
        lay_topo.setSpacing(6)

        lbl = QLabel("GitHub")
        lbl.setStyleSheet(
            f"color: {self._ctx}; font-size: 13px; font-weight: bold; background: transparent;"
        )
        lay_topo.addWidget(lbl)
        lay_topo.addWidget(self._montar_secao_clone())
        lay_topo.addWidget(self._montar_estado_github())
        lay.addWidget(topo, 0)

        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {self._cbd};")
        lay.addWidget(sep)

        # Área inferior expansível: antes do carregamento, o botão fica
        # centralizado no espaço disponível; depois, o scroll ocupa essa área.
        inferior = QWidget()
        inferior.setStyleSheet("background: transparent;")
        lay_inferior = QVBoxLayout(inferior)
        lay_inferior.setContentsMargins(0, 0, 0, 0)
        lay_inferior.setSpacing(6)

        self._gh_area_inicial = QWidget()
        self._gh_area_inicial.setStyleSheet("background: transparent;")
        lay_inicial = QVBoxLayout(self._gh_area_inicial)
        lay_inicial.setContentsMargins(0, 0, 0, 0)
        lay_inicial.setSpacing(6)
        lay_inicial.addStretch()

        # "Carregar repositórios" — lazy, só dispara no clique.
        self._gh_btn_carregar = QPushButton("  ↓  Carregar repositórios")
        self._gh_btn_carregar.setIcon(icone_tema("mdi.refresh"))
        self._gh_btn_carregar.setCursor(Qt.PointingHandCursor)
        self._gh_btn_carregar.setFixedSize(190, 30)
        self._gh_btn_carregar.setStyleSheet(
            f"QPushButton {{ background: {self._cca}; color: {self._ctx};"
            f" border: 1px solid {self._cbd}; border-radius: 5px;"
            f" padding: 8px 14px; font-size: 12px; text-align: center; }}"
            f"QPushButton:hover {{ border-color: {self._cvd}; color: {self._cvd}; }}"
        )
        self._gh_btn_carregar.clicked.connect(self._ao_clicar_carregar_repos)
        lay_inicial.addWidget(self._gh_btn_carregar, 0, Qt.AlignHCenter)

        self._gh_status_lbl = QLabel("Carregando repositórios...")
        self._gh_status_lbl.setAlignment(Qt.AlignCenter)
        self._gh_status_lbl.setStyleSheet(
            f"color: {self._cfr}; font-size: 11px; background: transparent;"
        )
        self._gh_status_lbl.hide()
        lay_inicial.addWidget(self._gh_status_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            f"QScrollBar:vertical {{ background: transparent; width: 6px; }}"
            f"QScrollBar::handle:vertical {{ background: {self._cthumb}; border-radius: 3px; }}"
            f"QScrollBar::handle:vertical:hover {{ background: {self._cthumb_hover}; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        self._gh_lista_widget = QWidget()
        self._gh_lista_widget.setStyleSheet("background: transparent;")
        self._gh_lista_lay = QVBoxLayout(self._gh_lista_widget)
        self._gh_lista_lay.setContentsMargins(0, 0, 0, 0)
        self._gh_lista_lay.setSpacing(4)
        self._gh_lista_lay.addStretch()
        scroll.setWidget(self._gh_lista_widget)
        scroll.hide()
        self._gh_scroll = scroll
        lay_inferior.addWidget(self._gh_area_inicial, 1)
        lay_inferior.addWidget(scroll, 1)
        lay.addWidget(inferior, 1)

        lay_inicial.addStretch()
        return col

    def _montar_estado_github(self) -> QWidget:
        """Mostra a sessão GitHub e concentra login/troca de conta."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)

        linha = QHBoxLayout()
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(6)

        self._gh_lbl_estado = QLabel()
        self._gh_lbl_estado.setStyleSheet(
            f"color: {self._cfr}; font-size: 11px; background: transparent;"
        )
        linha.addWidget(self._gh_lbl_estado, 1)

        self._gh_btn_contas = QPushButton()
        self._gh_btn_contas.setCursor(Qt.PointingHandCursor)
        self._gh_btn_contas.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {self._cvd};"
            f" border: 1px solid {self._cbd}; border-radius: 4px;"
            " padding: 4px 8px; font-size: 10px; }"
            f"QPushButton:hover {{ border-color: {self._cvd}; }}"
        )
        self._gh_btn_contas.clicked.connect(self._abrir_menu_contas)
        linha.addWidget(self._gh_btn_contas)

        self._gh_btn_conectar = QPushButton("Entrar no GitHub")
        self._gh_btn_conectar.setIcon(icone_tema("mdi.github"))
        self._gh_btn_conectar.setCursor(Qt.PointingHandCursor)
        self._gh_btn_conectar.setStyleSheet(
            f"QPushButton {{ background: {self._cca}; color: {self._ctx};"
            f" border: 1px solid {self._cbd}; border-radius: 5px;"
            " padding: 5px 9px; font-size: 10px; }"
            f"QPushButton:hover {{ border-color: {self._cvd}; color: {self._cvd}; }}"
        )
        self._gh_btn_conectar.clicked.connect(self._abrir_auth_github)
        linha.addWidget(self._gh_btn_conectar)
        lay.addLayout(linha)

        # O mesmo componente usado no painel Git é aberto neste contexto.
        # O terminal existe apenas como suporte de mensagens do Device Flow.
        self._gh_terminal = GitTerminal(self)
        self._gh_terminal.hide()
        self._gh_device_flow = _PainelDeviceFlow(self._gh_terminal, container)
        self._gh_device_flow.set_callback_autenticado(self._ao_github_autenticado)
        self._gh_device_flow.set_callback_cancelado(self._ao_github_login_cancelado)
        lay.addWidget(self._gh_device_flow)

        self._atualizar_estado_github()
        return container

    def _montar_secao_clone(self) -> QWidget:
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 12, 0, 0); lay.setSpacing(6)

        lbl = QLabel("Clonar repositório Git")
        lbl.setStyleSheet(
            f"color: {self._cfr}; font-size: 11px; font-weight: bold;"
        )
        lay.addWidget(lbl)

        linha = QHBoxLayout(); linha.setSpacing(6)
        self._campo_clone = QLineEdit()
        self._campo_clone.setPlaceholderText(
            "Cole a URL do repositório — ex: https://github.com/usuario/repo"
        )
        self._campo_clone.setFixedHeight(28)
        self._campo_clone.setStyleSheet(
            f"background: {self._cinput}; color: {self._ctx};"
            f" border: 1px solid {self._cbd};"
            "border-radius: 4px; padding: 0 8px; font-size: 12px;"
        )
        self._campo_clone.returnPressed.connect(self._iniciar_clone)
        linha.addWidget(self._campo_clone)

        self._btn_clone = QPushButton("Clonar")
        self._btn_clone.setFixedSize(70, 28)
        self._btn_clone.setStyleSheet(
            f"QPushButton {{ background: {self._cbutton}; color: {self._ctx}; border: none;"
            " border-radius: 4px; font-size: 12px; }"
            f"QPushButton:hover {{ background: {self._chv}; }}"
            f"QPushButton:disabled {{ background: {self._cca}; color: {self._cfr}; }}"
        )
        self._btn_clone.clicked.connect(self._iniciar_clone)
        linha.addWidget(self._btn_clone)
        lay.addLayout(linha)

        self._label_clone_status = QLabel("")
        self._label_clone_status.setStyleSheet(
            f"color: {self._cfr}; font-size: 10px;"
        )
        lay.addWidget(self._label_clone_status)
        return container

    # ── coluna 3: Configuração permanente ─────────────────────────────────────

    def _montar_coluna3(self) -> QWidget:
        col = QWidget(); col.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(8)
        lay.setAlignment(Qt.AlignTop)

        lbl = QLabel("Configuração")
        lbl.setStyleSheet(
            f"color: {self._ctx}; font-size: 13px; font-weight: bold; background: transparent;"
        )
        lay.addWidget(lbl)
        lay.addSpacing(4)

        # ── pasta de destino ──────────────────────────────────────────────────
        lbl_pasta = QLabel("Local dos projetos")
        lbl_pasta.setStyleSheet(
            f"color: {self._cfr}; font-size: 11px; background: transparent;"
        )
        lay.addWidget(lbl_pasta)

        row_pasta = QHBoxLayout(); row_pasta.setSpacing(4)
        self._campo_pasta = QLineEdit()
        self._campo_pasta.setPlaceholderText("C:\\Projetos")
        self._campo_pasta.setFixedHeight(28)
        self._campo_pasta.textChanged.connect(lambda _: self._salvar_config())
        row_pasta.addWidget(self._campo_pasta)

        btn_nav_pasta = QPushButton("…")
        btn_nav_pasta.setFixedSize(28, 28)
        btn_nav_pasta.setCursor(Qt.PointingHandCursor)
        btn_nav_pasta.setToolTip("Selecionar pasta")
        btn_nav_pasta.clicked.connect(self._ao_navegar_pasta)
        row_pasta.addWidget(btn_nav_pasta)
        lay.addLayout(row_pasta)

        lay.addSpacing(8)
        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {self._cbd};")
        lay.addWidget(sep)
        lay.addSpacing(8)

        # ── toggle venv ───────────────────────────────────────────────────────
        self._toggle_venv = QCheckBox("Criar venv automaticamente")
        self._toggle_venv.setChecked(True)
        self._toggle_venv.setToolTip(
            "Marcado: a hein IDE criará a .venv do projeto usando o "
            "interpretador selecionado.\n"
            "Desmarque somente se quiser configurar o ambiente manualmente."
        )
        self._toggle_venv.setStyleSheet(
            f"QCheckBox {{ color: {self._ctx}; font-size: 12px; font-weight: 600;"
            " background: transparent; padding: 3px 0; }"
            "QCheckBox::indicator { width: 18px; height: 18px; }"
            f"QCheckBox::indicator:checked {{ background: {self._cvd};"
            f" border: 2px solid {self._cvd}; border-radius: 4px; }}"
            f"QCheckBox::indicator:unchecked {{ background: {self._cca};"
            f" border: 1px solid {self._cfr}; border-radius: 4px; }}"
        )
        self._toggle_venv.toggled.connect(self._ao_toggle_venv)
        lay.addWidget(self._toggle_venv)
        lay.addSpacing(4)

        self._label_ajuda_venv = QLabel(
            "Marcado: cria a .venv automaticamente. "
            "Desmarcado: você configura o ambiente manualmente."
        )
        self._label_ajuda_venv.setWordWrap(True)
        self._label_ajuda_venv.setToolTip(self._toggle_venv.toolTip())
        self._label_ajuda_venv.setStyleSheet(
            f"color: {self._cfr}; font-size: 10px; background: transparent;"
        )
        lay.addWidget(self._label_ajuda_venv)
        lay.addSpacing(4)

        # ── área de interpretadores (visível só quando toggle ON) ─────────────
        self._area_interp = QWidget()
        self._area_interp.setStyleSheet("background: transparent;")
        lay_interp = QVBoxLayout(self._area_interp)
        lay_interp.setContentsMargins(0, 0, 0, 0); lay_interp.setSpacing(4)

        row_hdr = QHBoxLayout()
        lbl_interp = QLabel("INTERPRETADOR PYTHON")
        lbl_interp.setStyleSheet(
            f"font-size: 9px; font-weight: 700; color: {self._cfr};"
            " letter-spacing: 1.8px; background: transparent;"
        )
        row_hdr.addWidget(lbl_interp)
        row_hdr.addStretch()
        self._btn_atualizar_py = QPushButton("↺")
        self._btn_atualizar_py.setFixedSize(22, 22)
        self._btn_atualizar_py.setCursor(Qt.PointingHandCursor)
        self._btn_atualizar_py.setToolTip("Buscar interpretadores Python")
        self._btn_atualizar_py.setStyleSheet(
            "QPushButton { background: transparent; border: none; font-size: 13px; }"
            f"QPushButton:hover {{ color: {self._cvd}; }}"
        )
        self._btn_atualizar_py.clicked.connect(self._buscar_pythons)
        row_hdr.addWidget(self._btn_atualizar_py)
        lay_interp.addLayout(row_hdr)

        self._label_status_py = QLabel("Clique em ↺ para buscar interpretadores")
        self._label_status_py.setStyleSheet(
            f"color: {self._cfr}; font-size: 10px; background: transparent;"
        )
        lay_interp.addWidget(self._label_status_py)

        self._label_python_selecionado = QLabel(
            "Python selecionado automaticamente quando a busca terminar."
        )
        self._label_python_selecionado.setWordWrap(True)
        self._label_python_selecionado.setStyleSheet(
            f"color: {self._cvd}; font-size: 10px; font-weight: 600;"
            " background: transparent;"
        )
        lay_interp.addWidget(self._label_python_selecionado)

        self._lista_python = QListWidget()
        self._lista_python.setMinimumHeight(168)
        self._lista_python.setMaximumHeight(210)
        self._lista_python.setStyleSheet(
            f"QListWidget {{ background: {self._cca}; border: 1px solid {self._cbd};"
            f" border-radius: 5px; font-size: 11px; padding: 3px; }}"
             f"QListWidget::item {{ padding: 5px 7px; border-radius: 3px; }}"
             f"QListWidget::item:selected {{ background: {self._cvd};"
             f" color: {self._cf}; font-weight: 700; }}"
             f"QListWidget::item:hover {{ background: {self._chv}; }}"
        )
        self._lista_python.setAlternatingRowColors(True)
        self._lista_python.currentRowChanged.connect(self._ao_selecionar_python)
        lay_interp.addWidget(self._lista_python)

        lay.addWidget(self._area_interp)
        lay.addStretch()

        # ── botão Novo Projeto (fundo da coluna) ──────────────────────────────
        sep2 = QFrame(); sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background: {self._cbd};")
        lay.addWidget(sep2)
        lay.addSpacing(8)

        btn_novo = self._btn_acao("  Novo Projeto")
        btn_novo.setIcon(icone_tema("mdi.plus"))
        btn_novo.clicked.connect(self._ao_novo_projeto)
        lay.addWidget(btn_novo)

        return col

    # ── card de apoio ─────────────────────────────────────────────────────────

    def _montar_card_apoio(self) -> QWidget:
        _gif     = IMAGEM_GIF
        _qrpix   = IMAGEM_PIX
        _qrwhats = IMAGEM_ZAP

        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {self._cca}; border-top: 2px solid {self._cvd}; }}"
        )
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(48, 14, 48, 14); lay.setSpacing(20)

        lbl_gif = QLabel()
        lbl_gif.setFixedSize(100, 100); lbl_gif.setAlignment(Qt.AlignCenter)
        lbl_gif.setStyleSheet("background: transparent;")
        if os.path.isfile(_gif):
            self._movie_apoio = QMovie(_gif)
            self._movie_apoio.setScaledSize(lbl_gif.size())
            lbl_gif.setMovie(self._movie_apoio)
            self._movie_apoio.start()
        lay.addWidget(lbl_gif)

        col = QWidget(); col.setStyleSheet("background: transparent;")
        lay_col = QVBoxLayout(col)
        lay_col.setContentsMargins(0, 0, 0, 0); lay_col.setSpacing(8)
        lay_col.setAlignment(Qt.AlignVCenter)

        lbl_tit = QLabel("Gostou da hein IDE? Considere apoiar \U0001f90d")
        lbl_tit.setStyleSheet(
            f"color: {self._ctx}; font-size: 13px; font-weight: bold; background: transparent;"
        )
        lay_col.addWidget(lbl_tit)

        acoes = QWidget(); acoes.setStyleSheet("background: transparent;")
        lay_ac = QHBoxLayout(acoes)
        lay_ac.setContentsMargins(0, 0, 0, 0); lay_ac.setSpacing(12)

        lbl_pix = QLabel(
            f"<span style='color:{self._cvd}; font-size:12px;'>"
            f"<b>Pix</b> 008.064.101-67</span>"
        )
        lbl_pix.setStyleSheet("background: transparent;")
        lay_ac.addWidget(lbl_pix)

        btn_cp = QPushButton("Copiar")
        btn_cp.setCursor(Qt.PointingHandCursor); btn_cp.setFixedHeight(24)
        btn_cp.setStyleSheet(
            f"QPushButton {{ background: {self._cvd}; color: {self._cf}; border: none;"
            f" border-radius: 4px; padding: 0 12px; font-size: 11px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {self._cbright}; }}"
        )
        btn_cp.clicked.connect(lambda: QApplication.clipboard().setText("008.064.101-67"))
        lay_ac.addWidget(btn_cp)

        btn_pp = QPushButton("PayPal")
        btn_pp.setCursor(Qt.PointingHandCursor); btn_pp.setFixedHeight(24)
        btn_pp.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {self._cfr};"
            f" border: 1px solid {self._cbd}; border-radius: 4px;"
            f" padding: 0 10px; font-size: 11px; }}"
            f"QPushButton:hover {{ border-color: {self._ctx}; color: {self._ctx}; }}"
        )
        btn_pp.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://www.paypal.com/paypalme/henriqueliandro"))
        )
        lay_ac.addWidget(btn_pp)
        lay_ac.addStretch()
        lay_col.addWidget(acoes)
        lay.addWidget(col, 1)

        def _qr(path, cap):
            cw = QWidget(); cw.setStyleSheet("background: transparent;")
            cv = QVBoxLayout(cw); cv.setContentsMargins(0, 0, 0, 0); cv.setSpacing(3)
            cv.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
            lbl = QLabel(); lbl.setFixedSize(100, 100); lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                f"background: white; border-radius: 4px; border: 1px solid {self._cbd};"
            )
            if os.path.isfile(path):
                px = QPixmap(path).scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                lbl.setPixmap(px)
            else:
                lbl.setText("QR")
            lcap = QLabel(cap); lcap.setAlignment(Qt.AlignCenter)
            lcap.setStyleSheet(
                f"color:{self._cfr}; font-size:9px; background:transparent;"
            )
            cv.addWidget(lbl); cv.addWidget(lcap)
            return cw

        lay.addWidget(_qr(_qrpix,   "Pix"))
        lay.addWidget(_qr(_qrwhats, "WhatsApp"))
        return frame

    # ── helpers visuais ───────────────────────────────────────────────────────

    def _btn_acao(self, texto: str) -> QPushButton:
        btn = QPushButton(texto)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                color: {self._ctx};
                background: {self._cca};
                border: 1px solid {self._cbd};
                border-radius: 5px;
                padding: 10px 14px;
                font-size: 12px;
                min-width: 150px;
            }}
            QPushButton:hover {{
                background: {self._chv};
                border-color: {self._cvd};
                color: {self._cvd};
            }}
        """)
        return btn

    def _vsep(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.VLine)
        f.setFixedWidth(1)
        f.setStyleSheet(f"background: {self._cbd};")
        return f

    def _bandeira_brasil(self):
        try:
            from PySide6.QtSvg import QSvgRenderer
            from PySide6.QtGui import QPainter
            from PySide6.QtCore import QByteArray
            svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 14">
                <rect width="20" height="14" fill="#009c3b"/>
                <polygon points="10,1 19,7 10,13 1,7" fill="#ffdf00"/>
                <circle cx="10" cy="7" r="3.2" fill="#002776"/>
                <line x1="6.8" y1="7" x2="13.2" y2="7"
                    stroke="#fff" stroke-width="0.9" opacity="0.6"/>
            </svg>"""
            renderer = QSvgRenderer(QByteArray(svg))
            px = QPixmap(20, 14); px.fill(Qt.transparent)
            painter = QPainter(px); renderer.render(painter); painter.end()
            return px
        except Exception:
            return None

    # ── coluna 1: ações ───────────────────────────────────────────────────────

    def _popular_recentes(self):
        while self._lay_recentes.count():
            item = self._lay_recentes.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        recentes = _carregar_recentes()
        if recentes:
            for caminho in recentes:
                nome = os.path.basename(caminho)
                btn = QPushButton(f"  {nome}")
                btn.setIcon(icone_tema("mdi.source-repository"))
                btn.setToolTip(caminho)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        text-align: left;
                        color: {self._ctx};
                        background: {self._cca};
                        border: 1px solid {self._cbd};
                        border-radius: 5px;
                        padding: 8px 12px;
                        font-size: 12px;
                    }}
                    QPushButton:hover {{
                        background: {self._chv};
                        border-color: {self._cvd};
                        color: {self._cvd};
                    }}
                """)
                def _escolher_recente(_checked=False, p=caminho):
                    _log(
                        "_popular_recentes",
                        f"projeto_escolhido.emit(): origem=projeto recente; caminho={p}",
                    )
                    self.projeto_escolhido.emit(p)

                btn.clicked.connect(_escolher_recente)
                self._lay_recentes.addWidget(btn)
        else:
            lbl = QLabel("Nenhum projeto recente.")
            lbl.setStyleSheet(
                f"color: {self._cfr}; font-size: 12px; background: transparent;"
            )
            self._lay_recentes.addWidget(lbl)

    def atualizar_recentes(self):
        """Recarrega a lista sem recriar o widget inteiro."""
        self._popular_recentes()

    def _ao_abrir_projeto(self):
        pasta_ini = QSettings("hein", "hein_IDE").value(
            "ultima_pasta_destino", PASTA_PROJETOS
        )
        pasta = QFileDialog.getExistingDirectory(
            self, "Abrir Projeto", pasta_ini,
        )
        if pasta:
            _log(
                "_ao_abrir_projeto",
                f"projeto_escolhido.emit(): origem=abrir projeto; caminho={pasta}",
            )
            self.projeto_escolhido.emit(pasta)

    def _ao_abrir_arquivo(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Abrir Arquivo", "",
            "Python (*.py);;Todos (*.*)",
        )
        if caminho:
            # abre o diretório pai como projeto
            _pasta_projeto = os.path.dirname(caminho)
            _log(
                "_ao_abrir_arquivo",
                "projeto_escolhido.emit(): "
                f"origem=abrir arquivo; caminho={_pasta_projeto}",
            )
            self.projeto_escolhido.emit(_pasta_projeto)

    # ── coluna 3: ações ───────────────────────────────────────────────────────

    def _ao_navegar_pasta(self):
        atual = self._campo_pasta.text().strip() or PASTA_PROJETOS
        pasta = QFileDialog.getExistingDirectory(
            self, "Local dos projetos", atual,
        )
        if pasta:
            self._campo_pasta.setText(pasta)
            self._salvar_config()

    def _ao_toggle_venv(self, ativo: bool, iniciar_busca: bool = True):
        _log("_ao_toggle_venv", f"toggle venv: {'ON' if ativo else 'OFF'}")
        self._area_interp.setVisible(ativo)
        self._label_ajuda_venv.setText(
            "Ambiente automático ativo: a .venv será criada com o Python selecionado."
            if ativo else
            "Ambiente automático desativado: a .venv ficará para configuração manual."
        )
        self._salvar_config()
        # busca lazy — dispara quando a seção fica visível pela primeira vez
        if (
            iniciar_busca
            and ativo
            and self._lista_python.count() == 0
            and self._thread_buscador is None
        ):
            _log("_ao_toggle_venv", "primeira exibição da seção — iniciando busca lazy de interpretadores")
            self._buscar_pythons()

    def _buscar_pythons(self):
        _log("_buscar_pythons", "iniciando busca de interpretadores Python")
        self._lista_python.clear()
        self._label_status_py.setText("🔍 Buscando interpretadores Python...")
        self._label_python_selecionado.setText(
            "Procurando um interpretador Python..."
        )
        self._btn_atualizar_py.setEnabled(False)
        if self._thread_buscador is not None:
            _t_ant = self._thread_buscador
            self._thread_buscador = None
            try:
                _t_ant.encontrado.disconnect()
                _t_ant.concluido.disconnect()
            except RuntimeError:
                pass
            # nunca zera direto se ainda rodando — deixa o GC do Qt destruir com segurança
            if _t_ant.isRunning():
                _log("_buscar_pythons", "AVISO: thread anterior ainda rodando — conectando finished→deleteLater")
                event(
                    "QUIT_REQUESTED",
                    getattr(_t_ant, "_hein_diag_component", "PYTHON_SEARCH"),
                    getattr(_t_ant, "_hein_diag_task", ""),
                    obj=_t_ant,
                    reason="replaced_by_new_search",
                )
                _t_ant.finished.connect(_t_ant.deleteLater)
        t = _BuscadorPython()
        t.encontrado.connect(self._ao_python_encontrado)
        t.concluido.connect(self._ao_busca_concluida)
        self._thread_buscador = t
        t.start()
        _log("_buscar_pythons", "thread _BuscadorPython iniciada")

    def _ao_python_encontrado(self, exe: str, versao: str):
        if self._python_eh_da_ide(exe):
            _log("_ao_python_encontrado", f"ignorado (Python da IDE): {exe}")
            return
        item = QListWidgetItem(f"  🐍  Python {versao}   —   {exe}")
        item.setData(Qt.UserRole, exe)
        item.setData(Qt.UserRole + 1, versao)
        item.setSizeHint(QSize(0, 32))
        self._lista_python.addItem(item)
        if self._lista_python.count() == 1:
            self._lista_python.setCurrentRow(0)
        # restaura seleção salva
        salvo = QSettings("hein", "hein_IDE").value(_SK_PYTHON, "")
        if salvo and os.path.normcase(exe) == os.path.normcase(salvo):
            self._lista_python.setCurrentRow(self._lista_python.count() - 1)

    def _ao_busca_concluida(self):
        n = self._lista_python.count()
        self._label_status_py.setText(
            f"{n} interpretador{'es' if n > 1 else ''} encontrado{'s' if n > 1 else ''}."
            if n else "⚠️ Nenhum Python encontrado."
        )
        self._btn_atualizar_py.setEnabled(True)
        self._thread_buscador = None   # thread concluiu — limpa referência
        _log("_ao_busca_concluida", f"busca encerrada — {n} interpretador(es) encontrado(s)")

    def _ao_selecionar_python(self, row: int):
        item = self._lista_python.item(row)
        if item:
            self._python_selecionado = item.data(Qt.UserRole)
            self._python_versao = item.data(Qt.UserRole + 1) or ""
            self._label_python_selecionado.setText(
                f"Selecionado: Python {self._python_versao}"
            )
            self._salvar_config()
            _exe = self._python_selecionado
            _log(
                "_ao_selecionar_python",
                f"selecionado: {_exe}"
                + " ✓ (≠ sys.executable)",
            )

    @staticmethod
    def _python_eh_da_ide(exe: str) -> bool:
        if not exe:
            return False
        try:
            return os.path.normcase(os.path.abspath(exe)) == os.path.normcase(
                os.path.abspath(sys.executable)
            )
        except Exception:
            return False

    def _ao_novo_projeto(self):
        """Valida coluna 3 e muda para a página de Novo Projeto."""
        destino = self._campo_pasta.text().strip()
        if not destino or not os.path.isdir(destino):
            from _UTILITARIOS_.hein_pou_pap import HeinPopup
            HeinPopup.aviso(
                "Pasta inválida",
                "Configure um local de projetos válido antes de criar um projeto.",
                parent=self,
            )
            return
        criar_venv = self._toggle_venv.isChecked()
        python_exe = self._python_selecionado if criar_venv else ""
        if python_exe and self._python_eh_da_ide(python_exe):
            _log(
                "_ao_novo_projeto",
                f"Python da IDE rejeitado antes de abrir Novo Projeto: {python_exe}",
            )
            self._python_selecionado = ""
            python_exe = ""
        if criar_venv and not python_exe:
            from _UTILITARIOS_.hein_pou_pap import HeinPopup
            HeinPopup.aviso(
                "Interpretador não selecionado",
                "Selecione um interpretador Python ou desmarque 'Criar venv automaticamente'.",
                parent=self,
            )
            return
        self._painel_novo.definir_config(
            destino,
            python_exe,
            self._python_versao,
        )
        self._stack.setCurrentWidget(self._painel_novo)

    def _voltar_principal(self):
        self._stack.setCurrentWidget(self._pagina_principal)

    # ── criar projeto ─────────────────────────────────────────────────────────

    def _ao_criar_projeto(self, nome: str, destino: str, python_exe: str):
        """Recebe sinal do PainelNovoProjeto — pasta e arquivos já criados."""
        caminho = os.path.join(destino, nome)
        if python_exe and os.path.isfile(python_exe):
            self._iniciar_criacao_venv(caminho, python_exe)
        else:
            _log(
                "_ao_criar_projeto",
                f"projeto_escolhido.emit(): origem=criação de projeto; caminho={caminho}",
            )
            self.projeto_escolhido.emit(caminho)

    def _iniciar_criacao_venv(self, caminho: str, python_exe: str):
        try:
            from _UTILITARIOS_.loading_overlay import LoadingOverlay as _LO
            self._overlay_venv = _LO(self, mensagem="Criando ambiente virtual...")
            self._overlay_venv.show()
            QApplication.processEvents()
        except Exception:
            pass
        t = _CriadorVenv(caminho, python_exe)
        t.concluido.connect(self._ao_venv_criado)
        t.erro.connect(lambda err: self._ao_venv_erro(err, caminho))
        t.concluido.connect(t.quit)
        t.erro.connect(t.quit)
        self._thread_criador_venv = t
        t.start()

    def _ao_venv_criado(self, caminho: str):
        overlay = getattr(self, "_overlay_venv", None)
        if overlay:
            try: overlay.fechar()
            except Exception: pass
            self._overlay_venv = None
        self._thread_criador_venv = None
        _log(
            "_ao_venv_criado",
            f"projeto_escolhido.emit(): origem=venv criada; caminho={caminho}",
        )
        self.projeto_escolhido.emit(caminho)

    def _ao_venv_erro(self, erro: str, caminho: str):
        overlay = getattr(self, "_overlay_venv", None)
        if overlay:
            try: overlay.fechar()
            except Exception: pass
            self._overlay_venv = None
        self._thread_criador_venv = None
        _log("_ao_venv_erro", f"venv falhou — abrindo projeto sem venv: {erro}")
        # abre o projeto mesmo assim
        _log(
            "_ao_venv_erro",
            "projeto_escolhido.emit(): "
            f"origem=erro na criação da venv; caminho={caminho}",
        )
        self.projeto_escolhido.emit(caminho)

    # ── GitHub: carregar repos ────────────────────────────────────────────────

    def _ao_clicar_carregar_repos(self):
        if not config_github().esta_logado():
            self._gh_status_lbl.setText(
                "GitHub não conectado. Use «Entrar no GitHub» acima."
            )
            self._gh_status_lbl.show()
            self._gh_area_inicial.show()
            self._gh_scroll.hide()
            self._gh_btn_carregar.show()
            return
        self._gh_btn_carregar.hide()
        self._gh_status_lbl.setText("Carregando repositórios...")
        self._gh_status_lbl.show()
        self._gh_area_inicial.show()
        self._gh_scroll.hide()
        self._carregar_repos_github()

    def _carregar_repos_github(self):
        token = config_github().token if config_github().esta_logado() else ""
        if not token:
            self._gh_status_lbl.hide()
            self._gh_scroll.hide()
            self._gh_btn_carregar.show()
            return
        self._gh_repos_generation += 1
        generation = self._gh_repos_generation
        self._gh_nam = QNetworkAccessManager(self)
        req = QNetworkRequest(QUrl(
            "https://api.github.com/user/repos?sort=pushed&per_page=30&affiliation=owner"
        ))
        req.setRawHeader(b"Authorization", f"Bearer {token}".encode())
        req.setRawHeader(b"Accept", b"application/vnd.github+json")
        req.setRawHeader(b"X-GitHub-Api-Version", b"2022-11-28")
        req.setTransferTimeout(10_000)
        reply = self._gh_nam.get(req)
        reply.finished.connect(
            lambda: self._gh_reply_finished(reply, generation)
        )

    def _gh_reply_finished(self, reply, generation: int):
        if generation != self._gh_repos_generation:
            reply.deleteLater()
            return
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self._ao_repos_erro(reply.errorString()); return
            dados = json.loads(bytes(reply.readAll()).decode())
            repos = [
                {"name": r["name"], "private": r["private"], "clone_url": r["clone_url"]}
                for r in dados
            ]
            self._ao_repos_carregados(repos)
        except Exception as e:
            self._ao_repos_erro(str(e))
        finally:
            reply.deleteLater()

    def _ao_repos_carregados(self, repos: list):
        self._gh_status_lbl.hide()
        self._gh_area_inicial.hide()
        self._gh_scroll.show()
        while self._gh_lista_lay.count():
            item = self._gh_lista_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for repo in repos:
            nome, privado, clone_url = repo["name"], repo["private"], repo["clone_url"]
            iw = QWidget(); iw.setStyleSheet("background: transparent;")
            il = QHBoxLayout(iw); il.setContentsMargins(0, 0, 0, 0); il.setSpacing(6)
            lbl_ico = QLabel()
            lbl_ico.setPixmap(
                icone_tema(
                    "mdi.lock-outline" if privado else "mdi.source-repository",
                    color=self._cfr
                ).pixmap(14, 14)
            )
            lbl_ico.setStyleSheet("background: transparent;")
            il.addWidget(lbl_ico)
            btn_n = QPushButton(nome); btn_n.setCursor(Qt.PointingHandCursor); btn_n.setFlat(True)
            btn_n.setStyleSheet(
                f"QPushButton {{ color: {self._ctx}; background: transparent; border: none;"
                f" font-size: 12px; text-align: left; padding: 0; }}"
                f"QPushButton:hover {{ color: {self._cvd}; }}"
            )
            url_web = clone_url.replace(".git", "")
            btn_n.clicked.connect(
                lambda _c, u=url_web: QDesktopServices.openUrl(QUrl(u))
            )
            il.addWidget(btn_n, 1)
            btn_cl = QPushButton("Clonar"); btn_cl.setCursor(Qt.PointingHandCursor)
            btn_cl.setFixedSize(56, 22)
            btn_cl.setStyleSheet(
                f"QPushButton {{ background: {self._cbutton}; color: {self._ctx}; border: none;"
                " border-radius: 3px; font-size: 10px; }"
                f"QPushButton:hover {{ background: {self._chv}; }}"
            )
            btn_cl.clicked.connect(
                lambda _c, u=clone_url, n=nome: self._iniciar_clone_url(u, n)
            )
            il.addWidget(btn_cl)
            self._gh_lista_lay.addWidget(iw)
        self._gh_lista_lay.addStretch()

    def _ao_repos_erro(self, _erro: str):
        self._gh_status_lbl.setText(
            "Não foi possível carregar os repositórios. Tente novamente."
        )
        self._gh_status_lbl.show()
        self._gh_scroll.hide()
        self._gh_area_inicial.show()
        self._gh_btn_carregar.setText("  ↺  Tentar novamente")
        self._gh_btn_carregar.show()

    def _abrir_auth_github(self):
        try:
            if self._gh_device_flow is None or self._gh_terminal is None:
                return
            self._gh_auth = GerenciadorAuth()
            self._gh_btn_conectar.setEnabled(False)
            self._gh_device_flow.setVisible(True)
            self._gh_device_flow.iniciar(self._gh_auth)
        except Exception as exc:
            _log("_abrir_auth_github", f"falha ao iniciar login: {exc}")
            self._gh_btn_conectar.setEnabled(True)
            self._gh_status_lbl.setText(
                "Não foi possível iniciar o login do GitHub."
            )
            self._gh_status_lbl.show()

    def _ao_github_autenticado(self):
        self._gh_btn_conectar.setEnabled(True)
        self._gh_device_flow.setVisible(False)
        self._gh_auth = None
        self._atualizar_estado_github()
        self._resetar_lista_repositorios()
        self._gh_status_lbl.setText(
            "Login concluído. Clique em «Carregar repositórios»."
        )
        self._gh_status_lbl.show()
        self._gh_btn_carregar.setText("  ↓  Carregar repositórios")
        self._gh_btn_carregar.show()

    def _ao_github_login_cancelado(self):
        self._gh_btn_conectar.setEnabled(True)
        self._gh_auth = None
        self._atualizar_estado_github()

    def _atualizar_estado_github(self):
        cfg = config_github()
        logado = cfg.esta_logado()
        if logado:
            self._gh_lbl_estado.setText(f"Conectado como @{cfg.login}")
            self._gh_btn_contas.setText(f"Contas ({len(cfg.contas())})")
            self._gh_btn_contas.show()
            self._gh_btn_conectar.hide()
        else:
            self._gh_lbl_estado.setText("GitHub não conectado")
            contas_salvas = cfg.contas()
            if contas_salvas:
                self._gh_btn_contas.setText(f"Contas ({len(contas_salvas)})")
                self._gh_btn_contas.show()
            else:
                self._gh_btn_contas.hide()
            self._gh_btn_conectar.show()

    def _abrir_menu_contas(self):
        cfg = config_github()
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {self._cca}; color: {self._ctx};"
            f" border: 1px solid {self._cbd}; }}"
            "QMenu::item { padding: 6px 14px; }"
            f"QMenu::item:selected {{ background: {self._chv}; }}"
        )
        for conta in cfg.contas():
            login = conta.get("login", "")
            nome = conta.get("nome") or login
            acao = menu.addAction(f"@{login} — {nome}")
            acao.setCheckable(True)
            acao.setChecked(login == cfg.login)
            acao.triggered.connect(
                lambda _checked=False, conta_login=login:
                self._trocar_conta_github(conta_login)
            )
        if cfg.contas():
            menu.addSeparator()
        adicionar = menu.addAction("Adicionar outra conta")
        adicionar.triggered.connect(self._abrir_auth_github)
        if cfg.esta_logado():
            menu.addSeparator()
            sair = menu.addAction("Sair da conta atual")
            sair.triggered.connect(self._sair_conta_github)
        menu.exec(
            self._gh_btn_contas.mapToGlobal(
                self._gh_btn_contas.rect().bottomLeft()
            )
        )

    def _trocar_conta_github(self, login: str):
        if not config_github().ativar_conta(login):
            self._gh_status_lbl.setText("Conta salva não encontrada.")
            self._gh_status_lbl.show()
            return
        self._gh_repos_generation += 1
        self._atualizar_estado_github()
        self._resetar_lista_repositorios()
        self._gh_status_lbl.setText(
            f"Conta ativa: @{login}. Clique em «Carregar repositórios»."
        )
        self._gh_status_lbl.show()
        self._gh_btn_carregar.setText("  ↓  Carregar repositórios")
        self._gh_btn_carregar.show()

    def _sair_conta_github(self):
        config_github().limpar_sessao()
        self._gh_repos_generation += 1
        self._atualizar_estado_github()
        self._resetar_lista_repositorios()
        self._gh_status_lbl.setText(
            "GitHub desconectado. O Git local continua disponível."
        )
        self._gh_status_lbl.show()
        self._gh_btn_carregar.setText("  ↓  Carregar repositórios")
        self._gh_btn_carregar.show()

    def _resetar_lista_repositorios(self):
        self._gh_scroll.hide()
        self._gh_area_inicial.show()
        self._gh_status_lbl.hide()
        while self._gh_lista_lay.count():
            item = self._gh_lista_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._gh_lista_lay.addStretch()

    # ── clone ─────────────────────────────────────────────────────────────────

    def _iniciar_clone_url(self, url: str, nome_repo: str):
        from _UTILITARIOS_.hein_pou_pap import HeinPopup
        pasta_base = self._campo_pasta.text().strip()
        if not pasta_base or not os.path.isdir(pasta_base):
            HeinPopup.aviso(
                "Pasta de destino inválida",
                "Escolha uma pasta de destino válida antes de clonar.",
                parent=self,
            )
            return
        self._executar_clone(url, os.path.join(pasta_base, nome_repo), nome_repo)

    def _iniciar_clone(self):
        from _UTILITARIOS_.hein_pou_pap import HeinPopup
        url = self._campo_clone.text().strip()
        padrao = r"https?://(github\.com|gitlab\.com|bitbucket\.org)/.+/.+"
        if not re.match(padrao, url):
            HeinPopup.aviso(
                "URL inválida",
                "Use o formato <b>https://github.com/usuario/repositorio</b>",
                parent=self,
            )
            return
        pasta_base = self._campo_pasta.text().strip()
        if not pasta_base or not os.path.isdir(pasta_base):
            HeinPopup.aviso(
                "Pasta de destino inválida",
                "Escolha uma pasta de destino válida antes de clonar.",
                parent=self,
            )
            return
        nome_repo = url.rstrip("/").split("/")[-1]
        if nome_repo.endswith(".git"):
            nome_repo = nome_repo[:-4]
        self._executar_clone(url, os.path.join(pasta_base, nome_repo), nome_repo)

    def _executar_clone(self, url: str, pasta_destino: str, nome_repo: str):
        """Executa git clone em thread — sem popup de confirmação.
        A pasta de destino já está definida na coluna 3.
        Quando a URL é do GitHub, a sessão autenticada é usada somente
        durante o processo Git para permitir clones privados."""
        os.makedirs(os.path.dirname(pasta_destino) or ".", exist_ok=True)
        try:
            from _UTILITARIOS_.loading_overlay import LoadingOverlay as _LO
            self._overlay_clone = _LO(self, mensagem=f"Clonando {nome_repo}...")
            self._overlay_clone.show()
            QApplication.processEvents()
        except Exception:
            pass
        self._btn_clone.setEnabled(False)

        self._label_clone_status.setText(
            f"Clonando em: {os.path.dirname(pasta_destino)}"
        )
        self._thread_clone = QThread(self)
        token = ""
        if "github.com" in url.lower():
            token = config_github().token if config_github().esta_logado() else ""
        self._worker_clone = _WorkerClone(url, pasta_destino, token)
        _task_clone = getattr(self._worker_clone, "_hein_diag_task", "")
        bind(
            self._thread_clone,
            "CLONE",
            _task_clone,
            editor=None,
        )
        self._pasta_clone = pasta_destino
        self._worker_clone.moveToThread(self._thread_clone)
        self._thread_clone.started.connect(self._worker_clone.run)
        # Método vinculado ao QWidget: Qt entrega o sinal na thread da UI.
        # Evita atualizar overlay/widgets diretamente na thread do git.
        self._worker_clone.concluido.connect(self._ao_clone_concluido)
        self._worker_clone.concluido.connect(self._thread_clone.quit)
        self._thread_clone.finished.connect(self._ao_thread_clone_finalizada)
        self._thread_clone.finished.connect(self._worker_clone.deleteLater)
        self._thread_clone.finished.connect(self._thread_clone.deleteLater)
        event(
            "START_REQUESTED",
            "CLONE",
            _task_clone,
            obj=self._thread_clone,
            destination=pasta_destino,
            source_url=url,
        )
        self._thread_clone.start()

    def _ao_clone_concluido(self, sucesso: bool, erro: str):
        self._clone_finalizado(sucesso, erro, self._pasta_clone)

    def _ao_thread_clone_finalizada(self):
        thread = self._thread_clone
        event(
            "FINISHED",
            "CLONE",
            getattr(thread, "_hein_diag_task", "") if thread is not None else "",
            obj=thread,
            destination=self._pasta_clone,
        )
        self._thread_clone = None
        self._worker_clone = None
        self._pasta_clone = ""

    def _clone_finalizado(self, sucesso: bool, erro: str, pasta: str):
        from _UTILITARIOS_.hein_pou_pap import HeinPopup
        overlay = getattr(self, "_overlay_clone", None)
        if overlay:
            try: overlay.fechar()
            except Exception: pass
            self._overlay_clone = None
        self._btn_clone.setEnabled(True)
        self._label_clone_status.setText(
            f"Clone concluído em: {pasta}" if sucesso else ""
        )
        if not sucesso:
            HeinPopup.erro("Erro ao clonar", erro, parent=self)
            return
        # clone concluído — criar venv se toggle ON
        criar_venv = self._toggle_venv.isChecked()
        python_exe = self._python_selecionado if criar_venv else ""
        if python_exe and os.path.isfile(python_exe):
            self._iniciar_criacao_venv(pasta, python_exe)
        else:
            _log(
                "_clone_finalizado",
                f"projeto_escolhido.emit(): origem=clone concluído; caminho={pasta}",
            )
            self.projeto_escolhido.emit(pasta)

    # ── cleanup ao fechar ────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        _log("showEvent", f"JanelaPicker exibida: modo={self._modo}")

    def closeEvent(self, event):
        """Garante que threads em background não ficam órfãs."""
        _log("closeEvent", "\n")
        _log("closeEvent", "═" * 70)
        _log(
            "closeEvent",
            f">>> FECHAMENTO DA JANELA PICKER: modo={self._modo} <<<",
        )
        _log("closeEvent", "═" * 70)
        _log("closeEvent", "\n")
        _log("closeEvent", f"picker fechando (modo={self._modo})")
        if self._gh_device_flow is not None:
            try:
                self._gh_device_flow._timer_poll.stop()
                if self._gh_auth is not None:
                    self._gh_auth.cancelar()
            except (AttributeError, RuntimeError):
                pass
        for attr in ("_thread_buscador", "_thread_clone", "_thread_criador_venv"):
            t = getattr(self, attr, None)
            if t is not None:
                ainda_rodando = hasattr(t, "isRunning") and t.isRunning()
                if ainda_rodando:
                    _log("closeEvent", f"AVISO: thread '{attr}' ainda rodando ao fechar — agendando deleteLater")
                    event(
                        "QUIT_REQUESTED",
                        getattr(t, "_hein_diag_component", "THREAD"),
                        getattr(t, "_hein_diag_task", ""),
                        obj=t,
                        reason="picker_close",
                    )
                setattr(self, attr, None)
                try:
                    t.encontrado.disconnect()
                except (AttributeError, RuntimeError):
                    pass
                try:
                    t.concluido.disconnect()
                except (AttributeError, RuntimeError):
                    pass
                if ainda_rodando:
                    t.finished.connect(t.deleteLater)
        _log("closeEvent", "picker fechado — todas as threads encerradas ou agendadas para deleteLater")
        super().closeEvent(event)

    # ── projeto escolhido em modo dialog → processo novo ───────────────────

    def _ao_projeto_escolhido(self, caminho: str):
        """Handler interno: salva config, lança novo processo, fecha o picker."""
        self._salvar_config()
        _log("_ao_projeto_escolhido", f"abrindo em novo processo: {caminho}")

        # Esconde imediatamente o picker antes do Popen. Isso remove a janela
        # da área de trabalho no instante do clique e evita uma cópia fantasma
        # enquanto a nova janela independente inicializa.
        self.hide()
        QApplication.processEvents()

        from _APP_.Boas_Vindas.lancador_projeto import abrir_projeto_novo_processo
        abrir_projeto_novo_processo(caminho)
        if self._modo == "boot":
            # Fecha/destrói o picker antes de encerrar o processo inicial.
            # O pequeno atraso permite ao Qt processar o closeEvent e o
            # delete-on-close antes de sair do event loop.
            self.close()
            QTimer.singleShot(0, self._encerrar_boot)
        else:
            # modo dialog: fecha a janela, editor continua rodando
            QTimer.singleShot(0, self.close)

    def _encerrar_boot(self):
        """Encerra apenas o processo do picker após o novo processo iniciar."""
        app = QApplication.instance()
        if app is not None:
            app.quit()
