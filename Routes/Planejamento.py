from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from datetime import timedelta, datetime, date

# Import dos Serviços
from Services.PlanejamentoService import PlanejamentoService
from Services.Shared.GeoService import BuscarCoordenadasCidade, BuscarAeroportoMaisProximo
from Services.MalhaService import MalhaService

PlanejamentoBp = Blueprint('Planejamento', __name__)

COORDENADAS_UFS = {
    'AC': {'lat': -9.02, 'lon': -70.81}, 'AL': {'lat': -9.57, 'lon': -36.78},
    'AP': {'lat': 0.90, 'lon': -52.00},  'AM': {'lat': -3.41, 'lon': -65.87},
    'BA': {'lat': -12.57, 'lon': -41.70},'CE': {'lat': -5.49, 'lon': -39.32},
    'DF': {'lat': -15.79, 'lon': -47.88},'ES': {'lat': -19.18, 'lon': -40.30},
    'GO': {'lat': -15.82, 'lon': -49.83},'MA': {'lat': -4.96, 'lon': -45.27},
    'MT': {'lat': -12.68, 'lon': -56.92},'MS': {'lat': -20.77, 'lon': -54.78},
    'MG': {'lat': -18.51, 'lon': -44.55},'PA': {'lat': -1.99, 'lon': -54.93},
    'PB': {'lat': -7.23, 'lon': -36.78}, 'PR': {'lat': -25.25, 'lon': -52.02},
    'PE': {'lat': -8.81, 'lon': -36.95}, 'PI': {'lat': -7.71, 'lon': -42.72},
    'RJ': {'lat': -22.90, 'lon': -43.17},'RN': {'lat': -5.40, 'lon': -36.95},
    'RS': {'lat': -30.03, 'lon': -51.22},'RO': {'lat': -11.50, 'lon': -63.58},
    'RR': {'lat': 2.82, 'lon': -60.67},  'SC': {'lat': -27.24, 'lon': -50.21},
    'SP': {'lat': -23.55, 'lon': -46.63},'SE': {'lat': -10.57, 'lon': -37.38},
    'TO': {'lat': -10.17, 'lon': -48.33}
}

@PlanejamentoBp.route('/Dashboard')
@login_required
def Dashboard():
    return render_template('Planejamento/Index.html')

@PlanejamentoBp.route('/API/CTCs-Hoje')
@login_required
def ApiCtcsHoje():
    Dados = PlanejamentoService.BuscarCtcsAereoHoje()
    return jsonify(Dados)

@PlanejamentoBp.route('/API/Ctc-Detalhes/<string:filial>/<string:serie>/<string:ctc>')
@login_required
def ApiCtcDetalhes(filial, serie, ctc):
    Dados = PlanejamentoService.ObterCtcCompleto(filial, serie, ctc)
    if not Dados:
        return jsonify({'erro': 'CTC não encontrado'}), 404
    return jsonify(Dados)

