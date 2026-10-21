# 📁 _EDITOR_/Indexador/consultas.py
# -*- coding: utf-8 -*-
"""
Centraliza todas as consultas ao banco do indexador.
"""

class Consultas:
    def __init__(self, banco):
        self._banco = banco
        self._conn  = banco._conn

    # ── Símbolos ──────────────────────────────────────────────────────────────

    def buscar_definicao(self, nome: str) -> list[dict]:
        cur = self._conn.execute(
            """
            SELECT nome, tipo, arquivo, linha, coluna, escopo
            FROM symbols
            WHERE nome = ?
            ORDER BY arquivo, linha
            """,
            (nome,),
        )

        return [dict(row) for row in cur.fetchall()]

    def buscar_simbolos_por_prefixo(self, prefixo: str) -> list[dict]:
        cur = self._conn.execute(
            """
            SELECT nome, tipo, arquivo, linha, coluna, escopo
            FROM symbols
            WHERE nome LIKE ?
            ORDER BY nome, arquivo
            LIMIT 100
            """,
            (prefixo + "%",),
        )

        return [dict(row) for row in cur.fetchall()]

    def listar_simbolos_do_arquivo(self, arquivo: str) -> list[dict]:
        cur = self._conn.execute(
            """
            SELECT id, nome, tipo, linha, coluna, escopo
            FROM symbols
            WHERE arquivo = ?
            ORDER BY linha
            """,
            (arquivo,),
        )

        return [dict(row) for row in cur.fetchall()]

    # ── Referências ───────────────────────────────────────────────────────────

    def buscar_referencias(self, nome: str, arquivo_definicao: str) -> list[dict]:
        arquivo_norm = arquivo_definicao.replace("\\", "/")
        cur = self._conn.execute(
            """
            SELECT r.arquivo, r.linha, r.coluna
            FROM usages r
            JOIN symbols s ON s.id = r.symbol_id
            WHERE s.nome = ?
              AND replace(s.arquivo, char(92), '/') = ?
              AND r.tipo = 'call'
            ORDER BY r.arquivo, r.linha
            """,
            (nome, arquivo_norm),
        )

        return [dict(row) for row in cur.fetchall()]

    def contar_referencias(self, nome: str, arquivo_definicao: str) -> int:
        arquivo_norm = arquivo_definicao.replace("\\", "/")
        cur = self._conn.execute(
            """
            SELECT COUNT(*) as total
            FROM usages r
            JOIN symbols s ON s.id = r.symbol_id
            WHERE s.nome = ?
              AND replace(s.arquivo, char(92), '/') = ?
            """,
            (nome, arquivo_norm),
        )
        row = cur.fetchone()

        return row["total"] if row else 0

    def usages_por_arquivo(self, arquivo: str) -> dict[int, int]:
        arquivo_norm = arquivo.replace("\\", "/")
        cur = self._conn.execute(
            """
            SELECT s.linha, COUNT(r.id) as total
            FROM symbols s
            LEFT JOIN usages r ON r.symbol_id = s.id
            WHERE replace(s.arquivo, char(92), '/') = ?
            GROUP BY s.id
            """,
            (arquivo_norm,),
        )

        return {row["linha"]: row["total"] for row in cur.fetchall()}

    # ── Imports ───────────────────────────────────────────────────────────────

    def buscar_imports_do_arquivo(self, arquivo: str) -> list[dict]:
        cur = self._conn.execute(
            """
            SELECT modulo, linha
            FROM imports
            WHERE arquivo = ?
            ORDER BY linha
            """,
            (arquivo,),
        )

        return [dict(row) for row in cur.fetchall()]

    def arquivos_que_importam(self, modulo: str) -> list[dict]:
        cur = self._conn.execute(
            """
            SELECT arquivo, linha
            FROM imports
            WHERE modulo = ?
            ORDER BY arquivo
            """,
            (modulo,),
        )

        return [dict(row) for row in cur.fetchall()]

    # ── Estatísticas ──────────────────────────────────────────────────────────

    def resumo(self) -> dict:
        c_files   = self._conn.execute("SELECT COUNT(*) as n FROM files").fetchone()["n"]
        c_symbols = self._conn.execute("SELECT COUNT(*) as n FROM symbols").fetchone()["n"]
        c_refs    = self._conn.execute("SELECT COUNT(*) as n FROM usages").fetchone()["n"]
        c_imports = self._conn.execute("SELECT COUNT(*) as n FROM imports").fetchone()["n"]

        return {

            "arquivos":    c_files,
            "simbolos":    c_symbols,
            "referencias": c_refs,
            "imports":     c_imports,
        }
