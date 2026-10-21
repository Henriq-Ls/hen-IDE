# 📁 _CONFIGURA_/__init__.py
"""
Constantes globais da IDE hein.
Para alterar qualquer valor visual ou comportamental, edite este arquivo.

SEÇÕES:
  1.  JANELA PRINCIPAL
  2.  SPLITTERS
  3.  FONTES — hein Custom + fallbacks
  4.  TAMANHOS DE FONTE — por painel
  5.  EDITOR — limites de fonte
  6.  TERMINAL — tamanhos de fonte
  7.  OUTLINE — dimensões e timers
  8.  CORES — menu lateral
  9.  CORES — toolbar do terminal
 10.  CORES — botão Executar
 11.  CORES — terminal (fallback quando thema.json não tem a chave)
 12.  CORES — ANSI (paleta de 16 cores do terminal)
 13.  TAMANHOS — botões da toolbar
 14.  ATALHOS — menu Arquivo
 15.  ATALHOS — menu Executar
 16.  ATALHOS — menu Projeto (Ctrl+1 a Ctrl+6)
 17.  CAMINHOS — pastas do usuário
 18.  CAMINHOS — arquivos de configuração
 19.  MISC
 20.  CORES — Painel IA
 21.  IA — listas de exclusão de arquivos/pastas
"""
import json
import os
import re

# ══════════════════════════════════════════════════════════════════════
# 0. MIDIAS
# ══════════════════════════════════════════════════════════════════════
IMAGEM_LOGO = '_MIDIAS_/logo.png'
IMAGEM_ICO  = '_MIDIAS_/ico.ico'
IMAGEM_ZAP  = '_MIDIAS_/qrWhats.png'
IMAGEM_PIX  = '_MIDIAS_/qrcodePix.jpg'
IMAGEM_GIF  = '_MIDIAS_/smola.gif'
IMAGEM_BAND = '_MIDIAS_/band2.jpg'


# ══════════════════════════════════════════════════════════════════════
# 1. JANELA PRINCIPAL
# ══════════════════════════════════════════════════════════════════════

TITULO_APP    = " > hein ▋"
VERSAO_APP    = "v2.2-beta"  # atualizar a cada release
TEMA_QT_PADRAO       = "Fusion"

TEMAS_QT_DISPONIVEIS = [
    "Fusion", "Windows",    "WindowsVista",  "QDarkStyle",   "QtMaterial",
    "qtmodern",    "pyqtdarktheme",    "pyqtdarktheme_light",    "PyDracula",
]
GEOMETRIA_APP        = (100, 100, 1400, 900)
ALTURA_BARRA_TITULO  = 32   # altura da barra de título customizada
ALTURA_ABA           = 28   # altura das abas do editor

# ══════════════════════════════════════════════════════════════════════
# 2. SPLITTERS
# ══════════════════════════════════════════════════════════════════════

SPLITTER_PRINCIPAL = [50, 1050, 150]
SPLITTER_COL1      = [450, 150]
SPLITTER_COL2      = [500, 250]
SPLITTER_COL3      = [350, 150]

# ══════════════════════════════════════════════════════════════════════
# 3. FONTES — hein Custom
# ══════════════════════════════════════════════════════════════════════

# CORES PRINCIPAIS — ordenadas por afinidade com verde
PRETO          = "#020202"  # Preto  Puro
PRETO_FOSCO    = "#070706"  # Preto Quase Puro

CINZA_ESCURO   = "#0F1210"  # Quase Preto Esverdeado 0D0D0D
BRANCO         = "#EDEEF0"  # Branco Gelo
BEGE           = "#E6D7B0"  # Bege Quente
AMARELO        = "#FFC107"  # Amarelo Pálido
AMBAR          = "#E0A800"  # Âmbar Dourado
LIMA           = "#C6FF00"  # Lima Neon
OLIVA          = "#6B8E23"  # Verde Oliva
VERDE          = "#4ec994"  # Verde
VERDE_CLARO    = "#07B634"  # Verde Médio
VERDE_ESCURO   = "#0F1210"  # Verde Escuro
VERDE_PALIDO   = "#9AD49A"  # Verde Pálido
VERDE_AZULADO  = "#021D21"  # Azul muito escuro puxado para ciano/teal
VERDE_PETROLEO = "#062B2A"  #
SUCESSO        = "#28C76F"  # Verde Sucesso
MENTA          = "#7CFFB2"  # Menta Neon
TURQUESA       = "#00C2A8"  # Turquesa
AZUL_FOSCO     = "#7094A1"  # Azul Aço Fosco
AZUL_ESCURO    = "#1FB8D0"  # Azul Royal
AZUL           = "#0057FF"  # Ciano Brilhante
AZUL_CLARO     = "#2196F3"  # Azul Informação
AZU_PETROLEO   = "#082C3A"  #

LILAS          = "#9D7CFF"  # Lilás Médio
VIOLETA        = "#8A2BE2"  # Violeta
ROXO           = "#6B0585"  # Roxo Escuro
MAGENTA        = "#D100D1"  # Magenta Puro
PINK           = "#FF4D9D"  # Pink Vibrante
ROSA           = "#BA1A6D"  # Rosa Escuro
CORAL          = "#FF6B6B"  # Coral
CORAL_VERMELHO = "#B85A5A"
VERMELHO       = "#A10510"  # Vermelho Escuro
LARANJA        = "#B86A12"  # Laranja Médio
LARANJA_ESCURO = "#9E3B02"  # Laranja Escuro Enferrujado
TERRACOTA      = "#A0522D"  # Terracota

# ══════════════════════════════════════════════════════════════════════

FONTE_UI              = "hein"
FONTE_UI_FALLBACK     = "Segoe UI"
TAMANHO_FONTE_UI      = "13px"

FONTE_EDITOR          = "hein"
FONTE_EDITOR_FALLBACK = "SpecialElite-Regular"

FONTE_TERMINAL          = "hein"
FONTE_TERMINAL_FALLBACK = "SpecialElite-Regular"

FONTE_OUTLINE          = "hein"
FONTE_OUTLINE_FALLBACK = "Segoe UI"

FONTE_ARQUIVOS          = "hein"
FONTE_ARQUIVOS_FALLBACK = "SpecialElite-Regular"

FONTE_IA          = "hein"
FONTE_IA_FALLBACK = "SpecialElite-Regular"

FONTE_GIT          = "hein"
FONTE_GIT_FALLBACK = "SpecialElite-Regular"

# Fonte monoespaçada — terminal do Núcleo, barra de status e IA
FONTE_MONO          = "hein"
FONTE_MONO_FALLBACK = "Consolas"

BORDA_CONTORNO_UI  = VERMELHO
BORDA_TOPO         = LARANJA
BORDA_RODAPE       = VERMELHO
BORDA_GERAL        = VERDE_AZULADO  # fallback: fundo_aba_ativa + linhas das 3 barras de abas

FUNDO        = PRETO_FOSCO
FUNDO_PAINEL = PRETO
BORDA_PAINEL = "transparent"

# ══════════════════════════════════════════════════════════════════════
# CORES OUTDOOR
OUTIDOR_BACKGROUND = ROSA

# ══════════════════════════════════════════════════════════════════════
#  CORES — botões de ícone (qtawesome)
COR_BTN_ICONE_BG_qta    = PRETO_FOSCO
COR_BTN_ICONE_TEXTO_qta = VERDE

# fallbacks para chaves do thema.json (usadas quando o JSON falha ou a chave não existe)
COR_INPUT_BG           = "#0d1a0d"  # → interface.inputs
COR_BOTAO_PADRAO_FUNDO = "#1a3a1a"  # → interface.botao_padrao_fundo
COR_BOTAO_PADRAO_TEXTO = "#4ec994"  # → interface.botao_padrao_texto

# ══════════════════════════════════════════════════════════════════════
# 4. TAMANHOS DE FONTE — por painel
# ══════════════════════════════════════════════════════════════════════

TAMANHO_FONTE_EDITOR    = 12
TAMANHO_FONTE_TERMINAL  = 12
TAMANHO_FONTE_OUTLINE   = 11
TAMANHO_FONTE_ARQUIVOS  = 11
TAMANHO_FONTE_IA        = 12
TAMANHO_FONTE_GIT       = 11

# ══════════════════════════════════════════════════════════════════════
# 5. EDITOR — limites de fonte e cabeçalho do outline
# ══════════════════════════════════════════════════════════════════════

FONTE_EDITOR_PADRAO        = TAMANHO_FONTE_EDITOR
FONTE_EDITOR_MIN           = 6
FONTE_EDITOR_MAX           = 32
FONTE_OUTLINE_CABECALHO    = FONTE_OUTLINE
FONTE_OUTLINE_CABECALHO_PT = 9

FONTE_FIND_REFERENCES = FONTE_EDITOR

COR_OUTLINE_CLASSE       = "#56b6c2"  # Ciano Suave
COR_OUTLINE_FUNCAO       = "#61afef"  # Azul Claro
COR_OUTLINE_METODO       = "#61afef"  # Azul Claro
COR_OUTLINE_METODO_PRIV  = "#666666"  # Cinza Médio
COR_OUTLINE_ARQUIVO      = "#cccccc"  # Cinza Claro
COR_OUTLINE_PASTA        = "#888888"  # Cinza
COR_OUTLINE_CHAVE_JSON   = "#98c379"  # Verde Claro
COR_OUTLINE_OBJETO_JSON  = "#e5c07b"  # Amarelo Ocre
COR_OUTLINE_TAG_XML      = "#c678dd"  # Lilás
COR_OUTLINE_ITEM         = "#abb2bf"  # Cinza Azulado

