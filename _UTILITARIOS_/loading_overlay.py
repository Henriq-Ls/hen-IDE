# _UTILITARIOS_/loading_overlay.py
"""
LoadingOverlay — overlay modal animado para operações demoradas no hein IDE.

Bloqueia TODOS os cliques na janela enquanto estiver visível (ApplicationModal).
Sem botões. Fecha apenas programaticamen te via fechar().

────────────────────────────────────────────────────────────────────────────
USO BÁSICO (mixin_projeto.py / qualquer mixin)
────────────────────────────────────────────────────────────────────────────

    from _UTILITARIOS_.loading_overlay import LoadingOverlay

    overlay = LoadingOverlay(self, mensagem="Abrindo projeto...")
    overlay.show()
    QApplication.processEvents()   # garante 1 frame renderizado antes de travar

    try:
        self._fazer_trabalho_pesado()
    finally:
        overlay.fechar()

────────────────────────────────────────────────────────────────────────────
ATUALIZAR MENSAGEM EM TEMPO DE EXECUÇÃO
────────────────────────────────────────────────────────────────────────────

    overlay.set_mensagem("Restaurando sessão...")

────────────────────────────────────────────────────────────────────────────
INTEGRAÇÃO COM _ThreadSegura (para fechar ao sinal de conclusão)
────────────────────────────────────────────────────────────────────────────

    overlay = LoadingOverlay(self, mensagem="Carregando...")
    overlay.show()
    thread.concluido.connect(overlay.fechar)
    thread.start()

────────────────────────────────────────────────────────────────────────────
REGRAS DE THREAD — NÃO VIOLE
────────────────────────────────────────────────────────────────────────────
• show() e fechar() devem ser chamados na MAIN THREAD.
• fechar() pode ser conectado a Signal de QThread via connect() — o Qt
  despacha automaticamente para a main thread (conexão cross-thread).
• NÃO conecte finished de uma _ThreadSegura a fechar() diretamente se o
  objeto da thread e o overlay tiverem o mesmo parent — use um lambda ou
  slot intermediário para evitar ordem de destruição ambígua.
• Se a thread que dispara fechar() puder ser destruída antes do dispatch,
  use Qt.QueuedConnection explicitamente:
      thread.concluido.connect(overlay.fechar, Qt.QueuedConnection)
"""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout, QWidget


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de tema
# ─────────────────────────────────────────────────────────────────────────────

def _cor_tema(chave: str, fallback: str) -> str:
    """Lê uma cor do tema global com fallback seguro."""
    try:
        from _CONFIGURA_.gerenciador_tema import tema_global
        return tema_global().cor(chave, fallback)
    except Exception:
        return fallback


# ─────────────────────────────────────────────────────────────────────────────
# Spinner
# ─────────────────────────────────────────────────────────────────────────────

class _Spinner(QWidget):
    """
    Spinner de traços radiais animado via QPainter + QTimer.
    Sem GIF, sem dependência externa além de PySide6.
    """

    _N_TRACOS  = 10      # número de traços radiais
    _R_EXT     = 20      # raio externo em px
    _R_INT     = 11      # raio interno em px
    _ESPESSURA = 3       # largura do traço em px
    _INTERVALO = 70      # ms por frame (~14 fps)

    def __init__(self, cor: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cor   = QColor(cor)
        self._passo = 0
        lado = (self._R_EXT + 3) * 2
        self.setFixedSize(lado, lado)

        self._timer = QTimer(self)
        self._timer.setInterval(self._INTERVALO)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ------------------------------------------------------------------

    def parar(self) -> None:
        """Para a animação — chame antes de destruir o widget."""
        self._timer.stop()

    def _tick(self) -> None:
        self._passo = (self._passo + 1) % self._N_TRACOS
        self.update()

    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width()  / 2.0
        cy = self.height() / 2.0
        ang_passo = (2.0 * math.pi) / self._N_TRACOS

        for i in range(self._N_TRACOS):
            # Cabeçote = passo atual (mais opaco); cauda fica cada vez mais transparente
            distancia = (i - self._passo) % self._N_TRACOS
            alpha = int(255 * (1.0 - distancia / self._N_TRACOS))
            alpha = max(20, alpha)   # mínimo para a cauda não sumir completamente

            cor = QColor(self._cor)
            cor.setAlpha(alpha)

            pen = QPen(cor, self._ESPESSURA)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)

            ang = i * ang_passo
            cos_a = math.cos(ang)
            sin_a = math.sin(ang)

            p.drawLine(
                int(cx + self._R_INT * cos_a),
                int(cy + self._R_INT * sin_a),
                int(cx + self._R_EXT * cos_a),
                int(cy + self._R_EXT * sin_a),
            )


