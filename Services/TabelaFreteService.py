import os
import pandas as pd
from datetime import datetime
from sqlalchemy import desc
from Conexoes import ObterSessaoPostgres
from Models.POSTGRES.TabelaFrete import RemessaFrete, TabelaFrete
from Configuracoes import ConfiguracaoBase
from Services.LogService import LogService

class TabelaFreteService:
    DIR_TEMP = ConfiguracaoBase.DIR_TEMP

    @staticmethod
    def _GarantirDiretorio():
        if not os.path.exists(TabelaFreteService.DIR_TEMP):
            try:
                os.makedirs(TabelaFreteService.DIR_TEMP)
            except Exception as e:
                LogService.Error("TabelaFreteService", "Falha ao criar diretório temp", e)

    @staticmethod
    def _NormalizarTarifa(val):
        """
        Retorna float se válido, ou None se vazio/inválido.
        """
        if pd.isna(val): return None
        s = str(val).strip().upper()
        if s in ['', '-', 'NAN', 'NONE', 'N/A']: return None
        
        try:
            # Remove R$, espaços e converte vírgula
            clean_val = s.replace('R$', '').replace(' ', '').replace(',', '.')
            return float(clean_val)
        except:
            return None

    @staticmethod
    def ListarRemessas():
        Sessao = ObterSessaoPostgres()
        try:
            return Sessao.query(RemessaFrete).order_by(desc(RemessaFrete.DataUpload)).all()
        finally:
            Sessao.close()

    @staticmethod
    def ExcluirRemessa(id_remessa):
        Sessao = ObterSessaoPostgres()
        try:
            Remessa = Sessao.query(RemessaFrete).get(id_remessa)
            if Remessa:
                Sessao.delete(Remessa)
                Sessao.commit()
                return True, "Tabela excluída com sucesso."
            return False, "Registro não encontrado."
        except Exception as e:
            Sessao.rollback()
            return False, str(e)
        finally:
            Sessao.close()

    @staticmethod
    def ProcessarArquivo(arquivo, usuario):
        TabelaFreteService._GarantirDiretorio()
        Caminho = os.path.join(TabelaFreteService.DIR_TEMP, arquivo.filename)
        Sessao = ObterSessaoPostgres()
        
        try:
            arquivo.save(Caminho)
            LogService.Info("TabelaFreteService", f"Analisando arquivo: {arquivo.filename}")
            
            DfRaw = None
            
            # --- BLOCO DE LEITURA BLINDADO (Context Manager) ---
            # O 'with' garante que o arquivo será fechado ao sair do bloco
            with pd.ExcelFile(Caminho, engine='openpyxl') as XlsFile:
                
                # 1. Identificar a aba correta
                SheetName = None
                for sheet in XlsFile.sheet_names:
                    if 'TARIF' in sheet.upper(): 
                        SheetName = sheet
                        break
                
                if not SheetName:
                    SheetName = XlsFile.sheet_names[0]
                    LogService.Warning("TabelaFreteService", f"Aba 'TARIFÁRIO' não encontrada. Usando: {SheetName}")
                else:
                    LogService.Info("TabelaFreteService", f"Processando aba: {SheetName}")

                # 2. Ler os dados usando o arquivo já aberto
                DfRaw = pd.read_excel(XlsFile, sheet_name=SheetName, header=None)

            # --- FIM DO BLOCO DE LEITURA (Arquivo fechado aqui) ---

            # 3. Localizar Cabeçalho
            RowHeaderIdx = -1
            ColOrigemIdx = -1
            ColDestinoIdx = -1
            
            for i in range(min(15, len(DfRaw))):
                RowVals = [str(x).strip().upper() for x in DfRaw.iloc[i].values]
                if 'ORIGEM' in RowVals and 'DESTINO' in RowVals:
                    RowHeaderIdx = i
                    for idx, val in enumerate(RowVals):
                        if val == 'ORIGEM': ColOrigemIdx = idx
                        elif val == 'DESTINO': ColDestinoIdx = idx
                    break
            
            if RowHeaderIdx == -1:
                return False, "Estrutura inválida. Colunas Origem/Destino não encontradas."

            # 4. Mapear Serviços
            if RowHeaderIdx == 0:
                return False, "Arquivo sem linha de títulos de serviços."

            MapServicos = {}
            RowServicosIdx = RowHeaderIdx - 1
            
            for col in range(len(DfRaw.columns)):
                if col in [ColOrigemIdx, ColDestinoIdx]: continue
                
                NomeServico = str(DfRaw.iloc[RowServicosIdx, col]).strip()
                
                if NomeServico and NomeServico.upper() not in ['NAN', 'NONE', '', 'N/A']:
                    if " X " in NomeServico.upper(): continue
                    MapServicos[col] = NomeServico

            if not MapServicos:
                return False, "Nenhum serviço identificado."

            # 5. Persistir Dados
            NovaRemessa = RemessaFrete(
                DataReferencia=datetime.now().date(),
                NomeArquivoOriginal=arquivo.filename,
                UsuarioResponsavel=usuario,
                Ativo=True
            )
            Sessao.add(NovaRemessa)
            Sessao.flush()

            ListaInsert = []
            
            for i in range(RowHeaderIdx + 1, len(DfRaw)):
                Row = DfRaw.iloc[i]
                
                RawOrigem = str(Row[ColOrigemIdx]).strip().upper()
                RawDestino = str(Row[ColDestinoIdx]).strip().upper()
                
                if RawOrigem in ['', 'NAN', 'NONE'] or RawDestino in ['', 'NAN', 'NONE']: continue
                
                Origens = [o.strip() for o in RawOrigem.split('/')]
                
                for Origem in Origens:
                    for ColIdx, NomeServico in MapServicos.items():
                        ValorRaw = Row[ColIdx]
                        ValorTarifa = TabelaFreteService._NormalizarTarifa(ValorRaw)
                        
                        Cia = NomeServico.split(' ')[0].upper()
                        
                        Item = TabelaFrete(
                            IdRemessa=NovaRemessa.Id,
                            Origem=Origem,
                            Destino=RawDestino,
                            CiaAerea=Cia,
                            Servico=NomeServico,
                            Tarifa=ValorTarifa
                        )
                        ListaInsert.append(Item)

            if ListaInsert:
                Sessao.bulk_save_objects(ListaInsert)
                Sessao.commit()
                Msg = f"Sucesso! {len(ListaInsert)} linhas de tarifa importadas."
                LogService.Info("TabelaFreteService", Msg)
                return True, Msg
            else:
                return False, "Arquivo processado mas nenhum dado encontrado."

        except Exception as e:
            Sessao.rollback()
            LogService.Error("TabelaFreteService", "Erro fatal no processamento", e)
            return False, f"Erro técnico: {str(e)}"
        
        finally:
            # Agora é seguro remover, pois o 'with' já fechou o arquivo lá em cima
            if os.path.exists(Caminho):
                try:
                    os.remove(Caminho)
                except Exception as e:
                    LogService.Warning("TabelaFreteService", f"Não foi possível remover temp: {e}")
            Sessao.close()