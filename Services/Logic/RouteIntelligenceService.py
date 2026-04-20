import numpy as np
from datetime import datetime, timedelta

from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Aeroporto import Aeroporto
from Models.SQL_SERVER.MalhaAerea import RemessaMalha, VooMalha
from Services.CiaAereaService import CiaAereaService
from Services.LogService import LogService
from Services.Logic.RouteConfig import (
    ContextoRota,
    REGRAS_BUSCA_PADRAO,
    RouteSearchRules,
    ScoringWeights,
    normalizar_iatas,
    resolver_contexto,
)
from Services.Logic.RouteGraphEngine import RouteGraphEngine
from Services.Logic.RouteMLEngine import RouteMLEngine
from Services.TabelaFreteService import TabelaFreteService


class RouteIntelligenceService:
    """
    Orquestrador do fluxo de montagem de rotas.

    Esta classe mantém apenas o fluxo base do processo:
      consulta da malha -> geração de candidatos -> score -> categorização -> formatação

    Cada engine especializada vive separada em Services/Logic:
      - RouteGraphEngine: monta sequências válidas de voos pela malha
      - RouteMLEngine: ajusta ranking com aprendizado histórico
      - RouteAIEngine: reservado para uso futuro
    """

    CATEGORIAS_RESULTADO = (
        'recomendada',
        'direta',
        'rapida',
        'economica',
        'conexao_mesma_cia',
        'interline',
    )

    # -------------------------------------------------------------------------
    # ENTRADA PRINCIPAL
    # -------------------------------------------------------------------------

    @classmethod
    def BuscarOpcoesDeRotas(
        cls,
        data_inicio,
        data_fim,
        lista_origens,
        lista_destinos,
        peso_total=100.0,
        tipo_carga=None,
        servico_contratado=None,
        ml_context=None,
    ) -> dict:
        resultados = cls._novo_resultado_formatado()
        origens = normalizar_iatas(lista_origens)
        destinos = normalizar_iatas(lista_destinos)

        if not origens or not destinos:
            LogService.Warning("RouteIntelligence", "Busca ignorada: origens ou destinos vazios.")
            return resultados

        sessao = ObterSessaoSqlServer()
        try:
            LogService.Warning("RouteIntelligence", "=== BUSCA INTELIGENTE INICIADA ===")
            LogService.Info("RouteIntelligence", f"IATAs Buscados -> Origens: {origens} | Destinos: {destinos}")

            voos_db = cls._buscar_voos_disponiveis(sessao, data_inicio, data_fim, REGRAS_BUSCA_PADRAO)
            if not voos_db:
                LogService.Warning("RouteIntelligence", "FALHA: Nenhum voo foi encontrado no banco de dados para as datas solicitadas!")
                return resultados

            opcoes_brutas = cls.AnalisarEEncontrarRotas(
                voos_db=voos_db,
                data_inicio=data_inicio,
                lista_origens=origens,
                lista_destinos=destinos,
                peso_total=peso_total,
                tipo_carga=tipo_carga,
                servico_contratado=servico_contratado,
                regras=REGRAS_BUSCA_PADRAO,
            )

            if ml_context and any(valor for valor in opcoes_brutas.values() if valor):
                RouteMLEngine.RegistrarSessaoAnalise(
                    opcoes_brutas=opcoes_brutas,
                    filial=ml_context.get('filial', ''),
                    serie=ml_context.get('serie', ''),
                    ctc=ml_context.get('ctc', ''),
                    tipo_carga=tipo_carga,
                    servico_contratado=servico_contratado,
                    usuario=ml_context.get('usuario', ''),
                )

            return cls._formatar_resultados(sessao, opcoes_brutas)

        except Exception as e:
            LogService.Error("RouteIntelligence", "ERRO CRÍTICO em BuscarOpcoesDeRotas", e)
            return resultados
        finally:
            sessao.close()

    @classmethod
    def AnalisarEEncontrarRotas(
        cls,
        voos_db,
        data_inicio,
        lista_origens,
        lista_destinos,
        peso_total,
        tipo_carga,
        servico_contratado,
        regras: RouteSearchRules = REGRAS_BUSCA_PADRAO,
    ) -> dict:
        ctx = ContextoRota(tipo_carga, servico_contratado)
        servicos_alvo, pesos = resolver_contexto(ctx)

        LogService.Info("RouteIntelligence",
            f"Contexto: {ctx.tipo_carga}/{ctx.servico_contratado} | "
            f"peso_tempo={pesos.peso_tempo:.3f}  peso_custo={pesos.peso_custo:.3f}")

        scores_parceria = CiaAereaService.ObterDicionarioScores()
        cache_tarifas = TabelaFreteService.CarregarCacheParaVoos(voos_db)
        coords = RouteGraphEngine.CarregarCoordenadas()

        rotas = RouteGraphEngine.GerarRotasCronologicas(
            voos_db=voos_db,
            data_inicio=data_inicio,
            lista_origens=normalizar_iatas(lista_origens),
            lista_destinos=normalizar_iatas(lista_destinos),
            scores_parceria=scores_parceria,
            regras=regras,
        )

        candidatos = cls._montar_candidatos(
            rotas=rotas,
            peso_total=peso_total,
            servicos_alvo=servicos_alvo,
            scores_parceria=scores_parceria,
            coords=coords,
            regras=regras,
            cache_tarifas=cache_tarifas,
        )

        return cls._categorizar(candidatos, pesos, ctx, servicos_alvo, regras)

    # -------------------------------------------------------------------------
    # CONSULTA / MONTAGEM BASE
    # -------------------------------------------------------------------------

    @staticmethod
    def _buscar_voos_disponiveis(sessao, data_inicio, data_fim, regras: RouteSearchRules) -> list:
        filtro_data_inicio = data_inicio.date() if isinstance(data_inicio, datetime) else data_inicio
        filtro_data_fim = data_fim.date() if isinstance(data_fim, datetime) else data_fim
        data_limite = filtro_data_fim + timedelta(days=regras.dias_adicionais_busca)

        voos_db = (
            sessao.query(VooMalha)
            .join(RemessaMalha)
            .filter(
                RemessaMalha.Ativo == True,
                VooMalha.DataPartida >= filtro_data_inicio,
                VooMalha.DataPartida <= data_limite,
            )
            .all()
        )

        LogService.Info("RouteIntelligence", f"Buscando voos entre {filtro_data_inicio} e {data_limite}")
        LogService.Info("RouteIntelligence", f"Quantidade de voos totais resgatados da base: {len(voos_db)}")
        return voos_db

    @classmethod
    def _montar_candidatos(
        cls,
        rotas: list[list],
        peso_total,
        servicos_alvo: list,
        scores_parceria: dict,
        coords: dict,
        regras: RouteSearchRules,
        cache_tarifas=None,
    ) -> list:
        candidatos = []

        for voos in rotas:
            financeiro = cls.CalcularCustoRota(
                voos,
                peso_total,
                servicos_alvo,
                cache_tarifas=cache_tarifas,
            )

            parceria_media = sum(
                scores_parceria.get(str(voo.CiaAerea or '').strip().upper(), regras.score_parceria_padrao)
                for voo in voos
            ) / len(voos)

            candidatos.append({
                'rota': voos,
                'detalhes_tarifas': financeiro['detalhes'],
                'metricas': {
                    'duracao': cls._duracao(voos),
                    'custo': financeiro['custo_total'],
                    'escalas': len(voos) - 1,
                    'trocas_cia': cls._trocas_cia(voos),
                    'indice_parceria': parceria_media,
                    'sem_tarifa': financeiro['sem_tarifa'],
                    'fator_desvio': RouteGraphEngine.CalcularDesvio(voos, coords),
                    'score': 0.0,
                },
            })

        return candidatos

    @classmethod
    def _formatar_resultados(cls, sessao, opcoes_brutas: dict) -> dict:
        resultados = cls._novo_resultado_formatado()
        cache_aeroportos = {}
        voos_para_cache = []

        for candidato in opcoes_brutas.values():
            if candidato:
                voos_para_cache.extend(candidato['rota'])

        cls._completar_cache_aeroportos(sessao, voos_para_cache, cache_aeroportos)

        def formatar(candidato, tag):
            if not candidato:
                return []
            return cls._formatar_lista_rotas(
                candidato['rota'],
                cache_aeroportos,
                tag,
                candidato['metricas'],
                candidato['detalhes_tarifas'],
                bonus_ml=candidato.get('_bonus_ml', 0.0),
            )

        resultados['recomendada'] = formatar(opcoes_brutas.get('recomendada'), 'Recomendada')
        resultados['direta'] = formatar(opcoes_brutas.get('direta'), 'Voo Direto')
        resultados['rapida'] = formatar(opcoes_brutas.get('rapida'), 'Mais Rápida')
        resultados['economica'] = formatar(opcoes_brutas.get('economica'), 'Mais Econômica')
        resultados['conexao_mesma_cia'] = formatar(opcoes_brutas.get('conexao_mesma_cia'), 'Conexão (Mesma Cia)')
        resultados['interline'] = formatar(opcoes_brutas.get('interline'), 'Interline (Múltiplas Cias)')

        return resultados

    @staticmethod
    def _completar_cache_aeroportos(sessao, lista_voos, cache):
        iatas = set()
        for voo in lista_voos:
            iatas.add(voo.AeroportoOrigem)
            iatas.add(voo.AeroportoDestino)

        faltantes = [iata for iata in iatas if iata not in cache]
        if not faltantes:
            return

        for aeroporto in sessao.query(Aeroporto).filter(Aeroporto.CodigoIata.in_(faltantes)).all():
            cache[aeroporto.CodigoIata] = {
                'nome': aeroporto.NomeAeroporto,
                'lat': float(aeroporto.Latitude or 0),
                'lon': float(aeroporto.Longitude or 0),
            }

    @staticmethod
    def _formatar_lista_rotas(lista_voos, cache, tipo, metricas=None, detalhes_tarifas=None, bonus_ml: float = 0.0):
        resultado = []
        info_adicional = {}

        if metricas:
            total_segundos = int(metricas['duracao'] * 60)
            dias, resto = divmod(total_segundos, 86400)
            horas, minutos = divmod(resto, 3600)
            minutos //= 60
            duracao_fmt = f"{dias}d {horas:02}:{minutos:02}" if dias > 0 else f"{horas:02}:{minutos:02}"
            custo_fmt = f"R$ {metricas['custo']:,.2f}"
            info_adicional = {
                'total_duracao': duracao_fmt,
                'total_custo': custo_fmt,
                'total_custo_fmt': custo_fmt,
                'total_custo_raw': metricas['custo'],
                'ml_ativo': abs(bonus_ml) > REGRAS_BUSCA_PADRAO.limiar_bonus_ml_relevante,
                'ml_bonus': round(bonus_ml, 2),
            }

        for idx, voo in enumerate(lista_voos):
            origem = cache.get(voo.AeroportoOrigem, {'nome': voo.AeroportoOrigem})
            destino = cache.get(voo.AeroportoDestino, {'nome': voo.AeroportoDestino})
            dados_frete = detalhes_tarifas[idx] if detalhes_tarifas and idx < len(detalhes_tarifas) else {}
            custo_trecho = dados_frete.get('custo_calculado', 0.0)

            cia_tabela = dados_frete.get('cia_tarifaria')
            cia_voo = str(voo.CiaAerea or '').strip()
            cia_final = cia_tabela if cia_tabela else cia_voo

            resultado.append({
                'tipo_resultado': tipo,
                'cia': cia_voo,
                'voo': voo.NumeroVoo,
                'data': voo.DataPartida.strftime('%d/%m/%Y'),
                'horario_saida': voo.HorarioSaida.strftime('%H:%M'),
                'horario_chegada': voo.HorarioChegada.strftime('%H:%M'),
                'origem': {
                    'iata': voo.AeroportoOrigem,
                    'nome': origem.get('nome'),
                    'lat': origem.get('lat'),
                    'lon': origem.get('lon'),
                },
                'destino': {
                    'iata': voo.AeroportoDestino,
                    'nome': destino.get('nome'),
                    'lat': destino.get('lat'),
                    'lon': destino.get('lon'),
                },
                'base_calculo': {
                    'id_frete': dados_frete.get('id_frete'),
                    'tarifa': dados_frete.get('tarifa_base', 0.0),
                    'servico': dados_frete.get('servico', 'STANDARD'),
                    'cia_tarifaria': cia_final,
                    'peso_usado': dados_frete.get('peso_calculado', 0),
                    'custo_trecho': custo_trecho,
                    'custo_trecho_fmt': f"R$ {custo_trecho:,.2f}",
                },
                **info_adicional,
            })

        return resultado

    # -------------------------------------------------------------------------
    # SCORE VETORIZADO (NumPy)
    # -------------------------------------------------------------------------

    @staticmethod
    def _calcular_scores(
        candidatos: list,
        pesos: ScoringWeights,
        ctx: ContextoRota,
        servicos_alvo: list,
        regras: RouteSearchRules,
    ) -> list:
        """
        Pontua cada candidato de rota. Score MENOR = rota MELHOR (ranking ascendente).

        A fórmula combina penalidades e bônus em quatro dimensões:
          1. Tempo        → duração total da rota
          2. Conexões     → número de escalas + trocas de CIA
          3. Custo        → estratificado: sem tarifa > caro > proporcional
          4. Qualidade    → penalidade por desvio geográfico − bônus de parceria
          5. Serviço      → bônus/penalidade por alinhamento com o serviço contratado

        Após o score base (determinístico), o ML aplica um ajuste calibrado para a
        mesma escala do score base. O impacto é logado quando altera o vencedor.
        """
        if not candidatos:
            return candidatos

        # Extrai arrays NumPy de cada métrica — vetorizado, sem loop Python
        col = lambda key: np.array([c['metricas'][key] for c in candidatos], dtype=float)

        duracoes  = col('duracao')          # minutos totais de voo da origem ao destino
        custos    = col('custo')            # R$ total estimado para o peso informado
        escalas   = col('escalas')          # número de conexões (0 = direto)
        trocas    = col('trocas_cia')       # quantas trocas de companhia aérea na rota
        parcerias = col('indice_parceria')  # score médio de parceria das CIAs (0–100)
        sem_tar   = col('sem_tarifa')       # 1 se algum trecho está sem tarifa cadastrada
        desvios   = col('fator_desvio')     # razão dist_percorrida / dist_direta (1.0 = ótimo)

        # Verifica se o serviço do primeiro trecho bate com o serviço contratado
        svcs_usados = [
            str(c['detalhes_tarifas'][0].get('servico', '')).upper().strip()
            if c.get('detalhes_tarifas') else ''
            for c in candidatos
        ]
        alinhado = np.array([s in servicos_alvo for s in svcs_usados], dtype=float)

        # ── 1. Penalidade de TEMPO ────────────────────────────────────────────
        # Cada minuto extra na rota adiciona peso_tempo ao score.
        # Para perecível expresso, resolver_contexto multiplica este peso por 5.
        pen_tempo = duracoes * pesos.peso_tempo

        # ── 2. Penalidade de ESCALA ───────────────────────────────────────────
        # Cada conexão adiciona peso_conexao=20 pontos.
        # É uma penalidade propositalmente alta para que voos diretos sigam priorizados.
        pen_escala = escalas * pesos.peso_conexao

        # ── 3. Penalidade de TROCA DE CIA ─────────────────────────────────────
        # Mudar de companhia em uma escala = processo de liberação diferente,
        # mais manuseio e risco de perda. Penalidade por troca individual.
        pen_troca = trocas * pesos.penalidade_troca_cia

        # ── 4. Penalidade de CUSTO ────────────────────────────────────────────
        # Estratificada em 3 níveis (do mais grave ao menos grave):
        #   a) Sem tarifa cadastrada → penalidade máxima: custo real desconhecido
        #   b) Custo acima do limiar → penalidade alta: rota cara demais para aprovar
        #   c) Custo normal          → penalidade proporcional ao valor (custo × peso)
        pen_custo = np.where(
            sem_tar == 1,
            pesos.penalidade_sem_tarifa,
            np.where(
                custos > pesos.limiar_custo_alto,
                pesos.penalidade_custo_alto,
                custos * pesos.peso_custo,
            ),
        )

        # ── 5. Penalidade de DESVIO GEOGRÁFICO ───────────────────────────────
        # Razão: distância total percorrida / distância direta origem→destino.
        # Valor 1.0 = caminho ótimo (sem desvio). Valores > 1.0 indicam retrocesso.
        # Ex.: GRU→SSA→GIG tem desvio ~1.7 (SSA fica ao norte, mas GIG ao sul).
        pen_desvio = (desvios - 1.0) * pesos.penalidade_desvio

        # ── 6. Bônus de PARCERIA ──────────────────────────────────────────────
        # CIAs com parceria alta recebem bônus com crescimento exponencial (^2.2).
        # Isso cria separação clara entre parceiros premium e básicos — um parceiro
        # com score 90 recebe proporcionalmente muito mais bônus que um com score 60.
        bon_parceria = (parcerias ** pesos.fator_parceria) / pesos.divisor_parceria

        # ── 7. Bônus por SERVIÇO ALINHADO ─────────────────────────────────────
        # Rota que oferece exatamente o serviço contratado pelo cliente é premiada.
        # Ex.: cliente pediu "GOL LOG SAÚDE" → rota com "GOL LOG SAÚDE" ganha bônus.
        bon_servico = alinhado * pesos.bonus_servico_alinhado

        # ── 8. Penalidade perecível sem serviço alinhado ──────────────────────
        # Cargas perecíveis em modo expresso EXIGEM o serviço correto para
        # garantir a cadeia de frio. Se o serviço não bate, penalidade extra.
        pen_perecivel = (
            (1 - alinhado)
            * pesos.penalidade_perecivel_desalinhado
            * int(ctx.eh_perecivel_expresso)
        )

        # ── Score base (puro algorítmico, sem ML) ─────────────────────────────
        # Soma de todas as penalidades menos todos os bônus.
        # Score MENOR = rota MELHOR.
        scores = (
            pen_tempo
            + pen_escala
            + pen_troca
            + pen_custo
            + pen_desvio
            - bon_parceria
            - bon_servico
            + pen_perecivel
        )

        # ── Ajuste ML (opcional) ──────────────────────────────────────────────
        # PredizirBonus() consulta o modelo treinado e retorna ±pontos com base
        # nos padrões históricos das decisões dos planejadores.
        # Só é aplicado quando o modelo está confiante (|prob - 0.5| > CONFIANCA_MINIMA).
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

        # ── Diagnóstico do impacto ML ─────────────────────────────────────────
        # Conta quantos candidatos receberam ajuste significativo.
        # Compara quem seria o vencedor COM e SEM o ajuste ML.
        limiar_bonus_ml = regras.limiar_bonus_ml_relevante
        ativos = sum(1 for c in candidatos if abs(c.get('_bonus_ml', 0.0)) > limiar_bonus_ml)
        if ativos:
            idx_com_ml = min(range(len(candidatos)), key=lambda i: candidatos[i]['metricas']['score'])
            idx_sem_ml = min(range(len(candidatos)), key=lambda i: candidatos[i].get('_score_base', 0.0))
            ml_decisivo     = (idx_com_ml != idx_sem_ml)
            vencedor_tem_ml = abs(candidatos[idx_com_ml].get('_bonus_ml', 0.0)) > limiar_bonus_ml

            if ml_decisivo:
                LogService.Info("RouteIntelligence",
                    f"ML ATIVO: ajuste aplicado em {ativos}/{len(candidatos)} candidatos — vencedor alterado pelo ML")
            elif vencedor_tem_ml:
                LogService.Info("RouteIntelligence",
                    f"ML ATIVO: ajuste aplicado em {ativos}/{len(candidatos)} candidatos — vencedor confirmado pelo ML")
            else:
                # ML tem cobertura parcial, mas o vencedor algorítmico está fora dela.
                # Descarta os ajustes para não distorcer o ranking de forma assimétrica.
                for c in candidatos:
                    c['_bonus_ml'] = 0.0
                    c['metricas']['score'] = c.get('_score_base', c['metricas']['score'])
                LogService.Info("RouteIntelligence",
                    f"ML: ajuste parcial ({ativos}/{len(candidatos)} candidatos) — vencedor sem cobertura ML, score base mantido")
        else:
            LogService.Debug("RouteIntelligence",
                "ML: sem modelo treinado ou confiança insuficiente — ranking por score algorítmico puro")

        return candidatos

    # -------------------------------------------------------------------------
    # CATEGORIZACAO
    # -------------------------------------------------------------------------

    @classmethod
    def _categorizar(
        cls,
        candidatos: list,
        pesos: ScoringWeights,
        ctx: ContextoRota,
        servicos_alvo: list,
        regras: RouteSearchRules,
    ) -> dict:
        resultado = cls._novo_resultado_bruto()

        if not candidatos:
            LogService.Warning("RouteIntelligence", "Nenhum candidato aprovado nos filtros cronologicos.")
            return resultado

        candidatos = cls._calcular_scores(candidatos, pesos, ctx, servicos_alvo, regras)
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

    @classmethod
    def _novo_resultado_bruto(cls) -> dict:
        return {categoria: None for categoria in cls.CATEGORIAS_RESULTADO}

    @classmethod
    def _novo_resultado_formatado(cls) -> dict:
        return {categoria: [] for categoria in cls.CATEGORIAS_RESULTADO}


