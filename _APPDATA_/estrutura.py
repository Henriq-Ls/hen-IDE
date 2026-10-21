# 📁 _APPDATA_/estrutura.py
"""
_APPDATA_/estrutura.py

Responsável por garantir que toda a estrutura de pastas e arquivos padrão
do AppData da hein exista antes de qualquer módulo tentar usá-la.

Chamado UMA VEZ na inicialização, via GerenciadorAppData.inicializar().
Sem dependências internas da IDE — apenas stdlib Python.
Nunca lança exceção. Falhas são silenciosas (retornam lista vazia).
"""

import os
import shutil
# ─── Subpastas que devem existir dentro de PASTA_APPDATA ─────────────────────

_SUBPASTAS: list[str] = [
    "_conf_bakup",
    "estado_editor",
    "tarefas",
    "autocompletar",
    "temas",          # IMP-04
    "configuracoes",  # JSONs de configuração do usuário (atalhos, perfil, etc.)
    "dicionarios",    # dicionários do corretor ortográfico PT-BR
]

# ─── JSONs de configuração a migrar para AppData/configuracoes/ no primeiro uso
# Origem: _CONFIGURA_/  →  Destino: AppData/configuracoes/
# Copiados apenas se o arquivo de destino ainda não existir (primeiro uso).

_JSONS_CONFIG: list[str] = [  # IMP-03
    "configurar.json",
    "atalhos.json",
    "autocomplete.json",
    "perfil.json",
]

# ─── Templates de autocompletar a copiar para AppData no primeiro uso ─────────
# Origem: _CONFIGURA_/autocompletar/  →  Destino: AppData/autocompletar/
# Copiados apenas se o arquivo de destino ainda não existir.

_TEMPLATES_AUTOCOMPLETAR: list[str] = [
    "simbolos.json",
    "palavras.txt",
    "emojis.json",
]

# ─── LEIA-ME.txt: explicação em português simples da pasta, pra usuário iniciante
# Criado uma única vez (nunca sobrescreve um LEIA-ME.txt já existente, mesmo
# que o usuário tenha editado ou apagado o conteúdo).

_ARQUIVO_LEIA_ME = "LEIA-ME.txt"

_TEXTO_LEIA_ME = """\
Essa pasta é a "memória" do hein
=================================

Aqui o hein guarda tudo que precisa lembrar entre uma vez que você abre o
programa e a próxima — sem isso, ele "esqueceria" tudo a cada vez que você
fechasse. Você não precisa mexer em nada aqui pra usar o hein no dia a dia;
esse texto é só pra explicar o que é cada coisa, caso você fique curioso.

PASTAS

  configuracoes/
    Suas preferências do hein: atalhos de teclado, tema escolhido, tamanho
    de fonte e outras configurações que você ajustou pelo menu.

  temas/
    As "roupas" visuais do hein — os temas de cores disponíveis pra você
    escolher, incluindo os que já vêm de fábrica e os que você criar.

  estado_editor/
    Guarda, pra cada arquivo que você já abriu, coisas como em que linha o
    cursor estava e o que você tinha marcado ou dobrado — assim, quando
    você reabre o arquivo, ele volta do jeito que você deixou.

  tarefas/
    Suas anotações e tarefas criadas dentro do hein.

  autocompletar/
    Listas de palavras, símbolos e emojis que o hein usa pra sugerir
    enquanto você digita.

  _conf_bakup/
    Cópias de segurança automáticas, feitas de vez em quando, pra caso
    algo dê errado e você precise recuperar uma versão anterior.

ARQUIVOS

  hein.log
    Um "diário de bordo" com tudo que o hein fez enquanto estava aberto.
    Serve pra ajudar a descobrir o que aconteceu se algo der errado — você
    não precisa entender o conteúdo dele.

  layout.json
    Guarda como você deixou as janelas e painéis organizados na tela.

  recentes.json
    A lista de projetos que você abriu recentemente, pra aparecer no menu
    "Recentes".

  sessao.json
    Guarda quais arquivos/abas estavam abertos, pra você continuar
    exatamente de onde parou na próxima vez.

Se algum desses arquivos ou pastas for apagado por acidente, sem problema:
o hein recria tudo automaticamente na próxima vez que for aberto.
"""


