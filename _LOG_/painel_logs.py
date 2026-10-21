# 📁 _LOG_/painel_logs.py
"""
Painel de saída voltado ao usuário — mostra output do log_print.
Fica na aba "Saída" do terminal da IDE.

Conecta em:   _UTILITARIOS_.log_print.log_print.nova_saida
NÃO conecta:  log_signal (logs internos da IDE ficam só no arquivo)
"""
from _CONFIGURA_ import FONTE_MONO
from _CONFIGURA_.gerenciador_tema import tema_global
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QApplication,
    QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontMetrics
from _UTILITARIOS_.icones import icone_tema      # ícones nos botões

# ── Paleta de níveis ──────────────────────────────────────────────────────────
_NIVEL_COR = {
    "OK":    {"badge": "#1a3d2a", "texto": "#4ec994", "icone": "✓"},
    "INFO":  {"badge": "#0d1e33", "texto": "#569cd6", "icone": "·"},
    "AVISO": {"badge": "#2e2200", "texto": "#e5c07b", "icone": "⚠"},
    "ERRO":  {"badge": "#2e0d0d", "texto": "#e06c75", "icone": "✗"},
}
_COR_FALLBACK = {"badge": "#1a1a1a", "texto": "#888888", "icone": "·"}

class _EntradaSaida(QWidget):
    """Uma linha do painel: [badge nível]  hora  mensagem."""

    def __init__(self, nivel: str, hora: str, mensagem: str, parent=None):
        super().__init__(parent)
        cfg = _NIVEL_COR.get(nivel, _COR_FALLBACK)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget { background: #0b0b0b; border-radius: 0px; }"
            "QWidget:hover { background: #111; }"
        )

        linha = QHBoxLayout(self)
        linha.setContentsMargins(10, 5, 10, 5)
        linha.setSpacing(10)

        fonte_mono = QFont(FONTE_MONO)
        fonte_mono.setPixelSize(12)

        # ── Badge de nível ────────────────────────────────────────────
        badge = QLabel(f" {cfg['icone']} {nivel} ")
        badge.setFont(fonte_mono)
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(18)
        badge.setStyleSheet(
            f"color: {cfg['texto']};"
            f"background: {cfg['badge']};"
            f"border-radius: 3px;"
            f"padding: 0 4px;"
        )
        linha.addWidget(badge)

        # ── Hora ──────────────────────────────────────────────────────
        lbl_hora = QLabel(hora)
        lbl_hora.setFont(fonte_mono)
        lbl_hora.setStyleSheet("color: #555;")
        lbl_hora.setFixedWidth(58)
        linha.addWidget(lbl_hora)

        # ── Separador vertical ────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #222;")
        sep.setFixedWidth(1)
        linha.addWidget(sep)

        # ── Mensagem ──────────────────────────────────────────────────
        lbl_msg = QLabel(mensagem)
        lbl_msg.setFont(fonte_mono)
        lbl_msg.setStyleSheet(f"color: #d4d4d4;")
        lbl_msg.setWordWrap(True)
        lbl_msg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        linha.addWidget(lbl_msg, 1)

