from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from datetime import datetime
from Models.SQL_SERVER.Base import Base
from Models.SQL_SERVER.Permissoes import Tb_Sistema

class VersaoSistema(Base):
    __tablename__ = 'Tb_VersaoSistema'
    __table_args__ = {'schema': 'intec.dbo'} 
 
    Id = Column(Integer, primary_key=True)
    Id_Sistema = Column(Integer, ForeignKey('intec.dbo.Tb_Sistema.Id_Sistema'), nullable=False)
    NumeroVersao = Column(String(50), nullable=False)
    Estagio = Column(String(20), nullable=False)
    DataLancamento = Column(DateTime, default=datetime.now)
    Responsavel = Column(String(100))
    NotasVersao = Column(Text)
    HashCommit = Column(String(100))