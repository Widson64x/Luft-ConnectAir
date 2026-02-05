from flask_login import UserMixin
# Importação feita dentro do método para evitar Ciclo de Importação (Circular Import)

class UsuarioSistema(UserMixin):
    """
    Representa o usuário logado na sessão.
    """
    def __init__(self, Login, Nome, Email=None, Grupo=None, IdBanco=None, Id_Grupo_Banco=None):
        self.id = Login
        self.Login = Login
        self.Nome = Nome
        self.Email = Email
        self.Grupo = Grupo
        self.IdBanco = IdBanco # ID do Usuário (LogAcesso / PermissaoUsuario)
        self.Id_Grupo_Banco = Id_Grupo_Banco # ID do Grupo (PermissaoGrupo)
        
        # Cache simples para não consultar o banco 50x na mesma requisição
        self._cache_permissoes = {} 

    def TemPermissao(self, ChavePermissao):
        """
        Verifica se o usuário possui a permissão solicitada.
        Uso no Template: {% if current_user.TemPermissao('sistema.admin') %}
        """
        # 1. Se já verificamos essa chave nessa requisição, retorna do cache
        if ChavePermissao in self._cache_permissoes:
            return self._cache_permissoes[ChavePermissao]

        # 2. Importa o serviço aqui dentro (Lazy Import) para não travar o App.py
        from Services.PermissaoService import PermissaoService
        
        # 3. Verifica no banco
        Tem = PermissaoService.VerificarPermissao(self, ChavePermissao)
        
        # 4. Guarda no cache e retorna
        self._cache_permissoes[ChavePermissao] = Tem
        return Tem