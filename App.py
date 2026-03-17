from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, login_required, current_user
import os 
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
            static_url_path=f'{Prefix}/Static',
            static_folder='Static',
            template_folder='templates') # Adicionado para garantir que ache o HTML

# Chave secreta para sessões, criptografia ou outras operações sensíveis.
app.secret_key = ConfiguracaoAtual.APP_SECRET_KEY # Trocar por algo seguro depois

LogService.Inicializar()
LogService.Info("App", f"Iniciando aplicação no ambiente: {os.getenv('AMBIENTE_APP', 'DEV')}")

# Configuração do Flask-Login
GerenciadorLogin = LoginManager() # Instancia o gerenciador de login
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

    try: # Caso haja algum erro na consulta, é melhor logar e retornar None do que quebrar a aplicação inteira
        
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
                IdBanco=DadosUsuario.Codigo_Usuario,
                Id_Grupo_Banco = DadosUsuario.codigo_usuariogrupo
            )
            
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
    gerenciador_usuario=gerenciador_usuario,
    inject_theme=True,         # Injeta CSS de temas
    inject_global=True,        # Injeta CSS global estrutural
    inject_animations=True,    # Injeta animações CSS
    inject_js=True,             # Injeta o base.js do LuftCore

    show_topbar=True,         # Se meteres False, a barra de cima desaparece toda
    show_search=False,        # Oculta a barra de pesquisa
    show_notifications=False, # Oculta o botão do sininho
    show_breadcrumb=True      # Mantém os breadcrumbs automáticos ativados
)

# O Auth geralmente fica separado, ex: /Luft-ConnectAir/auth
app.register_blueprint(AuthBp, url_prefix=f'{Prefix}/auth')

# Os demais módulos assumem o prefixo base, pois suas rotas internas já possuem nomes (ex: /malha/...)
app.register_blueprint(ConfiguracoesBp, url_prefix=f'{Prefix}/Configuracoes')
app.register_blueprint(Seguranca_BP, url_prefix=f'{Prefix}/Seguranca')
app.register_blueprint(CortesBp, url_prefix=f'{Prefix}/Cortes')
app.register_blueprint(PlanejamentoBp, url_prefix=f'{Prefix}/Planejamento')
app.register_blueprint(EscalasBp, url_prefix=f'{Prefix}/Escalas')
app.register_blueprint(AcompanhamentoBP, url_prefix=f'{Prefix}/Acompanhamento')
app.register_blueprint(FreteBp, url_prefix=f'{Prefix}/Fretes')
app.register_blueprint(ReversaBp, url_prefix=f'{Prefix}/Reversa')
app.register_blueprint(MalhaBp, url_prefix=f'{Prefix}/Malha')
app.register_blueprint(AeroportoBp, url_prefix=f'{Prefix}/Aeroportos')
app.register_blueprint(CidadeBp, url_prefix=f'{Prefix}/Cidades')
app.register_blueprint(ServicosClientesBp, url_prefix=f'{Prefix}/Servicos') # Exemplo de rota específica para um módulo
app.register_blueprint(GlobalBp, url_prefix=f'{Prefix}/Global')


# Rota principal do Dashboard com o prefixo
@app.route(f'{Prefix}/')
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