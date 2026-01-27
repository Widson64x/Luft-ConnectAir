from datetime import datetime
from flask import Blueprint, render_template, request, jsonify
from Services.AcompanhamentoService import AcompanhamentoService
from Services.LogService import LogService

AcompanhamentoBP = Blueprint('Acompanhamento', __name__, url_prefix='/Acompanhamento')

@AcompanhamentoBP.route('/Painel', methods=['GET'])
def Painel():
    LogService.Info("AcompanhamentoRoute", "Acessando rota /Painel.")
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
    except Exception as e:
        LogService.Error("AcompanhamentoRoute", "Erro ao renderizar Painel.", e)
        hoje = datetime.now().strftime('%Y-%m-%d')
        return render_template('Acompanhamento/Index.html', resumo={}, data_inicio=hoje, data_fim=hoje)

@AcompanhamentoBP.route('/Api/ListarAwbs', methods=['GET'])
def ApiListarAwbs():
    filtros = {
        'DataInicio': request.args.get('dataInicio'),
        'DataFim': request.args.get('dataFim'),
        'NumeroAwb': request.args.get('numeroAwb'),
        'FilialCtc': request.args.get('filialCtc') 
    }
    LogService.Debug("AcompanhamentoRoute", f"API /ListarAwbs chamada. Parametros: {filtros}")
    dados = AcompanhamentoService.ListarAwbs(filtros)
    return jsonify(dados)

@AcompanhamentoBP.route('/Api/Historico/<path:numero_awb>', methods=['GET'])
def ApiHistorico(numero_awb):
    LogService.Debug("AcompanhamentoRoute", f"API /Historico chamada para {numero_awb}")
    historico = AcompanhamentoService.ObterHistoricoAwb(numero_awb)
    return jsonify(historico)

@AcompanhamentoBP.route('/Api/DetalhesVooModal', methods=['GET'])
def ApiDetalhesVooModal():
    numero = request.args.get('numeroVoo')
    data = request.args.get('dataRef') 
    
    LogService.Debug("AcompanhamentoRoute", f"API /DetalhesVooModal chamada para voo {numero} em {data}")
    detalhes = AcompanhamentoService.BuscarDetalhesVooModal(numero, data)
    
    if detalhes:
        return jsonify({'sucesso': True, 'dados': detalhes})
    else:
        return jsonify({'sucesso': False, 'msg': 'Voo não encontrado na malha prevista.'})
    
@AcompanhamentoBP.route('/Api/DetalhesAwbModal', methods=['GET'])
def ApiDetalhesAwbModal():
    cod_awb = request.args.get('codAwb')
    LogService.Debug("AcompanhamentoRoute", f"API /DetalhesAwbModal chamada. ID: {cod_awb}")
    
    if not cod_awb:
        LogService.Warning("AcompanhamentoRoute", "API /DetalhesAwbModal chamada sem codAwb.")
        return jsonify({'sucesso': False, 'msg': 'Código AWB não informado.'})
        
    dados = AcompanhamentoService.BuscarDetalhesAwbCompleto(cod_awb)
    
    if dados:
        return jsonify({'sucesso': True, 'dados': dados})
    else:
        return jsonify({'sucesso': False, 'msg': 'AWB não encontrada.'})