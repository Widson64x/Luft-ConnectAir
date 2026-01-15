from sqlalchemy import text
import sys
import os
# Adiciona o caminho raiz do projeto para importar Conexoes
ProjetoPath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ProjetoPath not in sys.path:
    sys.path.append(ProjetoPath)
from Conexoes import ObterEngineSqlServer

def ListarTabelas():
    print("🔍 Iniciando busca de tabelas no SQL Server...")
    
    Engine = ObterEngineSqlServer()
    if not Engine:
        print("❌ Falha na conexão com SQL Server.")
        return

    try:
        with Engine.connect() as conn:
            # Query para listar todas as tabelas e schemas
            Query = text("""
                SELECT TABLE_SCHEMA, TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_TYPE = 'BASE TABLE'
                AND TABLE_NAME LIKE '%ctc%' -- Filtra tabelas parecidas com CTC
                ORDER BY TABLE_NAME
            """)
            
            Resultados = conn.execute(Query).fetchall()
            
            if Resultados:
                print(f"✅ Encontradas {len(Resultados)} tabelas parecidas com 'ctc':")
                print("-" * 40)
                for Row in Resultados:
                    Schema, Tabela = Row
                    print(f"📂 Schema: {Schema} | 📄 Tabela: {Tabela}")
                print("-" * 40)
                print("💡 DICA: Copie o Schema e o Nome exatos para o seu Model.")
            else:
                print("⚠️ Nenhuma tabela com 'ctc' no nome foi encontrada.")
                
                # Se não achou, lista as primeiras 10 tabelas quaisquer para ver se o banco está certo
                print("\nListando 10 tabelas aleatórias para verificação:")
                QueryGeral = text("SELECT TOP 10 TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES")
                Geral = conn.execute(QueryGeral).fetchall()
                for R in Geral:
                    print(f" - {R[0]}.{R[1]}")

    except Exception as e:
        print(f"❌ Erro ao consultar: {e}")

if __name__ == "__main__":
    ListarTabelas()