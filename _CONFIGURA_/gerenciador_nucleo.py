# 📁 _CONFIGURA_/gerenciador_nucleo.py
"""
Carrega o nucleo.json e distribui configurações do Núcleo para a IDE.
Hot-reload via QFileSystemWatcher — edite e salve dentro da IDE.

Uso em qualquer módulo:
    from _CONFIGURA_.gerenciador_nucleo import nucleo_config_global
    cfg = nucleo_config_global()
    pastas   = cfg.obter("formatar", "pastas_ignorar",  [])
    arquivos = cfg.obter("formatar", "arquivos_ignorar", [])
    provedor = cfg.obter("ia", "provedor_preferido", "ollama")
"""
import json
from pathlib import Path
from PySide6.QtCore import QFileSystemWatcher, QObject, Signal
from _CONFIGURA_ import ARQUIVO_NUCLEO, _ler_json
from _LOG_.log import log
_ARQ = "gerenciador_nucleo.py"

_PADRAO: dict = {
    "formatar": {
        "pastas_ignorar":   [],
        "arquivos_ignorar": [],
        "pastas_fixas_ignorar": [
            ".venv", ".git", "__pycache__", ".idea",
            "venv", "env", ".nox", ".tox", ".zed",
            "node_modules", ".mypy_cache", ".pytest_cache", ".hen",
        ],
        "palavras_pulo_linha":     ["return", "raise", "yield"],
        "prefixos_modulos_locais": ["_", "APP"],
        "stdlib_modulos":          [],
    },
    "diagnostico": {
        "limite_linhas_funcao":             50,
        "limite_linhas_arquivo":           500,
        "limite_arquivos_pasta":            20,
        "alertar_funcoes_nao_chamadas":    True,
        "alertar_dependencias_circulares": True,
        "alertar_modulos_sem_init":        True,
    },
    "indice": {
        "pastas_ignorar":   [],
        "arquivos_ignorar": [],
        "extensoes_texto": [
            ".py", ".html", ".htm", ".css", ".scss", ".less",
            ".js", ".ts", ".jsx", ".tsx", ".vue", ".svelte",
            ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
            ".txt", ".md", ".rst", ".xml", ".svg",
            ".sh", ".bat", ".ps1",
        ],
    },
    "documentador": {
        "system_prompt":      "Você é um assistente técnico que documenta projetos de software. Responda em português, de forma direta e objetiva.",
        "min_arquivos_pasta": 1,
        "extensoes_docaveis": [
            ".py", ".md", ".txt", ".rst",
            ".html", ".htm", ".css", ".scss",
            ".js", ".ts", ".jsx", ".tsx",
            ".json", ".yaml", ".yml", ".toml",
            ".sh", ".bat", ".sql",
        ],
    },
    "ambiente": {
        "pasta_venv": ".venv",
    },
    "ia": {
        "provedor_preferido": "ollama",
    },
    "exportar": {
        "gerar_readme":        True,
        "gerar_arquitetura":   True,
        "gerar_documentacao":  True,
        "gerar_antes_do_push": True,
    },
}

class GerenciadorNucleo(QObject):
    """Singleton que carrega e distribui o nucleo.json.

    Signals:
        configuracao_alterada — emitido quando o arquivo é salvo.
    """

    configuracao_alterada = Signal()

    def __init__(self):
        super().__init__()
        self._dados: dict = {}
        self._erro_json: str = ""  # mensagem do último erro de JSON
        self._watcher = QFileSystemWatcher()
        self._watcher.fileChanged.connect(self._ao_arquivo_alterado)
        self._carregar()

    # ── Carregamento ──────────────────────────────────────────────────────────

    def _carregar(self):
        """
        Carrega nucleo.json com cadeia de fallback.

        Cadeia:
            1. Parse + auto-repair via _ler_json()
            2. Backup (.bak) do último load bem-sucedido
            3. _PADRAO hardcoded — IDE funciona normalmente
        """
        import os
        caminho = Path(ARQUIVO_NUCLEO)
        caminho_bak = Path(str(ARQUIVO_NUCLEO) + ".bak")

        if not caminho.exists():
            self._criar_padrao(caminho)

        # ── Tentativa 1: parse + auto-repair ──────────────────────────────────
        try:
            self._dados = _ler_json(str(caminho))
            self._erro_json = ""
            log.ok(_ARQ, "_carregar", "nucleo.json carregado")
            self._salvar_backup(str(caminho), str(caminho_bak))
        except json.JSONDecodeError as e:
            self._erro_json = str(e)
            log.erro(_ARQ, "_carregar", f"JSON inválido (tentando backup): {e}")
            self._dados = None
        except Exception as e:
            self._erro_json = str(e)
            log.erro(_ARQ, "_carregar", str(e))
            self._dados = None

        # ── Tentativa 2: backup ────────────────────────────────────────────────
        if self._dados is None and caminho_bak.is_file():
            try:
                self._dados = _ler_json(str(caminho_bak))
                log.aviso(_ARQ, "_carregar", f"usando backup: {caminho_bak}")
            except Exception as e2:
                log.erro(_ARQ, "_carregar", "backup também inválido", str(e2))
                self._dados = None

        # ── Tentativa 3: padrão hardcoded ─────────────────────────────────────
        if self._dados is None:
            self._dados = dict(_PADRAO)
            log.aviso(_ARQ, "_carregar", "usando _PADRAO hardcoded — modo degradado")

        if str(caminho) not in self._watcher.files():
            self._watcher.addPath(str(caminho))

    def _salvar_backup(self, origem: str, destino: str) -> None:
        try:
            import shutil as _sh
            _sh.copy2(origem, destino)
        except Exception as e:
            log.aviso(_ARQ, "_salvar_backup", str(e))

    def _criar_padrao(self, caminho: Path):
        try:
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_text(
                json.dumps(_PADRAO, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
            log.ok(_ARQ, "_criar_padrao", "nucleo.json criado com template padrão")
        except Exception as e:
            log.erro(_ARQ, "_criar_padrao", str(e))

    def _ao_arquivo_alterado(self, caminho: str):
        if caminho not in self._watcher.files():
            self._watcher.addPath(caminho)
        self._carregar()
        self.configuracao_alterada.emit()
        log.ok(_ARQ, "_ao_arquivo_alterado", "nucleo.json recarregado")

    # ── API pública ───────────────────────────────────────────────────────────

    def obter(self, secao: str, chave: str, fallback=None):
        """Retorna um valor do nucleo.json.

        Args:
            secao:    seção de primeiro nível (ex: "formatar", "ia")
            chave:    chave dentro da seção (ex: "pastas_ignorar", "provedor_preferido")
            fallback: valor padrão se não encontrar

        Returns:
            O valor do JSON ou fallback.
        """

        return self._dados.get(secao, {}).get(chave, fallback)

    def dados(self) -> dict:
        """Retorna o dicionário completo do nucleo.json."""

        return dict(self._dados)

    def abrir_para_edicao(self, janela):
        """Abre o nucleo.json no editor da IDE."""
        tabs = getattr(janela, "tabs", None)
        if tabs:
            tabs.add_new_tab(ARQUIVO_NUCLEO)

# ── Singleton ─────────────────────────────────────────────────────────────────

_instancia: GerenciadorNucleo | None = None

def nucleo_config_global() -> GerenciadorNucleo:
    """Retorna a instância única do GerenciadorNucleo."""
    global _instancia
    if _instancia is None:
        _instancia = GerenciadorNucleo()

    return _instancia
