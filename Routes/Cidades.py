from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from Services.CidadesService import CidadesService
from Services.LogService import LogService
from Services.PermissaoService import RequerPermissao 

CidadeBp = Blueprint('Cidade', __name__)

@CidadeBp.route('/Gerenciar', methods=['GET', 'POST'])
@login_required
@RequerPermissao('CADASTROS.CIDADES.EDITAR')
def gerenciar():
    modalConfirmacao = False
    dadosConfirmacao = {}

    if request.method == 'POST':
        # Upload Inicial
        if 'arquivo_xlsx' in request.files:
            arquivoXlsx = request.files['arquivo_xlsx']
            LogService.Info("Route.Cidades", f"Usuário {current_user.Login} enviou arquivo de cidades: {arquivoXlsx.filename}")
            
            if arquivoXlsx.filename == '':
                flash('Selecione o arquivo cidades.xlsx', 'warning')
            else:
                ok, info = CidadesService.AnalisarArquivo(arquivoXlsx)
                if not ok:
                    flash(info, 'danger')
                    LogService.Warning("Route.Cidades", f"Falha na análise: {info}")
                else:
                    if info['conflito']:
                        modalConfirmacao = True
                        dadosConfirmacao = info
                        LogService.Info("Route.Cidades", "Conflito detectado. Aguardando confirmação.")
                    else:
                        ok, msg = CidadesService.ProcessarArquivoFinal(info['caminho_temp'], info['mes_ref'], info['nome_arquivo'], current_user.Login, 'Importacao')
                        if ok: flash(msg, 'success')
                        else: flash(msg, 'danger')
                        return redirect(url_for('Cidade.gerenciar'))

        # Confirmação do Modal
        elif 'confirmar_substituicao' in request.form:
            LogService.Info("Route.Cidades", f"Usuário {current_user.Login} confirmou substituição de cidades.")
            caminhoTemp = request.form.get('caminho_temp')
            nomeOriginal = request.form.get('nome_arquivo')
            dataRef = datetime.strptime(request.form.get('mes_ref'), '%Y-%m-%d').date()
            
            ok, msg = CidadesService.ProcessarArquivoFinal(caminhoTemp, dataRef, nomeOriginal, current_user.Login, 'Substituicao')
            if ok: flash(msg, 'success')
            else: flash(msg, 'danger')
            return redirect(url_for('Cidade.gerenciar'))

    historicoRemessas = CidadesService.ListarRemessas()
    return render_template('Cadastros/Cidades/Manager.html', ListaRemessas=historicoRemessas, ExibirModal=modalConfirmacao, DadosModal=dadosConfirmacao)

@CidadeBp.route('/Excluir/<int:id_remessa>')
@login_required
@RequerPermissao('CADASTROS.CIDADES.DELETAR')
def excluir(id_remessa):
    LogService.Info("Route.Cidades", f"Usuário {current_user.Login} solicitou exclusão da remessa {id_remessa}")
    ok, msg = CidadesService.ExcluirRemessa(id_remessa)
    if ok: flash(msg, 'info')
    else: flash(msg, 'danger')
    return redirect(url_for('Cidade.gerenciar'))