# 📁 _TERMINAIS_/cliente_dap.py
"""
Cliente DAP (Debug Adapter Protocol) para integração com debugpy.

Fluxo correto para debugpy --listen --wait-for-client:

  1. Lança o script com:
         python -m debugpy --listen HOST:PORTA --wait-for-client script.py

  2. Conecta via TCP e realiza o handshake DAP em ordem garantida:
         initialize  →  aguarda AMBOS (initialize response E initialized event)
                     →  attach  →  setBreakpoints  →  configurationDone

  3. Loop de eventos: interpreta stopped/continued/exited,
     busca stack frame → scopes → variables e emite sinais para o PainelDebug.

Notas de segurança de thread:
  - _enviar() e _seq são protegidos por threading.Lock.
  - _sock.recv() usa timeout de 1 s para permitir parada limpa via self._parar.
  - A thread encerra sozinha ao receber exited/terminated ou ao chamar parar().

Notas de I/O do subprocess:
  - stdout → DEVNULL (evita bloqueio de pipe se o script emitir saída).
  - stderr → PIPE apenas para diagnóstico em caso de morte prematura.
    Nunca fica acumulado: lido no momento do erro e descartado depois.
"""
import json
import os as _os
import socket as _socket
import subprocess
import sys as _sys
import threading
import time
from PySide6.QtCore import QThread, Signal
from _THREADS_.thread_segura import _ThreadSegura
from _LOG_.log import log
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console
_ARQ = "cliente_dap.py"

_HOST            = "127.0.0.1"
_TIMEOUT_CONEXAO = 15    # segundos — tempo para o debugpy subir e aceitar conexão
_TIMEOUT_RECV    = 1.0   # segundos — timeout de recv (permite verificar self._parar)

def _porta_livre() -> int:
    """Retorna uma porta TCP efêmera disponível no sistema."""
    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)

        return s.getsockname()[1]

