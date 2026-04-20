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
    def ObterVersaoAtual(id_sistema=None):
        """Retorna a versão mais recente registrada no banco para o sistema informado."""
        id_sistema_resolvido = VersaoService._ResolverIdSistema(id_sistema)
        with ObterSessaoSqlServer() as sessao:
            versao = (
                sessao.query(VersaoSistema)
                .filter(VersaoSistema.Id_Sistema == id_sistema_resolvido)
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
        """Cria um novo registro de versão para o sistema informado."""
        id_sistema_resolvido = VersaoService._ResolverIdSistema(id_sistema)
        with ObterSessaoSqlServer() as sessao:
            nova_versao = VersaoSistema(
                Id_Sistema=id_sistema_resolvido,
                NumeroVersao=numero,
                Estagio=estagio,
                NotasVersao=notas,
                Responsavel=responsavel,
                HashCommit=hash_commit,
                DataLancamento=datetime.now()
            )
            sessao.add(nova_versao)
            sessao.commit()
            print(f"Versão {numero} ({estagio}) registrada com sucesso para o sistema {id_sistema_resolvido}.")

    @staticmethod
    def PromoverEstagio(novo_estagio, id_sistema=None):
        """Atualiza o estágio da versão atual do sistema informado (Ex: Alpha -> Beta)."""
        id_sistema_resolvido = VersaoService._ResolverIdSistema(id_sistema)
        with ObterSessaoSqlServer() as sessao:
            ultima_versao = (
                sessao.query(VersaoSistema)
                .filter(VersaoSistema.Id_Sistema == id_sistema_resolvido)
                .order_by(desc(VersaoSistema.DataLancamento), desc(VersaoSistema.Id))
                .first()
            )
            
            if ultima_versao:
                ultima_versao.Estagio = novo_estagio
                sessao.commit()
                print(f"Versão {ultima_versao.NumeroVersao} do sistema {id_sistema_resolvido} promovida para {novo_estagio}.")
            else:
                print(f"Nenhuma versão encontrada para promover no sistema {id_sistema_resolvido}.")