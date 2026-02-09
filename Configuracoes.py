import os
import urllib.parse
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

class ConfiguracaoBase:
    """
    Configurações Base compartilhadas entre todos os ambientes.
    """
    DIR_BASE = os.path.dirname(os.path.abspath(__file__))
    
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
    PG_DRIVER = os.getenv("PGDB_DRIVER", "psycopg") # Ex: psycopg2 ou psycopg (v3)

    AD_SERVER = os.getenv("LDAP_SERVER")
    AD_DOMAIN = os.getenv("LDAP_DOMAIN")
    
    APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "CHAVE_SUPER_SECRETA_DO_PROJETO_VOOS")
    
    # Define se mostra logs de conexão (SQLAlchemy Echo)
    MOSTRAR_LOGS_DB = os.getenv("DB_CONNECT_LOGS", "False").lower() == "true"

    DIR_UPLOADS = os.path.join(DIR_BASE, "Data", "Uploads")
    DIR_TEMP    = os.path.join(DIR_BASE, "Data", "Temp")
    DIR_LOGS    = os.path.join(DIR_BASE, "Logs")

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
        Formato: postgresql+driver://user:pass@host:port/dbname
        """
        SenhaCodificada = urllib.parse.quote_plus(self.PG_PASS)
        # self.PG_DB_NAME será definido nas classes filhas (Ambientes)
        return f"postgresql+{self.PG_DRIVER}://{self.PG_USER}:{SenhaCodificada}@{self.PG_HOST}:{self.PG_PORT}/{self.PG_DB_NAME}"

# --- Ambientes Específicos ---

class ConfiguracaoDesenvolvimento(ConfiguracaoBase):
    DEBUG = True
    # Define o nome do banco específico para DEV
    PG_DB_NAME = os.getenv("PGDB_NAME_DEV", "Luft-ConnectAir_DEV")

class ConfiguracaoHomologacao(ConfiguracaoBase):
    DEBUG = False
    # Define o nome do banco específico para HOMOLOG
    PG_DB_NAME = os.getenv("PGDB_NAME_HOMOLOG", "Luft-ConnectAir_HOMOLOG")

class ConfiguracaoProducao(ConfiguracaoBase):
    DEBUG = False
    # Define o nome do banco específico para PROD
    PG_DB_NAME = os.getenv("PGDB_NAME_PROD", "Luft-ConnectAir")

# Mapa de seleção do ambiente
MapaConfiguracao = {
    "desenvolvimento": ConfiguracaoDesenvolvimento,
    "homologacao": ConfiguracaoHomologacao,
    "producao": ConfiguracaoProducao
}

# Inicializa a configuração baseada no .env (AMBIENTE_APP)
# Se não encontrar, assume 'desenvolvimento'
NomeAmbiente = os.getenv("AMBIENTE_APP", "desenvolvimento").lower()
ConfiguracaoAtual = MapaConfiguracao.get(NomeAmbiente, ConfiguracaoDesenvolvimento)()

print(f"[OK] Configurações carregadas em modo: {NomeAmbiente.upper()}")
print(f"[OK] Banco Postgres Alvo: {ConfiguracaoAtual.PG_DB_NAME}")