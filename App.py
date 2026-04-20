from datetime import datetime, timedelta, timezone

from flask import Flask, redirect, render_template, request, session, url_for
from flask_login import LoginManager, login_required, current_user
import os 
from sqlalchemy import text
from werkzeug.middleware.proxy_fix import ProxyFix
from luftcore.extensions.flask_extension import LuftCorePackages, LuftUser

from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Usuario import Usuario, UsuarioGrupo
from Models.UsuarioModel import UsuarioSistema
from Configuracoes import ConfiguracaoAtual # Importação da Configuração
from Services.VersaoService import VersaoService
from Services.LogService import LogService
# Importação das Rotas e Modelos
from Routes.Global.APIs import GlobalBp
from Routes.Auth import AuthBp
from Routes.Malha import MalhaBp
from Routes.Aeroportos import AeroportoBp
from Routes.Cidades import CidadeBp
from Routes.Escalas import EscalasBp
from Routes.Planejamento import PlanejamentoBp
from Routes.Acompanhamento import AcompanhamentoBP
from Routes.TabelasFrete import FreteBp
from Routes.Reversa import ReversaBp
from Routes.Cortes import CortesBp
from Routes.Global.Configuracoes import ConfiguracoesBp
from Routes.Global.ConfiguracaoSeguranca import Seguranca_BP
from Routes.ServicosClientes import ServicosClientesBp


# --- REGISTRO DE ROTAS (BLUEPRINTS) ---
# Pega o prefixo definido no .env ou padrão (ex: /Luft-ConnectAir)
Prefix = ConfiguracaoAtual.ROUTE_PREFIX

# Define a aplicação Flask, configurando o caminho para arquivos estáticos com o prefixo
app = Flask(ConfiguracaoAtual.APP_NAME,
            static_url_path='/Static', 
            static_folder='Static')

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Chave secreta para sessões, criptografia ou outras operações sensíveis.
app.secret_key = ConfiguracaoAtual.APP_SECRET_KEY # Trocar por algo seguro depois
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=ConfiguracaoAtual.SESSAO_TIMEOUT_MINUTOS)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

LogService.Inicializar()
LogService.Info("App", f"Iniciando aplicação no ambiente: {os.getenv('AMBIENTE_APP', 'DEV')}")

# Configuração do Flask-Login
GerenciadorLogin = LoginManager() # Instancia o gerenciador de login
GerenciadorLogin.init_app(app)
GerenciadorLogin.login_view = 'Auth.login' # Nome da rota para redirecionar quem não tá logado

@app.context_processor
def InjetarDadosGlobais():
    """Disponibiliza a versão para todos os templates HTML"""
    versao_info = VersaoService.ObterVersaoAtual()
    return dict(
        SistemaVersao=versao_info,
        SessaoTimeoutMinutos=ConfiguracaoAtual.SESSAO_TIMEOUT_MINUTOS,
        SessaoKeepaliveSegundos=ConfiguracaoAtual.SESSAO_KEEPALIVE_SEGUNDOS,
    )


def _AtualizarMarcadorSessao():
    session.permanent = True
    session['sessao_ultima_atividade_utc'] = datetime.now(timezone.utc).isoformat()


@app.before_request
def RenovarContextoSessao():
    if request.endpoint == 'static':
        return

    if session.get('_user_id') or session.get('usuario_autenticado'):
        _AtualizarMarcadorSessao()

@GerenciadorLogin.user_loader
def CarregarUsuario(UserId):
    UsuarioSessao = UsuarioSistema.DeSessao(session.get('usuario_autenticado'))
    if UsuarioSessao and UsuarioSessao.get_id() == UserId:
        return UsuarioSessao

    Sessao = ObterSessaoSqlServer()
    UsuarioEncontrado = None

    try: # Caso haja algum erro na consulta, é melhor logar e retornar None do que quebrar a aplicação inteira
        
        # Log de debug para rastrear a persistência da sessão (opcional, bom para dev)
        # LogService.Debug("App.UserLoader", f"Recarregando usuário: {UserId}")

        if not Sessao:
            return None

        Resultado = Sessao.execute(
            text(
                """
                SELECT TOP 1
                    U.Login_Usuario,
                    U.Nome_Usuario,
                    U.Email_Usuario,
                    U.Codigo_Usuario,
                    U.codigo_usuariogrupo,
                    G.Sigla_UsuarioGrupo
                FROM usuario AS U
                LEFT JOIN usuariogrupo AS G
                    ON U.codigo_usuariogrupo = G.codigo_usuariogrupo
                WHERE U.Login_Usuario = :login
                """
            ),
            {'login': UserId}
        ).mappings().first()

        if Resultado:
            UsuarioEncontrado = UsuarioSistema(
                Login=Resultado['Login_Usuario'],
                Nome=Resultado['Nome_Usuario'],
                Email=Resultado['Email_Usuario'],
                Grupo=Resultado['Sigla_UsuarioGrupo'] or 'SEM_GRUPO',
                IdBanco=Resultado['Codigo_Usuario'],
                Id_Grupo_Banco=Resultado['codigo_usuariogrupo']
            )
            session['usuario_autenticado'] = UsuarioEncontrado.ParaSessao()
            
    except Exception as Erro:
        # AQUI O LOG É CRÍTICO
        LogService.Error("App.UserLoader", f"Falha crítica ao recarregar usuário {UserId}", Erro)
        return None
    
    finally:
        if Sessao:
            Sessao.close()

    return UsuarioEncontrado


