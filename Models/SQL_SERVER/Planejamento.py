from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class PlanejamentoCabecalho(Base):
    __tablename__ = 'Tb_PLN_PlanejamentoCabecalho'
    __table_args__ = {'schema': 'intec.dbo'}

    IdPlanejamento = Column(Integer, primary_key=True, autoincrement=True)
    DataCriacao = Column(DateTime, default=datetime.now)
    UsuarioCriacao = Column(String(50)) 
    Status = Column(String(20), default='Rascunho')
    AeroportoOrigem = Column(String(3)) 
    AeroportoDestino = Column(String(3)) 
    TotalVolumes = Column(Integer, default=0)
    TotalPeso = Column(Numeric(10,2), default=0.00)
    TotalValor = Column(Numeric(15,2), default=0.00)

    Itens = relationship("PlanejamentoItem", back_populates="Cabecalho", cascade="all, delete-orphan")
    Trechos = relationship("PlanejamentoTrecho", back_populates="Cabecalho", cascade="all, delete-orphan")

class PlanejamentoItem(Base):
    __tablename__ = 'Tb_PLN_PlanejamentoItem'
    __table_args__ = {'schema': 'intec.dbo'}

    IdItem = Column(Integer, primary_key=True, autoincrement=True)
    IdPlanejamento = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_PlanejamentoCabecalho.IdPlanejamento'))
    Filial = Column(String(10))
    Serie = Column(String(5))
    Ctc = Column(String(20))
    DataEmissao = Column(DateTime)
    Hora = Column(String(5))
    Remetente = Column(String(100))
    Destinatario = Column(String(100))
    OrigemCidade = Column(String(50))
    DestinoCidade = Column(String(50))
    Volumes = Column(Integer)
    PesoTaxado = Column(Numeric(10,3))
    ValMercadoria = Column(Numeric(15,2))
    IndConsolidado = Column(Boolean, default=False)
    
    Cabecalho = relationship("PlanejamentoCabecalho", back_populates="Itens")

class PlanejamentoTrecho(Base):
    __tablename__ = 'Tb_PLN_PlanejamentoTrecho'
    __table_args__ = {'schema': 'intec.dbo'}

    IdTrecho = Column(Integer, primary_key=True, autoincrement=True)
    IdPlanejamento = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_PlanejamentoCabecalho.IdPlanejamento'))
    Ordem = Column(Integer, nullable=False)
    CiaAerea = Column(String(50))
    NumeroVoo = Column(String(20))
    AeroportoOrigem = Column(String(3))
    AeroportoDestino = Column(String(3))
    DataPartida = Column(DateTime)
    DataChegada = Column(DateTime)
    StatusTrecho = Column(String(20), default='Previsto')

    Cabecalho = relationship("PlanejamentoCabecalho", back_populates="Trechos")