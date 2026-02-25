from sqlalchemy import text, func
from datetime import datetime
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Cortes import CortePlanejamento, CorteEmissao
from Models.SQL_SERVER.Filial import Filial
from Services.LogService import LogService

class CorteService:
    
    @staticmethod
    def ListarFiliais():
        sessao = ObterSessaoSqlServer()
        try:
            filiais = sessao.query(Filial).filter(Filial.filial != None).order_by(Filial.filial).all()
            lista = [{'id': f.id, 'codigo': f.filial, 'nome': f.nomefilial, 'uf': f.uf} for f in filiais]
            
            # Adiciona a opção "Todas" no início da lista
            lista.insert(0, {'id': 0, 'codigo': 'TODAS', 'nome': 'TODAS AS FILIAIS', 'uf': '*'})
            
            return lista
        except Exception as e:
            LogService.Error("CorteService", "Erro ao listar filiais", e)
            return []
        finally:
            sessao.close()

    @staticmethod
    def ListarCortesPlanejamento(filial_filtro=None):
        sessao = ObterSessaoSqlServer()
        try:
            query = sessao.query(CortePlanejamento).filter(CortePlanejamento.Ativo == True)
            if filial_filtro:
                query = query.filter(CortePlanejamento.Filial == filial_filtro)
            
            # Ordena pela Filial e depois pelo número sequencial do Corte (1, 2, 3...)
            resultados = query.order_by(CortePlanejamento.Filial, CortePlanejamento.Corte).all()
            
            lista = []
            for item in resultados:
                # Monta a descrição visual (ex: "1º - Rota Norte")
                desc_visual = f"{item.Corte}º - {item.Descricao}" if item.Corte else item.Descricao

                lista.append({
                    'id': item.IdCortePln,
                    'filial': item.Filial,
                    'descricao': desc_visual, 
                    'descricao_pura': item.Descricao, # Para preencher o input no modal de edição
                    'corte_seq': item.Corte,
                    'horario': item.HorarioCorte.strftime('%H:%M') if item.HorarioCorte else '',
                    'ativo': item.Ativo,
                    'criado_por': item.UsuarioCriacao,
                    'alterado_por': item.UsuarioAlteracao
                })
            return lista
        except Exception as e:
            LogService.Error("CorteService", "Erro ao listar Cortes Planejamento", e)
            return []
        finally:
            sessao.close()

    @staticmethod
    def ListarCortesEmissao(filial_filtro=None):
        sessao = ObterSessaoSqlServer()
        try:
            query = sessao.query(CorteEmissao).filter(CorteEmissao.Ativo == True)
            if filial_filtro:
                query = query.filter(CorteEmissao.Filial == filial_filtro)
            
            resultados = query.order_by(CorteEmissao.Filial, CorteEmissao.HorarioLimite).all()
            
            lista = []
            for item in resultados:
                lista.append({
                    'id': item.IdCorteEmi,
                    'filial': item.Filial,
                    'descricao': item.Descricao,
                    'horario': item.HorarioLimite.strftime('%H:%M') if item.HorarioLimite else '',
                    'ativo': item.Ativo,
                    'criado_por': item.UsuarioCriacao
                })
            return lista
        except Exception as e:
            LogService.Error("CorteService", "Erro ao listar Cortes Emissão", e)
            return []
        finally:
            sessao.close()

    @staticmethod
    def _GerarSequenciaCorte(sessao, filial_str):
        """
        Gera o próximo número de corte para uma filial específica.
        """
        # Usando text() para FORÇAR a busca na coluna de texto 'Filial',
        # impedindo que o ORM converta a busca para o 'CodFilial' sem querermos.
        max_corte = sessao.query(func.max(CortePlanejamento.Corte))\
            .filter(text("Filial = :filial"), CortePlanejamento.Ativo == True)\
            .params(filial=filial_str)\
            .scalar()
        
        return (max_corte or 0) + 1

    @staticmethod
    def SalvarCortePlanejamento(dados, usuario_responsavel):
        sessao = ObterSessaoSqlServer()
        try:
            id_corte = dados.get('id')
            cod_filial_str = dados.get('filial')
            descricao = dados.get('descricao')
            horario_str = dados.get('horario')
            horario_obj = datetime.strptime(horario_str, '%H:%M').time()

            # Identifica se é para todas as filiais (Apenas na criação)
            if cod_filial_str == 'TODAS' and not id_corte:
                filiais_processar = sessao.query(Filial).filter(Filial.filial != None).all()
            else:
                filial_obj = sessao.query(Filial).filter(Filial.filial == cod_filial_str).first()
                if not filial_obj: raise Exception("Filial não encontrada")
                filiais_processar = [filial_obj]

            # Dicionário para rastrear os cortes em memória. Muito mais rápido e evita bug de insert em lote!
            sequencias_memoria = {}

            for f in filiais_processar:
                if id_corte:
                    # --- EDIÇÃO ---
                    entidade = sessao.query(CortePlanejamento).get(id_corte)
                    if not entidade: continue
                    entidade.UsuarioAlteracao = usuario_responsavel
                    entidade.DataAlteracao = datetime.now()
                else:
                    # --- CRIAÇÃO ---
                    entidade = CortePlanejamento()
                    
                    # Checa o dicionário primeiro: se a filial não está lá, busca no banco. Se está, apenas soma +1.
                    if f.filial not in sequencias_memoria:
                        sequencias_memoria[f.filial] = CorteService._GerarSequenciaCorte(sessao, f.filial)
                    else:
                        sequencias_memoria[f.filial] += 1
                        
                    entidade.Corte = sequencias_memoria[f.filial]
                    
                    entidade.UsuarioCriacao = usuario_responsavel
                    entidade.DataCriacao = datetime.now()
                    sessao.add(entidade)

                entidade.Filial = f.filial
                entidade.CodFilial = f.codfilial
                entidade.Descricao = descricao
                entidade.HorarioCorte = horario_obj
                entidade.Ativo = True

            sessao.commit()
            return True, "Salvo com sucesso"
        except Exception as e:
            sessao.rollback()
            LogService.Error("CorteService", "Erro ao salvar Corte Planejamento", e)
            return False, str(e)
        finally:
            sessao.close()

    @staticmethod
    def SalvarCorteEmissao(dados, usuario_responsavel):
        sessao = ObterSessaoSqlServer()
        try:
            id_corte = dados.get('id')
            cod_filial_str = dados.get('filial')
            horario_str = dados.get('horario')
            descricao = dados.get('descricao')
            horario_obj = datetime.strptime(horario_str, '%H:%M').time()

            if cod_filial_str == 'TODAS' and not id_corte:
                filiais_processar = sessao.query(Filial).filter(Filial.filial != None).all()
            else:
                filial_obj = sessao.query(Filial).filter(Filial.filial == cod_filial_str).first()
                if not filial_obj: raise Exception("Filial não encontrada")
                filiais_processar = [filial_obj]

            for f in filiais_processar:
                if id_corte:
                    entidade = sessao.query(CorteEmissao).get(id_corte)
                    if not entidade: continue
                    entidade.UsuarioAlteracao = usuario_responsavel
                    entidade.DataAlteracao = datetime.now()
                else:
                    entidade = CorteEmissao()
                    entidade.UsuarioCriacao = usuario_responsavel
                    entidade.DataCriacao = datetime.now()
                    sessao.add(entidade)

                entidade.Filial = f.filial
                entidade.CodFilial = f.codfilial
                entidade.HorarioLimite = horario_obj
                entidade.Descricao = descricao
                entidade.Ativo = True

            sessao.commit()
            return True, "Salvo com sucesso"
        except Exception as e:
            sessao.rollback()
            LogService.Error("CorteService", "Erro ao salvar Corte Emissão", e)
            return False, str(e)
        finally:
            sessao.close()

    @staticmethod
    def ExcluirCorte(tipo, id_corte, usuario_responsavel=None):
        # Opcional: Se quiser registrar quem excluiu, precisaria de uma coluna "UsuarioExclusao" ou usar o "UsuarioAlteracao"
        sessao = ObterSessaoSqlServer()
        try:
            if tipo == 'planejamento':
                entidade = sessao.query(CortePlanejamento).get(id_corte)
            else:
                entidade = sessao.query(CorteEmissao).get(id_corte)
            
            if entidade:
                entidade.Ativo = False
                if usuario_responsavel:
                    entidade.UsuarioAlteracao = usuario_responsavel
                    entidade.DataAlteracao = datetime.now()
                
                sessao.commit()
            return True
        except Exception as e:
            sessao.rollback()
            LogService.Error("CorteService", f"Erro ao excluir {tipo}", e)
            return False
        finally:
            sessao.close()