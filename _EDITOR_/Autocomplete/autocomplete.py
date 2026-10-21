# 📁 _EDITOR_/Autocomplete/autocomplete.py
# -*- coding: utf-8 -*-
# 📁 _EDITOR_/Autocomplete/autocomplete.py
"""
Autocomplete profissional para a IDE hein.

Worker roda no Python do hein (sys.executable).
O código do usuário vai em arquivo temporário — evita problemas
com aspas, chaves e caracteres especiais no JSON.
Pacotes do projeto do usuário são encontrados via autocomplete.json.
Snippets do usuário também vêm do autocomplete.json.
"""
import os
import re
import sys
import json
import tempfile
import subprocess
import threading
from _LOG_.log import log
_ARQ = "autocomplete.py"
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView, QLabel
from _THREADS_.thread_segura import _ThreadSegura
from _THREADS_.ciclo_vida import encerrar_thread
from _THREADS_.diagnostico_workers import ensure_task, event, reference
from _THREADS_ import diagnostico_foco_temporario as _focus_trace
from PySide6.QtCore    import Qt, Signal, QTimer, QThread, QObject
from PySide6.QtGui     import QFont, QColor, QTextCursor
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_.gerenciador_autocomplete import autocomplete_global
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console
from _EDITOR_.Mult_Linguas import get_provider
try:
    from _UTILITARIOS_.icones import icone_tema as _icone_tema
    _QTA_OK = True
except Exception:
    _icone_tema = None
    _QTA_OK     = False
_WORKER_PATH  = os.path.join(os.path.dirname(__file__), "autocomplete_worker.py")
if getattr(sys, "frozen", False):
    # Frozen .exe: usa o proprio executavel como worker, interceptado em main.py
    # via flag --hein-autocomplete-worker (antes de qualquer import Qt).
    # Evita dist/python.exe que crashava ao encontrar Qt DLLs sem QApplication.
    _PYTHON_hein = sys.executable
    _WORKER_CMD  = [sys.executable, "--hein-autocomplete-worker"]
else:
    # Dev: python do venv com jedi; executa o worker diretamente.
    _PYTHON_hein = sys.executable
    _WORKER_CMD  = [sys.executable, "-X", "utf8", _WORKER_PATH]

_RAIZ_hein  = os.path.dirname(os.path.dirname(__file__))

_MDI = {
    "module":    "mdi.package-variant-outline",
    "class":     "mdi.alpha-c-box-outline",
    "instance":  "mdi.circle-small",
    "function":  "mdi.function-variant",
    "param":     "mdi.tag-outline",
    "keyword":   "mdi.key-outline",
    "statement": "mdi.code-braces",
    "import":    "mdi.import",
    "path":      "mdi.file-outline",
    "folder":    "mdi.folder-outline",
    "property":  "mdi.wrench-outline",
    "snippet":   "mdi.lightning-bolt",
    "word":      "mdi.text",
    "emoji":     "mdi.emoticon-outline",
    "symbol":    "mdi.omega",
    "auto_import": "mdi.import",
}

_COR_FALLBACK = {
    "module":    "#98c379", "class":    "#c678dd", "instance":  "#e0e0e0",
    "function":  "#26D3ED", "param":    "#e5c07b", "keyword":   "#e5c07b",
    "statement": "#888888", "import":   "#98c379", "snippet":   "#e5c07b",
    "word":      "#888888", "auto_import": "#98c379",
}

def _cor_por_tipo(tipo: str) -> str:
    t = tema_global()
    if tipo == "function":

        return t.cor("editor.sintaxe.funcao",        _COR_FALLBACK["function"])

    if tipo == "class":

        return t.cor("painel_outline.cor_classe",    _COR_FALLBACK["class"])

    if tipo in ("module", "import", "auto_import"):

        return t.cor("editor.sintaxe.string",        _COR_FALLBACK["module"])

    if tipo in ("keyword", "param", "snippet"):

        return t.cor("editor.sintaxe.string_regex",  _COR_FALLBACK["keyword"])

    return t.cor("interface.texto_fraco", _COR_FALLBACK.get(tipo, "#888888"))

def _palavras_do_buffer(texto: str, prefixo: str) -> list:
    """Palavras únicas do buffer que começam com o prefixo — word completer local."""
    if len(prefixo) < 2:

        return []

    palavras = set(re.findall(r'\b[A-Za-z_]\w+\b', texto))
    palavras.discard(prefixo)
    prefixo_lower = prefixo.lower()

    return [

        {"name": p, "type": "word", "description": "", "signature": "", "conteudo": ""}
        for p in sorted(palavras)
        if p.lower().startswith(prefixo_lower)
    ]

# -- IMP-04: auto-import de modulos nativos (estilo PyCharm/VSCode) -----------
# Nomes comuns da stdlib que o usuario as vezes digita sem ainda ter importado.
# Ao aceitar a sugestao, alem de inserir o nome no cursor, a IDE insere
# automaticamente a linha de import no topo do arquivo (se ainda nao existir).
_STDLIB_AUTO_IMPORT: dict[str, str] = {
    "os": "import os", "sys": "import sys", "re": "import re", "json": "import json",
    "time": "import time", "math": "import math", "random": "import random",
    "subprocess": "import subprocess", "shutil": "import shutil", "glob": "import glob",
    "copy": "import copy", "io": "import io", "csv": "import csv", "sqlite3": "import sqlite3",
    "threading": "import threading", "logging": "import logging", "argparse": "import argparse",
    "itertools": "import itertools", "functools": "import functools",
    "collections": "import collections", "datetime": "import datetime",
    "pathlib": "import pathlib", "traceback": "import traceback", "typing": "import typing",
    "enum": "import enum", "hashlib": "import hashlib", "base64": "import base64",
    "uuid": "import uuid", "socket": "import socket", "asyncio": "import asyncio",
    "unittest": "import unittest", "textwrap": "import textwrap", "platform": "import platform",
    "Path":        "from pathlib import Path",
    "OrderedDict": "from collections import OrderedDict",
    "defaultdict": "from collections import defaultdict",
    "Counter":     "from collections import Counter",
    "dataclass":   "from dataclasses import dataclass",
    "Optional":    "from typing import Optional",
    "List":        "from typing import List",
    "Dict":        "from typing import Dict",
    "Any":         "from typing import Any",
    "Union":       "from typing import Union",
    "Tuple":       "from typing import Tuple",
}

_RE_IMPORT_LINHA = re.compile(r'^\s*(import|from)\s+([A-Za-z_][\w.]*)')

def _ja_importado(codigo: str, nome: str, stmt: str) -> bool:
    """True se `nome` ja esta acessivel via algum import existente no arquivo
    (mesmo modulo, ou `import X as nome`, ou o proprio stmt ja presente)."""
    modulo_alvo = stmt.split()[1].split('.')[0]  # 'import os' / 'from pathlib import Path' -> 'os'/'pathlib'
    for linha in codigo.splitlines():
        m = _RE_IMPORT_LINHA.match(linha)
        if not m:
            continue
        if stmt.strip() in linha.strip():

            return True
        if m.group(2).split('.')[0] == modulo_alvo:

            return True
        if re.search(rf'\bas\s+{re.escape(nome)}\b', linha):

            return True

    return False

