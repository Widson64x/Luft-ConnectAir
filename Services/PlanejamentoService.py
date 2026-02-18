from datetime import datetime, date, time, timedelta
from decimal import Decimal
from sqlalchemy import desc, func, text
from Conexoes import ObterSessaoSqlServer, ObterSessaoSqlServer
from Models.SQL_SERVER.Ctc import CtcEsp, CtcEspCpl
from Models.SQL_SERVER.Planejamento import PlanejamentoCabecalho, PlanejamentoItem, PlanejamentoTrecho
from Models.SQL_SERVER.TabelaFrete import TabelaFrete, RemessaFrete
from Models.SQL_SERVER.Aeroporto import Aeroporto, RemessaAeroportos
from Models.SQL_SERVER.Cidade import Cidade, RemessaCidade
from Models.SQL_SERVER.MalhaAerea import VooMalha , RemessaMalha
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
            ,c.peso as PesoFisico
            ,c.pesotax as PesoTaxado
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
            
            -- LÓGICA DE MODAL E OCORRÊNCIA TM
            AND (
                -- CASO 1: É AÉREO NATIVO E NÃO TEM TM
                (c.modal LIKE 'AEREO%' AND NOT EXISTS (
                    SELECT 1 FROM intec.dbo.tb_ocorr cr (nolock) 
                    WHERE cr.cod_ocorr = 'TM' AND cr.filialctc = c.filialctc
                ))
                OR
                -- CASO 2: NÃO É AÉREO MAS TEM TM
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
            
            
            #print(f"Cabeçalho Row: {row} | Chave: {chave} | Info Cache: {info}")  # Log de debug para verificar a chave e o cache
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
                'peso_fisico': to_float(row.PesoFisico), # Novo campo para display
                'peso_taxado': to_float(row.PesoTaxado), # Campo MESTRE para cálculo
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
            
            # --- ALTERAÇÃO AQUI: Pegando a data de ontem ---
            Hoje = date.today() #- timedelta(days=1)
            
            # Filtro Específico
            # Alterado de >= para = para pegar apenas o dia de ontem
            FiltroSQL = """
                AND c.motivodoc IN ('REE', 'ENT', 'NOR') 
                AND c.data = :data_alvo
            """
            
            Query = text(PlanejamentoService._QueryBase + FiltroSQL + " ORDER BY c.data DESC, c.hora DESC")
            Rows = Sessao.execute(Query, {'data_alvo': Hoje}).fetchall()
            
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
                
                'peso_fisico': float(CtcEncontrado.peso or 0),
                'peso_taxado': float(CtcEncontrado.pesotax or 0), # Prioridade Aérea
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
        Busca CTCs do mesmo dia/rota/tipo.
        CORREÇÃO: Agora retorna 'origem_uf' e 'destino_uf' para evitar erro no salvamento.
        """
        Sessao = ObterSessaoSqlServer()
        try:
            LogService.Debug("PlanejamentoService", f"Busca consolidação (Inc. TM). Rota: {cidade_origem} -> {cidade_destino}")

            if isinstance(data_base, datetime): data_base = data_base.date()
            Inicio = datetime.combine(data_base, time.min)
            Fim = datetime.combine(data_base, time.max)
            
            cidade_origem = str(cidade_origem).strip().upper()
            uf_origem = str(uf_origem).strip().upper()
            cidade_destino = str(cidade_destino).strip().upper()
            uf_destino = str(uf_destino).strip().upper()

            # Subquery TM
            subquery_tm = text("SELECT 1 FROM intec.dbo.tb_ocorr O (NOLOCK) WHERE O.filialctc = C.filialctc AND O.cod_ocorr = 'TM'")

            Query = Sessao.query(CtcEsp, CtcEspCpl).outerjoin(
                CtcEspCpl, CtcEsp.filialctc == CtcEspCpl.filialctc
            ).filter(
                CtcEsp.data >= Inicio, CtcEsp.data <= Fim,
                CtcEsp.tipodoc != 'COB',
                func.upper(func.trim(CtcEsp.cidade_orig)) == cidade_origem,
                func.upper(func.trim(CtcEsp.uf_orig)) == uf_origem,
                func.upper(func.trim(CtcEsp.cidade_dest)) == cidade_destino,
                func.upper(func.trim(CtcEsp.uf_dest)) == uf_destino
            )
            
            # Filtros de Modal/TM
            Query = Query.filter(
                (CtcEsp.modal.like('AEREO%')) | (text("EXISTS (SELECT 1 FROM intec.dbo.tb_ocorr O WHERE O.filialctc = tb_ctc_esp.filialctc AND O.cod_ocorr = 'TM')"))
            )
            
            if tipo_carga: Query = Query.filter(CtcEspCpl.TipoCarga == str(tipo_carga).strip())
            if filial_excluir and ctc_excluir: Query = Query.filter(~((CtcEsp.filial == str(filial_excluir).strip()) & (CtcEsp.filialctc == str(ctc_excluir).strip())))
            
            Resultados = Query.order_by(desc(CtcEsp.data), desc(CtcEsp.hora)).all()
            
            ListaConsolidados = []
            for c, cpl in Resultados:
                tipo_candidato = cpl.TipoCarga if cpl else "N/A"
                def to_float(val): return float(val) if val else 0.0
                def to_int(val): return int(val) if val else 0
                def to_str(val): return str(val).strip() if val else ''
                
                str_hora = "00:00"
                if c.hora:
                    h_raw = str(c.hora).strip().replace(':', '').zfill(4)
                    if len(h_raw) >= 4: str_hora = f"{h_raw[:2]}:{h_raw[2:]}"

                ListaConsolidados.append({
                    'filial': to_str(c.filial),
                    'ctc': to_str(c.filialctc),
                    'serie': to_str(c.seriectc),
                    'volumes': to_int(c.volumes),
                    'peso_fisico': to_float(c.peso),
                    'peso_taxado': to_float(c.pesotax),
                    'val_mercadoria': to_float(c.valmerc),
                    'remetente': to_str(c.remet_nome),
                    'destinatario': to_str(c.dest_nome),
                    'data_emissao': c.data,
                    'hora_emissao': str_hora,
                    
                    # --- CORREÇÃO AQUI: Incluindo as UFs ---
                    'origem_cidade': to_str(c.cidade_orig),
                    'origem_uf': to_str(c.uf_orig),
                    'destino_cidade': to_str(c.cidade_dest),
                    'destino_uf': to_str(c.uf_dest),
                    
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
        Gera o Lote Virtual.
        CORREÇÃO: Propaga Cidades, UFs, Data e Hora para os itens da lista 'lista_docs'.
        """
        try:
            if not lista_candidatos:
                ctc_principal['is_consolidado'] = False
                ctc_principal['lista_docs'] = [ctc_principal.copy()] 
                ctc_principal['qtd_docs'] = 1
                return ctc_principal

            unificado = ctc_principal.copy()
            
            # 1. Garante que o item PRINCIPAL tenha os dados de Data/Hora e Local na lista
            docs = [{
                'filial': ctc_principal['filial'],
                'serie': ctc_principal['serie'],
                'ctc': ctc_principal['ctc'],
                'volumes': int(ctc_principal['volumes']),
                'peso_fisico': float(ctc_principal['peso_fisico']),
                'peso_taxado': float(ctc_principal['peso_taxado']),
                'valor': float(ctc_principal['valor']),
                'remetente': ctc_principal['remetente'],
                'destinatario': ctc_principal['destinatario'],
                'tipo_carga': ctc_principal['tipo_carga'],
                
                # Dados de Data e Hora (Originais do Principal)
                'data_emissao_real': ctc_principal.get('data_emissao_real'),
                'hora_formatada': ctc_principal.get('hora_formatada'),
                
                # Dados de Local
                'origem_cidade': ctc_principal.get('origem_cidade'),
                'origem_uf': ctc_principal.get('origem_uf'),
                'destino_cidade': ctc_principal.get('destino_cidade'),
                'destino_uf': ctc_principal.get('destino_uf')
            }]
            
            total_volumes = docs[0]['volumes']
            total_peso_fisico = docs[0]['peso_fisico']
            total_peso_taxado = docs[0]['peso_taxado']
            total_valor = docs[0]['valor']

            for c in lista_candidatos:
                c_doc = {
                    'filial': c['filial'],
                    'serie': c['serie'],
                    'ctc': c['ctc'],
                    'volumes': int(c['volumes']),
                    'peso_fisico': float(c['peso_fisico']),
                    'peso_taxado': float(c['peso_taxado']),
                    'valor': float(c['val_mercadoria']),
                    'remetente': c['remetente'],
                    'destinatario': c['destinatario'],
                    'tipo_carga': c['tipo_carga'],

                    # Dados de Data e Hora (Vindos da busca de consolidados)
                    'data_emissao': c.get('data_emissao'),
                    'hora_emissao': c.get('hora_emissao'),
                    
                    # Propagando Local para os filhos
                    'origem_cidade': c.get('origem_cidade'),
                    'origem_uf': c.get('origem_uf'),
                    'destino_cidade': c.get('destino_cidade'),
                    'destino_uf': c.get('destino_uf')
                }
                docs.append(c_doc)
                total_volumes += c_doc['volumes']
                total_peso_fisico += c_doc['peso_fisico']
                total_peso_taxado += c_doc['peso_taxado']
                total_valor += c_doc['valor']

            unificado['volumes'] = total_volumes
            unificado['peso_fisico'] = total_peso_fisico
            unificado['peso_taxado'] = total_peso_taxado 
            unificado['valor'] = total_valor
            
            unificado['is_consolidado'] = True
            unificado['lista_docs'] = docs
            unificado['qtd_docs'] = len(docs)
            unificado['resumo_consol'] = f"Lote com {len(docs)} CTCs"

            return unificado
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro em UnificarConsolidacao", e)
            return ctc_principal
    
    @staticmethod
    def RegistrarPlanejamento(dados_ctc_principal, lista_consolidados=None, usuario="Sistema", status_inicial='Em Planejamento', 
                              aero_origem=None, aero_destino=None, lista_trechos=None):
        SessaoPG = ObterSessaoSqlServer()
        if not SessaoPG: 
            LogService.Error("PlanejamentoService", "Falha de conexão com Postgres ao tentar RegistrarPlanejamento.")
            return None

        try:
            LogService.Info("PlanejamentoService", f"Iniciando Gravação de Planejamento. Usuário: {usuario}")

            # --- HELPER FUNCTIONS (Lookup) ---
            def buscar_id_cidade(nome, uf):
                if not nome: return None
                nome_busca = str(nome).strip()
                uf_busca = str(uf).strip()
                if '-' in nome_busca:
                    partes = nome_busca.rsplit('-', 1)
                    if len(partes) == 2 and len(partes[1].strip()) == 2:
                        nome_busca = partes[0].strip()
                        uf_busca = partes[1].strip()
                if not uf_busca: return None
                try:
                    res = SessaoPG.query(Cidade.Id).join(RemessaCidade, Cidade.IdRemessa == RemessaCidade.Id).filter(
                        RemessaCidade.Ativo == True,
                        func.upper(Cidade.Uf) == uf_busca.upper(),
                        func.upper(Cidade.NomeCidade).collate('SQL_Latin1_General_CP1_CI_AI').like(f"%{nome_busca.upper()}%")
                    ).first()
                    return res.Id if res else None
                except: return None

            def buscar_id_aeroporto(iata):
                if not iata: return None
                try:
                    res = SessaoPG.query(Aeroporto.Id).join(RemessaAeroportos, Aeroporto.IdRemessa == RemessaAeroportos.Id).filter(
                        RemessaAeroportos.Ativo == True,
                        Aeroporto.CodigoIata == str(iata).upper().strip()
                    ).first()
                    return res.Id if res else None
                except: return None

            def buscar_id_voo(cia, numero, data_partida, origem):
                if not cia or not numero or not data_partida: return None
                try:
                    dt = data_partida.date() if isinstance(data_partida, datetime) else data_partida
                    res = SessaoPG.query(VooMalha.Id).join(RemessaMalha, VooMalha.IdRemessa == RemessaMalha.Id).filter(
                        RemessaMalha.Ativo == True,
                        VooMalha.CiaAerea == str(cia).strip(),
                        VooMalha.NumeroVoo == str(numero).strip(),
                        VooMalha.DataPartida == dt,
                        VooMalha.AeroportoOrigem == str(origem).strip()
                    ).first()
                    return res.Id if res else None
                except: return None

            def buscar_frete_info(origem, destino, cia):
                if not origem or not destino or not cia: return (None, None)
                try:
                    res = SessaoPG.query(TabelaFrete).join(RemessaFrete, TabelaFrete.IdRemessa == RemessaFrete.Id).filter(
                        RemessaFrete.Ativo == True,
                        TabelaFrete.Origem == str(origem).upper().strip(),
                        TabelaFrete.Destino == str(destino).upper().strip(),
                        TabelaFrete.CiaAerea == str(cia).strip()
                    ).first()
                    return (res.Id, res.Servico) if res else (None, None)
                except: return (None, None)

            def parse_dt(dt_str):
                if not dt_str: return None
                try: return datetime.fromisoformat(str(dt_str).replace('Z', ''))
                except: return None
            # --- FIM HELPERS ---

            # 1. VALIDAÇÃO CABEÇALHO
            id_aero_orig_cab = buscar_id_aeroporto(aero_origem)
            id_aero_dest_cab = buscar_id_aeroporto(aero_destino)

            if not id_aero_orig_cab: raise Exception(f"Aeroporto de Origem '{aero_origem}' inválido ou inativo.")
            if not id_aero_dest_cab: raise Exception(f"Aeroporto de Destino '{aero_destino}' inválido ou inativo.")

            # Verifica ou Cria Cabeçalho
            item_existente = SessaoPG.query(PlanejamentoItem).join(PlanejamentoCabecalho).filter(
                PlanejamentoItem.Filial == str(dados_ctc_principal['filial']),
                PlanejamentoItem.Serie == str(dados_ctc_principal['serie']),
                PlanejamentoItem.Ctc == str(dados_ctc_principal['ctc']),
                PlanejamentoCabecalho.Status == status_inicial
            ).first()

            Cabecalho = None
            if item_existente:
                Cabecalho = item_existente.Cabecalho
                Cabecalho.AeroportoOrigem = aero_origem
                Cabecalho.IdAeroportoOrigem = id_aero_orig_cab
                Cabecalho.AeroportoDestino = aero_destino
                Cabecalho.IdAeroportoDestino = id_aero_dest_cab
                
                # Atualiza totais (Soma)
                def get_val(key): return float(dados_ctc_principal.get(key, 0) or 0)
                Cabecalho.TotalVolumes = int(get_val('volumes'))
                Cabecalho.TotalPeso = get_val('peso_taxado') 
                Cabecalho.TotalValor = get_val('valor')

                SessaoPG.query(PlanejamentoTrecho).filter(PlanejamentoTrecho.IdPlanejamento == Cabecalho.IdPlanejamento).delete()
                SessaoPG.query(PlanejamentoItem).filter(PlanejamentoItem.IdPlanejamento == Cabecalho.IdPlanejamento).delete()
            else:
                def get_val(key): return float(dados_ctc_principal.get(key, 0) or 0)
                Cabecalho = PlanejamentoCabecalho(
                    UsuarioCriacao=str(usuario),
                    Status=status_inicial,
                    AeroportoOrigem=aero_origem,
                    AeroportoDestino=aero_destino,
                    IdAeroportoOrigem=id_aero_orig_cab,
                    IdAeroportoDestino=id_aero_dest_cab,
                    TotalVolumes=int(get_val('volumes')),
                    TotalPeso=get_val('peso_taxado'), 
                    TotalValor=get_val('valor')       
                )
                SessaoPG.add(Cabecalho)
                SessaoPG.flush()

            # --- PREPARAÇÃO DA LISTA DE DOCUMENTOS ---
            todos_docs = []
            if dados_ctc_principal.get('lista_docs'):
                todos_docs = dados_ctc_principal['lista_docs']
                eh_consolidado = dados_ctc_principal.get('is_consolidado', False)
                for idx, doc in enumerate(todos_docs):
                    doc['IndConsolidado'] = eh_consolidado if idx == 0 else False
            else:
                dados_ctc_principal['IndConsolidado'] = False
                todos_docs.append(dados_ctc_principal)

            # Salva os Itens (Cada CTC com sua Data/Hora/Peso Individuais)
            for doc in todos_docs:
                cidade_orig = str(doc.get('origem_cidade', ''))
                uf_orig = str(doc.get('origem_uf') or doc.get('uf_orig', ''))
                cidade_dest = str(doc.get('destino_cidade', ''))
                uf_dest = str(doc.get('destino_uf') or doc.get('uf_dest', ''))
                
                # --- AQUI: Extraindo Data/Hora de CADA doc individualmente ---
                data_doc = doc.get('data_emissao_real') 
                if not data_doc: 
                    data_doc = doc.get('data_emissao')

                hora_doc = doc.get('hora_formatada')
                if not hora_doc:
                    hora_doc = doc.get('hora_emissao')
                # -------------------------------------------------------------

                id_cid_orig = buscar_id_cidade(cidade_orig, uf_orig)
                id_cid_dest = buscar_id_cidade(cidade_dest, uf_dest)

                if not id_cid_orig: raise Exception(f"Cidade Origem '{cidade_orig}-{uf_orig}' não encontrada/inativa para CTC {doc.get('ctc')}")
                if not id_cid_dest: raise Exception(f"Cidade Destino '{cidade_dest}-{uf_dest}' não encontrada/inativa para CTC {doc.get('ctc')}")

                SessaoPG.add(PlanejamentoItem(
                    IdPlanejamento=Cabecalho.IdPlanejamento,
                    Filial=str(doc['filial']),
                    Serie=str(doc['serie']),
                    Ctc=str(doc['ctc']),
                    DataEmissao=data_doc,   # Data específica deste CTC
                    Hora=str(hora_doc),     # Hora específica deste CTC
                    Remetente=str(doc.get('remetente',''))[:100],
                    Destinatario=str(doc.get('destinatario',''))[:100],
                    OrigemCidade=cidade_orig[:50],
                    DestinoCidade=cidade_dest[:50],
                    IdCidadeOrigem=id_cid_orig,
                    IdCidadeDestino=id_cid_dest,
                    Volumes=int(doc.get('volumes', 0)),
                    PesoTaxado=float(doc.get('peso_taxado', 0) or doc.get('peso', 0)), 
                    ValMercadoria=float(doc.get('valor', 0) or doc.get('val_mercadoria', 0)),
                    IndConsolidado=doc.get('IndConsolidado', False)
                ))

            # 2. GRAVA OS TRECHOS
            if lista_trechos and len(lista_trechos) > 0:
                for idx, trecho in enumerate(lista_trechos):
                    
                    origem_iata = trecho.get('origem', {}).get('iata') if isinstance(trecho.get('origem'), dict) else trecho.get('origem')
                    destino_iata = trecho.get('destino', {}).get('iata') if isinstance(trecho.get('destino'), dict) else trecho.get('destino')
                    cia = trecho.get('cia')
                    dt_partida = parse_dt(trecho.get('partida_iso'))
                    dt_chegada = parse_dt(trecho.get('chegada_iso'))

                    id_aero_orig = buscar_id_aeroporto(origem_iata)
                    id_aero_dest = buscar_id_aeroporto(destino_iata)
                    id_voo = buscar_id_voo(cia, trecho.get('voo'), dt_partida, origem_iata)
                    id_frete, tipo_servico_frete = buscar_frete_info(origem_iata, destino_iata, cia)

                    if not id_aero_orig: raise Exception(f"Trecho {idx+1}: Aeroporto Origem '{origem_iata}' inválido.")
                    if not id_aero_dest: raise Exception(f"Trecho {idx+1}: Aeroporto Destino '{destino_iata}' inválido.")
                    if not id_voo: raise Exception(f"Trecho {idx+1}: Voo {cia} {trecho.get('voo')} não encontrado na malha ativa.")
                    if not id_frete: raise Exception(f"Trecho {idx+1}: Tabela de Frete não encontrada para {cia} ({origem_iata}->{destino_iata}).")

                    tipo_servico = trecho.get('tipo_servico', tipo_servico_frete)
                    horario_corte = None
                    if trecho.get('horario_corte'):
                        try: horario_corte = datetime.strptime(trecho.get('horario_corte'), '%H:%M').time()
                        except: pass
                    data_corte = parse_dt(trecho.get('data_corte'))

                    NovoTrecho = PlanejamentoTrecho(
                        IdPlanejamento=Cabecalho.IdPlanejamento,
                        Ordem=idx + 1,
                        CiaAerea=cia,
                        NumeroVoo=trecho.get('voo'),
                        AeroportoOrigem=origem_iata,
                        AeroportoDestino=destino_iata,
                        IdAeroportoOrigem=id_aero_orig,
                        IdAeroportoDestino=id_aero_dest,
                        IdVoo=id_voo,
                        IdFrete=id_frete,
                        TipoServico=tipo_servico,
                        HorarioCorte=horario_corte,
                        DataCorte=data_corte,
                        DataPartida=dt_partida,
                        DataChegada=dt_chegada
                    )
                    SessaoPG.add(NovoTrecho)

            SessaoPG.commit()
            LogService.Info("PlanejamentoService", f"Planejamento gravado com sucesso! ID: {Cabecalho.IdPlanejamento}")
            return Cabecalho.IdPlanejamento

        except Exception as e:
            SessaoPG.rollback()
            LogService.Error("PlanejamentoService", f"Erro crítico (Validação/Gravação): {str(e)}", e)
            raise e 
        finally:
            SessaoPG.close()
            
    @staticmethod
    def ObterPlanejamentoPorCtc(filial, serie, ctc):
        SessaoPG = ObterSessaoSqlServer()
        try:
            # 1. Busca o Item para achar o ID do Cabeçalho
            Item = SessaoPG.query(PlanejamentoItem).join(PlanejamentoCabecalho).filter(
                PlanejamentoItem.Filial == str(filial),
                PlanejamentoItem.Serie == str(serie),
                PlanejamentoItem.Ctc == str(ctc),
                PlanejamentoCabecalho.Status != 'Cancelado'
            ).first()

            if not Item:
                return None

            Cabecalho = Item.Cabecalho
            PesoTotal = float(Cabecalho.TotalPeso or 0) # Peso usado no cálculo original

            # 2. Busca os Trechos ordenados E o valor da tarifa associada
            # JOIN com TabelaFrete para recuperar o valor unitário
            TrechosDB = SessaoPG.query(
                PlanejamentoTrecho, 
                TabelaFrete.Tarifa,
                TabelaFrete.Servico
            ).outerjoin(
                TabelaFrete, PlanejamentoTrecho.IdFrete == TabelaFrete.Id
            ).filter(
                PlanejamentoTrecho.IdPlanejamento == Cabecalho.IdPlanejamento
            ).order_by(PlanejamentoTrecho.Ordem).all()

            RotaFormatada = []
            CustoTotalCalculado = 0.0
            
            # Variáveis para cálculo de tempo
            PrimeiraPartida = None
            UltimaChegada = None

            for row in TrechosDB:
                t = row[0] # Objeto PlanejamentoTrecho
                val_tarifa = float(row[1] or 0) # Coluna Tarifa da TabelaFrete
                nm_servico = str(row[2] or 'STD') # Coluna Servico

                # Formata Horários
                partida_str = t.DataPartida.strftime('%H:%M') if t.DataPartida else "--:--"
                chegada_str = t.DataChegada.strftime('%H:%M') if t.DataChegada else "--:--"
                data_str = t.DataPartida.strftime('%d/%m/%Y') if t.DataPartida else ""
                
                # Controle de Tempo Total
                DtPartida = datetime.combine(t.DataPartida, t.DataPartida.time()) if isinstance(t.DataPartida, datetime) else t.DataPartida
                DtChegada = datetime.combine(t.DataChegada, t.DataChegada.time()) if isinstance(t.DataChegada, datetime) else t.DataChegada
                
                if PrimeiraPartida is None: PrimeiraPartida = DtPartida
                UltimaChegada = DtChegada

                # Recalcula Custo do Trecho (Visualização)
                custo_trecho = val_tarifa * PesoTotal
                CustoTotalCalculado += custo_trecho

                RotaFormatada.append({
                    'cia': t.CiaAerea,
                    'voo': t.NumeroVoo,
                    'data': data_str,
                    'horario_saida': partida_str,
                    'horario_chegada': chegada_str,
                    'origem': {'iata': t.AeroportoOrigem, 'lat': 0, 'lon': 0}, 
                    'destino': {'iata': t.AeroportoDestino, 'lat': 0, 'lon': 0},
                    'base_calculo': {
                        'servico': nm_servico,
                        'tarifa': val_tarifa,
                        'peso_usado': PesoTotal,
                        'custo_trecho': custo_trecho,
                        'custo_trecho_fmt': f"R$ {custo_trecho:,.2f}",
                    }
                })
            
            # 3. Calcula Duração Total
            DuracaoMinutos = 0
            DuracaoFmt = "--:--"
            if PrimeiraPartida and UltimaChegada:
                # Ajuste de dia se virou a noite (se necessário, mas o banco já deve ter a data correta)
                diff = UltimaChegada - PrimeiraPartida
                DuracaoMinutos = diff.total_seconds() / 60
                
                # Formata DDd HH:MM
                seg = int(diff.total_seconds())
                dias, resto = divmod(seg, 86400)
                horas, mins = divmod(resto, 3600); mins //= 60
                DuracaoFmt = f"{dias}d {horas:02}:{mins:02}" if dias > 0 else f"{horas:02}:{mins:02}"

            return {
                'id_planejamento': Cabecalho.IdPlanejamento,
                'status': Cabecalho.Status,
                'rota': RotaFormatada,
                'criado_por': Cabecalho.UsuarioCriacao,
                'data_criacao': Cabecalho.DataCriacao.strftime('%d/%m/%Y %H:%M') if Cabecalho.DataCriacao else "",
                
                # Métricas Totais para o Header do Editor
                'metricas': {
                    'custo': CustoTotalCalculado,
                    'duracao': DuracaoMinutos,
                    'duracao_fmt': DuracaoFmt,
                    'escalas': len(RotaFormatada) - 1 if RotaFormatada else 0
                }
            }

        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro ao obter planejamento existente", e)
            return None
        finally:
            SessaoPG.close()

    # --- NOVO MÉTODO: CANCELAR ---
    @staticmethod
    def CancelarPlanejamento(id_planejamento, usuario):
        SessaoPG = ObterSessaoSqlServer()
        try:
            Cabecalho = SessaoPG.query(PlanejamentoCabecalho).get(id_planejamento)
            if not Cabecalho: return False, "Planejamento não encontrado."

            Cabecalho.Status = 'Cancelado'
            # Poderia salvar log de quem cancelou se tiver campo na tabela ou log separado
            
            SessaoPG.commit()
            return True, "Cancelado com sucesso."
        except Exception as e:
            SessaoPG.rollback()
            LogService.Error("PlanejamentoService", "Erro ao cancelar", e)
            return False, str(e)
        finally:
            SessaoPG.close()