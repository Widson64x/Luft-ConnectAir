from datetime import datetime, date, time
from decimal import Decimal

from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Ctc import CtcEsp, CtcEspCpl, CtcEspFarma
from Models.SQL_SERVER.NfEsp import NfEsp
from Models.SQL_SERVER.Ocorrencia import Ocorrencia
from Services.LogService import LogService
from Services.PlanejamentoService import PlanejamentoService

class CtcService:
    """
    Serviço Compartilhado para operações globais de CTC.
    Acessível por qualquer módulo (Planejamento, Reversa, Monitoramento).
    """

    CAMPOS_SOBREPOSICAO_FARMA = (
        'origem',
        'remet_cgc',
        'remet_nome',
        'remet_end',
        'remet_cidade',
        'remet_uf',
        'remet_cep',
        'remet_ie',
        'respons_cgc',
        'respons_nome',
        'respons_end',
        'respons_cidade',
        'respons_uf',
        'respons_ie',
        'dest_cgc',
        'dest_nome',
        'dest_end',
        'dest_cidade',
        'dest_uf',
        'dest_cep',
        'dest_ie',
        'cidade_orig',
        'uf_orig',
        'cidade_dest',
        'uf_dest',
    )

    @staticmethod
    def _buscar_ctc_farma(sessao, ctc_corresp):
        candidatos = []
        valor_base = str(ctc_corresp or '').strip()

        for valor in (valor_base, valor_base.lstrip('0'), valor_base.zfill(10)):
            if valor and valor not in candidatos:
                candidatos.append(valor)

        for candidato in candidatos:
            ctc_farma = sessao.query(CtcEspFarma).filter(CtcEspFarma.filialctc == candidato).first()
            if ctc_farma:
                return ctc_farma

        return None

    @staticmethod
    def _sobrepor_dados_cadastro_farma(dados_completos, ctc_farma, safe_val):
        for campo in CtcService.CAMPOS_SOBREPOSICAO_FARMA:
            valor = getattr(ctc_farma, campo, None)
            if valor is None:
                continue

            valor_limpo = str(valor).strip() if isinstance(valor, str) else valor
            if valor_limpo == '':
                continue

            dados_completos[campo] = safe_val(valor)

        dados_completos['is_subcontratacao_farma'] = True

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
                
                ctc_corresp = getattr(Cpl, 'ctc_corresp', None)
                if ctc_corresp and str(ctc_corresp).strip():
                    ctc_farma = CtcService._buscar_ctc_farma(Sessao, ctc_corresp)
                    
                    if ctc_farma:
                        CtcService._sobrepor_dados_cadastro_farma(dados_completos, ctc_farma, safe_val)
            else:
                dados_completos['StatusCTC'] = 'N/A'
                dados_completos['TipoCarga'] = 'N/A'

            dados_completos['servico_contratado'] = PlanejamentoService.BuscarServicoContratadoCliente(
                dados_completos.get('respons_cgc'),
                dados_completos.get('remet_cgc'),
                dados_completos.get('dest_cgc')
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