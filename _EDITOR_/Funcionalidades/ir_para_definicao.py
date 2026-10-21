# 📁 _EDITOR_/Funcionalidades/ir_para_definicao.py
# -*- coding: utf-8 -*-
"""
Ir para definição — Ctrl+Click ou F12.

Prioridade de busca:
    1. Banco SQLite do Indexador  (projeto inteiro)
    2. Módulo do projeto → resolve nome para arquivo .py
    3. Import-following  → from X import nome → abre X.py na def
    4. Fallback AST: defs/classes/variáveis locais reais (não imports)
    5. Fallback regex

Palavras reservadas e built-ins do Python são ignorados.
"""
import ast
import builtins
import os
import re
from PySide6.QtCore    import Qt, QTimer, QObject, QEvent
from PySide6.QtGui     import QTextCursor, QTextCharFormat, QColor
from PySide6.QtWidgets import QTextEdit
from _LOG_.log   import log
_PALAVRAS_RESERVADAS = frozenset({
    "False", "None", "True", "and", "as", "assert", "async", "await",
    "break", "class", "continue", "def", "del", "elif", "else", "except",
    "finally", "for", "from", "global", "if", "import", "in", "is",
    "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
    "while", "with", "yield",
})
_BUILTINS = frozenset(dir(builtins))
_IGNORAR  = {".venv", "__pycache__", ".git", ".hein", "node_modules"}
_ARQ      = "ir_para_definicao.py"

def _norm(caminho: str) -> str:
    """Normaliza caminho para comparação segura no Windows (\\ vs /)."""

    return os.path.normcase(os.path.normpath(caminho)) if caminho else ""