COR_SINTAXE_PALAVRA_CHAVE     = "#c678dd"  # Lilás
COR_SINTAXE_FUNCAO            = "#61afef"  # Azul Claro
COR_SINTAXE_VARIAVEL_ESPECIAL = "#e06c75"  # Vermelho Rosado
COR_SINTAXE_VARIAVEL          = "#e0e0e0"  # Cinza Muito Claro
COR_SINTAXE_PONTUACAO         = "#abb2bf"  # Cinza Azulado

#  EDITOR — Calha de números de linha (Gutter)
# Layout (esq→dir): [git] [pad] [BP/BM] [pad] [números auto] [seta] [pad] | código
LARGURA_GIT    = 9           # barra de diff git — borda ESQUERDA da calha
PADDINGS       = 10          # espaço uniforme entre todos os elementos da calha
LARGURA_GUITER = 15          # zona de breakpoints/bookmarks
LARGURA_SETA   = 7           # seta de code folding — borda DIREITA da calha
SETA_ESTILO    = "triangulo" # "triangulo" | "chevron" | "classico"
LARGURA_ERRO   = 12          # régua de diagnósticos (ReguaErros) — widget separado


# EDITOR_HEIN ------------
FUNDO_PAPEL = '#bfa02f'
COR_TEXTO_PAPEL = PRETO
COR_PALTA_PAPEL = AZU_PETROLEO
COR_GUTER_CURSOR = VERMELHO
COR_TOPICO_PAPEL = AZU_PETROLEO
LARGURA_MARGEM_GUTTER = 3
COLUNA_LIMITE_CADERNO = 80  # Item-4: coluna do hard wrap + guia vertical

# ══════════════════════════════════════════════════════════════════════
# 6. TERMINAL — tamanhos de fonte
# ══════════════════════════════════════════════════════════════════════

FONTE_TERMINAL_TAMANHO_PT  = TAMANHO_FONTE_TERMINAL
TAMANHO_FONTE_TERMINAL_PX  = f"{TAMANHO_FONTE_TERMINAL}px"

# ══════════════════════════════════════════════════════════════════════
# 7. OUTLINE — dimensões e timers
# ══════════════════════════════════════════════════════════════════════

OUTLINE_LARGURA_MIN      = 250
OUTLINE_LARGURA_MAX      = 900
OUTLINE_TIMER_MS         = 800
OUTLINE_CABECALHO_ALTURA = 32
OUTLINE_BTN_MODO_W       = 72
OUTLINE_BTN_MODO_H       = 20

# ══════════════════════════════════════════════════════════════════════
# 8. CORES — menu lateral
# ══════════════════════════════════════════════════════════════════════

COR_MENU_BG          = PRETO
COR_MENU_TEXTO       = "#888888"  # Cinza
COR_MENU_HOVER_BG    = "#1a1a2e"  # Azul Marinho Muito Escuro
COR_MENU_HOVER_TEXTO = BRANCO
COR_MENU_ITEM        = "#cccccc"  # Cinza Claro
COR_MENU_ITEM_HOVER  = "#264f78"  # Azul Marinho Médio

# ══════════════════════════════════════════════════════════════════════
# 9. CORES — toolbar do terminal
# ══════════════════════════════════════════════════════════════════════

COR_TOOLBAR_TERM_BG = PRETO

# ══════════════════════════════════════════════════════════════════════
# 10. CORES — botão Executar (▶)
# ══════════════════════════════════════════════════════════════════════

COR_BTN_RUN_BG      = "#1e3a5f"  # Azul Marinho Escuro
COR_BTN_RUN_TEXTO   = "#98c379"  # Verde Claro
COR_BTN_RUN_HOVER   = "#264f78"  # Azul Marinho Médio
COR_BTN_ICONE_BG    = "transparent"  # Transparente
COR_BTN_ICONE_TEXTO = "#555555"  # Cinza Escuro

# ══════════════════════════════════════════════════════════════════════
# 11. CORES — terminal (fallback quando thema.json não tem a chave)
# ══════════════════════════════════════════════════════════════════════

COR_TERMINAL_FUNDO  = PRETO
COR_TERMINAL_TEXTO  = "#f0e6c8"  # Bege Claro
COR_TERMINAL_CURSOR = AZUL
COR_BRANCO          = BRANCO
COR_CINZA_TEXTO     = "#cccccc"  # Cinza Claro
COR_ERRO            = VERMELHO
COR_SUCESSO         = VERDE      # Verde Menta
COR_INFO            = "#61afef"  # Azul Claro
COR_AVISO           = AMARELO
COR_SEPARADOR       = "#555555"  # Cinza Escuro

# ══════════════════════════════════════════════════════════════════════
# 12. CORES — ANSI (paleta de 16 cores do terminal)
# ══════════════════════════════════════════════════════════════════════

ANSI_PADRAO: dict[str, str] = {
    "preto":              CINZA_ESCURO,
    "vermelho":           "#e06c75",  # Vermelho Rosado
    "verde":              "#4ec994",  # Verde Menta
    "amarelo":            "#e5c07b",  # Amarelo Ocre
    "azul":               "#61afef",  # Azul Claro
    "magenta":            "#c678dd",  # Lilás
    "ciano":              "#56b6c2",  # Ciano Suave
    "branco":             "#cccccc",  # Cinza Claro
    "preto_brilhante":    "#555555",  # Cinza Escuro
    "vermelho_brilhante": "#ff8a8a",  # Vermelho Salmão
    "verde_brilhante":    "#6ee7b7",  # Verde Água Claro
    "amarelo_brilhante":  "#ffd89b",  # Amarelo Pêssego
    "azul_brilhante":     "#82c8ff",  # Azul Bebê
    "magenta_brilhante":  "#e5b0ff",  # Lilás Claro
    "ciano_brilhante":    "#7ee8f2",  # Ciano Claro
    "branco_brilhante":   BRANCO,
}

# ══════════════════════════════════════════════════════════════════════
# 13. TAMANHOS — botões da toolbar do terminal
# ══════════════════════════════════════════════════════════════════════

LARGURA_BTN_RUN    = 40
LARGURA_BTN_LIMPAR = 30
LARGURA_BTN_NOVO   = 30

# ══════════════════════════════════════════════════════════════════════
# 14. ATALHOS — menu Arquivo
# ══════════════════════════════════════════════════════════════════════

ATALHO_NOVO_PROJETO  = "Ctrl+Shift+N"
ATALHO_ABRIR_PROJETO = "Ctrl+Shift+O"
ATALHO_ABRIR_ARQUIVO = "Ctrl+O"
ATALHO_SALVAR        = "Ctrl+S"

# ══════════════════════════════════════════════════════════════════════
# 15. ATALHOS — menu Executar
# ══════════════════════════════════════════════════════════════════════

ATALHO_EXECUTAR = "F5"

# 📁 _CONFIGURA_/__init__.py
# ══════════════════════════════════════════════════════════════════════
# 16. ATALHOS — menu Projeto (Ctrl+1 a Ctrl+7)
# ══════════════════════════════════════════════════════════════════════

ATALHO_TAREFAS_PROJETO  = "Ctrl+1"
ATALHO_TAREFAS_GLOBAIS  = "Ctrl+2"
ATALHO_EDITAR_TEMA      = "Ctrl+3"
ATALHO_EDITAR_ATALHOS   = "Ctrl+4"
ATALHO_EDITOR_CONFIG    = "Ctrl+5"
ATALHO_AUTOCOMPLETE     = "Ctrl+6"
ATALHO_NUCLEO           = "Ctrl+7"
ATALHO_EXECUTORES       = "Ctrl+8"
ATALHO_EXECUTAVEL       = "Ctrl+9"
ATALHO_PROMPTS_NUCLEO   = "Ctrl+0"    # IMP-D: editor visual dos prompts do Núcleo


# ══════════════════════════════════════════════════════════════════════
# 17. CAMINHOS — pastas do usuário
# ══════════════════════════════════════════════════════════════════════
import sys  # certifique-se de que o 'sys' está importado

PASTA_PROJETOS = os.path.join(os.path.expanduser("~"), "hein_Projetos")

# 🤖 DETECTA AMBIENTE: Se for .exe compilado, usa 'hein'. Se for código dev (.py), usa 'hein_sandbox'
_SUFIXO_PASTA  = "hein_basic" if getattr(sys, 'frozen', False) else "hein_basic_sandbox"
PASTA_APPDATA  = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", _SUFIXO_PASTA)
# True quando rodando como .exe compilado; False em dev/sandbox.
# Usado pelo sistema de log para filtrar quais niveis chegam ao painel visual.
MODO_PRODUCAO  = getattr(sys, 'frozen', False)

# ══════════════════════════════════════════════════════════════════════
# 18. CAMINHOS — arquivos de configuração
# ══════════════════════════════════════════════════════════════════════

_PASTA_CONFIGURA = os.path.dirname(__file__)

