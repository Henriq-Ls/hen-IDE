# 📁 _BUSCA_/motor_busca.py
# coding: utf-8
"""Dispatcher central — detecta prefixo e delega pra busca certa."""
from .modelo_resultado import ResultadoBusca, TipoBusca
from .busca_arquivos   import buscar_arquivos, buscar_recentes
from .busca_simbolos   import buscar_simbolos
from .busca_anotacoes  import buscar_anotacoes, AnotacoesThread
from .busca_linha      import buscar_linha
from .busca_comandos   import buscar_comandos
from _LOG_.log import log
from _CONFIGURA_ import BUSCA_GREP_LIMITE
from _THREADS_.ciclo_vida import encerrar_thread
_ARQ = "motor_busca.py"

# Mantém referências a GrepThread/AnotacoesThread até finished — evita GC prematuro
# quando cancelar_grep() faz self._grep_thread/_anotacoes_thread = None antes de
# run() retornar (mesmo padrão do fix BUG-202807-12 em painel_outline/validador).
_threads_vivas_grep: set = set()
_threads_vivas_anotacoes: set = set()

class MotorBusca:
    def __init__(self, janela):
        self._janela    = janela
        self._raiz:     str        = ""
        self._recentes: list[str]  = []
        self._grep_thread          = None
        self._anotacoes_thread     = None

    def set_projeto(self, raiz: str):
        self._raiz = raiz
        log.info(_ARQ, "set_projeto", "projeto definido", raiz)

    def set_recentes(self, lista: list[str]):
        self._recentes = lista

    def cancelar_grep(self):
        # threads Qt com finished-âdeleteLater podem ja ter o objeto C++
        # destruido (libshiboken) quando cancelar_grep roda de novo rapido
        # (ex: usuario reabre "@" antes do deleteLater anterior processar) -
        # sem o try/except, isRunning() em objeto morto crasha a IDE inteira.
        if self._grep_thread:
            try:
                self._grep_thread.requestInterruption()
                encerrar_thread(self._grep_thread, 2000)
            except RuntimeError as e:
                log.aviso(_ARQ, "cancelar_grep", f"grep_thread ja deletado (ok): {e}")
        self._grep_thread = None
        if self._anotacoes_thread:
            try:
                self._anotacoes_thread.requestInterruption()
                encerrar_thread(self._anotacoes_thread, 2000)
            except RuntimeError as e:
                log.aviso(_ARQ, "cancelar_grep", f"anotacoes_thread ja deletado (ok): {e}")
        self._anotacoes_thread = None

    # ⚠️  função grande (56 linhas)
    def buscar(self, termo, cb_resultados, cb_grep=None, cb_grep_fim=None,
               cb_grep_init=None):
        self.cancelar_grep()
        t = termo.strip()
        if not t:
            r = buscar_recentes(self._recentes, self._raiz)
            cb_resultados(r)

            return r

        if t.startswith(":") and len(t) > 1:
            r = buscar_linha(t)
            cb_resultados(r)

            return r

        if t.startswith(">"):
            r = buscar_comandos(t, self._janela)
            cb_resultados(r)

            return r

        if t.startswith("@") and len(t) > 1:
            cb_resultados([])
            if len(t) < 3:   # @x com 1 letra: aguarda digitar mais
                return []
            if self._raiz and cb_grep:
                from _BUSCA_.busca_grep import GrepThread
                self._grep_thread = GrepThread(t[1:], self._raiz, BUSCA_GREP_LIMITE)
                self._grep_thread.resultado_encontrado.connect(cb_grep)
                if cb_grep_fim:
                    self._grep_thread.busca_concluida.connect(cb_grep_fim)
                # NÃO conectar finished → deleteLater (BUG-202807-08).
                # _threads_vivas_grep mantém ref até finished — evita GC prematuro
                # quando cancelar_grep() zera self._grep_thread antes de run() retornar.
                _threads_vivas_grep.add(self._grep_thread)
                self._grep_thread.finished.connect(
                    lambda t=self._grep_thread: _threads_vivas_grep.discard(t)
                )
                self._grep_thread.start()
                if callable(cb_grep_init):
                    cb_grep_init(t[1:])

            return []

        if t.startswith("$") and len(t) > 1:
            r = buscar_simbolos(t[1:].strip(), self._raiz)
            cb_resultados(r)

            return r

        if t.startswith("#"):
            tl = t.lstrip("#").strip().lower()
            if tl.startswith("marcação") or tl.startswith("marcacao"):
                cb_resultados([])   # limpa resultados anteriores
                if self._raiz and cb_grep:
                    self._anotacoes_thread = AnotacoesThread(
                        t, self._raiz, parent=None
                    )
                    self._anotacoes_thread.resultado_encontrado.connect(cb_grep)
                    if cb_grep_fim:
                        self._anotacoes_thread.busca_concluida.connect(cb_grep_fim)
                    # NÃO conectar finished → deleteLater (BUG-202807-08).
                    # _threads_vivas_anotacoes mantém ref até finished — evita GC
                    # prematuro quando cancelar_grep() zera self._anotacoes_thread.
                    _threads_vivas_anotacoes.add(self._anotacoes_thread)
                    self._anotacoes_thread.finished.connect(
                        lambda t=self._anotacoes_thread: _threads_vivas_anotacoes.discard(t)
                    )
                    self._anotacoes_thread.start()
                else:
                    r = buscar_anotacoes(t, self._raiz)
                    cb_resultados(r)
                    return r

                return []

        termo_arq = t[1:] if t.startswith("*") else t
        arqs = buscar_arquivos(termo_arq, self._raiz)

        cb_resultados(arqs)

        if self._raiz and cb_grep:
            from _BUSCA_.busca_grep import GrepThread
            self._grep_thread = GrepThread(t, self._raiz, BUSCA_GREP_LIMITE)
            self._grep_thread.resultado_encontrado.connect(cb_grep)
            if cb_grep_fim:
                self._grep_thread.busca_concluida.connect(cb_grep_fim)
            # NÃO conectar finished → deleteLater (BUG-202807-08).
            # _threads_vivas_grep mantém ref até finished — evita GC prematuro
            # quando cancelar_grep() zera self._grep_thread antes de run() retornar.
            _threads_vivas_grep.add(self._grep_thread)
            self._grep_thread.finished.connect(
                lambda t=self._grep_thread: _threads_vivas_grep.discard(t)
            )
            self._grep_thread.start()
            if callable(cb_grep_init):
                cb_grep_init(t)

        return arqs
