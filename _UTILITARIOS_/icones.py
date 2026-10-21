# 📁 _UTILITARIOS_/icones.py
"""
Wrapper central para todos os ícones qtawesome da IDE hein.
Lê as cores diretamente do tema ativo — basta chamar icone_tema()
no lugar de qta.icon() para participar do hot-reload automático.
"""
import qtawesome as qta
from _CONFIGURA_ import COR_BTN_ICONE_TEXTO_qta

# 💡 tipo_opc = Literal["icone"] ← defina os valores válidos
def icone_tema(nome: str, tipo: str = "icone", **kwargs):
    """
    Substituto de qta.icon() que lê a cor do thema.json.

    tipo:
      "icone" → interface.icone  (única chave de cor de ícone no tema)

    Exemplo:
        icone_tema("mdi.play")   # cor lida de interface.icone
    """
    from _CONFIGURA_.gerenciador_tema import tema_global
    chave = f"interface.{tipo}"
    cor = kwargs.pop("color", None)          # usa color= explícito se passado
    if cor is None:
        cor = tema_global().cor(chave, COR_BTN_ICONE_TEXTO_qta)  # senão lê do tema

    return qta.icon(nome, color=cor, **kwargs)
