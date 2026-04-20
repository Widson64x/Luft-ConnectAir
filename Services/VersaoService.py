from datetime import datetime
import os
from pathlib import Path

from sqlalchemy import desc

from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.VersaoSistema import VersaoSistema

class VersaoService:
    ARQUIVO_VERSION = Path(__file__).resolve().parent.parent / 'VERSION'
    PADRAO_NUMERO = '0.0.0'
    PADRAO_ESTAGIO = 'Alpha'

    @staticmethod
    def _ResolverIdSistema(id_sistema=None):
        if id_sistema is not None:
            return int(id_sistema)
        return int(os.getenv('SISTEMA_ID', 1))

    @staticmethod
    def _NormalizarNumeroVersao(numero):
        return str(numero or '').strip()

    @staticmethod
    def _NormalizarEstagio(estagio):
        texto = str(estagio or '').strip()
        return texto or VersaoService.PADRAO_ESTAGIO

    @staticmethod
    def _ObterDadosVersaoPadrao(id_sistema):
        return {
            'NumeroVersao': VersaoService.PADRAO_NUMERO,
            'Estagio': VersaoService.PADRAO_ESTAGIO,
            'DataLancamento': datetime.now(),
            'Id_Sistema': id_sistema,
            'NotasVersao': None,
        }

    @staticmethod
    def _QueryVersoesSistema(sessao, id_sistema):
        return sessao.query(VersaoSistema).filter(VersaoSistema.Id_Sistema == id_sistema)

    @staticmethod
    def _ListarRegistrosDaVersao(sessao, id_sistema, numero_versao):
        numero_versao_normalizado = VersaoService._NormalizarNumeroVersao(numero_versao)
        return (
            VersaoService._QueryVersoesSistema(sessao, id_sistema)
            .filter(VersaoSistema.NumeroVersao == numero_versao_normalizado)
            .order_by(desc(VersaoSistema.DataLancamento), desc(VersaoSistema.Id))
            .all()
        )

    @staticmethod
    def LerVersaoArquivo():
        if not VersaoService.ARQUIVO_VERSION.exists():
            return {
                'NumeroVersao': VersaoService.PADRAO_NUMERO,
                'Estagio': VersaoService.PADRAO_ESTAGIO,
            }

        numero = None
        estagio = None
        linhas = VersaoService.ARQUIVO_VERSION.read_text(encoding='utf-8').splitlines()

        for linha in linhas:
            linha_limpa = linha.strip()
            if not linha_limpa or linha_limpa.startswith('#'):
                continue

            if '=' not in linha_limpa:
                if numero is None:
                    numero = linha_limpa
                continue

            chave, valor = linha_limpa.split('=', 1)
            chave_normalizada = chave.strip().upper()
            valor_normalizado = valor.strip()

            if chave_normalizada in {'NUMERO', 'VERSAO', 'NUMERO_VERSAO', 'NUMEROVERSAO'}:
                numero = valor_normalizado
            elif chave_normalizada in {'ESTAGIO', 'STAGE', 'TIPO'}:
                estagio = valor_normalizado

        return {
            'NumeroVersao': VersaoService._NormalizarNumeroVersao(numero) or VersaoService.PADRAO_NUMERO,
            'Estagio': VersaoService._NormalizarEstagio(estagio),
        }

    @staticmethod
    def AtualizarArquivoVersao(numero=None, estagio=None):
        dados_atuais = VersaoService.LerVersaoArquivo()
        numero_final = VersaoService._NormalizarNumeroVersao(numero) or dados_atuais['NumeroVersao'] or VersaoService.PADRAO_NUMERO
        estagio_final = VersaoService._NormalizarEstagio(estagio or dados_atuais['Estagio'])

        conteudo = f'NUMERO={numero_final}\nESTAGIO={estagio_final}\n'
        VersaoService.ARQUIVO_VERSION.write_text(conteudo, encoding='utf-8')

        return {
            'NumeroVersao': numero_final,
            'Estagio': estagio_final,
        }
    
    @staticmethod
    def ObterVersaoAtual(id_sistema=None):
        """Retorna a versão atual do sistema, priorizando o arquivo VERSION."""
        id_sistema_resolvido = VersaoService._ResolverIdSistema(id_sistema)
        dados_arquivo = VersaoService.LerVersaoArquivo()

        with ObterSessaoSqlServer() as sessao:
            if (
                dados_arquivo['NumeroVersao'] != VersaoService.PADRAO_NUMERO
                or dados_arquivo['Estagio'] != VersaoService.PADRAO_ESTAGIO
            ):
                versao_arquivo = (
                    VersaoService._QueryVersoesSistema(sessao, id_sistema_resolvido)
                    .filter(VersaoSistema.NumeroVersao == dados_arquivo['NumeroVersao'])
                    .order_by(desc(VersaoSistema.DataLancamento), desc(VersaoSistema.Id))
                    .first()
                )

                if versao_arquivo:
                    return {
                        'Id_Sistema': versao_arquivo.Id_Sistema,
                        'NumeroVersao': dados_arquivo['NumeroVersao'],
                        'Estagio': dados_arquivo['Estagio'],
                        'DataLancamento': versao_arquivo.DataLancamento,
                        'NotasVersao': versao_arquivo.NotasVersao,
                    }

                return {
                    'Id_Sistema': id_sistema_resolvido,
                    'NumeroVersao': dados_arquivo['NumeroVersao'],
                    'Estagio': dados_arquivo['Estagio'],
                    'DataLancamento': datetime.now(),
                    'NotasVersao': None,
                }

            versao = (
                VersaoService._QueryVersoesSistema(sessao, id_sistema_resolvido)
                .order_by(desc(VersaoSistema.DataLancamento), desc(VersaoSistema.Id))
                .first()
            )
            if not versao:
                return VersaoService._ObterDadosVersaoPadrao(id_sistema_resolvido)
            
            return {
                'Id_Sistema': versao.Id_Sistema,
                'NumeroVersao': versao.NumeroVersao,
                'Estagio': versao.Estagio,
                'DataLancamento': versao.DataLancamento,
                'NotasVersao': versao.NotasVersao,
            }

    @staticmethod
    def RegistrarNovaVersao(numero, estagio, notas, responsavel, hash_commit=None, id_sistema=None):
        """Registra ou atualiza a versão informada para o sistema."""
        id_sistema_resolvido = VersaoService._ResolverIdSistema(id_sistema)
        numero_normalizado = VersaoService._NormalizarNumeroVersao(numero)
        estagio_normalizado = VersaoService._NormalizarEstagio(estagio)

        if not numero_normalizado:
            raise ValueError('Número da versão não pode ser vazio.')

        with ObterSessaoSqlServer() as sessao:
            registros_existentes = VersaoService._ListarRegistrosDaVersao(sessao, id_sistema_resolvido, numero_normalizado)
            registro_principal = registros_existentes[0] if registros_existentes else None

            if registro_principal:
                registro_principal.NumeroVersao = numero_normalizado
                registro_principal.Estagio = estagio_normalizado
                registro_principal.Responsavel = responsavel
                registro_principal.NotasVersao = notas
                registro_principal.HashCommit = hash_commit
                registro_principal.DataLancamento = datetime.now()

                sessao.commit()
                print(
                    f"Versão {numero_normalizado} do sistema {id_sistema_resolvido} atualizada com sucesso. "
                    f"Estágio sincronizado para {registro_principal.Estagio}."
                )
                return {
                    'Id_Sistema': registro_principal.Id_Sistema,
                    'NumeroVersao': registro_principal.NumeroVersao,
                    'Estagio': registro_principal.Estagio,
                    'DataLancamento': registro_principal.DataLancamento,
                    'NotasVersao': registro_principal.NotasVersao,
                }

            nova_versao = VersaoSistema(
                Id_Sistema=id_sistema_resolvido,
                NumeroVersao=numero_normalizado,
                Estagio=estagio_normalizado,
                NotasVersao=notas,
                Responsavel=responsavel,
                HashCommit=hash_commit,
                DataLancamento=datetime.now()
            )
            sessao.add(nova_versao)
            sessao.commit()
            print(f"Versão {numero_normalizado} ({estagio_normalizado}) registrada com sucesso para o sistema {id_sistema_resolvido}.")
            return {
                'Id_Sistema': nova_versao.Id_Sistema,
                'NumeroVersao': nova_versao.NumeroVersao,
                'Estagio': nova_versao.Estagio,
                'DataLancamento': nova_versao.DataLancamento,
                'NotasVersao': nova_versao.NotasVersao,
            }

    @staticmethod
    def SincronizarVersaoArquivo(notas=None, responsavel='Sistema', hash_commit=None, id_sistema=None):
        if not VersaoService.ARQUIVO_VERSION.exists():
            raise FileNotFoundError(f'Arquivo VERSION não encontrado em {VersaoService.ARQUIVO_VERSION}.')

        dados_arquivo = VersaoService.LerVersaoArquivo()
        notas_finais = notas or f"Sincronização do arquivo VERSION ({dados_arquivo['NumeroVersao']} - {dados_arquivo['Estagio']})"
        return VersaoService.RegistrarNovaVersao(
            dados_arquivo['NumeroVersao'],
            dados_arquivo['Estagio'],
            notas_finais,
            responsavel,
            hash_commit=hash_commit,
            id_sistema=id_sistema,
        )

    @staticmethod
    def PromoverEstagio(novo_estagio, id_sistema=None, numero_versao=None):
        """Atualiza o estágio da versão lógica atual do sistema informado."""
        id_sistema_resolvido = VersaoService._ResolverIdSistema(id_sistema)
        estagio_normalizado = VersaoService._NormalizarEstagio(novo_estagio)
        with ObterSessaoSqlServer() as sessao:
            numero_alvo = VersaoService._NormalizarNumeroVersao(numero_versao)

            if not numero_alvo:
                ultima_versao = (
                    VersaoService._QueryVersoesSistema(sessao, id_sistema_resolvido)
                    .order_by(desc(VersaoSistema.DataLancamento), desc(VersaoSistema.Id))
                    .first()
                )

                if not ultima_versao:
                    print(f"Nenhuma versão encontrada para promover no sistema {id_sistema_resolvido}.")
                    return

                numero_alvo = ultima_versao.NumeroVersao

            registros_alvo = VersaoService._ListarRegistrosDaVersao(sessao, id_sistema_resolvido, numero_alvo)
            if not registros_alvo:
                return VersaoService.RegistrarNovaVersao(
                    numero_alvo,
                    estagio_normalizado,
                    f'Promoção manual para {estagio_normalizado}',
                    'Sistema',
                    id_sistema=id_sistema_resolvido,
                )

            for registro in registros_alvo:
                registro.Estagio = estagio_normalizado

            sessao.commit()
            print(
                f"Versão {numero_alvo} do sistema {id_sistema_resolvido} promovida para {estagio_normalizado} "
                f"em {len(registros_alvo)} registro(s)."
            )
            return {
                'Id_Sistema': id_sistema_resolvido,
                'NumeroVersao': numero_alvo,
                'Estagio': estagio_normalizado,
                'DataLancamento': registros_alvo[0].DataLancamento,
                'NotasVersao': registros_alvo[0].NotasVersao,
            }