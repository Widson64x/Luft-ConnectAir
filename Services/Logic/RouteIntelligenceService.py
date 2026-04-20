import numpy as np
import networkx as nx
from datetime import datetime, timedelta, time
from typing import Optional

from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Aeroporto import Aeroporto, RemessaAeroportos
from Utils.Geometria import Haversine
from Services.LogService import LogService
from Services.TabelaFreteService import TabelaFreteService
from Services.CiaAereaService import CiaAereaService
from Services.Logic.RouteConfig import ContextoRota, ScoringWeights, resolver_contexto
from Services.Logic.RouteMLEngine import RouteMLEngine


class RouteIntelligenceService:
    """
    Motor de roteamento inteligente:
    Grafos (NetworkX) -> Caminhos Cronologicos -> Score Vetorizado (NumPy + ML) -> Categorias

    Para mudar pesos ou regras de servico: edite Services/Logic/RouteConfig.py
    Para treinar o modelo ML:              chame RouteMLEngine.Treinar()
    Para registrar escolha do planejador:  chame RouteMLEngine.VincularPlanejamento() (em Routes/Planejamento.py)
    """

    # -------------------------------------------------------------------------
    # ENTRADA PRINCIPAL
    # -------------------------------------------------------------------------

    @staticmethod
    def AnalisarEEncontrarRotas(
        voos_db, data_inicio, lista_origens, lista_destinos,
        peso_total, tipo_carga, servico_contratado,
    ) -> dict:
        ctx = ContextoRota(tipo_carga, servico_contratado)
        servicos_alvo, pesos = resolver_contexto(ctx)

        LogService.Info("RouteIntelligence",
            f"Contexto: {ctx.tipo_carga}/{ctx.servico_contratado} | "
            f"peso_tempo={pesos.peso_tempo:.1f}  peso_custo={pesos.peso_custo:.3f}")

        scores_parceria = CiaAereaService.ObterDicionarioScores()
        G = RouteIntelligenceService._construir_grafo(voos_db, scores_parceria)
        LogService.Info("RouteIntelligence", f"Grafo: {G.number_of_nodes()} nos, {G.number_of_edges()} arestas")

        coords = RouteIntelligenceService._carregar_coordenadas()

        # Pre-carrega todas as tarifas em um único batch SQL (evita N+1 queries por candidato)
        cache_tarifas = TabelaFreteService.CarregarCacheParaVoos(voos_db)

        candidatos = RouteIntelligenceService._explorar_caminhos(
            G, lista_origens, lista_destinos, data_inicio, peso_total, servicos_alvo, scores_parceria, coords,
            cache_tarifas=cache_tarifas,
        )

        return RouteIntelligenceService._categorizar(candidatos, pesos, ctx, servicos_alvo)

    # -------------------------------------------------------------------------
    # GRAFO
    # -------------------------------------------------------------------------

    @staticmethod
    def _construir_grafo(voos_db, scores_parceria: dict) -> nx.DiGraph:
        G = nx.DiGraph()
        for voo in voos_db:
            cia = voo.CiaAerea.strip().upper()
            if scores_parceria.get(cia, 50) <= 0:
                continue
            o = voo.AeroportoOrigem.strip().upper()
            d = voo.AeroportoDestino.strip().upper()
            if G.has_edge(o, d):
                G[o][d]['voos'].append(voo)
            else:
                G.add_edge(o, d, voos=[voo])
        return G

    # -------------------------------------------------------------------------
    # EXPLORACAO DE CAMINHOS
    # -------------------------------------------------------------------------

    @staticmethod
    def _explorar_caminhos(
        G, origens, destinos, data_inicio, peso_total, servicos_alvo, scores_parceria, coords: dict,
        cache_tarifas=None,
    ) -> list:
        candidatos = []

        for origem in origens:
            for destino in destinos:
                if not G.has_node(origem):
                    LogService.Warning("RouteIntelligence", f"Origem {origem} ausente no grafo.")
                    continue
                if not G.has_node(destino):
                    LogService.Warning("RouteIntelligence", f"Destino {destino} ausente no grafo.")
                    continue

                try:
                    caminhos = list(nx.all_simple_paths(G, source=origem, target=destino, cutoff=3))
                except Exception as e:
                    LogService.Error("RouteIntelligence", "Erro no motor de caminhos", e)
                    continue

                LogService.Info("RouteIntelligence", f"{origem}->{destino}: {len(caminhos)} caminhos teoricos")

                for caminho in caminhos:
                    voos = RouteIntelligenceService._validar_cronologico(G, caminho, data_inicio)
                    if not voos:
                        continue

                    financeiro   = RouteIntelligenceService.CalcularCustoRota(voos, peso_total, servicos_alvo, cache_tarifas=cache_tarifas)
                    parceria_med = sum(scores_parceria.get(v.CiaAerea.strip().upper(), 50) for v in voos) / len(voos)

                    candidatos.append({
                        'rota':            voos,
                        'detalhes_tarifas': financeiro['detalhes'],
                        'metricas': {
                            'duracao':         RouteIntelligenceService._duracao(voos),
                            'custo':           financeiro['custo_total'],
                            'escalas':         len(voos) - 1,
                            'trocas_cia':      RouteIntelligenceService._trocas_cia(voos),
                            'indice_parceria': parceria_med,
                            'sem_tarifa':      financeiro['sem_tarifa'],
                            'fator_desvio':    RouteIntelligenceService._calcular_desvio(voos, coords),
                            'score':           0.0,
                        },
                    })

        return candidatos

    # -------------------------------------------------------------------------
    # SCORE VETORIZADO (NumPy)
    # -------------------------------------------------------------------------

    @staticmethod
    def _calcular_scores(
        candidatos: list, pesos: ScoringWeights, ctx: ContextoRota, servicos_alvo: list,
    ) -> list:
        if not candidatos:
            return candidatos

        col = lambda key: np.array([c['metricas'][key] for c in candidatos], dtype=float)

        duracoes  = col('duracao')
        custos    = col('custo')
        escalas   = col('escalas')
        trocas    = col('trocas_cia')
        parcerias = col('indice_parceria')
        sem_tar   = col('sem_tarifa')
        desvios   = col('fator_desvio')

        svcs_usados = [
            str(c['detalhes_tarifas'][0].get('servico', '')).upper().strip()
            if c.get('detalhes_tarifas') else ''
            for c in candidatos
        ]
        alinhado = np.array([s in servicos_alvo for s in svcs_usados], dtype=float)

        fator_custo = np.where(
            sem_tar == 1,  pesos.penalidade_sem_tarifa,
            np.where(
                custos > pesos.limiar_custo_alto, pesos.penalidade_custo_alto,
                custos * pesos.peso_custo,
            ),
        )

        scores = (
            duracoes  * pesos.peso_tempo
            + escalas * pesos.peso_conexao
            + trocas  * pesos.penalidade_troca_cia
            + fator_custo
            + (desvios - 1.0) * pesos.penalidade_desvio
            - (parcerias ** pesos.fator_parceria) / 50.0
            - alinhado * pesos.bonus_servico_alinhado
            + (1 - alinhado) * pesos.penalidade_perecivel_desalinhado * int(ctx.eh_perecivel_expresso)
        )

        # Ajuste ML por candidato (modelo pre-carregado em memoria, chamada e rapida)
        scores_base = scores.copy()
        for i, c in enumerate(candidatos):
            features = {
                'duracao':               duracoes[i],
                'custo':                 custos[i],
                'escalas':               escalas[i],
                'trocas_cia':            trocas[i],
                'indice_parceria':       parcerias[i],
                'sem_tarifa':            sem_tar[i],
                'eh_perecivel_expresso': int(ctx.eh_perecivel_expresso),
                'servico_alinhado':      alinhado[i],
            }
            rota_voos = c.get('rota', [])
            aero_orig = rota_voos[0].AeroportoOrigem.strip().upper() if rota_voos else None
            aero_dest = rota_voos[-1].AeroportoDestino.strip().upper() if rota_voos else None
            bonus                  = RouteMLEngine.PredizirBonus(features, aero_orig=aero_orig, aero_dest=aero_dest)
            scores[i]             += bonus
            c['metricas']['score'] = float(scores[i])
            c['_ml_features']      = features
            c['_score_base']       = float(scores_base[i])
            c['_bonus_ml']         = float(bonus)

        ativos = sum(1 for c in candidatos if abs(c.get('_bonus_ml', 0.0)) > 1.0)
        if ativos:
            idx_com_ml = min(range(len(candidatos)), key=lambda i: candidatos[i]['metricas']['score'])
            idx_sem_ml = min(range(len(candidatos)), key=lambda i: candidatos[i].get('_score_base', 0.0))
            ml_decisivo = (idx_com_ml != idx_sem_ml) # O modelo ML mudou o vencedor (melhor score) em comparação ao score base sem ML
            vencedor_tem_ml = abs(candidatos[idx_com_ml].get('_bonus_ml', 0.0)) > 1.0

            if ml_decisivo:
                LogService.Info("RouteIntelligence",
                    f"ML ATIVO: ajuste aplicado em {ativos}/{len(candidatos)} candidatos — vencedor alterado pelo ML")
            elif vencedor_tem_ml:
                LogService.Info("RouteIntelligence",
                    f"ML ATIVO: ajuste aplicado em {ativos}/{len(candidatos)} candidatos — vencedor confirmado pelo ML")
            else:
                # Bonuses ativos mas o vencedor é um aeroporto desconhecido — manter scores base
                for c in candidatos:
                    c['_bonus_ml'] = 0.0
                    c['metricas']['score'] = c.get('_score_base', c['metricas']['score'])
                LogService.Info("RouteIntelligence",
                    f"ML: ajuste parcial ({ativos}/{len(candidatos)} candidatos) — vencedor sem cobertura ML, GRAFO mantido")
        else:
            LogService.Debug("RouteIntelligence",
                "ML: sem modelo treinado — scores sem ajuste ML (fallback puro)")

        return candidatos

    # -------------------------------------------------------------------------
    # CATEGORIZACAO
    # -------------------------------------------------------------------------

    @staticmethod
    def _categorizar(
        candidatos: list, pesos: ScoringWeights, ctx: ContextoRota, servicos_alvo: list,
    ) -> dict:
        resultado = {k: None for k in
                     ('recomendada', 'direta', 'rapida', 'economica', 'conexao_mesma_cia', 'interline')}

        if not candidatos:
            LogService.Warning("RouteIntelligence", "Nenhum candidato aprovado nos filtros cronologicos.")
            return resultado

        candidatos = RouteIntelligenceService._calcular_scores(candidatos, pesos, ctx, servicos_alvo)
        by_score   = sorted(candidatos, key=lambda c: c['metricas']['score'])

        tem_tarifa = lambda c: (
            not c['metricas']['sem_tarifa']
            and c['metricas']['custo'] < pesos.limiar_custo_recomendada
        )

        validos = [c for c in by_score if tem_tarifa(c) or ctx.eh_perecivel_expresso]
        resultado['recomendada'] = (validos or by_score)[0]

        diretas = [c for c in by_score if c['metricas']['escalas'] == 0]
        resultado['direta'] = diretas[0] if diretas else None

        resultado['rapida'] = min(candidatos, key=lambda c: c['metricas']['duracao'])

        com_tarifa = [c for c in candidatos if tem_tarifa(c)]
        resultado['economica'] = min(com_tarifa, key=lambda c: c['metricas']['custo']) if com_tarifa else None

        mesma_cia = [c for c in by_score if c['metricas']['escalas'] > 0 and c['metricas']['trocas_cia'] == 0]
        resultado['conexao_mesma_cia'] = mesma_cia[0] if mesma_cia else None

        interline = [c for c in by_score if c['metricas']['trocas_cia'] > 0]
        resultado['interline'] = interline[0] if interline else None

        n_cat = sum(1 for v in resultado.values() if v)
        LogService.Info("RouteIntelligence", f"Categorizacao: {n_cat}/6 categorias preenchidas.")
        return resultado

    # -------------------------------------------------------------------------
    # CUSTO
    # -------------------------------------------------------------------------

    @staticmethod
    def CalcularCustoRota(lista_voos, peso_total, lista_servicos_alvo=None, cache_tarifas=None) -> dict:
        custo_total = 0.0
        detalhes    = []
        sem_tarifa  = False

        for voo in lista_voos:
            if cache_tarifas is not None:
                cia_norm   = TabelaFreteService._NormalizarNomeCia(voo.CiaAerea)
                orig       = str(voo.AeroportoOrigem or '').strip().upper()
                dest       = str(voo.AeroportoDestino or '').strip().upper()
                info_cache = cache_tarifas.get((cia_norm, orig, dest))
                if info_cache:
                    info  = dict(info_cache)  # cópia para não mutar o cache compartilhado
                    custo = info['tarifa_base'] * float(peso_total)
                    info['peso_calculado']  = float(peso_total)
                    info['custo_calculado'] = custo
                else:
                    # Par sem tarifa no batch — não abre nova sessão, marca como missing
                    custo = 0.0
                    info  = {
                        'tarifa_missing':  True,
                        'custo_calculado': 0.0,
                        'peso_calculado':  float(peso_total),
                    }
            else:
                custo, info = TabelaFreteService.CalcularCustoEstimado(
                    voo.AeroportoOrigem, voo.AeroportoDestino, voo.CiaAerea,
                    peso_total, lista_servicos_preferenciais=lista_servicos_alvo,
                )
                info['custo_calculado'] = custo

            sem_tarifa  = sem_tarifa or info.get('tarifa_missing', False)
            custo_total += custo
            detalhes.append(info)

        return {'custo_total': custo_total, 'detalhes': detalhes, 'sem_tarifa': sem_tarifa}

    # -------------------------------------------------------------------------
    # VALIDACAO CRONOLOGICA
    # -------------------------------------------------------------------------

    @staticmethod
    def _validar_cronologico(G, nos: list, data_inicio) -> Optional[list]:
        """
        Para cada caminho teórico, tenta TODAS as combinações de voo possíveis
        começando do primeiro trecho, aceitando conexões de 3h a 36h.
        Retorna a sequência válida mais cedo (menor data de partida total), ou None.
        """
        inicio = data_inicio if isinstance(data_inicio, datetime) else datetime.combine(data_inicio, time.min)

        origem0, destino0 = nos[0], nos[1]
        if not G.has_edge(origem0, destino0):
            return None

        primeiros_voos = sorted(
            [v for v in G[origem0][destino0]['voos']
             if datetime.combine(v.DataPartida, v.HorarioSaida) >= inicio],
            key=lambda v: (v.DataPartida, v.HorarioSaida),
        )

        for primeiro_voo in primeiros_voos:
            resultado = RouteIntelligenceService._construir_cadeia_cronologica(
                G, nos, [primeiro_voo], trecho_idx=1,
            )
            if resultado is not None:
                return resultado

        return None

    @staticmethod
    def _construir_cadeia_cronologica(G, nos: list, voos_ate_agora: list, trecho_idx: int) -> Optional[list]:
        """Recursivo: dado os voos já escolhidos, tenta encaixar o próximo trecho."""
        if trecho_idx == len(nos) - 1:
            return voos_ate_agora  # Caminho completo

        origem  = nos[trecho_idx]
        destino = nos[trecho_idx + 1]
        if not G.has_edge(origem, destino):
            return None

        opcoes = sorted(G[origem][destino]['voos'], key=lambda v: (v.DataPartida, v.HorarioSaida))

        # Preferência: mesma cia do trecho anterior
        cia_ant = voos_ate_agora[-1].CiaAerea
        opcoes = [v for v in opcoes if v.CiaAerea == cia_ant] + \
                 [v for v in opcoes if v.CiaAerea != cia_ant]

        chegada_ant = RouteIntelligenceService._chegada(voos_ate_agora[-1])

        for voo in opcoes:
            saida = datetime.combine(voo.DataPartida, voo.HorarioSaida)
            if chegada_ant + timedelta(hours=3) <= saida <= chegada_ant + timedelta(hours=36):
                resultado = RouteIntelligenceService._construir_cadeia_cronologica(
                    G, nos, voos_ate_agora + [voo], trecho_idx + 1,
                )
                if resultado is not None:
                    return resultado

        return None

    # -------------------------------------------------------------------------
    # COORDENADAS DE AEROPORTOS (cache local por chamada)
    # -------------------------------------------------------------------------

    @staticmethod
    def _carregar_coordenadas() -> dict:
        """Retorna {IATA: (lat, lon)} usando a remessa ativa de aeroportos."""
        sessao = ObterSessaoSqlServer()
        try:
            rows = (
                sessao.query(Aeroporto.CodigoIata, Aeroporto.Latitude, Aeroporto.Longitude)
                .join(RemessaAeroportos, Aeroporto.IdRemessa == RemessaAeroportos.Id)
                .filter(RemessaAeroportos.Ativo == True)
                .filter(Aeroporto.Latitude.isnot(None))
                .filter(Aeroporto.Longitude.isnot(None))
                .all()
            )
            return {
                r.CodigoIata.upper(): (float(r.Latitude), float(r.Longitude))
                for r in rows if r.CodigoIata
            }
        except Exception as e:
            LogService.Warning("RouteIntelligence", f"Falha ao carregar coordenadas: {e}")
            return {}
        finally:
            sessao.close()

    @staticmethod
    def _calcular_desvio(voos: list, coords: dict) -> float:
        """
        Razão entre a soma das distâncias de cada trecho e a distância direta origem→destino.
        1.0 = rota sem desvio (caminho ótimo).
        Valores acima indicam retrocesso geográfico (ex.: GIG→SSA→GRU→BEL retorna ao sul antes de subir).
        """
        if len(voos) < 2:
            return 1.0
        iatas = [voos[0].AeroportoOrigem.upper()] + [v.AeroportoDestino.upper() for v in voos]
        o, d = iatas[0], iatas[-1]
        if o not in coords or d not in coords:
            return 1.0
        dist_direta = Haversine(coords[o][0], coords[o][1], coords[d][0], coords[d][1])
        if dist_direta < 1:
            return 1.0
        dist_total = 0.0
        for i in range(len(iatas) - 1):
            a, b = iatas[i], iatas[i + 1]
            if a not in coords or b not in coords:
                return 1.0  # Sem dados → sem penalidade (benefício da dúvida)
            dist_total += Haversine(coords[a][0], coords[a][1], coords[b][0], coords[b][1])
        return dist_total / dist_direta

    # -------------------------------------------------------------------------
    # HELPERS DE DATA/HORA
    # -------------------------------------------------------------------------

    @staticmethod
    def _chegada(voo) -> datetime:
        dt = datetime.combine(voo.DataPartida, voo.HorarioChegada)
        return dt + timedelta(days=1) if voo.HorarioChegada < voo.HorarioSaida else dt

    @staticmethod
    def _duracao(voos: list) -> float:
        if not voos:
            return 0.0
        inicio = datetime.combine(voos[0].DataPartida, voos[0].HorarioSaida)
        fim    = RouteIntelligenceService._chegada(voos[-1])
        while fim < inicio:
            fim += timedelta(days=1)
        return (fim - inicio).total_seconds() / 60

    @staticmethod
    def _trocas_cia(voos: list) -> int:
        return sum(1 for i in range(len(voos) - 1) if voos[i].CiaAerea != voos[i + 1].CiaAerea)


