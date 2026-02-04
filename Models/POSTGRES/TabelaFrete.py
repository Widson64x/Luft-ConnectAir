from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .Base import BasePostgres

class RemessaFrete(BasePostgres):
    __tablename__ = 'Tb_RemessaFrete'
    __table_args__ = {'schema': 'MalhaAerea'} 

    Id = Column(Integer, primary_key=True, autoincrement=True)
    DataReferencia = Column(Date, nullable=False, index=True) # Mês/Data de vigência
    NomeArquivoOriginal = Column(String(255))
    DataUpload = Column(DateTime(timezone=True), server_default=func.now())
    UsuarioResponsavel = Column(String(100)) 
    Ativo = Column(Boolean, default=True)
    
    Itens = relationship("TabelaFrete", back_populates="Remessa", cascade="all, delete-orphan")

class TabelaFrete(BasePostgres):
    """
    Tabela normalizada de tarifas (Unpivoted)
    Ex: GRU -> AJU | GOL | LOG SAUDE | 17.55
    """
    __tablename__ = 'Tb_TabelaFrete'
    __table_args__ = {'schema': 'MalhaAerea'}

    Id = Column(Integer, primary_key=True, autoincrement=True)
    
    IdRemessa = Column(Integer, ForeignKey('MalhaAerea.Tb_RemessaFrete.Id'), nullable=False, index=True)
    
    Origem = Column(String(5), nullable=False)  # IATA 3 letras
    Destino = Column(String(5), nullable=False) # IATA 3 letras
    CiaAerea = Column(String(20), nullable=False) # GOL, LATAM, AZUL
    Servico = Column(String(100), nullable=False) # LOG SAUDE, STANDARD, etc
    Tarifa = Column(Float, nullable=True)
    
    Remessa = relationship("RemessaFrete", back_populates="Itens")