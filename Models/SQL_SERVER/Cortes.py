from sqlalchemy import Column, Integer, String, Time, Boolean, DateTime
from Models.SQL_SERVER.Base import Base
from datetime import datetime

class CortePlanejamento(Base):
    __tablename__ = 'Tb_PLN_CortePlanejamento'
    __table_args__ = {'schema': 'intec.dbo'}

    IdCortePln = Column(Integer, primary_key=True, autoincrement=True)
    CodFilial = Column(Integer, nullable=False)
    Filial = Column(String(10), nullable=False)
    
    # Nova coluna sequencial por filial (1º, 2º, 3º...)
    Corte = Column(Integer) 
    
    Descricao = Column(String(50))
    HorarioCorte = Column(Time, nullable=False)
    Ativo = Column(Boolean, default=True)

    # Auditoria
    UsuarioCriacao = Column(String(100))
    DataCriacao = Column(DateTime, default=datetime.now)
    UsuarioAlteracao = Column(String(100))
    DataAlteracao = Column(DateTime)

class CorteEmissao(Base):
    __tablename__ = 'Tb_PLN_CorteEmissao'
    __table_args__ = {'schema': 'intec.dbo'}

    IdCorteEmi = Column(Integer, primary_key=True, autoincrement=True)
    CodFilial = Column(Integer, nullable=False)
    Filial = Column(String(10), nullable=False)
    
    # Nova coluna solicitada
    Descricao = Column(String(100)) 
    
    HorarioLimite = Column(Time, nullable=False)
    BloqueiaEmissao = Column(Boolean, default=False)
    Ativo = Column(Boolean, default=True)

    # Auditoria
    UsuarioCriacao = Column(String(100))
    DataCriacao = Column(DateTime, default=datetime.now)
    UsuarioAlteracao = Column(String(100))
    DataAlteracao = Column(DateTime)