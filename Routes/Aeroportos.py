from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
# Importa a CLASSE do Serviço agora, não as funções soltas
from Services.AeroportosService import AeroportoService
from Services.LogService import LogService # <--- Import Log

AeroportoBp = Blueprint('Aeroporto', __name__)

@AeroportoBp.route('/Aeroportos/API/Listar-Simples')
@login_required
def ApiListarSimples():
    try:
        # Chamada corrigida: AeroportoService.ListarTodosParaSelect()
        Dados = AeroportoService.ListarTodosParaSelect()
        return jsonify(Dados)
    except Exception as e:
        LogService.Error("Route.Aeroportos", "Erro na API Listar-Simples", e)
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
            LogService.Info("Route.Aeroportos", f"Usuário {current_user.Login} enviou arquivo: {Arquivo.filename}")
            
            if Arquivo.filename == '':
                flash('Selecione um arquivo .csv', 'warning')
            else:
                # Chamada corrigida
                Sucesso, Info = AeroportoService.AnalisarArquivoAeroportos(Arquivo)
                
                if not Sucesso:
                    flash(Info, 'danger')
                    LogService.Warning("Route.Aeroportos", f"Falha na análise inicial: {Info}")
                else:
                    if Info['conflito']:
                        ModalConfirmacao = True
                        DadosConfirmacao = Info
                        LogService.Info("Route.Aeroportos", "Conflito detectado, solicitando confirmação ao usuário.")
                    else:
                        # Chamada corrigida
                        Ok, Msg = AeroportoService.ProcessarAeroportosFinal(
                            Info['caminho_temp'], 
                            Info['mes_ref'], 
                            Info['nome_arquivo'], 
                            current_user.Login, 
                            'Importacao'
                        )
                        if Ok: flash(Msg, 'success')
                        else: flash(Msg, 'danger')
                        return redirect(url_for('Aeroporto.Gerenciar'))

        # --- Confirmação do Modal ---
        elif 'confirmar_substituicao' in request.form:
            LogService.Info("Route.Aeroportos", f"Usuário {current_user.Login} confirmou substituição de base.")
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
                current_user.Login, 
                'Substituicao'
            )
            if Ok: flash(Msg, 'success')
            else: flash(Msg, 'danger')
            return redirect(url_for('Aeroporto.Gerenciar'))

    # Chamada corrigida
    Historico = AeroportoService.ListarRemessasAeroportos()
    return render_template('Aeroportos/Manager.html', 
                           ListaRemessas=Historico, 
                           ExibirModal=ModalConfirmacao, 
                           DadosModal=DadosConfirmacao)

@AeroportoBp.route('/Aeroportos/Excluir/<int:id_remessa>')
@login_required
def Excluir(id_remessa):
    LogService.Info("Route.Aeroportos", f"Usuário {current_user.Login} solicitou exclusão da remessa {id_remessa}")
    # Chamada corrigida
    Sucesso, Mensagem = AeroportoService.ExcluirRemessaAeroporto(id_remessa)
    if Sucesso: flash(Mensagem, 'info')
    else: flash(Mensagem, 'danger')
    return redirect(url_for('Aeroporto.Gerenciar'))