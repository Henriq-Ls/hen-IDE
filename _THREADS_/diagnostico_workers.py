"""Instrumentação de diagnóstico do ciclo de vida de workers da IDE.

Este módulo é deliberadamente passivo: não altera o ciclo de vida, sinais,
 herança ou política de encerramento dos workers. Em caso de falha do logger
 normal da aplicação, escreve diretamente em hein_workers.log para não perder a
 evidência do diagnóstico.
"""
from __future__ import annotations

import json
import os
import threading
import atexit
import weakref
import time
from datetime import datetime
from pathlib import Path

try:
    from _CONFIGURA_ import PASTA_APPDATA
except Exception:
    PASTA_APPDATA = os.path.join(
        os.path.expanduser("~"), "AppData", "Roaming", "hein"
    )

_LOCK = threading.RLock()
_CONTADORES: dict[str, int] = {}
_EDITORES: dict[int, int] = {}
_EDITOR_REFS: dict[int, weakref.ReferenceType] = {}
_ATIVOS: dict[str, dict] = {}
_EDITORES_CONECTADOS: set[int] = set()
_FOCO_CONECTADO = False
_EVENTOS_FINAIS = {"FINISHED", "DESTROYED"}
_EVENTOS_FLUSH = {
    "DESTROYED", "REFERENCE_GAP", "TERMINATE",
}
_LOG_FLUSH_EVENT_LIMIT = 50
_LOG_FLUSH_INTERVAL_SECONDS = 2.0
_EDIT_SAMPLE_INTERVAL = 25
_EDIT_LOG_STATE: dict[int, dict[str, float | int]] = {}
# Busca de interpretadores ocorre no boot/picker e está fora do escopo deste
# diagnóstico. Só pode ser reativada explicitamente para uma investigação
# separada, sem contaminar o log normal de edição/colagem.
_PYTHON_SEARCH_DIAGNOSTICS = os.environ.get(
    "HEIN_DIAG_PYTHON_SEARCH", ""
).strip().lower() in {"1", "true", "yes", "on"}
_LOG_HANDLE = None
_LOG_EVENTS_SINCE_FLUSH = 0
_LOG_LAST_FLUSH_MONOTONIC = 0.0


def _arquivo_log() -> Path:
    return Path(PASTA_APPDATA) / "hein_workers.log"


def _abrir_log() -> None:
    """Cria uma sessão limpa e mantém o arquivo aberto durante o processo."""
    global _LOG_HANDLE, _LOG_EVENTS_SINCE_FLUSH, _LOG_LAST_FLUSH_MONOTONIC
    with _LOCK:
        if _LOG_HANDLE is not None and not _LOG_HANDLE.closed:
            return
        try:
            caminho = _arquivo_log()
            caminho.parent.mkdir(parents=True, exist_ok=True)
            # Assim como o log operacional, cada processo começa uma sessão
            # nova. O handle permanece aberto para evitar abrir o arquivo em
            # cada evento dentro da thread do worker.
            _LOG_HANDLE = caminho.open(
                mode="w", encoding="utf-8"
            )
            _LOG_EVENTS_SINCE_FLUSH = 0
            _LOG_LAST_FLUSH_MONOTONIC = time.monotonic()
        except Exception:
            _LOG_HANDLE = None


_abrir_log()


def _fechar_log() -> None:
    """Faz flush e fecha o arquivo de diagnóstico no fim do processo."""
    global _LOG_HANDLE
    with _LOCK:
        if _LOG_HANDLE is None:
            return
        try:
            _LOG_HANDLE.flush()
            _LOG_HANDLE.close()
        except Exception:
            pass
        finally:
            _LOG_HANDLE = None


atexit.register(_fechar_log)


def _seguro(valor, padrao=""):
    try:
        return valor() if callable(valor) else valor
    except Exception:
        return padrao


def _weak_editor(editor):
    """Retorna apenas uma referência fraca ao editor para o contexto do logger."""
    if editor is None:
        return None
    try:
        return weakref.ref(editor)
    except TypeError:
        return None


def weak_editor(editor):
    """Versão pública para módulos instrumentados armazenarem contexto fraco."""
    return _weak_editor(editor)


def _desreferenciar(valor):
    if isinstance(valor, weakref.ReferenceType):
        return _seguro(valor, None)
    return valor


def _editor_info(editor):
    editor = _desreferenciar(editor)
    if editor is None:
        return 0, ""
    caminho = _seguro(lambda: getattr(editor, "file_path", None), "") or ""
    return id(editor), str(caminho)


