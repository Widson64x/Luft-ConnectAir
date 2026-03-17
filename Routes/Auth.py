from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from Services.AuthService import AuthService
from Models.UsuarioModel import UsuarioSistema
from Services.LogService import LogService
from datetime import timedelta

AuthBp = Blueprint('Auth', __name__)

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

            flash(f'Bem-vindo(a) a bordo, {dadosUsuario["nome"]}! ✈️', 'success')

            proximaPagina = url_for('Dashboard')
            return redirect(proximaPagina)

        else:
            LogService.Warning("Routes.Auth", f"Login recusado para '{identificador}' (IP: {ipCliente}).")
            flash('Login falhou. Verifique suas credenciais.', 'danger')

    return render_template('Auth/Login.html')

@AuthBp.route('/Deslogar')
@login_required
def logout():
    userLogin = current_user.Login if current_user.is_authenticated else "Desconhecido"
    LogService.Info("Routes.Auth", f"Usuário solicitou logout: {userLogin}")

    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('Auth.login'))