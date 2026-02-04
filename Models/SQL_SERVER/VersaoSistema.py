from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class VersaoSistema(Base):
    __tablename__ = 'Tb_PLN_VersaoSistema'
    __table_args__ = {'schema': 'intec.dbo'} 
 
    Id = Column(Integer, primary_key=True)
    NumeroVersao = Column(String(50), nullable=False)
    Estagio = Column(String(20), nullable=False)
    DataLancamento = Column(DateTime, default=datetime.now)
    Responsavel = Column(String(100))
    NotasVersao = Column(Text)
    HashCommit = Column(String(100))