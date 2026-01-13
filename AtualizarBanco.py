from sqlalchemy import text
from Conexoes import ObterEnginePostgres

def AtualizarSchema():
    print("🔨 Atualizando estrutura do banco...")
    Engine = ObterEnginePostgres()
    
    if Engine:
        try:
            with Engine.connect() as conn:
                # Adiciona a coluna se ela não existir
                Sql = """
                ALTER TABLE "MalhaAerea"."Tb_RemessaMalha" 
                ADD COLUMN IF NOT EXISTS "TipoAcao" VARCHAR(50) DEFAULT 'Importacao';
                """
                conn.execute(text(Sql))
                conn.commit()
                print("✅ Coluna 'TipoAcao' adicionada com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao atualizar: {e}")

if __name__ == "__main__":
    AtualizarSchema()