def _qt_thread_id() -> str:
    try:
        from PySide6.QtCore import QThread
        return str(id(QThread.currentThread()))
    except Exception:
        return ""


def _context(obj=None, editor=None) -> dict:
    if editor is None and obj is not None:
        editor = _seguro(lambda: getattr(obj, "_hein_diag_editor", None))
    editor = _desreferenciar(editor)
    editor_id, arquivo = _editor_info(editor)
    py_id = id(obj) if obj is not None else 0
    return {
        "editor_id": editor_id,
        "arquivo": arquivo,
        "py_id": py_id,
        "qt_thread": _qt_thread_id(),
        "native_thread_id": threading.get_ident(),
    }


def _write(evento: str, component: str, task: str,
           edit_generation: int = 0, obj=None, editor=None,
           flush: bool = False, **extra) -> None:
    global _LOG_EVENTS_SINCE_FLUSH, _LOG_LAST_FLUSH_MONOTONIC
    dados = {
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        "event": evento,
        "component": component,
        "task": task or "-",
        "edit_generation": int(edit_generation or 0),
    }
    dados.update(_context(obj, editor))
    dados.update(extra)
    linha = "[WORKER_DIAG] " + " ".join(
        f"{chave}={json.dumps(valor, ensure_ascii=False, default=str)}"
        for chave, valor in dados.items()
    )
    try:
        with _LOCK:
            if _LOG_HANDLE is None or _LOG_HANDLE.closed:
                _abrir_log()
            if _LOG_HANDLE is not None:
                _LOG_HANDLE.write(linha + "\n")
                _LOG_EVENTS_SINCE_FLUSH += 1
                agora = time.monotonic()
                periodic_flush = (
                    _LOG_EVENTS_SINCE_FLUSH >= _LOG_FLUSH_EVENT_LIMIT
                    or agora - _LOG_LAST_FLUSH_MONOTONIC
                    >= _LOG_FLUSH_INTERVAL_SECONDS
                )
                if flush or periodic_flush:
                    _LOG_HANDLE.flush()
                    _LOG_EVENTS_SINCE_FLUSH = 0
                    _LOG_LAST_FLUSH_MONOTONIC = agora
    except Exception:
        pass


def event(evento: str, component: str, task: str,
          obj=None, editor=None, edit_generation: int | None = None,
          **extra) -> None:
    """Registra um evento padronizado sem deixar exceção escapar."""
    if component == "PYTHON_SEARCH" and not _PYTHON_SEARCH_DIAGNOSTICS:
        return
    if edit_generation is None:
        edit_generation = _seguro(
            lambda: getattr(obj, "_hein_diag_edit_generation", 0), 0
        )
    if evento == "EDIT":
        editor_id = _seguro(
            lambda: int(extra.get("editor_id") or _editor_info(editor)[0]),
            0,
        )
        agora = time.monotonic()
        with _LOCK:
            estado = _EDIT_LOG_STATE.setdefault(
                editor_id,
                {"last_generation": 0, "last_logged_at": 0.0, "suppressed": 0},
            )
            ultima_geracao = int(estado["last_generation"])
            ultimo_log = float(estado["last_logged_at"])
            suprimidos = int(estado["suppressed"])
            deve_logar = (
                edit_generation == 1
                or edit_generation - ultima_geracao >= _EDIT_SAMPLE_INTERVAL
                or agora - ultimo_log >= 1.0
            )
            if not deve_logar:
                estado["suppressed"] = suprimidos + 1
                return
            estado["last_generation"] = int(edit_generation or 0)
            estado["last_logged_at"] = agora
            estado["suppressed"] = 0
        extra = {
            **extra,
            "sampled": True,
            "suppressed_edits_since_previous_sample": suprimidos,
        }
    _write(
        evento, component, task, edit_generation, obj, editor,
        flush=evento in _EVENTOS_FLUSH, **extra
    )
    if task and evento in _EVENTOS_FINAIS:
        with _LOCK:
            _ATIVOS.pop(task, None)


