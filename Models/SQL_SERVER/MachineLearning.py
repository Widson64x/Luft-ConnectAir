"""
Models/SQL_SERVER/MachineLearning.py
=====================================
Modelos SQLAlchemy para as tabelas de suporte à camada de Machine Learning.

Tabelas:
    Tb_PLN_ML_SessaoAnalise       → uma sessão por chamada de análise de rotas
    Tb_PLN_ML_CandidatoSessao     → até 6 candidatos por sessão (um por categoria)
    Tb_PLN_ML_ModeloVersao        → metadados de cada modelo treinado
    Tb_PLN_ML_FeatureImportancia  → importância de features por versão de modelo

Script de criação: SQL/MachineLearning.sql
"""
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, Numeric, String, Text, func,
)
from sqlalchemy.orm import relationship

from Models.SQL_SERVER.Base import Base


class ML_SessaoAnalise(Base):
    """
    Registra cada chamada ao motor de análise de rotas.
    Vinculada ao PlanejamentoCabecalho apenas após o save do planejador.
    """
    __tablename__  = 'Tb_PLN_ML_SessaoAnalise'
    __table_args__ = {'schema': 'intec.dbo'}

    IdSessao             = Column(Integer, primary_key=True, autoincrement=True)
    DataAnalise          = Column(DateTime, server_default=func.now(), nullable=False)

    Filial               = Column(String(10),  nullable=False)
    Serie                = Column(String(5),   nullable=False)
    Ctc                  = Column(String(20),  nullable=False)

    TipoCarga            = Column(String(50),  nullable=True)
    ServicoContratado    = Column(String(50),  nullable=True)
    ContextoDescricao    = Column(String(100), nullable=True)
    PesoTempo            = Column(Float,       nullable=True)
    PesoCusto            = Column(Float,       nullable=True)

    TotalCandidatos      = Column(Integer,  nullable=False, default=0)
    CategoriaPreenchidas = Column(Integer,  nullable=False, default=0)

    CategoriaEscolhida   = Column(String(50),  nullable=True)
    IdPlanejamento       = Column(
        Integer,
        ForeignKey('intec.dbo.Tb_PLN_PlanejamentoCabecalho.IdPlanejamento', ondelete='SET NULL', use_alter=True),
        nullable=True,
    )
    DataVinculo          = Column(DateTime, nullable=True)
    UsuarioAnalise       = Column(String(50), nullable=True)

    Candidatos = relationship(
        'ML_CandidatoSessao',
        back_populates='Sessao',
        cascade='all, delete-orphan',
        lazy='select',
    )


class ML_CandidatoSessao(Base):
    """
    Um candidato de rota apresentado ao planejador numa sessão de análise.
    Cada sessão tem no máximo uma linha por categoria de rota.
    FoiEscolhida = True aponta o label de treinamento para o modelo ML.
    """
    __tablename__  = 'Tb_PLN_ML_CandidatoSessao'
    __table_args__ = {'schema': 'intec.dbo'}

    IdCandidato    = Column(Integer, primary_key=True, autoincrement=True)
    IdSessao       = Column(
        Integer,
        ForeignKey('intec.dbo.Tb_PLN_ML_SessaoAnalise.IdSessao', ondelete='CASCADE'),
        nullable=False,
    )

    Categoria        = Column(String(30), nullable=False)
    AeroportoOrigem  = Column(String(3),  nullable=True)
    AeroportoDestino = Column(String(3),  nullable=True)

    # Features — espelham RouteMLEngine.FEATURES
    Duracao          = Column(Float,          nullable=True)
    Custo            = Column(Numeric(12, 2), nullable=True)
    Escalas          = Column(Integer,        nullable=True)
    TrocasCia        = Column(Integer,        nullable=True)
    IndiceParceria   = Column(Float,          nullable=True)
    SemTarifa        = Column(Boolean,        nullable=False, default=False)
    EhPerecivel      = Column(Boolean,        nullable=False, default=False)
    ServicoAlinhado  = Column(Boolean,        nullable=False, default=False)

    # Breakdown de scores
    ScoreBase        = Column(Float, nullable=True)
    BonusML          = Column(Float, nullable=True, default=0.0)
    ScoreFinal       = Column(Float, nullable=True)

    # Label de treinamento
    FoiEscolhida     = Column(Boolean, nullable=False, default=False)

    Sessao = relationship('ML_SessaoAnalise', back_populates='Candidatos')


class ML_ModeloVersao(Base):
    """
    Metadados de cada modelo treinado via RouteMLEngine.Treinar().
    Somente um registro pode ter IsAtivo = True simultaneamente.
    O arquivo binário .joblib é referenciado por CaminhoArquivo.
    """
    __tablename__  = 'Tb_PLN_ML_ModeloVersao'
    __table_args__ = {'schema': 'intec.dbo'}

    IdModelo        = Column(Integer, primary_key=True, autoincrement=True)
    DataTreino      = Column(DateTime, server_default=func.now(), nullable=False)

    TotalAmostras   = Column(Integer, nullable=False)
    AucCrossVal     = Column(Float,   nullable=True)

    IsAtivo         = Column(Boolean, nullable=False, default=False)
    CaminhoArquivo  = Column(String(500), nullable=True)

    Algoritmo       = Column(String(100), nullable=False, default='GradientBoostingClassifier')
    ParametrosJson  = Column(Text, nullable=True)

    UsuarioTreino   = Column(String(50), nullable=True)
    Observacoes     = Column(Text, nullable=True)

    Importancias = relationship(
        'ML_FeatureImportancia',
        back_populates='Modelo',
        cascade='all, delete-orphan',
        lazy='select',
    )


class ML_FeatureImportancia(Base):
    """
    Importância de cada feature para uma versão específica do modelo.
    Alimentada automaticamente após cada Treinar().
    """
    __tablename__  = 'Tb_PLN_ML_FeatureImportancia'
    __table_args__ = {'schema': 'intec.dbo'}

    IdImportancia = Column(Integer, primary_key=True, autoincrement=True)
    IdModelo      = Column(
        Integer,
        ForeignKey('intec.dbo.Tb_PLN_ML_ModeloVersao.IdModelo', ondelete='CASCADE'),
        nullable=False,
    )
    NomeFeature   = Column(String(100), nullable=False)
    Importancia   = Column(Float,       nullable=False)

    Modelo = relationship('ML_ModeloVersao', back_populates='Importancias')
