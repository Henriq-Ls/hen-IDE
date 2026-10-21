# 📁 _CONFIGURA_/gerenciador_autocomplete.py
"""
Gerencia o autocomplete.json: carrega dados, mantém snippets em memória
e notifica os editores via hot-reload quando o arquivo muda no disco.

Uso em GerenciadorAutocomplete (editor):
    from _CONFIGURA_.gerenciador_autocomplete import autocomplete_global
    autocomplete_global().registrar(self)      # no __init__()
    autocomplete_global().desregistrar(self)   # no closeEvent()
"""
import os
from PySide6.QtCore import QFileSystemWatcher, QTimer, Signal, QObject
from _CONFIGURA_ import ARQUIVO_AUTOCOMPLETE, _ler_json
from _LOG_.log import log
_ARQ = "gerenciador_autocomplete.py"

class GerenciadorAutocomplete(QObject):
    """
    Central do autocomplete.json.
    Mantém snippets carregados; hot-reload via QFileSystemWatcher.
    Registre editores com registrar(obj) — obj deve ter _recarregar_snippets().
    """

    snippets_alterados = Signal()

    def __init__(self):
        super().__init__()
        self._dados:     dict = {}
        self._listeners: list = []
        self._erro_json: str  = ""

        self._watcher = QFileSystemWatcher()
        self._watcher.fileChanged.connect(self._ao_arquivo_alterado)

        self._timer_reload = QTimer()
        self._timer_reload.setSingleShot(True)
        self._timer_reload.setInterval(400)   # debounce — ignora saves parciais
        self._timer_reload.timeout.connect(self._aplicar_reload)

        # Watcher dedicado: AppData/autocompletar/ (palavras.txt, simbolos.json, emojis.json, ...)
        # Detecta mudanças mesmo quando o arquivo é editado fora do autocomplete.json.
        self._watcher_appdata = QFileSystemWatcher()
        self._watcher_appdata.directoryChanged.connect(self._ao_appdata_alterado)
        self._watcher_appdata.fileChanged.connect(self._ao_appdata_alterado)

        self._timer_reload_appdata = QTimer()
        self._timer_reload_appdata.setSingleShot(True)
        self._timer_reload_appdata.setInterval(400)
        self._timer_reload_appdata.timeout.connect(self._aplicar_reload_appdata)

        self.carregar()
        self._sincronizar_watcher_appdata()

    # ── Registro de listeners ─────────────────────────────────────────────────────────────────────────────

    def registrar(self, listener) -> None:
        """Registra um GerenciadorAutocomplete do editor. Chamado no __init__ do editor."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def desregistrar(self, listener) -> None:
        """Remove listener quando o editor for fechado."""
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass

    # ── Dados ──────────────────────────────────────────────────────────────────────────────────

    def snippets(self) -> dict:
        """Snippets do usuário (filtra chaves com '_' — são comentários/metadados)."""
        raw = self._dados.get("snippets", {})

        return {k: v for k, v in raw.items() if not k.startswith("_")}

    def fontes_appdata(self) -> dict:
        """Listas de arquivos por tipo lidas de autocomplete.json[fontes_appdata]."""

        return self._dados.get("fontes_appdata", {})

    def dados(self) -> dict:

        return self._dados

    # ── Carga e fallback ────────────────────────────────────────────────────────────────────────

    def carregar(self, caminho: str = None) -> bool:
        """
        Carrega autocomplete.json com cadeia de fallback — nunca trava a IDE.

        Cadeia:
            1. Parse normal + auto-repair via _ler_json()
            2. Backup (.bak) do último load bem-sucedido
            3. Dados vazios — snippets desativados, Jedi continua funcionando
        """
        caminho     = caminho or ARQUIVO_AUTOCOMPLETE
        caminho_bak = caminho + ".bak"

        # ── Tentativa 1: parse normal + auto-repair ───────────────────────────────────────
        try:
            self._dados     = _ler_json(caminho)
            self._erro_json = ""
            self._salvar_backup(caminho, caminho_bak)
            if caminho not in self._watcher.files():
                self._watcher.addPath(caminho)
            log.ok(_ARQ, "carregar", caminho)

            return True

        except Exception as e:
            self._erro_json = str(e)
            log.aviso(_ARQ, "carregar", f"JSON inválido (tentando backup): {e}")

        # ── Tentativa 2: backup do último estado válido ────────────────────────────────
        if os.path.isfile(caminho_bak):
            try:
                self._dados = _ler_json(caminho_bak)
                if caminho not in self._watcher.files():
                    self._watcher.addPath(caminho)
                log.aviso(_ARQ, "carregar", f"usando backup: {caminho_bak}")

                return True

            except Exception as e2:
                log.erro(_ARQ, "carregar", "backup também inválido", str(e2))

        # ── Tentativa 3: dados vazios — snippets desativados ──────────────────────────
        self._dados = {}
        if caminho not in self._watcher.files():
            self._watcher.addPath(caminho)
        log.aviso(_ARQ, "carregar", "autocomplete.json inválido — snippets desativados")

        return False

    def _salvar_backup(self, origem: str, destino: str) -> None:
        try:
            import shutil as _sh
            _sh.copy2(origem, destino)
        except Exception as e:
            log.aviso(_ARQ, "_salvar_backup", str(e))

    def recarregar(self) -> bool:

        return self.carregar()

    # ── Hot-reload ───────────────────────────────────────────────────────────────────────────────

    def _ao_arquivo_alterado(self, caminho: str) -> None: # Alguns editores apagam+recriam o arquivo ao salvar — readicionar se sumiu
        if caminho not in self._watcher.files():
            self._watcher.addPath(caminho)
        self._timer_reload.start()

    def _aplicar_reload(self) -> None:
        if not self.carregar():

            return

        for listener in list(self._listeners):
            try:
                listener._recarregar_snippets()
            except Exception as e:
                log.aviso(_ARQ, "_aplicar_reload", f"Listener falhou: {e}")
        self.snippets_alterados.emit()
        log.ok(_ARQ, "_aplicar_reload", f"{len(self._listeners)} editor(es) atualizado(s)")

    # ── Watcher dedicado: AppData/autocompletar/ ──────────────────────────────────────────────────

    def _sincronizar_watcher_appdata(self) -> None:
        """
        (Re)adiciona a pasta AppData/autocompletar/ e todos os arquivos que ela contém
        ao watcher. Precisa ser chamado de novo sempre que um arquivo é criado/removido,
        porque QFileSystemWatcher só notifica sobre paths já registrados.
        """
        try:
            from _APPDATA_ import appdata
            pasta = appdata.autocompletar
        except Exception as e:
            log.aviso(_ARQ, "_sincronizar_watcher_appdata", str(e))

            return

        if pasta not in self._watcher_appdata.directories():
            self._watcher_appdata.addPath(pasta)

        try:
            atuais = {os.path.join(pasta, n) for n in os.listdir(pasta)}
        except OSError as e:
            log.aviso(_ARQ, "_sincronizar_watcher_appdata", str(e))

            return

        registrados = set(self._watcher_appdata.files())
        novos = [a for a in atuais if a not in registrados and os.path.isfile(a)]
        if novos:
            self._watcher_appdata.addPaths(novos)

    def _ao_appdata_alterado(self, caminho: str) -> None:
        """Disparado por mudança na pasta (novo/removido arquivo) ou em um arquivo já rastreado."""
        self._sincronizar_watcher_appdata()
        self._timer_reload_appdata.start()

    def _aplicar_reload_appdata(self) -> None:
        """Invalida o _CACHE_FONTES do autocomplete e avisa os editores abertos."""
        try:
            from _EDITOR_.Editor_Hein.autocomplete.autocomplete import (
                _invalidar_cache_fontes,
            )
            _invalidar_cache_fontes()
        except Exception as e:
            log.aviso(_ARQ, "_aplicar_reload_appdata", str(e))

            return

        for listener in list(self._listeners):
            try:
                listener._recarregar_snippets()
            except Exception as e:
                log.aviso(_ARQ, "_aplicar_reload_appdata", f"Listener falhou: {e}")
        log.ok(_ARQ, "_aplicar_reload_appdata", "Fontes AppData invalidadas (watcher dedicado)")

_instancia: GerenciadorAutocomplete | None = None

def autocomplete_global() -> GerenciadorAutocomplete:
    global _instancia
    if _instancia is None:
        _instancia = GerenciadorAutocomplete()

    return _instancia
