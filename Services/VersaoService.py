from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.VersaoSistema import VersaoSistema
from sqlalchemy import desc
from datetime import datetime
import os

class VersaoService:

    @staticmethod
    def _ResolverIdSistema(id_sistema=None):
        if id_sistema is not None:
            return int(id_sistema)
        return int(os.getenv('SISTEMA_ID', 1))

    @staticmethod
    def _NormalizarNumeroVersao(numero):
        return str(numero or '').strip()

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
    def ObterVersaoAtual(id_sistema=None):
        """Retorna a versão mais recente registrada no banco para o sistema informado."""
        id_sistema_resolvido = VersaoService._ResolverIdSistema(id_sistema)
        with ObterSessaoSqlServer() as sessao:
            versao = (
                VersaoService._QueryVersoesSistema(sessao, id_sistema_resolvido)
                .order_by(desc(VersaoSistema.DataLancamento), desc(VersaoSistema.Id))
                .first()
            )
            if not versao:
                return {
                    "NumeroVersao": "0.0.0",
                    "Estagio": "Indefinido",
                    "DataLancamento": datetime.now(),
                    "Id_Sistema": id_sistema_resolvido
                }
            
            # Retornamos um dicionário para desacoplar da sessão do banco
            return {
                "Id_Sistema": versao.Id_Sistema,
                "NumeroVersao": versao.NumeroVersao,
                "Estagio": versao.Estagio,
                "DataLancamento": versao.DataLancamento,
                "NotasVersao": versao.NotasVersao
            }

    @staticmethod
    def RegistrarNovaVersao(numero, estagio, notas, responsavel, hash_commit=None, id_sistema=None):
        """Registra ou atualiza a versão informada para o sistema."""
        id_sistema_resolvido = VersaoService._ResolverIdSistema(id_sistema)
        numero_normalizado = VersaoService._NormalizarNumeroVersao(numero)

        if not numero_normalizado:
            raise ValueError('Número da versão não pode ser vazio.')

        with ObterSessaoSqlServer() as sessao:
            registros_existentes = VersaoService._ListarRegistrosDaVersao(sessao, id_sistema_resolvido, numero_normalizado)
            registro_principal = registros_existentes[0] if registros_existentes else None

            if registro_principal:
                registro_principal.Responsavel = responsavel
                registro_principal.NotasVersao = notas
                registro_principal.HashCommit = hash_commit
                registro_principal.DataLancamento = datetime.now()

                if not registro_principal.Estagio:
                    registro_principal.Estagio = estagio

                sessao.commit()
                print(
                    f"Versão {numero_normalizado} do sistema {id_sistema_resolvido} atualizada com sucesso. "
                    f"Estágio mantido em {registro_principal.Estagio}."
                )
                return

            nova_versao = VersaoSistema(
                Id_Sistema=id_sistema_resolvido,
                NumeroVersao=numero_normalizado,
                Estagio=estagio,
                NotasVersao=notas,
                Responsavel=responsavel,
                HashCommit=hash_commit,
                DataLancamento=datetime.now()
            )
            sessao.add(nova_versao)
            sessao.commit()
            print(f"Versão {numero_normalizado} ({estagio}) registrada com sucesso para o sistema {id_sistema_resolvido}.")

    @staticmethod
    def PromoverEstagio(novo_estagio, id_sistema=None, numero_versao=None):
        """Atualiza o estágio da versão lógica atual do sistema informado."""
        id_sistema_resolvido = VersaoService._ResolverIdSistema(id_sistema)
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
                print(
                    f"Nenhuma versão {numero_alvo} encontrada para promover no sistema {id_sistema_resolvido}."
                )
                return

            for registro in registros_alvo:
                registro.Estagio = novo_estagio

            sessao.commit()
            print(
                f"Versão {numero_alvo} do sistema {id_sistema_resolvido} promovida para {novo_estagio} "
                f"em {len(registros_alvo)} registro(s)."
            )