# ==========================================
# --- INICIALIZAÇÃO DO LUFTCORE ---
# ==========================================

# 1. Mapeamento do Usuário
# O framework vai extrair esses dados do current_user do Flask-Login em cada requisição
gerenciador_usuario = LuftUser(
    callback_usuario=lambda: current_user,
    
    # ATENÇÃO AQUI: Estes são os nomes EXATOS dos atributos lá do seu Models/UsuarioModel.py -> UsuarioSistema
    attr_nome='Login',          # Mapeia para self.Nome
    cargo='Grupo',             # Mapeia para self.Grupo (Que você configurou lindamente no AuthService.py!)
)
# 2. Injeção do Framework na Aplicação
luftcore_app = LuftCorePackages(
    app=app,
    app_name=ConfiguracaoAtual.APP_NAME,
    app_version=VersaoService.ObterVersaoAtual()['NumeroVersao'],
    app_version_type=VersaoService.ObterVersaoAtual()['Estagio'],
    gerenciador_usuario=gerenciador_usuario,
    inject_theme=True,         # Injeta CSS de temas
    inject_global=True,        # Injeta CSS global estrutural
    inject_animations=True,    # Injeta animações CSS
    inject_js=True,             # Injeta o base.js do LuftCore

    show_topbar=True,         # Se meteres False, a barra de cima desaparece toda
    show_search=False,        # Oculta a barra de pesquisa
    show_notifications=False, # Oculta o botão do sininho
    show_breadcrumb=True,      # Mantém os breadcrumbs automáticos ativados
    #favicon=f"{Prefix}/Static/Img/Logos/LUFT-HANSA.ico" # Usa o favicon com o prefixo correto (certifique-se de que o caminho está certo!)
)

# O Auth geralmente fica separado, ex: /Luft-ConnectAir/auth
app.register_blueprint(AuthBp, url_prefix='/auth')

# Os demais módulos assumem o prefixo base, pois suas rotas internas já possuem nomes (ex: /malha/...)
app.register_blueprint(ConfiguracoesBp, url_prefix='/Configuracoes')
app.register_blueprint(Seguranca_BP, url_prefix='/Seguranca')
app.register_blueprint(CortesBp, url_prefix='/Cortes')
app.register_blueprint(PlanejamentoBp, url_prefix='/Planejamento')
app.register_blueprint(EscalasBp, url_prefix='/Escalas')
app.register_blueprint(AcompanhamentoBP, url_prefix='/Acompanhamento')
app.register_blueprint(FreteBp, url_prefix='/Fretes')
app.register_blueprint(ReversaBp, url_prefix='/Reversa')
app.register_blueprint(MalhaBp, url_prefix='/Malha')
app.register_blueprint(AeroportoBp, url_prefix='/Aeroportos')
app.register_blueprint(CidadeBp, url_prefix='/Cidades')
app.register_blueprint(ServicosClientesBp, url_prefix='/Servicos') # Exemplo de rota específica para um módulo
app.register_blueprint(GlobalBp, url_prefix='/Global')


# Rota principal do Dashboard com o prefixo
@app.route('/')
@login_required
def Dashboard():
    return render_template('HomeDashboard.html')

# Redirecionamento da raiz absoluta para o Dashboard correto
@app.route('/')
def IndexRoot():
    return redirect(url_for('Dashboard'))

if __name__ == '__main__': # Se rodar diretamente, inicia o servidor Flask (bom para desenvolvimento, em produção usar WSGI como Gunicorn ou uWSGI)
    # Define a porta (padrão 5000 se não encontrar no .env)
    PortaApp = int(os.getenv("PORT", 5000))

    # Exibe no log qual configuração de DEBUG está sendo usada
    print(f"[Sistema] Iniciando servidor Flask... Modo Debug: {ConfiguracaoAtual.DEBUG}")
    print(f"[Sistema] Acessar via: http://{ConfiguracaoAtual.HOST}:{PortaApp}{Prefix}/")
    print(f"[Sistema] Sistema {ConfiguracaoAtual.APP_NAME} versão {VersaoService.ObterVersaoAtual()}")
    app.run(
        host=ConfiguracaoAtual.HOST,                # '0.0.0.0' deixa o app visível na rede local (útil para testar de outros PCs)
        port=ConfiguracaoAtual.PORT,                 # Porta definida
        debug=ConfiguracaoAtual.DEBUG  # Pega True/False direto da sua classe de Configuração
    )