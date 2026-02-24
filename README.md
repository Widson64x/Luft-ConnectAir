```markdown
# ✈️ Luft-ConnectAir

![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)
![Flask](https://img.shields.io/badge/Flask-black?logo=flask)
![SQL_ALCHEMY]()
[![Deploy Automatico](https://github.com/widson64x/luft-connectair/actions/workflows/deploy.yml/badge.svg)](https://github.com/widson64x/luft-connectair/actions/workflows/deploy.yml)
![License](https://img.shields.io/github/license/widson64x/luft-connectair)

**Luft-ConnectAir** é uma aplicação web robusta desenvolvida em Python (Flask) projetada para a gestão de malhas aéreas, planejamento de rotas, controle de AWBs (Air Waybills), aeroportos, tarifas e logística. A arquitetura é baseada na separação de responsabilidades (Rotas, Serviços e Modelos), com suporte a múltiplos bancos de dados (SQL Server e PostgreSQL).

---

## 🛠️ Stack Tecnológica e Pré-requisitos

### Tecnologias Principais
* **Backend:** Python 3.9+, Flask
* **ORM e Banco de Dados:** SQLAlchemy, Microsoft SQL Server, PostgreSQL
* **Frontend:** HTML5, CSS3, JavaScript (Jinja2 Templates)
* **CI/CD:** GitHub Actions
* **Servidor Web:** WSGI (Gunicorn/Waitress dependendo do ambiente)

### Pré-requisitos de Ambiente
1. **Python 3.9** ou superior instalado.
2. **Gerenciador de pacotes PIP**.
3. **Drivers de Banco de Dados**:
   * ODBC Driver for SQL Server (necessário para a conexão com o SQL Server).
   * Cliente PostgreSQL (para conexões Postgres).
4. Acesso aos bancos de dados com as credenciais configuradas corretamente nas variáveis de ambiente.

---

## 🚀 Passo a Passo para Instalação e Execução

### 1. Clonar o Repositório
```bash
git clone [https://github.com/widson64x/luft-connectair.git](https://github.com/widson64x/luft-connectair.git)
cd luft-connectair

```

### 2. Configurar o Ambiente Virtual

É altamente recomendado isolar as dependências do projeto.

```bash
# Criar o ambiente virtual
python -m venv venv

# Ativar no Windows:
venv\Scripts\activate
# Ativar no Linux/Mac:
source venv/bin/activate

```

### 3. Instalar Dependências

```bash
pip install -r requirements.txt

```

### 4. Configurar as Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto (ou exporte as variáveis no seu SO) contendo as strings de conexão e chaves secretas necessárias (ex.: `DB_HOST`, `DB_USER`, `DB_PASS`, `SECRET_KEY`). As configurações globais são lidas em `Configuracoes.py` e `Conexoes.py`.

### 5. Execução em Ambiente de Desenvolvimento (Local)

```bash
python App.py

```

A aplicação iniciará o servidor de desenvolvimento do Flask.

### 6. Execução em Produção

Em produção, utilize o arquivo `WSGI.py` com um servidor WSGI adequado (ex.: Gunicorn no Linux ou Waitress no Windows).

```bash
gunicorn WSGI:app --bind 0.0.0.0:8000

```

---

## 🌍 Acesso à Aplicação

Por padrão, a aplicação roda localmente na porta `5000` (ou a definida no seu ambiente).

* **URL Base (Dev):** `http://localhost:5000`
* **Rotas Principais:**
* `/auth/login` - Autenticação de usuários.
* `/dashboard` - Painel principal do sistema.
* `/planejamento` - Módulo de inteligência e planejamento de rotas (Acesso ao mapa e editor).
* `/malha` - Gerenciamento da malha aérea.
* `/acompanhamento` - Tracking de AWBs e voos.
* `/tabelas-frete` - Gerenciamento de custos e tarifas.
* `/configuracoes` - Configurações de Cias Aéreas e Permissões.



---

## 🔄 Fluxo Geral do Sistema (Arquitetura)

A aplicação segue um padrão arquitetural limpo e modular:

1. **Frontend (Templates/Static):** O usuário interage com as telas renderizadas pelo Jinja2. O JavaScript realiza requisições assíncronas (AJAX/Fetch API) para os endpoints.
2. **Controladores (Routes/):** Os *Blueprints* do Flask recebem as requisições HTTP, lidam com a sessão/autenticação e repassam os dados para a camada de Serviços.
3. **Regras de Negócio (Services/):** Aqui reside o "coração" da aplicação. Toda validação, lógica de roteamento (`RouteIntelligenceService.py`), cálculo geométrico e transformações de dados acontecem nesta camada, mantendo as rotas limpas.
4. **Camada de Dados (Models/ & Conexoes.py):** Os serviços utilizam as classes do SQLAlchemy para realizar consultas e persistência em bancos SQL Server ou PostgreSQL.

---

## 📂 Estrutura e Árvore do Projeto

Abaixo detalhamos a organização do diretório raiz:

```text
Luft-ConnectAir/
├── .github/workflows/          # Scripts de CI/CD para deploy e controle de versão (Actions)
├── _DEV/                       # Scripts auxiliares para desenvolvedores (Diagnósticos, MockDB, etc.)
│   ├── AtualizarBanco.py
│   ├── InicializarBanco.py
│   └── ...
├── Data/                       # Arquivos estáticos de massa de dados (CSVs, Excel para cargas de malha, aeroportos, etc.)
├── Models/                     # Mapeamento ORM (Object-Relational Mapping) usando SQLAlchemy
│   ├── POSTGRES/               # Entidades exclusivas do banco PostgreSQL
│   ├── SQL_SERVER/             # Entidades mapeadas para o banco principal SQL Server (Aeroporto, AWB, Manifesto, etc.)
│   └── UsuarioModel.py         # Modelo geral de autenticação
├── Routes/                     # Controladores/Endpoints (Flask Blueprints) organizados por domínio
│   ├── Global/                 # APIs globais e endpoints utilitários
│   ├── Acompanhamento.py       # Rotas de tracking
│   ├── Auth.py                 # Login e gerenciamento de sessão
│   ├── Planejamento.py         # Endpoints para elaboração de rotas e malhas
│   └── ...
├── Scripts/                    # Scripts de utilidade geral e automação do sistema (ex: GestaoVersao.py)
├── Services/                   # Camada de Regras de Negócio
│   ├── Logic/                  # Inteligência de negócio complexa (ex: RouteIntelligenceService.py)
│   ├── Shared/                 # Serviços compartilhados (Geolocalização, Voos, AWB)
│   ├── PlanejamentoService.py  # Lógica de criação de planos de voo
│   └── ...
├── SQL/                        # Consultas SQL puras (Raw SQL) separadas para relatórios e views complexas
├── Static/                     # Arquivos públicos front-end
│   ├── CSS/                    # Folhas de estilo modulares (Global, Temas, componentes)
│   ├── Img/                    # Assets visuais e logotipos das companhias (AZUL, GOL, LATAM)
│   └── JS/                     # Lógica front-end dividida por contexto (Base, Planejamento, Aeroportos)
├── Templates/                  # Views em HTML renderizadas pelo Jinja2
│   ├── Components/             # Modais e fragmentos HTML reutilizáveis (ex: _ModalAwb.html)
│   ├── Layouts base e pastas divididas por domínio (Dashboard, Planejamento, Configurações)
│   └── Base.html               # Master page herdada pelos demais templates
├── Utils/                      # Funções helpers genéricas (Formatação, Texto, Geometria)
├── App.py                      # Arquivo de entrada para Desenvolvimento (App Factory/Setup)
├── Conexoes.py                 # Gerenciamento central das instâncias de conexão e Session Makers
├── Configuracoes.py            # Carregamento de variáveis de ambiente e setup da aplicação
├── requirements.txt            # Lista de dependências e bibliotecas Python
├── VERSION                     # Arquivo de controle estrito da versão atual do software
└── WSGI.py                     # Entrypoint de execução para ambiente de Produção

```

### Detalhamento dos Diretórios Chave

* **`_DEV/`**: Utilize esta pasta exclusivamente em ambiente local. Contém scripts destrutivos ou de setup, como o `InicializarBanco.py`. **Nunca** execute estes scripts em produção.
* **`Services/Logic/RouteIntelligenceService.py`**: Principal motor da aplicação. É aqui que algoritmos de definição de rotas e interseções de malha aérea operam.
* **`Templates/Components/`**: Mantenha a componentização visual aqui para evitar redundância de código nos templates principais.

---

## 🛡️ Boas Práticas e Observações para Desenvolvedores

1. **Separação de Responsabilidades (SoC):**
* **NÃO** escreva regras de negócio nas `Routes/`. As rotas devem apenas receber o Request, chamar uma função dentro de `Services/` e retornar o Response (JSON ou HTML).
* **NÃO** faça consultas de banco de dados diretamente nos arquivos de Rota. Use os métodos criados nos *Services*.


2. **Gerenciamento de Banco de Dados:**
* A aplicação lida com dois SGBDs distintos (`POSTGRES` e `SQL_SERVER`). Certifique-se de importar e usar a conexão correta dependendo do contexto do dado. Referencie as pastas adequadas dentro de `Models/`.


3. **Arquivos Estáticos e Cache:**
* Caso faça alterações em `/Static/JS` ou `/Static/CSS`, garanta que os manipuladores de cache do navegador sejam atualizados, utilizando "cache busting" se necessário ou forçando recarregamento com `Ctrl+F5`.


4. **Tratamento de Exceções:**
* O fluxo de `Services/` deve levantar exceções (Raise) customizadas. O tratamento visual (mensagens de erro ao usuário) deve ser resolvido pelas `Routes/` e `Templates/`.


5. **Versionamento:**
* Qualquer nova release deve ter a numeração ajustada no arquivo `VERSION` e gerida através do script `Scripts/GestaoVersao.py`, que dispara os hooks corretos no `.github/workflows`.



---

*Documentação gerada para orientar novos desenvolvedores na manutenção e evolução contínua da plataforma Luft-ConnectAir.*