class IrParaDefinicao(QObject):
    """
    Gerencia navegação para definições.
    Instanciado dentro do CodeEditor.

    Atalhos:
        F12        → ir para definição da palavra sob o cursor
        Ctrl+Click → mesma coisa com o mouse (com destaque visual ao segurar Ctrl)
        Alt+←      → voltar para posição anterior
    """

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor
        self._historico: list[tuple[str, int]] = []
        self._palavra_destacada: str | None    = None
        self._cursor_hover: QTextCursor | None = None
        self._editor.installEventFilter(self)
        log.info(_ARQ, "__init__", "IrParaDefinicao inicializado")

    # ── Filtro de eventos ─────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self._editor:
            if event.type() == QEvent.KeyRelease:
                if event.key() == Qt.Key_Control:
                    self._limpar_destaque_hover()

        return False

    # ══════════════════════════════════════════════════════════════════════════
    # API pública
    # ══════════════════════════════════════════════════════════════════════════

    def ir_para_definicao(self):
        """F12 — vai para a definição da palavra sob o cursor."""
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)

        palavra = cursor.selectedText().strip()
        if not palavra or self._e_ignoravel(palavra):
            if palavra in _PALAVRAS_RESERVADAS:
                self._status(f"'{palavra}' é palavra-chave Python — sem definição navigável")
            else:
                log.info(_ARQ, "ir_para_definicao", f"ignorado: '{palavra}'")

            return

        log.info(_ARQ, "ir_para_definicao", f"navegando para '{palavra}'")
        self._navegar(palavra)

    def voltar(self):
        """Alt+← — volta para a posição anterior."""
        if not self._historico:
            log.info(_ARQ, "voltar", "histórico vazio")

            return

        arquivo_anterior, pos = self._historico.pop()
        arquivo_atual = getattr(self._editor, "file_path", None) or ""

        if arquivo_anterior and _norm(arquivo_anterior) != _norm(arquivo_atual):
            self._abrir_em_outro_arquivo(arquivo_anterior, None, pos=pos)
        else:
            cursor = self._editor.textCursor()
            cursor.setPosition(pos)
            self._editor.setTextCursor(cursor)
            self._editor.ensureCursorVisible()

    def ao_click_mouse(self, event):
        """Chame no mousePressEvent do editor. Ctrl+Click → ir para definição."""
        if event.modifiers() == Qt.ControlModifier and event.button() == Qt.LeftButton:
            cursor = self._editor.cursorForPosition(event.pos())
            self._editor.setTextCursor(cursor)
            self._limpar_destaque_hover()
            self.ir_para_definicao()

            return True

        return False

    def ao_mover_mouse(self, event):
        """
        Chame no mouseMoveEvent do editor.
        Ctrl pressionado → sublinha palavra navegável e muda cursor para mãozinha.
        """
        if event.modifiers() == Qt.ControlModifier:
            cursor  = self._editor.cursorForPosition(event.pos())
            palavra = self._palavra_sob_cursor(cursor)

            if palavra and not self._e_ignoravel(palavra) and self._e_navegavel(palavra):
                if palavra != self._palavra_destacada:
                    self._aplicar_destaque_hover(cursor, palavra)
                self._editor.viewport().setCursor(Qt.PointingHandCursor)
            else:
                self._limpar_destaque_hover()
                self._editor.viewport().setCursor(Qt.IBeamCursor)
                if palavra and palavra in _BUILTINS:
                    self._status(f"'{palavra}' é um built-in do Python — sem definição navegável")
        else:
            self._limpar_destaque_hover()
            self._editor.viewport().setCursor(Qt.IBeamCursor)

    # ══════════════════════════════════════════════════════════════════════════
    # Navegação principal
    # ══════════════════════════════════════════════════════════════════════════

    # ⚠️  função grande (85 linhas)
    def _navegar(self, palavra: str):
        """Tenta navegar para a definição. Mostra resultado na status bar."""
        arquivo_atual = getattr(self._editor, "file_path", None) or ""

        # 0. Linha de import — navega para o módulo completo da linha
        try:
            modulo_import = self._modulo_da_linha_import()
        except Exception:
            modulo_import = None
        if modulo_import:
            arq_imp = self._resolver_stdlib(modulo_import)
            if not arq_imp:
                arq_imp = self._resolver_modulo(modulo_import.split(".")[-1])
            if arq_imp:
                log.ok(_ARQ, "_navegar", f"import→arquivo → {os.path.basename(arq_imp)}", modulo_import)
                self._historico.append((arquivo_atual, self._editor.textCursor().position()))
                self._abrir_em_outro_arquivo(arq_imp, 1)
                self._status(f"Módulo: {modulo_import} → {self._nome_curto(arq_imp)}")

                return

        # 1. Banco SQLite (símbolos do projeto inteiro)
        resultado = self._buscar_no_banco(palavra)
        if resultado:
            arquivo, linha = resultado
            log.ok(_ARQ, "_navegar", f"banco → {os.path.basename(arquivo)}:{linha}", palavra)
            self._historico.append((arquivo_atual, self._editor.textCursor().position()))
            if not arquivo or _norm(arquivo) == _norm(arquivo_atual):
                self._editor.ir_para_linha(linha)
                self._destacar_linha(linha)
                self._status(f"Definição: {palavra} → linha {linha}")
            else:
                self._abrir_em_outro_arquivo(arquivo, linha)
                self._status(f"Definição: {palavra} → {self._nome_curto(arquivo)}:{linha}")

            return

        # 2. Módulo do projeto → <palavra>.py
        arquivo_modulo = self._resolver_modulo(palavra)
        if arquivo_modulo:
            log.ok(_ARQ, "_navegar", f"módulo → {os.path.basename(arquivo_modulo)}", palavra)
            self._historico.append((arquivo_atual, self._editor.textCursor().position()))
            self._abrir_em_outro_arquivo(arquivo_modulo, 1)
            self._status(f"Módulo: {palavra} → {self._nome_curto(arquivo_modulo)}")

            return

        # 2.5. Módulo da stdlib ou pacote instalado
        arq_stdlib = self._resolver_stdlib(palavra)
        if arq_stdlib:
            log.ok(_ARQ, "_navegar", f"stdlib → {os.path.basename(arq_stdlib)}", palavra)
            self._historico.append((arquivo_atual, self._editor.textCursor().position()))
            self._abrir_em_outro_arquivo(arq_stdlib, 1)
            self._status(f"Módulo: {palavra} → {self._nome_curto(arq_stdlib)}")

            return

        # 3. Import-following: from X import palavra → abre X.py na def
        resultado_import = self._resolver_importado_de(palavra, arquivo_atual)
        if resultado_import:
            arq_origem, linha_def = resultado_import
            log.ok(_ARQ, "_navegar", f"import-follow → {os.path.basename(arq_origem)}:{linha_def}", palavra)
            self._historico.append((arquivo_atual, self._editor.textCursor().position()))
            self._abrir_em_outro_arquivo(arq_origem, linha_def)
            self._status(f"Importado de: {palavra} → {self._nome_curto(arq_origem)}:{linha_def}")

            return

        # 4. Fallback: defs/classes/variáveis LOCAIS reais (não imports)
        linha = self._encontrar_def_local(palavra)
        if linha is not None:
            log.ok(_ARQ, "_navegar", f"def local → linha {linha}", palavra)
            self._historico.append((arquivo_atual, self._editor.textCursor().position()))
            self._editor.ir_para_linha(linha)
            self._destacar_linha(linha)
            self._status(f"Definição local: {palavra} → linha {linha}")

            return

        # 5. Não encontrou
        if palavra in _BUILTINS:
            self._status(f"'{palavra}' é um built-in do Python — sem definição navegável")
        else:
            log.aviso(_ARQ, "_navegar", f"não encontrado: '{palavra}'")
            self._status(f"'{palavra}' — definição não encontrada no projeto", erro=True)

    # ══════════════════════════════════════════════════════════════════════════
    # Import-following
    # ══════════════════════════════════════════════════════════════════════════

    # ⚠️  função grande (84 linhas)
    def _resolver_importado_de(self, palavra: str, arquivo_atual: str) -> tuple[str, int] | None:
        """
        Verifica se `palavra` vem de um 'from X import palavra' no arquivo atual.
        Se sim, resolve X para arquivo .py e encontra 'def palavra' nele.
        Retorna (caminho_arquivo, linha_def) ou None.
        """
        codigo = self._editor.toPlainText()
        try:
            arvore = ast.parse(codigo)
        except SyntaxError:

            return None

        modulo_origem = None
        for no in ast.walk(arvore):
            if isinstance(no, ast.ImportFrom) and no.module:
                for alias in no.names:
                    nome_importado = alias.asname or alias.name
                    if nome_importado == palavra:
                        modulo_origem = no.module
                        break
            if modulo_origem:
                break

        if not modulo_origem:

            return None

        log.info(_ARQ, "_resolver_importado_de",
                 f"'{palavra}' importado de módulo '{modulo_origem}'")

        # Resolve o módulo para um arquivo .py
        janela  = self._editor.window()
        projeto = getattr(janela, "current_project_path", None)
        if not projeto:

            return None

        # Tenta <modulo>.py e sub/modulo.py
        partes = modulo_origem.replace(".", os.sep)
        candidatos = [
            os.path.join(projeto, partes + ".py"),
            os.path.join(os.path.dirname(arquivo_atual), partes + ".py"),
        ]
        arq_origem = None
        for c in candidatos:
            if os.path.isfile(c):
                arq_origem = c
                break

        if not arq_origem:
            # Busca recursiva
            nome_arq = modulo_origem.split(".")[-1] + ".py"
            for raiz, pastas, arquivos in os.walk(projeto):
                pastas[:] = [p for p in pastas if p not in _IGNORAR]
                if nome_arq in arquivos:
                    arq_origem = os.path.join(raiz, nome_arq)
                    break

        if not arq_origem:
            # Fallback: stdlib ou pacote instalado
            import importlib.util
            try:
                _spec = importlib.util.find_spec(modulo_origem)
                if _spec and _spec.origin and _spec.origin.endswith(".py"):
                    arq_origem = _spec.origin
            except (ModuleNotFoundError, ValueError, AttributeError):
                pass

        if not arq_origem:
            log.aviso(_ARQ, "_resolver_importado_de",
                      f"arquivo do módulo '{modulo_origem}' não encontrado")

            return None

        # Encontra a linha da def no arquivo de origem
        linha_def = self._encontrar_def_em_arquivo(arq_origem, palavra)
        if linha_def is None:
            linha_def = 1

        log.ok(_ARQ, "_resolver_importado_de",
               f"resolvido: {os.path.basename(arq_origem)}:{linha_def}")

        return arq_origem, linha_def

    def _encontrar_def_em_arquivo(self, caminho: str, nome: str) -> int | None:
        """Encontra a linha de definição de `nome` em outro arquivo."""
        try:
            with open(caminho, encoding="utf-8", errors="replace") as f:
                codigo = f.read()
        except OSError:

            return None

        try:
            arvore = ast.parse(codigo)
            for no in ast.walk(arvore):
                if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if no.name == nome:

                        return no.lineno

                elif isinstance(no, ast.ClassDef):
                    if no.name == nome:

                        return no.lineno

                elif isinstance(no, ast.Assign):
                    for alvo in no.targets:
                        if isinstance(alvo, ast.Name) and alvo.id == nome:

                            return no.lineno

                elif isinstance(no, ast.AnnAssign):
                    if isinstance(no.target, ast.Name) and no.target.id == nome:

                        return no.lineno

        except SyntaxError:
            pass

        # Fallback regex
        padroes = [
            rf"^\s*def\s+{re.escape(nome)}\s*\(",
            rf"^\s*async\s+def\s+{re.escape(nome)}\s*\(",
            rf"^\s*class\s+{re.escape(nome)}\s*[:(]",
            rf"^\s*{re.escape(nome)}\s*=",
        ]
        for i, linha in enumerate(codigo.splitlines(), 1):
            for padrao in padroes:
                if re.match(padrao, linha):

                    return i

        return None

    # ══════════════════════════════════════════════════════════════════════════
    # Busca no banco
    # ══════════════════════════════════════════════════════════════════════════

    def _buscar_no_banco(self, palavra: str) -> tuple[str, int] | None:
        indexador = self._pegar_indexador()
        if not indexador:

            return None

        resultados = indexador.consultas.buscar_definicao(palavra)
        if not resultados:

            return None

        if len(resultados) == 1:

            return resultados[0]["arquivo"], resultados[0]["linha"]

        arquivo_atual = getattr(self._editor, "file_path", None) or ""
        for r in resultados:
            if _norm(r["arquivo"]) == _norm(arquivo_atual):

                return r["arquivo"], r["linha"]

        return resultados[0]["arquivo"], resultados[0]["linha"]

    # ⚠️  except genérico vazio
    def _e_navegavel(self, palavra: str) -> bool:
        """True se a palavra tem definição navegável."""
        indexador = self._pegar_indexador()
        if indexador and indexador.consultas.buscar_definicao(palavra):

            return True

        if self._resolver_modulo(palavra):

            return True

        if self._resolver_stdlib(palavra):

            return True

        # Linha de import? Check leve (sem acesso ao cursor)
        try:
            _ln = self._editor.textCursor().block().text().strip()
            if re.match(r'^(import|from)\s+', _ln) and palavra not in ('import', 'from', 'as'):

                return True

        except Exception:
            pass

        # Verifica import-following
        arquivo_atual = getattr(self._editor, "file_path", None) or ""
        if self._resolver_importado_de(palavra, arquivo_atual):

            return True

        # Def local real (não import)
        if self._encontrar_def_local(palavra) is not None:

            return True

        return False

    def _pegar_indexador(self):
        return getattr(self._editor.window(), "_indexador", None)

    # ══════════════════════════════════════════════════════════════════════════
    # Módulo do projeto
    # ══════════════════════════════════════════════════════════════════════════

    def _resolver_modulo(self, nome: str) -> str | None:
        """Procura <nome>.py no projeto."""
        janela  = self._editor.window()
        projeto = getattr(janela, "current_project_path", None)
        if not projeto:

            return None

        for raiz, pastas, arquivos in os.walk(projeto):
            pastas[:] = [p for p in pastas if p not in _IGNORAR]
            for arq in arquivos:
                if arq == f"{nome}.py":

                    return os.path.join(raiz, arq)

        return None

    # ══════════════════════════════════════════════════════════════════════════
    # Fallback: defs LOCAIS REAIS (ignora import lines)
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    # ⚠️  except genérico vazio
    def _resolver_stdlib(nome: str) -> str | None:
        """Localiza o .py de um módulo da stdlib ou pacote instalado."""
        if not nome or not nome.replace('.', '').isidentifier():

            return None

        import importlib.util
        try:
            spec = importlib.util.find_spec(nome)
            if spec and spec.origin and spec.origin.endswith(".py"):

                return spec.origin

        except Exception:
            pass

        return None

    # ⚠️  except genérico vazio
    def _modulo_da_linha_import(self) -> str | None:
        """
        Retorna o módulo completo quando o cursor está numa linha de import
        E a palavra sob o cursor faz parte do caminho do módulo.

        'import os.path'              -> 'os.path'  (qualquer click)
        'from os.path import join'    -> 'os.path'  (click em 'os' ou 'path')
                                      -> None       (click em 'join')
        """
        try:
            cursor    = self._editor.textCursor()
            linha_txt = cursor.block().text().strip()
            palavra   = self._palavra_sob_cursor(cursor)

            m = re.match(r'^import\s+([\w.]+)', linha_txt)
            if m:

                return m.group(1)

            m = re.match(r'^from\s+([\w.]+)\s+import\s+(.*)', linha_txt)
            if m:
                modulo = m.group(1)
                nomes  = [n.strip().split(' as ')[0].strip() for n in m.group(2).split(',')]
                if palavra not in nomes:

                    return modulo

        except Exception:
            pass

        return None

    def _encontrar_def_local(self, palavra: str) -> int | None:
        """
        Retorna a linha de uma definição REAL (def/class/variável) no arquivo atual.
        NÃO retorna linhas de import — essas são tratadas pelo import-following.
        """
        codigo = self._editor.toPlainText()
        try:
            arvore = ast.parse(codigo)
            for no in ast.walk(arvore):
                if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if no.name == palavra:

                        return no.lineno

                elif isinstance(no, ast.ClassDef):
                    if no.name == palavra:

                        return no.lineno

                elif isinstance(no, ast.Assign):
                    for alvo in no.targets:
                        if isinstance(alvo, ast.Name) and alvo.id == palavra:

                            return no.lineno

                elif isinstance(no, ast.AnnAssign):
                    if isinstance(no.target, ast.Name) and no.target.id == palavra:

                        return no.lineno

                # ImportFrom e Import intencionalmente OMITIDOS aqui
        except SyntaxError:
            pass

        # Fallback regex — só defs e classes reais
        padroes = [
            rf"^\s*def\s+{re.escape(palavra)}\s*\(",
            rf"^\s*async\s+def\s+{re.escape(palavra)}\s*\(",
            rf"^\s*class\s+{re.escape(palavra)}\s*[:(]",
            rf"^\s*{re.escape(palavra)}\s*=",
        ]
        for i, linha in enumerate(codigo.splitlines(), 1):
            for padrao in padroes:
                if re.match(padrao, linha):

                    return i

        return None

    # ══════════════════════════════════════════════════════════════════════════
    # Abrir em outro arquivo — sem duplicar aba
    # ══════════════════════════════════════════════════════════════════════════

    def _abrir_em_outro_arquivo(self, arquivo: str, linha: int | None, pos: int | None = None):
        janela = self._editor.window()
        if not hasattr(janela, "tabs"):
            log.aviso(_ARQ, "_abrir_em_outro_arquivo", "janela sem atributo 'tabs'")

            return

        # Foca a aba existente se o arquivo já estiver aberto (normaliza para comparar)
        for indice, editor in janela.tabs.editores.items():
            caminho_aba = getattr(editor, "file_path", None)
            if caminho_aba and _norm(caminho_aba) == _norm(arquivo):
                log.info(_ARQ, "_abrir_em_outro_arquivo",
                         f"reutilizando aba existente: {os.path.basename(arquivo)}")
                janela.tabs.setCurrentIndex(indice)
                if linha is not None:
                    editor.ir_para_linha(linha)
                    self._destacar_linha_em(editor, linha)
                elif pos is not None:
                    cursor = editor.textCursor()
                    cursor.setPosition(pos)
                    editor.setTextCursor(cursor)
                    editor.ensureCursorVisible()

                return

        # Só abre nova aba se o arquivo ainda não está aberto
        log.info(_ARQ, "_abrir_em_outro_arquivo",
                 f"abrindo nova aba: {os.path.basename(arquivo)}")
        novo_editor = janela.tabs.add_new_tab(arquivo)
        if novo_editor and linha is not None:
            novo_editor.ir_para_linha(linha)
            self._destacar_linha_em(novo_editor, linha)

    # ══════════════════════════════════════════════════════════════════════════
    # Destaque visual do hover
    # ══════════════════════════════════════════════════════════════════════════

    def _aplicar_destaque_hover(self, cursor: QTextCursor, palavra: str):
        self._limpar_destaque_hover()

        cor = self._cor_tema("ctrl_click_hover_texto", "#4a90d9")
        c   = QTextCursor(cursor)
        c.select(QTextCursor.WordUnderCursor)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(cor))
        fmt.setFontUnderline(True)
        fmt.setUnderlineStyle(QTextCharFormat.SingleUnderline)
        fmt.setUnderlineColor(QColor(cor))
        c.mergeCharFormat(fmt)

        self._cursor_hover      = c
        self._palavra_destacada = palavra

    def _limpar_destaque_hover(self):
        if not self._palavra_destacada:

            return

        if self._cursor_hover:
            fmt = QTextCharFormat()
            fmt.setFontUnderline(False)
            fmt.setUnderlineStyle(QTextCharFormat.NoUnderline)
            fmt.setForeground(QColor(self._cor_tema("texto", "#e0e0e0")))
            self._cursor_hover.mergeCharFormat(fmt)
            self._cursor_hover = None

        self._palavra_destacada = None
        self._editor.viewport().setCursor(Qt.IBeamCursor)

    # ══════════════════════════════════════════════════════════════════════════
    # Destaque de linha ao chegar na definição
    # ══════════════════════════════════════════════════════════════════════════

    def _destacar_linha(self, numero_linha: int):
        self._destacar_linha_em(self._editor, numero_linha)

    @staticmethod
    def _destacar_linha_em(editor, numero_linha: int):
        bloco = editor.document().findBlockByNumber(numero_linha - 1)
        if not bloco.isValid():

            return

        cor = "#e09a4433"
        try:
            cor = editor.window()._tema.dados()["editor"]["ctrl_click_destino_fundo"]
        except (AttributeError, KeyError, TypeError):
            pass

        fmt = QTextCharFormat()
        fmt.setBackground(QColor(cor))
        fmt.setProperty(QTextCharFormat.FullWidthSelection, True)

        sel        = QTextEdit.ExtraSelection()
        sel.cursor = QTextCursor(bloco)
        sel.format = fmt

        editor.setExtraSelections(editor.extraSelections() + [sel])
        QTimer.singleShot(1500, lambda: editor.setExtraSelections(
            [s for s in editor.extraSelections() if s is not sel]
        ))

    # ══════════════════════════════════════════════════════════════════════════
    # Status bar
    # ══════════════════════════════════════════════════════════════════════════

    def _status(self, mensagem: str, erro: bool = False, duracao: int = 5000):
        janela = self._editor.window()
        if not hasattr(janela, "statusBar"):

            return

        if not mensagem:
            janela.statusBar().clearMessage()

            return

        janela.statusBar().showMessage(mensagem, duracao)

    # ══════════════════════════════════════════════════════════════════════════
    # Utilitários
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _e_ignoravel(palavra: str) -> bool:
        return palavra in _PALAVRAS_RESERVADAS

    @staticmethod
    def _palavra_sob_cursor(cursor: QTextCursor) -> str:
        c = QTextCursor(cursor)
        c.select(QTextCursor.WordUnderCursor)

        return c.selectedText().strip()

    @staticmethod
    def _nome_curto(caminho: str) -> str:
        return os.path.basename(caminho)

    def _cor_tema(self, chave: str, fallback: str) -> str:
        try:
            valor = self._editor.window()._tema.dados()["editor"][chave]
            if len(valor) == 9 and valor.startswith("#"):
                valor = valor[:7]

            return valor

        except (AttributeError, KeyError, TypeError):

            return fallback
