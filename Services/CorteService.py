from sqlalchemy import text, func
from datetime import datetime
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Cortes import CortePlanejamento, CorteEmissao
from Models.SQL_SERVER.Filial import Filial
from Services.LogService import LogService

class CorteService:
    
    @staticmethod
    def ListarFiliaisAgrupadas():
        sessao = ObterSessaoSqlServer()
        try:
            filiais = sessao.query(Filial).filter(Filial.filial != None).order_by(Filial.uf, Filial.filial).all()
            arvore = {}
            for f in filiais:
                uf = str(f.uf).strip().upper() if f.uf else 'OUTROS'
                if uf not in arvore: arvore[uf] = []
                arvore[uf].append({'id': f.id, 'codigo': f.filial, 'nome': f.nomefilial, 'uf': f.uf})
            return arvore
        except Exception as e:
            LogService.Error("CorteService", "Erro ao listar filiais arvore", e)
            return {}
        finally:
            sessao.close()

    @staticmethod
    def ListarCortesPlanejamentoAgrupado(filial_filtro=None):
        sessao = ObterSessaoSqlServer()
        try:
            query = sessao.query(CortePlanejamento, Filial.uf).outerjoin(
                Filial, CortePlanejamento.CodFilial == Filial.codfilial
            ).filter(CortePlanejamento.Ativo == True)
            
            if filial_filtro:
                query = query.filter(CortePlanejamento.Filial == filial_filtro)
            
            resultados = query.order_by(Filial.uf, CortePlanejamento.Filial, CortePlanejamento.Corte).all()
            
            arvore = {}
            for item, uf in resultados:
                uf_key = str(uf).strip().upper() if uf else 'OUTROS'
                filial_key = item.Filial
                if uf_key not in arvore: arvore[uf_key] = {}
                if filial_key not in arvore[uf_key]: arvore[uf_key][filial_key] = []
                
                desc_visual = f"{item.Corte}º - {item.Descricao}" if item.Corte else item.Descricao
                arvore[uf_key][filial_key].append({
                    'id': item.IdCortePln, 'filial': item.Filial,
                    'descricao': desc_visual, 'descricao_pura': item.Descricao,
                    'corte_seq': item.Corte, 'horario': item.HorarioCorte.strftime('%H:%M') if item.HorarioCorte else '',
                })
            return arvore
        except Exception as e: return {}
        finally: sessao.close()

    @staticmethod
    def ListarCortesEmissaoAgrupado(filial_filtro=None):
        sessao = ObterSessaoSqlServer()
        try:
            query = sessao.query(CorteEmissao, Filial.uf).outerjoin(
                Filial, CorteEmissao.CodFilial == Filial.codfilial
            ).filter(CorteEmissao.Ativo == True)
            
            if filial_filtro: query = query.filter(CorteEmissao.Filial == filial_filtro)
            
            resultados = query.order_by(Filial.uf, CorteEmissao.Filial, CorteEmissao.HorarioLimite).all()
            arvore = {}
            for item, uf in resultados:
                uf_key = str(uf).strip().upper() if uf else 'OUTROS'
                filial_key = item.Filial
                if uf_key not in arvore: arvore[uf_key] = {}
                if filial_key not in arvore[uf_key]: arvore[uf_key][filial_key] = []
                
                arvore[uf_key][filial_key].append({
                    'id': item.IdCorteEmi, 'filial': item.Filial,
                    'descricao': item.Descricao, 'horario': item.HorarioLimite.strftime('%H:%M') if item.HorarioLimite else '',
                })
            return arvore
        except Exception as e: return {}
        finally: sessao.close()

    @staticmethod
    def _GerarSequenciaCorte(sessao, filial_str):
        max_corte = sessao.query(func.max(CortePlanejamento.Corte)).filter(text("Filial = :filial"), CortePlanejamento.Ativo == True).params(filial=filial_str).scalar()
        return (max_corte or 0) + 1

    @staticmethod
    def SalvarCortePlanejamento(dados, usuario_responsavel):
        sessao = ObterSessaoSqlServer()
        try:
            ids_edicao = dados.get('ids', []) 
            lista_filiais = dados.get('filiais', []) 
            descricao = dados.get('descricao')
            horario_str = dados.get('horario')
            horario_obj = datetime.strptime(horario_str, '%H:%M').time() if horario_str else None

            if ids_edicao and len(ids_edicao) > 0:
                # --- EDIÇÃO EM MASSA (Baseada nos IDs selecionados na tabela) ---
                for id_corte in ids_edicao:
                    entidade = sessao.query(CortePlanejamento).get(id_corte)
                    if entidade:
                        if descricao: entidade.Descricao = descricao
                        if horario_obj: entidade.HorarioCorte = horario_obj
                        entidade.UsuarioAlteracao = usuario_responsavel
                        entidade.DataAlteracao = datetime.now()
            else:
                # --- CRIAÇÃO EM MASSA (Baseada nos Checkboxes do Modal) ---
                if not lista_filiais: raise Exception("Nenhuma filial selecionada.")
                sequencias_memoria = {}
                for cod_filial in lista_filiais:
                    f = sessao.query(Filial).filter(Filial.filial == cod_filial).first()
                    if not f: continue
                    
                    entidade = CortePlanejamento()
                    if f.filial not in sequencias_memoria:
                        sequencias_memoria[f.filial] = CorteService._GerarSequenciaCorte(sessao, f.filial)
                    else:
                        sequencias_memoria[f.filial] += 1
                        
                    entidade.Corte = sequencias_memoria[f.filial]
                    entidade.UsuarioCriacao = usuario_responsavel
                    entidade.DataCriacao = datetime.now()
                    entidade.Filial = f.filial
                    entidade.CodFilial = f.codfilial
                    entidade.Descricao = descricao
                    entidade.HorarioCorte = horario_obj
                    entidade.Ativo = True
                    sessao.add(entidade)

            sessao.commit()
            return True, "Operação realizada com sucesso!"
        except Exception as e:
            sessao.rollback()
            return False, str(e)
        finally:
            sessao.close()

    @staticmethod
    def SalvarCorteEmissao(dados, usuario_responsavel):
        sessao = ObterSessaoSqlServer()
        try:
            ids_edicao = dados.get('ids', [])
            lista_filiais = dados.get('filiais', [])
            horario_str = dados.get('horario')
            descricao = dados.get('descricao')
            horario_obj = datetime.strptime(horario_str, '%H:%M').time() if horario_str else None

            if ids_edicao and len(ids_edicao) > 0:
                for id_corte in ids_edicao:
                    entidade = sessao.query(CorteEmissao).get(id_corte)
                    if entidade:
                        if descricao: entidade.Descricao = descricao
                        if horario_obj: entidade.HorarioLimite = horario_obj
                        entidade.UsuarioAlteracao = usuario_responsavel
                        entidade.DataAlteracao = datetime.now()
            else:
                if not lista_filiais: raise Exception("Nenhuma filial selecionada.")
                for cod_filial in lista_filiais:
                    f = sessao.query(Filial).filter(Filial.filial == cod_filial).first()
                    if not f: continue
                    
                    entidade = CorteEmissao()
                    entidade.UsuarioCriacao = usuario_responsavel
                    entidade.DataCriacao = datetime.now()
                    entidade.Filial = f.filial
                    entidade.CodFilial = f.codfilial
                    entidade.HorarioLimite = horario_obj
                    entidade.Descricao = descricao
                    entidade.Ativo = True
                    sessao.add(entidade)

            sessao.commit()
            return True, "Operação realizada com sucesso!"
        except Exception as e:
            sessao.rollback()
            return False, str(e)
        finally:
            sessao.close()

    @staticmethod
    def ExcluirCortesEmMassa(tipo, ids, usuario_responsavel=None):
        sessao = ObterSessaoSqlServer()
        try:
            Classe = CortePlanejamento if tipo == 'planejamento' else CorteEmissao
            for id_corte in ids:
                entidade = sessao.query(Classe).get(id_corte)
                if entidade:
                    entidade.Ativo = False
                    if usuario_responsavel:
                        entidade.UsuarioAlteracao = usuario_responsavel
                        entidade.DataAlteracao = datetime.now()
            sessao.commit()
            return True, "Cortes excluídos com sucesso"
        except Exception as e:
            sessao.rollback()
            return False, str(e)
        finally:
            sessao.close()