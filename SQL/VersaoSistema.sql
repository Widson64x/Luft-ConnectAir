USE [intec];
GO

BEGIN TRY
    BEGIN TRAN;

    IF OBJECT_ID(N'dbo.Tb_VersaoSistema', N'U') IS NULL
       AND OBJECT_ID(N'dbo.Tb_PLN_VersaoSistema', N'U') IS NOT NULL
    BEGIN
        EXEC sp_rename N'dbo.Tb_PLN_VersaoSistema', N'Tb_VersaoSistema';
    END;

    IF OBJECT_ID(N'dbo.Tb_VersaoSistema', N'U') IS NULL
    BEGIN
        THROW 50001, 'Tabela dbo.Tb_VersaoSistema não encontrada.', 1;
    END;

    IF COL_LENGTH('dbo.Tb_VersaoSistema', 'Id_Sistema') IS NULL
    BEGIN
        ALTER TABLE dbo.Tb_VersaoSistema
        ADD Id_Sistema INT NULL;
    END;

    IF NOT EXISTS (
        SELECT 1
        FROM dbo.Tb_Sistema
        WHERE Id_Sistema = 1
    )
    BEGIN
        THROW 50002, 'O registro Id_Sistema = 1 não existe na dbo.Tb_Sistema.', 1;
    END;

    UPDATE dbo.Tb_VersaoSistema
       SET Id_Sistema = 1
     WHERE Id_Sistema IS NULL;

    IF EXISTS (
        SELECT 1
        FROM sys.columns
        WHERE object_id = OBJECT_ID(N'dbo.Tb_VersaoSistema')
          AND name = 'Id_Sistema'
          AND is_nullable = 1
    )
    BEGIN
        ALTER TABLE dbo.Tb_VersaoSistema
        ALTER COLUMN Id_Sistema INT NOT NULL;
    END;

    IF NOT EXISTS (
        SELECT 1
        FROM sys.foreign_keys
        WHERE name = 'FK_Tb_VersaoSistema_Tb_Sistema_Id_Sistema'
          AND parent_object_id = OBJECT_ID(N'dbo.Tb_VersaoSistema')
    )
    BEGIN
        ALTER TABLE dbo.Tb_VersaoSistema WITH CHECK
        ADD CONSTRAINT FK_Tb_VersaoSistema_Tb_Sistema_Id_Sistema
        FOREIGN KEY (Id_Sistema)
        REFERENCES dbo.Tb_Sistema (Id_Sistema);
    END;

    ;WITH VersoesDuplicadas AS (
        SELECT
            Id,
            ROW_NUMBER() OVER (
                PARTITION BY Id_Sistema, NumeroVersao
                ORDER BY DataLancamento DESC, Id DESC
            ) AS Ordem
        FROM dbo.Tb_VersaoSistema
    )
    DELETE V
      FROM dbo.Tb_VersaoSistema V
      INNER JOIN VersoesDuplicadas D
              ON D.Id = V.Id
     WHERE D.Ordem > 1;

    IF NOT EXISTS (
        SELECT 1
        FROM sys.indexes
        WHERE name = 'UX_Tb_VersaoSistema_IdSistema_NumeroVersao'
          AND object_id = OBJECT_ID(N'dbo.Tb_VersaoSistema')
    )
    BEGIN
        CREATE UNIQUE INDEX UX_Tb_VersaoSistema_IdSistema_NumeroVersao
            ON dbo.Tb_VersaoSistema (Id_Sistema, NumeroVersao);
    END;

    IF NOT EXISTS (
        SELECT 1
        FROM sys.indexes
        WHERE name = 'IX_Tb_VersaoSistema_IdSistema_DataLancamento'
          AND object_id = OBJECT_ID(N'dbo.Tb_VersaoSistema')
    )
    BEGIN
        CREATE INDEX IX_Tb_VersaoSistema_IdSistema_DataLancamento
            ON dbo.Tb_VersaoSistema (Id_Sistema, DataLancamento DESC, Id DESC);
    END;

    COMMIT;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK;
    THROW;
END CATCH;
GO

SELECT
    Id,
    Id_Sistema,
    NumeroVersao,
    Estagio,
    DataLancamento,
    Responsavel,
    HashCommit
FROM dbo.Tb_VersaoSistema
ORDER BY Id_Sistema, DataLancamento DESC, Id DESC;
GO