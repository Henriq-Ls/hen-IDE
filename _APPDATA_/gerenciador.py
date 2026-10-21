# 📁 _APPDATA_/gerenciador.py
"""
_APPDATA_/gerenciador.py

GerenciadorAppData — Singleton Facade do AppData da hein IDE.

É o ponto único de acesso a tudo que vive em %APPDATA%/hein/.
Nenhum módulo da IDE deve montar caminhos de AppData na mão.
Todos consultam esta classe.

Uso:
    from _APPDATA_ import appdata
    caminho = appdata.estado_editor
    appdata.restaurar_padrao("tema")

Inicialização (uma vez, em main.py ou MainWindow.__init__):
    from _APPDATA_ import appdata
    appdata.inicializar()
"""

import os
import shutil
import sys
from _CONFIGURA_ import (
    PASTA_APPDATA,
    PASTA_VENV_HEIN,
    PASTA_TAREFAS,
    ARQUIVO_LAYOUT,
    ARQUIVO_RECENTES,
    ARQUIVO_SESSAO,
    ARQUIVO_TAREFAS_GLOBAIS,
)
from _APPDATA_.estrutura import garantir_estrutura
# ─── Mapeamento: componente → nome do arquivo ativo dentro de AppData/ ────────
# O nome é relativo a PASTA_APPDATA (usa "/" mesmo no Windows — os.path.join
# normaliza na hora de montar o caminho).
#
# "tema" é o único caso especial: a fonte de fábrica não vive em _CONFIGURA_/
# (foi removida de lá para eliminar a duplicata — ver _DOC_APPDATA_.txt),
# e sim no pacote de temas pré-instalados _APPDATA_/temas/, ao lado deste
# módulo. Os demais componentes vêm direto de _CONFIGURA_/, a fonte de
# verdade única do projeto.

_MAPA_RESTORE: dict[str, str] = {
    "tema":         "temas/tema_padrao.json",
    "configurar":   "configuracoes/configurar.json",
    "atalhos":      "configuracoes/atalhos.json",
    "autocomplete": "configuracoes/autocomplete.json",
    "perfil":       "configuracoes/perfil.json",
}

