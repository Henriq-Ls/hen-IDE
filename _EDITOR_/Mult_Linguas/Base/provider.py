# _EDITOR_/Mult_Linguas/Base/provider.py
from __future__ import annotations
from PySide6.QtGui import QSyntaxHighlighter, QTextDocument


class _RealceInerte(QSyntaxHighlighter):
    """Highlighter que não faz nada — usado por linguagens sem realce."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        pass

    # Implementa a mesma interface dos highlighters reais para que
    # Editor.atualizar_tema() possa chamar aplicar_tema() sem verificar
    # o tipo — sem isso, trocar de tema com um .txt aberto causa
    # AttributeError e derruba o app inteiro.
    def aplicar_tema(self, tema: dict) -> None:  # noqa: N802
        pass


class LanguageProvider:
    """
    Contrato base de todo provider de linguagem da hein IDE.

    Cada subpasta de Mult_Linguas/ expõe:
        LANGUAGE_PROVIDER = MinhaLinguagemProvider()

    O LanguageManager lê esse atributo na auto-descoberta.
    """

    # ── Metadados ─────────────────────────────────────────────────────────
    extensions:  list[str] = []   # ex: ['.py', '.pyw']
    name:        str        = ''  # ex: 'Python'

    # ── Comportamento do Outline ──────────────────────────────────────────
    # Valores possíveis:
    #   'python_ast'   → parse AST em thread (PainelOutline existente)
    #   'preview_md'   → render Markdown no QTextBrowser
    #   'preview_html' → render HTML no QTextBrowser
    #   'tree_json'    → árvore estrutural JSON
    #   'tree_xml'     → árvore estrutural XML
    #   'tree_yaml'    → árvore estrutural YAML
    #   'none'         → outline vazio
    outline_mode: str = 'none'

    # ── Recursos ──────────────────────────────────────────────────────────
    lint:         bool = False   # roda _ThreadLint?
    autocomplete: str  = 'none'  # 'jedi' | 'none'
    spell_check:  bool = False   # True → instancia CorretorOrtografico PT-BR

    # ── Execução ──────────────────────────────────────────────────────────
    # can_run = True  → ▶ abre ExecutorTerminal dedicado (não-Python)
    # run_extensoes   → subset executável; [] = usa extensions inteiras
    can_run:       bool      = False
    run_extensoes: list[str] = []

    # ── Barra inferior do Outline ─────────────────────────────────────────
    # Controlam visibilidade e conteúdo dos labels na barra do PainelOutline.
    status_rotulo_a: str  = ''     # rótulo do 1.º label de contexto
    status_rotulo_b: str  = ''     # rótulo do 2.º label de contexto
    mostrar_erros:   bool = False  # True → exibe _lbl_ol_erros
    rotulo_erros:    str  = ''     # 'Erros' | 'Válido' | ''

    # ── Extras de UI (opcionais, usados por linguagens especiais) ──────────
    # tem_barra_formatacao: True → mostra barra de botões (Título/Lista/etc.)
    #                        no topo do PainelOutline, acima da árvore.
    # estilo_visual:        'codigo' (padrão) | 'caderno' (linhas horizontais
    #                        de fundo no editor, tipo papel pautado).
    tem_barra_formatacao: bool = False
    estilo_visual:        str  = 'codigo'

    # ──────────────────────────────────────────────────────────────────────
    # Métodos que cada provider pode sobrescrever
    # ──────────────────────────────────────────────────────────────────────

    def create_highlighter(
        self, document: QTextDocument
    ) -> QSyntaxHighlighter | None:
        """
        Retorna uma instância do highlighter para o documento.
        Retorne None para usar _RealceInerte.
        """
        return _RealceInerte(document)

    def folding_fn(self, texto: str, ext: str, proximo_texto: str = '') -> bool:
        """
        Retorna True se a linha `texto` é dobrável nesta linguagem.
        `proximo_texto` é o conteúdo da linha seguinte (útil para TXT/indentação).
        Padrão: nenhuma linha é dobrável.
        """
        return False

    def provide_outline(self, codigo: str, callback) -> None:
        """
        ASSÍNCRONO — nunca bloqueia a UI thread.

        Inicia o processamento do outline e chama callback(itens) ao concluir.
        - Python:   delega à _ThreadOutlinePy existente.
        - JSON/XML/YAML: pode chamar callback direto (parse rápido).
        - MD/HTML:  não usa callback — aciona _ativar_preview diretamente.

        Padrão: chama callback com lista vazia (sem outline).
        """
        callback([])