@PlanejamentoBp.route('/Montar/<string:filial>/<string:serie>/<string:ctc>')
@login_required
def MontarPlanejamento(filial, serie, ctc):
    
    # 1. Dados
    DadosCtc = PlanejamentoService.ObterCtcDetalhado(filial, serie, ctc)
    if not DadosCtc: return "Não encontrado", 404

    # 2. Geografia
    CoordOrigem = BuscarCoordenadasCidade(DadosCtc['origem_cidade'], DadosCtc['origem_uf'])
    CoordDestino = BuscarCoordenadasCidade(DadosCtc['destino_cidade'], DadosCtc['destino_uf'])
    
    if not CoordOrigem or not CoordDestino:
        return render_template('Planejamento/Editor.html', Erro="Erro Geo", Ctc=DadosCtc)

    # 3. Consolidação - Busca CTCs com mesma origem/destino
    CtcsConsolidados = PlanejamentoService.BuscarCtcsConsolidaveis(
        DadosCtc['origem_cidade'], 
        DadosCtc['origem_uf'],
        DadosCtc['destino_cidade'], 
        DadosCtc['destino_uf'],
        DadosCtc['data_emissao_real'],
        filial,
        ctc
    )
    
    print(f"📦 Consolidação: Encontrados {len(CtcsConsolidados)} CTCs adicionais com mesma origem/destino")
    
    # Calcula totais consolidados
    TotaisConsolidados = {
        'qtd_ctcs': len(CtcsConsolidados) + 1,  # +1 para incluir o CTC principal
        'volumes_total': DadosCtc['volumes'] + sum(c['volumes'] for c in CtcsConsolidados),
        'peso_total': DadosCtc['peso'] + sum(c['peso_taxado'] for c in CtcsConsolidados),
        'valor_total': float(DadosCtc['valor']) + sum(c['val_mercadoria'] for c in CtcsConsolidados),
        'notas_total': sum(c['qtd_notas'] for c in CtcsConsolidados) + 1  # +1 estimado para o principal
    }

    # 4. Aeroportos
    AeroOrigem = BuscarAeroportoMaisProximo(CoordOrigem['lat'], CoordOrigem['lon'])
    AeroDestino = BuscarAeroportoMaisProximo(CoordDestino['lat'], CoordDestino['lon'])

    # 5. Busca de Rotas
    RotasSugeridas = []
    if AeroOrigem and AeroDestino:
        """
            AQUI O SEGREDO: Usamos a data calculada onde temos a hora real + margem (10 horas após a Emissão),
            conforme implementado em Services/PlanejamentoService.py para fazer A busca de rotas inteligentes a 
            partir dessa data/hora. Isso garante que não traremos voos que já partiram. E garantimos que a busca 
            sempre trará resultados, aumentando o intervalo de dias se necessário (3, 10, 30).
        """

        DataInicioBusca = DadosCtc['data_busca'] 
        print(f"🔍 Buscando rotas inteligentes de {AeroOrigem['iata']} para {AeroDestino['iata']} a partir de {DataInicioBusca}...")
        
        for Dias in [3, 10, 30]: # Busca progressiva, 3 dias, 10 dias, 30 dias, se necessário
            DataLimite = DataInicioBusca + timedelta(days=Dias)
            RotasSugeridas = MalhaService.BuscarRotasInteligentes(
                DataInicioBusca, # Vai dar Data/Hora calculada de Emissão do CTC + 10h
                DataLimite, 
                AeroOrigem['iata'], AeroDestino['iata']
            )
            if RotasSugeridas: break

    return render_template('Planejamento/Editor.html', 
                           Ctc=DadosCtc, 
                           Origem=CoordOrigem, Destino=CoordDestino,
                           AeroOrigem=AeroOrigem, AeroDestino=AeroDestino,
                           Rotas=RotasSugeridas,
                           CtcsConsolidados=CtcsConsolidados,
                           TotaisConsolidados=TotaisConsolidados)
    
@PlanejamentoBp.route('/Mapa-Global')
@login_required
def MapaGlobal():
    ListaCtcs = PlanejamentoService.BuscarCtcsAereoHoje()
    Agrupamento = {}

    print(f"🌍 Gerando Mapa Agrupado para {len(ListaCtcs)} CTCs...")

    for c in ListaCtcs:
        try:
            _, UfOrig = c['origem'].split('/')
            UfOrig = UfOrig.strip().upper()
            
            if UfOrig not in Agrupamento:
                Agrupamento[UfOrig] = {
                    'uf': UfOrig,
                    'coords': COORDENADAS_UFS.get(UfOrig, {'lat': -15, 'lon': -47}),
                    'qtd_docs': 0,
                    'qtd_vols': 0,
                    'valor_total': 0.0,
                    'tem_urgencia': False,
                    'lista_ctcs': []
                }
            
            # Atualiza Totais
            Agrupamento[UfOrig]['qtd_docs'] += 1
            Agrupamento[UfOrig]['qtd_vols'] += int(c['volumes'])
            
            # --- CORREÇÃO AQUI ---
            # Usa o valor bruto direto (float), sem converter string
            Agrupamento[UfOrig]['valor_total'] += c['raw_val_mercadoria']
            # ---------------------
            
            if 'URGENTE' in str(c['prioridade']).upper():
                Agrupamento[UfOrig]['tem_urgencia'] = True
                c['eh_urgente'] = True 
            else:
                c['eh_urgente'] = False

            Agrupamento[UfOrig]['lista_ctcs'].append(c)

        except Exception as e:
            print(f"Erro ao agrupar CTC {c.get('ctc')}: {e}")
            continue
    
    DadosMapa = list(Agrupamento.values())
    return render_template('Planejamento/Map.html', Dados=DadosMapa)