def new_task(component: str, editor=None, edit_generation: int | None = None) -> str:
    prefixo = {
        "OUTLINE": "OUTLINE",
        "IMPORT": "IMPORT",
        "OUTLINEBUSCA": "OUTLINEBUSCA",
        "DIFF": "DIFF",
        "LINT": "LINT",
        "CORRETOR": "CORRETOR",
        "REINDEX": "REINDEX",
        "AC": "AC",
        "FIND_FILES": "FIND_FILES",
        "INDEX": "INDEX",
        "ANALISE": "ANALISE",
        "VENV": "VENV",
        "CLONE": "CLONE",
        "PYTHON_SEARCH": "PYTHON_SEARCH",
    }.get(component, component.upper())
    with _LOCK:
        _CONTADORES[prefixo] = _CONTADORES.get(prefixo, 0) + 1
        task = f"{prefixo}-{_CONTADORES[prefixo]:04d}"
        if component != "PYTHON_SEARCH" or _PYTHON_SEARCH_DIAGNOSTICS:
            _ATIVOS[task] = {
                "component": component,
                "editor": _weak_editor(editor),
                "editor_id": id(editor) if editor is not None else 0,
                "edit_generation": int(edit_generation or 0),
            }
    event("CREATE", component, task, editor=editor,
          edit_generation=edit_generation or 0)
    return task


def bind(obj, component: str, task: str, editor=None,
         edit_generation: int | None = None) -> str:
    """Associa task e contexto a um objeto Python/Qt."""
    if obj is None:
        return task
    if edit_generation is None:
        edit_generation = _seguro(
            lambda: _ATIVOS.get(task, {}).get("edit_generation", 0), 0
        )
    try:
        obj._hein_diag_task = task
        obj._hein_diag_component = component
        obj._hein_diag_editor = _weak_editor(editor)
        obj._hein_diag_edit_generation = int(edit_generation or 0)
        with _LOCK:
            if task in _ATIVOS:
                _ATIVOS[task]["object"] = _weak_editor(obj)
    except Exception:
        pass
    event("OBJECT_BOUND", component, task, obj=obj, editor=editor,
          edit_generation=edit_generation or 0)
    try:
        destroyed = getattr(obj, "destroyed", None)
        if destroyed is not None and not getattr(obj, "_hein_diag_destroyed_connected", False):
            obj._hein_diag_destroyed_connected = True
            editor_ref = _weak_editor(editor)
            destroyed.connect(
                lambda *_args, o_id=id(obj), c=component, t=task,
                e_ref=editor_ref, e_id=id(editor) if editor is not None else 0,
                g=int(edit_generation or 0):
                _write("DESTROYED", c, t, g, obj=None, editor=e_ref,
                       flush=True, destroyed_py_id=o_id, editor_id=e_id)
            )
    except Exception:
        pass
    return task


def ensure_task(obj, component: str, editor=None,
                edit_generation: int | None = None) -> str:
    """Garante uma tarefa para workers legados ainda sem instrumentação."""
    if obj is None:
        return ""
    task = task_for(obj)
    if task:
        return task
    task = new_task(component, editor, edit_generation)
    return bind(obj, component, task, editor, edit_generation)


def task_for(obj, default_component: str = "WORKER") -> str:
    return str(_seguro(lambda: getattr(obj, "_hein_diag_task", ""), "") or "")


def attach_editor(editor) -> None:
    global _FOCO_CONECTADO
    if editor is None:
        return
    editor_id = id(editor)
    with _LOCK:
        if editor_id in _EDITORES_CONECTADOS:
            return
        _EDITORES_CONECTADOS.add(editor_id)
        _EDITORES.setdefault(editor_id, 0)
        editor_ref = _weak_editor(editor)
        if editor_ref is not None:
            _EDITOR_REFS[editor_id] = editor_ref
    event("EDITOR_CREATED", "EDITOR", f"EDITOR-{editor_id:016x}", obj=editor,
          editor=editor, edit_generation=_EDITORES[editor_id])
    try:
        editor_ref = _weak_editor(editor)
        if editor_ref is None:
            with _LOCK:
                _EDITORES_CONECTADOS.discard(editor_id)
            return
        editor.textChanged.connect(
            lambda *_args, e_ref=editor_ref: edit_changed(_desreferenciar(e_ref))
        )
        editor.destroyed.connect(
            lambda *_args, e_id=editor_id, e_ref=editor_ref:
            _editor_destroyed(e_id, e_ref)
        )
        if not _FOCO_CONECTADO:
            try:
                from PySide6.QtWidgets import QApplication
                app = QApplication.instance()
                if app is not None:
                    app.focusChanged.connect(_registrar_foco)
                    _FOCO_CONECTADO = True
            except Exception:
                pass
    except Exception:
        pass


def edit_changed(editor) -> int:
    if editor is None:
        return 0
    editor_id = id(editor)
    with _LOCK:
        _EDITORES[editor_id] = _EDITORES.get(editor_id, 0) + 1
        generation = _EDITORES[editor_id]
    event("EDIT", "EDITOR", f"EDITOR-{editor_id:016x}", obj=editor,
          editor=editor, edit_generation=generation)
    return generation


