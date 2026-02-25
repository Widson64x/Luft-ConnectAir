import networkx as nx
from datetime import datetime, timedelta, time
from Services.LogService import LogService
from Services.TabelaFreteService import TabelaFreteService
from Services.CiaAereaService import CiaAereaService

class RouteIntelligenceService:
    """
    Serviço centralizado dedicado à inteligência de roteamento, montagem de grafos e categorização avançada.
    """

    # Pesos Base
    PESO_TEMPO = 1.0           
    PESO_CONEXAO = 150.0       
    PESO_CUSTO = 0.15        
    FATOR_PARCERIA_POWER = 2.2 
    PENALIDADE_SEM_TARIFA = 15000.0 

    @staticmethod
    def _DeParaServicoIdeal(servico_contratado, tipo_carga):
        """
        Função DEPARA: Analisa o serviço contratado pelo cliente e o tipo de carga
        para determinar quais serviços específicos da companhia aérea devem ser priorizados.
        """
        servico_str = str(servico_contratado).upper().strip() if servico_contratado else 'PADRÃO'
        carga_str = str(tipo_carga).upper().strip() if tipo_carga else 'GERAL'
        
        if carga_str == 'PERECIVEL' and 'EXPRESSO' in servico_str:
            return ['GOL LOG SAÚDE', 'GOL LOG RAPIDO', 'LATAM EXPRESSO (VELOZ)', 'LATAM RESERVADO']
        elif 'EXPRESSO' in servico_str:
            return ['GOL LOG SAÚDE', 'GOL LOG RAPIDO', 'GOL LOG ECONOMICO (SBY)', 'LATAM CONVENCIONAL (ESTANDAR MEDS)', 'LATAM EXPRESSO (VELOZ)', 'LATAM RESERVADO']
        else:
            return ['GOL LOG ECONOMICO (SBY)', 'LATAM CONVENCIONAL (ESTANDAR MEDS)']

    # =========================================================================
    # MOTOR DE GRAFOS E ROTEAMENTO (Movidos do MalhaService)
    # =========================================================================
    
    @staticmethod
    def AnalisarEEncontrarRotas(voos_db, data_inicio, lista_origens, lista_destinos, peso_total, tipo_carga, servico_contratado):
        """
        Método central que recebe os dados brutos e executa toda a inteligência (Grafo -> Caminhos -> Métricas -> Categorias).
        """
        LogService.Info("RouteIntelligence", "Iniciando processamento e montagem do grafo inteligente...")
        
        # 1. Obtém as regras de negócio (Scores e Serviços Alvo)
        ScoresParceria = CiaAereaService.ObterDicionarioScores()
        lista_servicos_alvo = RouteIntelligenceService._DeParaServicoIdeal(servico_contratado, tipo_carga)
        
        # 2. Montagem do Grafo filtrando parcerias bloqueadas
        G = nx.DiGraph()
        for Voo in voos_db:
            NomeCia = Voo.CiaAerea.strip().upper()
            if ScoresParceria.get(NomeCia, 50) <= 0:
                continue
            
            OrigemNo = Voo.AeroportoOrigem.strip().upper()
            DestinoNo = Voo.AeroportoDestino.strip().upper()
            if G.has_edge(OrigemNo, DestinoNo):
                G[OrigemNo][DestinoNo]['voos'].append(Voo)
            else:
                G.add_edge(OrigemNo, DestinoNo, voos=[Voo])
                
        # 3. Processamento de Caminhos
        ListaCandidatos = []
        for origem_iata in lista_origens:
            for destino_iata in lista_destinos:
                if not G.has_node(origem_iata) or not G.has_node(destino_iata): 
                    continue 

                try:
                    CaminhosNos = list(nx.all_simple_paths(G, source=origem_iata, target=destino_iata, cutoff=3))
                except: 
                    continue 

                for Caminho in CaminhosNos:
                    SequenciaVoos = RouteIntelligenceService._ValidarCaminhoCronologico(G, Caminho, data_inicio)
                    if not SequenciaVoos: continue
                    
                    # 4. Cálculo de Métricas da Rota
                    Duracao = RouteIntelligenceService._CalcularDuracaoRota(SequenciaVoos)
                    TrocasCia = RouteIntelligenceService._ContarTrocasCia(SequenciaVoos)
                    QtdEscalas = len(SequenciaVoos) - 1
                    DadosFinanceiros = RouteIntelligenceService.CalcularCustoRota(SequenciaVoos, peso_total, lista_servicos_alvo)

                    ScoreParceriaAcumulado = sum([ScoresParceria.get(v.CiaAerea.strip().upper(), 50) for v in SequenciaVoos])
                    MediaParceria = ScoreParceriaAcumulado / len(SequenciaVoos) if len(SequenciaVoos) > 0 else 50
                    
                    ListaCandidatos.append({
                        'rota': SequenciaVoos,
                        'detalhes_tarifas': DadosFinanceiros['detalhes'],
                        'metricas': {
                            'duracao': Duracao, 
                            'custo': DadosFinanceiros['custo_total'], 
                            'escalas': QtdEscalas, 
                            'trocas_cia': TrocasCia, 
                            'indice_parceria': MediaParceria,
                            'sem_tarifa': DadosFinanceiros['sem_tarifa'],
                            'score': 0
                        }
                    })
        
        # 5. Otimiza e Categoriza as Opções encontradas
        return RouteIntelligenceService.OtimizarOpcoes(ListaCandidatos, tipo_carga, servico_contratado)

    @staticmethod
    def CalcularCustoRota(lista_voos, peso_total, lista_servicos_alvo=None):
        custo_total = 0.0
        detalhes_financeiros = []
        sem_tarifa_flag = False

        for voo in lista_voos:
            custo_trecho, info_frete = TabelaFreteService.CalcularCustoEstimado(
                voo.AeroportoOrigem, voo.AeroportoDestino, voo.CiaAerea, peso_total, lista_servicos_preferenciais=lista_servicos_alvo 
            )

            if info_frete.get('tarifa_missing', False):
                sem_tarifa_flag = True
            
            info_frete['custo_calculado'] = custo_trecho
            custo_total += custo_trecho
            detalhes_financeiros.append(info_frete)

        return {'custo_total': custo_total, 'detalhes': detalhes_financeiros, 'sem_tarifa': sem_tarifa_flag}

    @staticmethod
    def _ValidarCaminhoCronologico(Grafo, ListaNos, DataInicio):
        VoosEscolhidos = []
        MomentoDisponivel = DataInicio if isinstance(DataInicio, datetime) else datetime.combine(DataInicio, time.min)
        for i in range(len(ListaNos) - 1):
            Origem, Destino = ListaNos[i], ListaNos[i+1]
            if Destino not in Grafo[Origem]: return None
            OpcoesVoos = sorted(Grafo[Origem][Destino]['voos'][:], key=lambda v: (v.DataPartida, v.HorarioSaida))
            
            CiaPreferida = VoosEscolhidos[-1].CiaAerea if VoosEscolhidos else None
            if CiaPreferida: OpcoesVoos = [v for v in OpcoesVoos if v.CiaAerea == CiaPreferida] + [v for v in OpcoesVoos if v.CiaAerea != CiaPreferida]
            
            VooViavel = None
            for Voo in OpcoesVoos:
                SaidaVoo = datetime.combine(Voo.DataPartida, Voo.HorarioSaida)
                if i == 0:
                    if SaidaVoo >= MomentoDisponivel: VooViavel = Voo; break
                else:
                    ChegadaAnt = datetime.combine(VoosEscolhidos[-1].DataPartida, VoosEscolhidos[-1].HorarioChegada)
                    if VoosEscolhidos[-1].HorarioChegada < VoosEscolhidos[-1].HorarioSaida: ChegadaAnt += timedelta(days=1)
                    if SaidaVoo >= ChegadaAnt + timedelta(hours=1) and SaidaVoo <= ChegadaAnt + timedelta(hours=48): VooViavel = Voo; break
            
            if VooViavel:
                VoosEscolhidos.append(VooViavel)
                ChegadaVoo = datetime.combine(VooViavel.DataPartida, VooViavel.HorarioChegada)
                if VooViavel.HorarioChegada < VooViavel.HorarioSaida: ChegadaVoo += timedelta(days=1)
                MomentoDisponivel = ChegadaVoo
            else: return None
        return VoosEscolhidos

    @staticmethod
    def _CalcularDuracaoRota(ListaVoos):
        if not ListaVoos: return 0
        Primeiro, Ultimo = ListaVoos[0], ListaVoos[-1]
        Inicio = datetime.combine(Primeiro.DataPartida, Primeiro.HorarioSaida)
        Fim = datetime.combine(Ultimo.DataPartida, Ultimo.HorarioChegada)
        if Ultimo.HorarioChegada < Ultimo.HorarioSaida: Fim += timedelta(days=1)
        while Fim < Inicio: Fim += timedelta(days=1)
        return (Fim - Inicio).total_seconds() / 60

    @staticmethod
    def _ContarTrocasCia(ListaVoos):
        if not ListaVoos: return 0
        return sum(1 for i in range(len(ListaVoos)-1) if ListaVoos[i].CiaAerea != ListaVoos[i+1].CiaAerea)

    # =========================================================================
    # LÓGICA DE SCORE E CATEGORIZAÇÃO
    # =========================================================================
    @staticmethod
    def OtimizarOpcoes(lista_candidatos, tipo_carga=None, servico_contratado=None):
        """
        Gera as categorias influenciadas pelo serviço contratado e tipo de carga.
        """
        
        # Estrutura de Retorno
        Categorias = {
            'recomendada': [], 
            'direta': [],
            'rapida': [], 
            'economica': [], 
            'conexao_mesma_cia': [],
            'interline': []
        }

        if not lista_candidatos:
            return Categorias

        candidatos_processados = []

        LogService.Info("RouteIntelligence", f"--- CATEGORIZANDO {len(lista_candidatos)} OPCOES ---")

        # --- INTELIGÊNCIA DINÂMICA (DEPARA) ---
        servicos_prioritarios = RouteIntelligenceService._DeParaServicoIdeal(servico_contratado, tipo_carga)
        eh_perecivel_expresso = (str(tipo_carga).upper().strip() == 'PERECIVEL' and 'EXPRESSO' in str(servico_contratado).upper().strip())
        
        peso_tempo_dinamico = RouteIntelligenceService.PESO_TEMPO
        peso_custo_dinamico = RouteIntelligenceService.PESO_CUSTO
        
        if eh_perecivel_expresso:
            LogService.Info("RouteIntelligence", "Modo PERECÍVEL+EXPRESSO ativado: Ignorando custos e forçando melhores serviços da cia.")
            peso_custo_dinamico = 0.0  # Zera o impacto financeiro (Ignorando Valores)
            peso_tempo_dinamico *= 5.0 # Peso extremo no tempo
        elif servico_contratado and 'EXPRESSO' in str(servico_contratado).upper():
            peso_custo_dinamico *= 0.5 # Financeiro pesa menos
            peso_tempo_dinamico *= 3.0 # Tempo pesa mais
            LogService.Info("RouteIntelligence", "Modo EXPRESSO ativado: Ajustando pesos algorítmicos.")

        # 1. Cálculo de Score para todos
        for i, item in enumerate(lista_candidatos):
            metricas = item['metricas']
            
            # CORREÇÃO AQUI: Lemos do 'detalhes_tarifas' e não do 'rota'
            servico_usado = ""
            if 'detalhes_tarifas' in item and len(item['detalhes_tarifas']) > 0:
                servico_usado = str(item['detalhes_tarifas'][0].get('servico', '')).upper().strip()
            
            # Verifica se a companhia aérea está oferecendo o serviço aderente à inteligência
            servico_alinhado = (servico_usado in servicos_prioritarios)
            
            # Recalcula Score passando os pesos e parâmetros dinâmicos
            novo_score, _ = RouteIntelligenceService._CalcularScoreAvancado(
                duracao=metricas['duracao'],
                custo=metricas['custo'],
                conexoes=metricas['escalas'],
                trocas_cia=metricas['trocas_cia'],
                indice_parceria=metricas['indice_parceria'],
                sem_tarifa=metricas['sem_tarifa'],
                peso_tempo_atual=peso_tempo_dinamico,   
                peso_custo_atual=peso_custo_dinamico,
                eh_perecivel_expresso=eh_perecivel_expresso,
                servico_alinhado=servico_alinhado
            )
            item['metricas']['score'] = novo_score
            candidatos_processados.append(item)

        # 2. Preenchimento das Categorias

        # A) RECOMENDADA (Menor Score Geral)
        candidatos_processados.sort(key=lambda x: x['metricas']['score'])
        
        # Se for perecível, permite custo alto. Se não, tenta pegar uma que tenha custo < 10000 e NÃO seja "Sem Tarifa".
        if candidates_validos := [c for c in candidatos_processados if (c['metricas']['custo'] < 10000 or eh_perecivel_expresso) and not c['metricas']['sem_tarifa']]:
             Categorias['recomendada'] = candidates_validos[0]
        elif candidatos_processados:
             Categorias['recomendada'] = candidatos_processados[0]

        # B) DIRETA (0 Escalas)
        diretas = [c for c in candidatos_processados if c['metricas']['escalas'] == 0]
        if diretas:
            diretas.sort(key=lambda x: x['metricas']['score'])
            Categorias['direta'] = diretas[0]

        # C) RÁPIDA (Menor Duração)
        rapidas = sorted(candidatos_processados, key=lambda x: x['metricas']['duracao'])
        if rapidas:
            Categorias['rapida'] = rapidas[0]

        # D) ECONÔMICA (Menor Custo)
        economicas = [c for c in candidatos_processados if c['metricas']['custo'] < 10000 and not c['metricas']['sem_tarifa']]
        if economicas:
            economicas.sort(key=lambda x: x['metricas']['custo'])
            Categorias['economica'] = economicas[0]

        # E) COM CONEXÕES (Mesma Cia)
        conexoes_simples = [c for c in candidatos_processados if c['metricas']['escalas'] > 0 and c['metricas']['trocas_cia'] == 0]
        if conexoes_simples:
            conexoes_simples.sort(key=lambda x: x['metricas']['score'])
            Categorias['conexao_mesma_cia'] = conexoes_simples[0]

        # F) INTERLINE (Troca de Cia)
        interline = [c for c in candidatos_processados if c['metricas']['trocas_cia'] > 0]
        if interline:
            interline.sort(key=lambda x: x['metricas']['score'])
            Categorias['interline'] = interline[0]

        return Categorias

    @staticmethod
    def _CalcularScoreAvancado(duracao, custo, conexoes, trocas_cia, indice_parceria, sem_tarifa, peso_tempo_atual, peso_custo_atual, eh_perecivel_expresso, servico_alinhado):
        # Base usando os pesos dinâmicos que vieram por parâmetro
        pontos_tempo = duracao * peso_tempo_atual
        pontos_conexoes = conexoes * RouteIntelligenceService.PESO_CONEXAO
        pontos_trocas = trocas_cia * 300 
        score_base = pontos_tempo + pontos_conexoes + pontos_trocas
        
        # Financeiro 
        fator_custo = 0
        if sem_tarifa:
            fator_custo = RouteIntelligenceService.PENALIDADE_SEM_TARIFA
        elif custo > 14000:
            fator_custo = RouteIntelligenceService.PENALIDADE_SEM_TARIFA
        else:
            fator_custo = float(custo) * peso_custo_atual

        # Parceria
        bonus_parceria = (float(indice_parceria) ** RouteIntelligenceService.FATOR_PARCERIA_POWER) / 50.0
        
        score_final = (score_base + fator_custo) - bonus_parceria
        
        # --- LÓGICA DO DEPARA DE SERVIÇOS ---
        
        # 1. Se o voo possui exatamente o serviço "top" focado para este cliente, damos um super bônus.
        if servico_alinhado:
            score_final -= 5000.0
            
        # 2. Se a carga DEVE ser Expressa e Perecível, e esse voo NÃO TEM o serviço aderente, 
        # penalizamos fortemente para que ele não se torne "Recomendada".
        if eh_perecivel_expresso and not servico_alinhado:
            score_final += 10000.0
        
        return score_final, ""