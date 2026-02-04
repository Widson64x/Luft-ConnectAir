from sqlalchemy import Column, Integer, String, Date, Time, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class RemessaMalha(Base):
    __tablename__ = 'Tb_PLN_RemessaVoo'
    __table_args__ = {'schema': 'intec.dbo'} 
    Id = Column(Integer, primary_key=True, autoincrement=True)
    MesReferencia = Column(Date, nullable=False, index=True)  # Mês/Ano da malha aérea
    NomeArquivoOriginal = Column(String(255))
    DataUpload = Column(DateTime, server_default=func.now())
    UsuarioResponsavel = Column(String(100)) 
    TipoAcao = Column(String(50), nullable=False, default='Importacao')
    Ativo = Column(Boolean, default=True)
    
    Voos = relationship("VooMalha", back_populates="Remessa", cascade="all, delete-orphan")

class VooMalha(Base):
    __tablename__ = 'Tb_PLN_Voo'
    __table_args__ = {'schema': 'intec.dbo'}

    Id = Column(Integer, primary_key=True, autoincrement=True)
    IdRemessa = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_RemessaVoo.Id'), nullable=False, index=True)
    
    CiaAerea = Column(String(10), nullable=False) 
    NumeroVoo = Column(String(20), nullable=False)
    DataPartida = Column(Date, nullable=False)
    AeroportoOrigem = Column(String(5), nullable=False)
    HorarioSaida = Column(Time, nullable=False)
    HorarioChegada = Column(Time, nullable=False)
    AeroportoDestino = Column(String(5), nullable=False)
    TempoVooEstimadoMinutos = Column(Integer) 
    
    Remessa = relationship("RemessaMalha", back_populates="Voos")