class GerenciadorAppData:
    """
    Singleton — instância única durante toda a vida do processo.

    Responsabilidades:
      - Garantir a estrutura de pastas/arquivos do AppData (inicializar)
      - Expor caminhos canônicos como propriedades (nunca strings soltas)
      - Restaurar configurações ao padrão de fábrica (restaurar_padrao)
    """

    _instancia: "GerenciadorAppData | None" = None

    def __init__(self) -> None:
        self._inicializado: bool = False
        self._pasta_configura: str = ""

    # ─── Singleton ───────────────────────────────────────────────────────────

    @classmethod
    def instancia(cls) -> "GerenciadorAppData":
        """Retorna (ou cria) a instância única do gerenciador."""
        if cls._instancia is None:
            cls._instancia = cls()

        return cls._instancia

    # ─── Inicialização ───────────────────────────────────────────────────────

    # ⚠️  except genérico vazio
    def inicializar(self) -> None:
        """
        Garante a estrutura completa do AppData.
        Deve ser chamado UMA vez na inicialização da IDE.
        Idempotente: chamadas subsequentes retornam imediatamente.
        """
        if self._inicializado:

            return

        import _CONFIGURA_ as _cfg_mod
        pasta_configura = os.path.dirname(_cfg_mod.__file__)
        self._pasta_configura = pasta_configura

        criados = garantir_estrutura(PASTA_APPDATA, pasta_configura)

        if criados:
            try:
                from _LOG_.log import log
                for p in criados:
                    log.ok("GerenciadorAppData", "inicializar",
                           f"estrutura criada: {p}")
            except Exception:
                pass

        self._inicializado = True

    # ─── Propriedades — AppData raiz ─────────────────────────────────────────

    @property
    def raiz(self) -> str:
        """Pasta raiz do AppData: %APPDATA%/hein/"""

        return PASTA_APPDATA

    @property
    def layout(self) -> str:
        """layout.json — larguras de splitters e tema Qt ativo."""

        return ARQUIVO_LAYOUT

    @property
    def recentes(self) -> str:
        """recentes.json — histórico de projetos recentes."""

        return ARQUIVO_RECENTES

    @property
    def sessao(self) -> str:
        """sessao.json — abas e projeto da última sessão."""

        return ARQUIVO_SESSAO

    @property
    def tarefas_globais(self) -> str:
        """tarefas.json — tarefas globais da IDE."""

        return ARQUIVO_TAREFAS_GLOBAIS

    @property
    def github_config(self) -> str:
        """github_config.json — token OAuth GitHub."""

        return os.path.join(PASTA_APPDATA, "github_config.json")

    # ─── Propriedades — subpastas ────────────────────────────────────────────

    @property
    def conf_bakup(self) -> str:
        """_conf_bakup/ — backups automáticos das configurações globais."""

        return os.path.join(PASTA_APPDATA, "_conf_bakup")

    @property
    def estado_editor(self) -> str:
        """estado_editor/ — estado salvo por arquivo (cursor, scroll, BPs)."""

        return os.path.join(PASTA_APPDATA, "estado_editor")

    @property
    def configuracoes(self) -> str:
        """configuracoes/ — JSONs editáveis pelo usuário (atalhos, tema de
        UI, perfil, núcleo, autocomplete) — os mesmos da aba "Configurações"
        do menu."""

        return os.path.join(PASTA_APPDATA, "configuracoes")

    @property
    def tarefas(self) -> str:
        """tarefas/ — scripts e tarefas do usuário (Twitch e futuros)."""

        return PASTA_TAREFAS

    @property
    def autocompletar(self) -> str:
        """autocompletar/ — templates de autocompletar editáveis pelo usuário."""

        return os.path.join(PASTA_APPDATA, "autocompletar")

    @property
    def temas(self) -> str:  # IMP-04
        """temas/ — temas instalados e baixados pelo usuário."""

        return os.path.join(PASTA_APPDATA, "temas")

    # ─── Propriedades — venv compartilhada ───────────────────────────────────

    @property
    def venv_compartilhada(self) -> str:
        """_venv_hein_/ — venv de pacotes globais do usuário da hein."""

        return PASTA_VENV_HEIN

    @property
    def python_compartilhado(self) -> str:
        """
        Caminho do executável Python da venv compartilhada.
        O arquivo pode não existir se a venv ainda não foi criada.
        """
        if sys.platform == "win32":

            return os.path.join(PASTA_VENV_HEIN, "Scripts", "python.exe")

        return os.path.join(PASTA_VENV_HEIN, "bin", "python")

    @property
    def venv_compartilhada_existe(self) -> bool:
        """True se a venv compartilhada já foi criada."""

        return os.path.isfile(self.python_compartilhado)

    # ─── Restore ─────────────────────────────────────────────────────────────

    def _resolver_origem_restore(self, componente: str) -> str | None:
        """
        Resolve o caminho de origem (arquivo de fábrica) para *componente*.

        "tema" vem do pacote de temas pré-instalados (_APPDATA_/temas/),
        os demais vêm direto de _CONFIGURA_/ — a fonte de verdade única
        do projeto, sempre atualizada junto com o código.
        """
        nome_relativo = _MAPA_RESTORE.get(componente)
        if nome_relativo is None:

            return None

        if componente == "tema":

            return os.path.join(os.path.dirname(__file__), "temas", "tema_padrao.json")

        pasta_configura = self._pasta_configura
        if not pasta_configura:
            # inicializar() ainda não rodou — resolve na hora, sem cachear.
            import _CONFIGURA_ as _cfg_mod
            pasta_configura = os.path.dirname(_cfg_mod.__file__)

        return os.path.join(pasta_configura, nome_relativo)

    # ⚠️  função grande (60 linhas) | except genérico vazio
    def restaurar_padrao(self, componente: str) -> bool:
        """
        Restaura um arquivo de configuração ao padrão de fábrica.

        componente : "tema" | "configurar" | "atalhos" | "autocomplete" | "nucleo" | "perfil"

        A fonte de fábrica é lida direto de _CONFIGURA_/ (ou, no caso de
        "tema", do pacote de temas pré-instalados) — nunca de uma cópia
        pré-extraída em AppData/. Isso garante que "Restaurar Padrões"
        sempre reflita a versão de fábrica atual, mesmo depois de uma
        atualização da IDE.

        Retorna True em sucesso, False em falha (arquivo de fábrica ausente,
        componente desconhecido, erro de I/O).

        ⚠ O chamador é responsável por disparar o hot-reload após restaurar.
        """
        if componente not in _MAPA_RESTORE:
            try:
                from _LOG_.log import log
                log.aviso("GerenciadorAppData", "restaurar_padrao",
                          f"componente desconhecido: '{componente}'")
            except Exception:
                pass

            return False

        src = self._resolver_origem_restore(componente)
        nome_relativo = _MAPA_RESTORE[componente]
        dst = os.path.join(PASTA_APPDATA, *nome_relativo.split("/"))

        if not src or not os.path.isfile(src):
            try:
                from _LOG_.log import log
                log.aviso("GerenciadorAppData", "restaurar_padrao",
                          f"arquivo de fábrica ausente: {src}")
            except Exception:
                pass

            return False

        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            try:
                from _LOG_.log import log
                log.ok("GerenciadorAppData", "restaurar_padrao",
                       f"'{componente}' restaurado → {dst}")
            except Exception:
                pass

            return True

        except Exception as e:
            try:
                from _LOG_.log import log
                log.erro("GerenciadorAppData", "restaurar_padrao",
                         f"falha ao restaurar '{componente}'", str(e))
            except Exception:
                pass

            return False
