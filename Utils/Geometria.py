import math

def Haversine(lat1, lon1, lat2, lon2):
    """
    Calcula a distância em Km entre dois pontos geográficos. Com base na fórmula Haversine.
    Retorna 999999 se algum dos pontos for inválido. Utiliza das coordenadas em decimal.
    """
    if not lat1 or not lon1 or not lat2 or not lon2:
        return 999999 # Retorna infinito se faltar dados

    R = 6371 # Raio da Terra em km
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    
    a = math.sin(dLat/2) * math.sin(dLat/2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLon/2) * math.sin(dLon/2)
        
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c