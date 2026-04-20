import sys
import os
import argparse

# Adiciona o diretório raiz ao path para importar os módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Services.VersaoService import VersaoService

def Executar():
    parser = argparse.ArgumentParser(description='Gestão de Versionamento do Luft-ConnectAir')
    parser.add_argument('--sistema-id', type=int, default=None, help='ID do sistema na Tb_Sistema. Se omitido, usa SISTEMA_ID ou 1.')
    parser_comum = argparse.ArgumentParser(add_help=False)
    parser_comum.add_argument('--sistema-id', type=int, default=None, help='ID do sistema na Tb_Sistema. Se omitido, usa SISTEMA_ID ou 1.')
    
    subparsers = parser.add_subparsers(dest='comando', help='Comandos disponíveis')

    # Comando: Nova Versão (Usado no Merge)
    parser_nova = subparsers.add_parser('nova', parents=[parser_comum], help='Registra ou atualiza uma versão')
    parser_nova.add_argument('--numero', required=True, help='Número da versão (ex: 1.0.0)')
    parser_nova.add_argument('--estagio', default='Alpha', help='Estágio inicial (ex: Alpha)')
    parser_nova.add_argument('--msg', default='Atualização automática', help='Notas da versão')
    parser_nova.add_argument('--dev', default='Sistema', help='Responsável')
    parser_nova.add_argument('--hash', default=None, help='Hash do Commit Git')

    # Comando: Promover (Usado pelo Dev)
    parser_promover = subparsers.add_parser('promover', parents=[parser_comum], help='Promove o estágio da versão atual')
    parser_promover.add_argument('--estagio', required=True, help='Novo estágio (ex: Beta, Stable)')
    parser_promover.add_argument('--numero', default=None, help='Número da versão a promover. Se omitido, usa a versão atual do sistema.')

    # Comando: Atual (Visualizar)
    parser_atual = subparsers.add_parser('atual', parents=[parser_comum], help='Exibe a versão atual')

    args = parser.parse_args()

    if args.comando == 'nova':
        VersaoService.RegistrarNovaVersao(
            args.numero,
            args.estagio,
            args.msg,
            args.dev,
            hash_commit=args.hash,
            id_sistema=args.sistema_id
        )
    
    elif args.comando == 'promover':
        VersaoService.PromoverEstagio(args.estagio, id_sistema=args.sistema_id, numero_versao=args.numero)
        
    elif args.comando == 'atual':
        dados = VersaoService.ObterVersaoAtual(id_sistema=args.sistema_id)
        print(f"Versão Atual (Sistema {dados['Id_Sistema']}): {dados['NumeroVersao']} - {dados['Estagio']}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    Executar()