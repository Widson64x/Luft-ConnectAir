from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from Services.PermissaoService import RequerPermissao
from Services.TabelaFreteService import TabelaFreteService
from Services.LogService import LogService

FreteBp = Blueprint('Frete', __name__)

@FreteBp.route('/Gerenciar', methods=['GET', 'POST'])
@login_required
@RequerPermissao('CADASTROS.TABELAS_FRETE.VISUALIZAR')
def gerenciar():
    if request.method == 'POST':
        if 'arquivo_xlsx' in request.files:
            arquivoRecebido = request.files['arquivo_xlsx']
            if arquivoRecebido.filename == '':
                flash('Selecione um arquivo válido.', 'warning')
            else:
                LogService.Info("Routes.Frete", f"Upload iniciado por {current_user.Login}")
                sucessoProcesso, msgProcesso = TabelaFreteService.ProcessarArquivo(arquivoRecebido, current_user.Login)
                
                if sucessoProcesso: flash(msgProcesso, 'success')
                else: flash(msgProcesso, 'danger')
                
                return redirect(url_for('Frete.gerenciar'))

    listaHistorico = TabelaFreteService.ListarRemessas()
    return render_template('Cadastros/TabelasFrete/Manager.html', ListaRemessas=listaHistorico)

@FreteBp.route('/Excluir/<int:id_remessa>')
@login_required
@RequerPermissao('CADASTROS.TABELAS_FRETE.DELETAR')
def excluir(id_remessa):
    sucessoExclusao, msgExclusao = TabelaFreteService.ExcluirRemessa(id_remessa)
    if sucessoExclusao: flash(msgExclusao, 'info')
    else: flash(msgExclusao, 'danger')
    return redirect(url_for('Frete.gerenciar'))