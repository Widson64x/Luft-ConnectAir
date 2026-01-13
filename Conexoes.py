from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from Configuracoes import ConfiguracaoAtual

# Carrega a URL do SQL Server das configurações
URL_BANCO_SQL = ConfiguracaoAtual.ObterUrlSqlServer()

def ObterEngineSqlServer():
    """
    Cria e retorna a Engine de conexão com o SQL Server.
    
    Motivo do NullPool: 
    O SQL Server gerencia conexões de forma diferente. Em aplicações web que acessam
    ERPs legados, muitas vezes é mais seguro abrir e fechar a conexão explicitamente 
    (sem pool) para evitar travamentos de sessão 'dormindo' no servidor do ERP.
    """
    try:
        Engine = create_engine(
            URL_BANCO_SQL, 
            poolclass=NullPool, 
            echo=ConfiguracaoAtual.MOSTRAR_LOGS_DB
        )
        return Engine
    except Exception as Erro:
        print(f"❌ Erro crítico ao criar engine do SQL Server: {Erro}")
        return None

def ObterSessaoSqlServer():
    """
    Fábrica de Sessões para uso rápido.
    Retorna uma nova instância de Session pronta para uso.
    """
    Engine = ObterEngineSqlServer()
    if Engine:
        FabricaSessao = sessionmaker(bind=Engine)
        return FabricaSessao()
    return None