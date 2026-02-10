import os
import networkx as nx
import pandas as pd
from datetime import datetime, timedelta, date, time
from sqlalchemy import desc
from Conexoes import ObterSessaoSqlServer
from Utils.Formatadores import PadronizarData
from Models.SQL_SERVER.Aeroporto import Aeroporto
from Models.SQL_SERVER.MalhaAerea import RemessaMalha, VooMalha
from Services.TabelaFreteService import TabelaFreteService
from Services.CiaAereaService import CiaAereaService
from Services.LogService import LogService
from Configuracoes import ConfiguracaoBase

class MalhaService:
    
    DIR_TEMP = ConfiguracaoBase.DIR_TEMP
    
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
    def _GarantirDiretorio():
        if not os.path.exists(MalhaService.DIR_TEMP):
            os.makedirs(MalhaService.DIR_TEMP)

    @staticmethod
    def BuscarOpcoesDeRotas(data_inicio, data_fim, origem_iata, destino_iata, peso_total=100.0):
        Sessao = ObterSessaoSqlServer()
        Opcoes = {'recomendada': [], 'mais_rapida': [], 'menor_custo': [], 'menos_conexoes': []}
        
        try:
            LogService.Info("MalhaService", f"--- ROTAS: {origem_iata} -> {destino_iata} | Peso: {peso_total}kg ---")
            
            # 1. Busca Voos (AMPLIADO PARA 5 DIAS para achar a LATAM)
            FiltroDataInicio = data_inicio.date() if isinstance(data_inicio, datetime) else data_inicio
            FiltroDataFim = data_fim.date() if isinstance(data_fim, datetime) else data_fim
            
            VoosDB = Sessao.query(VooMalha).join(RemessaMalha).filter(
                    RemessaMalha.Ativo == True,
                    VooMalha.DataPartida >= FiltroDataInicio, 
                    VooMalha.DataPartida <= FiltroDataFim + timedelta(days=5) 
                ).all()

            # --- DIAGNÓSTICO: QUEM VEIO PRO JOGO? ---
            Contagem = {}
            for v in VoosDB:
                cia = v.CiaAerea.strip().upper()
                Contagem[cia] = Contagem.get(cia, 0) + 1
            LogService.Info("MalhaService", f"✈️ INVENTÁRIO DE VOOS (5 DIAS): {Contagem}")
            
            if not VoosDB: return Opcoes

            # 2. Grafo
            G = nx.DiGraph()
            for Voo in VoosDB:
                if G.has_edge(Voo.AeroportoOrigem, Voo.AeroportoDestino):
                    G[Voo.AeroportoOrigem][Voo.AeroportoDestino]['voos'].append(Voo)
                else:
                    G.add_edge(Voo.AeroportoOrigem, Voo.AeroportoDestino, voos=[Voo])

            if not G.has_node(origem_iata) or not G.has_node(destino_iata):
                LogService.Info("MalhaService", f"Origem {origem_iata} ou Destino {destino_iata} não existem na malha.")
                return Opcoes

            # 3. Caminhos (Topologia)
            CaminhosNos = list(nx.all_simple_paths(G, source=origem_iata, target=destino_iata, cutoff=3))
            LogService.Info("MalhaService", f"Caminhos Possíveis (Nós): {len(CaminhosNos)}")
            
            RotasValidadas = []
            
            # Carrega Scores
            ScoresParceria = CiaAereaService.ObterDicionarioScores()
            
            Descartes = 0

            for Caminho in CaminhosNos:
                # Valida cronologia com janela estendida (48h)
                SequenciaVoos = MalhaService._ValidarCaminhoCronologico(G, Caminho, data_inicio)
                
                if SequenciaVoos:
                    Duracao = MalhaService._CalcularDuracaoRota(SequenciaVoos)
                    TrocasCia = MalhaService._ContarTrocasCia(SequenciaVoos)
                    QtdEscalas = len(SequenciaVoos) - 1
                    
                    CustoTotal = 0.0
                    ScoreParceriaRota = 0 
                    CiasDaRota = []

                    for v in SequenciaVoos:
                        c, _ = TabelaFreteService.CalcularCustoEstimado(v.AeroportoOrigem, v.AeroportoDestino, v.CiaAerea, peso_total)
                        CustoTotal += c
                        
                        nome_cia = v.CiaAerea.strip().upper()
                        score_cia = ScoresParceria.get(nome_cia, 50) 
                        ScoreParceriaRota += score_cia
                        CiasDaRota.append(f"{nome_cia}({score_cia}%)")
                    
                    MediaParceria = ScoreParceriaRota / len(SequenciaVoos) if len(SequenciaVoos) > 0 else 50
                    
                    # --- CÁLCULO DE SCORE CÚBICO ---
                    P_Troca = TrocasCia * 50000
                    P_Tempo = Duracao
                    P_Escala = QtdEscalas * 1000
                    P_Custo = CustoTotal * 0.1
                    
                    ScoreBase = P_Troca + P_Tempo + P_Escala + P_Custo
                    
                    # BÔNUS EXPONENCIAL
                    BonusParceria = (MediaParceria ** 3)
                    
                    ScoreFinal = ScoreBase - BonusParceria
                    
                    RotasValidadas.append({
                        'rota': SequenciaVoos,
                        'metricas': {
                            'duracao': Duracao, 'custo': CustoTotal, 'escalas': QtdEscalas, 
                            'trocas_cia': TrocasCia, 'score': ScoreFinal, 'indice_parceria': MediaParceria
                        }
                    })
                else:
                    Descartes += 1

            LogService.Info("MalhaService", f"Rotas Válidas: {len(RotasValidadas)} | Descartadas (Conexão > 48h): {Descartes}")

            if not RotasValidadas: return Opcoes

            # 4. Formatação e Seleção
            DadosAeroportos = {}
            MalhaService._CompletarCacheDestinos(Sessao, [v for r in RotasValidadas for v in r['rota']], DadosAeroportos)

            def formatar(item, tag):
                return MalhaService._FormatarListaRotas(item['rota'], DadosAeroportos, tag, item['metricas'])

            # Estratégias Padrão
            RotasValidadas.sort(key=lambda x: x['metricas']['duracao'])
            Opcoes['mais_rapida'] = formatar(RotasValidadas[0], 'Mais Rápida')

            ComCusto = [r for r in RotasValidadas if r['metricas']['custo'] > 0]
            if ComCusto:
                ComCusto.sort(key=lambda x: x['metricas']['custo'])
                Opcoes['menor_custo'] = formatar(ComCusto[0], 'Menor Custo')

            RotasValidadas.sort(key=lambda x: (x['metricas']['escalas'], x['metricas']['trocas_cia']))
            Opcoes['menos_conexoes'] = formatar(RotasValidadas[0], 'Menos Conexões')

            # ORDENAÇÃO PELO SCORE FINAL (LATAM VAI APARECER AQUI)
            RotasValidadas.sort(key=lambda x: x['metricas']['score'])
            Vencedora = RotasValidadas[0]
            
            LogService.Info("MalhaService", 
                f"🏆 CAMPEÃ: {Vencedora['rota'][0].CiaAerea} | Score: {Vencedora['metricas']['score']:.0f} | "
                f"Parceria Média: {Vencedora['metricas']['indice_parceria']:.0f}%"
            )

            Opcoes['recomendada'] = formatar(Vencedora, 'Recomendada')

            return Opcoes

        except Exception as e:
            LogService.Error("MalhaService", "Erro em BuscarOpcoesDeRotas", e)
            return Opcoes
        finally:
            Sessao.close()

    # --- MÉTODOS AUXILIARES ---

    @staticmethod
    def _ValidarCaminhoCronologico(Grafo, ListaNos, DataInicio):
        """
        Verifica se existe uma sequência de voos válida.
        Agora com janela de conexão de até 48h para permitir que Cias com menos frequência apareçam.
        """
        VoosEscolhidos = []
        MomentoDisponivel = DataInicio if isinstance(DataInicio, datetime) else datetime.combine(DataInicio, time.min)
        
        for i in range(len(ListaNos) - 1):
            Origem = ListaNos[i]
            Destino = ListaNos[i+1]
            
            if Destino not in Grafo[Origem]: return None
            OpcoesVoos = Grafo[Origem][Destino]['voos'][:]
            
            # Ordena cronologicamente
            OpcoesVoos.sort(key=lambda v: (v.DataPartida, v.HorarioSaida))
            
            VooViavel = None
            
            # Tenta encontrar o voo ideal (priorizando mesma CIA da perna anterior se houver)
            CiaPreferida = VoosEscolhidos[-1].CiaAerea if VoosEscolhidos else None
            
            # Divide em listas para priorizar Cia
            if CiaPreferida:
                Prioritarios = [v for v in OpcoesVoos if v.CiaAerea == CiaPreferida]
                Outros = [v for v in OpcoesVoos if v.CiaAerea != CiaPreferida]
                OpcoesVoos = Prioritarios + Outros

            for Voo in OpcoesVoos:
                SaidaVoo = datetime.combine(Voo.DataPartida, Voo.HorarioSaida)
                
                if i == 0:
                    if SaidaVoo >= MomentoDisponivel:
                        VooViavel = Voo
                        break
                else:
                    # Lógica de Conexão
                    ChegadaAnterior = datetime.combine(VoosEscolhidos[-1].DataPartida, VoosEscolhidos[-1].HorarioChegada)
                    if VoosEscolhidos[-1].HorarioChegada < VoosEscolhidos[-1].HorarioSaida:
                        ChegadaAnterior += timedelta(days=1)
                    
                    # Janela Estendida: Mínimo 1h, Máximo 48h (2 dias)
                    if SaidaVoo >= ChegadaAnterior + timedelta(hours=1):
                        if SaidaVoo <= ChegadaAnterior + timedelta(hours=48):
                            VooViavel = Voo
                            break
            
            if VooViavel:
                VoosEscolhidos.append(VooViavel)
                # Atualiza momento para a chegada deste voo
                ChegadaVoo = datetime.combine(VooViavel.DataPartida, VooViavel.HorarioChegada)
                if VooViavel.HorarioChegada < VooViavel.HorarioSaida:
                    ChegadaVoo += timedelta(days=1)
                MomentoDisponivel = ChegadaVoo
            else:
                return None # Sem conexão viável
                
        return VoosEscolhidos

    @staticmethod
    def _CalcularDuracaoRota(ListaVoos):
        if not ListaVoos: return 0
        Primeiro = ListaVoos[0]
        Ultimo = ListaVoos[-1]
        
        Inicio = datetime.combine(Primeiro.DataPartida, Primeiro.HorarioSaida)
        Fim = datetime.combine(Ultimo.DataPartida, Ultimo.HorarioChegada)
        
        if Ultimo.HorarioChegada < Ultimo.HorarioSaida:
            Fim += timedelta(days=1)
            
        # Ajuste de dias para conexões que viraram a noite ou dias
        # Como não temos a data exata de chegada calculada no objeto, aproximamos:
        # Se Fim < Inicio, soma dias até ficar maior (assumindo cronologia válida)
        while Fim < Inicio:
            Fim += timedelta(days=1)
            
        return (Fim - Inicio).total_seconds() / 60

    @staticmethod
    def _ContarTrocasCia(ListaVoos):
        if not ListaVoos: return 0
        Trocas = 0
        for i in range(len(ListaVoos) - 1):
            if ListaVoos[i].CiaAerea != ListaVoos[i+1].CiaAerea:
                Trocas += 1
        return Trocas

    @staticmethod
    def _CompletarCacheDestinos(Sessao, ListaVoos, Cache):
        Iatas = set()
        for v in ListaVoos:
            Iatas.add(v.AeroportoOrigem)
            Iatas.add(v.AeroportoDestino)
        
        Faltantes = [i for i in Iatas if i not in Cache]
        if Faltantes:
            Aeros = Sessao.query(Aeroporto).filter(Aeroporto.CodigoIata.in_(Faltantes)).all()
            for a in Aeros:
                Cache[a.CodigoIata] = {'nome': a.NomeAeroporto, 'lat': float(a.Latitude or 0), 'lon': float(a.Longitude or 0)}

    @staticmethod
    def _FormatarListaRotas(ListaVoos, Cache, Tipo, Metricas=None):
        Resultado = []
        InfoAdicional = {}
        
        if Metricas:
            seg = int(Metricas['duracao'] * 60)
            # Formata duração > 24h
            dias = seg // 86400
            horas = (seg % 86400) // 3600
            mins = (seg % 3600) // 60
            duracao_fmt = f"{horas:02}:{mins:02}"
            if dias > 0: duracao_fmt = f"{dias}d {duracao_fmt}"
            
            custo_fmt = f"R$ {Metricas['custo']:,.2f}"
            InfoAdicional = {'total_duracao': duracao_fmt, 'total_custo': custo_fmt}

        # Calcula datas reais para exibição (importante para voos de +2 dias)
        DataCorrente = ListaVoos[0].DataPartida
        
        for i, Voo in enumerate(ListaVoos):
            Orig = Cache.get(Voo.AeroportoOrigem, {'nome': Voo.AeroportoOrigem})
            Dest = Cache.get(Voo.AeroportoDestino, {'nome': Voo.AeroportoDestino})
            
            # Se a data do voo no banco for menor que a data corrente da simulação,
            # significa que o loop de dias virou. Ajustamos visualmente.
            # Mas como o objeto Voo tem a DataPartida real do banco, usamos ela.
            # A lógica de _ValidarCaminhoCronologico garante que Voo.DataPartida >= Anterior
            
            Resultado.append({
                'tipo_resultado': Tipo,
                'cia': Voo.CiaAerea.strip(),
                'voo': Voo.NumeroVoo,
                'data': Voo.DataPartida.strftime('%d/%m/%Y'),
                'horario_saida': Voo.HorarioSaida.strftime('%H:%M'),
                'horario_chegada': Voo.HorarioChegada.strftime('%H:%M'),
                'origem': {'iata': Voo.AeroportoOrigem, 'nome': Orig.get('nome'), 'lat': Orig.get('lat'), 'lon': Orig.get('lon')},
                'destino': {'iata': Voo.AeroportoDestino, 'nome': Dest.get('nome'), 'lat': Dest.get('lat'), 'lon': Dest.get('lon')},
                **InfoAdicional
            })
        return Resultado