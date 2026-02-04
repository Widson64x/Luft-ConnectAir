from sqlalchemy import text
import os
import sys

# Ajusta o path para importar módulos corretamente
CaminhoBase = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(CaminhoBase)

from Conexoes import ObterEnginePostgres
from Models.SQL_SERVER.Aeroporto import RemessaAeroportos, Aeroporto
from Models.SQL_SERVER.Base import BasePostgres

def Recriar():
    print("🔨 Recriando tabelas de Aeroportos com nova estrutura...")
    Engine = ObterEnginePostgres()
    
    if Engine:
        try:
            # Dropando tabelas antigas para garantir (A ordem importa por causa da FK)
            with Engine.connect() as conn: # With serve para garantir o fechamento da conexão
                print("🗑️  Apagando tabelas antigas...")
                conn.execute(text('DROP TABLE IF EXISTS "MalhaAerea"."Tb_Aeroporto" CASCADE;'))
                conn.execute(text('DROP TABLE IF EXISTS "MalhaAerea"."Tb_RemessaAeroporto" CASCADE;'))
                conn.commit()

            # Criando novas
            print("✨ Criando novas tabelas...")
            BasePostgres.metadata.create_all(Engine)
            
            print("✅ Sucesso! Tabelas Tb_RemessaAeroporto e Tb_Aeroporto criadas.")
            
        except Exception as e:
            print(f"❌ Erro: {e}")

if __name__ == "__main__":
    Recriar()