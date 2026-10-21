# 📁 _EDITOR_/Editor_Hein/_autocomplete_hein.py
"""
GerenciadorAutocompleteHein — autocomplete filtrado para o Editor Caderno.

Diferenças em relação ao GerenciadorAutocomplete padrão:

  1. Sem tooltip de assinatura
       ao_parentese_aberto() → pass
       Editor Caderno não é código — parêntese não significa chamada de função.

  2. Resultados do Jedi filtrados
       Só aceita type == 'function' ou 'class' vindos do Jedi.
       Remove: keyword, statement, module, import, param, instance, auto_import.
       O usuário quer ver funções e classes que ele mesmo criou nos arquivos
       do projeto — não quer ver print, def, class, os.path, etc.

  3. Sem auto-import
       O parâmetro auto_import é ignorado e nunca inserido.
       Não faz sentido inserir "import os" num arquivo de texto .hein.
"""
from ..Autocomplete.autocomplete import GerenciadorAutocomplete


class GerenciadorAutocompleteHein(GerenciadorAutocomplete):
    """Autocomplete do Editor Caderno — sem Python-noise."""

    # Tipos de completion do Jedi aceitos para .hein
    _TIPOS_JEDI_HEIN = frozenset({"function", "class"})

    # ── API pública ───────────────────────────────────────────────────────────

    def ao_parentese_aberto(self):
        """Editor Caderno não é código — nenhum tooltip de assinatura."""
        pass

    # ── Inserção filtrada ─────────────────────────────────────────────────────

    def _aplicar_completions(
        self,
        resposta:    dict,
        geracao:     int,
        prefixo:     str,
        snippets:    list,
        words:       list = [],
        paths:       list = [],
        fontes:      list = [],
        auto_import: list = [],   # ignorado para .hein
    ):
        if geracao != self._geracao:
            return   # resposta antiga — descarta

        completions = resposta.get("completions", [])

        # Filtra resultados do Jedi: aceita apenas funções e classes.
        # Keywords Python (def, class, print, for, import…), módulos e
        # builtins ficam fora — ruído num arquivo de texto .hein.
        completions = [
            c for c in completions
            if c.get("type") in self._TIPOS_JEDI_HEIN
        ]

        nomes_existentes = (
            {s["name"] for s in snippets}
            | {c["name"] for c in completions}
        )
        words_dedup  = [w for w in words  if w["name"] not in nomes_existentes]
        path_dedup   = [p for p in paths  if p["name"] not in nomes_existentes]
        fontes_dedup = [ft for ft in fontes if ft["name"] not in nomes_existentes]

        # auto_import descartado — sem sentido num arquivo de texto .hein
        tudo = snippets + completions + fontes_dedup + path_dedup + words_dedup
        if tudo:
            self._lista.mostrar_sugestoes(tudo, prefixo)
        else:
            self._lista.fechar()
