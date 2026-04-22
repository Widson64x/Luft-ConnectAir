from flask import Blueprint, render_template, jsonify, request, send_file, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import timedelta, datetime, date
from luftcore.extensions.flask_extension import require_ajax

# Import dos Serviços
from Services.PermissaoService import RequerPermissao
from Services.PlanejamentoService import PlanejamentoService
from Services.Shared.GeoService import BuscarCoordenadasCidade, BuscarAeroportoEstrategico, BuscarTopAeroportos
from Services.LogService import LogService
from Services.Logic.RouteIntelligenceService import RouteIntelligenceService
from Services.Logic.RouteMLEngine import RouteMLEngine

PlanejamentoBp = Blueprint('Planejamento', __name__)

COORDENADAS_UFS = {
    'AC': {'lat': -9.02, 'lon': -70.81}, 'AL': {'lat': -9.57, 'lon': -36.78},
    'AP': {'lat': 0.90, 'lon': -52.00},  'AM': {'lat': -3.41, 'lon': -65.87},
    'BA': {'lat': -12.57, 'lon': -41.70},'CE': {'lat': -5.49, 'lon': -39.32},
    'DF': {'lat': -15.79, 'lon': -47.88},'ES': {'lat': -19.18, 'lon': -40.30},
    'GO': {'lat': -15.82, 'lon': -49.83},'MA': {'lat': -4.96, 'lon': -45.27},
    'MT': {'lat': -12.68, 'lon': -56.92},'MS': {'lat': -20.77, 'lon': -54.78},
    'MG': {'lat': -18.51, 'lon': -44.55},'PA': {'lat': -1.99, 'lon': -54.93},
    'PB': {'lat': -7.23, 'lon': -36.78}, 'PR': {'lat': -25.25, 'lon': -52.02},
    'PE': {'lat': -8.81, 'lon': -36.95}, 'PI': {'lat': -7.71, 'lon': -42.72},
    'RJ': {'lat': -22.90, 'lon': -43.17},'RN': {'lat': -5.40, 'lon': -36.95},
    'RS': {'lat': -30.03, 'lon': -51.22},'RO': {'lat': -11.50, 'lon': -63.58},
    'RR': {'lat': 2.82, 'lon': -60.67},  'SC': {'lat': -27.24, 'lon': -50.21},
    'SP': {'lat': -23.55, 'lon': -46.63},'SE': {'lat': -10.57, 'lon': -37.38},
    'TO': {'lat': -10.17, 'lon': -48.33}
}


def _carregar_dados_editor_planejamento(filial, serie, ctc, servicos_escolhidos=None):
    return PlanejamentoService.MontarDadosPlanejamento(filial, serie, ctc, servicos_escolhidos)


def _calcular_contexto_rotas_editor(dados_ctc, dados_unificados, emitir_flash=False, ml_context=None):
    coord_origem = BuscarCoordenadasCidade(dados_ctc['origem_cidade'], dados_ctc['origem_uf'])
    coord_destino = BuscarCoordenadasCidade(dados_ctc['destino_cidade'], dados_ctc['destino_uf'])

    lista_origem = BuscarTopAeroportos(coord_origem['lat'], coord_origem['lon'], limite=5) if coord_origem else []
    lista_destino = BuscarTopAeroportos(coord_destino['lat'], coord_destino['lon'], limite=5) if coord_destino else []

    opcoes_rotas = {}
    if dados_unificados and not dados_unificados.get('servico_pendente'):
        iatas_origem = [a['iata'] for a in lista_origem]
        iatas_destino = [a['iata'] for a in lista_destino]

        if iatas_origem and iatas_destino:
            data_inicio_busca = dados_unificados['data_busca']
            peso_total = float(dados_unificados.get('peso_taxado', 0.0))
            if peso_total <= 0:
                peso_total = float(dados_unificados.get('peso_fisico', 10.0))

            data_limite = data_inicio_busca + timedelta(days=7)
            LogService.Info(
                "Routes.Planejamento",
                f"Buscando opções de rotas de {iatas_origem} para {iatas_destino} entre {data_inicio_busca} e {data_limite} com peso {peso_total}kg."
            )
            opcoes_rotas = RouteIntelligenceService.BuscarOpcoesDeRotas(
                data_inicio_busca,
                data_limite,
                iatas_origem,
                iatas_destino,
                peso_total,
                tipo_carga=dados_unificados.get('tipo_carga'),
                servico_contratado=dados_unificados.get('servico_roteamento') or dados_unificados.get('servico_contratado'),
                ml_context=ml_context,
            )

            if not opcoes_rotas and emitir_flash:
                flash("Atenção: Nenhuma rota aérea ativa foi encontrada para os parâmetros informados.", "warning")
        elif emitir_flash:
            flash("Atenção: Não foram encontrados aeroportos viáveis próximos à origem ou destino.", "warning")
    elif dados_unificados and dados_unificados.get('servico_pendente') and emitir_flash:
        flash("Defina o serviço dos clientes com regra por destino para calcular as rotas deste lote.", "info")

    return {
        'coord_origem': coord_origem,
        'coord_destino': coord_destino,
        'aero_origem_principal': lista_origem[0] if lista_origem else None,
        'aero_destino_principal': lista_destino[0] if lista_destino else None,
        'opcoes_rotas': opcoes_rotas
    }

