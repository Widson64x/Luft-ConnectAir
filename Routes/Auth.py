from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from Services.AuthService import AuthService
from Models.UsuarioModel import UsuarioSistema
from Services.LogService import LogService
from datetime import timedelta

AuthBp = Blueprint('Auth', __name__)

@AuthBp.route('/Logar', methods=['GET', 'POST'])
def Login():
    if request.method == 'POST':
        # O campo do form continua 'username', mas o usuário pode ter digitado o e-mail
        Identificador = request.form.get('username')
        Password = request.form.get('password')
        IpCliente = request.remote_addr

        LogService.Info("Routes.Auth", f"Recebida requisição de login. Identificador: {Identificador} | IP: {IpCliente}")

        # Chama a validação que agora aceita e-mail ou login
        DadosUsuario = AuthService.ValidarAcessoCompleto(Identificador, Password)

        if DadosUsuario:
            LogService.Info("Routes.Auth", f"Login aprovado. Criando sessão para: {DadosUsuario['login']}")

            UsuarioLogado = UsuarioSistema(
                Login=DadosUsuario['login'],
                Nome=DadosUsuario['nome'],
                Email=DadosUsuario['email'],
                Grupo=DadosUsuario['grupo'],
                IdBanco=DadosUsuario['id'],
                Id_Grupo_Banco=DadosUsuario.get('id_grupo')
            )

            # Define duração da sessão
            login_user(UsuarioLogado, duration=timedelta(hours=8))

            flash(f'Bem-vindo(a) a bordo, {DadosUsuario["nome"]}! ✈️', 'success')

            ProximaPagina = url_for('Dashboard')
            # Ajuste aqui para redirecionar corretamente
            return redirect(ProximaPagina)

        else:
            LogService.Warning("Routes.Auth", f"Login recusado para '{Identificador}' (IP: {IpCliente}).")
            flash('Login falhou. Verifique suas credenciais.', 'danger')

    return render_template('Auth/Login.html')

@AuthBp.route('/Deslogar')
@login_required
def Logout():
    user_login = current_user.Login if current_user.is_authenticated else "Desconhecido"
    LogService.Info("Routes.Auth", f"Usuário solicitou logout: {user_login}")

    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('Auth.Login'))