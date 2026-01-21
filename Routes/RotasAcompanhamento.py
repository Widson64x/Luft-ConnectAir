from datetime import datetime
from flask import Blueprint, render_template, request, jsonify
from Services.AcompanhamentoService import AcompanhamentoService

AcompanhamentoBP = Blueprint('Acompanhamento', __name__, url_prefix='/Acompanhamento')

@AcompanhamentoBP.route('/Painel', methods=['GET'])
def Painel():
    try:
        resumo = AcompanhamentoService.BuscarResumoPainel()
        
        # Define padrão: Hoje até Hoje (ou últimos 3 dias se preferir)
        hoje = datetime.now().strftime('%Y-%m-%d')
        
        return render_template(
            'Acompanhamento/Painel.html', 
            resumo=resumo, 
            data_inicio=hoje, 
            data_fim=hoje
        )
    except:
        hoje = datetime.now().strftime('%Y-%m-%d')
        return render_template('Acompanhamento/Painel.html', resumo={}, data_inicio=hoje, data_fim=hoje)

@AcompanhamentoBP.route('/Api/ListarAwbs', methods=['GET'])
def ApiListarAwbs():
    filtros = {
        'DataInicio': request.args.get('dataInicio'),
        'DataFim': request.args.get('dataFim'),
        'NumeroAwb': request.args.get('numeroAwb')
    }
    dados = AcompanhamentoService.ListarAwbs(filtros)
    return jsonify(dados)

@AcompanhamentoBP.route('/Api/Historico/<path:numero_awb>', methods=['GET'])
def ApiHistorico(numero_awb):
    historico = AcompanhamentoService.ObterHistoricoAwb(numero_awb)
    return jsonify(historico)