class PainelLogs(QWidget):
    """
    Painel de saída do usuário.
    Conecta ao log_print — NÃO ao log interno da IDE.
    """

    # ⚠️  except genérico vazio
    def __init__(self, parent=None):
        super().__init__(parent)
        self._linhas_texto: list[str] = []
        self._buffer: list[tuple[str, str, str]] = []   # (nivel, hora, msg)
        self._total = 0

        self._build()

        # Conecta ao log_print (saída do usuário)
        try:
            from _UTILITARIOS_.log_print import log_print
            log_print.nova_saida.connect(self._enfileirar)
        except Exception:
            pass

        # Erros internos da IDE — ERRO e EXCEC aparecem no painel Alerta
        try:
            from _LOG_.log_signal import log_signal
            log_signal.nova_entrada.connect(self._on_log_interno)
        except Exception:
            pass

        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._flush)
        self._timer.start()

    # ── Construção da UI ──────────────────────────────────────────────────────

    # ⚠️  função grande (97 linhas)
    def _build(self):
        self.setStyleSheet("background: #0b0b0b;")
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # Cabeçalho
        cab = QWidget()
        cab.setFixedHeight(24)
        cab.setStyleSheet(
            "background: #0d0d0d;"
            "border-bottom: 1px solid #1e1e1e;"
        )
        cl = QHBoxLayout(cab)
        cl.setContentsMargins(10, 0, 6, 0)
        cl.setSpacing(6)

        fonte_cab = QFont(FONTE_MONO)
        fonte_cab.setPixelSize(11)

        lbl_titulo = QLabel("Alerta")

        lbl_titulo.setFont(fonte_cab)
        lbl_titulo.setStyleSheet("color: #666; letter-spacing: 1px;")
        cl.addWidget(lbl_titulo)

        self._lbl_cont = QLabel("")
        self._lbl_cont.setFont(fonte_cab)
        self._lbl_cont.setStyleSheet("color: #333;")
        cl.addWidget(self._lbl_cont)

        cl.addStretch()

        # Botão limpar
        self._btn_limpar = QPushButton("⌫")
        self._btn_limpar.setToolTip("Limpar saída")
        self._btn_limpar.setFixedSize(20, 20)
        self._btn_limpar.setCursor(Qt.PointingHandCursor)
        self._btn_limpar.setStyleSheet(
            "QPushButton { background: transparent; color: #444; border: none; font-size: 11px; }"
            "QPushButton:hover { color: #e06c75; }"
        )
        self._btn_limpar.clicked.connect(self.limpar)
        cl.addWidget(self._btn_limpar)

        # Botão copiar
        self._btn_copiar = QPushButton("⎘")
        self._btn_copiar.setToolTip("Copiar tudo")
        self._btn_copiar.setFixedSize(20, 20)
        self._btn_copiar.setCursor(Qt.PointingHandCursor)
        self._btn_copiar.setStyleSheet(
            "QPushButton { background: transparent; color: #444; border: none; font-size: 12px; }"
            "QPushButton:hover { color: #4ec994; }"
        )
        self._btn_copiar.clicked.connect(self._copiar)
        cl.addWidget(self._btn_copiar)

        raiz.addWidget(cab)

        # Área de scroll
        self._area = QScrollArea()
        self._area.setWidgetResizable(True)
        self._area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._area.setStyleSheet(
            "QScrollArea { border: none; background: #0b0b0b; }"
            "QScrollBar:vertical { background: #111; width: 6px; border-radius: 3px; }"
            "QScrollBar::handle:vertical { background: #2a2a2a; border-radius: 3px; }"
            "QScrollBar::handle:vertical:hover { background: #3a3a3a; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

        self._cont = QWidget()
        self._cont.setStyleSheet("background: #0b0b0b;")
        self._vbox = QVBoxLayout(self._cont)
        self._vbox.setContentsMargins(0, 4, 0, 4)
        self._vbox.setSpacing(1)
        self._vbox.addStretch()

        self._area.setWidget(self._cont)
        raiz.addWidget(self._area, 1)

        # Rodapé com linha de status
        self._rodape = QWidget()
        self._rodape.setFixedHeight(18)
        self._rodape.setStyleSheet(
            "background: #0d0d0d; border-top: 1px solid #1a1a1a;"
        )
        rl = QHBoxLayout(self._rodape)
        rl.setContentsMargins(10, 0, 10, 0)
        self._lbl_status = QLabel("Pronto.")
        fonte_rod = QFont(FONTE_MONO)
        fonte_rod.setPixelSize(10)
        self._lbl_status.setFont(fonte_rod)
        self._lbl_status.setStyleSheet("color: #3a3a3a;")
        rl.addWidget(self._lbl_status)
        rl.addStretch()
        raiz.addWidget(self._rodape)

    # ── Pipeline de entrada ───────────────────────────────────────────────────

    def _enfileirar(self, nivel: str, hora: str, mensagem: str):
        self._buffer.append((nivel, hora, mensagem))

    def _on_log_interno(self, nivel: str, texto: str):
        """Recebe log interno da IDE — só ERRO e EXCEC vão ao painel Alerta."""
        if nivel in ("ERRO", "EXCEC"):
            from datetime import datetime
            hora = datetime.now().strftime("%H:%M:%S")
            self._enfileirar(nivel, hora, texto)

    def _flush(self):
        if not self._buffer:

            return

        lote = self._buffer[:30]
        self._buffer = self._buffer[30:]
        for nivel, hora, msg in lote:
            self._adicionar(nivel, hora, msg)

    def _adicionar(self, nivel: str, hora: str, mensagem: str):
        self._total += 1
        self._linhas_texto.append(f"[{hora}] [{nivel}] {mensagem}")
        self._lbl_cont.setText(f"({self._total})")
        self._lbl_status.setText(mensagem if len(mensagem) <= 80 else mensagem[:77] + "…")

        entrada = _EntradaSaida(nivel, hora, mensagem, self._cont)
        self._vbox.insertWidget(self._vbox.count() - 1, entrada)

        # Separador fino
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #141414;")
        self._vbox.insertWidget(self._vbox.count() - 1, sep)

        # Auto-scroll se estava no fundo
        sb = self._area.verticalScrollBar()
        QTimer.singleShot(0, lambda: sb.setValue(sb.maximum()))

    # ── Ações ──────────────────────────────────────────────────────────────────

    def limpar(self):
        """Remove todas as entradas do painel."""
        self._linhas_texto.clear()
        self._total = 0
        self._lbl_cont.setText("")
        self._lbl_status.setText("Pronto.")

        # Remove widgets filhos (todos menos o stretch)
        while self._vbox.count() > 1:
            item = self._vbox.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def _copiar(self):
        if self._linhas_texto:
            QApplication.clipboard().setText("\n".join(self._linhas_texto))
        self._btn_copiar.setText("✓")
        QTimer.singleShot(1400, lambda: self._btn_copiar.setText("⎘"))

    # ── API pública (compatibilidade) ─────────────────────────────────────────

    def adicionar(self, nivel: str, mensagem: str):
        """Adiciona entrada diretamente (sem passar pelo signal)."""
        from datetime import datetime
        hora = datetime.now().strftime("%H:%M:%S")
        self._adicionar(nivel, hora, mensagem)
