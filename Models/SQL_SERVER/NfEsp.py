from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean
from Models.SQL_SERVER.Base import Base

class NfEsp(Base):
    __tablename__ = 'tb_nf_esp'
    __table_args__ = {'schema': 'intec.dbo'}

    # Chave Primária (Baseado na coluna idcodigo ser NO Nullable e numérica)
    idcodigo = Column(Numeric, primary_key=True) 

    # --- Colunas Mapeadas via CSV ---
    filialctc = Column(String(10), nullable=False)
    numnfnum = Column(Numeric)
    numnf = Column(String(12), nullable=False)
    serie = Column(String(3))
    cliente_cgc = Column(String(14), nullable=False)
    cliente_nome = Column(String(40))
    emissao_nf = Column(DateTime)
    numpedido = Column(String(20))
    dtpedido = Column(DateTime)
    valornf = Column(Numeric) # Tipo 'money' no banco
    pesonf = Column(Numeric)  # Tipo 'money' no banco
    volumesnf = Column(Integer)
    data_interface = Column(DateTime)
    hora_interface = Column(String(5))
    at_cliente = Column(String(1))
    canhotonf = Column(String(1))
    canhotonfprot = Column(Numeric)
    canhotonfdata = Column(DateTime)
    tem_ocorrnf = Column(String(1))
    ordem = Column(DateTime)
    mod_incl = Column(String(1))
    flag_integracao = Column(Boolean) # Tipo 'bit' no banco
    chave_acesso = Column(String(44))
    statusnf = Column(String(2))
    chNFO = Column(String(44))
    qtdekits = Column(Numeric)
    form_gelo = Column(String(500))
    data_cadformgelo = Column(DateTime)
    usu_cadformgelo = Column(String(50))