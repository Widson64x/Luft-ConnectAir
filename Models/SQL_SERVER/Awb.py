from sqlalchemy import Column, Integer, String, DateTime, Numeric, Date, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Awb(Base):
    __tablename__ = 'tb_airAWB'
    __table_args__ = {'schema': 'intec.dbo'}

    # Chave Primária
    codawb = Column(String(15), primary_key=True)

    # Dados Gerais
    awb = Column(String(15))
    dig = Column(String(1))
    cia = Column(String(3))
    nomecia = Column(String(100))
    cgccia = Column(String(14))
    filial = Column(String(2))
    data = Column(DateTime)
    hora = Column(String(8))
    
    # Remetente / Expedidor
    nomeexp = Column(String(60))
    cnpjexp = Column(String(14))
    cidadexp = Column(String(60))
    ufexp = Column(String(2))
    
    # Destinatário
    nomedes = Column(String(60))
    cnpjdes = Column(String(14))
    cidadedes = Column(String(60))
    ufdes = Column(String(50)) # No CSV está varchar(50)
    
    # Rota e Aeroportos
    siglaorigem = Column(String(3))
    aeroportoorigem = Column(String(50))
    siglades = Column(String(3))
    aeroportodestino = Column(String(50))
    
    # Valores e Pesos
    volumes = Column(Numeric)
    pesoreal = Column(Numeric)
    pesocubado = Column(Numeric)
    valmerc = Column(Numeric)
    fretetotal = Column(Numeric)
    
    # Status e Controle
    ENTREGUE = Column(String(1))
    cancelado = Column(String(1))
    canc_motivo = Column(String(250))
    Data_Importacao = Column(DateTime)
    nOca = Column(String(100))
    chCTe_AWB = Column(String(44))

class AwbStatus(Base):
    __tablename__ = 'TB_AWB_STATUS'
    __table_args__ = {'schema': 'intec.dbo'}

    # Chave Composta (Log)
    CODAWB = Column(String(15), primary_key=True)
    STATUS_AWB = Column(String(50), primary_key=True)
    DATAHORA_STATUS = Column(DateTime, primary_key=True)
    
    CIA = Column(String(2))
    LOCAL_STATUS = Column(String(50))
    VOO = Column(String(20))
    VOLUMES = Column(Integer)
    FILIAL = Column(String(2))
    DIG = Column(String(1))
    Usuario = Column(String(30))
    TIPO_INCLUSAO = Column(String(1))

class AwbNota(Base):
    __tablename__ = 'tb_airAWBnota'
    __table_args__ = {'schema': 'intec.dbo'}

    Id = Column(Integer, primary_key=True) # Identificado ID no CSV
    codawb = Column(String(15))
    filialctc = Column(String(10))
    nota = Column(String(300))
    serie = Column(String(3))
    valor = Column(Numeric)