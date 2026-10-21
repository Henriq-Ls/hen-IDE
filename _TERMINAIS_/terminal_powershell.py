# 📁 _TERMINAIS_/terminal_powershell.py
"""
_TERMINAIS_/terminal_powershell.py
Terminal PowerShell com cores ANSI reais.
"""
from _TRADUTION_.tradutor_erros import traduzir
import platform
import re, os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QToolTip, QPushButton, QLabel, QToolButton, QMenu, QLineEdit
import json, uuid, datetime, pathlib
from PySide6.QtCore import Qt, QProcess, QProcessEnvironment, QTimer, Signal, QSize
from _UTILITARIOS_.icones import icone_tema
from PySide6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat, QDesktopServices
from _CONFIGURA_.gerenciador_tema import tema_global
from _UTILITARIOS_.hein_pacotes_util import registrar as _pkg_registrar, extrair_nome_versao
IS_WINDOWS = platform.system() == "Windows"
# ── Regex: detecta linha de sucesso do pip ────────────────────────────────────
# Exemplo: "Successfully installed watchdog-3.0.0 requests-2.31.0"
_RE_PIP_OK = re.compile(
    r'Successfully installed\s+((?:[\w.\-]+ *)+)',
    re.IGNORECASE,
)
_RE_TRACEBACK = re.compile(r'(?:File|Arquivo) "(.+?)", (?:line|linha) (\d+)')
_RE_URL       = re.compile(r'https?://[^\s)"\'>]+')
_RE_CAMINHO   = re.compile(r'[A-Za-z]:[/\\][^\s"\'<>|*?\r\n]+')
# Detecta URLs de servidor local: http://127.0.0.1:PORT ou http://localhost:PORT
_RE_SERVIDOR  = re.compile(r'http://(?:127\.0\.0\.1|localhost|0\.0\.0\.0):(\d+)', re.IGNORECASE)

# ── Helpers de cor ────────────────────────────────────────────────────────────

# 💡 padrao_opc = Literal["#cccccc"] ← defina os valores válidos
def _cor(tema: dict, *chaves, padrao: str = "#cccccc") -> str:
    atual = tema
    for chave in chaves:
        if not isinstance(atual, dict) or chave not in atual:

            return padrao

        atual = atual[chave]
    if isinstance(atual, str) and len(atual) == 9:

        return atual[:7]

    return atual if isinstance(atual, str) else padrao

# ── Paleta ANSI ───────────────────────────────────────────────────────────────

def _montar_cores_ansi(tema: dict) -> dict:

    return {

        30:  _cor(tema, "terminal", "cores_ansi", "preto",              padrao="#1e1e1e"),
        31:  _cor(tema, "terminal", "cores_ansi", "vermelho",           padrao="#e06c75"),
        32:  _cor(tema, "terminal", "cores_ansi", "verde",              padrao="#4ec994"),
        33:  _cor(tema, "terminal", "cores_ansi", "amarelo",            padrao="#e5c07b"),
        34:  _cor(tema, "terminal", "cores_ansi", "azul",               padrao="#61afef"),
        35:  _cor(tema, "terminal", "cores_ansi", "magenta",            padrao="#c678dd"),
        36:  _cor(tema, "terminal", "cores_ansi", "ciano",              padrao="#56b6c2"),
        37:  _cor(tema, "terminal", "cores_ansi", "branco",             padrao="#cccccc"),
        90:  _cor(tema, "terminal", "cores_ansi", "preto_brilhante",    padrao="#555555"),
        91:  _cor(tema, "terminal", "cores_ansi", "vermelho_brilhante", padrao="#ff8a8a"),
        92:  _cor(tema, "terminal", "cores_ansi", "verde_brilhante",    padrao="#6ee7b7"),
        93:  _cor(tema, "terminal", "cores_ansi", "amarelo_brilhante",  padrao="#ffd89b"),
        94:  _cor(tema, "terminal", "cores_ansi", "azul_brilhante",     padrao="#82c8ff"),
        95:  _cor(tema, "terminal", "cores_ansi", "magenta_brilhante",  padrao="#e5b0ff"),
        96:  _cor(tema, "terminal", "cores_ansi", "ciano_brilhante",    padrao="#7ee8f2"),
        97:  _cor(tema, "terminal", "cores_ansi", "branco_brilhante",   padrao="#ffffff"),
        40:  _cor(tema, "terminal", "cores_ansi", "preto",              padrao="#1e1e1e"),
        41:  _cor(tema, "terminal", "cores_ansi", "vermelho",           padrao="#e06c75"),
        42:  _cor(tema, "terminal", "cores_ansi", "verde",              padrao="#4ec994"),
        43:  _cor(tema, "terminal", "cores_ansi", "amarelo",            padrao="#e5c07b"),
        44:  _cor(tema, "terminal", "cores_ansi", "azul",               padrao="#61afef"),
        45:  _cor(tema, "terminal", "cores_ansi", "magenta",            padrao="#c678dd"),
        46:  _cor(tema, "terminal", "cores_ansi", "ciano",              padrao="#56b6c2"),
        47:  _cor(tema, "terminal", "cores_ansi", "branco",             padrao="#cccccc"),
        100: _cor(tema, "terminal", "cores_ansi", "preto_brilhante",    padrao="#555555"),
        101: _cor(tema, "terminal", "cores_ansi", "vermelho_brilhante", padrao="#ff8a8a"),
        102: _cor(tema, "terminal", "cores_ansi", "verde_brilhante",    padrao="#6ee7b7"),
        103: _cor(tema, "terminal", "cores_ansi", "amarelo_brilhante",  padrao="#ffd89b"),
        104: _cor(tema, "terminal", "cores_ansi", "azul_brilhante",     padrao="#82c8ff"),
        105: _cor(tema, "terminal", "cores_ansi", "magenta_brilhante",  padrao="#e5b0ff"),
        106: _cor(tema, "terminal", "cores_ansi", "ciano_brilhante",    padrao="#7ee8f2"),
        107: _cor(tema, "terminal", "cores_ansi", "branco_brilhante",   padrao="#ffffff"),
    }

# ── Parser ANSI ───────────────────────────────────────────────────────────────

_ANSI_RE = re.compile(
    r'\x1b\[([\d;]*)m|\x1b\[[^m]*[A-Za-z]|\x1b\].*?\x07|([^\x1b]+)',
    re.DOTALL
)

def _parse_ansi(text: str, cores_ansi: dict, cor_fg: str, cor_bg: str): # Nao setamos background por padrao — o widget (stylesheet) cuida disso. # Isso garante que ao trocar o tema o fundo atualiza em todo o terminal, # sem precisar limpar o buffer. Background explicito so para ANSI 40-47/100-107.
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(cor_fg))

    for m in _ANSI_RE.finditer(text):
        seq, chunk = m.group(1), m.group(2)
        if chunk:

            yield chunk, QTextCharFormat(fmt)

        elif seq is not None:
            if seq == "" or seq == "0":
                # reset total: volta ao padrao sem background explicito
                fmt = QTextCharFormat()
                fmt.setForeground(QColor(cor_fg))
            else:
                for code_str in seq.split(";"):
                    try:
                        code = int(code_str)
                    except ValueError:
                        continue
                    if code == 1:
                        fmt.setFontWeight(700)
                    elif code == 3:
                        fmt.setFontItalic(True)
                    elif code == 4:
                        fmt.setFontUnderline(True)
                    elif code in cores_ansi:
                        if 40 <= code <= 47 or 100 <= code <= 107:
                            fmt.setBackground(QColor(cores_ansi[code]))
                        else:
                            fmt.setForeground(QColor(cores_ansi[code]))
                    elif code == 39:
                        fmt.setForeground(QColor(cor_fg))
                    elif code == 49:
                        # reset background: remove cor explicita, herda do widget
                        from PySide6.QtGui import QBrush
                        fmt.setBackground(QBrush())

# ── Widget ────────────────────────────────────────────────────────────────────

