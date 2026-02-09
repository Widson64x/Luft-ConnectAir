from datetime import datetime, date, time, timedelta
from decimal import Decimal
from sqlalchemy import desc, func, text
from Conexoes import ObterSessaoSqlServer, ObterSessaoSqlServer
from Models.SQL_SERVER.Ctc import CtcEsp, CtcEspCpl
from Models.SQL_SERVER.Planejamento import PlanejamentoCabecalho, PlanejamentoItem, PlanejamentoTrecho
from Services.LogService import LogService 

class PlanejamentoService:
    """
    Service Layer Refatorada: Separação em Blocos (Diário, Reversa, Backlog).
    """

    # --- SQL BASE (Compartilhado entre os métodos para evitar repetição) ---
# --- SQL BASE ATUALIZADO (Correção da lógica TM) ---
    _QueryBase = """
        SELECT 
             c.filial as Filial
            ,c.filialctc as CTC
            ,c.seriectc as Serie
            ,C.MODAL as Modal
            ,c.motivodoc as MotivoCTC
            ,c.data as DataEmissao
            ,c.hora as HoraEmissao
            ,c.volumes as Volumes
            ,c.pesotax as Peso
            ,c.valmerc as Valor
            ,c.fretetotalbruto as FreteTotal
            ,upper(c.remet_nome) as Remetente
            ,upper(c.dest_nome) as Destinatario
            ,c.cidade_orig as CidadeOrigem
            ,c.uf_orig as UFOrigem
            ,c.cidade_dest as CidadeDestino
            ,c.uf_dest as UFDestino
            ,c.rotafilialdest as UnidadeDestino
            ,c.prioridade as Prioridade
            ,cl.StatusCTC as StatusCTC
            ,ISNULL(cl.TipoCarga, '') AS Tipo_carga
            ,c.nfs as Notas
        FROM intec.dbo.tb_ctc_esp c (nolock) 
        INNER JOIN intec.dbo.tb_ctc_esp_cpl cl (nolock) on cl.filialctc = c.filialctc
        INNER JOIN intec.dbo.tb_nf_esp n (nolock) on n.filialctc = c.filialctc
        
        -- Join AWB
        LEFT JOIN intec.dbo.tb_airAWBnota B (NOLOCK) ON c.filialctc = b.filialctc AND n.numnf = b.nota collate database_default
        LEFT JOIN intec.dbo.tb_airawb A (NOLOCK) ON A.codawb = B.codawb 
        
        -- Join Manifesto
        LEFT JOIN intec.dbo.tb_manifesto m (nolock) on m.filialctc = c.filialctc
        
        -- Join Reversa
        LEFT JOIN intec.dbo.Tb_PLN_ControleReversa rev (nolock) ON 
            rev.Filial COLLATE DATABASE_DEFAULT = c.filial COLLATE DATABASE_DEFAULT AND 
            rev.Serie COLLATE DATABASE_DEFAULT = c.seriectc COLLATE DATABASE_DEFAULT AND 
            rev.Ctc COLLATE DATABASE_DEFAULT = c.filialctc COLLATE DATABASE_DEFAULT

        WHERE 
            n.filialctc = c.filialctc
            and a.codawb is null
            and c.tipodoc <> 'COB'
            and c.tem_ocorr not in ('C','0','1')
            and left(c.respons_cgc,8) <> '02426290'
            and (a.cancelado is null or a.cancelado = '') 
            and (m.cancelado is null OR m.cancelado = 'S')
            and (m.motivo NOT in ('TRA','RED') OR m.motivo IS NULL)
            
            -- LÓGICA DE MODAL E OCORRÊNCIA TM (ATUALIZADO)
            AND (
                -- CASO 1: É AÉREO NATIVO E NÃO TEM TM (Continua Aéreo)
                (c.modal LIKE 'AEREO%' AND NOT EXISTS (
                    SELECT 1 FROM intec.dbo.tb_ocorr cr (nolock) 
                    WHERE cr.cod_ocorr = 'TM' AND cr.filialctc = c.filialctc
                ))
                OR
                -- CASO 2: NÃO É AÉREO (Ex: RODO) MAS TEM TM (Virou Aéreo)
                (c.modal NOT LIKE 'AEREO%' AND EXISTS (
                    SELECT 1 FROM intec.dbo.tb_ocorr cr (nolock) 
                    WHERE cr.cod_ocorr = 'TM' AND cr.filialctc = c.filialctc
                ))
            )
    """

    @staticmethod
    def _ObterMapaCache():
        """Helper para buscar o cache de planejamentos existentes."""
        SessaoPln = ObterSessaoSqlServer()
        mapa = {}
        if SessaoPln:
            try:
                rows = SessaoPln.query(
                    PlanejamentoItem.Filial, PlanejamentoItem.Serie, PlanejamentoItem.Ctc,
                    PlanejamentoCabecalho.Status, PlanejamentoCabecalho.IdPlanejamento
                ).join(PlanejamentoCabecalho, PlanejamentoItem.IdPlanejamento == PlanejamentoCabecalho.IdPlanejamento).all()
                
                for r in rows:
                    k = f"{str(r.Filial).strip()}-{str(r.Serie).strip()}-{str(r.Ctc).strip()}"
                    mapa[k] = {'status': r.Status, 'id_plan': r.IdPlanejamento}
            except: pass
            finally: SessaoPln.close()
        return mapa

    @staticmethod
    def _SerializarResultados(ResultadoSQL, NomeBloco, MapaCache):
        """Transforma o RowProxy do SQLAlchemy em Dicionário JSON padronizado."""
        Lista = []
        def to_float(val): return float(val) if val else 0.0
        def to_int(val): return int(val) if val else 0
        def to_str(val): return str(val).strip() if val else ''
        def fmt_moeda(val): return f"{to_float(val):,.2f}"

        for row in ResultadoSQL:
            data_emissao = row.DataEmissao.strftime('%d/%m/%Y') if row.DataEmissao else ''
            
            # Formatação Hora
            hora_fmt = '--:--'
            if row.HoraEmissao:
                h = str(row.HoraEmissao).strip()
                if ':' not in h:
                    if len(h) == 4: h = f"{h[:2]}:{h[2:]}"
                    elif len(h) <= 2: h = f"{h.zfill(2)}:00"
                hora_fmt = h

            # Qtd Notas
            qtd_notas = 0
            if row.Notas:
                s = str(row.Notas).replace('/', ',').replace(';', ',').replace('-', ',')
                qtd_notas = len([n for n in s.split(',') if n.strip()])
            if qtd_notas == 0 and to_int(row.Volumes) > 0: qtd_notas = 1

            # Cache Planejamento
            chave = f"{to_str(row.Filial)}-{to_str(row.Serie)}-{to_str(row.CTC)}"
            info = MapaCache.get(chave)
            
            
            print(f"Cabeçalho Row: {row} | Chave: {chave} | Info Cache: {info}")  # Log de debug para verificar a chave e o cache
            Lista.append({
                'id_unico': f"{to_str(row.Filial)}-{to_str(row.CTC)}",
                'origem_dados': NomeBloco,  # <--- IMPORTANTE: DIARIO, REVERSA ou BACKLOG
                'filial': to_str(row.Filial),
                'ctc': to_str(row.CTC),
                'serie': to_str(row.Serie),
                'data_emissao': data_emissao,
                'hora_emissao': hora_fmt,
                'prioridade': to_str(row.Prioridade),
                'motivodoc': to_str(row.MotivoCTC),
                'status_ctc': to_str(row.StatusCTC),
                'origem': f"{to_str(row.CidadeOrigem)}/{to_str(row.UFOrigem)}",
                'destino': f"{to_str(row.CidadeDestino)}/{to_str(row.UFDestino)}",
                'unid_lastmile': to_str(row.UnidadeDestino),
                'remetente': to_str(row.Remetente),
                'destinatario': to_str(row.Destinatario),
                'volumes': to_int(row.Volumes),
                'peso_taxado': to_float(row.Peso),
                'val_mercadoria': fmt_moeda(row.Valor),
                'raw_val_mercadoria': to_float(row.Valor),
                'raw_frete_total': to_float(row.FreteTotal),
                'qtd_notas': qtd_notas,
                'tipo_carga': to_str(row.Tipo_carga),
                'tem_planejamento': bool(info),
                'status_planejamento': info['status'] if info else None,
                'id_planejamento': info['id_plan'] if info else None,
                'full_data': { # Usado para montagem
                     'filial': row.Filial, 'filialctc': row.CTC, 'seriectc': row.Serie,
                     'data': str(row.DataEmissao), 'hora': str(row.HoraEmissao),
                     'origem_cidade': row.CidadeOrigem, 'uf_orig': row.UFOrigem,
                     'destino_cidade': row.CidadeDestino, 'uf_dest': row.UFDestino
                }
            })
        return Lista

    # -------------------------------------------------------------------------
    # BLOCO 1: DIÁRIO
    # -------------------------------------------------------------------------
    @staticmethod
    def BuscarCtcsDiario(mapa_cache=None):
        Sessao = ObterSessaoSqlServer()
        try:
            if not mapa_cache: mapa_cache = PlanejamentoService._ObterMapaCache()
            Hoje = date.today()
            
            # Filtro Específico
            FiltroSQL = """
                AND c.motivodoc IN ('REE', 'ENT', 'NOR') 
                AND c.data >= :data_hoje
            """
            
            Query = text(PlanejamentoService._QueryBase + FiltroSQL + " ORDER BY c.data DESC, c.hora DESC")
            Rows = Sessao.execute(Query, {'data_hoje': Hoje}).fetchall()
            
            return PlanejamentoService._SerializarResultados(Rows, "DIARIO", mapa_cache)
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro Buscar Diario", e)
            return []
        finally: Sessao.close()

    # -------------------------------------------------------------------------
    # BLOCO 2: REVERSA
    # -------------------------------------------------------------------------
    @staticmethod
    def BuscarCtcsReversa(mapa_cache=None):
        Sessao = ObterSessaoSqlServer()
        try:
            if not mapa_cache: mapa_cache = PlanejamentoService._ObterMapaCache()
            
            # Filtro Específico: Motivo DEV + Tabela Reversa Liberada
            FiltroSQL = """
                AND c.motivodoc = 'DEV' 
                AND rev.LiberadoPlanejamento = 1
            """
            
            Query = text(PlanejamentoService._QueryBase + FiltroSQL + " ORDER BY c.data DESC")
            Rows = Sessao.execute(Query).fetchall()
            
            return PlanejamentoService._SerializarResultados(Rows, "REVERSA", mapa_cache)
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro Buscar Reversa", e)
            return []
        finally: Sessao.close()

    # -------------------------------------------------------------------------
    # BLOCO 3: BACKLOG
    # -------------------------------------------------------------------------
    @staticmethod
    def BuscarCtcsBacklog(mapa_cache=None):
        Sessao = ObterSessaoSqlServer()
        try:
            if not mapa_cache: mapa_cache = PlanejamentoService._ObterMapaCache()
            
            Hoje = date.today()
            Corte = Hoje - timedelta(days=120)
            
            # Filtro Específico: Anterior a hoje, maior que corte, REE/ENT
            FiltroSQL = """
                AND c.motivodoc IN ('REE', 'ENT')
                AND c.data < :data_hoje 
                AND c.data >= :data_corte
            """
            
            Query = text(PlanejamentoService._QueryBase + FiltroSQL + " ORDER BY c.data ASC") # Backlog ordena pelos mais velhos
            Rows = Sessao.execute(Query, {'data_hoje': Hoje, 'data_corte': Corte}).fetchall()
            
            return PlanejamentoService._SerializarResultados(Rows, "BACKLOG", mapa_cache)
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro Buscar Backlog", e)
            return []
        finally: Sessao.close()

    # -------------------------------------------------------------------------
    # VISÃO GLOBAL (Chamada pela API Principal)
    # -------------------------------------------------------------------------
    @staticmethod
    def BuscarCtcsPlanejamento():
        """
        Executa as 3 buscas e consolida o resultado.
        """
        LogService.Debug("PlanejamentoService", "Iniciando busca GLOBAL (3 Blocos)...")
        
        # 1. Busca Cache uma única vez
        Cache = PlanejamentoService._ObterMapaCache()
        
        # 2. Busca os Blocos
        ListaDiario = PlanejamentoService.BuscarCtcsDiario(Cache)
        ListaReversa = PlanejamentoService.BuscarCtcsReversa(Cache)
        ListaBacklog = PlanejamentoService.BuscarCtcsBacklog(Cache)
        
        Total = len(ListaDiario) + len(ListaReversa) + len(ListaBacklog)
        LogService.Info("PlanejamentoService", f"Busca Concluída. Total: {Total} (D:{len(ListaDiario)}, R:{len(ListaReversa)}, B:{len(ListaBacklog)})")
        
        # 3. Retorna Unificado
        return ListaDiario + ListaReversa + ListaBacklog

    @staticmethod
    def ObterCtcDetalhado(Filial, Serie, Numero):
        """
        Captura detalhes completos do CTC a partir da Filial, Série e Número.
        AGORA COM JOIN NA TABELA COMPLEMENTAR PARA PEGAR O TIPO DE CARGA.
        """
        Sessao = ObterSessaoSqlServer()
        try:
            f = str(Filial).strip()
            s = str(Serie).strip()
            n = str(Numero).strip()

            # 1. ALTERAÇÃO: Trazemos a tupla (CtcEsp, CtcEspCpl)
            Query = Sessao.query(CtcEsp, CtcEspCpl).outerjoin(
                CtcEspCpl, 
                CtcEsp.filialctc == CtcEspCpl.filialctc
            ).filter(
                CtcEsp.filial == f, CtcEsp.seriectc == s, CtcEsp.filialctc == n
            )

            Resultado = Query.first()
            
            # Tentativas de busca flexível (zeros à esquerda)
            if not Resultado:
                Query = Sessao.query(CtcEsp, CtcEspCpl).outerjoin(CtcEspCpl, CtcEsp.filialctc == CtcEspCpl.filialctc).filter(
                    CtcEsp.filial == f, CtcEsp.seriectc == s, CtcEsp.filialctc == n.lstrip('0')
                )
                Resultado = Query.first()

            if not Resultado:
                 Query = Sessao.query(CtcEsp, CtcEspCpl).outerjoin(CtcEspCpl, CtcEsp.filialctc == CtcEspCpl.filialctc).filter(
                    CtcEsp.filial == f, CtcEsp.seriectc == s, CtcEsp.filialctc == n.zfill(10)
                )
                 Resultado = Query.first()

            if not Resultado: 
                LogService.Warning("PlanejamentoService", f"CTC Detalhado não encontrado: {f}-{s}-{n}")
                return None
            
            # Desempacota os objetos
            CtcEncontrado, CplEncontrado = Resultado

            DataBase = CtcEncontrado.data 
            HoraFinal = time(0, 0)
            str_hora = "00:00"

            if CtcEncontrado.hora:
                try:
                    h_str = str(CtcEncontrado.hora).strip().replace(':', '')
                    h_str = h_str.zfill(4)
                    if len(h_str) >= 4:
                        HoraFinal = datetime.strptime(h_str[:4], '%H%M').time()
                        str_hora = f"{h_str[:2]}:{h_str[2:]}"
                except: pass

            DataEmissaoReal = datetime.combine(DataBase.date(), HoraFinal)
            DataBuscaVoos = DataEmissaoReal + timedelta(hours=10)

            # 2. Captura o Tipo de Carga
            TipoCargaValor = CplEncontrado.TipoCarga if CplEncontrado else None

            return {
                'filial': CtcEncontrado.filial,
                'serie': CtcEncontrado.seriectc,
                'ctc': CtcEncontrado.filialctc,
                'data_emissao_real': DataEmissaoReal,
                'hora_formatada': str_hora,
                'data_busca': DataBuscaVoos,
                'origem_cidade': str(CtcEncontrado.cidade_orig).strip(),
                'origem_uf': str(CtcEncontrado.uf_orig).strip(),
                'destino_cidade': str(CtcEncontrado.cidade_dest).strip(),
                'destino_uf': str(CtcEncontrado.uf_dest).strip(),
                'peso': float(CtcEncontrado.peso or 0),
                'volumes': int(CtcEncontrado.volumes or 0),
                'valor': (CtcEncontrado.valmerc or 0),
                'remetente': str(CtcEncontrado.remet_nome).strip(),
                'destinatario': str(CtcEncontrado.dest_nome).strip(),
                'tipo_carga': TipoCargaValor 
            }
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro em ObterCtcDetalhado", e)
            return None
        finally:
            Sessao.close()

    @staticmethod
    def BuscarCtcsConsolidaveis(cidade_origem, uf_origem, cidade_destino, uf_destino, data_base, filial_excluir=None, ctc_excluir=None, tipo_carga=None):
        """
        Busca todos os CTCs aéreos do mesmo dia, mesma rota e MESMO TIPO DE CARGA.
        """
        Sessao = ObterSessaoSqlServer()
        try:
            # Logs substituindo prints
            LogService.Debug("PlanejamentoService", f"Iniciando busca consolidação. Rota: {cidade_origem}/{uf_origem} -> {cidade_destino}/{uf_destino}, TipoCarga: {tipo_carga}")

            if isinstance(data_base, datetime): data_base = data_base.date()
            Inicio = datetime.combine(data_base, time.min)
            Fim = datetime.combine(data_base, time.max)
            
            cidade_origem = str(cidade_origem).strip().upper()
            uf_origem = str(uf_origem).strip().upper()
            cidade_destino = str(cidade_destino).strip().upper()
            uf_destino = str(uf_destino).strip().upper()
            
            # ALTERADO: Trazemos (CtcEsp, CtcEspCpl) para poder dar print no tipo
            Query = Sessao.query(CtcEsp, CtcEspCpl).outerjoin(
                CtcEspCpl, 
                CtcEsp.filialctc == CtcEspCpl.filialctc
            ).filter(
                CtcEsp.data >= Inicio, CtcEsp.data <= Fim,
                CtcEsp.tipodoc != 'COB', CtcEsp.modal.like('AEREO%'),
                func.upper(func.trim(CtcEsp.cidade_orig)) == cidade_origem,
                func.upper(func.trim(CtcEsp.uf_orig)) == uf_origem,
                func.upper(func.trim(CtcEsp.cidade_dest)) == cidade_destino,
                func.upper(func.trim(CtcEsp.uf_dest)) == uf_destino
            )
            
            # Filtro do Tipo de Carga
            if tipo_carga:
                Query = Query.filter(CtcEspCpl.TipoCarga == str(tipo_carga).strip())
            
            if filial_excluir and ctc_excluir:  
                Query = Query.filter(~((CtcEsp.filial == str(filial_excluir).strip()) & (CtcEsp.filialctc == str(ctc_excluir).strip())))
            
            Resultados = Query.order_by(desc(CtcEsp.data), desc(CtcEsp.hora)).all()
            
            LogService.Info("PlanejamentoService", f"Encontrados {len(Resultados)} candidatos para consolidação na rota {cidade_origem}-{cidade_destino}.")

            ListaConsolidados = []
            
            for c, cpl in Resultados:
                tipo_candidato = cpl.TipoCarga if cpl else "N/A"
                # Log Debug opcional
                # LogService.Debug("PlanejamentoService", f"Candidato: {c.filialctc} | Tipo: {tipo_candidato}")

                def to_float(val): return float(val) if val else 0.0
                def to_int(val): return int(val) if val else 0
                def to_str(val): return str(val).strip() if val else ''
                
                str_hora = "00:00"
                if c.hora:
                    h_raw = str(c.hora).strip().replace(':', '').zfill(4)
                    if len(h_raw) >= 4:
                        str_hora = f"{h_raw[:2]}:{h_raw[2:]}"

                ListaConsolidados.append({
                    'filial': to_str(c.filial),
                    'ctc': to_str(c.filialctc),
                    'serie': to_str(c.seriectc),
                    'volumes': to_int(c.volumes),
                    'peso_taxado': to_float(c.pesotax),
                    'val_mercadoria': to_float(c.valmerc),
                    'remetente': to_str(c.remet_nome),
                    'destinatario': to_str(c.dest_nome),
                    'data_emissao': c.data,
                    'hora_emissao': str_hora,
                    'origem_cidade': to_str(c.cidade_orig),
                    'destino_cidade': to_str(c.cidade_dest),
                    'tipo_carga': tipo_candidato
                })
            
            return ListaConsolidados
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro em BuscarCtcsConsolidaveis", e)
            return []
        finally:
            Sessao.close()

    @staticmethod
    def UnificarConsolidacao(ctc_principal, lista_candidatos):
        """
        Recebe o CTC Principal e a Lista de Candidatos.
        Retorna um objeto 'Virtual' (Lote) somando volumes, pesos e valores.
        """
        try:
            if not lista_candidatos:
                ctc_principal['is_consolidado'] = False
                ctc_principal['lista_docs'] = [ctc_principal.copy()] 
                ctc_principal['qtd_docs'] = 1
                return ctc_principal

            unificado = ctc_principal.copy()
            
            docs = [{
                'filial': ctc_principal['filial'],
                'serie': ctc_principal['serie'],
                'ctc': ctc_principal['ctc'],
                'volumes': int(ctc_principal['volumes']),
                'peso': float(ctc_principal['peso']),
                'valor': float(ctc_principal['valor']),
                'remetente': ctc_principal['remetente'],
                'destinatario': ctc_principal['destinatario'],
                'tipo_carga': ctc_principal['tipo_carga']
            }]
            
            total_volumes = docs[0]['volumes']
            total_peso = docs[0]['peso']
            total_valor = docs[0]['valor']

            for c in lista_candidatos:
                c_doc = {
                    'filial': c['filial'],
                    'serie': c['serie'],
                    'ctc': c['ctc'],
                    'volumes': int(c['volumes']),
                    'peso': float(c['peso_taxado']),
                    'valor': float(c['val_mercadoria']),
                    'remetente': c['remetente'],
                    'destinatario': c['destinatario'],
                    'tipo_carga': c['tipo_carga']
                }
                docs.append(c_doc)
                total_volumes += c_doc['volumes']
                total_peso += c_doc['peso']
                total_valor += c_doc['valor']

            unificado['volumes'] = total_volumes
            unificado['peso'] = total_peso
            unificado['valor'] = total_valor
            
            unificado['is_consolidado'] = True
            unificado['lista_docs'] = docs
            unificado['qtd_docs'] = len(docs)
            unificado['resumo_consol'] = f"Lote com {len(docs)} CTCs"

            LogService.Info("PlanejamentoService", f"Consolidação Unificada: {len(docs)} documentos, Total Peso: {total_peso}")
            return unificado
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro em UnificarConsolidacao", e)
            return ctc_principal # Retorna o original para não quebrar tudo
    
    @staticmethod
    def RegistrarPlanejamento(dados_ctc_principal, lista_consolidados=None, usuario="Sistema", status_inicial='Em Planejamento', 
                              aero_origem=None, aero_destino=None, lista_trechos=None):
        """
        Salva ou atualiza o Planejamento, Itens e TRECHOS DE VOO.
        """
        SessaoPG = ObterSessaoSqlServer()
        if not SessaoPG: 
            LogService.Error("PlanejamentoService", "Falha de conexão com Postgres ao tentar RegistrarPlanejamento.")
            return None

        try:
            LogService.Info("PlanejamentoService", f"Iniciando Gravação de Planejamento. Usuário: {usuario}")

            def parse_dt(dt_str):
                if not dt_str: return None
                try: return datetime.fromisoformat(str(dt_str).replace('Z', ''))
                except: return None

            item_existente = SessaoPG.query(PlanejamentoItem).join(PlanejamentoCabecalho).filter(
                PlanejamentoItem.Filial == str(dados_ctc_principal['filial']),
                PlanejamentoItem.Serie == str(dados_ctc_principal['serie']),
                PlanejamentoItem.Ctc == str(dados_ctc_principal['ctc']),
                PlanejamentoCabecalho.Status == status_inicial
            ).first()

            Cabecalho = None

            if item_existente:
                LogService.Info("PlanejamentoService", f"Atualizando Planejamento Existente ID: {item_existente.Cabecalho.IdPlanejamento}")
                Cabecalho = item_existente.Cabecalho
                if aero_origem: Cabecalho.AeroportoOrigem = aero_origem
                if aero_destino: Cabecalho.AeroportoDestino = aero_destino
                
                # Limpa trechos antigos para regravar
                SessaoPG.query(PlanejamentoTrecho).filter(PlanejamentoTrecho.IdPlanejamento == Cabecalho.IdPlanejamento).delete()
            
            else:
                LogService.Info("PlanejamentoService", "Criando novo registro de Planejamento Cabecalho/Itens.")
                def get_val(key): return float(dados_ctc_principal.get(key, 0) or 0)
                
                Cabecalho = PlanejamentoCabecalho(
                    UsuarioCriacao=str(usuario),
                    Status=status_inicial,
                    AeroportoOrigem=aero_origem,
                    AeroportoDestino=aero_destino,
                    TotalVolumes=int(get_val('volumes')),
                    TotalPeso=get_val('peso'),
                    TotalValor=get_val('valor')
                )
                SessaoPG.add(Cabecalho)
                SessaoPG.flush()

                # Adiciona CTC Principal
                if dados_ctc_principal.get('is_consolidado'): info = dados_ctc_principal['lista_docs'][0]
                else: info = dados_ctc_principal
                
                ItemPrincipal = PlanejamentoItem(
                    IdPlanejamento=Cabecalho.IdPlanejamento,
                    Filial=str(dados_ctc_principal['filial']),
                    Serie=str(dados_ctc_principal['serie']),
                    Ctc=str(dados_ctc_principal['ctc']),
                    DataEmissao=dados_ctc_principal.get('data_emissao_real'),
                    Hora=dados_ctc_principal.get('hora_formatada'), 
                    Remetente=str(dados_ctc_principal.get('remetente',''))[:100],
                    Destinatario=str(dados_ctc_principal.get('destinatario',''))[:100],
                    OrigemCidade=str(dados_ctc_principal.get('origem_cidade',''))[:50],
                    DestinoCidade=str(dados_ctc_principal.get('destino_cidade',''))[:50],
                    Volumes=int(info.get('volumes', 0)),
                    PesoTaxado=float(info.get('peso', 0) or info.get('peso_taxado', 0)),
                    ValMercadoria=float(info.get('valor', 0) or info.get('val_mercadoria', 0)),
                    IndConsolidado=False
                )
                SessaoPG.add(ItemPrincipal)

                # Adiciona Consolidados
                if lista_consolidados:
                    for c in lista_consolidados:
                        SessaoPG.add(PlanejamentoItem(
                            IdPlanejamento=Cabecalho.IdPlanejamento,
                            Filial=str(c['filial']), Serie=str(c['serie']), Ctc=str(c['ctc']),
                            Volumes=int(c.get('volumes',0)), PesoTaxado=float(c.get('peso_taxado',0)),
                            ValMercadoria=float(c.get('val_mercadoria',0)),
                            Remetente=str(c.get('remetente',''))[:100], Destinatario=str(c.get('destinatario',''))[:100],
                            DataEmissao=c.get('data_emissao'),
                            Hora=c.get('hora_emissao'), 
                            OrigemCidade=str(c.get('origem_cidade', ''))[:50],
                            DestinoCidade=str(c.get('destino_cidade', ''))[:50],
                            IndConsolidado=True
                        ))

            # 3. GRAVA OS TRECHOS
            if lista_trechos and len(lista_trechos) > 0:
                LogService.Debug("PlanejamentoService", f"Gravando {len(lista_trechos)} trechos de voo.")
                for idx, trecho in enumerate(lista_trechos):
                    NovoTrecho = PlanejamentoTrecho(
                        IdPlanejamento=Cabecalho.IdPlanejamento,
                        Ordem=idx + 1,
                        CiaAerea=trecho.get('cia'),
                        NumeroVoo=trecho.get('voo'),
                        AeroportoOrigem=trecho.get('origem', {}).get('iata') if isinstance(trecho.get('origem'), dict) else trecho.get('origem'),
                        AeroportoDestino=trecho.get('destino', {}).get('iata') if isinstance(trecho.get('destino'), dict) else trecho.get('destino'),
                        DataPartida=parse_dt(trecho.get('partida_iso')),
                        DataChegada=parse_dt(trecho.get('chegada_iso'))
                    )
                    SessaoPG.add(NovoTrecho)

            SessaoPG.commit()
            LogService.Info("PlanejamentoService", f"Planejamento gravado com sucesso! ID: {Cabecalho.IdPlanejamento}")
            return Cabecalho.IdPlanejamento

        except Exception as e:
            SessaoPG.rollback()
            LogService.Error("PlanejamentoService", "Erro crítico ao gravar planejamento", e)
            return None
        finally:
            SessaoPG.close()