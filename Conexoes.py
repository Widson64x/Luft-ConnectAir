from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from Configuracoes import ConfiguracaoAtual

# Carrega as URLs das configurações
URL_BANCO_SQL = ConfiguracaoAtual.ObterUrlSqlServer()
URL_BANCO_PG  = ConfiguracaoAtual.ObterUrlPostgres()

# --- SQL SERVER ---
def ObterEngineSqlServer():
    """
    Cria e retorna a Engine de conexão com o SQL Server (ERP).
    Usa NullPool para evitar travamentos de sessão no servidor legado.
    """
    try:
        Engine = create_engine(
            URL_BANCO_SQL, 
            poolclass=NullPool, 
            # echo=ConfiguracaoAtual.MOSTRAR_LOGS_DB
            echo=False
        )
        return Engine
    except Exception as Erro:
        print(f"❌ Erro crítico ao criar engine do SQL Server: {Erro}")
        return None

def ObterSessaoSqlServer():
    Engine = ObterEngineSqlServer()
    if Engine:
        return sessionmaker(bind=Engine)()
    return None

# --- POSTGRESQL ---
def ObterEnginePostgres():
    """
    Cria e retorna a Engine do PostgreSQL (Banco da Aplicação).
    Aqui usamos o pool padrão do SQLAlchemy (mais eficiente para a App Web).
    'pool_pre_ping=True' testa a conexão antes de usar, evitando erros de queda.
    """
    try:
        Engine = create_engine(
            URL_BANCO_PG, 
            pool_pre_ping=True, # Verifica se o banco tá vivo antes de tentar query
            # echo=ConfiguracaoAtual.MOSTRAR_LOGS_DB
            echo=False
        )
        return Engine
    except Exception as Erro:
        print(f"❌ Erro crítico ao criar engine do PostgreSQL: {Erro}")
        return None

def ObterSessaoPostgres():
    """
    Fábrica de sessões para o PostgreSQL.
    Use esta função para manipular os dados da Malha Aérea.
    """
    Engine = ObterEnginePostgres()
    if Engine:
        return sessionmaker(bind=Engine)()
    return None