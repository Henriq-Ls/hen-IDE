# 📁 _APPDATA_/backup.py
"""
_APPDATA_/backup.py

Rotação automática de backups das configurações globais da hein.

Funciona assim:
  - Os arquivos ativos (configurar.json, atalhos.json, etc.) vivem em
    AppData/hein/configuracoes/ (nao em _CONFIGURA_/).
    O tema nao entra aqui: vive em AppData/temas/ e ja tem seu proprio
    backup automatico (.bak) a cada carregamento.
  - A cada fechamento da IDE, cada arquivo ativo é copiado para
    AppData/_conf_bakup/<nome>_YYYYMMDD_HHMMSS.<ext>
  - Quando o número de cópias por arquivo ultrapassa MAX_CÓPIAS, as mais antigas
    são removidas (rotação FIFO).

Chamada pública:
    from _APPDATA_.backup import fazer_backup
    fazer_backup()   # sem parâmetros — lê tudo de _CONFIGURA_ e appdata

Regras:
  - stdlib puro, sem PySide6
  - import de _LOG_.log é lazy
  - falha silenciosa em cada arquivo — um erro não impede os demais
"""

import os
import shutil
from datetime import datetime
# ─── Quantas cópias manter por arquivo ───────────────────────────────────────
MAX_COPIAS: int = 5

# ─── Arquivos a copiar: (caminho relativo em _CONFIGURA_, extensão) ──────────
# Adicionado via _MAPA_ARQUIVOS em vez de hardcode inline para facilitar extensão.

_MAPA_ARQUIVOS: list[tuple[str, str]] = [
    # "thema.json" nao entra mais aqui: nao existe mais copia ativa solta na
    # raiz do AppData. O tema ativo vive em AppData/temas/ e ja recebe seu
    # proprio ".bak" automatico a cada carregamento (gerenciador_tema.py).
    ("configurar.json",  ".json"),
    ("atalhos.json",     ".json"),
    ("autocomplete.json",".json"),
]

# ─── API pública ──────────────────────────────────────────────────────────────

def fazer_backup() -> list[str]:
    """
    Copia cada arquivo de configuração ativo para _conf_bakup/ com timestamp,
    depois rotaciona mantendo no máximo MAX_COPIAS por arquivo.

    Retorna lista de paths dos backups criados.
    Falhas individuais são silenciosas — registradas via log quando possível.
    """
    from _APPDATA_ import appdata
    pasta_bakup = appdata.conf_bakup
    pasta_raiz  = appdata.configuracoes  # IMP-03: JSONs ativos vivem em AppData/configuracoes/

    try:
        os.makedirs(pasta_bakup, exist_ok=True)
    except Exception:

        return []

    criados: list[str] = []
    agora = datetime.now().strftime("%Y%m%d_%H%M%S")

    for nome_arquivo, ext in _MAPA_ARQUIVOS:
        src = os.path.join(pasta_raiz, nome_arquivo)  # IMP-03
        if not os.path.isfile(src):
            continue

        # Nome do backup: "thema_20260628_143000.json"
        base = nome_arquivo[: nome_arquivo.rfind(".")]   # sem extensão
        dst  = os.path.join(pasta_bakup, f"{base}_{agora}{ext}")

        try:
            shutil.copy2(src, dst)
            criados.append(dst)
        except Exception as e:
            _log_aviso(f"Falha ao copiar {nome_arquivo}", str(e))
            continue

        _rotacionar(pasta_bakup, base, ext)

    if criados:
        _log_ok(f"{len(criados)} backup(s) criado(s) em _conf_bakup/")

    return criados

# ─── Helpers internos ─────────────────────────────────────────────────────────

def _rotacionar(pasta: str, base: str, ext: str) -> None:
    """
    Remove os backups mais antigos de *base* quando o total ultrapassa MAX_COPIAS.
    Padrão de nome esperado: <base>_YYYYMMDD_HHMMSS<ext>
    """
    try:
        prefixo = f"{base}_"
        candidatos = [
            os.path.join(pasta, f)
            for f in os.listdir(pasta)
            if f.startswith(prefixo) and f.endswith(ext)
        ]
        candidatos.sort()   # sort lexicográfico = cronológico (YYYYMMDD_HHMMSS)

        while len(candidatos) > MAX_COPIAS:
            mais_antigo = candidatos.pop(0)
            try:
                os.remove(mais_antigo)
            except Exception as e:
                _log_aviso(f"Falha ao remover backup antigo: {mais_antigo}", str(e))
    except Exception as e:
        _log_aviso("_rotacionar falhou", str(e))

# ⚠️  except genérico vazio
def _log_ok(msg: str) -> None:
    try:
        from _LOG_.log import log
        log.ok("backup", "fazer_backup", msg)
    except Exception:
        pass

# ⚠️  except genérico vazio
def _log_aviso(msg: str, detalhe: str = "") -> None:
    try:
        from _LOG_.log import log
        log.aviso("backup", "fazer_backup", msg, detalhe)
    except Exception:
        pass
