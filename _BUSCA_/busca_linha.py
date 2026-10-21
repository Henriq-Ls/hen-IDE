# 📁 _BUSCA_/busca_linha.py
# coding: utf-8
from .modelo_resultado import ResultadoBusca, TipoBusca

def buscar_linha(termo: str) -> list[ResultadoBusca]:
    """termo = ':42' ou '42' — navega no editor atual."""
    try:
        num = int(termo.lstrip(":").strip())
        if num < 1:

            return []

        return [ResultadoBusca(

            tipo=TipoBusca.LINHA,
            titulo=f"Ir para linha {num}",
            subtitulo="no arquivo atual",
            linha=num - 1,
            icone="fa5s.level-down-alt",
        )]
    except ValueError:

        return []