# "configuracoes/" — subpasta que agrupa os JSONs editáveis pelo usuário na
# aba "Configurações" do menu (atalhos, configurar, perfil, núcleo,
# autocomplete). Antes ficavam soltos direto na raiz do AppData, o que
# confundia quem ia procurar manualmente — agora ficam visualmente juntos,
# no mesmo lugar que o menu já sugere.
PASTA_CONFIGURACOES   = os.path.join(PASTA_APPDATA, "configuracoes")
ARQUIVO_ATALHOS       = os.path.join(PASTA_CONFIGURACOES, "atalhos.json")      # IMP-03
ARQUIVO_CONFIG        = os.path.join(PASTA_CONFIGURACOES, "configurar.json")   # IMP-03
ARQUIVO_PERFIL        = os.path.join(PASTA_CONFIGURACOES, "perfil.json")       # dados do usuário (nome, email, avatar, git, ativação, etc.)
ARQUIVO_TEMA          = os.path.join(PASTA_APPDATA, "temas", "tema_padrao.json")  # tema ativo padrão — corrigido (antes apontava para o backup de fábrica thema.json, nunca o tema realmente ativo)
ARQUIVO_NUCLEO        = os.path.join(PASTA_CONFIGURACOES, "nucleo.json")       # IMP-03
ARQUIVO_NUCLEO_PROMPTS = os.path.join(PASTA_APPDATA, "nucleo_prompts.json")   # IMP-D
ARQUIVO_AUTOCOMPLETE  = os.path.join(PASTA_CONFIGURACOES, "autocomplete.json") # IMP-03
ARQUIVO_EXECUTORES    = os.path.join(_PASTA_CONFIGURA, "executores.json")

# Estado persistente da sessão (não é "configuração" — é o que o usuário
# deixou aberto/arrumado da última vez). Fica solto na raiz do AppData de
# propósito: layout de painéis, projetos recentes e abas abertas.
ARQUIVO_LAYOUT   = os.path.join(PASTA_APPDATA, "layout.json")
ARQUIVO_RECENTES = os.path.join(PASTA_APPDATA, "recentes.json")
ARQUIVO_SESSAO   = os.path.join(PASTA_APPDATA, "sessao.json")

PASTA_TAREFAS           = os.path.join(PASTA_APPDATA, "tarefas")
PASTA_SCRIPTS           = PASTA_TAREFAS  # alias retrocompatível

# ── Migração automática: renomeia "scripts" → "tarefas" ──────────────────
# ⚠️  except genérico vazio
def _migrar_pasta_scripts():
    _old = os.path.join(PASTA_APPDATA, "scripts")
    _new = PASTA_TAREFAS
    if os.path.isdir(_old) and not os.path.isdir(_new):
        try:
            os.rename(_old, _new)
        except Exception:
            pass
_migrar_pasta_scripts()

# ── Migração automática: move os JSONs de configuração da raiz do AppData
# para configuracoes/ (instalações antigas os tinham soltos na raiz).
# Move o arquivo e seu .bak sibling, se existirem, e só se o destino ainda
# não existir (nunca sobrescreve algo que já foi migrado ou recriado).
# ⚠️  except genérico vazio
def _migrar_jsons_configuracao():
    try:
        os.makedirs(PASTA_CONFIGURACOES, exist_ok=True)
    except Exception:
        return
    for _nome in ("atalhos.json", "configurar.json", "perfil.json", "nucleo.json", "autocomplete.json"):
        for _sufixo in ("", ".bak"):
            _old = os.path.join(PASTA_APPDATA, _nome + _sufixo)
            _new = os.path.join(PASTA_CONFIGURACOES, _nome + _sufixo)
            if os.path.isfile(_old) and not os.path.isfile(_new):
                try:
                    os.rename(_old, _new)
                except Exception:
                    pass
_migrar_jsons_configuracao()
PASTA_VENV_HEIN         = os.path.join(PASTA_APPDATA, "_venv_hein_")
ARQUIVO_TAREFAS_GLOBAIS = os.path.join(PASTA_APPDATA, "tarefas.json")
# F2–F10 → 9 slots de tarefas (índice 0=F2, 1=F3, ..., 8=F10).
# ⚠️  F5 (índice 3) coexiste com editor::ExecutarCodigo no contexto Global
#     do atalhos.json. O ApplicationShortcut da tarefa toma prioridade
#     quando o slot 3 está preenchido. Para evitar conflito: deixe-o vazio.
TAREFAS_FKEYS: list[str] = ["F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10"]

# ══════════════════════════════════════════════════════════════════════
# 19. MISC
# ══════════════════════════════════════════════════════════════════════

COR_FALLBACK          = "#e0e0e0"  # Cinza Muito Claro
MAX_RECENTES          = 10         # máximo de projetos recentes na lista
TEMPO_STATUS_MSG      = 3000       # ms de exibição na barra de status
ATALHOS_NAO_REGISTRAR = {"ctrl-click", "tab", "shift-tab"}
BUSCA_GREP_LIMITE     = 50         # máximo de resultados por busca grep

# ══════════════════════════════════════════════════════════════════════
# 20. CORES — Painel IA (Catppuccin Mocha)
# ══════════════════════════════════════════════════════════════════════

IA_COR_BG    = "#1e1e2e"  # Azul Noite Escuro
IA_COR_BG2   = "#181825"  # Azul Noite Muito Escuro
IA_COR_SURF0 = "#313244"  # Azul Noite Médio
IA_COR_SURF1 = "#45475a"  # Azul Noite Claro
IA_COR_OVER0 = "#6c7086"  # Cinza Azulado
IA_COR_TEXT  = "#cdd6f4"  # Lavanda Claro
IA_COR_BLUE  = "#89b4fa"  # Azul Lavanda
IA_COR_GREEN = "#a6e3a1"  # Verde Menta Claro
IA_COR_RED   = "#f38ba8"  # Rosa Flamingo
IA_COR_GOLD      = "#f9e2af"  # Amarelo Pêssego
IA_COR_MAUVE     = "#cba6f7"  # Roxo Mauve — cor da análise hein?
IA_COR_MAUVE_DIM = "#b4a0e8"  # Roxo Mauve dim — hover botão hein?
IA_COR_SUBTEXT0  = "#a6adc8"  # Cinza Lavanda — texto secundário hein?
IA_COR_CRUST     = "#11111b"  # Preto Catppuccin — fundo inline code
IA_COR_VERDE_BG  = "#1e3a2a"  # Verde Fundo — fundo de mensagem salva
IA_COR_GREEN_DIM = "#89d489"  # Verde dim — hover botão pip
# Catppuccin Mocha — paleta usada no highlight do chat IA
IA_SINTAXE_KEYWORD   = "#cba6f7"  # mauve
IA_SINTAXE_BUILTIN   = "#89dceb"  # sky
IA_SINTAXE_STRING    = "#a6e3a1"  # green
IA_SINTAXE_COMMENT   = "#6c7086"  # overlay0
IA_SINTAXE_NUMBER    = "#fab387"  # peach
IA_SINTAXE_DECORATOR = "#f38ba8"  # red
IA_SINTAXE_FUNC      = "#89b4fa"  # blue
IA_SINTAXE_CLASS     = "#f9e2af"  # yellow
IA_SINTAXE_SELF      = "#f38ba8"  # red (mesmo que DECORATOR)
IA_SINTAXE_OPERATOR  = "#89dceb"  # sky
TODAS_BORDAS = "transparent"  # Transparente

IA_FONTE_TEXTO  = 11
IA_FONTE_META   = 9
IA_FONTE_CODIGO = 11
IA_FONTE_INPUT  = 12

IA_FONTE_MONO          = "hein_Codigo"
IA_FONTE_MONO_FALLBACK = "Cascadia Code"

# ══════════════════════════════════════════════════════════════════════
# 21. IA — pastas e arquivos ignorados ao ler o projeto
# ══════════════════════════════════════════════════════════════════════

IA_PASTAS_IGNORAR: set[str] = {
    "Ias",
    "_GERENTE_PROJETO_",
    "__pycache__",
    ".git",
    ".github",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    ".zed",
    ".husls",
    ".RESUMO",
}

IA_ARQUIVOS_IGNORAR: set[str] = {
    ".DS_Store",
    "Thumbs.db",
    ".env",
    ".env.local",
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "hein_observa_para_ias.py",
    ".hein_memoria.json.bak",
    "Instalados.txt",
}

# ══════════════════════════════════════════════════════════════════════
# CORES — Editor UI, busca e grafo (complementares à paleta principal)
# ══════════════════════════════════════════════════════════════════════
COR_SINTAXE_NUMERO       = "#d19a66"  # Laranja suave — números no highlight
COR_BUSCA_NORMAL         = "#4a90d9"  # Azul médio — seleção de busca (RGB base)
COR_BUSCA_ATIVO          = "#e09a44"  # Laranja — resultado ativo de busca (RGB base)
COR_EDITOR_GUIA          = "#2a2a3a"  # Cinza azulado — guia de indentação
COR_MINI_SCROLLBAR       = "#4a4a6a"  # Cinza azulado — mini scrollbar normal
COR_MINI_SCROLLBAR_HOVER = "#8888aa"  # Cinza claro — mini scrollbar hover
COR_REGUA_AVISO_ALT      = "#FFB86C"  # Laranja Dracula — tooltip régua de avisos
COR_REGUA_ERRO_ALT       = "#FF5555"  # Vermelho Dracula — ponto régua de erros
COR_GUTTER_BP            = "#4a9eff"  # Azul vivo — breakpoint na calha de números
COR_LINHA_ATIVA_FUNDO    = "#141414"  # Cinza muito escuro — fundo linha ativa editor
COR_GIT_TEXTO_NEUTRO     = "#c9d1d9"  # Cinza azulado — texto neutro git (GitHub)
# ── Fundos de status git (calha de arquivos) ─────────────────────────
COR_GIT_FUNDO_MODIFICADO   = "#3a2e00"
COR_GIT_FUNDO_DELETADO     = "#3a0a0a"

