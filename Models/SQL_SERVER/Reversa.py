from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class ControleReversa(Base):
    """
    Tabela para controle de liberação de CTCs de Devolução pelo time de Reversa.
    """
    __tablename__ = 'Tb_PLN_ControleReversa'
    __table_args__ = {'schema': 'intec.dbo'}

    IdControle = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identificação do CTC (Chave Composta Lógica)
    Filial = Column(String(10), nullable=False)
    Serie = Column(String(5), nullable=False)
    Ctc = Column(String(20), nullable=False)

    # Controle
    LiberadoPlanejamento = Column(Boolean, default=False)
    UsuarioResponsavel = Column(String(50))
    DataAtualizacao = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<Reversa {self.Filial}-{self.Ctc} | Liberado: {self.LiberadoPlanejamento}>"