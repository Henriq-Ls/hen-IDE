# 📁 _UTILITARIOS_/versionamento.py
"""
Utilitário compartilhado de versionamento para hein IDE.

Gerencia VERSION e CHANGELOG.md do projeto aberto.
Thread-safe: RLock de módulo garante que painel Git, IA e Executável
nunca escrevam simultaneamente nos mesmos arquivos.

Funções públicas:
  criar_changelog_inicial  → publicação inicial (b__git_ui_conta)
  registrar_changelog_commit → Git panel após commit OK (c__git_ui_projeto)
  registrar_commit         → IA após HEIN-GIT commit código 0 (ias_handlers)
  registrar_push           → Git panel e IA após push OK
  checar_regressao_versao  → UI do Executável antes de iniciar release
  registrar_release        → Executável após push da tag OK
"""
import os
import threading
from datetime import datetime

from _LOG_.log import log
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console
_ARQ  = "versionamento.py"
_lock = threading.RLock()   # reentrant — mesma thread pode chamar funções aninhadas


# ── helpers privados ──────────────────────────────────────────────────

def _data_hoje() -> str:
    return datetime.now().strftime("%d/%m/%Y")


def _ler_version(caminho_projeto: str) -> str:
    arq = os.path.join(caminho_projeto, "VERSION")
    try:
        if os.path.exists(arq):
            return open(arq, encoding="utf-8").read().strip()
    except Exception:
        pass
    return ""


def _escrever_version(caminho_projeto: str, versao: str) -> None:
    arq = os.path.join(caminho_projeto, "VERSION")
    with open(arq, "w", encoding="utf-8") as f:
        f.write(versao + "\n")


def _incrementar_patch(versao: str) -> str:
    """v0.1.4 → v0.1.5. Devolve a mesma string se não conseguir parsear."""
    try:
        sem_v  = versao.lstrip("v")
        partes = sem_v.split(".")
        if len(partes) != 3:
            return versao
        major, minor, patch = int(partes[0]), int(partes[1]), int(partes[2])
        patch += 1
        return f"v{major}.{minor}.{patch}"
    except Exception:
        return versao


def _nums(versao: str) -> tuple:
    """Converte 'v1.2.3' em (1, 2, 3) para comparação. Lança ValueError se inválido."""
    return tuple(int(x) for x in versao.lstrip("v").split("."))


def _garantir_version(caminho_projeto: str) -> str:
    """
    Retorna a versão atual do projeto.
    Se VERSION não existir:
      1. Tenta ler da tag git mais recente (git describe --tags --abbrev=0).
      2. Cai em 'v0.1.0' como padrão.
      3. Cria o arquivo VERSION com o valor encontrado.
    Deve ser chamado DENTRO de _lock (não adquire o lock novamente).
    """
    versao = _ler_version(caminho_projeto)
    if versao:
        return versao

    # Tenta obter do git antes de usar o padrão
    try:
        import subprocess
        r = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=caminho_projeto,
            capture_output=True, text=True, timeout=5,
            **opcoes_processo_sem_console(),
        )
        if r.returncode == 0:
            versao = r.stdout.strip()
    except Exception:
        pass

    if not versao:
        versao = "v0.1.0"

    try:
        _escrever_version(caminho_projeto, versao)
        log.ok(_ARQ, "_garantir_version",
               f"VERSION criado em '{caminho_projeto}': {versao}")
    except Exception as e:
        log.erro(_ARQ, "_garantir_version", f"falha ao criar VERSION: {e}")

    return versao


def _prepend_changelog(caminho_projeto: str, entrada: str) -> None:
    """Insere uma seção no topo do CHANGELOG.md (abaixo do cabeçalho fixo)."""
    arq = os.path.join(caminho_projeto, "CHANGELOG.md")
    try:
        if os.path.exists(arq):
            conteudo = open(arq, encoding="utf-8").read()
        else:
            conteudo = "# Histórico do projeto\n\n"

        # Mantém a primeira linha (# Histórico...) no topo, insere logo abaixo
        partes = conteudo.split("\n", 1)
        cabecalho = partes[0]
        resto     = partes[1].lstrip("\n") if len(partes) > 1 else ""
        novo = f"{cabecalho}\n\n{entrada.rstrip()}\n\n{resto}".rstrip() + "\n"

        with open(arq, "w", encoding="utf-8") as f:
            f.write(novo)
    except Exception as e:
        log.erro(_ARQ, "_prepend_changelog", str(e))


# ── API pública ───────────────────────────────────────────────────────

