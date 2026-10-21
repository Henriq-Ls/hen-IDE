# 📁 _EDITOR_/Indexador/banco.py
# -*- coding: utf-8 -*-
"""
Gerencia o banco SQLite do indexador da IDE hein.

Tabelas:
    files      — arquivos conhecidos + hash para cache incremental
    symbols    — definições (def/class) com coluna e escopo
    usages     — onde cada símbolo é referenciado
    imports    — imports encontrados nos arquivos
"""
import sqlite3
import os
import threading

class Banco:
    def __init__(self, projeto_path: str):
        pasta = os.path.join(projeto_path, ".hein")
        os.makedirs(pasta, exist_ok=True)
        self._db_path = os.path.join(pasta, "index.db")
        # Cada thread terá sua própria conexão via threading.local()
        self._local = threading.local()
        # Inicializa a conexão na thread principal e cria as tabelas
        self._criar_tabelas()
        self._migrar()

    # ── Conexão por thread ────────────────────────────────────────────────────

    @property
    def _conn(self) -> sqlite3.Connection:
        """Retorna (ou cria) a conexão SQLite da thread atual."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn

        return self._local.conn

    # ── Criação ───────────────────────────────────────────────────────────────

    def _criar_tabelas(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                arquivo       TEXT PRIMARY KEY,
                hash          TEXT NOT NULL,
                modificado_em REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS symbols (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                nome    TEXT    NOT NULL,
                tipo    TEXT    NOT NULL,
                arquivo TEXT    NOT NULL,
                linha   INTEGER NOT NULL,
                coluna  INTEGER NOT NULL DEFAULT 0,
                escopo  TEXT    NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS usages (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol_id INTEGER NOT NULL,
                arquivo   TEXT    NOT NULL,
                linha     INTEGER NOT NULL,
                coluna    INTEGER NOT NULL DEFAULT 0,
                tipo      TEXT    NOT NULL DEFAULT 'name',
                FOREIGN KEY(symbol_id) REFERENCES symbols(id)
            );

            CREATE TABLE IF NOT EXISTS imports (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                modulo  TEXT    NOT NULL,
                arquivo TEXT    NOT NULL,
                linha   INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_symbols_nome    ON symbols(nome);
            CREATE INDEX IF NOT EXISTS idx_symbols_arquivo ON symbols(arquivo);
            CREATE INDEX IF NOT EXISTS idx_refs_symbol     ON usages(symbol_id);
            CREATE INDEX IF NOT EXISTS idx_refs_arquivo    ON usages(arquivo);
            CREATE INDEX IF NOT EXISTS idx_imports_arquivo ON imports(arquivo);
        """)
        self._conn.commit()

    def _migrar(self):
        """Aplica migrations incrementais no banco existente."""
        colunas = [row[1] for row in self._conn.execute("PRAGMA table_info(usages)").fetchall()]
        if "tipo" not in colunas:
            self._conn.execute("ALTER TABLE usages ADD COLUMN tipo TEXT NOT NULL DEFAULT 'name'")
            self._conn.commit()
            self.limpar_tudo()

    # ── Files ─────────────────────────────────────────────────────────────────

    def arquivo_modificado(self, arquivo: str, hash_atual: str) -> bool:
        cur = self._conn.execute(
            "SELECT hash FROM files WHERE arquivo = ?", (arquivo,)
        )
        row = cur.fetchone()

        return row is None or row["hash"] != hash_atual

    def registrar_arquivo(self, arquivo: str, hash_atual: str, modificado_em: float):
        self._conn.execute(
            """
            INSERT INTO files(arquivo, hash, modificado_em)
            VALUES (?, ?, ?)
            ON CONFLICT(arquivo) DO UPDATE SET
                hash = excluded.hash,
                modificado_em = excluded.modificado_em
            """,
            (arquivo, hash_atual, modificado_em)
        )
        self._conn.commit()

    def remover_arquivo(self, arquivo: str):
        cur = self._conn.execute(
            "SELECT id FROM symbols WHERE arquivo = ?", (arquivo,)
        )
        ids = [row["id"] for row in cur.fetchall()]
        if ids:
            placeholders = ",".join("?" * len(ids))
            self._conn.execute(
                f"DELETE FROM usages WHERE symbol_id IN ({placeholders})", ids
            )
        self._conn.execute("DELETE FROM usages  WHERE arquivo = ?", (arquivo,))
        self._conn.execute("DELETE FROM symbols  WHERE arquivo = ?", (arquivo,))
        self._conn.execute("DELETE FROM imports  WHERE arquivo = ?", (arquivo,))
        self._conn.execute("DELETE FROM files    WHERE arquivo = ?", (arquivo,))
        self._conn.commit()

    def listar_arquivos_indexados(self) -> list[str]:
        cur = self._conn.execute("SELECT arquivo FROM files")

        return [row["arquivo"] for row in cur.fetchall()]

    # ── Escrita em batch ──────────────────────────────────────────────────────

    def inserir_simbolos_batch(self, simbolos: list[tuple]) -> dict[tuple, int]:
        """
        simbolos: lista de (nome, tipo, arquivo, linha, coluna, escopo)
        Retorna mapa (nome, linha) → id para uso posterior nas referências.
        """
        if not simbolos:

            return {}

        self._conn.executemany(
            """
            INSERT INTO symbols(nome, tipo, arquivo, linha, coluna, escopo)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            simbolos,
        )
        self._conn.commit()
        arquivo = simbolos[0][2]
        cur = self._conn.execute(
            "SELECT id, nome, linha FROM symbols WHERE arquivo = ?", (arquivo,)
        )

        return {(row["nome"], row["linha"]): row["id"] for row in cur.fetchall()}

    def inserir_referencias_batch(self, referencias: list[tuple]): # referencias: (symbol_id, arquivo, linha, coluna, tipo)
        if not referencias:

            return

        self._conn.executemany(
            """
            INSERT INTO usages(symbol_id, arquivo, linha, coluna, tipo)
            VALUES (?, ?, ?, ?, ?)
            """,
            referencias,
        )
        self._conn.commit()

    def inserir_imports_batch(self, imports: list[tuple]):
        """imports: lista de (modulo, arquivo, linha)"""
        if not imports:

            return

        self._conn.executemany(
            "INSERT INTO imports(modulo, arquivo, linha) VALUES (?, ?, ?)",
            imports,
        )
        self._conn.commit()

    # ── Escrita singular (mantida para compatibilidade) ───────────────────────

    def inserir_simbolo(self, nome, tipo, arquivo, linha, coluna=0, escopo="") -> int:
        cur = self._conn.execute(
            "INSERT INTO symbols(nome, tipo, arquivo, linha, coluna, escopo) VALUES (?,?,?,?,?,?)",
            (nome, tipo, arquivo, linha, coluna, escopo),
        )
        self._conn.commit()

        return cur.lastrowid

    def inserir_referencia(self, symbol_id, arquivo, linha, coluna=0):
        self._conn.execute(
            "INSERT INTO usages(symbol_id, arquivo, linha, coluna) VALUES (?,?,?,?)",
            (symbol_id, arquivo, linha, coluna),
        )
        self._conn.commit()

    def inserir_import(self, modulo, arquivo, linha):
        self._conn.execute(
            "INSERT INTO imports(modulo, arquivo, linha) VALUES (?,?,?)",
            (modulo, arquivo, linha),
        )
        self._conn.commit()

    def limpar_tudo(self):
        self._conn.executescript(
            "DELETE FROM usages; DELETE FROM symbols; "
            "DELETE FROM imports; DELETE FROM files;"
        )
        self._conn.commit()

    # ── Conexão ───────────────────────────────────────────────────────────────

    def fechar(self):
        """Fecha a conexão da thread atual."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None
