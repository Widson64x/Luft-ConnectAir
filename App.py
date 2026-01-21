from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, login_required, current_user
import os

from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Usuario import Usuario, UsuarioGrupo
from Models.UsuarioModel import UsuarioSistema
from Configuracoes import ConfiguracaoAtual # Importação da Configuração

# Importação das Rotas e Modelos
from Routes.RotasAutenticacao import AuthBp
from Routes.RotasMalha import MalhaBp
from Routes.RotasAeroportos import AeroportoBp
from Routes.RotasCidades import CidadeBp
from Routes.RotasEscalas import EscalasBp
from Routes.RotasPlanejamento import PlanejamentoBp
from Routes.RotasAcompanhamento import AcompanhamentoBP

Prefix = ConfiguracaoAtual.ROUTE_PREFIX

app = Flask(__name__,
            static_url_path=f'{Prefix}/Static', 
            static_folder='Static')

app.secret_key = 'CHAVE_SUPER_SECRETA_DO_PROJETO_VOOS' # Trocar por algo seguro depois

# Configuração do Flask-Login
GerenciadorLogin = LoginManager()
GerenciadorLogin.init_app(app)
GerenciadorLogin.login_view = 'Auth.Login' # Nome da rota para redirecionar quem não tá logado

@GerenciadorLogin.user_loader
def CarregarUsuario(UserId):
    """
    Recarrega o usuário a partir do ID armazenado na sessão (neste caso, o Login do AD).
    Busca dados atualizados no SQL Server a cada requisição.
    """
    Sessao = ObterSessaoSqlServer()
    UsuarioEncontrado = None

    try:
        # Busca Usuário + Grupo fazendo um JOIN
        # UserId aqui é o Login (ex: 'joao.silva') que salvamos no cookie
        Resultado = Sessao.query(Usuario, UsuarioGrupo)\
            .outerjoin(UsuarioGrupo, Usuario.codigo_usuariogrupo == UsuarioGrupo.codigo_usuariogrupo)\
            .filter(Usuario.Login_Usuario == UserId)\
            .first()

        if Resultado:
            # Desempacota a tupla retornada pela query
            DadosUsuario, DadosGrupo = Resultado
            
            # Trata caso o usuário esteja sem grupo vinculado
            NomeGrupo = DadosGrupo.Sigla_UsuarioGrupo if DadosGrupo else "SEM_GRUPO"

            # Cria o objeto que ficará disponível em 'current_user'
            UsuarioEncontrado = UsuarioSistema(
                Login=DadosUsuario.Login_Usuario,
                Nome=DadosUsuario.Nome_Usuario,
                Email=DadosUsuario.Email_Usuario,
                Grupo=NomeGrupo,
                IdBanco=DadosUsuario.Codigo_Usuario
            )
            
    except Exception as Erro:
        print(f"⚠️ Erro ao recarregar usuário do banco: {Erro}")
        # Em caso de erro de banco, retornamos None para forçar o logout por segurança
        return None
    
    finally:
        # CRÍTICO: Sempre fechar a sessão para não travar o SQL Server de produção
        if Sessao:
            Sessao.close()

    return UsuarioEncontrado

# --- REGISTRO DE ROTAS (BLUEPRINTS) ---
# Pega o prefixo definido no .env ou padrão (ex: /T-FlightOps)
Prefix = ConfiguracaoAtual.ROUTE_PREFIX

# O Auth geralmente fica separado, ex: /T-FlightOps/auth
app.register_blueprint(AuthBp, url_prefix=f'{Prefix}/auth')

# Os demais módulos assumem o prefixo base, pois suas rotas internas já possuem nomes (ex: /malha/...)
app.register_blueprint(MalhaBp, url_prefix=Prefix)
app.register_blueprint(AeroportoBp, url_prefix=Prefix)
app.register_blueprint(CidadeBp, url_prefix=Prefix)
app.register_blueprint(PlanejamentoBp, url_prefix=f'{Prefix}/Planejamento')
app.register_blueprint(EscalasBp, url_prefix=f'{Prefix}/Escalas')
app.register_blueprint(AcompanhamentoBP, url_prefix=f'{Prefix}/Acompanhamento')

# Rota principal do Dashboard com o prefixo
@app.route(f'{Prefix}/')
@login_required
def Dashboard():
    return render_template('Dashboard.html')

# Redirecionamento da raiz absoluta para o Dashboard correto
@app.route('/')
def IndexRoot():
    return redirect(url_for('Dashboard'))

if __name__ == '__main__':
    app.run(debug=True)