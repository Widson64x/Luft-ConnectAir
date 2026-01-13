from sqlalchemy import Column, Integer, String, Date, Time, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .Base import BasePostgres

class RemessaMalha(BasePostgres):
    __tablename__ = 'Tb_RemessaMalha'
    __table_args__ = {'schema': 'MalhaAerea'} 

    Id = Column(Integer, primary_key=True, autoincrement=True)
    MesReferencia = Column(Date, nullable=False, index=True)
    NomeArquivoOriginal = Column(String(255))
    DataUpload = Column(DateTime(timezone=True), server_default=func.now())
    UsuarioResponsavel = Column(String(100)) 
    
    # NOVAS COLUNAS / AJUSTES
    # Tipo da operação: 'Importacao', 'Substituicao'
    TipoAcao = Column(String(50), nullable=False, default='Importacao')
    
    Ativo = Column(Boolean, default=True)
    
    Voos = relationship("VooMalha", back_populates="Remessa", cascade="all, delete-orphan")
class VooMalha(BasePostgres):
    """
    Tabela de DADOS (Schema: MalhaAerea)
    """
    __tablename__ = 'Tb_VooMalha'
    __table_args__ = {'schema': 'MalhaAerea'}

    Id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Na chave estrangeira, precisamos ser explícitos: 'schema.tabela.coluna'
    IdRemessa = Column(Integer, ForeignKey('MalhaAerea.Tb_RemessaMalha.Id'), nullable=False, index=True)
    
    CiaAerea = Column(String(10), nullable=False) 
    NumeroVoo = Column(String(20), nullable=False)
    DataPartida = Column(Date, nullable=False)
    AeroportoOrigem = Column(String(5), nullable=False)
    HorarioSaida = Column(Time, nullable=False)
    HorarioChegada = Column(Time, nullable=False)
    AeroportoDestino = Column(String(5), nullable=False)
    TempoVooEstimadoMinutos = Column(Integer, nullable=True) 
    
    Remessa = relationship("RemessaMalha", back_populates="Voos")