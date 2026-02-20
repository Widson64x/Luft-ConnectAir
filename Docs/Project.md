# Documentação Técnica: Visão Geral e Arquivos Base (Luft-ConnectAir)

Este documento detalha a arquitetura técnica, as configurações de ambiente e os arquivos de inicialização (core) para o sistema **Luft-ConnectAir**.

## 1. Visão Geral do Projeto

### Objetivo do Sistema

O **Luft-ConnectAir** é um sistema web robusto focado em **Operações de Voo**. Sua principal finalidade é gerenciar e planejar malhas aéreas, administrar escalas, controlar cadastros de aeroportos e cidades, além de realizar o acompanhamento estratégico de cargas (AWBs) e manifestos de voo. O projeto utiliza uma arquitetura modular baseada em Python para atuar como o elo de integração entre sistemas legados (ERP) e novos módulos de negócios.

### Stack Tecnológica Utilizada

A aplicação foi construída sobre uma stack moderna, garantindo alta disponibilidade, segurança e fácil manutenção:

* **Linguagem:** Python 3.13+
* **Framework Web:** Flask 3.1.2 (Escolhido por sua flexibilidade na criação de aplicações modulares utilizando *Blueprints*).
* **Bancos de Dados:**
* **SQL Server:** Utilizado para integração com o legado/corporativo.
* **PostgreSQL:** Utilizado para persistência dos novos módulos estruturais da malha aérea.

* **ORM (Object-Relational Mapping):** SQLAlchemy 2.0 (Garante abstração segura contra SQL Injection e facilita o mapeamento das tabelas).
* **Autenticação:** Flask-Login com suporte a integração de usuários via banco de dados e AD/LDAP.
* **Servidor de Produção (WSGI):** Waitress (Escolhido por ser altamente compatível com implantações em ambientes Windows Server).
* **Processamento de Dados:** Pandas e OpenPyXL para manipulação de planilhas e relatórios.

### Estrutura de Pastas e Arquitetura

A arquitetura de pastas segue o padrão MVC (Model-View-Controller) adaptado para o ecossistema Flask (usando Rotas/Templates), separando claramente as responsabilidades de Banco de Dados, Regras de Negócio e Apresentação.

```text
Luft-ConnectAir/
├── App.py                     # Ponto de entrada da aplicação (Flask App)
├── Conexoes.py                # Gerenciamento de pools de conexão (SQLAlchemy)
├── Configuracoes.py           # Configurações globais e de ambiente (.env)
├── WSGI.py                    # Entry point WSGI para servidor de produção
├── Models/                    # Modelos ORM divididos por tipo de banco (POSTGRES / SQL_SERVER)
├── Routes/                    # Controladores e definição de Endpoints (Blueprints)
├── Services/                  # Camada de abstração para Regras de Negócio
├── Static/                    # Arquivos CSS, JS e Imagens
└── Templates/                 # Arquivos HTML renderizados via Jinja2

```

## 2. Arquivos Base (Core da Aplicação)

Esta seção detalha o funcionamento dos arquivos que sustentam a aplicação, desde o carregamento de variáveis até a inicialização do servidor HTTP.

### `Configuracoes.py`

**Responsabilidade:** Centralizar o carregamento das variáveis de ambiente (`.env`) e definir as configurações comportamentais da aplicação de acordo com o ambiente de execução (Desenvolvimento, Homologação ou Produção).

**Fluxo Técnico:**

1. A biblioteca `dotenv` carrega as variáveis do arquivo `.env` para a memória.
2. A classe genérica `ConfiguracaoBase` define os parâmetros comuns (prefixos de rota, chaves secretas, caminhos de diretório).
3. O sistema detecta a variável `AMBIENTE_APP` e instância a classe filha correspondente (ex: `ConfiguracaoProducao`), que sobrescreve parâmetros como `DEBUG` e nome do banco de dados alvo.

**Trecho de Código - Lógica de Ambientes:**

```python
# Mapeamento do ambiente via herança de classes
class ConfiguracaoDesenvolvimento(ConfiguracaoBase):
    DEBUG = True
    PG_DB_NAME = os.getenv("PGDB_NAME_DEV", "Luft-ConnectAir_DEV")

class ConfiguracaoProducao(ConfiguracaoBase):
    DEBUG = False
    PG_DB_NAME = os.getenv("PGDB_NAME_PROD", "Luft-ConnectAir")

MapaConfiguracao = {
    "desenvolvimento": ConfiguracaoDesenvolvimento,
    "producao": ConfiguracaoProducao
}

NomeAmbiente = os.getenv("AMBIENTE_APP", "desenvolvimento").lower()
ConfiguracaoAtual = MapaConfiguracao.get(NomeAmbiente, ConfiguracaoDesenvolvimento)()

```

### `Conexoes.py`

**Responsabilidade:** Isolar a criação das *Engines* (motores de conexão) e das fábricas de sessão (`sessionmaker`) do SQLAlchemy para os dois bancos de dados da aplicação.

**Decisões Arquiteturais:**

