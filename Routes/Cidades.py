from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from Services.CidadesService import CidadesService
from Services.LogService import LogService # <--- Import Log

CidadeBp = Blueprint('Cidade', __name__)

@CidadeBp.route('/Cidades/Gerenciar', methods=['GET', 'POST'])
@login_required
def Gerenciar():
    ModalConfirmacao = False
    DadosConfirmacao = {}

    if request.method == 'POST':
        # Upload Inicial
        if 'arquivo_xlsx' in request.files:
            Arquivo = request.files['arquivo_xlsx']
            LogService.Info("Route.Cidades", f"Usuário {current_user.Login} enviou arquivo de cidades: {Arquivo.filename}")
            
            if Arquivo.filename == '':
                flash('Selecione o arquivo cidades.xlsx', 'warning')
            else:
                Ok, Info = CidadesService.AnalisarArquivo(Arquivo)
                if not Ok:
                    flash(Info, 'danger')
                    LogService.Warning("Route.Cidades", f"Falha na análise: {Info}")
                else:
                    if Info['conflito']:
                        ModalConfirmacao = True
                        DadosConfirmacao = Info
                        LogService.Info("Route.Cidades", "Conflito detectado. Aguardando confirmação.")
                    else:
                        Ok, Msg = CidadesService.ProcessarArquivoFinal(Info['caminho_temp'], Info['mes_ref'], Info['nome_arquivo'], current_user.Login, 'Importacao')
                        if Ok: flash(Msg, 'success')
                        else: flash(Msg, 'danger')
                        return redirect(url_for('Cidade.Gerenciar'))

        # Confirmação do Modal
        elif 'confirmar_substituicao' in request.form:
            LogService.Info("Route.Cidades", f"Usuário {current_user.Login} confirmou substituição de cidades.")
            Caminho = request.form.get('caminho_temp')
            Nome = request.form.get('nome_arquivo')
            DataRef = datetime.strptime(request.form.get('mes_ref'), '%Y-%m-%d').date()
            
            Ok, Msg = CidadesService.ProcessarArquivoFinal(Caminho, DataRef, Nome, current_user.Login, 'Substituicao')
            if Ok: flash(Msg, 'success')
            else: flash(Msg, 'danger')
            return redirect(url_for('Cidade.Gerenciar'))

    Historico = CidadesService.ListarRemessas()
    return render_template('Cidades/Manager.html', ListaRemessas=Historico, ExibirModal=ModalConfirmacao, DadosModal=DadosConfirmacao)

@CidadeBp.route('/Cidades/Excluir/<int:id_remessa>')
@login_required
def Excluir(id_remessa):
    LogService.Info("Route.Cidades", f"Usuário {current_user.Login} solicitou exclusão da remessa {id_remessa}")
    Ok, Msg = CidadesService.ExcluirRemessa(id_remessa)
    if Ok: flash(Msg, 'info')
    else: flash(Msg, 'danger')
    return redirect(url_for('Cidade.Gerenciar'))