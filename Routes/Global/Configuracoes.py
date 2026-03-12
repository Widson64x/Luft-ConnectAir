from flask import Blueprint, render_template, request, jsonify, flash, url_for
from flask_login import login_required
from Services.CiaAereaService import CiaAereaService
from Services.PermissaoService import RequerPermissao

ConfiguracoesBp = Blueprint('Configuracoes', __name__)

@ConfiguracoesBp.route('/')
@login_required
@RequerPermissao('sistema.configuracoes.visualizar')
def Index():
    return render_template('Pages/Configs/Index.html')

@ConfiguracoesBp.route('/CiasAereas')
@RequerPermissao('sistema.configuracoes.editar')
def GerenciarCias():
    Lista = CiaAereaService.ObterTodasCias()
    return render_template('Pages/Configs/CiasAereas.html', Cias=Lista)

@ConfiguracoesBp.route('/API/CiasAereas/Salvar', methods=['POST'])
@RequerPermissao('sistema.configuracoes.editar')
def SalvarScoreCia():
    try:
        data = request.json
        cia = data.get('cia')
        score = data.get('score')
        
        if not cia: return jsonify({'sucesso': False, 'msg': 'Nome obrigatório'}), 400

        # O Service já cria se não existir
        if CiaAereaService.AtualizarScore(cia, int(score)):
            return jsonify({'sucesso': True})
        
        return jsonify({'sucesso': False, 'msg': 'Erro no Service'}), 500
    except Exception as e:
        return jsonify({'sucesso': False, 'msg': str(e)}), 500