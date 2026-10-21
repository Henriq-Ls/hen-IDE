# 📁 _TERMINAIS_/Debug/painel_debug.py
"""
Painel de controle do depurador integrado da hein IDE.

Responsabilidades:
  - Exibir controles de fluxo: Continuar, Próxima Linha, Entrar, Sair, Parar.
  - Mostrar o arquivo e a linha em execução.
  - Listar as variáveis locais em QTreeWidget (nome / tipo / valor).
  - Criar e controlar o ClienteDAP (thread de comunicação com debugpy).

Uso:
    painel = PainelDebug(arquivo="script.py")
    painel.iniciar_sessao(arquivo="script.py", python_path="/venv/bin/python")
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTreeWidget, QTreeWidgetItem, QFrame, QSizePolicy, QHeaderView,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont
from _CONFIGURA_.gerenciador_tema import tema_global
from _UTILITARIOS_.icones import icone_tema
from _THREADS_.ciclo_vida import encerrar_thread
# ── Estados visuais ───────────────────────────────────────────────────────────
_ESTADOS: dict[str, tuple[str, str]] = {
    "aguardando": ("Aguardando...", "#8b949e"),
    "pausado":    ("⏸  Pausado",    "#e6c547"),
    "executando": ("▶  Executando", "#4ec994"),
    "parado":     ("■  Parado",     "#f87070"),
    "erro":       ("✕  Erro",       "#f87070"),
}

class PainelDebug(QWidget):
    """
    Painel de depuração com interface completa e integração ao ClienteDAP.
    Sinais públicos são emitidos para extensibilidade futura.
    """

    # sinais públicos (para plugins / extensões futuras)
    continuar_solicitado = Signal()
    proximo_solicitado   = Signal()
    entrar_solicitado    = Signal()
    sair_solicitado      = Signal()
    parar_solicitado     = Signal()

    _MAX_PROFUNDIDADE = 10   # protege contra estruturas cíclicas

    # ─────────────────────────────────────────────────────────────────────────
    def __init__(self, arquivo: str = "", parent=None):
        super().__init__(parent)
        self._arquivo_atual = arquivo
        self._dap = None          # ClienteDAP ativo (ou None)
        self._construir_ui()
        self.set_estado("aguardando")
        self._aplicar_tema()
        if arquivo:
            self.set_arquivo(arquivo)

    # ─────────────────────────────────────────────────────────────────────────
    # Sessão de debug
    # ─────────────────────────────────────────────────────────────────────────

    def iniciar_sessao(self, arquivo: str, python_path: str, breakpoints: set | None = None):
        """
        Encerra qualquer sessão ativa e inicia uma nova sessão de debug.
        breakpoints: conjunto de linhas (1-based) com breakpoints ativos.
        """
        self._parar_sessao_atual()

        from _TERMINAIS_.Debug.cliente_dap import ClienteDAP
        bps_lista = sorted(breakpoints) if breakpoints else []
        self._dap = ClienteDAP(
            arquivo=arquivo,
            python_path=python_path,
            breakpoints=bps_lista,
        )

        # sinais do DAP → slots da UI
        self._dap.pausado.connect(self._ao_pausar)
        self._dap.variaveis_recebidas.connect(self.atualizar_variaveis)
        self._dap.executando.connect(self._ao_executar)
        self._dap.encerrado.connect(self._ao_encerrar)
        self._dap.erro.connect(self._ao_erro)

        # QThread.finished é emitido APÓS run() retornar e o thread do SO
        # estar completamente encerrado — único momento seguro para deletar.
        self._dap.finished.connect(self._ao_thread_finalizada)

        self.set_arquivo(arquivo)
        self.set_estado("executando")
        self.limpar()
        self._dap.start()

    def sincronizar_breakpoints(self, arquivo: str, bps: set):
        """
        Atualiza os breakpoints durante uma sessão ativa.
        Chamado pelo main_window quando o usuário clica na margem do editor.
        """
        if self._dap and self._dap.isRunning():
            self._dap.set_breakpoints(sorted(bps))

    # ⚠️  except genérico vazio
    def _parar_sessao_atual(self):
        """Encerra a sessão DAP atual de forma segura, sem destruir a QThread
        enquanto ela ainda está em execução."""
        if not self._dap:

            return

        dap        = self._dap
        self._dap  = None                    # limpa referência antes de esperar

        # desconecta o slot de limpeza automática para não executar duas vezes
        try:
            dap.finished.disconnect(self._ao_thread_finalizada)
        except Exception:
            pass

        if dap.isRunning():
            dap.parar()
            encerrar_thread(dap, 8000)

        dap.deleteLater()                    # destrói o QObject no próximo ciclo

    def _ao_thread_finalizada(self):
        """
        Slot conectado a QThread.finished.
        Emitido depois que run() retornou E o thread do SO terminou completamente
        — único momento seguro para destruir o objeto QThread sem o aviso
        'QThread: Destroyed while thread is still running'.
        """
        dap       = self._dap
        self._dap = None
        if dap is not None:
            dap.deleteLater()

    # ── Slots do ClienteDAP ───────────────────────────────────────────────────

    def _ao_pausar(self, arquivo: str, linha: int):
        self.set_arquivo(arquivo, linha)
        self.set_estado("pausado")

    def _ao_executar(self):
        self.set_estado("executando")

    def _ao_encerrar(self): # Apenas atualiza a UI; limpeza do objeto fica em _ao_thread_finalizada
        self.set_estado("parado")

    def _ao_erro(self, mensagem: str): # Apenas atualiza a UI; limpeza do objeto fica em _ao_thread_finalizada
        self.set_estado("erro")
        self._lbl_local.setText(f"  ✕ {mensagem}")

    # ── Comandos dos botões (chamam o DAP ou emitem sinal público) ────────────

    def _cmd_continuar(self):
        self.continuar_solicitado.emit()
        if self._dap:
            self._dap.continuar()

    def _cmd_proximo(self):
        self.proximo_solicitado.emit()
        if self._dap:
            self._dap.proximo()

    def _cmd_entrar(self):
        self.entrar_solicitado.emit()
        if self._dap:
            self._dap.entrar()

    def _cmd_sair(self):
        self.sair_solicitado.emit()
        if self._dap:
            self._dap.sair()

    def _cmd_parar(self):
        self.parar_solicitado.emit()
        self._parar_sessao_atual()
        self.set_estado("parado")
        self.limpar()

    # ─────────────────────────────────────────────────────────────────────────
    # Construção da UI
    # ─────────────────────────────────────────────────────────────────────────

    # ⚠️  função grande (100 linhas)
    def _construir_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── barra de ferramentas ──────────────────────────────────────────────
        self._barra = QWidget()
        self._barra.setObjectName("barra_debug")
        self._barra.setFixedHeight(34)
        lay_barra = QHBoxLayout(self._barra)
        lay_barra.setContentsMargins(6, 0, 6, 0)
        lay_barra.setSpacing(2)

        _estilo_btn = (
            "QPushButton {"
            "  background: transparent; border: none; border-radius: 4px;"
            "}"
            "QPushButton:hover { background: rgba(255,255,255,0.08); }"
            "QPushButton:pressed { background: rgba(255,255,255,0.14); }"
            "QPushButton:disabled { opacity: 0.30; }"
        )

        def _btn(tooltip: str, icone_nome: str, slot) -> QPushButton:
            b = QPushButton()
            b.setToolTip(tooltip)
            b.setIcon(icone_tema(icone_nome))
            b.setIconSize(QSize(16, 16))
            b.setFixedSize(26, 26)
            b.setStyleSheet(_estilo_btn)
            b.clicked.connect(slot)

            return b

        self._btn_continuar = _btn("Continuar (F5)",          "mdi.play-circle-outline", self._cmd_continuar)
        self._btn_proximo   = _btn("Próxima Linha (F10)",     "mdi.debug-step-over",     self._cmd_proximo)
        self._btn_entrar    = _btn("Entrar na Função (F11)",  "mdi.debug-step-into",     self._cmd_entrar)
        self._btn_sair      = _btn("Sair da Função (⇧F11)",  "mdi.debug-step-out",      self._cmd_sair)
        self._btn_parar     = _btn("Parar Depurador",         "mdi.stop-circle-outline", self._cmd_parar)

        _sep = QFrame()
        _sep.setFrameShape(QFrame.VLine)
        _sep.setFixedWidth(1)

        self._lbl_estado = QLabel()
        self._lbl_estado.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        lay_barra.addWidget(self._btn_continuar)
        lay_barra.addWidget(self._btn_proximo)
        lay_barra.addWidget(self._btn_entrar)
        lay_barra.addWidget(self._btn_sair)
        lay_barra.addWidget(self._btn_parar)
        lay_barra.addWidget(_sep)
        lay_barra.addWidget(self._lbl_estado)
        root.addWidget(self._barra)

        # ── label de localização ──────────────────────────────────────────────
        self._lbl_local = QLabel("  Nenhum arquivo em depuração")
        self._lbl_local.setObjectName("lbl_local_debug")
        self._lbl_local.setFixedHeight(22)
        fonte_local = QFont()
        fonte_local.setPointSize(10)
        fonte_local.setItalic(True)
        self._lbl_local.setFont(fonte_local)
        root.addWidget(self._lbl_local)

        # ── separador ─────────────────────────────────────────────────────────
        self._sep_h = QFrame()
        self._sep_h.setFrameShape(QFrame.HLine)
        self._sep_h.setFixedHeight(1)
        root.addWidget(self._sep_h)

        # ── tabela de variáveis ───────────────────────────────────────────────
        self._tabela = QTreeWidget()
        self._tabela.setHeaderLabels(["Nome", "Tipo", "Valor"])
        self._tabela.header().setSectionResizeMode(0, QHeaderView.Interactive)
        self._tabela.header().setSectionResizeMode(1, QHeaderView.Interactive)
        self._tabela.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self._tabela.setColumnWidth(0, 160)
        self._tabela.setColumnWidth(1, 110)
        self._tabela.setAlternatingRowColors(True)
        self._tabela.setAnimated(True)
        self._tabela.setIndentation(16)
        self._tabela.setRootIsDecorated(True)
        self._tabela.setSortingEnabled(True)
        self._tabela.sortByColumn(0, Qt.AscendingOrder)
        fonte_tab = QFont("Consolas", 10)
        self._tabela.setFont(fonte_tab)
        root.addWidget(self._tabela)

        # ── mensagem de espera ────────────────────────────────────────────────
        self._lbl_vazio = QLabel(
            "Clique em ▶ Continuar para executar até o próximo ponto de parada,\n"
            "ou use ⤵ Próxima Linha para avançar passo a passo."
        )
        self._lbl_vazio.setAlignment(Qt.AlignCenter)
        self._lbl_vazio.setWordWrap(True)
        root.addWidget(self._lbl_vazio)

        self._tabela.setVisible(False)
        self._lbl_vazio.setVisible(True)

    # ─────────────────────────────────────────────────────────────────────────
    # API pública
    # ─────────────────────────────────────────────────────────────────────────

    def set_arquivo(self, caminho: str, linha: int = 0):
        self._arquivo_atual = caminho
        nome   = os.path.basename(caminho) if caminho else "—"
        sufixo = f" : linha {linha}" if linha else ""
        self._lbl_local.setText(f"  📍 {nome}{sufixo}")

    def set_estado(self, estado: str):
        """
        Atualiza estado visual e habilita/desabilita botões.
        Válidos: 'aguardando', 'pausado', 'executando', 'parado', 'erro'.
        """
        texto, cor = _ESTADOS.get(estado, ("—", "#8b949e"))
        self._lbl_estado.setText(texto)
        self._lbl_estado.setStyleSheet(
            f"font-size: 11px; padding: 0 8px; color: {cor}; font-weight: bold;"
        )
        em_pausa = (estado == "pausado")
        for btn in (self._btn_continuar, self._btn_proximo,
                    self._btn_entrar, self._btn_sair):
            btn.setEnabled(em_pausa)
        self._btn_parar.setEnabled(estado in ("pausado", "executando"))

    def atualizar_variaveis(self, variaveis: list):
        """
        Preenche a tabela. Cada item: {"nome": str, "tipo": str, "valor": str,
        "filhos": list[dict] (opcional)}.
        """
        self._tabela.clear()
        if not variaveis:
            self._tabela.setVisible(False)
            self._lbl_vazio.setVisible(True)

            return

        self._tabela.setVisible(True)
        self._lbl_vazio.setVisible(False)
        for v in variaveis:
            self._tabela.addTopLevelItem(self._criar_item(v))

    def limpar(self):
        self._tabela.clear()
        self._tabela.setVisible(False)
        self._lbl_vazio.setVisible(True)

    # ─────────────────────────────────────────────────────────────────────────
    # Auxiliares
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _criar_item(v: dict, _prof: int = 0) -> QTreeWidgetItem:
        item = QTreeWidgetItem([
            str(v.get("nome",  "")),
            str(v.get("tipo",  "")),
            str(v.get("valor", "")),
        ])
        item.setTextAlignment(1, Qt.AlignCenter)
        filhos = v.get("filhos", [])
        if filhos and _prof < PainelDebug._MAX_PROFUNDIDADE:
            for f in filhos:
                item.addChild(PainelDebug._criar_item(f, _prof + 1))
        elif filhos:
            item.addChild(QTreeWidgetItem(["", "", "... (muito aninhado)"]))

        return item

    # ─────────────────────────────────────────────────────────────────────────
    # Tema
    # ─────────────────────────────────────────────────────────────────────────

    # ⚠️  função grande (59 linhas)
    def _aplicar_tema(self):
        t      = tema_global()
        fundo  = t.cor("interface.fundo",        "#0d1117")
        fundo2 = t.cor("interface.fundo_painel", "#161b22")
        texto  = t.cor("interface.texto",        "#e6edf3")
        fraco  = t.cor("interface.texto_fraco",  "#8b949e")
        borda  = t.cor("interface.borda",        "#21262d")
        alt    = t.cor("interface.hover",        "#1c2128")

        self.setStyleSheet(f"""
            PainelDebug {{ background: {fundo}; }}
            QWidget#barra_debug {{
                background: {fundo2};
                border-bottom: 1px solid {borda};
            }}
            QLabel#lbl_local_debug {{
                background: {fundo2};
                color: {fraco};
                border-bottom: 1px solid {borda};
                font-size: 10px;
                padding-left: 4px;
            }}
            QTreeWidget {{
                background: {fundo};
                alternate-background-color: {alt};
                color: {texto};
                border: none;
                outline: 0;
            }}
            QTreeWidget::item {{ padding: 3px 4px; border: none; }}
            QTreeWidget::item:selected {{
                background: rgba(78,201,148,0.15);
                color: {texto};
            }}
            QTreeWidget::item:hover {{ background: rgba(255,255,255,0.05); }}
            QHeaderView::section {{
                background: {fundo2};
                color: {fraco};
                border: none;
                border-bottom: 1px solid {borda};
                border-right: 1px solid {borda};
                padding: 3px 6px;
                font-size: 11px;
                font-weight: bold;
            }}
            QScrollBar:vertical {{
                background: {fundo}; width: 8px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {borda}; border-radius: 4px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        self._sep_h.setStyleSheet(f"color: {borda};")
        self._lbl_vazio.setStyleSheet(
            f"font-size: 12px; padding: 24px 40px; color: {fraco};"
        )

    def closeEvent(self, event):
        """Garante que a thread DAP seja encerrada quando o widget for destruído."""
        self._parar_sessao_atual()
        super().closeEvent(event)
