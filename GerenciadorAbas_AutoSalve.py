# GerenciadorAbas_AutoSalve.py
"""
GerenciadorAbas_AutoSalve.py — Centro de controle das abas do editor.

Responsabilidades:
  ✅ Auto-save: salva automaticamente após 3s de inatividade
  ✅ FileWatcher: recarrega abas quando arquivo muda no disco
  ✅ Não destrói histórico de undo ao salvar
  ✅ Não recarrega se o editor tiver edições não salvas
  ✅ Reindexação em background + atualização do CodeLens após qualquer save

Arquitetura:
  - A flag _salvando_internamente fica no CodeEditor (quem sabe que está salvando)
  - O watcher usa reload diferido (QTimer 150ms) para evitar race condition
  - Reindex roda em _ThreadReindex (background) — nunca bloqueia a UI
"""
import json
import os
from PySide6.QtCore import QObject, QRunnable, QTimer, QFileSystemWatcher, QThreadPool, Signal
from PySide6.QtWidgets import QApplication
from _CONFIGURA_ import PASTA_APPDATA as _PASTA_APPDATA  # canônico — IMP-03
from _THREADS_.diagnostico_workers import (
    bind, edit_generation, event, new_task, reference, weak_editor,
)
_ARQUIVO_SESSAO = os.path.join(_PASTA_APPDATA, 'sessao.json')


def _eh_arquivo_interno(caminho: str) -> bool:
    """Impede restaurar logs e estados internos como abas do editor."""
    try:
        nome = os.path.basename(os.path.normpath(caminho)).lower()
        return nome in {"hein.log", "hein_exception.log", "hein_faulthandler.log"}
    except (TypeError, ValueError):
        return True

class _SinaisReindex(QObject):
    """QObject portador dos sinais de _RunnableReindex."""
    concluido = Signal(str)  # caminho reindexado


class _RunnableReindex(QRunnable):
    """
    Reindexar um único arquivo em background após salvar — não bloqueia a UI.

    Fase 1 (QRunnable): pool gerencia ciclo de vida.
    autoDelete=True: pool deleta após run(). Caller guarda ref a .signals.
    """

    def __init__(self, indexador, caminho: str, task: str = "",
                 editor=None, edit_generation: int = 0):
        super().__init__()
        self.setAutoDelete(True)
        self._indexador = indexador
        self._caminho   = caminho
        self.signals    = _SinaisReindex()
        self._hein_diag_task = task
        self._hein_diag_component = "REINDEX"
        self._hein_diag_editor = weak_editor(editor)
        self._hein_diag_edit_generation = edit_generation
        bind(self.signals, "REINDEX", task, editor, edit_generation)

    def run(self):
        event("RUN_ENTER", "REINDEX", self._hein_diag_task,
              obj=self.signals, editor=self._hein_diag_editor)
        try:
            self._indexador.reindexar_arquivo(self._caminho)
            self.signals.concluido.emit(self._caminho)
            event("RESULT_EMITTED", "REINDEX", self._hein_diag_task,
                  obj=self.signals, editor=self._hein_diag_editor)
        finally:
            event("RUN_EXIT", "REINDEX", self._hein_diag_task,
                  obj=self.signals, editor=self._hein_diag_editor)

