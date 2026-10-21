# 📁 _EDITOR_/Funcionalidades/realce_sintaxe_json.py
"""
Realce de sintaxe JSONC — JSON with Comments.
Suporta:
  - "chave": valor          → chave em laranja/negrito, valor colorido por tipo
  - // comentário de linha  → cinza itálico (cor "comentario" do tema)
  - // após valor           → "chave": "valor"  // comentário inline
  - Strings, números, booleanos, null, pontuação
"""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui  import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

class RealceSintaxeJSON(QSyntaxHighlighter):
    def __init__(self, documento, tema: dict = None):
        super().__init__(documento)
        self._regras: list = []
        self._fmt_comentario: QTextCharFormat | None = None
        self.aplicar_tema(tema or {})

    # ------------------------------------------------------------------
    # Construção de regras
    # ------------------------------------------------------------------

    # ⚠️  função grande (66 linhas)
    def aplicar_tema(self, tema: dict):
        sintaxe = tema.get("editor", {}).get("sintaxe", {})

        # 💡 fallback_opc = Literal["#e0e0e0"] ← defina os valores válidos
        def cor(chave, fallback="#e0e0e0") -> QColor:
            valor = sintaxe.get(chave, fallback)
            if isinstance(valor, str) and len(valor) == 9 and valor.startswith("#"):
                valor = valor[:7]

            return QColor(valor)

        def fmt(qcor, negrito=False, italico=False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(qcor)
            if negrito:
                f.setFontWeight(QFont.Bold)
            if italico:
                f.setFontItalic(True)

            return f

        self._regras = []

        # 1. Strings genéricas (valores) — aplicadas primeiro
        self._regras.append((
            QRegularExpression(r'"([^"\\]*(\\.[^"\\]*)*)"'),
            fmt(cor("string", "#98c379")), 0
        ))

        # 2. Chaves JSON (string antes de :) — sobrescreve regra 1
        self._regras.append((
            QRegularExpression(r'"([^"\\]*(\\.[^"\\]*)*)"(?=\s*:)'),
            fmt(cor("chave_json", "#CE9178"), negrito=True), 0
        ))

        # 3. Números (apenas valores, após :)
        self._regras.append((
            QRegularExpression(r'(?<=:)\s*(-?\d+\.?\d*(?:[eE][+-]?\d+)?)'),
            fmt(cor("numero", "#d19a66")), 1
        ))

        # 4. Booleanos e null
        self._regras.append((
            QRegularExpression(r'\b(true|false|null)\b'),
            fmt(cor("palavra_chave", "#e5c07b")), 0
        ))

        # 5. Chaves e colchetes
        self._regras.append((
            QRegularExpression(r'[{}\[\]]'),
            fmt(cor("pontuacao_chave", "#abb2bf")), 0
        ))

        # 6. Vírgula e dois-pontos
        self._regras.append((
            QRegularExpression(r'[,:]'),
            fmt(cor("pontuacao", "#5c6370")), 0
        ))

        # Formato de comentário — salvo separado pois aplicado manualmente
        estilo = sintaxe.get("comentario_estilo", "italic")
        self._fmt_comentario = fmt(
            cor("comentario", "#5c6370"),
            italico=("italic" in estilo)
        )

        self.rehighlight()

    # ------------------------------------------------------------------
    # Highlight por bloco
    # ------------------------------------------------------------------

    def highlightBlock(self, texto: str): # ── 1. Regras de regex (strings, números, etc.) ──────────────
        for regra in self._regras:
            expressao, fmto, grupo = regra
            it = expressao.globalMatch(texto)
            while it.hasNext():
                match = it.next()
                inicio  = match.capturedStart(grupo)
                tamanho = match.capturedLength(grupo)
                if inicio >= 0 and tamanho > 0:
                    self.setFormat(inicio, tamanho, fmto)

        # ── 2. Comentário // (detecta posição fora de string) ────────
        pos_comentario = self._pos_comentario(texto)
        if pos_comentario >= 0 and self._fmt_comentario:
            tamanho = len(texto) - pos_comentario
            self.setFormat(pos_comentario, tamanho, self._fmt_comentario)

    # ------------------------------------------------------------------
    # Utilitário: encontra // fora de string
    # ------------------------------------------------------------------

    @staticmethod
    def _pos_comentario(linha: str) -> int:
        """
        Retorna o índice do primeiro // que não está dentro de uma string JSON.
        Retorna -1 se não houver comentário na linha.
        """
        dentro_string = False
        escapado      = False
        i = 0
        while i < len(linha):
            c = linha[i]
            if escapado:
                escapado = False
                i += 1
                continue
            if c == '\\' and dentro_string:
                escapado = True
                i += 1
                continue
            if c == '"':
                dentro_string = not dentro_string
                i += 1
                continue
            if not dentro_string and c == '/' and i + 1 < len(linha) and linha[i + 1] == '/':

                return i

            i += 1

        return -1
