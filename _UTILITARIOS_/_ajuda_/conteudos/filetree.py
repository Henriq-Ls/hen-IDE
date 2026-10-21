# 📁 _UTILITARIOS_/_ajuda_/conteudos/filetree.py
"""Texto de ajuda da árvore do projeto (_PAINEL_ESQUERDO_/FileTree/painel.py)."""
from _CONFIGURA_.gerenciador_tema import tema_global


def texto() -> str:
    """
    HTML de ajuda da árvore de arquivos. Atalhos aqui (F2, Delete, Ctrl+C,
    Ctrl+V, Ctrl+Z) são tratados direto no keyPressEvent da árvore — não
    passam pelo atalhos.json, então não têm `tecla_de()` dinâmico (não são
    remapeáveis pelo usuário hoje).
    """
    verde = tema_global().cor("grafo.no_texto", "#4ec994")

    return f"""
<h3 style='color:{verde}'>Árvore do Projeto</h3>

<h4>Abrir arquivos</h4>
<ul>
<li><b>Duplo clique</b> — abre no editor central</li>
<li><b>Clique simples</b> — troca para a aba já aberta</li>
<li><b>Clique simples em pasta</b> — expande ou colapsa</li>
</ul>

<h4>Indicadores Git</h4>
<ul>
<li><b>Amarelo</b> — arquivo novo (untracked)</li>
<li><b>Laranja</b> — modificado, não commitado</li>
<li><b>Vermelho</b> — deletado localmente</li>
<li>Bolinha: <b>+</b> novo · <b>~</b> modificado · <b>×</b> deletado</li>
</ul>

<h4>Menu de contexto (clique direito)</h4>
<ul>
<li><b>Novo Arquivo / Nova Pasta</b> — cria na pasta selecionada</li>
<li><b>Renomear</b> — edição inline (também: F2)</li>
<li><b>Apagar</b> — move para .hein/lixeira (recuperável com Ctrl+Z)</li>
<li><b>Enviar para IA</b> — análise direta do arquivo</li>
<li><b>Abrir no Navegador</b> — arquivos .html</li>
<li><b>Adicionar ao Git</b> — executa git add</li>
</ul>

<h4>Atalhos (foco na árvore)</h4>
<table>
<tr><td><b>F2</b></td><td>Renomear inline</td></tr>
<tr><td><b>Delete</b></td><td>Apagar (para lixeira)</td></tr>
<tr><td><b>Ctrl+C</b></td><td>Copiar</td></tr>
<tr><td><b>Ctrl+V</b></td><td>Colar (duplica)</td></tr>
<tr><td><b>Ctrl+Z</b></td><td>Desfazer</td></tr>
</table>

<h4>Drag-and-drop</h4>
<p>Arraste arquivos ou pastas para movê-los dentro do projeto.</p>

<hr/>
<p><i>A pasta .hein/lixeira guarda apagados — limpe via "Esvaziar Lixeira".</i></p>
"""
