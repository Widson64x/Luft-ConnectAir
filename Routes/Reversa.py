from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from luftcore.extensions.flask_extension import require_ajax
from Services.PermissaoService import RequerPermissao
from Services.ReversaService import ReversaService
from Services.LogService import LogService

ReversaBp = Blueprint('Reversa', __name__)
 
@ReversaBp.route('/Gerenciamento')
@login_required
@RequerPermissao('REVERSA.LOGISTICA.VISUALIZAR')
def index():
    try:
        listaDevolucoes = ReversaService.ListarDevolucoesPendentes()
        return render_template('Pages/Reversa/Index.html', Lista=listaDevolucoes)
    except Exception as e:
        LogService.Error("Rotas.Reversa", "Erro ao renderizar index", e)
        return "Erro ao carregar dados", 500

@ReversaBp.route('/AtualizarStatus', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('REVERSA.LOGISTICA.EDITAR')
def atualizarStatus():
    dadosRequisicao = request.get_json()
    
    filialReq = dadosRequisicao.get('filial')
    serieReq = dadosRequisicao.get('serie')
    ctcReq = dadosRequisicao.get('ctc')
    statusLiberado = dadosRequisicao.get('liberado')

    if not all([filialReq, serieReq, ctcReq]):
        return jsonify({'sucesso': False, 'msg': 'Dados inválidos'}), 400

    sucessoAtualizacao, msgRetorno = ReversaService.AtualizarStatusReversa(
        filialReq, serieReq, ctcReq, statusLiberado, current_user.Login 
    )

    if sucessoAtualizacao:
        return jsonify({'sucesso': True})
    else:
        return jsonify({'sucesso': False, 'msg': msgRetorno}), 500