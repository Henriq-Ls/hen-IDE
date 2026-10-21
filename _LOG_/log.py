# 📁 _LOG_/log.py
"""
Sistema de log centralizado da hein IDE.
Salva em arquivo e emite para o painel visual.

UM único arquivo:  hein.log
  → recebe tudo em ordem cronológica: ok / info / aviso / erro / excecao / crash
  → faulthandler (crash nativo C/Qt) aponta direto para ele via arquivo_direto
  → sys.excepthook (crash Python) usa log.crash()

Uso em qualquer arquivo do projeto:
    from _LOG_.log import log
    log.info("git_ui.py", "_construir", "iniciando")
    log.ok("git_ui.py", "_construir", "ok")
    log.aviso("git_ui.py", "_construir", "atenção")
    log.erro("git_ui.py", "_construir", "falhou")
    log.crash("main.py", "excepthook", traceback_texto)

ARQUITETURA — FileHandler síncrono, sem thread:

  Python 3.14 + Windows: qualquer thread que bloqueie em Condition.wait()
  — com ou sem timeout — usa WaitForSingleObjectEx(bAlertable=TRUE).
  Qt/IAccessible (STA) entrega APCs COM via esse mecanismo. Resultado:
  0x8001010d em qualquer thread com fila, independente da implementação.

  Solução definitiva: sem thread de log. Sem fila. Sem nenhuma espera.

  logging.FileHandler (stdlib) é thread-safe via lock interno que usa
  EnterCriticalSection() — não-alertable, nunca recebe APCs COM.
  Gravação direta pelo thread chamador. Performance: microsegundos por linha,
  adequado para qualquer volume de log de IDE.

INICIALIZAÇÃO:
  log = _SistemaLog()   ← import-time: abre arquivo, configura FileHandler
  log.iniciar_worker()  ← no-op: mantido para compatibilidade com main.py

SHUTDOWN:
  app.aboutToQuit.connect(log.encerrar)
  encerrar() → fecha FileHandler limpo.
"""

import os
import json
import logging
import traceback
from datetime import datetime
from pathlib import Path

# ── Onde salvar o arquivo de log ──────────────────────────────────────
try:
    from _CONFIGURA_ import PASTA_APPDATA as _PASTA_APPDATA_LOG
except Exception:
    _PASTA_APPDATA_LOG = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "hein")

_PASTA_LOG   = Path(_PASTA_APPDATA_LOG)
_ARQUIVO_LOG = _PASTA_LOG / "hein.log"


class _PassthroughFormatter(logging.Formatter):
    """Formatter pass-through: _SistemaLog já monta a linha completa.
    O logging não deve adicionar timestamp, nível ou nome próprio."""
    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()


