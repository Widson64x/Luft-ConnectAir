from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.VersaoSistema import VersaoSistema
from sqlalchemy import desc
from datetime import datetime

class VersaoService:
    
    @staticmethod
    def ObterVersaoAtual():
        """Retorna a versão mais recente registrada no banco."""
        with ObterSessaoSqlServer() as sessao:
            versao = sessao.query(VersaoSistema).order_by(desc(VersaoSistema.DataLancamento)).first()
            if not versao:
                return {
                    "NumeroVersao": "0.0.0",
                    "Estagio": "Indefinido",
                    "DataLancamento": datetime.now()
                }
            
            # Retornamos um dicionário para desacoplar da sessão do banco
            return {
                "NumeroVersao": versao.NumeroVersao,
                "Estagio": versao.Estagio,
                "DataLancamento": versao.DataLancamento,
                "NotasVersao": versao.NotasVersao
            }

    @staticmethod
    def RegistrarNovaVersao(numero, estagio, notas, responsavel, hash_commit=None):
        """Cria um novo registro de versão (Usado no Merge)."""
        with ObterSessaoSqlServer() as sessao:
            nova_versao = VersaoSistema(
                NumeroVersao=numero,
                Estagio=estagio,
                NotasVersao=notas,
                Responsavel=responsavel,
                HashCommit=hash_commit,
                DataLancamento=datetime.now()
            )
            sessao.add(nova_versao)
            sessao.commit()
            print(f"Versão {numero} ({estagio}) registrada com sucesso.")

    @staticmethod
    def PromoverEstagio(novo_estagio):
        """Atualiza o estágio da versão atual (Ex: Alpha -> Beta)."""
        with ObterSessaoSqlServer() as sessao:
            ultima_versao = sessao.query(VersaoSistema).order_by(desc(VersaoSistema.DataLancamento)).first()
            
            if ultima_versao:
                ultima_versao.Estagio = novo_estagio
                sessao.commit()
                print(f"Versão {ultima_versao.NumeroVersao} promovida para {novo_estagio}.")
            else:
                print("Nenhuma versão encontrada para promover.")