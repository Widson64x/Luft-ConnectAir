import os
import pandas as pd
from datetime import date
from sqlalchemy import desc
from Conexoes import ObterSessaoSqlServer
from Configuracoes import ConfiguracaoBase
from Models.SQL_SERVER.Cidade import RemessaCidade, Cidade
from Services.LogService import LogService  # <--- Import do Log

DIR_TEMP = ConfiguracaoBase.DIR_TEMP

class CidadesService:
    """
    Responsável por processar arquivos de carga de Cidades,
    parsear Excels malucos e gerenciar o histórico de remessas no Postgres.
    """
    
    # Constante da Classe para organizar a bagunça
    DIR_TEMP = 'Data/Temp_Cidades'

    @staticmethod
    def _GarantirDiretorio():
        """Garante que a pasta temporária existe antes de tentar salvar algo."""
        if not os.path.exists(CidadesService.DIR_TEMP):
            os.makedirs(CidadesService.DIR_TEMP)
            LogService.Debug("CidadesService", f"Diretório temporário criado: {CidadesService.DIR_TEMP}")

    @staticmethod
    def ListarRemessas():
        """
        Lista o histórico de uploads (Quem subiu, quando e se está ativo).
        """
        Sessao = ObterSessaoSqlServer()
        try:
            return Sessao.query(RemessaCidade).order_by(desc(RemessaCidade.DataUpload)).all()
        except Exception as e:
            LogService.Error("CidadesService", "Erro ao listar remessas.", e)
            return []
        finally:
            Sessao.close()

    @staticmethod
    def ExcluirRemessa(id_remessa):
        """
        Apaga um lote de cidades inteiro. Thanos Snap. 🫰
        """
        Sessao = ObterSessaoSqlServer()
        try:
            LogService.Info("CidadesService", f"Tentativa de excluir remessa ID: {id_remessa}")
            Remessa = Sessao.query(RemessaCidade).get(id_remessa)
            if Remessa:
                Sessao.delete(Remessa)
                Sessao.commit()
                LogService.Info("CidadesService", f"Remessa {id_remessa} excluída com sucesso.")
                return True, "Base de cidades excluída com sucesso."
            
            LogService.Warning("CidadesService", f"Remessa {id_remessa} não encontrada para exclusão.")
            return False, "Remessa não encontrada."
        except Exception as e:
            Sessao.rollback()
            LogService.Error("CidadesService", f"Erro ao excluir remessa {id_remessa}", e)
            return False, f"Erro ao excluir: {e}"
        finally:
            Sessao.close()

    @staticmethod
    def AnalisarArquivo(file_storage):
        """
        Recebe o upload, salva no temp e verifica se já existe carga para este mês.
        Não processa ainda, só dá uma olhadinha. 👀
        """
        try:
            LogService.Info("CidadesService", f"Iniciando análise do arquivo: {file_storage.filename}")
            CidadesService._GarantirDiretorio()
            
            CaminhoTemp = os.path.join(CidadesService.DIR_TEMP, file_storage.filename)
            file_storage.save(CaminhoTemp)
            
            # Data de Referência é Hoje (Cadastro Estático: Mês Atual)
            Hoje = date.today()
            DataRef = date(Hoje.year, Hoje.month, 1)

            Sessao = ObterSessaoSqlServer()
            ExisteConflito = False
            try:
                # Verifica se já tem uma remessa ativa para este mês
                Anterior = Sessao.query(RemessaCidade).filter_by(MesReferencia=DataRef, Ativo=True).first()
                if Anterior:
                    ExisteConflito = True
                    LogService.Warning("CidadesService", f"Conflito detectado: Já existe remessa para {DataRef}")
            finally:
                Sessao.close()

            return True, {
                'caminho_temp': CaminhoTemp,
                'mes_ref': DataRef,
                'nome_arquivo': file_storage.filename,
                'conflito': ExisteConflito
            }
        except Exception as e:
            LogService.Error("CidadesService", "Erro na análise do arquivo de cidades.", e)
            return False, f"Erro na análise do arquivo: {e}"

    @staticmethod
    def ProcessarArquivoFinal(caminho_arquivo, data_ref, nome_original, usuario, tipo_acao):
        """
        O Motorzão V8:
        1. Lê o Excel (que na verdade é um CSV disfarçado).
        2. Desativa a remessa anterior.
        3. Cria a nova remessa.
        4. Faz o parsing manual linha a linha.
        5. Bulk Insert no banco.
        """
        LogService.Info("CidadesService", f"Iniciando processamento final (Ação: {tipo_acao}) - Arquivo: {nome_original}")
        Sessao = ObterSessaoSqlServer()
        try:
            # 1. Ler Excel (engine openpyxl para .xlsx)
            # header=None pois o arquivo parece não ter cabeçalho padrão ou é processado bruto
            DfRaw = pd.read_excel(caminho_arquivo, header=None, engine='openpyxl')
            
            # Pega a primeira coluna (índice 0) que contém o texto concatenado
            SerieDados = DfRaw.iloc[:, 0].astype(str)
            LogService.Debug("CidadesService", f"Arquivo lido. Total de linhas brutas: {len(SerieDados)}")

            # 2. Desativar remessa anterior (se houver)
            Anterior = Sessao.query(RemessaCidade).filter_by(MesReferencia=data_ref, Ativo=True).first()
            if Anterior:
                Anterior.Ativo = False
                LogService.Info("CidadesService", f"Remessa anterior (ID: {Anterior.Id}) desativada.")

            # 3. Criar Cabeçalho da Nova Remessa
            NovaRemessa = RemessaCidade(
                MesReferencia=data_ref,
                NomeArquivoOriginal=nome_original,
                UsuarioResponsavel=usuario,
                TipoAcao=tipo_acao,
                Ativo=True
            )
            Sessao.add(NovaRemessa)
            Sessao.flush() # Garante que NovaRemessa ganhe um ID

            # 4. Processar Linha a Linha (Parsing Manual da string concatenada)
            ListaCidades = []
            
            for Linha in SerieDados:
                # Limpeza: Remove aspas e espaços extras
                LinhaLimpa = Linha.replace('"', '').replace("'", "").strip()
                
                # Quebra pelo ponto e vírgula
                Partes = LinhaLimpa.split(';')
                
                # Validação básica: Precisa ter pelo menos 5 colunas
                # id_municipio; uf; municipio; longitude; latitude
                if len(Partes) < 5:
                    continue

                # Pula o cabeçalho se encontrar a palavra 'municipio' ou 'uf'
                if 'municipio' in Partes[2].lower() or 'uf' in Partes[1].lower():
                    continue

                try:
                    # Tratamento de erro na conversão de decimais (virgula para ponto)
                    Lat = float(Partes[4].replace(',', '.')) if Partes[4] else 0.0
                    Lon = float(Partes[3].replace(',', '.')) if Partes[3] else 0.0
                    
                    CidadeObj = Cidade(
                        IdRemessa=NovaRemessa.Id,
                        CodigoIbge=int(Partes[0]),
                        Uf=Partes[1].strip(),
                        NomeCidade=Partes[2].strip(),
                        Longitude=Lon,
                        Latitude=Lat
                    )
                    ListaCidades.append(CidadeObj)
                except ValueError:
                    continue # Pula linha se falhar a conversão

            # 5. Bulk Insert (Performance Extrema)
            Sessao.bulk_save_objects(ListaCidades)
            Sessao.commit()
            
            LogService.Info("CidadesService", f"Processamento concluído. {len(ListaCidades)} cidades importadas na Remessa {NovaRemessa.Id}.")

            # Limpa o arquivo temporário
            if os.path.exists(caminho_arquivo): 
                os.remove(caminho_arquivo)
                
            return True, f"Base de Cidades processada! {len(ListaCidades)} registros importados."

        except Exception as e:
            Sessao.rollback()
            LogService.Error("CidadesService", "Falha crítica no processamento de cidades.", e)
            return False, f"Falha crítica no processamento: {e}"
        finally:
            Sessao.close()