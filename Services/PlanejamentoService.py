from datetime import datetime, date, time, timedelta
from decimal import Decimal
from sqlalchemy import desc, func
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Ctc import Ctc

class PlanejamentoService:
    """
    Service Layer para o Módulo de Planejamento.
    Responsável por buscar CTCs no SQL Server, tratar tipos de dados (Decimal/Date)
    e preparar objetos para o Front-end.
    
    """

    @staticmethod
    def ObterCtcCompleto(filial, serie, ctc_num):
        """
        Busca um CTC específico e retorna um dicionário com TODAS as colunas.
        Usado para modais de detalhe e inspeção profunda.
        """
        Sessao = ObterSessaoSqlServer()
        try:
            # Busca flexível (remove zeros a esquerda se precisar)
            f, s, n = str(filial).strip(), str(serie).strip(), str(ctc_num).strip()
            
            c = Sessao.query(Ctc).filter(
                Ctc.filial == f,
                Ctc.seriectc == s,
                Ctc.filialctc == n
            ).first()

            # Tenta achar sem zeros se falhar
            if not c:
                c = Sessao.query(Ctc).filter(
                    Ctc.filial == f, 
                    Ctc.seriectc == s, 
                    Ctc.filialctc == n.lstrip('0')
                ).first()

            if not c: return None

            # Serializa TODAS as colunas
            dados_completos = {}
            for coluna in c.__table__.columns:
                valor = getattr(c, coluna.name)
                if isinstance(valor, (datetime, date, time)):
                    valor = str(valor)
                elif isinstance(valor, Decimal):
                    valor = float(valor)
                elif valor is None:
                    valor = ""
                dados_completos[coluna.name] = valor
                
            return dados_completos
        finally:
            Sessao.close()

    @staticmethod
    def BuscarCtcsAereoHoje():
        """
        Lista principal do Dashboard.
        Traz todos os CTCs Aéreos emitidos HOJE, com formatação para os Cards.
        """
        Sessao = ObterSessaoSqlServer()
        try:
            Hoje = date.today() - timedelta(days=0) # Ajuste para pegar os CTCs do dia atual
            Inicio = datetime.combine(Hoje, time.min)
            Fim = datetime.combine(Hoje, time.max)
            
            Resultados = Sessao.query(Ctc).filter(
                Ctc.data >= Inicio,
                Ctc.data <= Fim,
                Ctc.tipodoc != 'COB',
                # Ctc.motivodoc != 'DEV', # Retirando Devolução
                Ctc.modal.like('AEREO%')
            ).order_by(
                desc(Ctc.data),
                desc(Ctc.hora)
            ).all()
            
            ListaCtcs = []
            for c in Resultados:
                # --- HELPER: Serializa TODOS os dados do banco para o Modal ---
                dados_completos = {}
                for coluna in c.__table__.columns:
                    valor = getattr(c, coluna.name)
                    # Trata tipos que o JSON não aceita nativamente
                    if isinstance(valor, (datetime, date, time)):
                        valor = str(valor)
                    elif isinstance(valor, Decimal):
                        valor = float(valor)
                    elif valor is None:
                        valor = ""
                    
                    dados_completos[coluna.name] = valor
                # ------------------------------------------------------------

                # Formatadores visuais para o Card
                def to_float(val): return float(val) if val else 0.0
                def to_int(val): return int(val) if val else 0
                def to_str(val): return str(val).strip() if val else ''
                def fmt_moeda(val): return f"{to_float(val):,.2f}"

                # --- LÓGICA DE CONTAGEM DE NOTAS ---
                # Tenta pegar o campo 'notas'. Se sua coluna tiver outro nome (ex: doc_originario), altere aqui.
                raw_notas = getattr(c, 'notas', '') 
                qtd_notas_calc = 0
                
                if raw_notas:
                    # Transforma tudo em string, troca barras e espaços extras por vírgula para padronizar
                    s_notas = str(raw_notas).replace('/', ',').replace(';', ',').replace('-', ',')
                    # Quebra por vírgula e filtra itens vazios
                    lista_n = [n for n in s_notas.split(',') if n.strip()]
                    qtd_notas_calc = len(lista_n)
                
                # Fallback: Se a contagem deu 0 mas existe volumes, assumimos pelo menos 1 documento
                if qtd_notas_calc == 0 and to_int(c.volumes) > 0:
                    qtd_notas_calc = 1
                # ------------------------------------

                HoraFormatada = '--:--'
                if c.hora:
                    h = str(c.hora).strip()
                    if len(h) == 4 and ':' not in h: h = f"{h[:2]}:{h[2:]}"
                    elif len(h) == 3 and ':' not in h: h = f"0{h[:1]}:{h[1:]}"
                    elif len(h) <= 2: h = f"{h.zfill(2)}:00"
                    HoraFormatada = h

                ListaCtcs.append({
                    # Dados Resumidos para o Card
                    'id_unico': f"{to_str(c.filial)}-{to_str(c.filialctc)}",
                    'filial': to_str(c.filial),
                    'ctc': to_str(c.filialctc),
                    'serie': to_str(c.seriectc),
                    'data_emissao': c.data.strftime('%d/%m/%Y') if c.data else '',
                    'hora_emissao': HoraFormatada,
                    'prioridade': to_str(c.prioridade),
                    'origem': f"{to_str(c.cidade_orig)}/{to_str(c.uf_orig)}",
                    'destino': f"{to_str(c.cidade_dest)}/{to_str(c.uf_dest)}",
                    'unid_lastmile': to_str(c.rotafilialdest),
                    'remetente': to_str(c.remet_nome),     # Nome do Cliente
                    'destinatario': to_str(c.dest_nome),
                    'volumes': to_int(c.volumes),
                    'peso_taxado': to_float(c.pesotax),
                    'val_mercadoria': fmt_moeda(c.valmerc),
                    'raw_val_mercadoria': to_float(c.valmerc),
                    'raw_frete_total': to_float(c.fretetotalbruto),
                    
                    # --- NOVO CAMPO CALCULADO ---
                    'qtd_notas': qtd_notas_calc,
                    # ----------------------------

                    # O Objeto Completo vai aqui
                    'full_data': dados_completos
                })
                
            return ListaCtcs
        finally:
            Sessao.close()

    @staticmethod
    def ObterCtcDetalhado(Filial, Serie, Numero):
        """
        Captura detalhes completos do CTC a partir da Filial, Série e Número.
        Usado na rota de Montagem de Planejamento.
        Calcula a Data de Busca de Voos (Emissão + 10h).
        """
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
                # Processa a hora mesmo que esteja em formatos estranhos, e ajusta para 4 dígitos
                try:
                    h_str = str(CtcEncontrado.hora).strip().replace(':', '')
                    h_str = h_str.zfill(4) 
                    if len(h_str) >= 4:
                        HoraFinal = datetime.strptime(h_str[:4], '%H%M').time()
                except: pass

            # 3. Combina
            DataEmissaoReal = datetime.combine(DataBase.date(), HoraFinal)
            
            # 4. Margem de 10 horas para busca de voos
            DataBuscaVoos = DataEmissaoReal + timedelta(hours=10)

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
                'valor': (CtcEncontrado.valmerc or 0),
                'remetente': str(CtcEncontrado.remet_nome).strip(),
                'destinatario': str(CtcEncontrado.dest_nome).strip()
            }
        finally:
            Sessao.close()
    @staticmethod
    def BuscarCtcsConsolidaveis(cidade_origem, uf_origem, cidade_destino, uf_destino, data_base, filial_excluir=None, ctc_excluir=None):
        """
        Busca todos os CTCs aéreos do mesmo dia que compartilham a mesma origem e destino.
        Utilizado para consolidação de cargas no planejamento.
        
        Args:
            cidade_origem: Cidade de origem
            uf_origem: UF de origem
            cidade_destino: Cidade de destino
            uf_destino: UF de destino
            data_base: Data de referência (date ou datetime)
            filial_excluir: Filial do CTC principal (para não incluir na lista)
            ctc_excluir: Número do CTC principal (para não incluir na lista)
        
        Returns:
            Lista de CTCs consolidáveis com dados resumidos
        """
        Sessao = ObterSessaoSqlServer()
        try:
            # Normaliza a data para buscar todo o dia
            if isinstance(data_base, datetime):
                data_base = data_base.date()
            
            Inicio = datetime.combine(data_base, time.min)
            Fim = datetime.combine(data_base, time.max)
            
            # Normaliza strings para comparação
            cidade_origem = str(cidade_origem).strip().upper()
            uf_origem = str(uf_origem).strip().upper()
            cidade_destino = str(cidade_destino).strip().upper()
            uf_destino = str(uf_destino).strip().upper()
            
            # Query para buscar CTCs com mesma origem e destino
            Query = Sessao.query(Ctc).filter(
                Ctc.data >= Inicio,
                Ctc.data <= Fim,
                Ctc.tipodoc != 'COB',
                Ctc.modal.like('AEREO%'),
                func.upper(func.trim(Ctc.cidade_orig)) == cidade_origem,
                func.upper(func.trim(Ctc.uf_orig)) == uf_origem,
                func.upper(func.trim(Ctc.cidade_dest)) == cidade_destino,
                func.upper(func.trim(Ctc.uf_dest)) == uf_destino
            )
            
            # Exclui o CTC principal da lista
            if filial_excluir and ctc_excluir:
                Query = Query.filter(
                    ~((Ctc.filial == str(filial_excluir).strip()) & 
                      (Ctc.filialctc == str(ctc_excluir).strip()))
                )
            
            Resultados = Query.order_by(desc(Ctc.data), desc(Ctc.hora)).all()
            
            # Formata os dados para retorno
            ListaConsolidados = []
            for c in Resultados:
                def to_float(val): return float(val) if val else 0.0
                def to_int(val): return int(val) if val else 0
                def to_str(val): return str(val).strip() if val else ''
                
                # Formata hora
                HoraFormatada = '--:--'
                if c.hora:
                    h = str(c.hora).strip()
                    if len(h) == 4 and ':' not in h: h = f"{h[:2]}:{h[2:]}"
                    elif len(h) == 3 and ':' not in h: h = f"0{h[:1]}:{h[1:]}"
                    elif len(h) <= 2: h = f"{h.zfill(2)}:00"
                    HoraFormatada = h
                
                # Conta notas
                raw_notas = getattr(c, 'notas', '') or getattr(c, 'nfs', '')
                qtd_notas_calc = 0
                if raw_notas:
                    s_notas = str(raw_notas).replace('/', ',').replace(';', ',').replace('-', ',')
                    lista_n = [n for n in s_notas.split(',') if n.strip()]
                    qtd_notas_calc = len(lista_n)
                if qtd_notas_calc == 0 and to_int(c.volumes) > 0:
                    qtd_notas_calc = 1
                
                ListaConsolidados.append({
                    'filial': to_str(c.filial),
                    'ctc': to_str(c.filialctc),
                    'serie': to_str(c.seriectc),
                    'data_emissao': c.data.strftime('%d/%m/%Y') if c.data else '',
                    'hora_emissao': HoraFormatada,
                    'prioridade': to_str(c.prioridade),
                    'remetente': to_str(c.remet_nome),
                    'destinatario': to_str(c.dest_nome),
                    'volumes': to_int(c.volumes),
                    'peso_taxado': to_float(c.pesotax),
                    'peso_real': to_float(c.peso),
                    'val_mercadoria': to_float(c.valmerc),
                    'frete_total': to_float(c.fretetotalbruto),
                    'qtd_notas': qtd_notas_calc,
                    'tabela_frete': to_str(c.tabfrete),
                    'natureza': to_str(c.natureza),
                    'especie': to_str(c.especie),
                    # Campos para expansão futura
                    'tipo_produto': to_str(c.natureza),  # Pode ser refinado
                    'valor_tarifa': to_float(c.fretetotalbruto),  # Placeholder
                })
            
            return ListaConsolidados
            
        finally:
            Sessao.close()