* **SQL Server (Legado):** Utiliza o `NullPool`. Como bancos de dados corporativos legados frequentemente derrubam conexões inativas ou sofrem com travamentos de sessão, o `NullPool` garante que o SQLAlchemy não mantenha conexões abertas no pool, criando e destruindo uma nova conexão a cada transação.
* **PostgreSQL (Novo):** Utiliza o pool padrão embutido no SQLAlchemy com a flag `pool_pre_ping=True`. Isso garante alta performance (reaproveitando conexões) e testa a integridade da conexão (ping) antes de cada *query*, evitando erros caso o servidor do banco tenha sido reiniciado.

**Trecho de Código - Engine do PostgreSQL:**

```python
def ObterEnginePostgres():
    """Cria a Engine do PostgreSQL com pre-ping para evitar stale connections."""
    try:
        Engine = create_engine(
            URL_BANCO_PG, 
            pool_pre_ping=True, # Verifica se o banco tá vivo
            echo=False
        )
        return Engine
    except Exception as Erro:
        print(f"❌ Erro crítico ao criar engine do PostgreSQL: {Erro}")
        return None

```

### `App.py`

**Responsabilidade:** É o orquestrador principal. Instancia o objeto Flask, registra os `Blueprints` (módulos de rotas), configura o gerenciador de sessões (`Flask-Login`) e injeta variáveis globais nos templates Jinja2.

**Fluxo de Inicialização:**

1. A instância `app` do Flask é criada utilizando configurações de caminhos customizadas baseadas na propriedade `ROUTE_PREFIX` (ex: `/Luft-ConnectAir/Static`) para suportar implantações atrás de proxies reversos.
2. O `Flask-Login` é acoplado via `GerenciadorLogin.init_app(app)`.
3. A função decorada com `@GerenciadorLogin.user_loader` é estabelecida para recarregar o usuário a partir do SQL Server a cada requisição autenticada, convertendo-o em um objeto DTO (`UsuarioSistema`).
4. Todos os módulos de rotas (Acompanhamento, Escalas, Malha, etc.) são registrados via `app.register_blueprint(...)` garantindo separação de responsabilidades.

**Trecho de Código - Injeção Global e Loader de Usuários:**

```python
@app.context_processor
def InjetarDadosGlobais():
    """Disponibiliza a versão atual do sistema para todos os templates HTML gerados."""
    versao_info = VersaoService.ObterVersaoAtual()
    return dict(SistemaVersao=versao_info)

@GerenciadorLogin.user_loader
def CarregarUsuario(UserId):
    """Consulta o banco de dados e reconstrói o objeto do usuário logado na sessão."""
    Sessao = ObterSessaoSqlServer()
    try:
        Resultado = Sessao.query(Usuario, UsuarioGrupo)\
            .outerjoin(UsuarioGrupo, Usuario.codigo_usuariogrupo == UsuarioGrupo.codigo_usuariogrupo)\
            .filter(Usuario.Login_Usuario == UserId)\
            .first()
        # Mapeamento do resultado ORM para a classe de sessão da aplicação
        if Resultado:
            DadosUsuario, DadosGrupo = Resultado
            return UsuarioSistema(
                Login=DadosUsuario.Login_Usuario,
                Nome=DadosUsuario.Nome_Usuario,
                Email=DadosUsuario.Email_Usuario,
                Grupo=DadosGrupo.Sigla_UsuarioGrupo if DadosGrupo else "SEM_GRUPO",
                IdBanco=DadosUsuario.Codigo_Usuario,
                Id_Grupo_Banco=DadosUsuario.codigo_usuariogrupo
            )
    except Exception as Erro:
        LogService.Error("App.UserLoader", f"Falha ao carregar {UserId}", Erro)
        return None
    finally:
        if Sessao: Sessao.close()

```

### `WSGI.py`

**Responsabilidade:** Servir a aplicação em ambientes produtivos. O servidor de desenvolvimento embutido do Flask não é preparado para suportar tráfego de produção ou requisições concorrentes de forma segura.

**Abordagem Técnica:**
O projeto faz uso da biblioteca `waitress`, um servidor WSGI focado em Python para ambientes Windows (onde ferramentas como Gunicorn não possuem suporte nativo ideal). Ele importa a instância de `app` contida em `App.py` e serve o tráfego escutando portas definidas em variáveis de ambiente, ideal para atuar atrás de um IIS ou NGINX.

**Trecho de Código:**

```python
from App import app
from waitress import serve
import os

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "9007"))
    
    # Executa o servidor WSGI com 6 threads para processamento paralelo
    serve(app, host=host, port=port, threads=6)

```

## 3. Módulo `Routes/` (Controladores e Endpoints)

### Organização e Responsabilidades

O diretório `Routes/` atua como a camada *Controller* na arquitetura do sistema. Ele é responsável por interceptar as requisições HTTP, aplicar as regras de segurança (autenticação e autorização), repassar os dados de entrada para a camada de `Services` e devolver uma resposta ao cliente.

A organização utiliza o conceito de **Blueprints** do Flask, que permite modularizar as rotas da aplicação por contexto de negócio (ex: Autenticação, Malha, Aeroportos).

