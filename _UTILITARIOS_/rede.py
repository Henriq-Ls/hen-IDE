# 📁 _UTILITARIOS_/rede.py
"""
Utilitários de verificação de conectividade.
Usa apenas socket (built-in do Python — não instalar nada).
"""
import socket


def tem_internet(host: str = "8.8.8.8", porta: int = 53,
                 timeout: float = 3.0) -> bool:
    """
    Verifica se há conexão com a internet tentando uma conexão
    TCP com o DNS público do Google (8.8.8.8:53).

    - Rápido: retorna em milissegundos quando há conexão.
    - Seguro: timeout máximo de 3 segundos, sem travar a UI.
    - Leve: zero dependências externas, socket é built-in.

    Returns:
        True  → há internet.
        False → sem internet ou firewall bloqueando.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, porta))
        sock.close()
        return True
    except (socket.error, OSError):
        return False
