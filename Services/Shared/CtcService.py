from datetime import datetime, date, time
from decimal import Decimal
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Ctc import CtcEsp, CtcEspFarma, CtcEspCpl
from Models.SQL_SERVER.NfEsp import NfEsp
from Models.SQL_SERVER.Ocorrencia import Ocorrencia
from Services.LogService import LogService

class CtcService:
    """
    Serviço Compartilhado para operações globais de CTC.
    Acessível por qualquer módulo (Planejamento, Reversa, Monitoramento).
    """

from datetime import datetime, date, time
from decimal import Decimal
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Ctc import CtcEsp, CtcEspCpl
from Models.SQL_SERVER.NfEsp import NfEsp       
from Models.SQL_SERVER.Ocorrencia import Ocorrencia 
from Services.LogService import LogService

# Importe para buscar as regras do cliente dinamicamente
from Services.PlanejamentoService import PlanejamentoService

class CtcService:
    """
    Serviço Compartilhado para operações globais de CTC.
    Acessível por qualquer módulo (Planejamento, Reversa, Monitoramento).
    """

    @staticmethod
    def ObterCtcCompleto(filial, serie, ctc_num):
        """
        Busca um CTC específico + CPL + NFs + Ocorrências
        Retorna um dicionário unificado e estruturado.
        """
        Sessao = ObterSessaoSqlServer()
        try:
            # Busca flexível
            f, s, n = str(filial).strip(), str(serie).strip(), str(ctc_num).strip()
            
            # 1. Busca CTC e CPL
            Query = Sessao.query(CtcEsp, CtcEspCpl).outerjoin(
                CtcEspCpl, 
                CtcEsp.filialctc == CtcEspCpl.filialctc
            ).filter(
                CtcEsp.filial == f,
                CtcEsp.seriectc == s,
                CtcEsp.filialctc == n
            )

            Resultado = Query.first()

            if not Resultado: 
                LogService.Warning("Shared.CtcService", f"CTC não encontrado {f}-{s}-{n}")
                return None

            Ctc, Cpl = Resultado
            dados_completos = {}

            # --- Helper Local de Serialização ---
            def safe_val(val):
                if isinstance(val, (datetime, date)): return val.strftime('%d/%m/%Y %H:%M')
                if isinstance(val, time): return str(val)
                if isinstance(val, Decimal): return float(val)
                if val is None: return ""
                return str(val)

            # 2. Serializa CTC Principal
            for coluna in Ctc.__table__.columns:
                dados_completos[coluna.name] = safe_val(getattr(Ctc, coluna.name))
            
            # 3. Serializa CPL
            if Cpl:
                for coluna in Cpl.__table__.columns:
                    dados_completos[coluna.name] = safe_val(getattr(Cpl, coluna.name))
                
                # ---------------------------------------------------------
                # NOVA LÓGICA: INTERCEPTAÇÃO SUBCONTRATAÇÃO FARMA
                # ---------------------------------------------------------
                ctc_corresp = getattr(Cpl, 'ctc_corresp', None)
                if ctc_corresp and str(ctc_corresp).strip():
                    # Busca na tabela da Farma usando o ctc_corresp
                    ctc_farma = Sessao.query(CtcEspFarma).filter(
                        CtcEspFarma.filialctc == str(ctc_corresp).strip()
                    ).first()
                    
                    if ctc_farma:
                        # Temos uma subcontratação! Substituímos os dados no dict principal
                        # Usando 'respons_nome' e 'respons_cgc' da Farma como você pediu
                        cliente_real_nome = safe_val(getattr(ctc_farma, 'respons_nome'))
                        cliente_real_cgc = safe_val(getattr(ctc_farma, 'respons_cgc'))
                        
                        # Sobrescreve as variáveis do remetente/responsável no dicionário final
                        dados_completos['remet_nome'] = cliente_real_nome
                        dados_completos['remet_cgc'] = cliente_real_cgc
                        dados_completos['respons_nome'] = cliente_real_nome
                        dados_completos['respons_cgc'] = cliente_real_cgc
                        
                        # Opcional: Criar uma flag para o Front-end saber que foi subcontratado
                        dados_completos['is_subcontratacao_farma'] = True
            else:
                dados_completos['StatusCTC'] = 'N/A'
                dados_completos['TipoCarga'] = 'N/A'

            # ---------------------------------------------------------
            # 3.1. NOVO: Captura as Regras do Cliente e Serviço Contratado
            # ---------------------------------------------------------
            cnpj_alvo = getattr(Ctc, 'respons_cgc', None) or getattr(Ctc, 'remet_cgc', None)
            dados_completos['servico_contratado'] = PlanejamentoService.BuscarServicoContratadoCliente(
                getattr(Ctc, 'respons_cgc', None),
                getattr(Ctc, 'remet_cgc', None),
                getattr(Ctc, 'dest_cgc', None)
            )

            # ---------------------------------------------------------
            # 4. Busca e Serializa NOTAS FISCAIS (tb_nf_esp)
            # ---------------------------------------------------------
            ResultNFs = Sessao.query(NfEsp).filter(NfEsp.filialctc == n).all()
            ListaNFs = []
            for item in ResultNFs:
                nf_dict = {}
                for col in item.__table__.columns:
                    nf_dict[col.name] = safe_val(getattr(item, col.name))
                ListaNFs.append(nf_dict)
            dados_completos['_ListaNFs'] = ListaNFs

            # ---------------------------------------------------------
            # 5. Busca e Serializa OCORRÊNCIAS (tb_ocorr) - TIMELINE
            # ---------------------------------------------------------
            ResultOcorr = Sessao.query(Ocorrencia).filter(
                Ocorrencia.filialctc == n
            ).order_by(Ocorrencia.data, Ocorrencia.hora).all() # Ordenado por data/hora

            ListaOcorr = []
            for item in ResultOcorr:
                oc_dict = {}
                for col in item.__table__.columns:
                    oc_dict[col.name] = safe_val(getattr(item, col.name))
                ListaOcorr.append(oc_dict)
            dados_completos['_ListaOcorrencias'] = ListaOcorr
            # ---------------------------------------------------------

            return dados_completos

        except Exception as e:
            LogService.Error("Shared.CtcService", "Erro ao obter CTC completo", e)
            return None
        finally:
            Sessao.close()