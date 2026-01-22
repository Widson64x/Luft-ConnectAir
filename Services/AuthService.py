import os
from ldap3 import Server, Connection, SIMPLE, core

# Configurações do Active Directory (buscando de variáveis de ambiente ou padrão)
LDAP_SERVER = os.getenv("LDAP_SERVER", "luftfarma.com.br")
LDAP_DOMAIN = os.getenv("LDAP_DOMAIN", "luftfarma")

def AutenticarAd(Usuario, Senha):
    """
    Realiza a tentativa de login no servidor LDAP (Active Directory).
    Retorna True se a senha estiver correta, False caso contrário.
    """
    if not Senha:
        return False
        
    # Formata o usuário como 'DOMINIO\usuario'
    FullUser = f'{LDAP_DOMAIN}\\{Usuario}'
    
    try:
        # Tenta conectar ao servidor LDAP
        Servidor = Server(LDAP_SERVER, port=389, use_ssl=False, get_info=None)
        
        # Tenta logar (auto_bind=True executa o bind imediatamente)
        Conexao = Connection(Servidor, user=FullUser, password=Senha, authentication=SIMPLE, auto_bind=True)
        
        print(f"✅ [AUTH AD] Usuário '{Usuario}' autenticado com sucesso!")
        Conexao.unbind() # Fecha a conexão LDAP
        return True
        
    except core.exceptions.LDAPBindError as e:
        print(f"❌ [AUTH AD] Falha de login para '{Usuario}': {e}")
        return False
    except Exception as e:
        print(f"❌ [AUTH AD] Erro de conexão LDAP: {e}")
        return False