# 📁 _TRADUTION_/_motor.py
#
# Motor de tradução — lógica das camadas.
# NÃO contém dados. Importa tudo de _dados/.
#
# Ordem de execução (imutável — alterar quebra a tradução):
#
#   Camada 0a — normaliza underscores              (antes de tudo)
#   Camada 2  — Regex com capture groups           (vê aspas originais)
#   Camada 1  — Frases exatas                      (vê aspas originais)
#   Camada 0b — protege caminhos, código, aspas... (bloqueia Camada 3)
#   Camada 3  — Palavra a palavra                  (fallback)
#   Camada 4  — Restaura, remove redundâncias, capitaliza, limpa

import re
from functools import lru_cache
from typing import Any
from ._dados.camada0_pre      import proteger, normalizar_underscores
from ._dados.camada1_frases   import FRASES
from ._dados.camada2_regex    import PADROES
from ._dados.camada3_palavras import PALAVRAS
from ._dados.camada4_pos      import (
    restaurar,
    remover_redundancias,
    corrigir_capitalizacao,
    limpar_artefatos,
)

# ── Compilação — feita uma única vez no import ────────────────────────────────
_FRASES_COMPILADAS: list[tuple[re.Pattern, str]] = [
    (re.compile(re.escape(en), re.IGNORECASE), pt)
    for en, pt in FRASES
]

_DICIONARIO_COMPILADO: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\b' + re.escape(en) + r'\b', re.IGNORECASE), pt)
    for en, pt in PALAVRAS
]

_REGEX_CAPTURE = PADROES  # já compilados em camada2_regex.py

# ── Núcleo interno — cacheado ─────────────────────────────────────────────────
# Separado de traduzir() para que o lru_cache opere sobre str pura.
# O terminal repete a mesma linha de erro inúmeras vezes (ex: loop falhando);
# o cache zera o custo de reprocessamento nesse caso.

@lru_cache(maxsize=512)
def _traduzir_str(texto: str) -> str:
    # ── Camada 0a ─────────────────────────────────────────────────────────────
    texto = normalizar_underscores(texto)

    # ── Camada 2 — Regex com capture groups ───────────────────────────────────
    for padrao, traducao in _REGEX_CAPTURE:
        texto = padrao.sub(traducao, texto)

    # ── Camada 1 — Frases exatas ──────────────────────────────────────────────
    for padrao, traducao in _FRASES_COMPILADAS:
        texto = padrao.sub(traducao, texto)

    # ── Camada 0b — Protege antes da Camada 3 ────────────────────────────────
    texto, cofre = proteger(texto)

    # ── Camada 3 — Palavra a palavra ──────────────────────────────────────────
    for padrao, traducao in _DICIONARIO_COMPILADO:
        texto = padrao.sub(traducao, texto)

    # ── Camada 4 — Pós-processamento ─────────────────────────────────────────
    texto = restaurar(texto, cofre)
    texto = remover_redundancias(texto)
    texto = corrigir_capitalizacao(texto)
    texto = limpar_artefatos(texto)

    return texto

# ── Função pública ────────────────────────────────────────────────────────────

def traduzir(texto: Any) -> str:
    """
    Traduz uma mensagem de erro do inglês para o português.

    Camadas:
        0a — Normaliza underscores isolados
        2  — Regex com capture groups  (preserva variáveis e nomes)
        1  — Frases exatas             (contexto completo)
        0b — Protege caminhos, código, aspas, versões, pacotes, erros
        3  — Dicionário palavra a palavra  (fallback)
        4  — Restaura, remove redundâncias, capitaliza, limpa artefatos

    Uso:
        from _TRADUTION_.tradutor_erros import traduzir
        texto_pt = traduzir("NameError: name 'x' is not defined")
    """
    if not texto:
        return str(texto)

    return _traduzir_str(str(texto))
