from datetime import datetime, date, time
from decimal import Decimal
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Ctc import CtcEsp, CtcEspCpl
from Models.SQL_SERVER.NfEsp import NfEsp       # <--- Importe Novo
from Models.SQL_SERVER.Ocorrencia import Ocorrencia # <--- Importe Novo
from Services.LogService import LogService

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
            else:
                dados_completos['StatusCTC'] = 'N/A'
                dados_completos['TipoCarga'] = 'N/A'

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