# ── Sintaxe neutra / statement ──────────────────────────────────────
COR_SINTAXE_NEUTRO         = "#abb2bf"

# ── Fundos de badge nos logs ─────────────────────────────────────────
COR_LOG_BG_AVISO           = "#2b1e0d"
COR_LOG_BG_ERRO            = "#2b0d0d"

COR_GRAFO_NO_BG          = "#0d1a0d"  # Verde muito escuro — fundo nó do grafo
COR_GRAFO_NO_BORDA       = "#1a3a1a"  # Verde escuro — borda nó do grafo
COR_GRAFO_SETA           = "#2a4a2a"  # Verde médio escuro — seta do grafo
COR_GRAFO_FUNDO          = "#050505"  # Preto quase puro — fundo do grafo
COR_GRAFO_LABEL          = "#333333"  # Cinza — label secundário do grafo

_IGNORAR_CONTADOR = {".venv", ".hein", "__pycache__", ".git"}

_ICONE_GIT = {
    "modificado": ("mdi6.circle",        "#e5c07b"),  # Amarelo Ocre
    "novo":       ("mdi6.plus-circle",   "#98c379"),  # Verde Claro
    "deletado":   ("mdi6.delete-circle", "#e06c75"),  # Vermelho Rosado
    "renomeado":  ("mdi6.circle",        "#e5c07b"),  # Amarelo Ocre
}
_TOOLTIP_GIT = {
    "modificado": "Modificado — alterado desde o último commit",
    "novo":       "Novo — ainda não rastreado pelo Git",
    "deletado":   "Deletado — removido desde o último commit",
    "renomeado":  "Renomeado — arquivo movido ou renomeado",
}

_ICONE_EXT = {
    ".py":       ("fa5b.python",       "#4ec994"),  # Verde Menta
    ".js":       ("fa5b.js",           "#e5c07b"),  # Amarelo Ocre
    ".ts":       ("fa5b.js",           "#4a90d9"),  # Azul Médio
    ".html":     ("fa5b.html5",        "#e06c75"),  # Vermelho Rosado
    ".htm":      ("fa5b.html5",        "#e06c75"),  # Vermelho Rosado
    ".css":      ("fa5b.css3-alt",     "#4a90d9"),  # Azul Médio
    ".json":     ("fa5s.database",     "#e5c07b"),  # Amarelo Ocre
    ".md":       ("fa5b.markdown",     "#888888"),  # Cinza
    ".xml":      ("fa5s.code",         "#888888"),  # Cinza
    ".yml":      ("fa5s.cog",          "#888888"),  # Cinza
    ".yaml":     ("fa5s.cog",          "#888888"),  # Cinza
    ".toml":     ("fa5s.cog",          "#888888"),  # Cinza
    ".ini":      ("fa5s.cog",          "#888888"),  # Cinza
    ".cfg":      ("fa5s.cog",          "#888888"),  # Cinza
    ".env":      ("fa5s.lock",         "#e5c07b"),  # Amarelo Ocre
    ".sh":       ("fa5s.terminal",     "#98c379"),  # Verde Claro
    ".bat":      ("fa5s.terminal",     "#98c379"),  # Verde Claro
    ".ps1":      ("fa5b.windows",      "#4a90d9"),  # Azul Médio
    ".sql":      ("fa5s.database",     "#4a90d9"),  # Azul Médio
    ".db":       ("fa5s.database",     "#4a90d9"),  # Azul Médio
    ".sqlite":   ("fa5s.database",     "#4a90d9"),  # Azul Médio
    ".png":      ("fa5s.image",        "#c678dd"),  # Lilás
    ".jpg":      ("fa5s.image",        "#c678dd"),  # Lilás
    ".jpeg":     ("fa5s.image",        "#c678dd"),  # Lilás
    ".gif":      ("fa5s.image",        "#c678dd"),  # Lilás
    ".svg":      ("fa5s.image",        "#c678dd"),  # Lilás
    ".ico":      ("fa5s.image",        "#c678dd"),  # Lilás
    ".ttf":      ("fa5s.font",         "#e5c07b"),  # Amarelo Ocre
    ".otf":      ("fa5s.font",         "#e5c07b"),  # Amarelo Ocre
    ".woff":     ("fa5s.font",         "#e5c07b"),  # Amarelo Ocre
    ".pdf":      ("fa5s.file-pdf",     "#e06c75"),  # Vermelho Rosado
    ".zip":      ("fa5s.file-archive", "#888888"),  # Cinza
    ".tar":      ("fa5s.file-archive", "#888888"),  # Cinza
    ".gz":       ("fa5s.file-archive", "#888888"),  # Cinza
    ".txt":      ("fa5s.file-alt",     "#888888"),  # Cinza
    ".csv":      ("fa5s.table",        "#98c379"),  # Verde Claro
    ".exe":      ("fa5s.bolt",         "#e5c07b"),  # Amarelo Ocre
    ".dll":      ("fa5s.bolt",         "#e5c07b"),  # Amarelo Ocre
    ".gitignore":("fa5b.git-alt",      "#e06c75"),  # Vermelho Rosado
    # ── Linguagens adicionadas pelo Mult_Linguas ──────────────
    ".jsx":       ("fa5b.js",           "#e5c07b"),  # Amarelo Ocre
    ".tsx":       ("fa5b.js",           "#4a90d9"),  # Azul Médio
    ".scss":      ("fa5b.css3-alt",     "#c678dd"),  # Lilás
    ".c":         ("fa5s.file-code",    "#4a90d9"),  # Azul Médio
    ".cpp":       ("fa5s.file-code",    "#c678dd"),  # Lilás
    ".lua":       ("fa5s.moon",         "#00b4d8"),  # Azul Lua
    ".mk":        ("fa5s.tools",        "#e5c07b"),  # Amarelo Ocre
    ".dockerfile":("fa5b.docker",       "#0db7ed"),  # Azul Docker
}

_ICONE_PASTA  = ("fa5s.folder", "#e5c07b")  # Amarelo Ocre
_ICONE_PADRAO = ("fa5s.file",   "#555555")  # Cinza Escuro

_PACK_MDI = {
    ".py":       ("mdi6.language-python",       "#4ec994"),  # Verde Menta
    ".js":       ("mdi6.language-javascript",   "#e5c07b"),  # Amarelo Ocre
    ".ts":       ("mdi6.language-typescript",   "#4a90d9"),  # Azul Médio
    ".html":     ("mdi6.language-html5",        "#e06c75"),  # Vermelho Rosado
    ".htm":      ("mdi6.language-html5",        "#e06c75"),  # Vermelho Rosado
    ".css":      ("mdi6.language-css3",         "#4a90d9"),  # Azul Médio
    ".json":     ("mdi6.code-json",             "#e5c07b"),  # Amarelo Ocre
    ".md":       ("mdi6.language-markdown",     "#888888"),  # Cinza
    ".xml":      ("mdi6.xml",                   "#888888"),  # Cinza
    ".yml":      ("mdi6.cog-outline",           "#c678dd"),  # Lilás
    ".yaml":     ("mdi6.cog-outline",           "#c678dd"),  # Lilás
    ".toml":     ("mdi6.cog-outline",           "#c678dd"),  # Lilás
    ".ini":      ("mdi6.cog-outline",           "#c678dd"),  # Lilás
    ".cfg":      ("mdi6.cog-outline",           "#c678dd"),  # Lilás
    ".env":      ("mdi6.shield-key-outline",    "#e5c07b"),  # Amarelo Ocre
    ".sh":       ("mdi6.bash",                  "#98c379"),  # Verde Claro
    ".bat":      ("mdi6.script-text-outline",   "#98c379"),  # Verde Claro
    ".ps1":      ("mdi6.powershell",            "#4a90d9"),  # Azul Médio
    ".sql":      ("mdi6.database-outline",      "#4a90d9"),  # Azul Médio
    ".db":       ("mdi6.database",              "#4a90d9"),  # Azul Médio
    ".sqlite":   ("mdi6.database",              "#4a90d9"),  # Azul Médio
    ".png":      ("mdi6.file-image-outline",    "#c678dd"),  # Lilás
    ".jpg":      ("mdi6.file-image-outline",    "#c678dd"),  # Lilás
    ".jpeg":     ("mdi6.file-image-outline",    "#c678dd"),  # Lilás
    ".gif":      ("mdi6.gif",                   "#c678dd"),  # Lilás
    ".svg":      ("mdi6.svg",                   "#c678dd"),  # Lilás
    ".ico":      ("mdi6.file-image-outline",    "#c678dd"),  # Lilás
    ".ttf":      ("mdi6.format-font",           "#e5c07b"),  # Amarelo Ocre
    ".otf":      ("mdi6.format-font",           "#e5c07b"),  # Amarelo Ocre
    ".woff":     ("mdi6.format-font",           "#e5c07b"),  # Amarelo Ocre
    ".pdf":      ("mdi6.file-pdf-box",          "#e06c75"),  # Vermelho Rosado
    ".zip":      ("mdi6.zip-box-outline",       "#888888"),  # Cinza
    ".tar":      ("mdi6.zip-box-outline",       "#888888"),  # Cinza
    ".gz":       ("mdi6.zip-box-outline",       "#888888"),  # Cinza
    ".txt":      ("mdi6.text-box-outline",      "#888888"),  # Cinza
    ".csv":      ("mdi6.file-delimited-outline","#98c379"),  # Verde Claro
    ".exe":      ("mdi6.application-cog",       "#e5c07b"),  # Amarelo Ocre
    ".dll":      ("mdi6.application-cog",       "#e5c07b"),  # Amarelo Ocre
    ".gitignore":("mdi6.git",                   "#e06c75"),  # Vermelho Rosado
    # ── Linguagens adicionadas pelo Mult_Linguas ──────────────
    ".jsx":       ("mdi6.language-javascript",  "#e5c07b"),  # Amarelo Ocre
    ".tsx":       ("mdi6.language-typescript",  "#4a90d9"),  # Azul Médio
    ".scss":      ("mdi6.sass",                 "#c678dd"),  # Lilás
    ".c":         ("mdi6.language-c",           "#4a90d9"),  # Azul Médio
    ".cpp":       ("mdi6.language-cpp",         "#c678dd"),  # Lilás
    ".lua":       ("mdi6.language-lua",         "#00b4d8"),  # Azul Lua
    ".mk":        ("mdi6.hammer-wrench",        "#e5c07b"),  # Amarelo Ocre
    ".dockerfile":("mdi6.docker",               "#0db7ed"),  # Azul Docker
}

