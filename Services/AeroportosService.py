import os
import pandas as pd
import math # Importante para verificações numéricas se necessário
from datetime import datetime, date
from sqlalchemy import desc, text
# AJUSTE 1: Importar a conexão correta (se você renomeou no Conexoes.py, ajuste aqui)
# Se você manteve o nome da função mas mudou o conteúdo, pode manter. 
# Recomendado: Usar a conexão do SQL Server explicitamente.
from Conexoes import ObterSessaoSqlServer as ObterSessao 
# AJUSTE 2: Importar os modelos da pasta SQL_SERVER
from Models.SQL_SERVER.Aeroporto import RemessaAeroportos, Aeroporto
from Configuracoes import ConfiguracaoBase
from Models.SQL_SERVER.Planejamento import RankingAeroportos
from Services.LogService import LogService

DIR_TEMP = ConfiguracaoBase.DIR_TEMP

class AeroportoService:
    
    @staticmethod
    def BuscarPorSigla(Sigla):
        """
        Busca um aeroporto pelo código IATA (ex: GRU, JFK).
        """
        Sessao = ObterSessao()
        try:
            if not Sigla: return None
            Sigla = Sigla.upper().strip()
            return Sessao.query(Aeroporto).filter(Aeroporto.CodigoIata == Sigla).first()
        except Exception as e:
            LogService.Error("AeroportoService", f"Erro ao buscar aeroporto {Sigla}", e)
            return None
        finally:
            Sessao.close()

    @staticmethod
    def ListarRemessasAeroportos():
        Sessao = ObterSessao()
        try:
            return Sessao.query(RemessaAeroportos).order_by(desc(RemessaAeroportos.DataUpload)).all()
        except Exception as e:
             LogService.Error("AeroportoService", "Erro ao listar remessas.", e)
             return []
        finally:
            Sessao.close()

    @staticmethod
    def ExcluirRemessaAeroporto(IdRemessa):
        Sessao = ObterSessao()
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
            
            CaminhoTemp = os.path.join(DIR_TEMP, FileStorage.filename)
            FileStorage.save(CaminhoTemp)
            
            Hoje = date.today()
            DataRef = date(Hoje.year, Hoje.month, 1)

            Sessao = ObterSessao()
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
        Sessao = ObterSessao()
        try:
            # 1. Ler CSV
            try:
                Df = pd.read_csv(CaminhoArquivo, sep=',', engine='python')
            except UnicodeDecodeError:
                LogService.Warning("AeroportoService", "Falha com UTF-8, tentando Latin1.")
                Df = pd.read_csv(CaminhoArquivo, sep=',', engine='python', encoding='latin1')
            except Exception as e:
                LogService.Warning("AeroportoService", f"Falha na leitura padrão: {e}. Tentando sem aspas.")
                import csv
                Df = pd.read_csv(CaminhoArquivo, sep=',', quoting=csv.QUOTE_NONE, engine='python')
            
            if len(Df.columns) < 2:
                 import csv
                 Df = pd.read_csv(CaminhoArquivo, sep=',', quoting=csv.QUOTE_NONE, engine='python')

            # 2. Limpeza dos Nomes das Colunas
            Df.columns = [c.replace('"', '').replace("'", "").strip().lower() for c in Df.columns]
            
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
            
            # --- CORREÇÃO PRINCIPAL: Substituir NaN por None ---
            # SQL Server não aceita float('nan'). Deve ser None (NULL no banco).
            Df = Df.where(pd.notnull(Df), None)

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
                
                # Limpeza extra de strings caso tenha sobrado aspas
                for key, val in Aero.items():
                    if isinstance(val, str):
                        Aero[key] = val.replace('"', '').strip()
                
                # Garantia final de numéricos (redundante mas segura)
                if Aero.get('Latitude') is not None:
                     try: Aero['Latitude'] = float(Aero['Latitude'])
                     except: Aero['Latitude'] = None
                     
                if Aero.get('Longitude') is not None:
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
        Sessao = ObterSessao()
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

    @staticmethod
    def ListarAeroportosPorEstado():
        """
        Busca aeroportos BR, agrupa por UF (convertendo NomeRegiao) 
        e traz o índice de importância salvo (se houver).
        """
        Sessao = ObterSessao()
        try:
            # Mapa de De-Para (NomeRegiao do Banco -> Sigla UF)
            MapaRegiaoUf = {
                'SAO PAULO': 'SP', 'RIO DE JANEIRO': 'RJ', 'MINAS GERAIS': 'MG',
                'ESPIRITO SANTO': 'ES', 'PARANA': 'PR', 'SANTA CATARINA': 'SC',
                'RIO GRANDE DO SUL': 'RS', 'BAHIA': 'BA', 'PERNAMBUCO': 'PE',
                'CEARA': 'CE', 'DISTRITO FEDERAL': 'DF', 'GOIAS': 'GO',
                'AMAZONAS': 'AM', 'PARA': 'PA', 'MATO GROSSO': 'MT',
                'MATO GROSSO DO SUL': 'MS', 'ACRE': 'AC', 'ALAGOAS': 'AL',
                'AMAPA': 'AP', 'MARANHAO': 'MA', 'PARAIBA': 'PB',
                'PIAUI': 'PI', 'RIO GRANDE DO NORTE': 'RN', 'RONDONIA': 'RO',
                'RORAIMA': 'RR', 'SERGIPE': 'SE', 'TOCANTINS': 'TO'
            }

            # 1. Busca Aeroportos BR
            Aeroportos = Sessao.query(Aeroporto).filter(
                Aeroporto.CodigoPais == 'BR'
            ).order_by(Aeroporto.NomeRegiao, Aeroporto.NomeAeroporto).all()

            # 2. Busca Rankings Já Salvos
            Rankings = Sessao.query(RankingAeroportos).all()
            MapRankings = {f"{r.Uf}-{r.IdAeroporto}": (r.IndiceImportancia, r.IndiceUso) for r in Rankings}

            DadosAgrupados = {}

            for aero in Aeroportos:
                if not aero.NomeRegiao: continue
                
                regiao_upper = str(aero.NomeRegiao).upper().strip()
                
                # Tenta converter, senão usa as 2 primeiras letras como fallback
                uf_sigla = MapaRegiaoUf.get(regiao_upper, regiao_upper[:2])

                if uf_sigla not in DadosAgrupados:
                    DadosAgrupados[uf_sigla] = []

                # Verifica se já tem ranking salvo
                chave = f"{uf_sigla}-{aero.Id}"
                manual, uso = MapRankings.get(chave, (0, 0))

                DadosAgrupados[uf_sigla].append({
                    'id_aeroporto': aero.Id,
                    'iata': aero.CodigoIata,
                    'nome': aero.NomeAeroporto,
                    'regiao': aero.NomeRegiao,
                    'importancia': manual,
                    'importancia_uso': uso,
                })

            # Retorna ordenado por UF
            return dict(sorted(DadosAgrupados.items()))

        except Exception as e:
            LogService.Error("AeroportosService", "Erro ao listar aeroportos por estado", e)
            return {}
        finally:
            Sessao.close()

    @staticmethod
    def SalvarRankingUf(uf, lista_dados):
        """
        Recebe UF e lista de {id_aeroporto, importancia}.
        Atualiza ou Insere na Tb_PLN_RankingAeroportos.
        """
        Sessao = ObterSessao()
        try:
            uf = str(uf).upper().strip()
            
            for item in lista_dados:
                id_aero = int(item['id_aeroporto'])
                valor = int(item['importancia'])
                
                if valor < 0: valor = 0
                if valor > 100: valor = 100

                Registro = Sessao.query(RankingAeroportos).filter(
                    RankingAeroportos.Uf == uf,
                    RankingAeroportos.IdAeroporto == id_aero
                ).first()

                if Registro:
                    Registro.IndiceImportancia = valor
                else:
                    Novo = RankingAeroportos(
                        Uf=uf,
                        IdAeroporto=id_aero,
                        IndiceImportancia=valor
                    )
                    Sessao.add(Novo)
            
            Sessao.commit()
            return True, "Rankings atualizados com sucesso."
        except Exception as e:
            Sessao.rollback()
            LogService.Error("AeroportosService", f"Erro ao salvar ranking UF {uf}", e)
            return False, str(e)
        finally:
            Sessao.close()

    @staticmethod
    def RecalcularUsoAeroportos():
        """
        Conta quantas vezes cada aeroporto aparece nos PlanejamentoTrecho (origem/destino),
        normaliza 0-100 por UF e persiste em RankingAeroportos.IndiceUso.
        Só atualiza IndiceUso — nunca toca em IndiceImportancia (manual).
        """
        Sessao = ObterSessao()
        try:
            MapaRegiaoUf = {
                'SAO PAULO': 'SP', 'RIO DE JANEIRO': 'RJ', 'MINAS GERAIS': 'MG',
                'ESPIRITO SANTO': 'ES', 'PARANA': 'PR', 'SANTA CATARINA': 'SC',
                'RIO GRANDE DO SUL': 'RS', 'BAHIA': 'BA', 'PERNAMBUCO': 'PE',
                'CEARA': 'CE', 'DISTRITO FEDERAL': 'DF', 'GOIAS': 'GO',
                'AMAZONAS': 'AM', 'PARA': 'PA', 'MATO GROSSO': 'MT',
                'MATO GROSSO DO SUL': 'MS', 'ACRE': 'AC', 'ALAGOAS': 'AL',
                'AMAPA': 'AP', 'MARANHAO': 'MA', 'PARAIBA': 'PB',
                'PIAUI': 'PI', 'RIO GRANDE DO NORTE': 'RN', 'RONDONIA': 'RO',
                'RORAIMA': 'RR', 'SERGIPE': 'SE', 'TOCANTINS': 'TO'
            }

            # 1. Contar aparições por IATA nos trechos de planejamento
            sql = text("""
                SELECT iata, SUM(cnt) AS total FROM (
                    SELECT AeroportoOrigem AS iata, COUNT(*) AS cnt
                    FROM intec.dbo.Tb_PLN_PlanejamentoTrecho
                    WHERE AeroportoOrigem IS NOT NULL AND AeroportoOrigem != ''
                    GROUP BY AeroportoOrigem
                    UNION ALL
                    SELECT AeroportoDestino AS iata, COUNT(*) AS cnt
                    FROM intec.dbo.Tb_PLN_PlanejamentoTrecho
                    WHERE AeroportoDestino IS NOT NULL AND AeroportoDestino != ''
                    GROUP BY AeroportoDestino
                ) t GROUP BY iata
            """)
            contagem_bruta = {row[0]: int(row[1]) for row in Sessao.execute(sql).fetchall()}

            if not contagem_bruta:
                return True, "Nenhum dado de uso encontrado nos planejamentos."

            # 2. Busca aeroportos brasileiros da remessa ativa
            Aeroportos = Sessao.query(Aeroporto).join(
                RemessaAeroportos, Aeroporto.IdRemessa == RemessaAeroportos.Id
            ).filter(
                RemessaAeroportos.Ativo == True,
                Aeroporto.CodigoPais == 'BR'
            ).all()

            # 3. Agrupa por UF com uso
            uso_por_uf = {}  # { 'SP': [(id_aero, uso), ...] }
            for aero in Aeroportos:
                if not aero.NomeRegiao: continue
                uf = MapaRegiaoUf.get(str(aero.NomeRegiao).upper().strip())
                if not uf: continue
                uso = contagem_bruta.get(aero.CodigoIata, 0)
                uso_por_uf.setdefault(uf, []).append((aero.Id, uso))

            # 4. Normaliza 0-100 por UF e faz upsert em RankingAeroportos
            atualizados = 0
            for uf, lista in uso_por_uf.items():
                max_uso = max(u for _, u in lista) if lista else 0
                for id_aero, uso in lista:
                    indice = round(uso * 100 / max_uso) if max_uso > 0 else 0
                    Registro = Sessao.query(RankingAeroportos).filter(
                        RankingAeroportos.Uf == uf,
                        RankingAeroportos.IdAeroporto == id_aero
                    ).first()
                    if Registro:
                        Registro.IndiceUso = indice
                    else:
                        Sessao.add(RankingAeroportos(
                            Uf=uf, IdAeroporto=id_aero,
                            IndiceImportancia=0, IndiceUso=indice
                        ))
                    atualizados += 1

            Sessao.commit()
            LogService.Info("AeroportosService", f"RecalcularUso: {atualizados} registros atualizados.")
            return True, f"{atualizados} aeroportos recalculados com base nos planejamentos."

        except Exception as e:
            Sessao.rollback()
            LogService.Error("AeroportosService", "Erro ao recalcular uso de aeroportos.", e)
            return False, str(e)
        finally:
            Sessao.close()