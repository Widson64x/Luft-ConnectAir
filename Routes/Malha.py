from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from Services.MalhaService import MalhaService
from Services.LogService import LogService # <--- Import Adicionado
MalhaBp = Blueprint('Malha', __name__)

@MalhaBp.route('/Malha/API/Rotas')
@login_required
def ApiRotas():
    Inicio = request.args.get('inicio')
    Fim = request.args.get('fim')
    Origem = request.args.get('origem')
    Destino = request.args.get('destino')
    NumeroVoo = request.args.get('numero_voo') # Novo parâmetro capturado
    
    if not Inicio or not Fim:
        return jsonify([])

    try:
        from datetime import datetime
        DataIni = datetime.strptime(Inicio, '%Y-%m-%d').date()
        DataFim = datetime.strptime(Fim, '%Y-%m-%d').date()
        
        LogService.Info("Routes.Malha", f"API Rota Solicitada por {current_user.Nome}: {Origem}->{Destino} ({Inicio} a {Fim})")

        # Chama a busca inteligente passando o novo parâmetro
        Dados = MalhaService.BuscarRotasInteligentes(DataIni, DataFim, Origem, Destino, NumeroVoo)
        
        return jsonify(Dados)
    except Exception as e:
        LogService.Error("Routes.Malha", "Erro na API de Rotas", e)
        return jsonify({'erro': str(e)}), 500

@MalhaBp.route('/Malha/Gerenciar', methods=['GET', 'POST'])
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
                LogService.Info("Routes.Malha", f"Upload de Malha iniciado por {current_user.Nome}")
                Sucesso, Info = MalhaService.AnalisarArquivo(Arquivo)
                
                if not Sucesso:
                    LogService.Warning("Routes.Malha", f"Upload falhou na análise: {Info}")
                    flash(Info, 'danger')
                else:
                    # Se detectou conflito (já existe malha ativa), abre o Modal
                    if Info['conflito']:
                        LogService.Info("Routes.Malha", "Conflito de malha detectado. Aguardando confirmação do usuário.")
                        ModalConfirmacao = True
                        DadosConfirmacao = Info
                    else:
                        # Se NÃO tem conflito, processa direto como 'Importação'
                        Ok, Msg = MalhaService.ProcessarMalhaFinal(
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
                LogService.Info("Routes.Malha", f"Usuário {current_user.Nome} confirmou substituição de malha.")
                # Converte string para objeto date
                DataRef = datetime.strptime(MesStr, '%Y-%m-%d').date()
                
                Ok, Msg = MalhaService.ProcessarMalhaFinal(
                    CaminhoTemp, 
                    DataRef, 
                    NomeOriginal, 
                    current_user.Nome, 
                    'Substituicao'
                )
                if Ok: flash(Msg, 'success')
                else: flash(Msg, 'danger')
                
            except Exception as e:
                LogService.Error("Routes.Malha", "Erro ao processar data na confirmação", e)
                flash(f"Erro ao processar data: {e}", 'danger')

            return redirect(url_for('Malha.Gerenciar'))

    Historico = MalhaService.ListarRemessas()
    
    return render_template('Malha/Manager.html', 
                           ListaRemessas=Historico, 
                           ExibirModal=ModalConfirmacao, 
                           DadosModal=DadosConfirmacao)

@MalhaBp.route('/Malha/Excluir/<int:id_remessa>')
@login_required
def Excluir(id_remessa):
    LogService.Warning("Routes.Malha", f"Solicitação de exclusão de remessa {id_remessa} por {current_user.Nome}")
    Sucesso, Mensagem = MalhaService.ExcluirRemessa(id_remessa)
    if Sucesso: flash(Mensagem, 'info')
    else: flash(Mensagem, 'danger')
    return redirect(url_for('Malha.Gerenciar'))