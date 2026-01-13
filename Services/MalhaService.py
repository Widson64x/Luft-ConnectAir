import os
import pandas as pd
from datetime import datetime
from sqlalchemy import desc
from Conexoes import ObterSessaoPostgres
from Models.POSTGRES.MalhaAerea import RemessaMalha, VooMalha
from Utils.Formatadores import PadronizarData

# Pasta temporária para guardar o arquivo enquanto o usuário confirma
DIR_TEMP = 'Temp_Uploads'
if not os.path.exists(DIR_TEMP):
    os.makedirs(DIR_TEMP)

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
    """
    Passo 1: Salva o arquivo temporariamente, lê a data e verifica se já existe malha ativa.
    Retorna: (Status, InfoDict ou MensagemErro)
    """
    try:
        # Salva em pasta temporária
        CaminhoTemp = os.path.join(DIR_TEMP, FileStorage.filename)
        FileStorage.save(CaminhoTemp)
        
        # Lê o Excel
        Df = pd.read_excel(CaminhoTemp, engine='openpyxl')
        Df.columns = [c.strip().upper() for c in Df.columns]
        
        ColunaData = next((col for col in ['DIA', 'DATA'] if col in Df.columns), None)
        if not ColunaData:
            return False, "Coluna de DATA não encontrada."

        # Pega a primeira data válida para definir o mês
        PrimeiraData = PadronizarData(Df[ColunaData].iloc[0])
        if not PrimeiraData:
            return False, "Não foi possível ler a data do arquivo."
            
        DataRef = PrimeiraData.replace(day=1) # 01/MM/YYYY
        
        # Verifica conflito no Banco
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
    """
    Passo 2: Efetiva a gravação no banco (Desativa anterior e Insere nova).
    """
    Sessao = ObterSessaoPostgres()
    try:
        # Lê novamente do temp
        Df = pd.read_excel(CaminhoArquivo, engine='openpyxl')
        Df.columns = [c.strip().upper() for c in Df.columns]
        ColunaData = next((col for col in ['DIA', 'DATA'] if col in Df.columns), None)
        
        # Aplica padronização em tudo
        Df['DATA_PADRAO'] = Df[ColunaData].apply(PadronizarData)
        Df = Df.dropna(subset=['DATA_PADRAO'])

        # Se for Substituição ou Importação nova, desativa a anterior (Garante integridade)
        RemessaAnterior = Sessao.query(RemessaMalha).filter_by(MesReferencia=DataRef, Ativo=True).first()
        if RemessaAnterior:
            RemessaAnterior.Ativo = False

        # Cria Nova Remessa
        NovaRemessa = RemessaMalha(
            MesReferencia=DataRef,
            NomeArquivoOriginal=NomeOriginal,
            UsuarioResponsavel=Usuario,
            TipoAcao=TipoAcao, # <--- Gravamos se foi Importação ou Substituição
            Ativo=True
        )
        Sessao.add(NovaRemessa)
        Sessao.flush()

        # Insere Voos (Mesma lógica de antes)
        ListaVoos = []
        for _, Linha in Df.iterrows():
             # ... (Lógica de horários igual à anterior) ...
            try:
                H_Saida = pd.to_datetime(str(Linha['HORÁRIO DE SAIDA']), format='%H:%M:%S', errors='coerce').time() if str(Linha['HORÁRIO DE SAIDA']) != 'nan' else datetime.min.time()
                H_Chegada = pd.to_datetime(str(Linha['HORÁRIO DE CHEGADA']), format='%H:%M:%S', errors='coerce').time() if str(Linha['HORÁRIO DE CHEGADA']) != 'nan' else datetime.min.time()
            except:
                 H_Saida = datetime.min.time()
                 H_Chegada = datetime.min.time()

            Voo = VooMalha(
                IdRemessa=NovaRemessa.Id,
                CiaAerea=str(Linha['CIA']),
                NumeroVoo=str(Linha['Nº VOO']),
                DataPartida=Linha['DATA_PADRAO'],
                AeroportoOrigem=str(Linha['ORIGEM']),
                HorarioSaida=H_Saida,
                HorarioChegada=H_Chegada,
                AeroportoDestino=str(Linha['DESTINO'])
            )
            ListaVoos.append(Voo)

        Sessao.bulk_save_objects(ListaVoos)
        Sessao.commit()
        
        # Limpa arquivo temporário
        if os.path.exists(CaminhoArquivo):
            os.remove(CaminhoArquivo)
            
        return True, f"Malha de {DataRef.strftime('%m/%Y')} processada com sucesso! ({TipoAcao})"

    except Exception as e:
        Sessao.rollback()
        return False, f"Erro ao gravar: {e}"
    finally:
        Sessao.close()