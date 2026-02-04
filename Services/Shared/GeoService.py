from sqlalchemy import distinct
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Cidade import Cidade, RemessaCidade
from Models.SQL_SERVER.Aeroporto import Aeroporto, RemessaAeroportos
from Models.SQL_SERVER.MalhaAerea import VooMalha, RemessaMalha 
from Utils.Geometria import Haversine
from Utils.Texto import NormalizarTexto

def BuscarCoordenadasCidade(NomeCidade, Uf):
    Sessao = ObterSessaoSqlServer()
    try:
        if not NomeCidade or not Uf: return None
        
        # Normalização para evitar erros de acento (Itajaí vs Itajai)
        NomeBusca = NormalizarTexto(NomeCidade)
        UfBusca = NormalizarTexto(Uf)
        # Buscar todas as cidades do estado
        CidadesDoEstado = Sessao.query(Cidade)\
        .filter(RemessaCidade.Ativo == True) \
        .filter(Cidade.Uf == UfBusca).all()
        
        for c in CidadesDoEstado:
            NomeBanco = NormalizarTexto(c.NomeCidade)
            if NomeBanco == NomeBusca or NomeBusca in NomeBanco:
                return {
                    'lat': c.Latitude, 
                    'lon': c.Longitude, 
                    'nome': c.NomeCidade,
                    'uf': c.Uf
                }
        return None
    finally:
        Sessao.close()

def BuscarAeroportoMaisProximo(Lat, Lon):
    """
    Busca o aeroporto mais próximo que TENHA VOOS NA MALHA ATIVA.
    """
    Sessao = ObterSessaoSqlServer()
    try:
        # 1. Lista de aeroportos que realmente operam (têm voos saindo) NA MALHA ATIVA
        AeroportosAtivos = Sessao.query(distinct(VooMalha.AeroportoOrigem))\
            .join(RemessaMalha)\
            .filter(RemessaMalha.Ativo == True)\
            .all()
            
        ListaIatasAtivos = [a[0] for a in AeroportosAtivos]

        if not ListaIatasAtivos:
            # Se não tem malha ativa, não retorna nenhum aeroporto como "ativo"
            print("⚠️ Nenhuma malha ativa encontrada.")
            return None
        else:
            # Busca dados geográficos apenas dos aeroportos ativos
            TodosAeroportos = Sessao.query(
                Aeroporto.CodigoIata, 
                Aeroporto.Latitude, 
                Aeroporto.Longitude, 
                Aeroporto.NomeAeroporto
            ).join(RemessaAeroportos)\
            .filter(RemessaAeroportos.Ativo == True)\
            .filter(
                Aeroporto.Latitude != None,
                Aeroporto.CodigoIata.in_(ListaIatasAtivos)
            ).all()
        
        MenorDistancia = float('inf')
        AeroportoEscolhido = None
        
        for Aero in TodosAeroportos:
            Dist = Haversine(Lat, Lon, Aero.Latitude, Aero.Longitude)
            
            if Dist < MenorDistancia:
                MenorDistancia = Dist
                AeroportoEscolhido = {
                    'iata': Aero.CodigoIata,
                    'nome': Aero.NomeAeroporto,
                    'lat': Aero.Latitude,
                    'lon': Aero.Longitude,
                    'distancia_km': round(Dist, 1)
                }
        
        if AeroportoEscolhido:
            print(f"📍 Aeroporto Ativo mais próximo: {AeroportoEscolhido['iata']} ({AeroportoEscolhido['distancia_km']}km)")
            
        return AeroportoEscolhido
    finally:
        Sessao.close()