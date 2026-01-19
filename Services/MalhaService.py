import os
import pandas as pd
from datetime import datetime, timedelta, date, time
from sqlalchemy import desc, func
from Conexoes import ObterSessaoPostgres
from Models.POSTGRES.Aeroporto import Aeroporto
from Models.POSTGRES.MalhaAerea import RemessaMalha, VooMalha
from Utils.Formatadores import PadronizarData
import networkx as nx

# Pasta temporária
DIR_TEMP = 'Data/Temp_Malhas'
if not os.path.exists(DIR_TEMP):
    os.makedirs(DIR_TEMP)

# --- FUNÇÕES DE CONTROLE DE REMESSAS (Mantidas iguais) ---
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
                # Tratamento de Horário Seguro
                raw_saida = str(Linha.get('HORÁRIO DE SAIDA', ''))
                raw_chegada = str(Linha.get('HORÁRIO DE CHEGADA', ''))
                
                if len(raw_saida) == 5: raw_saida += ":00"
                if len(raw_chegada) == 5: raw_chegada += ":00"

                H_Saida = pd.to_datetime(raw_saida, format='%H:%M:%S', errors='coerce').time() if raw_saida != 'nan' else time(0,0)
                H_Chegada = pd.to_datetime(raw_chegada, format='%H:%M:%S', errors='coerce').time() if raw_chegada != 'nan' else time(0,0)
            except:
                H_Saida = time(0,0)
                H_Chegada = time(0,0)

            Voo = VooMalha(
                IdRemessa=NovaRemessa.Id,
                CiaAerea=str(Linha.get('CIA', '')),
                NumeroVoo=str(Linha.get('Nº VOO', '')),
                DataPartida=Linha['DATA_PADRAO'],
                AeroportoOrigem=str(Linha.get('ORIGEM', '')),
                HorarioSaida=H_Saida,
                HorarioChegada=H_Chegada,
                AeroportoDestino=str(Linha.get('DESTINO', ''))
            )
            ListaVoos.append(Voo)

        Sessao.bulk_save_objects(ListaVoos)
        Sessao.commit()
        
        if os.path.exists(CaminhoArquivo):
            os.remove(CaminhoArquivo)
            
        return True, f"Malha processada com sucesso!"

    except Exception as e:
        Sessao.rollback()
        return False, f"Erro ao gravar: {e}"
    finally:
        Sessao.close()

# --- BUSCA INTELIGENTE E ROTEAMENTO (CORRIGIDA) ---

def BuscarRotasInteligentes(DataInicio, DataFim, OrigemIata=None, DestinoIata=None):
    Sessao = ObterSessaoPostgres()
    try:
        # 1. Filtros para o Banco
        FiltroDataInicio = DataInicio.date() if isinstance(DataInicio, datetime) else DataInicio
        FiltroDataFim = DataFim.date() if isinstance(DataFim, datetime) else DataFim

        OrigemIata = OrigemIata.upper().strip() if OrigemIata else None
        DestinoIata = DestinoIata.upper().strip() if DestinoIata else None
        
        # CORREÇÃO PRINCIPAL: JOIN COM REMESSA E FILTRO ATIVO=TRUE
        VoosDB = Sessao.query(VooMalha)\
            .join(RemessaMalha)\
            .filter(
                RemessaMalha.Ativo == True,  # <--- SÓ O QUE É ATIVO
                VooMalha.DataPartida >= FiltroDataInicio, 
                VooMalha.DataPartida <= FiltroDataFim + timedelta(days=1)
            ).all()
        
        DadosAeroportos = {}
        G = nx.DiGraph()
        ListaGeral = [] 

        # 3. Monta o Grafo
        for Voo in VoosDB:
            if not (OrigemIata and DestinoIata):
                # Se for busca genérica (sem origem/destino), adiciona na lista simples
                if (not OrigemIata or Voo.AeroportoOrigem == OrigemIata) and \
                   (not DestinoIata or Voo.AeroportoDestino == DestinoIata):
                       ListaGeral.append(Voo)
            
            # Adiciona ao Grafo
            if G.has_edge(Voo.AeroportoOrigem, Voo.AeroportoDestino):
                G[Voo.AeroportoOrigem][Voo.AeroportoDestino]['voos'].append(Voo)
            else:
                G.add_edge(Voo.AeroportoOrigem, Voo.AeroportoDestino, voos=[Voo])

        # Se não tem origem/destino, retorna lista simples
        if not (OrigemIata and DestinoIata):
            CompletarCacheDestinos(Sessao, ListaGeral, DadosAeroportos)
            return FormatarListaRotas(ListaGeral[:2000], DadosAeroportos, 'Geral')

        # --- ALGORITMO DE MENOR CAMINHO ---
        if not G.has_node(OrigemIata) or not G.has_node(DestinoIata):
            return []
            
        try:
            # Busca rotas possíveis (Topologia apenas)
            Caminhos = list(nx.all_simple_paths(G, source=OrigemIata, target=DestinoIata, cutoff=3))
            
            if not Caminhos: return []
            
            RotasValidas = []
            for CaminhoNos in Caminhos:
                Rota = ValidarCaminhoCronologico(G, CaminhoNos, DataInicio)
                if Rota:
                    RotasValidas.append(Rota)
            
            if not RotasValidas: return []

            # Ordena por: 1) Menor Duração, 2) Menos Escalas
            RotasValidas.sort(key=lambda r: (CalcularDuracaoRota(r), len(r)))

            MelhorRota = RotasValidas[0]
            
            CompletarCacheDestinos(Sessao, MelhorRota, DadosAeroportos)
            Tipo = 'Direto' if len(MelhorRota) == 1 else 'Conexao'
            return FormatarListaRotas(MelhorRota, DadosAeroportos, Tipo)
                    
        except Exception as e:
            print(f"Erro grafo: {e}")
            return []

    finally:
        Sessao.close()