def criar_changelog_inicial(caminho_projeto: str) -> None:
    """
    Cria CHANGELOG.md com cabeçalho vazio.
    Chamado por b__git_ui_conta._ao_publicar_projeto na publicação inicial.
    Idempotente — não faz nada se o arquivo já existir.
    """
    with _lock:
        arq = os.path.join(caminho_projeto, "CHANGELOG.md")
        if os.path.exists(arq):
            return
        try:
            with open(arq, "w", encoding="utf-8") as f:
                f.write("# Histórico do projeto\n\n")
            log.ok(_ARQ, "criar_changelog_inicial",
                   f"CHANGELOG.md criado em {caminho_projeto}")
        except Exception as e:
            log.erro(_ARQ, "criar_changelog_inicial", str(e))


def registrar_changelog_commit(
    caminho_projeto: str, mensagem: str, versao: str
) -> None:
    """
    Registra entrada de commit no CHANGELOG.md.
    VERSION já foi escrito pelo painel Git antes do commit — não reescreve.

    Chamado por c__git_ui_projeto._ao_salvar (dentro de _concluido, após r.ok).
    """
    with _lock:
        try:
            entrada = f"## {versao} — {_data_hoje()}\n- {mensagem}"
            _prepend_changelog(caminho_projeto, entrada)
            log.ok(_ARQ, "registrar_changelog_commit",
                   f"{versao}: {mensagem[:50]}")
        except Exception as e:
            log.erro(_ARQ, "registrar_changelog_commit", str(e))


def registrar_commit(caminho_projeto: str, mensagem: str) -> str:
    """
    Lê VERSION (criando-o se ausente), bumpa patch, escreve VERSION e CHANGELOG.md.
    Uso da IA: o commit já foi feito, o bump vem depois e entra no próximo commit.

    Chamado por ias_handlers._processar_hein_git (código 0, comando commit).
    Retorna a nova versão.
    """
    with _lock:
        versao_atual = _garantir_version(caminho_projeto)   # cria se não existir
        nova_versao = _incrementar_patch(versao_atual)
        try:
            _escrever_version(caminho_projeto, nova_versao)
            entrada = f"## {nova_versao} — {_data_hoje()}\n- {mensagem}"
            _prepend_changelog(caminho_projeto, entrada)
            log.ok(_ARQ, "registrar_commit",
                   f"{versao_atual} → {nova_versao}: {mensagem[:50]}")
        except Exception as e:
            log.erro(_ARQ, "registrar_commit", str(e))
        return nova_versao


def registrar_push(caminho_projeto: str) -> None:
    """
    Registra entrada de push no CHANGELOG.md.
    Chamado por c__git_ui_projeto._ao_enviar e por ias_handlers após push OK.
    """
    with _lock:
        versao = _garantir_version(caminho_projeto)  # cria se não existir; nunca "?"
        try:
            entrada = f"## {versao} — {_data_hoje()}\n- Enviado ao GitHub"
            _prepend_changelog(caminho_projeto, entrada)
            log.ok(_ARQ, "registrar_push", f"push registrado ({versao})")
        except Exception as e:
            log.erro(_ARQ, "registrar_push", str(e))


def checar_regressao_versao(caminho_projeto: str, versao_nova: str) -> bool:
    """
    Retorna True se versao_nova é menor que o VERSION atual (regressão).
    Usado pela UI do Executável para perguntar ao usuário antes de iniciar release.
    """
    versao_atual = _ler_version(caminho_projeto)
    if not versao_atual:
        return False
    try:
        return _nums(versao_nova) < _nums(versao_atual)
    except Exception:
        return False


def registrar_release(
    caminho_projeto: str, versao: str, descricao: str = ""
) -> None:
    """
    Sincroniza VERSION com a versão do release e adiciona entrada no CHANGELOG.
    Se versão nova < atual: loga aviso mas prossegue
    (a UI já perguntou ao usuário via checar_regressao_versao + HeinPopup.confirmar).

    Chamado por executavel_explorer._proxima_etapa_release quando a fila termina.
    """
    with _lock:
        versao_atual = _ler_version(caminho_projeto) or "?"
        versao_norm  = versao if versao.lower().startswith("v") else f"v{versao}"

        # Rede de segurança — UI já deve ter perguntado
        try:
            if _nums(versao_norm) < _nums(versao_atual):
                log.aviso(_ARQ, "registrar_release",
                          f"versão regressiva: {versao_norm} < {versao_atual} "
                          f"(usuário confirmou na UI)")
        except Exception:
            pass

        try:
            _escrever_version(caminho_projeto, versao_norm)
            desc   = descricao.strip() if descricao.strip() else f"Release {versao_norm}."
            entrada = f"## release {versao_norm} — {_data_hoje()}\n{desc}"
            _prepend_changelog(caminho_projeto, entrada)
            log.ok(_ARQ, "registrar_release", f"release {versao_norm} registrado")
        except Exception as e:
            log.erro(_ARQ, "registrar_release", str(e))
