# 📁 _BUSCA_/busca_comandos.py
# coding: utf-8
from .modelo_resultado import ResultadoBusca, TipoBusca

def _cmd(titulo: str, icone: str, acao) -> ResultadoBusca:
    return ResultadoBusca(

        tipo=TipoBusca.COMANDO,
        titulo=titulo,
        subtitulo="comando",
        icone=icone,
        acao=acao,
    )

def buscar_comandos(termo: str, janela) -> list[ResultadoBusca]:
    todos = [
        _cmd("Salvar arquivo",       "fa5s.save",          lambda: janela.salvar_arquivo()),
        _cmd("Novo arquivo",         "fa5s.plus",           lambda: janela.tabs.add_new_tab()),
        _cmd("Abrir arquivo…",       "fa5s.file-import",    lambda: janela.abrir_arquivo()),
        _cmd("Abrir projeto…",       "fa5s.folder-open",    lambda: janela.abrir_projeto()),
        _cmd("Novo projeto…",        "fa5s.folder-plus",    lambda: janela.novo_projeto()),
        _cmd("Fechar aba",           "fa5s.times",          lambda: janela.tabs.fechar_aba(janela.tabs.currentIndex())),
        _cmd("Executar arquivo",     "fa5s.play",           lambda: janela.executar_codigo()),
        _cmd("Novo terminal",        "fa5s.terminal",       lambda: janela.novo_terminal()),
        _cmd("Aumentar fonte",       "fa5s.search-plus",    lambda: janela.aumentar_fonte()),
        _cmd("Diminuir fonte",       "fa5s.search-minus",   lambda: janela.diminuir_fonte()),
        _cmd("Tela cheia",           "fa5s.expand",         lambda: janela.alternar_tela_cheia()),
        _cmd("Desfazer",             "fa5s.undo",           lambda: janela.desfazer()),
        _cmd("Refazer",              "fa5s.redo",           lambda: janela.refazer()),
        _cmd("Comentar/descomentar", "fa5s.code",           lambda: janela.comentar_linha()),
        _cmd("Formatar documento",   "fa5s.align-left",     lambda: janela.formatar_documento() if hasattr(janela, "formatar_documento") else None),
        _cmd("Ir para linha…",       "fa5s.level-down-alt", lambda: janela.ir_para_linha_dialogo()),
    ]

    filtro = termo.lstrip(">").strip().lower()
    if not filtro:

        return todos

    return [c for c in todos if filtro in c.titulo.lower()]