_PACK_MDI_NEON = {
    ".py":       ("mdi6.language-python",       "#00ff99"),  # Verde Neon
    ".js":       ("mdi6.language-javascript",   "#ffff00"),  # Amarelo Neon
    ".ts":       ("mdi6.language-typescript",   "#00cfff"),  # Ciano Neon
    ".html":     ("mdi6.language-html5",        "#ff4444"),  # Vermelho Neon
    ".htm":      ("mdi6.language-html5",        "#ff4444"),  # Vermelho Neon
    ".css":      ("mdi6.language-css3",         "#00cfff"),  # Ciano Neon
    ".json":     ("mdi6.code-json",             "#ffff00"),  # Amarelo Neon
    ".md":       ("mdi6.language-markdown",     "#aaaaaa"),  # Cinza Claro
    ".xml":      ("mdi6.xml",                   "#aaaaaa"),  # Cinza Claro
    ".yml":      ("mdi6.cog-outline",           "#ff00ff"),  # Magenta Neon
    ".yaml":     ("mdi6.cog-outline",           "#ff00ff"),  # Magenta Neon
    ".toml":     ("mdi6.cog-outline",           "#ff00ff"),  # Magenta Neon
    ".ini":      ("mdi6.cog-outline",           "#ff00ff"),  # Magenta Neon
    ".cfg":      ("mdi6.cog-outline",           "#ff00ff"),  # Magenta Neon
    ".env":      ("mdi6.shield-key-outline",    "#ffff00"),  # Amarelo Neon
    ".sh":       ("mdi6.bash",                  "#00ff99"),  # Verde Neon
    ".bat":      ("mdi6.script-text-outline",   "#00ff99"),  # Verde Neon
    ".ps1":      ("mdi6.powershell",            "#00cfff"),  # Ciano Neon
    ".sql":      ("mdi6.database-outline",      "#00cfff"),  # Ciano Neon
    ".db":       ("mdi6.database",              "#00cfff"),  # Ciano Neon
    ".sqlite":   ("mdi6.database",              "#00cfff"),  # Ciano Neon
    ".png":      ("mdi6.file-image-outline",    "#ff00ff"),  # Magenta Neon
    ".jpg":      ("mdi6.file-image-outline",    "#ff00ff"),  # Magenta Neon
    ".jpeg":     ("mdi6.file-image-outline",    "#ff00ff"),  # Magenta Neon
    ".gif":      ("mdi6.gif",                   "#ff00ff"),  # Magenta Neon
    ".svg":      ("mdi6.svg",                   "#ff00ff"),  # Magenta Neon
    ".ico":      ("mdi6.file-image-outline",    "#ff00ff"),  # Magenta Neon
    ".ttf":      ("mdi6.format-font",           "#ffff00"),  # Amarelo Neon
    ".otf":      ("mdi6.format-font",           "#ffff00"),  # Amarelo Neon
    ".woff":     ("mdi6.format-font",           "#ffff00"),  # Amarelo Neon
    ".pdf":      ("mdi6.file-pdf-box",          "#ff4444"),  # Vermelho Neon
    ".zip":      ("mdi6.zip-box-outline",       "#aaaaaa"),  # Cinza Claro
    ".tar":      ("mdi6.zip-box-outline",       "#aaaaaa"),  # Cinza Claro
    ".gz":       ("mdi6.zip-box-outline",       "#aaaaaa"),  # Cinza Claro
    ".txt":      ("mdi6.text-box-outline",      "#aaaaaa"),  # Cinza Claro
    ".csv":      ("mdi6.file-delimited-outline","#00ff99"),  # Verde Neon
    ".exe":      ("mdi6.application-cog",       "#ffff00"),  # Amarelo Neon
    ".dll":      ("mdi6.application-cog",       "#ffff00"),  # Amarelo Neon
    ".gitignore":("mdi6.git",                   "#ff4444"),  # Vermelho Neon
    # ── Linguagens adicionadas pelo Mult_Linguas ──────────────
    ".jsx":       ("mdi6.language-javascript",  "#ffff00"),  # Amarelo Neon
    ".tsx":       ("mdi6.language-typescript",  "#00cfff"),  # Ciano Neon
    ".scss":      ("mdi6.sass",                 "#ff00ff"),  # Magenta Neon
    ".c":         ("mdi6.language-c",           "#00cfff"),  # Ciano Neon
    ".cpp":       ("mdi6.language-cpp",         "#ff00ff"),  # Magenta Neon
    ".lua":       ("mdi6.language-lua",         "#00ffff"),  # Ciano Neon
    ".mk":        ("mdi6.hammer-wrench",        "#ffff00"),  # Amarelo Neon
    ".dockerfile":("mdi6.docker",               "#00cfff"),  # Ciano Neon
}

_PACK_MINIMALISTA = {
    ".py":       ("fa5s.circle",      "#4ec994"),  # Verde Menta
    ".js":       ("fa5s.circle",      "#e5c07b"),  # Amarelo Ocre
    ".ts":       ("fa5s.circle",      "#4a90d9"),  # Azul Médio
    ".html":     ("fa5s.circle",      "#e06c75"),  # Vermelho Rosado
    ".htm":      ("fa5s.circle",      "#e06c75"),  # Vermelho Rosado
    ".css":      ("fa5s.circle",      "#4a90d9"),  # Azul Médio
    ".json":     ("fa5s.circle",      "#e5c07b"),  # Amarelo Ocre
    ".md":       ("fa5s.circle",      "#888888"),  # Cinza
    ".xml":      ("fa5s.circle",      "#888888"),  # Cinza
    ".yml":      ("fa5s.dot-circle",  "#c678dd"),  # Lilás
    ".yaml":     ("fa5s.dot-circle",  "#c678dd"),  # Lilás
    ".toml":     ("fa5s.dot-circle",  "#c678dd"),  # Lilás
    ".ini":      ("fa5s.dot-circle",  "#c678dd"),  # Lilás
    ".cfg":      ("fa5s.dot-circle",  "#c678dd"),  # Lilás
    ".env":      ("fa5s.dot-circle",  "#e5c07b"),  # Amarelo Ocre
    ".sh":       ("fa5s.circle",      "#98c379"),  # Verde Claro
    ".bat":      ("fa5s.circle",      "#98c379"),  # Verde Claro
    ".ps1":      ("fa5s.circle",      "#4a90d9"),  # Azul Médio
    ".sql":      ("fa5s.circle",      "#4a90d9"),  # Azul Médio
    ".db":       ("fa5s.circle",      "#4a90d9"),  # Azul Médio
    ".sqlite":   ("fa5s.circle",      "#4a90d9"),  # Azul Médio
    ".png":      ("fa5s.circle",      "#c678dd"),  # Lilás
    ".jpg":      ("fa5s.circle",      "#c678dd"),  # Lilás
    ".jpeg":     ("fa5s.circle",      "#c678dd"),  # Lilás
    ".gif":      ("fa5s.circle",      "#c678dd"),  # Lilás
    ".svg":      ("fa5s.circle",      "#c678dd"),  # Lilás
    ".ico":      ("fa5s.circle",      "#c678dd"),  # Lilás
    ".ttf":      ("fa5s.circle",      "#e5c07b"),  # Amarelo Ocre
    ".otf":      ("fa5s.circle",      "#e5c07b"),  # Amarelo Ocre
    ".woff":     ("fa5s.circle",      "#e5c07b"),  # Amarelo Ocre
    ".pdf":      ("fa5s.circle",      "#e06c75"),  # Vermelho Rosado
    ".zip":      ("fa5s.minus-circle","#888888"),  # Cinza
    ".tar":      ("fa5s.minus-circle","#888888"),  # Cinza
    ".gz":       ("fa5s.minus-circle","#888888"),  # Cinza
    ".txt":      ("fa5s.circle",      "#888888"),  # Cinza
    ".csv":      ("fa5s.circle",      "#98c379"),  # Verde Claro
    ".exe":      ("fa5s.dot-circle",  "#e5c07b"),  # Amarelo Ocre
    ".dll":      ("fa5s.dot-circle",  "#e5c07b"),  # Amarelo Ocre
    ".gitignore":("fa5s.dot-circle",  "#e06c75"),  # Vermelho Rosado
    # ── Linguagens adicionadas pelo Mult_Linguas ──────────────
    ".jsx":       ("fa5s.circle",      "#e5c07b"),  # Amarelo Ocre
    ".tsx":       ("fa5s.circle",      "#4a90d9"),  # Azul Médio
    ".scss":      ("fa5s.circle",      "#c678dd"),  # Lilás
    ".c":         ("fa5s.circle",      "#4a90d9"),  # Azul Médio
    ".cpp":       ("fa5s.circle",      "#c678dd"),  # Lilás
    ".lua":       ("fa5s.circle",      "#00b4d8"),  # Azul Lua
    ".mk":        ("fa5s.circle",      "#e5c07b"),  # Amarelo Ocre
    ".dockerfile":("fa5s.circle",      "#0db7ed"),  # Azul Docker
}

