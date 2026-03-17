from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from Services.AeroportosService import AeroportoService
from Services.LogService import LogService
from Services.PermissaoService import RequerPermissao 
from luftcore.extensions.flask_extension import require_ajax

AeroportoBp = Blueprint('Aeroporto', __name__)

@AeroportoBp.route('/API/Listar-Simples')
@login_required
@require_ajax
@RequerPermissao('CADASTROS.AEROPORTOS.VISUALIZAR')
def apiListarSimples():
    try:
        dados = AeroportoService.ListarTodosParaSelect()
        return jsonify(dados)
    except Exception as e:
        LogService.Error("Route.Aeroportos", "Erro na API Listar-Simples", e)
        return jsonify([]), 500

@AeroportoBp.route('/Gerenciar', methods=['GET', 'POST'])
@login_required
@RequerPermissao('CADASTROS.AEROPORTOS.EDITAR')
def gerenciar():
    modalConfirmacao = False
    dadosConfirmacao = {}

    if request.method == 'POST':
        # --- Upload Inicial ---
        if 'arquivo_csv' in request.files:
            arquivoCsv = request.files['arquivo_csv']
            LogService.Info("Route.Aeroportos", f"Usuário {current_user.Login} enviou arquivo: {arquivoCsv.filename}")
            
            if arquivoCsv.filename == '':
                flash('Selecione um arquivo .csv', 'warning')
            else:
                sucesso, info = AeroportoService.AnalisarArquivoAeroportos(arquivoCsv)
                
                if not sucesso:
                    flash(info, 'danger')
                    LogService.Warning("Route.Aeroportos", f"Falha na análise inicial: {info}")
                else:
                    if info['conflito']:
                        modalConfirmacao = True
                        dadosConfirmacao = info
                        LogService.Info("Route.Aeroportos", "Conflito detectado, solicitando confirmação ao usuário.")
                    else:
                        ok, msg = AeroportoService.ProcessarAeroportosFinal(
                            info['caminho_temp'], 
                            info['mes_ref'], 
                            info['nome_arquivo'], 
                            current_user.Login, 
                            'Importacao'
                        )
                        if ok: flash(msg, 'success')
                        else: flash(msg, 'danger')
                        return redirect(url_for('Aeroporto.gerenciar'))

        # --- Confirmação do Modal ---
        elif 'confirmar_substituicao' in request.form:
            LogService.Info("Route.Aeroportos", f"Usuário {current_user.Login} confirmou substituição de base.")
            caminhoTemp = request.form.get('caminho_temp')
            nomeOriginal = request.form.get('nome_arquivo')
            mesStr = request.form.get('mes_ref') 
            
            # Limpeza de segurança da data
            if mesStr and ' ' in mesStr: mesStr = mesStr.split(' ')[0]
            dataRef = datetime.strptime(mesStr, '%Y-%m-%d').date()

            ok, msg = AeroportoService.ProcessarAeroportosFinal(
                caminhoTemp, 
                dataRef, 
                nomeOriginal, 
                current_user.Login, 
                'Substituicao'
            )
            if ok: flash(msg, 'success')
            else: flash(msg, 'danger')
            return redirect(url_for('Aeroporto.gerenciar'))

    historicoRemessas = AeroportoService.ListarRemessasAeroportos()
    return render_template('Cadastros/Aeroportos/Manager.html', 
                           ListaRemessas=historicoRemessas, 
                           ExibirModal=modalConfirmacao, 
                           DadosModal=dadosConfirmacao)

@AeroportoBp.route('/Excluir/<int:id_remessa>')
@login_required
@RequerPermissao('CADASTROS.AEROPORTOS.DELETAR')
def excluir(id_remessa):
    LogService.Info("Route.Aeroportos", f"Usuário {current_user.Login} solicitou exclusão da remessa {id_remessa}")
    sucesso, mensagem = AeroportoService.ExcluirRemessaAeroporto(id_remessa)
    if sucesso: flash(mensagem, 'info')
    else: flash(mensagem, 'danger')
    return redirect(url_for('Aeroporto.gerenciar'))

@AeroportoBp.route('/Ranking')
@login_required
@RequerPermissao('CADASTROS.AEROPORTOS.VISUALIZAR') 
def rankingIndex():
    dadosAeroportos = AeroportoService.ListarAeroportosPorEstado()
    return render_template('Cadastros/Aeroportos/Ranking.html', Dados=dadosAeroportos)

@AeroportoBp.route('/API/SalvarRanking', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CADASTROS.AEROPORTOS.EDITAR')
def salvarRanking():
    try:
        dadosRequisicao = request.json
        siglaUf = dadosRequisicao.get('uf')
        listaAeroportos = dadosRequisicao.get('aeroportos') 
        
        sucesso, msg = AeroportoService.SalvarRankingUf(siglaUf, listaAeroportos)
        return jsonify({'sucesso': sucesso, 'msg': msg})
    except Exception as erro:
        return jsonify({'sucesso': False, 'msg': str(erro)}), 500