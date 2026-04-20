from sqlalchemy import distinct, desc
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Cidade import Cidade, RemessaCidade
from Models.SQL_SERVER.Aeroporto import Aeroporto, RemessaAeroportos
from Models.SQL_SERVER.MalhaAerea import VooMalha, RemessaMalha
# Importação da Model de Ranking (Planejamento)
from Models.SQL_SERVER.Planejamento import RankingAeroportos 
from Utils.Geometria import Haversine
from Utils.Texto import NormalizarTexto
from Services.LogService import LogService

# Configuração de Inteligência
# Quanto maior este número, mais o sistema ignora a distância para priorizar o Ranking.
# Ex: 3.5 significa que 1 ponto de ranking equivale a percorrer 3.5km a mais para chegar lá.
FATOR_RANKING_KM = 3.5 

def BuscarCoordenadasCidade(NomeCidade, Uf):
    Sessao = ObterSessaoSqlServer()
    try:
        if not NomeCidade or not Uf: return None
        
        NomeBusca = NormalizarTexto(NomeCidade)
        UfBusca = NormalizarTexto(Uf)
        
        CidadesDoEstado = Sessao.query(Cidade)\
            .join(RemessaCidade)\
            .filter(RemessaCidade.Ativo == True) \
            .filter(Cidade.Uf == UfBusca).all()
        
        for c in CidadesDoEstado:
            NomeBanco = NormalizarTexto(c.NomeCidade)
            if NomeBanco == NomeBusca or NomeBusca in NomeBanco:
                return {
                    'lat': float(c.Latitude) if c.Latitude else 0.0, 
                    'lon': float(c.Longitude) if c.Longitude else 0.0, 
                    'nome': c.NomeCidade,
                    'uf': c.Uf
                }
        return None
    except Exception as e:
        LogService.Error("GeoService", f"Erro ao buscar cidade {NomeCidade}-{Uf}", e)
        return None
    finally:
        Sessao.close()

