from sqlalchemy import text
from Conexoes import ObterEnginePostgres
from Models.POSTGRES.Base import BasePostgres

# Importar os modelos para que o SQLAlchemy saiba o que criar
from Models.POSTGRES.MalhaAerea import RemessaMalha, VooMalha

def CriarTabelas():
    print("🚀 Iniciando setup do Banco de Dados...")
    
    Engine = ObterEnginePostgres()
    
    if Engine:
        try:
            # 1. Cria o Schema explicitamente (caso não exista)
            print("🔨 Verificando Schema 'MalhaAerea'...")
            with Engine.connect() as conn:
                conn.execute(text('CREATE SCHEMA IF NOT EXISTS "MalhaAerea";'))
                conn.commit() # É necessário commitar a criação do schema
            
            # 2. Cria as tabelas dentro do schema
            print("🔨 Criando/Verificando tabelas...")
            BasePostgres.metadata.create_all(Engine)
            
            print("✅ Sucesso! Estrutura criada:")
            print("   - Schema: MalhaAerea")
            print("   - Tabela: Tb_RemessaMalha")
            print("   - Tabela: Tb_VooMalha")
            
        except Exception as e:
            print(f"❌ Erro ao inicializar banco: {e}")
    else:
        print("❌ Não foi possível conectar ao banco.")

if __name__ == "__main__":
    CriarTabelas()