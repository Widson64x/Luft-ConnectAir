from flask import Blueprint, jsonify, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from Services.ServicoClienteService import ServicoClienteService

# Blueprint para os Serviços dos Clientes
ServicosClientesBp = Blueprint('ServicosClientes', __name__, url_prefix='/Planejamento/Servicos')

@ServicosClientesBp.route('/', methods=['GET'])
@login_required
def Gerenciar():
    """Renderiza a tela de cadastro enviando a lista de clientes para a Árvore de Seleção"""
    ListaClientes = ServicoClienteService.ObterClientesParaSelecao()
    return render_template('ServicoCliente/Manager.html', Clientes=ListaClientes)

@ServicosClientesBp.route('/DadosCliente/<int:CodigoCliente>', methods=['GET'])
@login_required
def ObterDadosCliente(CodigoCliente):
    """Endpoint para obter os dados de um cliente específico via Fetch API no Frontend"""
    DadosCliente = ServicoClienteService.ObterDadosCliente(CodigoCliente)
    if DadosCliente:
        return jsonify(DadosCliente)
    else:
        return jsonify({"Erro": "Cliente não encontrado"}), 404

@ServicosClientesBp.route('/Listagem', methods=['GET'])
@login_required
def ListaServicosContratados():
    """ Traz a lista de serviços contratados para exibir na mesma tela de Manager """
    listaServicos = ServicoClienteService.ListarServicosContratados()
    
    resultado = []
    # Agora desempacotamos a tupla (servico, cliente, grupo) que vem do banco
    for servico, cliente, grupo in listaServicos:
        
        # Mesmo tratamento para quem não tem grupo
        nome_grupo = grupo.Descricao_ClienteGrupo if grupo else 'Z_Sem Grupo'
        
        resultado.append({
            "Id": servico.Id,
            "CodigoCliente": servico.CodigoCliente,
            "Cnpj": cliente.CNPJ_Cliente if cliente else "",
            "RazaoSocial": cliente.Nome_RazaoSocialCliente if cliente else "",
            "Fantasia": cliente.Nome_FantasiaCliente if cliente else "",
            "Grupo": nome_grupo, # <--- Enviando o grupo para o JS
            "DurabilidadeGelo": servico.DurabilidadeGelo,
            "AutorizacaoTrocaGelo": servico.AutorizacaoTrocaGelo,
            "AutorizacaoArmazenagem": servico.AutorizacaoArmazenagem,
            "ServicoContratado": servico.ServicoContratado
        })

    return jsonify(resultado)

@ServicosClientesBp.route('/Salvar', methods=['POST'])
@login_required
def SalvarServico():
    """Recebe o Form Submit da tela para Cadastrar serviços em LOTE"""
    UsuarioLogado = current_user.Login if current_user and hasattr(current_user, 'Login') else "UsuarioDesconhecido"
    
    # Pega os dados básicos do formulário (sem a lista de arrays)
    DadosFormulario = request.form.to_dict()
    
    # Extrai o array de clientes seleccionados gerado pelo Treeview
    clientes_selecionados = request.form.getlist('clientes_selecionados[]')
    
    if not clientes_selecionados:
        flash("Nenhum cliente selecionado. Por favor, marque pelo menos um cliente na árvore.", "warning")
        return redirect(url_for('ServicosClientes.Gerenciar'))

    sucessos = 0
    erro_msg = ""

    # Processa cada cliente selecionado no lote
    for codigo_cliente in clientes_selecionados:
        # Injeta o código do cliente no dicionário para reaproveitar a sua função existente no Service
        DadosFormulario['CodigoCliente'] = codigo_cliente
        
        Resultado = ServicoClienteService.CadastrarNovoServico(DadosFormulario, UsuarioLogado)
        
        if Resultado["Sucesso"]:
            sucessos += 1
        else:
            erro_msg = Resultado["Mensagem"] # Guarda o erro caso algum falhe

    # Verifica o resultado da operação em lote
    if sucessos == len(clientes_selecionados):
        flash(f"Parâmetros aplicados com sucesso para {sucessos} cliente(s)!", "success")
    elif sucessos > 0:
        flash(f"Salvo parcialmente: {sucessos} aplicados com sucesso, mas houve erro(s): {erro_msg}", "warning")
    else:
        flash(f"Erro ao salvar o lote: {erro_msg}", "danger")
        
    return redirect(url_for('ServicosClientes.Gerenciar'))

@ServicosClientesBp.route('/Editar/<int:IdServico>', methods=['POST'])
@login_required
def EditarServico(IdServico):
    """Recebe os dados do formulário para atualizar um serviço EXISTENTE"""
    UsuarioLogado = current_user.Login if current_user and hasattr(current_user, 'Login') else "UsuarioDesconhecido"
    
    DadosFormulario = request.form.to_dict()
    clientes_selecionados = request.form.getlist('clientes_selecionados[]')
    
    # Como removemos o <select name="CodigoCliente">, precisamos garantir que o código
    # do cliente seja injectado no dicionário (apanhando o único que ficou marcado na árvore)
    if clientes_selecionados:
        DadosFormulario['CodigoCliente'] = clientes_selecionados[0]
        
    Resultado = ServicoClienteService.EditarServico(IdServico, DadosFormulario, UsuarioLogado)

    if Resultado["Sucesso"]:
        flash(Resultado["Mensagem"], "success")
    else:
        flash(f"Erro ao editar: {Resultado['Mensagem']}", "danger")
        
    return redirect(url_for('ServicosClientes.Gerenciar'))

@ServicosClientesBp.route('/Excluir/<int:IdServico>', methods=['POST'])
@login_required
def ExcluirServico(IdServico):
    """Exclui um serviço específico pelo ID"""
    UsuarioLogado = current_user.Login if current_user and hasattr(current_user, 'Login') else "UsuarioDesconhecido"
    
    Resultado = ServicoClienteService.ExcluirServico(IdServico, UsuarioLogado)

    if Resultado["Sucesso"]:
        flash(Resultado["Mensagem"], "success")
    else:
        flash(f"Erro ao excluir: {Resultado['Mensagem']}", "danger")
        
    return redirect(url_for('ServicosClientes.Gerenciar'))