class GerenciadorAbas_AutoSalve(QObject):
    _INTERVALO_SAVE_MS = 3000  # 3s de inatividade → salva

    def __init__(self, tabs, parent=None):
        super().__init__(parent)
        self._tabs = tabs

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._INTERVALO_SAVE_MS)
        self._timer.timeout.connect(self._auto_salvar)

        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._arquivo_alterado_no_disco)

        self._recarregando = False
        self._signals_reindex: _SinaisReindex | None = None

        tabs.aba_adicionada.connect(self._ao_abrir_aba)

        # Save por perda de foco — estilo PyCharm
        app = QApplication.instance()
        if app:
            app.focusChanged.connect(self._ao_foco_alterado)

    # ── Focus save (PyCharm style) ───────────────────────────────────

    def _ao_foco_alterado(self, antigo, novo):
        """Salva ao sair do editor — comportamento estilo PyCharm.
        Dispara quando o foco sai do widget do editor (ou qualquer filho dele).
        """
        if antigo is None:

            return

        editor = self._tabs.get_current_editor()
        if editor is None:

            return

        # Verifica se o foco estava no editor ou em algum filho (viewport, scrollbar)
        widget = antigo
        while widget is not None:
            if widget is editor:
                if editor.file_path and editor.is_modified():
                    editor.save_file()

                return

            widget = getattr(widget, 'parent', lambda: None)()

    # ── Auto-save ─────────────────────────────────────────────────────

    def _ao_abrir_aba(self, editor):
        editor.textChanged.connect(self._timer.start)
        editor.arquivo_salvo.connect(self._monitorar)
        editor.arquivo_salvo.connect(self._ao_salvar_reindexar)
        if editor.file_path:
            self._monitorar(editor.file_path)

    def _ao_salvar_reindexar(self, caminho: str): # Status bar — rápido, fica na UI thread
        janela = self._tabs.window()
        if hasattr(janela, "statusBar"):
            nome = os.path.basename(caminho)
            janela.statusBar().showMessage(f"Salvo: {nome}", 3000)

        # Reindex em background — não bloqueia a UI
        indexador = getattr(janela, "_indexador", None)
        if indexador and caminho.endswith(".py"):
            # Descarta sinais do reindex anterior (runnable termina no pool)
            if self._signals_reindex is not None:
                try:
                    self._signals_reindex.concluido.disconnect()
                except RuntimeError:
                    pass
                reference("ZERO", "REINDEX", self, "_signals_reindex",
                          before=self._signals_reindex, after=None,
                          editor=self._tabs.get_current_editor(),
                          task=getattr(self._signals_reindex, "_hein_diag_task", ""))
            editor = self._tabs.get_current_editor()
            _edit = edit_generation(editor)
            _task = new_task("REINDEX", editor, _edit)
            r = _RunnableReindex(indexador, caminho, _task, editor, _edit)
            reference("REPLACE", "REINDEX", self, "_signals_reindex",
                      before=self._signals_reindex, after=r.signals,
                      editor=editor, task=_task)
            self._signals_reindex = r.signals
            self._signals_reindex.concluido.connect(self._ao_reindex_concluido)
            event("START_REQUESTED", "REINDEX", _task,
                  obj=r.signals, editor=editor,
                  destination=caminho)
            QThreadPool.globalInstance().start(r)

    def _ao_reindex_concluido(self, caminho: str):
        """Chamado pela thread quando reindex termina — atualiza CodeLens na UI."""
        editor = self._tabs.get_current_editor()
        if editor and hasattr(editor, '_atualizar_code_lens'):
            QTimer.singleShot(100, editor._atualizar_code_lens)

    def _auto_salvar(self):
        editor = self._tabs.get_current_editor()
        if editor and editor.file_path and editor.is_modified():
            # IMP-05: JSONs de configuração vivem em AppData — nunca auto-salvar
            # Usa normcase+abspath para ser robusto a case e separadores no Windows
            _appdata_norm = os.path.normcase(os.path.abspath(_PASTA_APPDATA))
            _arq_norm     = os.path.normcase(os.path.abspath(editor.file_path))
            if _arq_norm.startswith(_appdata_norm + os.sep):
                return
            nome = os.path.basename(editor.file_path)
            janela = self._tabs.window()
            if hasattr(janela, "statusBar"):
                janela.statusBar().showMessage(f"Auto-salvo: {nome}", 3000)
            editor.save_file()

    # ── File Watcher ──────────────────────────────────────────────────

    def _monitorar(self, caminho: str):
        if caminho and os.path.isfile(caminho):
            if caminho not in self._watcher.files():
                self._watcher.addPath(caminho)

    def _arquivo_alterado_no_disco(self, caminho: str):
        if self._recarregando:

            return

        if not os.path.isfile(caminho):

            return

        if caminho not in self._watcher.files():
            self._watcher.addPath(caminho)

            return

        # Reload diferido: dá tempo ao flag _salvando_internamente ser checado
        # depois que o save (assíncrono do watcher) for processado
        QTimer.singleShot(150, lambda: self._reload_diferido(caminho))

    def _reload_diferido(self, caminho: str):
        """150ms após watcher — verifica se reload é seguro antes de executar."""
        if self._recarregando:

            return

        self._recarregando = True
        try:
            for editor in self._tabs.editores.values():
                if editor.file_path != caminho:
                    continue
                if getattr(editor, "_salvando_internamente", False):
                    # Ainda dentro do janela de save — ignora

                    return

                if editor.is_modified():
                    # Usuário tem edições não salvas — não sobrescreve

                    return

                editor.load_file(caminho)
        finally:
            self._recarregando = False

    # Persistencia de sessao

    # ⚠️  except genérico vazio
    def salvar_sessao(self, projeto: str = '') -> None:
        try:
            editores = self._tabs.editores
            caminhos = [
                e.file_path for e in editores.values()
                if getattr(e, 'file_path', None)
                and os.path.isfile(e.file_path)
                and not _eh_arquivo_interno(e.file_path)
            ]
            ativo = ''
            editor_ativo = self._tabs.get_current_editor()
            if editor_ativo:
                ativo = getattr(editor_ativo, 'file_path', '') or ''
            os.makedirs(_PASTA_APPDATA, exist_ok=True)
            with open(_ARQUIVO_SESSAO, 'w', encoding='utf-8') as f:
                json.dump({'abas': caminhos, 'ativo': ativo, 'projeto': projeto}, f,
                          ensure_ascii=False, indent=2)
        except Exception:
            pass

    def restaurar_sessao(self, projeto_esperado: str = None) -> tuple:
        """
        Restaura as abas salvas em sessao.json.

        projeto_esperado: quando informado, so agenda a abertura das abas se
        o 'projeto' salvo bater com ele (normcase/abspath) - evita abrir abas
        de um projeto antigo quando o usuario esta abrindo um projeto
        diferente (cada projeto tem sua propria sessao - ver IMP-08).
        """
        if not os.path.isfile(_ARQUIVO_SESSAO):

            return (False, '')

        try:
            with open(_ARQUIVO_SESSAO, 'r', encoding='utf-8') as f:
                dados = json.load(f)
            caminhos = [c for c in dados.get('abas', [])
                        if isinstance(c, str)
                        and os.path.isfile(c)
                        and not _eh_arquivo_interno(c)]
            ativo   = dados.get('ativo', '')
            projeto = dados.get('projeto', '')
        except Exception:

            return (False, '')

        if projeto_esperado is not None:
            _norm_esperado = os.path.normcase(os.path.realpath(projeto_esperado))
            _norm_sessao   = os.path.normcase(os.path.realpath(projeto)) if projeto else ''
            if _norm_esperado != _norm_sessao:

                return (False, projeto)

        if not caminhos:

            return (False, '')

        # Arquivo ativo abre primeiro (delay=0 -> usuario ve imediatamente)
        # Demais arquivos escalonados a cada 80 ms -> sem freeze na UI
        priorizado = [c for c in caminhos if c == ativo]
        outros     = [c for c in caminhos if c != ativo]
        ordem = priorizado + outros

        total = len(ordem)
        for i, caminho in enumerate(ordem):
            e_ultimo = (i == total - 1)
            QTimer.singleShot(
                i * 80,
                lambda c=caminho, u=e_ultimo, a=ativo:
                    self._abrir_sessao_item(c, a, u),
            )

        return (True, projeto)

    def _abrir_sessao_item(self, caminho: str, caminho_ativo: str, e_ultimo: bool) -> None:
        if not os.path.isfile(caminho) or _eh_arquivo_interno(caminho):

            return

        self._tabs.add_new_tab(caminho)
        if e_ultimo and caminho_ativo:
            for indice, editor in self._tabs.editores.items():
                if getattr(editor, 'file_path', '') == caminho_ativo:
                    self._tabs.setCurrentIndex(indice)
                    break

    def recarregar_todos(self):
        for editor in self._tabs.editores.values():
            if editor.file_path and os.path.isfile(editor.file_path):
                editor.load_file(editor.file_path)