class PowerShellTerminalWidget(QWidget):
    navegar_para_erro        = Signal(str, int)
    abrir_arquivo_solicitado = Signal(str)   # emitido por "abrir <arquivo>"

    def __init__(self, parent=None, project_path: str = None):
        super().__init__(parent)

        self._tema          = tema_global().dados()
        self._cor_fundo     = _cor(self._tema, "terminal", "fundo",          padrao="#000000")
        self._cor_texto     = _cor(self._tema, "terminal", "texto",          padrao="#f0e6c8")
        self._cor_cursor    = _cor(self._tema, "terminal", "cursor",         padrao="#26d3ed")
        self._cor_brilhante = _cor(self._tema, "terminal", "texto_brilhante",padrao="#ffffff")
        self._cores_ansi    = _montar_cores_ansi(self._tema)

        self.project_path = project_path
        self._input_start = 0
        self._terminal_id = str(uuid.uuid4())[:8]   # ID unico desta sessao
        self._servidores_rastreados: list = []       # cache local
        self._links_erro:    list[tuple[int, int, str, int]] = []
        self._links_url:     list[tuple[int, int, str]]       = []
        self._links_caminho: list[tuple[int, int, str]]       = []
        self._historico: list[str] = []
        self._hist_idx = -1
        self._ultimo_comando = ""
        self._ultimo_cmd_executado = ""  # nao zerado pelo eco; usado no rastreamento
        # DEPOIS
        self._suprimindo_setup      = True   # sempre suprime output inicial (encoding setup)
        self._projeto_para_mostrar  = ""
        self._venv_ativo            = False
        self._comando_tarefa        = ""   # comando a enviar após o setup concluir
        self._setup_concluido       = False  # guard: _mostrar_header_limpo já executou
        self._setup_iniciado        = False  # guard: set_project_path já foi disparado
        self._aguardando_prompt_natural  = False  # IMP-01: aguarda prompt natural do PS após HEIN_SETUP_OK
        self._suprimindo_proximo_prompt  = False  # IMP-01: suprime o segundo prompt independente que o PS emite

        self._cwd = project_path or None   # autocomplete: dir base p/ arquivos
        self._tab_ciclando = False         # autocomplete: sessão de ciclo de Tab ativa
        self._tab_matches: list = []       # candidatos da rodada atual
        self._tab_idx = -1                 # índice do candidato mostrado no momento
        self._tab_ini = 0                  # posição (doc) onde o prefixo começa
        self._tab_fim = 0                  # posição (doc) onde o texto inserido termina

        self._construir_ui()
        self._iniciar_processo()

    # DEPOIS
    # ⚠️  função grande (70 linhas)
    def _construir_ui(self):
        from _CONFIGURA_.gerenciador_perfil import obter_nome_usuario
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._barra_ps = QWidget()
        self._barra_ps.setFixedHeight(26)
        _lay_barra = QHBoxLayout(self._barra_ps)
        _lay_barra.setContentsMargins(6, 0, 4, 0)
        _lay_barra.setSpacing(2)

        nome = obter_nome_usuario()
        self._lbl_barra = QLabel(f"PowerShell  ·  hein IDE  ·  {nome}")
        self._lbl_barra.setStyleSheet(
            "color: #555555; font-size: 10px; background: transparent;"
        )
        _lay_barra.addWidget(self._lbl_barra)
        _lay_barra.addStretch()

        _estilo_mini = (
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover { background: rgba(255,255,255,0.07); }"
        )

        self._btn_copiar_ps = QPushButton()
        self._btn_copiar_ps.setIcon(icone_tema("mdi.content-copy"))
        self._btn_copiar_ps.setIconSize(QSize(14, 14))
        self._btn_copiar_ps.setFixedSize(22, 22)
        self._btn_copiar_ps.setToolTip("Copiar")
        self._btn_copiar_ps.setStyleSheet(_estilo_mini)
        self._btn_copiar_ps.clicked.connect(self._copiar_ps)

        self._btn_limpar_ps = QPushButton()
        self._btn_limpar_ps.setIcon(icone_tema("mdi.delete-sweep"))
        self._btn_limpar_ps.setIconSize(QSize(14, 14))
        self._btn_limpar_ps.setFixedSize(22, 22)
        self._btn_limpar_ps.setToolTip("Limpar")
        self._btn_limpar_ps.setStyleSheet(_estilo_mini)
        self._btn_limpar_ps.clicked.connect(self.limpar)

        _estilo_destruir = (
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover { background: rgba(224,108,117,0.15); }"
        )
        self._btn_matar_localhost = QToolButton()
        self._btn_matar_localhost.setIcon(icone_tema("mdi.power-plug-off"))
        self._btn_matar_localhost.setIconSize(QSize(14, 14))
        self._btn_matar_localhost.setFixedSize(22, 22)
        self._btn_matar_localhost.setToolTip(
            "Servidores iniciados neste terminal\n"
            "Clique para ver e encerrar processos rastreados"
        )
        self._btn_matar_localhost.setStyleSheet(_estilo_destruir)
        self._btn_matar_localhost.setPopupMode(QToolButton.InstantPopup)
        self._menu_servidores = QMenu(self._btn_matar_localhost)
        self._btn_matar_localhost.setMenu(self._menu_servidores)
        self._menu_servidores.aboutToShow.connect(self._popular_menu_servidores)

        # ── botão Ctrl+F ─────────────────────────────────────────────
        self._btn_busca_ps = QPushButton()
        self._btn_busca_ps.setIcon(icone_tema("mdi.magnify"))
        self._btn_busca_ps.setIconSize(QSize(14, 14))
        self._btn_busca_ps.setFixedSize(22, 22)
        self._btn_busca_ps.setToolTip("Buscar no terminal  (Ctrl+F)")
        self._btn_busca_ps.setStyleSheet(_estilo_mini)
        self._btn_busca_ps.clicked.connect(self._toggle_busca)

        _lay_barra.addWidget(self._btn_busca_ps)
        _lay_barra.addWidget(self._btn_copiar_ps)
        _lay_barra.addWidget(self._btn_limpar_ps)
        _lay_barra.addWidget(self._btn_matar_localhost)
        layout.addWidget(self._barra_ps)

        # ── barra de busca (oculta por padrão) ───────────────────────
        self._barra_busca = QWidget()
        self._barra_busca.setFixedHeight(28)
        self._barra_busca.setVisible(False)
        _lay_busca = QHBoxLayout(self._barra_busca)
        _lay_busca.setContentsMargins(6, 2, 4, 2)
        _lay_busca.setSpacing(4)

        self._input_busca = QLineEdit()
        self._input_busca.setPlaceholderText("Buscar no terminal...")
        self._input_busca.setFixedHeight(20)
        self._input_busca.returnPressed.connect(self._buscar_proximo)
        # Estilo do campo: mesmas chaves do tema_global() usadas em barra_buscas.py
        _t          = tema_global()
        _inp_fundo  = _t.cor("interface.inputs",      self._cor_fundo)
        _inp_texto  = _t.cor("interface.texto",       self._cor_texto)
        _inp_borda  = _t.cor("interface.borda",       self._cor_fundo)
        _inp_foco   = _t.cor("interface.borda_foco",  self._cor_cursor)
        _inp_fraco  = _t.cor("interface.texto_fraco", self._cor_texto)
        _inp_hover  = _t.cor("interface.fundo_item_hover", self._cor_fundo)
        self._input_busca.setStyleSheet(
            f"QLineEdit {{"
            f"  background:{_inp_fundo}; color:{_inp_texto};"
            f"  border:1px solid {_inp_borda}; border-radius:3px;"
            f"  padding:1px 6px; font-size:11pt;"
            f"}}"
            f"QLineEdit:focus {{ border-color:{_inp_foco}; }}"
        )

        _estilo_nav = (
            f"QPushButton {{"
            f"  background:transparent; color:{_inp_fraco};"
            f"  border:none; border-radius:3px; padding:0 4px; font-size:11pt;"
            f"}}"
            f"QPushButton:hover {{ background:{_inp_hover}; color:{_inp_texto}; }}"
        )
        self._btn_busca_ant  = QPushButton("▲")
        self._btn_busca_prox = QPushButton("▼")
        self._btn_fechar_busca = QPushButton("✕")
        for _b in (self._btn_busca_ant, self._btn_busca_prox, self._btn_fechar_busca):
            _b.setFixedSize(22, 20)
            _b.setStyleSheet(_estilo_nav)
        self._btn_busca_ant.setToolTip("Anterior")
        self._btn_busca_prox.setToolTip("Próximo")
        self._btn_fechar_busca.setToolTip("Fechar busca  (Esc)")
        self._btn_busca_ant.clicked.connect(self._buscar_anterior)
        self._btn_busca_prox.clicked.connect(self._buscar_proximo)
        self._btn_fechar_busca.clicked.connect(lambda: self._barra_busca.setVisible(False))

        self._lbl_busca_info = QLabel("")
        self._lbl_busca_info.setStyleSheet(
            f"color:{_inp_fraco}; font-size:9pt;"
        )

        _lay_busca.addWidget(self._input_busca)
        _lay_busca.addWidget(self._btn_busca_ant)
        _lay_busca.addWidget(self._btn_busca_prox)
        _lay_busca.addWidget(self._lbl_busca_info)
        _lay_busca.addStretch()
        _lay_busca.addWidget(self._btn_fechar_busca)
        layout.addWidget(self._barra_busca)

        self.console = QTextEdit()
        self.console.setReadOnly(False)
        self._aplicar_estilo()
        self.console.installEventFilter(self)
        self.console.viewport().installEventFilter(self)
        layout.addWidget(self.console)

    def _copiar_ps(self):
        if self.console.textCursor().hasSelection():
            self.console.copy()
        else:
            self.console.selectAll()
            self.console.copy()

    def _aplicar_estilo(self):
        from _CONFIGURA_ import FONTE_TERMINAL, TAMANHO_FONTE_TERMINAL
        try:
            from _CONFIGURA_.gerenciador_configurar import config_global
            _fonte = config_global().obter("terminal", "fonte", FONTE_TERMINAL)
            _pt    = int(config_global().obter("terminal", "tamanho_fonte", TAMANHO_FONTE_TERMINAL))
        except Exception:
            _fonte = FONTE_TERMINAL
            _pt    = TAMANHO_FONTE_TERMINAL

        self.console.setStyleSheet(f"""
            QTextEdit {{
                background-color: {self._cor_fundo};
                color: {self._cor_texto};
                border: none;
                font-family: '{_fonte}';
                font-size: {_pt}pt;
                selection-background-color: {self._cor_cursor};
                selection-color: {self._cor_fundo};
            }}
        """)
        # Paleta: garante contraste no bloco de cursor
        from PySide6.QtGui import QPalette
        pal = self.console.palette()
        pal.setColor(QPalette.Highlight,     QColor(self._cor_cursor))
        pal.setColor(QPalette.HighlightedText, QColor(self._cor_fundo))
        self.console.setPalette(pal)
        # IMP-02: cursor de bloco (estilo terminal clássico)
        # setCursorWidth define a largura visual do cursor — um char = bloco sólido
        _fm = self.console.fontMetrics()
        self.console.setCursorWidth(_fm.averageCharWidth())

    def atualizar_tema(self, tema: dict = None):
        """Chamado pelo hot-reload do gerenciador_tema."""
        self._tema          = tema_global().dados()
        self._cor_fundo     = _cor(self._tema, "terminal", "fundo",          padrao="#000000")
        self._cor_texto     = _cor(self._tema, "terminal", "texto",          padrao="#f0e6c8")
        self._cor_cursor    = _cor(self._tema, "terminal", "cursor",         padrao="#26d3ed")
        self._cor_brilhante = _cor(self._tema, "terminal", "texto_brilhante",padrao="#ffffff")
        self._cores_ansi    = _montar_cores_ansi(self._tema)
        self._aplicar_estilo()

    def _iniciar_processo(self):
        self.process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("TERM", "xterm-256color")
        env.insert("PYTHONIOENCODING", "utf-8")
        if IS_WINDOWS:
                env.insert("PYTHONUTF8", "1")
        self.process.setProcessEnvironment(env)
        self.process.readyReadStandardOutput.connect(self._ler_saida)
        self.process.readyReadStandardError.connect(self._ler_erro)

        if IS_WINDOWS:
            self.process.start("powershell.exe", ["-NoLogo", "-NoExit"])
        else:
            shell = os.environ.get("SHELL", "/bin/bash")
            self.process.start(shell, [])

        if self.project_path:
            _pp = self.project_path
            QTimer.singleShot(400, lambda: self.set_project_path(_pp))
        else:
            # sem projeto: configura encoding silenciosamente
            QTimer.singleShot(400, self._setup_encoding_sem_projeto)

    # DEPOIS
    def _ler_saida(self):
        raw  = self.process.readAllStandardOutput().data()
        text = raw.decode("utf-8", errors="replace")
        if self._suprimindo_setup:
            if "HEIN_SETUP_OK" in text:
                # IMP-01: remove sentinela; verifica se o prompt natural veio junto
                resto = re.sub(r'HEIN_SETUP_OK\r?\n?', '', text)
                resto_strip = resto.strip()
                if resto_strip and re.search(r'>\s*$', resto_strip):
                    # Prompt veio no mesmo chunk → exibe direto, sem enviar \r\n
                    self._mostrar_header_limpo(prompt_natural=resto_strip)
                else:
                    # Prompt ainda não chegou → aguarda próximo readyRead
                    self._aguardando_prompt_natural = True
                    QTimer.singleShot(1000, self._fallback_aguardo_prompt)
            elif self._aguardando_prompt_natural:
                # Próximo readyRead: verifica padrão de prompt do PS
                texto_strip = text.strip()
                if texto_strip and re.search(r'>\s*$', texto_strip):
                    # Prompt detectado → passa o texto, sem enviar \r\n
                    self._aguardando_prompt_natural = False
                    self._mostrar_header_limpo(prompt_natural=texto_strip)
                # else: chunk intermediário → descarta, continua aguardando

            return

        # IMP-01: suprime o prompt independente que o PS emite logo após o setup
        if self._suprimindo_proximo_prompt:
            self._suprimindo_proximo_prompt = False
            texto_strip = text.strip()
            # Só suprime se o chunk inteiro for apenas prompt PS (padrão ancorado)
            # Cobre: (.venv) PS C:\...> e PS C:\...> com/sem prefixo
            _PAT_PROMPT = re.compile(
                r'^(\(\S+\)\s+)?PS\s+\S.*>\s*$', re.MULTILINE
            )
            linhas_reais = [l.strip() for l in texto_strip.split('\n') if l.strip()]
            e_so_prompt = (bool(_PAT_PROMPT.search(texto_strip)) and
                           all(_PAT_PROMPT.match(l) for l in linhas_reais)
                           ) if linhas_reais else True
            if e_so_prompt:
                self._mark_input_start()

                return

            # Se tem conteúdo real junto, deixa passar normalmente

        # suprime eco: PS devolve o comando digitado (as vezes com prefixo de prompt)
        if self._ultimo_comando:
            linhas = text.split("\n", 1)
            primeira = linhas[0].strip()
            cmd_strip = self._ultimo_comando.strip()
            if primeira == cmd_strip or primeira.endswith("> " + cmd_strip):
                text = linhas[1] if len(linhas) > 1 else ""
                self._ultimo_comando = ""
        # Remove apenas a linha do sentinela, preservando todas as outras quebras
        text = re.sub(r'HEIN_SETUP_OK\r?\n?', '', text)
        if text:
            self._inserir_ansi(traduzir(text))
        self._mark_input_start()
        self._detectar_pip_instalado(text)
        self._detectar_servidor(text)

    def _ler_erro(self):
        raw  = self.process.readAllStandardError().data()
        text = raw.decode("utf-8", errors="replace")
        text = traduzir(text)
        if self._suprimindo_setup:

            return

        text = re.sub(r'HEIN_SETUP_OK\r?\n?', '', text)
        self._inserir_ansi(text)
        self._mark_input_start()
        # pip às vezes imprime "Successfully installed" no stderr também
        self._detectar_pip_instalado(text)
        # uvicorn, flask e outros logam a URL de escuta no stderr
        self._detectar_servidor(text)

    def _detectar_pip_instalado(self, texto: str) -> None:
        """
        Detecta 'Successfully installed X-ver Y-ver …' no output do terminal.
        Registra somente o primeiro token de cada par (nome sem versão de dependências),
        evitando guardar dependências transitivas — só o que o usuário instalou
        explicitamente está na linha principal do pip.

        Nota: o pip sempre imprime TODOS os pacotes afetados numa única linha.
        Guardamos todos eles porque o usuário pediu exatamente este pacote; as
        dependências aparecem em linhas separadas de "Collecting …" e não disparam
        este regex.
        """
        for m in _RE_PIP_OK.finditer(texto):
            tokens = m.group(1).split()
            for token in tokens:
                token = token.strip()
                if not token:
                    continue
                nome, versao = extrair_nome_versao(token)
                if nome and nome[0].isalpha():
                    _pkg_registrar(self.project_path or "", nome, versao)
            # feedback na status bar: mostra o primeiro pacote da lista
            if tokens:
                nome_principal, _ = extrair_nome_versao(tokens[0])
                self._status(f"'{nome_principal}' instalado", 4000)
            # notifica a aba Pacotes para se atualizar
            self._avisar_aba_pacotes()

    def _status(self, msg: str, duracao: int = 0) -> None:
        """Envia mensagem para a status bar da janela principal."""
        janela = self.window()
        if not hasattr(janela, "statusBar"):

            return

        if duracao:
            janela.statusBar().showMessage(msg, duracao)
        else:
            janela.statusBar().showMessage(msg)

    # ⚠️  except genérico vazio
    def _avisar_aba_pacotes(self) -> None:
        """Pede para a aba Pacotes se atualizar (se existir no TerminalTabWidget)."""
        try:
            from _UTILITARIOS_.gerenciador_pacotes import GerenciadorPacotes
            tab_widget = self.parent()
            if tab_widget is None:

                return

            for i in range(tab_widget.count()):
                w = tab_widget.widget(i)
                if isinstance(w, GerenciadorPacotes):
                    w.atualizar()
                    break
        except Exception:
            pass

    def _inserir_ansi(self, text: str):
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.End)
        for chunk, fmt in _parse_ansi(text, self._cores_ansi, self._cor_texto, self._cor_fundo):
            matches = [("tb", m) for m in _RE_TRACEBACK.finditer(chunk)]
            matches += [("url", m) for m in _RE_URL.finditer(chunk)]
            matches += [("caminho", m) for m in _RE_CAMINHO.finditer(chunk)]
            matches.sort(key=lambda x: x[1].start())
            if not matches:
                cursor.insertText(chunk, fmt)
            else:
                from _CONFIGURA_ import COR_INFO
                ultimo = 0
                for tipo, m in matches:
                    if m.start() < ultimo:
                        continue
                    cursor.insertText(chunk[ultimo:m.start()], fmt)
                    ini = cursor.position()
                    if tipo == "tb":
                        fmt_link = QTextCharFormat(fmt)
                        fmt_link.setForeground(
                            tema_global().qcolor("editor.info", COR_INFO)
                        )
                        fmt_link.setFontUnderline(True)
                        cursor.insertText(m.group(0), fmt_link)
                        fim = cursor.position()
                        self._links_erro.append((ini, fim, m.group(1), int(m.group(2))))
                    elif tipo == "url":
                        fmt_url = QTextCharFormat(fmt)
                        from _CONFIGURA_ import COR_INFO
                        fmt_url.setForeground(tema_global().qcolor("terminal.link_url", COR_INFO))
                        fmt_url.setFontUnderline(True)
                        cursor.insertText(m.group(0), fmt_url)
                        fim = cursor.position()
                        self._links_url.append((ini, fim, m.group(0)))
                    else:
                        fmt_caminho = QTextCharFormat(fmt)
                        from _CONFIGURA_ import COR_SINTAXE_NUMERO
                        fmt_caminho.setForeground(tema_global().qcolor("terminal.link_caminho", COR_SINTAXE_NUMERO))
                        fmt_caminho.setFontUnderline(True)
                        cursor.insertText(m.group(0), fmt_caminho)
                        fim = cursor.position()
                        self._links_caminho.append((ini, fim, m.group(0)))
                    ultimo = m.end()
                cursor.insertText(chunk[ultimo:], fmt)
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()

    def _mark_input_start(self):
        self._input_start = self.console.textCursor().position()

    def enviar_comando(self, cmd: str):
        if cmd.strip():
            self._ultimo_comando       = cmd
            self._ultimo_cmd_executado = cmd
        self.process.write((cmd + "\n").encode())

    def limpar(self):
        self.console.clear()
        self._links_erro.clear()
        self._links_url.clear()
        self._links_caminho.clear()
        self._mark_input_start()

    def set_project_path(self, path: str):
        """Navega para o projeto, ativa o .venv e exibe header limpo."""
        if not (path and os.path.exists(path)):

            return

        # Guard: bloqueia re-chamada com mesmo projeto ANTES do setup terminar
        # (QTimer 400ms + chamada externa chegam quase juntos — _setup_iniciado
        #  é setado na primeira e bloqueia a segunda, evitando prompt duplo)
        if self._setup_iniciado and self.project_path == path:

            return

        self._setup_iniciado       = True    # marca: setup deste path já foi disparado
        self._setup_concluido      = False   # permite novo header se projeto mudou
        self.project_path          = path
        self._projeto_para_mostrar = path
        self._cwd                  = path    # autocomplete: cwd inicial = raiz do projeto
        self._suprimindo_setup     = True

        if IS_WINDOWS:
            path_ps    = path.replace("/", "\\")
            venv_dir   = os.path.join(path, ".venv")
            python_exe = os.path.join(venv_dir, "Scripts", "python.exe")
            self._venv_ativo = os.path.exists(python_exe)

            # Comando composto: UTF-8 + cd + venv + sentinel (1 linha = 1 echo)
            partes = [
                "chcp 65001 | Out-Null",
                "$OutputEncoding = [System.Text.Encoding]::UTF8",
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8",
                "[Console]::InputEncoding  = [System.Text.Encoding]::UTF8",
                f'Set-Location "{path_ps}"',
            ]
            if self._venv_ativo:
                            venv_ps = venv_dir.replace("/", "\\")
                            partes += [
                                f'& "{venv_ps}\\Scripts\\Activate.ps1"',
                            ]
            partes.append('Write-Host "HEIN_SETUP_OK"')
            cmd = "; ".join(partes)
            self.process.write((cmd + "\r\n").encode("utf-8"))

        else:
            path_u   = path.replace("\\", "/")
            activate = os.path.join(path, ".venv", "bin", "activate")
            self._venv_ativo = os.path.exists(activate)
            partes = [f'cd "{path_u}"']
            if self._venv_ativo:
                partes.append(f'source "{activate}"')
            partes.append("echo HEIN_SETUP_OK")
            self.process.write((" && ".join(partes) + "\n").encode("utf-8"))