def ValidarCaminhoCronologico(Grafo, Nos, DataMinimaAbsoluta):
    """
    Verifica se existe conexão válida respeitando horários.
    DataMinimaAbsoluta: Momento exato que a carga está liberada (Data + Hora).
    """
    VoosEscolhidos = []
    
    if isinstance(DataMinimaAbsoluta, date) and not isinstance(DataMinimaAbsoluta, datetime):
        DataReferencia = datetime.combine(DataMinimaAbsoluta, time.min)
    else:
        DataReferencia = DataMinimaAbsoluta

    for i in range(len(Nos) - 1):
        Orig = Nos[i]
        Dest = Nos[i+1]
        
        # Pega voos do trecho
        if Dest not in Grafo[Orig]: return None
        Candidatos = Grafo[Orig][Dest]['voos']
        
        # Ordena cronologicamente
        Candidatos.sort(key=lambda v: (v.DataPartida, v.HorarioSaida))
        
        VooEleito = None
        for Voo in Candidatos:
            SaidaVoo = datetime.combine(Voo.DataPartida, Voo.HorarioSaida)
            
            if i == 0:
                # PRIMEIRO TRECHO
                if SaidaVoo > DataReferencia: 
                    VooEleito = Voo
                    break
            else:
                # CONEXÃO
                VooAnt = VoosEscolhidos[-1] # Último voo escolhido até agora
                ChegadaAnt = datetime.combine(VooAnt.DataPartida, VooAnt.HorarioChegada) # Chegada do voo anterior
                if VooAnt.HorarioChegada < VooAnt.HorarioSaida: # Virou a noite
                    ChegadaAnt += timedelta(days=1)
                
                # Regra de conexão: Mínimo 1h, Máximo 24h
                if SaidaVoo >= ChegadaAnt + timedelta(hours=1):
                    if SaidaVoo <= ChegadaAnt + timedelta(hours=24):
                        VooEleito = Voo
                        break
        
        if VooEleito:
            VoosEscolhidos.append(VooEleito)
            DataReferencia = datetime.combine(VooEleito.DataPartida, VooEleito.HorarioChegada)
        else:
            return None 
            
    return VoosEscolhidos

def CalcularDuracaoRota(ListaVoos):
    if not ListaVoos: return 99999999
    
    def to_dt(d, t): return datetime.combine(d, t)

    Primeiro = ListaVoos[0]
    Ultimo = ListaVoos[-1]
    
    Inicio = to_dt(Primeiro.DataPartida, Primeiro.HorarioSaida)
    Fim = to_dt(Ultimo.DataPartida, Ultimo.HorarioChegada)
    
    if Ultimo.HorarioChegada < Ultimo.HorarioSaida:
        Fim += timedelta(days=1)
        
    return (Fim - Inicio).total_seconds()

def CompletarCacheDestinos(Sessao, ListaVoos, Cache):
    Iatas = set()
    for v in ListaVoos:
        Iatas.add(v.AeroportoOrigem)
        Iatas.add(v.AeroportoDestino)
    
    Faltantes = [i for i in Iatas if i not in Cache]
    if Faltantes:
        Aeroportos = Sessao.query(Aeroporto).filter(Aeroporto.CodigoIata.in_(Faltantes)).all()
        for a in Aeroportos:
            Cache[a.CodigoIata] = {'lat': a.Latitude, 'lon': a.Longitude, 'nome': a.NomeAeroporto}

def FormatarListaRotas(ListaVoos, Cache, Tipo):
    Resultado = []
    for Voo in ListaVoos:
        Orig = Cache.get(Voo.AeroportoOrigem, {})
        Dest = Cache.get(Voo.AeroportoDestino, {})
        
        Resultado.append({
            'tipo_resultado': Tipo,
            'cia': Voo.CiaAerea,
            'voo': Voo.NumeroVoo,
            'data': Voo.DataPartida.strftime('%d/%m/%Y'),
            'horario_saida': Voo.HorarioSaida.strftime('%H:%M'),
            'horario_chegada': Voo.HorarioChegada.strftime('%H:%M'),
            'origem': {'iata': Voo.AeroportoOrigem, 'nome': Orig.get('nome'), 'lat': Orig.get('lat'), 'lon': Orig.get('lon')},
            'destino': {'iata': Voo.AeroportoDestino, 'nome': Dest.get('nome'), 'lat': Dest.get('lat'), 'lon': Dest.get('lon')}
        })
    return Resultado

def ObterTotalVoosData(DataRef):
    """
    Conta o total de voos ativos para uma data específica.
    """
    Sessao = ObterSessaoPostgres()
    try:
        # Garante que é apenas a data (sem hora)
        DataFiltro = DataRef.date() if isinstance(DataRef, datetime) else DataRef
        
        Total = Sessao.query(func.count(VooMalha.Id))\
            .join(RemessaMalha)\
            .filter(
                RemessaMalha.Ativo == True,
                VooMalha.DataPartida == DataFiltro
            ).scalar()
            
        return Total or 0
    except Exception as e:
        print(f"Erro ao contar voos: {e}")
        return 0
    finally:
        Sessao.close()