from flask_login import UserMixin

class UsuarioSistema(UserMixin):
    """
    Representa o usuário logado.
    Armazena apenas os dados essenciais para não precisar ir ao banco em toda verificação simples.
    """
    def __init__(self, Login, Nome, Email=None, Grupo=None, IdBanco=None):
        self.id = Login  # O Flask-Login usa isso como identificador na sessão (cookie)
        self.Login = Login
        self.Nome = Nome
        self.Email = Email
        self.Grupo = Grupo
        self.IdBanco = IdBanco # O ID numérico (PK) do SQL Server, útil para logs ou FKs

    def TemPermissao(self, PermissaoNecessaria):
        # Futuramente você pode validar baseado no self.Grupo
        pass