# 📁 _UTILITARIOS_/_ajuda_/conteudos/busca.py
"""Texto de ajuda da barra de busca universal (_APP_/barra_buscas.py)."""
from _CONFIGURA_.gerenciador_tema import tema_global
from _UTILITARIOS_._ajuda_.atalhos import tecla_de

# ação (chave de _CONFIGURA_/gerenciador_atalhos.py) → descrição em português
_ACOES = (
    ("busca::AbrirBarra",          "abrir barra"),
    ("busca::BuscarNoArquivo",     "buscar no arquivo"),
    ("busca::AbrirSubstituicao",   "substituir"),
    ("busca::IrParaLinha",         "ir para linha (:)"),
    ("busca::BuscarMarcacao",      "marcações (#marcação)"),
    ("busca::BuscarNoProjeto",     "buscar no projeto (@)"),
    ("busca::AbrirArquivoPorNome", "buscar arquivo (*)"),
    ("busca::AbrirCommandPalette", "command palette (&gt;)"),
)


def texto() -> str:
    """
    HTML de ajuda da busca universal. As teclas são lidas do atalhos.json
    NO MOMENTO do clique (via `tecla_de`) — se o usuário remapear algum
    atalho, este popup já mostra a tecla nova, sem precisar editar nada
    aqui.
    """
    verde = tema_global().cor("grafo.no_texto", "#4ec994")
    atalhos_html = "".join(
        f"<li><code>{tecla_de(acao)}</code> — {label}</li>"
        for acao, label in _ACOES
    )

    return f"""
<h3 style='color:{verde}'>Busca universal</h3>
<p>Digite direto na barra — sem prefixo, ela busca no arquivo atual.</p>

<b>Prefixos:</b>
<ul>
  <li><b>@termo</b> — busca em todo o projeto</li>
  <li><b>*nome</b> — busca arquivo pelo nome</li>
  <li><b>:42</b> — vai para a linha 42</li>
  <li><b>#marcação</b> — lista marcações do projeto (TODO, LEMBRAR, CONSERTAR, FAZER, GAMBIARRA)</li>
  <li><b>&gt;comando</b> — command palette</li>
</ul>

<b>Atalhos:</b>
<ul>
{atalhos_html}
</ul>

<p><b>Navegação:</b> ▲▼ ou Enter para ir entre ocorrências. <b>Aa</b> diferencia maiúsculas, <b>.*</b> ativa regex.</p>
"""
