from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from Services.AuthService import AuthService
from Models.UsuarioModel import UsuarioSistema
from Services.LogService import LogService # <--- Importação

AuthBp = Blueprint('Auth', __name__)

@AuthBp.route('/Logar', methods=['GET', 'POST'])
def Login():
    if request.method == 'POST':
        Username = request.form.get('username')
        Password = request.form.get('password')
        IpCliente = request.remote_addr
        
        LogService.Info("Routes.Auth", f"Recebida requisição de login. Usuário: {Username} | IP: {IpCliente}")

        DadosUsuario = AuthService.ValidarAcessoCompleto(Username, Password)

        if DadosUsuario:
            LogService.Info("Routes.Auth", f"Login aprovado. Criando sessão para: {DadosUsuario['login']}")
            
            UsuarioLogado = UsuarioSistema(
                Login=DadosUsuario['login'],
                Nome=DadosUsuario['nome'],
                Email=DadosUsuario['email'],
                Grupo=DadosUsuario['grupo'],
                IdBanco=DadosUsuario['id']
            )

            login_user(UsuarioLogado)
            
            flash(f'Bem-vindo(a) a bordo, {DadosUsuario["nome"]}! ✈️', 'success')
            
            ProximaPagina = url_for('Dashboard')
            return redirect(ProximaPagina or '/T-FlightOps')
        
        else:
            LogService.Warning("Routes.Auth", f"Login recusado para {Username} (IP: {IpCliente}).")
            flash('Login falhou. Verifique usuário e senha.', 'danger')

    return render_template('Auth/Login.html')

@AuthBp.route('/Deslogar')
@login_required
def Logout():
    user_login = current_user.Login if current_user.is_authenticated else "Desconhecido"
    LogService.Info("Routes.Auth", f"Usuário solicitou logout: {user_login}")
    
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('Auth.Login'))