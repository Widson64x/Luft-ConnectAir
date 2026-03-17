from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from luftcore.extensions.flask_extension import require_ajax
from datetime import datetime
from Services.MalhaService import MalhaService
from Services.LogService import LogService
from Services.PermissaoService import RequerPermissao

MalhaBp = Blueprint('Malha', __name__)

@MalhaBp.route('/API/Rotas')
@login_required
@require_ajax
@RequerPermissao('CADASTROS.MALHA.VISUALIZAR')
def apiRotas():
    strInicio = request.args.get('inicio')
    strFim = request.args.get('fim')
    strOrigem = request.args.get('origem')
    strDestino = request.args.get('destino')
    numeroVooReq = request.args.get('numero_voo') 
    
    if not strInicio or not strFim:
        return jsonify([])

    try:
        dataIni = datetime.strptime(strInicio, '%Y-%m-%d').date()
        dataFim = datetime.strptime(strFim, '%Y-%m-%d').date()
        
        LogService.Info("Routes.Malha", f"API Rota Solicitada por {current_user.Login}: {strOrigem}->{strDestino} ({strInicio} a {strFim})")

        dadosRetorno = MalhaService.BuscarRotasInteligentes(dataIni, dataFim, strOrigem, strDestino, numeroVooReq)
        
        return jsonify(dadosRetorno)
    except Exception as e:
        LogService.Error("Routes.Malha", "Erro na API de Rotas", e)
        return jsonify({'erro': str(e)}), 500

@MalhaBp.route('/Gerenciar', methods=['GET', 'POST'])
@login_required
@RequerPermissao('CADASTROS.MALHA.EDITAR')
def gerenciar():
    modalConfirmacao = False
    dadosConfirmacao = {}

    if request.method == 'POST':
        if 'arquivo_xlsx' in request.files:
            arquivoUp = request.files['arquivo_xlsx']
            if arquivoUp.filename == '':
                flash('Selecione um arquivo.', 'warning')
            else:
                LogService.Info("Routes.Malha", f"Upload de Malha iniciado por {current_user.Login}")
                sucessoAnalise, infoAnalise = MalhaService.AnalisarArquivo(arquivoUp)
                
                if not sucessoAnalise:
                    LogService.Warning("Routes.Malha", f"Upload falhou na análise: {infoAnalise}")
                    flash(infoAnalise, 'danger')
                else:
                    if infoAnalise['conflito']:
                        LogService.Info("Routes.Malha", "Conflito de malha detectado. Aguardando confirmação do usuário.")
                        modalConfirmacao = True
                        dadosConfirmacao = infoAnalise
                    else:
                        okProcesso, msgProcesso = MalhaService.ProcessarMalhaFinal(
                            infoAnalise['caminho_temp'], 
                            infoAnalise['mes_ref'], 
                            infoAnalise['nome_arquivo'], 
                            current_user.Login, 
                            'Importacao'
                        )
                        if okProcesso: flash(msgProcesso, 'success')
                        else: flash(msgProcesso, 'danger')
                        return redirect(url_for('Malha.gerenciar'))

        elif 'confirmar_substituicao' in request.form:
            caminhoTempForm = request.form.get('caminho_temp')
            nomeOriginalForm = request.form.get('nome_arquivo')
            
            mesStrForm = request.form.get('mes_ref')
            
            if mesStrForm and ' ' in mesStrForm:
                mesStrForm = mesStrForm.split(' ')[0]
            
            try:
                LogService.Info("Routes.Malha", f"Usuário {current_user.Login} confirmou substituição de malha.")
                dataRefObj = datetime.strptime(mesStrForm, '%Y-%m-%d').date()
                
                okSubs, msgSubs = MalhaService.ProcessarMalhaFinal(
                    caminhoTempForm, 
                    dataRefObj, 
                    nomeOriginalForm, 
                    current_user.Login, 
                    'Substituicao'
                )
                if okSubs: flash(msgSubs, 'success')
                else: flash(msgSubs, 'danger')
                
            except Exception as e:
                LogService.Error("Routes.Malha", "Erro ao processar data na confirmação", e)
                flash(f"Erro ao processar data: {e}", 'danger')

            return redirect(url_for('Malha.gerenciar'))

    listaHistorico = MalhaService.ListarRemessas()
    
    return render_template('Cadastros/Malha/Manager.html', 
                           ListaRemessas=listaHistorico, 
                           ExibirModal=modalConfirmacao, 
                           DadosModal=dadosConfirmacao)

@MalhaBp.route('/Excluir/<int:id_remessa>')
@login_required
@RequerPermissao('CADASTROS.MALHA.DELETAR')
def excluir(id_remessa):
    LogService.Warning("Routes.Malha", f"Solicitação de exclusão de remessa {id_remessa} por {current_user.Login}")
    sucessoExcluir, msgExcluir = MalhaService.ExcluirRemessa(id_remessa)
    if sucessoExcluir: flash(msgExcluir, 'info')
    else: flash(msgExcluir, 'danger')
    return redirect(url_for('Malha.gerenciar'))