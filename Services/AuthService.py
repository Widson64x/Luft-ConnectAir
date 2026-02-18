from ldap3 import Server, Connection, ALL, SIMPLE
from sqlalchemy import or_
from Models.SQL_SERVER.Usuario import Usuario, UsuarioGrupo
from Conexoes import ObterSessaoSqlServer
from Configuracoes import ConfiguracaoAtual
from Services.LogService import LogService

class AuthService:
    """
    Serviço responsável pela autenticação via Active Directory e Sincronização com SQL Server.
    Suporta login via Nome de Usuário ou E-mail.
    """

    @staticmethod
    def AutenticarNoAd(usuario, senha):
        """
        Valida credenciais no AD usando SIMPLE BIND.
        Espera receber o LOGIN (username), não o e-mail.
        """
        # Bypass de Debug
        if ConfiguracaoAtual.DEBUG and senha == "admin":
            LogService.Warning("AuthService", f"Bypass de autenticação acionado para usuário '{usuario}'.")
            return True

        AD_SERVER = ConfiguracaoAtual.AD_SERVER
        AD_DOMAIN = ConfiguracaoAtual.AD_DOMAIN

        # Monta o usuário no formato DOMINIO\usuario
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
    def BuscarUsuarioNoBanco(identificador):
        """
        Busca usuário pelo Login OU pelo E-mail.
        Retorna os dados se encontrar.
        """
        Sessao = ObterSessaoSqlServer()
        DadosUsuario = None

        try:
            LogService.Debug("AuthService", f"Consultando identificador '{identificador}' (Login ou Email) no SQL Server.")

            # CORREÇÃO: Removido o filtro .filter(Usuario.Ativo == True)
            Resultado = Sessao.query(Usuario, UsuarioGrupo) \
                .outerjoin(UsuarioGrupo, Usuario.codigo_usuariogrupo == UsuarioGrupo.codigo_usuariogrupo) \
                .filter(or_(Usuario.Login_Usuario == identificador, Usuario.Email_Usuario == identificador)) \
                .first()

            if Resultado:
                UsuarioEncontrado, GrupoEncontrado = Resultado
                sigla_grupo = GrupoEncontrado.Sigla_UsuarioGrupo if GrupoEncontrado else "VISITANTE"

                DadosUsuario = {
                    "id": UsuarioEncontrado.Codigo_Usuario,
                    "nome": UsuarioEncontrado.Nome_Usuario,
                    "email": UsuarioEncontrado.Email_Usuario,
                    "login": UsuarioEncontrado.Login_Usuario, # Login real para o AD
                    "grupo": sigla_grupo,
                    "id_grupo": UsuarioEncontrado.codigo_usuariogrupo,
                    "ativo": True # Assumimos True já que não há coluna no banco para validar
                }
                LogService.Info("AuthService", f"Usuário localizado no SQL via '{identificador}'. Login real: {UsuarioEncontrado.Login_Usuario}")
            else:
                LogService.Warning("AuthService", f"Identificador '{identificador}' não encontrado no banco SQL.")

        except Exception as e:
            LogService.Error("AuthService", f"Erro de consulta SQL para '{identificador}'", e)

        finally:
            if Sessao: Sessao.close()

        return DadosUsuario

    @staticmethod
    def ValidarAcessoCompleto(identificador, senha):
        """
        1. Busca no Banco para traduzir "E-mail" -> "Login" (se necessário).
        2. Tenta autenticar no AD com o Login encontrado.
        """

        # Passo 1: Verifica se o usuário existe no nosso banco (pelo login OU email)
        DadosUsuario = AuthService.BuscarUsuarioNoBanco(identificador)

        if DadosUsuario:
            LoginReal = DadosUsuario['login']

            # Passo 2: Tenta validar a senha desse login no AD
            if AuthService.AutenticarNoAd(LoginReal, senha):
                return DadosUsuario
            else:
                # Usuário existe, mas senha está errada
                return None

        # Usuário nem existe no banco
        return None