# ══════════════════════════════════════════════════════════════════════
class _SistemaLog:
    def __init__(self):
        self._salvar_arquivo = True
        self._arq_direto     = None   # handle exclusivo do faulthandler (main.py)
        self._file_handler   = None   # FileHandler síncrono — vida inteira do processo

        # Logger stdlib nomeado; propagação desativada
        self._logger = logging.getLogger("hein")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        try:
            _PASTA_LOG.mkdir(parents=True, exist_ok=True)
            self._rotacionar_na_inicializacao()
            self._abrir_direto()
            self._escrever_cabecalho_sessao()
            self._configurar_file_handler()
        except Exception:
            self._salvar_arquivo = False

    # ── Métodos públicos ──────────────────────────────────────────────

    def iniciar_worker(self):
        """No-op — mantido para compatibilidade com main.py.

        Python 3.14 + Windows: qualquer thread bloqueada em Condition.wait()
        — com ou sem timeout — usa WaitForSingleObjectEx(bAlertable=TRUE).
        Qt/IAccessible entrega APCs COM via wait alertable → 0x8001010d.
        Isso afeta _worker_disco manual (R9-04), QueueListener stdlib (R9-10)
        e qualquer outra fila/thread de espera. Não há implementação de
        thread segura nesse ambiente.

        Solução definitiva: FileHandler síncrono puro, sem thread.
        O lock interno do FileHandler usa EnterCriticalSection() — não-alertable.
        Performance: microsegundos por linha; adequado para volume de log de IDE.
        """
        pass   # intencional

    def flush_forcado(self):
        """Force fsync ao disco — apenas para pontos DIAG críticos.  # DIAG-TEMP
        logging.FileHandler.emit() já chama flush() (buffer Python→OS),
        mas abort() via qFatal não faz fsync. Este método garante que os
        dados cheguem ao disco mesmo se o processo morrer logo em seguida."""  # DIAG-TEMP
        try:  # DIAG-TEMP
            if self._file_handler and hasattr(self._file_handler, 'stream') \
                    and self._file_handler.stream:  # DIAG-TEMP
                self._file_handler.flush()  # DIAG-TEMP
                os.fsync(self._file_handler.stream.fileno())  # DIAG-TEMP
        except Exception:  # DIAG-TEMP
            pass  # DIAG-TEMP

    def encerrar(self):
        """Fecha o FileHandler de forma limpa (chamar em app.aboutToQuit)."""
        if self._file_handler:
            try:
                self._logger.removeHandler(self._file_handler)
                self._file_handler.flush()
                self._file_handler.close()
            except Exception:
                pass
            self._file_handler = None
        if self._arq_direto:
            try:
                self._arq_direto.flush()
                self._arq_direto.close()
            except Exception:
                pass
            self._arq_direto = None

    def info(self, arquivo: str, metodo: str, mensagem: str, dado=None):
        self._registrar("INFO", arquivo, metodo, mensagem, dado)

    def debug(self, arquivo: str, metodo: str, mensagem: str, dado=None):
        self._registrar("DEBUG", arquivo, metodo, mensagem, dado)

    def ok(self, arquivo: str, metodo: str, mensagem: str, dado=None):
        self._registrar("OK", arquivo, metodo, mensagem, dado)

    def aviso(self, arquivo: str, metodo: str, mensagem: str, dado=None):
        self._registrar("AVISO", arquivo, metodo, mensagem, dado)

    def erro(self, arquivo: str, metodo: str, mensagem: str, dado=None):
        self._registrar("ERRO", arquivo, metodo, mensagem, dado)

    def excecao(self, arquivo: str, metodo: str, mensagem: str):
        tb = traceback.format_exc()
        self._registrar("EXCEC", arquivo, metodo, mensagem, tb)

    def crash(self, arquivo: str, metodo: str, texto: str):
        """Crash Python não tratado — sys.excepthook. Escrita direta, sem fila."""
        self._escrever_secao_direta("CRASH", f"[{arquivo}.{metodo}]", texto)

    def fault(self, texto: str):
        """Dump manual de faulthandler. Escrita direta, sem fila."""
        self._escrever_secao_direta("FAULTHANDLER", "", texto)

    def caminho_arquivo(self) -> str:
        return str(_ARQUIVO_LOG)

    @property
    def arquivo_direto(self):
        """Handle aberto — passado a faulthandler.enable() em main.py."""
        return self._arq_direto

    # ── Interno ───────────────────────────────────────────────────────

    def _registrar(self, nivel: str, arquivo: str, metodo: str, mensagem: str, dado=None):
        agora    = datetime.now().strftime("%H:%M:%S")
        dado_str = self._formatar_dado(dado)
        local    = f"{arquivo} › {metodo}"

        # ── Arquivo — gravação síncrona pelo thread chamador ───────────
        # FileHandler.emit() adquire self.lock (EnterCriticalSection, não-alertable).
        # Thread-safe. Sem Condition.wait(). Sem exposição a APCs COM.
        if self._salvar_arquivo:
            linha = (
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
                f"[{nivel}] {local} — {mensagem}"
                + (f" | {dado_str}" if dado_str else "")
            )
            self._logger.info(linha)

        # ── Painel visual (log_signal) — só AVISO/ERRO/OK/EXCEC ──────────
        try:
            from _CONFIGURA_ import MODO_PRODUCAO as _modo_prod
        except Exception:
            _modo_prod = False
        _niveis_signal = {"ERRO", "EXCEC"} if _modo_prod else {"AVISO", "ERRO", "OK", "EXCEC"}
        if nivel in _niveis_signal:
            texto_visual = f"{agora}  {local} — {mensagem}"
            if dado_str:
                texto_visual += f"  |  {dado_str}"
            try:
                from _LOG_.log_signal import log_signal
                log_signal.nova_entrada.emit(nivel.strip(), texto_visual)
            except Exception:
                pass  # Qt ainda não iniciou — ignora silenciosamente

    @staticmethod
    def _formatar_dado(dado) -> str:
        if dado is None:
            return ""
        if isinstance(dado, (dict, list)):
            try:
                return json.dumps(dado, ensure_ascii=False, default=str)
            except Exception:
                return str(dado)
        return str(dado)

    def _rotacionar_na_inicializacao(self):
        """Apaga o log existente — cada sessão começa com arquivo limpo."""
        try:
            if _ARQUIVO_LOG.exists():
                _ARQUIVO_LOG.unlink()
        except Exception:
            pass

    def _abrir_direto(self):
        """Abre handle exclusivo para faulthandler.enable() em main.py.
        Este handle nunca é usado para gravação normal de logs."""
        try:
            self._arq_direto = open(_ARQUIVO_LOG, "a", encoding="utf-8", buffering=1)
        except Exception:
            self._arq_direto = None

    def _configurar_file_handler(self):
        """FileHandler síncrono — ativo da inicialização ao encerramento.
        Nenhuma thread. Nenhuma fila. Lock interno: EnterCriticalSection (não-alertable)."""
        try:
            self._file_handler = logging.FileHandler(
                filename=str(_ARQUIVO_LOG),
                mode="a",
                encoding="utf-8",
                delay=False,
            )
            self._file_handler.setFormatter(_PassthroughFormatter())
            self._file_handler.setLevel(logging.DEBUG)
            self._logger.addHandler(self._file_handler)
        except Exception:
            self._salvar_arquivo = False

    def _escrever_cabecalho_sessao(self):
        """Cabeçalho de sessão — escrito uma vez na abertura, antes do FileHandler."""
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(_ARQUIVO_LOG, "a", encoding="utf-8", buffering=1) as f:
                f.write(f"{'═' * 60}\n")
                f.write(f"  SESSÃO INICIADA: {agora}\n")
                f.write(f"{'═' * 60}\n")
                f.write(f"  FAULTHANDLER ATIVO\n")
                f.write(f"{'─' * 60}\n")
        except Exception:
            pass

    def _escrever_secao_direta(self, titulo: str, contexto: str, texto: str):
        """Escrita direta no arquivo — usada apenas por crash() e fault().
        Não passa pelo FileHandler; garante gravação mesmo em shutdown."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bloco = (
            f"\n[{ts}] {'═' * 20} {titulo} {'═' * 20}\n"
            + (f"[{ts}] {contexto}\n" if contexto else "")
            + texto.strip() + "\n"
            + f"{'─' * 60}\n"
        )
        try:
            with open(_ARQUIVO_LOG, "a", encoding="utf-8", buffering=1) as f:
                f.write(bloco)
        except Exception:
            pass


# ── Instância global ──────────────────────────────────────────────────
log = _SistemaLog()
