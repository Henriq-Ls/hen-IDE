# _EDITOR_/Mult_Linguas/Shell/realce.py
"""
Realce de sintaxe Shell (Bash/Zsh/PowerShell/Batch) — usa chaves do tema hein.
Suporta: shebang, palavras-chave, builtins, variáveis $VAR/${VAR},
         strings "..." e '...', comentários #, números.
"""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui  import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


class RealceSintaxeShell(QSyntaxHighlighter):
    def __init__(self, documento, tema: dict = None):
        super().__init__(documento)
        self._regras: list = []
        self.aplicar_tema(tema or {})

    def aplicar_tema(self, tema: dict):
        sintaxe = tema.get("editor", {}).get("sintaxe", {})

        def cor(chave, fallback="#e0e0e0") -> QColor:
            v = sintaxe.get(chave, fallback)
            if isinstance(v, str) and len(v) == 9 and v.startswith("#"):
                v = v[:7]
            return QColor(v)

        def fmt(qcor, negrito=False, italico=False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(qcor)
            if negrito: f.setFontWeight(QFont.Bold)
            if italico: f.setFontItalic(True)
            return f

        estilo_cmt = sintaxe.get("comentario_estilo", "italic")
        italico_cmt = "italic" in estilo_cmt

        kw_bash = [
            "if","then","else","elif","fi","for","while","until","do","done",
            "case","esac","in","function","return","break","continue","select",
            "time","coproc","declare","local","typeset","readonly","export",
        ]
        kw_powershell = [
            "if","else","elseif","switch","while","for","foreach","do","until",
            "return","break","continue","function","param","begin","process","end",
            "class","enum","using","namespace","try","catch","finally","throw",
            "Write-Host","Write-Output","Write-Error","Get-","Set-","New-","Remove-",
        ]
        builtins = [
            "echo","printf","read","cd","ls","pwd","exit","source","exec",
            "eval","set","unset","shift","wait","trap","kill","true","false",
            "test","grep","awk","sed","cat","rm","cp","mv","mkdir","touch",
            "chmod","chown","find","which","type","alias","unalias","history",
        ]

        self._regras = [
            # 1. Comentários (incluindo shebang #!)
            (QRegularExpression(r'#[^\n]*'),
             fmt(cor("comentario", "#5c6370"), italico=italico_cmt), 0),

            # 2. Strings duplas
            (QRegularExpression(r'"([^"\\]|\\.)*"'),
             fmt(cor("string", "#98c379")), 0),

            # 3. Strings simples (literais em shell)
            (QRegularExpression(r"'[^']*'"),
             fmt(cor("string", "#98c379")), 0),

            # 4. Shebang especial #!/... — sobrescreve comentário (aplicado depois)
            (QRegularExpression(r'^#!.*'),
             fmt(cor("tipo", "#56b6c2"), negrito=True), 0),

            # 5. Variáveis ${VAR} e $VAR e variáveis especiais $1 $@ $# etc.
            (QRegularExpression(r'\$\{[^}]+\}|\$[0-9@#$!?*-]|\$[a-zA-Z_]\w*'),
             fmt(cor("variavel_especial", "#fd971f")), 0),

            # 6. Substituição de comando $(...)
            (QRegularExpression(r'\$\([^)]*\)'),
             fmt(cor("pontuacao_parentese", "#fd971f")), 0),

            # 7. Números
            (QRegularExpression(r'\b\d+\.?\d*\b'),
             fmt(cor("numero", "#d19a66")), 0),
        ]

        # 8. Palavras-chave bash
        for w in kw_bash:
            self._regras.append((
                QRegularExpression(rf'\b{w}\b'),
                fmt(cor("palavra_chave", "#c678dd"), negrito=True), 0
            ))

        # 9. Builtins
        for b in builtins:
            self._regras.append((
                QRegularExpression(rf'\b{b}\b'),
                fmt(cor("funcao", "#61afef")), 0
            ))

        # 10. Definição de função "nome()" ou "function nome"
        self._regras.append((
            QRegularExpression(r'\b([a-zA-Z_]\w*)\s*\(\s*\)'),
            fmt(cor("funcao", "#61afef"), negrito=True), 1
        ))
        self._regras.append((
            QRegularExpression(r'\bfunction\s+([a-zA-Z_]\w*)'),
            fmt(cor("funcao", "#61afef"), negrito=True), 1
        ))

        self.rehighlight()

    def highlightBlock(self, texto: str):
        for regra in self._regras:
            expr, fmto, grupo = regra
            it = expr.globalMatch(texto)
            while it.hasNext():
                m = it.next()
                s = m.capturedStart(grupo); n = m.capturedLength(grupo)
                if s >= 0 and n > 0:
                    self.setFormat(s, n, fmto)
        self.setCurrentBlockState(0)
