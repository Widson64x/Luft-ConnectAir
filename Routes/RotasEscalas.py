from flask import Blueprint, jsonify, render_template
from flask_login import login_required
from datetime import datetime
from Services.MalhaService import ObterTotalVoosData

EscalasBp = Blueprint('Escalas', __name__)

@EscalasBp.route('/Mapa')
@login_required
def Mapa():
    # Renderiza o template que conterá o mapa (antigo mapa da Malha)
    return render_template('Escalas/Index.html')

# 1. Removi '/escalas' da rota pois já está no prefixo do Blueprint em App.py
# 2. Renomeei a função da rota para não conflitar com nomes de serviço
# 3. Chamo a função correta do Service passando o argumento
@EscalasBp.route('/API/Voos-Hoje') 
@login_required
def ApiVoosHoje():
    Hoje = datetime.now()
    # Chama a função do Service que aceita a data
    Quantidade = ObterTotalVoosData(Hoje)
    return jsonify(Quantidade)