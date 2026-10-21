# 📁 _EDITOR_/Funcionalidades/validador_imports.py
# -*- coding: utf-8 -*-
"""
Detecção de imports inválidos — sublinha em vermelho/amarelo imports que não
existem, igual ao VS Code e PyCharm.

Como funciona:
    1. Observa textChanged com debounce de 800ms
    2. Faz parse AST do arquivo atual
    3. Para cada import, tenta resolver o módulo:
         a) stdlib do Python
         b) Pacotes instalados (.venv / site-packages)
         c) Arquivos .py do projeto (inclui namespace packages)
    4. Import inválido → sublinha wave via setExtraSelections
    5. Emite erros_detectados {linha: "error"|"warning"} para ReguaErros e gutter
    6. Fallback por regex quando o arquivo inteiro tem SyntaxError

Uso (em Editor.py, no __init__):
    from .Funcionalidades.validador_imports import ValidadorImports
    self._validador_imports = ValidadorImports(self)
"""
import ast
import os
import re
import sys
from PySide6.QtCore    import Qt, QObject, QTimer, QThread, Signal
from _THREADS_.thread_segura import _ThreadSegura
from PySide6.QtGui     import QTextCharFormat, QColor, QTextCursor
from PySide6.QtWidgets import QTextEdit
from _LOG_.log   import log
from _THREADS_.diagnostico_workers import bind, event, reference, weak_editor
_ARQ     = "validador_imports.py"

# Mantém referências a _ThreadValidador até finished — evita GC prematuro
# quando ValidadorImports é destruído antes de run() retornar (BUG-202807-12).
_threads_vivas_validador: set = set()

_IGNORAR = {".venv", "__pycache__", ".git", ".hein", "node_modules",
            ".mypy_cache", ".pytest_cache"}

# Cache de stdlib (Python 3.10+)
try:
    _STDLIB = sys.stdlib_module_names  # type: ignore
except AttributeError:
    import sys as _sys
    _STDLIB = frozenset(_sys.modules.keys()) | {
        "os", "sys", "re", "ast", "json", "math", "time", "datetime",
        "pathlib", "typing", "collections", "itertools", "functools",
        "threading", "subprocess", "tempfile", "shutil", "copy",
        "string", "random", "hashlib", "io", "abc", "enum", "dataclasses",
        "contextlib", "inspect", "importlib", "logging", "warnings",
        "traceback", "unittest", "argparse", "struct", "socket",
        "http", "urllib", "email", "html", "xml", "csv", "sqlite3",
        "pickle", "shelve", "gzip", "zipfile", "tarfile", "base64",
        "uuid", "platform", "signal", "queue", "weakref",
        "gc", "dis", "tokenize", "token", "keyword", "builtins",
    }

