from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean, Text
from Models.SQL_SERVER.Base import Base

class Manifesto(Base):
    __tablename__ = 'tb_manifesto'
    __table_args__ = {'schema': 'intec.dbo'}

    idcodigo = Column(Integer, primary_key=True)
    
    manifesto = Column(Integer)
    filialmanifesto = Column(String(8))
    filial = Column(String(2))
    
    dtemissao = Column(DateTime)
    dtsaida = Column(DateTime)
    
    # Veículo e Motorista
    codveiculo = Column(String(3))
    placaveic = Column(String(8))
    placa_carreta = Column(String(7))
    motorista = Column(String(30))
    motorista_cpf = Column(String(20))
    
    # Rota
    origem = Column(String(12))
    rotafilialdest = Column(String(12))
    
    # Status
    status_man = Column(String(30))
    cancelado = Column(String(1))
    
    # Totais
    qtdepallets = Column(Integer)
    qtdegaiolas = Column(Integer)
    
    filialctc = Column(String(10)) 
    motivo = Column(String(50))
    
class CteInfo(Base):
    __tablename__ = 'CTe_infCte'
    __table_args__ = {'schema': 'intec.dbo'}

    Id = Column(String(23), primary_key=True)
    
    chCTe = Column(String(44))
    nCT = Column(Numeric)
    serie = Column(String(3))
    dEmi = Column(DateTime)
    
    codSituacao = Column(String(10))
    descSituacao = Column(String(500))
    
    xmlReqEmiss = Column(Text) # Mapeado como Text pois é XML/Varchar(max)
    xmlRetEmiss = Column(Text)
    
    nProt = Column(Numeric)
    dhRecbto = Column(DateTime)