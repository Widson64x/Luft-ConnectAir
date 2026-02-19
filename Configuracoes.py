import os # Biblioteca para manipulação de caminhos e variáveis de ambiente
import urllib.parse
import secrets
from dotenv import load_dotenv

load_dotenv() # Carrega as variáveis de ambiente do arquivo .env para o ambiente de execução

class ConfiguracaoBase:
    """
    Configurações Base compartilhadas entre todos os ambientes.
    """
    DIR_BASE = os.path.dirname(os.path.abspath(__file__))
    # Nome da aplicação, usado para exibição e prefixo de rotas (pode ser personalizado via .env)
    APP_NAME = os.getenv("APP_NAME", "Luft-ConnectAir") # Obtém a variável APP_NAME, com a função getenv, que permite definir um valor padrão caso a variável não esteja presente. Se APP_NAME não estiver definido no .env, ele usará "Luft-ConnectAir" como nome da aplicação.

    # Define o prefixo global das rotas (Ex: /Luft-ConnectAir)
    ROUTE_PREFIX = os.getenv("ROUTE_PREFIX", "/Luft-ConnectAir")
    
    # --- Configurações do SQL SERVER (Banco de Negócio/ERP) ---
    SQL_HOST = os.getenv("SQL_HOST")
    SQL_PORT = os.getenv("SQL_PORT", "1433")
    SQL_DB   = os.getenv("SQL_DB")
    SQL_USER = os.getenv("SQL_USER")
    SQL_PASS = os.getenv("SQL_PASS")
    
    # --- Configurações do POSTGRESQL (Banco da Aplicação/Malha) ---
    PG_HOST = os.getenv("PGDB_HOST", "localhost")
    PG_PORT = os.getenv("PGDB_PORT", "5432")
    PG_USER = os.getenv("PGDB_USER", "postgres")
    PG_PASS = os.getenv("PGDB_PASSWORD", "")
    PG_DRIVER = os.getenv("PGDB_DRIVER", "psycopg")

    AD_SERVER = os.getenv("LDAP_SERVER")
    AD_DOMAIN = os.getenv("LDAP_DOMAIN")
    
    # Define se mostra logs de conexão (SQLAlchemy Echo)
    MOSTRAR_LOGS_DB = os.getenv("DB_CONNECT_LOGS", "False").lower() == "true"

    DIR_UPLOADS = os.path.join(DIR_BASE, "Data", "Uploads")
    DIR_TEMP    = os.path.join(DIR_BASE, "Data", "Temp")
    DIR_LOGS    = os.path.join(DIR_BASE, "Logs")

    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))

    # --- Lógica de Segurança da SECRET_KEY ---
    _chave_env = os.getenv("APP_SECRET_KEY")
    
    # Verifica se a chave existe e não é "null". Se não for segura, gera uma nova.
    if _chave_env and _chave_env.lower() != "null":
        APP_SECRET_KEY = _chave_env
    else:
        # Gera uma chave URL-safe segura de 64 bytes
        APP_SECRET_KEY = secrets.token_urlsafe(64)
        print(f"[!] AVISO DE SEGURANÇA: 'APP_SECRET_KEY' não encontrada no .env.")
        print(f"[!] Uma chave temporária foi gerada: {APP_SECRET_KEY}")

    def ObterUrlSqlServer(self):
        """
        Gera a string de conexão para o SQL Server.
        """
        if not self.SQL_PASS:
            return (
                f"mssql+pyodbc://{self.SQL_HOST}:{self.SQL_PORT}/{self.SQL_DB}"
                "?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes"
            )
        
        SenhaCodificada = urllib.parse.quote_plus(self.SQL_PASS)
        return (
            f"mssql+pyodbc://{self.SQL_USER}:{SenhaCodificada}@{self.SQL_HOST}:{self.SQL_PORT}/{self.SQL_DB}"
            "?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"
        )

    def ObterUrlPostgres(self):
        """
        Gera a string de conexão para o PostgreSQL.
        """
        # Se a senha estiver vazia, tenta conectar sem autenticação (útil para dev local com trust auth)
        SenhaCodificada = urllib.parse.quote_plus(self.PG_PASS)
        return f"postgresql+{self.PG_DRIVER}://{self.PG_USER}:{SenhaCodificada}@{self.PG_HOST}:{self.PG_PORT}/{self.PG_DB_NAME}"

# --- Ambientes Específicos ---

class ConfiguracaoDesenvolvimento(ConfiguracaoBase):
    DEBUG = True
    PG_DB_NAME = os.getenv("PGDB_NAME_DEV", "Luft-ConnectAir_DEV")

class ConfiguracaoHomologacao(ConfiguracaoBase):
    DEBUG = False
    PG_DB_NAME = os.getenv("PGDB_NAME_HOMOLOG", "Luft-ConnectAir_HOMOLOG")

class ConfiguracaoProducao(ConfiguracaoBase):
    DEBUG = False
    PG_DB_NAME = os.getenv("PGDB_NAME_PROD", "Luft-ConnectAir")

# Mapa de seleção do ambiente
MapaConfiguracao = {
    "desenvolvimento": ConfiguracaoDesenvolvimento,
    "homologacao": ConfiguracaoHomologacao,
    "producao": ConfiguracaoProducao
}

# Inicializa a configuração
NomeAmbiente = os.getenv("AMBIENTE_APP", "desenvolvimento").lower()
ConfiguracaoAtual = MapaConfiguracao.get(NomeAmbiente, ConfiguracaoDesenvolvimento)()

print(f"[OK] Configurações carregadas em modo: {NomeAmbiente.upper()}")
print(f"[OK] Banco Postgres Alvo: {ConfiguracaoAtual.PG_DB_NAME}")
# Opcional: imprimir aviso se a chave for temporária para lembrar o dev
if not os.getenv("APP_SECRET_KEY") or os.getenv("APP_SECRET_KEY") == "null":
    print("[!] ATENÇÃO: A APP_SECRET_KEY é temporária. Sessões serão invalidadas ao reiniciar.")