### Fluxo de Dados nas Rotas

1. A requisição atinge um endpoint (ex: `POST /Malha/Gerenciar`).
2. Decoradores de segurança (`@login_required`, `@RequerPermissao`) validam se o usuário tem acesso.
3. A rota extrai os dados do formulário (`request.form`) ou arquivos (`request.files`).
4. A lógica de negócio é delegada para os `Services` correspondentes (ex: `MalhaService.AnalisarArquivo`).
5. O resultado é renderizado via Jinja2 (`render_template`), redirecionado (`redirect`) ou retornado como JSON (`jsonify`) no caso de APIs.

### Exemplo 1: Autenticação (`Routes/Auth.py`)

O arquivo gerencia o ciclo de vida da sessão do usuário, validando credenciais e registrando os eventos de acesso.

* **Endpoint:** `POST /auth/Logar`
* **Integração:** Consome o `AuthService` para validação e utiliza o `LogService` para rastreabilidade de IP e tentativas de acesso.

**Código Fonte (Rota de Login):**

```python
@AuthBp.route('/Logar', methods=['GET', 'POST'])
def Login():
    if request.method == 'POST':
        Identificador = request.form.get('username')
        Password = request.form.get('password')
        IpCliente = request.remote_addr

        # Registro de log da tentativa
        LogService.Info("Routes.Auth", f"Recebida requisição de login. Identificador: {Identificador} | IP: {IpCliente}")

        # Delegação da regra de validação para o Service
        DadosUsuario = AuthService.ValidarAcessoCompleto(Identificador, Password)

        if DadosUsuario:
            # Criação do DTO da Sessão
            UsuarioLogado = UsuarioSistema(
                Login=DadosUsuario['login'],
                Nome=DadosUsuario['nome'],
                Email=DadosUsuario['email'],
                Grupo=DadosUsuario['grupo'],
                IdBanco=DadosUsuario['id'],
                Id_Grupo_Banco=DadosUsuario.get('id_grupo')
            )

            # Persiste a sessão por 8 horas utilizando Flask-Login
            login_user(UsuarioLogado, duration=timedelta(hours=8))
            flash(f'Bem-vindo(a) a bordo, {DadosUsuario["nome"]}! ✈️', 'success')
            return redirect(url_for('Dashboard'))

        else:
            LogService.Warning("Routes.Auth", f"Login recusado para '{Identificador}' (IP: {IpCliente}).")
            flash('Login falhou. Verifique suas credenciais.', 'danger')

    return render_template('Auth/Login.html')

```

### Exemplo 2: Gestão de Malha Aérea (`Routes/Malha.py`)

Este módulo lida com fluxos complexos, como o upload de planilhas de malha aérea, tratamento de conflitos e devolução de dados via API para os mapas/gráficos.

**Código Fonte (Endpoint API com controle de permissão):**

```python
@MalhaBp.route('/Malha/API/Rotas')
@login_required
@RequerPermissao('cadastros.malha.editar') # Decorador customizado de autorização
def ApiRotas():
    # Extração de parâmetros de Query (GET)
    Inicio = request.args.get('inicio')
    Fim = request.args.get('fim')
    Origem = request.args.get('origem')
    Destino = request.args.get('destino')
    NumeroVoo = request.args.get('numero_voo')
    
    if not Inicio or not Fim:
        return jsonify([])

    try:
        DataIni = datetime.strptime(Inicio, '%Y-%m-%d').date()
        DataFim = datetime.strptime(Fim, '%Y-%m-%d').date()
        
        # Chamada ao serviço com inteligência de rotas
        Dados = MalhaService.BuscarRotasInteligentes(DataIni, DataFim, Origem, Destino, NumeroVoo)
        
        # Retorno serializado para consumo de bibliotecas de frontend (ex: NetworkX/Leaflet)
        return jsonify(Dados)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

```

## 4. Módulo `Models/` (Camada de Dados e Entidades)

### Estrutura dos Models

O diretório `Models/` abriga duas categorias distintas de objetos:

1. **Modelos ORM (SQLAlchemy):** Classes que mapeiam diretamente para tabelas físicas nos bancos de dados (divididos nas pastas `POSTGRES` e `SQL_SERVER`).
2. **Modelos de Domínio/Sessão:** Classes utilitárias, como o `UsuarioModel.py`, que mantêm o estado da aplicação em memória durante a navegação.

### Modelos de Banco de Dados (`SQL_SERVER/Usuario.py`)

Os modelos ORM herdam da classe `Base` declarativa do SQLAlchemy. Eles definem a tipagem de dados, chaves primárias e as chaves estrangeiras, permitindo que a aplicação faça consultas SQL utilizando programação orientada a objetos.

**Código Fonte (Definição de Tabelas e Relacionamentos):**

