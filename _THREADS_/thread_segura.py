# _THREADS_/thread_segura.py
"""
_ThreadSegura — base class segura para QThread no hein IDE.

REGRA CRÍTICA: NUNCA conectar finished ao próprio deleteLater no MESMO objeto.

    thread.finished.connect(thread.deleteLater)  ← PROIBIDO
    → QThread: Destroyed while thread '' is still running → qFatal → abort()

CORRETO:
    thread.finished.connect(worker.deleteLater)  ← objetos DISTINTOS → OK
    Ou: usar parent= no construtor → Qt gerencia destruição automaticamente.

Ver BUG-202807-05 a BUG-202807-08 em nucleo/_DOC_ERROS_BUGS.txt

PROTEÇÃO COM (BUG-202807-14):
    No Windows/Python 3.14, shutil.which(), tempfile._mkstemp_inner() e outras
    chamadas de filesystem via C-extension disparam 0x8001010d em threads sem
    COM inicializado. _ThreadSegura.run() chama CoInitializeEx antes de
    executar e CoUninitialize no finally — todas as subclasses ficam protegidas
    automaticamente sem alterar o código de cada uma.
"""
import re
import inspect
import sys
import textwrap

from PySide6.QtCore import QThread


class _ThreadSegura(QThread):
    """
    Substitui QThread como base de todas as QThread subclasses do hein IDE.

    Proteções ativas
    ────────────────
    __init_subclass__ — detecta o padrão bugado NA DEFINIÇÃO da subclasse.
                        Roda uma única vez no import do módulo. Lança
                        RuntimeError imediatamente se encontrar o padrão.

    _encerrar_seguro  — implementação canônica de quit + wait + terminate
                        para callers usarem antes de criar nova instância.

    Toda subclasse DEVE ter run() definido e NÃO deve conectar
    self.finished → self.deleteLater (mesmo objeto = crash garantido).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # O diagnóstico fica na classe-base para cobrir também workers
        # antigos que não chamam event() no próprio run().
        try:
            self.finished.connect(self._registrar_finished_diagnostico)
        except Exception:
            pass

    def _registrar_finished_diagnostico(self):
        try:
            from _THREADS_.diagnostico_workers import thread_finished
            thread_finished(self)
        except Exception:
            pass

    def start(self, priority=QThread.InheritPriority):
        """Registra o início observado sem alterar o start nativo do Qt."""
        try:
            from _THREADS_.diagnostico_workers import thread_started
            thread_started(self)
        except Exception:
            pass
        return super().start(priority)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        # ── Verificação de padrão bugado ──────────────────────────────────
        try:
            src = textwrap.dedent(inspect.getsource(cls))
            m = re.search(
                r'(\b\w+\b)\.finished\.connect\s*\(\s*\1\.deleteLater\s*\)',
                src,
            )
            if m:
                raise RuntimeError(
                    f"\n[_ThreadSegura] PADRÃO BUGADO DETECTADO em '{cls.__name__}':\n"
                    f"  {m.group()!r}\n"
                    "  Este padrão causa:\n"
                    "    QThread: Destroyed while thread '' is still running"
                    " → qFatal → abort()\n"
                    "  Corrija: remova a linha ou use objetos DISTINTOS"
                    " (worker ≠ thread).\n"
                    "  Ref: BUG-202807-05 a BUG-202807-08 em"
                    " nucleo/_DOC_ERROS_BUGS.txt"
                )
        except (OSError, TypeError):
            # inspect.getsource() pode falhar em frozen/embedded — ignora
            pass

        # ── Proteção COM — BUG-202807-14 (Windows/Python 3.14) ───────────
        # shutil.which(), tempfile._mkstemp_inner() e outras chamadas de
        # filesystem via C-extension disparam 0x8001010d em QThreads sem COM
        # inicializado. Envolvemos run() de cada subclasse automaticamente em
        # CoInitializeEx / CoUninitialize para que nenhuma subclasse precise
        # fazer isso manualmente.
        # Aplica SOMENTE quando a subclasse define run() ela mesma (não herda).
        if sys.platform == "win32" and "run" in cls.__dict__:
            _orig_run = cls.__dict__["run"]

            def _run_com_protegido(self, _orig=_orig_run):
                import ctypes
                ctypes.windll.ole32.CoInitializeEx(None, 0)
                try:
                    _orig(self)
                finally:
                    ctypes.windll.ole32.CoUninitialize()

            _run_com_protegido.__name__ = "run"
            _run_com_protegido.__qualname__ = f"{cls.__qualname__}.run"
            cls.run = _run_com_protegido

    def _encerrar_seguro(
        self, ms_quit: int = 300, ms_terminate: int = 200
    ) -> None:
        """
        Encerra a thread de forma segura.

        Sequência: isRunning? → quit() → wait(ms_quit)
                             → [terminate() → wait(ms_terminate)]

        Uso recomendado no caller antes de criar nova instância:

            if self._minha_thread:
                self._minha_thread._encerrar_seguro()
            self._minha_thread = _MinhaThread(...)
        """
        if not self.isRunning():
            return
        self.quit()
        if not self.wait(ms_quit):
            self.terminate()
            self.wait(ms_terminate)
