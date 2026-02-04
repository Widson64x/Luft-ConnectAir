from datetime import datetime, timedelta
from sqlalchemy import func, case, and_, or_, Date, cast, desc, text # Adicionado text
from sqlalchemy.orm import sessionmaker

# --- LOG SERVICE ---
from Services.LogService import LogService

# --- MODELS SQL SERVER (LEGADO) ---
from Models.SQL_SERVER.Awb import Awb, AwbStatus, AwbNota
from Models.SQL_SERVER.Ctc import CtcEsp
from Models.SQL_SERVER.Cadastros import CompanhiaAerea
from Conexoes import ObterEngineSqlServer

# --- MODELS POSTGRES (NOVO - MALHA) ---
from Models.SQL_SERVER.MalhaAerea import VooMalha, RemessaMalha
from Models.SQL_SERVER.Aeroporto import Aeroporto
from Conexoes import ObterSessaoSqlServer

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
            LogService.Debug("AcompanhamentoService", "Iniciando cálculo do resumo do painel (KPIs).")
            Hoje = datetime.now().date()
            TotalHoje = session.query(func.count(Awb.codawb)).filter(cast(Awb.data, Date) == Hoje).scalar()
            
            resumo = { "EmTransito": TotalHoje or 0, "Pendentes": 0, "EntreguesHoje": 0 }
            LogService.Debug("AcompanhamentoService", f"Resumo calculado: {resumo}")
            return resumo
        except Exception as e: 
            LogService.Error("AcompanhamentoService", "Erro ao buscar resumo do painel.", e)
            return { "EmTransito": 0, "Pendentes": 0, "EntreguesHoje": 0 }
        finally: session.close()

    # --- LISTAGEM PRINCIPAL (TABELA) ---
    @staticmethod
    def ListarAwbs(filtros=None):
        LogService.Info("AcompanhamentoService", f"Iniciando listagem de AWBs. Filtros: {filtros}")
        session = AcompanhamentoService._ObterSessaoSql()
        try:
            # Inicia a query base unindo com a tabela de Cia Aérea para pegar o nome fantasia
            query = session.query(Awb, CompanhiaAerea.fantasia)\
                .outerjoin(CompanhiaAerea, Awb.cia.collate('DATABASE_DEFAULT') == CompanhiaAerea.codcia.collate('DATABASE_DEFAULT'))

            # --- APLICAÇÃO DOS FILTROS ---
            if filtros:
                # 1. Filtro por Número da AWB (Prioridade Alta)
                if filtros.get('NumeroAwb'):
                    query = query.filter(Awb.awb.like(f"%{filtros['NumeroAwb']}%"))
                
                # 2. NOVO FILTRO: Filial CTC / Documento Vinculado
                elif filtros.get('FilialCtc'):
                    valor_busca = filtros['FilialCtc'].strip()
                    query = query.join(AwbNota, Awb.codawb == AwbNota.codawb)\
                        .filter(
                            or_(
                                AwbNota.filialctc.like(f"%{valor_busca}%"),
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
                    
                    query = query.filter(cast(Awb.data, Date) >= DataInicio, cast(Awb.data, Date) <= DataFim)

            # Executa a query limitando a 300 resultados para performance
            resultados_awb = query.order_by(Awb.data.desc()).limit(300).all()
            
            # --- OTIMIZAÇÃO: BUSCA DE STATUS EM LOTE ---
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
                    dicionario_status[st.CODAWB] = {
                        'Status': st.STATUS_AWB, 
                        'Data': st.DATAHORA_STATUS, 
                        'Voo': st.VOO, 
                        'DataInsert': st.DATA_INSERT
                    }

            # --- MONTAGEM DA LISTA FINAL ---
            lista_final = []
            for awb_obj, cia_nome in resultados_awb:
                d_st = dicionario_status.get(awb_obj.awb, {
                    'Status': 'AGUARDANDO', 
                    'Data': None, 
                    'Voo': '', 
                    'DataInsert': None
                })
                
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
                    "DataInsert": d_st['DataInsert'].strftime('%d/%m/%Y %H:%M') if d_st['DataInsert'] else '',
                    "Voo": d_st['Voo'] or '',
                    "RotaMap": {
                        "Origem": [geo_o.Latitude, geo_o.Longitude] if geo_o and geo_o.Latitude else None,
                        "Destino": [geo_d.Latitude, geo_d.Longitude] if geo_d and geo_d.Latitude else None
                    }
                })
            
            LogService.Info("AcompanhamentoService", f"Listagem concluída. {len(lista_final)} registros retornados.")
            return lista_final

        except Exception as e:
            LogService.Error("AcompanhamentoService", "Erro crítico ao listar AWBs.", e)
            return []
        finally:
            session.close()

    # --- HELPER: LIMPEZA DE NÚMERO DE VOO ---
    @staticmethod
    def _LimparNumeroVoo(numero_voo):
        if not numero_voo: return ""
        base = numero_voo.split('/')[0].upper().strip()
        prefixos = ['G3', 'JJ', 'LA', 'AD', 'TP', 'QR', 'H2', 'CM', 'AC', 'AF', 'UX']
        for p in prefixos:
            base = base.replace(p, '')
        return "".join(filter(str.isdigit, base))

    # --- HISTÓRICO PARA O MAPA/TIMELINE (REFATORADO COM RAW SQL) ---
    @staticmethod
    def ObterHistoricoAwb(numero_awb):
        LogService.Info("AcompanhamentoService", f"Buscando histórico para AWB: {numero_awb} via SQL Otimizado")
        session = AcompanhamentoService._ObterSessaoSql()
        try:
            # 1. Recupera AWB Mestre para saber Origem/Destino previstos (usado para rota pendente)
            awb_master = session.query(Awb).filter(Awb.awb == numero_awb).first()
            destino_final_esperado = awb_master.siglades if awb_master else None
            origem_inicial = awb_master.siglaorigem if awb_master else None

            # 2. Query SQL Otimizada fornecida (elimina duplicatas e traz malha SQL Server)
            sql_query = text("""
                WITH xVOO (Cia, Voo, Orig, Dest) AS (
                    SELECT 
                        CiaAerea,
                        CASE 
                            WHEN ciaaerea = 'LATAM' THEN LEFT(numerovoo, 2) + RIGHT(numerovoo, 4) 
                            ELSE numerovoo 
                        END AS Voo, 
                        aeroportoorigem, 
                        aeroportodestino 
                    FROM intec..Tb_VooMalha
                    GROUP BY ciaaerea, numerovoo, aeroportoorigem, aeroportodestino
                )
                SELECT  
                    CONVERT(VARCHAR, MAX(s.DATAHORA_STATUS), 103) AS Data,
                    CONVERT(VARCHAR, MAX(s.DATAHORA_STATUS), 108) AS Hora,
                    s.STATUS_AWB AS Status,
                    s.VOO AS Voo,
                    xVOO.Orig AS Origem,
                    xVOO.Dest AS Destino,
                    xVOO.Cia AS Companhia,
                    MAX(s.Usuario) as Usuario
                FROM
                    intec.dbo.TB_AWB_STATUS s
                LEFT JOIN xVOO ON s.VOO = xVOO.voo
                WHERE
                    s.CODAWB = :cod_awb
                GROUP BY
                    s.STATUS_AWB,
                    s.VOO,
                    xVOO.Orig,
                    xVOO.Dest,
                    xVOO.Cia
                ORDER BY
                    MAX(s.DATAHORA_STATUS) ASC;
            """)

            resultado_sql = session.execute(sql_query, {'cod_awb': numero_awb}).fetchall()

            dados_retorno = []
            trajeto_consolidado = []
            
            # Variável para rastrear o local atual baseado no último status válido
            ultimo_local_mapa = None 
            
            for row in resultado_sql:
                # row keys: Data, Hora, Status, Voo, Origem, Destino, Companhia, Usuario
                
                detalhes_voo = None
                
                # Se a query trouxe Origem e Destino do Voo, montamos o objeto de detalhes
                # e adicionamos ao trajeto consolidado para desenhar no mapa.
                if row.Origem and row.Destino:
                    
                    # Precisamos das coordenadas (Lat/Lon) para o mapa, buscamos no Service de Aeroportos
                    go = AeroportoService.BuscarPorSigla(row.Origem)
                    gd = AeroportoService.BuscarPorSigla(row.Destino)
                    
                    if go and gd:
                        detalhes_voo = {
                            "Voo": row.Voo, 
                            "VooNumerico": AcompanhamentoService._LimparNumeroVoo(row.Voo),
                            "Origem": row.Origem, 
                            "Destino": row.Destino,
                            "CoordOrigem": [go.Latitude, go.Longitude], 
                            "CoordDestino": [gd.Latitude, gd.Longitude],
                            "HorarioPartida": '--:--', # SQL agrupado não traz horário exato do voo, apenas status
                            "HorarioChegada": '--:--'
                        }
                        
                        # Adiciona ao trajeto se for um segmento novo
                        if not trajeto_consolidado or \
                           (trajeto_consolidado[-1]['VooNumerico'] != detalhes_voo['VooNumerico'] or \
                            trajeto_consolidado[-1]['Origem'] != detalhes_voo['Origem']):
                            trajeto_consolidado.append(detalhes_voo)
                            
                        # Atualiza local atual para o destino deste voo
                        ultimo_local_mapa = row.Destino
                    else:
                        # Se tem voo mas não achou coordenada, assume Origem do voo como local atual
                        ultimo_local_mapa = row.Origem

                # Monta item do histórico visual
                item = {
                    "Status": row.Status, 
                    "Data": f"{row.Data} {row.Hora}",
                    "Local": row.Origem if row.Origem else '-', # Mostra Origem do voo como local se disponível
                    "Usuario": row.Usuario or '-', 
                    "Voo": row.Voo or '-', 
                    "DetalhesVoo": detalhes_voo
                }
                dados_retorno.append(item)

            # --- CÁLCULO DE ROTA PENDENTE (Tracejado no Mapa) ---
            rota_pendente = None
            
            # Se não determinou local pelos voos, tenta pegar do primeiro status ou origem inicial
            if not ultimo_local_mapa and origem_inicial:
                ultimo_local_mapa = origem_inicial

            # Se temos onde estamos e para onde devemos ir, e eles são diferentes
            if ultimo_local_mapa and destino_final_esperado and ultimo_local_mapa != destino_final_esperado:
                geo_atual = AeroportoService.BuscarPorSigla(ultimo_local_mapa)
                geo_final = AeroportoService.BuscarPorSigla(destino_final_esperado)
                
                if geo_atual and geo_final:
                    rota_pendente = {
                        "Origem": ultimo_local_mapa,
                        "Destino": destino_final_esperado,
                        "CoordOrigem": [geo_atual.Latitude, geo_atual.Longitude],
                        "CoordDestino": [geo_final.Latitude, geo_final.Longitude]
                    }

            # Inverte para mostrar o mais recente primeiro na lista (timeline)
            # Mas mantemos ordem cronológica para montar o mapa
            return { 
                "Historico": dados_retorno[::-1], 
                "TrajetoCompleto": trajeto_consolidado,
                "RotaPendente": rota_pendente 
            }

        except Exception as e: 
            LogService.Error("AcompanhamentoService", f"Erro ao montar histórico da AWB {numero_awb}", e)
            return { "Historico": [], "TrajetoCompleto": [], "RotaPendente": None }
        finally: session.close()

    # --- MODAL VOO (MALHA PREVISTA) ---
    @staticmethod
    def BuscarDetalhesVooModal(numero_voo, data_ref_str):
        session_pg = ObterSessaoSqlServer()
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

            if not voo: 
                LogService.Debug("AcompanhamentoService", f"Voo {numero_voo} não encontrado na malha para a data {data_ref_str}")
                return None

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
            LogService.Error("AcompanhamentoService", f"Erro ao buscar detalhes do voo modal {numero_voo}", e)
            return None
        finally: session_pg.close()

    @staticmethod
    def BuscarDetalhesAwbCompleto(cod_awb_req):
        LogService.Info("AcompanhamentoService", f"Buscando detalhes completos (Modal) da AWB ID: {cod_awb_req}")
        session = AcompanhamentoService._ObterSessaoSql()
        try:
            # 1. Busca Tabela Base (tb_airAWB) pelo codawb
            awb = session.query(Awb).filter(Awb.codawb == cod_awb_req).first()
            if not awb: 
                LogService.Warning("AcompanhamentoService", f"AWB ID {cod_awb_req} não encontrada.")
                return None
            
            def fmt(v, t='str'):
                if v is None: return 0.0 if t=='num' else ''
                if t == 'num': return float(v)
                if t == 'date': 
                    if isinstance(v, str): return v
                    return v.strftime('%d/%m/%Y')
                if t == 'datetime': return v.strftime('%d/%m/%Y %H:%M')
                return str(v).strip()

            # 2. Busca Notas (tb_airAWBnota) 
            notas_db = session.query(AwbNota).filter(AwbNota.codawb == awb.codawb).all()
            lista_notas = []
            for n in notas_db:
                lista_notas.append({
                    'nota': fmt(n.nota),
                    'serie': fmt(n.serie),
                    'tipo': fmt(n.tipo), 
                    'filial': n.filialctc,
                    'valor': fmt(n.valor, 'num'),
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
            LogService.Error("AcompanhamentoService", "Erro ao buscar detalhes completos da AWB.", e)
            return None
        finally:
            session.close()

    @staticmethod
    def ListarCtcSemAwb(): return []