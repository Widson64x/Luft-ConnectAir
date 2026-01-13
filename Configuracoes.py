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
    
    # --- Configurações do SQL SERVER (Banco de Negócio/ERP) ---
    SQL_HOST = os.getenv("SQL_HOST")
    SQL_PORT = os.getenv("SQL_PORT", "1433")
    SQL_DB   = os.getenv("SQL_DB")
    SQL_USER = os.getenv("SQL_USER")
    SQL_PASS = os.getenv("SQL_PASS")
    
    # Define se mostra logs de conexão (SQLAlchemy Echo)
    MOSTRAR_LOGS_DB = os.getenv("DB_LOGS", "False").lower() == "true"

    def ObterUrlSqlServer(self):
        """
        Gera a string de conexão (Connection String) para o SQL Server.
        Utiliza o driver ODBC Driver 17.
        """
        if not self.SQL_PASS:
            # Caso não tenha senha, assume Autenticação do Windows (Trusted Connection)
            return (
                f"mssql+pyodbc://{self.SQL_HOST}:{self.SQL_PORT}/{self.SQL_DB}"
                "?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes"
            )
        
        # Codifica a senha para evitar erros com caracteres especiais (@, #, etc)
        SenhaCodificada = urllib.parse.quote_plus(self.SQL_PASS)
        return (
            f"mssql+pyodbc://{self.SQL_USER}:{SenhaCodificada}@{self.SQL_HOST}:{self.SQL_PORT}/{self.SQL_DB}"
            "?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"
        )

# --- Ambientes Específicos ---

class ConfiguracaoDesenvolvimento(ConfiguracaoBase):
    DEBUG = True
    # Aqui poderíamos ter um banco Postgres de DEV separado, se necessário

class ConfiguracaoHomologacao(ConfiguracaoBase):
    DEBUG = False

class ConfiguracaoProducao(ConfiguracaoBase):
    DEBUG = False

# Mapa de seleção do ambiente
MapaConfiguracao = {
    "desenvolvimento": ConfiguracaoDesenvolvimento,
    "homologacao": ConfiguracaoHomologacao,
    "producao": ConfiguracaoProducao
}

# Inicializa a configuração baseada no .env
NomeAmbiente = os.getenv("AMBIENTE_APP", "desenvolvimento").lower()
ConfiguracaoAtual = MapaConfiguracao.get(NomeAmbiente, ConfiguracaoDesenvolvimento)()

print(f"🔧 Configurações carregadas em modo: {NomeAmbiente.upper()}")