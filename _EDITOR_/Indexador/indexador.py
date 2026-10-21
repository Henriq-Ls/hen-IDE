# 📁 _EDITOR_/Indexador/indexador.py
# -*- coding: utf-8 -*-
"""
Indexador AST da IDE hein.

Varre todos os .py do projeto, extrai definições, referências e imports,
e popula o banco SQLite. Usa hash MD5 para indexar só o que mudou.
Roda em thread separada para não travar a IDE.
"""
import ast
import hashlib
import os
from PySide6.QtCore import QThread, Signal
from _THREADS_.thread_segura import _ThreadSegura
from _THREADS_.ciclo_vida import encerrar_thread
from _THREADS_.diagnostico_workers import ensure_task, event
from .banco     import Banco
from .consultas import Consultas
# Mantém referências a ThreadIndexacao até finished — evita GC prematuro
# se self._thread do Indexador for substituído antes de run() retornar (BUG-202807-12).
_threads_vivas_indexacao: set = set()

# ══════════════════════════════════════════════════════════════════════════════
# Thread de indexação
# ══════════════════════════════════════════════════════════════════════════════

class ThreadIndexacao(_ThreadSegura):
    """Roda a indexação completa em background."""

    concluido = Signal(dict)
    progresso = Signal(str)

    def __init__(self, indexador):
        super().__init__()
        self._indexador = indexador
        ensure_task(self, "INDEX")

    def run(self):
        _task = ensure_task(self, "INDEX")
        event("RUN_ENTER", "INDEX", _task, obj=self)
        try:
            resumo = self._indexador.indexar_projeto()
            self.concluido.emit(resumo)
            event("RESULT_EMITTED", "INDEX", _task, obj=self,
                  result_keys=list(resumo.keys()) if isinstance(resumo, dict) else [])
        except Exception as e:
            from _LOG_.log import log
            log.erro("indexador.py", "ThreadIndexacao.run", "excecao nao tratada na thread", str(e))
            self.concluido.emit({})
            event("ERROR", "INDEX", _task, obj=self, error=str(e))
        finally:
            event("RUN_EXIT", "INDEX", _task, obj=self)

# ══════════════════════════════════════════════════════════════════════════════
# Indexador principal
# ══════════════════════════════════════════════════════════════════════════════

