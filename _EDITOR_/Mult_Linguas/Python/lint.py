# _EDITOR_/Mult_Linguas/Python/lint.py
"""
_RunnableLint — roda AST + Pyflakes em background para arquivos Python.

Fase 1 (QRunnable): QThreadPool gerencia ciclo de vida.
  - Sem finished→deleteLater (BUG-202807-05 a 08 impossíveis).
  - _SinaisLint separa o QObject de sinais do QRunnable de execução.
  - autoDelete=True: pool deleta o runnable ao terminar automaticamente.
  - Caller guarda ref a _SinaisLint (não ao runnable) para desconectar
    sinal quando uma nova execução começa antes da anterior terminar.
"""
import warnings
# Suprime SyntaxWarning globalmente para o processo.
# catch_warnings() nao e thread-safe — em QRunnable o filtro pode nao valer.
# Como a IDE NUNCA quer SyntaxWarning de codigo do usuario vazando no console
# (ela sublinha no editor), o filtro permanente e a abordagem correta.
warnings.filterwarnings("ignore", category=SyntaxWarning)

from PySide6.QtCore import QObject, QRunnable, Signal
from _THREADS_.diagnostico_workers import bind, event, weak_editor


class _SinaisLint(QObject):
    """
    QObject portador dos sinais de _RunnableLint.
    QRunnable não herda de QObject — sinais precisam de objeto separado.
    Caller guarda referência a este objeto até receber 'concluido'.
    """
    concluido = Signal(object, object)  # (erros: dict, mensagens: dict)


class _RunnableLint(QRunnable):
    """Roda AST + Pyflakes em background — não bloqueia a UI."""

    def __init__(self, codigo: str, task: str = "", editor=None,
                 edit_generation: int = 0):
        super().__init__()
        self.setAutoDelete(True)   # pool deleta após run() — não guardar ref
        self._codigo = codigo
        self.signals = _SinaisLint()
        self._hein_diag_task = task
        self._hein_diag_component = "LINT"
        self._hein_diag_editor = weak_editor(editor)
        self._hein_diag_edit_generation = edit_generation
        bind(self.signals, "LINT", task, editor, edit_generation)

    def run(self):
        event("RUN_ENTER", "LINT", self._hein_diag_task, obj=self.signals,
              editor=self._hein_diag_editor)
        try:
            import ast as _ast
            erros: dict = {}
            mensagens: dict = {}

            linhas_teste = self._codigo.splitlines()
            tentativas = 0
            while tentativas < 60:
                tentativas += 1
                try:
                    _ast.parse("\n".join(linhas_teste))
                    break
                except SyntaxError as e:
                    linha = e.lineno or 1
                    if linha < 1 or linha > len(linhas_teste):
                        break
                    erros[linha] = "error"
                    mensagens[linha] = f"\u2717  {e.msg}"
                    linhas_teste[linha - 1] = ""

            if not erros:
                try:
                    from pyflakes.checker import Checker
                    from pyflakes import messages as pf_msgs
                    tree = compile(self._codigo, "<editor>", "exec",
                                   _ast.PyCF_ONLY_AST)
                    checker = Checker(tree, "<editor>")
                    for msg in checker.messages:
                        l = msg.lineno
                        try:
                            texto = msg.message % msg.message_args
                        except Exception:
                            texto = str(msg)
                        mensagens[l] = texto
                        if isinstance(msg, (pf_msgs.UndefinedName,
                                            pf_msgs.UndefinedLocal)):
                            erros[l] = "error"
                        else:
                            erros.setdefault(l, "warning")
                except ImportError:
                    pass
                except Exception:
                    pass

            self.signals.concluido.emit(erros, mensagens)
            event("RESULT_EMITTED", "LINT", self._hein_diag_task,
                  obj=self.signals, editor=self._hein_diag_editor,
                  error_count=len(erros))

        except Exception as e:
            from _LOG_.log import log
            log.erro("lint.py", "_RunnableLint.run",
                     "excecao nao tratada no runnable", str(e))
            self.signals.concluido.emit({}, {})
            event("RESULT_EMITTED", "LINT", self._hein_diag_task,
                  obj=self.signals, editor=self._hein_diag_editor,
                  error_count=0, exception=True)
        finally:
            event("RUN_EXIT", "LINT", self._hein_diag_task, obj=self.signals,
                  editor=self._hein_diag_editor)
