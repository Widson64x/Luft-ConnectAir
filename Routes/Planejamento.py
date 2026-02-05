from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from datetime import timedelta, datetime, date

# Import dos Serviços
from Services.PermissaoService import RequerPermissao
from Services.PlanejamentoService import PlanejamentoService
from Services.Shared.GeoService import BuscarCoordenadasCidade, BuscarAeroportoMaisProximo
from Services.MalhaService import MalhaService
from Services.LogService import LogService  # <--- Import Adicionado

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
@RequerPermissao('planejamento.visualizar')
def Dashboard():
    LogService.Info("Routes.Planejamento", f"Usuário {current_user.id} acessou Dashboard Planejamento.")
    return render_template('Planejamento/Index.html')

@PlanejamentoBp.route('/API/Listar')
@login_required
@RequerPermissao('planejamento.visualizar')
def ApiCtcsHoje():
    # Log de Debug para não poluir o histórico principal com chamadas de API frequentes
    LogService.Debug("Routes.Planejamento", "API Listar CTCs requisitada.")
    Dados = PlanejamentoService.BuscarCtcsAereoHoje()
    return jsonify(Dados)

@PlanejamentoBp.route('/Montar/<string:filial>/<string:serie>/<string:ctc>')
@login_required
@RequerPermissao('planejamento.editar')
def MontarPlanejamento(filial, serie, ctc):
    LogService.Info("Routes.Planejamento", f"Iniciando Montagem Planejamento: {filial}-{serie}-{ctc}")
    
    # 1. Busca Dados do CTC Principal
    DadosCtc = PlanejamentoService.ObterCtcDetalhado(filial, serie, ctc)
    if not DadosCtc: 
        LogService.Error("Routes.Planejamento", f"Erro ao montar: CTC Base não encontrado {filial}-{serie}-{ctc}")
        return "Não encontrado", 404

    # 2. Geografia
    CoordOrigem = BuscarCoordenadasCidade(DadosCtc['origem_cidade'], DadosCtc['origem_uf'])
    CoordDestino = BuscarCoordenadasCidade(DadosCtc['destino_cidade'], DadosCtc['destino_uf'])
    
    if not CoordOrigem or not CoordDestino:
        LogService.Warning("Routes.Planejamento", f"Falha de Geolocalização para {DadosCtc['origem_cidade']} ou {DadosCtc['destino_cidade']}")
        return render_template('Planejamento/Editor.html', Erro="Erro Geo", Ctc=DadosCtc)

    # 3. Consolidação
    CtcsCandidatos = PlanejamentoService.BuscarCtcsConsolidaveis(
        DadosCtc['origem_cidade'], 
        DadosCtc['origem_uf'],
        DadosCtc['destino_cidade'], 
        DadosCtc['destino_uf'],
        DadosCtc['data_emissao_real'],
        filial,
        ctc,
        DadosCtc['tipo_carga']
    )
    
    # Unifica (Apenas memória, NÃO GRAVA AINDA)
    DadosUnificados = PlanejamentoService.UnificarConsolidacao(DadosCtc, CtcsCandidatos)

    # 4. Aeroportos
    AeroOrigem = BuscarAeroportoMaisProximo(CoordOrigem['lat'], CoordOrigem['lon'])
    AeroDestino = BuscarAeroportoMaisProximo(CoordDestino['lat'], CoordDestino['lon'])

    # 5. Busca de Rotas
    RotasSugeridas = []
    if AeroOrigem and AeroDestino:
        DataInicioBusca = DadosUnificados['data_busca'] 
        for Dias in [3, 10, 30]:
            DataLimite = DataInicioBusca + timedelta(days=Dias)
            RotasSugeridas = MalhaService.BuscarRotasInteligentes(
                DataInicioBusca, DataLimite, AeroOrigem['iata'], AeroDestino['iata']
            )
            if RotasSugeridas: break

    return render_template('Planejamento/Editor.html', 
                           Ctc=DadosUnificados, 
                           Origem=CoordOrigem, Destino=CoordDestino,
                           AeroOrigem=AeroOrigem, AeroDestino=AeroDestino,
                           Rotas=RotasSugeridas)

@PlanejamentoBp.route('/API/Salvar', methods=['POST'])
@login_required
@RequerPermissao('planejamento.editar')
def SalvarPlanejamento():
    try:
        dados_front = request.json
        if not dados_front: return jsonify({'sucesso': False}), 400

        filial = dados_front.get('filial')
        serie = dados_front.get('serie')
        ctc = dados_front.get('ctc')
        
        LogService.Info("Routes.Planejamento", f"Recebendo requisição de salvamento para {filial}-{serie}-{ctc}")

        # Recebe a lista completa de voos (rota)
        rota_completa = dados_front.get('rota_completa', []) 

        DadosCtc = PlanejamentoService.ObterCtcDetalhado(filial, serie, ctc)
        CtcsCandidatos = PlanejamentoService.BuscarCtcsConsolidaveis(
            DadosCtc['origem_cidade'], DadosCtc['origem_uf'],
            DadosCtc['destino_cidade'], DadosCtc['destino_uf'],
            DadosCtc['data_emissao_real'], filial, ctc,
            DadosCtc['tipo_carga']
        )
        DadosUnificados = PlanejamentoService.UnificarConsolidacao(DadosCtc, CtcsCandidatos)
        
        # Geografia
        CoordOrigem = BuscarCoordenadasCidade(DadosCtc['origem_cidade'], DadosCtc['origem_uf'])
        CoordDestino = BuscarCoordenadasCidade(DadosCtc['destino_cidade'], DadosCtc['destino_uf'])
        AeroOrigem = BuscarAeroportoMaisProximo(CoordOrigem['lat'], CoordOrigem['lon']) if CoordOrigem else None
        AeroDestino = BuscarAeroportoMaisProximo(CoordDestino['lat'], CoordDestino['lon']) if CoordDestino else None
        
        # Grava
        Id = PlanejamentoService.RegistrarPlanejamento(
            DadosUnificados, 
            CtcsCandidatos, 
            current_user.id if current_user.is_authenticated else "Anonimo",
            status_inicial='Em Planejamento',
            aero_origem=AeroOrigem['iata'] if AeroOrigem else None,
            aero_destino=AeroDestino['iata'] if AeroDestino else None,
            lista_trechos=rota_completa
        )
        
        if Id: 
            LogService.Info("Routes.Planejamento", f"Planejamento salvo com sucesso. ID Retornado: {Id}")
            return jsonify({'sucesso': True, 'id_planejamento': Id})
        
        LogService.Error("Routes.Planejamento", "Service retornou None ao salvar.")
        return jsonify({'sucesso': False, 'msg': 'Erro ao gravar'}), 500

    except Exception as e:
        LogService.Error("Routes.Planejamento", "Exceção não tratada ao salvar planejamento", e)
        return jsonify({'sucesso': False, 'msg': str(e)}), 500
    
@PlanejamentoBp.route('/Mapa-Global')
@login_required
@RequerPermissao('planejamento.mapa')
def MapaGlobal():
    try:
        LogService.Debug("Routes.Planejamento", "Gerando Mapa Global...")
        ListaCtcs = PlanejamentoService.BuscarCtcsAereoHoje()
        Agrupamento = {}

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
                LogService.Warning("Routes.Planejamento", f"Erro ao agrupar item no mapa: {e}")
                continue
        
        DadosMapa = list(Agrupamento.values())
        return render_template('Planejamento/Map.html', Dados=DadosMapa)
    except Exception as e:
        LogService.Error("Routes.Planejamento", "Erro fatal ao renderizar Mapa Global", e)
        return "Erro interno", 500