_PACK_NEON = {
    ".py":       ("fa5b.python",       "#00ff99"),  # Verde Neon
    ".js":       ("fa5b.js",           "#ffff00"),  # Amarelo Neon
    ".ts":       ("fa5b.js",           "#00cfff"),  # Ciano Neon
    ".html":     ("fa5b.html5",        "#ff4444"),  # Vermelho Neon
    ".htm":      ("fa5b.html5",        "#ff4444"),  # Vermelho Neon
    ".css":      ("fa5b.css3-alt",     "#00cfff"),  # Ciano Neon
    ".json":     ("fa5s.database",     "#ffff00"),  # Amarelo Neon
    ".md":       ("fa5b.markdown",     "#aaaaaa"),  # Cinza Claro
    ".xml":      ("fa5s.code",         "#aaaaaa"),  # Cinza Claro
    ".yml":      ("fa5s.cog",          "#ff00ff"),  # Magenta Neon
    ".yaml":     ("fa5s.cog",          "#ff00ff"),  # Magenta Neon
    ".toml":     ("fa5s.cog",          "#ff00ff"),  # Magenta Neon
    ".ini":      ("fa5s.cog",          "#ff00ff"),  # Magenta Neon
    ".cfg":      ("fa5s.cog",          "#ff00ff"),  # Magenta Neon
    ".env":      ("fa5s.lock",         "#ffff00"),  # Amarelo Neon
    ".sh":       ("fa5s.terminal",     "#00ff99"),  # Verde Neon
    ".bat":      ("fa5s.terminal",     "#00ff99"),  # Verde Neon
    ".ps1":      ("fa5b.windows",      "#00cfff"),  # Ciano Neon
    ".sql":      ("fa5s.database",     "#00cfff"),  # Ciano Neon
    ".db":       ("fa5s.database",     "#00cfff"),  # Ciano Neon
    ".sqlite":   ("fa5s.database",     "#00cfff"),  # Ciano Neon
    ".png":      ("fa5s.image",        "#ff00ff"),  # Magenta Neon
    ".jpg":      ("fa5s.image",        "#ff00ff"),  # Magenta Neon
    ".jpeg":     ("fa5s.image",        "#ff00ff"),  # Magenta Neon
    ".gif":      ("fa5s.image",        "#ff00ff"),  # Magenta Neon
    ".svg":      ("fa5s.image",        "#ff00ff"),  # Magenta Neon
    ".ico":      ("fa5s.image",        "#ff00ff"),  # Magenta Neon
    ".ttf":      ("fa5s.font",         "#ffff00"),  # Amarelo Neon
    ".otf":      ("fa5s.font",         "#ffff00"),  # Amarelo Neon
    ".woff":     ("fa5s.font",         "#ffff00"),  # Amarelo Neon
    ".pdf":      ("fa5s.file-pdf",     "#ff4444"),  # Vermelho Neon
    ".zip":      ("fa5s.file-archive", "#aaaaaa"),  # Cinza Claro
    ".tar":      ("fa5s.file-archive", "#aaaaaa"),  # Cinza Claro
    ".gz":       ("fa5s.file-archive", "#aaaaaa"),  # Cinza Claro
    ".txt":      ("fa5s.file-alt",     "#aaaaaa"),  # Cinza Claro
    ".csv":      ("fa5s.table",        "#00ff99"),  # Verde Neon
    ".exe":      ("fa5s.bolt",         "#ffff00"),  # Amarelo Neon
    ".dll":      ("fa5s.bolt",         "#ffff00"),  # Amarelo Neon
    ".gitignore":("fa5b.git-alt",      "#ff4444"),  # Vermelho Neon
    # ── Linguagens adicionadas pelo Mult_Linguas ──────────────
    ".jsx":       ("fa5b.js",           "#ffff00"),  # Amarelo Neon
    ".tsx":       ("fa5b.js",           "#00cfff"),  # Ciano Neon
    ".scss":      ("fa5b.css3-alt",     "#ff00ff"),  # Magenta Neon
    ".c":         ("fa5s.file-code",    "#00cfff"),  # Ciano Neon
    ".cpp":       ("fa5s.file-code",    "#ff00ff"),  # Magenta Neon
    ".lua":       ("fa5s.moon",         "#00ffff"),  # Ciano Neon
    ".mk":        ("fa5s.tools",        "#ffff00"),  # Amarelo Neon
    ".dockerfile":("fa5b.docker",       "#00cfff"),  # Ciano Neon
}

_PACK_PASTEL = {
    ".py":       ("fa5b.python",       "#a8d8a8"),  # Verde Pastel
    ".js":       ("fa5b.js",           "#ffd3a8"),  # Laranja Pastel
    ".ts":       ("fa5b.js",           "#a8c8f0"),  # Azul Pastel
    ".html":     ("fa5b.html5",        "#f0a8a8"),  # Rosa Pastel
    ".htm":      ("fa5b.html5",        "#f0a8a8"),  # Rosa Pastel
    ".css":      ("fa5b.css3-alt",     "#a8c8f0"),  # Azul Pastel
    ".json":     ("fa5s.database",     "#ffd3a8"),  # Laranja Pastel
    ".md":       ("fa5b.markdown",     "#cccccc"),  # Cinza Claro
    ".xml":      ("fa5s.code",         "#cccccc"),  # Cinza Claro
    ".yml":      ("fa5s.cog",          "#d8a8f0"),  # Lilás Pastel
    ".yaml":     ("fa5s.cog",          "#d8a8f0"),  # Lilás Pastel
    ".toml":     ("fa5s.cog",          "#d8a8f0"),  # Lilás Pastel
    ".ini":      ("fa5s.cog",          "#d8a8f0"),  # Lilás Pastel
    ".cfg":      ("fa5s.cog",          "#d8a8f0"),  # Lilás Pastel
    ".env":      ("fa5s.lock",         "#ffd3a8"),  # Laranja Pastel
    ".sh":       ("fa5s.terminal",     "#a8d8a8"),  # Verde Pastel
    ".bat":      ("fa5s.terminal",     "#a8d8a8"),  # Verde Pastel
    ".ps1":      ("fa5b.windows",      "#a8c8f0"),  # Azul Pastel
    ".sql":      ("fa5s.database",     "#a8c8f0"),  # Azul Pastel
    ".db":       ("fa5s.database",     "#a8c8f0"),  # Azul Pastel
    ".sqlite":   ("fa5s.database",     "#a8c8f0"),  # Azul Pastel
    ".png":      ("fa5s.image",        "#d8a8f0"),  # Lilás Pastel
    ".jpg":      ("fa5s.image",        "#d8a8f0"),  # Lilás Pastel
    ".jpeg":     ("fa5s.image",        "#d8a8f0"),  # Lilás Pastel
    ".gif":      ("fa5s.image",        "#d8a8f0"),  # Lilás Pastel
    ".svg":      ("fa5s.image",        "#d8a8f0"),  # Lilás Pastel
    ".ico":      ("fa5s.image",        "#d8a8f0"),  # Lilás Pastel
    ".ttf":      ("fa5s.font",         "#ffd3a8"),  # Laranja Pastel
    ".otf":      ("fa5s.font",         "#ffd3a8"),  # Laranja Pastel
    ".woff":     ("fa5s.font",         "#ffd3a8"),  # Laranja Pastel
    ".pdf":      ("fa5s.file-pdf",     "#f0a8a8"),  # Rosa Pastel
    ".zip":      ("fa5s.file-archive", "#cccccc"),  # Cinza Claro
    ".tar":      ("fa5s.file-archive", "#cccccc"),  # Cinza Claro
    ".gz":       ("fa5s.file-archive", "#cccccc"),  # Cinza Claro
    ".txt":      ("fa5s.file-alt",     "#cccccc"),  # Cinza Claro
    ".csv":      ("fa5s.table",        "#a8d8a8"),  # Verde Pastel
    ".exe":      ("fa5s.bolt",         "#ffd3a8"),  # Laranja Pastel
    ".dll":      ("fa5s.bolt",         "#ffd3a8"),  # Laranja Pastel
    ".gitignore":("fa5b.git-alt",      "#f0a8a8"),  # Rosa Pastel
    # ── Linguagens adicionadas pelo Mult_Linguas ──────────────
    ".jsx":       ("fa5b.js",           "#ffd3a8"),  # Laranja Pastel
    ".tsx":       ("fa5b.js",           "#a8c8f0"),  # Azul Pastel
    ".scss":      ("fa5b.css3-alt",     "#d8a8f0"),  # Lilás Pastel
    ".c":         ("fa5s.file-code",    "#a8c8f0"),  # Azul Pastel
    ".cpp":       ("fa5s.file-code",    "#d8a8f0"),  # Lilás Pastel
    ".lua":       ("fa5s.moon",         "#a8e8f8"),  # Ciano Pastel
    ".mk":        ("fa5s.tools",        "#ffd3a8"),  # Laranja Pastel
    ".dockerfile":("fa5b.docker",       "#a8c8f0"),  # Azul Pastel
}