class _ThreadValidador(_ThreadSegura):
    """
    Roda toda a verificação de imports em background — nunca bloqueia a UI thread.
    Recebe apenas dados puros (str) do editor; não toca nenhum objeto Qt.
    """
    concluido = Signal(object)  # {linha: "error"|"warning"}

    def __init__(self, codigo: str, projeto: str, venv: str,
                 task: str = "", editor=None, edit_generation: int = 0):
        super().__init__()
        self._codigo  = codigo
        self._projeto = projeto
        self._venv    = venv
        self._hein_diag_task = task
        self._hein_diag_component = "IMPORT"
        self._hein_diag_editor = weak_editor(editor)
        self._hein_diag_edit_generation = edit_generation

    def run(self):
        if self.isInterruptionRequested():
            event("RUN_CANCELLED", "IMPORT", self._hein_diag_task, obj=self,
                  editor=self._hein_diag_editor, phase="before_run")
            return

        event("RUN_ENTER", "IMPORT", self._hein_diag_task, obj=self,
              editor=self._hein_diag_editor)
        linhas: dict[int, str] = {}
        try:
            arvore = ast.parse(self._codigo, filename="<editor>")
        except SyntaxError:
            if self.isInterruptionRequested():
                event("RUN_CANCELLED", "IMPORT", self._hein_diag_task,
                      obj=self, editor=self._hein_diag_editor,
                      phase="syntax_error")
                return
            self._regex(self._codigo, linhas)
            if self.isInterruptionRequested():
                event("RUN_CANCELLED", "IMPORT", self._hein_diag_task,
                      obj=self, editor=self._hein_diag_editor,
                      phase="syntax_error_result")
                return
            self.concluido.emit(linhas)
            event("RESULT_EMITTED", "IMPORT", self._hein_diag_task, obj=self,
                  editor=self._hein_diag_editor, result_count=len(linhas),
                  syntax_error=True)
            event("RUN_EXIT", "IMPORT", self._hein_diag_task, obj=self,
                  editor=self._hein_diag_editor)

            return

        for no in ast.walk(arvore):
            if self.isInterruptionRequested():
                event("RUN_CANCELLED", "IMPORT", self._hein_diag_task,
                      obj=self, editor=self._hein_diag_editor, phase="walk")
                return
            if not isinstance(no, (ast.Import, ast.ImportFrom)):
                continue
            for modulo, nivel in self._extrair_modulos(no):
                if self.isInterruptionRequested():
                    event("RUN_CANCELLED", "IMPORT", self._hein_diag_task,
                          obj=self, editor=self._hein_diag_editor,
                          phase="module")
                    return
                if not modulo:
                    continue
                if not self._modulo_existe(modulo, nivel):
                    linhas[no.lineno] = "error"
                elif isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
                    for alias in no.names:
                        if alias.name == "*":
                            continue
                        if not self._nome_existe(alias.name, no.module):
                            linhas.setdefault(no.lineno, "warning")
        if self.isInterruptionRequested():
            event("RUN_CANCELLED", "IMPORT", self._hein_diag_task,
                  obj=self, editor=self._hein_diag_editor, phase="result")
            return
        self.concluido.emit(linhas)
        event("RESULT_EMITTED", "IMPORT", self._hein_diag_task, obj=self,
              editor=self._hein_diag_editor, result_count=len(linhas))
        event("RUN_EXIT", "IMPORT", self._hein_diag_task, obj=self,
              editor=self._hein_diag_editor)

    # ── lógica pura (sem Qt) ─────────────────────────────────────────────

    def _modulo_existe(self, modulo: str, nivel: int) -> bool:
        if not modulo:

            return True

        if modulo in _STDLIB:

            return True

        if not self._venv and modulo in sys.modules:

            return True

        if self._projeto and self._existe_no_projeto(modulo):

            return True

        if self._venv and self._existe_no_venv(modulo):

            return True

        if not self._venv:
            try:
                import importlib.util
                if importlib.util.find_spec(modulo) is not None:

                    return True

            except (ModuleNotFoundError, ValueError, AttributeError):
                pass

        return False

    def _existe_no_projeto(self, modulo: str) -> bool:
        for raiz, pastas, arquivos in os.walk(self._projeto):
            pastas[:] = [p for p in pastas if p not in _IGNORAR]
            if f"{modulo}.py" in arquivos or modulo in pastas:

                return True

        return False

    def _existe_no_venv(self, modulo: str) -> bool:
        for sp in [
            os.path.join(self._venv, "Lib", "site-packages"),
            os.path.join(self._venv, "lib"),
        ]:
            if not os.path.isdir(sp):
                continue
            if os.path.isdir(os.path.join(sp, modulo)):

                return True

            if os.path.isfile(os.path.join(sp, modulo + ".py")):

                return True

            nome_norm = modulo.replace("-", "_").lower()
            for item in os.listdir(sp):
                if item.lower().startswith(nome_norm):

                    return True

        return False

    # ⚠️  função grande (92 linhas)
    def _nome_existe(self, nome: str, modulo: str) -> bool:
        if not self._projeto:

            return True

        partes = modulo.replace(".", os.sep)
        candidatos = [
            os.path.join(self._projeto, partes + ".py"),
            os.path.join(self._projeto, partes, "__init__.py"),
        ]
        pasta_local = ""
        if not any(os.path.isfile(c) for c in candidatos):
            raiz_mod = modulo.split(".")[0]
            for dirpath, pastas, arquivos in os.walk(self._projeto):
                pastas[:] = [p for p in pastas if p not in _IGNORAR]
                if f"{raiz_mod}.py" in arquivos or raiz_mod in pastas:
                    sub = partes[len(raiz_mod):].lstrip(os.sep)
                    candidatos = [
                        os.path.join(dirpath, partes + ".py"),
                        os.path.join(dirpath, partes, "__init__.py"),
                        os.path.join(dirpath, sub + ".py") if sub else "",
                    ]
                    if raiz_mod in pastas:
                        pasta_local = os.path.join(dirpath, raiz_mod)
                    break
            else:

                return True  # módulo externo — não flagra

        for caminho in candidatos:
            if not caminho or not os.path.isfile(caminho):
                continue
            try:
                with open(caminho, encoding="utf-8", errors="replace") as f:
                    src = f.read()
                tree = ast.parse(src)
                for n in ast.walk(tree):
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        if n.name == nome:

                            return True

                    elif isinstance(n, ast.Assign):
                        for t in n.targets:
                            if isinstance(t, ast.Name) and t.id == nome:

                                return True

                    elif isinstance(n, (ast.Import, ast.ImportFrom)):
                        for a in n.names:
                            if (a.asname or a.name) == nome:

                                return True

                return False

            except Exception:

                return True  # parse falhou — não flagra

        if pasta_local and os.path.isdir(pasta_local):
            for arq in os.listdir(pasta_local):
                if not arq.endswith(".py"):
                    continue
                try:
                    with open(os.path.join(pasta_local, arq), encoding="utf-8", errors="replace") as f:
                        src = f.read()
                    tree = ast.parse(src)
                    for n in ast.walk(tree):
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            if n.name == nome:

                                return True

                        elif isinstance(n, ast.Assign):
                            for t in n.targets:
                                if isinstance(t, ast.Name) and t.id == nome:

                                    return True

                        elif isinstance(n, (ast.Import, ast.ImportFrom)):
                            for a in n.names:
                                if (a.asname or a.name) == nome:

                                    return True

                except Exception:
                    continue

            return False

        return True

    def _regex(self, codigo: str, resultado: dict) -> None:
        for lineno, linha in enumerate(codigo.splitlines(), start=1):
            if not linha.strip().startswith(("import ", "from ")):
                continue
            m = re.match(r"^\s*from\s+(\S+)\s+import\s+(.+)$", linha)
            if m:
                raiz = m.group(1).split(".")[0]
                if not self._modulo_existe(raiz, 0):
                    resultado[lineno] = "error"
                else:
                    for nome_raw in m.group(2).split(","):
                        partes = nome_raw.strip().split()
                        if not partes:
                            continue
                        nome = partes[0]
                        if nome and nome != "*" and not self._nome_existe(nome, m.group(1)):
                            resultado.setdefault(lineno, "warning")
                continue
            m = re.match(r"^\s*import\s+(.+)$", linha)
            if m:
                for parte in m.group(1).split(","):
                    raiz = parte.strip().split()[0].split(".")[0]
                    if raiz and not self._modulo_existe(raiz, 0):
                        resultado[lineno] = "error"

    @staticmethod
    def _extrair_modulos(no) -> list:
        if isinstance(no, ast.Import):

            return [(alias.name.split(".")[0], 0) for alias in no.names]

        if isinstance(no, ast.ImportFrom):
            if (no.level or 0) > 0:

                return []

            raiz = (no.module or "").split(".")[0]

            return [(raiz, 0)]

        return []

