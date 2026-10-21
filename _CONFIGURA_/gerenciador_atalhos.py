# 📁 _CONFIGURA_/gerenciador_atalhos.py
"""
Lê o atalhos.json e registra os QShortcuts na janela principal.
Permite recarregar atalhos em tempo real sem reiniciar a IDE.
Detecta e avisa sobre conflitos entre atalhos (sem bloquear).

✅ AtalhoLivre1–15 mapeados
✅ ctrl-z/y/x/c/v/a removidos de _NATIVOS_QT (eram tratados pelo menu, causando duplo-undo)
   — agora APENAS o Editor.py e a MainWindow controlam esses atalhos
✅ ide::AbrirAutoComplete  → abrir_autocomplete
✅ ide::AbrirEditorConfig  → abrir_configurar
✅ ide::FormatarCodigo     → formatar_codigo_nucleo   (Ctrl+Alt+F)
"""
import json
from _LOG_.log import log
_ARQ = "gerenciador_atalhos.py"
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtCore import QFileSystemWatcher, Qt
from _CONFIGURA_ import ARQUIVO_ATALHOS, ATALHOS_NAO_REGISTRAR, _ler_json
# Mapa: string do JSON → método da MainWindow
_ACOES: dict[str, str] = {
    # ── Edição básica ──────────────────────────────────────────────
    "editor::Desfazer":                    "desfazer",
    "editor::Refazer":                     "refazer",
    "editor::RefazerAlternativo":          "refazer",
    "editor::SalvarArquivo":               "salvar_arquivo",
    "editor::SelecionarTudo":              "selecionar_tudo",
    "editor::Recortar":                    "recortar",
    "editor::Copiar":                      "copiar",
    "editor::Colar":                       "colar",
    "editor::NovoArquivo":                 "novo_arquivo_aba",
    "editor::AbrirArquivo":                "abrir_arquivo",
    # ── Navegação ──────────────────────────────────────────────────
    "editor::IrParaLinha":                 "ir_para_linha_dialogo",
    "editor::IrParaInicio":                "ir_para_inicio",
    "editor::IrParaFim":                   "ir_para_fim",
    "editor::IrParaDefinicao":             "ir_para_definicao",
    "editor::IrParaDefinicaoMouse":        "ir_para_definicao",
    "editor::VoltarDefinicao":             "voltar_definicao",
    # ── Manipulação de linhas ──────────────────────────────────────
    "editor::MoverLinhaParaCima":          "mover_linha_cima",
    "editor::MoverLinhaParaBaixo":         "mover_linha_baixo",
    "editor::NovaLinhaAbaixo":             "nova_linha_abaixo",
    "editor::ComentarLinha":               "comentar_linha",
    "editor::DeletarLinha":                "deletar_linha",
    "editor::DuplicarLinha":               "duplicar_linha",
    "editor::CentralizarLinha":            "centralizar_linha_cursor",
    # ── Busca ──────────────────────────────────────────────────────
    "busca::AbrirBarra":                   "abrir_busca",
    "busca::BuscarNoArquivo":              "abrir_busca",
    "busca::AbrirSubstituicao":            "abrir_substituicao",
    "busca::IrParaLinha":                  "focar_barra_linha",
    "busca::BuscarMarcacao":               "focar_barra_marcacao",
    "busca::BuscarNoProjeto":              "buscar_no_projeto",
    "busca::AbrirArquivoPorNome":          "focar_barra_arquivo_nome",
    "busca::AbrirCommandPalette":          "abrir_command_palette",
    "busca::SelecionarTodasOcorrencias":   "selecionar_todas_ocorrencias",
    # ── Fonte ──────────────────────────────────────────────────────
    "editor::AumentarFonte":               "aumentar_fonte",
    "editor::DiminuirFonte":               "diminuir_fonte",
    "editor::ResetarFonte":                "resetar_fonte",
    # ── Execução ───────────────────────────────────────────────────
    "editor::ExecutarCodigo":              "executar_codigo",
    # ── Múltiplos cursores ─────────────────────────────────────────
    "editor::AdicionarCursorAcima":        "adicionar_cursor_acima",
    "editor::AdicionarCursorAbaixo":       "adicionar_cursor_abaixo",
    "editor::SelecionarTodasOcorrencias":  "selecionar_todas_ocorrencias",
    "editor::SelecionarProximaOcorrencia": "selecionar_proxima_ocorrencia",
    # ── Dobramento ─────────────────────────────────────────────────
    "editor::RecolherBloco":               "recolher_bloco",
    "editor::ExpandirBloco":               "expandir_bloco",
    "editor::RecolherTudo":                "recolher_tudo",
    "editor::ExpandirTudo":                "expandir_tudo",
    # ── IDE ────────────────────────────────────────────────────────
    "ide::NovoProjeto":                    "novo_projeto",
    "ide::AbrirProjeto":                   "abrir_projeto",
    "ide::TelaCheia":                      "alternar_tela_cheia",
    "ide::AbrirTarefasGlobais":           "abrir_tarefas",
    "ide::AbrirArquivoAtalhos":            "abrir_arquivo_atalhos",
    "ide::AbrirArquivoConfiguracoes":      "abrir_arquivo_configuracoes",
    "ide::AbrirTarefasDoProjeto":          "abrir_tarefas_projeto",
    "ide::AbrirAutoComplete":              "abrir_autocomplete",
    "ide::AbrirEditorConfig":              "abrir_configurar",
    "ide::AbrirPainelErros":               "abrir_painel_erros",
    "ide::AbrirArquivoNucleo":             "abrir_nucleo_config",
    "ide::AbrirPromptNucleo":              "abrir_prompt_nucleo",   # IMP-D
    "ide::AbrirExecutores":                "abrir_executores",
    "ide::FormatarCodigo":                 "formatar_codigo_nucleo",
    # ── Terminal ───────────────────────────────────────────────────
    "terminal::AlternarVisibilidade":      "alternar_terminal",
    "terminal::NovoTerminal":              "novo_terminal",
    "terminal::FecharTerminalAtivo":       "fechar_terminal_ativo",
    "terminal::LimparTerminal":            "limpar_terminal_ativo",
    # ── Painéis visuais ────────────────────────────────────────────
    "ide::AlternarPainelArquivos":         "alternar_painel_arquivos",
    "ide::AlternarPainelIA":               "alternar_painel_ia",
    "ide::AlternarPainelGit":              "alternar_painel_git",
    "ide::AlternarOutline":               "alternar_outline",
    "ide::AlternarEditor":                "alternar_editor",
    # ── Tarefas ────────────────────────────────────────────────────
    "tarefa::CriarVenv":                   "tarefa_criar_venv",
    "tarefa::AtivarVenvAtualizarPip":      "tarefa_ativar_venv",
    "tarefa::ConfigurarNovoProjeto":       "novo_projeto",
}

