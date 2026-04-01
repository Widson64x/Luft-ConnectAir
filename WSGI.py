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

if __name__ == "__main__": 
    # Configurações do ambiente
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "9003"))

    # Pega o prefixo usando a mesma lógica do App.py
    from Configuracoes import ConfiguracaoAtual
    prefix = ConfiguracaoAtual.ROUTE_PREFIX
    
    # Se o prefixo for vazio, definimos o padrão para o ConnectAir
    if not prefix:
        prefix = "/Luft-ConnectAir"

    print(f"--> INICIANDO SERVIDOR WSGI (WAITRESS) PARA O Luft-ConnectAir")
    print(f"--> Endereço: http://{host}:{port}{prefix}")
    print(f"--> Modo: Produção (Serviço Windows)")
    
    # Inicia o servidor Waitress com o url_prefix!
    serve(app, host=host, port=port, threads=6, url_prefix=prefix)