# 📁 _UTILITARIOS_/_ajuda_/conteudos/git_terminal.py
"""Texto de ajuda do terminal Git (aba ⎇  Git no painel de terminais)."""
from _CONFIGURA_.gerenciador_tema import tema_global


def texto() -> str:
    v = tema_global().cor("grafo.no_texto",         "#4ec994")  # verde
    a = tema_global().cor("editor.info",            "#4ec9c9")  # azul
    c = tema_global().cor("interface.texto",        "#c9d1d9")  # cinza claro
    d = tema_global().cor("interface.texto_fraco",  "#666666")  # cinza escuro

    def row(icone, nome, desc):
        return (
            f"<tr>"
            f"<td style='padding:3px 8px 3px 0; color:{d}; white-space:nowrap'>{icone}</td>"
            f"<td style='padding:3px 8px 3px 0; color:{v}; white-space:nowrap'><b>{nome}</b></td>"
            f"<td style='padding:3px 0; color:{c}'>{desc}</td>"
            f"</tr>"
        )

    def aba(nome, desc, destaque=False):
        cor = a if destaque else c
        return (
            f"<tr>"
            f"<td style='padding:3px 8px 3px 0; color:{a if destaque else d}; white-space:nowrap'><b>{nome}</b></td>"
            f"<td style='padding:3px 0; color:{cor}'>{desc}</td>"
            f"</tr>"
        )

    return f"""
<h3 style='color:{v}; margin:0 0 8px 0'>⎇&nbsp; Terminal Git</h3>

<p style='color:{d}; font-size:9px; margin:0 0 10px 0'>
Trabalha com o repositório <b style='color:{c}'>local</b> do seu computador.<br>
Só <b style='color:{c}'>Enviar</b> e <b style='color:{c}'>Baixar</b> acessam o GitHub.
</p>

<b style='color:{c}'>Botões</b>
<table cellspacing='0' cellpadding='0' style='margin:4px 0 12px 0'>
  {row("💾", "Salvar",   "Registra as mudanças no histórico local &nbsp;<code style='color:{d}'>git add + commit</code>")}
  {row("⬆", "Enviar",   "Manda os commits para o GitHub &nbsp;<code style='color:{d}'>git push</code>")}
  {row("⬇", "Baixar",   "Traz o que mudou no GitHub para cá &nbsp;<code style='color:{d}'>git pull</code>")}
  {row("🕐", "Histórico","Lista commits do projeto; <i>Restaurar</i> volta o projeto inteiro a uma versão")}
</table>

<b style='color:{c}'>Abas</b>
<table cellspacing='0' cellpadding='0' style='margin:4px 0 12px 0'>
  {aba("Status",       "Arquivos modificados. Botão direito → preparar, descartar ou remover da fila.")}
  {aba("Diferenças",   "O que mudou linha a linha em cada arquivo.")}
  {aba("Ramificações", "Cria, muda, mescla ou exclui branches.")}
  {aba("Guardados",    "Guarda mudanças sem commitar para trocar de branch depois.")}
  {aba("Arquivo ★",   "Histórico do <b>arquivo aberto no editor</b> — clique num commit para ver<br>"
                       "o conteúdo exato naquele momento. Tem busca e numeração de linha.", destaque=True)}
</table>

<b style='color:{c}'>Aba Arquivo — detalhes</b>
<ul style='margin:4px 0; padding-left:18px; color:{c}'>
  <li>Muda automaticamente ao trocar de aba no editor</li>
  <li>A busca destaca todas as ocorrências no texto</li>
  <li>Apenas leitura — não altera nada no disco</li>
</ul>
"""