@PlanejamentoBp.route('/Dashboard')
@login_required
@RequerPermissao('PLANEJAMENTO.ROTAS.VISUALIZAR')
def dashboard():
    LogService.Info("Routes.Planejamento", f"Usuário {current_user.id} acessou Dashboard Planejamento.")
    return render_template('Pages/Planejamento/Index.html')

@PlanejamentoBp.route('/API/Listar')
@login_required
@require_ajax
@RequerPermissao('PLANEJAMENTO.ROTAS.VISUALIZAR')
def apiCtcsHoje():
    LogService.Debug("Routes.Planejamento", "API Listar CTCs requisitada.")

    sincronizacao = PlanejamentoService.SincronizarStatusPlanejamentosComAwb()
    if sincronizacao.get('modo') == 'erro':
        LogService.Warning(
            "Routes.Planejamento",
            f"Falha ao sincronizar planejamentos com AWB antes da listagem: {sincronizacao.get('erro', 'erro não informado')}"
        )
    elif sincronizacao.get('planejamentos_atualizados'):
        LogService.Info(
            "Routes.Planejamento",
            f"Sincronização AWB concluída antes da listagem. Planejamentos atualizados: {sincronizacao['planejamentos_atualizados']}"
        )

    dadosCtc = PlanejamentoService.BuscarCtcsPlanejamento()
    return jsonify(dadosCtc)

@PlanejamentoBp.route('/Montar/<string:filial>/<string:serie>/<string:ctc>')
@login_required
@RequerPermissao('PLANEJAMENTO.ROTAS.EDITAR')
def montarPlanejamento(filial, serie, ctc):
    LogService.Info("Routes.Planejamento", f"Iniciando Montagem Planejamento: {filial}-{serie}-{ctc}")

    dadosCtc, _, dadosUnificados = _carregar_dados_editor_planejamento(filial, serie, ctc)
    
    # Se os dados do CTC não forem encontrados ou já tiverem sido processados, redireciona de volta com mensagem de erro
    if not dadosCtc: 
        flash(f"Erro: O CTC {filial}-{serie}-{ctc} não foi encontrado ou já foi processado.", "danger")
        return redirect(url_for('Planejamento.dashboard'))

    # Se houver consolidação, exibe uma mensagem informando quantos CTCs foram consolidados para este planejamento
    if dadosUnificados.get('is_consolidado'):
        flash(f"Lote virtual criado: {dadosUnificados.get('qtd_docs')} CTCs foram consolidados para esta rota.", "success")

    # Se já existe planejamento ativo para este CTC, abre direto em modo visualização
    # sem calcular rotas (evita o processo caro de ~2 minutos)
    planejamentoSalvo = PlanejamentoService.ObterPlanejamentoPorCtc(filial, serie, ctc)

    if planejamentoSalvo:
        LogService.Info("Routes.Planejamento", f"Planejamento ativo encontrado (ID {planejamentoSalvo['id_planejamento']}) — abrindo modo visualização.")
        coord_origem = BuscarCoordenadasCidade(dadosCtc['origem_cidade'], dadosCtc['origem_uf'])
        coord_destino = BuscarCoordenadasCidade(dadosCtc['destino_cidade'], dadosCtc['destino_uf'])
        return render_template('Pages/Planejamento/Editor.html',
                               Ctc=dadosUnificados,
                               Origem=coord_origem,
                               Destino=coord_destino,
                               AeroOrigem=None,
                               AeroDestino=None,
                               OpcoesRotas={},
                               PlanejamentoSalvo=planejamentoSalvo)

    # Sem planejamento ativo (primeira montagem ou após cancelamento) — monta rotas completo
    contexto_rotas = _calcular_contexto_rotas_editor(
        dadosCtc, dadosUnificados, emitir_flash=True,
        ml_context={'filial': filial, 'serie': serie, 'ctc': ctc, 'usuario': current_user.id}
    )

    return render_template('Pages/Planejamento/Editor.html', 
                           Ctc=dadosUnificados, 
                           Origem=contexto_rotas['coord_origem'], Destino=contexto_rotas['coord_destino'],
                           AeroOrigem=contexto_rotas['aero_origem_principal'],
                           AeroDestino=contexto_rotas['aero_destino_principal'],
                           OpcoesRotas=contexto_rotas['opcoes_rotas'],
                           PlanejamentoSalvo=None) 