# ─────────────────────────────────────────────────────────────────────────────
# Overlay principal
# ─────────────────────────────────────────────────────────────────────────────

class LoadingOverlay(QDialog):
    """
    Overlay modal sem botões para operações demoradas.

    Bloqueia toda interação com a aplicação enquanto estiver visível.
    Fecha SOMENTE via fechar() — o usuário não consegue fechar manualmente.

    Parâmetros
    ----------
    parent      : QWidget pai (normalmente MainWindow / self)
    mensagem    : texto exibido abaixo do spinner
    usar_tema   : se True (padrão), lê cores do tema_global(); se False usa os
                  parâmetros cor_* explicitamente
    cor_spinner : cor do spinner quando usar_tema=False
    cor_fundo   : cor de fundo do painel quando usar_tema=False
    cor_texto   : cor do texto quando usar_tema=False
    """

    def __init__(
        self,
        parent: QWidget,
        mensagem: str = "Aguarde...",
        usar_tema: bool = True,
        cor_spinner: str = "#4ec9b0",
        cor_fundo: str = "#1a1a1a",
        cor_texto: str = "#cccccc",
    ) -> None:
        super().__init__(parent)

        # ── cores — seguem menu_contexto.* (mesmo visual do heinContextMenu) ──
        if usar_tema:
            cor_spinner = _cor_tema("interface.destaque",        cor_spinner)
            cor_fundo   = _cor_tema("menu_contexto.fundo",       cor_fundo)
            cor_texto   = _cor_tema("menu_contexto.texto",       cor_texto)

        self._cor_fundo  = cor_fundo
        self._cor_borda  = _cor_tema("menu_contexto.borda", "#2d2d2d") if usar_tema else "#2d2d2d"
        self._fechado    = False

        # ── flags da janela ───────────────────────────────────────────────
        # ApplicationModal: bloqueia TODA a aplicação (não só o parent)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)

        # impede Alt+F4 / Esc fecharem o overlay acidentalmente
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)

        # ── layout ────────────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)
        layout.setContentsMargins(36, 28, 36, 28)

        self._spinner = _Spinner(cor_spinner, self)
        layout.addWidget(self._spinner, alignment=Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel(mensagem, self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(
            f"color: {cor_texto}; font-size: 12px; background: transparent;"
        )
        layout.addWidget(self._label)

        self.setFixedSize(230, 148)

    # ── API pública ───────────────────────────────────────────────────────

    def set_mensagem(self, texto: str) -> None:
        """Atualiza o texto em tempo de execução. Thread-safe via sinal Qt."""
        self._label.setText(texto)

    def fechar(self) -> None:
        """
        Fecha o overlay e reativa a janela pai.

        Pode ser chamado diretamente ou conectado a um Signal de QThread.
        Idempotente — chamadas repetidas são ignoradas.
        """
        if self._fechado:
            return
        self._fechado = True
        self._spinner.parar()
        self.accept()

    # ── eventos ───────────────────────────────────────────────────────────

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """Engole Esc e Enter para não fechar o overlay acidentalmente."""
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        """Impede o fechamento via Alt+F4 ou clique no X (quando a borda existe)."""
        if not self._fechado:
            event.ignore()
            return
        super().closeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        """Centraliza sobre o parent ao exibir."""
        if self.parent() and hasattr(self.parent(), "frameGeometry"):
            geo = self.parent().frameGeometry()
            self.move(
                geo.center().x() - self.width()  // 2,
                geo.center().y() - self.height() // 2,
            )
        super().showEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        """Desenha o fundo arredondado (necessário com WA_TranslucentBackground)."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(self._cor_fundo))
        pen = QPen(QColor(self._cor_borda))
        pen.setWidth(1)
        p.setPen(pen)
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 10, 10)