def _garantir_dicionarios(pasta_appdata: str, criados: list[str]) -> None:
    """
    Copia pt_BR_basico.txt e tech_whitelist.txt de _APPDATA_/dicionarios/
    para AppData/dicionarios/ apenas se ainda não existirem (primeiro uso).
    Garante também a existência de pt_BR_usuario.txt vazio.
    """
    pasta_src = os.path.join(os.path.dirname(__file__), "dicionarios")
    pasta_dst = os.path.join(pasta_appdata, "dicionarios")

    if os.path.isdir(pasta_src):
        for nome in ("pt_BR_basico.txt", "tech_whitelist.txt"):
            src = os.path.join(pasta_src, nome)
            dst = os.path.join(pasta_dst, nome)
            # Sempre sobrescreve os dicionários bundlados — eles são gerenciados
            # pelo app, não pelo usuário. Garante que atualizações cheguem ao
            # AppData sem exigir deleção manual.
            if os.path.isfile(src):
                try:
                    shutil.copy2(src, dst)
                    criados.append(dst)
                except Exception:
                    pass

    # Cria dicionário do usuário vazio se ainda não existe
    usuario = os.path.join(pasta_dst, "pt_BR_usuario.txt")
    if not os.path.isfile(usuario):
        try:
            with open(usuario, "w", encoding="utf-8") as f:
                f.write("# Dicionário pessoal — uma palavra por linha\n")
            criados.append(usuario)
        except Exception:
            pass


def _garantir_leia_me(pasta_appdata: str, criados: list[str]) -> None:
    """Cria LEIA-ME.txt na raiz do AppData, explicando em português simples
    o que é cada pasta/arquivo — pensado pra quem está começando a usar o
    hein. Só cria se ainda não existir (nunca sobrescreve edições do
    usuário). Falha silenciosa."""
    destino = os.path.join(pasta_appdata, _ARQUIVO_LEIA_ME)
    if not os.path.isfile(destino):
        try:
            with open(destino, "w", encoding="utf-8") as f:
                f.write(_TEXTO_LEIA_ME)
            criados.append(destino)
        except Exception:
            pass

# ─── API pública ──────────────────────────────────────────────────────────────

def garantir_estrutura(pasta_appdata: str, pasta_configura: str) -> list[str]:
    """
    Garante a existência de toda a estrutura de diretórios e arquivos padrão
    dentro de *pasta_appdata*.

    Parâmetros
    ----------
    pasta_appdata   : caminho absoluto para %APPDATA%/hein/
    pasta_configura : caminho absoluto para _CONFIGURA_/ (raiz do pacote)

    Retorna
    -------
    Lista de paths recém-criados (pastas ou arquivos).
    Lista vazia indica que tudo já existia ou que todas as falhas foram
    silenciadas.
    """
    criados: list[str] = []

    _garantir_pasta(pasta_appdata, criados)
    _migrar_pasta_editor_states(pasta_appdata)   # renomeia editor_states/ -> estado_editor/ antes de criar as subpastas

    for sub in _SUBPASTAS:
        _garantir_pasta(os.path.join(pasta_appdata, sub), criados)

    _garantir_jsons_configura(pasta_appdata, pasta_configura, criados)       # IMP-03
    _garantir_templates_autocompletar(pasta_appdata, pasta_configura, criados)
    _garantir_temas(pasta_appdata, pasta_configura, criados)                 # IMP-04
    _garantir_ia(pasta_appdata, criados)                                     # perguntas e system prompt do PainelIA
    _garantir_leia_me(pasta_appdata, criados)                                # LEIA-ME.txt pra usuário iniciante
    _garantir_dicionarios(pasta_appdata, criados)                            # pt_BR_basico.txt + tech_whitelist.txt
    _limpar_legado(pasta_appdata)                                            # limpeza de instalações antigas

    return criados

# ─── Helpers internos ─────────────────────────────────────────────────────────

# ⚠️  except genérico vazio
def _garantir_jsons_configura(pasta_appdata: str, pasta_configura: str, criados: list[str]) -> None:  # IMP-03
    """
    Copia os JSONs de configuração de _CONFIGURA_/ para AppData/configuracoes/
    apenas se ainda não existirem no destino. Garante que o primeiro uso tenha
    os valores de fábrica disponíveis em AppData, já agrupados na mesma pasta
    que a aba "Configurações" do menu representa.
    """
    pasta_config = os.path.join(pasta_appdata, "configuracoes")
    for nome in _JSONS_CONFIG:
        src = os.path.join(pasta_configura, nome)
        dst = os.path.join(pasta_config,    nome)
        if os.path.isfile(src) and not os.path.isfile(dst):
            try:
                shutil.copy2(src, dst)
                criados.append(dst)
            except Exception:
                pass

