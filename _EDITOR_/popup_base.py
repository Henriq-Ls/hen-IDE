# 📁 _EDITOR_/popup_base.py
# -*- coding: utf-8 -*-
"""
PopupBase — base unificada para todos os popups flutuantes da hein IDE.

Todos os popups flutuantes do editor herdam daqui:
  - _PopupSugestoes  (corretor_ortografico.py)  — hover sobre palavra sublinhada
  - PopupQuickFix    (quick_fix.py)             — hover sobre erro de import
  - _ToastInstalando (quick_fix.py)             — spinner de instalação de pacote

═══════════════════════════════════════════════════════════════════
 REGRAS DE THREAD — LEIA ANTES DE USAR
═══════════════════════════════════════════════════════════════════

  Toda a API pública desta classe (mostrar, fechar, adiar_fechar,
  iniciar_fechar) DEVE ser chamada exclusivamente da main thread.
  Popups são widgets Qt — tocar qualquer método Qt de uma worker
  thread (QRunnable.run(), _ThreadSegura, threading.Thread) causa
  crash ou comportamento indefinido.

  Padrão correto:
    ┌─ worker thread ─────────────────────────────────────────┐
    │  resultado = calcular()                                  │
    │  self.signals.concluido.emit(resultado)  ← sinal puro   │
    └──────────────────────────────────────────────────────────┘
    ┌─ main thread (slot conectado por AutoConnection) ────────┐
    │  def _ao_concluir(self, resultado):                      │
    │      self._popup.mostrar(pos, ...)   ← OK aqui          │
    └──────────────────────────────────────────────────────────┘

  Se _posicionar_e_exibir() detectar que está sendo chamado fora
  da main thread, ele loga um aviso e aborta — nunca crasha.

═══════════════════════════════════════════════════════════════════

Uso básico:

    class MeuPopup(PopupBase):
        def __init__(self, editor):
            # fechar_ao_perder_foco=True  → fecha quando o foco sai do editor
            # debounce_ms=200             → fecha 200 ms após mouse sair
            super().__init__(
                editor.viewport(),
                fechar_ao_perder_foco=True,
                debounce_ms=0,
            )
            self._editor = editor
            self._construir_ui()
            self._aplicar_tema()

        def _editor_widget(self):
            return self._editor   # necessário para fechar_ao_perder_foco

        def _aplicar_tema(self):
            self._aplicar_estilo_base()           # fundo + borda + radius
            self._lbl.setStyleSheet(
                f"color: {self._cor_texto()}; background: transparent;"
            )

        def mostrar(self, pos_global, texto: str):
            self._lbl.setText(texto)
            self._posicionar_e_exibir(pos_global)  # ← sempre último
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Qt, QTimer
from PySide6.QtWidgets import QApplication, QFrame

from _THREADS_ import diagnostico_foco_temporario as _focus_trace

_ARQ = "popup_base.py"


def _tema():
    """Import lazy — evita circular no startup."""
    from _CONFIGURA_.gerenciador_tema import tema_global  # noqa: PLC0415
    return tema_global()


# ─── Base ─────────────────────────────────────────────────────────────────────

class PopupBase(QFrame):
    """
    QFrame flutuante com flags, tema e ciclo de vida padronizados.

    Parâmetros
    ----------
    parent                : widget pai (geralmente editor.viewport())
    fechar_ao_perder_foco : True  → fecha quando o foco sai do editor/popup
                            False → fecha só quando solicitado explicitamente
    debounce_ms           : > 0 → fecha após N ms sem hover (popups de mouse)
                            0   → sem debounce
    """

    def __init__(
        self,
        parent=None,
        *,
        fechar_ao_perder_foco: bool = False,
        debounce_ms: int = 0,
    ) -> None:
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        # WA_DeleteOnClose=False: o objeto é reutilizado — não destruir no hide()
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self._fechar_ao_perder_foco = fechar_ao_perder_foco

        # ── Debounce de fechamento (popups ativados por hover) ─────────────
        self._timer_fechar: QTimer | None = None
        if debounce_ms > 0:
            self._timer_fechar = QTimer(self)
            self._timer_fechar.setSingleShot(True)
            self._timer_fechar.setInterval(debounce_ms)
            self._timer_fechar.timeout.connect(self.hide)

        # ── Fechamento automático ao perder foco (popups de ação) ─────────
        if fechar_ao_perder_foco:
            app = QApplication.instance()
            if app is not None:
                _focus_trace.install(app)
                app.focusChanged.connect(self._ao_foco_mudar)
                app.applicationStateChanged.connect(self._ao_estado_app_mudar)

    # ── Cores do tema ─────────────────────────────────────────────────────

    def _cor_fundo(self) -> str:
        return _tema().cor("menu_contexto.fundo", "#1e1e2e")

    def _cor_borda(self) -> str:
        return _tema().cor("menu_contexto.borda", "#3a3a5a")

    def _cor_texto(self) -> str:
        return _tema().cor("menu_contexto.texto", "#d4d4d4")

    def _cor_texto_fraco(self) -> str:
        return _tema().cor("interface.texto_fraco", "#888888")

    def _cor_hover(self) -> str:
        return _tema().cor("menu_contexto.item_hover", "#2a4060")

    def _cor_destaque(self) -> str:
        """Acento — parâmetro ativo, palavra com erro ortográfico, etc."""
        return _tema().cor("editor.palavra_destaque", "#e5c07b")

    # ── Estilo base ───────────────────────────────────────────────────────

    def _aplicar_estilo_base(self) -> None:
        """
        Aplica fundo + borda + border-radius do QFrame usando o tema atual.
        Subclasses chamam isso no início do seu _aplicar_tema() e
        completam com os estilos específicos dos widgets filhos.
        """
        self.setStyleSheet(
            f"QFrame {{"
            f"  background-color: {self._cor_fundo()};"
            f"  border: 1px solid {self._cor_borda()};"
            f"  border-radius: 6px;"
            f"}}"
        )

    # ── Posicionamento e exibição ─────────────────────────────────────────

    def _posicionar_e_exibir(self, pos_global) -> None:
        """
        Posiciona e exibe o popup. Deve ser chamado ao FINAL do mostrar()
        da subclasse, depois que todo o conteúdo já foi preparado.

        Thread-guard: se chamado fora da main thread, loga e aborta.
        """
        app = QApplication.instance()
        if app is not None and QThread.currentThread() is not app.thread():
            try:
                from _LOG_.log import log
                log.aviso(_ARQ, "_posicionar_e_exibir",
                          "chamado fora da main thread — abortado")
            except Exception:
                pass
            return

        if self._timer_fechar is not None:
            self._timer_fechar.stop()

        self.adjustSize()
        self.move(pos_global)
        self.show()
        self.raise_()

    # ── API de debounce (popups de hover) ─────────────────────────────────

    def adiar_fechar(self) -> None:
        """Cancela o timer de fechamento — mouse entrou no popup."""
        if self._timer_fechar is not None:
            self._timer_fechar.stop()

    def iniciar_fechar(self) -> None:
        """Inicia o timer de fechamento por debounce. Sem debounce: fecha imediatamente."""
        if self._timer_fechar is not None:
            self._timer_fechar.start()
        else:
            self.hide()

    # ── Eventos de mouse do próprio popup ─────────────────────────────────

    def enterEvent(self, event) -> None:  # noqa: N802
        """Mouse entrou no popup — cancela o timer de fechamento."""
        self.adiar_fechar()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        """Mouse saiu do popup — inicia o timer de fechamento."""
        self.iniciar_fechar()
        super().leaveEvent(event)

    # ── Fechamento por perda de foco ──────────────────────────────────────

    def _editor_widget(self):
        """
        Retorna o widget do editor para checagem de foco.
        Obrigatório quando fechar_ao_perder_foco=True.
        """
        return None

    def _pertence_ao_popup(self, widget) -> bool:
        """True se `widget` é o próprio popup ou qualquer filho dele."""
        w = widget
        while w is not None:
            if w is self:
                return True
            w = w.parentWidget()
        return False

    def _ao_foco_mudar(self, _antigo, novo) -> None:
        """Fecha quando o foco vai pra qualquer widget que não seja o editor nem o popup."""
        _focus_trace.enter("popup_base", _antigo, novo)
        try:
            if not self.isVisible():
                return
            if novo is self._editor_widget() or self._pertence_ao_popup(novo):
                return
            _focus_trace.reaction("popup_base", "fechar")
            self.fechar()
        finally:
            _focus_trace.exit("popup_base")

    def _ao_estado_app_mudar(self, estado) -> None:
        """Fecha quando a janela do hein perde o foco pro SO (alt-tab, etc.)."""
        if not self.isVisible():
            return
        if estado != Qt.ApplicationActive:
            self.fechar()

    # ── API pública ───────────────────────────────────────────────────────

    def fechar(self) -> None:
        """Esconde o popup. Subclasses podem sobrescrever para reset adicional."""
        if self._timer_fechar is not None:
            self._timer_fechar.stop()
        self.hide()
