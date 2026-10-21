"""Instrumentação temporária para provar reentrância de focusChanged.

Este módulo é deliberadamente separado de diagnostico_workers.py e deve ser
removido após a investigação. Não altera foco nem fecha widgets.
"""
from __future__ import annotations

from collections import deque
import logging
import sys
from time import monotonic

from _LOG_.log import log


_ARQ = "diagnostico_foco_temporario.py"
_JANELA_SEGUNDOS = 0.2
_FOCUS_TIMES: deque[float] = deque()
_FOCUS_SEQUENCE = 0
_CALL_DEPTH = 0
_INSTALLED = False


def _widget_info(widget) -> str:
    if widget is None:
        return "None"
    try:
        nome = widget.objectName()
    except Exception:
        nome = ""
    return f"{type(widget).__name__}({nome})" if nome else type(widget).__name__


def _emitir(mensagem: str) -> None:
    try:
        log.aviso(_ARQ, "focus_trace", mensagem)
    except Exception as exc:
        # A instrumentação nunca pode interferir no fluxo do editor. Ainda
        # assim, uma falha do logger não pode desaparecer completamente:
        # registra no logger stdlib já configurado e, se ele também falhar,
        # deixa uma evidência mínima no stderr.
        fallback = (
            f"{_ARQ} › focus_trace — LOGGER_ERROR "
            f"mensagem={mensagem!r} erro={exc!r}"
        )
        try:
            logging.getLogger("hein").error(fallback)
        except Exception:
            try:
                sys.stderr.write(fallback + "\n")
                sys.stderr.flush()
            except Exception:
                pass


def install(app) -> None:
    """Instala uma única observação global antes dos listeners instrumentados."""
    global _INSTALLED
    if _INSTALLED:
        return
    if app is None:
        _emitir("INSTALL_ERROR app=None")
        return
    try:
        app.focusChanged.connect(_ao_focus_changed)
        _INSTALLED = True
        _emitir(
            "INSTALL ok "
            f"app={type(app).__name__} "
            f"thread={type(app.thread()).__name__}"
        )
    except Exception as exc:
        _emitir(f"INSTALL_ERROR erro={exc!r}")


def _ao_focus_changed(anterior, novo) -> None:
    """Registra cada emissão real, inclusive emissões aninhadas."""
    global _FOCUS_SEQUENCE
    agora = monotonic()
    _FOCUS_TIMES.append(agora)
    limite = agora - _JANELA_SEGUNDOS
    while _FOCUS_TIMES and _FOCUS_TIMES[0] < limite:
        _FOCUS_TIMES.popleft()
    _FOCUS_SEQUENCE += 1
    _emitir(
        "SIGNAL "
        f"seq={_FOCUS_SEQUENCE} "
        f"depth={_CALL_DEPTH} "
        f"count_200ms={len(_FOCUS_TIMES)} "
        f"anterior={_widget_info(anterior)} "
        f"novo={_widget_info(novo)}"
    )


def enter(listener: str, anterior, novo) -> int:
    """Marca a entrada de um listener e denuncia chamada reentrante."""
    global _CALL_DEPTH
    _CALL_DEPTH += 1
    agora = monotonic()
    while _FOCUS_TIMES and _FOCUS_TIMES[0] < agora - _JANELA_SEGUNDOS:
        _FOCUS_TIMES.popleft()
    mensagem = (
        f"ENTER listener={listener} depth={_CALL_DEPTH} "
        f"count_200ms={len(_FOCUS_TIMES)} "
        f"anterior={_widget_info(anterior)} novo={_widget_info(novo)}"
    )
    if _CALL_DEPTH > 1:
        mensagem = "REENTRANT " + mensagem
    _emitir(mensagem)
    return _CALL_DEPTH


def reaction(listener: str, action: str) -> None:
    """Marca a ação que pode provocar uma nova emissão de foco."""
    _emitir(
        f"REACTION listener={listener} action={action} depth={_CALL_DEPTH}"
    )


def exit(listener: str) -> None:
    """Registra a saída e restaura a profundidade global."""
    global _CALL_DEPTH
    _emitir(f"EXIT listener={listener} depth={_CALL_DEPTH}")
    _CALL_DEPTH = max(0, _CALL_DEPTH - 1)