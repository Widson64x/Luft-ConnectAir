from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from datetime import datetime
from Models.SQL_SERVER.Base import Base

# --- ATENÇÃO ---
# Como a conexão principal do App é com o banco 'LuftInforma' (ERP),
# precisamos usar 'schema="intec.dbo"' para acessar as tabelas do banco 'intec'
# via Cross-Database Query.

class Tb_PLN_Permissao(Base):
    __tablename__ = "Tb_PLN_Permissao"
    __table_args__ = {"schema": "intec.dbo"} # <--- Mágica aqui

    Id_Permissao = Column(Integer, primary_key=True, autoincrement=True)
    Chave_Permissao = Column(String(100), unique=True, nullable=False)
    Descricao_Permissao = Column(String(255))
    Categoria_Permissao = Column(String(50))

class Tb_PLN_PermissaoGrupo(Base):
    __tablename__ = "Tb_PLN_PermissaoGrupo"
    __table_args__ = {"schema": "intec.dbo"}

    Id_Vinculo = Column(Integer, primary_key=True, autoincrement=True)
    # FK aponta para a tabela 'usuariogrupo' do banco padrão (LuftInforma)
    Codigo_UsuarioGrupo = Column(Integer, ForeignKey("usuariogrupo.codigo_usuariogrupo")) 
    # FK aponta para a tabela local 'Tb_PLN_Permissao' (intec)
    Id_Permissao = Column(Integer, ForeignKey("intec.dbo.Tb_PLN_Permissao.Id_Permissao"))

class Tb_PLN_PermissaoUsuario(Base):
    __tablename__ = "Tb_PLN_PermissaoUsuario"
    __table_args__ = {"schema": "intec.dbo"}

    Id_Vinculo = Column(Integer, primary_key=True, autoincrement=True)
    # FK aponta para a tabela 'usuario' do banco padrão (LuftInforma)
    Codigo_Usuario = Column(Integer, ForeignKey("usuario.Codigo_Usuario")) 
    Id_Permissao = Column(Integer, ForeignKey("intec.dbo.Tb_PLN_Permissao.Id_Permissao"))
    Conceder = Column(Boolean, default=True)

class Tb_PLN_LogAcesso(Base):
    __tablename__ = "Tb_PLN_LogAcesso"
    __table_args__ = {"schema": "intec.dbo"}

    Id_Log = Column(Integer, primary_key=True, autoincrement=True)
    Id_Usuario = Column(Integer, nullable=True)
    Nome_Usuario = Column(String(150))
    Rota_Acessada = Column(String(200))
    Metodo_Http = Column(String(10))
    Ip_Origem = Column(String(50))
    Permissao_Exigida = Column(String(100))
    Acesso_Permitido = Column(Boolean)
    Data_Hora = Column(DateTime, default=datetime.now)