# 📁 _EDITOR_/Autocomplete/autocomplete_worker.py
# -*- coding: utf-8 -*-
"""
Roda como subprocess no Python do hein.
Recebe pedidos JSON via stdin — o código do usuário vai em arquivo temporário,
não no JSON, para evitar problemas com aspas e caracteres especiais.
"""
import os
import sys
import json
import traceback
try:
    import jedi
except ImportError:
    print(json.dumps({"error": "jedi_not_found"}), flush=True)
    sys.exit(1)

_RAIZ_hein  = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_CONFIG_PATH = os.path.join(_RAIZ_hein, "_CONFIGURA_", "autocomplete.json")

def _carregar_config() -> dict:
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:

            return json.load(f)

    except Exception:

        return {}

def _achar_site_packages(project_path: str, config: dict) -> list:
    amb  = config.get("ambiente", {})
    venv = amb.get("pasta_venv", ".venv")
    base = os.path.join(project_path, venv)
    encontrados = []
    win = os.path.join(base, "Lib", "site-packages")
    if os.path.isdir(win):
        encontrados.append(win)
    lib = os.path.join(base, "lib")
    if os.path.isdir(lib):
        for pasta in os.listdir(lib):
            sp = os.path.join(lib, pasta, "site-packages")
            if os.path.isdir(sp):
                encontrados.append(sp)

    return encontrados

# ⚠️  função grande (99 linhas) | except genérico vazio
def _handle(request: dict, config: dict) -> dict:
    action   = request.get("action")
    line     = request.get("line", 1)
    col      = request.get("col", 0)
    path     = request.get("path") or None
    proj     = request.get("project_path") or None
    tmp_path = request.get("tmp_path") or None

    # Fallback: se não tem project_path, usa a pasta do arquivo aberto
    if not proj and path:
        proj = os.path.dirname(os.path.abspath(path))

    # Lê o código do arquivo temporário
    if tmp_path and os.path.isfile(tmp_path):
        try:
            with open(tmp_path, encoding="utf-8") as f:
                code = f.read()
        except Exception as e:

            return {"completions": [], "erro": f"Erro ao ler arquivo temp: {e}"}

    else:
        code = request.get("code", "")

    kwargs = {"code": code}
    if path:
        kwargs["path"] = path
    if proj:
        try:
            kwargs["project"] = jedi.Project(
                path           = proj,
                added_sys_path = _achar_site_packages(proj, config),
            )
        except Exception as e:
            from _LOG_.log import log
            file=sys.stderr
            flush=True
            log.erro("autocomplete_worker.py", "[WORKER] Erro ao criar Project:",f" {e}")
            log.erro("autocomplete_worker.py", "file",file)
            log.erro("autocomplete_worker.py", "Wflush",flush)

    script = jedi.Script(**kwargs)

    if action == "complete":
        try:
            completions = script.complete(line, col)
        except Exception as e:

            return {"completions": [], "erro": str(e)}

        result = []
        for c in completions[:50]:
            tipo  = c.type or "statement"
            assin = ""
            desc  = ""
            if tipo == "function":
                try:
                    sigs = c.get_signatures()
                    if sigs:
                        assin = sigs[0].to_string()[:80]
                except Exception:
                    pass
            try:
                desc = c.docstring(raw=True)[:60]
            except Exception:
                pass
            result.append({
                "name":        c.name[:60],
                "type":        tipo,
                "description": desc,
                "signature":   assin,
            })

        return {"completions": result}

    elif action == "signatures":
        try:
            sigs = script.get_signatures(line, col)
        except Exception as e:

            return {"signatures": [], "erro": str(e)}

        result = []
        for s in sigs:
            params = [
                {"name": p.name[:40], "description": p.description[:40], "index": i}
                for i, p in enumerate(s.params)
            ]
            result.append({
                "name":          s.name[:60],
                "full":          s.to_string()[:120],
                "index":         s.index,
                "bracket_start": s.bracket_start,
                "params":        params,
            })

        return {"signatures": result}

    return {"erro": f"acao desconhecida: {action}"}

def main():
    config = _carregar_config()
    sys.stdout.write(json.dumps({"ready": True}) + "\n")
    sys.stdout.flush()

    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            request  = json.loads(raw_line)
            response = _handle(request, config)
        except Exception as e:
            response = {"erro": str(e), "traceback": traceback.format_exc()}

        try:
            linha = json.dumps(response, ensure_ascii=True) + "\n"
        except Exception as e:
            linha = json.dumps({"completions": [], "erro": f"Erro ao serializar: {e}"}) + "\n"

        sys.stdout.write(linha)
        sys.stdout.flush()

if __name__ == "__main__":
    main()
