from datetime import datetime, date, time, timedelta
from decimal import Decimal
import random
import unicodedata
import pandas as pd
import io
from sqlalchemy.orm import joinedload
from sqlalchemy import desc, func, text
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Ctc import CtcEsp, CtcEspCpl
from Models.SQL_SERVER.Planejamento import PlanejamentoCabecalho, PlanejamentoItem, PlanejamentoTrecho
from Models.SQL_SERVER.TabelaFrete import TabelaFrete, RemessaFrete
from Models.SQL_SERVER.Aeroporto import Aeroporto, RemessaAeroportos
from Models.SQL_SERVER.Cidade import Cidade, RemessaCidade
from Models.SQL_SERVER.MalhaAerea import VooMalha , RemessaMalha
from Models.SQL_SERVER.Cadastros import Cliente
from Models.SQL_SERVER.ServicoCliente import ServicoCliente
from Models.SQL_SERVER.Filial import Filial
import re
from Services.LogService import LogService 

class PlanejamentoService:
    """
    Service Layer Refatorada: Separação em Blocos (Diário, Reversa, Backlog).
    """

    # --- SQL BASE ATUALIZADO (Correção da lógica TM) ---
    _QueryBase = """
         SELECT DISTINCT
             c.filial as Filial
             ,fil.nomefilial as Filial_Nome
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
             
             -- LÓGICA DE SUBCONTRATAÇÃO FARMA: CAMPOS HOMÔNIMOS DO CTC CORRESPONDENTE
             ,CASE 
                 WHEN ISNULL(cl.ctc_corresp, '') <> '' AND f.remet_nome IS NOT NULL THEN UPPER(f.remet_nome)
                 ELSE UPPER(c.remet_nome)
              END as Remetente
              
             ,CASE 
                 WHEN ISNULL(cl.ctc_corresp, '') <> '' AND f.dest_nome IS NOT NULL THEN UPPER(f.dest_nome)
                 ELSE UPPER(c.dest_nome)
              END as Destinatario
             ,CASE 
                 WHEN ISNULL(cl.ctc_corresp, '') <> '' AND f.respons_nome IS NOT NULL THEN UPPER(f.respons_nome)
                 ELSE UPPER(c.respons_nome)
              END as ClienteNome
             ,CASE 
                 WHEN ISNULL(cl.ctc_corresp, '') <> '' AND f.cidade_orig IS NOT NULL THEN f.cidade_orig
                 ELSE c.cidade_orig
              END as CidadeOrigem
             ,CASE 
                 WHEN ISNULL(cl.ctc_corresp, '') <> '' AND f.uf_orig IS NOT NULL THEN f.uf_orig
                 ELSE c.uf_orig
              END as UFOrigem
             ,CASE 
                 WHEN ISNULL(cl.ctc_corresp, '') <> '' AND f.cidade_dest IS NOT NULL THEN f.cidade_dest
                 ELSE c.cidade_dest
              END as CidadeDestino
             ,CASE 
                 WHEN ISNULL(cl.ctc_corresp, '') <> '' AND f.uf_dest IS NOT NULL THEN f.uf_dest
                 ELSE c.uf_dest
              END as UFDestino
             ,c.rotafilialdest as UnidadeDestino
             ,c.prioridade as Prioridade
             ,cl.StatusCTC as StatusCTC
             ,ISNULL(cl.TipoCarga, '') AS Tipo_carga
             ,c.nfs as Notas
             ,CAST(c.qtdenfs AS INT) as QtdNotas
             
             -- LÓGICA DE SUBCONTRATAÇÃO FARMA: CNPJS
             ,CASE 
                 WHEN ISNULL(cl.ctc_corresp, '') <> '' AND f.remet_cgc IS NOT NULL THEN f.remet_cgc
                 ELSE c.remet_cgc
              END as RemetCGC   
             ,CASE 
                 WHEN ISNULL(cl.ctc_corresp, '') <> '' AND f.dest_cgc IS NOT NULL THEN f.dest_cgc
                 ELSE c.dest_cgc
              END as DestCGC     
             ,CASE 
                 WHEN ISNULL(cl.ctc_corresp, '') <> '' AND f.respons_cgc IS NOT NULL THEN f.respons_cgc
                 ELSE c.respons_cgc
              END as ResponsCGC
              
         FROM intec.dbo.tb_ctc_esp c (nolock)
             INNER JOIN intec.dbo.tb_ctc_esp_cpl cl (nolock) on cl.filialctc = c.filialctc
             
             -- JOIN PARA BUSCAR A SUBCONTRATAÇÃO NA FARMA
             LEFT JOIN farma.dbo.tb_ctc_esp f (nolock) ON f.filialctc = cl.ctc_corresp AND ISNULL(cl.ctc_corresp, '') <> ''
             
             LEFT JOIN intec.dbo.tb_filial fil (nolock) ON fil.filial COLLATE DATABASE_DEFAULT = c.filial COLLATE DATABASE_DEFAULT

             LEFT JOIN intec.dbo.tb_manifesto m (nolock) on m.filialctc = c.filialctc
             LEFT JOIN intec.dbo.Tb_PLN_ControleReversa rev (nolock) ON
             rev.Filial COLLATE DATABASE_DEFAULT = c.filial COLLATE DATABASE_DEFAULT AND
             rev.Serie COLLATE DATABASE_DEFAULT = c.seriectc COLLATE DATABASE_DEFAULT AND
             rev.Ctc COLLATE DATABASE_DEFAULT = c.filialctc COLLATE DATABASE_DEFAULT
         WHERE
             c.tipodoc <> 'COB'
           and c.tem_ocorr not in ('C','0','1')
           and left(c.respons_cgc,8) <> '02426290'
           and (m.cancelado is null OR m.cancelado = 'S')
           and (m.motivo NOT in ('TRA','RED') OR m.motivo IS NULL)
           and cl.StatusCTC NOT IN ('CTC CANCELADO')
           AND NOT EXISTS (
             SELECT 1
             FROM intec.dbo.tb_airAWBnota B (NOLOCK)
                      INNER JOIN intec.dbo.tb_airawb A (NOLOCK) ON A.codawb = B.codawb
             WHERE B.filialctc = c.filialctc
               AND (A.cancelado IS NULL OR A.cancelado = '')
         )
           AND (
             (c.modal LIKE 'AEREO%' AND NOT EXISTS (
                 SELECT 1 FROM intec.dbo.tb_ocorr cr (nolock)
                 WHERE cr.cod_ocorr = 'TM' AND cr.filialctc = c.filialctc
             ))
                 OR
             (c.modal NOT LIKE 'AEREO%' AND EXISTS (
                 SELECT 1 FROM intec.dbo.tb_ocorr cr (nolock)
                 WHERE cr.cod_ocorr = 'TM' AND cr.filialctc = c.filialctc
             ))
             ) 
         """

    # --- NOVO: Mapeamento Rápido de UF para Aeroporto Principal ---
    MAPA_UF_IATA = {
        'SP': 'GRU', 'RJ': 'GIG', 'MG': 'CNF', 'RS': 'POA', 'PR': 'CWB',
        'SC': 'FLN', 'BA': 'SSA', 'PE': 'REC', 'CE': 'FOR', 'AM': 'MAO',
        'PA': 'BEL', 'GO': 'BSB', 'DF': 'BSB', 'MT': 'CGB', 'MS': 'CGR',
        'ES': 'VIX', 'MA': 'SLZ', 'PB': 'JPA', 'RN': 'NAT', 'AL': 'MCZ',
        'SE': 'AJU', 'PI': 'THE', 'RO': 'PVH', 'RR': 'BVB', 'AP': 'MCP',
        'AC': 'RBR', 'TO': 'PMW'
    }

    @staticmethod
    def _RemoverAcentos(texto):
        return ''.join(
            char for char in unicodedata.normalize('NFKD', str(texto or ''))
            if not unicodedata.combining(char)
        )

    @staticmethod
    def _NormalizarServicoContratado(servico):
        valor_original = str(servico or '').strip()
        if not valor_original:
            return 'STANDARD'

        valor = PlanejamentoService._RemoverAcentos(valor_original).upper()
        valor = valor.replace('-', '_').replace(' ', '_')
        valor = re.sub(r'_+', '_', valor).strip('_')

        if 'DEPEND' in valor and 'DESTINO' in valor:
            return 'DEPENDE_DO_DESTINO'
        if 'EXPRESSO' in valor:
            return 'EXPRESSO'
        if 'ECON' in valor:
            return 'ECONÔMICO'
        if valor in {'PADRAO', 'STANDARD'}:
            return 'STANDARD'

        return valor_original.upper()

    @staticmethod
    def _ServicoEhDependenteDestino(servico):
        return PlanejamentoService._NormalizarServicoContratado(servico) == 'DEPENDE_DO_DESTINO'

    @staticmethod
    def _NormalizarChaveCliente(cnpj):
        return re.sub(r'[^0-9]', '', str(cnpj or ''))

    @staticmethod
    def _ObterChaveServicoCliente(doc):
        chave = PlanejamentoService._NormalizarChaveCliente(doc.get('cnpj_cliente'))
        if chave:
            return chave
        return f"{doc.get('filial', '')}-{doc.get('serie', '')}-{doc.get('ctc', '')}"

    @staticmethod
    def _NormalizarMapaServicosEscolhidos(servicos_escolhidos):
        mapa_normalizado = {}
        if not isinstance(servicos_escolhidos, dict):
            return mapa_normalizado

        for chave, servico in servicos_escolhidos.items():
            chave_normalizada = PlanejamentoService._NormalizarChaveCliente(chave) or str(chave or '').strip()
            servico_normalizado = PlanejamentoService._NormalizarServicoContratado(servico)
            if chave_normalizada and servico_normalizado:
                mapa_normalizado[chave_normalizada] = servico_normalizado

        return mapa_normalizado

    @staticmethod
    def _DeterminarServicoRoteamento(lista_docs):
        if not lista_docs:
            return 'STANDARD'

        servicos = [
            PlanejamentoService._NormalizarServicoContratado(doc.get('servico_contratado'))
            for doc in lista_docs
        ]

        if any(PlanejamentoService._ServicoEhDependenteDestino(servico) for servico in servicos):
            return None

        if any(servico == 'EXPRESSO' for servico in servicos):
            return 'EXPRESSO'

        for servico in servicos:
            if servico not in {'', 'STANDARD'}:
                return servico

        return 'STANDARD'

    @staticmethod
    def _MontarPendenciasServico(lista_docs):
        grupos = {}

        for doc in lista_docs:
            if not PlanejamentoService._ServicoEhDependenteDestino(doc.get('servico_contratado')):
                continue

            chave_cliente = doc.get('cliente_key') or PlanejamentoService._ObterChaveServicoCliente(doc)
            grupo = grupos.get(chave_cliente)

            if not grupo:
                grupo = {
                    'cliente_key': chave_cliente,
                    'cliente_cnpj': doc.get('cnpj_cliente', ''),
                    'cliente_nome': doc.get('cliente_nome') or doc.get('remetente') or doc.get('destinatario') or 'Cliente sem identificação',
                    'quantidade_docs': 0,
                    'peso_total': 0.0,
                    'opcoes': ['ECONÔMICO', 'EXPRESSO'],
                    'docs': []
                }
                grupos[chave_cliente] = grupo

            grupo['quantidade_docs'] += 1
            grupo['peso_total'] += float(doc.get('peso_taxado') or 0)
            grupo['docs'].append({
                'filial': doc.get('filial'),
                'serie': doc.get('serie'),
                'ctc': doc.get('ctc'),
                'destinatario': doc.get('destinatario'),
                'peso_taxado': float(doc.get('peso_taxado') or 0),
                'volumes': int(doc.get('volumes') or 0)
            })

        return list(grupos.values())

    @staticmethod
    def MontarDadosPlanejamento(filial, serie, ctc, servicos_escolhidos=None):
        dados_ctc = PlanejamentoService.ObterCtcDetalhado(filial, serie, ctc)
        if not dados_ctc:
            return None, [], None

        ctcs_candidatos = PlanejamentoService.BuscarCtcsConsolidaveis(
            dados_ctc['origem_cidade'], dados_ctc['origem_uf'],
            dados_ctc['destino_cidade'], dados_ctc['destino_uf'],
            dados_ctc['data_emissao_real'], filial, ctc,
            dados_ctc['tipo_carga'],
            servico_alvo=dados_ctc.get('servico_contratado')
        )

        dados_unificados = PlanejamentoService.UnificarConsolidacao(
            dados_ctc,
            ctcs_candidatos,
            servicos_escolhidos=servicos_escolhidos
        )

        return dados_ctc, ctcs_candidatos, dados_unificados

    @staticmethod
    def _CarregarCacheTarifas():
        """Consulta 1 única vez a menor tarifa de cada rota ativa para cálculo virtual rápido"""
        Sessao = ObterSessaoSqlServer()
        cache = {}
        try:
            res = Sessao.query(
                TabelaFrete.Origem, 
                TabelaFrete.Destino, 
                func.min(TabelaFrete.Tarifa).label('menor_tarifa')
            ).join(RemessaFrete, TabelaFrete.IdRemessa == RemessaFrete.Id).filter(
                RemessaFrete.Ativo == True
            ).group_by(TabelaFrete.Origem, TabelaFrete.Destino).all()
            
            for r in res:
                chave = f"{str(r.Origem).strip()}-{str(r.Destino).strip()}"
                cache[chave] = float(r.menor_tarifa or 0)
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro em _CarregarCacheTarifas", e)
        finally:
            Sessao.close()
        return cache

    @staticmethod
    def _ObterMapaCache():
        SessaoPln = ObterSessaoSqlServer()
        mapa = {}
        if SessaoPln:
            try:
                # 1. Buscar a soma das tarifas para cada IdPlanejamento (pois pode ter conexões)
                tarifas_por_plan = {}
                res_tarifas = SessaoPln.query(
                    PlanejamentoTrecho.IdPlanejamento, 
                    func.sum(TabelaFrete.Tarifa).label('tarifa_total')
                ).outerjoin(
                    TabelaFrete, PlanejamentoTrecho.IdFrete == TabelaFrete.Id
                ).group_by(PlanejamentoTrecho.IdPlanejamento).all()
                
                for r in res_tarifas:
                    tarifas_por_plan[r.IdPlanejamento] = float(r.tarifa_total or 0)
                
                # 2. Buscar os itens com o peso_taxado para calcular o custo proporcional
                rows = SessaoPln.query(
                    PlanejamentoItem.Filial, PlanejamentoItem.Serie, PlanejamentoItem.Ctc,
                    PlanejamentoItem.PesoTaxado,
                    PlanejamentoCabecalho.Status, PlanejamentoCabecalho.IdPlanejamento
                ).join(
                    PlanejamentoCabecalho, PlanejamentoItem.IdPlanejamento == PlanejamentoCabecalho.IdPlanejamento
                ).filter(
                    PlanejamentoCabecalho.Status != 'Cancelado'
                ).all()
                
                for r in rows:
                    k = f"{str(r.Filial).strip()}-{str(r.Serie).strip()}-{str(r.Ctc).strip()}"
                    
                    # CÁLCULO REAL: (Soma das tarifas das conexões) * (Peso Taxado)
                    tarifa_t = tarifas_por_plan.get(r.IdPlanejamento, 0.0)
                    peso_item = float(r.PesoTaxado or 0)
                    custo_real_trechos = peso_item * tarifa_t
                    
                    mapa[k] = {
                        'status': r.Status, 
                        'id_plan': r.IdPlanejamento,
                        'custo_planejado': custo_real_trechos,
                        'tarifa_rota': tarifa_t
                    }
            except Exception as e:
                LogService.Error("PlanejamentoService", "Erro em _ObterMapaCache", e)
            finally: 
                SessaoPln.close()
        return mapa

    @staticmethod
    def _SerializarResultados(ResultadoSQL, NomeBloco, MapaCache, CacheTarifas=None):
        if CacheTarifas is None: CacheTarifas = {}
        Lista = []
        def to_float(val): return float(val) if val else 0.0
        def to_int(val): return int(val) if val else 0
        def to_str(val): return str(val).strip() if val else ''
        def fmt_moeda(val): return f"{to_float(val):,.2f}"

        for row in ResultadoSQL:
            data_emissao = row.DataEmissao.strftime('%d/%m/%Y') if row.DataEmissao else ''
            
            hora_fmt = '--:--'
            if row.HoraEmissao:
                h = str(row.HoraEmissao).strip()
                if ':' not in h:
                    if len(h) == 4: h = f"{h[:2]}:{h[2:]}"
                    elif len(h) <= 2: h = f"{h.zfill(2)}:00"
                hora_fmt = h

            qtd_notas = to_int(row.QtdNotas)
            if qtd_notas == 0 and to_int(row.Volumes) > 0:
                qtd_notas = 1

            chave = f"{to_str(row.Filial)}-{to_str(row.Serie)}-{to_str(row.CTC)}"
            info = MapaCache.get(chave)
            
            is_dev = to_str(row.MotivoCTC) == 'DEV'
            remetente_final = to_str(row.Destinatario) if is_dev else to_str(row.Remetente)
            destinatario_final = to_str(row.Remetente) if is_dev else to_str(row.Destinatario)
            cliente_nome = to_str(getattr(row, 'ClienteNome', '')) or remetente_final or destinatario_final
            

            # --- NOVA LÓGICA DE PLANEJAMENTO VIRTUAL RÁPIDO ---
            uf_orig = to_str(row.UFOrigem)
            uf_dest = to_str(row.UFDestino)
            
            # Pega o Aeroporto principal da UF (Se não achar, chuta GRU -> MAO como fallback)
            iata_orig = PlanejamentoService.MAPA_UF_IATA.get(uf_orig, 'GRU')
            iata_dest = PlanejamentoService.MAPA_UF_IATA.get(uf_dest, 'MAO')
            
            chave_tarifa = f"{iata_orig}-{iata_dest}"
            
            # Pega o valor real do banco em memória. Se a rota não existir na tabela, usa R$ 5.50
            tarifa_virtual = CacheTarifas.get(chave_tarifa, 5.50)
            # --------------------------------------------------

            Lista.append({
                'id_unico': f"{to_str(row.Filial)}-{to_str(row.CTC)}",
                'origem_dados': NomeBloco,
                'filial': to_str(row.Filial),
                'nomefilial': to_str(getattr(row, 'Filial_Nome', '')),
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
                'cliente_nome': cliente_nome,
                'remetente': remetente_final,
                'destinatario': destinatario_final,
                'volumes': to_int(row.Volumes),
                'peso_fisico': to_float(row.PesoFisico),
                'peso_taxado': to_float(row.PesoTaxado),
                'val_mercadoria': fmt_moeda(row.Valor),
                'raw_val_mercadoria': to_float(row.Valor),
                'raw_frete_total': to_float(row.FreteTotal),
                'qtd_notas': qtd_notas,
                'tipo_carga': to_str(row.Tipo_carga),
                'tem_planejamento': bool(info),
                'status_planejamento': info['status'] if info else None,
                'id_planejamento': info['id_plan'] if info else None,
                'custo_planejado': info['custo_planejado'] if info else 0.0,
                'tarifa_estimada': info['tarifa_rota'] if info and info.get('tarifa_rota', 0) > 0 else tarifa_virtual,
                'full_data': { 
                     'filial': row.Filial, 'filialctc': row.CTC, 'seriectc': row.Serie,
                     'data': str(row.DataEmissao), 'hora': str(row.HoraEmissao),
                     'origem_cidade': row.CidadeOrigem, 'uf_orig': row.UFOrigem,
                     'destino_cidade': row.CidadeDestino, 'uf_dest': row.UFDestino
                }
            })
        return Lista

    @staticmethod
    def BuscarCtcsDiario(mapa_cache=None, cache_tarifas=None): # ADICIONADO AQUI
        Sessao = ObterSessaoSqlServer()
        try:
            if not mapa_cache: mapa_cache = PlanejamentoService._ObterMapaCache()
            Hoje = date.today() 
            FiltroSQL = """
                AND c.motivodoc IN ('REE', 'ENT', 'NOR') 
                AND c.data = :data_alvo
            """
            Query = text(PlanejamentoService._QueryBase + FiltroSQL + " ORDER BY c.data DESC, c.hora DESC")
            Rows = Sessao.execute(Query, {'data_alvo': Hoje}).fetchall()
            
            # ADICIONADO O cache_tarifas AQUI NO RETORNO:
            return PlanejamentoService._SerializarResultados(Rows, "DIARIO", mapa_cache, cache_tarifas)
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro Buscar Diario", e)
            return []
        finally: Sessao.close()

    @staticmethod
    def BuscarCtcsReversa(mapa_cache=None, cache_tarifas=None): # ADICIONADO AQUI
        Sessao = ObterSessaoSqlServer()
        try:
            if not mapa_cache: mapa_cache = PlanejamentoService._ObterMapaCache()
            FiltroSQL = """
                AND c.motivodoc = 'DEV' 
                AND rev.LiberadoPlanejamento = 1
            """
            Query = text(PlanejamentoService._QueryBase + FiltroSQL + " ORDER BY c.data DESC")
            Rows = Sessao.execute(Query).fetchall()
            
            return PlanejamentoService._SerializarResultados(Rows, "REVERSA", mapa_cache, cache_tarifas)
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro Buscar Reversa", e)
            return []
        finally: Sessao.close()

    @staticmethod
    def BuscarCtcsBacklog(mapa_cache=None, cache_tarifas=None): # ADICIONADO AQUI
        Sessao = ObterSessaoSqlServer()
        try:
            if not mapa_cache: mapa_cache = PlanejamentoService._ObterMapaCache()
            Hoje = date.today()
            Corte = Hoje - timedelta(days=120)
            FiltroSQL = """
                AND c.motivodoc IN ('REE', 'ENT')
                AND c.data < :data_hoje 
                AND c.data >= :data_corte
            """
            Query = text(PlanejamentoService._QueryBase + FiltroSQL + " ORDER BY c.data ASC")
            Rows = Sessao.execute(Query, {'data_hoje': Hoje, 'data_corte': Corte}).fetchall()
            
            # ADICIONADO O cache_tarifas AQUI NO RETORNO:
            return PlanejamentoService._SerializarResultados(Rows, "BACKLOG", mapa_cache, cache_tarifas)
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro Buscar Backlog", e)
            return []
        finally: Sessao.close()

    @staticmethod
    def BuscarCtcsPlanejamento():
        LogService.Debug("PlanejamentoService", "Iniciando busca GLOBAL (3 Blocos)...")
        Cache = PlanejamentoService._ObterMapaCache()
        
        # NOVO: Carrega as tarifas virtuais 1 única vez para toda a tela
        CacheTarifas = PlanejamentoService._CarregarCacheTarifas() 
        
        # Passamos o CacheTarifas para dentro das buscas
        ListaDiario = PlanejamentoService.BuscarCtcsDiario(Cache, CacheTarifas)
        ListaReversa = PlanejamentoService.BuscarCtcsReversa(Cache, CacheTarifas)
        ListaBacklog = PlanejamentoService.BuscarCtcsBacklog(Cache, CacheTarifas)
        
        Total = len(ListaDiario) + len(ListaReversa) + len(ListaBacklog)
        LogService.Info("PlanejamentoService", f"Busca Concluída. Total: {Total} (D:{len(ListaDiario)}, R:{len(ListaReversa)}, B:{len(ListaBacklog)})")
        return ListaDiario + ListaReversa + ListaBacklog

    @staticmethod
    def BuscarServicoContratadoCliente(*cnpjs):
        Sessao = ObterSessaoSqlServer()
        try:
            from sqlalchemy import or_ 
            lista_cnpjs_limpos = []
            for cnpj in cnpjs:
                if cnpj:
                    limpo = re.sub(r'[^0-9]', '', str(cnpj))
                    if len(limpo) >= 8 and limpo[:8] not in lista_cnpjs_limpos:
                        lista_cnpjs_limpos.append(limpo[:8])
            
            if not lista_cnpjs_limpos: return "STANDARD"
            
            filtros = []
            for raiz in lista_cnpjs_limpos:
                filtros.append(Cliente.CNPJ_Cliente.like(f"{raiz[:2]}.{raiz[2:5]}.{raiz[5:8]}%"))
                filtros.append(Cliente.CNPJ_Cliente.like(f"{raiz}%"))
                
            ClientesEncontrados = Sessao.query(Cliente.Codigo_Cliente).filter(or_(*filtros)).all()
            if not ClientesEncontrados: return "STANDARD"
                
            lista_codigos = [cli.Codigo_Cliente for cli in ClientesEncontrados]
            Servico = Sessao.query(ServicoCliente).filter(
                ServicoCliente.CodigoCliente.in_(lista_codigos),
                ServicoCliente.ServicoContratado != 'STANDARD' 
            ).first()
            
            return PlanejamentoService._NormalizarServicoContratado(Servico.ServicoContratado if Servico else "STANDARD")
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro em BuscarServicoContratadoCliente", e)
            return "STANDARD"
        finally:
            Sessao.close()

    @staticmethod
    def ObterCtcDetalhado(Filial, Serie, Numero):
        Sessao = ObterSessaoSqlServer()
        try:
            f = str(Filial).strip()
            s = str(Serie).strip()
            n = str(Numero).strip()

            Query = Sessao.query(CtcEsp, CtcEspCpl).outerjoin(
                CtcEspCpl, CtcEsp.filialctc == CtcEspCpl.filialctc
            ).filter(CtcEsp.filial == f, CtcEsp.seriectc == s, CtcEsp.filialctc == n)

            Resultado = Query.first()
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
            
            CtcEncontrado, CplEncontrado = Resultado
    
            # VERIFICA SUBCONTRATAÇÃO FARMA
            if CplEncontrado and CplEncontrado.ctc_corresp and str(CplEncontrado.ctc_corresp).strip():
                try:
                    ctc_farma = str(CplEncontrado.ctc_corresp).strip()
                    # Busca pontual no banco da Farma
                    query_farma = text("""
                        SELECT TOP 1
                            origem,
                            remet_nome,
                            remet_cgc,
                            remet_end,
                            remet_cidade,
                            remet_uf,
                            remet_cep,
                            remet_ie,
                            respons_nome,
                            respons_cgc,
                            respons_end,
                            respons_cidade,
                            respons_uf,
                            respons_ie,
                            dest_nome,
                            dest_cgc,
                            dest_end,
                            dest_cidade,
                            dest_uf,
                            dest_cep,
                            dest_ie,
                            cidade_orig,
                            uf_orig,
                            cidade_dest,
                            uf_dest
                        FROM farma.dbo.tb_ctc_esp (NOLOCK)
                        WHERE filialctc = :ctc
                    """)
                    farma_data = Sessao.execute(query_farma, {'ctc': ctc_farma}).fetchone()
                    
                    if farma_data:
                        campos_farma = (
                            'origem',
                            'remet_nome',
                            'remet_cgc',
                            'remet_end',
                            'remet_cidade',
                            'remet_uf',
                            'remet_cep',
                            'remet_ie',
                            'respons_nome',
                            'respons_cgc',
                            'respons_end',
                            'respons_cidade',
                            'respons_uf',
                            'respons_ie',
                            'dest_nome',
                            'dest_cgc',
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

                        for campo in campos_farma:
                            valor = getattr(farma_data, campo, None)
                            if valor is not None and str(valor).strip() != '':
                                setattr(CtcEncontrado, campo, valor)
                except Exception as e_farma:
                    LogService.Warning("PlanejamentoService", f"Erro ao buscar subcontratação Farma: {e_farma}")

            DataBase = CtcEncontrado.data 
            HoraFinal = time(0, 0)

            if CtcEncontrado.hora:
                try:
                    h_str = str(CtcEncontrado.hora).strip().replace(':', '')
                    h_str = h_str.zfill(4)
                    if len(h_str) >= 4:
                        HoraFinal = datetime.strptime(h_str[:4], '%H%M').time()
                        str_hora = f"{h_str[:2]}:{h_str[2:]}"
                except: pass

            DataEmissaoReal = datetime.combine(DataBase.date(), HoraFinal)
            
            # SLA DE OPERAÇÃO: Adiciona 12 horas a partir de 'agora' para dar tempo de separar e transportar a carga até o aeroporto.
            DataBuscaVoos = datetime.now() + timedelta(hours=12) 
            
            TipoCarga = CplEncontrado.TipoCarga if CplEncontrado else None

            is_dev = CtcEncontrado.motivodoc == 'DEV'
            if is_dev:
                cnpj_alvo = getattr(CtcEncontrado, 'respons_cgc', None) or getattr(CtcEncontrado, 'dest_cgc', None)
                remetente_nome = str(CtcEncontrado.dest_nome).strip()
                destinatario_nome = str(CtcEncontrado.remet_nome).strip()
            else:
                cnpj_alvo = getattr(CtcEncontrado, 'respons_cgc', None) or getattr(CtcEncontrado, 'remet_cgc', None)
                remetente_nome = str(CtcEncontrado.remet_nome).strip()
                destinatario_nome = str(CtcEncontrado.dest_nome).strip()

            cliente_nome = str(getattr(CtcEncontrado, 'respons_nome', '') or '').strip() or remetente_nome or destinatario_nome

            servico_contratado = PlanejamentoService.BuscarServicoContratadoCliente(cnpj_alvo)

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
                'peso_taxado': float(CtcEncontrado.pesotax or 0),
                'volumes': int(CtcEncontrado.volumes or 0),
                'valor': (CtcEncontrado.valmerc or 0),
                'cliente_nome': cliente_nome,
                'remetente': remetente_nome,
                'destinatario': destinatario_nome,
                'tipo_carga': TipoCarga,
                'motivodoc': CtcEncontrado.motivodoc, # Adicionado
                'cnpj_cliente': cnpj_alvo,
                'servico_contratado': servico_contratado
            }
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro em ObterCtcDetalhado", e)
            return None
        finally:
            Sessao.close()

    @staticmethod
    def BuscarCtcsConsolidaveis(cidade_origem, uf_origem, cidade_destino, uf_destino, data_base, filial_excluir=None, ctc_excluir=None, tipo_carga=None, servico_alvo=None):
        Sessao = ObterSessaoSqlServer()
        try:
            mapa_cache = PlanejamentoService._ObterMapaCache()

            cidade_origem = str(cidade_origem).strip().upper()
            uf_origem = str(uf_origem).strip().upper()
            cidade_destino = str(cidade_destino).strip().upper()
            uf_destino = str(uf_destino).strip().upper()

            FiltroSQL = f"""
                AND UPPER(LTRIM(RTRIM(c.cidade_orig))) = '{cidade_origem}'
                AND UPPER(LTRIM(RTRIM(c.uf_orig))) = '{uf_origem}'
                AND UPPER(LTRIM(RTRIM(c.cidade_dest))) = '{cidade_destino}'
                AND UPPER(LTRIM(RTRIM(c.uf_dest))) = '{uf_destino}'
            """
            
            if tipo_carga: FiltroSQL += f" AND cl.TipoCarga = '{str(tipo_carga).strip()}'"
            if filial_excluir and ctc_excluir: FiltroSQL += f" AND NOT (c.filial = '{str(filial_excluir).strip()}' AND c.filialctc = '{str(ctc_excluir).strip()}')"
            
            Query = text(PlanejamentoService._QueryBase + FiltroSQL + " ORDER BY c.data DESC, c.hora DESC")
            Resultados = Sessao.execute(Query).fetchall()
            
            ListaConsolidados = []
            for row in Resultados:
                def to_float(val): return float(val) if val else 0.0
                def to_int(val): return int(val) if val else 0
                def to_str(val): return str(val).strip() if val else ''

                chave = f"{to_str(row.Filial)}-{to_str(row.Serie)}-{to_str(row.CTC)}"
                info_plan = mapa_cache.get(chave)
                if info_plan and str(info_plan.get('status', '')).upper() != 'CANCELADO':
                    continue 

                str_hora = "00:00"
                if row.HoraEmissao:
                    h_raw = str(row.HoraEmissao).strip().replace(':', '').zfill(4)
                    if len(h_raw) >= 4: str_hora = f"{h_raw[:2]}:{h_raw[2:]}"

                is_dev = to_str(row.MotivoCTC) == 'DEV'
                if is_dev:
                    cnpj_alvo = getattr(row, 'ResponsCGC', None) or getattr(row, 'DestCGC', None)
                    remetente_nome = to_str(row.Destinatario)
                    destinatario_nome = to_str(row.Remetente)
                else:
                    cnpj_alvo = getattr(row, 'ResponsCGC', None) or getattr(row, 'RemetCGC', None)
                    remetente_nome = to_str(row.Remetente)
                    destinatario_nome = to_str(row.Destinatario)

                cliente_nome = to_str(getattr(row, 'ClienteNome', '')) or remetente_nome or destinatario_nome

                servico_cand = PlanejamentoService.BuscarServicoContratadoCliente(
                    getattr(row, 'ResponsCGC', None), 
                    getattr(row, 'RemetCGC', None), 
                    getattr(row, 'DestCGC', None)
                )
                if servico_alvo:
                    servico_alvo_norm = PlanejamentoService._NormalizarServicoContratado(servico_alvo)
                    servico_cand_norm = PlanejamentoService._NormalizarServicoContratado(servico_cand)
                    if not (
                        PlanejamentoService._ServicoEhDependenteDestino(servico_alvo_norm) or
                        PlanejamentoService._ServicoEhDependenteDestino(servico_cand_norm)
                    ) and servico_cand_norm != servico_alvo_norm:
                        continue 

                ListaConsolidados.append({
                    'filial': to_str(row.Filial),
                    'ctc': to_str(row.CTC),
                    'serie': to_str(row.Serie),
                    'volumes': to_int(row.Volumes),
                    'peso_fisico': to_float(row.PesoFisico),
                    'peso_taxado': to_float(row.PesoTaxado),
                    'val_mercadoria': to_float(row.Valor),
                    'cliente_nome': cliente_nome,
                    'remetente': remetente_nome,
                    'destinatario': destinatario_nome,
                    'data_emissao': row.DataEmissao,
                    'hora_emissao': str_hora,
                    'origem_cidade': to_str(row.CidadeOrigem),
                    'origem_uf': to_str(row.UFOrigem),
                    'destino_cidade': to_str(row.CidadeDestino),
                    'destino_uf': to_str(row.UFDestino),
                    'tipo_carga': to_str(row.Tipo_carga),
                    'motivodoc': to_str(row.MotivoCTC), # Adicionado
                    'cnpj_cliente': to_str(cnpj_alvo),
                    'servico_contratado': servico_cand 
                })

            return ListaConsolidados
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro em BuscarCtcsConsolidaveis", e)
            return []
        finally:
            Sessao.close()

    @staticmethod
    def UnificarConsolidacao(ctc_principal, lista_candidatos, servicos_escolhidos=None):
        try:
            overrides = PlanejamentoService._NormalizarMapaServicosEscolhidos(servicos_escolhidos)
            unificado = ctc_principal.copy()
            unificado['cnpj_cliente'] = ctc_principal.get('cnpj_cliente', '')
            unificado['cliente_nome'] = ctc_principal.get('cliente_nome', '')
            docs = []

            def montar_doc(origem_doc, principal=False):
                servico_base = PlanejamentoService._NormalizarServicoContratado(origem_doc.get('servico_contratado', 'STANDARD'))
                cliente_key = PlanejamentoService._NormalizarChaveCliente(origem_doc.get('cnpj_cliente'))
                if not cliente_key:
                    cliente_key = f"{origem_doc.get('filial', '')}-{origem_doc.get('serie', '')}-{origem_doc.get('ctc', '')}"

                servico_final = overrides.get(cliente_key, servico_base)
                if PlanejamentoService._ServicoEhDependenteDestino(servico_base) and cliente_key not in overrides:
                    servico_final = 'DEPENDE_DO_DESTINO'

                return {
                    'filial': origem_doc.get('filial'),
                    'serie': origem_doc.get('serie'),
                    'ctc': origem_doc.get('ctc'),
                    'volumes': int(origem_doc.get('volumes') or 0),
                    'peso_fisico': float(origem_doc.get('peso_fisico') or 0),
                    'peso_taxado': float(origem_doc.get('peso_taxado') or 0),
                    'valor': float(origem_doc.get('valor', origem_doc.get('val_mercadoria', 0)) or 0),
                    'remetente': origem_doc.get('remetente', ''),
                    'destinatario': origem_doc.get('destinatario', ''),
                    'tipo_carga': origem_doc.get('tipo_carga'),
                    'motivodoc': origem_doc.get('motivodoc'),
                    'cnpj_cliente': origem_doc.get('cnpj_cliente', ''),
                    'cliente_key': cliente_key,
                    'cliente_nome': origem_doc.get('cliente_nome') or origem_doc.get('remetente') or origem_doc.get('destinatario') or 'Cliente sem identificação',
                    'servico_contratado_original': servico_base,
                    'servico_contratado': servico_final,
                    'data_emissao_real': origem_doc.get('data_emissao_real') or origem_doc.get('data_emissao'),
                    'hora_formatada': origem_doc.get('hora_formatada') or origem_doc.get('hora_emissao'),
                    'origem_cidade': origem_doc.get('origem_cidade'),
                    'origem_uf': origem_doc.get('origem_uf'),
                    'destino_cidade': origem_doc.get('destino_cidade'),
                    'destino_uf': origem_doc.get('destino_uf'),
                    'principal': principal
                }

            docs.append(montar_doc(ctc_principal, principal=True))
            for c in (lista_candidatos or []):
                docs.append(montar_doc(c))

            total_volumes = sum(doc['volumes'] for doc in docs)
            total_peso_fisico = sum(doc['peso_fisico'] for doc in docs)
            total_peso_taxado = sum(doc['peso_taxado'] for doc in docs)
            total_valor = sum(doc['valor'] for doc in docs)

            unificado['volumes'] = total_volumes
            unificado['peso_fisico'] = total_peso_fisico
            unificado['peso_taxado'] = total_peso_taxado 
            unificado['valor'] = total_valor

            unificado['is_consolidado'] = len(docs) > 1
            unificado['lista_docs'] = docs
            unificado['qtd_docs'] = len(docs)
            unificado['resumo_consol'] = f"Lote com {len(docs)} CTCs"

            pendencias = PlanejamentoService._MontarPendenciasServico(docs)
            servico_roteamento = PlanejamentoService._DeterminarServicoRoteamento(docs)

            unificado['servicos_pendentes'] = pendencias
            unificado['servico_pendente'] = len(pendencias) > 0
            unificado['servico_roteamento'] = servico_roteamento
            unificado['servico_contratado'] = servico_roteamento or 'DEFINIR NO PLANEJAMENTO'

            return unificado
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro em UnificarConsolidacao", e)
            return ctc_principal
    
    @staticmethod
    def RegistrarPlanejamento(dados_ctc_principal, lista_consolidados=None, usuario="Sistema", status_inicial='Em Planejamento', 
                              aero_origem=None, aero_destino=None, lista_trechos=None, motor_escolha='GRAFO'):
        SessaoPG = ObterSessaoSqlServer()
        if not SessaoPG: 
            LogService.Error("PlanejamentoService", "Falha de conexão com banco ao tentar RegistrarPlanejamento.")
            return None

        try:
            LogService.Info("PlanejamentoService", f"Iniciando Gravação de Planejamento. Usuário: {usuario}")

            from Models.SQL_SERVER.NfEsp import NfEsp
            from Models.SQL_SERVER.Cortes import CortePlanejamento
            from datetime import datetime, time

            # --- HELPER FUNCTIONS ---
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

            def buscar_info_corte(filial):
                if not filial: return None, None, None, None
                try:
                    hora_atual = datetime.now().time()
                    cortes = SessaoPG.query(CortePlanejamento).filter(
                        CortePlanejamento.Filial == str(filial).strip(),
                        CortePlanejamento.Ativo == True
                    ).order_by(CortePlanejamento.HorarioCorte).all()

                    if not cortes: return None, None, None, None
                    if len(cortes) == 1:
                        return cortes[0].IdCortePln, cortes[0].Corte, cortes[0].HorarioCorte, cortes[0].HorarioCorte

                    for i, c in enumerate(cortes):
                        if hora_atual <= c.HorarioCorte:
                            corte_anterior = cortes[i-1].HorarioCorte if i > 0 else cortes[-1].HorarioCorte
                            return c.IdCortePln, c.Corte, c.HorarioCorte, corte_anterior

                    return cortes[0].IdCortePln, cortes[0].Corte, cortes[0].HorarioCorte, cortes[-1].HorarioCorte
                except Exception as e:
                    LogService.Error("PlanejamentoService", f"Erro buscar_info_corte: {e}", e)
                    return None, None, None, None

            # 1. VALIDAÇÃO CABEÇALHO E AEROPORTOS
            id_aero_orig_cab = buscar_id_aeroporto(aero_origem)
            id_aero_dest_cab = buscar_id_aeroporto(aero_destino)

            if not id_aero_orig_cab: raise Exception(f"Aeroporto de Origem '{aero_origem}' inválido ou inativo.")
            if not id_aero_dest_cab: raise Exception(f"Aeroporto de Destino '{aero_destino}' inválido ou inativo.")

            id_corte_pln, num_corte, horario_corte, horario_anterior = buscar_info_corte(dados_ctc_principal.get('filial'))

            todos_docs = []
            if dados_ctc_principal.get('lista_docs'):
                todos_docs = dados_ctc_principal['lista_docs']
                eh_consolidado = dados_ctc_principal.get('is_consolidado', False)
                for idx, doc in enumerate(todos_docs):
                    doc['IndConsolidado'] = eh_consolidado if idx == 0 else False
            else:
                dados_ctc_principal['IndConsolidado'] = False
                todos_docs.append(dados_ctc_principal)

            # --- NOVA TRAVA DE HORÁRIO COM EXCEÇÃO (BACKLOG/REVERSA) ---
            for doc in todos_docs:
                data_doc = doc.get('data_emissao_real') or doc.get('data_emissao')
                motivodoc = doc.get('motivodoc', '')

                # 1. Checa se o documento é uma exceção
                is_exception = False
                if motivodoc == 'DEV':
                    is_exception = True # É Reversa
                else:
                    if data_doc:
                        d_date = None
                        if isinstance(data_doc, datetime): d_date = data_doc.date()
                        elif isinstance(data_doc, date): d_date = data_doc
                        else:
                            try:
                                d_date = datetime.fromisoformat(str(data_doc).split('T')[0]).date()
                            except:
                                try: d_date = datetime.strptime(str(data_doc)[:10], '%Y-%m-%d').date()
                                except: pass
                        
                        # É Backlog
                        if d_date and d_date < datetime.now().date():
                            is_exception = True
                
                # Se for exceção (Backlog ou Reversa) assume 1º Corte as 00:00 e ignora trava
                if is_exception:
                    doc['corte_aplicado'] = 1
                    doc['horario_corte_aplicado'] = time(0, 0)
                    continue

                # Se não for exceção (Documento do dia normal), aplica corte e trava
                doc['corte_aplicado'] = num_corte
                doc['horario_corte_aplicado'] = horario_corte

                if horario_corte and horario_anterior:
                    hora_doc_str = doc.get('hora_formatada') or doc.get('hora_emissao')
                    if not hora_doc_str: continue
                    
                    try:
                        hora_str_clean = str(hora_doc_str).replace(':', '').zfill(4)
                        if len(hora_str_clean) >= 4:
                            hora_obj = datetime.strptime(hora_str_clean[:4], '%H%M').time()
                            fora_da_janela = False

                            if horario_anterior == horario_corte:
                                if hora_obj > horario_corte:
                                    fora_da_janela = True
                            else:
                                if horario_anterior < horario_corte:
                                    if not (horario_anterior < hora_obj <= horario_corte):
                                        fora_da_janela = True
                                else:
                                    if not (hora_obj > horario_anterior or hora_obj <= horario_corte):
                                        fora_da_janela = True

                            if fora_da_janela:
                                msg_regra = f"até as {horario_corte.strftime('%H:%M')}" if horario_anterior == horario_corte else f"apenas entre {horario_anterior.strftime('%H:%M')} e {horario_corte.strftime('%H:%M')}"
                                raise Exception(f"TRAVA DE CORTE: O CTC {doc.get('ctc')} não pode ser planejado agora pois foi emitido às {hora_obj.strftime('%H:%M')}. O corte atual ({num_corte}º Corte) aceita documentos emitidos {msg_regra}.")
                    except Exception as e:
                        if "TRAVA DE CORTE" in str(e):
                            raise e

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
                Cabecalho.IdCortePln = id_corte_pln
                Cabecalho.MotorEscolha = motor_escolha 
                
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
                    TotalValor=get_val('valor'),
                    IdCortePln=id_corte_pln,
                    MotorEscolha=motor_escolha
                )
                SessaoPG.add(Cabecalho)
                SessaoPG.flush()

            # Salva os Itens
            for doc in todos_docs:
                cidade_orig = str(doc.get('origem_cidade', ''))
                uf_orig = str(doc.get('origem_uf') or doc.get('uf_orig', ''))
                cidade_dest = str(doc.get('destino_cidade', ''))
                uf_dest = str(doc.get('destino_uf') or doc.get('uf_dest', ''))
                
                data_doc = doc.get('data_emissao_real') or doc.get('data_emissao')
                hora_doc = doc.get('hora_formatada') or doc.get('hora_emissao')

                id_cid_orig = buscar_id_cidade(cidade_orig, uf_orig)
                id_cid_dest = buscar_id_cidade(cidade_dest, uf_dest)

                if not id_cid_orig: raise Exception(f"Cidade Origem '{cidade_orig}-{uf_orig}' não encontrada/inativa para CTC {doc.get('ctc')}")
                if not id_cid_dest: raise Exception(f"Cidade Destino '{cidade_dest}-{uf_dest}' não encontrada/inativa para CTC {doc.get('ctc')}")

                NfsBanco = SessaoPG.query(NfEsp).filter(NfEsp.filialctc == str(doc['ctc'])).all()

                if NfsBanco and len(NfsBanco) > 0:
                    QtdNotas = len(NfsBanco)
                    for nf_obj in NfsBanco:
                        SessaoPG.add(PlanejamentoItem(
                            IdPlanejamento=Cabecalho.IdPlanejamento,
                            Filial=str(doc['filial']),
                            Serie=str(doc['serie']),
                            Ctc=str(doc['ctc']),
                            NotaFiscal=str(nf_obj.numnf).strip() if nf_obj.numnf else '',
                            DataEmissao=data_doc,   
                            Hora=str(hora_doc),
                            # Puxa o Corte flexível (1 para Reversa/Backlog, ou o corte normal para os do dia)
                            Corte=doc.get('corte_aplicado', num_corte),
                            HorarioCorte=doc.get('horario_corte_aplicado', horario_corte),
                            Remetente=str(doc.get('remetente',''))[:100],
                            Destinatario=str(doc.get('destinatario',''))[:100],
                            OrigemCidade=cidade_orig[:50],
                            DestinoCidade=cidade_dest[:50],
                            IdCidadeOrigem=id_cid_orig,
                            IdCidadeDestino=id_cid_dest,
                            Volumes=int(doc.get('volumes', 0)) // QtdNotas,
                            PesoTaxado=float(doc.get('peso_taxado', 0) or doc.get('peso', 0)) / QtdNotas, 
                            ValMercadoria=float(doc.get('valor', 0) or doc.get('val_mercadoria', 0)) / QtdNotas,
                            IndConsolidado=doc.get('IndConsolidado', False)
                        ))
                else:
                    SessaoPG.add(PlanejamentoItem(
                        IdPlanejamento=Cabecalho.IdPlanejamento,
                        Filial=str(doc['filial']),
                        Serie=str(doc['serie']),
                        Ctc=str(doc['ctc']),
                        NotaFiscal=str(doc['ctc']),
                        DataEmissao=data_doc,
                        Hora=str(hora_doc),
                        Corte=doc.get('corte_aplicado', num_corte),
                        HorarioCorte=doc.get('horario_corte_aplicado', horario_corte),
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

                    id_frete = trecho.get('id_frete')
                    tipo_servico = trecho.get('tipo_servico')

                    if not id_frete:
                        id_frete_fallback, tipo_servico_frete_fallback = buscar_frete_info(origem_iata, destino_iata, cia)
                        id_frete = id_frete_fallback
                        if not tipo_servico:
                            tipo_servico = tipo_servico_frete_fallback

                    if not id_aero_orig: raise Exception(f"Trecho {idx+1}: Aeroporto Origem '{origem_iata}' inválido.")
                    if not id_aero_dest: raise Exception(f"Trecho {idx+1}: Aeroporto Destino '{destino_iata}' inválido.")
                    if not id_voo: raise Exception(f"Trecho {idx+1}: Voo {cia} {trecho.get('voo')} não encontrado na malha ativa.")
                    
                    if not tipo_servico:
                        servicos = ['STANDARD']
                        tipo_servico = random.choice(servicos) if servicos else 'STANDARD'
                        
                    horario_corte_trecho = None
                    if trecho.get('horario_corte'):
                        try: horario_corte_trecho = datetime.strptime(trecho.get('horario_corte'), '%H:%M').time()
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
                        HorarioCorte=horario_corte_trecho,
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
            Item = SessaoPG.query(PlanejamentoItem).join(PlanejamentoCabecalho).filter(
                PlanejamentoItem.Filial == str(filial),
                PlanejamentoItem.Serie == str(serie),
                PlanejamentoItem.Ctc == str(ctc),
                PlanejamentoCabecalho.Status != 'Cancelado'
            ).first()

            if not Item: return None

            Cabecalho = Item.Cabecalho
            PesoTotal = float(Cabecalho.TotalPeso or 0) 

            TrechosDB = SessaoPG.query(
                PlanejamentoTrecho, 
                TabelaFrete.Tarifa,
                TabelaFrete.Servico
            ).outerjoin(
                TabelaFrete, PlanejamentoTrecho.IdFrete == TabelaFrete.Id
            ).filter(
                PlanejamentoTrecho.IdPlanejamento == Cabecalho.IdPlanejamento
            ).order_by(PlanejamentoTrecho.Ordem).all()

            iatasUnicos = {
                str(iata or '').strip().upper()
                for row in TrechosDB
                for iata in (row[0].AeroportoOrigem, row[0].AeroportoDestino)
                if str(iata or '').strip()
            }

            coordsAeroportos = {}
            if iatasUnicos:
                aeroportosDb = (
                    SessaoPG.query(Aeroporto.CodigoIata, Aeroporto.Latitude, Aeroporto.Longitude)
                    .join(RemessaAeroportos, Aeroporto.IdRemessa == RemessaAeroportos.Id)
                    .filter(RemessaAeroportos.Ativo == True)
                    .filter(Aeroporto.CodigoIata.in_(iatasUnicos))
                    .all()
                )
                for aeroporto in aeroportosDb:
                    codigoIata = str(aeroporto.CodigoIata or '').strip().upper()
                    if not codigoIata:
                        continue
                    coordsAeroportos[codigoIata] = {
                        'lat': float(aeroporto.Latitude) if aeroporto.Latitude is not None else 0.0,
                        'lon': float(aeroporto.Longitude) if aeroporto.Longitude is not None else 0.0,
                    }

            RotaFormatada = []
            CustoTotalCalculado = 0.0
            PrimeiraPartida = None
            UltimaChegada = None

            for row in TrechosDB:
                t = row[0]
                val_tarifa = float(row[1] or 0)
                nm_servico = str(row[2] or 'STD') 

                partida_str = t.DataPartida.strftime('%H:%M') if t.DataPartida else "--:--"
                chegada_str = t.DataChegada.strftime('%H:%M') if t.DataChegada else "--:--"
                data_str = t.DataPartida.strftime('%d/%m/%Y') if t.DataPartida else ""
                
                DtPartida = datetime.combine(t.DataPartida, t.DataPartida.time()) if isinstance(t.DataPartida, datetime) else t.DataPartida
                DtChegada = datetime.combine(t.DataChegada, t.DataChegada.time()) if isinstance(t.DataChegada, datetime) else t.DataChegada
                
                if PrimeiraPartida is None: PrimeiraPartida = DtPartida
                UltimaChegada = DtChegada

                custo_trecho = val_tarifa * PesoTotal
                CustoTotalCalculado += custo_trecho

                origemIata = str(t.AeroportoOrigem or '').strip().upper()
                destinoIata = str(t.AeroportoDestino or '').strip().upper()
                coordsOrigem = coordsAeroportos.get(origemIata, {'lat': 0.0, 'lon': 0.0})
                coordsDestino = coordsAeroportos.get(destinoIata, {'lat': 0.0, 'lon': 0.0})

                RotaFormatada.append({
                    'cia': t.CiaAerea,
                    'voo': t.NumeroVoo,
                    'data': data_str,
                    'horario_saida': partida_str,
                    'horario_chegada': chegada_str,
                    'origem': {'iata': origemIata, 'lat': coordsOrigem['lat'], 'lon': coordsOrigem['lon']}, 
                    'destino': {'iata': destinoIata, 'lat': coordsDestino['lat'], 'lon': coordsDestino['lon']},
                    'base_calculo': {
                        'id_frete': t.IdFrete,
                        'servico': nm_servico,
                        'tarifa': val_tarifa,
                        'peso_usado': PesoTotal,
                        'custo_trecho': custo_trecho,
                        'custo_trecho_fmt': f"R$ {custo_trecho:,.2f}",
                    }
                })
            
            DuracaoMinutos = 0
            DuracaoFmt = "--:--"
            if PrimeiraPartida and UltimaChegada:
                diff = UltimaChegada - PrimeiraPartida
                DuracaoMinutos = diff.total_seconds() / 60
                
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

    @staticmethod
    def CancelarPlanejamento(id_planejamento, usuario):
        SessaoPG = ObterSessaoSqlServer()
        try:
            Cabecalho = SessaoPG.query(PlanejamentoCabecalho).get(id_planejamento)
            if not Cabecalho: return False, "Planejamento não encontrado."
            Cabecalho.Status = 'Cancelado'
            SessaoPG.commit()
            return True, "Cancelado com sucesso."
        except Exception as e:
            SessaoPG.rollback()
            LogService.Error("PlanejamentoService", "Erro ao cancelar", e)
            return False, str(e)
        finally:
            SessaoPG.close()

    @staticmethod
    def GerarExcelPlanejamentos():
        SessaoPG = ObterSessaoSqlServer()
        try:
            Resultados = SessaoPG.query(
                PlanejamentoItem,
                CtcEsp.rotafilialdest,
                CtcEsp.motivodoc,
                CtcEsp.remet_nome,
                CtcEsp.dest_nome,
                CtcEsp.respons_nome,
                CtcEspCpl.ctc_corresp,
                CtcEspCpl.TipoCarga,
                Filial.nomefilial
            ).join(
                PlanejamentoCabecalho, PlanejamentoItem.IdPlanejamento == PlanejamentoCabecalho.IdPlanejamento
            ).outerjoin(
                CtcEsp,
                (PlanejamentoItem.Filial.collate('DATABASE_DEFAULT') == CtcEsp.filial.collate('DATABASE_DEFAULT')) &
                (PlanejamentoItem.Serie.collate('DATABASE_DEFAULT') == CtcEsp.seriectc.collate('DATABASE_DEFAULT')) &
                (PlanejamentoItem.Ctc.collate('DATABASE_DEFAULT') == CtcEsp.filialctc.collate('DATABASE_DEFAULT'))
            ).outerjoin(
                CtcEspCpl, CtcEsp.filialctc == CtcEspCpl.filialctc
            ).outerjoin(
                Filial, PlanejamentoItem.Filial.collate('DATABASE_DEFAULT') == Filial.filial.collate('DATABASE_DEFAULT')
            ).options(
                joinedload(PlanejamentoItem.Cabecalho).joinedload(PlanejamentoCabecalho.Trechos),
                joinedload(PlanejamentoItem.CidadeOrigemObj),
                joinedload(PlanejamentoItem.CidadeDestinoObj)
            ).filter(
                PlanejamentoCabecalho.Status != 'Cancelado'
            ).all()

            DadosPlanilha = []
            Hoje = date.today()
            
            # Cache para evitar consultar o mesmo CTC da Farma repetidas vezes no banco
            CacheFarma = {}

            for Row in Resultados:
                Item = Row.PlanejamentoItem
                RotaLastMile = Row.rotafilialdest if Row.rotafilialdest else ''
                MotivoDoc = Row.motivodoc if Row.motivodoc else ''
                NomeFilialStr = str(Row.nomefilial).strip() if Row.nomefilial else Item.Filial
                TipoCargaStr = str(Row.TipoCarga).strip() if Row.TipoCarga else ''
                
                RemetNome = Row.remet_nome if Row.remet_nome else Item.Remetente
                DestNome = Row.dest_nome if Row.dest_nome else Item.Destinatario
                ClienteNome = Row.respons_nome if Row.respons_nome else Item.Remetente
                CtcCorresp = Row.ctc_corresp

                # --- LÓGICA DE SUBCONTRATAÇÃO FARMA ---
                if CtcCorresp and str(CtcCorresp).strip():
                    ctc_farma = str(CtcCorresp).strip()
                    if ctc_farma not in CacheFarma:
                        try:
                            query_farma = text("SELECT respons_nome FROM farma.dbo.tb_ctc_esp (NOLOCK) WHERE filialctc = :ctc")
                            farma_data = SessaoPG.execute(query_farma, {'ctc': ctc_farma}).fetchone()
                            if farma_data and farma_data.respons_nome:
                                CacheFarma[ctc_farma] = farma_data.respons_nome
                            else:
                                CacheFarma[ctc_farma] = None
                        except Exception as e_farma:
                            LogService.Warning("PlanejamentoService", f"Erro buscar subcontratação Farma no Excel: {e_farma}")
                            CacheFarma[ctc_farma] = None
                    
                    nome_farma = CacheFarma.get(ctc_farma)
                    if nome_farma:
                        ClienteNome = nome_farma

                # --- LÓGICA DE REVERSA (DEV) ---
                ClienteFinal = ClienteNome
                DestinatarioFinal = RemetNome if MotivoDoc == 'DEV' else DestNome

                if not ClienteFinal: ClienteFinal = Item.Remetente
                if not DestinatarioFinal: DestinatarioFinal = Item.Destinatario

                # --- MONTAGEM DOS TRECHOS DE VOO ---
                Cabecalho = Item.Cabecalho
                TrechoPrincipal = None
                VooFormatado = ""
                
                if Cabecalho.Trechos:
                    TrechosOrdenados = sorted(Cabecalho.Trechos, key=lambda t: t.Ordem)
                    if TrechosOrdenados:
                        TrechoPrincipal = TrechosOrdenados[0]
                        
                        TrechosStrings = []
                        for idx, trecho in enumerate(TrechosOrdenados):
                            origem = trecho.AeroportoOrigem or ''
                            destino = trecho.AeroportoDestino or ''
                            cia = trecho.CiaAerea or ''
                            voo = trecho.NumeroVoo or ''
                            saida = trecho.DataPartida.strftime('%H:%M') if getattr(trecho, 'DataPartida', None) else '--:--'
                            chegada = trecho.DataChegada.strftime('%H:%M') if getattr(trecho, 'DataChegada', None) else '--:--'
                            
                            if idx == 0:
                                str_t = f"EM {origem} VOO {cia} {voo} {saida} / {chegada} EM {destino}"
                            else:
                                str_t = f"VOO {cia} {voo} {saida} / {chegada} EM {destino}"
                                
                            TrechosStrings.append(str_t)
                            
                        VooFormatado = " - ".join(TrechosStrings)

                UfOrigem = Item.CidadeOrigemObj.Uf if Item.CidadeOrigemObj and hasattr(Item.CidadeOrigemObj, 'Uf') else ''
                UfDestino = Item.CidadeDestinoObj.Uf if Item.CidadeDestinoObj and hasattr(Item.CidadeDestinoObj, 'Uf') else ''
                
                TipoClassificacao = "DIÁRIO"
                if MotivoDoc == 'DEV':
                    TipoClassificacao = "REVERSA"
                elif Item.DataEmissao and Item.DataEmissao.date() < Hoje:
                    TipoClassificacao = "BACKLOG"

                # --- LÓGICA DO CORTE SEM HORÁRIO ---
                CorteFmt = ''
                if Item.Corte is not None:
                    CorteFmt = f"{Item.Corte}° Corte"

                DataPartidaFmt = TrechoPrincipal.DataPartida.strftime('%d/%m/%Y %H:%M') if TrechoPrincipal and TrechoPrincipal.DataPartida else ''

                # --- LÓGICA DE MULTIPLAS NOTAS FISCAIS EM LINHAS SEPARADAS ---
                NotasRawStr = str(Item.NotaFiscal).strip() if Item.NotaFiscal else str(Item.Ctc)
                # Divide por qualquer separador comum: vírgula, barra, ponto-e-vírgula ou espaço
                NotasLista = [n.strip() for n in re.split(r'[,;/|\s]+', NotasRawStr) if n.strip()]
                
                # Se após limpar não sobrar nada, ele garante que pelo menos use o CTC
                if not NotasLista:
                    NotasLista = [str(Item.Ctc)]

                # Cria uma linha duplicada idêntica pra cada nota fiscal separada no array
                for nf_individual in NotasLista:
                    Linha = {
                        'UF ORIGEM': UfOrigem,
                        'UNIDADE RESPONSÁVEL LAST MILE': RotaLastMile, 
                        'TIPO': TipoClassificacao, 
                        'TIPO DE CARGA': TipoCargaStr,
                        'CIA': TrechoPrincipal.CiaAerea if TrechoPrincipal else '',
                        'SERVIÇO': TrechoPrincipal.TipoServico if TrechoPrincipal else '',
                        'CORTE': CorteFmt,
                        'NOTA FISCAL': nf_individual, # Campo individualizado da NF
                        'CLIENTE': str(ClienteFinal).strip().upper() if ClienteFinal else '',
                        'RAZÃO SOCIAL DESTINATÁRIO': str(DestinatarioFinal).strip().upper() if DestinatarioFinal else '',
                        'CIDADE DESTINO': Item.DestinoCidade,
                        'UF DESTINO': UfDestino,
                        'VOLUMES': Item.Volumes,
                        'PESO': float(Item.PesoTaxado) if Item.PesoTaxado else 0.0,
                        'VALOR NF': float(Item.ValMercadoria) if Item.ValMercadoria else 0.0,
                        'PLANEJAMENTO': Cabecalho.IdPlanejamento,
                        'STATUS': Cabecalho.Status,
                        'FILIAL': NomeFilialStr, 
                        'SÉRIE': Item.Serie,
                        'CTC': Item.Ctc,
                        'VOO': VooFormatado, 
                        'PREVISÃO DT. PARTIDA': DataPartidaFmt
                    }
                    DadosPlanilha.append(Linha)

            DfPlanilha = pd.DataFrame(DadosPlanilha)
            ArquivoMemoria = io.BytesIO()
            
            with pd.ExcelWriter(ArquivoMemoria, engine='openpyxl') as EscritorExcel:
                DfPlanilha.to_excel(EscritorExcel, index=False, sheet_name='Planejamentos')
            
            ArquivoMemoria.seek(0)
            return ArquivoMemoria

        except Exception as ErroProcessamento:
            LogService.Error("PlanejamentoService", "Erro ao Gerar Excel dos Planeja mentos", ErroProcessamento)
            return None
        finally:
            SessaoPG.close()