_NATIVOS_QT = {}

class GerenciadorAtalhos:
    """
    Registra e gerencia todos os QShortcuts da IDE a partir do atalhos.json.

    Uso em MainWindow.__init__:
        self._atalhos = GerenciadorAtalhos(self)
        self._atalhos.carregar()

    Hot-reload: edite e salve o atalhos.json dentro da própria IDE —
    os atalhos são reaplicados automaticamente sem reiniciar.
    """

    def __init__(self, janela):
        self._janela    = janela
        self._shortcuts: list[QShortcut] = []
        self._watcher = QFileSystemWatcher()
        self._watcher.fileChanged.connect(self._ao_arquivo_alterado)
        self._erro_json: str = ""  # mensagem do último erro de JSON

    def _ao_arquivo_alterado(self, caminho: str):
        if caminho not in self._watcher.files():
            self._watcher.addPath(caminho)
        self.carregar(caminho)
        self._janela.statusBar().showMessage("⌨️  Atalhos recarregados!", 3000)

    # ⚠️  função grande (67 linhas)
    def carregar(self, caminho: str = None) -> bool:
        """
        Carrega atalhos.json com cadeia de fallback.

        Cadeia:
            1. Parse + auto-repair via _ler_json()
            2. Backup (.bak) do último load bem-sucedido
            3. Lista vazia — IDE abre sem atalhos customizados (Qt nativos continuam)
        """
        import os
        caminho = caminho or ARQUIVO_ATALHOS
        caminho_bak = caminho + ".bak"
        dados = None

        # ── Tentativa 1 ───────────────────────────────────────────────────────
        try:
            dados = _ler_json(caminho)
            self._erro_json = ""
            self._salvar_backup(caminho, caminho_bak)
        except (ValueError, json.JSONDecodeError) as e:
            self._erro_json = str(e)
            log.erro(_ARQ, "carregar", f"JSON inválido (tentando backup): {e}")
        except Exception as e:
            self._erro_json = str(e)
            log.erro(_ARQ, "carregar", f"Erro ao carregar (tentando backup): {e}", caminho)

        # ── Tentativa 2: backup ───────────────────────────────────────────────
        if dados is None and os.path.isfile(caminho_bak):
            try:
                dados = _ler_json(caminho_bak)
                log.aviso(_ARQ, "carregar", f"usando backup: {caminho_bak}")
            except Exception as e2:
                log.erro(_ARQ, "carregar", "backup também inválido", str(e2))

        # ── Tentativa 3: lista vazia — IDE abre sem atalhos ──────────────────
        if dados is None:
            dados = []
            log.aviso(_ARQ, "carregar", "atalhos.json inválido — IDE sem atalhos customizados")

        for sc in self._shortcuts:
            sc.setEnabled(False)
            sc.deleteLater()
        self._shortcuts = []

        # Verifica conflitos
        mapa_teclas: dict[str, list[str]] = {}
        for bloco in dados:
            contexto = bloco.get("contexto", "?")
            for tecla, acao in bloco.get("atalhos", {}).items():
                seq   = self._converter_tecla(tecla)
                chave = seq.lower()
                mapa_teclas.setdefault(chave, []).append(f"{contexto}::{acao}")

        conflitos = {k: v for k, v in mapa_teclas.items() if len(v) > 1}
        if conflitos:
            log.aviso(_ARQ, "carregar", f"Conflitos detectados: {list(conflitos.keys())}")

        for bloco in dados:
            for tecla, acao in bloco.get("atalhos", {}).items():
                self._registrar(tecla, acao)

        if caminho not in self._watcher.files():
            self._watcher.addPath(caminho)

        log.ok(_ARQ, "carregar", f"{len(self._shortcuts)} atalho(s) carregado(s)")

        return True

    def _salvar_backup(self, origem: str, destino: str) -> None:
        try:
            import shutil as _sh
            _sh.copy2(origem, destino)
        except Exception as e:
            log.aviso(_ARQ, "_salvar_backup", str(e))

    def recarregar(self):
        self.carregar()

    def _registrar(self, tecla: str, acao: str):
        if tecla.lower() in _NATIVOS_QT:

            return

        if tecla.lower() in ATALHOS_NAO_REGISTRAR:

            return

        metodo_nome = _ACOES.get(acao)
        if not metodo_nome:

            return

        metodo = getattr(self._janela, metodo_nome, None)
        if metodo is None:
            log.aviso(_ARQ, "_registrar", f"Método '{metodo_nome}' não encontrado na MainWindow")

            return

        sequencia = self._converter_tecla(tecla)
        try:
            sc = QShortcut(QKeySequence(sequencia), self._janela)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(metodo)
            self._shortcuts.append(sc)

            """# ← ADICIONA ISSO (remove depois do debug)
            if tecla.lower() == "ctrl-l":
                print(f">>> ctrl-l REGISTRADO: seq='{sequencia}' metodo='{metodo_nome}'")
                sc.activatedAmbiguously.connect(
                    lambda: print(">>> ctrl-l AMBIGUIDADE — outro shortcut competindo!")
                )"""

        except Exception as e:
            log.erro(_ARQ, "_registrar", f"Erro ao registrar '{tecla}'", str(e))

    @staticmethod
    def _converter_tecla(tecla: str) -> str:
        mapa = {
            "ctrl": "Ctrl", "alt": "Alt", "shift": "Shift",
            "meta": "Meta", "win": "Meta",
            "up": "Up", "down": "Down", "left": "Left", "right": "Right",
            "enter": "Return", "return": "Return", "esc": "Escape",
            "tab": "Tab", "del": "Delete", "backspace": "Backspace",
            "+": "Plus", "-": "Minus", "=": "Equal",
            "f1":  "F1",  "f2":  "F2",  "f3":  "F3",  "f4":  "F4",
            "f5":  "F5",  "f6":  "F6",  "f7":  "F7",  "f8":  "F8",
            "f9":  "F9",  "f10": "F10", "f11": "F11", "f12": "F12",
        }
        partes = [p for p in tecla.split("-") if p]
        if tecla.endswith("-"):
            partes.append("-")

        return "+".join(

            mapa.get(p.strip().lower(), p.strip().upper())
            for p in partes
        )

    def abrir_para_edicao(self):
        tabs = getattr(self._janela, "tabs", None)
        if tabs:
            tabs.add_new_tab(ARQUIVO_ATALHOS)
