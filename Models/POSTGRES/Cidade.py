from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from .Base import BasePostgres

class RemessaCidade(BasePostgres):
    __tablename__ = 'Tb_RemessaCidade'
    __table_args__ = {'schema': 'MalhaAerea'} 

    Id = Column(Integer, primary_key=True, autoincrement=True)
    MesReferencia = Column(Date, nullable=False, index=True)
    NomeArquivoOriginal = Column(String(255))
    DataUpload = Column(DateTime(timezone=True), server_default=func.now())
    UsuarioResponsavel = Column(String(100))
    TipoAcao = Column(String(50), default='Importacao')
    Ativo = Column(Boolean, default=True)
    
    Cidades = relationship("Cidade", back_populates="Remessa", cascade="all, delete-orphan")

class Cidade(BasePostgres):
    __tablename__ = 'Tb_Cidade'
    __table_args__ = {'schema': 'MalhaAerea'} 

    Id = Column(Integer, primary_key=True, autoincrement=True)
    IdRemessa = Column(Integer, ForeignKey('MalhaAerea.Tb_RemessaCidade.Id'), nullable=False, index=True)
    
    CodigoIbge = Column(Integer, index=True) # id_municipio
    Uf = Column(String(5))                   # uf
    NomeCidade = Column(String(255))         # municipio
    
    Latitude = Column(Float)
    Longitude = Column(Float)

    Remessa = relationship("RemessaCidade", back_populates="Cidades")