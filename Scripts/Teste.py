# Exemplo de uso no seu Service
from flask import session
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Awb import Awb, AwbStatus
from Models.SQL_SERVER.Ctc import Ctc

Sessao = ObterSessaoSqlServer()

def buscar_acompanhamento(session):
    # Join AWB com Status (Equivalente ao LINQ do código legado)
    query = session.query(
        Awb.codawb,
        Awb.awb,
        AwbStatus.STATUS_AWB,
        AwbStatus.DATAHORA_STATUS
    ).join(
        AwbStatus, Awb.codawb == AwbStatus.CODAWB
    ).all()
    
    print("Resultados do Acompanhamento de AWBs:")
    for resultado in query:
        print(f"CodAWB: {resultado.codawb}, AWB: {resultado.awb}, Status: {resultado.STATUS_AWB}, Data/Hora: {resultado.DATAHORA_STATUS}")
    return query

buscar_acompanhamento(Sessao)