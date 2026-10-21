# 📁 _EDITOR_/Ui/diff_git_gutter.py
# -*- coding: utf-8 -*-
"""
ThreadDiffGutter — executa 'git diff HEAD -- <arquivo>' em background
e emite o mapeamento linha→tipo para a AreaNumerosLinha.

Uso:
    t = ThreadDiffGutter(arquivo, projeto_path, parent=editor)
    t.diff_pronto.connect(editor.area_numeros.set_git_changes)
    # NÃO conectar t.finished → t.deleteLater (BUG-202807-05/07): race condition.
    # Com parent=editor, Qt gerencia destruição via hierarquia pai-filho.
    t.start()
"""
import subprocess
from PySide6.QtCore import QObject, QRunnable, Signal
from _LOG_.log import log
from _THREADS_.diagnostico_workers import bind, event, weak_editor
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console
_ARQ = "diff_git_gutter.py"


class _SinaisDiffGutter(QObject):
    """
    QObject portador dos sinais de _RunnableDiffGutter.
    QRunnable não herda de QObject — sinais precisam de objeto separado.
    Caller guarda referência a este objeto até receber ambos os sinais.
    """
    diff_pronto   = Signal(object)  # dict[int, str] linha_1based: "added"|"modified"|"deleted"
    hunks_prontos = Signal(object)  # list[dict] hunks com linhas removidas (popup hover)


class _RunnableDiffGutter(QRunnable):
    """
    Parseia 'git diff HEAD' em background — não bloqueia a UI.

    Fase 1 (QRunnable): pool gerencia ciclo de vida.
    Uso:
        r = _RunnableDiffGutter(arquivo, projeto_path)
        r.signals.diff_pronto.connect(area_numeros.set_git_changes)
        r.signals.hunks_prontos.connect(area_numeros.set_git_hunks)
        QThreadPool.globalInstance().start(r)
        self._signals_diff_gutter = r.signals   # guarda ref dos sinais
    """

    def __init__(self, arquivo: str, projeto_path: str, task: str = "",
                 editor=None, edit_generation: int = 0):
        super().__init__()
        self.setAutoDelete(True)
        self._arquivo      = arquivo
        self._projeto_path = projeto_path
        self.signals = _SinaisDiffGutter()
        self._hein_diag_task = task
        self._hein_diag_component = "DIFF"
        self._hein_diag_editor = weak_editor(editor)
        self._hein_diag_edit_generation = edit_generation
        bind(self.signals, "DIFF", task, editor, edit_generation)

    def run(self):
        event("RUN_ENTER", "DIFF", self._hein_diag_task, obj=self.signals,
              editor=self._hein_diag_editor)
        try:
            resultado = _executar_diff(self._arquivo, self._projeto_path)
            self.signals.diff_pronto.emit(resultado)
            raw = obter_diff_raw(self._arquivo, self._projeto_path)
            self.signals.hunks_prontos.emit(parsear_hunks(raw))
            event("RESULT_EMITTED", "DIFF", self._hein_diag_task,
                  obj=self.signals, editor=self._hein_diag_editor,
                  changes_count=len(resultado))
        except Exception as e:
            log.erro(_ARQ, "_RunnableDiffGutter.run",
                     "excecao nao tratada no runnable", str(e))
            self.signals.diff_pronto.emit({})
            self.signals.hunks_prontos.emit([])
            event("RESULT_EMITTED", "DIFF", self._hein_diag_task,
                  obj=self.signals, editor=self._hein_diag_editor,
                  changes_count=0, exception=True)
        finally:
            event("RUN_EXIT", "DIFF", self._hein_diag_task, obj=self.signals,
                  editor=self._hein_diag_editor)

# ──────────────────────────────────────────────────────────────────────────────
# Funções internas
# ──────────────────────────────────────────────────────────────────────────────

# ⚠️  função grande (80 linhas)
def _executar_diff(arquivo: str, projeto_path: str) -> dict:
    """
    Roda 'git diff HEAD -- <arquivo>' e retorna dict[linha→tipo].
    Trata também arquivos novos (nunca commitados): todas as linhas = "added".
    Retorna {} se: git não no PATH, fora de repositório, ou qualquer erro.
    """
    import os
    cwd = projeto_path or "."
    try:
        # 1) Diff contra HEAD (arquivo já commitado pelo menos uma vez)
        proc = subprocess.run(
            ["git", "diff", "HEAD", "--", arquivo],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
            errors="replace",
            **opcoes_processo_sem_console(),
        )
        log.info(_ARQ, "_executar_diff",
                 f"git diff HEAD rc={proc.returncode} "
                 f"saida={len(proc.stdout)} chars  arq={arquivo!r}")
        saida = proc.stdout.strip()

        # 2) Nada no diff HEAD → tenta staged (arquivo novo adicionado ao index)
        if not saida:
            proc2 = subprocess.run(
                ["git", "diff", "--cached", "--", arquivo],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=5,
                encoding="utf-8",
                errors="replace",
                **opcoes_processo_sem_console(),
            )
            log.info(_ARQ, "_executar_diff",
                     f"git diff --cached rc={proc2.returncode} "
                     f"saida={len(proc2.stdout)} chars")
            saida = proc2.stdout.strip()

        # 3) Ainda vazio → verifica se o arquivo é novo e não rastreado
        if not saida:
            proc3 = subprocess.run(
                ["git", "ls-files", "--error-unmatch", "--", arquivo],
                cwd=cwd,
                capture_output=True,
                timeout=3,
                **opcoes_processo_sem_console(),
            )
            if proc3.returncode != 0:
                # Arquivo não rastreado: todas as linhas são "added"
                log.info(_ARQ, "_executar_diff",
                         f"arquivo não rastreado → marcando todas as linhas como added")
                try:
                    with open(arquivo, encoding="utf-8", errors="replace") as fh:
                        total = sum(1 for _ in fh)

                    return {i: "added" for i in range(1, total + 1)}

                except OSError:

                    return {}

            log.info(_ARQ, "_executar_diff", "diff vazio — arquivo sem mudanças")

            return {}

        resultado = _parsear_diff(saida)
        log.info(_ARQ, "_executar_diff", f"{len(resultado)} linha(s) marcadas")

        return resultado

    except FileNotFoundError:
        log.aviso(_ARQ, "_executar_diff", "git não encontrado no PATH (RG-07)")

        return {}

    except Exception as e:
        log.erro(_ARQ, "_executar_diff", "erro inesperado", str(e))

        return {}

