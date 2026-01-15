from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from Services.CidadeService import ListarRemessasCidades, ExcluirRemessaCidade, AnalisarArquivoCidades, ProcessarCidadesFinal

CidadeBp = Blueprint('Cidade', __name__)

@CidadeBp.route('/cidades/gerenciar', methods=['GET', 'POST'])
@login_required
def Gerenciar():
    ModalConfirmacao = False
    DadosConfirmacao = {}

    if request.method == 'POST':
        # Upload Inicial
        if 'arquivo_xlsx' in request.files:
            Arquivo = request.files['arquivo_xlsx']
            if Arquivo.filename == '':
                flash('Selecione o arquivo cidades.xlsx', 'warning')
            else:
                Ok, Info = AnalisarArquivoCidades(Arquivo)
                if not Ok:
                    flash(Info, 'danger')
                else:
                    if Info['conflito']:
                        ModalConfirmacao = True
                        DadosConfirmacao = Info
                    else:
                        Ok, Msg = ProcessarCidadesFinal(Info['caminho_temp'], Info['mes_ref'], Info['nome_arquivo'], current_user.Nome, 'Importacao')
                        if Ok: flash(Msg, 'success')
                        else: flash(Msg, 'danger')
                        return redirect(url_for('Cidade.Gerenciar'))

        # Confirmação do Modal
        elif 'confirmar_substituicao' in request.form:
            Caminho = request.form.get('caminho_temp')
            Nome = request.form.get('nome_arquivo')
            DataRef = datetime.strptime(request.form.get('mes_ref'), '%Y-%m-%d').date()
            
            Ok, Msg = ProcessarCidadesFinal(Caminho, DataRef, Nome, current_user.Nome, 'Substituicao')
            if Ok: flash(Msg, 'success')
            else: flash(Msg, 'danger')
            return redirect(url_for('Cidade.Gerenciar'))

    Historico = ListarRemessasCidades()
    return render_template('Cidades/Gerenciar.html', ListaRemessas=Historico, ExibirModal=ModalConfirmacao, DadosModal=DadosConfirmacao)

@CidadeBp.route('/cidades/excluir/<int:id_remessa>')
@login_required
def Excluir(id_remessa):
    Ok, Msg = ExcluirRemessaCidade(id_remessa)
    if Ok: flash(Msg, 'info')
    else: flash(Msg, 'danger')
    return redirect(url_for('Cidade.Gerenciar'))