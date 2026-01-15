import os
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import desc
from sqlalchemy.orm import aliased
from Conexoes import ObterSessaoPostgres
from Models.POSTGRES.Aeroporto import Aeroporto
from Models.POSTGRES.MalhaAerea import RemessaMalha, VooMalha
from Utils.Formatadores import PadronizarData
import networkx as nx

# Pasta temporária
DIR_TEMP = 'Data/Temp_Malhas'
if not os.path.exists(DIR_TEMP):
    os.makedirs(DIR_TEMP)

# --- FUNÇÕES DE CONTROLE DE REMESSAS (Mantidas) ---
def ListarRemessas():
    Sessao = ObterSessaoPostgres()
    try:
        return Sessao.query(RemessaMalha).order_by(desc(RemessaMalha.DataUpload)).all()
    finally:
        Sessao.close()

def ExcluirRemessa(IdRemessa):
    Sessao = ObterSessaoPostgres()
    try:
        RemessaAlvo = Sessao.query(RemessaMalha).get(IdRemessa)
        if RemessaAlvo:
            Sessao.delete(RemessaAlvo)
            Sessao.commit()
            return True, "Remessa excluída com sucesso."
        return False, "Remessa não encontrada."
    except Exception as e:
        Sessao.rollback()
        return False, f"Erro ao excluir: {e}"
    finally:
        Sessao.close()

def AnalisarArquivo(FileStorage):
    try:
        CaminhoTemp = os.path.join(DIR_TEMP, FileStorage.filename)
        FileStorage.save(CaminhoTemp)
        
        Df = pd.read_excel(CaminhoTemp, engine='openpyxl')
        Df.columns = [c.strip().upper() for c in Df.columns]
        
        ColunaData = next((col for col in ['DIA', 'DATA'] if col in Df.columns), None)
        if not ColunaData:
            return False, "Coluna de DATA não encontrada."

        PrimeiraData = PadronizarData(Df[ColunaData].iloc[0])
        if not PrimeiraData:
            return False, "Não foi possível ler a data do arquivo."
            
        DataRef = PrimeiraData.replace(day=1) 
        
        Sessao = ObterSessaoPostgres()
        ExisteConflito = False
        try:
            Anterior = Sessao.query(RemessaMalha).filter_by(MesReferencia=DataRef, Ativo=True).first()
            if Anterior:
                ExisteConflito = True
        finally:
            Sessao.close()
            
        return True, {
            'caminho_temp': CaminhoTemp,
            'mes_ref': DataRef,
            'nome_arquivo': FileStorage.filename,
            'conflito': ExisteConflito
        }
    except Exception as e:
        return False, f"Erro ao analisar arquivo: {e}"

def ProcessarMalhaFinal(CaminhoArquivo, DataRef, NomeOriginal, Usuario, TipoAcao):
    Sessao = ObterSessaoPostgres()
    try:
        Df = pd.read_excel(CaminhoArquivo, engine='openpyxl')
        Df.columns = [c.strip().upper() for c in Df.columns]
        ColunaData = next((col for col in ['DIA', 'DATA'] if col in Df.columns), None)
        
        Df['DATA_PADRAO'] = Df[ColunaData].apply(PadronizarData)
        Df = Df.dropna(subset=['DATA_PADRAO'])

        RemessaAnterior = Sessao.query(RemessaMalha).filter_by(MesReferencia=DataRef, Ativo=True).first()
        if RemessaAnterior:
            RemessaAnterior.Ativo = False

        NovaRemessa = RemessaMalha(
            MesReferencia=DataRef,
            NomeArquivoOriginal=NomeOriginal,
            UsuarioResponsavel=Usuario,
            TipoAcao=TipoAcao,
            Ativo=True
        )
        Sessao.add(NovaRemessa)
        Sessao.flush()

        ListaVoos = []
        for _, Linha in Df.iterrows():
            try:
                H_Saida = pd.to_datetime(str(Linha['HORÁRIO DE SAIDA']), format='%H:%M:%S', errors='coerce').time() if str(Linha['HORÁRIO DE SAIDA']) != 'nan' else datetime.min.time()
                H_Chegada = pd.to_datetime(str(Linha['HORÁRIO DE CHEGADA']), format='%H:%M:%S', errors='coerce').time() if str(Linha['HORÁRIO DE CHEGADA']) != 'nan' else datetime.min.time()
            except:
                H_Saida = datetime.min.time()
                H_Chegada = datetime.min.time()

            Voo = VooMalha(
                IdRemessa=NovaRemessa.Id,
                CiaAerea=str(Linha['CIA']),
                NumeroVoo=str(Linha['Nº VOO']),
                DataPartida=Linha['DATA_PADRAO'],
                AeroportoOrigem=str(Linha['ORIGEM']),
                HorarioSaida=H_Saida,
                HorarioChegada=H_Chegada,
                AeroportoDestino=str(Linha['DESTINO'])
            )
            ListaVoos.append(Voo)

        Sessao.bulk_save_objects(ListaVoos)
        Sessao.commit()
        
        if os.path.exists(CaminhoArquivo):
            os.remove(CaminhoArquivo)
            
        return True, f"Malha de {DataRef.strftime('%m/%Y')} processada com sucesso! ({TipoAcao})"

    except Exception as e:
        Sessao.rollback()
        return False, f"Erro ao gravar: {e}"
    finally:
        Sessao.close()

