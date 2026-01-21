from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class AeroportoLocal(Base):
    __tablename__ = 'tb_aircadlocal'
    __table_args__ = {'schema': 'intec.dbo'}

    id = Column(Integer, primary_key=True)
    sigla = Column(String(3))
    localidade = Column(String(255))
    aeroporto = Column(String(255))
    uf = Column(String(2))
    regiaogeo = Column(String(50))

class CompanhiaAerea(Base):
    __tablename__ = 'tb_aircadcia'
    __table_args__ = {'schema': 'intec.dbo'}

    id_Cia = Column(Integer, primary_key=True)
    codcia = Column(String(3))
    fantasia = Column(String(20))
    cgc = Column(String(14)) # CNPJ
    Status_Cia = Column(Boolean)

class UnidadeFederativa(Base):
    __tablename__ = 'tb_caduf'
    __table_args__ = {'schema': 'intec.dbo'}

    uf = Column(String(2), primary_key=True)
    cidade = Column(String(35)) # Capital ou referência
    regiaogeo = Column(String(20))

class Praca(Base):
    __tablename__ = 'tb_pracas'
    __table_args__ = {'schema': 'intec.dbo'}

    id_praca = Column(Integer, primary_key=True)
    codigo = Column(String(12))
    tipo = Column(String(3))
    cidade = Column(String(35))
    uf = Column(String(2))
    status = Column(String(1))

class UnidadeResponsavel(Base):
    __tablename__ = 'tb_Unid_Responsavel'
    __table_args__ = {'schema': 'intec.dbo'}

    id_unid = Column(Integer, primary_key=True)
    cd_unid = Column(String(10))
    ds_unid = Column(String(50))
    cnpj_unid = Column(String(14))
    ds_email_unid = Column(String(500))
    cidaderetira = Column(String(100))
    ufretira = Column(String(2))