```python
from sqlalchemy import Column, Integer, String, ForeignKey
from Models.SQL_SERVER.Base import Base

class Usuario(Base):
    __tablename__ = "usuario" # Nome exato da tabela no SQL Server

    Codigo_Usuario = Column(Integer, primary_key=True, autoincrement=True)
    Login_Usuario = Column(String)
    Nome_Usuario = Column(String)                 
    Email_Usuario = Column(String)                      
    # Definição de Chave Estrangeira ligando à tabela de grupos
    codigo_usuariogrupo = Column(Integer, ForeignKey("usuariogrupo.codigo_usuariogrupo"))

class UsuarioGrupo(Base):
    __tablename__ = "usuariogrupo"

    codigo_usuariogrupo = Column(Integer, primary_key=True, autoincrement=True)
    Sigla_UsuarioGrupo = Column(String) 
    Descricao_UsuarioGrupo = Column(String)  
    Permite_Cadastrar = Column(Integer)  

```

### Modelo de Sessão (`UsuarioModel.py`)

Este arquivo contém a classe `UsuarioSistema`, que herda de `UserMixin` do *Flask-Login*. Este modelo não é uma tabela de banco, mas sim o Data Transfer Object (DTO) que fica armazenado na sessão do navegador do usuário.

**Características Técnicas Notáveis:**

* **Lazy Loading e Caching de Permissões:** O método `TemPermissao` possui um cache interno (dicionário `_cache_permissoes`). Isso evita que o sistema execute dezenas de consultas (queries) no banco de dados quando uma única página HTML contém vários botões protegidos por permissões diferentes.
* **Importação Tardia (Lazy Import):** O serviço `PermissaoService` é importado apenas no momento da verificação para evitar erros de ciclo de importação (Circular Import) na inicialização do Flask.

**Código Fonte (Modelo de Sessão em Memória):**

```python
from flask_login import UserMixin

class UsuarioSistema(UserMixin):
    def __init__(self, Login, Nome, Email=None, Grupo=None, IdBanco=None, Id_Grupo_Banco=None):
        self.id = Login # Campo obrigatório do UserMixin
        self.Login = Login
        self.Nome = Nome
        self.Grupo = Grupo
        self.IdBanco = IdBanco
        self.Id_Grupo_Banco = Id_Grupo_Banco
        
        # Dicionário em memória para otimização de performance
        self._cache_permissoes = {} 

    def TemPermissao(self, ChavePermissao):
        """Verifica se o usuário possui a permissão solicitada."""
        
        # 1. Verifica o cache primeiro
        if ChavePermissao in self._cache_permissoes:
            return self._cache_permissoes[ChavePermissao]

        # 2. Lazy Import para evitar bloqueio
        from Services.PermissaoService import PermissaoService
        
        # 3. Consulta ao serviço (banco de dados) e salva no cache
        Tem = PermissaoService.VerificarPermissao(self, ChavePermissao)
        self._cache_permissoes[ChavePermissao] = Tem
        return Tem

```

Aqui está o documento completo a partir do Módulo 5, já com todas as adições integradas de forma nativa. Adicionei os blocos de código da `_QueryBase` e mostrei exatamente como as funções de distinção a utilizam, deixando tudo **bem visível** e documentado tecnicamente.

## 5. Módulo `Services/` (Regras de Negócio e Lógica Central)

### Organização e Responsabilidades

A pasta `Services/` implementa o padrão *Service Layer*, garantindo que os Controladores (`Routes/`) fiquem enxutos e atuem apenas como despachantes de requisições HTTP. Toda a complexidade algorítmica, manipulação de grafos, cálculos financeiros, integrações externas (AD/LDAP) e logs centralizados residem nos Serviços.

### `PlanejamentoService.py` (A Principal Parte do Sistema)

Trata-se do motor central do sistema Luft-ConnectAir. Este serviço é responsável por orquestrar a fila de cargas pendentes (CTCs), gerenciar a consolidação de lotes e atrelar mercadorias a voos específicos.

#### A Engenharia da `_QueryBase`

A maior inteligência na captura de dados deste serviço reside na variável estática `_QueryBase`. Trata-se de uma query SQL robusta e unificada cujo **objetivo principal é buscar no ERP legado exclusivamente os CTCs que AINDA NÃO possuem um AWB (Conhecimento de Transporte) válido atrelado**.

**Código Fonte (`_QueryBase`):**