class ValidadorImports(QObject):
    """
    Valida todos os imports do arquivo aberto e sublinha os inválidos.
    """

    # Signal(object) — evita conversão para QVariantMap que quebra chaves int
    erros_detectados = Signal(object)

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor
        self._timer  = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(800)
        self._timer.timeout.connect(self._lancar_validacao)
        self._erros_atuais:     dict[int, str]       = {}
        self._selecoes_cache:   list                 = []   # cache para reaplicar após cursorPositionChanged
        self._hash_codigo:      int | None           = None  # evita re-lançamento com conteúdo igual
        self._thread_validador: _ThreadValidador | None = None
        self._threads_validador_antigas: list[_ThreadValidador] = []
        self._edit_generation_atual = 0
        self._encerrando = False
        editor.textChanged.connect(self._agendar)
        editor.cursorPositionChanged.connect(self._reaplicar_destaques)
        editor.viewport().installEventFilter(self)

    # ── API pública ───────────────────────────────────────────────────

    def verificar_agora(self):
        """Força verificação imediata (ex: ao abrir arquivo)."""
        self._timer.stop()
        self._hash_codigo = None  # força re-lançamento mesmo se conteúdo igual
        self._lancar_validacao()

    def limpar(self):
        """Remove todos os destaques de erro."""
        self._selecoes_cache = []
        self._aplicar_destaques([])
        if self._erros_atuais:
            self._erros_atuais = {}
            self.erros_detectados.emit({})

    # ── Agendamento ───────────────────────────────────────────────────

    def _agendar(self):
        caminho = getattr(self._editor, 'file_path', None) or ''
        if not caminho.endswith('.py'):

            return

        self._timer.start()

    # ── Verificação principal ─────────────────────────────────────────

    def _lancar_validacao(self):
        """Snapshot de dados puros + lança _ThreadValidador em background."""
        if self._encerrando:
            return

        codigo = self._editor.toPlainText()
        if not codigo.strip():
            self.limpar()

            return

        _h = hash(codigo)
        if _h == self._hash_codigo:

            return

        self._hash_codigo = _h

        if self._thread_validador and self._thread_validador.isRunning():
            _old = self._thread_validador
            _old_task = getattr(_old, "_hein_diag_task", "")
            try:
                _old.concluido.disconnect()
            except RuntimeError:
                pass
            event("QUIT_REQUESTED", "IMPORT", _old_task, obj=_old,
                  editor=self._editor, reason="replaced_by_new_import")
            _old.requestInterruption()
            _old.quit()
            try:
                _terminou = _old.wait(100)
            except RuntimeError:
                _terminou = True
            if not _terminou:
                self._threads_validador_antigas.append(_old)
                reference("APPEND", "IMPORT", self, "_threads_validador_antigas",
                          before=None, after=_old, editor=self._editor,
                          task=_old_task)
        self._threads_validador_antigas = [
            t for t in self._threads_validador_antigas
            if self._thread_esta_rodando(t)
        ]

        projeto = self._pegar_projeto()
        venv    = self._pegar_venv(projeto)
        from _THREADS_.diagnostico_workers import edit_generation, new_task
        _edit = edit_generation(self._editor)
        _task = new_task("IMPORT", self._editor, _edit)
        _old_main = self._thread_validador
        _novo = _ThreadValidador(
            codigo, projeto, venv, _task, self._editor, _edit
        )
        self._thread_validador = _novo
        self._edit_generation_atual = _edit
        bind(_novo, "IMPORT", _task, self._editor, _edit)
        reference("REPLACE", "IMPORT", self, "_thread_validador",
                  before=_old_main, after=_novo,
                  editor=self._editor, task=_task)
        _novo.concluido.connect(
            lambda linhas, t=_novo, g=_edit:
                self._aplicar_resultados_validador(linhas, t, g)
        )
        # NÃO conectar finished → deleteLater (BUG-202807-07/12): crash.
        # _threads_vivas_validador mantém referência viva até finished — evita GC
        # prematuro se ValidadorImports for destruído antes de run() retornar.
        _threads_vivas_validador.add(_novo)
        _novo.finished.connect(
            lambda t=_novo: (
                _threads_vivas_validador.discard(t)
            )
        )
        _novo.start()

    def encerrar_threads(self, timeout_ms: int = 150):
        """Encerra o validador antes de o editor ser destruído."""
        self._encerrando = True
        self._timer.stop()

        _threads = []
        if self._thread_validador is not None:
            _threads.append(self._thread_validador)
        _threads.extend(self._threads_validador_antigas)

        _unicas = []
        _ids = set()
        for thread in _threads:
            if id(thread) not in _ids:
                _ids.add(id(thread))
                _unicas.append(thread)

        for thread in _unicas:
            try:
                thread.concluido.disconnect()
            except (RuntimeError, TypeError):
                pass

            try:
                if not thread.isRunning():
                    continue
                _task = getattr(thread, "_hein_diag_task", "")
                event("QUIT_REQUESTED", "IMPORT", _task, obj=thread,
                      editor=self._editor, reason="editor_closed")
                thread.requestInterruption()
                thread.quit()
                if thread.wait(timeout_ms):
                    continue

                event("TERMINATE", "IMPORT", _task, obj=thread,
                      editor=self._editor, reason="editor_closed_timeout")
                thread.terminate()
                thread.wait(200)
            except RuntimeError:
                pass

        self._threads_validador_antigas = [
            thread for thread in _unicas
            if self._thread_esta_rodando(thread)
        ]
        if (self._thread_validador is not None
                and not self._thread_esta_rodando(self._thread_validador)):
            self._thread_validador = None

    @staticmethod
    def _thread_esta_rodando(thread) -> bool:
        try:
            return thread.isRunning()
        except RuntimeError:
            return False

    def _verificar(self):
        """Mantido para compatibilidade — delega para _lancar_validacao."""
        self._lancar_validacao()

    def _aplicar_resultados_validador(
        self, linhas_invalidas: dict, origem=None, origem_generation=None
    ):
        """Chamado pela thread quando termina — aplica destaques na UI thread."""
        if self._encerrando:
            return
        if origem is not self._thread_validador:
            return
        if origem_generation != self._edit_generation_atual:
            return

        # ╔══════════════════════════════════════════════════════════════╗
        # ║ CRÍTICO: NÃO reagrupar o emit+destaques dentro do if.      ║
        # ║ _aplicar_destaques é chamado SEMPRE (não só quando erros   ║
        # ║ mudam) para restaurar underlines apagados por busca/lint.  ║
        # ╚══════════════════════════════════════════════════════════════╝
        if linhas_invalidas != self._erros_atuais:
            self._erros_atuais = linhas_invalidas
            self.erros_detectados.emit(linhas_invalidas)
        try:
            codigo = self._editor.toPlainText()
            selecoes = self._construir_selecoes(codigo, linhas_invalidas)
            self._aplicar_destaques(selecoes)
        except RuntimeError:
            pass  # editor já foi destruído
    # ── Fallback regex (usado quando há SyntaxError no arquivo) ───────

    # ⚠️  função grande (59 linhas)
    def _verificar_por_regex(self, codigo: str, projeto: str, venv: str, resultado: dict[int, str]) -> None:
        """Extrai e valida imports via regex quando AST falha por SyntaxError."""
        msgs = getattr(self._editor, '_mensagens_erros', None)

        for lineno, linha in enumerate(codigo.splitlines(), start=1):
            linha_strip = linha.strip()
            if not linha_strip.startswith(("import ", "from ")):
                continue

            # from X import Y, Z
            m = re.match(r"^\s*from\s+(\S+)\s+import\s+(.+)$", linha)
            if m:
                modulo_full = m.group(1)
                raiz        = modulo_full.split(".")[0]
                nomes_raw   = m.group(2)
                ok_modulo   = self._modulo_existe(raiz, 0, projeto, venv)
                if not ok_modulo:
                    log.aviso(_ARQ, "_verificar_por_regex",
                              f"módulo inválido: '{raiz}'", f"linha {lineno}")
                    resultado[lineno] = "error"
                    if msgs is not None:
                        msgs[lineno] = (
                            f"Módulo '{raiz}' não encontrado"
                            " — clique para instalar"
                        )
                else:
                    for nome_raw in nomes_raw.split(","):
                        nome = nome_raw.strip().split()[0]  # remove "as alias"
                        if not nome or nome == "*":
                            continue
                        existe = self._nome_existe_no_modulo(nome, modulo_full, projeto)
                        if not existe:
                            log.aviso(_ARQ, "_verificar_por_regex",
                                      f"nome '{nome}' não encontrado em '{modulo_full}'",
                                      f"linha {lineno}")
                            resultado.setdefault(lineno, "warning")
                            if msgs is not None:
                                msgs[lineno] = (
                                    f"'{nome}' não existe em '{modulo_full}'"
                                )
                continue

            # import X, Y
            m = re.match(r"^\s*import\s+(.+)$", linha)
            if m:
                for parte in m.group(1).split(","):
                    raiz = parte.strip().split()[0].split(".")[0]
                    if not raiz:
                        continue
                    ok = self._modulo_existe(raiz, 0, projeto, venv)
                    if not ok:
                        log.aviso(_ARQ, "_verificar_por_regex",
                                  f"módulo inválido: '{raiz}'", f"linha {lineno}")
                        resultado[lineno] = "error"
                        if msgs is not None:
                            msgs[lineno] = (
                                f"Módulo '{raiz}' não encontrado"
                                " — clique para instalar"
                            )

    # ── Extração de módulos (via AST) ─────────────────────────────────

    @staticmethod
    def _extrair_modulos(no) -> list[tuple[str, int]]:
        """Retorna lista de (nome_raiz_modulo, nivel_relativo)."""
        resultado = []
        if isinstance(no, ast.Import):
            for alias in no.names:
                raiz = alias.name.split(".")[0]
                resultado.append((raiz, 0))
        elif isinstance(no, ast.ImportFrom):
            nivel = no.level or 0
            if nivel > 0:
                # Import relativo (from . import X) — não valida aqui

                return []

            modulo = no.module or ""
            raiz   = modulo.split(".")[0] if modulo else ""
            resultado.append((raiz, 0))

        return resultado

    # ── Resolução de módulo ───────────────────────────────────────────

    # ⚠️  função grande (118 linhas)
    def _nome_existe_no_modulo(self, nome: str, modulo: str, projeto: str) -> bool:
        """Verifica se `nome` está definido em `modulo` dentro do projeto."""
        if not projeto:
            log.aviso(_ARQ, "_nome_existe_no_modulo",
                      f"projeto vazio — não flagra '{nome}'")

            return True

        partes     = modulo.replace(".", os.sep)
        candidatos = [
            os.path.join(projeto, partes + ".py"),
            os.path.join(projeto, partes, "__init__.py"),
        ]

        pasta_modulo_local: str = ""
        if not any(os.path.isfile(c) for c in candidatos):
            raiz_mod = modulo.split(".")[0]
            for dirpath, pastas, arquivos in os.walk(projeto):
                pastas[:] = [p for p in pastas if p not in _IGNORAR]
                if f"{raiz_mod}.py" in arquivos or raiz_mod in pastas:
                    sub = partes[len(raiz_mod):].lstrip(os.sep)
                    candidatos = [
                        os.path.join(dirpath, partes + ".py"),
                        os.path.join(dirpath, partes, "__init__.py"),
                        os.path.join(dirpath, sub + ".py") if sub else "",
                    ]
                    if raiz_mod in pastas:
                        pasta_modulo_local = os.path.join(dirpath, raiz_mod)
                    break
            else:
                log.aviso(_ARQ, "_nome_existe_no_modulo",
                          f"raiz '{raiz_mod}' NÃO encontrada no projeto"
                          " — módulo externo, não flagra")

                return True

        for caminho in candidatos:
            if not caminho or not os.path.isfile(caminho):
                continue
            try:
                with open(caminho, encoding="utf-8", errors="replace") as f:
                    src = f.read()
                tree = ast.parse(src)
                for n in ast.walk(tree):
                    if isinstance(n, (ast.FunctionDef,
                                      ast.AsyncFunctionDef,
                                      ast.ClassDef)):
                        if n.name == nome:

                            return True

                    elif isinstance(n, ast.Assign):
                        for t in n.targets:
                            if isinstance(t, ast.Name) and t.id == nome:

                                return True

                    elif isinstance(n, (ast.Import, ast.ImportFrom)):
                        for a in n.names:
                            if (a.asname or a.name) == nome:

                                return True

                log.aviso(_ARQ, "_nome_existe_no_modulo",
                          f"'{nome}' NÃO encontrado em '{caminho}' — retorna False")

                return False

            except Exception as e:
                log.erro(_ARQ, "_nome_existe_no_modulo",
                         f"erro ao parsear '{caminho}' — não flagra", str(e))

                return True

        # Namespace package: pasta existe sem __init__.py — varre todos os .py
        if pasta_modulo_local and os.path.isdir(pasta_modulo_local):
            for arq in os.listdir(pasta_modulo_local):
                if not arq.endswith(".py"):
                    continue
                caminho_arq = os.path.join(pasta_modulo_local, arq)
                try:
                    with open(caminho_arq, encoding="utf-8", errors="replace") as f:
                        src = f.read()
                    tree = ast.parse(src)
                    for n in ast.walk(tree):
                        if isinstance(n, (ast.FunctionDef,
                                          ast.AsyncFunctionDef,
                                          ast.ClassDef)):
                            if n.name == nome:

                                return True

                        elif isinstance(n, ast.Assign):
                            for t in n.targets:
                                if isinstance(t, ast.Name) and t.id == nome:

                                    return True

                        elif isinstance(n, (ast.Import, ast.ImportFrom)):
                            for a in n.names:
                                if (a.asname or a.name) == nome:

                                    return True

                except Exception as e:
                    log.erro(_ARQ, "_nome_existe_no_modulo",
                             f"erro ao parsear '{arq}'", str(e))
                    continue
            log.aviso(_ARQ, "_nome_existe_no_modulo",
                      f"'{nome}' NÃO está em nenhum .py de"
                      f" '{pasta_modulo_local}' — retorna False")

            return False

        log.aviso(_ARQ, "_nome_existe_no_modulo",
                  f"módulo externo não resolvível — não flagra '{nome}'")

        return True

    def _modulo_existe(self, modulo: str, nivel: int, projeto: str, venv: str) -> bool:
        """Retorna True se o módulo pode ser resolvido."""
        if not modulo:

            return True

        # 1. stdlib
        if modulo in _STDLIB:

            return True

        # 2. sys.modules — só quando NÃO há venv de projeto.
        # sys.modules reflete o processo da IDE, não o projeto do usuário.
        if not venv and modulo in sys.modules:

            return True

        # 3. projeto local (inclui namespace packages sem __init__.py)
        if projeto and self._existe_no_projeto(modulo, projeto):

            return True

        # 4. .venv do projeto
        if venv and self._existe_no_venv(modulo, venv):

            return True

        # 5. find_spec — só quando NÃO há venv de projeto definido.
        # Com venv definido, find_spec usaria o Python da IDE (venv errado)
        # e daria falso negativo: módulo desinstalado do projeto seria dado como OK.
        if not venv:
            try:
                import importlib.util
                spec = importlib.util.find_spec(modulo)
                if spec is not None:

                    return True

            except (ModuleNotFoundError, ValueError, AttributeError) as e:
                pass

        log.aviso(_ARQ, "_modulo_existe",
                  f"'{modulo}' → NÃO encontrado em nenhuma fonte")

        return False

    @staticmethod
    def _existe_no_projeto(modulo: str, projeto: str) -> bool:
        """Verifica se <modulo>.py ou <modulo>/ existe no projeto."""
        for raiz, pastas, arquivos in os.walk(projeto):
            pastas[:] = [p for p in pastas if p not in _IGNORAR]
            if f"{modulo}.py" in arquivos:

                return True

            if modulo in pastas:
                # aceita namespace package (pasta sem __init__.py) — Python 3.3+

                return True

        return False

    @staticmethod
    def _existe_no_venv(modulo: str, venv: str) -> bool:
        """Verifica se o módulo existe no .venv/Lib/site-packages."""
        site_pkgs_candidatos = [
            os.path.join(venv, "Lib", "site-packages"),   # Windows
            os.path.join(venv, "lib"),                      # Linux
        ]
        for sp in site_pkgs_candidatos:
            if not os.path.isdir(sp):
                continue
            if os.path.isdir(os.path.join(sp, modulo)):

                return True

            if os.path.isfile(os.path.join(sp, modulo + ".py")):

                return True

            nome_norm = modulo.replace("-", "_").lower()
            for item in os.listdir(sp):
                if item.lower().startswith(nome_norm):

                    return True

        return False

    # ── Destaques visuais ─────────────────────────────────────────────

    def _construir_selecoes(self, codigo: str, linhas: dict[int, str]) -> list:
        """Cria ExtraSelections com sublinhado wave para cada linha inválida."""
        selecoes     = []
        linhas_texto = codigo.splitlines()

        fmt_erro = QTextCharFormat()
        fmt_erro.setUnderlineStyle(QTextCharFormat.WaveUnderline)
        fmt_erro.setUnderlineColor(QColor("#ff4444"))

        fmt_aviso = QTextCharFormat()
        fmt_aviso.setUnderlineStyle(QTextCharFormat.WaveUnderline)
        fmt_aviso.setUnderlineColor(QColor("#ffaa00"))

        for linha_1based, tipo in linhas.items():
            idx = linha_1based - 1
            if idx < 0 or idx >= len(linhas_texto):
                continue

            bloco = self._editor.document().findBlockByNumber(idx)
            if not bloco.isValid():
                continue

            texto = linhas_texto[idx]
            inicio_nome, fim_nome = self._localizar_modulo_na_linha(texto, tipo)

            cursor = QTextCursor(bloco)
            cursor.setPosition(bloco.position() + inicio_nome)
            cursor.setPosition(bloco.position() + fim_nome,
                               QTextCursor.KeepAnchor)

            sel        = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format = fmt_erro if tipo == "error" else fmt_aviso
            selecoes.append(sel)

        return selecoes

    @staticmethod
    # 💡 tipo_opc = Literal["error"] ← defina os valores válidos
    def _localizar_modulo_na_linha(texto: str, tipo: str = "error") -> tuple[int, int]:
        """
        Retorna (inicio, fim) do trecho a sublinhar.
        warning → sublinha o nome importado (após 'import')
        error   → sublinha o nome do módulo (após 'from' ou 'import')
        """
        if tipo == "warning":
            # sublinha o nome após "import" (ex: vai_tomar_no_cu)
            m = re.match(r"^(\s*from\s+\S+\s+import\s+)(\S+)", texto)
            if m:
                inicio = len(m.group(1))
                fim    = inicio + len(m.group(2).rstrip(","))

                return inicio, fim

        # error: sublinha o módulo
        m = re.match(r"^(\s*from\s+)(\S+)", texto)
        if m:
            inicio = len(m.group(1))
            fim    = inicio + len(m.group(2))

            return inicio, fim

        m = re.match(r"^(\s*import\s+)(\S+)", texto)
        if m:
            inicio = len(m.group(1))
            fim    = inicio + len(m.group(2).rstrip(","))

            return inicio, fim

        return 0, max(1, len(texto.rstrip()))

    def _aplicar_destaques(self, novas_selecoes: list):
        """
        Aplica novas ExtraSelections sem remover as de outros módulos
        (highlight de linha, Ctrl+Click, etc.).
        Salva em cache para reaplicar quando o editor limpar as seleções.
        WaveUnderlines marcadas com UserProperty+100=True são do lint (pyflakes) — preservar.
        """
        from PySide6.QtGui import QTextFormat as _QTF
        _LINT_MARKER = _QTF.UserProperty + 100
        self._selecoes_cache = novas_selecoes
        existentes = [
            s for s in self._editor.extraSelections()
            if s.format.underlineStyle() != QTextCharFormat.WaveUnderline
            or s.format.property(_LINT_MARKER)   # preserva underlines do lint
        ]
        self._editor.setExtraSelections(existentes + novas_selecoes)

    def _reaplicar_destaques(self):
        """
        Chamado em cursorPositionChanged.
        Usa singleShot(0) para rodar DEPOIS de todos os outros slots conectados
        ao mesmo sinal (ex: current-line highlight do editor), garantindo que
        nossas seleções não sejam apagadas por eles.
        """
        if not self._selecoes_cache:

            return

        QTimer.singleShot(0, self._forcar_destaques)

    def _forcar_destaques(self):
        """Recoloca as seleções de erro após todos os eventos do ciclo atual."""
        if not self._selecoes_cache:

            return

        try:
            from PySide6.QtGui import QTextFormat as _QTF
            _LINT_MARKER = _QTF.UserProperty + 100
            existentes = [
                s for s in self._editor.extraSelections()
                if s.format.underlineStyle() != QTextCharFormat.WaveUnderline
                or s.format.property(_LINT_MARKER)   # preserva underlines do lint
            ]
            self._editor.setExtraSelections(existentes + self._selecoes_cache)
        except RuntimeError:
            pass

    # ── Utilitários ───────────────────────────────────────────────────

    def _pegar_projeto(self) -> str:
        return getattr(self._editor.window(), "current_project_path", None) or ""

    def _pegar_venv(self, projeto: str) -> str:
        """Localiza o .venv dentro do projeto do usuário."""
        if not projeto:

            return ""

        candidatos = [
            os.path.join(projeto, ".venv"),
            os.path.join(projeto, "venv"),
            os.path.join(projeto, "env"),
        ]
        for c in candidatos:
            if os.path.isdir(c):

                return c

        return ""

    # ── Clique direito em import inválido ────────────────────────────────

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        try:
            if (obj is self._editor.viewport()
                    and event.type() == QEvent.Type.MouseButtonPress):
                if event.button() in (Qt.RightButton, Qt.LeftButton):
                    # Clique esquerdo ou direito — mostra menu de instalação se
                    # o cursor cair em uma linha com erro de módulo não encontrado.
                    # Retorna True (consome o evento) só no clique esquerdo p/ não
                    # duplicar a ação com o comportamento padrão do editor.
                    consumido = self._checar_clique_import(event.pos())
                    if consumido and event.button() == Qt.LeftButton:

                        return True

        except RuntimeError:
            pass

        return False

    def _checar_clique_import(self, pos) -> bool:
        """Retorna True se o menu de instalação foi exibido (linha com erro 'error')."""
        cursor = self._editor.cursorForPosition(pos)
        linha  = cursor.blockNumber() + 1
        # Só mostra menu de instalação para erros de módulo não encontrado ('error'),
        # não para avisos de nome inexistente dentro do módulo ('warning').
        if self._erros_atuais.get(linha) != "error":

            return False

        modulo = self._extrair_nome_modulo(cursor.block().text())
        if modulo:
            self._mostrar_menu_instalar(pos, modulo)

            return True

        return False

    @staticmethod
    def _extrair_nome_modulo(linha: str) -> str:
        m = re.match(r"^\s*from\s+(\S+)", linha)
        if m:

            return m.group(1).split(".")[0]

        m = re.match(r"^\s*import\s+(\S+)", linha)
        if m:

            return m.group(1).split(",")[0].strip()

        return ""

    def _mostrar_menu_instalar(self, pos, modulo: str):
        from PySide6.QtWidgets import QMenu
        from _UTILITARIOS_.icones import icone_tema
        menu = QMenu(self._editor)
        acao = menu.addAction(
            icone_tema("mdi.download"),
            f"Instalar '{modulo}' via pip",
        )
        if menu.exec(self._editor.viewport().mapToGlobal(pos)) == acao:
            self._instalar_pacote(modulo)

    # ⚠️  função grande (66 linhas)
    def _instalar_pacote(self, modulo: str):
        import platform
        from PySide6.QtCore import QProcess
        from _UTILITARIOS_.hein_pacotes_util import registrar as _pkg_registrar
        projeto = self._pegar_projeto()
        venv    = self._pegar_venv(projeto)
        pip     = ""
        if venv:
            pip = os.path.join(
                venv,
                "Scripts" if platform.system() == "Windows" else "bin",
                "pip.exe" if platform.system() == "Windows" else "pip",
            )

        # ── Status bar: "Instalando…" ─────────────────────────────────
        self._status_bar_msg(f"Instalando '{modulo}'...")

        self._proc_install = QProcess(self._editor)
        self._proc_install.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        self._proc_install._saida_acumulada = b""

        def _ler():
            chunk = self._proc_install.readAll().data()
            self._proc_install._saida_acumulada += chunk

        def _ao_terminar(code, _):
            if code == 0:
                # parse da versão a partir da saída do pip
                saida_texto = self._proc_install._saida_acumulada.decode(
                    "utf-8", errors="replace"
                )
                versao = ""
                import re
                m = re.search(
                    r'Successfully installed ' + re.escape(modulo) + r'-([\d][\w.]*)',
                    saida_texto, re.IGNORECASE
                )
                if m:
                    versao = m.group(1)
                else:
                    # fallback: qualquer token que comece com o nome do módulo
                    m2 = re.search(
                        re.escape(modulo) + r'-([\d][\w.]*)',
                        saida_texto, re.IGNORECASE
                    )
                    if m2:
                        versao = m2.group(1)

                _pkg_registrar(projeto, modulo, versao)
                self._status_bar_msg(f"'{modulo}' instalado", duracao=4000)
                self.verificar_agora()
                self._avisar_aba_pacotes()
            else:
                self._status_bar_msg(f"Falha ao instalar '{modulo}'", duracao=4000)
                log.aviso(_ARQ, "_instalar_pacote",
                          f"Falha ao instalar '{modulo}' (código {code})")

        self._proc_install.readyRead.connect(_ler)
        self._proc_install.finished.connect(_ao_terminar)

        if pip and os.path.isfile(pip):
            self._proc_install.start(pip, ["install", modulo])
        else:
            self._proc_install.start(sys.executable, ["-m", "pip", "install", modulo])

    # ⚠️  except genérico vazio
    def _status_bar_msg(self, msg: str, duracao: int = 0) -> None:
        """Envia mensagem para a status bar da janela principal."""
        try:
            janela = self._editor.window()
            if not hasattr(janela, "statusBar"):

                return

            if duracao:
                janela.statusBar().showMessage(msg, duracao)
            else:
                janela.statusBar().showMessage(msg)
        except Exception:
            pass

    # ⚠️  except genérico vazio
    def _avisar_aba_pacotes(self) -> None:
        """Pede para a aba Pacotes se atualizar se estiver aberta no terminal."""
        try:
            from _UTILITARIOS_.gerenciador_pacotes import GerenciadorPacotes
            janela = self._editor.window()
            term_tabs = getattr(janela, "terminal_tabs", None)
            if not term_tabs:

                return

            for i in range(term_tabs.count()):
                w = term_tabs.widget(i)
                if isinstance(w, GerenciadorPacotes):
                    w.atualizar()
                    break
        except Exception:
            pass
