from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime # <--- AQUI: Importação correta da classe
from Services.MalhaService import AnalisarArquivo, ProcessarMalhaFinal, ListarRemessas, ExcluirRemessa

MalhaBp = Blueprint('Malha', __name__)

@MalhaBp.route('/malha/gerenciar', methods=['GET', 'POST'])
@login_required
def Gerenciar():
    # Variáveis para controlar o Modal de Confirmação
    ModalConfirmacao = False
    DadosConfirmacao = {}

    if request.method == 'POST':
        # --- FLUXO 1: Upload Inicial ---
        if 'arquivo_xlsx' in request.files:
            Arquivo = request.files['arquivo_xlsx']
            if Arquivo.filename == '':
                flash('Selecione um arquivo.', 'warning')
            else:
                Sucesso, Info = AnalisarArquivo(Arquivo)
                
                if not Sucesso:
                    flash(Info, 'danger')
                else:
                    # Se detectou conflito (já existe malha ativa), abre o Modal
                    if Info['conflito']:
                        ModalConfirmacao = True
                        DadosConfirmacao = Info
                    else:
                        # Se NÃO tem conflito, processa direto como 'Importação'
                        Ok, Msg = ProcessarMalhaFinal(
                            Info['caminho_temp'], 
                            Info['mes_ref'], 
                            Info['nome_arquivo'], 
                            current_user.Nome, 
                            'Importacao'
                        )
                        if Ok: flash(Msg, 'success')
                        else: flash(Msg, 'danger')
                        return redirect(url_for('Malha.Gerenciar'))

        # --- FLUXO 2: Confirmação de Substituição (Vem do Modal) ---
        elif 'confirmar_substituicao' in request.form:
            CaminhoTemp = request.form.get('caminho_temp')
            NomeOriginal = request.form.get('nome_arquivo')
            
            # Recupera a data do formulário (Ex: "2026-01-01" ou "2026-01-01 00:00:00")
            MesStr = request.form.get('mes_ref')
            
            # BLINDAGEM: Remove o horário se vier junto (corrige o erro 'unconverted data remains')
            if MesStr and ' ' in MesStr:
                MesStr = MesStr.split(' ')[0]
            
            try:
                # Converte string para objeto date
                DataRef = datetime.strptime(MesStr, '%Y-%m-%d').date()
                
                Ok, Msg = ProcessarMalhaFinal(
                    CaminhoTemp, 
                    DataRef, 
                    NomeOriginal, 
                    current_user.Nome, 
                    'Substituicao'
                )
                if Ok: flash(Msg, 'success')
                else: flash(Msg, 'danger')
                
            except Exception as e:
                flash(f"Erro ao processar data: {e}", 'danger')

            return redirect(url_for('Malha.Gerenciar'))

    Historico = ListarRemessas()
    
    return render_template('Malha/Gerenciar.html', 
                           ListaRemessas=Historico, 
                           ExibirModal=ModalConfirmacao, 
                           DadosModal=DadosConfirmacao)

@MalhaBp.route('/malha/excluir/<int:id_remessa>')
@login_required
def Excluir(id_remessa):
    Sucesso, Mensagem = ExcluirRemessa(id_remessa)
    if Sucesso: flash(Mensagem, 'info')
    else: flash(Mensagem, 'danger')
    return redirect(url_for('Malha.Gerenciar'))