```python
_QueryBase = """
     SELECT DISTINCT
         c.filial as Filial
                   ,c.filialctc as CTC
                   ,c.seriectc as Serie
                   ,C.MODAL as Modal
                   ,c.motivodoc as MotivoCTC
                   ,c.data as DataEmissao
                   ,c.hora as HoraEmissao
                   ,c.volumes as Volumes
                   ,c.peso as PesoFisico
                   ,c.pesotax as PesoTaxado
                   ,c.valmerc as Valor
                   ,c.fretetotalbruto as FreteTotal
                   ,upper(c.remet_nome) as Remetente
                   ,upper(c.dest_nome) as Destinatario
                   ,c.cidade_orig as CidadeOrigem
                   ,c.uf_orig as UFOrigem
                   ,c.cidade_dest as CidadeDestino
                   ,c.uf_dest as UFDestino
                   ,c.rotafilialdest as UnidadeDestino
                   ,c.prioridade as Prioridade
                   ,cl.StatusCTC as StatusCTC
                   ,ISNULL(cl.TipoCarga, '') AS Tipo_carga
                   ,c.nfs as Notas
                   ,CAST(c.qtdenfs AS INT) as QtdNotas
     FROM intec.dbo.tb_ctc_esp c (nolock)
              INNER JOIN intec.dbo.tb_ctc_esp_cpl cl (nolock) on cl.filialctc = c.filialctc
              LEFT JOIN intec.dbo.tb_manifesto m (nolock) on m.filialctc = c.filialctc
              LEFT JOIN intec.dbo.Tb_PLN_ControleReversa rev (nolock) ON
         rev.Filial COLLATE DATABASE_DEFAULT = c.filial COLLATE DATABASE_DEFAULT AND
         rev.Serie COLLATE DATABASE_DEFAULT = c.seriectc COLLATE DATABASE_DEFAULT AND
         rev.Ctc COLLATE DATABASE_DEFAULT = c.filialctc COLLATE DATABASE_DEFAULT

     WHERE
         c.tipodoc <> 'COB'
       and c.tem_ocorr not in ('C','0','1')
       and left(c.respons_cgc,8) <> '02426290'
       and (m.cancelado is null OR m.cancelado = 'S')
       and (m.motivo NOT in ('TRA','RED') OR m.motivo IS NULL)

       -- FILTRO DE AWB: Verifica se NÃO existe um AWB válido vinculado a este CTC
       AND NOT EXISTS (
         SELECT 1
         FROM intec.dbo.tb_airAWBnota B (NOLOCK)
                  INNER JOIN intec.dbo.tb_airawb A (NOLOCK) ON A.codawb = B.codawb
         WHERE B.filialctc = c.filialctc
           AND (A.cancelado IS NULL OR A.cancelado = '')
     )

       -- LÓGICA DE MODAL E OCORRÊNCIA TM
       AND (
         -- CASO 1: É AÉREO NATIVO E NÃO TEM TM
         (c.modal LIKE 'AEREO%' AND NOT EXISTS (
             SELECT 1 FROM intec.dbo.tb_ocorr cr (nolock)
             WHERE cr.cod_ocorr = 'TM' AND cr.filialctc = c.filialctc
         ))
             OR
         -- CASO 2: NÃO É AÉREO MAS TEM TM
         (c.modal NOT LIKE 'AEREO%' AND EXISTS (
             SELECT 1 FROM intec.dbo.tb_ocorr cr (nolock)
             WHERE cr.cod_ocorr = 'TM' AND cr.filialctc = c.filialctc
         ))
         ) \
"""

```

#### Funções de Distinção (Os Blocos Operacionais)

Ao invés de reescrever queries complexas, o sistema utiliza funções de distinção que apenas "herdam" a `_QueryBase` e concatenam (`+`) pequenos filtros adicionais (cláusulas `WHERE` específicas) para distribuir os dados nas abas de visualização (Diário, Reversa, Backlog).

**Código Fonte (Aplicações da Herança da Query Base):**

```python
# BLOCO 1: DIÁRIO
@staticmethod
def BuscarCtcsDiario(mapa_cache=None):
    Sessao = ObterSessaoSqlServer()
    try:
        if not mapa_cache: mapa_cache = PlanejamentoService._ObterMapaCache()
        Hoje = date.today()
        
        # Filtro Específico concatenado na base
        FiltroSQL = " AND c.motivodoc IN ('REE', 'ENT', 'NOR') AND c.data = :data_alvo"
        
        Query = text(PlanejamentoService._QueryBase + FiltroSQL + " ORDER BY c.data DESC, c.hora DESC")
        Rows = Sessao.execute(Query, {'data_alvo': Hoje}).fetchall()
        return PlanejamentoService._SerializarResultados(Rows, "DIARIO", mapa_cache)
    finally: Sessao.close()

# BLOCO 2: REVERSA
@staticmethod
def BuscarCtcsReversa(mapa_cache=None):
    Sessao = ObterSessaoSqlServer()
    try:
        if not mapa_cache: mapa_cache = PlanejamentoService._ObterMapaCache()
        
        # Filtro Específico: Motivo DEV + Tabela Reversa Liberada
        FiltroSQL = " AND c.motivodoc = 'DEV' AND rev.LiberadoPlanejamento = 1"
        
        Query = text(PlanejamentoService._QueryBase + FiltroSQL + " ORDER BY c.data DESC")
        Rows = Sessao.execute(Query).fetchall()
        return PlanejamentoService._SerializarResultados(Rows, "REVERSA", mapa_cache)
    finally: Sessao.close()

# BLOCO 3: BACKLOG
@staticmethod
def BuscarCtcsBacklog(mapa_cache=None):
    Sessao = ObterSessaoSqlServer()
    try:
        if not mapa_cache: mapa_cache = PlanejamentoService._ObterMapaCache()
        Hoje = date.today()
        Corte = Hoje - timedelta(days=120)
        
        # Filtro Específico: Anterior a hoje, maior que corte, REE/ENT
        FiltroSQL = " AND c.motivodoc IN ('REE', 'ENT') AND c.data < :data_hoje AND c.data >= :data_corte"
        
        Query = text(PlanejamentoService._QueryBase + FiltroSQL + " ORDER BY c.data ASC")
        Rows = Sessao.execute(Query, {'data_hoje': Hoje, 'data_corte': Corte}).fetchall()
        return PlanejamentoService._SerializarResultados(Rows, "BACKLOG", mapa_cache)
    finally: Sessao.close()

```

