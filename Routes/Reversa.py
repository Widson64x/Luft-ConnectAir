from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from Services.PermissaoService import RequerPermissao
from Services.ReversaService import ReversaService
from Services.LogService import LogService

ReversaBp = Blueprint('Reversa', __name__)
 
@ReversaBp.route('/Gerenciamento')
@login_required
@RequerPermissao('reversa.visualizar')
def Index():
    """Renderiza a tela de listagem"""
    try:
        ListaDevolucoes = ReversaService.ListarDevolucoesPendentes()
        return render_template('Reversa/Index.html', Lista=ListaDevolucoes)
    except Exception as e:
        LogService.Error("Rotas.Reversa", "Erro ao renderizar index", e)
        return "Erro ao carregar dados", 500

@ReversaBp.route('/AtualizarStatus', methods=['POST'])
@login_required
@RequerPermissao('reversa.editar')
def AtualizarStatus():
    """API chamada pelo checkbox para liberar/bloquear"""
    dados = request.get_json()
    
    filial = dados.get('filial')
    serie = dados.get('serie')
    ctc = dados.get('ctc')
    liberado = dados.get('liberado') # Boolean

    if not all([filial, serie, ctc]):
        return jsonify({'sucesso': False, 'msg': 'Dados inválidos'}), 400

    sucesso, msg = ReversaService.AtualizarStatusReversa(
        filial, serie, ctc, liberado, current_user.Login # Ou current_user.Login
    )

    if sucesso:
        return jsonify({'sucesso': True})
    else:
        return jsonify({'sucesso': False, 'msg': msg}), 500