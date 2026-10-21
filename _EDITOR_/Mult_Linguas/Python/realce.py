# 📁 _EDITOR_/Funcionalidades/realce_sintaxe.py
"""
📁 _EDITOR_/Funcionalidades/realce_sintaxe.py
Realce de sintaxe Python integrado ao sistema de temas hein.
"""
import re as _re
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import (
    QSyntaxHighlighter, QTextCharFormat, QColor, QFont
)

# --- Tags de Comentário hein: #cod: (fundo) / #cod; (fonte) / #: (atalho) ---
# Código = primeira + última letra do nome da cor em português.
# #cod:  -> pinta o FUNDO do comentário ("titulo") e fica ATIVO para o #: seguinte.
# #cod;  -> pinta só a FONTE ("paragrafo"/referencia pontual) e tambem fica ATIVO.
# #:     -> herda o TIPO (fundo ou fonte) e a COR de quem estiver mais proximo
#          acima -- seja um #cod: ou um #cod; -- sem repetir o codigo.
_PALETA_TAGS_COMENTARIO = {
    "al": "#3B82F6",  # azul
    "vo": "#E53935",  # vermelho
    "po": "#000000",  # preto
    "ao": "#FBC02D",  # amarelo
    "ca": "#9E9E9E",  # cinza
    "co": "#00ACC1",  # ciano
    "ba": "#F5F5F5",  # branca
    "ve": "#43A047",  # verde
    "ra": "#EC407A",  # rosa
    "ro": "#8E24AA",  # roxo
    "mm": "#8D6E43",  # marrom
    "la": "#FB8C00",  # laranja
}
_CODIGOS_TAGS_COMENTARIO = list(_PALETA_TAGS_COMENTARIO.keys())
_N_TAGS_COMENTARIO = len(_CODIGOS_TAGS_COMENTARIO)
# indice 0 = nenhuma; 1..N = cor ativa em modo FUNDO (veio de #cod:);
# N+1..2N = cor ativa em modo FONTE (veio de #cod;). #: herda o que
# estiver mais proximo acima, seja fundo ou fonte.
_INDICE_TAGS_COMENTARIO = {c: i + 1 for i, c in enumerate(_CODIGOS_TAGS_COMENTARIO)}

