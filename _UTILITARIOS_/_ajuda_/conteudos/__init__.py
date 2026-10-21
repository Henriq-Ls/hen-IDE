# 📁 _UTILITARIOS_/_ajuda_/conteudos/__init__.py
"""
Um arquivo por tela/módulo que tem botão de ajuda. Cada arquivo expõe
uma função `texto() -> str` com o HTML (RichText) do popup daquela tela.

Arquivos existentes:
- busca.py        → barra de busca universal (_APP_/barra_buscas.py)
- tarefas.py      → painel de tarefas F2–F10 (_TERMINAIS_/Tarefas/tarefas_explorer.py)
- filetree.py     → árvore do projeto (_PAINEL_ESQUERDO_/FileTree/painel.py)
- git_terminal.py → terminal Git ⎇ Git (_APP_/main_window/mixin_terminal_debug.py)
- painel_ia_chat.py → painel de IA / Sage (_PAINEL_DIREITO_/Ias/painel_ia.py)
- config_ia.py      → configurações da IA (_PAINEL_DIREITO_/Ias/painel_config_ia.py)
- nucleo.py         → painel Núcleo / Projeto (_NUCLEO_/painel_projeto.py)

Pra adicionar ajuda numa tela nova, crie `<nome_da_tela>.py` aqui com uma
função `texto()` e importe ela onde for criar o botão (ver docstring de
`_ajuda_/__init__.py`).
"""
