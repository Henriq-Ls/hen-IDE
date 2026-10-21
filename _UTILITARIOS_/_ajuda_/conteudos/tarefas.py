# 📁 _UTILITARIOS_/_ajuda_/conteudos/tarefas.py
"""Texto de ajuda do painel de Tarefas F2–F10 (_TERMINAIS_/Tarefas/tarefas_explorer.py)."""
from _CONFIGURA_.gerenciador_tema import tema_global


def texto() -> str:
    """HTML de ajuda de como usar o painel de tarefas."""
    verde = tema_global().cor("grafo.no_texto", "#4ec994")

    return f"""
<h3 style='color:{verde}'>Tarefas — F2 a F10</h3>
<p>Cada tarefa é um atalho de teclado que executa algo.<br>
Pressione a tecla correspondente a qualquer momento.</p>

<b>Tipos de ação:</b>
<ul>
  <li><b>Executar comando</b> — qualquer comando de terminal</li>
  <li><b>Executar Python</b> — escolhe um .py e argumentos</li>
  <li><b>Script PowerShell</b> — executa um .ps1</li>
  <li><b>Abrir pasta</b> — abre pasta no Explorer</li>
</ul>

<b>Variáveis disponíveis nos campos:</b>
<ul>
  <li><code>$PYTHON</code> — Python do venv do projeto (ou IDE)</li>
  <li><code>$PROJETO</code> — pasta raiz do projeto aberto</li>
  <li><code>$ARQUIVO</code> — arquivo aberto no editor</li>
  <li><code>$VENV</code> — pasta .venv do projeto</li>
  <li><code>$TAREFAS</code> — pasta de tarefas globais</li>
</ul>

<b>Exemplos:</b>
<ul>
  <li><code>python $ARQUIVO</code> — executa o arquivo aberto</li>
  <li><code>$PYTHON main.py --debug</code> — usa Python do venv</li>
  <li><code>pytest $PROJETO</code> — roda testes do projeto</li>
  <li><code>pip install flask</code> — instala pacote</li>
</ul>

<p><b>Dica:</b> clique em <b>Salvar</b> após editar. O atalho fica ativo imediatamente.</p>
"""