def edit_generation(editor) -> int:
    return _EDITORES.get(id(editor), 0) if editor is not None else 0


def reference(action: str, component: str, owner, attr: str,
              before=None, after=None, editor=None, task: str = "",
              **extra) -> None:
    event("REFERENCE_" + action.upper(), component, task or task_for(before),
          obj=owner, editor=editor, before_py_id=id(before) if before else 0,
          after_py_id=id(after) if after else 0, attribute=attr, **extra)


def start_requested(obj, component: str | None = None, task: str = "") -> None:
    component = component or _seguro(lambda: getattr(obj, "_hein_diag_component", "WORKER"), "WORKER")
    task = task or task_for(obj)
    event("START_REQUESTED", component, task, obj=obj)


def result_emitted(obj, component: str | None = None, task: str = "",
                   **extra) -> None:
    component = component or _seguro(lambda: getattr(obj, "_hein_diag_component", "WORKER"), "WORKER")
    task = task or task_for(obj)
    event("RESULT_EMITTED", component, task, obj=obj, **extra)


def thread_started(obj, component: str | None = None, task: str = "") -> None:
    """Registra o pedido efetivo de início de uma QThread."""
    start_requested(obj, component, task)


def thread_finished(obj, component: str | None = None, task: str = "",
                    **extra) -> None:
    """Registra o término observado de uma QThread."""
    component = component or _seguro(
        lambda: getattr(obj, "_hein_diag_component", "THREAD"), "THREAD"
    )
    task = task or task_for(obj)
    event("FINISHED", component, task, obj=obj, **extra)


def active_tasks(editor) -> list[dict]:
    editor = _desreferenciar(editor)
    editor_id = id(editor) if editor is not None else 0
    return active_tasks_by_id(editor_id)


def active_tasks_by_id(editor_id: int) -> list[dict]:
    with _LOCK:
        tarefas = []
        for task, info in _ATIVOS.items():
            if info.get("editor_id", 0) == editor_id:
                tarefas.append({"task": task, "component": info.get("component")})
        return tarefas


def _editor_destroyed(editor_id: int, editor_ref) -> None:
    """Registra destruição sem precisar manter o editor vivo no callback."""
    _write("EDITOR_DESTROYED", "EDITOR", f"EDITOR-{editor_id:016x}",
           _EDITORES.get(editor_id, 0), obj=None, editor=editor_ref,
           active_tasks=active_tasks_by_id(editor_id), editor_id=editor_id)
    with _LOCK:
        _EDITORES_CONECTADOS.discard(editor_id)
        _EDITOR_REFS.pop(editor_id, None)
        _EDITORES.pop(editor_id, None)


def _editor_ancestor(widget):
    """Identifica um editor também quando o foco está em um filho dele."""
    atual = widget
    while atual is not None:
        atual_id = id(atual)
        editor_ref = _EDITOR_REFS.get(atual_id)
        if editor_ref is not None and _desreferenciar(editor_ref) is atual:
            return atual
        atual = _seguro(lambda: atual.parent(), None)
    return None


def _registrar_foco(anterior, novo) -> None:
    antigo_editor = _editor_ancestor(anterior)
    novo_editor = _editor_ancestor(novo)
    if antigo_editor is None and novo_editor is None:
        return
    novo_id = id(novo_editor) if novo_editor is not None else 0
    antigo_id = id(antigo_editor) if antigo_editor is not None else 0
    event("EDITOR_FOCUS", "EDITOR",
          f"EDITOR-{novo_id:016x}" if novo_id else f"EDITOR-{antigo_id:016x}",
          obj=novo_editor or antigo_editor, editor=novo_editor or antigo_editor,
          previous_editor_id=antigo_id, current_editor_id=novo_id)


def check_live_without_reference(owner, attr: str, component: str,
                                 editor=None) -> None:
    """Registra workers vivos quando o dono já zerou a referência principal."""
    try:
        if getattr(owner, attr, object()) is not None:
            return
    except Exception:
        return
    editor_id = id(editor) if editor is not None else 0
    with _LOCK:
        candidatos = [
            (task, info.copy()) for task, info in _ATIVOS.items()
            if info.get("component") == component
            and info.get("editor_id", 0) == editor_id
        ]
    for task, info in candidatos:
        objeto = _desreferenciar(info.get("object"))
        try:
            vivo = bool(objeto is not None and objeto.isRunning())
        except Exception:
            vivo = False
        if vivo:
            event("REFERENCE_GAP", component, task, obj=objeto,
                  editor=editor, owner_py_id=id(owner), attribute=attr,
                  reference_is_none=True)