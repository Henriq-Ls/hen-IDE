# 📁 _UTILITARIOS_/atualizador.py
from PySide6.QtCore import QThread, Signal, QTimer
from _THREADS_.thread_segura import _ThreadSegura
import requests
from _CONFIGURA_ import VERSAO_APP
from _LOG_.log import log

_REPO_API = "https://api.github.com/repos/Henriq-Ls/hein-IDE/releases"
_REPO_URL = "https://github.com/Henriq-Ls/hein-IDE/releases/latest"


class _WorkerVerifica(_ThreadSegura):
    # (versao_remota, url_html, url_exe, body)
    nova_versao = Signal(str, str, str, str)

    def run(self):
        try:
            r = requests.get(_REPO_API, timeout=8)
            if r.status_code != 200:
                log.aviso("atualizador.py", "run", f"API retornou {r.status_code}")
                return

            lista = r.json()
            if not lista:
                log.aviso("atualizador.py", "run", "Nenhuma release encontrada")
                return

            dados       = lista[0]
            versao_remota = dados.get("tag_name", "").lstrip("v")
            url_html    = dados.get("html_url", _REPO_URL)
            body        = dados.get("body", "") or ""
            versao_local = VERSAO_APP.lstrip("v")

            # URL direta do .exe nos assets do release
            url_exe = ""
            for asset in dados.get("assets", []):
                if asset.get("name", "").endswith(".exe"):
                    url_exe = asset.get("browser_download_url", "")
                    break

            if versao_remota and versao_remota != versao_local:
                log.info("atualizador.py", "run", f"Nova versão disponível: {versao_remota}")
                self.nova_versao.emit(versao_remota, url_html, url_exe, body)
            else:
                log.ok("atualizador.py", "run", "hein IDE está atualizada")

        except Exception as e:
            log.aviso("atualizador.py", "run", f"Falha ao verificar atualização: {e}")


def verificar_atualizacao(barra_aba_topo, parent=None):
    worker = _WorkerVerifica(parent)
    worker.nova_versao.connect(barra_aba_topo.notificar_update)
    worker.finished.connect(worker.deleteLater)
    QTimer.singleShot(5000, worker.start)
    if parent is not None:
        parent._worker_atualizacao = worker