#### Unificação e Gravação

* **Consolidação Virtual:** Métodos como `BuscarCtcsConsolidaveis` e `UnificarConsolidacao` permitem agrupar dezenas de CTCs de mesma origem/destino em um único "Lote Virtual", propagando UFs e somando volumes/pesos para facilitar o trabalho do usuário.
* **`RegistrarPlanejamento`:** O método final que converte a decisão do usuário em persistência. Ele valida aeroportos e cidades, cria um cabeçalho de planejamento no PostgreSQL e vincula os trechos geográficos (Flights) e o cálculo financeiro.

### `MalhaService.py` (Inteligência de Rotas e Processamento de Dados)

Este é o serviço mais complexo do sistema. Ele gerencia o ciclo de vida das malhas aéreas (upload, validação e persistência) e atua como o motor de busca inteligente para conexões de voos.

#### Arquitetura e Fluxo de Dados (Busca de Rotas Inteligentes)

1. O sistema extrai todos os voos disponíveis no banco de dados para o intervalo de datas solicitado.
2. Os dados brutos são convertidos em um Grafo Direcionado (`nx.DiGraph()`) utilizando a biblioteca `networkx`.
3. Companhias aéreas com "score" de parceria zerado são ignoradas (Filtro de Parceria).
4. O algoritmo calcula todos os caminhos simples (`all_simple_paths`) entre a Origem e o Destino com um limite de escalas (`cutoff=3`).
5. Cada caminho passa pela validação cronológica (`_ValidarCaminhoCronologico`), garantindo que o tempo de conexão entre voos seja viável (entre 1h e 48h).
6. O serviço aciona o `TabelaFreteService` para calcular o custo estimado de cada "perna" do voo de acordo com o peso informado.
7. O resultado é categorizado via `RouteIntelligenceService` em rotas "Econômicas", "Rápidas", "Recomendadas", etc.

**Código Fonte (Construção do Grafo e Filtro de Parceria):**

```python
# Trecho do método BuscarOpcoesDeRotas no MalhaService
G = nx.DiGraph()
for Voo in VoosDB:
    NomeCia = Voo.CiaAerea.strip().upper()
    
    #  FILTRO DE PARCERIA ZERO 
    # Se o score for 0, a companhia é tratada como desativada e seus voos não entram no grafo
    if ScoresParceria.get(NomeCia, 50) <= 0:
        continue

    OrigemNo = Voo.AeroportoOrigem.strip().upper()
    DestinoNo = Voo.AeroportoDestino.strip().upper()
    
    # Adiciona a aresta (rota) e anexa os dados do voo ao nó do grafo
    if G.has_edge(OrigemNo, DestinoNo):
        G[OrigemNo][DestinoNo]['voos'].append(Voo)
    else:
        G.add_edge(OrigemNo, DestinoNo, voos=[Voo])

```

### `AuthService.py` (Autenticação de Dupla Etapa SQL/AD)

Serviço responsável por unificar o banco de dados da aplicação com a infraestrutura corporativa do Active Directory (LDAP).

#### Fluxo Interno

1. O usuário submete um e-mail ou nome de login na tela.
2. O método `BuscarUsuarioNoBanco` vasculha a base SQL Server para encontrar o cadastro do colaborador. Se encontrado via e-mail, extrai o Login real (ex: `nome.sobrenome`).
3. O método `AutenticarNoAd` tenta estabelecer um `SIMPLE BIND` com o servidor LDAP utilizando o formato de domínio (`DOMINIO\usuario`) e a senha recebida.

**Código Fonte (Orquestração de Validação):**

```python
# Trecho do AuthService
@staticmethod
def ValidarAcessoCompleto(identificador, senha):
    """
    1. Busca no Banco para traduzir "E-mail" -> "Login" (se necessário).
    2. Tenta autenticar no AD com o Login encontrado.
    """
    # Consulta híbrida no banco
    DadosUsuario = AuthService.BuscarUsuarioNoBanco(identificador)

    if DadosUsuario:
        LoginReal = DadosUsuario['login']

        # Disparo da requisição LDAP via biblioteca ldap3
        if AuthService.AutenticarNoAd(LoginReal, senha):
            return DadosUsuario
        else:
            return None # Usuário existe, mas senha está errada

    return None

```

### `PermissaoService.py` (Controle de Acesso Baseado em Regras e Auditoria)

Este módulo assegura a integridade das operações e impede acessos indevidos por meio de uma arquitetura sofisticada de sobreposição de permissões (Usuário > Grupo).

#### Lógica de Prevalência

