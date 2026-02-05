import math
# Método HARVERSINE para cálculo de distância entre dois pontos geográficos
def Haversine(lat1, lon1, lat2, lon2):
    """
    Calcula a distância em Km entre dois pontos geográficos. Com base na fórmula Haversine.
    Retorna 999999 se algum dos pontos for inválido. Utiliza das coordenadas em decimal.
    """
    if not lat1 or not lon1 or not lat2 or not lon2: # Verufica se os dados são válidos
        return 999999 # Retorna infinito se faltar dados

    R = 6371 # Raio da Terra em km
    dLat = math.radians(lat2 - lat1) # Diferença de latitude em radianos
    dLon = math.radians(lon2 - lon1) # Diferença de longitude em radianos
    
    """_summary_

    Returns:
        _type_: _description_
        
        # INDICE DA FÓRMULA:
        # Δφ = Delta Maiusculo + Phi Minusculo
        # Δλ = Delta Maiusculo + Lambda Minusculo
        # R = Raio da Terra
        # sin²(x) = valor do seno ao quadrado
        # atan2 = função arco tangente de dois argumentos
        
    """
    
    
    # a = sin²(Δφ/2) + cos φ1 ⋅ cos φ2 ⋅ sin²(Δλ/2)
    a = math.sin(dLat/2) * math.sin(dLat/2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLon/2) * math.sin(dLon/2)
    
    # c = 2 ⋅ atan2( √a, √(1−a) )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c