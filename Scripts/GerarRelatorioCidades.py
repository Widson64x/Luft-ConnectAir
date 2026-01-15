import os
import pandas as pd
from bs4 import BeautifulSoup

def processar_kmls_para_excel(pasta_raiz, nome_arquivo_saida):
    """
    Percorre pastas, lê arquivos KML e gera um Excel consolidado.
    """
    print(f"--- Iniciando processamento na pasta: {pasta_raiz} ---")
    
    # Lista para guardar todas as linhas de dados encontradas
    todos_dados = []
    
    # Contador para acompanharmos o progresso
    arquivos_processados = 0

    # 1. Navegar por todas as pastas e subpastas
    for raiz, pastas, arquivos in os.walk(pasta_raiz):
        for arquivo in arquivos:
            if arquivo.lower().endswith('.kml'):
                caminho_completo = os.path.join(raiz, arquivo)
                
                # O nome da pasta pai geralmente é o Estado (ex: TO, SP)
                nome_pasta_estado = os.path.basename(raiz)
                
                try:
                    # 2. Abrir e Ler o KML
                    with open(caminho_completo, 'r', encoding='utf-8') as f:
                        conteudo_xml = f.read()
                    
                    # Usamos 'xml' como parser para entender a estrutura do KML
                    soup = BeautifulSoup(conteudo_xml, 'xml')
                    
                    # 3. Encontrar todos os Placemarks (cada cidade/localidade)
                    placemarks = soup.find_all('Placemark')
                    
                    for placemark in placemarks:
                        # Dicionário para guardar os dados desta linha
                        linha = {
                            'Estado_Origem': nome_pasta_estado,
                            'Nome_Arquivo': arquivo,
                            'Nome_Placemark': placemark.find('name').text if placemark.find('name') else ''
                        }
                        
                        # Extrair dados estendidos (SimpleData)
                        # É aqui que estão: NM_MUN, SIGLA_UF, NM_LOCALIDADE, etc.
                        extended_data = placemark.find_all('SimpleData')
                        for data in extended_data:
                            nome_campo = data.get('name') # Ex: NM_MUN
                            valor_campo = data.text       # Ex: Aragominas
                            linha[nome_campo] = valor_campo

                        # Extrair Coordenadas (Geometria)
                        # Pode ser um Ponto ou Polígono
                        coords_tag = placemark.find('coordinates')
                        if coords_tag:
                            # Limpa quebras de linha e espaços extras
                            linha['Coordenadas_Geo'] = coords_tag.text.strip().replace('\n', ' ')
                        else:
                            linha['Coordenadas_Geo'] = ''

                        # Adiciona a linha à lista geral
                        todos_dados.append(linha)
                    
                    arquivos_processados += 1
                    print(f"Lido: {arquivo} ({len(placemarks)} locais)")

                except Exception as e:
                    print(f"Erro ao ler {arquivo}: {e}")

    # 4. Gerar o Excel
    if todos_dados:
        print("--- Gerando arquivo Excel... ---")
        df = pd.DataFrame(todos_dados)
        
        # Organizando colunas: colocar Cidade e UF primeiro se existirem
        colunas_prioridade = ['Estado_Origem', 'NM_MUN', 'SIGLA_UF', 'NM_LOCALIDADE', 'Coordenadas_Geo']
        # Pega as colunas que realmente existem no DataFrame
        colunas_existentes = [c for c in colunas_prioridade if c in df.columns]
        # O restante das colunas
        outras_colunas = [c for c in df.columns if c not in colunas_existentes]
        
        # Reordena
        df = df[colunas_existentes + outras_colunas]

        df.to_excel(nome_arquivo_saida, index=False)
        print(f"Sucesso! Arquivo gerado: {nome_arquivo_saida}")
        print(f"Total de arquivos lidos: {arquivos_processados}")
        print(f"Total de registros extraídos: {len(df)}")
    else:
        print("Nenhum dado encontrado ou nenhum arquivo KML válido processado.")

# --- Configuração ---
# O 'r' antes das aspas ajuda o Python a lidar com as barras invertidas do Windows
caminho_da_pasta = r'C:\Users\widson.araujo\Downloads\kml' 
nome_do_excel = 'Data\Relatorio_Geral_Cidades.xlsx'

# Executar a função
processar_kmls_para_excel(caminho_da_pasta, nome_do_excel)