from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from Services.PermissaoService import RequerPermissao
from Services.CorteService import CorteService
from luftcore.extensions.flask_extension import require_ajax

CortesBp = Blueprint('Cortes', __name__)

@CortesBp.route('/Gerenciar')
@login_required
@RequerPermissao('CADASTROS.CORTES.VISUALIZAR')
def gerenciar():
    arvoreFiliais = CorteService.ListarFiliaisAgrupadas()
    return render_template('Cadastros/Cortes/Manager.html', ArvoreFiliais=arvoreFiliais)

@CortesBp.route('/API/Listar/Planejamento')
@login_required
@require_ajax
@RequerPermissao('CADASTROS.CORTES.VISUALIZAR')
def apiListarPlanejamento():
    return jsonify(CorteService.ListarCortesPlanejamentoAgrupado())

@CortesBp.route('/API/Listar/Emissao')
@login_required
@require_ajax
@RequerPermissao('CADASTROS.CORTES.VISUALIZAR')
def apiListarEmissao():
    return jsonify(CorteService.ListarCortesEmissaoAgrupado())

@CortesBp.route('/API/Salvar/Planejamento', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CADASTROS.CORTES.EDITAR')
def apiSalvarPlanejamento():
    sucesso, msg = CorteService.SalvarCortePlanejamento(request.json, current_user.Login)
    if sucesso: return jsonify({'status': 'ok', 'msg': msg})
    return jsonify({'status': 'erro', 'msg': msg}), 500

@CortesBp.route('/API/Salvar/Emissao', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CADASTROS.CORTES.EDITAR')
def apiSalvarEmissao():
    sucesso, msg = CorteService.SalvarCorteEmissao(request.json, current_user.Login)
    if sucesso: return jsonify({'status': 'ok', 'msg': msg})
    return jsonify({'status': 'erro', 'msg': msg}), 500

@CortesBp.route('/API/ExcluirEmMassa/<string:tipo>', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CADASTROS.CORTES.DELETAR')
def apiExcluirEmMassa(tipo):
    dadosRequisicao = request.json
    listaIds = dadosRequisicao.get('ids', [])
    if not listaIds: return jsonify({'status': 'erro', 'msg': 'Nenhum ID selecionado'}), 400
    
    sucesso, msg = CorteService.ExcluirCortesEmMassa(tipo, listaIds, current_user.Login)
    if sucesso: return jsonify({'status': 'ok'})
    return jsonify({'status': 'erro', 'msg': msg}), 500