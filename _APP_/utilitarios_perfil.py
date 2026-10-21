# 📁 _APP_/utilitarios_perfil.py
"""
Utilitários para exibir saudações dinâmicas conforme a hora do dia.
"""

from datetime import datetime
from _CONFIGURA_.gerenciador_perfil import obter_nome_usuario

def gerar_saudacao() -> str:
    hora = datetime.now().hour
    nome = obter_nome_usuario()

    if 5 <= hora < 12:
        return f"Bom dia, {nome}"

    elif 12 <= hora < 18:
        return f"Boa tarde, {nome}"

    else:
        return f"Boa noite, {nome}"

def obter_periodo_do_dia() -> str:
    hora = datetime.now().hour

    if 5 <= hora < 12:
        return "manhã"

    elif 12 <= hora < 18:
        return "tarde"

    else:
        return "noite"

# ⚠️  except genérico vazio
def saudacao_longa() -> str:
    import locale
    try:
        locale.setlocale(locale.LC_TIME, "pt_BR.UTF-8")
    except:
        try:
            locale.setlocale(locale.LC_TIME, "pt_BR")
        except:
            pass

    agora = datetime.now()
    nome = obter_nome_usuario()
    data_formatada = agora.strftime("%A, %d de %B de %Y").capitalize()

    if 5 <= agora.hour < 12:
        periodo = "manhã"
    elif 12 <= agora.hour < 18:
        periodo = "tarde"
    else:
        periodo = "noite"

    return f"Bom {periodo}, {nome}!\n{data_formatada}"
