-- Está query no Python está configurada em ORM SQLAlchemy, mas aqui está em SQL puro para referência.
SELECT 
    CONCAT(c.filial, '-', c.filialctc) AS id_unico,
    c.filial,
    c.filialctc AS ctc,
    c.seriectc AS serie,
    FORMAT(c.data, 'dd/MM/yyyy') AS data_emissao,
    c.hora AS hora_emissao,
    c.prioridade,
    CONCAT(c.cidade_orig, '/', c.uf_orig) AS origem,
    CONCAT(c.cidade_dest, '/', c.uf_dest) AS destino,
    c.rotafilialdest AS unid_lastmile,
    c.remet_nome AS remetente,
    c.dest_nome AS destinatario,
    ISNULL(c.volumes, 0) AS volumes,
    ISNULL(c.pesotax, 0) AS peso_taxado,
    ISNULL(c.valmerc, 0) AS val_mercadoria, 
    ISNULL(c.fretetotalbruto, 0) AS raw_frete_total,
    CASE 
        WHEN c.nfs IS NULL OR c.nfs = '' THEN 
            CASE WHEN ISNULL(c.volumes, 0) > 0 THEN 1 ELSE 0 END
        ELSE 
            (LEN(c.nfs) - LEN(REPLACE(REPLACE(REPLACE(c.nfs, '/', ''), ';', ''), '-', ''))) + 1
    END AS qtd_notas,
    ISNULL(cpl.TipoCarga, '') AS tipo_carga
FROM tb_ctc_esp c
LEFT JOIN tb_ctc_esp_cpl cpl ON c.filialctc = cpl.filialctc
WHERE 
    CAST(c.data AS DATE) = CAST(GETDATE() AS DATE)
    AND c.tipodoc != 'COB'
    AND c.modal LIKE 'AEREO%'
    AND cpl.StatusCTC != 'CTC CANCELADO'
ORDER BY 
    c.data DESC, 
    c.hora DESC