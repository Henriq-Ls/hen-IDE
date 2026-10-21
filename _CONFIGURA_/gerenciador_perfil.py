# _CONFIGURA_/gerenciador_perfil.py
"""
Gerenciador de Perfil do Usuário da hein IDE.

Guarda TODOS os dados do usuário em um arquivo próprio (perfil.json),
separado das configurações visuais (configurar.json). Isso permite
crescer o perfil (idioma, avatar, git, integrações do site/chat, etc.)
sem misturar com configuração de UI/fonte.
"""
import os
import json
import datetime
from _CONFIGURA_ import ARQUIVO_PERFIL, ARQUIVO_CONFIG
from _LOG_.log import log

_ARQ = "gerenciador_perfil.py"


def _perfil_padrao() -> dict:
    """Esquema completo do perfil — todo campo novo deve nascer aqui,
    com valor padrão, para nunca faltar chave em código que consome o perfil."""
    return {
        "nome": "",
        "email": "",
        "idioma": "pt-BR",
        "avatar": "",
        "github": "",
        "saudacao_personalizada": "",
        "pasta_projetos": "",
        "data_criacao": "",
        "ativacao": {
            "chave": "",
            "data_ativacao": "",
            "status": "gratuito",
        },
        "git": {
            "nome": "",
            "email": "",
        },
        "extras": {},
    }


def obter_caminho_perfil() -> str:
    """Resolve o caminho absoluto do perfil.json (respeita sandbox/produção)."""
    return ARQUIVO_PERFIL


def _mesclar_com_padrao(dados: dict) -> dict:
    """Preenche chaves ausentes com o padrão, sem apagar o que já existe
    (permite adicionar campo novo ao esquema sem quebrar perfis antigos)."""
    padrao = _perfil_padrao()
    for chave, valor in padrao.items():
        if chave not in dados:
            dados[chave] = valor
        elif isinstance(valor, dict) and isinstance(dados.get(chave), dict):
            for sub_chave, sub_valor in valor.items():
                dados[chave].setdefault(sub_chave, sub_valor)
    return dados


def _migrar_perfil_antigo() -> dict | None:
    """Migração de uma única vez: se ainda não existe perfil.json mas o
    configurar.json antigo tem um bloco 'perfil' (esquema anterior), traz
    esses dados para o novo arquivo e limpa o bloco antigo.

    Retorna o dict migrado, ou None se não havia nada para migrar.
    """
    if not os.path.exists(ARQUIVO_CONFIG):
        return None
    try:
        with open(ARQUIVO_CONFIG, "r", encoding="utf-8") as f:
            config_antigo = json.load(f)
    except Exception as e:
        log.aviso(_ARQ, "_migrar_perfil_antigo", f"Não foi possível ler configurar.json: {e}")
        return None

    perfil_antigo = config_antigo.get("perfil")
    caminho_antigo = config_antigo.get("caminho_projetos")

    if not perfil_antigo and not caminho_antigo:
        return None

    log.info(_ARQ, "_migrar_perfil_antigo", "Migrando perfil do configurar.json antigo para perfil.json")

    novo = _perfil_padrao()
    if perfil_antigo:
        novo["nome"] = perfil_antigo.get("nome", "")
        novo["email"] = perfil_antigo.get("email", "")
        novo["ativacao"]["chave"] = perfil_antigo.get("chave_ativacao", "")
        if novo["ativacao"]["chave"]:
            novo["ativacao"]["status"] = "gratuito"
    if caminho_antigo:
        novo["pasta_projetos"] = caminho_antigo
    novo["data_criacao"] = _agora_iso()

    # Remove os blocos antigos do configurar.json para não duplicar a fonte da verdade
    config_antigo.pop("perfil", None)
    config_antigo.pop("caminho_projetos", None)
    try:
        with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
            json.dump(config_antigo, f, indent=4, ensure_ascii=False)
    except Exception as e:
        log.erro(_ARQ, "_migrar_perfil_antigo", f"Falha ao limpar configurar.json antigo: {e}")

    return novo


def _agora_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def ler_perfil() -> dict:
    """Lê perfil.json de forma segura. Faz a migração automática do esquema
    antigo (configurar.json) na primeira leitura, se aplicável."""
    caminho = obter_caminho_perfil()

    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                dados = json.load(f)
            return _mesclar_com_padrao(dados)
        except Exception as e:
            log.erro(_ARQ, "ler_perfil", f"Erro ao ler perfil.json: {e}")
            return _perfil_padrao()

    migrado = _migrar_perfil_antigo()
    if migrado is not None:
        salvar_perfil_completo(migrado)
        return migrado

    return _perfil_padrao()


def salvar_perfil_completo(dados: dict) -> bool:
    """Grava o dict de perfil inteiro em perfil.json (mesclando com o que
    já existe, pra nunca perder campo que não foi passado)."""
    caminho = obter_caminho_perfil()
    try:
        os.makedirs(os.path.dirname(caminho), exist_ok=True)

        atual = {}
        if os.path.exists(caminho):
            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    atual = json.load(f)
            except Exception:
                atual = {}

        atual.update(dados)
        atual = _mesclar_com_padrao(atual)

        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(atual, f, indent=4, ensure_ascii=False)

        log.ok(_ARQ, "salvar_perfil_completo", "perfil.json gravado com sucesso.")
        return True
    except Exception as e:
        log.erro(_ARQ, "salvar_perfil_completo", f"Erro ao gravar perfil.json: {e}")
        return False


def salvar_perfil(nome: str, email: str, chave_ativacao: str = "") -> bool:
    """Salva os dados essenciais do cadastro inicial (nome, email, chave).
    Os demais campos do esquema (idioma, avatar, git, etc.) ficam com seus
    padrões até o usuário editá-los em uma tela de perfil futura."""
    perfil_atual = ler_perfil()
    if not perfil_atual.get("data_criacao"):
        perfil_atual["data_criacao"] = _agora_iso()

    perfil_atual["nome"] = nome
    perfil_atual["email"] = email
    perfil_atual["ativacao"]["chave"] = chave_ativacao
    if chave_ativacao and not perfil_atual["ativacao"].get("data_ativacao"):
        perfil_atual["ativacao"]["data_ativacao"] = _agora_iso()

    return salvar_perfil_completo(perfil_atual)


def obter_perfil() -> dict:
    """Retorna o perfil inteiro (nome, email, avatar, idioma, git, etc.)."""
    return ler_perfil()


def obter_nome_usuario() -> str:
    """Retorna o nome salvo do usuário, ou 'Usuário' caso não exista."""
    nome = obter_perfil().get("nome", "").strip()
    return nome or "Usuário"


def salvar_caminho_projetos(caminho: str) -> bool:
    """Grava o diretório padrão onde o usuário criará seus projetos."""
    perfil_atual = ler_perfil()
    perfil_atual["pasta_projetos"] = os.path.abspath(caminho)
    return salvar_perfil_completo(perfil_atual)


def obter_caminho_projetos() -> str:
    """Retorna o caminho de projetos salvo, ou um padrão amigável caso não exista."""
    caminho = obter_perfil().get("pasta_projetos", "")
    if caminho:
        return caminho

    default_path = os.path.join(os.path.expanduser("~"), "hein_Projetos")
    return os.path.abspath(default_path)
