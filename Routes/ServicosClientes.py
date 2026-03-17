from flask import Blueprint, jsonify, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from luftcore.extensions.flask_extension import require_ajax

from Services.PermissaoService import RequerPermissao
from Services.ServicoClienteService import ServicoClienteService

ServicosClientesBp = Blueprint('ServicosClientes', __name__)

@ServicosClientesBp.route('/', methods=['GET'])
@login_required
@RequerPermissao('PLANEJAMENTO.SERVICOS_CLIENTES.VISUALIZAR')
def gerenciar():
    listaClientesView = ServicoClienteService.ObterClientesParaSelecao()
    return render_template('Cadastros/ServicoCliente/Manager.html', Clientes=listaClientesView)

@ServicosClientesBp.route('/DadosCliente/<int:CodigoCliente>', methods=['GET'])
@login_required
@require_ajax
@RequerPermissao('PLANEJAMENTO.SERVICOS_CLIENTES.VISUALIZAR')
def obterDadosCliente(CodigoCliente):
    dadosClienteObj = ServicoClienteService.ObterDadosCliente(CodigoCliente)
    if dadosClienteObj:
        return jsonify(dadosClienteObj)
    else:
        return jsonify({"Erro": "Cliente não encontrado"}), 404

@ServicosClientesBp.route('/Listagem', methods=['GET'])
@login_required
@require_ajax
@RequerPermissao('PLANEJAMENTO.SERVICOS_CLIENTES.VISUALIZAR')
def listaServicosContratados():
    listaServicosObj = ServicoClienteService.ListarServicosContratados()
    
    resultadoJson = []
    for servicoItem, clienteItem, grupoItem in listaServicosObj:
        
        nomeGrupo = grupoItem.Descricao_ClienteGrupo if grupoItem else 'Z_Sem Grupo'
        
        resultadoJson.append({
            "Id": servicoItem.Id,
            "CodigoCliente": servicoItem.CodigoCliente,
            "Cnpj": clienteItem.CNPJ_Cliente if clienteItem else "",
            "RazaoSocial": clienteItem.Nome_RazaoSocialCliente if clienteItem else "",
            "Fantasia": clienteItem.Nome_FantasiaCliente if clienteItem else "",
            "Grupo": nomeGrupo, 
            "DurabilidadeGelo": servicoItem.DurabilidadeGelo,
            "AutorizacaoTrocaGelo": servicoItem.AutorizacaoTrocaGelo,
            "AutorizacaoArmazenagem": servicoItem.AutorizacaoArmazenagem,
            "ServicoContratado": servicoItem.ServicoContratado
        })

    return jsonify(resultadoJson)

@ServicosClientesBp.route('/Salvar', methods=['POST'])
@login_required
@RequerPermissao('PLANEJAMENTO.SERVICOS_CLIENTES.EDITAR')
def salvarServico():
    usuarioLogadoReq = current_user.Login if current_user and hasattr(current_user, 'Login') else "UsuarioDesconhecido"
    
    dadosFormularioDict = request.form.to_dict()
    clientesSelecionadosList = request.form.getlist('clientes_selecionados[]')
    
    if not clientesSelecionadosList:
        flash("Nenhum cliente selecionado. Por favor, marque pelo menos um cliente na árvore.", "warning")
        return redirect(url_for('ServicosClientes.gerenciar'))

    contadorSucessos = 0
    erroMensagemStr = ""

    for codigoClienteForm in clientesSelecionadosList:
        dadosFormularioDict['CodigoCliente'] = codigoClienteForm
        
        resultadoOperacao = ServicoClienteService.CadastrarNovoServico(dadosFormularioDict, usuarioLogadoReq)
        
        if resultadoOperacao["Sucesso"]:
            contadorSucessos += 1
        else:
            erroMensagemStr = resultadoOperacao["Mensagem"] 

    if contadorSucessos == len(clientesSelecionadosList):
        flash(f"Parâmetros aplicados com sucesso para {contadorSucessos} cliente(s)!", "success")
    elif contadorSucessos > 0:
        flash(f"Salvo parcialmente: {contadorSucessos} aplicados com sucesso, mas houve erro(s): {erroMensagemStr}", "warning")
    else:
        flash(f"Erro ao salvar o lote: {erroMensagemStr}", "danger")
        
    return redirect(url_for('ServicosClientes.gerenciar'))

@ServicosClientesBp.route('/Editar/<int:IdServico>', methods=['POST'])
@login_required
@RequerPermissao('PLANEJAMENTO.SERVICOS_CLIENTES.EDITAR')
def editarServico(IdServico):
    usuarioLogadoReq = current_user.Login if current_user and hasattr(current_user, 'Login') else "UsuarioDesconhecido"
    
    dadosFormularioDict = request.form.to_dict()
    clientesSelecionadosList = request.form.getlist('clientes_selecionados[]')
    
    if clientesSelecionadosList:
        dadosFormularioDict['CodigoCliente'] = clientesSelecionadosList[0]
        
    resultadoOperacao = ServicoClienteService.EditarServico(IdServico, dadosFormularioDict, usuarioLogadoReq)

    if resultadoOperacao["Sucesso"]:
        flash(resultadoOperacao["Mensagem"], "success")
    else:
        flash(f"Erro ao editar: {resultadoOperacao['Mensagem']}", "danger")
        
    return redirect(url_for('ServicosClientes.gerenciar'))

@ServicosClientesBp.route('/Excluir/<int:IdServico>', methods=['POST'])
@login_required
@RequerPermissao('PLANEJAMENTO.SERVICOS_CLIENTES.DELETAR')
def excluirServico(IdServico):
    usuarioLogadoReq = current_user.Login if current_user and hasattr(current_user, 'Login') else "UsuarioDesconhecido"
    
    resultadoOperacao = ServicoClienteService.ExcluirServico(IdServico, usuarioLogadoReq)

    if resultadoOperacao["Sucesso"]:
        flash(resultadoOperacao["Mensagem"], "success")
    else:
        flash(f"Erro ao excluir: {resultadoOperacao['Mensagem']}", "danger")
        
    return redirect(url_for('ServicosClientes.gerenciar'))