# ⚠️  except genérico vazio
def _migrar_pasta_editor_states(pasta_appdata: str) -> None:
    """
    Renomeia AppData/editor_states/ (nome antigo, em inglês) para
    AppData/estado_editor/ — alinhado ao restante das pastas do projeto, que
    são todas em português (tarefas/, temas/, autocompletar/, configuracoes/).
    Só renomeia se a pasta nova ainda não existir, pra não perder nada de uma
    migração anterior. Falha silenciosa: se não der, a pasta antiga continua
    funcionando normalmente (retrocompatível).
    """
    _old = os.path.join(pasta_appdata, "editor_states")
    _new = os.path.join(pasta_appdata, "estado_editor")
    if os.path.isdir(_old) and not os.path.isdir(_new):
        try:
            os.rename(_old, _new)
        except Exception:
            pass

# ⚠️  except genérico vazio
def _limpar_legado(pasta_appdata: str) -> None:
    """
    Remove a pasta AppData/default/, órfã de uma reorganização anterior.
    Ela guardava cópias de fábrica para restaurar_padrao(); hoje esse
    componente lê direto de _CONFIGURA_/ (fonte de verdade), então a pasta
    não tem mais uso. Falha silenciosa: se não existir ou não puder ser
    removida, não faz diferença — é lixo inofensivo.
    """
    pasta_legado = os.path.join(pasta_appdata, "default")
    if os.path.isdir(pasta_legado):
        try:
            shutil.rmtree(pasta_legado)
        except Exception:
            pass

# ⚠️  except genérico vazio
def _garantir_ia(pasta_appdata: str, criados: list[str]) -> None:
    """
    Copia os arquivos padrão do PainelIA de _APPDATA_/ia/ para AppData/ia/
    apenas se ainda não existirem no destino.

    Arquivos copiados:
      perguntas.json    — 15 perguntas pré-definidas em 3 categorias
      system_prompt.json — prompt de sistema padrão + max_tokens

    IAs (credenciais do usuário) NUNCA são copiadas — ficam só no projeto.
    Ao lançar uma atualização com novos defaults, só usuários que nunca
    modificaram o arquivo receberão o novo padrão.
    """
    pasta_src = os.path.join(os.path.dirname(__file__), "ia")
    pasta_dst = os.path.join(pasta_appdata, "ia")

    if not os.path.isdir(pasta_src):
        return

    for nome in ("perguntas.json", "system_prompt.json"):
        src = os.path.join(pasta_src, nome)
        dst = os.path.join(pasta_dst, nome)
        if os.path.isfile(src) and not os.path.isfile(dst):
            try:
                shutil.copy2(src, dst)
                criados.append(dst)
            except Exception:
                pass


# ⚠️  except genérico vazio
def _garantir_temas(pasta_appdata: str, pasta_configura: str, criados: list[str]) -> None:  # IMP-04
    """
    Copia os temas pré-instalados de _APPDATA_/temas/ (pasta do projeto, ao lado
    deste módulo) para AppData/temas/
    apenas se ainda não existirem no destino.
    Novos temas baixados pelo usuário ficam em AppData/temas/ e não são tocados.
    """
    pasta_src = os.path.join(os.path.dirname(__file__), "temas")   # REORG-TEMA
    pasta_dst = os.path.join(pasta_appdata, "temas")

    if not os.path.isdir(pasta_src):
        return

    for nome in os.listdir(pasta_src):
        if not nome.endswith(".json"):
            continue
        src = os.path.join(pasta_src, nome)
        dst = os.path.join(pasta_dst, nome)
        if os.path.isfile(src) and not os.path.isfile(dst):
            try:
                shutil.copy2(src, dst)
                criados.append(dst)
            except Exception:
                pass

# ⚠️  except genérico vazio
def _garantir_pasta(path: str, criados: list[str]) -> None:
    """Cria *path* (incluindo pais) se não existir. Falha silenciosa."""
    try:
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
            criados.append(path)
    except Exception:
        pass

# ⚠️  except genérico vazio
def _garantir_templates_autocompletar( pasta_appdata: str, pasta_configura: str, criados: list[str], ) -> None:
    """
    Copia os arquivos-template de _CONFIGURA_/autocompletar/ para
    AppData/autocompletar/ apenas se ainda não existirem no destino.
    Garante que o usuário já veja os exemplos no primeiro uso.
    """
    origem  = os.path.join(pasta_configura, "autocompletar")
    destino = os.path.join(pasta_appdata,   "autocompletar")

    for nome in _TEMPLATES_AUTOCOMPLETAR:
        src = os.path.join(origem,  nome)
        dst = os.path.join(destino, nome)

        if os.path.isfile(src) and not os.path.isfile(dst):
            try:
                shutil.copy2(src, dst)
                criados.append(dst)
            except Exception:
                pass
