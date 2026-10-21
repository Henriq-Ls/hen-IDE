# 📁 _EDITOR_/Core/estado_editor.py
# -*- coding: utf-8 -*-
"""
Persiste o estado do editor (breakpoints, bookmarks, dobramento, posição do
cursor) em JSON no diretório de dados do usuário da IDE.

Arquivo por caminho de arquivo: cada arquivo aberto tem seu próprio .json.
Localização: %APPDATA%/hein/estado_editor/<nome_seguro>.json
"""
import json
import os
import re
from _LOG_.log import log
_ARQ = "estado_editor.py"

try:
    from _CONFIGURA_ import PASTA_APPDATA
except ImportError:
    PASTA_APPDATA = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "hein")

_PASTA_ESTADOS = os.path.join(PASTA_APPDATA, "estado_editor")

def _caminho_estado(caminho_arquivo: str) -> str:
    """Retorna o caminho do arquivo .json para o estado de <caminho_arquivo>."""
    # Substitui TODOS os chars especiais incluindo \ e . para evitar:
    # (a) subdirectories fantasmas por barras no path, (b) duplo .json.json
    seguro = re.sub(r'[\\/:*?"<>|.]', '_', caminho_arquivo)
    seguro = seguro.strip("_").replace(" ", "_")
    if len(seguro) > 180:
        seguro = seguro[:80] + "___" + seguro[-80:]

    return os.path.join(_PASTA_ESTADOS, seguro + ".json")

class EstadoEditor:
    """
    Mantém e persiste o estado completo de um arquivo aberto no editor.

    Estado persistido (JSON em disco):
        breakpoints  — set[int]         linhas com breakpoint (1-based)
        bookmarks    — set[int]         linhas marcadas (1-based)
        folds        — set[int]         linhas recolhidas (1-based)
        cursor_linha — int              última posição do cursor
        cursor_col   — int              última coluna do cursor
        scroll_y     — int              última posição vertical do scroll
    """

    def __init__(self):
        self.caminho_arquivo: str | None = None
        self.texto_original:  str        = ""

        # Estado em memória
        self._breakpoints: set[int] = set()
        self._bookmarks:   set[int] = set()
        self._folds:       set[int] = set()
        self._cursor_linha: int = 1
        self._cursor_col:   int = 0
        self._scroll_y:     int = 0

    # ── Arquivo ───────────────────────────────────────────────────────

    def definir_caminho(self, caminho: str) -> None:
        self.caminho_arquivo = caminho

    def definir_texto_original(self, texto: str) -> None:
        self.texto_original = texto

    def foi_modificado(self, texto_atual: str) -> bool:
        return texto_atual != self.texto_original

    # ── Breakpoints ───────────────────────────────────────────────────

    def definir_breakpoints(self, bps: set[int]) -> None:
        self._breakpoints = set(bps)

    def obter_breakpoints(self) -> set[int]:
        return set(self._breakpoints)

    def alternar_breakpoint(self, linha: int) -> bool:
        """Alterna o breakpoint na linha. Retorna True se adicionou, False se removeu."""
        if linha in self._breakpoints:
            self._breakpoints.discard(linha)

            return False

        else:
            self._breakpoints.add(linha)

            return True

    # ── Bookmarks ─────────────────────────────────────────────────────

    def definir_bookmarks(self, bms: set[int]) -> None:
        self._bookmarks = set(bms)

    def obter_bookmarks(self) -> set[int]:
        return set(self._bookmarks)

    def alternar_bookmark(self, linha: int) -> bool:
        """Alterna o bookmark na linha. Retorna True se adicionou, False se removeu."""
        if linha in self._bookmarks:
            self._bookmarks.discard(linha)

            return False

        else:
            self._bookmarks.add(linha)

            return True

    # ── Dobramento (folds) ────────────────────────────────────────────

    def definir_folds(self, folds: set[int]) -> None:
        self._folds = set(folds)

    def obter_folds(self) -> set[int]:
        return set(self._folds)

    # ── Posição de cursor e scroll ────────────────────────────────────

    def definir_posicao(self, linha: int, col: int, scroll_y: int = 0) -> None:
        self._cursor_linha = linha
        self._cursor_col   = col
        self._scroll_y     = scroll_y

    def obter_posicao(self) -> tuple[int, int, int]:
        """Retorna (linha, col, scroll_y)."""

        return self._cursor_linha, self._cursor_col, self._scroll_y

    # ── Persistência JSON ─────────────────────────────────────────────

    def salvar(self) -> None:
        """Salva o estado atual em disco. Silencioso em caso de erro."""
        if not self.caminho_arquivo:

            return

        try:
            os.makedirs(_PASTA_ESTADOS, exist_ok=True)
            caminho_json = _caminho_estado(self.caminho_arquivo)
            payload = {
                "arquivo":      self.caminho_arquivo,
                "breakpoints":  sorted(self._breakpoints),
                "bookmarks":    sorted(self._bookmarks),
                "folds":        sorted(self._folds),
                "cursor_linha": self._cursor_linha,
                "cursor_col":   self._cursor_col,
                "scroll_y":     self._scroll_y,
            }
            with open(caminho_json, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            log.info(_ARQ, "salvar", f"estado salvo: {os.path.basename(caminho_json)}")
        except Exception as e:
            log.aviso(_ARQ, "salvar", f"falha ao salvar estado", str(e))

    def carregar(self) -> bool:
        """
        Carrega o estado do disco para o arquivo atual.
        Retorna True se encontrou e carregou, False se não havia arquivo de estado.
        """
        if not self.caminho_arquivo:

            return False

        caminho_json = _caminho_estado(self.caminho_arquivo)
        if not os.path.isfile(caminho_json):

            return False

        try:
            with open(caminho_json, encoding="utf-8") as f:
                payload = json.load(f)
            self._breakpoints  = set(int(x) for x in payload.get("breakpoints", []))
            self._bookmarks    = set(int(x) for x in payload.get("bookmarks",   []))
            self._folds        = set(int(x) for x in payload.get("folds",       []))
            self._cursor_linha = int(payload.get("cursor_linha", 1))
            self._cursor_col   = int(payload.get("cursor_col",   0))
            self._scroll_y     = int(payload.get("scroll_y",     0))
            log.info(_ARQ, "carregar", f"estado carregado: {len(self._breakpoints)} BPs, "
                     f"{len(self._bookmarks)} bookmarks, {len(self._folds)} folds")

            return True

        except Exception as e:
            log.aviso(_ARQ, "carregar", f"falha ao carregar estado", str(e))

            return False

    # ⚠️  except genérico vazio
    def apagar(self) -> None:
        """Remove o arquivo de estado do disco (usado ao fechar / resetar)."""
        if not self.caminho_arquivo:

            return

        caminho_json = _caminho_estado(self.caminho_arquivo)
        try:
            if os.path.isfile(caminho_json):
                os.remove(caminho_json)
        except Exception:
            pass

    def limpar_memoria(self) -> None:
        """Limpa o estado em memória sem apagar o disco."""
        self._breakpoints  = set()
        self._bookmarks    = set()
        self._folds        = set()
        self._cursor_linha = 1
        self._cursor_col   = 0
        self._scroll_y     = 0
