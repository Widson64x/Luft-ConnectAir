import sys
import os
import argparse

# Adiciona o diretório raiz ao path para importar os módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Services.VersaoService import VersaoService

def Executar():
    parser = argparse.ArgumentParser(description='Gestão de Versionamento do T-FlightOps')
    
    subparsers = parser.add_subparsers(dest='comando', help='Comandos disponíveis')

    # Comando: Nova Versão (Usado no Merge)
    parser_nova = subparsers.add_parser('nova', help='Registra uma nova versão')
    parser_nova.add_argument('--numero', required=True, help='Número da versão (ex: 1.0.0)')
    parser_nova.add_argument('--estagio', default='Alpha', help='Estágio inicial (ex: Alpha)')
    parser_nova.add_argument('--msg', default='Atualização automática', help='Notas da versão')
    parser_nova.add_argument('--dev', default='Sistema', help='Responsável')
    parser_nova.add_argument('--hash', default=None, help='Hash do Commit Git')

    # Comando: Promover (Usado pelo Dev)
    parser_promover = subparsers.add_parser('promover', help='Promove o estágio da versão atual')
    parser_promover.add_argument('--estagio', required=True, help='Novo estágio (ex: Beta, Stable)')

    # Comando: Atual (Visualizar)
    parser_atual = subparsers.add_parser('atual', help='Exibe a versão atual')

    args = parser.parse_args()

    if args.comando == 'nova':
        VersaoService.RegistrarNovaVersao(args.numero, args.estagio, args.msg, args.dev, hash_commit=args.hash)
    
    elif args.comando == 'promover':
        VersaoService.PromoverEstagio(args.estagio)
        
    elif args.comando == 'atual':
        dados = VersaoService.ObterVersaoAtual()
        print(f"Versão Atual: {dados['NumeroVersao']} - {dados['Estagio']}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    Executar()