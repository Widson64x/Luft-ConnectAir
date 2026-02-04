from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class RemessaCidade(Base):
    __tablename__ = 'Tb_PLN_RemessaCidade'
    __table_args__ = {'schema': 'intec.dbo'} 

    Id = Column(Integer, primary_key=True, autoincrement=True)
    MesReferencia = Column(Date, nullable=False, index=True)
    NomeArquivoOriginal = Column(String(255))
    DataUpload = Column(DateTime, server_default=func.now())
    UsuarioResponsavel = Column(String(100))
    TipoAcao = Column(String(50), default='Importacao')
    Ativo = Column(Boolean, default=True)
    
    Cidades = relationship("Cidade", back_populates="Remessa", cascade="all, delete-orphan")

class Cidade(Base):
    __tablename__ = 'Tb_PLN_Cidade'
    __table_args__ = {'schema': 'intec.dbo'} 

    Id = Column(Integer, primary_key=True, autoincrement=True)
    IdRemessa = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_RemessaCidade.Id'), nullable=False, index=True)
    
    CodigoIbge = Column(Integer, index=True)
    Uf = Column(String(5))
    NomeCidade = Column(String(255))
    Latitude = Column(Float)
    Longitude = Column(Float)

    Remessa = relationship("RemessaCidade", back_populates="Cidades")