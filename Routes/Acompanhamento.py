from datetime import datetime
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from Services.AcompanhamentoService import AcompanhamentoService
from Services.LogService import LogService
from Services.PermissaoService import RequerPermissao
from luftcore.extensions.flask_extension import require_ajax

AcompanhamentoBP = Blueprint('Acompanhamento', __name__)

@AcompanhamentoBP.route('/Painel', methods=['GET'])
@login_required
@RequerPermissao('ACOMPANHAMENTO.PAINEL.VISUALIZAR')
def painel():
    LogService.Info("AcompanhamentoRoute", "Acessando rota /Painel.")
    try:
        dadosResumo = AcompanhamentoService.BuscarResumoPainel()
        
        dataHoje = datetime.now().strftime('%Y-%m-%d')
        
        return render_template(
            'Pages/Acompanhamento/Index.html', 
            resumo=dadosResumo, 
            data_inicio=dataHoje, 
            data_fim=dataHoje
        )
    except Exception as e:
        LogService.Error("AcompanhamentoRoute", "Erro ao renderizar Painel.", e)
        dataHoje = datetime.now().strftime('%Y-%m-%d')
        return render_template('Pages/Acompanhamento/Index.html', resumo={}, data_inicio=dataHoje, data_fim=dataHoje)

@AcompanhamentoBP.route('/Api/ListarAwbs', methods=['GET'])
@login_required
@require_ajax
@RequerPermissao('ACOMPANHAMENTO.PAINEL.VISUALIZAR')
def apiListarAwbs():
    dictFiltros = {
        'DataInicio': request.args.get('dataInicio'),
        'DataFim': request.args.get('dataFim'),
        'NumeroAwb': request.args.get('numeroAwb'),
        'FilialCtc': request.args.get('filialCtc') 
    }
    LogService.Debug("AcompanhamentoRoute", f"API /ListarAwbs chamada. Parametros: {dictFiltros}")
    listaDados = AcompanhamentoService.ListarAwbs(dictFiltros)
    return jsonify(listaDados)

@AcompanhamentoBP.route('/Api/Historico/<path:numero_awb>', methods=['GET'])
@login_required
@require_ajax
@RequerPermissao('ACOMPANHAMENTO.PAINEL.VISUALIZAR')
def apiHistorico(numero_awb):
    LogService.Debug("AcompanhamentoRoute", f"API /Historico chamada para {numero_awb}")
    listaHistorico = AcompanhamentoService.ObterHistoricoAwb(numero_awb)
    return jsonify(listaHistorico)

@AcompanhamentoBP.route('/Api/DetalhesVooModal', methods=['GET'])
@login_required
@require_ajax
def apiDetalhesVooModal():
    numeroVooConsulta = request.args.get('numeroVoo')
    dataRefConsulta = request.args.get('dataRef') 
    
    LogService.Debug("AcompanhamentoRoute", f"API /DetalhesVooModal chamada para voo {numeroVooConsulta} em {dataRefConsulta}")
    dictDetalhes = AcompanhamentoService.BuscarDetalhesVooModal(numeroVooConsulta, dataRefConsulta)
    
    if dictDetalhes:
        return jsonify({'sucesso': True, 'dados': dictDetalhes})
    else:
        return jsonify({'sucesso': False, 'msg': 'Voo não encontrado na malha prevista.'})