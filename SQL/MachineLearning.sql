-- =============================================================================
-- LUFT-CONNECTAIR | Machine Learning — Tabelas de Suporte
-- Banco: intec | Schema: dbo
-- Padrão de nomenclatura: Tb_PLN_ML_...
--
-- Estrutura:
--   Tb_PLN_ML_SessaoAnalise      → 1 registro por chamada de análise de rotas
--   Tb_PLN_ML_CandidatoSessao    → até 6 candidatos por sessão (1 por categoria)
--   Tb_PLN_ML_ModeloVersao       → metadados de cada modelo treinado
--   Tb_PLN_ML_FeatureImportancia → importância de cada feature por versão de modelo
-- =============================================================================

USE [intec];
GO

-- -----------------------------------------------------------------------------
-- 1. SESSÃO DE ANÁLISE
--    Registra cada chamada ao motor de rotas (GET /Montar ou /API/OpcoesRotas).
--    Vinculada ao PlanejamentoCabecalho apenas após o planejador salvar.
-- -----------------------------------------------------------------------------
CREATE TABLE [dbo].[Tb_PLN_ML_SessaoAnalise] (
    IdSessao              INT           IDENTITY(1,1)  NOT NULL,
    DataAnalise           DATETIME2     NOT NULL        DEFAULT GETDATE(),

    -- Identificação do CTC analisado
    Filial                VARCHAR(10)   NOT NULL,
    Serie                 VARCHAR(5)    NOT NULL,
    Ctc                   VARCHAR(20)   NOT NULL,

    -- Contexto de roteamento usado na análise
    TipoCarga             VARCHAR(50)   NULL,
    ServicoContratado     VARCHAR(50)   NULL,
    ContextoDescricao     VARCHAR(100)  NULL,   -- Ex: 'SECA/EXPRESSO'
    PesoTempo             FLOAT         NULL,
    PesoCusto             FLOAT         NULL,

    -- Resultado da análise
    TotalCandidatos       INT           NOT NULL  DEFAULT 0,
    CategoriaPreenchidas  INT           NOT NULL  DEFAULT 0,

    -- Preenchido no momento do save (POST /Salvar)
    CategoriaEscolhida    VARCHAR(50)   NULL,
    IdPlanejamento        INT           NULL,
    DataVinculo           DATETIME2     NULL,

    -- Auditoria
    UsuarioAnalise        VARCHAR(50)   NULL,

    CONSTRAINT PK_ML_SessaoAnalise   PRIMARY KEY (IdSessao),
    CONSTRAINT FK_ML_Sessao_Plan     FOREIGN KEY (IdPlanejamento)
        REFERENCES [dbo].[Tb_PLN_PlanejamentoCabecalho] (IdPlanejamento)
        ON DELETE SET NULL
);
GO

CREATE INDEX IX_ML_Sessao_Ctc        ON [dbo].[Tb_PLN_ML_SessaoAnalise] (Filial, Serie, Ctc);
CREATE INDEX IX_ML_Sessao_IdPlan     ON [dbo].[Tb_PLN_ML_SessaoAnalise] (IdPlanejamento);
CREATE INDEX IX_ML_Sessao_Data       ON [dbo].[Tb_PLN_ML_SessaoAnalise] (DataAnalise DESC);
GO

-- -----------------------------------------------------------------------------
-- 2. CANDIDATO DE SESSÃO
--    Um registro por categoria de rota apresentada ao planejador (máx 6 por sessão).
--    FoiEscolhida = 1 apenas na categoria que o planejador confirmou no save.
--    Esta tabela é a fonte de dados para o treinamento do modelo ML.
-- -----------------------------------------------------------------------------
CREATE TABLE [dbo].[Tb_PLN_ML_CandidatoSessao] (
    IdCandidato           INT           IDENTITY(1,1)  NOT NULL,
    IdSessao              INT           NOT NULL,

    -- Identificação da categoria de rota
    Categoria             VARCHAR(30)   NOT NULL,  -- recomendada | direta | rapida | economica | conexao_mesma_cia | interline
    AeroportoOrigem       VARCHAR(3)    NULL,
    AeroportoDestino      VARCHAR(3)    NULL,

    -- Features de entrada para o modelo ML (espelham RouteMLEngine.FEATURES)
    Duracao               FLOAT         NULL,  -- minutos total da rota
    Custo                 DECIMAL(12,2) NULL,  -- custo calculado para o peso
    Escalas               TINYINT       NULL,  -- número de conexões (0 = direto)
    TrocasCia             TINYINT       NULL,  -- número de trocas de companhia aérea
    IndiceParceria        FLOAT         NULL,  -- média do score de parceria das cias (0-100)
    SemTarifa             BIT           NOT NULL  DEFAULT 0,  -- 1 = algum trecho sem tarifa cadastrada
    EhPerecivel           BIT           NOT NULL  DEFAULT 0,  -- 1 = contexto perecível+expresso
    ServicoAlinhado       BIT           NOT NULL  DEFAULT 0,  -- 1 = serviço do 1º trecho bate com o contratado

    -- Scores gerados pelo motor
    ScoreBase             FLOAT         NULL,  -- score antes do ajuste ML
    BonusML               FLOAT         NULL  DEFAULT 0,  -- ajuste aplicado pelo modelo treinado
    ScoreFinal            FLOAT         NULL,  -- score final (ScoreBase + BonusML)

    -- Label de treinamento (preenchido no vinculo com planejamento)
    FoiEscolhida          BIT           NOT NULL  DEFAULT 0,

    CONSTRAINT PK_ML_CandidatoSessao  PRIMARY KEY (IdCandidato),
    CONSTRAINT FK_ML_Candidato_Sessao FOREIGN KEY (IdSessao)
        REFERENCES [dbo].[Tb_PLN_ML_SessaoAnalise] (IdSessao)
        ON DELETE CASCADE
);
GO

