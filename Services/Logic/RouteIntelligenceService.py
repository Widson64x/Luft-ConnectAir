from Services.LogService import LogService

class RouteIntelligenceService:
    """
    Serviço dedicado à inteligência de roteamento e ranking de opções.
    Centraliza os pesos e as regras de negócio para definir a 'Melhor Rota'.
    """

    # --- PESOS DE PONDERAÇÃO (Configurável) ---
    PESO_TEMPO = 1.0          # 1 ponto por minuto
    PESO_CONEXAO = 150.0      # 150 pontos por conexão (equivale a 2h30 de penalidade)
    PESO_CUSTO = 0.15         # 0.15 pontos por R$ 1,00 (R$ 100 = 15 pontos)
    
    # Fator Exponencial de Parceria: Quanto maior, mais a parceria "perdoa" custos e tempos altos
    FATOR_PARCERIA_POWER = 2.8 
    
    # Penalidade para rotas sem tarifa (para jogá-las para baixo, mas não ocultar)
    PENALIDADE_SEM_TARIFA = 5000.0 

    @staticmethod
    def OtimizarOpcoes(lista_candidatos):
        """
        Recebe uma lista de candidatos (dicionários com 'rota', 'metricas', 'detalhes_tarifas').
        Retorna o dicionário categorizado: recomendada, rapida, custo, etc.
        """
        Opcoes = {
            'recomendada': [], 
            'mais_rapida': [], 
            'menor_custo': [], 
            'menos_conexoes': []
        }

        if not lista_candidatos:
            return Opcoes

        candidatos_processados = []

        # 1. Processamento e Cálculo de Score Profundo
        for item in lista_candidatos:
            metricas = item['metricas']
            
            # Recalcula o Score com a lógica avançada
            novo_score = RouteIntelligenceService._CalcularScoreAvancado(
                duracao=metricas['duracao'],
                custo=metricas['custo'],
                conexoes=metricas['escalas'],
                trocas_cia=metricas['trocas_cia'],
                indice_parceria=metricas['indice_parceria'],
                sem_tarifa=metricas['sem_tarifa']
            )
            
            # Atualiza o score no objeto
            item['metricas']['score'] = novo_score
            candidatos_processados.append(item)

        # 2. Estratégias de Ordenação (Ranking)

        # A) Mais Rápida (Puramente tempo)
        candidatos_processados.sort(key=lambda x: x['metricas']['duracao'])
        Opcoes['mais_rapida'] = candidatos_processados[0]

        # B) Menor Custo (Ignora quem não tem tarifa)
        com_custo = [r for r in candidatos_processados if not r['metricas']['sem_tarifa']]
        if com_custo:
            com_custo.sort(key=lambda x: x['metricas']['custo'])
            Opcoes['menor_custo'] = com_custo[0]
        elif candidatos_processados:
            # Fallback se ninguém tiver tarifa
            Opcoes['menor_custo'] = candidatos_processados[0]

        # C) Menos Conexões (Prioriza voo direto, desempata por tempo)
        candidatos_processados.sort(key=lambda x: (x['metricas']['escalas'], x['metricas']['duracao']))
        Opcoes['menos_conexoes'] = candidatos_processados[0]

        # D) RECOMENDADA (O Algoritmo Principal)
        # Ordena pelo Score calculado (menor é melhor)
        candidatos_processados.sort(key=lambda x: x['metricas']['score'])
        vencedora = candidatos_processados[0]
        
        LogService.Info("RouteIntelligence", 
            f"Vencedora: {vencedora['rota'][0].CiaAerea} | Score: {vencedora['metricas']['score']:.1f} | "
            f"Parceria: {vencedora['metricas']['indice_parceria']}%"
        )
        
        Opcoes['recomendada'] = vencedora

        return Opcoes

    @staticmethod
    def _CalcularScoreAvancado(duracao, custo, conexoes, trocas_cia, indice_parceria, sem_tarifa):
        """
        Algoritmo profundo de análise de qualidade da rota.
        Objetivo: Score Baixo = Melhor Rota.
        """
        
        # 1. Custo Base (O "Sofrimento" do cliente)
        # Tempo pesa 1:1. Conexões pesam muito.
        score_base = (duracao * RouteIntelligenceService.PESO_TEMPO) + \
                     (conexoes * RouteIntelligenceService.PESO_CONEXAO) + \
                     (trocas_cia * 200) # Troca de companhia é pior que conexão simples
        
        # 2. Análise Financeira
        if sem_tarifa:
            # Se não tem tarifa, aplicamos uma penalidade fixa alta.
            # Isso garante que voos PAGOS e VIÁVEIS apareçam antes dos "Consultar",
            # a menos que o voo pago seja absurdamente ruim.
            fator_custo = RouteIntelligenceService.PENALIDADE_SEM_TARIFA
        else:
            fator_custo = custo * RouteIntelligenceService.PESO_CUSTO

        # 3. Fator de Parceria (O Diferencial Estratégico)
        # A parceria funciona como um "Redutor de Custo/Sofrimento".
        # Se Parceria = 100%, reduzimos o impacto negativo significativamente.
        # Fórmula: Bonus = (IndiceParceria ^ Power) 
        # Ex: 100^2.8 = ~400.000 (valor alto para subtrair do custo)
        # Ajustamos a escala para não quebrar a matemática
        
        bonus_parceria = (indice_parceria ** RouteIntelligenceService.FATOR_PARCERIA_POWER) / 50.0
        
        # Score Final = (Dores + Custo) - BonusParceria
        score_final = (score_base + fator_custo) - bonus_parceria
        
        return score_final