class ClienteDAP(_ThreadSegura):
    """
    Thread de comunicação com debugpy via protocolo DAP.

    Sinais emitidos (thread-safe — PySide6 entrega na thread principal):
      pausado(arquivo, linha)    — debugger pausou (stopOnEntry / step)
      variaveis_recebidas(list)  — dicts {nome, tipo, valor} do frame atual
      executando()               — sessão retomou a execução
      encerrado()                — processo encerrou ou parar() foi chamado
      erro(str)                  — mensagem para exibir na UI
    """

    pausado             = Signal(str, int)
    variaveis_recebidas = Signal(list)
    executando          = Signal()
    encerrado           = Signal()
    erro                = Signal(str)

    def __init__(self, arquivo: str, python_path: str, porta: int = 0, breakpoints: list[int] | None = None):
        super().__init__()
        self._arquivo   = arquivo
        self._python    = python_path
        self._porta     = porta or _porta_livre()
        self._seq       = 0
        self._seq_lock  = threading.Lock()   # protege _seq + socket send
        self._sock: _socket.socket | None = None
        self._proc: subprocess.Popen | None = None
        self._parar     = False
        self._thread_id: int | None = None
        self._frame_id:  int | None = None
        self._buf       = b""
        # linhas com breakpoint (1-based); usadas no handshake e em atualizações
        self._bps: list[int] = sorted(breakpoints) if breakpoints else []

    # ── API pública — chamada segura da thread principal ──────────────────────

    def continuar(self):
        self._enviar("continue",  {"threadId": self._thread_id or 1})

    def proximo(self):
        self._enviar("next",      {"threadId": self._thread_id or 1})

    def entrar(self):
        self._enviar("stepIn",    {"threadId": self._thread_id or 1})

    def sair(self):
        self._enviar("stepOut",   {"threadId": self._thread_id or 1})

    def set_breakpoints(self, linhas: list[int]):
        """
        Atualiza os breakpoints durante uma sessão ativa.
        Pode ser chamado da thread principal a qualquer momento após o handshake.
        """
        self._bps = sorted(linhas)
        self._enviar_set_breakpoints()

    # ⚠️  except genérico vazio
    def parar(self):
        log.aviso(_ARQ, "parar", "parar() chamado pela UI")
        self._parar = True
        try:
            self._enviar("disconnect", {"restart": False})
        except Exception:
            pass
        self._encerrar()

    # ── QThread.run ───────────────────────────────────────────────────────────

    def run(self):
        log.ok(_ARQ, "run", f"thread iniciada | arq={self._arquivo} porta={self._porta}")
        try:
            self._iniciar_processo()
            self._conectar_socket()
            self._handshake()
            self._loop_mensagens()
        except Exception as exc:
            log.erro(_ARQ, "run", str(exc))
            self.erro.emit(str(exc))
        finally:
            log.aviso(_ARQ, "run", "thread encerrando")
            self._encerrar()
            self.encerrado.emit()

    # ── Processo filho ────────────────────────────────────────────────────────

    # ── Localiza o debugpy da venv da IDE (chamado uma vez, resultado cacheado) ─

    @staticmethod
    def _site_packages_debugpy() -> str:
        """
        Retorna o diretório site-packages da venv da IDE onde o debugpy está
        instalado.  O módulo já está importado no processo da IDE, então basta
        pegar o caminho do pacote e subir um nível.

        Retorna "" se o debugpy não estiver disponível na venv da IDE
        (situação improvável, mas tratada com falha silenciosa).
        """
        try:
            import debugpy as _dbg          # importado no contexto da IDE
            import pathlib
            # debugpy/__init__.py → debugpy/ → site-packages/

            return str(pathlib.Path(_dbg.__file__).parent.parent)

        except Exception:

            return ""

    # ⚠️  função grande (53 linhas)
    def _iniciar_processo(self):
        if not self._python:

            raise RuntimeError(

                "Nenhum interpretador Python encontrado no projeto. "
                "Certifique-se de que existe uma pasta '.venv' na raiz do projeto."
            )

        cmd = [
            self._python, "-m", "debugpy",
            "--listen", f"{_HOST}:{self._porta}",
            "--wait-for-client",
            self._arquivo,
        ]

        # Herda variáveis de ambiente do processo pai
        env = _os.environ.copy()

        # ── Injeta o debugpy da venv da IDE no PYTHONPATH do processo filho ──
        #
        # O usuário usa o Python do SEU projeto (para ter acesso aos pacotes
        # que ele instalou), mas não precisa ter o debugpy instalado lá — o
        # debugpy da IDE é injetado via PYTHONPATH e fica disponível para o
        # "-m debugpy" do processo filho.
        #
        # Isso é o mesmo comportamento do VS Code: o debugpy vem com a IDE,
        # não com o projeto do usuário.
        site_ida = self._site_packages_debugpy()
        if site_ida:
            existente = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = (
                f"{site_ida}{_os.pathsep}{existente}" if existente else site_ida
            )

        # Diretório de trabalho = pasta do script (para imports relativos)
        cwd = _os.path.dirname(_os.path.abspath(self._arquivo)) or None

        kwargs: dict = dict(
            # stdout → DEVNULL: evita bloqueio de buffer se o script gerar saída
            stdout=subprocess.DEVNULL,
            # stderr → PIPE: só lido em caso de morte prematura (diagnóstico)
            stderr=subprocess.PIPE,
            env=env,
            cwd=cwd,
        )
        kwargs.update(opcoes_processo_sem_console())

        self._proc = subprocess.Popen(cmd, **kwargs)
        log.ok(_ARQ, "_iniciar_processo",
               f"PID {self._proc.pid} | python={self._python} | porta={self._porta}")

    # ── Conexão TCP ───────────────────────────────────────────────────────────

    def _conectar_socket(self):
        """
        Tenta conectar ao debugpy por até _TIMEOUT_CONEXAO segundos.
        Se o processo filho morrer antes, lê o stderr para diagnóstico e
        lança RuntimeError imediatamente (sem aguardar o timeout completo).
        """
        prazo      = time.monotonic() + _TIMEOUT_CONEXAO
        ultimo_err = ""
        while time.monotonic() < prazo:
            if self._parar:

                raise RuntimeError("Depurador encerrado antes de conectar.")

            # ── detecta morte prematura do subprocess ──────────────────────
            if self._proc and self._proc.poll() is not None:
                stderr_raw = self._ler_stderr_proc()
                detalhe    = stderr_raw or "(sem saída de erro)"
                log.erro(_ARQ, "_conectar_socket",
                         f"subprocess morreu (cod={self._proc.returncode}) | {stderr_raw[:400]}")

                raise RuntimeError(

                    f"O processo debugpy encerrou inesperadamente "
                    f"(código {self._proc.returncode}).\n{detalhe}"
                )

            try:
                s = _socket.create_connection((_HOST, self._porta), timeout=2)
                s.settimeout(_TIMEOUT_RECV)
                self._sock = s
                log.ok(_ARQ, "_conectar_socket", f"TCP conectado na porta {self._porta}")

                return

            except OSError as e:
                ultimo_err = str(e)
                time.sleep(0.35)

        raise RuntimeError(

            f"Não foi possível conectar ao debugpy na porta {self._porta} "
            f"após {_TIMEOUT_CONEXAO} s. Verifique se 'debugpy' está instalado "
            f"na venv do projeto (pip install debugpy). Detalhe: {ultimo_err}"
        )

    def _ler_stderr_proc(self) -> str:
        """Lê e descarta stderr do processo (call-once após morte do processo)."""
        if not (self._proc and self._proc.stderr):

            return ""

        try:
            raw = self._proc.stderr.read()

            return (raw or b"").decode("utf-8", errors="replace").strip()

        except Exception:

            return ""

    # ── DAP: envio — thread-safe via _seq_lock ────────────────────────────────

    def _enviar(self, command: str, arguments: dict | None = None):
        """Monta e envia uma mensagem DAP. Thread-safe."""
        if not self._sock:

            return

        with self._seq_lock:
            self._seq += 1
            seq = self._seq
            msg: dict = {"seq": seq, "type": "request", "command": command}
            if arguments is not None:
                msg["arguments"] = arguments
            corpo  = json.dumps(msg).encode("utf-8")
            header = f"Content-Length: {len(corpo)}\r\n\r\n".encode("ascii")
            try:
                self._sock.sendall(header + corpo)
            except OSError:
                pass

    # ── DAP: recepção com buffer TCP ──────────────────────────────────────────

    def _ler_mensagem(self) -> dict | None:
        """Lê próxima mensagem DAP completa. Retorna None se encerrado."""
        while not self._parar:
            # tenta extrair do buffer acumulado antes de fazer recv
            msg = self._extrair_do_buffer()
            if msg is not None:

                return msg

            try:
                chunk = self._sock.recv(4096)
                if not chunk:

                    return None

                self._buf += chunk
            except _socket.timeout:
                continue   # re-verifica self._parar
            except OSError:

                return None

        return None

    def _extrair_do_buffer(self) -> dict | None:
        sep = b"\r\n\r\n"
        idx = self._buf.find(sep)
        if idx == -1:

            return None

        header_txt = self._buf[:idx].decode("ascii", errors="replace")
        tamanho    = 0
        for linha in header_txt.splitlines():
            if linha.lower().startswith("content-length:"):
                try:
                    tamanho = int(linha.split(":", 1)[1].strip())
                except ValueError:
                    pass
                break
        inicio = idx + len(sep)
        if len(self._buf) < inicio + tamanho:

            return None   # corpo ainda incompleto — aguarda mais recv

        corpo_bytes = self._buf[inicio : inicio + tamanho]
        self._buf   = self._buf[inicio + tamanho :]
        try:

            return json.loads(corpo_bytes.decode("utf-8"))

        except (json.JSONDecodeError, UnicodeDecodeError):

            return None   # mensagem malformada — ignora e continua

    # ── DAP: handshake ────────────────────────────────────────────────────────

    # ⚠️  função grande (84 linhas)
    def _handshake(self):
        """
        Handshake DAP para debugpy --listen --wait-for-client.

        ORDEM CORRETA para esta versão do debugpy:
          1. initialize   →  aguarda initialize RESPONSE
          2. attach        →  enviado IMEDIATAMENTE após response
                              (o debugpy só emite 'initialized' event após receber attach)
          3. aguarda initialized EVENT
          4. setBreakpoints
          5. configurationDone  →  debugpy inicia a execução do script

        ⚠️  NÃO espere 'initialized event' antes de 'attach':
            esta versão do debugpy fica em deadlock se fizer isso.
        """
        # 1) initialize → aguarda APENAS o response (não o evento ainda)
        log.ok(_ARQ, "_handshake", "[1/5] enviando initialize...")
        self._enviar("initialize", {
            "adapterID":                    "hein-ide",
            "clientID":                     "hein-ide",
            "clientName":                   "hein IDE",
            "pathFormat":                   "path",
            "linesStartAt1":                True,
            "columnsStartAt1":              True,
            "supportsVariableType":         True,
            "supportsRunInTerminalRequest": False,
        })

        while not self._parar:
            msg = self._ler_mensagem()
            if msg is None:

                return

            tipo = msg.get("type", "")
            if tipo == "response" and msg.get("command") == "initialize":
                if not msg.get("success", True):

                    raise RuntimeError(

                        f"initialize rejeitado pelo debugpy: {msg.get('message', '')}"
                    )
                log.ok(_ARQ, "_handshake", "initialize response OK")
                break
            # outros eventos antes do response são descartados

        if self._parar:

            return

        # 2) attach IMEDIATAMENTE — sem esperar initialized event
        #    stopOnEntry: True pausa na 1ª linha quando não há breakpoints
        _stop_on_entry = len(self._bps) == 0
        log.ok(_ARQ, "_handshake",
               f"[2/5] attach | stopOnEntry={_stop_on_entry} | bps={self._bps}")
        self._enviar("attach", {
            "justMyCode":  True,
            "stopOnEntry": _stop_on_entry,
        })

        # 3) agora sim aguarda o initialized event
        while not self._parar:
            msg = self._ler_mensagem()
            if msg is None:

                return

            tipo = msg.get("type", "")
            if tipo == "event" and msg.get("event") == "initialized":
                log.ok(_ARQ, "_handshake", "initialized event OK")
                break
            # responses do attach e outros eventos são descartados

        if self._parar:

            return

        # 4) envia breakpoints
        log.ok(_ARQ, "_handshake", f"[4/5] setBreakpoints linhas={self._bps}")
        self._enviar_set_breakpoints()

        # 5) sinaliza fim da configuração → debugpy inicia o script
        log.ok(_ARQ, "_handshake", "[5/5] configurationDone enviado")
        self._enviar("configurationDone", {})

    # ── Loop de eventos DAP ───────────────────────────────────────────────────

    def _loop_mensagens(self):
        while not self._parar:
            msg = self._ler_mensagem()
            if msg is None:
                break
            tipo = msg.get("type")
            if tipo == "event":
                self._tratar_evento(msg)
            elif tipo == "response":
                self._tratar_resposta(msg)

    def _tratar_evento(self, msg: dict):
        evento = msg.get("event", "")
        body   = msg.get("body") or {}

        if evento == "stopped":
            self._thread_id = body.get("threadId", 1)
            log.ok(_ARQ, "_tratar_evento",
                   f"STOPPED | razao={body.get('reason')} | thread={self._thread_id}")
            self._buscar_localizacao()   # → stackTrace → scopes → variables

        elif evento == "continued":
            self.executando.emit()

        elif evento in ("exited", "terminated"):
            log.aviso(_ARQ, "_tratar_evento", f"evento '{evento}' — loop encerrando")
            self._parar = True

    def _tratar_resposta(self, msg: dict):
        cmd  = msg.get("command", "")
        body = msg.get("body") or {}

        if cmd == "stackTrace":
            frames = body.get("stackFrames", [])
            if frames:
                frame          = frames[0]
                self._frame_id = frame.get("id")
                src            = (frame.get("source") or {}).get("path", self._arquivo)
                linha          = frame.get("line", 0)
                log.ok(_ARQ, "_tratar_resposta", f"pausado em {src}:{linha}")
                self.pausado.emit(src, linha)
                self._buscar_variaveis()

        elif cmd == "scopes":
            escopos = body.get("scopes", [])
            if escopos:
                ref = escopos[0].get("variablesReference", 0)
                if ref:
                    self._enviar("variables", {"variablesReference": ref})

        elif cmd == "variables":
            vars_raw = body.get("variables", [])
            out = [
                {
                    "nome":  v.get("name",  ""),
                    "tipo":  v.get("type",  ""),
                    "valor": v.get("value", ""),
                }
                for v in vars_raw
                if not v.get("name", "").startswith(("__", "@py_"))
            ]
            self.variaveis_recebidas.emit(out)

    def _buscar_localizacao(self):
        self._enviar("stackTrace", {
            "threadId":   self._thread_id,
            "startFrame": 0,
            "levels":     1,
        })

    def _buscar_variaveis(self):
        if self._frame_id is not None:
            self._enviar("scopes", {"frameId": self._frame_id})

    def _enviar_set_breakpoints(self):
        """Envia o estado atual de self._bps ao debugpy via DAP setBreakpoints."""
        self._enviar("setBreakpoints", {
            "source": {"path": self._arquivo},
            "breakpoints": [{"line": l} for l in self._bps],
        })

    # ── Encerramento seguro ───────────────────────────────────────────────────

    # ⚠️  except genérico vazio
    def _encerrar(self): # Fecha o socket primeiro (interrompe _ler_mensagem em recv)
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

        # Encerra o processo e drena os descritores de arquivo (incluindo pipes)
        if self._proc:
            proc = self._proc
            self._proc = None   # limpa referência antes de aguardar

            # Drena stderr restante para evitar bloqueio no wait()
            try:
                if proc.stderr:
                    proc.stderr.read()
                    proc.stderr.close()
            except Exception:
                pass

            if proc.poll() is None:
                # Processo ainda vivo — solicita encerramento gracioso
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except Exception:
                    try:
                        proc.kill()
                        proc.wait(timeout=2)
                    except Exception:
                        pass
            else:
                # Já encerrou — apenas recolhe o exit code
                try:
                    proc.wait(timeout=1)
                except Exception:
                    pass
