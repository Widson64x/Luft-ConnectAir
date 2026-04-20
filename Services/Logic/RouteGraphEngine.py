import networkx as nx
from datetime import datetime, timedelta, time
from typing import Optional

from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Aeroporto import Aeroporto, RemessaAeroportos
from Services.LogService import LogService
from Services.Logic.RouteConfig import RouteSearchRules
from Utils.Geometria import Haversine


class RouteGraphEngine:
    """
    Engine determinística baseada em grafo.

    Responsável apenas por transformar a malha aérea em sequências válidas de voos.
    Não calcula score, não categoriza e não aplica ML.
    """

    @classmethod
    def GerarRotasCronologicas(
        cls,
        voos_db,
        data_inicio,
        lista_origens: list[str],
        lista_destinos: list[str],
        scores_parceria: dict,
        regras: RouteSearchRules,
    ) -> list[list]:
        grafo = cls._construir_grafo(voos_db, scores_parceria, regras)
        LogService.Info("RouteGraphEngine", f"Grafo: {grafo.number_of_nodes()} nos, {grafo.number_of_edges()} arestas")

        rotas = []
        for origem in lista_origens:
            for destino in lista_destinos:
                if not grafo.has_node(origem):
                    LogService.Warning("RouteGraphEngine", f"Origem {origem} ausente no grafo.")
                    continue
                if not grafo.has_node(destino):
                    LogService.Warning("RouteGraphEngine", f"Destino {destino} ausente no grafo.")
                    continue

                try:
                    caminhos = list(nx.all_simple_paths(
                        grafo,
                        source=origem,
                        target=destino,
                        cutoff=regras.max_trechos,
                    ))
                except Exception as e:
                    LogService.Error("RouteGraphEngine", "Erro no motor de caminhos", e)
                    continue

                LogService.Info("RouteGraphEngine", f"{origem}->{destino}: {len(caminhos)} caminhos teoricos")

                for caminho in caminhos:
                    voos = cls._validar_cronologico(grafo, caminho, data_inicio, regras)
                    if voos:
                        rotas.append(voos)

        return rotas

    @staticmethod
    def CarregarCoordenadas() -> dict:
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
            LogService.Warning("RouteGraphEngine", f"Falha ao carregar coordenadas: {e}")
            return {}
        finally:
            sessao.close()

    @staticmethod
    def CalcularDesvio(voos: list, coords: dict) -> float:
        """
        Razão entre a soma das distâncias de cada trecho e a distância direta origem→destino.
        1.0 = rota sem desvio (caminho ótimo).
        Valores acima indicam retrocesso geográfico.
        """
        if len(voos) < 2:
            return 1.0

        iatas = [voos[0].AeroportoOrigem.upper()] + [v.AeroportoDestino.upper() for v in voos]
        origem, destino = iatas[0], iatas[-1]
        if origem not in coords or destino not in coords:
            return 1.0

        dist_direta = Haversine(coords[origem][0], coords[origem][1], coords[destino][0], coords[destino][1])
        if dist_direta < 1:
            return 1.0

        dist_total = 0.0
        for idx in range(len(iatas) - 1):
            aero_a, aero_b = iatas[idx], iatas[idx + 1]
            if aero_a not in coords or aero_b not in coords:
                return 1.0
            dist_total += Haversine(coords[aero_a][0], coords[aero_a][1], coords[aero_b][0], coords[aero_b][1])

        return dist_total / dist_direta

    @staticmethod
    def _construir_grafo(voos_db, scores_parceria: dict, regras: RouteSearchRules) -> nx.DiGraph:
        grafo = nx.DiGraph()
        for voo in voos_db:
            cia = str(voo.CiaAerea or '').strip().upper()
            if scores_parceria.get(cia, regras.score_parceria_padrao) <= regras.score_parceria_minimo_elegivel:
                continue

            origem = str(voo.AeroportoOrigem or '').strip().upper()
            destino = str(voo.AeroportoDestino or '').strip().upper()
            if not origem or not destino:
                continue

            if grafo.has_edge(origem, destino):
                grafo[origem][destino]['voos'].append(voo)
            else:
                grafo.add_edge(origem, destino, voos=[voo])

        return grafo

    @classmethod
    def _validar_cronologico(cls, grafo, nos: list, data_inicio, regras: RouteSearchRules) -> Optional[list]:
        """
        Para cada caminho teórico, tenta todas as combinações possíveis de voo,
        respeitando a janela mínima e máxima entre conexões.
        """
        inicio = data_inicio if isinstance(data_inicio, datetime) else datetime.combine(data_inicio, time.min)

        origem_0, destino_0 = nos[0], nos[1]
        if not grafo.has_edge(origem_0, destino_0):
            return None

        primeiros_voos = sorted(
            [
                voo for voo in grafo[origem_0][destino_0]['voos']
                if datetime.combine(voo.DataPartida, voo.HorarioSaida) >= inicio
            ],
            key=lambda voo: (voo.DataPartida, voo.HorarioSaida),
        )

        for primeiro_voo in primeiros_voos:
            resultado = cls._construir_cadeia_cronologica(
                grafo,
                nos,
                [primeiro_voo],
                trecho_idx=1,
                regras=regras,
            )
            if resultado is not None:
                return resultado

        return None

    @classmethod
    def _construir_cadeia_cronologica(
        cls,
        grafo,
        nos: list,
        voos_ate_agora: list,
        trecho_idx: int,
        regras: RouteSearchRules,
    ) -> Optional[list]:
        if trecho_idx == len(nos) - 1:
            return voos_ate_agora

        origem = nos[trecho_idx]
        destino = nos[trecho_idx + 1]
        if not grafo.has_edge(origem, destino):
            return None

        opcoes = sorted(grafo[origem][destino]['voos'], key=lambda voo: (voo.DataPartida, voo.HorarioSaida))

        cia_anterior = voos_ate_agora[-1].CiaAerea
        opcoes = [voo for voo in opcoes if voo.CiaAerea == cia_anterior] + [
            voo for voo in opcoes if voo.CiaAerea != cia_anterior
        ]

        chegada_anterior = cls._chegada(voos_ate_agora[-1])
        minimo = timedelta(hours=regras.min_horas_conexao)
        maximo = timedelta(hours=regras.max_horas_conexao)

        for voo in opcoes:
            saida = datetime.combine(voo.DataPartida, voo.HorarioSaida)
            if chegada_anterior + minimo <= saida <= chegada_anterior + maximo:
                resultado = cls._construir_cadeia_cronologica(
                    grafo,
                    nos,
                    voos_ate_agora + [voo],
                    trecho_idx + 1,
                    regras,
                )
                if resultado is not None:
                    return resultado

        return None

    @staticmethod
    def _chegada(voo) -> datetime:
        data_hora_chegada = datetime.combine(voo.DataPartida, voo.HorarioChegada)
        return data_hora_chegada + timedelta(days=1) if voo.HorarioChegada < voo.HorarioSaida else data_hora_chegada