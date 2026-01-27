SELECT 
    s.DATAHORA_STATUS AS [Data],
    s.STATUS_AWB AS [Status],
    s.VOO AS [Numero do Voo],
    s.LOCAL_STATUS AS [Local],
    s.Usuario AS [Quem Fez],
    ta.fantasia AS [Companhia]
FROM 
    intec.dbo.TB_AWB_STATUS s
INNER JOIN 
    intec.dbo.tb_aircadcia ta 
    ON s.CIA COLLATE DATABASE_DEFAULT = ta.codcia COLLATE DATABASE_DEFAULT
WHERE 
    s.CODAWB = '1031845'
ORDER BY 
    s.DATAHORA_STATUS DESC;
