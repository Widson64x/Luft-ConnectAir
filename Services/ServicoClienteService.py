from sqlalchemy.orm import Session
from sqlalchemy import and_
from Conexoes import ObterSessaoSqlServer 
from Models.SQL_SERVER.Cadastros import Cliente, ClienteGrupo, ClienteServicoContratado
from Models.SQL_SERVER.ServicoCliente import ServicoCliente

class ServicoClienteService:

    @staticmethod
    def ObterClientesParaSelecao():
        """Retorna clientes ativos, aplicando os filtros da query SQL e removendo duplicatas"""
        Db: Session = ObterSessaoSqlServer()
        try:
            ListaClientes = Db.query(
                Cliente.Codigo_Cliente,
                Cliente.CNPJ_Cliente,
                Cliente.Nome_RazaoSocialCliente,
                Cliente.Nome_FantasiaCliente,
                ClienteGrupo.Descricao_ClienteGrupo.label('Grupo')
            ).outerjoin( # <--- MUDANÇA AQUI: outerjoin para trazer clientes sem grupo
                ClienteGrupo, Cliente.Codigo_ClienteGrupo == ClienteGrupo.Codigo_ClienteGrupo
            ).join(
                ClienteServicoContratado, Cliente.Codigo_Cliente == ClienteServicoContratado.Codigo_Cliente # Esse continua JOIN normal pois só queremos quem tem serviço contratado
            ).filter(
                and_(
                    Cliente.CNPJ_Cliente.isnot(None), # Filtro para remover clientes sem CNPJ
                    Cliente.CNPJ_Cliente.notlike('04.019.475%'), # Filtro para remover clientes com CNPJ específico
                    # ClienteServicoContratado.Data_FimOperacao.is_(None), # Data de fim nula indica serviço ativo
                    ClienteServicoContratado.Opcao_ServicoContratado == 't' # Filtro de ativo da query
                )
            ).order_by(Cliente.Nome_RazaoSocialCliente).all()

            Retorno = []
            CodigosVistos = set() # <-- Criamos um Set para controlar quem já entrou na lista

            for Cli in ListaClientes:
                # Só adiciona o cliente na lista se o Código dele ainda não foi visto
                if Cli.Codigo_Cliente not in CodigosVistos:
                    
                    # Prevenção extra para o Frontend: se o Grupo vier nulo do banco, forçamos um nome padrão
                    NomeGrupo = Cli.Grupo if Cli.Grupo else 'Z_Sem Grupo' # Coloquei o 'Z_' para ele ir pro final da lista em ordem alfabética

                    Retorno.append({
                        "CodigoCliente": Cli.Codigo_Cliente,
                        "Cnpj": Cli.CNPJ_Cliente,
                        "RazaoSocial": Cli.Nome_RazaoSocialCliente,
                        "Fantasia": Cli.Nome_FantasiaCliente,
                        "Grupo": NomeGrupo # <-- Usa a variável tratada
                    })
                    CodigosVistos.add(Cli.Codigo_Cliente) # Marca este código como visto
                    
            return Retorno
        finally:
            Db.close()

    @staticmethod
    def ObterDadosCliente(CodigoCliente):
        """Retorna os dados de um cliente específico, caso precise exibir na tela de edição"""
        Db: Session = ObterSessaoSqlServer()
        try:
            ClienteEncontrado = Db.query(
                Cliente.Codigo_Cliente,
                Cliente.CNPJ_Cliente,
                Cliente.Nome_RazaoSocialCliente,
                Cliente.Nome_FantasiaCliente,
                ClienteGrupo.Descricao_ClienteGrupo.label('Grupo')
            ).join(
                ClienteGrupo, Cliente.Codigo_ClienteGrupo == ClienteGrupo.Codigo_ClienteGrupo
            ).filter(
                Cliente.Codigo_Cliente == CodigoCliente
            ).first()

            if not ClienteEncontrado:
                return None

            return {
                "CodigoCliente": ClienteEncontrado.Codigo_Cliente,
                "Cnpj": ClienteEncontrado.CNPJ_Cliente,
                "RazaoSocial": ClienteEncontrado.Nome_RazaoSocialCliente,
                "Fantasia": ClienteEncontrado.Nome_FantasiaCliente,
                "Grupo": ClienteEncontrado.Grupo
            }
        finally:
            Db.close()

    @staticmethod
    def ListarServicosContratados():
        """Retorna a lista de serviços contratados fazendo JOIN com os dados do cliente e seu GRUPO"""
        Db: Session = ObterSessaoSqlServer()
        try:
            # Traz o Servico, o Cliente, e o ClienteGrupo
            Lista = Db.query(ServicoCliente, Cliente, ClienteGrupo).outerjoin(
                Cliente, ServicoCliente.CodigoCliente == Cliente.Codigo_Cliente
            ).outerjoin(
                ClienteGrupo, Cliente.Codigo_ClienteGrupo == ClienteGrupo.Codigo_ClienteGrupo
            ).all()
            
            return Lista
        finally:
            Db.close()

    @staticmethod
    def CadastrarNovoServico(DadosRecebidos, UsuarioLogado):
        """Salva a parametrização juntando dados do formulário com dados automáticos do banco"""
        Db: Session = ObterSessaoSqlServer()
        try:
            CodigoCliente = DadosRecebidos.get('CodigoCliente')

            # 1. Busca as informações automáticas (Tipo de Operação/Armazenagem) da base legado
            ServicoLegado = Db.query(ClienteServicoContratado).filter(
                ClienteServicoContratado.Codigo_Cliente == CodigoCliente,
                ClienteServicoContratado.Data_FimOperacao.is_(None)
            ).first()

            TipoOperacaoCalculado = ""
            TipoArmazenagemCalculado = ""

            # Simulando os "CASE WHEN" da sua query
            if ServicoLegado:
                TipoOperacaoCalculado = 'Transporte' if ServicoLegado.Opcao_ServicoContratado == 't' else 'Armazenagem'
                
                if ServicoLegado.Opcao_TipoArmazenagem == 'FL':
                    TipoArmazenagemCalculado = 'Filial'
                elif ServicoLegado.Opcao_TipoArmazenagem == 'DP':
                    TipoArmazenagemCalculado = 'Depósito'
                elif ServicoLegado.Opcao_TipoArmazenagem == 'AG':
                    TipoArmazenagemCalculado = 'Armazém Geral'

            # 2. Cria o registro mesclando o Form + Dados Automáticos
            NovoServico = ServicoCliente(
                CodigoCliente=CodigoCliente,
                DurabilidadeGelo=DadosRecebidos.get('DurabilidadeGelo'),
                AutorizacaoTrocaGelo=DadosRecebidos.get('AutorizacaoTrocaGelo'),
                AutorizacaoArmazenagem=DadosRecebidos.get('AutorizacaoArmazenagem'),
                ServicoContratado=DadosRecebidos.get('ServicoContratado'),
                TipoOperacao=TipoOperacaoCalculado,       # Automático!
                TipoArmazenagem=TipoArmazenagemCalculado, # Automático!
                UsuarioResponsavel=UsuarioLogado
            )
            
            Db.add(NovoServico)
            Db.commit()
            return {"Sucesso": True, "Mensagem": "Parâmetros de serviço cadastrados com sucesso!"}
        except Exception as Ex:
            Db.rollback()
            return {"Sucesso": False, "Mensagem": f"Erro no banco: {str(Ex)}"}
        finally:
            Db.close()

    @staticmethod
    def EditarServico(IdServico, DadosRecebidos, UsuarioLogado):
        """Edita um serviço existente, atualizando os campos e registrando o usuário responsável pela alteração"""
        Db: Session = ObterSessaoSqlServer()
        try:
            ServicoExistente = Db.query(ServicoCliente).filter(ServicoCliente.Id == IdServico).first()
            if not ServicoExistente:
                return {"Sucesso": False, "Mensagem": "Serviço não encontrado"}

            # Atualiza os campos do serviço com os novos dados
            ServicoExistente.DurabilidadeGelo = DadosRecebidos.get('DurabilidadeGelo', ServicoExistente.DurabilidadeGelo)
            ServicoExistente.AutorizacaoTrocaGelo = DadosRecebidos.get('AutorizacaoTrocaGelo', ServicoExistente.AutorizacaoTrocaGelo)
            ServicoExistente.AutorizacaoArmazenagem = DadosRecebidos.get('AutorizacaoArmazenagem', ServicoExistente.AutorizacaoArmazenagem)
            ServicoExistente.ServicoContratado = DadosRecebidos.get('ServicoContratado', ServicoExistente.ServicoContratado)
            ServicoExistente.UsuarioResponsavel = UsuarioLogado  # Atualiza o usuário responsável pela última alteração

            Db.commit()
            return {"Sucesso": True, "Mensagem": "Parâmetros de serviço atualizados com sucesso!"}
        except Exception as Ex:
            Db.rollback()
            return {"Sucesso": False, "Mensagem": f"Erro no banco: {str(Ex)}"}
        finally:
            Db.close()

    @staticmethod
    def ExcluirServico(IdServico, UsuarioLogado):
        """Exclui um serviço existente, registrando o usuário responsável pela exclusão"""
        Db: Session = ObterSessaoSqlServer()
        try:
            ServicoExistente = Db.query(ServicoCliente).filter(ServicoCliente.Id == IdServico).first()
            if not ServicoExistente:
                return {"Sucesso": False, "Mensagem": "Serviço não encontrado"}

            Db.delete(ServicoExistente)
            Db.commit()
            return {"Sucesso": True, "Mensagem": "Parâmetros de serviço excluídos com sucesso!"}
        except Exception as Ex:
            Db.rollback()
            return {"Sucesso": False, "Mensagem": f"Erro no banco: {str(Ex)}"}
        finally:
            Db.close()