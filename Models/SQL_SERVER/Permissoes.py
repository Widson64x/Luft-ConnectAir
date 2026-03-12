from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from datetime import datetime
from Models.SQL_SERVER.Base import Base

class Tb_PLN_Sistema(Base):
    __tablename__ = "Tb_PLN_Sistema"
    __table_args__ = {"schema": "intec.dbo"}

    Id_Sistema = Column(Integer, primary_key=True, autoincrement=True)
    Nome_Sistema = Column(String(100), unique=True, nullable=False)
    Descricao_Sistema = Column(String(255))
    Ativo = Column(Boolean, default=True)

class Tb_PLN_Permissao(Base):
    __tablename__ = "Tb_PLN_Permissao"
    __table_args__ = {"schema": "intec.dbo"}

    Id_Permissao = Column(Integer, primary_key=True, autoincrement=True)
    Id_Sistema = Column(Integer, ForeignKey("intec.dbo.Tb_PLN_Sistema.Id_Sistema"), nullable=False)
    Chave_Permissao = Column(String(100), nullable=False)
    Descricao_Permissao = Column(String(255))
    Categoria_Permissao = Column(String(50))

class Tb_PLN_PermissaoGrupo(Base):
    __tablename__ = "Tb_PLN_PermissaoGrupo"
    __table_args__ = {"schema": "intec.dbo"}

    Id_Vinculo = Column(Integer, primary_key=True, autoincrement=True)
    Codigo_UsuarioGrupo = Column(Integer, nullable=False) # Sem FK para evitar erro cross-database
    Id_Permissao = Column(Integer, ForeignKey("intec.dbo.Tb_PLN_Permissao.Id_Permissao"))

class Tb_PLN_PermissaoUsuario(Base):
    __tablename__ = "Tb_PLN_PermissaoUsuario"
    __table_args__ = {"schema": "intec.dbo"}

    Id_Vinculo = Column(Integer, primary_key=True, autoincrement=True)
    Codigo_Usuario = Column(Integer, nullable=False) # Sem FK para evitar erro cross-database
    Id_Permissao = Column(Integer, ForeignKey("intec.dbo.Tb_PLN_Permissao.Id_Permissao"))
    Conceder = Column(Boolean, default=True)

class Tb_PLN_LogAcesso(Base):
    __tablename__ = "Tb_PLN_LogAcesso"
    __table_args__ = {"schema": "intec.dbo"}

    Id_Log = Column(Integer, primary_key=True, autoincrement=True)
    Id_Sistema = Column(Integer, ForeignKey("intec.dbo.Tb_PLN_Sistema.Id_Sistema"), nullable=True)
    Id_Usuario = Column(Integer, nullable=True)
    Nome_Usuario = Column(String(150))
    Rota_Acessada = Column(String(200))
    Metodo_Http = Column(String(10))
    Ip_Origem = Column(String(50))
    Permissao_Exigida = Column(String(100))
    Acesso_Permitido = Column(Boolean)
    Data_Hora = Column(DateTime, default=datetime.now)

    Parametros_Requisicao = Column(Text, nullable=True)
    Resposta_Acao = Column(Text, nullable=True)