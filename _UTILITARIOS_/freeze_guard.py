# _UTILITARIOS_/freeze_guard.py
"""
FreezeGuard — proteção global contra freeze de UI no hein IDE.

Três formas de uso:
────────────────────────────────────────────────────────────────────────────

1. CONTEXT MANAGER (qualquer operação lenta):

    from _UTILITARIOS_.freeze_guard import FreezeGuard

    with FreezeGuard(self, "Carregando projeto..."):
        operacao_pesada()

    # Com callbacks deferred (QTimer.singleShot) após o bloco:
    with FreezeGuard(self, "Carregando...", fechar_apos_ms=1500):
        self._iniciar_trabalho_deferred()   # agenda QTimer callbacks

2. DECORATOR (métodos de instância que herdam de QWidget):

    from _UTILITARIOS_.freeze_guard import operacao_lenta

    @operacao_lenta("Indexando arquivos...")
    def _reindexar(self):
        ...   # self deve ser QWidget ou ter janela_pai()

3. MONITOR DE HEARTBEAT (detecta qualquer freeze ≥ threshold):

    # Em MainWindow.__init__:
    from _UTILITARIOS_.freeze_guard import HeartbeatMonitor
    self._freeze_monitor = HeartbeatMonitor(threshold_ms=800)
    self._freeze_monitor.freeze_detectado.connect(self._ao_freeze)
    self._freeze_monitor.iniciar()

    def _ao_freeze(self, duracao_ms: int):
        log.aviso("main_window", "_ao_freeze",
                  f"main thread travou por ~{duracao_ms}ms")

────────────────────────────────────────────────────────────────────────────
LIMITAÇÃO IMPORTANTE
────────────────────────────────────────────────────────────────────────────
Enquanto a main thread executa código síncrono pesado, o event loop está
parado — o spinner congela. O overlay bloqueia cliques e é visível, mas
não anima durante o freeze. A animação volta quando o event loop retorna.

Para animação contínua durante o trabalho, o único caminho é mover a
operação para _ThreadSegura (QThread). O FreezeGuard é a solução prática
enquanto isso não é feito.
"""

from __future__ import annotations

import functools
import threading
import time
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal, Qt
from PySide6.QtWidgets import QApplication, QWidget


# ─────────────────────────────────────────────────────────────────────────────
# FreezeGuard — context manager
# ─────────────────────────────────────────────────────────────────────────────

class FreezeGuard:
    """
    Exibe LoadingOverlay durante operações lentas na main thread.

    Parâmetros
    ----------
    parent        : QWidget pai (normalmente self / MainWindow)
    mensagem      : texto exibido no overlay
    fechar_apos_ms: ms EXTRAS de espera após o __exit__ antes de fechar.
                    Use quando há QTimer.singleShot callbacks deferred que
                    rodam DEPOIS do bloco 'with' mas antes da UI ficar livre.
                    Exemplo: fechar_apos_ms=1500 cobre callbacks de até 1.5s.
    limiar_ms     : operações mais curtas que isso NÃO mostram overlay.
                    Padrão=0 (sempre mostra). Use >0 para operações que
                    às vezes são rápidas e só ocasionalmente lentas.
    """

    def __init__(
        self,
        parent: QWidget,
        mensagem: str = "Aguarde...",
        fechar_apos_ms: int = 0,
        limiar_ms: int = 0,
    ) -> None:
        self._parent        = parent
        self._mensagem      = mensagem
        self._fechar_apos   = fechar_apos_ms
        self._limiar_ms     = limiar_ms
        self._overlay       = None
        self._inicio        = 0.0
        self._timer_fechar  = None

    # ── API de context manager ────────────────────────────────────────────

    def __enter__(self) -> "FreezeGuard":
        from _UTILITARIOS_.loading_overlay import LoadingOverlay
        from _LOG_.log import log

        self._inicio = time.monotonic()

        if self._limiar_ms > 0:
            # Cria o overlay mas não mostra ainda — aguarda o limiar
            # NOTA: como a main thread vai bloquear, o timer nunca vai disparar
            # durante o trabalho. Portanto, se limiar_ms > 0, o overlay só
            # aparece se for chamado manualmente via forçar_exibir().
            # Para uso simples, mantenha limiar_ms=0 (padrão).
            self._overlay = LoadingOverlay(self._parent, mensagem=self._mensagem)
        else:
            self._overlay = LoadingOverlay(self._parent, mensagem=self._mensagem)
            self._overlay.show()
            QApplication.processEvents()
            log.info("freeze_guard.py", "FreezeGuard.__enter__",
                     f"overlay exibido: {self._mensagem!r}")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        from _LOG_.log import log

        duracao_ms = int((time.monotonic() - self._inicio) * 1000)
        log.info("freeze_guard.py", "FreezeGuard.__exit__",
                 f"operação concluída em {duracao_ms}ms — "
                 f"fechar_apos_ms={self._fechar_apos}")

        if self._overlay is None:
            return False

        if self._fechar_apos > 0:
            # Mantém overlay aberto para cobrir callbacks deferred.
            # Parent = self._parent (QWidget): sem parent, o QTimer não tem
            # dono Qt e é destruído pelo GC Python quando FreezeGuard sai de
            # escopo (FreezeGuard não é QObject), matando o timer antes de
            # disparar e deixando o overlay preso na tela para sempre.
            # O closure captura _ov diretamente para não depender de self
            # após o GC coletar o FreezeGuard.
            _ov = self._overlay
            def _fechar_deferred(_o=_ov):
                if _o and not _o._fechado:
                    _o.fechar()
            self._timer_fechar = QTimer(self._parent)
            self._timer_fechar.setSingleShot(True)
            self._timer_fechar.timeout.connect(_fechar_deferred)
            self._timer_fechar.start(self._fechar_apos)
        else:
            self._fechar_agora()

        return False   # não suprime exceções

    def _fechar_agora(self) -> None:
        from _LOG_.log import log
        if self._overlay and not self._overlay._fechado:
            self._overlay.fechar()
            log.info("freeze_guard.py", "FreezeGuard._fechar_agora", "overlay fechado")
        self._overlay = None

    # ── API de controle em tempo de execução ─────────────────────────────

    def set_mensagem(self, texto: str) -> None:
        """Atualiza o texto do overlay durante a operação."""
        if self._overlay:
            self._overlay.set_mensagem(texto)

    def fechar_agora(self) -> None:
        """Fecha o overlay imediatamente, ignorando fechar_apos_ms."""
        if self._timer_fechar:
            self._timer_fechar.stop()
        self._fechar_agora()