_PACK_CINZA = {
    ".py":       ("fa5b.python",       "#888888"),  # Cinza
    ".js":       ("fa5b.js",           "#888888"),  # Cinza
    ".ts":       ("fa5b.js",           "#aaaaaa"),  # Cinza Claro
    ".html":     ("fa5b.html5",        "#888888"),  # Cinza
    ".htm":      ("fa5b.html5",        "#888888"),  # Cinza
    ".css":      ("fa5b.css3-alt",     "#888888"),  # Cinza
    ".json":     ("fa5s.database",     "#888888"),  # Cinza
    ".md":       ("fa5b.markdown",     "#666666"),  # Cinza Médio
    ".xml":      ("fa5s.code",         "#666666"),  # Cinza Médio
    ".yml":      ("fa5s.cog",          "#666666"),  # Cinza Médio
    ".yaml":     ("fa5s.cog",          "#666666"),  # Cinza Médio
    ".toml":     ("fa5s.cog",          "#666666"),  # Cinza Médio
    ".ini":      ("fa5s.cog",          "#666666"),  # Cinza Médio
    ".cfg":      ("fa5s.cog",          "#666666"),  # Cinza Médio
    ".env":      ("fa5s.lock",         "#aaaaaa"),  # Cinza Claro
    ".sh":       ("fa5s.terminal",     "#aaaaaa"),  # Cinza Claro
    ".bat":      ("fa5s.terminal",     "#aaaaaa"),  # Cinza Claro
    ".ps1":      ("fa5b.windows",      "#aaaaaa"),  # Cinza Claro
    ".sql":      ("fa5s.database",     "#888888"),  # Cinza
    ".db":       ("fa5s.database",     "#888888"),  # Cinza
    ".sqlite":   ("fa5s.database",     "#888888"),  # Cinza
    ".png":      ("fa5s.image",        "#888888"),  # Cinza
    ".jpg":      ("fa5s.image",        "#888888"),  # Cinza
    ".jpeg":     ("fa5s.image",        "#888888"),  # Cinza
    ".gif":      ("fa5s.image",        "#888888"),  # Cinza
    ".svg":      ("fa5s.image",        "#888888"),  # Cinza
    ".ico":      ("fa5s.image",        "#888888"),  # Cinza
    ".ttf":      ("fa5s.font",         "#888888"),  # Cinza
    ".otf":      ("fa5s.font",         "#888888"),  # Cinza
    ".woff":     ("fa5s.font",         "#888888"),  # Cinza
    ".pdf":      ("fa5s.file-pdf",     "#888888"),  # Cinza
    ".zip":      ("fa5s.file-archive", "#666666"),  # Cinza Médio
    ".tar":      ("fa5s.file-archive", "#666666"),  # Cinza Médio
    ".gz":       ("fa5s.file-archive", "#666666"),  # Cinza Médio
    ".txt":      ("fa5s.file-alt",     "#888888"),  # Cinza
    ".csv":      ("fa5s.table",        "#aaaaaa"),  # Cinza Claro
    ".exe":      ("fa5s.bolt",         "#888888"),  # Cinza
    ".dll":      ("fa5s.bolt",         "#888888"),  # Cinza
    ".gitignore":("fa5b.git-alt",      "#888888"),  # Cinza
    # ── Linguagens adicionadas pelo Mult_Linguas ──────────────
    ".jsx":       ("fa5b.js",           "#aaaaaa"),  # Cinza Claro
    ".tsx":       ("fa5b.js",           "#888888"),  # Cinza
    ".scss":      ("fa5b.css3-alt",     "#888888"),  # Cinza
    ".c":         ("fa5s.file-code",    "#888888"),  # Cinza
    ".cpp":       ("fa5s.file-code",    "#888888"),  # Cinza
    ".lua":       ("fa5s.moon",         "#888888"),  # Cinza
    ".mk":        ("fa5s.tools",        "#888888"),  # Cinza
    ".dockerfile":("fa5b.docker",       "#888888"),  # Cinza
}

PACKS_ICONES = {
    "fa5":        _ICONE_EXT,
    "mdi":        _PACK_MDI,
    "mdi_neon":   _PACK_MDI_NEON,
    "minimalista":_PACK_MINIMALISTA,
    "neon":       _PACK_NEON,
    "pastel":     _PACK_PASTEL,
    "cinza":      _PACK_CINZA,
}

_PACK_ATIVO = "fa5"

# ══════════════════════════════════════════════════════════════════════
# 22. CORES — menu de contexto (heinContextMenu)
# ══════════════════════════════════════════════════════════════════════

COR_MENU_CONTEXTO_FUNDO        = PRETO_FOSCO   # fundo do popup
COR_MENU_CONTEXTO_TEXTO        = "#e8f5e8"     # texto dos itens
COR_MENU_CONTEXTO_TEXTO_DESATIV= "#3a4d3a"     # itens desabilitados
COR_MENU_CONTEXTO_HOVER        = "#1a2e1a"     # fundo item selecionado
COR_MENU_CONTEXTO_BORDA        = "#252530"     # borda do menu
COR_MENU_CONTEXTO_SEPARADOR    = "#1a2e1a"     # linha divisória
COR_MENU_CONTEXTO_ICONE        = "#6b8f6b"     # cor dos ícones qta
MENU_CONTEXTO_RAIO             = "4px"         # border-radius dos cantos

# ══════════════════════════════════════════════════════════════════════
# 23. PARSER JSON COM COMENTÁRIOS
# ══════════════════════════════════════════════════════════════════════

# ⚠️  função grande (65 linhas)
def _reparar_json(texto: str) -> str:
    """
    Tenta corrigir erros comuns de edição manual no JSON sem perder dados.

    Corrige:
      - Literais Python True/False/None fora de strings → true/false/null
      - Texto inválido após valor antes da vírgula:  "#010108",SIM  →  "#010108",
      - Vírgulas trailing antes de } ou ]:           { "a": 1, }    →  { "a": 1 }
      - BOM (byte-order mark) no início do arquivo.
    """
    texto = texto.lstrip("\ufeff")

    # Substitui True/False/None Python → true/false/null JSON,
    # mas apenas fora de strings entre aspas duplas.
    def _substituir_python_bools(texto: str) -> str:
        resultado = []
        i = 0
        while i < len(texto):
            if texto[i] == '"':
                # Avança pela string inteira sem tocar nela
                resultado.append(texto[i])
                i += 1
                while i < len(texto):
                    c = texto[i]
                    resultado.append(c)
                    if c == '\\':
                        i += 1
                        if i < len(texto):
                            resultado.append(texto[i])
                    elif c == '"':
                        break
                    i += 1
                i += 1
            elif texto[i:i+4] == 'True' and (i + 4 >= len(texto) or not texto[i+4].isalnum()):
                resultado.append('true')
                i += 4
            elif texto[i:i+5] == 'False' and (i + 5 >= len(texto) or not texto[i+5].isalnum()):
                resultado.append('false')
                i += 5
            elif texto[i:i+4] == 'None' and (i + 4 >= len(texto) or not texto[i+4].isalnum()):
                resultado.append('null')
                i += 4
            else:
                resultado.append(texto[i])
                i += 1

        return ''.join(resultado)

    texto = _substituir_python_bools(texto)

    # Texto não-JSON após valor seguido de vírgula: "val",PALAVRA → "val",
    texto = re.sub(
        r'(:\s*(?:"(?:[^"\\]|\\.)*"|-?\d[\d.eE+\-]*|true|false|null))',
        lambda m: m.group(0),  # placeholder: garante que o grupo captura valores
        texto,
    )
    # Reescreve usando substituição direta (mais confiável que lookahead)
    texto = re.sub(
        r'(:\s*(?:"[^"]*"|\d[\d.]*|true|false|null))\s*,\s*[A-Za-z_]\w*(\s*\n)',
        r'\1,\2',
        texto,
    )
    texto = re.sub(r',( *[}\]])', r'\1', texto)

    return texto

def _ler_json(caminho: str):
    """
    Lê um arquivo JSON com suporte a comentários de linha e inline.

    Suporta:
        // comentário de linha inteira
        "chave": "valor"  // comentário no fim da linha

    Preserva // dentro de strings (ex: "url": "http://...").

    Estratégia de parse:
        1. Tenta direto.
        2. Se falhar, aplica _reparar_json() (corrige erros comuns).
        3. Se ainda falhar, propaga json.JSONDecodeError — nunca swallowa.
    O chamador (gerenciador_tema.carregar) trata o erro e usa fallback.
    """
    with open(caminho, "r", encoding="utf-8-sig") as _f:
        _texto = _f.read()
    # Remove // fora de strings
    _texto = re.sub(
        r'"' r'(?:[^"\\]|\\.)*' r'"|//[^\n]*',
        lambda m: m.group(0) if m.group(0).startswith('"') else '',
        _texto,
    )
    try:

        return json.loads(_texto)

    except json.JSONDecodeError:
        pass
    # Tenta auto-repair
    _reparado = _reparar_json(_texto)

    return json.loads(_reparado)  # propaga JSONDecodeError se ainda falhar