def _montar_auto_import(prefixo: str, codigo: str) -> list:
    """Sugestoes de auto-import (stdlib) que batem com o prefixo digitado
    e ainda nao foram importadas no arquivo atual."""
    if not prefixo:

        return []

    sugestoes = []
    for nome, stmt in _STDLIB_AUTO_IMPORT.items():
        if nome.startswith(prefixo) and not _ja_importado(codigo, nome, stmt):
            sugestoes.append({
                "name": nome, "type": "auto_import",
                "description": f"auto-import — {stmt}",
                "signature": "", "conteudo": "", "_import_stmt": stmt,
            })

    return sugestoes

def _inserir_import_no_topo(editor, stmt: str) -> None:
    """Insere `stmt` ('import os' etc.) logo apos o bloco de imports
    existente no topo do arquivo (ou apos docstring/shebang, se nao houver
    nenhum import ainda). Nao duplica se o stmt exato ja estiver presente."""
    doc = editor.document()
    ultima_linha_import = -1
    ponto_insercao = 0
    bloco = doc.firstBlock()
    em_docstring = False
    while bloco.isValid():
        txt = bloco.text()
        stripped = txt.strip()
        if stripped.startswith(('"""', "'''")) and not em_docstring:
            aspas = stripped[:3]
            _fechou_na_mesma_linha = len(stripped) > 3 and stripped.endswith(aspas)
            ponto_insercao = bloco.blockNumber() + 1
            if not _fechou_na_mesma_linha:
                em_docstring = True
            bloco = bloco.next()
            continue
        if em_docstring:
            if stripped.endswith(('"""', "'''")):
                em_docstring = False
                ponto_insercao = bloco.blockNumber() + 1
            bloco = bloco.next()
            continue
        if stripped == stmt.strip():

            return  # ja existe — nao duplica
        if _RE_IMPORT_LINHA.match(txt):
            ultima_linha_import = bloco.blockNumber()
        elif stripped and ultima_linha_import == -1 and ponto_insercao == 0 and not stripped.startswith('#') and not stripped.startswith('#!'):
            break
        bloco = bloco.next()

    if ultima_linha_import != -1:
        bloco_alvo = doc.findBlockByNumber(ultima_linha_import)
        c = QTextCursor(bloco_alvo)
        c.movePosition(QTextCursor.EndOfBlock)
        c.insertText("\n" + stmt)
    else:
        bloco_alvo = doc.findBlockByNumber(max(ponto_insercao, 0))
        c = QTextCursor(bloco_alvo)
        c.movePosition(QTextCursor.StartOfBlock)
        c.insertText(stmt + "\n\n")

# -- Tabstops de snippet ($1, $2, ${1:texto}, $0) ------------------------------

_RE_TABSTOP = re.compile(r'\$(?:(\d+)|\{(\d+):([^}]*)\})')

def _parsear_snippet(conteudo: str) -> tuple[str, list]:
    """
    Extrai marcadores de tabstop de um snippet e devolve o texto sem eles.
    Cada spec e (numero, posicao_no_texto_final, tamanho_do_placeholder).
    $0 e sempre o ultimo a ser visitado, mesmo que apareca antes no texto.
    """
    pedacos: list = []
    specs:   list = []
    cursor_saida = 0
    ultimo = 0
    for m in _RE_TABSTOP.finditer(conteudo):
        trecho = conteudo[ultimo:m.start()]
        pedacos.append(trecho)
        cursor_saida += len(trecho)
        numero      = int(m.group(1) if m.group(1) is not None else m.group(2))
        placeholder = m.group(3) or ""
        specs.append((numero, cursor_saida, len(placeholder)))
        pedacos.append(placeholder)
        cursor_saida += len(placeholder)
        ultimo = m.end()
    pedacos.append(conteudo[ultimo:])
    # Ordena por numero (1, 2, 3...) e deixa o $0 (numero == 0) por ultimo.
    specs.sort(key=lambda s: (s[0] == 0, s[0]))

    return "".join(pedacos), specs

# -- Fontes do AppData (palavras.txt / simbolos.json / emojis.json) -----------

_CACHE_FONTES: dict = {'palavras': None, 'simbolos': None, 'emojis': None}

# ⚠️  except genérico vazio
def _carregar_fontes_appdata() -> None:
    """Lê fontes do AppData/autocompletar/ respeitando listas de autocomplete.json."""
    try:
        from _APPDATA_ import appdata
        pasta = appdata.autocompletar
    except Exception:

        return

    fa = autocomplete_global().fontes_appdata()

    if _CACHE_FONTES['palavras'] is None:
        palavras: list = []
        for nome_arq in (fa.get('palavras') or ['palavras.txt']):
            try:
                with open(os.path.join(pasta, nome_arq), encoding='utf-8') as f:
                    palavras += [l.strip() for l in f if l.strip() and not l.startswith('#')]
            except Exception:
                pass
        _CACHE_FONTES['palavras'] = sorted(set(palavras))

    if _CACHE_FONTES['simbolos'] is None:
        merged: dict = {}
        for nome_arq in (fa.get('simbolos') or ['simbolos.json']):
            try:
                with open(os.path.join(pasta, nome_arq), encoding='utf-8') as f:
                    dados = json.load(f)
                merged.update({k: v for k, v in dados.items() if not k.startswith('_')})
            except Exception:
                pass
        _CACHE_FONTES['simbolos'] = merged

    if _CACHE_FONTES['emojis'] is None:
        merged2: dict = {}
        for nome_arq in (fa.get('emojis') or ['emojis.json']):
            try:
                with open(os.path.join(pasta, nome_arq), encoding='utf-8') as f:
                    dados = json.load(f)
                merged2.update({k: v for k, v in dados.items() if not k.startswith('_')})
            except Exception:
                pass
        _CACHE_FONTES['emojis'] = merged2

def _fuzzy_score(prefixo_lower: str, alvo_lower: str):
    """
    Fuzzy matching estilo VS Code: as letras do prefixo precisam aparecer em
    alvo NA MESMA ORDEM, mas não precisam ser contíguas nem estar no início
    (ex: 'fgo' bate em 'fogo'). Retorna None se não bate, ou uma tupla-score
    (menor = melhor) para ordenar: menos 'saltos' entre letras, match mais
    cedo no alvo, e alvo mais curto (startswith puro sempre vence).
    """
    if not prefixo_lower:

        return (0, 0, len(alvo_lower))

    pos_alvo     = 0
    pos_prefixo  = 0
    primeiro_idx = -1
    ultimo_idx   = -1
    saltos       = 0
    while pos_prefixo < len(prefixo_lower) and pos_alvo < len(alvo_lower):
        if alvo_lower[pos_alvo] == prefixo_lower[pos_prefixo]:
            if primeiro_idx == -1:
                primeiro_idx = pos_alvo
            elif pos_alvo != ultimo_idx + 1:
                saltos += 1
            ultimo_idx  = pos_alvo
            pos_prefixo += 1
        pos_alvo += 1

    if pos_prefixo < len(prefixo_lower):

        return None

    return (saltos, primeiro_idx, len(alvo_lower))


