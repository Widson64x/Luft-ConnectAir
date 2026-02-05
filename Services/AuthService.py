from ldap3 import Server, Connection, ALL, SIMPLE
from Models.SQL_SERVER.Usuario import Usuario, UsuarioGrupo
from Conexoes import ObterSessaoSqlServer
from Configuracoes import ConfiguracaoAtual
from Services.LogService import LogService # <--- Importação

class AuthService:
    """
    Serviço responsável pela autenticação via Active Directory e Sincronização com SQL Server.
    """

    @staticmethod
    def AutenticarNoAd(usuario, senha):
        """
        Valida credenciais no AD usando SIMPLE BIND.
        """
        # Bypass de Debug
        if ConfiguracaoAtual.DEBUG and senha == "admin":
            LogService.Warning("AuthService", f"Bypass de autenticação acionado para usuário '{usuario}'.")
            return True

        AD_SERVER = ConfiguracaoAtual.AD_SERVER
        AD_DOMAIN = ConfiguracaoAtual.AD_DOMAIN
        user_ad = f"{AD_DOMAIN}\\{usuario}"
        
        try:
            LogService.Debug("AuthService", f"Iniciando tentativa de bind LDAP para: {user_ad}")
            
            server = Server(AD_SERVER, get_info=ALL)
            conn = Connection(server, user=user_ad, password=senha, authentication=SIMPLE)
            
            if conn.bind():
                LogService.Info("AuthService", f"Autenticação AD bem-sucedida para: {usuario}")
                conn.unbind()
                return True
            else:
                LogService.Warning("AuthService", f"Falha de autenticação AD para: {usuario}. Credenciais inválidas.")
                return False
                
        except Exception as e:
            LogService.Error("AuthService", f"Exceção durante conexão LDAP para {usuario}", e)
            return False

    @staticmethod
    def BuscarUsuarioNoBanco(login):
        Sessao = ObterSessaoSqlServer()
        DadosUsuario = None

        try:
            LogService.Debug("AuthService", f"Consultando usuário '{login}' no SQL Server.")

            Resultado = Sessao.query(Usuario, UsuarioGrupo)\
                .outerjoin(UsuarioGrupo, Usuario.codigo_usuariogrupo == UsuarioGrupo.codigo_usuariogrupo)\
                .filter(Usuario.Login_Usuario == login)\
                .first()

            if Resultado:
                UsuarioEncontrado, GrupoEncontrado = Resultado
                sigla_grupo = GrupoEncontrado.Sigla_UsuarioGrupo if GrupoEncontrado else "VISITANTE"
                
                DadosUsuario = {
                    "id": UsuarioEncontrado.Codigo_Usuario,
                    "nome": UsuarioEncontrado.Nome_Usuario,
                    "email": UsuarioEncontrado.Email_Usuario,
                    "login": UsuarioEncontrado.Login_Usuario,
                    "grupo": sigla_grupo,
                    "id_grupo": UsuarioEncontrado.codigo_usuariogrupo,
                    "ativo": True 
                }
                LogService.Info("AuthService", f"Usuário '{login}' localizado no SQL. Grupo: {sigla_grupo}")
            else:
                LogService.Warning("AuthService", f"Usuário '{login}' autenticado no AD, mas inexistente no banco SQL.")

        except Exception as e:
            LogService.Error("AuthService", f"Erro de consulta SQL para usuário '{login}'", e)
        
        finally:
            if Sessao: Sessao.close()

        return DadosUsuario

    @staticmethod
    def ValidarAcessoCompleto(usuario, senha):
        if AuthService.AutenticarNoAd(usuario, senha):
            return AuthService.BuscarUsuarioNoBanco(usuario)
        return None