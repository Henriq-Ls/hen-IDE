# 📁 _UTILITARIOS_/_ajuda_/atalhos.py
"""
Helper pra qualquer conteúdo de ajuda mostrar a tecla ATUAL de uma ação,
lendo o atalhos.json na hora — nunca hardcoded. Se o usuário remapear
uma tecla, os textos de ajuda que usam isso já mostram a tecla nova
automaticamente, sem precisar editar nada.

Uso dentro de um `_ajuda_/conteudos/<nome>.py`:

    from _UTILITARIOS_._ajuda_.atalhos import tecla_de
    f"<code>{tecla_de('busca::BuscarNoProjeto')}</code>"
"""
from _CONFIGURA_ import ARQUIVO_ATALHOS, _ler_json


def tecla_de(acao: str) -> str:
    """
    Devolve a tecla mapeada AGORA para `acao` (ex: 'busca::BuscarNoProjeto'),
    já formatada (ex: 'Ctrl+J'). Devolve '—' se a ação não estiver mapeada
    ou se o atalhos.json não puder ser lido.
    """
    try:
        from _CONFIGURA_.gerenciador_atalhos import GerenciadorAtalhos
        for bloco in _ler_json(ARQUIVO_ATALHOS):
            for tecla, acao_bloco in bloco.get("atalhos", {}).items():
                if acao_bloco == acao:
                    return GerenciadorAtalhos._converter_tecla(tecla)
    except Exception:
        pass

    return "—"
