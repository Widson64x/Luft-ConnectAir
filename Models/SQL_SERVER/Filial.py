from sqlalchemy import Column, Integer, String
from Models.SQL_SERVER.Base import Base

class Filial(Base):
    __tablename__ = 'tb_filial'
    __table_args__ = {'schema': 'intec.dbo'}

    # Mantendo nomes das colunas conforme o banco (minúsculo), 
    # mas o serviço irá expor como CamelCase
    id = Column(Integer, primary_key=True)
    filial = Column(String(10))     # Código string '01'
    codfilial = Column(Integer)     # Código numérico 1
    nomefilial = Column(String(100))
    cidade = Column(String(50))
    uf = Column(String(2))