# --- ALGORITMO DE ROTAS INTELIGENTES (REFATORADO) ---

def BuscarRotasInteligentes(DataInicio, DataFim, OrigemIata=None, DestinoIata=None):
    Sessao = ObterSessaoPostgres()
    try:
        OrigemIata = OrigemIata.upper().strip() if OrigemIata else None
        DestinoIata = DestinoIata.upper().strip() if DestinoIata else None
        
        # 1. Carregar Voos do Banco
        VoosDB = Sessao.query(
            VooMalha,
            Aeroporto.Latitude, Aeroporto.Longitude, Aeroporto.NomeAeroporto
        ).join(Aeroporto, VooMalha.AeroportoOrigem == Aeroporto.CodigoIata)\
         .filter(VooMalha.DataPartida >= DataInicio, VooMalha.DataPartida <= DataFim + timedelta(days=3))\
         .all()
        
        DadosAeroportos = {}
        G = nx.DiGraph()
        ListaGeral = []

        for Voo, Lat, Lon, Nome in VoosDB:
            if Voo.AeroportoOrigem not in DadosAeroportos:
                DadosAeroportos[Voo.AeroportoOrigem] = {'lat': Lat, 'lon': Lon, 'nome': Nome}
            
            if G.has_edge(Voo.AeroportoOrigem, Voo.AeroportoDestino):
                G[Voo.AeroportoOrigem][Voo.AeroportoDestino]['voos'].append(Voo)
            else:
                G.add_edge(Voo.AeroportoOrigem, Voo.AeroportoDestino, voos=[Voo])

            # Lógica Visão Geral
            if not (OrigemIata and DestinoIata):
                if (not OrigemIata or Voo.AeroportoOrigem == OrigemIata) and \
                   (not DestinoIata or Voo.AeroportoDestino == DestinoIata):
                       if DataInicio <= Voo.DataPartida <= DataFim:
                           ListaGeral.append(Voo)

        if not (OrigemIata and DestinoIata):
            CompletarCacheDestinos(Sessao, ListaGeral, DadosAeroportos)
            return FormatarListaRotas(ListaGeral[:5000], DadosAeroportos, 'Geral')

        # --- ESTRATÉGIA DE MENOR CAMINHO EFICIENTE ---
        if not G.has_node(OrigemIata) or not G.has_node(DestinoIata):
            return []
            
        try:
            # Busca todos os caminhos possíveis (Topologia)
            CaminhosPossiveis = list(nx.all_simple_paths(G, source=OrigemIata, target=DestinoIata, cutoff=3))
            
            if not CaminhosPossiveis:
                return []
            
            RotasCandidatas = []

            # Itera sobre TODOS os caminhos para validar horários
            for CaminhoNos in CaminhosPossiveis:
                RotaValida = ValidarCaminhoCronologico(G, CaminhoNos, DataInicio)
                if RotaValida:
                    RotasCandidatas.append(RotaValida)
            
            if not RotasCandidatas:
                return []

            # --- O PULO DO GATO: ORDENAÇÃO INTELIGENTE ---
            # Ordenamos as rotas encontradas baseadas em:
            # 1. Duração Total (Chegada no Destino - Saída da Origem) -> Mais rápido ganha
            # 2. Número de Escalas (Menos escalas ganha como critério de desempate)
            
            RotasCandidatas.sort(key=lambda r: (CalcularDuracaoRota(r), len(r)))

            # Pega a campeã
            MelhorRota = RotasCandidatas[0]
            
            CompletarCacheDestinos(Sessao, MelhorRota, DadosAeroportos)
            Tipo = 'Direto' if len(MelhorRota) == 1 else 'Conexao'
            return FormatarListaRotas(MelhorRota, DadosAeroportos, Tipo)
                    
        except nx.NetworkXNoPath:
            return []
        except Exception as e:
            print(f"Erro no processamento de rotas: {e}")
            return []

    finally:
        Sessao.close()

