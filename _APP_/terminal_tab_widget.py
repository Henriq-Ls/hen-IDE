# 📁 _APP_/terminal_tab_widget.py

"""Gerencia as abas de terminal da IDE hein."""

from _UTILITARIOS_.icones import icone_tema
from PySide6.QtCore import QProcess, Qt, Signal, QSize, QRect, QPointF
from PySide6.QtGui import QPainter, QColor, QPainterPath, QPen
from PySide6.QtWidgets import QTabWidget, QTabBar, QWidget, QHBoxLayout, QPushButton, QFrame, QStyleOptionTab, QStyle
from _TERMINAIS_ import Power_Shwell, Run_Out
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import (COR_BTN_ICONE_BG_qta, COR_BTN_ICONE_TEXTO_qta,
    BORDA_GERAL, FUNDO_PAINEL, BordaOverlay, BordaCompleta,

)

from _LOG_.painel_logs import PainelLogs
from _THREADS_.ciclo_vida import encerrar_processo

class TerminalTabBar(QTabBar):
    """TabBar customizada com o mesmo formato das AbaWidget da BarraTitulo:
    cantos superiores arredondados + pés em S, e borda inferior na cor do tema."""

    H = 28
    @classmethod
    def _padding_h(cls) -> int:
        """Lê padding_aba_h do JSON de configuração (fallback: 12)."""
        try:
            from _CONFIGURA_.gerenciador_configurar import config_global
            return int(config_global().obter("ui", "padding_aba_h", 12))
        except Exception:
            return 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setExpanding(False)
        self.setFixedHeight(self.H)

        self._borda_cor    = BORDA_GERAL
        self._borda_larg   = 0
        self._borda_estilo = "solid"

    def tabSizeHint(self, index):
        fm = self.fontMetrics()
        texto = self.tabText(index)
        largura_texto = fm.horizontalAdvance(texto)

        f = 8
        icone_w = 14 + 6 if not self.tabIcon(index).isNull() else 0

        botao_w = 22
        btn_esq_w = 26   # play/stop
        padding_lateral = self._padding_h()

        largura = padding_lateral + btn_esq_w + 6 + largura_texto + botao_w + padding_lateral

        return QSize(max(largura, 90), self.H)

    def _caminho(self, rect: QRect):
        """Retângulo com cantos superiores arredondados e pés em S (tipo aba de navegador)."""

        w, h = rect.width(), rect.height()
        r = 4
        f = 8
        path = QPainterPath()
        path.moveTo(0, h)
        path.cubicTo(f * 0.5, h, f, h - f * 0.5, f, h - f)
        path.lineTo(f, r)
        path.quadTo(f, 0, f + r, 0)
        path.lineTo(w - f - r, 0)

        path.quadTo(w - f, 0, w - f, r)
        path.lineTo(w - f, h - f)
        path.cubicTo(w - f, h - f * 0.5, w - f * 0.5, h, w, h)
        path.closeSubpath()
        path.translate(rect.topLeft())

        return path

    def _caminho_borda(self, rect: QRect):
        """Mesmo contorno de _caminho mas sem fechar (open path) — só topo e laterais."""
        w, h = rect.width(), rect.height()
        r = 4
        f = 8
        path = QPainterPath()
        path.moveTo(0, h)

        path.cubicTo(f * 0.5, h, f, h - f * 0.5, f, h - f)

        path.lineTo(f, r)

        path.quadTo(f, 0, f + r, 0)

        path.lineTo(w - f - r, 0)

        path.quadTo(w - f, 0, w - f, r)

        path.lineTo(w - f, h - f)

        path.cubicTo(w - f, h - f * 0.5, w - f * 0.5, h, w, h)

        path.translate(rect.topLeft())

        return path

    # ⚠️  função grande (55 linhas)

    def paintEvent(self, event):
        t = tema_global()

        cor_borda = t.cor("interface.fundo_aba_ativa", BORDA_GERAL)

        cor_fundo_ativa   = t.cor("interface.fundo_aba_ativa",   "#1a1f2e")

        cor_fundo_inativa = t.cor("interface.fundo_aba_inativa", "#1b242d")

        cor_texto_ativo   = t.cor("interface.texto", "#e0e0e0")

        cor_texto_inativo = t.cor("interface.texto_fraco", "#666666")

        painter = QPainter(self)

        painter.setRenderHint(QPainter.Antialiasing)

        painter.fillRect(self.rect(), QColor(t.cor("interface.fundo", FUNDO_PAINEL)))

        # linha base padrão (quando não há BordaCompleta ativa)

        if not self._borda_larg:
            pen = QPen(QColor(cor_borda), 2)

            painter.setPen(pen)

            largura_total = self.parentWidget().width() if self.parentWidget() else self.width()

            painter.drawLine(0, self.height() - 1, largura_total, self.height() - 1)

        # ── fills e texto das abas ─────────────────────────────────────────────────

        for i in range(self.count()):
            rect = self.tabRect(i)

            ativo = i == self.currentIndex()

            if ativo:
                painter.fillPath(self._caminho(rect), QColor(cor_fundo_ativa))

            else:
                painter.fillPath(self._caminho(rect), QColor(cor_fundo_inativa))

            painter.setPen(QColor(cor_texto_ativo if ativo else cor_texto_inativo))

            icone = self.tabIcon(i)

            texto = self.tabText(i)

            x = rect.left() + self._padding_h() + 20   # padding + botão esquerdo(20)

            texto_rect = QRect(x, rect.top(), rect.right() - x - 26, rect.height())

            painter.drawText(texto_rect, Qt.AlignVCenter | Qt.AlignLeft, texto)

        painter.end()

        f = 8

        for i in range(self.count()):
            rect = self.tabRect(i)

            btn_esq = self.tabButton(i, QTabBar.LeftSide)

            if btn_esq:
                bw, bh = btn_esq.width(), btn_esq.height()

                btn_esq.move(rect.left() + f, rect.center().y() - bh // 2)

            btn_dir = self.tabButton(i, QTabBar.RightSide)

            if btn_dir:
                bw, bh = btn_dir.width(), btn_dir.height()

                # X fica logo após o texto (mesma origem que drawText usa)

                _fm = self.fontMetrics()

                _x_texto = rect.left() + self._padding_h() + 20  # igual ao x do drawText

                _x_apos = _x_texto + _fm.horizontalAdvance(self.tabText(i))

                btn_dir.move(_x_apos + 6, rect.center().y() - bh // 2)

class _CantoWidget(QWidget):
    """Corner widget que também desenha a linha inferior da tab bar."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAttribute(Qt.WA_StyledBackground, True)

        self.setStyleSheet("_CantoWidget { background: transparent; }")

    def paintEvent(self, event):
        super().paintEvent(event)

        t = tema_global()

        cor = t.cor("interface.fundo_aba_ativa", BORDA_GERAL)

        painter = QPainter(self)

        pen = QPen(QColor(cor), 2)

        painter.setPen(pen)

        y = TerminalTabBar.H - 1

        painter.drawLine(0, y, self.width(), y)

        painter.end()

class TerminalTabWidget(QTabWidget):
    executar_solicitado          = Signal()

    contexto_terminal_solicitado = Signal(str, str)

    navegar_para_erro            = Signal(str, int)
    abrir_arquivo_solicitado     = Signal(str)

    debug_solicitado             = Signal()

    aba_vai_fechar               = Signal(object)

    # ⚠️  except genérico vazio

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setTabBar(TerminalTabBar(self))

        self.setDocumentMode(True)

        self.setStyleSheet("QTabWidget::pane { border: none; }")

        self.setTabsClosable(True)

        self.tabCloseRequested.connect(self.fechar_aba)

        self.terminais: dict[int, object] = {}

        self._contador_ps = 0

        self._run_btns: dict[int, QPushButton] = {}

        self._setup_botoes_canto()

        self._atualizar_icones()

        self.abrir_aba_log()

        # log_print -> foca a aba Saida automaticamente quando o nucleo emite algo

        try:
            from _UTILITARIOS_.log_print import log_print
            log_print.pedido_foco.connect(self.abrir_aba_log)

        except Exception:
            pass

        self._linha_borda = QFrame(self)

        self._linha_borda.setFrameShape(QFrame.NoFrame)

        self._linha_borda.setFixedHeight(2)

        self._linha_borda.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._linha_borda.setAttribute(Qt.WA_StyledBackground, True)

        self._atualizar_linha_borda()

        def _obter_tab_terminal():
            from PySide6.QtCore import QRect
            bar = self.tabBar()

            idx = bar.currentIndex()

            if not (0 <= idx < bar.count()):
                return None

            tr = bar.tabRect(idx)

            tl = bar.mapTo(self, tr.topLeft())

            return QRect(tl.x(), tl.y(), tr.width(), tr.height())

        self._borda_overlay = BordaOverlay.criar(self)   # mantido para retrocompatibilidade

        self._borda_completa = BordaCompleta.criar(self, _obter_tab_terminal)




    # ⚠️  função grande (96 linhas)

    def _setup_botoes_canto(self):
        canto = _CantoWidget()

        layout = QHBoxLayout(canto)

        layout.setContentsMargins(4, 0, 34, 0)

        layout.setSpacing(4)

        canto.setFixedHeight(24)

        def _estilo_btn_id(obj_name: str) -> str:
            return f"""

                QPushButton#{obj_name} {{

                    background: transparent;

                    border: none;

                }}

                QPushButton#{obj_name}:hover {{

                    background: {COR_BTN_ICONE_BG_qta};

                }}

            """

        self._btn_run = QPushButton()

        self._btn_run.setObjectName("ttw_btn_run")

        self._btn_run.setStyleSheet(_estilo_btn_id("ttw_btn_run"))

        self._btn_run.setIconSize(QSize(16, 16))

        self._btn_run.setToolTip("Executar (F1)")

        self._btn_run.setFixedSize(24, 24)

        self._btn_run.clicked.connect(self.executar_solicitado)

        self._btn_stop_canto = QPushButton()

        self._btn_stop_canto.setObjectName("ttw_btn_stop")

        self._btn_stop_canto.setStyleSheet(_estilo_btn_id("ttw_btn_stop"))

        self._btn_stop_canto.setIconSize(QSize(16, 16))

        self._btn_stop_canto.setToolTip("Parar execução")

        self._btn_stop_canto.setFixedSize(24, 24)

        self._btn_stop_canto.setVisible(False)

        self._btn_stop_canto.clicked.connect(self._parar_run_ativo)

        self._btn_terminal = QPushButton()

        self._btn_terminal.setObjectName("ttw_btn_terminal")

        self._btn_terminal.setStyleSheet(_estilo_btn_id("ttw_btn_terminal"))

        self._btn_terminal.setIconSize(QSize(16, 16))

        self._btn_terminal.setToolTip("Novo Terminal")

        self._btn_terminal.setFixedSize(24, 24)

        self._btn_terminal.clicked.connect(lambda: self.add_new_terminal(modo="powershell"))

        self._btn_debug = QPushButton()

        self._btn_debug.setObjectName("ttw_btn_debug")

        self._btn_debug.setStyleSheet(_estilo_btn_id("ttw_btn_debug"))

        self._btn_debug.setIconSize(QSize(16, 16))

        self._btn_debug.setToolTip("Iniciar Depurador")

        self._btn_debug.setFixedSize(24, 24)

        self._btn_debug.clicked.connect(self.debug_solicitado)

        self._btn_json = QPushButton()

        self._btn_json.setObjectName("ttw_btn_json")

        self._btn_json.setStyleSheet(_estilo_btn_id("ttw_btn_json"))

        self._btn_json.setIconSize(QSize(16, 16))

        self._btn_json.setToolTip("Explorar JSON do terminal")

        self._btn_json.setFixedSize(24, 24)

        self._btn_json.clicked.connect(self._explorar_json_terminal_ativo)



        self._btn_pacotes = QPushButton()

        self._btn_pacotes.setObjectName("ttw_btn_pacotes")

        self._btn_pacotes.setStyleSheet(_estilo_btn_id("ttw_btn_pacotes"))

        self._btn_pacotes.setIconSize(QSize(16, 16))

        self._btn_pacotes.setToolTip("Gerenciador de Pacotes")

        self._btn_pacotes.setFixedSize(24, 24)

        self._btn_pacotes.clicked.connect(self.abrir_aba_pacotes)



        layout.addWidget(self._btn_run)

        layout.addWidget(self._btn_terminal)

        layout.addWidget(self._btn_debug)

        layout.addWidget(self._btn_json)


        layout.addWidget(self._btn_pacotes)


        canto.setFixedWidth(240)    # 7 botões × 24 px + espaçamento + margem direita

        self.setCornerWidget(canto, Qt.TopRightCorner)

    def _atualizar_icones(self): # recria todos os ícones com a cor atual do thema.json
        self._btn_run.setIcon(icone_tema("mdi.play"))

        self._btn_terminal.setIcon(icone_tema("mdi.console"))

        self._btn_debug.setIcon(icone_tema("mdi.bug"))

        self._btn_json.setIcon(icone_tema("mdi.code-braces"))



        self._btn_pacotes.setIcon(icone_tema("mdi.cube-outline"))


        # atualiza ícones das abas já abertas — novas já pegam a cor via add_new_terminal()

        from _LOG_.painel_logs import PainelLogs
        from _UTILITARIOS_.gerenciador_pacotes import GerenciadorPacotes
        for i in range(self.count()):
            w = self.widget(i)

            if isinstance(w, PainelLogs):
                self.setTabIcon(i, icone_tema("mdi6.history"))

            elif isinstance(w, GerenciadorPacotes):
                self.setTabIcon(i, icone_tema("mdi.cube-outline"))

            elif isinstance(w, Run_Out):
                self.setTabIcon(i, icone_tema("mdi.play"))

            else:
                from _BUSCA_.painel_busca_global import PainelBuscaGlobal
                if isinstance(w, PainelBuscaGlobal):
                    self.setTabIcon(i, icone_tema("mdi.magnify"))
                else:  # Power_Shwell
                    self.setTabIcon(i, icone_tema("mdi.console"))

    def atualizar_tema(self, tema=None):
        self._atualizar_linha_borda()

        self._atualizar_icones()

        if hasattr(self, "_borda_overlay") and self._borda_overlay is not None:
            _tb_h = self.tabBar().height()

            self._borda_overlay.setGeometry(0, _tb_h, self.width(), max(0, self.height() - _tb_h))

            self._borda_overlay.raise_()

    def abrir_aba_pacotes(self) -> None:
        """Abre (ou foca) a aba Pacotes no terminal."""

        from _UTILITARIOS_.gerenciador_pacotes import GerenciadorPacotes
        for i in range(self.count()):
            if isinstance(self.widget(i), GerenciadorPacotes):
                self.widget(i).atualizar()

                self.setCurrentIndex(i)

                return

        painel = GerenciadorPacotes()

        janela = self.window()

        projeto = getattr(janela, "current_project_path", None) or ""

        painel.set_projeto(projeto)

        icone = icone_tema("mdi.cube-outline")

        idx   = self.addTab(painel, icone, "Pacotes")

        self.setCurrentIndex(idx)

    def abrir_aba_busca_global(self, painel) -> None:
        """Abre (ou foca) a aba Busca no Projeto no terminal.

        Padrão idêntico ao de abrir_aba_pacotes: se já existir uma aba com
        PainelBuscaGlobal, foca ela; caso contrário adiciona como nova aba.
        O painel é um singleton criado na MainWindow — não é recriado aqui.
        """
        from _BUSCA_.painel_busca_global import PainelBuscaGlobal
        for i in range(self.count()):
            if isinstance(self.widget(i), PainelBuscaGlobal):
                self.setCurrentIndex(i)
                return

        icone = icone_tema("mdi.magnify")
        idx   = self.addTab(painel, icone, "Busca no Projeto")
        self.setCurrentIndex(idx)

    def set_project_path_pacotes(self, caminho: str) -> None:
        """Atualiza o project_path na aba Pacotes, se aberta."""

        from _UTILITARIOS_.gerenciador_pacotes import GerenciadorPacotes
        for i in range(self.count()):
            if isinstance(self.widget(i), GerenciadorPacotes):
                self.widget(i).set_projeto(caminho)

                break

    def abrir_aba_pip(self, titulo: str):
        """Abre nova aba de log pip/migração — sem diálogo. Retorna AbaLogPip."""

        from _TERMINAIS_.aba_log_pip import AbaLogPip
        aba = AbaLogPip()

        icone = icone_tema("mdi.package-variant")

        idx   = self.addTab(aba, icone, titulo)

        self.setCurrentIndex(idx)

        return aba



    # ── Helpers ───────────────────────────────────────────────────────

    def _copiar_terminal_ativo(self):
        from _LOG_.painel_logs import PainelLogs
        widget_aba = self.currentWidget()

        if isinstance(widget_aba, PainelLogs):
            widget_aba._copiar_tudo()

            return

        terminal = self.terminal_ativo()

        if not terminal:
            return

        widget = getattr(terminal, "console", None) or getattr(terminal, "ui", None)

        if not widget:
            return

        widget.setFocus()

        tem_sel = hasattr(widget, "textCursor") and widget.textCursor().hasSelection()

        if not tem_sel:
            widget.selectAll()

            widget.copy()

            cursor = widget.textCursor()

    def _limpar_ativo(self):
        terminal = self.terminal_ativo()

        if not terminal:
            return

        if hasattr(terminal, "clear_terminal"):
            terminal.clear_terminal()

        elif hasattr(terminal, "clear"):
            terminal.clear()

    def _enviar_para_ia(self):
        terminal = self.terminal_ativo()

        if not terminal:
            return

        widget = getattr(terminal, "console", None) or getattr(terminal, "ui", None)

        if not widget:
            return

        cursor = widget.textCursor() if hasattr(widget, "textCursor") else None

        if cursor and cursor.hasSelection():
            conteudo = cursor.selectedText().replace('\u2029', '\n')

        else:
            conteudo = widget.toPlainText() if hasattr(widget, "toPlainText") else ""

        if not conteudo.strip():
            return

        origem = self.tabText(self.currentIndex())

        self.contexto_terminal_solicitado.emit(conteudo.strip(), origem)

    def _abrir_json_explorer(self, texto: str):
        from _TERMINAIS_.json_explorer import JsonExplorer
        for i in range(self.count()):
            if isinstance(self.widget(i), JsonExplorer):
                explorer = self.widget(i)

                explorer.carregar(texto)

                self.setCurrentIndex(i)

                return

        explorer = JsonExplorer()

        explorer.carregar(texto)

        janela = self.window()

        if hasattr(janela, "tabs"):
            explorer.abrir_no_editor.connect(

                lambda codigo: janela.tabs.add_new_tab_com_conteudo(codigo, "json_code.py")

            )

        nome_aba = " JSON"

        if hasattr(janela, "tabs"):
            editor = None

            for i in range(janela.tabs.count()):
                e = janela.tabs.editores.get(i)

                if e and e.toPlainText().strip():
                    editor = e

                    break

            if editor and getattr(editor, "file_path", None):
                import os
                nome_aba = os.path.basename(editor.file_path)

        icone = icone_tema("mdi.code-braces")

        idx   = self.addTab(explorer, icone, nome_aba)

        self.setCurrentIndex(idx)

    def _explorar_json_terminal_ativo(self):
        from _TERMINAIS_ import Run_Out
        terminal = self.terminal_ativo()

        texto = ""

        if isinstance(terminal, Run_Out):
            widget = getattr(terminal, "console", None) or getattr(terminal, "ui", None)

            texto  = widget.toPlainText() if widget and hasattr(widget, "toPlainText") else ""

        if not texto.strip():
            janela = self.window()

            if hasattr(janela, "tabs"):
                for i in range(janela.tabs.count()):
                    editor = janela.tabs.editores.get(i)

                    if editor:
                        conteudo = editor.toPlainText()

                        if conteudo.strip():
                            texto = conteudo

                            break

        self._abrir_json_explorer(texto)

    # 💡 modo_opc = Literal["powershell"] ← defina os valores válidos

    def add_new_terminal(self, modo="powershell", nome_aba=None, project_path=None):
        if modo == "powershell":
            self._contador_ps += 1
            janela  = self.window()
            caminho = project_path or getattr(janela, "current_project_path", None)
            terminal = Power_Shwell(project_path=caminho)
            terminal.navegar_para_erro.connect(self.navegar_para_erro)
            terminal.abrir_arquivo_solicitado.connect(self.abrir_arquivo_solicitado)

            nome_aba = nome_aba or f"Terminal {self._contador_ps}"
            icone = icone_tema("mdi.console")

        else:  # "saida", "run_output", qualquer outro
            terminal = Run_Out()
            nome_aba = nome_aba or "Saída"
            terminal.explorar_json_solicitado.connect(self._abrir_json_explorer)
            icone = icone_tema("mdi.play")

            indice = self.addTab(terminal, icone, nome_aba)  # ← faltava o ícone aqui também
            self.terminais[indice] = terminal
            self.setCurrentIndex(indice)

            _estilo_run_btn = (
                "QPushButton { background: transparent; border: none; }"
                "QPushButton:hover { background: rgba(255,255,255,0.08); border-radius: 3px; }"
            )

            btn_run_aba = QPushButton()
            btn_run_aba.setIcon(icone_tema("mdi.play"))
            btn_run_aba.setIconSize(QSize(14, 14))
            btn_run_aba.setFixedSize(20, 20)
            btn_run_aba.setStyleSheet(_estilo_run_btn)
            btn_run_aba.setToolTip("Executar (F1)")

            btn_run_aba.clicked.connect(
                lambda checked=False, _t=terminal, idx=indice: (
                    self.setCurrentIndex(idx),
                    _t.process.kill()
                    if _t.process.state() != QProcess.ProcessState.NotRunning
                    else _t._reexecutar()
                )
            )

            self.tabBar().setTabButton(indice, QTabBar.LeftSide, btn_run_aba)

            self._run_btns[indice] = btn_run_aba

            terminal.processo_iniciado.connect(

                lambda pid, idx=indice: self._ao_run_iniciado(idx, pid)

            )

            terminal.processo_terminou_sinal.connect(

                lambda code, idx=indice: self._ao_run_terminou(idx, code)

            )

            return terminal  # ← esse return estava lá, mas o problema era o modo inválido

        indice = self.addTab(terminal, icone, nome_aba)

        self.terminais[indice] = terminal

        self.setCurrentIndex(indice)

        return terminal

    # ⚠️  except genérico vazio
    def encerrar_todos_processos(self) -> None:
        """
        Mata todo QProcess/PowerShell ainda rodando nas abas de terminal.

        Chamado explicitamente pelo MainWindow.closeEvent ANTES do app
        fechar. As abas de terminal são widgets internos (não janelas de
        topo), então o Qt nunca dispara o closeEvent delas sozinho ao sair
        do app — sem isso, o processo do PowerShell fica órfão e o Qt avisa
        no console "QProcess: Destroyed while process is still running" /
        "QThread: Destroyed while thread is still running" ao encerrar.
        """
        for terminal in list(self.terminais.values()):
            proc = getattr(terminal, "process", None)
            if proc is None:
                continue
            encerrar_processo(proc)

        # Sessões de debug (ClienteDAP/QThread) também são widgets internos —
        # PainelDebug.closeEvent() nunca dispara ao fechar o app pelo mesmo
        # motivo acima. Sem isso, uma sessão de debug ativa ao fechar a IDE
        # gera "QThread: Destroyed while thread is still running".
        from _TERMINAIS_.Debug.painel_debug import PainelDebug
        for i in range(self.count()):
            w = self.widget(i)
            if isinstance(w, PainelDebug):
                try:
                    w._parar_sessao_atual()
                except Exception:
                    pass

    def abrir_aba_log(self) -> None:
        """Abre (ou foca) a aba Log no terminal. Sem botão de fechar."""

        for i in range(self.count()):
            if isinstance(self.widget(i), PainelLogs):
                self.setCurrentIndex(i)

                return

        painel = PainelLogs()

        icone  = icone_tema("mdi.console-line")

        idx    = self.addTab(painel, icone, "Saída")

        self.tabBar().setTabButton(idx, QTabBar.RightSide, None)  # sem botão fechar

        self.setCurrentIndex(idx)

    def abrir_aba_debug(self, arquivo: str = "") -> object:
        """Abre (ou foca) a aba do Depurador. Retorna o PainelDebug."""

        from _TERMINAIS_.Debug.painel_debug import PainelDebug
        for i in range(self.count()):
            if isinstance(self.widget(i), PainelDebug):
                self.setCurrentIndex(i)

                if arquivo:
                    self.widget(i).set_arquivo(arquivo)

                return self.widget(i)

        painel = PainelDebug(arquivo=arquivo)

        icone  = icone_tema("mdi.bug")

        idx    = self.addTab(painel, icone, "Depurador")

        self.setCurrentIndex(idx)

        return painel

    def painel_debug_ativo(self) -> object | None:
        """Retorna o PainelDebug com sessão ativa (_dap não None), ou None."""

        from _TERMINAIS_.Debug.painel_debug import PainelDebug
        for i in range(self.count()):
            w = self.widget(i)

            if isinstance(w, PainelDebug) and w._dap is not None:
                return w

        return None

    def abrir_aba_tarefa(self, nome: str, comando: str, diretorio: str = "") -> object:
        """

        Abre uma nova aba PowerShell dedicada à tarefa e executa o comando.

        Se já existir uma aba com esse nome, ela é fechada antes de criar outra.

        O comando é enviado via hook _comando_tarefa após o setup do terminal.

        """

        # fecha aba anterior com mesmo nome, se existir

        for i in range(self.count() - 1, -1, -1):
            if self.tabText(i) == nome:
                self.fechar_aba(i)

                break

        terminal = self.add_new_terminal(

            modo="powershell",

            nome_aba=nome,

            project_path=diretorio or None,

        )

        if terminal and hasattr(terminal, "_comando_tarefa"):
            terminal._comando_tarefa = comando

        elif terminal and hasattr(terminal, "enviar_comando"):
            # fallback: terminal sem setup pendente

            from PySide6.QtCore import QTimer
            QTimer.singleShot(800, lambda: terminal.enviar_comando(comando))

        return terminal


    def abrir_executor_terminal(self, nome_linguagem: str, arquivo: str) -> None:
        """Abre (ou foca e reutiliza) a aba ExecutorTerminal da linguagem.

        Cada linguagem tem no maximo UMA aba — ao executar outro arquivo

        da mesma linguagem, a aba existente e reaproveitada via set_arquivo().

        """

        from _TERMINAIS_.Mult_Terminais.terminal_executor import ExecutorTerminal
        from _TERMINAIS_.Mult_Terminais.html_visor import HTMLVisorTerminal
        # HTML: roteamento dedicado
        if nome_linguagem == 'HTML':
            for i in range(self.count()):
                if isinstance(self.widget(i), HTMLVisorTerminal):
                    self.widget(i).set_arquivo(arquivo)
                    self.setCurrentIndex(i)

                    return

            visor = HTMLVisorTerminal(arquivo)
            idx   = self.addTab(visor, icone_tema("mdi.language-html5"), "HTML")
            self.setCurrentIndex(idx)

            return

        for i in range(self.count()):
            w = self.widget(i)

            if isinstance(w, ExecutorTerminal) and w._nome == nome_linguagem:
                w.set_arquivo(arquivo)

                self.setCurrentIndex(i)

                return

        terminal = ExecutorTerminal(nome_linguagem, arquivo)

        icone    = icone_tema("mdi.play-box-outline")

        idx      = self.addTab(terminal, icone, nome_linguagem)

        self.setCurrentIndex(idx)

    def fechar_aba(self, indice: int):
        widget = self.widget(indice)

        if isinstance(widget, PainelLogs):
            return  # aba Log não pode ser fechada

        if self.count() <= 1:
            return

        # encerra sessão DAP antes de destruir o widget

        from _TERMINAIS_.Debug.painel_debug import PainelDebug
        if isinstance(widget, PainelDebug):
            widget._parar_sessao_atual()

        from _TERMINAIS_.Mult_Terminais.terminal_executor import ExecutorTerminal
        from _TERMINAIS_.Mult_Terminais.html_visor import HTMLVisorTerminal
        if isinstance(widget, (ExecutorTerminal, HTMLVisorTerminal)):
            widget.parar()

        terminal = self.terminais.get(indice)

        if terminal and hasattr(terminal, "process"):
            if terminal.process.state() != QProcess.NotRunning:
                terminal.process.kill()

        self.aba_vai_fechar.emit(widget)

        self.removeTab(indice)

        self.terminais.pop(indice, None)

        self._reindexar()

    def _reindexar(self):
        novos = {}

        for i, k in enumerate(sorted(self.terminais)):
            novos[i] = self.terminais[k]

        self.terminais = novos

    def terminal_ativo(self):
        return self.terminais.get(self.currentIndex())

    # 💡 nome_opc = Literal["Saída"] ← defina os valores válidos

    def obter_ou_criar_saida(self, nome: str = "Saída"):
        icone = icone_tema("mdi.play")

        for i in range(self.count()):
            if self.tabText(i) == nome and isinstance(self.widget(i), Run_Out):
                self.setCurrentIndex(i)

                self.setTabIcon(i, icone)

                w = self.widget(i)

                self.terminais[i] = w

                return w

        # ← era "run_output", que não existe → caia no else mas retornava None

        return self.add_new_terminal(modo="saida", nome_aba=nome)

    def abrir_aba_imagem_controles(self, caminho: str) -> None:
        """Abre OU ATUALIZA o unico painel compartilhado de ferramentas de imagem."""

        from _TERMINAIS_.visualizador_imagem import ControlesImagem
        import os as _os
        nome = "Imagem: " + _os.path.basename(caminho)

        for i in range(self.count()):
            w = self.widget(i)

            if isinstance(w, ControlesImagem):
                w.set_caminho(caminho)

                self.setTabText(i, nome)

                self.setCurrentIndex(i)

                return

        controles = ControlesImagem(caminho)

        indice = self.addTab(controles, nome)

        self.setCurrentIndex(indice)

    def fechar_aba_imagem_controles(self) -> None:
        """Fecha o painel de ferramentas de imagem quando nao ha mais imagens abertas."""

        from _TERMINAIS_.visualizador_imagem import ControlesImagem
        for i in range(self.count()):
            if isinstance(self.widget(i), ControlesImagem):
                self.removeTab(i)

                return

    def _parar_run_ativo(self):
        terminal = self.terminal_ativo()

        if terminal and isinstance(terminal, Run_Out):
            terminal.process.kill()

    def _atualizar_botoes_run(self, indice: int = -1):
        terminal = self.terminal_ativo()

        em_execucao = (

            isinstance(terminal, Run_Out)

            and terminal.process.state() == terminal.process.ProcessState.Running

        )

        self._btn_stop_canto.setVisible(em_execucao)

    def _ao_run_iniciado(self, indice: int, pid: int):
        try:
            if 0 <= indice < self.count():
                self.tabBar().setTabToolTip(indice, f"Saída\nPID: {pid}")
            btn = self._run_btns.get(indice)
            if btn:
                btn.setIcon(icone_tema("mdi.stop"))
                btn.setToolTip("Parar execução")
        except RuntimeError:
            # O processo pode terminar depois que a aba foi destruída.
            return

    def _ao_run_terminou(self, indice: int, exit_code: int):
        try:
            status = "✓ OK" if exit_code == 0 else f"✗ código {exit_code}"
            if 0 <= indice < self.count():
                self.tabBar().setTabToolTip(indice, f"Saída\n{status}")
            btn = self._run_btns.get(indice)
            if btn:
                btn.setIcon(icone_tema("mdi.play"))
                btn.setToolTip("Executar (F1)")
        except RuntimeError:
            # O callback pode chegar após o QPushButton/aba ser destruído.
            return

    def _atualizar_linha_borda(self):
        t = tema_global()

        cor = t.cor("interface.fundo_aba_ativa", BORDA_GERAL)

        self._linha_borda.setStyleSheet(f"background-color: {cor}; border: none;")

        self._linha_borda.setAttribute(Qt.WA_StyledBackground, True)

    def atualizar_borda(self, cor: str, larg: int, estilo: str, raio: int = 8):
        if hasattr(self, "_borda_completa"):
            self._borda_completa.atualizar(cor, larg, estilo)

        # atualiza também a tab bar para controlar o estilo da linha base

        bar = self.tabBar()

        if hasattr(bar, '_borda_larg'):
            bar._borda_cor    = cor

            bar._borda_larg   = larg

            bar._borda_estilo = estilo

            bar.update()

        tb = self.tabBar()

        tb._borda_cor    = cor

        tb._borda_larg   = larg

        tb._borda_estilo = estilo

        tb.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if hasattr(self, "_linha_borda"):
            y = self.tabBar().height() - 2

            self._linha_borda.setGeometry(0, y, self.width(), 2)

            self._linha_borda.raise_()

        if hasattr(self, "_borda_completa"):
            self._borda_completa.setGeometry(self.rect())

            self._borda_completa.raise_()
