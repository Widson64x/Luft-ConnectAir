from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required
from datetime import datetime
from Services.Logic.RouteIntelligenceService import RouteIntelligenceService
from Services.PermissaoService import RequerPermissao

EscalasBp = Blueprint('Escalas', __name__)

@EscalasBp.route('/Mapa')
@login_required
@RequerPermissao('CADASTROS.MALHA.VISUALIZAR')
def mapa():
    return render_template('Pages/Escalas/Index.html')

@EscalasBp.route('/Api/OtimizarRotas', methods=['GET'])
@login_required
@RequerPermissao('CADASTROS.MALHA.VISUALIZAR')
def apiOtimizarRotas():
    try:
        dataInicioStr = request.args.get('inicio')
        dataFimStr = request.args.get('fim')
        origemBusca = request.args.get('origem', '').upper()
        destinoBusca = request.args.get('destino', '').upper()
        pesoStr = request.args.get('peso', '100')

        if not (dataInicioStr and dataFimStr and origemBusca and destinoBusca):
            return jsonify({'erro': 'Parâmetros incompletos.'}), 400

        try:
            dtInicio = datetime.strptime(dataInicioStr, '%Y-%m-%d')
            dtFim = datetime.strptime(dataFimStr, '%Y-%m-%d')
            pesoTotalBusca = float(pesoStr)
        except ValueError:
            return jsonify({'erro': 'Formato de data ou peso inválido.'}), 400

        opcoesRotas = RouteIntelligenceService.BuscarOpcoesDeRotas(
            data_inicio=dtInicio,
            data_fim=dtFim,
            lista_origens=origemBusca,   
            lista_destinos=destinoBusca, 
            peso_total=pesoTotalBusca
        )

        totalRotas = sum(1 for v in opcoesRotas.values() if v)
        if totalRotas == 0:
            return jsonify({'status': 'vazio', 'mensagem': 'Nenhuma combinação de rotas encontrada para estes parâmetros.'})

        return jsonify({'status': 'sucesso', 'dados': opcoesRotas})

    except Exception as e:
        return jsonify({'erro': f'Erro interno: {str(e)}'}), 500