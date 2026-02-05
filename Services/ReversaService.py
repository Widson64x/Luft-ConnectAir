from datetime import datetime
from sqlalchemy import text
from Conexoes import ObterSessaoSqlServer
from Services.LogService import LogService
from Models.SQL_SERVER.Reversa import ControleReversa

class ReversaService:
    
    @staticmethod
    def ListarDevolucoesPendentes(modal='AEREO'):
        """
        Lista as devoluções pendentes usando SQL NATIVO OTIMIZADO (NOLOCK).
        Filtra estritamente por motivodoc = 'DEV'.
        
        CORREÇÃO: 
        - Modal 'AEREO' agora traz: (Modal=AEREO e Sem TM) OU (Modal=RODOVIARIO e Com TM).
        - Ocorrência TM (Terminal) indica que a carga rodoviária entrou no fluxo aéreo.
        """
        Sessao = ObterSessaoSqlServer()
        try:
            sql_query = text("""
                SELECT 
                      c.filial
                    , c.seriectc
                    , c.filialctc as CTC
                    , C.MODAL as Modal
                    , m.filialmanifesto as Manifesto
                    , m.motivo as MotvoManif
                    , c.tabfrete as Tabela
                    , c.tabfretedescr as TabDescricao
                    , c.natureza as Natureza
                    , c.motivodoc as MotivoCTC
                    , c.data as DataOriginal
                    , convert(varchar, c.data, 103) as DataCTC
                    , convert(varchar, c.prev_entrega, 103) as DataEntrega
                    , cl.ultimaocorrctccodocorr as UltOcorr
                    , c.respons_cgc as CNPJEmbarcador
                    , c.respons_nome as Embarcador
                    , upper(c.remet_nome) as Remetente
                    , c.dest_nome as Destinatario
                    , c.volumes
                    , c.peso
                    
                    -- Inversão de Praça para Devolução
                    , c.dest_UF as UFOrigem
                    , c.remet_uf as UFDestino
                    , c.remet_cidade as CidadeDestino
                    , c.dest_cidade as CidadeOrigem
                    
                    , ISNULL(cl.TipoCarga, '') AS Tipo_carga
                    
                    -- Dados do Controle Interno
                    , ctrl.LiberadoPlanejamento
                    , ctrl.UsuarioResponsavel
                    , ctrl.IdControle

                FROM intec.dbo.tb_ctc_esp c (nolock) 
                INNER JOIN intec.dbo.tb_ctc_esp_cpl cl (nolock) on cl.filialctc = c.filialctc
                INNER JOIN intec.dbo.tb_nf_esp n (nolock) on n.filialctc = c.filialctc
                
                -- Joins Opcionais
                LEFT JOIN intec.dbo.tb_airAWBnota B (NOLOCK) ON c.filialctc = b.filialctc and  n.numnf = b.nota  collate database_default
                LEFT JOIN intec.dbo.tb_airawb A (NOLOCK) ON A.codawb = B.codawb 
                LEFT JOIN intec.dbo.CTe_infCte cte(NOLOCK) ON c.filialctc COLLATE DATABASE_DEFAULT = cte.Id COLLATE DATABASE_DEFAULT 
                LEFT JOIN intec.dbo.tb_manifesto m (nolock) on m.filialctc = c.filialctc
                
                LEFT JOIN intec.dbo.Tb_PLN_ControleReversa ctrl (nolock)
                    ON ctrl.Filial COLLATE DATABASE_DEFAULT = c.filial COLLATE DATABASE_DEFAULT
                    AND ctrl.Serie COLLATE DATABASE_DEFAULT = c.seriectc COLLATE DATABASE_DEFAULT
                    AND ctrl.Ctc COLLATE DATABASE_DEFAULT = c.filialctc COLLATE DATABASE_DEFAULT

                WHERE c.data > getdate() - 120
                AND c.motivodoc = 'DEV'
                and n.filialctc = c.filialctc COLLATE DATABASE_DEFAULt
                and a.codawb is null
                
                -- LÓGICA DO MODAL CORRIGIDA
                AND (
                    -- Se pedir AEREO, traz: (AEREO puro) OU (RODOVIARIO virou AEREO via TM)
                    (:modal = 'AEREO' AND (
                        (c.modal = 'AEREO' AND NOT EXISTS (select 1 from intec.dbo.tb_ocorr cr (nolock) where cr.cod_ocorr = 'TM' and cr.filialctc = c.filialctc))
                        OR 
                        (c.modal = 'RODOVIARIO' AND EXISTS (select 1 from intec.dbo.tb_ocorr cr (nolock) where cr.cod_ocorr = 'TM' and cr.filialctc = c.filialctc))
                    ))
                    
                    OR 
                    
                    -- Se pedir RODOVIARIO (caso precise no futuro), traz o inverso (Rodo sem TM)
                    (:modal = 'RODOVIARIO' AND (
                         c.modal = 'RODOVIARIO' AND NOT EXISTS (select 1 from intec.dbo.tb_ocorr cr (nolock) where cr.cod_ocorr = 'TM' and cr.filialctc = c.filialctc)
                    ))
                )

                and c.tem_ocorr not in ('C','0','1') 
                and c.tipodoc <> 'COB'
                and left(c.respons_cgc,8) <> '02426290'
                and (a.cancelado is null or a.cancelado = '') 
                and m.cancelado is null
                and (m.motivo noT in ('TRA','RED') OR M.MOTIVO IS NULL)

                GROUP BY 
                      c.filialctc
                    , c.filial
                    , c.seriectc
                    , c.tabfrete
                    , c.natureza
                    , c.motivodoc
                    , c.data
                    , c.prev_entrega
                    , c.respons_cgc
                    , c.respons_nome
                    , c.remet_nome
                    , c.dest_nome
                    , c.volumes
                    , c.peso
                    , c.remet_cidade
                    , c.remet_uf 
                    , c.dest_uf 
                    , c.dest_cidade
                    , c.cidade_orig
                    , cl.TipoCarga
                    , cl.ultimaocorrctccodocorr
                    , m.filialmanifesto
                    , m.motivo
                    , c.tabfretedescr
                    , C.MODAL
                    , ctrl.LiberadoPlanejamento
                    , ctrl.UsuarioResponsavel
                    , ctrl.IdControle

                ORDER BY c.data
            """)

            Resultados = Sessao.execute(sql_query, {'modal': modal}).fetchall()

            Qtd = len(Resultados)
            LogService.Info("ReversaService", f"Busca realizada (SQL OTIMIZADO + TM CORRIGIDO). Modal: {modal}. Encontrados: {Qtd}.")

            ListaRetorno = []
            
            for row in Resultados:
                liberado = False
                responsavel = '-'
                
                if row.IdControle:
                    liberado = bool(row.LiberadoPlanejamento)
                    responsavel = row.UsuarioResponsavel or '-'

                ListaRetorno.append({
                    'filial': str(row.filial).strip(),
                    'serie': str(row.seriectc).strip(),
                    'ctc': str(row.CTC).strip(),
                    'data_emissao': str(row.DataCTC).strip(),
                    'remetente': str(row.Remetente).strip(),
                    'destinatario': str(row.Destinatario or '').strip(),
                    'cidade_origem': str(row.CidadeOrigem).strip(),
                    'cidade_destino': str(row.CidadeDestino).strip(),
                    'volumes': int(row.volumes or 0),
                    'peso': float(row.peso or 0),
                    'is_liberado': liberado,
                    'responsavel': responsavel,
                    'tipo_carga': str(row.Tipo_carga).strip(),
                    'ultima_ocorrencia': str(row.UltOcorr or '').strip()
                })

            return ListaRetorno

        except Exception as e:
            LogService.Error("ReversaService", "Erro ao listar devoluções (SQL Otimizado)", e)
            return []
        finally:
            Sessao.close()

    @staticmethod
    def AtualizarStatusReversa(filial, serie, ctc, status_liberado, usuario):
        Sessao = ObterSessaoSqlServer()
        try:
            Registro = Sessao.query(ControleReversa).filter(
                ControleReversa.Filial == str(filial),
                ControleReversa.Serie == str(serie),
                ControleReversa.Ctc == str(ctc)
            ).first()

            if not Registro:
                Registro = ControleReversa(
                    Filial=str(filial),
                    Serie=str(serie),
                    Ctc=str(ctc),
                    LiberadoPlanejamento=status_liberado,
                    UsuarioResponsavel=usuario,
                    DataAtualizacao=datetime.now()
                )
                Sessao.add(Registro)
            else:
                Registro.LiberadoPlanejamento = status_liberado
                Registro.UsuarioResponsavel = usuario
                Registro.DataAtualizacao = datetime.now()

            Sessao.commit()
            return True, "Status atualizado com sucesso"
        except Exception as e:
            Sessao.rollback()
            LogService.Error("ReversaService", "Erro ao atualizar status", e)
            return False, str(e)
        finally:
            Sessao.close()