from datetime import datetime, date, time, timedelta
from sqlalchemy import desc
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Ctc import Ctc

def BuscarCtcsAereoHoje():
    Sessao = ObterSessaoSqlServer()
    try:
        Hoje = date.today() - timedelta(days=0  ) # <--- Subtrai 1 dia
        #Hoje = date.today()
        Inicio = datetime.combine(Hoje, time.min)
        Fim = datetime.combine(Hoje, time.max)
        
        Resultados = Sessao.query(Ctc).filter(
            Ctc.data >= Inicio,
            Ctc.data <= Fim,
            Ctc.tipodoc != 'COB',
            Ctc.modal.like('AEREO%')
        ).order_by(desc(Ctc.fretetotal)).all()
        
        ListaCtcs = []
        for c in Resultados:
            # Formatadores
            def to_float(val): return float(val) if val else 0.0
            def to_int(val): return int(val) if val else 0
            def to_str(val): return str(val).strip() if val else ''
            def fmt_moeda(val): return f"{to_float(val):,.2f}"

            HoraFormatada = '--:--'
            if c.hora:
                h = str(c.hora).strip()
                if len(h) == 4 and ':' not in h: h = f"{h[:2]}:{h[2:]}"
                elif len(h) == 3 and ':' not in h: h = f"0{h[:1]}:{h[1:]}"
                elif len(h) <= 2: h = f"{h.zfill(2)}:00"
                HoraFormatada = h

            ListaCtcs.append({
                'id_unico': f"{to_str(c.filial)}-{to_str(c.filialctc)}",
                'filial': to_str(c.filial),
                'ctc': to_str(c.filialctc),
                'serie': to_str(c.seriectc),
                'data_emissao': c.data.strftime('%d/%m/%Y') if c.data else '',
                'hora_emissao': HoraFormatada,
                'prioridade': to_str(c.prioridade),
                'origem': f"{to_str(c.cidade_orig)}/{to_str(c.uf_orig)}",
                'destino': f"{to_str(c.cidade_dest)}/{to_str(c.uf_dest)}",
                'remetente': to_str(c.remet_nome),
                'destinatario': to_str(c.dest_nome),
                'nfs': to_str(c.nfs),
                'natureza': to_str(c.natureza),
                'especie': to_str(c.especie),
                'volumes': to_int(c.volumes),
                'peso_real': to_float(c.peso),
                'peso_taxado': to_float(c.pesotax),
                'val_mercadoria': fmt_moeda(c.valmerc),
                'frete_valor': fmt_moeda(c.fretevalor),
                'gris': fmt_moeda(c.gris),
                'frete_total': fmt_moeda(c.fretetotal),
                'raw_frete_total': to_float(c.fretetotal)
            })
            
        return ListaCtcs
    finally:
        Sessao.close()

from sqlalchemy import or_

def ObterCtcDetalhado(Filial, Serie, Numero):
    Sessao = ObterSessaoSqlServer()
    try:
        # Limpeza dos parâmetros de entrada
        f = str(Filial).strip()
        s = str(Serie).strip()
        n = str(Numero).strip()

        # Tenta buscar exato primeiro
        CtcEncontrado = Sessao.query(Ctc).filter(
            Ctc.filial == f,
            Ctc.seriectc == s,
            Ctc.filialctc == n
        ).first()
        
        # Se não achar, tenta remover zeros à esquerda do número (ex: 054... vs 54...)
        if not CtcEncontrado:
            CtcEncontrado = Sessao.query(Ctc).filter(
                Ctc.filial == f,
                Ctc.seriectc == s,
                Ctc.filialctc == n.lstrip('0') # Remove zeros do início
            ).first()

        # Se ainda não achar, tenta adicionar zeros (alguns sistemas padronizam 10 dígitos)
        if not CtcEncontrado:
             CtcEncontrado = Sessao.query(Ctc).filter(
                Ctc.filial == f,
                Ctc.seriectc == s,
                Ctc.filialctc == n.zfill(10) # Completa com zeros até 10 dígitos
            ).first()

        if not CtcEncontrado: 
            print(f"❌ CTC não encontrado no banco: Filial={f}, Série={s}, Num={n}")
            return None
        
        # 1. Pega a Data Base
        DataBase = CtcEncontrado.data 
        
        # 2. Processa a Hora
        HoraFinal = time(0, 0)
        if CtcEncontrado.hora:
            try:
                h_str = str(CtcEncontrado.hora).strip().replace(':', '')
                h_str = h_str.zfill(4) 
                if len(h_str) >= 4:
                    HoraFinal = datetime.strptime(h_str[:4], '%H%M').time()
            except: pass

        # 3. Combina
        DataEmissaoReal = datetime.combine(DataBase.date(), HoraFinal)
        
        # 4. Margem
        DataBuscaVoos = DataEmissaoReal + timedelta(hours=3)

        return {
            'filial': CtcEncontrado.filial,
            'serie': CtcEncontrado.seriectc,
            'ctc': CtcEncontrado.filialctc,
            'data_emissao_real': DataEmissaoReal,
            'data_busca': DataBuscaVoos,
            'origem_cidade': str(CtcEncontrado.cidade_orig).strip(),
            'origem_uf': str(CtcEncontrado.uf_orig).strip(),
            'destino_cidade': str(CtcEncontrado.cidade_dest).strip(),
            'destino_uf': str(CtcEncontrado.uf_dest).strip(),
            'peso': float(CtcEncontrado.peso or 0),
            'volumes': int(CtcEncontrado.volumes or 0),
            'valor': float(CtcEncontrado.valmerc or 0),
            'remetente': str(CtcEncontrado.remet_nome).strip(),
            'destinatario': str(CtcEncontrado.dest_nome).strip()
        }
    finally:
        Sessao.close()