from datetime import datetime, date, time
from sqlalchemy import desc
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Ctc import Ctc

def BuscarCtcsAereoHoje():
    Sessao = ObterSessaoSqlServer()
    try:
        Hoje = date.today()
        Inicio = datetime.combine(Hoje, time.min)
        Fim = datetime.combine(Hoje, time.max)
        
        Resultados = Sessao.query(Ctc).filter(
            Ctc.data >= Inicio,
            Ctc.data <= Fim,
            Ctc.modal.like('AEREO%')
        ).order_by(desc(Ctc.fretetotal)).all() # <--- ORDENAÇÃO POR VALOR (Mais caro no topo)
        
        ListaCtcs = []
        for c in Resultados:
            # Helpers de formatação
            def to_float(val): return float(val) if val else 0.0
            def to_int(val): return int(val) if val else 0
            def to_str(val): return str(val).strip() if val else ''
            def fmt_moeda(val): return f"{to_float(val):,.2f}" # Retorna número formatado sem R$ para o front estilizar

            ListaCtcs.append({
                # ID Único para rastreio no Front (Filial + Numero)
                'id_unico': f"{to_str(c.filial)}-{to_str(c.filialctc)}",
                
                'filial': to_str(c.filial),
                'ctc': to_str(c.filialctc),
                'serie': to_str(c.seriectc),
                
                # Tempos
                'data_emissao': c.data.strftime('%d/%m') if c.data else '',
                'hora_emissao': to_str(c.hora) if to_str(c.hora) else '--:--',
                
                # Dados Comerciais
                'prioridade': to_str(c.prioridade),
                'origem': f"{to_str(c.cidade_orig)}/{to_str(c.uf_orig)}",
                'destino': f"{to_str(c.cidade_dest)}/{to_str(c.uf_dest)}",
                'remetente': to_str(c.remet_nome),
                'destinatario': to_str(c.dest_nome),
                
                # Detalhes Carga
                'nfs': to_str(c.nfs),
                'natureza': to_str(c.natureza),
                'especie': to_str(c.especie),
                'volumes': to_int(c.volumes),
                
                # Pesos (Numérico puro para cálculos se precisar)
                'peso_real': to_float(c.peso),
                'peso_taxado': to_float(c.pesotax),
                
                # Valores (Formatados string '1.000,00')
                'val_mercadoria': fmt_moeda(c.valmerc),
                'frete_valor': fmt_moeda(c.fretevalor),
                'gris': fmt_moeda(c.gris),
                'frete_bruto': fmt_moeda(c.fretetotalbruto),
                'frete_total': fmt_moeda(c.fretetotal),
                
                # Valor cru para ordenação no front se precisar
                'raw_frete_total': to_float(c.fretetotal)
            })
            
        return ListaCtcs
        
    except Exception as e:
        print(f"Erro service: {e}")
        return []
    finally:
        Sessao.close()