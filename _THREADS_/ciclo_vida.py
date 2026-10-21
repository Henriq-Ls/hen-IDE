"""Politica comum de encerramento de recursos Qt."""
from __future__ import annotations

from PySide6.QtCore import QProcess, QThread


def _diagnosticar(evento: str, obj, **extra) -> None:
    """Emite diagnóstico sem jamais interferir no encerramento."""
    try:
        from _THREADS_.diagnostico_workers import event, task_for
        component = getattr(obj, "_hein_diag_component", "THREAD")
        task = task_for(obj)
        event(evento, component, task, obj=obj, **extra)
    except Exception:
        pass


def executar_shutdown(nome: str, callback) -> bool:
    """Executa uma etapa de encerramento sem abortar as etapas seguintes."""
    try:
        callback()
        return True
    except Exception as exc:
        try:
            from _LOG_.log import log
            log.erro("ciclo_vida.py", nome, str(exc))
        except Exception:
            pass
        return False


def encerrar_processo(processo: QProcess | None, timeout_ms: int = 1000) -> bool:
    """Encerra um QProcess e confirma que ele nao ficou rodando."""
    if processo is None:
        return True
    try:
        if processo.state() == QProcess.ProcessState.NotRunning:
            _diagnosticar("FINISHED", processo, state="NOT_RUNNING")
            return True
        _diagnosticar("QUIT_REQUESTED", processo, timeout_ms=timeout_ms)
        processo.terminate()
        _diagnosticar("WAIT_BEGIN", processo, timeout_ms=timeout_ms)
        if processo.waitForFinished(timeout_ms):
            _diagnosticar("WAIT_END", processo, completed=True)
            _diagnosticar("FINISHED", processo)
            return True
        _diagnosticar("WAIT_END", processo, completed=False)
        _diagnosticar("TERMINATE", processo)
        processo.kill()
        _diagnosticar("WAIT_BEGIN", processo, timeout_ms=500)
        finished = processo.waitForFinished(500)
        _diagnosticar("WAIT_END", processo, completed=finished)
        _diagnosticar("FINISHED", processo, completed=finished)
        return finished
    except RuntimeError:
        _diagnosticar("FINISHED", processo, runtime_error=True)
        return True


def encerrar_thread(thread: QThread | None, timeout_ms: int = 1500) -> bool:
    """Encerra uma QThread sem liberar a referencia enquanto ela estiver viva."""
    if thread is None:
        return True
    try:
        if not thread.isRunning():
            _diagnosticar("FINISHED", thread, state="NOT_RUNNING")
            return True
        _diagnosticar("QUIT_REQUESTED", thread, timeout_ms=timeout_ms)
        thread.quit()
        _diagnosticar("WAIT_BEGIN", thread, timeout_ms=timeout_ms)
        if thread.wait(timeout_ms):
            _diagnosticar("WAIT_END", thread, completed=True)
            _diagnosticar("FINISHED", thread, completed=True)
            return True
        _diagnosticar("WAIT_END", thread, completed=False)
        _diagnosticar("TERMINATE", thread)
        thread.terminate()
        _diagnosticar("WAIT_BEGIN", thread, timeout_ms=500)
        _finished = thread.wait(500)
        _diagnosticar("WAIT_END", thread, completed=_finished)
        _diagnosticar("FINISHED", thread, completed=_finished)
        return _finished
    except RuntimeError:
        _diagnosticar("FINISHED", thread, runtime_error=True)
        return True