# ─────────────────────────────────────────────────────────────────────────────
# Decorator @operacao_lenta
# ─────────────────────────────────────────────────────────────────────────────

def operacao_lenta(
    mensagem: str = "Aguarde...",
    fechar_apos_ms: int = 0,
    obter_parent: Callable | None = None,
):
    """
    Decorator para métodos que podem travar a UI.

    O método DEVE pertencer a uma classe cujo self é QWidget, ou você deve
    fornecer obter_parent: uma função que recebe (self) e retorna o QWidget pai.

    Exemplos:

        @operacao_lenta("Carregando projeto...")
        def _meu_metodo(self):
            ...   # self é QWidget

        @operacao_lenta("Salvando...", obter_parent=lambda s: s.janela_pai)
        def _salvar(self):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self_obj, *args, **kwargs):
            if obter_parent is not None:
                parent = obter_parent(self_obj)
            elif isinstance(self_obj, QWidget):
                parent = self_obj
            else:
                # Sem parent válido — executa sem overlay
                return func(self_obj, *args, **kwargs)

            with FreezeGuard(parent, mensagem, fechar_apos_ms=fechar_apos_ms):
                return func(self_obj, *args, **kwargs)

        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# HeartbeatMonitor — detecta freezes da main thread
# ─────────────────────────────────────────────────────────────────────────────

class HeartbeatMonitor(QObject):
    """
    Monitora a responsividade da main thread via heartbeat.

    Um QTimer na main thread atualiza um timestamp a cada `intervalo_ms`.
    Uma thread de OS verifica se o timestamp está ficando velho.
    Se o atraso ultrapassar `threshold_ms`, emite `freeze_detectado`.

    IMPORTANTE: este monitor DETECTA e LOGA freezes, mas NÃO pode mostrar
    UI durante o freeze (a main thread está bloqueada). Use FreezeGuard para
    mostrar o overlay ANTES da operação lenta.

    Uso:
        self._monitor = HeartbeatMonitor(threshold_ms=800)
        self._monitor.freeze_detectado.connect(self._ao_freeze)
        self._monitor.iniciar()

        # Para ao fechar a janela:
        self._monitor.parar()
    """

    freeze_detectado = Signal(int)   # duração estimada do freeze em ms

    def __init__(
        self,
        parent: QObject | None = None,
        threshold_ms: int = 800,
        intervalo_ms: int = 100,
    ) -> None:
        super().__init__(parent)
        self._threshold  = threshold_ms / 1000.0
        self._intervalo  = intervalo_ms / 1000.0
        self._ultimo_bat = time.monotonic()
        self._ativo      = False
        self._thread: threading.Thread | None = None

        # Timer na main thread — atualiza o heartbeat
        self._timer = QTimer(self)
        self._timer.setInterval(intervalo_ms)
        self._timer.timeout.connect(self._bater_coracao)

    def iniciar(self) -> None:
        """Inicia o monitor. Chamar em MainWindow.__init__ após a UI estar pronta."""
        if self._ativo:
            return
        self._ativo = True
        self._ultimo_bat = time.monotonic()
        self._timer.start()
        self._thread = threading.Thread(
            target=self._loop_monitor,
            name="HeartbeatMonitor",
            daemon=True,
        )
        self._thread.start()

    def parar(self) -> None:
        """Para o monitor. Chamar em closeEvent."""
        self._ativo = False
        self._timer.stop()

    def _bater_coracao(self) -> None:
        self._ultimo_bat = time.monotonic()

    def _loop_monitor(self) -> None:
        """Roda em thread de OS — só lê/escreve variáveis thread-safe."""
        _em_freeze = False
        _inicio_freeze = 0.0

        while self._ativo:
            time.sleep(self._intervalo)
            agora = time.monotonic()
            atraso = agora - self._ultimo_bat

            if atraso >= self._threshold:
                if not _em_freeze:
                    _em_freeze = True
                    _inicio_freeze = agora
            else:
                if _em_freeze:
                    _em_freeze = False
                    duracao_ms = int((agora - _inicio_freeze) * 1000)
                    # Emite via QueuedConnection — só processa quando a
                    # main thread voltar a ter event loop ativo.
                    self.freeze_detectado.emit(duracao_ms)
