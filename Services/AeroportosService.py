import os
import pandas as pd
from datetime import datetime, date
from sqlalchemy import desc
from Conexoes import ObterSessaoPostgres
from Models.POSTGRES.Aeroporto import RemessaAeroportos, Aeroporto
from Configuracoes import ConfiguracaoBase
from Services.LogService import LogService # <--- Import do Log

DIR_TEMP = ConfiguracaoBase.DIR_TEMP

class AeroportoService:
    
    @staticmethod
    def BuscarPorSigla(Sigla):
        """
        Busca um aeroporto pelo código IATA (ex: GRU, JFK).
        Utilizado pelo serviço de acompanhamento para plotar o mapa.
        """
        Sessao = ObterSessaoPostgres()
        try:
            # Garante que a sigla esteja em maiúscula e sem espaços
            if not Sigla: return None
            
            Sigla = Sigla.upper().strip()
            
            # Retorna o objeto Aeroporto (que contém Latitude e Longitude)
            return Sessao.query(Aeroporto).filter(Aeroporto.CodigoIata == Sigla).first()
        except Exception as e:
            LogService.Error("AeroportoService", f"Erro ao buscar aeroporto {Sigla}", e)
            return None
        finally:
            Sessao.close()

    @staticmethod
    def ListarRemessasAeroportos():
        Sessao = ObterSessaoPostgres()
        try:
            return Sessao.query(RemessaAeroportos).order_by(desc(RemessaAeroportos.DataUpload)).all()
        except Exception as e:
             LogService.Error("AeroportoService", "Erro ao listar remessas.", e)
             return []
        finally:
            Sessao.close()

    @staticmethod
    def ExcluirRemessaAeroporto(IdRemessa):
        Sessao = ObterSessaoPostgres()
        try:
            LogService.Info("AeroportoService", f"Tentativa de excluir remessa ID: {IdRemessa}")
            Remessa = Sessao.query(RemessaAeroportos).get(IdRemessa)
            if Remessa:
                Sessao.delete(Remessa)
                Sessao.commit()
                LogService.Info("AeroportoService", f"Remessa de aeroportos {IdRemessa} excluída.")
                return True, "Versão da base de aeroportos excluída."
            
            LogService.Warning("AeroportoService", f"Remessa {IdRemessa} não encontrada para exclusão.")
            return False, "Remessa não encontrada."
        except Exception as e:
            Sessao.rollback()
            LogService.Error("AeroportoService", f"Erro ao excluir remessa {IdRemessa}", e)
            return False, f"Erro: {e}"
        finally:
            Sessao.close()

    @staticmethod
    def AnalisarArquivoAeroportos(FileStorage):
        try:
            LogService.Info("AeroportoService", f"Iniciando análise do arquivo: {FileStorage.filename}")
            
            # Salva Temp
            CaminhoTemp = os.path.join(DIR_TEMP, FileStorage.filename)
            FileStorage.save(CaminhoTemp)
            
            # Mês Atual como referência
            Hoje = date.today()
            DataRef = date(Hoje.year, Hoje.month, 1)

            # Verifica conflito
            Sessao = ObterSessaoPostgres()
            ExisteConflito = False
            try:
                Anterior = Sessao.query(RemessaAeroportos).filter_by(MesReferencia=DataRef, Ativo=True).first()
                if Anterior:
                    ExisteConflito = True
                    LogService.Warning("AeroportoService", f"Conflito: Já existe base de aeroportos para {DataRef}")
            finally:
                Sessao.close()

            return True, {
                'caminho_temp': CaminhoTemp,
                'mes_ref': DataRef, 
                'nome_arquivo': FileStorage.filename,
                'conflito': ExisteConflito
            }
        except Exception as e:
            LogService.Error("AeroportoService", "Erro na análise do arquivo.", e)
            return False, f"Erro ao analisar arquivo: {e}"

    @staticmethod
    def ProcessarAeroportosFinal(CaminhoArquivo, DataRef, NomeOriginal, Usuario, TipoAcao):
        LogService.Info("AeroportoService", f"Processando arquivo {NomeOriginal} (Ação: {TipoAcao})")
        Sessao = ObterSessaoPostgres()
        try:
            # 1. Ler CSV
            try:
                Df = pd.read_csv(CaminhoArquivo, sep=',', engine='python')
            except UnicodeDecodeError:
                LogService.Warning("AeroportoService", "Falha com UTF-8, tentando Latin1.")
                Df = pd.read_csv(CaminhoArquivo, sep=',', engine='python', encoding='latin1')
            except Exception as e:
                # Última tentativa
                LogService.Warning("AeroportoService", f"Falha na leitura padrão: {e}. Tentando sem aspas.")
                import csv
                Df = pd.read_csv(CaminhoArquivo, sep=',', quoting=csv.QUOTE_NONE, engine='python')
            
            if len(Df.columns) < 2:
                 # Check extra se a leitura falhou silenciosamente gerando poucas colunas
                 import csv
                 Df = pd.read_csv(CaminhoArquivo, sep=',', quoting=csv.QUOTE_NONE, engine='python')

            # 2. Limpeza dos Nomes das Colunas
            Df.columns = [c.replace('"', '').replace("'", "").strip().lower() for c in Df.columns]
            
            # Mapeamento CSV -> Banco
            Mapa = {
                'country_code': 'CodigoPais',
                'region_name': 'NomeRegiao',
                'iata': 'CodigoIata',
                'icao': 'CodigoIcao',
                'airport': 'NomeAeroporto',
                'latitude': 'Latitude',
                'longitude': 'Longitude'
            }
            
            ColunasUteis = [c for c in Mapa.keys() if c in Df.columns]
            
            if not ColunasUteis:
                LogService.Error("AeroportoService", f"Colunas não identificadas. Headers encontrados: {list(Df.columns)}")
                return False, f"Colunas não identificadas. Encontradas: {list(Df.columns)}"

            Df = Df[ColunasUteis].rename(columns=Mapa)

            # 3. Gerenciar Histórico
            Anterior = Sessao.query(RemessaAeroportos).filter_by(MesReferencia=DataRef, Ativo=True).first()
            if Anterior:
                Anterior.Ativo = False
                LogService.Info("AeroportoService", f"Remessa anterior {Anterior.Id} desativada.")

            # 4. Criar Nova Remessa
            NovaRemessa = RemessaAeroportos(
                MesReferencia=DataRef,
                NomeArquivoOriginal=NomeOriginal,
                UsuarioResponsavel=Usuario,
                TipoAcao=TipoAcao,
                Ativo=True
            )
            Sessao.add(NovaRemessa)
            Sessao.flush()

            # 5. Preparar Dados para Inserção
            ListaAeroportos = Df.to_dict(orient='records')
            
            for Aero in ListaAeroportos:
                Aero['IdRemessa'] = NovaRemessa.Id
                
                for key, val in Aero.items():
                    if isinstance(val, str):
                        Aero[key] = val.replace('"', '').strip()

                try: Aero['Latitude'] = float(Aero['Latitude'])
                except: Aero['Latitude'] = None
                
                try: Aero['Longitude'] = float(Aero['Longitude'])
                except: Aero['Longitude'] = None

            Sessao.bulk_insert_mappings(Aeroporto, ListaAeroportos)
            Sessao.commit()

            LogService.Info("AeroportoService", f"Sucesso! {len(ListaAeroportos)} aeroportos importados na Remessa {NovaRemessa.Id}.")

            if os.path.exists(CaminhoArquivo): os.remove(CaminhoArquivo)

            return True, f"Base atualizada! {len(ListaAeroportos)} aeroportos importados."

        except Exception as e:
            Sessao.rollback()
            LogService.Error("AeroportoService", "Erro técnico crítico no processamento de aeroportos.", e)
            return False, f"Erro técnico ao processar: {e}"
        finally:
            Sessao.close()
            
    @staticmethod
    def ListarTodosParaSelect():
        """
        Retorna lista simplificada para preencher combobox/datalist no frontend.
        """
        Sessao = ObterSessaoPostgres()
        try:
            Dados = Sessao.query(
                Aeroporto.CodigoIata, 
                Aeroporto.NomeAeroporto,
                Aeroporto.Latitude,
                Aeroporto.Longitude
            ).filter(Aeroporto.CodigoIata != None).all()
            
            Lista = []
            for Linha in Dados:
                Lista.append({
                    'iata': Linha.CodigoIata,
                    'nome': Linha.NomeAeroporto,
                    'lat': Linha.Latitude,
                    'lon': Linha.Longitude
                })
            return Lista
        except Exception as e:
            LogService.Error("AeroportoService", "Erro ao listar para select.", e)
            return []
        finally:
            Sessao.close()