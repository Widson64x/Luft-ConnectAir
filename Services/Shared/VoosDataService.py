from datetime import datetime
from sqlalchemy import func
from sqlalchemy import func

from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.MalhaAerea import VooMalha, RemessaMalha
from Services.LogService import LogService


def ObterTotalVoosData(data_ref):
    """Retorna count de voos ativos para uma data específica."""
    Sessao = ObterSessaoSqlServer()
    try:
        DataFiltro = data_ref.date() if isinstance(data_ref, datetime) else data_ref
        
        Total = Sessao.query(func.count(VooMalha.Id))\
            .join(RemessaMalha)\
            .filter(
                RemessaMalha.Ativo == True,
                VooMalha.DataPartida == DataFiltro
            ).scalar()
            
        return Total or 0
    except Exception as e:
        # Substituído print por LogService
        LogService.Error("MalhaService", "Erro ao obter total de voos", e)
        return 0
    finally:
        Sessao.close()