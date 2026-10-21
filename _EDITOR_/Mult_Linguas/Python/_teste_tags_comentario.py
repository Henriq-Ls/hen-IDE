#al: bloco de autenticação -- fundo azul (título), "al" fica ativo em modo FUNDO
def autenticar(usuario, senha):
    #: continua fundo azul (herda fundo do #al: acima)
    token = gerar_token(usuario)
    return token


#vo: bloco de erro critico -- fundo vermelho (título), "vo" ativo em modo FUNDO
def levantar_erro(msg):
    #: continua fundo vermelho
    raise Exception(msg)


#ve: bloco de validação -- fundo verde (título), "ve" ativo em modo FUNDO
def validar_dados(dados):
    #: continua fundo verde
    if not dados:
        return False
    return True


def outra_funcao_qualquer():
    # comentário normal, sem tag -- continua cinza/itálico de sempre
    #al; essa linha é só fonte azul (referência pontual), "al" vira ativo em modo FONTE
    #: agora herda FONTE azul (não mais fundo!) -- porque o #al; é o mais próximo acima
    pass


#ao: bloco de configuração -- fundo amarelo (título), "ao" ativo em modo FUNDO
CONFIG = {
    "debug": True,
}
#: ainda fundo amarelo aqui embaixo, mesma cadeia
