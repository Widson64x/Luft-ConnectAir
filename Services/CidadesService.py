import os
import pandas as pd
from datetime import date
from sqlalchemy import desc
from Conexoes import ObterSessaoPostgres
from Configuracoes import ConfiguracaoBase
from Models.POSTGRES.Cidade import RemessaCidade, Cidade

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

    @staticmethod
    def ListarRemessas():
        """
        Lista o histórico de uploads (Quem subiu, quando e se está ativo).
        """
        Sessao = ObterSessaoPostgres()
        try:
            return Sessao.query(RemessaCidade).order_by(desc(RemessaCidade.DataUpload)).all()
        finally:
            Sessao.close()

    @staticmethod
    def ExcluirRemessa(id_remessa):
        """
        Apaga um lote de cidades inteiro. Thanos Snap. 🫰
        """
        Sessao = ObterSessaoPostgres()
        try:
            Remessa = Sessao.query(RemessaCidade).get(id_remessa)
            if Remessa:
                Sessao.delete(Remessa)
                Sessao.commit()
                return True, "Base de cidades excluída com sucesso."
            return False, "Remessa não encontrada."
        except Exception as e:
            Sessao.rollback()
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
            CidadesService._GarantirDiretorio()
            
            CaminhoTemp = os.path.join(CidadesService.DIR_TEMP, file_storage.filename)
            file_storage.save(CaminhoTemp)
            
            # Data de Referência é Hoje (Cadastro Estático: Mês Atual)
            Hoje = date.today()
            DataRef = date(Hoje.year, Hoje.month, 1)

            Sessao = ObterSessaoPostgres()
            ExisteConflito = False
            try:
                # Verifica se já tem uma remessa ativa para este mês
                Anterior = Sessao.query(RemessaCidade).filter_by(MesReferencia=DataRef, Ativo=True).first()
                if Anterior:
                    ExisteConflito = True
            finally:
                Sessao.close()

            return True, {
                'caminho_temp': CaminhoTemp,
                'mes_ref': DataRef,
                'nome_arquivo': file_storage.filename,
                'conflito': ExisteConflito
            }
        except Exception as e:
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
        Sessao = ObterSessaoPostgres()
        try:
            # 1. Ler Excel (engine openpyxl para .xlsx)
            # header=None pois o arquivo parece não ter cabeçalho padrão ou é processado bruto
            DfRaw = pd.read_excel(caminho_arquivo, header=None, engine='openpyxl')
            
            # Pega a primeira coluna (índice 0) que contém o texto concatenado
            SerieDados = DfRaw.iloc[:, 0].astype(str)

            # 2. Desativar remessa anterior (se houver)
            Anterior = Sessao.query(RemessaCidade).filter_by(MesReferencia=data_ref, Ativo=True).first()
            if Anterior:
                Anterior.Ativo = False

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

            # Limpa o arquivo temporário
            if os.path.exists(caminho_arquivo): 
                os.remove(caminho_arquivo)
                
            return True, f"Base de Cidades processada! {len(ListaCidades)} registros importados."

        except Exception as e:
            Sessao.rollback()
            return False, f"Falha crítica no processamento: {e}"
        finally:
            Sessao.close()