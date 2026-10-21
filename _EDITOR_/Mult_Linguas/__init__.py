# _EDITOR_/Mult_Linguas/__init__.py
"""
LanguageManager — registro central de providers de linguagem.

Auto-descoberta: ao importar este módulo, escaneia subpastas de Mult_Linguas/
(exceto Base/) e registra qualquer módulo que exponha LANGUAGE_PROVIDER.

Uso:
    from _EDITOR_.Mult_Linguas import get_provider

    provider = get_provider('.py')     # → PythonProvider
    provider = get_provider('.json')   # → JSONProvider
    provider = get_provider('.xyz')    # → PythonProvider (padrão)
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path

from _EDITOR_.Mult_Linguas.Base.provider import LanguageProvider

# ── registro interno: {'.py': PythonProvider(), '.json': JSONProvider(), ...}
_registro: dict[str, LanguageProvider] = {}

# provider padrão para extensões não registradas (definido após descoberta)
_provider_padrao: LanguageProvider | None = None


def _descobrir() -> None:
    """
    Percorre subpastas de Mult_Linguas/ (exceto Base/) e registra providers.
    Chamado automaticamente na importação do módulo.
    """
    global _provider_padrao

    pasta_raiz = Path(__file__).parent

    for subpasta in sorted(pasta_raiz.iterdir()):
        if not subpasta.is_dir():
            continue
        if subpasta.name in ('Base', '__pycache__'):
            continue
        if not (subpasta / '__init__.py').exists():
            continue

        nome_modulo = f'_EDITOR_.Mult_Linguas.{subpasta.name}'
        try:
            mod = importlib.import_module(nome_modulo)
        except Exception as exc:  # pragma: no cover
            from _LOG_.log import log as _log
            _log.aviso("Mult_Linguas/__init__.py", "_descobrir",
                       f"falha ao importar provider '{nome_modulo}'", str(exc))
            continue

        provider = getattr(mod, 'LANGUAGE_PROVIDER', None)
        # Duck-typing em vez de isinstance — evita falha quando o mesmo módulo
        # é carregado por caminhos distintos (namespace packages sem __init__.py).
        if provider is None or not hasattr(provider, 'extensions') or not hasattr(provider, 'outline_mode'):
            continue

        for ext in provider.extensions:
            _registro[ext.lower()] = provider

        # Python é o padrão para extensões desconhecidas
        if subpasta.name == 'Python':
            _provider_padrao = provider


def register(provider: LanguageProvider) -> None:
    """
    Registra um provider manualmente (usado por extensões externas).
    Sobrescreve qualquer provider anterior para as mesmas extensões.
    """
    for ext in provider.extensions:
        _registro[ext.lower()] = provider


def get_provider(ext: str) -> LanguageProvider:
    """
    Retorna o provider para a extensão informada.
    ext pode ser '.py', 'py' ou o caminho completo do arquivo.

    Extensão desconhecida → PythonProvider (padrão).
    """
    # normaliza: aceita caminho completo, extensão com ou sem ponto
    ext = os.path.splitext(ext)[1] if '.' in ext[1:] else ext
    if not ext.startswith('.'):
        ext = '.' + ext

    provider = _registro.get(ext.lower())
    if provider is not None:
        return provider

    # Sem extensão (ex: Makefile, README sem .txt) → TextoProvider
    if ext == "." or ext == "":
        texto_pv = _registro.get(".txt")
        if texto_pv is not None:
            return texto_pv

    # fallback para o provider padrão (Python)
    if _provider_padrao is not None:
        return _provider_padrao

    # segurança: se Python ainda não foi carregado, retorna provider vazio
    return LanguageProvider()


def is_registered(ext: str) -> bool:
    """
    Retorna True se há um provider explicitamente registrado para a extensão.
    Usado por editor_dobramento para distinguir extensões conhecidas de desconhecidas.
    """
    if not ext.startswith('.'):
        ext = '.' + ext
    return ext.lower() in _registro


# ── executa a descoberta na importação do módulo ──────────────────────────────
_descobrir()
