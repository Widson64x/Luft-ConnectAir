from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from datetime import timedelta, datetime, date

# Import dos Serviços
from Services.PlanejamentoService import BuscarCtcsAereoHoje, ObterCtcDetalhado
from Services.GeografiaService import BuscarCoordenadasCidade, BuscarAeroportoMaisProximo
from Services.MalhaService import BuscarRotasInteligentes

PlanejamentoBp = Blueprint('Planejamento', __name__)

@PlanejamentoBp.route('/Dashboard')
@login_required
def Dashboard():
    return render_template('Planejamento/Dashboard.html')

@PlanejamentoBp.route('/API/CTCs-Hoje')
@login_required
def ApiCtcsHoje():
    Dados = BuscarCtcsAereoHoje()
    return jsonify(Dados)

@PlanejamentoBp.route('/montar/<string:filial>/<string:serie>/<string:ctc>')
@login_required
def MontarPlanejamento(filial, serie, ctc):
    
    # 1. Dados
    DadosCtc = ObterCtcDetalhado(filial, serie, ctc)
    if not DadosCtc: return "Não encontrado", 404

    # 2. Geografia
    CoordOrigem = BuscarCoordenadasCidade(DadosCtc['origem_cidade'], DadosCtc['origem_uf'])
    CoordDestino = BuscarCoordenadasCidade(DadosCtc['destino_cidade'], DadosCtc['destino_uf'])
    
    if not CoordOrigem or not CoordDestino:
        return render_template('Planejamento/Montar.html', Erro="Erro Geo", Ctc=DadosCtc)

    # 3. Aeroportos
    AeroOrigem = BuscarAeroportoMaisProximo(CoordOrigem['lat'], CoordOrigem['lon'])
    AeroDestino = BuscarAeroportoMaisProximo(CoordDestino['lat'], CoordDestino['lon'])

    # 4. Busca
    RotasSugeridas = []
    if AeroOrigem and AeroDestino:
        # AQUI O SEGREDO: Usamos a data calculada (+3h) para a busca
        DataInicioBusca = DadosCtc['data_busca'] 
        
        for Dias in [3, 10, 30]:
            DataLimite = DataInicioBusca + timedelta(days=Dias)
            RotasSugeridas = BuscarRotasInteligentes(
                DataInicioBusca, # <--- VAI FILTRAR VOOS APÓS 12:22
                DataLimite, 
                AeroOrigem['iata'], AeroDestino['iata']
            )
            if RotasSugeridas: break

    return render_template('Planejamento/Montar.html', 
                           Ctc=DadosCtc, 
                           Origem=CoordOrigem, Destino=CoordDestino,
                           AeroOrigem=AeroOrigem, AeroDestino=AeroDestino,
                           Rotas=RotasSugeridas)
    
@PlanejamentoBp.route('/mapa-global')
@login_required
def MapaGlobal():
    # 1. Pega todos os CTCs aéreos de hoje
    ListaCtcs = BuscarCtcsAereoHoje()
    
    DadosMapa = []
    
    print(f"🌍 Gerando Mapa Global para {len(ListaCtcs)} CTCs...")

    for c in ListaCtcs:
        try:
            # Separa cidade/UF (formato "Cidade/UF")
            CidadeOrig, UfOrig = c['origem'].split('/')
            CidadeDest, UfDest = c['destino'].split('/')
            
            # Busca Coordenadas
            CoordO = BuscarCoordenadasCidade(CidadeOrig, UfOrig)
            CoordD = BuscarCoordenadasCidade(CidadeDest, UfDest)
            
            if CoordO and CoordD:
                # Busca Aeroportos
                AeroO = BuscarAeroportoMaisProximo(CoordO['lat'], CoordO['lon'])
                AeroD = BuscarAeroportoMaisProximo(CoordD['lat'], CoordD['lon'])
                
                if AeroO and AeroD:
                    DadosMapa.append({
                        'id': c['id_unico'],
                        'filial': c['filial'], # <--- IMPORTANTE
                        'serie': c['serie'],   # <--- AQUI ESTÁ A CORREÇÃO
                        'ctc': c['ctc'],
                        'valor': c['val_mercadoria'],
                        'peso': c['peso_taxado'],
                        'origem': CoordO,
                        'destino': CoordD,
                        'aero_origem': AeroO,
                        'aero_destino': AeroD
                    })
        except Exception as e:
            print(f"Erro ao processar CTC {c.get('ctc')}: {e}")
            continue

    return render_template('Planejamento/MapaGlobal.html', Dados=DadosMapa)