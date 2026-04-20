from datetime import datetime, timedelta, timezone

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user
from Services.AuthService import AuthService
from Models.UsuarioModel import UsuarioSistema
from Services.LogService import LogService
from Configuracoes import ConfiguracaoAtual

AuthBp = Blueprint('Auth', __name__)


def _MarcarSessaoAutenticada(usuario):
    session.permanent = True
    session['usuario_autenticado'] = usuario.ParaSessao()
    session['sessao_ultima_atividade_utc'] = datetime.now(timezone.utc).isoformat()


def _LimparEstadoSessao():
    session.pop('usuario_autenticado', None)
    session.pop('sessao_ultima_atividade_utc', None)

@AuthBp.route('/Logar', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identificador = request.form.get('username')
        password = request.form.get('password')
        ipCliente = request.remote_addr

        LogService.Info("Routes.Auth", f"Recebida requisição de login. Identificador: {identificador} | IP: {ipCliente}")

        dadosUsuario = AuthService.ValidarAcessoCompleto(identificador, password)

        if dadosUsuario:
            LogService.Info("Routes.Auth", f"Login aprovado. Criando sessão para: {dadosUsuario['login']}")

            usuarioLogado = UsuarioSistema(
                Login=dadosUsuario['login'],
                Nome=dadosUsuario['nome'],
                Email=dadosUsuario['email'],
                Grupo=dadosUsuario['grupo'],
                IdBanco=dadosUsuario['id'],
                Id_Grupo_Banco=dadosUsuario.get('id_grupo')
            )

            login_user(usuarioLogado, duration=timedelta(hours=8))
            _MarcarSessaoAutenticada(usuarioLogado)

            flash(f'Bem-vindo(a) a bordo, {dadosUsuario["nome"]}! ✈️', 'success')

            proximaPagina = url_for('Dashboard')
            return redirect(proximaPagina)

        else:
            LogService.Warning("Routes.Auth", f"Login recusado para '{identificador}' (IP: {ipCliente}).")
            flash('Login falhou. Verifique suas credenciais.', 'danger')

    return render_template('Auth/Login.html')

@AuthBp.route('/KeepAlive', methods=['POST'])
def keepalive():
    if not current_user.is_authenticated:
        return jsonify({'authenticated': False}), 401

    session.permanent = True
    session['sessao_ultima_atividade_utc'] = datetime.now(timezone.utc).isoformat()

    return ('', 204)

@AuthBp.route('/Deslogar')
def logout():
    motivo = (request.args.get('motivo') or 'manual').strip().lower()
    dadosSessao = session.get('usuario_autenticado') or {}
    userLogin = current_user.Login if current_user.is_authenticated else dadosSessao.get('Login', 'Desconhecido')

    if motivo == 'inatividade':
        LogService.Info("Routes.Auth", f"Sessão encerrada por inatividade: {userLogin}")
    else:
        LogService.Info("Routes.Auth", f"Usuário solicitou logout: {userLogin}")

    if current_user.is_authenticated:
        logout_user()

    _LimparEstadoSessao()

    if motivo == 'inatividade':
        flash(
            f'Sua sessão foi encerrada após {ConfiguracaoAtual.SESSAO_TIMEOUT_MINUTOS} minutos sem atividade.',
            'warning'
        )
    else:
        flash('Você saiu do sistema.', 'info')

    return redirect(url_for('Auth.login'))