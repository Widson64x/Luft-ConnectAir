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
from Services.Logic.RouteIntelligenceService import RouteIntelligenceService
from Services.Logic.RouteMLEngine import RouteMLEngine
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
                    AeroportoOrigem=str(Linha.get('ORIGEM', '')).strip().upper(),
                    HorarioSaida=H_Saida,
                    HorarioChegada=H_Chegada,
                    AeroportoDestino=str(Linha.get('DESTINO', '')).strip().upper()
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
    
    # --- MÉTODO PRINCIPAL DE BUSCA ---
    @staticmethod
    def BuscarOpcoesDeRotas(data_inicio, data_fim, lista_origens, lista_destinos, peso_total=100.0, tipo_carga=None, servico_contratado=None, ml_context=None):
        """Compatibilidade legada: delega a montagem de rotas para Services/Logic."""
        return RouteIntelligenceService.BuscarOpcoesDeRotas(
            data_inicio=data_inicio,
            data_fim=data_fim,
            lista_origens=lista_origens,
            lista_destinos=lista_destinos,
            peso_total=peso_total,
            tipo_carga=tipo_carga,
            servico_contratado=servico_contratado,
            ml_context=ml_context,
        )

    @staticmethod
    def _CompletarCacheDestinos(Sessao, ListaVoos, Cache):
        Iatas = set()
        for v in ListaVoos:
            Iatas.add(v.AeroportoOrigem); Iatas.add(v.AeroportoDestino)
        Faltantes = [i for i in Iatas if i not in Cache]
        if Faltantes:
            for a in Sessao.query(Aeroporto).filter(Aeroporto.CodigoIata.in_(Faltantes)).all():
                Cache[a.CodigoIata] = {'nome': a.NomeAeroporto, 'lat': float(a.Latitude or 0), 'lon': float(a.Longitude or 0)}

    @staticmethod
    def _FormatarListaRotas(ListaVoos, Cache, Tipo, Metricas=None, DetalhesTarifas=None, bonus_ml: float = 0.0):
        Resultado = []
        InfoAdicional = {}
        if Metricas:
            seg = int(Metricas['duracao'] * 60)
            dias, resto = divmod(seg, 86400)
            horas, mins = divmod(resto, 3600); mins //= 60
            duracao_fmt = f"{dias}d {horas:02}:{mins:02}" if dias > 0 else f"{horas:02}:{mins:02}"
            custo_fmt = f"R$ {Metricas['custo']:,.2f}"
            InfoAdicional = {
                'total_duracao': duracao_fmt,
                'total_custo': custo_fmt,
                'total_custo_fmt': custo_fmt,
                'total_custo_raw': Metricas['custo'],
                'ml_ativo': abs(bonus_ml) > 1.0,
                'ml_bonus': round(bonus_ml, 2),
            }
        
        for i, Voo in enumerate(ListaVoos):
            Orig = Cache.get(Voo.AeroportoOrigem, {'nome': Voo.AeroportoOrigem})
            Dest = Cache.get(Voo.AeroportoDestino, {'nome': Voo.AeroportoDestino})
            
            # Garante que pega o detalhe correspondente ao índice
            dados_frete = DetalhesTarifas[i] if DetalhesTarifas and i < len(DetalhesTarifas) else {}
            custo_trecho = dados_frete.get('custo_calculado', 0.0)
            
            # Tratamento de fallback para exibição de Cia Tarifaria vs Cia Voo
            cia_tabela = dados_frete.get('cia_tarifaria')
            cia_voo = Voo.CiaAerea.strip()
            # Se a tarifa foi encontrada usando fallback (Strategy 2 do TabelaFreteService),
            # 'cia_tarifaria' virá correta (ex: LATAM). Se não, usa a do voo.
            cia_final = cia_tabela if cia_tabela else cia_voo

            Resultado.append({
                'tipo_resultado': Tipo,
                'cia': cia_voo, 
                'voo': Voo.NumeroVoo,
                'data': Voo.DataPartida.strftime('%d/%m/%Y'),
                'horario_saida': Voo.HorarioSaida.strftime('%H:%M'),
                'horario_chegada': Voo.HorarioChegada.strftime('%H:%M'),
                'origem': {'iata': Voo.AeroportoOrigem, 'nome': Orig.get('nome'), 'lat': Orig.get('lat'), 'lon': Orig.get('lon')},
                'destino': {'iata': Voo.AeroportoDestino, 'nome': Dest.get('nome'), 'lat': Dest.get('lat'), 'lon': Dest.get('lon')},
                'base_calculo': {
                    'id_frete': dados_frete.get('id_frete'),
                    'tarifa': dados_frete.get('tarifa_base', 0.0),
                    'servico': dados_frete.get('servico', 'STANDARD'),
                    'cia_tarifaria': cia_final, 
                    'peso_usado': dados_frete.get('peso_calculado', 0),
                    'custo_trecho': custo_trecho,
                    'custo_trecho_fmt': f"R$ {custo_trecho:,.2f}"
                },
                **InfoAdicional
            })
        return Resultado