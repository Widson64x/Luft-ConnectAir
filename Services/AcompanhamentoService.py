from datetime import datetime, timedelta
from sqlalchemy import func, case, and_, or_, Date, cast, desc
from sqlalchemy.orm import sessionmaker

# --- MODELS SQL SERVER (LEGADO) ---
# Certifique-se de que o arquivo Models/SQL_SERVER/Awb.py foi atualizado com as novas colunas
from Models.SQL_SERVER.Awb import Awb, AwbStatus, AwbNota
from Models.SQL_SERVER.Ctc import Ctc
from Models.SQL_SERVER.Cadastros import CompanhiaAerea
from Conexoes import ObterEngineSqlServer

# --- MODELS POSTGRES (NOVO - MALHA) ---
from Models.POSTGRES.MalhaAerea import VooMalha, RemessaMalha
from Models.POSTGRES.Aeroporto import Aeroporto
from Conexoes import ObterSessaoPostgres

# --- SERVICES ---
from Services.AeroportosService import AeroportoService

class AcompanhamentoService:
    
    @staticmethod
    def _ObterSessaoSql():
        Engine = ObterEngineSqlServer()
        return sessionmaker(bind=Engine)()

    # --- KPI DO PAINEL ---
    @staticmethod
    def BuscarResumoPainel():
        session = AcompanhamentoService._ObterSessaoSql()
        try:
            Hoje = datetime.now().date()
            TotalHoje = session.query(func.count(Awb.codawb)).filter(cast(Awb.data, Date) == Hoje).scalar()
            return { "EmTransito": TotalHoje or 0, "Pendentes": 0, "EntreguesHoje": 0 }
        except: return { "EmTransito": 0, "Pendentes": 0, "EntreguesHoje": 0 }
        finally: session.close()

    # --- LISTAGEM PRINCIPAL (TABELA) ---
    @staticmethod
    def ListarAwbs(filtros=None):
        session = AcompanhamentoService._ObterSessaoSql()
        try:
            # Inicia a query base unindo com a tabela de Cia Aérea para pegar o nome fantasia
            query = session.query(Awb, CompanhiaAerea.fantasia)\
                .outerjoin(CompanhiaAerea, Awb.cia.collate('DATABASE_DEFAULT') == CompanhiaAerea.codcia.collate('DATABASE_DEFAULT'))

            # --- APLICAÇÃO DOS FILTROS ---
            if filtros:
                # 1. Filtro por Número da AWB (Prioridade Alta)
                if filtros.get('NumeroAwb'):
                    # Limpa caracteres não numéricos se necessário ou busca direta
                    # Aqui usamos like para flexibilidade
                    query = query.filter(Awb.awb.like(f"%{filtros['NumeroAwb']}%"))
                
                # 2. NOVO FILTRO: Filial CTC / Documento Vinculado
                elif filtros.get('FilialCtc'):
                    valor_busca = filtros['FilialCtc'].strip()
                    
                    # Faz o JOIN com a tabela de Notas (tb_airAWBnota) usando o codawb
                    # Isso permite filtrar registros na tabela principal baseados em dados da tabela filha
                    query = query.join(AwbNota, Awb.codawb == AwbNota.codawb)\
                        .filter(
                            or_(
                                # Busca pela Filial do CTC (ex: SAO, VCP)
                                AwbNota.filialctc.like(f"%{valor_busca}%"),
                                # Busca também pelo Número da Nota/CTC para facilitar
                                # AwbNota.nota.like(f"%{valor_busca}%")
                            )
                        )
                
                # 3. Filtro de Data (Padrão se não houver busca específica)
                else:
                    DataInicio = datetime.now().date()
                    DataFim = datetime.now().date()
                    
                    if filtros.get('DataInicio'):
                        try: DataInicio = datetime.strptime(filtros['DataInicio'], '%Y-%m-%d').date()
                        except: pass
                    
                    if filtros.get('DataFim'):
                        try: DataFim = datetime.strptime(filtros['DataFim'], '%Y-%m-%d').date()
                        except: pass
                    
                    # Filtra pelo intervalo de datas de emissão da AWB
                    query = query.filter(cast(Awb.data, Date) >= DataInicio, cast(Awb.data, Date) <= DataFim)

            # Executa a query limitando a 300 resultados para performance
            # Ordena da mais recente para a mais antiga
            resultados_awb = query.order_by(Awb.data.desc()).limit(300).all()
            
            # --- OTIMIZAÇÃO: BUSCA DE STATUS EM LOTE ---
            # Coleta os IDs (AWB Número) para buscar os status de uma vez só
            lista_numeros = [r[0].awb for r in resultados_awb if r[0].awb]
            dicionario_status = {}
            
            if lista_numeros:
                st_q = session.query(
                    AwbStatus.CODAWB, 
                    AwbStatus.STATUS_AWB, 
                    AwbStatus.DATAHORA_STATUS, 
                    AwbStatus.DATA_INSERT, 
                    AwbStatus.VOO
                ).filter(AwbStatus.CODAWB.in_(lista_numeros))\
                 .order_by(AwbStatus.DATAHORA_STATUS.asc()).all()
                
                for st in st_q:
                    # Sobrescreve no dicionário mantendo sempre o último status (mais recente devido ao order by asc)
                    dicionario_status[st.CODAWB] = {
                        'Status': st.STATUS_AWB, 
                        'Data': st.DATAHORA_STATUS, 
                        'Voo': st.VOO, 
                        'DataInsert': st.DATA_INSERT
                    }

            # --- MONTAGEM DA LISTA FINAL ---
            lista_final = []
            for awb_obj, cia_nome in resultados_awb:
                # Recupera status do dicionário ou define padrão
                d_st = dicionario_status.get(awb_obj.awb, {
                    'Status': 'AGUARDANDO', 
                    'Data': None, 
                    'Voo': '', 
                    'DataInsert': None
                })
                
                # Busca coordenadas para o mapa
                geo_o = AeroportoService.BuscarPorSigla(awb_obj.siglaorigem)
                geo_d = AeroportoService.BuscarPorSigla(awb_obj.siglades)

                lista_final.append({
                    "CodigoId": awb_obj.codawb, # Chave Primária para abrir Modal
                    "Numero": awb_obj.awb,
                    "CiaAerea": cia_nome or awb_obj.nomecia,
                    "Origem": awb_obj.siglaorigem,
                    "Destino": awb_obj.siglades,
                    "Volumes": awb_obj.volumes,
                    "Peso": float(awb_obj.pesoreal or 0),
                    "Status": d_st['Status'],
                    "DataStatus": d_st['Data'].strftime('%d/%m %H:%M') if d_st['Data'] else '',
                    "DataInsert": d_st['DataInsert'].strftime('%d/%m/%Y %H:%M') if d_st['DataInsert'] else '',
                    "Voo": d_st['Voo'] or '',
                    "RotaMap": {
                        "Origem": [geo_o.Latitude, geo_o.Longitude] if geo_o and geo_o.Latitude else None,
                        "Destino": [geo_d.Latitude, geo_d.Longitude] if geo_d and geo_d.Latitude else None
                    }
                })
                
            return lista_final

        except Exception as e:
            print(f"Erro ao listar AWBs: {e}")
            return []
        finally:
            session.close()

    # --- HELPER: LIMPEZA DE NÚMERO DE VOO ---
    @staticmethod
    def _LimparNumeroVoo(numero_voo):
        """
        Remove prefixos (G3, LA), sufixos (/19JAN) e retorna apenas os dígitos do voo.
        Ex: 'G31182/19JAN' -> '1182'
        """
        if not numero_voo: return ""
        
        # 1. Pega tudo antes da barra "/"
        base = numero_voo.split('/')[0].upper().strip()
        
        # 2. Remove prefixos de Cia conhecidos
        prefixos = ['G3', 'JJ', 'LA', 'AD', 'TP', 'QR', 'H2', 'CM', 'AC', 'AF', 'UX']
        for p in prefixos:
            base = base.replace(p, '')
            
        # 3. Extrai apenas os dígitos restantes
        return "".join(filter(str.isdigit, base))

    # --- BUSCA DETALHES DO VOO (MALHA POSTGRES) ---
    @staticmethod
    def _BuscarDetalhesVooPostgres(numero_voo, data_ref, local_origem=None):
        session_pg = ObterSessaoPostgres()
        try:
            voo_numerico = AcompanhamentoService._LimparNumeroVoo(numero_voo)
            if not voo_numerico: return None
            
            data_busca = data_ref.date()
            
            def executar_busca(data_alvo):
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

    # --- HISTÓRICO PARA O MAPA/TIMELINE ---
    @staticmethod
    def ObterHistoricoAwb(numero_awb):
        session = AcompanhamentoService._ObterSessaoSql()
        try:
            # 1. Recupera AWB Mestre para saber Origem/Destino previstos
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
                    "Status": h.STATUS_AWB, 
                    "Data": h.DATAHORA_STATUS.strftime('%d/%m/%Y %H:%M'),
                    "Local": local_atual or '-', 
                    "Usuario": h.Usuario or '-', 
                    "Voo": voo or '-', 
                    "DetalhesVoo": None
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

            # Cálculo de Rota Pendente
            rota_pendente = None
            local_atual_mapa = None

            if trajeto_consolidado:
                local_atual_mapa = trajeto_consolidado[-1]['Destino']
            elif historico_asc:
                for h in reversed(historico_asc):
                    if h.LOCAL_STATUS and h.LOCAL_STATUS.lower() != 'nul':
                        local_atual_mapa = h.LOCAL_STATUS.strip()[:3].upper()
                        break
            
            destino_real = destino_final_esperado
            if historico_asc and destino_final_esperado:
                primeiro_h = historico_asc[0]
                primeiro_local = primeiro_h.LOCAL_STATUS.strip()[:3].upper() if primeiro_h.LOCAL_STATUS and primeiro_h.LOCAL_STATUS.lower() != 'nul' else None
                if primeiro_local == destino_final_esperado:
                    destino_real = origem_inicial

            if not local_atual_mapa and origem_inicial:
                local_atual_mapa = origem_inicial

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
        except: 
            return { "Historico": [], "TrajetoCompleto": [], "RotaPendente": None }
        finally: session.close()

    # --- MODAL VOO (MALHA PREVISTA) ---
    @staticmethod
    def BuscarDetalhesVooModal(numero_voo, data_ref_str):
        session_pg = ObterSessaoPostgres()
        try:
            voo_numerico = AcompanhamentoService._LimparNumeroVoo(numero_voo)
            if not voo_numerico: return None

            try: data_busca = datetime.strptime(data_ref_str, '%d/%m/%Y %H:%M').date()
            except:
                try: data_busca = datetime.strptime(data_ref_str, '%Y-%m-%d').date()
                except: data_busca = datetime.now().date()

            def query_voo(data):
                return session_pg.query(VooMalha).join(RemessaMalha)\
                    .filter(
                        RemessaMalha.Ativo == True,
                        cast(VooMalha.DataPartida, Date) == data,
                        func.regexp_replace(VooMalha.NumeroVoo, r'\D', '', 'g') == voo_numerico
                    ).first()

            voo = query_voo(data_busca)
            if not voo: voo = query_voo(data_busca - timedelta(days=1))

            if not voo: return None

            origem = AeroportoService.BuscarPorSigla(voo.AeroportoOrigem)
            destino = AeroportoService.BuscarPorSigla(voo.AeroportoDestino)

            return {
                "Cia": voo.CiaAerea,
                "Numero": voo.NumeroVoo,
                "Data": voo.DataPartida.strftime('%d/%m/%Y'),
                "OrigemIata": voo.AeroportoOrigem,
                "OrigemNome": origem.NomeAeroporto if origem else "Aeroporto de Origem",
                "DestinoIata": voo.AeroportoDestino,
                "DestinoNome": destino.NomeAeroporto if destino else "Aeroporto de Destino",
                "HorarioSaida": voo.HorarioSaida.strftime('%H:%M'),
                "HorarioChegada": voo.HorarioChegada.strftime('%H:%M'),
                "Status": "PROGRAMADO"
            }
        except Exception as e:
            return None
        finally: session_pg.close()

    @staticmethod
    def BuscarDetalhesAwbCompleto(cod_awb_req):
        session = AcompanhamentoService._ObterSessaoSql()
        try:
            # 1. Busca Tabela Base (tb_airAWB) pelo codawb
            awb = session.query(Awb).filter(Awb.codawb == cod_awb_req).first()
            if not awb: return None
            
            def fmt(v, t='str'):
                if v is None: return 0.0 if t=='num' else ''
                if t == 'num': return float(v)
                if t == 'date': 
                    if isinstance(v, str): return v
                    return v.strftime('%d/%m/%Y')
                if t == 'datetime': return v.strftime('%d/%m/%Y %H:%M')
                return str(v).strip()

            # 2. Busca Notas (tb_airAWBnota) 
            # Colunas usadas estritamente do CSV: nota, serie, valor, filialctc, tipo
            notas_db = session.query(AwbNota).filter(AwbNota.codawb == awb.codawb).all()
            lista_notas = []
            for n in notas_db:
                lista_notas.append({
                    'nota': fmt(n.nota),
                    'serie': fmt(n.serie),
                    'tipo': fmt(n.tipo), # Usado no lugar de espécie na lista de notas
                    'filial': n.filialctc,
                    'valor': fmt(n.valor, 'num'),
                    # Campos vazios pois não existem na tb_airAWBnota
                    'chave': '', 
                    'data': '',
                    'peso': 0,
                    'volumes': 0,
                    'especie': fmt(n.tipo) 
                })

            # 3. Busca Histórico (TB_AWB_STATUS)
            status_db = session.query(AwbStatus)\
                .filter(AwbStatus.CODAWB == awb.awb)\
                .order_by(desc(AwbStatus.DATAHORA_STATUS)).all()
                
            lista_status = []
            for s in status_db:
                lista_status.append({
                    'status': fmt(s.STATUS_AWB),
                    'data': fmt(s.DATAHORA_STATUS, 'datetime'),
                    'local': fmt(s.LOCAL_STATUS),
                    'voo': fmt(s.VOO),
                    'usuario': fmt(s.Usuario),
                    'volumes': fmt(s.VOLUMES, 'num')
                })

            # 4. Monta Objeto Completo
            return {
                "codawb": awb.codawb,
                "awb": awb.awb,
                "dig": awb.dig,
                "cia": f"{fmt(awb.nomecia)} ({fmt(awb.cia)})",
                "emissao": {
                    "data": fmt(awb.data, 'date'),
                    "hora": fmt(awb.hora),
                    "filial": fmt(awb.filial),
                    "tipo": fmt(awb.Tipo_Servico)
                },
                "origem": f"{fmt(awb.siglaorigem)} - {fmt(awb.aeroportoorigem)}",
                "destino": f"{fmt(awb.siglades)} - {fmt(awb.aeroportodestino)}",
                "lugar_entrega": fmt(awb.lugar),
                
                # Contatos usando TEL/FAX (Email não existe no CSV)
                "remetente": {
                    "nome": fmt(awb.nomeexp), "cnpj": fmt(awb.cnpjexp), "ie": fmt(awb.inscrestexp),
                    "endereco": f"{fmt(awb.endexp)}, {fmt(awb.bairroexp)}",
                    "local": f"{fmt(awb.cidadexp)} / {fmt(awb.ufexp)} - {fmt(awb.cepexp)}",
                    "contato": f"Tel: {fmt(awb.telexp)} | Fax: {fmt(awb.faxexp)}"
                },
                "destinatario": {
                    "nome": fmt(awb.nomedes), "cnpj": fmt(awb.cnpjdes), "ie": fmt(awb.inscrestdes),
                    "endereco": f"{fmt(awb.enddes)}, {fmt(awb.bairrodes)}",
                    "local": f"{fmt(awb.cidadedes)} / {fmt(awb.ufdes)} - {fmt(awb.cepdes)}",
                    "contato": f"Tel: {fmt(awb.teldes)} | Fax: {fmt(awb.faxdes)}"
                },
                
                "carga": {
                    "especie": fmt(awb.especie),
                    "volumes": fmt(awb.volumes, 'num'),
                    "peso_real": fmt(awb.pesoreal, 'num'),
                    "peso_cubado": fmt(awb.pesocubado, 'num'),
                    "dimensoes": f"{fmt(awb.comprimento, 'num')} x {fmt(awb.largura, 'num')} x {fmt(awb.altura, 'num')}",
                    "valor": fmt(awb.valmerc, 'num'),
                    "perecivel": fmt(awb.perecivel_duracao)
                },
                "notas": lista_notas,
                "historico": lista_status,
                "entregue": awb.ENTREGUE == 'S',
                "cancelado": awb.cancelado == 'S',
                "motivo_canc": fmt(awb.canc_motivo),
                "integracao": {
                    "nOca": fmt(awb.nOca),
                    "chave_cte": fmt(awb.chCTe_AWB),
                    "dt_importacao": fmt(awb.Data_Importacao, 'datetime')
                }
            }
        except Exception as e:
            print(f"Erro AWB Full: {e}")
            return None
        finally:
            session.close()

    @staticmethod
    def ListarCtcSemAwb(): return []