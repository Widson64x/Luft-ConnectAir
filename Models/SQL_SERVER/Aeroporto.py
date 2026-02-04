from sqlalchemy import Column, Date, DateTime, Integer, String, Float, func, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class RemessaAeroportos(Base):
    __tablename__ = 'Tb_PLN_RemessaAeroporto'
    __table_args__ = {'schema': 'intec.dbo'}

    Id = Column(Integer, primary_key=True, autoincrement=True)
    MesReferencia = Column(Date, nullable=False, index=True)
    NomeArquivoOriginal = Column(String(255))
    DataUpload = Column(DateTime, server_default=func.now())
    UsuarioResponsavel = Column(String(100)) 
    TipoAcao = Column(String(50), nullable=False, default='Importacao')
    Ativo = Column(Boolean, default=True)
    
    Aeroportos = relationship("Aeroporto", back_populates="Remessa", cascade="all, delete-orphan")
    
class Aeroporto(Base):
    __tablename__ = 'Tb_PLN_Aeroporto'
    __table_args__ = {'schema': 'intec.dbo'}

    Id = Column(Integer, primary_key=True, autoincrement=True)
    IdRemessa = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_RemessaAeroporto.Id'), nullable=False, index=True)

    CodigoPais = Column(String(5))
    NomeRegiao = Column(String(100))
    CodigoIata = Column(String(3), index=True)
    CodigoIcao = Column(String(4))
    NomeAeroporto = Column(String(255))
    Latitude = Column(Float)
    Longitude = Column(Float)

    Remessa = relationship("RemessaAeroportos", back_populates="Aeroportos")