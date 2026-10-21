# 📁 _EDITOR_/Editor_Hein/_float_menu_hein.py
"""
_FloatHeinMenu — widget flutuante no canto superior direito do Editor Caderno.

Exibe:
  • Data atual  (DD/MM/AA)
  • Botão ≡ → abre painel de cores inline (texto, fundo; gutter = fundo sempre)

Cores aplicadas diretamente no CodeEditor via _aplicar_cores_caderno().
"""
import datetime
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QColorDialog, QFrame,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui  import QColor


class _FloatHeinMenu(QWidget):
    """Menu flutuante (data + ≡) posicionado no canto superior direito do viewport."""

    def __init__(self, editor):
        super().__init__(editor.viewport())
        self._editor = editor
        self._painel_aberto = False

        # ── layout principal (horizontal: data + botão) ─────────────
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 3, 6, 3)
        lay.setSpacing(6)

        self._lbl_data = QLabel(self._data_str())
        self._lbl_data.setAlignment(Qt.AlignVCenter | Qt.AlignRight)

        # Separador vertical cinza entre a data e o botão ≡
        self._sep = QFrame()
        self._sep.setFrameShape(QFrame.VLine)
        self._sep.setFrameShadow(QFrame.Plain)
        self._sep.setFixedWidth(1)
        self._sep.setFixedHeight(14)

        self._btn_menu = QPushButton("≡")
        self._btn_menu.setFixedSize(22, 20)
        self._btn_menu.setToolTip("Cores do caderno")
        self._btn_menu.clicked.connect(self._toggle_painel)

        lay.addWidget(self._lbl_data)
        lay.addWidget(self._sep)
        lay.addWidget(self._btn_menu)

        # ── painel de cores (oculto por padrão) ─────────────────────
        self._painel = _PainelCores(editor, parent=editor.viewport())
        self._painel.hide()

        self._aplicar_estilo()
        self.adjustSize()
        self.raise_()

        # Atualiza a data a meia-noite
        self._timer_data = QTimer(self)
        self._timer_data.setInterval(60_000)   # verifica a cada minuto
        self._timer_data.timeout.connect(self._atualizar_data)
        self._timer_data.start()

    # ── data ────────────────────────────────────────────────────────

    @staticmethod
    def _data_str() -> str:
        h = datetime.date.today()
        return f"{h.day:02d}/{h.month:02d}/{str(h.year)[2:]}"

    def _atualizar_data(self):
        self._lbl_data.setText(self._data_str())

    # ── estilo ──────────────────────────────────────────────────────

    def _aplicar_estilo(self):
        # Usa as cores atuais do editor para o próprio menu
        fundo = getattr(self._editor, '_cor_fundo', '#FDFBF7')
        texto = getattr(self._editor, '_cor_texto', '#1A1A1A')
        pauta = getattr(self._editor, '_cor_pauta', '#D8D0C8')
        self.setStyleSheet(f"""
            QWidget {{
                background: {fundo};
                border: 1px solid {pauta};
                border-radius: 4px;
            }}
            QLabel {{
                color: {pauta};
                font-size: 10px;
                border: none;
                background: transparent;
            }}
            QPushButton {{
                color: {pauta};
                background: transparent;
                border: none;
                font-size: 15px;
            }}
            QPushButton:hover {{
                color: {texto};
            }}
        """)
        # Cor do separador vertical acompanha a pauta
        if hasattr(self, '_sep'):
            self._sep.setStyleSheet(f"background: {pauta}; border: none;")

    # ── posicionamento ───────────────────────────────────────────────

    def posicionar(self):
        vp = self._editor.viewport()
        self.adjustSize()
        x = vp.width() - self.width() - 6
        self.move(max(0, x), 4)
        self.raise_()
        # Reposiciona painel de cores se estiver aberto
        if self._painel_aberto and self._painel.isVisible():
            self._posicionar_painel()

    def _posicionar_painel(self):
        vp = self._editor.viewport()
        px = vp.width() - self._painel.width() - 6
        py = self.y() + self.height() + 2
        self._painel.move(max(0, px), py)
        self._painel.raise_()

    # ── toggle painel ────────────────────────────────────────────────

    def _toggle_painel(self):
        if self._painel_aberto:
            self._painel.hide()
            self._painel_aberto = False
        else:
            self._painel.adjustSize()
            self._posicionar_painel()
            self._painel.show()
            self._painel.raise_()
            self._painel_aberto = True

    def fechar_painel(self):
        self._painel.hide()
        self._painel_aberto = False

    # ── notificado pelo editor quando cores mudam ────────────────────

    def atualizar_estilo(self):
        """Chamado pelo editor após _aplicar_cores_caderno() para refletir novas cores."""
        self._aplicar_estilo()
        self._painel._atualizar_botoes()


# ══════════════════════════════════════════════════════════════════════
# Painel de cores
# ══════════════════════════════════════════════════════════════════════

