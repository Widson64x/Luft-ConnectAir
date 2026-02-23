from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from Models.SQL_SERVER.Base import Base

class ServicoCliente(Base):
    __tablename__ = 'Tb_PLN_ServicoCliente'
    __table_args__ = {'schema': 'intec.dbo'} 

    Id = Column(Integer, primary_key=True, autoincrement=True)
    CodigoCliente = Column(Integer, index=True, nullable=False) # Referência lógica ao Cliente do LuftInforma
    
    DurabilidadeGelo = Column(String(86)) # Ex: '24 horas', '48 horas', '72 horas'
    # Dados extraídos da query/planilha e parametrizados no novo sistema
    AutorizacaoTrocaGelo = Column(String(30)) # Ex: 'SIM', 'NÃO', 'SÓ COM AUTORIZAÇÃO'
    AutorizacaoArmazenagem = Column(String(30)) # Ex: 'SIM', 'NÃO', 'SÓ COM AUTORIZAÇÃO'
    TipoOperacao = Column(String(50)) # Ex: 'Transporte' ou 'Armazenagem'
    TipoArmazenagem = Column(String(50)) # Ex: 'Filial', 'Depósito', 'Armazém Geral'
    
    # CORREÇÃO AQUI: De 'SeviçoContratado' para 'ServicoContratado'
    ServicoContratado = Column(String(100)) # Ex: 'ECONÔMICO', 'EXPRESSO', etc.    
    
    # Auditoria e Controle
    DataCadastro = Column(DateTime, server_default=func.now())
    UsuarioResponsavel = Column(String(100))
    Ativo = Column(Boolean, default=True)

    # Nota: Como o Cliente fica no banco/schema LuftInforma e essa tabela no Intec,
    # caso não seja possível criar um ForeignKey cross-database nativamente via SQL Server,
    # deixamos o CodigoCliente apenas como um Index (vínculo lógico) para fazermos
    # os Joins diretamente nas consultas do SQLAlchemy ou via Services.