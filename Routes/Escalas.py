from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required
from datetime import datetime
from Services.MalhaService import MalhaService
from Services.PermissaoService import RequerPermissao

EscalasBp = Blueprint('Escalas', __name__)

@EscalasBp.route('/Mapa')
@login_required
@RequerPermissao('cadastros.malha.visualizar')
def Mapa():
    """Renderiza a tela principal do mapa de escalas."""
    return render_template('Escalas/Index.html')

@EscalasBp.route('/Api/OtimizarRotas', methods=['GET'])
@login_required
@RequerPermissao('cadastros.malha.visualizar')
def ApiOtimizarRotas():
    """
    Rota API que processa a inteligência de rotas.
    Recebe: inicio, fim, origem, destino, peso
    Retorna: JSON com as opções (recomendada, mais_rapida, etc.)
    """
    try:
        # 1. Captura Argumentos
        data_inicio_str = request.args.get('inicio')
        data_fim_str = request.args.get('fim')
        origem = request.args.get('origem', '').upper()
        destino = request.args.get('destino', '').upper()
        peso_str = request.args.get('peso', '100')

        # 2. Validações Básicas
        if not (data_inicio_str and data_fim_str and origem and destino):
            return jsonify({'erro': 'Parâmetros incompletos.'}), 400

        # 3. Conversão de Tipos
        try:
            dt_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
            dt_fim = datetime.strptime(data_fim_str, '%Y-%m-%d')
            peso = float(peso_str)
        except ValueError:
            return jsonify({'erro': 'Formato de data ou peso inválido.'}), 400

        # 4. Chama o Serviço de Inteligência
        # O serviço retorna um dict: {'recomendada': [...], 'menor_custo': [...], ...}
        opcoes = MalhaService.BuscarOpcoesDeRotas(
            data_inicio=dt_inicio,
            data_fim=dt_fim,
            origem_iata=origem,
            destino_iata=destino,
            peso_total=peso
        )

        # Verifica se alguma rota foi encontrada
        total_rotas = sum(1 for v in opcoes.values() if v)
        if total_rotas == 0:
            return jsonify({'status': 'vazio', 'mensagem': 'Nenhuma combinação de rotas encontrada para estes parâmetros.'})

        return jsonify({'status': 'sucesso', 'dados': opcoes})

    except Exception as e:
        return jsonify({'erro': f'Erro interno: {str(e)}'}), 500