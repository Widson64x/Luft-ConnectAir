from datetime import datetime
from sqlalchemy import and_, or_
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Reversa import ControleReversa
from Models.SQL_SERVER.Ctc import CtcEsp
from Models.SQL_SERVER.Awb import AwbNota
from Services.LogService import LogService

class ReversaService:
    
    @staticmethod
    def ListarDevolucoesPendentes():
        """
        Busca CTCs com Motivo 'DEV' e Modal 'AEREO' que NÃO possuem AWB emitido.
        """
        Sessao = ObterSessaoSqlServer()
        try:
            COLLATE_FIX = 'DATABASE_DEFAULT'

            # Query Base
            # select ctc.*, controle.*
            # from CtcEsp ctc
            # left join AwbNota awb on ctc.filialctc = awb.filialctc
            # left join ControleReversa controle on
            #     ctc.filial = controle.Filial and
            #     ctc.seriectc = controle.Serie and
            #     ctc.filialctc = controle.Ctc
            # where ctc.motivodoc = 'DEV'
            #   and ctc.tipodoc != 'COB'
            #   and ctc.modal like 'AEREO%'
            #   and (awb.codawb is null or awb.codawb = '')
            # order by ctc.data desc
            # limit 200;
            # Pega todos os CTCs que são devoluções aéreas sem AWB emitido
            # Construção da Query
            Query = Sessao.query(CtcEsp, ControleReversa)\
                .outerjoin(
                    AwbNota, 
                    CtcEsp.filialctc.collate(COLLATE_FIX) == AwbNota.filialctc.collate(COLLATE_FIX)
                )\
                .outerjoin(ControleReversa, and_(
                    CtcEsp.filial.collate(COLLATE_FIX) == ControleReversa.Filial.collate(COLLATE_FIX),
                    CtcEsp.seriectc.collate(COLLATE_FIX) == ControleReversa.Serie.collate(COLLATE_FIX),
                    CtcEsp.filialctc.collate(COLLATE_FIX) == ControleReversa.Ctc.collate(COLLATE_FIX)
                ))\
                .filter(
                    CtcEsp.motivodoc == 'DEV',
                    CtcEsp.tipodoc != 'COB',
                    # CORREÇÃO: Aceita AEREO (sem acento) OU AÉREO (com acento)
                    or_(
                        CtcEsp.modal.like('AEREO%'),
                        CtcEsp.modal.like('AÉREO%') 
                    ),
                    # Filtra quem NÃO tem AWB (Join falhou ou campo vazio)
                    or_(
                        AwbNota.codawb == None,
                        AwbNota.codawb.collate(COLLATE_FIX) == ''
                    )
                )\
                .order_by(CtcEsp.data.desc())\
                .limit(200)

            # Executa
            Resultados = Query.all()
            
            # --- LOG DE DIAGNÓSTICO (Para entendermos o que está retornando) ---
            Qtd = len(Resultados)
            LogService.Info("ReversaService", f"Busca realizada. Encontrados: {Qtd} registros.")
            # ------------------------------------------------------------------

            ListaRetorno = []
            for ctc, controle in Resultados:
                liberado = False
                responsavel = '-'
                
                if controle:
                    liberado = controle.LiberadoPlanejamento
                    responsavel = controle.UsuarioResponsavel or '-'

                ListaRetorno.append({
                    'filial': str(ctc.filial).strip(),
                    'serie': str(ctc.seriectc).strip(),
                    'ctc': str(ctc.filialctc).strip(),
                    'data_emissao': ctc.data.strftime('%d/%m/%Y') if ctc.data else '',
                    'remetente': str(ctc.remet_nome).strip(),
                    'destinatario': str(ctc.dest_nome).strip(),
                    'cidade_origem': str(ctc.cidade_orig).strip(),
                    'cidade_destino': str(ctc.cidade_dest).strip(), # Corrigido: cidade_dest
                    'volumes': int(ctc.volumes or 0),
                    'peso': float(ctc.peso or 0),
                    'is_liberado': liberado,
                    'responsavel': responsavel
                })

            return ListaRetorno

        except Exception as e:
            LogService.Error("ReversaService", "Erro ao listar devoluções", e)
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