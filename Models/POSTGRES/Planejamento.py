from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from Models.POSTGRES.Base import BasePostgres

class PlanejamentoCabecalho(BasePostgres):
    __tablename__ = 'Tb_PlanejamentoCabecalho'
    __table_args__ = {'schema': 'MalhaAerea'}

    IdPlanejamento = Column(Integer, primary_key=True, autoincrement=True)
    DataCriacao = Column(DateTime, default=datetime.now)
    UsuarioCriacao = Column(String(50)) 
    Status = Column(String(20), default='Rascunho')
    
    AeroportoOrigem = Column(String(3)) 
    AeroportoDestino = Column(String(3)) 
    
    TotalVolumes = Column(Integer, default=0)
    TotalPeso = Column(Numeric(10,2), default=0.00)
    TotalValor = Column(Numeric(15,2), default=0.00)

    # Relacionamentos
    Itens = relationship("PlanejamentoItem", back_populates="Cabecalho", cascade="all, delete-orphan")
    Trechos = relationship("PlanejamentoTrecho", back_populates="Cabecalho", cascade="all, delete-orphan") # <--- NOVO

class PlanejamentoItem(BasePostgres):
    __tablename__ = 'Tb_PlanejamentoItem'
    __table_args__ = {'schema': 'MalhaAerea'}

    IdItem = Column(Integer, primary_key=True, autoincrement=True)
    IdPlanejamento = Column(Integer, ForeignKey('MalhaAerea.Tb_PlanejamentoCabecalho.IdPlanejamento'))
    
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

class PlanejamentoTrecho(BasePostgres):
    """
    Tabela de Voos/Conexões (Nova).
    """
    __tablename__ = 'Tb_PlanejamentoTrecho'
    __table_args__ = {'schema': 'MalhaAerea'}

    IdTrecho = Column(Integer, primary_key=True, autoincrement=True)
    IdPlanejamento = Column(Integer, ForeignKey('MalhaAerea.Tb_PlanejamentoCabecalho.IdPlanejamento'))
    
    Ordem = Column(Integer, nullable=False) # 1, 2, 3...
    CiaAerea = Column(String(50))
    NumeroVoo = Column(String(20))
    AeroportoOrigem = Column(String(3))
    AeroportoDestino = Column(String(3))
    DataPartida = Column(DateTime)
    DataChegada = Column(DateTime)
    StatusTrecho = Column(String(20), default='Previsto')

    Cabecalho = relationship("PlanejamentoCabecalho", back_populates="Trechos")