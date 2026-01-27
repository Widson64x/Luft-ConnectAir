from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from .Base import BasePostgres

class VersaoSistema(BasePostgres):
    __tablename__ = 'Tb_VersaoSistema'
    __table_args__ = {'schema': 'MalhaAerea'} 
 
    Id = Column(Integer, primary_key=True)
    NumeroVersao = Column(String(50), nullable=False)  # Ex: 1.0.2
    Estagio = Column(String(20), nullable=False)       # Alpha, Beta, Release Candidate, Stable
    DataLancamento = Column(DateTime, default=datetime.now)
    Responsavel = Column(String(100))                  # Quem fez o deploy/merge
    NotasVersao = Column(Text)                         # O que mudou (Changelog)
    HashCommit = Column(String(100))                   # Opcional: Hash do Git

    def __repr__(self):
        return f"<Versao {self.NumeroVersao} - {self.Estagio}>"