class _PainelCores(QFrame):
    """Painel inline com seletores de cor para texto e fundo."""

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self._editor = editor
        self.setWindowFlags(Qt.Widget)
        self.setFrameShape(QFrame.StyledPanel)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        # ── linha: cor do texto ──────────────────────────────────────
        row_txt = QHBoxLayout()
        row_txt.setSpacing(6)
        lbl_txt = QLabel("Texto")
        lbl_txt.setFixedWidth(48)
        self._btn_texto = QPushButton()
        self._btn_texto.setFixedSize(48, 20)
        self._btn_texto.setToolTip("Cor do texto")
        self._btn_texto.clicked.connect(self._escolher_texto)
        row_txt.addWidget(lbl_txt)
        row_txt.addWidget(self._btn_texto)
        row_txt.addStretch()
        lay.addLayout(row_txt)

        # ── linha: cor do fundo (+ gutter) ──────────────────────────
        row_bg = QHBoxLayout()
        row_bg.setSpacing(6)
        lbl_bg = QLabel("Fundo")
        lbl_bg.setFixedWidth(48)
        self._btn_fundo = QPushButton()
        self._btn_fundo.setFixedSize(48, 20)
        self._btn_fundo.setToolTip("Cor do fundo (gutter = fundo)")
        self._btn_fundo.clicked.connect(self._escolher_fundo)
        row_bg.addWidget(lbl_bg)
        row_bg.addWidget(self._btn_fundo)
        row_bg.addStretch()
        lay.addLayout(row_bg)

        # ── linha: cor das pautas ────────────────────────────────────
        row_pa = QHBoxLayout()
        row_pa.setSpacing(6)
        lbl_pa = QLabel("Pauta")
        lbl_pa.setFixedWidth(48)
        self._btn_pauta = QPushButton()
        self._btn_pauta.setFixedSize(48, 20)
        self._btn_pauta.setToolTip("Cor das linhas do caderno")
        self._btn_pauta.clicked.connect(self._escolher_pauta)
        row_pa.addWidget(lbl_pa)
        row_pa.addWidget(self._btn_pauta)
        row_pa.addStretch()
        lay.addLayout(row_pa)

        self._atualizar_botoes()
        self._aplicar_estilo_painel()

    # ── atualiza a cor exibida nos botões ────────────────────────────

    def _atualizar_botoes(self):
        fundo = getattr(self._editor, '_cor_fundo', '#FDFBF7')
        texto = getattr(self._editor, '_cor_texto', '#1A1A1A')
        pauta = getattr(self._editor, '_cor_pauta', '#D8D0C8')
        self._btn_texto.setStyleSheet(
            f"background:{texto}; border:1px solid {pauta}; border-radius:3px;"
        )
        self._btn_fundo.setStyleSheet(
            f"background:{fundo}; border:1px solid {pauta}; border-radius:3px;"
        )
        self._btn_pauta.setStyleSheet(
            f"background:{pauta}; border:1px solid {pauta}; border-radius:3px;"
        )

    def _aplicar_estilo_painel(self):
        fundo = getattr(self._editor, '_cor_fundo', '#FDFBF7')
        texto = getattr(self._editor, '_cor_texto', '#1A1A1A')
        pauta = getattr(self._editor, '_cor_pauta', '#D8D0C8')
        self.setStyleSheet(f"""
            QFrame {{
                background: {fundo};
                border: 1px solid {pauta};
                border-radius: 4px;
            }}
            QLabel {{
                color: {texto};
                font-size: 11px;
                background: transparent;
                border: none;
            }}
        """)

    # ── seletores ────────────────────────────────────────────────────

    def _escolher_texto(self):
        cor_atual = QColor(getattr(self._editor, '_cor_texto', '#1A1A1A'))
        nova = QColorDialog.getColor(cor_atual, self, "Cor do Texto")
        if nova.isValid():
            self._editor._cor_texto = nova.name()
            self._editor._aplicar_cores_caderno()
            self._editor._salvar_cores_caderno()  # Item-5
            self._atualizar_botoes()
            self._aplicar_estilo_painel()
            if hasattr(self._editor, '_float_menu'):
                self._editor._float_menu.atualizar_estilo()

    def _escolher_fundo(self):
        cor_atual = QColor(getattr(self._editor, '_cor_fundo', '#FDFBF7'))
        nova = QColorDialog.getColor(cor_atual, self, "Cor do Fundo / Gutter")
        if nova.isValid():
            self._editor._cor_fundo = nova.name()
            # Gutter sempre igual ao fundo
            self._editor._aplicar_cores_caderno()
            self._editor._salvar_cores_caderno()  # Item-5
            self._atualizar_botoes()
            self._aplicar_estilo_painel()
            if hasattr(self._editor, '_float_menu'):
                self._editor._float_menu.atualizar_estilo()

    def _escolher_pauta(self):
        cor_atual = QColor(getattr(self._editor, '_cor_pauta', '#D8D0C8'))
        nova = QColorDialog.getColor(cor_atual, self, "Cor das Pautas")
        if nova.isValid():
            self._editor._cor_pauta = nova.name()
            self._editor._aplicar_cores_caderno()
            self._editor._salvar_cores_caderno()  # Item-5
            self._editor.viewport().update()
            self._atualizar_botoes()
            self._aplicar_estilo_painel()
            if hasattr(self._editor, '_float_menu'):
                self._editor._float_menu.atualizar_estilo()
