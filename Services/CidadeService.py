import os
import pandas as pd
from datetime import date
from sqlalchemy import desc
from Conexoes import ObterSessaoPostgres
from Models.POSTGRES.Cidade import RemessaCidade, Cidade

DIR_TEMP = 'Data/Temp_Cidades'
if not os.path.exists(DIR_TEMP):
    os.makedirs(DIR_TEMP)

def ListarRemessasCidades():
    Sessao = ObterSessaoPostgres()
    try:
        return Sessao.query(RemessaCidade).order_by(desc(RemessaCidade.DataUpload)).all()
    finally:
        Sessao.close()

def ExcluirRemessaCidade(IdRemessa):
    Sessao = ObterSessaoPostgres()
    try:
        Remessa = Sessao.query(RemessaCidade).get(IdRemessa)
        if Remessa:
            Sessao.delete(Remessa)
            Sessao.commit()
            return True, "Base de cidades excluída."
        return False, "Remessa não encontrada."
    except Exception as e:
        Sessao.rollback()
        return False, f"Erro: {e}"
    finally:
        Sessao.close()

def AnalisarArquivoCidades(FileStorage):
    try:
        CaminhoTemp = os.path.join(DIR_TEMP, FileStorage.filename)
        FileStorage.save(CaminhoTemp)
        
        # Data de Referência é Hoje (Cadastro Estático)
        Hoje = date.today()
        DataRef = date(Hoje.year, Hoje.month, 1)

        Sessao = ObterSessaoPostgres()
        ExisteConflito = False
        try:
            Anterior = Sessao.query(RemessaCidade).filter_by(MesReferencia=DataRef, Ativo=True).first()
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
        return False, f"Erro ao analisar: {e}"

def ProcessarCidadesFinal(CaminhoArquivo, DataRef, NomeOriginal, Usuario, TipoAcao):
    Sessao = ObterSessaoPostgres()
    try:
        # 1. Ler Excel (header=None para pegar a primeira linha como dados também)
        # O arquivo é XLSX, mas tem tudo numa coluna só separado por ;
        DfRaw = pd.read_excel(CaminhoArquivo, header=None, engine='openpyxl')
        
        # Pega a primeira coluna (índice 0) que contém o texto concatenado
        SerieDados = DfRaw.iloc[:, 0].astype(str)

        # 2. Desativar anterior
        Anterior = Sessao.query(RemessaCidade).filter_by(MesReferencia=DataRef, Ativo=True).first()
        if Anterior:
            Anterior.Ativo = False

        # 3. Criar Cabeçalho da Remessa
        NovaRemessa = RemessaCidade(
            MesReferencia=DataRef,
            NomeArquivoOriginal=NomeOriginal,
            UsuarioResponsavel=Usuario,
            TipoAcao=TipoAcao,
            Ativo=True
        )
        Sessao.add(NovaRemessa)
        Sessao.flush()

        # 4. Processar Linha a Linha (Parsing Manual)
        ListaCidades = []
        
        for Linha in SerieDados:
            # Limpeza: Remove aspas duplas e espaços
            # Ex entrada: "123";"SP";"Sao Paulo"
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
                # Tratamento de erro na conversão
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
                continue # Pula linha se der erro de conversão (cabeçalho ou sujeira)

        # Bulk Insert (Muito mais rápido)
        Sessao.bulk_save_objects(ListaCidades)
        Sessao.commit()

        if os.path.exists(CaminhoArquivo): os.remove(CaminhoArquivo)
        return True, f"Base de Cidades atualizada! {len(ListaCidades)} registros."

    except Exception as e:
        Sessao.rollback()
        return False, f"Erro ao processar: {e}"
    finally:
        Sessao.close()