from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from Services.PlanejamentoService import BuscarCtcsAereoHoje

PlanejamentoBp = Blueprint('Planejamento', __name__)

@PlanejamentoBp.route('/planejamento/dashboard')
@login_required
def Dashboard():
    return render_template('Planejamento/Dashboard.html')

# API para o "On Time" (chamada via AJAX)
@PlanejamentoBp.route('/planejamento/api/ctcs-hoje')
@login_required
def ApiCtcsHoje():
    Dados = BuscarCtcsAereoHoje()
    return jsonify(Dados)