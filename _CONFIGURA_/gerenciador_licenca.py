# 📁 _CONFIGURA_/gerenciador_licenca.py



import os
import sys
import platform
import uuid
import hashlib
from _LOG_.log import log

_ARQ = "gerenciador_licenca.py"
# ⚠️ Mantenha essa palavra-chave em segredo absoluto! Ela é a assinatura da sua IDE.
_SEGREDO_SALT = "HEIN_IDE_GOLDEN_KEY_2026" 

def obter_hwid() -> str:
    """
    Descobre o ID único do computador do usuário de forma persistente.
    No Windows, lê o GUID único da instalação; nos outros, usa MAC address robusto.
    """
    try:
        if platform.system() == "Windows":
            import winreg
            chave = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            guid, _ = winreg.QueryValueEx(chave, "MachineGuid")
            
            return guid.strip().replace("{", "").replace("}", "").upper()
    except Exception as e:
        log.aviso(_ARQ, "obter_hwid", f"Falha ao ler registro do Windows, usando fallback. Erro: {e}")

    # Fallback seguro multiplataforma (Gera um hash baseado na CPU e Placa de Rede)
    hardware_info = f"{platform.processor()}-{platform.machine()}-{uuid.getnode()}"
    
    return hashlib.sha256(hardware_info.encode()).hexdigest().upper()[:36]

def gerar_chave_licenca(hwid: str, email: str) -> str:
    """
    Gera a assinatura criptográfica que valida o uso.
    Você usará essa mesma função no seu painel de vendas para gerar as chaves dos clientes!
    """
    # Junta o HWID do usuário + Email + seu segredo para ninguém conseguir forjar chaves
    dados_combina = f"{hwid.strip().upper()}:{email.strip().lower()}:{_SEGREDO_SALT}"
    sha = hashlib.sha256(dados_combina.encode()).hexdigest().upper()
    
    # Formata como uma chave de produto profissional: XXXX-XXXX-XXXX-XXXX
    return f"{sha[0:4]}-{sha[4:8]}-{sha[8:12]}-{sha[12:16]}"

def verificar_licenca_local() -> bool:
    """
    Verifica se os dados salvos no perfil.json batem com a máquina atual.
    """
    from _CONFIGURA_.gerenciador_perfil import obter_perfil
    perfil = obter_perfil()

    email = perfil.get("email", "").strip()
    chave_salva = perfil.get("ativacao", {}).get("chave", "").strip()
    
    if not email or not chave_salva:
        return False
        
    hwid_atual = obter_hwid()
    chave_esperada = gerar_chave_licenca(hwid_atual, email)
    
    return chave_salva == chave_esperada