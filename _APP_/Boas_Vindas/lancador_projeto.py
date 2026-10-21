# _APP_/lancador_projeto.py
"""
Único ponto de lançamento de um projeto em processo separado.
Tanto o main.py (modo boot) quanto o main_window.py (modo dialog)
chamam esta função — ninguém reimplementa o Popen na mão.
"""
import os
import subprocess
import sys
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console


def _log(func: str, msg: str, erro: bool = False) -> None:
    try:
        from _LOG_.log import log
        if erro:
            log.erro("lancador_projeto.py", func, msg)
        else:
            log.info("lancador_projeto.py", func, msg)
    except Exception:
        pass


def abrir_projeto_novo_processo(caminho: str) -> None:
    """Spawna uma nova instância da IDE já apontando para `caminho`.

    Este caminho é usado apenas para abrir uma janela independente. A
    primeira abertura, partindo do picker de boot, acontece no mesmo processo.
    """
    _log("abrir_projeto_novo_processo", f"início: caminho={caminho}")

    # Em desenvolvimento, o alvo é o interpretador + main.py. Em um bundle
    # PyInstaller, o alvo já é o próprio executável: não existe um main.py
    # executável fora do bundle para ser passado como argumento.
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main_py = os.path.join(raiz, "main.py")
    if getattr(sys, "frozen", False):
        comando = [sys.executable, f"--projeto={caminho}"]
        diretorio = os.path.dirname(os.path.abspath(sys.executable))
    else:
        comando = [sys.executable, main_py, f"--projeto={caminho}"]
        diretorio = raiz

    _log(
        "abrir_projeto_novo_processo",
        f"comando={comando!r}; cwd={diretorio!r}; "
        f"frozen={getattr(sys, 'frozen', False)!r}",
    )
    try:
        processo = subprocess.Popen(
            comando,
            cwd=diretorio,
            close_fds=True,
            **opcoes_processo_sem_console(),
        )
    except Exception as exc:
        _log(
            "abrir_projeto_novo_processo",
            f"exceção ao lançar novo processo: {exc!r}",
            erro=True,
        )
        raise
    _log(
        "abrir_projeto_novo_processo",
        f"novo processo iniciado: pid={processo.pid}; comando={comando!r}",
    )
