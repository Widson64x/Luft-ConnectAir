from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
# Importa a CLASSE do Serviço agora, não as funções soltas
from Services.AeroportoService import AeroportoService

AeroportoBp = Blueprint('Aeroporto', __name__)

@AeroportoBp.route('/Aeroportos/API/Listar-Simples')
@login_required
def ApiListarSimples():
    try:
        # Chamada corrigida: AeroportoService.ListarTodosParaSelect()
        Dados = AeroportoService.ListarTodosParaSelect()
        return jsonify(Dados)
    except Exception as e:
        return jsonify([]), 500

@AeroportoBp.route('/Aeroportos/Gerenciar', methods=['GET', 'POST'])
@login_required
def Gerenciar():
    ModalConfirmacao = False
    DadosConfirmacao = {}

    if request.method == 'POST':
        # --- Upload Inicial ---
        if 'arquivo_csv' in request.files:
            Arquivo = request.files['arquivo_csv']
            if Arquivo.filename == '':
                flash('Selecione um arquivo .csv', 'warning')
            else:
                # Chamada corrigida
                Sucesso, Info = AeroportoService.AnalisarArquivoAeroportos(Arquivo)
                
                if not Sucesso:
                    flash(Info, 'danger')
                else:
                    if Info['conflito']:
                        ModalConfirmacao = True
                        DadosConfirmacao = Info
                    else:
                        # Chamada corrigida
                        Ok, Msg = AeroportoService.ProcessarAeroportosFinal(
                            Info['caminho_temp'], 
                            Info['mes_ref'], 
                            Info['nome_arquivo'], 
                            current_user.Nome, 
                            'Importacao'
                        )
                        if Ok: flash(Msg, 'success')
                        else: flash(Msg, 'danger')
                        return redirect(url_for('Aeroporto.Gerenciar'))

        # --- Confirmação do Modal ---
        elif 'confirmar_substituicao' in request.form:
            CaminhoTemp = request.form.get('caminho_temp')
            NomeOriginal = request.form.get('nome_arquivo')
            MesStr = request.form.get('mes_ref') # Vem como 'YYYY-MM-DD'
            
            # Limpeza de segurança da data
            if MesStr and ' ' in MesStr: MesStr = MesStr.split(' ')[0]
            DataRef = datetime.strptime(MesStr, '%Y-%m-%d').date()

            # Chamada corrigida
            Ok, Msg = AeroportoService.ProcessarAeroportosFinal(
                CaminhoTemp, 
                DataRef, 
                NomeOriginal, 
                current_user.Nome, 
                'Substituicao'
            )
            if Ok: flash(Msg, 'success')
            else: flash(Msg, 'danger')
            return redirect(url_for('Aeroporto.Gerenciar'))

    # Chamada corrigida
    Historico = AeroportoService.ListarRemessasAeroportos()
    return render_template('Aeroportos/Gerenciar.html', 
                           ListaRemessas=Historico, 
                           ExibirModal=ModalConfirmacao, 
                           DadosModal=DadosConfirmacao)

@AeroportoBp.route('/Aeroportos/Excluir/<int:id_remessa>')
@login_required
def Excluir(id_remessa):
    # Chamada corrigida
    Sucesso, Mensagem = AeroportoService.ExcluirRemessaAeroporto(id_remessa)
    if Sucesso: flash(Mensagem, 'info')
    else: flash(Mensagem, 'danger')
    return redirect(url_for('Aeroporto.Gerenciar'))