# DEPOIS
    def _fallback_aguardo_prompt(self):
        """Fallback IMP-01: prompt não detectado em 1s → pede um novo ao PS."""
        if self._aguardando_prompt_natural:
            self._aguardando_prompt_natural = False
            self._mostrar_header_limpo(prompt_natural="")  # sem prompt → envia \r\n

    def _mostrar_header_limpo(self, prompt_natural: str = ""): # IMP-01: prompt_natural = texto do prompt já capturado pelo PS. # Quando fornecido, é exibido diretamente — sem enviar \r\n ao PS, # eliminando a segunda fonte de prompt que causava o prompt duplo.
        self._aguardando_prompt_natural = False
        # Guard: impede header duplo (set_project_path chamado 2×)
        if self._setup_concluido:

            return

        self._setup_concluido = True
        self.console.clear()
        if self._projeto_para_mostrar:
            self._write_colored(
                "Copyright (C) Microsoft Corporation. All rights reserved.\n\n",
                self._cor_texto
            )
            self._inserir_ansi("https://github.com/Henriq-Ls/hein-IDE/blob/main/README.md\n")
            self._write_colored("─" * 60 + "\n\n", "#444444")
            nome_proj = os.path.basename(self._projeto_para_mostrar)
            venv_txt  = "  [.venv ✓]" if self._venv_ativo else "  [sem .venv]"
            self._lbl_barra.setText(f"PowerShell  ·  {nome_proj}{venv_txt}")
        self._suprimindo_setup = False
        if prompt_natural:
            # Exibe o prompt já capturado — sem disparar novo readyRead
            self._inserir_ansi(prompt_natural)
            # PS ainda vai emitir seu prompt independente uma vez → suprime
            self._suprimindo_proximo_prompt = True
        else:
            # Fallback (prompt não detectado a tempo): pede um novo ao PS
            self.process.write(b"\r\n")
        self._mark_input_start()
        # ── hook de tarefa: envia o comando pendente após setup ──────────
        if self._comando_tarefa:
            from PySide6.QtCore import QTimer
            _cmd = self._comando_tarefa
            self._comando_tarefa = ""
            QTimer.singleShot(80, lambda: self.enviar_comando(_cmd))

    def append_output(self, text: str):
        """Escreve texto colorido de saída (usa cor do tema terminal)."""
        cor = _cor(self._tema, "terminal", "texto_brilhante", padrao="#ffffff")
        self._write_colored(text, cor)
        self._mark_input_start()

    def clear_terminal(self):
        self.console.clear()
        self._mark_input_start()

    # ⚠️  função grande (92 linhas)
    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        from _LOG_.log import log
        try:
            viewport = self.console.viewport()
        except RuntimeError:

            return False

        if obj is viewport:
            if event.type() == QEvent.MouseButtonPress:
                self.console.setFocus()
                log.info("terminal_powershell.py", "eventFilter", "clique no viewport → setFocus")
                if event.button() == Qt.LeftButton:
                    pos_cursor = self.console.cursorForPosition(event.pos()).position()
                    for ini, fim, arquivo, linha in self._links_erro:
                        if ini <= pos_cursor <= fim:
                            self.navegar_para_erro.emit(arquivo, linha)

                            return True

                    for ini, fim, url in self._links_url:
                        if ini <= pos_cursor <= fim:
                            from PySide6.QtCore import QUrl
                            QDesktopServices.openUrl(QUrl(url))

                            return True

                    for ini, fim, _caminho in self._links_caminho:
                        if ini <= pos_cursor <= fim:
                            _p = os.path.normpath(_caminho)
                            from PySide6.QtCore import QUrl
                            if os.path.isdir(_p):
                                QDesktopServices.openUrl(QUrl.fromLocalFile(_p))
                            elif os.path.isfile(_p):
                                self.navegar_para_erro.emit(_p, 1)

                            return True

            if event.type() == QEvent.MouseMove:
                ctrl = bool(event.modifiers() & Qt.ControlModifier)
                pos_cursor = self.console.cursorForPosition(event.pos()).position()
                sobre_link = False
                for ini, fim, arquivo, linha in self._links_erro:
                    if ini <= pos_cursor <= fim:
                        sobre_link = True
                        self.console.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
                        nome = os.path.basename(arquivo)
                        dica = f"{nome}  —  linha {linha}\n{arquivo}"
                        if ctrl: dica += "\n\u2192 Ctrl+Click: abrir no editor"
                        QToolTip.showText(event.globalPos(), dica, self.console.viewport())
                        break
                if not sobre_link:
                    for ini, fim, url in self._links_url:
                        if ini <= pos_cursor <= fim:
                            sobre_link = True
                            self.console.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
                            dica = url + ("\n\u2192 Ctrl+Click: abrir navegador" if ctrl else "")
                            QToolTip.showText(event.globalPos(), dica, self.console.viewport())
                            break
                if not sobre_link:
                    for ini, fim, _caminho in self._links_caminho:
                        if ini <= pos_cursor <= fim:
                            _p = os.path.normpath(_caminho)
                            if os.path.exists(_p):
                                sobre_link = True
                                self.console.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
                                if os.path.isdir(_p):
                                    acao = "\u2192 Ctrl+Click: abrir no Explorer" if ctrl else "Abrir pasta"
                                    dica = f"{acao}\n{_p}"
                                else:
                                    acao = "\u2192 Ctrl+Click: abrir no editor" if ctrl else os.path.basename(_p)
                                    dica = f"{acao}\n{_p}"
                                QToolTip.showText(event.globalPos(), dica, self.console.viewport())
                            break
                if not sobre_link:
                    self.console.viewport().setCursor(Qt.CursorShape.IBeamCursor)
                    QToolTip.hideText()

                return False

            if event.type() == QEvent.ContextMenu:
                self._mostrar_menu_contexto(event.globalPos())

                return True

        if obj is self.console:
            # IMP-03: bloqueia Ctrl+F global (QAction da IDE) quando o terminal tem foco
            # ShortcutOverride dispara ANTES do QAction → accept() impede a IDE de consumir
            if event.type() == QEvent.ShortcutOverride:
                key = event.key()
                mod = event.modifiers()
                if key == Qt.Key_F and (mod & Qt.ControlModifier):
                    event.accept()

                    return True

            if event.type() == QEvent.KeyPress:

                return self._tratar_tecla(event)

        return super().eventFilter(obj, event)

    def _mostrar_menu_contexto(self, pos_global):
        from _UTILITARIOS_.hein_context_menu import heinContextMenu
        from PySide6.QtWidgets import QApplication
        tem_sel = self.console.textCursor().hasSelection()

        def _colar():
            texto = QApplication.clipboard().text()
            if texto:
                cursor = self.console.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.console.setTextCursor(cursor)
                self._insert_char(texto)

        itens = [
            ("Copiar",        "mdi.content-copy",  self.console.copy),
            ("Colar",         "mdi.content-paste", _colar),
            None,
            ("Selecionar Tudo", "mdi.select-all",  self.console.selectAll),
            None,
            ("Limpar",        "mdi.delete-sweep",  self.limpar),
        ]

        menu = heinContextMenu(parent=self, itens=itens)
        menu.acao("Copiar").setEnabled(tem_sel)
        menu.exec(pos_global)

    # ⚠️  função grande (82 linhas)
    def _tratar_tecla(self, event):
        key  = event.key()
        mod  = event.modifiers()
        text = event.text()

        if key != Qt.Key_Tab and self._tab_ciclando:
            self._tab_ciclando = False
            self._tab_matches  = []
            self._tab_idx      = -1

        if key in (Qt.Key_Return, Qt.Key_Enter):
            QToolTip.hideText()
            cursor = self.console.textCursor()
            cursor.movePosition(QTextCursor.End)
            end_pos = cursor.position()
            cursor.setPosition(self._input_start)
            cursor.setPosition(end_pos, QTextCursor.KeepAnchor)
            cmd = cursor.selectedText().replace('\u2029', '\n')
            cursor.movePosition(QTextCursor.End)
            self.console.setTextCursor(cursor)
            self.console.insertPlainText("\n")
            if cmd.strip():
                self._historico.append(cmd)
                self._ultimo_comando = cmd
                self._ultimo_cmd_executado = cmd
            self._hist_idx = -1
            # Comando hein: "abrir <arquivo>" — abre no editor sem enviar ao PS
            _abrir_m = __import__('re').match(
                r'abrir\s+(.+)', cmd.strip(), __import__('re').IGNORECASE
            )
            if _abrir_m:
                _nome_arq    = _abrir_m.group(1).strip().strip('"\'')
                _caminho_arq = self._encontrar_arquivo_projeto(_nome_arq)
                if _caminho_arq:
                    self._write_colored(
                        f"[hein] Abrindo {_caminho_arq}\n", self._cor_cursor
                    )
                    self.abrir_arquivo_solicitado.emit(_caminho_arq)
                else:
                    self._write_colored(
                        f"[hein] Arquivo não encontrado: {_nome_arq}\n", "#e06c75"
                    )
                self._mark_input_start()

                return True

            self._atualizar_cwd_por_comando(cmd)

            # Fix: .ps1 digitado sem prefixo .\ nao e reconhecido pelo PowerShell
            _cmd_env = cmd.strip()
            if (_cmd_env.lower().endswith(".ps1")
                    and not _cmd_env.startswith(".\\") and not _cmd_env.startswith("./")
                    and "\\" not in _cmd_env and "/" not in _cmd_env):
                _cmd_env = ".\\" + _cmd_env
            self.process.write((_cmd_env + "\n").encode())
            self._mark_input_start()

            return True

        if key == Qt.Key_Backspace:
            if self.console.textCursor().position() <= self._input_start:

                return True

            QTimer.singleShot(0, self._atualizar_dica_autocomplete)

            return False

        if key == Qt.Key_Up:
            if self._historico:
                self._hist_idx = min(self._hist_idx + 1, len(self._historico) - 1)
                self._set_input(self._historico[-(self._hist_idx + 1)])
                self._atualizar_dica_autocomplete()

            return True

        if key == Qt.Key_Down:
            if self._hist_idx > 0:
                self._hist_idx -= 1
                self._set_input(self._historico[-(self._hist_idx + 1)])
            else:
                self._hist_idx = -1
                self._set_input("")
            self._atualizar_dica_autocomplete()

            return True

        if key == Qt.Key_Tab and not mod & (Qt.ControlModifier | Qt.ShiftModifier):
            self._tratar_tab()

            return True

        if key == Qt.Key_Escape:
            QToolTip.hideText()

            return True

        if key == Qt.Key_C and mod & Qt.ControlModifier:
            self.process.write(b"\x03")

            return True

        if key == Qt.Key_L and mod & Qt.ControlModifier:
            self.limpar()

            return True

        if key == Qt.Key_F and mod & Qt.ControlModifier:
            self._toggle_busca()

            return True

        if key == Qt.Key_Left:
            if self.console.textCursor().position() <= self._input_start:

                return True

            return False

        if text and not mod & Qt.ControlModifier:
            if self.console.textCursor().position() < self._input_start:
                cursor = self.console.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.console.setTextCursor(cursor)
            self._insert_char(text)
            self._atualizar_dica_autocomplete()

            return True

        return False

    # ── Autocomplete básico (arquivos + pacotes) ────────────────────────────────

    _RE_CD = __import__('re').compile(
        r'^\s*(?:cd|Set-Location|sl)\s+[\'"]?([^\'"]+)[\'"]?\s*$',
        __import__('re').IGNORECASE,
    )
    _RE_IMPORT_CTX = __import__('re').compile(
        r'^\s*(?:import|from)\s+([\w.]*)$',
        __import__('re').IGNORECASE,
    )

    def _atualizar_cwd_por_comando(self, cmd: str) -> None:
        """Rastreia cd/Set-Location para manter self._cwd correto (best-effort)."""
        m = self._RE_CD.match(cmd)
        if not m or not self._cwd:

            return

        alvo = m.group(1).strip()
        novo = alvo if os.path.isabs(alvo) else os.path.normpath(os.path.join(self._cwd, alvo))
        if os.path.isdir(novo):
            self._cwd = novo

    def _cursor_no_fim_da_linha(self) -> bool:
        """
        True só quando o cursor está exatamente no fim do documento.
        Tab-completion e a dica só operam nessa condição — evitar completar
        no meio da linha (depois de mover com ←) é o que causava corrupção
        de texto (caracteres duplicados/glifo de caixa) ao misturar a lógica
        de 'substituir até o fim' com um cursor que não estava no fim.
        """
        cursor = self.console.textCursor()
        fim = QTextCursor(self.console.document())
        fim.movePosition(QTextCursor.End)

        return cursor.position() == fim.position()

    def _prefixo_atual(self):
        """Retorna (texto_da_linha_ate_o_cursor, prefixo_da_palavra, pos_inicio_prefixo)."""
        cursor = self.console.textCursor()
        pos = cursor.position()
        if pos < self._input_start:

            return "", "", pos

        c2 = self.console.textCursor()
        c2.setPosition(self._input_start)
        c2.setPosition(pos, QTextCursor.KeepAnchor)
        linha = c2.selectedText().replace('\u2029', '\n')
        i = len(linha)
        while i > 0 and linha[i - 1] not in (' ', '\t'):
            i -= 1
        prefixo = linha[i:]

        return linha, prefixo, self._input_start + i

    def _listar_arquivos_cwd(self, prefixo: str) -> list:
        """
        Nomes de arquivos/pastas que batem com o prefixo, dentro do diretório atual
        do terminal. Suporta caminho com subpasta (ex: 'models\\liv') — nesse caso
        lista dentro de 'models\\' e devolve o candidato já com o prefixo de volta,
        para o Tab completar 'models\\livros.py' e não só 'livros.py'.
        """
        base = self._cwd or self.project_path
        if not base or not os.path.isdir(base):

            return []

        sep_pos = max(prefixo.rfind('/'), prefixo.rfind('\\'))
        if sep_pos >= 0:
            subcaminho   = prefixo[:sep_pos + 1]      # inclui a barra, ex: 'models\\'
            parcial      = prefixo[sep_pos + 1:]
            alvo         = os.path.join(base, subcaminho)
        else:
            subcaminho   = ""
            parcial      = prefixo
            alvo         = base

        if not os.path.isdir(alvo):

            return []

        try:
            nomes = os.listdir(alvo)
        except OSError:

            return []

        parcial_l = parcial.lower()
        resultado = []
        for nome in sorted(nomes):
            if not nome.lower().startswith(parcial_l):
                continue
            if nome.startswith('.') and not parcial.startswith('.'):
                continue
            completo = os.path.join(alvo, nome)
            resultado.append(subcaminho + nome + ("\\" if os.path.isdir(completo) else ""))

        return resultado

    def _listar_pacotes_venv(self, prefixo: str) -> list:
        """Módulos importáveis: pacotes do .venv do projeto + stdlib do processo hein."""
        prefixo_l = prefixo.lower()
        nomes = set()

        base = self.project_path
        if base:
            if IS_WINDOWS:
                site_pkgs = os.path.join(base, ".venv", "Lib", "site-packages")
            else:
                site_pkgs = os.path.join(base, ".venv", "lib")
            if IS_WINDOWS and os.path.isdir(site_pkgs):
                for nome in os.listdir(site_pkgs):
                    if nome.endswith((".dist-info", ".egg-info", ".egg-link")) or nome.startswith("_"):
                        continue
                    nomes.add(nome[:-3] if nome.endswith(".py") else nome)
            elif not IS_WINDOWS and os.path.isdir(site_pkgs):
                for pyver in os.listdir(site_pkgs):
                    sp = os.path.join(site_pkgs, pyver, "site-packages")
                    if os.path.isdir(sp):
                        for nome in os.listdir(sp):
                            if nome.endswith((".dist-info", ".egg-info", ".egg-link")) or nome.startswith("_"):
                                continue
                            nomes.add(nome[:-3] if nome.endswith(".py") else nome)

        import sys as _sys
        nomes.update(getattr(_sys, "stdlib_module_names", ()))

        return sorted(n for n in nomes if n and not n.startswith("_") and n.lower().startswith(prefixo_l))

    def _tratar_tab(self) -> None:
        """
        Autocomplete básico do terminal: Tab completa/cicla entre candidatos.
        Contexto 'import X' / 'from X' → sugere pacotes do .venv + stdlib.
        Caso contrário → sugere arquivos/pastas do diretório atual do terminal.
        """
        if not self._cursor_no_fim_da_linha():

            return

        if self._tab_ciclando and self._tab_matches:
            self._tab_idx = (self._tab_idx + 1) % len(self._tab_matches)
            self._substituir_prefixo(self._tab_matches[self._tab_idx])
            QToolTip.hideText()

            return

        linha, prefixo, pos_ini = self._prefixo_atual()
        if not prefixo:

            return

        if self._RE_IMPORT_CTX.match(linha):
            candidatos = self._listar_pacotes_venv(prefixo)
        else:
            candidatos = self._listar_arquivos_cwd(prefixo)

        if not candidatos:

            return

        self._tab_ini      = pos_ini
        self._tab_matches  = candidatos
        self._tab_idx      = 0
        self._tab_ciclando = len(candidatos) > 1
        self._substituir_prefixo(candidatos[0])
        QToolTip.hideText()

    def _substituir_prefixo(self, texto: str) -> None:
        """Substitui o trecho [self._tab_ini, fim_da_linha_de_input] pelo candidato escolhido."""
        cursor = self.console.textCursor()
        cursor.setPosition(self._tab_ini)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(self._cor_brilhante))
        cursor.setCharFormat(fmt)
        cursor.insertText(texto)
        self._tab_fim = cursor.position()
        self.console.setTextCursor(cursor)

    def _atualizar_dica_autocomplete(self) -> None:
        """
        Tooltip leve (sem popup) que mostra os candidatos de Tab enquanto o
        usuário digita — não altera o texto, só avisa o que Tab faria.
        """
        if self._tab_ciclando:
            # já estamos em ciclo de Tab; o texto mostra a escolha atual

            return

        if not self._cursor_no_fim_da_linha():
            QToolTip.hideText()

            return

        linha, prefixo, _ = self._prefixo_atual()
        if not prefixo:
            QToolTip.hideText()

            return

        if self._RE_IMPORT_CTX.match(linha):
            candidatos = self._listar_pacotes_venv(prefixo)
        else:
            candidatos = self._listar_arquivos_cwd(prefixo)

        if not candidatos:
            QToolTip.hideText()

            return

        MOSTRAR = 8
        texto_dica = "  ".join(candidatos[:MOSTRAR])
        if len(candidatos) > MOSTRAR:
            texto_dica += f"  … (+{len(candidatos) - MOSTRAR})"
        rect = self.console.cursorRect()
        pos  = self.console.viewport().mapToGlobal(rect.bottomLeft())
        QToolTip.showText(pos, f"Tab  →  {texto_dica}", self.console)

    def _set_input(self, texto: str):
        cursor = self.console.textCursor()
        cursor.setPosition(self._input_start)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(texto)
        self.console.setTextCursor(cursor)

    def _insert_char(self, ch: str):
        """Insere caractere digitado usando a cor brilhante do tema."""
        cursor = self.console.textCursor()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(self._cor_brilhante))
        # sem setBackground: herda o fundo do widget
        cursor.setCharFormat(fmt)
        cursor.insertText(ch)
        self.console.setTextCursor(cursor)

    def _write_colored(self, text: str, color: str):
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        # sem setBackground: herda o fundo do widget (atualiza com o tema)
        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()

    # ── Rastreamento de servidores locais ──────────────────────────────────────

    def _arquivo_servidores(self) -> pathlib.Path:
        """JSON em ~/.hein/servidores_locais.json"""
        p = pathlib.Path.home() / ".hein"
        p.mkdir(exist_ok=True)

        return p / "servidores_locais.json"

    def _carregar_servidores(self) -> list:
        """Le o JSON de servidores rastreados (todos os terminais)."""
        arq = self._arquivo_servidores()
        if not arq.exists():

            return []

        try:

            return json.loads(arq.read_text(encoding="utf-8"))

        except Exception:

            return []

    # ⚠️  except genérico vazio
    def _salvar_servidores(self, lista: list) -> None:
        """Persiste a lista de servidores no JSON."""
        try:
            self._arquivo_servidores().write_text(
                json.dumps(lista, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass

    def _detectar_servidor(self, text: str) -> None:
        """
        Varre o output do terminal buscando URLs de servidor local.
        Quando detecta http://127.0.0.1:PORT (ou localhost / 0.0.0.0),
        registra {porta, terminal_id, comando, quando} no JSON.
        Ignora portas ja rastreadas por este terminal.
        """
        for m in _RE_SERVIDOR.finditer(text):
            porta = int(m.group(1))
            todos = self._carregar_servidores()
            ja_tem = any(
                e.get("porta") == porta and e.get("terminal_id") == self._terminal_id
                for e in todos
            )
            if ja_tem:
                continue
            entrada = {
                "porta":       porta,
                "terminal_id": self._terminal_id,
                "comando":     self._ultimo_cmd_executado.strip() or "desconhecido",
                "quando":      datetime.datetime.now().strftime("%H:%M:%S"),
                "project":     self.project_path or "",
            }
            todos.append(entrada)
            self._servidores_rastreados = [
                e for e in todos if e.get("terminal_id") == self._terminal_id
            ]
            self._salvar_servidores(todos)
            self._status(f"Servidor detectado na porta {porta}", 3000)

    def _porta_ativa(self, porta: int) -> bool:
        """Verifica se ha algum processo escutando na porta (socket rapido)."""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)

                return s.connect_ex(("127.0.0.1", porta)) == 0

        except Exception:

            return False

    # ⚠️  função grande (53 linhas)
    def _popular_menu_servidores(self) -> None:
        """Preenche o menu dropdown antes de exibir."""
        self._menu_servidores.clear()
        todos = self._carregar_servidores()
        # Sanitiza: garante que porta e int valido em todas as entradas
        todos = [e for e in todos if isinstance(e.get("porta"), int) and e["porta"] > 0]
        meus  = [e for e in todos if e.get("terminal_id") == self._terminal_id]

        # Remove portas inativas de todos os terminais (limpeza global)
        todos_ativos = [e for e in todos if self._porta_ativa(e["porta"])]
        if len(todos_ativos) != len(todos):
            self._salvar_servidores(todos_ativos)
            meus = [e for e in todos_ativos if e.get("terminal_id") == self._terminal_id]
            self._servidores_rastreados = meus

        if not meus:
            # Sem rastreamento: escaneia portas de dev comuns
            portas_dev = [3000, 4000, 4173, 5000, 5173, 8000, 8080]
            ativas = [p for p in portas_dev if self._porta_ativa(p)]
            if ativas:
                cab = self._menu_servidores.addAction(
                    "Portas ativas (nao rastreadas):"
                )
                cab.setEnabled(False)
                for p in ativas:
                    a = self._menu_servidores.addAction(f"  x  :{p}")
                    a.triggered.connect(
                        lambda checked=False, _p=p: self._matar_porta_avulsa(_p)
                    )
                self._menu_servidores.addSeparator()
            else:
                vazio = self._menu_servidores.addAction("Nenhum servidor ativo")
                vazio.setEnabled(False)
                self._menu_servidores.addSeparator()
            tudo = self._menu_servidores.addAction("x  Matar todas as portas de dev")
            tudo.triggered.connect(self._matar_localhost_tudo)

            return

        # Servidores rastreados: lista um por um com kill individual
        for e in meus:
            porta   = e["porta"]
            comando = e.get("comando", "?")[:40]
            quando  = e.get("quando", "")
            label   = f"  x  :{porta}  -  {comando}  ({quando})"
            acao = self._menu_servidores.addAction(label)
            acao.triggered.connect(lambda checked=False, _e=e: self._matar_servidor_rastreado(_e))

        self._menu_servidores.addSeparator()
        todos_acao = self._menu_servidores.addAction(
            f"x  Encerrar todos deste terminal ({len(meus)})"
        )
        todos_acao.triggered.connect(self._matar_todos_rastreados)

    def _matar_servidor_rastreado(self, entrada: dict) -> None:
        """Mata o processo na porta rastreada e remove do JSON."""
        porta = entrada["porta"]
        if IS_WINDOWS:
            cmd = (
                # Busca PID na porta + PID do processo pai (ex: uvicorn reloader)
                f"$ids = @(netstat -ano | Select-String ':{porta}\\s') "
                "| ForEach-Object { ($_ -split '\\s+')[-1] } "
                "| Where-Object { $_ -match '^[1-9][0-9]*$' } | Sort-Object -Unique; "
                "$todos = @(); "
                "foreach ($x in $ids) { "
                "  $todos += $x; "
                "  try { "
                "    $pai = (Get-CimInstance Win32_Process -Filter \"ProcessId=$x\" -EA SilentlyContinue).ParentProcessId; "
                "    if ($pai -and \"$pai\" -match '^[1-9][0-9]*$') { $todos += \"$pai\" } "
                "  } catch {} "
                "}; "
                "$mortos = @(); "
                "foreach ($x in ($todos | Sort-Object -Unique)) { "
                "  taskkill /PID $x /F /T 2>$null | Out-Null; "
                "  if ($LASTEXITCODE -eq 0) { $mortos += \"PID $x\" } "
                "}; "
                f"if ($mortos.Count -gt 0) {{ Write-Host '[hein] Encerrado:' ($mortos -join ', ') '(porta {porta})' }} "
                f"else {{ Write-Host '[hein] Porta {porta}: nenhum processo encontrado.' }}"
            )
        else:
            cmd = (
                f"_pids=$(lsof -ti :{porta} 2>/dev/null); "
                '[ -n "$_pids" ] && echo "$_pids" | xargs kill -15 2>/dev/null; '
                "sleep 0.3; "
                '[ -n "$_pids" ] && echo "$_pids" | xargs kill -9 2>/dev/null; '
                f"echo '[hein] Porta {porta} encerrada.'"
            )
        self.enviar_comando(cmd)
        # Remove do JSON
        todos = self._carregar_servidores()
        todos = [
            e for e in todos
            if not (e.get("porta") == porta and e.get("terminal_id") == self._terminal_id)
        ]
        self._salvar_servidores(todos)
        self._servidores_rastreados = [
            e for e in self._servidores_rastreados if e.get("porta") != porta
        ]

    def _matar_todos_rastreados(self) -> None:
        """Mata todos os servidores rastreados por este terminal."""
        todos = self._carregar_servidores()
        meus  = [e for e in todos if e.get("terminal_id") == self._terminal_id]
        for e in meus:
            self._matar_servidor_rastreado(e)

    def _matar_porta_avulsa(self, porta: int) -> None:
        """
        Mata processo em uma porta especifica sem rastreamento previo.
        Usado no fallback de scan de portas ativas.
        """
        if IS_WINDOWS:
            cmd = (
                # Busca PID na porta + PID do processo pai (ex: uvicorn reloader)
                f"$ids = @(netstat -ano | Select-String ':{porta}\\s') "
                "| ForEach-Object { ($_ -split '\\s+')[-1] } "
                "| Where-Object { $_ -match '^[1-9][0-9]*$' } | Sort-Object -Unique; "
                "$todos = @(); "
                "foreach ($x in $ids) { "
                "  $todos += $x; "
                "  try { "
                "    $pai = (Get-CimInstance Win32_Process -Filter \"ProcessId=$x\" -EA SilentlyContinue).ParentProcessId; "
                "    if ($pai -and \"$pai\" -match '^[1-9][0-9]*$') { $todos += \"$pai\" } "
                "  } catch {} "
                "}; "
                "$mortos = @(); "
                "foreach ($x in ($todos | Sort-Object -Unique)) { "
                "  taskkill /PID $x /F /T 2>$null | Out-Null; "
                "  if ($LASTEXITCODE -eq 0) { $mortos += \"PID $x\" } "
                "}; "
                f"if ($mortos.Count -gt 0) {{ Write-Host '[hein] Encerrado:' ($mortos -join ', ') '(porta {porta})' }} "
                f"else {{ Write-Host '[hein] Porta {porta}: nenhum processo encontrado.' }}"
            )
        else:
            cmd = (
                f"_pids=$(lsof -ti :{porta} 2>/dev/null); "
                '[ -n "$_pids" ] && echo "$_pids" | xargs kill -15 2>/dev/null; '
                "sleep 0.3; "
                '[ -n "$_pids" ] && echo "$_pids" | xargs kill -9 2>/dev/null; '
                f"echo '[hein] Porta {porta} encerrada.'"
            )
        self.enviar_comando(cmd)

    def _matar_localhost_tudo(self) -> None:
        """Fallback: mata todas as portas de dev (sem rastreamento)."""
        portas = [3000, 4000, 4173, 5000, 5173, 8000, 8080]
        if IS_WINDOWS:
            linhas = ["$mortos = @()"]
            for p in portas:
                linhas.append(
                    f"$ids{p} = @(netstat -ano | Select-String ':{p} ') "
                    f"| ForEach-Object {{ ($_ -split '\\s+')[-1] }} "
                    f"| Where-Object {{ $_ -match '^[1-9][0-9]*$' }} "
                    f"| Sort-Object -Unique; "
                    f"foreach ($x in $ids{p}) {{ "
                    f"  taskkill /PID $x /F 2>$null | Out-Null; "
                    f"  if ($LASTEXITCODE -eq 0) {{ $mortos += 'PID ' + $x + ' (:{p})' }} "
                    f"}}"
                )
            linhas.append(
                "if ($mortos.Count -gt 0) { "
                "  Write-Host '[hein] Encerrados:' ($mortos -join ', ') "
                "} else { "
                "  Write-Host '[hein] Nenhum processo encontrado nas portas de dev.' "
                "}"
            )
            cmd = "; ".join(linhas)
        else:
            portas_str = " ".join(str(p) for p in portas)
            cmd = (
                f"for _p in {portas_str}; do "
                "_pids=$(lsof -ti :$_p 2>/dev/null); "
                '[ -n "$_pids" ] && echo "$_pids" | xargs kill -15 2>/dev/null; '
                'sleep 0.3; '
                '[ -n "$_pids" ] && echo "$_pids" | xargs kill -9 2>/dev/null '
                '&& echo "[hein] Porta $_p encerrada."; '
                "done; echo '[hein] Concluido.'"
            )
        self.enviar_comando(cmd)

    def _matar_localhost(self) -> None:
        """Compatibilidade: nao usado diretamente (menu via QToolButton)."""
        pass

    # ── Foco automático ao exibir a aba ────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.console.setFocus)

    # ── Busca no terminal (Ctrl+F) ─────────────────────────────────────────────

    def _toggle_busca(self):
        visivel = not self._barra_busca.isVisible()
        self._barra_busca.setVisible(visivel)
        if visivel:
            self._input_busca.setFocus()
            self._input_busca.selectAll()
        else:
            self.console.setFocus()

    def _buscar_proximo(self):
        self._buscar_no_terminal(False)

    def _buscar_anterior(self):
        self._buscar_no_terminal(True)

    def _buscar_no_terminal(self, backward: bool):
        from PySide6.QtGui import QTextDocument
        termo = self._input_busca.text()
        if not termo:
            self._lbl_busca_info.setText("")

            return

        flags = QTextDocument.FindFlag(0)
        if backward:
            flags |= QTextDocument.FindBackward
        found = self.console.find(termo, flags)
        if not found:
            # wrap-around: se for frente vai ao Start; se for trás vai ao End
            cur = self.console.textCursor()
            cur.movePosition(QTextCursor.Start if not backward else QTextCursor.End)
            self.console.setTextCursor(cur)
            found = self.console.find(termo, flags)
        self._lbl_busca_info.setText("" if found else "não encontrado")

    # ── Localiza arquivo no projeto ────────────────────────────────────────

    def _encontrar_arquivo_projeto(self, nome: str) -> str:
        """Busca <nome> dentro de self.project_path. Retorna caminho absoluto ou ''."""
        if not self.project_path or not os.path.exists(self.project_path):

            return ""

        # caminho absoluto direto
        if os.path.isabs(nome) and os.path.isfile(nome):

            return nome

        # relativo ao projeto
        cand = os.path.join(self.project_path, nome)
        if os.path.isfile(cand):

            return os.path.normpath(cand)

        # busca recursiva (máx 4 níveis, ignora pastas de sistema)
        _ignorar = {'.venv', '__pycache__', '.git', 'node_modules'}
        nome_low = nome.lower()
        for raiz, dirs, arqs in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in _ignorar]
            nivel   = raiz.replace(self.project_path, '').count(os.sep)
            if nivel >= 4:
                dirs.clear()
            for arq in arqs:
                if arq.lower() == nome_low:

                    return os.path.normpath(os.path.join(raiz, arq))

        return ""

    # ── Encoding sem projeto ──────────────────────────────────────────────

    def _setup_encoding_sem_projeto(self):
        """Configura encoding UTF-8 quando iniciado sem projeto."""
        if IS_WINDOWS:
            cmd = (
                "chcp 65001 | Out-Null; "
                "$OutputEncoding = [System.Text.Encoding]::UTF8; "
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
                "[Console]::InputEncoding  = [System.Text.Encoding]::UTF8; "
                'Write-Host "HEIN_SETUP_OK"'
            )
            self.process.write((cmd + "\r\n").encode("utf-8"))
        else:
            self.process.write(b"echo HEIN_SETUP_OK\n")

    def closeEvent(self, event): # Reset defensivo: garante que flags de supressão não fiquem travados
        self._suprimindo_setup           = False
        self._aguardando_prompt_natural  = False
        self._suprimindo_proximo_prompt  = False
        try:
            self.console.viewport().removeEventFilter(self)
            self.console.removeEventFilter(self)
        except RuntimeError:
            pass
        self.process.kill()
        event.accept()
