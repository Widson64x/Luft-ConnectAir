from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_login import login_required
from Services import MalhaService
from Services.Shared.AwbService import AwbService
from Services.Shared.CtcService import CtcService
from Services.LogService import LogService
from Services.Shared.VoosDataService import ObterTotalVoosData

GlobalBp = Blueprint('Global', __name__)

@GlobalBp.route('/API/Ctc-Detalhes/<string:filial>/<string:serie>/<string:ctc>')
@login_required
def ApiCtcDetalhes(filial, serie, ctc):
    """
    API Global para buscar detalhes de um CTC.
    Usada nos modais de detalhes em todo o sistema.
    """
    Dados = CtcService.ObterCtcCompleto(filial, serie, ctc)
    
    if not Dados:
        LogService.Warning("Routes.Global", f"API Detalhes: CTC não encontrado {filial}-{serie}-{ctc}")
        return jsonify({'erro': 'CTC não encontrado'}), 404
        
    return jsonify(Dados)

@GlobalBp.route('/Api/DetalhesAwbModal', methods=['GET'])
def ApiDetalhesAwbModal():
    cod_awb = request.args.get('codAwb')
    LogService.Debug("Global", f"API /DetalhesAwbModal chamada. ID: {cod_awb}")
    
    if not cod_awb:
        LogService.Warning("Global", "API /DetalhesAwbModal chamada sem codAwb.")
        return jsonify({'sucesso': False, 'msg': 'Código AWB não informado.'})
        
    dados = AwbService.BuscarDetalhesAwbCompleto(cod_awb)
    
    if dados:
        return jsonify({'sucesso': True, 'dados': dados})
    else:
        return jsonify({'sucesso': False, 'msg': 'AWB não encontrada.'})
    
@GlobalBp.route('/API/Voos-Hoje') 
@login_required
def ApiVoosHoje():
    Hoje = datetime.now()
    # Chama a função do Service que aceita a data
    Quantidade = ObterTotalVoosData(Hoje)
    return jsonify(Quantidade)  