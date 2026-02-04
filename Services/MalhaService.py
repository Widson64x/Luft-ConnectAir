import os
import pandas as pd
from datetime import datetime, timedelta, date, time
from sqlalchemy import desc, func
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Aeroporto import Aeroporto
from Models.SQL_SERVER.MalhaAerea import RemessaMalha, VooMalha
from Utils.Formatadores import PadronizarData
from Configuracoes import ConfiguracaoBase
from Services.LogService import LogService  # <--- Import Adicionado
import networkx as nx

DIR_TEMP = ConfiguracaoBase.DIR_TEMP

class MalhaService:
    """
    Service Layer responsável pela gestão da Malha Aérea.
    Contém lógica de importação de arquivos, persistência de dados e algoritmos de roteamento (Graph Theory).
    """

    DIR_TEMP = os.path.join(os.getcwd(), 'DATA', 'Temp_Malhas')
    
    @staticmethod
    def _GarantirDiretorio():
        """Garante que a pasta temporária exista antes de processar arquivos."""
        if not os.path.exists(MalhaService.DIR_TEMP):
            os.makedirs(MalhaService.DIR_TEMP)

    # --- MÉTODOS DE GESTÃO (CRUD) ---

    @staticmethod
    def ListarRemessas():
        """Lista histórico de importações de malha."""
        Sessao = ObterSessaoSqlServer()
        try:
            return Sessao.query(RemessaMalha).order_by(desc(RemessaMalha.DataUpload)).all()
        finally:
            Sessao.close()

    @staticmethod
    def ExcluirRemessa(id_remessa):
        """Realiza a exclusão lógica ou física de uma remessa e seus voos associados."""
        Sessao = ObterSessaoSqlServer()
        try:
            RemessaAlvo = Sessao.query(RemessaMalha).get(id_remessa)
            if RemessaAlvo:
                Sessao.delete(RemessaAlvo)
                Sessao.commit()
                LogService.Info("MalhaService", f"Remessa ID {id_remessa} excluída com sucesso.")
                return True, "Remessa excluída com sucesso."
            
            LogService.Warning("MalhaService", f"Tentativa de excluir remessa inexistente ID {id_remessa}.")
            return False, "Remessa não encontrada."
        except Exception as e:
            Sessao.rollback()
            LogService.Error("MalhaService", f"Erro técnico ao excluir remessa ID {id_remessa}", e)
            return False, f"Erro técnico ao excluir: {e}"
        finally:
            Sessao.close()

    @staticmethod
    def AnalisarArquivo(file_storage):
        """
        Analisa a integridade do arquivo enviado e verifica conflitos de vigência.
        Retorna metadados para confirmação do usuário.
        """
        try:
            LogService.Info("MalhaService", f"Iniciando análise do arquivo: {file_storage.filename}")
            MalhaService._GarantirDiretorio()
            CaminhoTemp = os.path.join(MalhaService.DIR_TEMP, file_storage.filename)
            file_storage.save(CaminhoTemp)
            
            Df = pd.read_excel(CaminhoTemp, engine='openpyxl')
            Df.columns = [c.strip().upper() for c in Df.columns]
            
            ColunaData = next((col for col in ['DIA', 'DATA'] if col in Df.columns), None)
            if not ColunaData:
                LogService.Warning("MalhaService", "Arquivo rejeitado: Coluna de DATA não encontrada.")
                return False, "Coluna de DATA não encontrada no arquivo."

            PrimeiraData = PadronizarData(Df[ColunaData].iloc[0])
            if not PrimeiraData:
                LogService.Warning("MalhaService", "Arquivo rejeitado: Falha ao analisar formato de data.")
                return False, "Falha ao analisar formato de data."
            
            # Define o primeiro dia do mês como referência
            DataRef = PrimeiraData.replace(day=1) 
            
            Sessao = ObterSessaoSqlServer()
            ExisteConflito = False
            try:
                Anterior = Sessao.query(RemessaMalha).filter_by(MesReferencia=DataRef, Ativo=True).first()
                if Anterior:
                    ExisteConflito = True
                    LogService.Info("MalhaService", f"Conflito detectado para mês referência: {DataRef}")
            finally:
                Sessao.close()
                
            return True, {
                'caminho_temp': CaminhoTemp,
                'mes_ref': DataRef,
                'nome_arquivo': file_storage.filename,
                'conflito': ExisteConflito
            }
        except Exception as e:
            LogService.Error("MalhaService", "Exceção durante análise do arquivo", e)
            return False, f"Exceção durante análise do arquivo: {e}"

    @staticmethod
    def ProcessarMalhaFinal(caminho_arquivo, data_ref, nome_original, usuario, tipo_acao):
        """
        Processa o arquivo validado e persiste os voos no banco de dados.
        Realiza a substituição de malha anterior caso necessário.
        """
        LogService.Info("MalhaService", f"Iniciando processamento final ({tipo_acao}) para {data_ref}")
        Sessao = ObterSessaoSqlServer()
        try:
            Df = pd.read_excel(caminho_arquivo, engine='openpyxl')
            Df.columns = [c.strip().upper() for c in Df.columns]
            ColunaData = next((col for col in ['DIA', 'DATA'] if col in Df.columns), None)
            
            Df['DATA_PADRAO'] = Df[ColunaData].apply(PadronizarData)
            Df = Df.dropna(subset=['DATA_PADRAO'])

            # Desativa remessa anterior
            RemessaAnterior = Sessao.query(RemessaMalha).filter_by(MesReferencia=data_ref, Ativo=True).first()
            if RemessaAnterior:
                RemessaAnterior.Ativo = False

            NovaRemessa = RemessaMalha(
                MesReferencia=data_ref,
                NomeArquivoOriginal=nome_original,
                UsuarioResponsavel=usuario,
                TipoAcao=tipo_acao,
                Ativo=True
            )
            Sessao.add(NovaRemessa)
            Sessao.flush()

            ListaVoos = []
            for _, Linha in Df.iterrows():
                try:
                    # Tratamento de Horário
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
            
            LogService.Info("MalhaService", f"Malha processada com sucesso. {len(ListaVoos)} voos importados.")
            
            if os.path.exists(caminho_arquivo):
                os.remove(caminho_arquivo)
                
            return True, "Malha processada e persistida com sucesso."

        except Exception as e:
            Sessao.rollback()
            LogService.Error("MalhaService", "Erro de persistência na Malha", e)
            return False, f"Erro de persistência: {e}"
        finally:
            Sessao.close()

    @staticmethod
    def ObterTotalVoosData(data_ref):
        """Retorna count de voos ativos para uma data específica."""
        Sessao = ObterSessaoSqlServer()
        try:
            DataFiltro = data_ref.date() if isinstance(data_ref, datetime) else data_ref
            
            Total = Sessao.query(func.count(VooMalha.Id))\
                .join(RemessaMalha)\
                .filter(
                    RemessaMalha.Ativo == True,
                    VooMalha.DataPartida == DataFiltro
                ).scalar()
                
            return Total or 0
        except Exception as e:
            # Substituído print por LogService
            LogService.Error("MalhaService", "Erro ao obter total de voos", e)
            return 0
        finally:
            Sessao.close()

    # --- ALGORITMOS DE ROTEAMENTO E BUSCA ---

    @staticmethod
    def BuscarRotasInteligentes(data_inicio, data_fim, origem_iata=None, destino_iata=None, numero_voo=None):
        """
        Executa busca de voos ou cálculo de rotas (Dijkstra/DFS limitado).
        Suporta busca direta por número de voo ou busca de rotas origem->destino.
        """
        Sessao = ObterSessaoSqlServer()
        try:
            LogService.Debug("MalhaService", f"Buscando rotas: {data_inicio} até {data_fim} | {origem_iata}->{destino_iata} | Voo: {numero_voo}")
            
            FiltroDataInicio = data_inicio.date() if isinstance(data_inicio, datetime) else data_inicio
            FiltroDataFim = data_fim.date() if isinstance(data_fim, datetime) else data_fim

            origem_iata = origem_iata.upper().strip() if origem_iata else None
            destino_iata = destino_iata.upper().strip() if destino_iata else None
            numero_voo = numero_voo.strip() if numero_voo else None
            
            # Query Base
            Query = Sessao.query(VooMalha)\
                .join(RemessaMalha)\
                .filter(
                    RemessaMalha.Ativo == True,
                    VooMalha.DataPartida >= FiltroDataInicio, 
                    VooMalha.DataPartida <= FiltroDataFim + timedelta(days=1)
                )

            # Filtro por Número de Voo (Busca Rápida)
            if numero_voo:
                Query = Query.filter(VooMalha.NumeroVoo.ilike(f"%{numero_voo}%"))

            VoosDB = Query.all()
            
            DadosAeroportos = {}
            ListaGeral = [] 

            # Retorno direto se busca por número
            if numero_voo:
                MalhaService._CompletarCacheDestinos(Sessao, VoosDB, DadosAeroportos)
                return MalhaService._FormatarListaRotas(VoosDB, DadosAeroportos, 'Geral')

            # Construção do Grafo
            G = nx.DiGraph()
            
            for Voo in VoosDB:
                if not (origem_iata and destino_iata):
                    if (not origem_iata or Voo.AeroportoOrigem == origem_iata) and \
                       (not destino_iata or Voo.AeroportoDestino == destino_iata):
                            ListaGeral.append(Voo)
                
                # Adiciona aresta ao Grafo
                if G.has_edge(Voo.AeroportoOrigem, Voo.AeroportoDestino):
                    G[Voo.AeroportoOrigem][Voo.AeroportoDestino]['voos'].append(Voo)
                else:
                    G.add_edge(Voo.AeroportoOrigem, Voo.AeroportoDestino, voos=[Voo])

            if not (origem_iata and destino_iata):
                MalhaService._CompletarCacheDestinos(Sessao, ListaGeral, DadosAeroportos)
                return MalhaService._FormatarListaRotas(ListaGeral[:2000], DadosAeroportos, 'Geral')

            # Algoritmo de Busca de Caminhos
            if not G.has_node(origem_iata) or not G.has_node(destino_iata):
                LogService.Debug("MalhaService", "Origem ou Destino não encontrados no grafo da malha.")
                return []
                
            try:
                # Busca caminhos topológicos (sem validar horários ainda)
                Caminhos = list(nx.all_simple_paths(G, source=origem_iata, target=destino_iata, cutoff=3))
                
                if not Caminhos: return []
                
                RotasValidas = []
                for CaminhoNos in Caminhos:
                    Rota = MalhaService._ValidarCaminhoCronologico(G, CaminhoNos, data_inicio)
                    if Rota:
                        RotasValidas.append(Rota)
                
                if not RotasValidas: return []

                # Ordenação Multicritério: 
                # 1. Menor número de trocas de CIA
                # 2. Menor duração total
                # 3. Menor número de escalas
                RotasValidas.sort(key=lambda r: (
                    MalhaService._ContarTrocasCia(r), 
                    MalhaService._CalcularDuracaoRota(r), 
                    len(r)
                ))

                MelhorRota = RotasValidas[0]
                
                MalhaService._CompletarCacheDestinos(Sessao, MelhorRota, DadosAeroportos)
                Tipo = 'Direto' if len(MelhorRota) == 1 else 'Conexao'
                return MalhaService._FormatarListaRotas(MelhorRota, DadosAeroportos, Tipo)
                        
            except Exception as e:
                # Substituído print por LogService
                LogService.Error("MalhaService", "Erro no algoritmo de grafo", e)
                return []

        finally:
            Sessao.close()

    # --- MÉTODOS AUXILIARES (PRIVADOS) ---

    @staticmethod
    def _ValidarCaminhoCronologico(Grafo, Nos, DataMinimaAbsoluta):
        """
        Valida se uma sequência de nós aeroportuários possui voos compatíveis cronologicamente.
        Implementa lógica de conexão (mínimo 1h, máximo 24h) e prioriza mesma Cia Aérea.
        """
        VoosEscolhidos = []
        
        if isinstance(DataMinimaAbsoluta, date) and not isinstance(DataMinimaAbsoluta, datetime):
            DataReferencia = datetime.combine(DataMinimaAbsoluta, time.min)
        else:
            DataReferencia = DataMinimaAbsoluta

        for i in range(len(Nos) - 1):
            Orig = Nos[i]
            Dest = Nos[i+1]
            
            if Dest not in Grafo[Orig]: return None
            Candidatos = Grafo[Orig][Dest]['voos'][:]
            
            # Ordenação primária por horário
            Candidatos.sort(key=lambda v: (v.DataPartida, v.HorarioSaida))
            
            CandidatosOrdenados = []
            
            # Heurística: Priorizar mesma Cia Aérea
            if VoosEscolhidos:
                CiaAnterior = VoosEscolhidos[-1].CiaAerea
                MesmaCia = [v for v in Candidatos if v.CiaAerea == CiaAnterior]
                OutraCia = [v for v in Candidatos if v.CiaAerea != CiaAnterior]
                CandidatosOrdenados = MesmaCia + OutraCia
            else:
                CandidatosOrdenados = Candidatos

            VooEleito = None
            for Voo in CandidatosOrdenados:
                SaidaVoo = datetime.combine(Voo.DataPartida, Voo.HorarioSaida)
                
                if i == 0: # Primeiro Trecho
                    if SaidaVoo > DataReferencia: 
                        VooEleito = Voo
                        break
                else: # Conexão
                    VooAnt = VoosEscolhidos[-1]
                    ChegadaAnt = datetime.combine(VooAnt.DataPartida, VooAnt.HorarioChegada)
                    if VooAnt.HorarioChegada < VooAnt.HorarioSaida: # Overnight
                        ChegadaAnt += timedelta(days=1)
                    
                    # Janela de Conexão: 1h a 24h
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

    @staticmethod
    def _CalcularDuracaoRota(ListaVoos):
        if not ListaVoos: return 99999999
        
        def to_dt(d, t): return datetime.combine(d, t)

        Primeiro = ListaVoos[0]
        Ultimo = ListaVoos[-1]
        
        Inicio = to_dt(Primeiro.DataPartida, Primeiro.HorarioSaida)
        Fim = to_dt(Ultimo.DataPartida, Ultimo.HorarioChegada)
        
        if Ultimo.HorarioChegada < Ultimo.HorarioSaida:
            Fim += timedelta(days=1)
            
        return (Fim - Inicio).total_seconds()

    @staticmethod
    def _ContarTrocasCia(Rota):
        trocas = 0
        for i in range(len(Rota) - 1):
            if Rota[i].CiaAerea != Rota[i+1].CiaAerea:
                trocas += 1
        return trocas

    @staticmethod
    def _CompletarCacheDestinos(Sessao, ListaVoos, Cache):
        """Popula cache com coordenadas e nomes de aeroportos para otimizar retorno."""
        Iatas = set()
        for v in ListaVoos:
            Iatas.add(v.AeroportoOrigem)
            Iatas.add(v.AeroportoDestino)
        
        Faltantes = [i for i in Iatas if i not in Cache]
        if Faltantes:
            Aeroportos = Sessao.query(Aeroporto).filter(Aeroporto.CodigoIata.in_(Faltantes)).all()
            for a in Aeroportos:
                Cache[a.CodigoIata] = {'lat': a.Latitude, 'lon': a.Longitude, 'nome': a.NomeAeroporto}

    @staticmethod
    def _FormatarListaRotas(ListaVoos, Cache, Tipo):
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