def CalcularDuracaoRota(ListaVoos):
    """Calcula a duração total em segundos para ordenação"""
    if not ListaVoos: return float('inf')
    
    # Monta Datetime Saída Origem
    Primeiro = ListaVoos[0]
    DtSaida = datetime.combine(Primeiro.DataPartida, Primeiro.HorarioSaida)
    
    # Monta Datetime Chegada Destino Final
    Ultimo = ListaVoos[-1]
    DtChegada = datetime.combine(Ultimo.DataPartida, Ultimo.HorarioChegada)
    
    # CORREÇÃO: Se o horário de chegada for menor que o de saída, virou o dia
    if Ultimo.HorarioChegada < Ultimo.HorarioSaida:
        DtChegada += timedelta(days=1)
    
    return (DtChegada - DtSaida).total_seconds()

def ValidarCaminhoCronologico(Grafo, Nos, DataMinima):
    """
    Tenta montar um itinerário válido para uma sequência de aeroportos.
    Retorna a lista de voos se conseguir conectar tudo.
    """
    VoosEscolhidos = []
    
    # DataReferencia controla a data mínima para o próximo voo
    DataReferencia = DataMinima
    
    for i in range(len(Nos) - 1):
        Origem = Nos[i]
        Destino = Nos[i+1]
        
        if Destino not in Grafo[Origem]: return None
        Candidatos = Grafo[Origem][Destino]['voos']
        
        # Ordena cronologicamente
        Candidatos.sort(key=lambda v: (v.DataPartida, v.HorarioSaida))
        
        VooEleito = None
        for Voo in Candidatos:
            # 1. Primeiro Voo
            if i == 0:
                if Voo.DataPartida >= DataReferencia:
                    VooEleito = Voo
                    break
            
            # 2. Conexões
            else:
                # Dados do voo anterior (já escolhido)
                VooAnterior = VoosEscolhidos[-1]
                ChegadaAnterior = datetime.combine(VooAnterior.DataPartida, VooAnterior.HorarioChegada)
                
                # CORREÇÃO: Se chegou no dia seguinte (ex: saiu 23h, chegou 01h)
                if VooAnterior.HorarioChegada < VooAnterior.HorarioSaida:
                    ChegadaAnterior += timedelta(days=1)
                
                # Dados do voo candidato (Atual)
                SaidaAtual = datetime.combine(Voo.DataPartida, Voo.HorarioSaida)
                
                DifHoras = (SaidaAtual - ChegadaAnterior).total_seconds() / 3600
                
                # Regra: Conexão entre 1h e 24h
                if 1 <= DifHoras <= 24:
                    VooEleito = Voo
                    break
        
        if VooEleito:
            VoosEscolhidos.append(VooEleito)
            # Atualiza a DataReferencia para a data desse voo, para otimizar o loop seguinte
            DataReferencia = VooEleito.DataPartida
        else:
            return None # Caminho quebrado
            
    return VoosEscolhidos

def CompletarCacheDestinos(Sessao, ListaVoos, Cache):
    IatasFaltantes = set()
    for Voo in ListaVoos:
        if Voo.AeroportoDestino not in Cache:
            IatasFaltantes.add(Voo.AeroportoDestino)
    if IatasFaltantes:
        Infos = Sessao.query(Aeroporto).filter(Aeroporto.CodigoIata.in_(IatasFaltantes)).all()
        for Info in Infos:
            Cache[Info.CodigoIata] = {'lat': Info.Latitude, 'lon': Info.Longitude, 'nome': Info.NomeAeroporto}

def FormatarListaRotas(ListaVoos, CacheAeroportos, Tipo):
    Rotas = []
    for Voo in ListaVoos:
        Orig = CacheAeroportos.get(Voo.AeroportoOrigem, {})
        Dest = CacheAeroportos.get(Voo.AeroportoDestino, {})
        
        Sai = Voo.HorarioSaida.strftime('%H:%M') if Voo.HorarioSaida else '--:--'
        Che = Voo.HorarioChegada.strftime('%H:%M') if Voo.HorarioChegada else '--:--'

        Rotas.append({
            'tipo_resultado': Tipo,
            'voo': Voo.NumeroVoo,
            'cia': Voo.CiaAerea.upper().strip(),
            'data': Voo.DataPartida.strftime('%d/%m/%Y'),
            'horario_saida': Sai,
            'horario_chegada': Che,
            'origem': {
                'iata': Voo.AeroportoOrigem, 
                'nome': Orig.get('nome', Voo.AeroportoOrigem), 
                'lat': Orig.get('lat'), 'lon': Orig.get('lon')
            },
            'destino': {
                'iata': Voo.AeroportoDestino, 
                'nome': Dest.get('nome', Voo.AeroportoDestino), 
                'lat': Dest.get('lat'), 'lon': Dest.get('lon')
            }
        })
    return Rotas