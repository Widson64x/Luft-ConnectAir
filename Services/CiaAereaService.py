from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.CiaConfig import CiaConfig
from Models.SQL_SERVER.MalhaAerea import VooMalha, RemessaMalha
from Services.LogService import LogService
from Services.Logic.RouteConfig import REGRAS_BUSCA_PADRAO

class CiaAereaService:

    @staticmethod
    def _NormalizarNomeCia(nome_cia):
        if nome_cia is None:
            return None

        nome_normalizado = str(nome_cia).strip().upper()
        return nome_normalizado or None
    
    @staticmethod
    def ObterTodasCias():
        """
        Lista todas as Cias Aéreas que existem na Malha ou já configuradas,
        junto com seus scores atuais.
        """
        Sessao = ObterSessaoSqlServer()
        try:
            # 1. Busca Cias Configuradas
            Configs = Sessao.query(CiaConfig).filter(CiaConfig.Ativo == True).all()
            MapConfigs = {}

            for config in Configs:
                nome_config = CiaAereaService._NormalizarNomeCia(config.CiaAerea)
                if nome_config:
                    MapConfigs[nome_config] = config.ScoreParceria
            
            # 2. Busca Cias da Malha Ativa (para garantir que novas apareçam)
            CiasMalha = Sessao.query(VooMalha.CiaAerea).join(RemessaMalha)\
                .filter(RemessaMalha.Ativo == True).distinct().all()
            
            ListaFinal = []
            CiasVistas = set()

            # Adiciona as da Malha
            for (nome_cia,) in CiasMalha:
                nome_cia = CiaAereaService._NormalizarNomeCia(nome_cia)
                if not nome_cia or nome_cia in CiasVistas:
                    continue

                score = MapConfigs.get(nome_cia, REGRAS_BUSCA_PADRAO.score_parceria_padrao)
                ListaFinal.append({'cia': nome_cia, 'score': score})
                CiasVistas.add(nome_cia)
            
            # Adiciona as configuradas que talvez não estejam na malha hoje (histórico)
            for c in Configs:
                nome_cia = CiaAereaService._NormalizarNomeCia(c.CiaAerea)
                if nome_cia and nome_cia not in CiasVistas:
                    ListaFinal.append({'cia': nome_cia, 'score': c.ScoreParceria})
                    CiasVistas.add(nome_cia)
            
            # Ordena por nome
            ListaFinal.sort(key=lambda x: x['cia'])
            return ListaFinal

        except Exception as e:
            LogService.Error("CiaAereaService", "Erro ao listar cias", e)
            return []
        finally:
            Sessao.close()

    @staticmethod
    def AtualizarScore(cia, novo_score):
        """Atualiza o índice de 'parceria' de uma cia."""
        Sessao = ObterSessaoSqlServer()
        try:
            cia = CiaAereaService._NormalizarNomeCia(cia)
            if not cia:
                return False

            Config = Sessao.query(CiaConfig).filter(CiaConfig.CiaAerea == cia).first()
            
            if not Config:
                Config = CiaConfig(CiaAerea=cia, ScoreParceria=novo_score)
                Sessao.add(Config)
            else:
                Config.ScoreParceria = novo_score
            
            Sessao.commit()
            return True
        except Exception as e:
            LogService.Error("CiaAereaService", f"Erro ao atualizar score {cia}", e)
            return False
        finally:
            Sessao.close()

    @staticmethod
    def ObterDicionarioScores():
        """Retorna um dict simples {'LATAM': 100, 'GOL': 20} para uso rápido no algoritmo."""
        Sessao = ObterSessaoSqlServer()
        try:
            Configs = Sessao.query(CiaConfig).filter(CiaConfig.Ativo == True).all()
            return {
                CiaAereaService._NormalizarNomeCia(c.CiaAerea): c.ScoreParceria
                for c in Configs
                if CiaAereaService._NormalizarNomeCia(c.CiaAerea)
            }
        except:
            return {}
        finally:
            Sessao.close()