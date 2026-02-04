from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class RemessaFrete(Base):
    __tablename__ = 'Tb_PLN_RemessaFrete'
    __table_args__ = {'schema': 'intec.dbo'} 

    Id = Column(Integer, primary_key=True, autoincrement=True)
    DataReferencia = Column(Date, nullable=False, index=True)
    NomeArquivoOriginal = Column(String(255))
    DataUpload = Column(DateTime, server_default=func.now())
    UsuarioResponsavel = Column(String(100)) 
    Ativo = Column(Boolean, default=True)
    
    Itens = relationship("TabelaFrete", back_populates="Remessa", cascade="all, delete-orphan")

class TabelaFrete(Base):
    __tablename__ = 'Tb_PLN_Frete'
    __table_args__ = {'schema': 'intec.dbo'}

    Id = Column(Integer, primary_key=True, autoincrement=True)
    IdRemessa = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_RemessaFrete.Id'), nullable=False, index=True)
    
    Origem = Column(String(5), nullable=False)
    Destino = Column(String(5), nullable=False)
    CiaAerea = Column(String(20), nullable=False)
    Servico = Column(String(100), nullable=False)
    Tarifa = Column(Float)
    
    Remessa = relationship("RemessaFrete", back_populates="Itens")