class RealceSintaxePython(QSyntaxHighlighter):
    """
    Realce de sintaxe para Python.
    Lê as cores direto do dicionário de tema carregado pelo GerenciadorTema.
    """

    def __init__(self, documento, tema: dict = None):
        super().__init__(documento)
        self._regras = []
        # Rastreio de foco pra minimizar os codigos das Tags de Comentario
        # (#al:, #al;, #:): por padrao aparecem discretos (fonte pequena/
        # apagada); voltam ao normal so na linha do cursor ou selecionada.
        self._linha_cursor_tag = -1
        self._bloco_selecao_inicio = -1
        self._bloco_selecao_fim = -1
        self.aplicar_tema(tema or {})

    def definir_linha_cursor_tag(self, numero_bloco: int):
        """Chamado pelo editor (cursorPositionChanged) -- linha onde os
        codigos das Tags de Comentario devem aparecer por completo."""
        anterior = self._linha_cursor_tag
        if anterior == numero_bloco:
            return
        self._linha_cursor_tag = numero_bloco
        doc = self.document()
        for n in (anterior, numero_bloco):
            if 0 <= n < doc.blockCount():
                self.rehighlightBlock(doc.findBlockByNumber(n))

    def definir_selecao_tag(self, bloco_inicio: int, bloco_fim: int):
        """Chamado pelo editor (selectionChanged) com o intervalo de blocos
        selecionados (-1, -1 quando nao ha selecao)."""
        antigo_ini, antigo_fim = self._bloco_selecao_inicio, self._bloco_selecao_fim
        if (antigo_ini, antigo_fim) == (bloco_inicio, bloco_fim):
            return
        self._bloco_selecao_inicio, self._bloco_selecao_fim = bloco_inicio, bloco_fim
        doc = self.document()
        candidatos = [x for x in (antigo_ini, antigo_fim, bloco_inicio, bloco_fim) if x >= 0]
        if not candidatos:
            return
        ini_uniao, fim_uniao = min(candidatos), max(candidatos)
        for n in range(ini_uniao, min(fim_uniao, doc.blockCount() - 1) + 1):
            self.rehighlightBlock(doc.findBlockByNumber(n))

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    # ⚠️  função grande (153 linhas)
    def aplicar_tema(self, tema: dict):
        """Reconstrói todas as regras com as cores do tema recebido."""
        sintaxe = tema.get("editor", {}).get("sintaxe", {})

        # 💡 fallback_opc = Literal["#e0e0e0"] ← defina os valores válidos
        def cor(chave, fallback="#e0e0e0"):
            valor = sintaxe.get(chave, fallback)
            # Remove canal alpha se vier em formato #RRGGBBAA
            if len(valor) == 9 and valor.startswith("#"):
                valor = valor[:7]

            return QColor(valor)

        self._regras = []

        # --- Palavras-chave Python ---
        fmt_kw = self._criar_formato(cor("palavra_chave"), negrito=True)
        palavras_chave = [
            "False", "None", "True", "and", "as", "assert", "async",
            "await", "break", "class", "continue", "def", "del", "elif",
            "else", "except", "finally", "for", "from", "global", "if",
            "import", "in", "is", "lambda", "nonlocal", "not", "or",
            "pass", "raise", "return", "try", "while", "with", "yield",
        ]
        for palavra in palavras_chave:
            padrao = QRegularExpression(rf"\b{palavra}\b")
            self._regras.append((padrao, fmt_kw))

        # --- Funções embutidas ---
        fmt_fn = self._criar_formato(cor("funcao"))
        builtins = [
            "abs", "all", "any", "bin", "bool", "breakpoint", "bytearray",
            "bytes", "callable", "chr", "classmethod", "compile", "complex",
            "delattr", "dict", "dir", "divmod", "enumerate", "eval", "exec",
            "filter", "float", "format", "frozenset", "getattr", "globals",
            "hasattr", "hash", "help", "hex", "id", "input", "int",
            "isinstance", "issubclass", "iter", "len", "list", "locals",
            "map", "max", "memoryview", "min", "next", "object", "oct",
            "open", "ord", "pow", "print", "property", "range", "repr",
            "reversed", "round", "set", "setattr", "slice", "sorted",
            "staticmethod", "str", "sum", "super", "tuple", "type", "vars",
            "zip",
        ]
        for fn in builtins:
            padrao = QRegularExpression(rf"\b{fn}\b(?=\s*\()")
            self._regras.append((padrao, fmt_fn))

        # --- Definição de funções e classes (nome após def/class) ---
        fmt_def = self._criar_formato(cor("funcao"), negrito=True)
        self._regras.append((
            QRegularExpression(r"\bdef\s+(\w+)"),
            fmt_def, 1  # grupo 1
        ))
        self._regras.append((
            QRegularExpression(r"\bclass\s+(\w+)"),
            self._criar_formato(cor("tipo"), negrito=True), 1
        ))

        # --- Decoradores ---
        fmt_dec = self._criar_formato(cor("atributo"))
        self._regras.append((QRegularExpression(r"@\w+"), fmt_dec))

        # --- Números ---
        fmt_num = self._criar_formato(cor("numero"))
        self._regras.append((
            QRegularExpression(r"\b(0x[\da-fA-F]+|0b[01]+|0o[0-7]+|\d+\.?\d*([eE][+-]?\d+)?)\b"),
            fmt_num
        ))

        # --- Strings simples e duplas (linha única) ---
        fmt_str = self._criar_formato(cor("string", "#ce9178"))
        self._regras.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), fmt_str))
        self._regras.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), fmt_str))

        # --- f-strings ---
        # --- f-strings ---
        fmt_fstr = self._criar_formato(cor("string", "#ce9178"))
        fmt_fstr_var = self._criar_formato(cor("variavel", "#e0e0e0"))
        fmt_fstr_col = self._criar_formato(cor("pontuacao_colchete", "#e5c07b"))

        self._fmt_fstr_var = fmt_fstr_var
        self._fmt_fstr_col = fmt_fstr_col

        self._regras.append((QRegularExpression(r'f"[^"\\]*(\\.[^"\\]*)*"'), fmt_fstr))
        self._regras.append((QRegularExpression(r"f'[^'\\]*(\\.[^'\\]*)*'"), fmt_fstr))
        self._regras.append((QRegularExpression(r'\{[\w.]*\}'), fmt_fstr_var))
        self._regras.append((QRegularExpression(r'[{}]'), fmt_fstr_col))

        # --- Comentários ---
        estilo = sintaxe.get("comentario_estilo", "")
        fmt_com = self._criar_formato(
            cor("comentario"),
            italico=("italic" in estilo)
        )
        self._regras.append((QRegularExpression(r"#[^\n]*"), fmt_com))

        # --- Tags de Comentário hein (#cod: fundo / #cod; fonte / #: atalho) ---
        _alternativas = "|".join(_CODIGOS_TAGS_COMENTARIO)
        self._re_tag_fundo = QRegularExpression(rf"#({_alternativas}):")
        self._re_tag_fonte = QRegularExpression(rf"#({_alternativas});")
        self._re_tag_atalho = QRegularExpression(r"#:")

        self._formatos_tag_fundo = {}
        self._formatos_tag_fonte = {}
        for codigo, hexcor in _PALETA_TAGS_COMENTARIO.items():
            fmt_fundo = QTextCharFormat()
            cor_fundo = QColor(hexcor)
            cor_fundo.setAlpha(70)
            fmt_fundo.setBackground(cor_fundo)
            self._formatos_tag_fundo[codigo] = fmt_fundo

            fmt_fonte = QTextCharFormat()
            fmt_fonte.setForeground(QColor(hexcor))
            self._formatos_tag_fonte[codigo] = fmt_fonte

        # Formato "mini" pro codigo da tag (#al:, #al;, #:) quando a linha
        # nao esta em foco -- discreto, fonte pequena e apagada. Some do
        # tamanho normal so na linha do cursor ou dentro da selecao.
        fmt_tag_mini = QTextCharFormat()
        fmt_tag_mini.setFontPointSize(6)
        cor_mini = cor("comentario")
        cor_mini.setAlpha(120)
        fmt_tag_mini.setForeground(cor_mini)
        self._formato_tag_mini = fmt_tag_mini

        # --- Color preview / swatch: #RRGGBB ou #RGB literal no codigo ---
        # pinta o fundo do proprio hex com a cor que ele representa (igual
        # a ideia das Tags de Comentario) e escolhe a fonte (preta/branca)
        # pelo contraste, pra virar uma "amostra" visual da cor.
        self._re_cor_hex = QRegularExpression(
            r"(?<![0-9A-Fa-f])#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})(?![0-9A-Fa-f])"
        )
        self._cache_formato_hex = {}

        # --- self, cls ---
        fmt_self = self._criar_formato(cor("variavel_especial"), italico=True)
        self._regras.append((QRegularExpression(r"\bself\b"), fmt_self))
        self._regras.append((QRegularExpression(r"\bcls\b"), fmt_self))

        # atributos após ponto
        fmt_attr = self._criar_formato(cor("atributo"))

        self._regras.append((
            QRegularExpression(r"(?<=\.)[A-Za-z_][A-Za-z0-9_]*"),
            fmt_attr
        ))

        # --- Operadores ---
        fmt_op = self._criar_formato(cor("operador"))
        self._regras.append((
            QRegularExpression(r"[+\-*/%=<>!&|^~]+"), fmt_op
        ))

        # --- Pontuação ---
        fmt_pont = self._criar_formato(cor("pontuacao"))
        self._regras.append((
            QRegularExpression(r"[.,:;]"),
            fmt_pont
        ))

        # --- Parênteses ---
        fmt_parentese = self._criar_formato(cor("pontuacao_parentese"))
        self._regras.append((
            QRegularExpression(r"[\(\)]"),
            fmt_parentese
        ))

        # --- Colchetes ---
        fmt_colchete = self._criar_formato(cor("pontuacao_colchete"))
        self._regras.append((
            QRegularExpression(r"[\[\]]"),
            fmt_colchete
        ))

        # --- Chaves ---
        fmt_chave = self._criar_formato(cor("pontuacao_chave"))
        self._regras.append((
            QRegularExpression(r"[\{\}]"),
            fmt_chave
        ))

        # Triple-quotes standalone (docstring/comentário) → cor cinza do tema
        self._formato_string_multilinhas = self._criar_formato(
            cor("docstring", "#555555"), italico=True
        )
        # Triple-quotes dentro de expressão (print, =, etc.) → cor de string normal
        self._formato_triple_string = self._criar_formato(
            cor("string", "#05962B")
        )
        # Força re-highlight de todo documento
        self.rehighlight()

    # ------------------------------------------------------------------
    # Interno
    # ------------------------------------------------------------------

    @staticmethod
    def _criar_formato(cor: QColor, negrito=False, italico=False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(cor)
        if negrito:
            fmt.setFontWeight(QFont.Bold)
        if italico:
            fmt.setFontItalic(True)

        return fmt

    def _formato_cor_hex(self, hex_str: str) -> QTextCharFormat:
        """Formato de 'amostra' pra um literal #RRGGBB/#RGB: fundo com a
        propria cor e fonte preta/branca conforme o contraste."""
        chave = hex_str.lower()
        fmt = self._cache_formato_hex.get(chave)
        if fmt is not None:
            return fmt

        cor_fundo = QColor(hex_str)
        if not cor_fundo.isValid():
            return None

        # Luminancia relativa aproximada -> decide se a fonte fica preta ou branca
        luminancia = 0.299 * cor_fundo.red() + 0.587 * cor_fundo.green() + 0.114 * cor_fundo.blue()
        cor_fonte = QColor("#000000") if luminancia > 140 else QColor("#FFFFFF")

        fmt = QTextCharFormat()
        fmt.setBackground(cor_fundo)
        fmt.setForeground(cor_fonte)
        self._cache_formato_hex[chave] = fmt

        return fmt

    # ⚠️  função grande (>70 linhas)
    def highlightBlock(self, texto: str):
        # Estado combinado: unidade = estado tríplice de string (0/1/2),
        # dezena+ = indice da cor ATIVA da cadeia de Tags de Comentario
        # (0 = nenhuma; 1..N = modo FUNDO; N+1..2N = modo FONTE).
        estado_bruto_anterior = self.previousBlockState()
        if estado_bruto_anterior < 0:
            estado_bruto_anterior = 0
        estado_triplice_anterior = estado_bruto_anterior % 10
        tag_ativa = estado_bruto_anterior // 10

        estado_triplice_final = 0
        inicio_busca = 0
        abertura = QRegularExpression(r'("""|\'\'\')')
        _rangos_ml: list[tuple[int, int, object]] = []  # (inicio, fim, formato)

        if estado_triplice_anterior in (1, 2):
            # escolhe o formato do bloco anterior: 1=docstring cinza, 2=string verde
            fmt_cont = self._formato_string_multilinhas if estado_triplice_anterior == 1 else self._formato_triple_string
            match_fim = abertura.match(texto, 0)
            if match_fim.hasMatch():
                fim = match_fim.capturedStart() + 3
                _rangos_ml.append((0, fim, fmt_cont))
                inicio_busca = fim
                estado_triplice_final = 0
            else:
                self.setFormat(0, len(texto), fmt_cont)
                # mantém string tríplice E a cor ativa exatamente como estavam
                self.setCurrentBlockState(estado_triplice_anterior + tag_ativa * 10)

                return

        while True:
            match = abertura.match(texto, inicio_busca)
            if not match.hasMatch():
                break
            inicio_ab = match.capturedStart()
            delim     = match.captured()

            # contexto: há conteúdo não-branco antes do """ nesta linha?
            texto_antes = texto[:inicio_ab].strip()
            fmt_ml = self._formato_triple_string if texto_antes else self._formato_string_multilinhas
            novo_estado = 2 if texto_antes else 1  # 2=string em expressão, 1=docstring

            match_fim = QRegularExpression(_re.escape(delim)).match(texto, inicio_ab + 3)
            if match_fim.hasMatch():
                fim = match_fim.capturedStart() + 3
                _rangos_ml.append((inicio_ab, fim, fmt_ml))
                inicio_busca = fim
            else:
                _rangos_ml.append((inicio_ab, len(texto), fmt_ml))
                estado_triplice_final = novo_estado
                break

        # ── Regras simples ────────────────────────────────────────────
        for regra in self._regras:
            if len(regra) == 3:
                expressao, fmt, grupo = regra
            else:
                expressao, fmt = regra
                grupo = 0
            it = expressao.globalMatch(texto)
            while it.hasNext():
                match = it.next()
                inicio = match.capturedStart(grupo)
                tamanho = match.capturedLength(grupo)
                self.setFormat(inicio, tamanho, fmt)

        for ini, fim, fmt in _rangos_ml:
            self.setFormat(ini, fim - ini, fmt)

            trecho = texto[ini:fim]

            for m in _re.finditer(r"\{[^{}]+\}", trecho):
                s = ini + m.start()
                e = ini + m.end()

                self.setFormat(s, e - s, self._fmt_fstr_var)
                self.setFormat(s, 1, self._fmt_fstr_col)
                self.setFormat(e - 1, 1, self._fmt_fstr_col)

        # ── Tags de Comentário hein: #cod: (fundo) / #cod; (fonte) / #: (atalho) ──
        # #: herda o TIPO (fundo ou fonte) e a COR de quem estiver mais
        # proximo acima, seja um #cod: ou um #cod; -- por isso ambos
        # atualizam "tag_ativa" agora (nao so o #cod:).
        bloco_atual = self.currentBlock().blockNumber()
        linha_em_foco = (
            bloco_atual == self._linha_cursor_tag
            or (
                self._bloco_selecao_inicio >= 0
                and self._bloco_selecao_inicio <= bloco_atual <= self._bloco_selecao_fim
            )
        )
        marcador_span = None  # (inicio, tamanho) do texto "#al:"/"#al;"/"#:" em si

        m_fundo = self._re_tag_fundo.match(texto)
        if m_fundo.hasMatch():
            codigo = m_fundo.captured(1)
            inicio = m_fundo.capturedStart()
            fmt = self._formatos_tag_fundo.get(codigo)
            if fmt is not None:
                self.setFormat(inicio, len(texto) - inicio, fmt)
            if codigo in _INDICE_TAGS_COMENTARIO:
                tag_ativa = _INDICE_TAGS_COMENTARIO[codigo]  # modo FUNDO
            marcador_span = (inicio, m_fundo.capturedLength())
        else:
            m_fonte = self._re_tag_fonte.match(texto)
            if m_fonte.hasMatch():
                codigo = m_fonte.captured(1)
                inicio = m_fonte.capturedStart()
                fmt = self._formatos_tag_fonte.get(codigo)
                if fmt is not None:
                    self.setFormat(inicio, len(texto) - inicio, fmt)
                if codigo in _INDICE_TAGS_COMENTARIO:
                    tag_ativa = _INDICE_TAGS_COMENTARIO[codigo] + _N_TAGS_COMENTARIO  # modo FONTE
                marcador_span = (inicio, m_fonte.capturedLength())
            elif tag_ativa:
                m_atalho = self._re_tag_atalho.match(texto)
                if m_atalho.hasMatch():
                    if tag_ativa <= _N_TAGS_COMENTARIO:
                        codigo_ativo = _CODIGOS_TAGS_COMENTARIO[tag_ativa - 1]
                        fmt = self._formatos_tag_fundo.get(codigo_ativo)
                    else:
                        codigo_ativo = _CODIGOS_TAGS_COMENTARIO[tag_ativa - _N_TAGS_COMENTARIO - 1]
                        fmt = self._formatos_tag_fonte.get(codigo_ativo)
                    inicio = m_atalho.capturedStart()
                    if fmt is not None:
                        self.setFormat(inicio, len(texto) - inicio, fmt)
                    # #: so repete o que estiver ativo -- nao redefine nem encerra a cadeia
                    marcador_span = (inicio, m_atalho.capturedLength())

        # Minimiza o codigo da tag (ex.: "#al:") quando a linha nao esta
        # em foco -- some pro tamanho normal na linha do cursor/selecao.
        if marcador_span is not None and not linha_em_foco:
            m_inicio, m_tamanho = marcador_span
            self.setFormat(m_inicio, m_tamanho, self._formato_tag_mini)

        # ── Color preview / swatch: pinta #RRGGBB / #RGB com a propria cor ──
        it_hex = self._re_cor_hex.globalMatch(texto)
        while it_hex.hasNext():
            m_hex = it_hex.next()
            fmt_hex = self._formato_cor_hex(m_hex.captured())
            if fmt_hex is not None:
                self.setFormat(m_hex.capturedStart(), m_hex.capturedLength(), fmt_hex)

        self.setCurrentBlockState(estado_triplice_final + tag_ativa * 10)
