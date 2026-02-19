# Executar_Producao.py
import os
import sys

# Garante que o diretório atual esteja no path para importação correta
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importa a instância 'app' diretamente do seu arquivo App.py
# (O App.py atual instancia o Flask globalmente, não usa factory 'create_app')
from App import app

# Tenta importar o Waitress para produção
try:
    from waitress import serve
except ImportError:
    print("ERRO: A biblioteca 'waitress' não está instalada.")
    print("Instale rodando: pip install waitress")
    sys.exit(1)

if __name__ == "__main__": # Méto python padrão para execução direta, se __name_ for "__main__", significa que este script está sendo executado diretamente, e não importado como módulo
    # Configurações do ambiente
    # Em produção com NGINX na frente, geralmente rodamos em localhost
    host = os.environ.get("HOST", "127.0.0.1")
    
    # Porta interna do serviço (O NGINX vai redirecionar a porta 80 para cá)
    port = int(os.environ.get("PORT", "9007"))

    print(f"--> INICIANDO SERVIDOR WSGI (WAITRESS) PARA O Luft-ConnectAir")
    print(f"--> Endereço: http://{host}:{port}")
    print(f"--> Modo: Produção (Serviço Windows)")
    
    # Inicia o servidor Waitress
    # threads=6 é um bom padrão para aplicações médias, ajuste conforme a carga
    serve(app, host=host, port=port, threads=6)