# gerador_chaves.py
"""
Script Administrativo - Gerador de Chaves para a hein IDE.
Mantenha este arquivo seguro no seu computador/servidor de vendas.
"""
import hashlib

# ⚠️ DEVE SER EXATAMENTE O MESMO DO SEU 'gerenciador_licenca.py'
_SEGREDO_SALT = "HEIN_IDE_GOLDEN_KEY_2026"

def gerar_chave(hwid: str, email: str) -> str:
    # Padroniza os dados para evitar erros de digitação (espaços/letras maiúsculas)
    dados = f"{hwid.strip().upper()}:{email.strip().lower()}:{_SEGREDO_SALT}"
    sha = hashlib.sha256(dados.encode()).hexdigest().upper()

    # Formato amigável: XXXX-XXXX-XXXX-XXXX
    return f"{sha[0:4]}-{sha[4:8]}-{sha[8:12]}-{sha[12:16]}"

if __name__ == "__main__":
    print("=== GERADOR DE CHAVES - hein IDE ===")

    # Pegue o HWID que a janela de ativação da IDE exibiu para você
    hwid_cliente = input("Digite ou cole o HWID do cliente: ").strip()
    email_cliente = input("Digite o E-mail do cliente: ").strip()

    if not hwid_cliente or not email_cliente:
        print("Erro: HWID e Email são obrigatórios!")
    else:
        chave = gerar_chave(hwid_cliente, email_cliente)
        print("\n" + "="*40)
        print(f"CLIENTE: {email_cliente}")
        print(f"HWID:    {hwid_cliente}")
        print(f"CHAVE DE ATIVAÇÃO: {chave}")
        print("="*40 + "\n")
