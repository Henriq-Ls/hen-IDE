# 📁 _TERMINAIS_/terminal_run.py
"""
_TERMINAIS_/terminal_run.py
Terminal de output para execução de código (Run), com suporte a input interativo.
Widget que mostra output do Python rodando e permite enviar entrada para o processo (stdin).
"""
import re, os
from PySide6.QtCore import QProcess, Qt, Signal, QTimer, QProcessEnvironment, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPlainTextEdit, QLabel, QPushButton, QToolTip, QApplication, QLineEdit
)
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor, QDesktopServices
from PySide6.QtCore import QEvent
_RE_TRACEBACK = re.compile(r'(?:File|Arquivo) "(.+?)", (?:line|linha) (\d+)')
_RE_URL       = re.compile(r'https?://[^\s)"\'>]+')
_RE_CAMINHO   = re.compile(r'[A-Za-z]:[/\\][^\s"\'<>|*?\r\n]+')
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import FONTE_MONO, COR_INFO, COR_SINTAXE_NUMERO
from _TRADUTION_.tradutor_erros import traduzir as _traduzir_erros
# Traduções adicionais para saída de help() / pydoc (não cobertas por _traduzir_erros)
_PYDOC_PT: list[tuple[str, str]] = [
    ("Help on built-in function",              "Ajuda sobre função embutida"),
    ("Help on built-in method",                "Ajuda sobre método embutido"),
    ("Help on function",                       "Ajuda sobre função"),
    ("Help on class",                          "Ajuda sobre classe"),
    ("Help on module",                         "Ajuda sobre módulo"),
    ("Help on package",                        "Ajuda sobre pacote"),
    ("Help on method",                         "Ajuda sobre método"),
    ("in module builtins:",                    "do módulo builtins:"),
    ("in module",                              "no módulo"),
    ("No documentation found for",             "Nenhuma documentação encontrada para"),
    ("Prints the values to a stream, or to sys.stdout by default.",
                                               "Imprime os valores para um fluxo ou para sys.stdout por padrão."),
    ("string inserted between values, default a space.",
                                               "string inserida entre os valores; padrão: espaço."),
    ("string appended after the last value, default a newline.",
                                               "string adicionada após o último valor; padrão: nova linha."),
    ("a file-like object (stream); defaults to the current sys.stdout.",
                                               "objeto tipo arquivo (stream); padrão: sys.stdout."),
    ("whether to forcibly flush the stream.",  "se o buffer do fluxo deve ser forçado a esvaziar."),
    ("Return None",                            "Retorna None"),
    ("Return True",                            "Retorna True"),
    ("Return False",                           "Retorna False"),
    ("Traceback (most recent call last):",     "Rastreamento (chamada mais recente por último):"),
]

def traduzir(texto: str) -> str:
    """Aplica _PYDOC_PT primeiro (frases completas) e depois _traduzir_erros (palavras)."""
    for en, pt in _PYDOC_PT:
        if en in texto:
            texto = texto.replace(en, pt)
    texto = _traduzir_erros(texto)

    return texto

from _UTILITARIOS_.icones import icone_tema
from _THREADS_.ciclo_vida import encerrar_processo

