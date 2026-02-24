import math
# Método HARVERSINE para cálculo de distância entre dois pontos geográficos
def Haversine(lat1, lon1, lat2, lon2):
    """ Este método calcula a distância em quilômetros entre dois pontos geográficos usando a fórmula Haversine.
    A fórmula Haversine é uma equação fundamental na navegação esférica, permitindo calcular a distância entre dois pontos na superfície de uma esfera (como a Terra) a partir de suas latitudes e longitudes.
    Ela é especialmente útil para calcular distâncias em rotas aéreas, marítimas ou terrestres, onde a curvatura da Terra deve ser considerada para obter resultados precisos.

    Returns:
        float: Distância em quilômetros entre os dois pontos.
        
        # Indice da fórmula:
        # Δφ = Delta Maiusculo + Phi Minusculo
        # Δλ = Delta Maiusculo + Lambda Minusculo
        # R = Raio da Terra
        # sin²(x) = valor do seno ao quadrado
        # atan2 = função arco tangente de dois argumentos
        
    """

    if not lat1 or not lon1 or not lat2 or not lon2: # Verufica se os dados são válidos
        return 999999 # Retorna infinito se faltar dados

    R = 6371 # Raio da Terra em km
    dLat = math.radians(lat2 - lat1) # Diferença de latitude em radianos
    dLon = math.radians(lon2 - lon1) # Diferença de longitude em radianos
    
    # a = sin²(Δφ/2) + cos φ1 ⋅ cos φ2 ⋅ sin²(Δλ/2)
    a = math.sin(dLat/2) * math.sin(dLat/2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLon/2) * math.sin(dLon/2)
    
    # c = 2 ⋅ atan2( √a, √(1−a) )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c