Quando uma permissão é avaliada, o sistema verifica se há uma permissão específica gravada para aquele **Usuário**. Caso exista, essa decisão (*Conceder* ou *Negar*) sobrescreve qualquer regra que o **Grupo** do usuário possua. Após a avaliação, o acesso (permitido ou bloqueado) é gravado fisicamente na tabela `Tb_PLN_LogAcesso` para fins de auditoria.

**Código Fonte (Decorator de Rotas):**

```python
# Criação do Decorator Customizado de Autorização
def RequerPermissao(ChavePermissao):
    def Decorator(F):
        @wraps(F)
        def Wrapper(*args, **kwargs):
            # 1. Avalia autoridade usando o motor de regras
            Permitido = PermissaoService.VerificarPermissao(current_user, ChavePermissao)
            
            # 2. Grava log físico no SQL Server para auditoria
            PermissaoService.RegistrarLog(
                Usuario=current_user,
                Rota=request.path,
                Metodo=request.method,
                Ip=request.remote_addr,
                Chave=ChavePermissao,
                Permitido=Permitido
            )

            # 3. Interrompe a execução com um flash de erro enriquecido caso negado
            if not Permitido:
                Categoria = PermissaoService.ObterCategoriaPermissao(ChavePermissao)
                flash(f"Acesso Negado. Você precisa de permissão no módulo '{Categoria}' para acessar este recurso.", "danger")
                return redirect(url_for('Dashboard') if current_user.is_authenticated else url_for('Auth.Login'))
            
            return F(*args, **kwargs)
        return Wrapper
    return Decorator

```

### `LogService.py` (Rastreabilidade e Depuração)

Substitui a função `print` tradicional pelo módulo `logging` avançado do Python, permitindo auditoria forense e monitoramento de saúde do sistema.

#### Características

* **Separação de Preocupações:** Grava logs táticos e de debug (com reconstrução em todas as inicializações) no arquivo `session.log` e logs estratégicos (histórico eterno focado em auditoria) no arquivo `application.log`.
* **Tratamento de Exceções:** O método `.Error()` captura automaticamente a pilha de rastreamento (*Stack Trace*) completa, formatando-a via `traceback` para identificar rapidamente a linha falha em ambiente produtivo.

### Outros Serviços Importantes de Integração

Além dos módulos detalhados acima, a camada de serviços conta com outras peças cruciais para o funcionamento do roteamento e cálculos automáticos:

* **`TabelaFreteService.py`:** Atua de forma síncrona com o `PlanejamentoService` e o `MalhaService`. Cruza o "peso taxado" da carga com a tabela financeira da Cia Aérea escolhida, retornando o custo de frete estimado para a rota exata.
* **`RouteIntelligenceService.py`:** Módulo de lógica complementar que categoriza as opções de roteamento geradas pelos grafos (ex: "Econômicas", "Rápidas", "Recomendadas"), entregando a informação mastigada para a tomada de decisão do usuário final.

## 6. Outros Módulos e Pastas Relevantes

### Módulo `Templates/` e `Static/` (Camada de Apresentação)

A interface de usuário do Luft-ConnectAir é renderizada no lado do servidor (Server-Side Rendering) utilizando o motor de templates **Jinja2**, nativo do ecossistema Flask.

* **`Templates/`:** Contém os arquivos `.html` divididos por contexto (ex: `/Malha`, `/Planejamento`, `/Auth`). Utiliza a herança de templates (`Base.html`) para evitar repetição de código (como menus de navegação e rodapés). Componentes reutilizáveis, como modais de detalhes de AWBs e CTCs, ficam isolados na subpasta `Components/`.
* **`Static/`:** Armazena os ativos estáticos servidos diretamente ao navegador do cliente. A separação inclui `CSS/` (estilização global e temas) e `JS/` (lógica de frontend, validações de formulários e renderização de mapas ou gráficos).

**Integração de Código (Injeção de Variáveis Globais no Jinja2):**
Conforme definido em `App.py`, o backend injeta dados globais que ficam disponíveis para qualquer arquivo HTML em `Templates/`.

```python
# Trecho de App.py: Disponibilizando a versão do sistema no Frontend
@app.context_processor
def InjetarDadosGlobais():
    """Disponibiliza a versão para todos os templates HTML gerados."""
    versao_info = VersaoService.ObterVersaoAtual()
    return dict(SistemaVersao=versao_info)

```

*Uso no HTML (Jinja2):* `<span class="version">Versão: {{ SistemaVersao }}</span>`

### Módulo `Scripts/` (Automação e Manutenção)

Os scripts soltos nesta pasta operam fora do ciclo de vida das requisições web (HTTP). Eles são utilizados por administradores do sistema ou via agendadores de tarefas (como o *Task Scheduler* do Windows ou *Cron* no Linux) para rotinas de banco de dados.

* **`AtualizarBanco.py` / `InicializarBanco.py`:** Scripts que criam as tabelas e aplicam migrações (DDL) baseadas nas classes ORM definidas na pasta `Models/`.
* **`GestaoVersao.py`:** Atualiza o arquivo `VERSION` e gerencia o log de mudanças de *releases*.
* **`DiagnosticoTabelas.py`:** Varre a integridade das conexões entre o PostgreSQL e o SQL Server, gerando alertas de discrepância de dados geográficos ou cadastrais.

