from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, login_required, current_user
import os

from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Usuario import Usuario, UsuarioGrupo
from Models.UsuarioModel import UsuarioSistema
from Configuracoes import ConfiguracaoAtual # Importação da Configuração
from Services.VersaoService import VersaoService
from Services.LogService import LogService
# Importação das Rotas e Modelos
from Routes.Auth import AuthBp
from Routes.Malha import MalhaBp
from Routes.Aeroportos import AeroportoBp
from Routes.Cidades import CidadeBp
from Routes.Escalas import EscalasBp
from Routes.Planejamento import PlanejamentoBp
from Routes.Acompanhamento import AcompanhamentoBP
from Routes.TabelasFrete import FreteBp
from Routes.Reversa import ReversaBp


# --- REGISTRO DE ROTAS (BLUEPRINTS) ---
# Pega o prefixo definido no .env ou padrão (ex: /T-FlightOps)
Prefix = ConfiguracaoAtual.ROUTE_PREFIX

app = Flask(__name__,
            static_url_path=f'{Prefix}/Static', 
            static_folder='Static')

app.secret_key = 'CHAVE_SUPER_SECRETA_DO_PROJETO_VOOS' # Trocar por algo seguro depois

LogService.Inicializar()
LogService.Info("App", f"Iniciando aplicação no ambiente: {os.getenv('AMBIENTE_APP', 'DEV')}")

# Configuração do Flask-Login
GerenciadorLogin = LoginManager()
GerenciadorLogin.init_app(app)
GerenciadorLogin.login_view = 'Auth.Login' # Nome da rota para redirecionar quem não tá logado

@app.context_processor
def InjetarDadosGlobais():
    """Disponibiliza a versão para todos os templates HTML"""
    versao_info = VersaoService.ObterVersaoAtual()
    return dict(SistemaVersao=versao_info)

@GerenciadorLogin.user_loader
def CarregarUsuario(UserId):
    Sessao = ObterSessaoSqlServer()
    UsuarioEncontrado = None

    try:
        # Log de debug para rastrear a persistência da sessão (opcional, bom para dev)
        # LogService.Debug("App.UserLoader", f"Recarregando usuário: {UserId}")

        Resultado = Sessao.query(Usuario, UsuarioGrupo)\
            .outerjoin(UsuarioGrupo, Usuario.codigo_usuariogrupo == UsuarioGrupo.codigo_usuariogrupo)\
            .filter(Usuario.Login_Usuario == UserId)\
            .first()

        if Resultado:
            DadosUsuario, DadosGrupo = Resultado
            NomeGrupo = DadosGrupo.Sigla_UsuarioGrupo if DadosGrupo else "SEM_GRUPO"

            UsuarioEncontrado = UsuarioSistema(
                Login=DadosUsuario.Login_Usuario,
                Nome=DadosUsuario.Nome_Usuario,
                Email=DadosUsuario.Email_Usuario,
                Grupo=NomeGrupo,
                IdBanco=DadosUsuario.Codigo_Usuario
            )
            
    except Exception as Erro:
        # AQUI O LOG É CRÍTICO
        LogService.Error("App.UserLoader", f"Falha crítica ao recarregar usuário {UserId}", Erro)
        return None
    
    finally:
        if Sessao:
            Sessao.close()

    return UsuarioEncontrado

# O Auth geralmente fica separado, ex: /T-FlightOps/auth
app.register_blueprint(AuthBp, url_prefix=f'{Prefix}/auth')

# Os demais módulos assumem o prefixo base, pois suas rotas internas já possuem nomes (ex: /malha/...)
app.register_blueprint(MalhaBp, url_prefix=Prefix)
app.register_blueprint(AeroportoBp, url_prefix=Prefix)
app.register_blueprint(CidadeBp, url_prefix=Prefix)
app.register_blueprint(PlanejamentoBp, url_prefix=f'{Prefix}/Planejamento')
app.register_blueprint(EscalasBp, url_prefix=f'{Prefix}/Escalas')
app.register_blueprint(AcompanhamentoBP, url_prefix=f'{Prefix}/Acompanhamento')
app.register_blueprint(FreteBp, url_prefix=f'{Prefix}/Fretes')
app.register_blueprint(ReversaBp, url_prefix=f'{Prefix}/Reversa')

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