def _fontes_appdata_filtradas(prefixo: str) -> list:
    if not prefixo:

        return []

    _carregar_fontes_appdata()
    prefixo_lower = prefixo.lower()
    pontuados: list = []
    for p in (_CACHE_FONTES.get('palavras') or []):
        score = _fuzzy_score(prefixo_lower, p.lower())
        if score is not None:
            pontuados.append((score, {'name': p, 'type': 'word',
                               'description': 'wordlist', 'signature': '', 'conteudo': ''}))
    for nome, char in (_CACHE_FONTES.get('simbolos') or {}).items():
        score = _fuzzy_score(prefixo_lower, nome.lower())
        if score is not None:
            pontuados.append((score, {'name': nome, 'type': 'symbol',
                               'description': char, 'signature': '', 'conteudo': char,
                               '_extra_delete': 0}))
    for nome, emoji in (_CACHE_FONTES.get('emojis') or {}).items():
        score = _fuzzy_score(prefixo_lower, nome.lower())
        if score is not None:
            pontuados.append((score, {'name': nome, 'type': 'emoji',
                               'description': emoji, 'signature': '', 'conteudo': emoji,
                               '_extra_delete': 0}))

    pontuados.sort(key=lambda par: par[0])

    return [item for _, item in pontuados]

def _invalidar_cache_fontes() -> None:
    _CACHE_FONTES['palavras'] = None
    _CACHE_FONTES['simbolos'] = None
    _CACHE_FONTES['emojis']   = None

def _detectar_caminho(bloco: str, col: int) -> tuple[bool, str]:
    """Retorna (dentro_de_string, texto_desde_a_abertura_até_o_cursor)."""
    antes = bloco[:col]
    for q in ('"', "'"):
        pos = antes.rfind(q)
        if pos < 0:
            continue
        interior = antes[pos + 1:]
        if q not in interior:      # aspas não fechada — cursor está dentro

            return True, interior

    return False, ""

# ⚠️  função grande (62 linhas)
def _arquivos_do_projeto(project_path: str, path_prefixo: str, arq_prefixo: str) -> list:
    """
    Sugere arquivos/pastas do projeto a partir do conteúdo digitado dentro da string.
    Suporta:
      - prefixo simples: "logo  → logo-hein-ido.png
      - subdiretórios:   "./docs/rel  → relatorio.txt
      - glob:            "*.py  → main.py / SIMPLES.py
    """
    import fnmatch as _fnmatch
    if not project_path:

        return []

    # Separa parte de diretório e parte de arquivo
    if "/" in path_prefixo or "\\" in path_prefixo:
        sep = "/" if "/" in path_prefixo else "\\"
        dir_str, arq_str = path_prefixo.rsplit(sep, 1)
    else:
        dir_str, arq_str = "", path_prefixo

    # Resolve caminho base: limpa ./ e ../ relativos
    dir_clean = dir_str.lstrip("./\\").replace("../", "").replace("..\\", "")
    base_dir  = os.path.normpath(os.path.join(project_path, dir_clean)) if dir_clean else project_path
    if not os.path.isdir(base_dir):

        return []

    try:
        entradas = os.listdir(base_dir)
    except PermissionError:

        return []

    # Filtro: glob (*) ou startswith case-insensitive no arq_str completo
    glob_mode = "*" in path_prefixo
    if glob_mode:
        arq_search = arq_str
        matched = _fnmatch.filter(entradas, arq_search) if arq_search else list(entradas)
    else:
        arq_search = arq_str   # pode conter hifens/pontos — mais específico que arq_prefixo
        if arq_search:
            matched = [e for e in entradas if e.lower().startswith(arq_search.lower())]
        else:
            matched = list(entradas)[:20]

    # extra_delete: chars a apagar além do prefixo alnum padrão (hifens, glob, pontos)
    extra_delete = max(0, len(arq_search) - len(arq_prefixo))

    resultado = []
    for nome in sorted(matched)[:30]:   # limite anti-ruído
        eh_pasta = os.path.isdir(os.path.join(base_dir, nome))
        ext = os.path.splitext(nome)[1][1:] or "arquivo"
        resultado.append({
            "name":          nome,
            "type":          "folder" if eh_pasta else "path",
            "description":   "pasta"  if eh_pasta else ext,
            "signature":     "",
            "conteudo":      "",
            "_extra_delete": extra_delete,
        })

    return resultado

def _jedi_permitido(editor) -> bool:
    """
    So consulta o worker Jedi quando o provider da linguagem do arquivo atual
    declara autocomplete = 'jedi' (hoje: so Python). Para as demais linguagens
    (JS, Shell, SQL, C/C++ etc.) evita mandar codigo nao-Python pro Jedi parsear
    - o usuario ainda recebe snippets, word-completer local, fontes do AppData
    (emojis/simbolos/palavras) e file path completer, que sao independentes de linguagem.
    """
    caminho = getattr(editor, 'file_path', None)
    if not caminho:

        return True   # arquivo ainda sem caminho (novo/nao salvo) -> assume Python

    return get_provider(caminho).autocomplete == 'jedi'

def _salvar_codigo_temp(codigo: str) -> str | None:
    """Salva o código em arquivo temporário e retorna o caminho."""
    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", encoding="utf-8",
            delete=False, prefix="hein_ac_"
        )
        tmp.write(codigo)
        tmp.flush()
        tmp.close()

        return tmp.name

    except Exception:

        return None

# ══════════════════════════════════════════════════════════════════════════════
# WorkerSubprocess
# ══════════════════════════════════════════════════════════════════════════════

class WorkerSubprocess:
    def __init__(self, project_path: str):
        self._project_path = project_path
        self._proc         = None
        self._pronto       = False
        self._lock         = threading.Lock()

    def iniciar(self) -> bool:
        try:
            self._proc = subprocess.Popen(
                _WORKER_CMD,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                encoding="utf-8", bufsize=1,
                **opcoes_processo_sem_console(),
            )
            linha = self._proc.stdout.readline()
            if not linha:
                err = self._proc.stderr.read()
                log.erro(_ARQ, "iniciar", "Worker não respondeu", str(err))

                return False

            msg = json.loads(linha.strip())
            if msg.get("ready"):
                self._pronto = True
                log.info(_ARQ, "iniciar", "Worker pronto", str(_PYTHON_hein))

                return True

            if msg.get("error") == "jedi_not_found":
                log.aviso(_ARQ, "iniciar", "Jedi não encontrado", f"Instale: {_PYTHON_hein} -m pip install jedi")

            return False

        except Exception as e:
            log.erro(_ARQ, "iniciar", "Falha ao iniciar worker", str(e))

            return False

    def consultar(self, payload: dict) -> dict | None:
        if not self._pronto or not self._proc:

            return None

        with self._lock:
            try:
                payload["project_path"] = self._project_path
                linha = json.dumps(payload, ensure_ascii=False) + "\n"
                self._proc.stdin.write(linha)
                self._proc.stdin.flush()
                resposta = self._proc.stdout.readline()
                if not resposta:
                    err = self._proc.stderr.read()
                    log.erro(_ARQ, "consultar", "Worker encerrou", str(err))
                    self._pronto = False

                    return None

                return json.loads(resposta.strip())

            except Exception as e:
                log.erro(_ARQ, "consultar", "Erro na consulta", str(e))
                self._pronto = False

                return None

    # ⚠️  except genérico vazio
    def encerrar(self):
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc   = None
            self._pronto = False

