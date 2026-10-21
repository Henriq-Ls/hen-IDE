# 📁 _TERMINAIS_/aba_log_pip.py
# -*- coding: utf-8 -*-
"""
AbaLogPip — widget leve de log para pip install e migração de .venv.
Adicionado como aba no TerminalTabWidget em vez de QDialog.
Zero janelas flutuantes.
"""
from __future__ import annotations
from PySide6.QtCore    import Signal
from PySide6.QtGui     import QColor, QFont, QTextCursor
from PySide6.QtWidgets import QVBoxLayout, QWidget, QTextEdit
from _LOG_.log import log
_ARQ = "aba_log_pip.py"

class AbaLogPip(QWidget):
    """
    Aba de log para pip install / migração de .venv.

    API pública:
        append_log(texto: str)           → acrescenta linha ao log (slot-safe)
        ao_concluir(sucesso: bool, msg)  → estiliza resultado e emite concluido
        concluido  Signal(bool)          → emitido após ao_concluir
    """

    concluido = Signal(bool)   # True = sucesso

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont(FONTE_MONO, 9))
        self._log.setLineWrapMode(QTextEdit.NoWrap)
        self._aplicar_estilo()
        lay.addWidget(self._log)

    # ── estilo ─────────────────────────────────────────────────────────

    def _aplicar_estilo(self):
        try:
            from _CONFIGURA_.gerenciador_tema import tema_global
            t  = tema_global()
            bg = t.cor("editor.fundo",  "#0d0d0d")
            fg = t.cor("editor.texto",  "#c8c8c8")
        except Exception:
            bg, fg = tema_global().cor("terminal.fundo","#0d0d0d"), COR_CINZA_TEXTO
        self._log.setStyleSheet(
            f"QTextEdit {{ background: {bg}; color: {fg}; border: none; }}"
        )

    # ── API pública ─────────────────────────────────────────────────────

    def append_log(self, texto: str):
        """Acrescenta linha de texto simples ao log (thread-safe via Qt signal)."""
        self._log.append(texto)
        self._log.ensureCursorVisible()

    def ao_concluir(self, sucesso: bool, msg: str = ""):
        """Chamado pelo thread ao terminar. Adiciona linha colorida de resultado."""
        if sucesso:
            self._log.append(
                "<span style='color:#4ec994; font-weight:bold'>"
                "✓  Concluído com sucesso!</span>"
            )
            log.ok(_ARQ, "ao_concluir", "pip/migração ok")
        else:
            self._log.setTextColor(QColor(COR_SINTAXE_VARIAVEL_ESPECIAL))
            self._log.append(f"\n✗  Falha:\n{msg or '(sem mensagem)'}")
            self._log.setTextColor(QColor(COR_CINZA_TEXTO))
            log.aviso(_ARQ, "ao_concluir", f"pip/migração falhou: {msg[:80]}")
        self._log.ensureCursorVisible()
        self.concluido.emit(sucesso)
