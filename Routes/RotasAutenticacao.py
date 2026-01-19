from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from Services.AutenticacaoService import AutenticarAd
from Models.UsuarioModel import UsuarioSistema

# Novos imports para conectar no Banco
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Usuario import Usuario, UsuarioGrupo

# Definição do Blueprint
AuthBp = Blueprint('Auth', __name__)

@AuthBp.route('/Logar', methods=['GET', 'POST'])
def Login():
    """
    Rota responsável por exibir o formulário e processar o login.
    """
    if request.method == 'POST':
        Username = request.form.get('username')
        Password = request.form.get('password')
        
        # 1. Validação de Credenciais no AD
        if AutenticarAd(Username, Password): # Se Usuario/Pass corretos no AD
            # 2. Buscar dados do usuário no SQL Server
            Sessao = ObterSessaoSqlServer()
            try:
                # 2. Busca o usuário no SQL Server para pegar Permissões/Grupo
                # Fazemos um Left Join com Grupo para garantir que traga mesmo sem grupo
                Resultado = Sessao.query(Usuario, UsuarioGrupo)\
                    .outerjoin(UsuarioGrupo, Usuario.codigo_usuariogrupo == UsuarioGrupo.codigo_usuariogrupo)\
                    .filter(Usuario.Login_Usuario == Username)\
                    .first()

                if Resultado:
                    DadosUsuario, DadosGrupo = Resultado
                    
                    # Define nome do grupo ou padrão
                    NomeGrupo = DadosGrupo.Sigla_UsuarioGrupo if DadosGrupo else "SEM_GRUPO"

                    # Cria o objeto de sessão compatível com a nova classe UsuarioSistema
                    UsuarioLogado = UsuarioSistema(
                        Login=DadosUsuario.Login_Usuario,
                        Nome=DadosUsuario.Nome_Usuario,
                        Email=DadosUsuario.Email_Usuario,
                        Grupo=NomeGrupo,
                        IdBanco=DadosUsuario.Codigo_Usuario
                    )

                    # Efetiva o login no Flask
                    login_user(UsuarioLogado)
                    
                    flash(f'Bem-vindo(a), {DadosUsuario.Nome_Usuario}!', 'success')
                    
                    # Redireciona
                    ProximaPagina = request.args.get('next')
                    return redirect(ProximaPagina or '/')
                
                else:
                    # Caso autentique no AD mas não tenha cadastro no SQL
                    flash('Login correto (AD), mas usuário não cadastrado no sistema.', 'warning')

            except Exception as e:
                print(f"❌ Erro no banco durante login: {e}")
                flash('Erro técnico ao buscar dados do usuário.', 'danger')
            finally:
                if Sessao:
                    Sessao.close()
        
        else:
            flash('Usuário ou senha inválidos.', 'danger')

    return render_template('Login.html')

@AuthBp.route('/Deslogar')
@login_required
def Logout():
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('Auth.Login'))