from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Boolean, Time
from sqlalchemy.orm import relationship
from datetime import datetime
from Models.SQL_SERVER.Base import Base

class PlanejamentoCabecalho(Base):
    __tablename__ = 'Tb_PLN_PlanejamentoCabecalho'
    __table_args__ = {'schema': 'intec.dbo'}

    IdPlanejamento = Column(Integer, primary_key=True, autoincrement=True)
    DataCriacao = Column(DateTime, default=datetime.now)
    UsuarioCriacao = Column(String(50)) 
    Status = Column(String(20), default='Rascunho')
    
    AeroportoOrigem = Column(String(3)) 
    AeroportoDestino = Column(String(3)) 
    
    # IDs vinculados
    IdAeroportoOrigem = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_Aeroporto.Id'), nullable=True)
    IdAeroportoDestino = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_Aeroporto.Id'), nullable=True)

    IdCortePln = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_CortePlanejamento.IdCortePln'), nullable=True)

    TotalVolumes = Column(Integer, default=0)
    TotalPeso = Column(Numeric(10,2), default=0.00)
    TotalValor = Column(Numeric(15,2), default=0.00)

    Itens = relationship("PlanejamentoItem", back_populates="Cabecalho", cascade="all, delete-orphan")
    Trechos = relationship("PlanejamentoTrecho", back_populates="Cabecalho", cascade="all, delete-orphan")

    AeroportoOrigemObj = relationship("Aeroporto", foreign_keys=[IdAeroportoOrigem])
    AeroportoDestinoObj = relationship("Aeroporto", foreign_keys=[IdAeroportoDestino])


class PlanejamentoItem(Base):
    __tablename__ = 'Tb_PLN_PlanejamentoItem'
    __table_args__ = {'schema': 'intec.dbo'}

    IdItem = Column(Integer, primary_key=True, autoincrement=True)
    IdPlanejamento = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_PlanejamentoCabecalho.IdPlanejamento'))
    Filial = Column(String(10))
    Serie = Column(String(5))
    Ctc = Column(String(20))
    NotaFiscal = Column(String(50))
    DataEmissao = Column(DateTime)
    Hora = Column(String(5))
    Remetente = Column(String(100))
    Destinatario = Column(String(100))
    
    OrigemCidade = Column(String(50))
    DestinoCidade = Column(String(50))

    # IDs vinculados
    IdCidadeOrigem = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_Cidade.Id'), nullable=True)
    IdCidadeDestino = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_Cidade.Id'), nullable=True)

    Corte = Column(Integer, nullable=True)
    HorarioCorte = Column(Time, nullable=True)

    Volumes = Column(Integer)
    PesoTaxado = Column(Numeric(10,3))
    ValMercadoria = Column(Numeric(15,2))
    IndConsolidado = Column(Boolean, default=False)
    
    Cabecalho = relationship("PlanejamentoCabecalho", back_populates="Itens")

    CidadeOrigemObj = relationship("Cidade", foreign_keys=[IdCidadeOrigem])
    CidadeDestinoObj = relationship("Cidade", foreign_keys=[IdCidadeDestino])


class PlanejamentoTrecho(Base):
    __tablename__ = 'Tb_PLN_PlanejamentoTrecho'
    __table_args__ = {'schema': 'intec.dbo'}

    IdTrecho = Column(Integer, primary_key=True, autoincrement=True)
    IdPlanejamento = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_PlanejamentoCabecalho.IdPlanejamento'))
    Ordem = Column(Integer, nullable=False)
    
    CiaAerea = Column(String(50))
    NumeroVoo = Column(String(20))
    
    IdVoo = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_Voo.Id'), nullable=True)

    AeroportoOrigem = Column(String(3))
    AeroportoDestino = Column(String(3))

    IdAeroportoOrigem = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_Aeroporto.Id'), nullable=True)
    IdAeroportoDestino = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_Aeroporto.Id'), nullable=True)

    # --- NOVAS COLUNAS SOLICITADAS ---
    IdFrete = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_Frete.Id'), nullable=True)
    TipoServico = Column(String(100), nullable=True) # Ex: Standard, Expresso
    HorarioCorte = Column(Time, nullable=True)       # Ex: 18:00
    DataCorte = Column(DateTime, nullable=True)      # Data/Hora absoluta do corte

    DataPartida = Column(DateTime)
    DataChegada = Column(DateTime)
    StatusTrecho = Column(String(20), default='Previsto')

    Cabecalho = relationship("PlanejamentoCabecalho", back_populates="Trechos")
    
    VooObj = relationship("VooMalha", foreign_keys=[IdVoo])
    AeroportoOrigemObj = relationship("Aeroporto", foreign_keys=[IdAeroportoOrigem])
    AeroportoDestinoObj = relationship("Aeroporto", foreign_keys=[IdAeroportoDestino])
    
    # Novo relacionamento com Frete
    FreteObj = relationship("TabelaFrete", foreign_keys=[IdFrete])

class RankingAeroportos(Base):
    __tablename__ = 'Tb_PLN_RankingAeroportos'
    __table_args__ = {'schema': 'intec.dbo'}
    Id = Column(Integer, primary_key=True, autoincrement=True)
    Uf = Column(String(2), nullable=False)  # A Sigla (SP, RJ, etc.)
    IdAeroporto = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_Aeroporto.Id'), nullable=False) # Ajuste se o nome real da tabela for diferente
    IndiceImportancia = Column(Integer, default=0) # 0 a 100
    
    # Relacionamentos
    # Pegar na tabela de Aeroporto para mostrar o nome completo, cidade, etc.
    Aeroporto = relationship("Aeroporto", backref="rankings")