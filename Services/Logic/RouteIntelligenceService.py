from Services.LogService import LogService

class RouteIntelligenceService:
    """
    Serviço dedicado à inteligência de roteamento e categorização avançada.
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
        
        # 1. PERECÍVEL + EXPRESSO (Urgência Máxima) 
        if carga_str == 'PERECIVEL' and 'EXPRESSO' in servico_str:
            """
            Serviços top de linha para cargas perecíveis e que exigem rapidez extrema.
            OBS: Mantemos os serviços expressos como opção, pois podem ser mais rápidos e o cliente pode se interessar caso sejam 
            apresentados como recomendação. Nesses casos sempre damos um super bônus para os serviços que se encaixam nessa categoria, 
            mas sem eliminar completamente as outras opções, já que o cliente pode ter escolhido expresso por outros motivos 
            (ex: prioridade na entrega, mesmo que a carga não seja perecível).
             A ideia aqui é que, mesmo para clientes que escolheram expresso, os serviços mais rápidos e aderentes à carga perecível 
             sejam destacados como recomendação, mas sem eliminar completamente os serviços expressos, já que o cliente demonstrou interesse em 
             algo mais rápido.
            """
            return [
                'GOL LOG SAÚDE', 
                'GOL LOG RAPIDO',
                'LATAM EXPRESSO (VELOZ)', 
                'LATAM RESERVADO', 
            ]
        
        # 2. EXPRESSO (Prioridade Alta) Porém sem a urgência extrema da perecibilidade
        elif 'EXPRESSO' in servico_str:
            """
            Serviços premium para clientes que optaram por serviço expresso, mesmo sem ser perecível.
            OBS: Mantemos os serviços economicos como opção, pois o cliente pode ter escolhido expresso por outros motivos 
            (ex: prioridade na entrega, mesmo que a carga não seja perecível).
            Aqui seria o meio termo, onde damos preferência para os serviços expressos, mas sem eliminar completamente os econômicos, 
            já que o cliente demonstrou interesse em algo mais rápido.
            """
            return [
                'GOL LOG SAÚDE', 
                'GOL LOG RAPIDO',
                'GOL LOG ECONOMICO (SBY)',
                'LATAM CONVENCIONAL (ESTANDAR MEDS)',
                'LATAM EXPRESSO (VELOZ)',
                'LATAM RESERVADO'
            ]
        
        # 3. PADRÃO / ECONÔMICO / CONVENCIONAL
        else:
            """
            Serviços padrão para clientes que não optaram por serviços expressos ou perecíveis.
            OBS: Mesmo para clientes que não escolheram expresso, mantemos os serviços expressos como opção, pois podem ser mais rápidos 
            e o cliente pode se interessar caso sejam apresentados como recomendação.
            """
            return [
                'GOL LOG ECONOMICO (SBY)', 
                'LATAM CONVENCIONAL (ESTANDAR MEDS)'
            ]

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