from flask import Blueprint, render_template, request, jsonify, flash, url_for
from flask_login import login_required
from Services.CiaAereaService import CiaAereaService
from Services.PermissaoService import RequerPermissao

ConfiguracoesBp = Blueprint('Configuracoes', __name__)

@ConfiguracoesBp.route('/')
@login_required
@RequerPermissao('SISTEMA.CONFIGURACOES.VISUALIZAR')
def index():
    return render_template('Pages/Configs/Index.html')

@ConfiguracoesBp.route('/CiasAereas')
@RequerPermissao('SISTEMA.CONFIGURACOES.VISUALIZAR')
def gerenciarCias():
    listaCias = CiaAereaService.ObterTodasCias()
    return render_template('Pages/Configs/CiasAereas.html', Cias=listaCias)

@ConfiguracoesBp.route('/API/CiasAereas/Salvar', methods=['POST'])
@RequerPermissao('SISTEMA.CONFIGURACOES.EDITAR')
def salvarScoreCia():
    try:
        dadosRequisicao = request.json
        nomeCia = (dadosRequisicao.get('cia') or '').strip()
        valorScore = dadosRequisicao.get('score')
        
        if not nomeCia: return jsonify({'sucesso': False, 'msg': 'Nome obrigatório'}), 400

        if CiaAereaService.AtualizarScore(nomeCia, int(valorScore)):
            return jsonify({'sucesso': True})
        
        return jsonify({'sucesso': False, 'msg': 'Erro no Service'}), 500
    except Exception as e:
        return jsonify({'sucesso': False, 'msg': str(e)}), 500