# ══════════════════════════════════════════════════════════════════════════════
# _ConsultaThread
# ══════════════════════════════════════════════════════════════════════════════

class _ConsultaThread(_ThreadSegura):
    resultado = Signal(dict, int)   # resposta + geração

    def __init__(self, worker: WorkerSubprocess, payload: dict, geracao: int = 0,
                 tmp_path: str | None = None, editor=None):
        super().__init__()
        self._worker   = worker
        self._payload  = payload
        self._geracao  = geracao
        self._tmp_path = tmp_path
        ensure_task(self, "AC", editor=editor)

    def run(self):
        _task = ensure_task(self, "AC")
        event("RUN_ENTER", "AC", _task, obj=self)
        try:
            resposta = self._worker.consultar(self._payload)
            if self._tmp_path:
                try:
                    os.remove(self._tmp_path)
                except Exception:
                    pass
            if resposta:
                self.resultado.emit(resposta, self._geracao)
                event("RESULT_EMITTED", "AC", _task, obj=self,
                      result_keys=list(resposta.keys()))
        except Exception as e:
            log.erro(_ARQ, "_ConsultaThread.run", "excecao nao tratada na thread", str(e))
            event("ERROR", "AC", _task, obj=self, error=str(e))
        finally:
            event("RUN_EXIT", "AC", _task, obj=self)

# ══════════════════════════════════════════════════════════════════════════════
# TooltipSignature
# ══════════════════════════════════════════════════════════════════════════════

