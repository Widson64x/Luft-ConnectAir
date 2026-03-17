from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from Services.PermissaoService import RequerPermissao
from Services.CorteService import CorteService
from luftcore.extensions.flask_extension import require_ajax

CortesBp = Blueprint('Cortes', __name__)

@CortesBp.route('/Gerenciar')
@login_required
@RequerPermissao('CADASTROS.CORTES.VISUALIZAR')
def Gerenciar():
    arvore_filiais = CorteService.ListarFiliaisAgrupadas()
    return render_template('Cadastros/Cortes/Manager.html', ArvoreFiliais=arvore_filiais)

@CortesBp.route('/API/Listar/Planejamento')
@login_required
@require_ajax
@RequerPermissao('CADASTROS.CORTES.VISUALIZAR')
def ApiListarPlanejamento():
    return jsonify(CorteService.ListarCortesPlanejamentoAgrupado())

@CortesBp.route('/API/Listar/Emissao')
@login_required
@require_ajax
@RequerPermissao('CADASTROS.CORTES.VISUALIZAR')
def ApiListarEmissao():
    return jsonify(CorteService.ListarCortesEmissaoAgrupado())

@CortesBp.route('/API/Salvar/Planejamento', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CADASTROS.CORTES.EDITAR')
def ApiSalvarPlanejamento():
    sucesso, msg = CorteService.SalvarCortePlanejamento(request.json, current_user.Login)
    if sucesso: return jsonify({'status': 'ok', 'msg': msg})
    return jsonify({'status': 'erro', 'msg': msg}), 500

@CortesBp.route('/API/Salvar/Emissao', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CADASTROS.CORTES.EDITAR')
def ApiSalvarEmissao():
    sucesso, msg = CorteService.SalvarCorteEmissao(request.json, current_user.Login)
    if sucesso: return jsonify({'status': 'ok', 'msg': msg})
    return jsonify({'status': 'erro', 'msg': msg}), 500

@CortesBp.route('/API/ExcluirEmMassa/<string:tipo>', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CADASTROS.CORTES.DELETAR')
def ApiExcluirEmMassa(tipo):
    dados = request.json
    ids = dados.get('ids', [])
    if not ids: return jsonify({'status': 'erro', 'msg': 'Nenhum ID selecionado'}), 400
    
    sucesso, msg = CorteService.ExcluirCortesEmMassa(tipo, ids, current_user.Login)
    if sucesso: return jsonify({'status': 'ok'})
    return jsonify({'status': 'erro', 'msg': msg}), 500