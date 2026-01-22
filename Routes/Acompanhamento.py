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
            'Acompanhamento/Index.html', 
            resumo=resumo, 
            data_inicio=hoje, 
            data_fim=hoje
        )
    except:
        hoje = datetime.now().strftime('%Y-%m-%d')
        return render_template('Acompanhamento/Index.html', resumo={}, data_inicio=hoje, data_fim=hoje)

@AcompanhamentoBP.route('/Api/ListarAwbs', methods=['GET'])
def ApiListarAwbs():
    filtros = {
        'DataInicio': request.args.get('dataInicio'),
        'DataFim': request.args.get('dataFim'),
        'NumeroAwb': request.args.get('numeroAwb'),
        'FilialCtc': request.args.get('filialCtc') # <--- Captura o novo filtro
    }
    dados = AcompanhamentoService.ListarAwbs(filtros)
    return jsonify(dados)

@AcompanhamentoBP.route('/Api/Historico/<path:numero_awb>', methods=['GET'])
def ApiHistorico(numero_awb):
    historico = AcompanhamentoService.ObterHistoricoAwb(numero_awb)
    return jsonify(historico)

@AcompanhamentoBP.route('/Api/DetalhesVooModal', methods=['GET'])
def ApiDetalhesVooModal():
    numero = request.args.get('numeroVoo')
    data = request.args.get('dataRef') # Espera formato dd/mm/yyyy HH:MM ou yyyy-mm-dd
    
    detalhes = AcompanhamentoService.BuscarDetalhesVooModal(numero, data)
    
    if detalhes:
        return jsonify({'sucesso': True, 'dados': detalhes})
    else:
        return jsonify({'sucesso': False, 'msg': 'Voo não encontrado na malha prevista.'})
    
@AcompanhamentoBP.route('/Api/DetalhesAwbModal', methods=['GET'])
def ApiDetalhesAwbModal():
    cod_awb = request.args.get('codAwb')
    if not cod_awb:
        return jsonify({'sucesso': False, 'msg': 'Código AWB não informado.'})
        
    dados = AcompanhamentoService.BuscarDetalhesAwbCompleto(cod_awb)
    
    if dados:
        return jsonify({'sucesso': True, 'dados': dados})
    else:
        return jsonify({'sucesso': False, 'msg': 'AWB não encontrada.'}) 
    