class Indexador:
    """
    Ponto de entrada do indexador.

    Uso básico:
        idx = Indexador(project_path)
        idx.iniciar()                          # indexa em background
        idx.consultas.buscar_definicao("fn")   # consulta síncrona
        idx.consultas.usages_por_arquivo(path) # para o CodeLens
    """

    _IGNORAR = {
        ".venv", "__pycache__", ".git", ".hein",
        "node_modules", ".mypy_cache", ".tox", "dist", "build",
    }

    def __init__(self, projeto_path: str):
        self._projeto_path = projeto_path
        self.banco     = Banco(projeto_path)
        self.consultas = Consultas(self.banco)
        self._thread: ThreadIndexacao | None = None

    # ── API pública ───────────────────────────────────────────────────────────

    def iniciar(self, callback_concluido=None, callback_progresso=None):
        """Inicia indexação completa em background. Não bloqueia a UI."""
        if self._thread and self._thread.isRunning():

            return

        self._thread = ThreadIndexacao(self)
        if callback_concluido:
            self._thread.concluido.connect(callback_concluido)
        if callback_progresso:
            self._thread.progresso.connect(callback_progresso)
        # _threads_vivas_indexacao mantém ref até finished — evita GC prematuro
        # se iniciar() for chamado novamente antes de run() retornar.
        _threads_vivas_indexacao.add(self._thread)
        self._thread.finished.connect(
            lambda t=self._thread: _threads_vivas_indexacao.discard(t)
        )
        self._thread.start()

    def parar(self):
        encerrar_thread(self._thread, 3000)

    def fechar(self):
        encerrar_thread(self._thread, 3000)
        self.banco.fechar()

    def reindexar_arquivo(self, caminho: str):
        """Reindexar um único arquivo após salvar. Síncrono — rápido para .py."""
        if not caminho or not caminho.endswith(".py"):

            return

        if not os.path.isfile(caminho):

            return

        codigo, hash_atual = self._ler_com_hash(caminho)
        arvore = self._parsear(codigo, caminho)
        self.banco.remover_arquivo(caminho)
        self._indexar_arquivo(caminho, hash_atual, codigo, arvore)
        self._indexar_referencias(caminho, arvore)

    # ── Indexação ─────────────────────────────────────────────────────────────

    def indexar_projeto(self) -> dict:
        arquivos_disco = set(self._listar_python())
        arquivos_banco = set(self.banco.listar_arquivos_indexados())

        for arq in arquivos_banco - arquivos_disco:
            self.banco.remover_arquivo(arq)

        reindexados: dict[str, tuple[str | None, ast.AST | None]] = {}
        for arq in arquivos_disco:
            codigo, hash_atual = self._ler_com_hash(arq)
            if self.banco.arquivo_modificado(arq, hash_atual):
                self.banco.remover_arquivo(arq)
                arvore = self._parsear(codigo, arq)
                self._indexar_arquivo(arq, hash_atual, codigo, arvore)
                reindexados[arq] = (codigo, arvore)

        for arq, (_codigo, arvore) in reindexados.items():
            # A árvore AST é mantida para evitar uma segunda leitura e um
            # segundo ast.parse(); arquivos com erro de sintaxe não têm refs.
            self._indexar_referencias(arq, arvore)

        return self.consultas.resumo()

    def _indexar_arquivo(self, arquivo: str, hash_atual: str,
                         codigo: str | None, arvore: ast.AST | None):
        """Extrai definições e imports em batch — um commit por arquivo."""
        if codigo is None:

            return

        if arvore is None:
            self.banco.registrar_arquivo(arquivo, hash_atual, os.path.getmtime(arquivo))

            return

        escopos = self._mapear_escopos(arvore)

        simbolos = []
        for no in ast.walk(arvore):
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                simbolos.append((
                    no.name, "function", arquivo,
                    no.lineno, no.col_offset, escopos.get(id(no), ""),
                ))
            elif isinstance(no, ast.ClassDef):
                simbolos.append((
                    no.name, "class", arquivo,
                    no.lineno, no.col_offset, escopos.get(id(no), ""),
                ))

        imports = []
        for no in ast.walk(arvore):
            if isinstance(no, ast.ImportFrom):
                modulo = no.module or ""
                for alias in no.names:
                    imports.append((alias.asname or alias.name, arquivo, no.lineno))
                if modulo:
                    imports.append((modulo, arquivo, no.lineno))
            elif isinstance(no, ast.Import):
                for alias in no.names:
                    imports.append((alias.asname or alias.name.split(".")[0], arquivo, no.lineno))

        self.banco.inserir_simbolos_batch(simbolos)
        self.banco.inserir_imports_batch(imports)
        self.banco.registrar_arquivo(arquivo, hash_atual, os.path.getmtime(arquivo))

    # ⚠️  função grande (64 linhas)
    def _indexar_referencias(self, arquivo: str, arvore: ast.AST | None):
        """
        Extrai referências e salva em batch.
        Passagem 1: ast.Call  → tipo='call'  (chamadas reais)
        Passagem 2: ast.Name/Import → tipo='name' (usos gerais)
        """
        if arvore is None:
            return

        ja_registrados: set[tuple[str, int, int]] = set()
        pendentes: list[tuple[str, int, int, str]] = []  # (nome, linha, coluna, tipo)

        # Passagem 1: chamadas reais → tipo='call'
        for no in ast.walk(arvore):
            if isinstance(no, ast.Call):
                nome = self._nome_da_chamada(no.func)
                col  = getattr(no.func, "col_offset", 0)
                lin  = getattr(no.func, "lineno", no.lineno)
                if nome:
                    chave = (nome, lin, col)
                    if chave not in ja_registrados:
                        pendentes.append((nome, lin, col, "call"))
                        ja_registrados.add(chave)

        # Passagem 2: nomes e imports → tipo='name'
        for no in ast.walk(arvore):
            if isinstance(no, ast.Name):
                chave = (no.id, no.lineno, no.col_offset)
                if chave not in ja_registrados:
                    pendentes.append((no.id, no.lineno, no.col_offset, "name"))
                    ja_registrados.add(chave)

            elif isinstance(no, ast.ImportFrom):
                for alias in no.names:
                    nome = alias.asname or alias.name
                    chave = (nome, no.lineno, 0)
                    if chave not in ja_registrados:
                        pendentes.append((nome, no.lineno, 0, "name"))
                        ja_registrados.add(chave)

            elif isinstance(no, ast.Import):
                for alias in no.names:
                    nome = alias.asname or alias.name.split(".")[0]
                    chave = (nome, no.lineno, 0)
                    if chave not in ja_registrados:
                        pendentes.append((nome, no.lineno, 0, "name"))
                        ja_registrados.add(chave)

        # Resolve symbol_ids e monta batch com tipo
        referencias = []
        for nome, linha, coluna, tipo in pendentes:
            sym_id = self._resolver_symbol_id(nome, arquivo)
            if sym_id is not None:
                referencias.append((sym_id, arquivo, linha, coluna, tipo))

        self.banco.inserir_referencias_batch(referencias)

    def _resolver_symbol_id(self, nome: str, arquivo: str) -> int | None:
        conn = self.banco._conn

        row = conn.execute(
            "SELECT id FROM symbols WHERE nome = ? AND arquivo = ? LIMIT 1",
            (nome, arquivo),
        ).fetchone()
        if row:

            return row["id"]

        row = conn.execute(
            """
            SELECT s.id FROM symbols s
            JOIN imports i ON i.modulo = s.nome
            WHERE s.nome = ? AND i.arquivo = ?
            LIMIT 1
            """,
            (nome, arquivo),
        ).fetchone()
        if row:

            return row["id"]

        # Prefere símbolo na mesma pasta — evita LIMIT 1 sem ordem quando
        # múltiplos arquivos definem funções com o mesmo nome
        pasta = os.path.dirname(arquivo)
        rows = conn.execute(
            "SELECT id, arquivo FROM symbols WHERE nome = ?", (nome,)
        ).fetchall()
        if not rows:

            return None

        for row in rows:
            if os.path.dirname(row["arquivo"]) == pasta:

                return row["id"]

        return rows[0]["id"]

    # ── Utilitários ───────────────────────────────────────────────────────────

    @staticmethod
    def _mapear_escopos(arvore: ast.AST) -> dict[int, str]:
        escopos: dict[int, str] = {}

        def visitar(no, classe_atual: str):
            if isinstance(no, ast.ClassDef):
                escopos[id(no)] = classe_atual
                for filho in ast.iter_child_nodes(no):
                    visitar(filho, no.name)
            elif isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                escopos[id(no)] = classe_atual
                for filho in ast.iter_child_nodes(no):
                    visitar(filho, "")
            else:
                for filho in ast.iter_child_nodes(no):
                    visitar(filho, classe_atual)

        for filho in ast.iter_child_nodes(arvore):
            visitar(filho, "")

        return escopos

    def _listar_python(self) -> list[str]:
        resultado = []
        for raiz, pastas, arquivos in os.walk(self._projeto_path):
            pastas[:] = [p for p in pastas if p not in self._IGNORAR]
            for nome in arquivos:
                if nome.endswith(".py"):
                    resultado.append(os.path.join(raiz, nome))

        return resultado

    @staticmethod
    def _ler_com_hash(arquivo: str) -> tuple[str | None, str]:
        """Lê uma vez: preserva o hash dos bytes e fornece texto para o AST."""
        try:
            with open(arquivo, "rb") as f:
                dados = f.read()

            return dados.decode("utf-8", errors="ignore"), hashlib.md5(dados).hexdigest()

        except Exception:
            return None, ""

    @staticmethod
    def _parsear(codigo: str | None, arquivo: str) -> ast.AST | None:
        """Parseia o conteúdo já lido e preserva o fallback de SyntaxError."""
        if codigo is None:
            return None

        try:
            return ast.parse(codigo, filename=arquivo)
        except SyntaxError:
            return None

    @staticmethod
    def _nome_da_chamada(no) -> str | None:
        if isinstance(no, ast.Name):

            return no.id

        if isinstance(no, ast.Attribute):

            return no.attr

        return None