def BuscarAeroportoEstrategico(Latitude, Longitude, UfAlvo):
    """
    Busca o melhor aeroporto baseando-se na Estratégia da Empresa (Ranking) 
    restrito à UF do cliente.
    """
    Sessao = ObterSessaoSqlServer()
    try:
        # 1. Normalização da UF para garantir o filtro
        UfFiltro = UfAlvo.upper().strip()

        # 2. Busca aeroportos que estão no Ranking E que estão ativos na RemessaAeroportos
        CandidatosEstrategicos = Sessao.query(
            RankingAeroportos.IndiceImportancia,
            RankingAeroportos.IndiceUso,
            Aeroporto.CodigoIata,
            Aeroporto.NomeAeroporto,
            Aeroporto.Latitude,
            Aeroporto.Longitude
        ).join(Aeroporto, RankingAeroportos.IdAeroporto == Aeroporto.Id)\
         .join(RemessaAeroportos, Aeroporto.IdRemessa == RemessaAeroportos.Id)\
         .filter(RankingAeroportos.Uf == UfFiltro)\
         .filter(RemessaAeroportos.Ativo == True)\
         .all()

        MelhorOpcao = None
        MenorScore = float('inf') # Quanto menor o score, melhor (Score = Custo/Esforço)

        # Lista para log de decisão (Debug)
        LogDecisao = []

        if CandidatosEstrategicos:
            # CENÁRIO A: Temos aeroportos rankeados nesta UF. Vamos competir Distância vs Ranking.
            for Cand in CandidatosEstrategicos:
                DistanciaReal = Haversine(Latitude, Longitude, float(Cand.Latitude), float(Cand.Longitude))
                
                # Prioridade efetiva: Manual se definida (>0), senão usa a calculada por Uso
                IndiceEfetivo = Cand.IndiceImportancia if Cand.IndiceImportancia > 0 else Cand.IndiceUso
                BonusRanking = IndiceEfetivo * FATOR_RANKING_KM
                ScoreCalculado = DistanciaReal - BonusRanking

                LogDecisao.append(f"{Cand.CodigoIata}: Dist={DistanciaReal:.1f}km, Manual={Cand.IndiceImportancia}, Uso={Cand.IndiceUso}, Efetivo={IndiceEfetivo}, Score={ScoreCalculado:.1f}")

                if ScoreCalculado < MenorScore:
                    MenorScore = ScoreCalculado
                    MelhorOpcao = {
                        'iata': Cand.CodigoIata,
                        'nome': Cand.NomeAeroporto,
                        'lat': float(Cand.Latitude),
                        'lon': float(Cand.Longitude),
                        'distancia_km': round(DistanciaReal, 1),
                        'ranking': IndiceEfetivo,
                        'ranking_manual': Cand.IndiceImportancia,
                        'ranking_uso': Cand.IndiceUso,
                        'metodo': 'Estrategico (Ranking)'
                    }
            
            LogService.Debug("GeoService", f"Analise Estrategica UF {UfFiltro}: { ' | '.join(LogDecisao) }")

        else:
            # CENÁRIO B: A UF não tem aeroportos na tabela de Ranking (ou nenhum ativo).
            # Fallback: Busca o mais próximo geograficamente DENTRO DA UF, sem ponderar ranking.
            LogService.Info("GeoService", f"Nenhum aeroporto rankeado em {UfFiltro}. Usando proximidade simples.")
            
            AeroportosDaUf = Sessao.query(Aeroporto)\
                .join(RemessaAeroportos, Aeroporto.IdRemessa == RemessaAeroportos.Id)\
                .filter(RemessaAeroportos.Ativo == True)\
                .filter(Aeroporto.Uf == UfFiltro)\
                .all()
            
            MenorDistancia = float('inf')
            
            for Aero in AeroportosDaUf:
                Dist = Haversine(Latitude, Longitude, float(Aero.Latitude), float(Aero.Longitude))
                if Dist < MenorDistancia:
                    MenorDistancia = Dist
                    MelhorOpcao = {
                        'iata': Aero.CodigoIata,
                        'nome': Aero.NomeAeroporto,
                        'lat': float(Aero.Latitude),
                        'lon': float(Aero.Longitude),
                        'distancia_km': round(Dist, 1),
                        'ranking': 0,
                        'metodo': 'Proximidade (Fallback UF)'
                    }

        return MelhorOpcao

    except Exception as e:
        LogService.Error("GeoService", f"Erro ao buscar aeroporto estrategico em {UfAlvo}", e)
        return None
    finally:
        Sessao.close()

# Manter métodos auxiliares legados caso outras partes do sistema ainda usem, 
# mas o Planejamento deve chamar o BuscarAeroportoEstrategico acima.
def BuscarTopAeroportos(lat_cidade, lon_cidade, limite=2):
    Sessao = ObterSessaoSqlServer()
    try:
        aeroportos = Sessao.query(Aeroporto)\
            .join(RemessaAeroportos, Aeroporto.IdRemessa == RemessaAeroportos.Id)\
            .filter(
                RemessaAeroportos.Ativo == True,
                Aeroporto.Latitude != None,
                Aeroporto.Longitude != None
            ).all()
        
        lista_distancias = []
        for aero in aeroportos:
            dist = Haversine(lat_cidade, lon_cidade, float(aero.Latitude), float(aero.Longitude))
            lista_distancias.append({
                'iata': aero.CodigoIata,
                'nome': aero.NomeAeroporto,
                'lat': float(aero.Latitude),
                'lon': float(aero.Longitude),
                'distancia': dist
            })

        lista_distancias.sort(key=lambda x: x['distancia'])
        return lista_distancias[:limite]

    except Exception as e:
        LogService.Error("GeoService", "Erro ao buscar Top Aeroportos", e)
        return []
    finally:
        Sessao.close()