class RunOutputWidget(QWidget):
    """Widget para mostrar output do Run, com suporte a input interativo (stdin)."""
    navegar_para_erro        = Signal(str, int)   # arquivo, linha
    explorar_json_solicitado = Signal(str)         # texto JSON detectado
    processo_iniciado        = Signal(int)         # pid
    processo_terminou_sinal  = Signal(int)         # exit_code

    # ⚠️  função grande (135 linhas)
    def __init__(self):
        super().__init__()
        self._links_erro:    list[tuple[int, int, str, int]] = []
        self._links_url:     list[tuple[int, int, str]]       = []
        self._links_caminho: list[tuple[int, int, str]]       = []
        self._ultimo_json_detectado = ""
        self._arquivo_exec = ""
        self._cursor_override_ativo = False

        self.ui = QPlainTextEdit()
        self.ui.setReadOnly(False)
        self.ui.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.ui.installEventFilter(self)
        self.ui.viewport().installEventFilter(self)  # ContextMenu e links chegam aqui
        self._input_start = 0

        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self._ler_saida)
        self.process.readyReadStandardError.connect(self._ler_erro)
        self.process.finished.connect(self._processo_terminou)
        self.process.started.connect(self._ao_iniciar_processo)

        # --- Barra de controle ---
        self._barra_run = QWidget()
        self._barra_run.setFixedHeight(28)
        lay_run = QHBoxLayout(self._barra_run)
        lay_run.setContentsMargins(6, 0, 6, 0)
        lay_run.setSpacing(4)

        from _CONFIGURA_.gerenciador_perfil import obter_nome_usuario
        nome = obter_nome_usuario()
        self._lbl_barra_run = QLabel(f"  ·  hein  ·  {nome} | Rodando")
        self._lbl_barra_run.setStyleSheet("font-size:10px; color:#555555; background: transparent;")

        self._lbl_script = QLabel("")
        self._lbl_script.setStyleSheet("font-size:10px; color:#666; padding-left:6px;")

        _estilo_mini = (
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover { background: rgba(255,255,255,0.07); }"
        )

        self._btn_busca_run = QPushButton()
        self._btn_busca_run.setIcon(icone_tema("mdi.magnify"))
        self._btn_busca_run.setIconSize(QSize(14, 14))
        self._btn_busca_run.setFixedSize(22, 22)
        self._btn_busca_run.setToolTip("Buscar no output  (Ctrl+F)")
        self._btn_busca_run.setStyleSheet(_estilo_mini)
        self._btn_busca_run.clicked.connect(self._toggle_busca)

        self._btn_copiar_run = QPushButton()
        self._btn_copiar_run.setIcon(icone_tema("mdi.content-copy"))
        self._btn_copiar_run.setIconSize(QSize(14, 14))
        self._btn_copiar_run.setFixedSize(22, 22)
        self._btn_copiar_run.setToolTip("Copiar")
        self._btn_copiar_run.setStyleSheet(_estilo_mini)
        self._btn_copiar_run.clicked.connect(self._copiar_run)

        self._btn_limpar_run = QPushButton()
        self._btn_limpar_run.setIcon(icone_tema("mdi.delete-sweep"))
        self._btn_limpar_run.setIconSize(QSize(14, 14))
        self._btn_limpar_run.setFixedSize(22, 22)
        self._btn_limpar_run.setToolTip("Limpar")
        self._btn_limpar_run.setStyleSheet(_estilo_mini)
        self._btn_limpar_run.clicked.connect(self.clear)

        lay_run.addWidget(self._lbl_barra_run)
        lay_run.addWidget(self._lbl_script)
        lay_run.addStretch()
        lay_run.addWidget(self._btn_busca_run)
        lay_run.addWidget(self._btn_copiar_run)
        lay_run.addWidget(self._btn_limpar_run)

        # --- Barra de busca (Ctrl+F, oculta por padrão) ---
        self._barra_busca = QWidget()
        self._barra_busca.setFixedHeight(28)
        self._barra_busca.setVisible(False)
        _lay_busca = QHBoxLayout(self._barra_busca)
        _lay_busca.setContentsMargins(6, 2, 4, 2)
        _lay_busca.setSpacing(4)

        self._input_busca = QLineEdit()
        self._input_busca.setPlaceholderText("Buscar no output...")
        self._input_busca.setFixedHeight(20)
        self._input_busca.returnPressed.connect(self._buscar_proximo)
        _t         = tema_global()
        _inp_fundo = _t.cor("interface.inputs",           "#1e1e1e")
        _inp_texto = _t.cor("interface.texto",            "#cccccc")
        _inp_borda = _t.cor("interface.borda",            "#333333")
        _inp_foco  = _t.cor("interface.borda_foco",       "#569cd6")
        _inp_fraco = _t.cor("interface.texto_fraco",      "#666666")
        _inp_hover = _t.cor("interface.fundo_item_hover", "#2a2a2a")
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
        self._btn_busca_ant   = QPushButton("▲")
        self._btn_busca_prox  = QPushButton("▼")
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
        self._lbl_busca_info.setStyleSheet(f"color:{_inp_fraco}; font-size:9pt;")

        _lay_busca.addWidget(self._input_busca)
        _lay_busca.addWidget(self._btn_busca_ant)
        _lay_busca.addWidget(self._btn_busca_prox)
        _lay_busca.addWidget(self._lbl_busca_info)
        _lay_busca.addStretch()
        _lay_busca.addWidget(self._btn_fechar_busca)

        # --- Layout principal ---
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._barra_run)
        layout.addWidget(self._barra_busca)
        layout.addWidget(self.ui)

        # --- Barra JSON (rodapé) ---
        self._barra_json = QWidget()
        self._barra_json.setFixedHeight(28)
        self._barra_json.setVisible(False)

        lay_barra = QHBoxLayout(self._barra_json)
        lay_barra.setContentsMargins(8, 0, 8, 0)
        lay_barra.setSpacing(6)

        _icone = QLabel("{ }")
        _icone.setStyleSheet(
            "color:#e5c07b; font-family:Consolas; font-weight:bold;"
        )
        lay_barra.addWidget(_icone)

        self._lbl_json_info = QLabel("JSON detectado no output")
        self._lbl_json_info.setStyleSheet("font-size:11px; color:#888;")
        lay_barra.addWidget(self._lbl_json_info)
        lay_barra.addStretch()

        btn_explorar = QPushButton("Explorar")
        btn_explorar.setIcon(icone_tema("mdi.file-tree"))
        btn_explorar.setFixedHeight(22)
        btn_explorar.setStyleSheet("""
            QPushButton {
                background:#1a3a1a; color:#98c379;
                border:none; padding:2px 12px;
                font-size:10px; border-radius:3px;
            }
            QPushButton:hover { background:#264f78; }
        """)
        btn_explorar.clicked.connect(self._ao_explorar_json)
        lay_barra.addWidget(btn_explorar)

        layout.addWidget(self._barra_json)
        self.setLayout(layout)

        self._aplicar_tema()

    def _copiar_run(self):
        if self.ui.textCursor().hasSelection():
            self.ui.copy()
        else:
            self.ui.selectAll()
            self.ui.copy()

    # ---
    # Tema
    # ---

    def _aplicar_tema(self):
        t     = tema_global()
        fundo = t.cor("terminal_run.fundo",      "#000000")
        texto = t.cor("terminal_run.texto_saida","#e0e0e0")
        self.ui.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {fundo};
                color: {texto};
                font-family: '{FONTE_MONO}', 'Consolas', monospace;
                font-size: 11px;
                border: none;
            }}
        """)

    def atualizar_tema(self, tema: dict = None):
        self._aplicar_tema()

    # ---
    # Leitura de processo
    # ---

    def _ler_saida(self):
        out = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        out = traduzir(out)
        cor = tema_global().cor("terminal_run.texto_saida", "#e0e0e0")
        self._imprimir_com_links(out, cor)

    def _ler_erro(self):
        err = self.process.readAllStandardError().data().decode("utf-8", errors="replace")
        err = traduzir(err)
        cor_erro = tema_global().cor("terminal_run.texto_erro", "#e06c75")
        self._imprimir_com_links(f"\n[ERRO] {err}\n", cor_erro)

    def _imprimir_com_links(self, texto: str, cor: str):
        cursor   = self.ui.textCursor()
        fmt_norm = QTextCharFormat()
        fmt_norm.setForeground(QColor(cor))
        fmt_link = QTextCharFormat()
        fmt_link.setForeground(tema_global().qcolor("editor.info", COR_INFO))
        fmt_link.setFontUnderline(True)
        fmt_url = QTextCharFormat()
        fmt_url.setForeground(tema_global().qcolor("terminal_run.link_url", COR_INFO))
        fmt_url.setFontUnderline(True)
        fmt_caminho = QTextCharFormat()
        fmt_caminho.setForeground(tema_global().qcolor("terminal_run.link_caminho", COR_SINTAXE_NUMERO))
        fmt_caminho.setFontUnderline(True)
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Coleta todos os matches (traceback + URL + caminho) em ordem de posicao
        matches = [("tb", m) for m in _RE_TRACEBACK.finditer(texto)]
        matches += [("url", m) for m in _RE_URL.finditer(texto)]
        matches += [("caminho", m) for m in _RE_CAMINHO.finditer(texto)]
        matches.sort(key=lambda x: x[1].start())

        ultimo = 0
        for tipo, m in matches:
            if m.start() < ultimo:
                continue
            cursor.insertText(texto[ultimo:m.start()], fmt_norm)
            ini = cursor.position()
            if tipo == "tb":
                cursor.insertText(m.group(0), fmt_link)
                fim = cursor.position()
                self._links_erro.append((ini, fim, m.group(1), int(m.group(2))))
            elif tipo == "url":
                cursor.insertText(m.group(0), fmt_url)
                fim = cursor.position()
                self._links_url.append((ini, fim, m.group(0)))
            else:
                cursor.insertText(m.group(0), fmt_caminho)
                fim = cursor.position()
                self._links_caminho.append((ini, fim, m.group(0)))
            ultimo = m.end()

        cursor.insertText(texto[ultimo:], fmt_norm)
        self.ui.setTextCursor(cursor)
        self.ui.verticalScrollBar().setValue(
            self.ui.verticalScrollBar().maximum()
        )
        self._input_start = self.ui.textCursor().position()
        QTimer.singleShot(0, self._verificar_json)

    def _processo_terminou(self, exit_code, exit_status):
        self.processo_terminou_sinal.emit(exit_code)
        t   = tema_global()
        sep = t.cor("terminal_run.texto_separador", "#555555")
        cor = (t.cor("terminal_run.texto_sucesso", "#4ec994")
               if exit_code == 0
               else t.cor("terminal_run.texto_erro", "#e06c75"))
        self._imprimir_colorido(
            f"\n{'---' * 30}Concluído com código {exit_code}\n", sep
        )
        self._imprimir_colorido(f"[{'OK' if exit_code == 0 else 'FALHA'}]\n", cor )

    # ---
    # Impressão  ----- PONTO CENTRAL --- cuidado aqui
    # ---

    def _imprimir(self, texto: str):
        cursor = self.ui.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(texto)
        self.ui.setTextCursor(cursor)
        self.ui.verticalScrollBar().setValue(
            self.ui.verticalScrollBar().maximum()
        )
        self._input_start = self.ui.textCursor().position()
        QTimer.singleShot(0, self._verificar_json)

    def append_output(self, texto: str) -> None:
        """API públic para escrever uma linha no terminal.
        Adiciona '\\n' ao final -- use quando alimentando saída de ProcessoThread
        (que emite linhas via rstrip, sem '\\n')."""
        self._imprimir(texto + "\n")

    def _verificar_json(self):
        """Analisa o output completo procurando JSON. Roda fora do ciclo de impressão."""
        from _TERMINAIS_.json_explorer import _extrair_json_do_output
        texto_completo = self.ui.toPlainText()
        dados, trecho  = _extrair_json_do_output(texto_completo)

        if dados is None:
            if self._barra_json.isVisible():
                self._barra_json.setVisible(False)
                self._ultimo_json_detectado = ""

            return

        if trecho == self._ultimo_json_detectado:

            return

        self._ultimo_json_detectado = trecho
        tipo = type(dados).__name__
        self._lbl_json_info.setText(f"JSON detectado  ---  {tipo}")
        self._barra_json.setVisible(True)

    def _ao_explorar_json(self):
        if self._ultimo_json_detectado:
            self.explorar_json_solicitado.emit(self._ultimo_json_detectado)

    def _imprimir_colorido(self, texto: str, cor: str):
        cursor = self.ui.textCursor()
        fmt    = QTextCharFormat()
        fmt.setForeground(QColor(cor))
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(texto, fmt)
        self.ui.setTextCursor(cursor)
        self.ui.verticalScrollBar().setValue(
            self.ui.verticalScrollBar().maximum()
        )
        self._input_start = self.ui.textCursor().position()

    def imprimir_info(self, texto: str):
        cor = tema_global().cor("terminal_run.texto_info", "#61afef")
        self._imprimir_colorido(texto, cor)

    def imprimir_aviso(self, texto: str):
        cor = tema_global().cor("terminal_run.texto_aviso", "#e5c07b")
        self._imprimir_colorido(f"[AVISO] {texto}", cor)

    def imprimir_separador(self, titulo: str = ""):
        cor = tema_global().cor("terminal_run.texto_separador", "#555555")
        linha = f"\n--- {titulo} ---\n" if titulo else f"\n{'---' * 40}\n"
        self._imprimir_colorido(linha, cor)

    # ---
    # Input interativo (stdin)
    # ---

    def _tratar_tecla(self, event) -> bool:
        cursor = self.ui.textCursor()
        key    = event.key()

        if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down,
                   Qt.Key_Home, Qt.Key_End, Qt.Key_PageUp, Qt.Key_PageDown):

            return False

        if cursor.position() < self._input_start or cursor.selectionStart() < self._input_start:
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.ui.setTextCursor(cursor)

            if key in (Qt.Key_Backspace, Qt.Key_Delete):

                return True

        if key in (Qt.Key_Return, Qt.Key_Enter):
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.setPosition(self._input_start, QTextCursor.MoveMode.KeepAnchor)
            texto_digitado = cursor.selectedText()
            texto_digitado = texto_digitado.replace('\u2029', '\n')

            if self.process.state() == QProcess.ProcessState.Running:
                self.process.write((texto_digitado + "\n").encode("utf-8"))

            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText("\n")
            self.ui.setTextCursor(cursor)
            self._input_start = cursor.position()

            return True

        if key == Qt.Key_Backspace:
            cursor.movePosition(QTextCursor.MoveOperation.End)
            if cursor.position() <= self._input_start:

                return True

            return False

        if key == Qt.Key_C and (event.modifiers() & Qt.ControlModifier):
            if not cursor.hasSelection() and self.process.state() == QProcess.ProcessState.Running:
                self.process.kill()

                return True

            return False

        return False

    # ---
    # API pública
    # ---

    def _ao_iniciar_processo(self):
        self.processo_iniciado.emit(self.process.processId())

    # ---
    # Resolucao de executor por extensao
    # ---

    def _resolver_executor(self, arquivo: str, python_path: str = "") -> tuple:
        """Retorna (programa, args_prefixo) conforme a extensao do arquivo."""
        import sys
        import platform
        ext = os.path.splitext(arquivo)[1].lower()

        if ext == ".ps1":

            return ("powershell.exe", ["-ExecutionPolicy", "Bypass", "-File"])

        if ext in (".bat", ".cmd"):

            return ("cmd.exe", ["/c"])

        if ext == ".sh":
            shell = "bash" if platform.system() != "Darwin" else "zsh"

            return (shell, [])

        py = (python_path
              if python_path and os.path.isfile(python_path)
              else sys.executable)

        return (py, ["-u"])

    def _reexecutar(self):
        if not self._arquivo_exec:

            return

        if self.process.state() != QProcess.ProcessState.NotRunning:
            encerrar_processo(self.process, 2000)
        self.clear()
        self.imprimir_separador(os.path.basename(self._arquivo_exec))
        self.process.start(self._executor_prog, self._executor_prefixo + [self._arquivo_exec])

    def executar_python(self, arquivo_codigo: str, python_path: str = ""):
        self._arquivo_exec = arquivo_codigo
        prog, prefixo = self._resolver_executor(arquivo_codigo, python_path)
        self._executor_prog    = prog
        self._executor_prefixo = prefixo
        self._lbl_script.setText(os.path.basename(arquivo_codigo))

        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        self.process.setProcessEnvironment(env)

        if self.process.state() != QProcess.ProcessState.NotRunning:
            encerrar_processo(self.process, 2000)
        self.process.start(prog, prefixo + [arquivo_codigo])

    def executar_comando(self, cmd: str, cwd: str | None = None) -> None:
        """Executa um comando shell arbitrário no terminal.

        Usado por HEIN-RUN para rodar comandos da IA sem poluir o chat.
        Suporta qualquer comando sh/bash (Linux/Mac) ou cmd.exe (Windows).
        """
        import platform
        self._arquivo_exec = ""
        self._lbl_script.setText((cmd[:60] + "…") if len(cmd) > 60 else cmd)

        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        self.process.setProcessEnvironment(env)

        if cwd:
            self.process.setWorkingDirectory(str(cwd))

        if self.process.state() != QProcess.ProcessState.NotRunning:
            encerrar_processo(self.process, 2000)

        if platform.system() == "Windows":
            self._executor_prog    = "cmd.exe"
            self._executor_prefixo = ["/c"]
        else:
            self._executor_prog    = "sh"
            self._executor_prefixo = ["-c"]

        self.process.start(self._executor_prog, self._executor_prefixo + [cmd])

    def executar_pwsh(self, cmd: str, cwd: str | None = None) -> None:
        """Executa um comando PowerShell no terminal.

        Usado por HEIN-PWSH para scripts de servidor, automações e PS1.
        Tenta pwsh (PowerShell Core, cross-platform) antes do powershell.exe.
        """
        import shutil
        self._arquivo_exec = ""
        self._lbl_script.setText((cmd[:60] + "…") if len(cmd) > 60 else cmd)

        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        self.process.setProcessEnvironment(env)

        if cwd:
            self.process.setWorkingDirectory(str(cwd))

        if self.process.state() != QProcess.ProcessState.NotRunning:
            encerrar_processo(self.process, 2000)

        pwsh = (shutil.which("pwsh")
                or shutil.which("powershell")
                or "powershell.exe")
        self._executor_prog    = pwsh
        self._executor_prefixo = ["-NoProfile", "-Command"]

        self.process.start(self._executor_prog, self._executor_prefixo + [cmd])

    def clear(self):
        self.ui.clear()
        self._links_erro.clear()
        self._links_url.clear()
        self._links_caminho.clear()
        self._barra_json.setVisible(False)
        self._ultimo_json_detectado = ""
        self._input_start = 0

    def _mostrar_menu_contexto(self, pos_global):
        from _UTILITARIOS_.hein_context_menu import heinContextMenu
        from PySide6.QtWidgets import QApplication
        tem_sel    = self.ui.textCursor().hasSelection()
        em_execucao = self.process.state() == QProcess.ProcessState.Running

        def _colar():
            texto = QApplication.clipboard().text()
            if texto:
                cursor = self.ui.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.ui.setTextCursor(cursor)
                cursor.insertText(texto)

        def _interromper():
            self.process.kill()

        itens = [
            ("Copiar",          "mdi.content-copy",     self.ui.copy),
            ("Colar",           "mdi.content-paste",    _colar),
            None,
            ("Selecionar Tudo", "mdi.select-all",       self.ui.selectAll),
            None,
            ("Limpar",          "mdi.delete-sweep",     self.clear),
            ("Interromper",     "mdi.stop-circle-outline", _interromper),
        ]

        menu = heinContextMenu(parent=self, itens=itens)
        menu.acao("Copiar").setEnabled(tem_sel)
        menu.acao("Interromper").setEnabled(em_execucao)
        menu.exec(pos_global)

    # ⚠️  função grande (93 linhas)
    def eventFilter(self, obj, event):
        viewport = self.ui.viewport()

        if obj is viewport:
            # navegação por link --- clique esquerdo no link de erro
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
                pos_cursor = self.ui.cursorForPosition(event.pos()).position()
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

            # menu de contexto em português
            if event.type() == QEvent.Type.MouseMove:
                ctrl = bool(event.modifiers() & Qt.ControlModifier)
                pos_cursor = self.ui.cursorForPosition(event.pos()).position()
                sobre_link = False
                for ini, fim, arquivo, linha in self._links_erro:
                    if ini <= pos_cursor <= fim:
                        sobre_link = True
                        nome = os.path.basename(arquivo)
                        dica = f"{nome}  \u2014  linha {linha}\n{arquivo}"
                        if ctrl: dica += "\n\u2192 Ctrl+Click: abrir no editor"
                        QToolTip.showText(event.globalPos(), dica, self.ui.viewport())
                        break
                if not sobre_link:
                    for ini, fim, url in self._links_url:
                        if ini <= pos_cursor <= fim:
                            sobre_link = True
                            dica = url + ("\n\u2192 Ctrl+Click: abrir navegador" if ctrl else "")
                            QToolTip.showText(event.globalPos(), dica, self.ui.viewport())
                            break
                if not sobre_link:
                    for ini, fim, _caminho in self._links_caminho:
                        if ini <= pos_cursor <= fim:
                            _p = os.path.normpath(_caminho)
                            if os.path.exists(_p):
                                sobre_link = True
                                if os.path.isdir(_p):
                                    acao = "\u2192 Ctrl+Click: abrir no Explorer" if ctrl else "Abrir pasta"
                                    dica = f"{acao}\n{_p}"
                                else:
                                    acao = "\u2192 Ctrl+Click: abrir no editor" if ctrl else os.path.basename(_p)
                                    dica = f"{acao}\n{_p}"
                                QToolTip.showText(event.globalPos(), dica, self.ui.viewport())
                            break
                if sobre_link:
                    if not self._cursor_override_ativo:
                        QApplication.setOverrideCursor(Qt.CursorShape.PointingHandCursor)
                        self._cursor_override_ativo = True
                else:
                    if self._cursor_override_ativo:
                        QApplication.restoreOverrideCursor()
                        self._cursor_override_ativo = False
                    QToolTip.hideText()

                return False

            if event.type() == QEvent.Type.Leave:
                if self._cursor_override_ativo:
                    QApplication.restoreOverrideCursor()
                    self._cursor_override_ativo = False
                QToolTip.hideText()

            if event.type() == QEvent.Type.ContextMenu:
                self._mostrar_menu_contexto(event.globalPos())

                return True

        if obj is self.ui:
            # Bloqueia Ctrl+F global e abre busca local
            if event.type() == QEvent.Type.ShortcutOverride:
                if event.key() == Qt.Key.Key_F and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                    event.accept()
                    return True
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_F and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                    self._toggle_busca()
                    return True
                if event.key() == Qt.Key.Key_Escape and self._barra_busca.isVisible():
                    self._barra_busca.setVisible(False)
                    self.ui.setFocus()
                    return True
                return self._tratar_tecla(event)

        return super().eventFilter(obj, event)

    def escrever(self, texto: str):
        self._imprimir(texto)

    def append_output(self, texto: str):
        self._imprimir(texto)

    # ── Busca no output (Ctrl+F) ───────────────────────────────────────────

    def _toggle_busca(self):
        visivel = not self._barra_busca.isVisible()
        self._barra_busca.setVisible(visivel)
        if visivel:
            self._input_busca.setFocus()
            self._input_busca.selectAll()
        else:
            self.ui.setFocus()

    def _buscar_proximo(self):
        self._buscar_no_output(False)

    def _buscar_anterior(self):
        self._buscar_no_output(True)

    def _buscar_no_output(self, backward: bool):
        from PySide6.QtGui import QTextDocument
        termo = self._input_busca.text()
        if not termo:
            self._lbl_busca_info.setText("")
            return
        flags = QTextDocument.FindFlag(0)
        if backward:
            flags |= QTextDocument.FindBackward
        found = self.ui.find(termo, flags)
        if not found:
            cur = self.ui.textCursor()
            cur.movePosition(QTextCursor.MoveOperation.Start if not backward else QTextCursor.MoveOperation.End)
            self.ui.setTextCursor(cur)
            found = self.ui.find(termo, flags)
        self._lbl_busca_info.setText("" if found else "não encontrado")
