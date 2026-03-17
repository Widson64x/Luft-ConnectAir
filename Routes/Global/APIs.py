from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_login import login_required
from Services import MalhaService
from Services.PermissaoService import RequerPermissao
from luftcore.extensions.flask_extension import require_ajax
from Services.Shared.AwbService import AwbService
from Services.Shared.CtcService import CtcService
from Services.LogService import LogService
from Services.Shared.VoosDataService import ObterTotalVoosData

GlobalBp = Blueprint('Global', __name__)

@GlobalBp.route('/API/Ctc-Detalhes/<string:filial>/<string:serie>/<string:ctc>')
@login_required
@require_ajax
@RequerPermissao('ACOMPANHAMENTO.PAINEL.VISUALIZAR')
def apiCtcDetalhes(filial, serie, ctc):
    dadosCtc = CtcService.ObterCtcCompleto(filial, serie, ctc)
    
    if not dadosCtc:
        LogService.Warning("Routes.Global", f"API Detalhes: CTC não encontrado {filial}-{serie}-{ctc}")
        return jsonify({'erro': 'CTC não encontrado'}), 404
        
    return jsonify(dadosCtc)

@GlobalBp.route('/Api/DetalhesAwbModal', methods=['GET'])
@login_required
@require_ajax
@RequerPermissao('ACOMPANHAMENTO.PAINEL.VISUALIZAR')
def apiDetalhesAwbModal():
    codAwb = request.args.get('codAwb')
    LogService.Debug("Global", f"API /DetalhesAwbModal chamada. ID: {codAwb}")
    
    if not codAwb:
        LogService.Warning("Global", "API /DetalhesAwbModal chamada sem codAwb.")
        return jsonify({'sucesso': False, 'msg': 'Código AWB não informado.'})
        
    dadosAwb = AwbService.BuscarDetalhesAwbCompleto(codAwb)
    
    if dadosAwb:
        return jsonify({'sucesso': True, 'dados': dadosAwb})
    else:
        return jsonify({'sucesso': False, 'msg': 'AWB não encontrada.'})
    
@GlobalBp.route('/API/Voos-Hoje') 
@login_required
@require_ajax
@RequerPermissao('PLANEJAMENTO.ROTAS.VISUALIZAR')
def apiVoosHoje():
    hojeData = datetime.now()
    quantidadeVoos = ObterTotalVoosData(hojeData)
    return jsonify(quantidadeVoos)