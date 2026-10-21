# 📁 _CONFIGURA_/gerenciador_templates.py
"""
Salva e carrega os templates de arquivos padrão para novos projetos.
Arquivo: PASTA_APPDATA/templates_projeto.json

Formato de cada template (arquivo):
  { "tipo": "arquivo", "nome": "main", "ext": ".py", "conteudo": "..." }

Formato de template pasta:
  { "tipo": "pasta", "nome": "src", "filhos": [
      { "tipo": "arquivo", "nome": "main", "ext": ".py", "conteudo": "..." }
  ]}

Retrocompatibilidade: entradas sem campo "tipo" são tratadas como "arquivo".
"""
import json
import os
from _CONFIGURA_ import PASTA_APPDATA
_ARQUIVO = os.path.join(PASTA_APPDATA, "templates_projeto.json")

_PADRAO = [
    {
        "tipo": "arquivo",
        "nome": "main",
        "ext": ".py",
        "conteudo": (
            "# 📁 main.py\n\n\n"
            "def main():\n"
            '    print("Olá, mundo!")\n\n\n'
            'if __name__ == "__main__":\n'
            "    main()\n"
        ),
    },
]

def _normalizar_item(item: dict) -> None:
    """Garante campos obrigatórios em cada entrada (retrocompatibilidade)."""
    # Entradas antigas sem "tipo" são arquivos
    item.setdefault("tipo", "arquivo")
    item.setdefault("conteudo", "")
    # Para pastas, normalizar filhos recursivamente
    for filho in item.get("filhos", []):
        filho.setdefault("tipo", "arquivo")
        filho.setdefault("conteudo", "")

# ⚠️  except genérico vazio
def carregar() -> list[dict]:
    try:
        with open(_ARQUIVO, "r", encoding="utf-8") as f:
            dados = json.load(f)
        if isinstance(dados, list):
            for item in dados:
                _normalizar_item(item)
            return dados

    except Exception:
        pass

    return [dict(t) for t in _PADRAO]

def salvar(templates: list[dict]) -> None:
    os.makedirs(PASTA_APPDATA, exist_ok=True)
    with open(_ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)
