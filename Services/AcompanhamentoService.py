from datetime import datetime, timedelta
from sqlalchemy import func, case, and_, or_, Date, cast, desc
from sqlalchemy.orm import sessionmaker

# --- MODELS SQL SERVER (LEGADO) ---
from Models.SQL_SERVER.Awb import Awb, AwbStatus, AwbNota
from Models.SQL_SERVER.Ctc import Ctc
from Models.SQL_SERVER.Cadastros import CompanhiaAerea
from Conexoes import ObterEngineSqlServer

# --- MODELS POSTGRES (NOVO - MALHA) ---
from Models.POSTGRES.MalhaAerea import VooMalha, RemessaMalha
from Models.POSTGRES.Aeroporto import Aeroporto
from Conexoes import ObterSessaoPostgres

# --- SERVICES ---
from Services.AeroportoService import AeroportoService

class AcompanhamentoService:
    
    @staticmethod
    def _ObterSessaoSql():
        Engine = ObterEngineSqlServer()
        return sessionmaker(bind=Engine)()

    @staticmethod
    def BuscarResumoPainel():
        session = AcompanhamentoService._ObterSessaoSql()
        try:
            Hoje = datetime.now().date()
            TotalHoje = session.query(func.count(Awb.codawb)).filter(cast(Awb.data, Date) == Hoje).scalar()
            return { "EmTransito": TotalHoje or 0, "Pendentes": 0, "EntreguesHoje": 0 }
        except: return { "EmTransito": 0, "Pendentes": 0, "EntreguesHoje": 0 }
        finally: session.close()

    @staticmethod
    def ListarAwbs(filtros=None):
        session = AcompanhamentoService._ObterSessaoSql()
        try:
            query = session.query(Awb, CompanhiaAerea.fantasia)\
                .outerjoin(CompanhiaAerea, Awb.cia.collate('DATABASE_DEFAULT') == CompanhiaAerea.codcia.collate('DATABASE_DEFAULT'))

            if filtros and filtros.get('NumeroAwb'):
                query = query.filter(Awb.awb.like(f"%{filtros['NumeroAwb']}%"))
            else:
                DataInicio = datetime.now().date()
                DataFim = datetime.now().date()
                if filtros:
                    if filtros.get('DataInicio'):
                        try: DataInicio = datetime.strptime(filtros['DataInicio'], '%Y-%m-%d').date()
                        except: pass
                    if filtros.get('DataFim'):
                        try: DataFim = datetime.strptime(filtros['DataFim'], '%Y-%m-%d').date()
                        except: pass
                query = query.filter(cast(Awb.data, Date) >= DataInicio, cast(Awb.data, Date) <= DataFim)

            resultados_awb = query.order_by(Awb.data.desc()).limit(300).all()
            
            lista_numeros = [r[0].awb for r in resultados_awb if r[0].awb]
            dicionario_status = {}
            if lista_numeros:
                st_q = session.query(AwbStatus.CODAWB, AwbStatus.STATUS_AWB, AwbStatus.DATAHORA_STATUS, AwbStatus.VOO)\
                    .filter(AwbStatus.CODAWB.in_(lista_numeros)).order_by(AwbStatus.DATAHORA_STATUS.asc()).all()
                for st in st_q:
                    dicionario_status[st.CODAWB] = {'Status': st.STATUS_AWB, 'Data': st.DATAHORA_STATUS, 'Voo': st.VOO}

            lista_final = []
            for awb_obj, cia_nome in resultados_awb:
                d_st = dicionario_status.get(awb_obj.awb, {'Status': 'AGUARDANDO', 'Data': None, 'Voo': ''})
                geo_o = AeroportoService.BuscarPorSigla(awb_obj.siglaorigem)
                geo_d = AeroportoService.BuscarPorSigla(awb_obj.siglades)

                lista_final.append({
                    "CodigoId": awb_obj.codawb,
                    "Numero": awb_obj.awb,
                    "CiaAerea": cia_nome or awb_obj.nomecia,
                    "Origem": awb_obj.siglaorigem,
                    "Destino": awb_obj.siglades,
                    "Volumes": awb_obj.volumes,
                    "Peso": float(awb_obj.pesoreal or 0),
                    "Status": d_st['Status'],
                    "DataStatus": d_st['Data'].strftime('%d/%m %H:%M') if d_st['Data'] else '',
                    "Voo": d_st['Voo'] or '',
                    "RotaMap": {
                        "Origem": [geo_o.Latitude, geo_o.Longitude] if geo_o and geo_o.Latitude else None,
                        "Destino": [geo_d.Latitude, geo_d.Longitude] if geo_d and geo_d.Latitude else None
                    }
                })
            return lista_final
        except Exception as e:
            return []
        finally: session.close()

    @staticmethod
    def _BuscarDetalhesVooPostgres(numero_voo, data_ref, local_origem=None):
        session_pg = ObterSessaoPostgres()
        try:
            if not numero_voo: return None
            
            # Limpeza
            base_voo = numero_voo.split('/')[0].upper().strip()
            for p in ['G3', 'JJ', 'LA', 'AD', 'TP', 'QR', 'H2']:
                base_voo = base_voo.replace(p, '')
            voo_numerico = "".join(filter(str.isdigit, base_voo))
            
            if not voo_numerico: return None
            
            data_busca = data_ref.date()
            
            def executar_busca(data_alvo):
                # CORREÇÃO: Uso de r'\D' para evitar SyntaxWarning
                q = session_pg.query(VooMalha).join(RemessaMalha, VooMalha.IdRemessa == RemessaMalha.Id)\
                    .filter(
                        RemessaMalha.Ativo == True,
                        cast(VooMalha.DataPartida, Date) == data_alvo,
                        func.regexp_replace(VooMalha.NumeroVoo, r'\D', '', 'g') == voo_numerico
                    )
                if local_origem and len(local_origem) >= 3:
                    q = q.filter(VooMalha.AeroportoOrigem == local_origem[:3].upper())
                return q.first()

            voo = executar_busca(data_busca)
            if not voo: voo = executar_busca(data_busca - timedelta(days=1))

            if not voo: return None

            go = AeroportoService.BuscarPorSigla(voo.AeroportoOrigem)
            gd = AeroportoService.BuscarPorSigla(voo.AeroportoDestino)

            if go and gd:
                return {
                    "Voo": numero_voo, 
                    "VooNumerico": voo_numerico,
                    "Origem": go.CodigoIata, 
                    "Destino": gd.CodigoIata,
                    "CoordOrigem": [go.Latitude, go.Longitude], 
                    "CoordDestino": [gd.Latitude, gd.Longitude],
                    "HorarioPartida": voo.HorarioSaida.strftime('%H:%M') if voo.HorarioSaida else '--:--',
                    "HorarioChegada": voo.HorarioChegada.strftime('%H:%M') if voo.HorarioChegada else '--:--'
                }
            return None
        except: return None
        finally: session_pg.close()

    @staticmethod
    def ObterHistoricoAwb(numero_awb):
        session = AcompanhamentoService._ObterSessaoSql()
        try:
            # 1. Recupera o Destino Final e Origem da AWB (Mestre)
            awb_master = session.query(Awb).filter(Awb.awb == numero_awb).first()
            destino_final_esperado = awb_master.siglades if awb_master else None
            origem_inicial = awb_master.siglaorigem if awb_master else None

            historico_asc = session.query(AwbStatus).filter(AwbStatus.CODAWB == numero_awb)\
                .order_by(AwbStatus.DATAHORA_STATUS.asc()).all()

            dados_retorno = []
            trajeto_consolidado = []
            
            for i, h in enumerate(historico_asc):
                local_atual = h.LOCAL_STATUS.strip() if h.LOCAL_STATUS and h.LOCAL_STATUS.lower() != 'nul' else None
                voo = h.VOO.strip() if h.VOO else None
                
                item = {
                    "Status": h.STATUS_AWB, "Data": h.DATAHORA_STATUS.strftime('%d/%m/%Y %H:%M'),
                    "Local": local_atual or '-', "Usuario": h.Usuario or '-', "Voo": voo or '-', "DetalhesVoo": None
                }

                if voo and len(voo) > 2:
                    detalhes = AcompanhamentoService._BuscarDetalhesVooPostgres(voo, h.DATAHORA_STATUS, local_atual)
                    if detalhes:
                        item["DetalhesVoo"] = detalhes
                        st_upper = h.STATUS_AWB.upper()
                        
                        eh_ultimo = (i == len(historico_asc) - 1)
                        destino_confirmado = False
                        
                        if not eh_ultimo:
                            for j in range(i + 1, len(historico_asc)):
                                prox = historico_asc[j]
                                prox_loc = prox.LOCAL_STATUS.strip()[:3].upper() if prox.LOCAL_STATUS and prox.LOCAL_STATUS.lower() != 'nul' else None
                                if prox_loc:
                                    if prox_loc == detalhes['Destino']: destino_confirmado = True
                                    if prox_loc == detalhes['Origem']: destino_confirmado = False
                                    break
                        
                        desenhar = False
                        if eh_ultimo:
                            if any(x in st_upper for x in ["VOO", "PARTIDA", "DECOLOU", "TRANSITO"]):
                                desenhar = True
                        else:
                            desenhar = destino_confirmado

                        if desenhar:
                            if not trajeto_consolidado or \
                               (trajeto_consolidado[-1]['VooNumerico'] != detalhes['VooNumerico'] or \
                                trajeto_consolidado[-1]['Origem'] != detalhes['Origem']):
                                trajeto_consolidado.append(detalhes)

                dados_retorno.append(item)

            # --- CÁLCULO DA ROTA PENDENTE (COM CORREÇÃO DE INVERSÃO) ---
            rota_pendente = None
            local_atual_mapa = None

            # 1. Determina Local Atual
            if trajeto_consolidado:
                local_atual_mapa = trajeto_consolidado[-1]['Destino']
            elif historico_asc:
                # Pega o último status válido com local
                for h in reversed(historico_asc):
                    if h.LOCAL_STATUS and h.LOCAL_STATUS.lower() != 'nul':
                        local_atual_mapa = h.LOCAL_STATUS.strip()[:3].upper()
                        break
            
            # 2. Verifica Inversão de Rota (Onde o cadastro diz uma coisa, mas a realidade é outra)
            destino_real = destino_final_esperado
            
            # Se a carga começou exatamente onde o cadastro diz que deveria terminar...
            if historico_asc and destino_final_esperado:
                primeiro_h = historico_asc[0]
                primeiro_local = primeiro_h.LOCAL_STATUS.strip()[:3].upper() if primeiro_h.LOCAL_STATUS and primeiro_h.LOCAL_STATUS.lower() != 'nul' else None
                
                if primeiro_local == destino_final_esperado:
                    # ...então o destino real provavelmente é a Origem do Cadastro (Logística Reversa ou Erro)
                    destino_real = origem_inicial

            # 3. Fallback se não achou local atual
            if not local_atual_mapa and origem_inicial:
                local_atual_mapa = origem_inicial

            # 4. Gera a Rota Pendente apenas se não estivermos no destino
            if local_atual_mapa and destino_real and local_atual_mapa != destino_real:
                geo_atual = AeroportoService.BuscarPorSigla(local_atual_mapa)
                geo_final = AeroportoService.BuscarPorSigla(destino_real)
                
                if geo_atual and geo_final:
                    rota_pendente = {
                        "Origem": local_atual_mapa,
                        "Destino": destino_real,
                        "CoordOrigem": [geo_atual.Latitude, geo_atual.Longitude],
                        "CoordDestino": [geo_final.Latitude, geo_final.Longitude]
                    }

            return { 
                "Historico": dados_retorno[::-1], 
                "TrajetoCompleto": trajeto_consolidado,
                "RotaPendente": rota_pendente 
            }
        finally: session.close()

    @staticmethod
    def ListarCtcSemAwb(): return []