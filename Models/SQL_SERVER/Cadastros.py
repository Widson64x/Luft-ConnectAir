from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from Models.SQL_SERVER.Base import Base

# ======================================================================
# SCHEMA: intec.dbo (Cadastros Gerais)
# ======================================================================

class AeroportoLocal(Base):
    __tablename__ = 'tb_aircadlocal'
    __table_args__ = {'schema': 'intec.dbo'}

    # O primeiro parâmetro do Column() é o nome exato no banco de dados. 
    # A variável é como chamaremos no Python (CamelCase).
    Id = Column('id', Integer, primary_key=True)
    Sigla = Column('sigla', String(3))
    Localidade = Column('localidade', String(255))
    Aeroporto = Column('aeroporto', String(255))
    Uf = Column('uf', String(2))
    RegiaoGeo = Column('regiaogeo', String(50))

class CompanhiaAerea(Base):
    __tablename__ = 'tb_aircadcia'
    __table_args__ = {'schema': 'intec.dbo'}

    IdCia = Column('id_Cia', Integer, primary_key=True)
    CodCia = Column('codcia', String(3))
    Fantasia = Column('fantasia', String(20))
    Cgc = Column('cgc', String(14)) # CNPJ
    StatusCia = Column('Status_Cia', Boolean)

class UnidadeFederativa(Base):
    __tablename__ = 'tb_caduf'
    __table_args__ = {'schema': 'intec.dbo'}

    Uf = Column('uf', String(2), primary_key=True)
    Cidade = Column('cidade', String(35)) # Capital ou referência
    RegiaoGeo = Column('regiaogeo', String(20))

class Praca(Base):
    __tablename__ = 'tb_pracas'
    __table_args__ = {'schema': 'intec.dbo'}

    IdPraca = Column('id_praca', Integer, primary_key=True)
    Codigo = Column('codigo', String(12))
    Tipo = Column('tipo', String(3))
    Cidade = Column('cidade', String(35))
    Uf = Column('uf', String(2))
    Status = Column('status', String(1))

class UnidadeResponsavel(Base):
    __tablename__ = 'tb_Unid_Responsavel'
    __table_args__ = {'schema': 'intec.dbo'}

    IdUnid = Column('id_unid', Integer, primary_key=True)
    CdUnid = Column('cd_unid', String(10))
    DsUnid = Column('ds_unid', String(50))
    CnpjUnid = Column('cnpj_unid', String(14))
    DsEmailUnid = Column('ds_email_unid', String(500))
    CidadeRetira = Column('cidaderetira', String(100))
    UfRetira = Column('ufretira', String(2))

# ======================================================================
# SCHEMA: luftinforma.dbo (Tabelas Legadas - Planejamento)
# ======================================================================

class Municipio(Base):
    __tablename__ = 'Municipio'
    __table_args__ = {'schema': 'luftinforma.dbo'}

    Codigo_Municipio = Column(Numeric, primary_key=True)
    Nome_Municipio = Column(String(100))
    
    # Relacionamentos
    Clientes = relationship("Cliente", back_populates="Municipio")

class Operador(Base):
    __tablename__ = 'Operador'
    __table_args__ = {'schema': 'luftinforma.dbo'}

    Codigo_Operador = Column(Integer, primary_key=True)
    Nome_Operador = Column(String(100))
    Codigo_Funcao = Column(Integer)

class ClienteGrupo(Base):
    __tablename__ = 'ClienteGrupo'
    __table_args__ = {'schema': 'luftinforma.dbo'}

    Codigo_ClienteGrupo = Column(Integer, primary_key=True)
    Descricao_ClienteGrupo = Column(String(100))

class Empresa(Base):
    __tablename__ = 'Empresa'
    __table_args__ = {'schema': 'luftinforma.dbo'}

    Codigo_Empresa = Column(Integer, primary_key=True)
    Codigo_EmpresaMatriz = Column(Integer, ForeignKey('luftinforma.dbo.Empresa.Codigo_Empresa'))
    Nome_FantasiaEmpresa = Column(String(100))
    CNPJ_Empresa = Column(String(20))
    Opcao_EmpresaAtiva = Column(Boolean)

class Cliente(Base):
    __tablename__ = 'Cliente'
    __table_args__ = {'schema': 'luftinforma.dbo'}

    Codigo_Cliente = Column(Integer, primary_key=True)
    Nome_RazaoSocialCliente = Column(String(100))
    Nome_FantasiaCliente = Column(String(100))
    CNPJ_Cliente = Column(String(20))
    
    # Endereçamento
    Endereco_Cliente = Column(String(100))
    Numero_Cliente = Column(Integer)
    EndComp_Cliente = Column(String(100))
    Bairro_Cliente = Column(String(30))
    Cep_Cliente = Column(String(10))
    
    # Chaves Estrangeiras
    Codigo_Municipio = Column(Numeric, ForeignKey('luftinforma.dbo.Municipio.Codigo_Municipio'))
    Codigo_GerenteComercial = Column(Integer, ForeignKey('luftinforma.dbo.Operador.Codigo_Operador'))
    Codigo_ClienteGrupo = Column(Integer, ForeignKey('luftinforma.dbo.ClienteGrupo.Codigo_ClienteGrupo'))

    # Relacionamentos
    Municipio = relationship("Municipio", back_populates="Clientes")
    ServicosContratados = relationship("ClienteServicoContratado", back_populates="Cliente")

class ClienteServicoContratado(Base):
    __tablename__ = 'ClienteServicoContratado'
    __table_args__ = {'schema': 'luftinforma.dbo'}

    Codigo_Cliente = Column(Integer, ForeignKey('luftinforma.dbo.Cliente.Codigo_Cliente'), primary_key=True)
    Codigo_Empresa = Column(Integer, ForeignKey('luftinforma.dbo.Empresa.Codigo_Empresa'), primary_key=True)
    
    Opcao_ServicoContratado = Column(String(1)) # 't' para Transporte, etc.
    Opcao_TipoArmazenagem = Column(String(2)) # 'FL', 'DP', 'AG'
    PermiteTroca_Gelo = Column(String(1)) # 'N', 'S', 'A'
    OtdMeta = Column(Numeric)
    
    Data_InicioOperacao = Column(DateTime)
    Data_FimOperacao = Column(DateTime, nullable=True)

    # Relacionamentos
    Cliente = relationship("Cliente", back_populates="ServicosContratados")