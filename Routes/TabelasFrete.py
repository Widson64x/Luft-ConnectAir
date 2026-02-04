from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from Services.TabelaFreteService import TabelaFreteService
from Services.LogService import LogService

FreteBp = Blueprint('Frete', __name__)

@FreteBp.route('/Fretes/Gerenciar', methods=['GET', 'POST'])
@login_required
def Gerenciar():
    if request.method == 'POST':
        if 'arquivo_xlsx' in request.files:
            Arquivo = request.files['arquivo_xlsx']
            if Arquivo.filename == '':
                flash('Selecione um arquivo válido.', 'warning')
            else:
                LogService.Info("Routes.Frete", f"Upload iniciado por {current_user.Login}")
                Sucesso, Msg = TabelaFreteService.ProcessarArquivo(Arquivo, current_user.Login)
                
                if Sucesso: flash(Msg, 'success')
                else: flash(Msg, 'danger')
                
                return redirect(url_for('Frete.Gerenciar'))

    Historico = TabelaFreteService.ListarRemessas()
    return render_template('TabelasFrete/Manager.html', ListaRemessas=Historico)

@FreteBp.route('/Fretes/Excluir/<int:id_remessa>')
@login_required
def Excluir(id_remessa):
    Sucesso, Msg = TabelaFreteService.ExcluirRemessa(id_remessa)
    if Sucesso: flash(Msg, 'info')
    else: flash(Msg, 'danger')
    return redirect(url_for('Frete.Gerenciar'))