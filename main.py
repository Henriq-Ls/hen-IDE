# main.py
"""
Ponto de entrada da IDE hein-basic-ide.
Execute este arquivo para iniciar o editor.

Ordem de inicialização (NÃO alterar):
  1. QApplication              — setup do Qt
  2. log.iniciar_worker()      — no-op (R9-11: FileHandler síncrono, sem thread)
  3. faulthandler.enable()     — dump em crash real
  4. _instalar_veh_com()       — filtra 0x8001010d antes do faulthandler (R9-12)
  5. QLockFile                 — garante instância única
  6. carregar_fontes()         — registra fontes hein no Qt
  7. appdata.inicializar()     — garante estrutura do AppData
  8. Validação de Licença      — impede acesso não autorizado 🔑
  9. MainWindow()              — constrói a janela principal
  10. app.exec()               — loop de eventos
"""
#al; meus importe mais importante: 🚀
import os
import sys
from _CONFIGURA_ import TEMA_QT_PADRAO, PASTA_APPDATA, IMAGEM_ICO



# ── Worker de autocomplete no .exe: intercepta ANTES de qualquer import Qt ────
if "--hein-autocomplete-worker" in sys.argv:
    if sys.stdout is None:
        sys.stdout = open(1, "w", encoding="utf-8", buffering=1, closefd=False)
    if sys.stderr is None:
        sys.stderr = open(2, "w", encoding="utf-8", buffering=1, closefd=False)
    if sys.stdin is None:
        sys.stdin = open(0, "r", encoding="utf-8", closefd=False)
    from _EDITOR_.Autocomplete.autocomplete_worker import main as _worker_main
    _worker_main()
    sys.exit(0)

# ── Sem console: redireciona streams ausentes para hein.log ──────────────────
if sys.stdout is None or sys.stderr is None:
    from _APPDATA_ import appdata as _appdata
    _appdata.inicializar()
    _crash_file = open(
        os.path.join(PASTA_APPDATA, "hein.log"), "a", encoding="utf-8", buffering=1
    )
    if sys.stdout is None:
        sys.stdout = _crash_file
    if sys.stderr is None:
        sys.stderr = _crash_file

import tempfile
import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QLockFile, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QIcon
from _CONFIGURA_.fontes import carregar_fontes

# ── Mensagens internas do Qt → log ────────────────────────────────────────────
def _qt_message_handler(mode, context, message):
    from _LOG_.log import log
    texto = message.strip()
    if not texto:
        return
    if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
        (getattr(log, "erro", None) or log.aviso)("main.py", "_qt_message_handler", texto)
    else:
        log.info("main.py", "_qt_message_handler", texto)

def _caminho_recurso(relativo: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relativo)

def _instalar_veh_com():
    """Instala VEH que filtra 0x8001010d antes do faulthandler (R9-12).

    0x8001010D = RPC_E_CANTCALLOUT_ININPUTSYNCCALL.
    O Qt/Windows gera essa exceção internamente (IAccessible, shell, WMF) e
    JÁ a trata — o app não crasha. O faulthandler interceptava antes do Qt e
    imprimia "Windows fatal exception" como falso alarme.
    Retornamos EXCEPTION_CONTINUE_EXECUTION para devolver ao Qt.
    No-op em plataformas não-Windows.
    """
    if sys.platform != "win32":
        return None
    import ctypes
    _PVECTORED = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)

    @_PVECTORED
    def _handler(exc_pointers):
        try:
            # exc_pointers → EXCEPTION_POINTERS* → ExceptionRecord* → ExceptionCode
            exc_rec = ctypes.c_void_p.from_address(exc_pointers).value
            code    = ctypes.c_uint.from_address(exc_rec    ).value
            flags   = ctypes.c_uint.from_address(exc_rec + 4).value
            # 0x8001010D continuável (flags & 1 == 0) → devolver ao Qt
            if code == 0x8001010D and not (flags & 0x1):
                return -1  # EXCEPTION_CONTINUE_EXECUTION
        except Exception:
            pass
        return 0  # EXCEPTION_CONTINUE_SEARCH

    ctypes.windll.kernel32.AddVectoredExceptionHandler(1, _handler)
    return _handler  # referência mantida pelo chamador — evita GC do callback

# Handle do VEH mantido em módulo para evitar GC do callback
_veh_handle = None