def obter_diff_raw(arquivo: str, projeto_path: str) -> str:
    """
    Retorna o texto bruto do 'git diff HEAD -- <arquivo>'.
    Reutiliza a mesma lógica de fallback de _executar_diff (HEAD → cached).
    Retorna string vazia se não há diff ou em caso de erro.
    """
    cwd = projeto_path or "."
    try:
        for args in (
            ["git", "diff", "HEAD",      "--", arquivo],
            ["git", "diff", "--cached",  "--", arquivo],
        ):
            proc = subprocess.run(
                args, cwd=cwd, capture_output=True,
                text=True, timeout=5, encoding="utf-8", errors="replace",
                **opcoes_processo_sem_console(),
            )
            if proc.stdout.strip():
                return proc.stdout
        return ""
    except Exception:
        return ""


def _parsear_diff(diff: str) -> dict:
    """
    Parseia unified diff e retorna dict[linha_1based → tipo].

    Regras:
      - Bloco que começa com '-' seguido de '+' → "modified" (substituição)
      - '+' isolado → "added"
      - '-' sem '+' seguinte → marca a posição como "deleted" (triângulo 3px)
    """
    mudancas: dict[int, str] = {}
    linha_nova       = 0
    removidas_hunk   = 0   # quantidade de '-' desde o último contexto

    for linha in diff.splitlines():
        if linha.startswith("@@"):
            removidas_hunk = 0
            try:
                parte      = linha.split("+")[1].split(",")[0].split(" ")[0]
                linha_nova = int(parte)
            except Exception:
                linha_nova = 0
            continue

        if linha.startswith("---") or linha.startswith("+++"):
            continue

        if linha.startswith("-"):
            removidas_hunk += 1
            # Registra ponto de deleção na posição atual do novo arquivo
            if linha_nova > 0 and linha_nova not in mudancas:
                mudancas[linha_nova] = "deleted"

        elif linha.startswith("+"):
            if removidas_hunk > 0:
                # Substituição: essa linha nova corresponde a uma removida → modified
                mudancas[linha_nova] = "modified"
                removidas_hunk -= 1
            else:
                mudancas[linha_nova] = "added"
            linha_nova += 1

        else:
            # Linha de contexto: zera pendência de remoções e avança
            removidas_hunk = 0
            if linha_nova > 0:
                linha_nova += 1

    return mudancas

def parsear_hunks(diff: str) -> list:
    """Parseia unified diff e retorna lista de hunks para o popup de hover.

    Cada hunk (dict):
        "linhas":      list[int]  - linhas do novo arquivo afetadas
        "removidas":   list[str]  - texto das linhas removidas (sem prefixo -)
        "adicionadas": list[str]  - texto das linhas adicionadas (sem prefixo +)
        "cabecalho":   str        - linha @@ bruta do hunk
    """
    hunks:       list = []
    removidas:   list = []
    adicionadas: list = []
    linhas_hunk: list = []
    cabecalho_atual   = ''
    linha_nova        = 0

    def _fechar():
        if removidas or adicionadas:
            hunks.append({
                "linhas":      list(linhas_hunk),
                "removidas":   list(removidas),
                "adicionadas": list(adicionadas),
                "cabecalho":   cabecalho_atual,
            })

    for linha in diff.splitlines():
        if linha.startswith("@@"):
            _fechar()
            removidas.clear(); adicionadas.clear(); linhas_hunk.clear()
            cabecalho_atual = linha
            try:
                parte      = linha.split("+")[1].split(",")[0].split(" ")[0]
                linha_nova = int(parte)
            except Exception:
                linha_nova = 0
            continue

        if linha.startswith(("---", "+++")):
            continue

        if linha.startswith("-"):
            removidas.append(linha[1:])
            if linha_nova > 0 and linha_nova not in linhas_hunk:
                linhas_hunk.append(linha_nova)
        elif linha.startswith("+"):
            adicionadas.append(linha[1:])
            if linha_nova > 0:
                linhas_hunk.append(linha_nova)
            linha_nova += 1
        else:
            if linha_nova > 0:
                linha_nova += 1

    _fechar()
    return hunks
