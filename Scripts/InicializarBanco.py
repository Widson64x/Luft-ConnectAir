from sqlalchemy import text
import os
import sys
# Ajusta o path para importar módulos corretamente
CaminhoBase = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(CaminhoBase)

from Conexoes import ObterEnginePostgres
from Models.SQL_SERVER.Base import BasePostgres

# Importar os modelos para que o SQLAlchemy saiba o que criar
from Models.SQL_SERVER.MalhaAerea import RemessaMalha, VooMalha
from Models.SQL_SERVER.Aeroporto import RemessaAeroportos, Aeroporto
from Models.SQL_SERVER.Cidade import RemessaCidade, Cidade 
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
            print("   - Tabela: Tb_Cidade (NOVO)")
            
        except Exception as e:
            print(f"❌ Erro ao inicializar banco: {e}")
    else:
        print("❌ Não foi possível conectar ao banco.")

if __name__ == "__main__":
    CriarTabelas()