def main():
    import traceback

    # Diagnóstico do roteamento deve existir antes de qualquer decisão do boot.
    # O logger completo é inicializado mais abaixo; esta função mantém o
    # diagnóstico disponível mesmo quando o processo falha durante o startup.
    def _log_boot(msg: str) -> None:
        try:
            from _LOG_.log import log as _boot_log
            _boot_log.info("main.py", "main", msg)
        except Exception:
            try:
                print(msg, flush=True)
            except Exception:
                pass

    _log_boot(f"sys.argv recebido: {sys.argv!r}")
    app = QApplication(sys.argv)

    # A sonda de foco é instalada explicitamente no boot, antes de qualquer
    # MainWindow, editor ou popup. Os módulos instrumentados também chamam
    # install() defensivamente ao serem construídos; a instalação é idempotente.
    from _THREADS_ import diagnostico_foco_temporario as _focus_trace
    _focus_trace.install(app)

    # ── Parseia --projeto=<caminho> ANTES do lock ─────────────────────────────
    # Instâncias com --projeto são janelas de editor independentes — múltiplas
    # são desejadas (uma por projeto). Só o picker (sem --projeto) é singular.
    _projeto_arg: str | None = None
    for _a in sys.argv[1:]:
        if _a.startswith("--projeto="):
            _projeto_arg = _a[len("--projeto="):]
            break

    if _projeto_arg:
        _log_boot(f"ROTA: MainWindow direto com projeto={_projeto_arg}")
        _log_boot("═" * 70)
        _log_boot(f">>> INÍCIO DA JANELA DO PROJETO: {_projeto_arg} <<<")
        _log_boot("═" * 70)
        _log_boot("\n")
    else:
        _log_boot("ROTA: JanelaPicker boot")
        _log_boot("═" * 70)
        _log_boot(">>> INÍCIO DA TELA DE BOAS-VINDAS (PICKER) <<<")
        _log_boot("═" * 70)
        _log_boot("\n")

    # Adquire o lock apenas para o picker (modo boot sem --projeto).
    # O logger limpa/cria o arquivo na inicialização; por isso o lock vem
    # antes do import do logger para evitar que uma segunda instância do
    # picker duplique o cabeçalho do log.
    _lock: QLockFile | None = None
    if _projeto_arg is None:
        _lock_name = "hein_ide_picker.lock" if getattr(sys, "frozen", False) else "hein_ide_picker_dev.lock"
        _lock = QLockFile(os.path.join(tempfile.gettempdir(), _lock_name))
        _lock.setStaleLockTime(0)
        if not _lock.tryLock(100):
            sys.exit(0)

    # Abre/trunca o diagnóstico em toda inicialização, inclusive quando o
    # picker não dispara nenhum worker instrumentado durante o boot.
    from _THREADS_ import diagnostico_workers as _worker_diagnostics

    from _LOG_.log import log
    qInstallMessageHandler(_qt_message_handler)

    # ── Confirma modo de log síncrono (R9-11) ────────────────────────────────
    # log.iniciar_worker() é no-op desde R9-11: o sistema usa FileHandler
    # síncrono com EnterCriticalSection (lock não-alertable), sem thread de
    # fila. Chamada mantida para compatibilidade de interface — não cria
    # nenhuma thread interna. Não há mais QueueHandler / QueueListener.
    log.iniciar_worker()
    app.aboutToQuit.connect(log.encerrar)

    # ── Faulthandler APÓS QApplication() ─────────────────────────────────────
    import faulthandler
    # Instala o VEH antes do faulthandler para garantir prioridade do nosso
    # handler e evitar que o faulthandler logue falso-alarmes 0x8001010d.
    global _veh_handle
    # Temporariamente desativado para confirmar diagnóstico do handler VEH no .exe.
    # _veh_handle = _instalar_veh_com()
    if log.arquivo_direto:
        faulthandler.enable(file=log.arquivo_direto, all_threads=True)

    # SIGTERM no Linux/macOS — registra no mesmo handle do faulthandler
    if os.name != "nt":
        try:
            faulthandler.register(signal.SIGTERM, file=log.arquivo_direto, all_threads=True)
        except Exception:
            pass

    # ── VEH: silencia 0x8001010d antes do faulthandler (R9-12) ───────────────
    # (instalação já feita acima, antes do faulthandler.enable)

    # ── sys.excepthook: exceções Python não tratadas → hein.log ───────────────
    def excepthook(exc_type, exc_value, exc_tb):
        texto = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            log.crash("main.py", "excepthook", texto)
        except Exception:
            pass
        try:
            traceback.print_exception(exc_type, exc_value, exc_tb)
        except Exception:
            pass
        sys.exit(1)

    sys.excepthook = excepthook

    app.setStyle(TEMA_QT_PADRAO)
    app.setWindowIcon(QIcon(IMAGEM_ICO))

    nomes = carregar_fontes()
    log.ok("main.py", "[hein] Fontes carregadas:", nomes)

    from _APPDATA_ import appdata
    appdata.inicializar()

    # _projeto_arg já foi parseado antes do lock (ver acima)
    projeto_inicial = _projeto_arg

    # ── 🔑 Validação de Licença ────────────────────────────────────────────────
    from _CONFIGURA_.gerenciador_licenca import verificar_licenca_local

    if not verificar_licenca_local():
        log.aviso("main.py", "validar_licenca", "Licença não encontrada ou inválida. Abrindo tela de ativação.")
        from _APP_.janela_primeiro_acesso import JanelaPrimeiroAcesso

        tela_ativacao = JanelaPrimeiroAcesso()
        if tela_ativacao.exec() != JanelaPrimeiroAcesso.Accepted:
            log.aviso("main.py", "validar_licenca", "Configuração inicial cancelada. Encerrando IDE.")
            sys.exit(0)

        log.ok("main.py", "validar_licenca", "Licença ativada com sucesso pelo usuário!")

    if projeto_inicial:
        # ── Modo editor: abre direto no projeto solicitado ────────────────────
        log.info("main.py", "main", f"abrindo projeto: {projeto_inicial}")
        try:
            from _APP_.main_window import MainWindow
            janela = MainWindow(projeto_inicial=projeto_inicial)
            log.info(
                "main.py",
                "main",
                f"MainWindow criada: projeto={projeto_inicial}",
            )
            janela.show()
            log.info(
                "main.py",
                "main",
                f"MainWindow.show() chamado: projeto={projeto_inicial}",
            )
        except Exception as exc:
            log.erro(
                "main.py",
                "main",
                f"exceção ao criar/mostrar MainWindow: {exc!r}",
            )
            raise
    else:
        # ── Modo picker: tela leve de boas-vindas (sem threads pesadas) ───────
        log.info("main.py", "main", "modo boot — exibindo JanelaPicker")
        from _APP_.Boas_Vindas.janela_picker import JanelaPicker
        janela = JanelaPicker(modo="boot")
        log.info("main.py", "main", "JanelaPicker criada: modo=boot")

        def _abrir_projeto_no_mesmo_processo(caminho: str) -> None:
            """Troca o picker inicial pela MainWindow sem relançar a IDE.

            O relançamento é reservado para abrir um projeto em uma janela
            independente. No boot, manter o mesmo QApplication evita que o
            processo que iniciou a tela de boas-vindas termine antes de a
            janela do projeto existir.
            """
            nonlocal janela
            picker = janela
            log.info("main.py", "main", "\n")
            log.info(
                "main.py",
                "main",
                f"picker concluiu seleção; abrindo no mesmo processo: {caminho}",
            )
            try:
                picker._salvar_config()
            except (AttributeError, RuntimeError) as exc:
                log.erro(
                    "main.py",
                    "_abrir_projeto_no_mesmo_processo",
                    f"exceção ao salvar configuração do picker: {exc!r}",
                )
                pass
            picker._motivo_fechamento = "transição para MainWindow no mesmo processo"
            log.info(
                "main.py",
                "_abrir_projeto_no_mesmo_processo",
                f"fechando picker por transição no mesmo processo: {caminho}",
            )
            picker.hide()

            try:
                from _APP_.main_window import MainWindow
                janela = MainWindow(projeto_inicial=caminho)
                log.info(
                    "main.py",
                    "_abrir_projeto_no_mesmo_processo",
                    f"MainWindow criada: projeto={caminho}",
                )
                janela.show()
                log.info(
                    "main.py",
                    "_abrir_projeto_no_mesmo_processo",
                    f"MainWindow.show() chamado: projeto={caminho}",
                )
            except Exception as exc:
                log.erro(
                    "main.py",
                    "_abrir_projeto_no_mesmo_processo",
                    f"exceção ao criar/mostrar MainWindow: {exc!r}",
                )
                raise

            # O projeto já está visível antes de o picker iniciar seu cleanup.
            # Assim o QApplication nunca fica sem uma janela principal durante
            # a transição.
            log.info(
                "main.py",
                "_abrir_projeto_no_mesmo_processo",
                f"fechando picker após MainWindow.show(): {caminho}",
            )
            log.info("main.py", "_abrir_projeto_no_mesmo_processo", "\n")
            picker.close()

        janela.projeto_escolhido.connect(_abrir_projeto_no_mesmo_processo)
        # Mantém uma referência explícita durante todo o loop de eventos.
        # O picker também usa WA_DeleteOnClose para ser destruído no close.
        janela.show()
        log.info("main.py", "main", "JanelaPicker.show() chamado: modo=boot")

    sys.exit(app.exec())

if __name__ == "__main__":
    import traceback
    try:
        main()
    except Exception:
        texto = traceback.format_exc()
        try:
            from _LOG_.log import log
            log.crash("main.py", "__main__", texto)
        except Exception:
            pass
        sys.exit(1)
