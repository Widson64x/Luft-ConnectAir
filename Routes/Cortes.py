from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from Services.PermissaoService import RequerPermissao
from Services.CorteService import CorteService

CortesBp = Blueprint('Cortes', __name__)

@CortesBp.route('/Gerenciar')
@login_required
@RequerPermissao('cadastros.cortes.visualizar') 
def Gerenciar():
    # Carrega as filiais para o Dropdown do Modal
    lista_filiais = CorteService.ListarFiliais()
    return render_template('Cortes/Manager.html', Filiais=lista_filiais)

@CortesBp.route('/API/Listar/Planejamento')
@login_required
@RequerPermissao('cadastros.cortes.visualizar') 
def ApiListarPlanejamento():
    filial = request.args.get('filial')
    dados = CorteService.ListarCortesPlanejamento(filial)
    return jsonify(dados)

@CortesBp.route('/API/Listar/Emissao')
@login_required
@RequerPermissao('cadastros.cortes.visualizar') 
def ApiListarEmissao():
    filial = request.args.get('filial')
    dados = CorteService.ListarCortesEmissao(filial)
    return jsonify(dados)

@CortesBp.route('/API/Salvar/Planejamento', methods=['POST'])
@login_required
@RequerPermissao('cadastros.cortes.editar') 
def ApiSalvarPlanejamento():
    # CORREÇÃO: Passando current_user.Login como segundo argumento
    sucesso, msg = CorteService.SalvarCortePlanejamento(request.json, current_user.Login)
    if sucesso: return jsonify({'status': 'ok'})
    return jsonify({'status': 'erro', 'msg': msg}), 500

@CortesBp.route('/API/Salvar/Emissao', methods=['POST'])
@login_required
@RequerPermissao('cadastros.cortes.editar') 
def ApiSalvarEmissao():
    # CORREÇÃO: Passando current_user.Login como segundo argumento
    sucesso, msg = CorteService.SalvarCorteEmissao(request.json, current_user.Login)
    if sucesso: return jsonify({'status': 'ok'})
    return jsonify({'status': 'erro', 'msg': msg}), 500

@CortesBp.route('/API/Excluir/<string:tipo>/<int:id_corte>', methods=['DELETE'])
@login_required
@RequerPermissao('cadastros.cortes.excluir') 
def ApiExcluir(tipo, id_corte):
    # tipo deve ser 'planejamento' ou 'emissao'
    # CORREÇÃO: Passando current_user.Login para registrar quem excluiu
    if CorteService.ExcluirCorte(tipo, id_corte, current_user.Login):
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'erro'}), 500