CREATE INDEX IX_ML_Candidato_Sessao  ON [dbo].[Tb_PLN_ML_CandidatoSessao] (IdSessao);
CREATE INDEX IX_ML_Candidato_Label   ON [dbo].[Tb_PLN_ML_CandidatoSessao] (FoiEscolhida);
GO

-- -----------------------------------------------------------------------------
-- 3. VERSÃO DE MODELO TREINADO
--    Registra cada execução de Treinar(). Apenas um modelo pode ser IsAtivo = 1.
--    O arquivo binário (.joblib) fica em Data/ML/ e o caminho é registrado aqui.
-- -----------------------------------------------------------------------------
CREATE TABLE [dbo].[Tb_PLN_ML_ModeloVersao] (
    IdModelo              INT           IDENTITY(1,1)  NOT NULL,
    DataTreino            DATETIME2     NOT NULL        DEFAULT GETDATE(),

    -- Métricas de qualidade
    TotalAmostras         INT           NOT NULL,
    AucCrossVal           FLOAT         NULL,  -- AUC-ROC médio na validação cruzada

    -- Estado
    IsAtivo               BIT           NOT NULL  DEFAULT 0,  -- somente o modelo em uso ativo

    -- Referência ao arquivo binário
    CaminhoArquivo        VARCHAR(500)  NULL,

    -- Metadados do algoritmo
    Algoritmo             VARCHAR(100)  NOT NULL  DEFAULT 'GradientBoostingClassifier',
    ParametrosJson        VARCHAR(MAX)  NULL,  -- hiperparâmetros usados no treino (JSON)

    -- Auditoria
    UsuarioTreino         VARCHAR(50)   NULL,
    Observacoes           VARCHAR(MAX)  NULL,

    CONSTRAINT PK_ML_ModeloVersao  PRIMARY KEY (IdModelo)
);
GO

CREATE INDEX IX_ML_Modelo_Ativo  ON [dbo].[Tb_PLN_ML_ModeloVersao] (IsAtivo);
GO

-- -----------------------------------------------------------------------------
-- 4. IMPORTÂNCIA DE FEATURES
--    Detalha o peso de cada feature no modelo treinado.
--    Fundamental para auditoria, debug e evolução futura do modelo.
-- -----------------------------------------------------------------------------
CREATE TABLE [dbo].[Tb_PLN_ML_FeatureImportancia] (
    IdImportancia         INT           IDENTITY(1,1)  NOT NULL,
    IdModelo              INT           NOT NULL,

    NomeFeature           VARCHAR(100)  NOT NULL,
    Importancia           FLOAT         NOT NULL,  -- valor bruto de feature_importances_ (sklearn)
    ImportanciaPerc       AS (CAST(Importancia * 100 AS DECIMAL(6,2))),  -- coluna calculada (%)

    CONSTRAINT PK_ML_FeatureImportancia   PRIMARY KEY (IdImportancia),
    CONSTRAINT FK_ML_Feature_Modelo       FOREIGN KEY (IdModelo)
        REFERENCES [dbo].[Tb_PLN_ML_ModeloVersao] (IdModelo)
        ON DELETE CASCADE
);
GO

CREATE INDEX IX_ML_Feature_Modelo  ON [dbo].[Tb_PLN_ML_FeatureImportancia] (IdModelo);
GO

-- =============================================================================
-- VIEWS DE SUPORTE (opcionais — facilitam consultas de BI/monitoramento)
-- =============================================================================

-- View consolidada: candidatos com contexto da sessão (útil para dashboards)
CREATE OR ALTER VIEW [dbo].[Vw_MLCandidatosCompletos] AS
SELECT
    c.IdCandidato,
    s.IdSessao,
    s.DataAnalise,
    s.Filial,
    s.Serie,
    s.Ctc,
    s.TipoCarga,
    s.ServicoContratado,
    s.ContextoDescricao,
    s.IdPlanejamento,
    s.CategoriaEscolhida,
    s.UsuarioAnalise,
    c.Categoria,
    c.AeroportoOrigem,
    c.AeroportoDestino,
    c.Duracao,
    c.Custo,
    c.Escalas,
    c.TrocasCia,
    c.IndiceParceria,
    c.SemTarifa,
    c.EhPerecivel,
    c.ServicoAlinhado,
    c.ScoreBase,
    c.BonusML,
    c.ScoreFinal,
    c.FoiEscolhida
FROM [dbo].[Tb_PLN_ML_CandidatoSessao] c
INNER JOIN [dbo].[Tb_PLN_ML_SessaoAnalise] s ON c.IdSessao = s.IdSessao;
GO

-- View das últimas versões de modelo com importâncias
CREATE OR ALTER VIEW [dbo].[Vw_MLModeloUltimaVersao] AS
SELECT
    m.IdModelo,
    m.DataTreino,
    m.TotalAmostras,
    m.AucCrossVal,
    m.IsAtivo,
    m.Algoritmo,
    m.UsuarioTreino,
    f.NomeFeature,
    f.Importancia,
    f.ImportanciaPerc
FROM [dbo].[Tb_PLN_ML_ModeloVersao] m
INNER JOIN [dbo].[Tb_PLN_ML_FeatureImportancia] f ON f.IdModelo = m.IdModelo;
GO