### Módulo `Utils/` (Helpers Genéricos)

Funções puras que não dependem de estado, banco de dados ou contexto web ficam isoladas aqui para maximizar a reutilização em qualquer parte do `Services/` ou `Routes/`.

* **`Formatadores.py`:** Funções para higienizar strings, aplicar máscaras em CNPJ/CPF, e o método `PadronizarData` (utilizado intensivamente pelo `MalhaService` na leitura de planilhas).
* **`Geometria.py` e `Texto.py`:** Utilitários auxiliares para lidar com cálculos de distância (Haversine) aplicados a coordenadas de aeroportos e normalização de codificações de texto (UTF-8, remoção de acentos).

## 7. Gestão de Dependências (`requirements.txt`)

O arquivo `requirements.txt` define o ecossistema tecnológico do projeto. Abaixo, as principais bibliotecas mapeadas e suas justificativas arquiteturais:

| Biblioteca | Versão | Responsabilidade no Sistema |
|  |  |  |
| **Flask** | `3.1.2` | Framework web principal. Roteamento, views e controle de requisições. |
| **SQLAlchemy** | `2.0.45` | ORM (Object-Relational Mapping) maduro. Garante proteção contra SQL Injection e abstrai o dialeto do SQL Server e PostgreSQL. |
| **pyodbc** | `5.3.0` | Driver de baixo nível exigido pelo SQLAlchemy para comunicar-se com o Microsoft SQL Server. |
| **psycopg** | `3.3.2` | Driver moderno (C-based) para comunicação de alta performance com o PostgreSQL. |
| **pandas** & **openpyxl** | `2.3.3` / `3.1.5` | Leitores e manipuladores de dados em memória. Essenciais para o fluxo de importação das planilhas de malha aérea em `.xlsx`. |
| **networkx** | `3.6.1` | Biblioteca avançada para teoria dos grafos. Utilizada na Inteligência de Rotas para calcular os caminhos de voo (`all_simple_paths`) entre aeroportos. |
| **ldap3** | `2.9.1` | Protocolo de comunicação utilizado pelo `AuthService` para validar credenciais diretamente no Active Directory corporativo. |
| **waitress** | `3.0.2` | Servidor WSGI de grau de produção utilizado no arquivo `WSGI.py` para rodar o Flask em modo multi-thread. |

## 8. Arquitetura Consolidada e Fluxo de Dados

Para consolidar o entendimento do projeto **Luft-ConnectAir**, o fluxo de execução padrão da funcionalidade principal (O Planejamento de Cargas) segue o padrão arquitetural abaixo:

1. **Apresentação (Cliente):** O navegador do usuário solicita o carregamento da tela de Backlog ou Diário (`GET /Planejamento/...`) contendo o token de sessão.
2. **Controlador (`Routes/Planejamento.py`):** Intercepta a requisição, valida as permissões e repassa o pedido ao serviço.
3. **Serviço (`PlanejamentoService.py`):** Aciona a `_QueryBase` para buscar no SQL Server exclusivamente os CTCs "limpos" (sem AWB emitido e validados com TM).
4. **Algoritmo de Negócio (`MalhaService`):** Ao selecionar os CTCs, o sistema constrói um Grafo em memória (`networkx`) e calcula o roteamento geográfico respeitando as conexões válidas.
5. **Integração Externa (`TabelaFreteService`):** O serviço é invocado para calcular e atrelar os custos financeiros de cada trecho mapeado para os CTCs.
6. **Resposta e Persistência:** O Controlador devolve as opções, o usuário confirma o roteiro, e o método `RegistrarPlanejamento` salva toda a operação no banco PostgreSQL, finalizando o fluxo.

### Diagrama Funcional Simplificado

```text
[ NAVEGADOR / NGINX ] 
        │ (HTTP/REST)
        ▼
[ WAITRESS (WSGI.py) ] ───▶ [ APP.PY (Flask Core) ]
                                   │
                                   ├─▶ [ Middleware de Auth (LogService / AuthService) ]
                                   │
                                   ▼
[ CAMADA DE ROTAS (Routes/) ] ◀──(Valida Dados e Permissões)
        │
        ▼
[ CAMADA DE SERVIÇOS (Services/) ] ───▶ (Regras de Negócio, Cálculo de Grafos, Uploads)
        │
        ▼
[ CAMADA DE ORM (Models/) ] 
        │
        ├─▶ ENGINE POSTGRES (Dados Geográficos / Relatórios rápidos)
        │
        └─▶ ENGINE SQL SERVER (ERP, Cadastros Legados, AWBs, Financeiro)

```

A documentação do ecossistema e dos arquivos fornecidos está completa, cobrindo com altíssimo rigor a visão geral, configurações base, módulos de roteamento, modelagem de dados, regras de negócio e dependências estruturais do **Luft-ConnectAir**.