class TooltipSignature(QLabel):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor
        self.setWindowFlags(Qt.ToolTip)
        self.setFont(QFont("Consolas", 10))
        self.setTextFormat(Qt.RichText)
        self._aplicar_tema()
        self.hide()

    def _aplicar_tema(self):
        t      = tema_global()
        fundo  = t.cor("editor.fundo",           "#0F1210")
        borda  = t.cor("interface.borda_externa", "#082c3a")
        texto  = t.cor("editor.texto",            "#e0e0e0")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {fundo};
                color: {texto};
                border: 1px solid {borda};
                border-radius: 4px;
                padding: 4px 12px;
            }}
        """)

    def mostrar(self, signatures: list):
        if not signatures:
            self.hide()

            return

        sig    = signatures[0]
        nome   = sig.get("name", "")
        idx    = sig.get("index", -1)
        params = sig.get("params", [])
        partes = []
        for i, p in enumerate(params):
            np = p.get("name", "")
            if i == idx:
                partes.append(f'<b style="color:#e5c07b">{np}</b>')
            else:
                partes.append(f'<span style="color:#abb2bf">{np}</span>')
        self.setText(
            f'<span style="color:#61afef">{nome}</span>'
            f'({", ".join(partes)})'
        )
        self.adjustSize()
        ponto = self._editor.cursorRect().topLeft()
        ponto.setY(ponto.y() - self.height() - 6)
        self.move(self._editor.mapToGlobal(ponto))
        self.show()
        self.raise_()

    def fechar(self):
        self.hide()

# ══════════════════════════════════════════════════════════════════════════════
# ListaAutocomplete
# ══════════════════════════════════════════════════════════════════════════════

class ListaAutocomplete(QListWidget):
    sugestao_confirmada = Signal(str, int, str, int)   # nome, tamanho_prefixo, tipo, extra_delete

    def __init__(self, editor):
        super().__init__(editor)
        self._editor  = editor
        self._prefixo = ""
        self.setWindowFlags(Qt.ToolTip)
        self.setFocusPolicy(Qt.NoFocus)
        # BUG-02: no Windows, mostrar um ToolTip top-level pode desativar a janela
        # principal por um frame, fazendo o editor perder foco e o Esc nunca chegar
        # no keyPressEvent. WA_ShowWithoutActivating previne a desativacao.
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setMaximumHeight(220)
        self.setMinimumWidth(260)
        self.setMaximumWidth(520)
        self.setFont(QFont("Consolas", 11))
        self._aplicar_tema()
        self.itemClicked.connect(self._ao_clicar)
        self.hide()

    def _aplicar_tema(self):
        t      = tema_global()
        fundo  = t.cor("menu_contexto.fundo",            "#0F1210")
        borda  = t.cor("menu_contexto.borda",            "#082c3a")
        texto  = t.cor("menu_contexto.texto",            "#e0e0e0")
        hover       = t.cor("menu_contexto.item_hover",  "#1a2e1a")
        texto_hover = t.cor("menu_contexto.texto_hover", "#ffffff")
        scroll      = t.cor("interface.fundo_aba_ativa", "#082C3A")
        self.setStyleSheet(f"""
            QListWidget {{
                background-color: {fundo};
                color: {texto};
                border: 1px solid {borda};
                border-radius: 4px;
                padding: 2px;
                outline: none;
            }}
            QListWidget::item              {{ padding: 3px 8px; border-radius: 2px; }}
            QListWidget::item:hover        {{ background-color: {hover}; }}
            QListWidget::item:selected     {{ background-color: {hover}; color: {texto_hover}; }}
            QScrollBar:vertical            {{ width: 6px; background: transparent; }}
            QScrollBar::handle:vertical    {{ background: {scroll}; border-radius: 3px; }}
        """)

    # ⚠️  except genérico vazio
    def mostrar_sugestoes(self, sugestoes: list, prefixo: str):
        self._aplicar_tema()
        self._prefixo = prefixo
        self.clear()
        for s in sugestoes:
            tipo  = s.get("type", "statement")
            assin = f"  {s['signature']}" if s.get("signature") else ""
            item  = QListWidgetItem(f"{s['name']}{assin}")
            item.setData(Qt.UserRole,     s["name"])
            item.setData(Qt.UserRole + 1, tipo)
            item.setData(Qt.UserRole + 2, s.get("conteudo", ""))
            item.setData(Qt.UserRole + 3, s.get("_extra_delete", 0))
            item.setToolTip(s.get("description", ""))
            item.setForeground(QColor(_cor_por_tipo(tipo)))
            if _QTA_OK:
                try:
                    item.setIcon(_icone_tema(_MDI.get(tipo, "mdi.code-braces"),
                                             color=_cor_por_tipo(tipo)))
                except Exception:
                    pass
            self.addItem(item)
        if self.count() == 0:
            self.hide()

            return

        self.setCurrentRow(0)
        ponto = self._editor.cursorRect().bottomLeft()
        self.move(self._editor.viewport().mapToGlobal(ponto))
        self.adjustSize()
        self.setFixedWidth(max(260, self.sizeHintForColumn(0) + 24))
        self.show()
        self.raise_()
        self._editor.setFocus()   # garante que o editor mantem foco apos show() do popup

    def fechar(self):
        self.hide()
        self.clear()

    # Bug #6: no Windows, Qt.ToolTip + Qt.NoFocus faz com que itemClicked
    # não dispare (clique não entregue ao widget filho pois a janela não
    # recebe ativação). mousePressEvent garante que qualquer press esquerdo
    # sobre um item confirme a sugestão, independente do comportamento de foco.
    def mousePressEvent(self, event):
        from PySide6.QtCore import Qt as _Qt
        if event.button() == _Qt.LeftButton:
            item = self.itemAt(event.position().toPoint())
            if item:
                self._ao_clicar(item)
                return
        super().mousePressEvent(event)

    def navegar(self, direcao: int):
        if self.count() == 0:

            return

        # Wrap-around: seta pra cima no primeiro item vai para o ultimo e
        # vice-versa - sem isso, currentRow() ficava travado em 0/ultimo.
        nova = (self.currentRow() + direcao) % self.count()
        self.setCurrentRow(nova)

    def confirmar(self):
        item = self.currentItem()
        if item:
            self.sugestao_confirmada.emit(
                item.data(Qt.UserRole),
                len(self._prefixo),
                item.data(Qt.UserRole + 1),
                item.data(Qt.UserRole + 3) or 0,
            )
            self.fechar()

    def keyPressEvent(self, event):
        # Repassa tudo ao editor — o popup nunca consome teclas direto.
        # Garante que Esc, setas e qualquer outra tecla sempre cheguem
        # ao keyPressEvent do editor, independente de foco no Windows.
        self._editor.keyPressEvent(event)

    def _ao_clicar(self, item: QListWidgetItem):
        self.sugestao_confirmada.emit(
            item.data(Qt.UserRole),
            len(self._prefixo),
            item.data(Qt.UserRole + 1),
            item.data(Qt.UserRole + 3) or 0,
        )
        self.fechar()

# ══════════════════════════════════════════════════════════════════════════════
# _FiltroTeclasGlobal
# ══════════════════════════════════════════════════════════════════════════════

class _FiltroTeclasGlobal(QObject):
    """
    Event filter instalado na QApplication — intercepta qualquer KeyPress
    enquanto o popup de autocomplete ou o tooltip de assinatura estiver visível.

    Resolve o cenário Windows onde Qt.ToolTip rouba o foco da janela principal
    mesmo com WA_ShowWithoutActivating: o editor perde foco, seu keyPressEvent
    não é chamado e o Esc nunca chega em interceptar_tecla.
    """

    def __init__(self, gerenciador):
        super().__init__()
        self._ger = gerenciador

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            # Qt.ToolTip/Qt.Popup podem roubar o foco e impedir que o
            # keyPressEvent do editor seja chamado. A rotina centralizada do
            # editor fecha também quick-fix, busca, referências, corretor e
            # demais pop-ups pertencentes ao editor.
            try:
                if self._ger._editor._fechar_popups_esc():
                    return True
            except (AttributeError, RuntimeError):
                pass

        if event.type() == QEvent.MouseButtonPress:
            ger = self._ger
            try:
                lista = ger._lista
                if (
                    event.button() == Qt.LeftButton
                    and lista.isVisible()
                ):
                    ponto_global = event.globalPosition().toPoint()
                    ponto_lista = lista.mapFromGlobal(ponto_global)
                    if lista.rect().contains(ponto_lista):
                        item = lista.itemAt(ponto_lista)
                        if item is not None:
                            lista._ao_clicar(item)
                            return True
            except (RuntimeError, AttributeError):
                return False
        if event.type() == QEvent.KeyPress:
            ger = self._ger
            # Guard: se o editor foi destruido e o disconnect ainda nao
            # processou, _lista/_tooltip podem estar mortos no C++.
            try:
                lista_visivel   = ger._lista.isVisible()
                tooltip_visivel = ger._tooltip.isVisible()
            except RuntimeError:
                return False
            if lista_visivel or tooltip_visivel:
                # Esc fecha o popup sem verificar foco. No Windows,
                # Qt.ToolTip rouba o foco mesmo com WA_ShowWithoutActivating,
                # fazendo a checagem de foco abaixo falhar e o Esc
                # nunca chegar ao keyPressEvent do editor.
                if event.key() == Qt.Key_Escape:
                    ger.fechar()
                    return True
                # Demais teclas (Tab, setas): so intercepta quando
                # o foco nao esta no editor, evitando duplo processamento.
                from PySide6.QtWidgets import QApplication
                foco = QApplication.focusWidget()
                if foco is not ger._editor and foco is not ger._editor.viewport():
                    if ger.interceptar_tecla(event):
                        return True
        return False

# ══════════════════════════════════════════════════════════════════════════════
# GerenciadorAutocomplete
# ══════════════════════════════════════════════════════════════════════════════

class GerenciadorAutocomplete:
    """
    Ponto de entrada usado pelo Editor.
    Worker roda no .venv do hein.
    Código do usuário vai em arquivo temporário — sem problemas de encoding no JSON.
    Snippets e configuração de ambiente vêm do autocomplete.json.
    """

    def __init__(self, editor):
        self._editor       = editor
        self._lista        = ListaAutocomplete(editor)
        self._tooltip      = TooltipSignature(editor)
        self._project_path = None
        self._worker:  WorkerSubprocess | None = None
        self._threads: list = []  # mantém threads vivas até terminarem
        self._snippets: dict = autocomplete_global().snippets()
        self._gen: int = 0  # descarta respostas de queries antigas

        self._lista.sugestao_confirmada.connect(self._inserir_sugestao)
        self._geracao  = 0
        self._bloqueado = False  # True apos fechar(); False quando usuario digita
        # Geração independente das consultas de assinatura. Respostas Jedi
        # podem chegar depois que o popup foi fechado ou que o cursor mudou;
        # nesse caso, o resultado não pertence mais ao contexto atual.
        self._geracao_signature = 0

        # Sessao de tabstops ($1, $2, $0) apos inserir um snippet com varios
        # pontos de parada - Tab pula entre eles enquanto ativa.
        self._tabstop_ativo = False
        self._tabstops:    list = []
        self._tabstop_idx  = 0

        self._timer_complete = QTimer()
        self._timer_complete.setSingleShot(True)
        self._timer_complete.setInterval(300)
        self._timer_complete.timeout.connect(self._calcular_complete)

        self._timer_sig = QTimer()
        self._timer_sig.setSingleShot(True)
        self._timer_sig.setInterval(120)
        self._timer_sig.timeout.connect(self._calcular_signature)

        # hot-reload delegado ao gerenciador_autocomplete central
        autocomplete_global().registrar(self)

        # Event filter global — garante que Esc chega mesmo quando o popup
        # ToolTip rouba o foco no Windows (WA_ShowWithoutActivating nao e 100%
        # confiavel em todas as versoes do Windows + Qt).
        from PySide6.QtWidgets import QApplication
        self._filtro_global = _FiltroTeclasGlobal(self)
        app = QApplication.instance()
        _focus_trace.install(app)
        app.installEventFilter(self._filtro_global)

        # Mesmo bug do PopupQuickFix: Qt.ToolTip + WA_ShowWithoutActivating
        # deixa a lista de sugestoes e o tooltip de assinatura "sem dono"
        # pro SO -- eles nao fecham sozinhos ao trocar de janela (alt-tab,
        # clicar em outro programa) nem ao mudar de foco dentro do proprio
        # hein. Ficavam flutuando por cima de QUALQUER janela pra sempre.
        app.focusChanged.connect(self._ao_foco_mudar)
        app.applicationStateChanged.connect(self._ao_estado_app_mudar)

        # O filtro acima fica instalado na QApplication (global, fora do
        # ciclo de vida do editor). Se o editor for destruido (aba fechada,
        # painel dividido fechado, janela flutuante fechada) sem remover o
        # filtro, ele continua recebendo eventos de teclado do app inteiro
        # e tenta acessar self._lista / self._tooltip, cujo objeto C++ ja
        # foi destruido -> RuntimeError: Internal C++ object already
        # deleted. O sinal destroyed() do Qt dispara nesse exato momento,
        # entao removemos o filtro ali, sem depender de nenhum outro
        # codigo de fechamento de aba/painel/janela chamar cleanup.
        editor.destroyed.connect(self._ao_editor_destruido)

    def _ao_editor_destruido(self, *_args):
        """Remove TODOS os callbacks globais quando o editor e destruido no C++.

        _filtro_global, focusChanged e applicationStateChanged ficam
        instalados na QApplication (escopo global, fora do ciclo de vida
        do editor). Sem desconectar aqui, continuam disparando depois que
        _lista/_tooltip ja foram deletados pelo Qt, causando:
            RuntimeError: libshiboken: Internal C++ object already deleted.

        FIX: removeEventFilter ja existia; adicionado disconnect de
        focusChanged e applicationStateChanged -- causa raiz do crash
        (ListaAutocomplete already deleted) reportado no log de sessao.
        """
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                app.removeEventFilter(self._filtro_global)
                try:
                    app.focusChanged.disconnect(self._ao_foco_mudar)
                except Exception:
                    pass
                try:
                    app.applicationStateChanged.disconnect(self._ao_estado_app_mudar)
                except Exception:
                    pass
        except Exception:
            pass

    def _pertence_ao_autocomplete(self, widget) -> bool:
        """True se `widget` e a lista de sugestoes, o tooltip de assinatura,
        ou algum filho deles."""
        w = widget
        while w is not None:
            if w is self._lista or w is self._tooltip:
                return True
            w = w.parentWidget()
        return False

    def _ao_foco_mudar(self, _antigo, novo):
        """Fecha lista/tooltip quando o foco vai pra qualquer widget que nao
        seja o editor nem os proprios popups -- outra aba, outro painel,
        outra janela do hein, etc."""
        _focus_trace.enter("autocomplete", _antigo, novo)
        try:
            self._ao_foco_mudar_impl(_antigo, novo)
        finally:
            _focus_trace.exit("autocomplete")

    def _ao_foco_mudar_impl(self, _antigo, novo):
        # Guard: _lista/_tooltip podem ja ter sido destruidos pelo C++ se
        # o editor foi fechado antes do disconnect do focusChanged completar
        # (race condition entre destroyed() e a ultima emissao do sinal).
        try:
            tooltip_visivel = self._tooltip.isVisible()
        except RuntimeError:
            return
        if not self.esta_visivel() and not tooltip_visivel:
            return
        if novo is self._editor or self._pertence_ao_autocomplete(novo):
            return
        _focus_trace.reaction("autocomplete", "fechar")
        self.fechar()

    def _ao_estado_app_mudar(self, estado):
        """Fecha lista/tooltip quando a janela do hein inteira perde o foco
        pro SO (alt-tab, clicar em outro programa) -- e onde o bug aparecia
        flutuando por cima de outros aplicativos inteiros."""
        # Guard: mesmo motivo do _ao_foco_mudar -- race condition pos-destroy.
        try:
            tooltip_visivel = self._tooltip.isVisible()
        except RuntimeError:
            return
        if not self.esta_visivel() and not tooltip_visivel:
            return
        if estado != Qt.ApplicationActive:
            self.fechar()

    def _recarregar_snippets(self):
        self._snippets = autocomplete_global().snippets()
        _invalidar_cache_fontes()   # garante releitura das fontes AppData junto
        log.ok(_ARQ, "_recarregar_snippets", "Snippets recarregados do autocomplete.json")

    # ── Projeto ───────────────────────────────────────────────────────────────

    def set_project_path(self, path: str | None):
        if path == self._project_path:

            return

        self._project_path = path
        self._snippets = autocomplete_global().snippets()
        if self._worker:
            self._worker.encerrar()
            self._worker = None
        if not path:

            return

        # Iniciar o worker faz Popen + readline() bloqueante esperando o
        # subprocess (jedi) ficar pronto - isso podia levar varios segundos
        # e travava a UI inteira ("nao responde") logo ao abrir um arquivo
        # pela primeira vez. Roda em background, igual _tentar_reiniciar_worker.
        def _fazer(caminho=path):
            worker = WorkerSubprocess(caminho)
            if worker.iniciar():
                if self._project_path == caminho:
                    self._worker = worker
                else:
                    worker.encerrar()   # projeto trocou enquanto o worker subia
            else:
                log.erro(_ARQ, "set_project_path", "Worker não iniciou")

        threading.Thread(target=_fazer, daemon=True).start()

    # ── API pública ───────────────────────────────────────────────────────────

    def _tentar_reiniciar_worker(self):
        """Reinicia o worker em background se ele morreu. Não bloqueia a UI."""
        if self._worker and self._worker._pronto:

            return                          # está vivo, nada a fazer

        if getattr(self, '_reiniciando', False):

            return                          # restart já em andamento

        if not self._project_path:

            return

        if self._worker:
            self._worker.encerrar()
            self._worker = None
        self._reiniciando = True

        def _fazer():
            worker = WorkerSubprocess(self._project_path)
            if worker.iniciar():
                self._worker = worker
                log.ok(_ARQ, "_tentar_reiniciar_worker", "Worker reiniciado")
            else:
                log.erro(_ARQ, "_tentar_reiniciar_worker", "Worker não reiniciou")
            self._reiniciando = False

        threading.Thread(target=_fazer, daemon=True).start()

    # ── API pública ───────────────────────────────────────────────────────────

    def interceptar_tecla(self, event) -> bool:
        key = event.key()

        # Esc fecha tanto o popup de sugestoes quanto o tooltip de
        # assinatura - antes so verificava self._lista, entao o Esc nao
        # fazia nada quando so o tooltip de parametros estava visivel.
        if key == Qt.Key_Escape:
            if self._lista.isVisible() or self._tooltip.isVisible():
                log.info(_ARQ, "interceptar_tecla",
                         f"Esc recebido — lista={self._lista.isVisible()} "
                         f"tooltip={self._tooltip.isVisible()} — fechando")
                self.fechar()

                return True

            if self._tabstop_ativo:
                self._cancelar_tabstops()

                return True

            return False

        if self._lista.isVisible():
            # Apenas Tab aceita a sugestao - Enter fica livre para quebrar
            # linha normalmente, mesmo com o popup aberto.
            if key == Qt.Key_Tab:
                self._lista.confirmar()

                return True

            if key in (Qt.Key_Return, Qt.Key_Enter):
                self.fechar()

                return False

            if key == Qt.Key_Up:
                self._lista.navegar(-1)

                return True

            if key == Qt.Key_Down:
                self._lista.navegar(1)

                return True

            return False

        # Sessao de tabstops ativa (snippet com $1, $2, $0 ja inserido):
        # Tab avanca, Shift+Tab volta. Fora da sessao, Tab segue o fluxo
        # normal do editor (indentacao).
        if self._tabstop_ativo and key in (Qt.Key_Tab, Qt.Key_Backtab):
            self._avancar_tabstop(-1 if key == Qt.Key_Backtab else 1)

            return True

        return False

    def _avancar_tabstop(self, direcao: int):
        novo_idx = self._tabstop_idx + direcao
        if not (0 <= novo_idx < len(self._tabstops)):
            self._cancelar_tabstops()

            return

        self._tabstop_idx = novo_idx
        self._editor.setTextCursor(self._tabstops[novo_idx])

    def _cancelar_tabstops(self):
        self._tabstop_ativo = False
        self._tabstops      = []
        self._tabstop_idx   = 0

    def ao_tecla_pressionada(self):
        self._bloqueado = False  # usuario digitou: libera o popup
        self._timer_complete.start()

    def ao_parentese_aberto(self):
        # Invalida uma consulta anterior antes de agendar a próxima. O timer
        # continua com o mesmo debounce; apenas respostas fora de contexto
        # deixam de poder reabrir o tooltip.
        self._geracao_signature += 1
        self._lista.fechar()
        self._timer_sig.start()

    def ao_parentese_fechado(self):
        self._geracao_signature += 1
        self._tooltip.fechar()
        self._timer_sig.stop()

    def fechar(self):
        # Incrementa a geracao e ativa bloqueio para descartar qualquer
        # thread Jedi em voo ou _calcular_complete enfileirado que poderia
        # reabrir o popup imediatamente apos o fechar() (ex: apos Esc).
        self._geracao  += 1
        self._geracao_signature += 1
        self._bloqueado = True
        self._lista.fechar()
        self._tooltip.fechar()
        self._timer_complete.stop()
        self._timer_sig.stop()

    def esta_visivel(self) -> bool:
        try:
            return self._lista.isVisible()
        except RuntimeError:
            return False

    def navegar_cima(self):  self._lista.navegar(-1)
    def navegar_baixo(self): self._lista.navegar(1)
    def confirmar(self):     self._lista.confirmar()
    # ── Completions + Snippets ────────────────────────────────────────────────

    # ⚠️  função grande (98 linhas)
    def _calcular_complete(self):
        # Se o popup foi fechado explicitamente (ex: Esc), nao reabre ate
        # o usuario digitar de novo (ao_tecla_pressionada limpa o flag).
        if self._bloqueado:
            return
        cursor      = self._editor.textCursor()
        bloco_texto = cursor.block().text()
        coluna      = cursor.positionInBlock()
        char_antes  = bloco_texto[coluna - 1] if 0 < coluna <= len(bloco_texto) else ""

        if char_antes in (" ", "\t", ")", "]", "}", ";"):
            self.fechar()

            return

        if char_antes == ",":
            self._timer_sig.start()
            self.fechar()

            return

        inicio = coluna
        while inicio > 0 and inicio <= len(bloco_texto) and (bloco_texto[inicio - 1].isalnum() or bloco_texto[inicio - 1] == "_"):
            inicio -= 1
        prefixo = bloco_texto[inicio:coluna]

        # IMP-07 — gatilho ':' abre popup exclusivo de emojis/símbolos
        _char_gatilho = (
            bloco_texto[inicio - 1]
            if 0 < inicio <= len(bloco_texto) else ""
        )
        if _char_gatilho == ":" and prefixo:
            _carregar_fontes_appdata()
            _prefixo_l = prefixo.lower()
            _pontuados = []
            for k, v in (_CACHE_FONTES.get("emojis") or {}).items():
                _s = _fuzzy_score(_prefixo_l, k.lower())
                if _s is not None:
                    _pontuados.append((_s, {"name": k, "type": "emoji",  "description": v,
                        "signature": "", "conteudo": v, "_extra_delete": 1}))
            for k, v in (_CACHE_FONTES.get("simbolos") or {}).items():
                _s = _fuzzy_score(_prefixo_l, k.lower())
                if _s is not None:
                    _pontuados.append((_s, {"name": k, "type": "symbol", "description": v,
                        "signature": "", "conteudo": v, "_extra_delete": 1}))
            _pontuados.sort(key=lambda par: par[0])
            _emo = [item for _, item in _pontuados]
            if _emo:
                self._lista.mostrar_sugestoes(_emo, prefixo)
            else:
                self.fechar()

            return   # modo emoji — não consulta Jedi nem outras fontes

        snippets_filtrados = []
        if prefixo:
            for nome, conteudo in self._snippets.items():
                if nome.startswith(prefixo):
                    snippets_filtrados.append({
                        "name":        nome,
                        "type":        "snippet",
                        "description": conteudo[:80],
                        "signature":   "",
                        "conteudo":    conteudo,
                    })
            # —— snippets built-in de marcação —————————————————
            _nomes_existentes = {s['name'] for s in snippets_filtrados}
            _MARCACOES_BUILTIN = {
                "TODO":      "TODO: $1",
                "LEMBRAR":   "LEMBRAR: $1",
                "CONSERTAR": "CONSERTAR: $1",
                "FAZER":     "FAZER: $1",
                "GAMBIARRA": "GAMBIARRA: $1",
            }
            for _nome, _conteudo in _MARCACOES_BUILTIN.items():
                if _nome.startswith(prefixo.upper()) and _nome not in _nomes_existentes:
                    snippets_filtrados.append({
                        "name":        _nome,
                        "type":        "snippet",
                        "description": f"marcação  # {_nome}:",
                        "signature":   "",
                        "conteudo":    _conteudo,
                    })

        codigo = self._editor.toPlainText()
        words_filtradas = _palavras_do_buffer(codigo, prefixo) if prefixo else []
        fontes_filtradas = _fontes_appdata_filtradas(prefixo) if prefixo else []
        auto_import_filtrados = _montar_auto_import(prefixo, codigo) if prefixo else []  # IMP-04

        # IMP-05 — file path completer: ativa dentro de strings
        _dentro_str, _path_full = _detectar_caminho(bloco_texto, coluna)
        _tem_path = _dentro_str and self._project_path and (
            prefixo or _path_full.endswith(("/", "\\")) or "*" in _path_full
        )
        path_filtradas = _arquivos_do_projeto(
            self._project_path, _path_full, prefixo
        ) if _tem_path else []

        # Jedi so roda para linguagens que declaram autocomplete = 'jedi'
        # (Python) - as demais usam so as fontes universais acima.
        self._tentar_reiniciar_worker()
        if not self._worker or not self._worker._pronto or not _jedi_permitido(self._editor):
            tudo = snippets_filtrados + fontes_filtradas + path_filtradas + auto_import_filtrados + words_filtradas
            if tudo:
                self._lista.mostrar_sugestoes(tudo, prefixo)

            return

        # Salva o código em arquivo temporário
        tmp_path = _salvar_codigo_temp(codigo)

        payload = {
            "action":   "complete",
            "tmp_path": tmp_path,   # worker lê daqui
            "line":     cursor.blockNumber() + 1,
            "col":      coluna,
            "path":     getattr(self._editor, "file_path", None),
        }

        self._verificar_worker()
        self._geracao += 1
        gen = self._geracao
        self._threads = self._threads_vivas()
        t = _ConsultaThread(self._worker, payload, gen, tmp_path, self._editor)
        t.resultado.connect(
            lambda r, g, p=prefixo, s=snippets_filtrados, w=words_filtradas, pth=path_filtradas, ft=fontes_filtradas, ai=auto_import_filtrados: self._aplicar_completions(r, g, p, s, w, pth, ft, ai)
        )
        reference("APPEND", "AC", self, "_threads",
                  before=None, after=t, editor=self._editor,
                  task=getattr(t, "_hein_diag_task", ""))
        self._threads.append(t)
        t.start()

    def _aplicar_completions(self, resposta: dict, geracao: int, prefixo: str, snippets: list, words: list = [], paths: list = [], fontes: list = [], auto_import: list = []):
        if geracao != self._geracao:

            return   # resposta antiga — descarta

        completions = resposta.get("completions", [])
        nomes_existentes = {s['name'] for s in snippets} | {c['name'] for c in completions}
        words_dedup = [w for w in words if w['name'] not in nomes_existentes]
        path_dedup  = [p for p in paths if p['name'] not in nomes_existentes]
        fontes_dedup = [ft for ft in fontes if ft['name'] not in nomes_existentes]
        auto_import_dedup = [a for a in auto_import if a['name'] not in nomes_existentes]  # IMP-04
        tudo = snippets + completions + fontes_dedup + path_dedup + auto_import_dedup + words_dedup
        if tudo:
            self._lista.mostrar_sugestoes(tudo, prefixo)
        else:
            self._lista.fechar()

    # ── Signatures ────────────────────────────────────────────────────────────

    def _calcular_signature(self):
        self._tentar_reiniciar_worker()
        if not self._worker or not self._worker._pronto or not _jedi_permitido(self._editor):

            return

        self._geracao_signature += 1
        geracao = self._geracao_signature
        cursor   = self._editor.textCursor()
        codigo   = self._editor.toPlainText()
        tmp_path = _salvar_codigo_temp(codigo)

        payload = {
            "action":   "signatures",
            "tmp_path": tmp_path,
            "line":     cursor.blockNumber() + 1,
            "col":      cursor.positionInBlock(),
            "path":     getattr(self._editor, "file_path", None),
        }

        self._threads = self._threads_vivas()
        t = _ConsultaThread(self._worker, payload, geracao, tmp_path, self._editor)
        reference("APPEND", "AC", self, "_threads",
                  before=None, after=t, editor=self._editor,
                  task=getattr(t, "_hein_diag_task", ""))
        t.resultado.connect(self._aplicar_signature)
        self._threads.append(t)
        t.start()

    def _aplicar_signature(self, resposta: dict, geracao: int):
        """Exibe apenas a resposta de assinatura do contexto ainda vigente."""
        if geracao != self._geracao_signature:
            return
        self._tooltip.mostrar(resposta.get("signatures", []))

    # ── Inserção ──────────────────────────────────────────────────────────────
    def _verificar_worker(self):
        """Reinicia o worker Jedi se morreu."""
        if not self._project_path:

            return

        if self._worker and self._worker._pronto:

            return

        log.info(_ARQ, "_reiniciar_worker", "Worker morto ou ausente — reiniciando")
        if self._worker:
            self._worker.encerrar()
        w = WorkerSubprocess(self._project_path)
        self._worker = w if w.iniciar() else None

    def _inserir_sugestao(self, nome: str, tamanho_prefixo: int, tipo: str, extra_delete: int = 0):
        cursor = self._editor.textCursor()
        for _ in range(tamanho_prefixo + extra_delete):
            cursor.deletePreviousChar()
        if tipo == "snippet":
            _MARCACOES_BUILTIN = {
                "TODO": "TODO: $1", "LEMBRAR": "LEMBRAR: $1",
                "CONSERTAR": "CONSERTAR: $1", "FAZER": "FAZER: $1",
                "GAMBIARRA": "GAMBIARRA: $1",
            }
            conteudo = self._snippets.get(nome) or _MARCACOES_BUILTIN.get(nome, nome)
            # Preserva indentação do ponto de inserção em snippets multiline
            if "\n" in conteudo:
                linha_atual = cursor.block().text()
                recuo = linha_atual[: len(linha_atual) - len(linha_atual.lstrip())]
                if recuo:
                    conteudo = conteudo.replace("\n", "\n" + recuo)
            # Marcadores $1, $2, ${1:texto}, $0 definem tabstops - pontos onde
            # o cursor para apos o Tab. $0 e sempre o ultimo. Com 2+ tabstops,
            # abre uma sessao: Tab/Shift+Tab navegam entre eles.
            texto_final, specs = _parsear_snippet(conteudo)
            pos_base = cursor.position()
            cursor.insertText(texto_final)
            if specs:
                doc = self._editor.document()
                tabstops = []
                for _numero, offset, tamanho in specs:
                    c = QTextCursor(doc)
                    c.setPosition(pos_base + offset)
                    if tamanho:
                        c.setPosition(pos_base + offset + tamanho, QTextCursor.KeepAnchor)
                    tabstops.append(c)
                if len(tabstops) > 1:
                    self._tabstops      = tabstops
                    self._tabstop_idx   = 0
                    self._tabstop_ativo = True
                cursor = tabstops[0]
        elif tipo in ("emoji", "symbol"):
            # Conteúdo (char real) vem do cache — não de self._snippets
            char = ((_CACHE_FONTES.get("emojis")  or {}).get(nome)
                 or (_CACHE_FONTES.get("simbolos") or {}).get(nome, nome))
            cursor.insertText(char)
        else:
            cursor.insertText(nome)
        self._editor.setTextCursor(cursor)

        # IMP-04 — auto-import: além do nome, insere a linha de import no
        # topo do arquivo, se ainda não existir.
        if tipo == "auto_import":
            stmt = _STDLIB_AUTO_IMPORT.get(nome)
            if stmt and not _ja_importado(self._editor.toPlainText(), nome, stmt):
                _inserir_import_no_topo(self._editor, stmt)
                log.info(_ARQ, "_inserir_sugestao", f"auto-import aplicado: {stmt!r}")

        self._editor.setFocus()

    def _threads_vivas(self) -> list:
        vivas = []
        for thread in self._threads:
            try:
                if thread.isRunning():
                    vivas.append(thread)
            except RuntimeError:
                pass
        return vivas

    def encerrar_threads(self):
        """Chamado pelo CodeEditor.encerrar_threads_bg() antes da aba fechar —
        para as QThreads de consulta Jedi e o worker antes que o editor seja
        destruído (senão: 'QThread: Destroyed while thread is still
        running" no meio do uso, não só ao fechar a IDE).

        FIX: adicionado terminate() como fallback apos quit()+wait(300).
        _ConsultaThread bloqueia em subprocess.readline() — quit() so
        para o event loop da thread, NAO interrompe chamadas bloqueantes.
        Sem terminate(), a thread ainda esta viva ao destruir o editor
        -> "QThread: Destroyed while thread is still running".
        """
        for t in list(self._threads):
            encerrar_thread(t, 300)
        reference("ZERO", "AC", self, "_threads",
                  before=self._threads, after=None, editor=self._editor)
        self._threads = []
        if self._worker:
            try:
                self._worker.encerrar()
            except Exception:
                pass

    def __del__(self):
        for t in self._threads:
            encerrar_thread(t, 300)
        if self._worker:
            self._worker.encerrar()