@PlanejamentoBp.route('/API/OpcoesRotas', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('PLANEJAMENTO.ROTAS.EDITAR')
def apiOpcoesRotasPlanejamento():
    try:
        dadosFront = request.json or {}
        filial = dadosFront.get('filial')
        serie = dadosFront.get('serie')
        ctc = dadosFront.get('ctc')
        servicos_escolhidos = dadosFront.get('servicos_escolhidos', {})

        dadosCtc, _, dadosUnificados = _carregar_dados_editor_planejamento(
            filial,
            serie,
            ctc,
            servicos_escolhidos=servicos_escolhidos
        )

        if not dadosCtc or not dadosUnificados:
            return jsonify({'sucesso': False, 'msg': 'CTC não encontrado para cálculo de rotas.'}), 404

        if dadosUnificados.get('servico_pendente'):
            return jsonify({'sucesso': False, 'msg': 'Existem clientes com serviço pendente de definição.', 'ctc': dadosUnificados}), 400

        contexto_rotas = _calcular_contexto_rotas_editor(
            dadosCtc, dadosUnificados, emitir_flash=False,
            ml_context={'filial': filial, 'serie': serie, 'ctc': ctc, 'usuario': current_user.id}
        )
        return jsonify({
            'sucesso': True,
            'ctc': dadosUnificados,
            'opcoes_rotas': contexto_rotas['opcoes_rotas']
        })
    except Exception as e:
        LogService.Error("Routes.Planejamento", "Erro ao recalcular opções de rota", e)
        return jsonify({'sucesso': False, 'msg': f'Erro ao calcular rotas: {str(e)}'}), 500

@PlanejamentoBp.route('/API/Cancelar', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('PLANEJAMENTO.ROTAS.EDITAR')
def cancelarPlanejamentoRota():
    dadosRequisicao = request.json
    idPlan = dadosRequisicao.get('id_planejamento')
    
    if not idPlan: 
        return jsonify({'sucesso': False, 'msg': 'ID de planejamento inválido para cancelamento.'})
    
    sucesso, msg = PlanejamentoService.CancelarPlanejamento(idPlan, current_user.id)
    
    if sucesso:
        RouteMLEngine.DesvincularPlanejamento(idPlan)
        msg = "Planejamento cancelado com sucesso. Os CTCs retornaram para a fila de pendências."
        
    return jsonify({'sucesso': sucesso, 'msg': msg})

@PlanejamentoBp.route('/API/Salvar', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('PLANEJAMENTO.ROTAS.EDITAR')
def salvarPlanejamento():
    try:
        dadosFront = request.json
        if not dadosFront: 
            return jsonify({'sucesso': False, 'msg': 'Nenhum dado recebido do formulário.'}), 400

        filial = dadosFront.get('filial')
        serie = dadosFront.get('serie')
        ctc = dadosFront.get('ctc')
        servicos_escolhidos = dadosFront.get('servicos_escolhidos', {})
        
        LogService.Info("Routes.Planejamento", f"Recebendo requisição de salvamento para {filial}-{serie}-{ctc}")

        rotaCompleta = dadosFront.get('rota_completa', [])
        motor_escolha = dadosFront.get('motor_escolha', 'GRAFO') 

        dadosCtc, ctcsCandidatos, dadosUnificados = _carregar_dados_editor_planejamento(
            filial,
            serie,
            ctc,
            servicos_escolhidos=servicos_escolhidos
        )

        if not dadosCtc or not dadosUnificados:
            return jsonify({'sucesso': False, 'msg': 'CTC não encontrado para gravação.'}), 404

        if dadosUnificados.get('servico_pendente'):
            return jsonify({'sucesso': False, 'msg': 'Defina o serviço de todos os clientes pendentes antes de confirmar a rota.'}), 400
        
        coordOrigem = BuscarCoordenadasCidade(dadosCtc['origem_cidade'], dadosCtc['origem_uf'])
        coordDestino = BuscarCoordenadasCidade(dadosCtc['destino_cidade'], dadosCtc['destino_uf'])
        
        aeroOrigem = None
        aeroDestino = None

        if coordOrigem:
            aeroOrigem = BuscarAeroportoEstrategico(
                coordOrigem['lat'], coordOrigem['lon'], coordOrigem['uf']
            )
            
        if coordDestino:
            aeroDestino = BuscarAeroportoEstrategico(
                coordDestino['lat'], coordDestino['lon'], coordDestino['uf']
            )
        
        idPlanejamento = PlanejamentoService.RegistrarPlanejamento(
            dadosUnificados, 
            ctcsCandidatos, 
            current_user.id if current_user.is_authenticated else "Anonimo",
            status_inicial='Em Planejamento',
            aero_origem=aeroOrigem['iata'] if aeroOrigem else None,
            aero_destino=aeroDestino['iata'] if aeroDestino else None,
            lista_trechos=rotaCompleta,
            motor_escolha=motor_escolha
        )
        
        if idPlanejamento: 
            LogService.Info("Routes.Planejamento", f"Planejamento salvo com sucesso. ID Retornado: {idPlanejamento}")
            RouteMLEngine.VincularPlanejamento(
                filial=filial,
                serie=serie,
                ctc=ctc,
                id_planejamento=idPlanejamento,
                categoria_escolhida=dadosFront.get('estrategia', ''),
            )
            return jsonify({
                'sucesso': True, 
                'id_planejamento': idPlanejamento, 
                'msg': 'Planejamento registrado com sucesso! O lote foi encaminhado para a próxima etapa.'
            })
        
        LogService.Error("Routes.Planejamento", "Service retornou None ao salvar.")
        return jsonify({'sucesso': False, 'msg': 'Erro interno ao tentar gravar os trechos do voo. Contate o suporte.'}), 500

    except Exception as e:
        LogService.Error("Routes.Planejamento", "Exceção ao salvar planejamento", e)
        msgErro = str(e)
        
        if "TRAVA DE CORTE" in msgErro:
            return jsonify({'sucesso': False, 'msg': msgErro}), 400
            
        return jsonify({'sucesso': False, 'msg': f"Erro ao registrar planejamento: {msgErro}"}), 500

@PlanejamentoBp.route('/API/Exportar')
@login_required
@RequerPermissao('PLANEJAMENTO.ROTAS.EXPORTAR')
def exportarPlanejamentosExcel():
    LogService.Info("Routes.Planejamento", f"Usuário {current_user.id} solicitou exportação de planejamento.")
    
    arquivoGerado = PlanejamentoService.GerarExcelPlanejamentos()
    
    if not arquivoGerado:
        flash("Erro de Conexão: Não foi possível gerar o arquivo de planejamento no momento. Tente novamente.", "danger")
        return redirect(url_for('Planejamento.dashboard'))

    nomeArquivo = f'Planejamento_Aereo_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
    
    return send_file(
        arquivoGerado,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=nomeArquivo
    )

@PlanejamentoBp.route('/Mapa-Global')
@login_required
@RequerPermissao('PLANEJAMENTO.MAPA.VISUALIZAR')
def mapaGlobal():
    try:
        LogService.Debug("Routes.Planejamento", "Gerando Mapa Global...")
        listaCtcs = PlanejamentoService.BuscarCtcsPlanejamento()
        agrupamentoCtcs = {}

        for ctcItem in listaCtcs:
            try:
                _, ufOrig = ctcItem['origem'].split('/')
                ufOrig = ufOrig.strip().upper()
                
                if ufOrig not in agrupamentoCtcs:
                    agrupamentoCtcs[ufOrig] = {
                        'uf': ufOrig,
                        'coords': COORDENADAS_UFS.get(ufOrig, {'lat': -15, 'lon': -47}),
                        'qtd_docs': 0,
                        'qtd_vols': 0,
                        'valor_total': 0.0,
                        'tem_urgencia': False,
                        'lista_ctcs': []
                    }
                
                agrupamentoCtcs[ufOrig]['qtd_docs'] += 1
                agrupamentoCtcs[ufOrig]['qtd_vols'] += int(ctcItem['volumes'])
                agrupamentoCtcs[ufOrig]['valor_total'] += ctcItem['raw_val_mercadoria']
                
                if 'URGENTE' in str(ctcItem['prioridade']).upper():
                    agrupamentoCtcs[ufOrig]['tem_urgencia'] = True
                    ctcItem['eh_urgente'] = True 
                else:
                    ctcItem['eh_urgente'] = False

                agrupamentoCtcs[ufOrig]['lista_ctcs'].append(ctcItem)

            except Exception as e:
                LogService.Warning("Routes.Planejamento", f"Erro ao agrupar item no mapa: {e}")
                continue
        
        dadosMapa = list(agrupamentoCtcs.values())
        return render_template('Pages/Planejamento/Map.html', Dados=dadosMapa)
    except Exception as e:
        LogService.Error("Routes.Planejamento", "Erro fatal ao renderizar Mapa Global", e)
        flash("Erro de Conexão: Não foi possível carregar os dados do mapa. Tente novamente em instantes.", "danger")
        return redirect(url_for('Planejamento.dashboard'))