# ══════════════════════════════════════════════════════════════════════════════
# BordaOverlay — widget filho transparente que desenha borda SOBRE os filhos
# ══════════════════════════════════════════════════════════════════════════════
class BordaOverlay:
    """
    Fábrica / mixin de overlay de borda para qualquer QWidget.

    Uso (dentro do __init__ ou _construir do widget pai):
        self._borda_overlay = BordaOverlay.criar(self)

    Para atualizar (chamado pelo gerenciador_configurar):
        self._borda_overlay.atualizar(cor, larg, estilo, raio)

    No resizeEvent do pai:
        if hasattr(self, "_borda_overlay"):
            self._borda_overlay.setGeometry(self.rect())
            self._borda_overlay.raise_()
    """

    _ESTILOS = {}   # preenchido na primeira importação do Qt

    @staticmethod
    def _qt_estilo(nome: str):
        from PySide6.QtCore import Qt
        mapa = {
            "solid":        Qt.SolidLine,
            "dashed":       Qt.DashLine,
            "dotted":       Qt.DotLine,
            "dash-dot":     Qt.DashDotLine,
            "dash-dot-dot": Qt.DashDotDotLine,
            "none":         Qt.NoPen,
        }

        return mapa.get(nome, Qt.SolidLine)

    @staticmethod
    def criar(pai) -> "BordaOverlay._Widget":
        w = BordaOverlay._Widget(pai)
        w.setGeometry(pai.rect())
        w.raise_()

        return w

    class _Widget:
        """Widget interno — herda de QWidget em tempo de criação (lazy)."""
        # ⚠️  função grande (56 linhas)
        def __new__(cls, pai):
            from PySide6.QtWidgets import QWidget
            from PySide6.QtCore import Qt

            class _Impl(QWidget):
                def __init__(self, parent):
                    super().__init__(parent)
                    self.setAttribute(Qt.WA_TransparentForMouseEvents)
                    self.setAttribute(Qt.WA_NoSystemBackground)
                    self._cor         = "#CC7A14"
                    self._larg        = 0
                    self._raio        = 10
                    self._sem_topo    = False
                    self._sem_direita = False
                    self._qt_est      = Qt.SolidLine

                def atualizar(self, cor: str, larg: int, estilo: str, raio: int = 10, sem_topo: bool = False, sem_direita: bool = False):
                    self._cor         = cor
                    self._larg        = larg
                    self._raio        = raio
                    self._sem_topo    = sem_topo
                    self._sem_direita = sem_direita
                    self._qt_est      = BordaOverlay._qt_estilo(estilo)
                    self.update()
                    self.raise_()

                def paintEvent(self, event):
                    if self._larg <= 0:

                        return

                    from PySide6.QtGui import QPainter, QPen, QColor
                    from PySide6.QtCore import QRectF, QPointF, Qt
                    painter = QPainter(self)
                    painter.setRenderHint(QPainter.Antialiasing)
                    pen = QPen(QColor(self._cor), self._larg, self._qt_est)
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)
                    half = self._larg / 2.0
                    if self._sem_topo:
                        w, h = self.width(), self.height()
                        # borda esquerda (sempre)
                        painter.drawLine(QPointF(half, 0), QPointF(half, h - half))
                        # borda inferior (sempre)
                        painter.drawLine(QPointF(half, h - half), QPointF(w - half, h - half))
                        # borda direita (opcional)
                        if not self._sem_direita:
                            painter.drawLine(QPointF(w - half, 0), QPointF(w - half, h - half))
                    else:
                        rect = QRectF(self.rect()).adjusted(half, half, -half, -half)
                        painter.drawRoundedRect(rect, self._raio, self._raio)
                    painter.end()

            obj = _Impl(pai)

            return obj

# BordaCompleta — overlay que desenha o contorno FECHADO passando em volta da aba ativa
# ══════════════════════════════════════════════════════════════════════════════════════
class BordaCompleta:
    """
    Overlay transparente que desenha UMA ÚNICA curva fechada cobrindo o painel inteiro,
    passando por cima da aba ativa.

    Uso:
        self._borda_completa = BordaCompleta.criar(self, self._obter_tab)

    Onde `obter_tab` é um callable que retorna QRect da aba ativa
    em coordenadas do próprio widget pai (ou None se não há aba).

    Para atualizar cor/espessura/estilo:
        self._borda_completa.atualizar(cor, larg, estilo)

    No resizeEvent:
        if hasattr(self, '_borda_completa'):
            self._borda_completa.setGeometry(self.rect())
            self._borda_completa.raise_()
    """

    @staticmethod
    def criar(pai, obter_tab, sem_base: bool = False) -> "BordaCompleta._Widget":
        w = BordaCompleta._Widget(pai, obter_tab, sem_base)
        w.setGeometry(pai.rect())
        w.raise_()

        return w

    class _Widget: # ⚠️ função grande (92 linhas)
        def __new__(cls, pai, obter_tab, sem_base=False):
            from PySide6.QtWidgets import QWidget
            from PySide6.QtCore import Qt

            class _Impl(QWidget):
                def __init__(self, parent, fn_tab, sem_base=False):
                    super().__init__(parent)
                    self.setAttribute(Qt.WA_TransparentForMouseEvents)
                    self.setAttribute(Qt.WA_NoSystemBackground)
                    self._fn_tab   = fn_tab
                    self._cor      = "#CC7A14"
                    self._larg     = 0
                    self._qt_est   = Qt.SolidLine
                    self._sem_base = sem_base

                def atualizar(self, cor: str, larg: int, estilo: str):
                    from PySide6.QtCore import Qt
                    _mapa = {
                        "solid": Qt.SolidLine, "dashed": Qt.DashLine,
                        "dotted": Qt.DotLine, "dash-dot": Qt.DashDotLine,
                        "dash-dot-dot": Qt.DashDotDotLine, "none": Qt.NoPen,
                    }
                    self._cor    = cor
                    self._larg   = larg
                    self._qt_est = _mapa.get(estilo, Qt.SolidLine)
                    self.update()
                    self.raise_()

                # ⚠️  função grande (60 linhas)
                def paintEvent(self, event):
                    if self._larg <= 0:
                        return

                    from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath
                    from PySide6.QtCore import Qt

                    w    = float(self.width())
                    h    = float(self.height())
                    half = self._larg / 2.0

                    tab_r = self._fn_tab()
                    if tab_r is None or tab_r.isEmpty():
                        # Sem aba ativa: topo + dois lados (sem base se sem_base=True)
                        path = QPainterPath()
                        path.moveTo(half, h - half)
                        path.lineTo(half, half)          # lado esquerdo
                        path.lineTo(w - half, half)      # topo
                        path.lineTo(w - half, h - half)  # lado direito
                        if not self._sem_base:
                            path.closeSubpath()          # fecha base
                        painter = QPainter(self)
                        painter.setRenderHint(QPainter.Antialiasing)
                        pen = QPen(QColor(self._cor), self._larg, self._qt_est)
                        pen.setJoinStyle(Qt.RoundJoin)
                        painter.setPen(pen)
                        painter.setBrush(Qt.NoBrush)
                        painter.drawPath(path)
                        painter.end()
                        return

                    tx   = float(tab_r.x())
                    ty   = float(tab_r.y())
                    tw   = float(tab_r.width())
                    th   = float(tab_r.height())
                    f    = 8.0
                    rc   = 4.0

                    path = QPainterPath()
                    path.moveTo(half, h - half)          # canto inferior esquerdo
                    path.lineTo(half, ty + th)            # sobe pelo lado esquerdo

                    if tx > half:
                        # conector horizontal esquerdo (quando a aba não está na borda)
                        path.lineTo(tx, ty + th)
                        path.cubicTo(tx + f*0.5, ty+th,
                                     tx+f, ty+th - f*0.5,
                                     tx+f, ty+th - f)
                    else:
                        # aba na borda esquerda: pé-S saindo direto do lado do painel
                        path.cubicTo(half + f*0.5, ty+th,
                                     tx+f, ty+th - f*0.5,
                                     tx+f, ty+th - f)

                    path.lineTo(tx+f, ty+rc)              # sobe o lado esquerdo da aba
                    path.quadTo(tx+f, ty, tx+f+rc, ty)    # canto superior esquerdo
                    path.lineTo(tx+tw-f-rc, ty)            # topo da aba
                    path.quadTo(tx+tw-f, ty,               # canto superior direito
                                tx+tw-f, ty+rc)
                    path.lineTo(tx+tw-f, ty+th-f)          # desce lado direito da aba
                    path.cubicTo(tx+tw-f, ty+th - f*0.5,  # pé-S direito
                                 tx+tw - f*0.5, ty+th,
                                 tx+tw, ty+th)
                    path.lineTo(w - half, ty + th)         # conector horizontal direito
                    path.lineTo(w - half, h - half)        # desce pelo lado direito
                    if not self._sem_base:
                        path.closeSubpath()                # fecha na base (painéis com conteúdo abaixo)

                    painter = QPainter(self)
                    painter.setRenderHint(QPainter.Antialiasing)
                    pen = QPen(QColor(self._cor), self._larg, self._qt_est)
                    pen.setJoinStyle(Qt.RoundJoin)
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)
                    painter.drawPath(path)
                    painter.end()

            obj = _Impl(pai, obter_tab, sem_base)

            return obj
