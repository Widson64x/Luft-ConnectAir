from datetime import datetime, date, time, timedelta
from decimal import Decimal
from sqlalchemy import desc, func
from Conexoes import ObterSessaoSqlServer, ObterSessaoSqlServer
from Models.SQL_SERVER.Ctc import CtcEsp, CtcEspCpl
from Models.SQL_SERVER.Planejamento import PlanejamentoCabecalho, PlanejamentoItem, PlanejamentoTrecho
from Services.LogService import LogService 

class PlanejamentoService:
    """
    Service Layer para o Módulo de Planejamento.
    Responsável por buscar CTCs no SQL Server, tratar tipos de dados (Decimal/Date)
    e preparar objetos para o Front-end.
    """

    @staticmethod
    def ObterCtcCompleto(filial, serie, ctc_num):
        """
        Busca um CTC específico + DADOS COMPLEMENTARES (CPL)
        Retorna um dicionário unificado com TODAS as colunas de ambas as tabelas.
        """
        Sessao = ObterSessaoSqlServer()
        try:
            # Busca flexível (remove zeros a esquerda se precisar)
            f, s, n = str(filial).strip(), str(serie).strip(), str(ctc_num).strip()
            
            # Query com Outer Join para garantir que traga o CTC mesmo sem CPL
            Query = Sessao.query(CtcEsp, CtcEspCpl).outerjoin(
                CtcEspCpl, 
                CtcEsp.filialctc == CtcEspCpl.filialctc
            ).filter(
                CtcEsp.filial == f,
                CtcEsp.seriectc == s,
                CtcEsp.filialctc == n
            )

            Resultado = Query.first()

            # Tenta achar sem zeros se falhar (Lógica de fallback existente)
            if not Resultado:
                Query = Sessao.query(CtcEsp, CtcEspCpl).outerjoin(CtcEspCpl, CtcEsp.filialctc == CtcEspCpl.filialctc).filter(
                    CtcEsp.filial == f, CtcEsp.seriectc == s, CtcEsp.filialctc == n.lstrip('0')
                )
                Resultado = Query.first()

            if not Resultado: 
                LogService.Warning("PlanejamentoService", f"ObterCtcCompleto: CTC não encontrado {f}-{s}-{n}")
                return None

            # Desempacota
            Ctc, Cpl = Resultado
            dados_completos = {}

            # 1. Serializa CTC Principal
            for coluna in Ctc.__table__.columns:
                valor = getattr(Ctc, coluna.name)
                if isinstance(valor, (datetime, date, time)): valor = str(valor)
                elif isinstance(valor, Decimal): valor = float(valor)
                elif valor is None: valor = ""
                dados_completos[coluna.name] = valor
            
            # 2. Serializa CPL (se existir) e mescla no mesmo dict
            if Cpl:
                for coluna in Cpl.__table__.columns:
                    valor = getattr(Cpl, coluna.name)
                    if isinstance(valor, (datetime, date, time)): valor = str(valor)
                    elif isinstance(valor, Decimal): valor = float(valor)
                    elif valor is None: valor = ""
                    
                    # Evita sobrescrever chaves importantes se nomes forem idênticos (exceto se for intencional)
                    # O CPL geralmente tem prefixos unicos (Fatura_, CTE_, etc), então é seguro.
                    dados_completos[coluna.name] = valor
            else:
                # Preenche campos vitais do CPL com vazio para não quebrar o front
                dados_completos['StatusCTC'] = 'N/A'
                dados_completos['TipoCarga'] = 'N/A'

            LogService.Debug("PlanejamentoService", f"Detalhes recuperados (Base+Cpl) para {f}-{s}-{n}")
            return dados_completos

        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro em ObterCtcCompleto", e)
            return None
        finally:
            Sessao.close()

    @staticmethod
    def BuscarCtcsAereoHoje():
        """
        Lista principal do Dashboard.
        Traz todos os CTCs Aéreos emitidos HOJE do SQL Server e cruza com o
        Postgres para saber o Status do Planejamento.
        """
        SessaoSQL = ObterSessaoSqlServer()
        SessaoPG = ObterSessaoSqlServer() 
        
        try:
            LogService.Debug("PlanejamentoService", "Iniciando busca de CTCs Aéreos de Hoje/Ontem...")
            
            # 1. BUSCA DADOS NO SQL SERVER (CTCs DO DIA) + JOIN COM CPL
            Hoje = date.today() - timedelta(days=0) # Ajuste de dias se necessário
            Inicio = datetime.combine(Hoje, time.min)
            Fim = datetime.combine(Hoje, time.max)
            
            Resultados = SessaoSQL.query(CtcEsp, CtcEspCpl).outerjoin(
                CtcEspCpl, 
                CtcEsp.filialctc == CtcEspCpl.filialctc
            ).filter(
                CtcEsp.data >= Inicio,
                CtcEsp.data <= Fim,
                CtcEsp.tipodoc != 'COB',
                CtcEsp.modal.like('AEREO%'),
                CtcEspCpl.StatusCTC != 'CTC CANCELADO' # Exclui CTCs cancelados
            ).order_by(
                desc(CtcEsp.data),
                desc(CtcEsp.hora)
            ).all()

            LogService.Info("PlanejamentoService", f"Encontrados {len(Resultados)} CTCs no SQL Server.")
            LogService.Debug("PlanejamentoService", f"Os CTCs de tipo 'COB' ou modal diferente de 'AÉREO' foram excluídos.")
            # 2. BUSCA CACHE DE PLANEJAMENTOS NO POSTGRES
            rows_pg = []
            if SessaoPG:
                try:
                    rows_pg = SessaoPG.query(
                        PlanejamentoItem.Filial,
                        PlanejamentoItem.Serie,
                        PlanejamentoItem.Ctc,
                        PlanejamentoCabecalho.Status,
                        PlanejamentoCabecalho.IdPlanejamento
                    ).join(
                        PlanejamentoCabecalho, 
                        PlanejamentoItem.IdPlanejamento == PlanejamentoCabecalho.IdPlanejamento
                    ).all()
                except Exception as e:
                    LogService.Error("PlanejamentoService", "Erro ao consultar Cache Postgres (Planejamento)", e)

            mapa_planejamento = {}
            for row in rows_pg:
                chave = f"{str(row.Filial).strip()}-{str(row.Serie).strip()}-{str(row.Ctc).strip()}"
                mapa_planejamento[chave] = {
                    'status': row.Status,
                    'id_plan': row.IdPlanejamento
                }

            # 3. MONTAGEM DA LISTA FINAL
            ListaCtcs = []
            
            def to_float(val): return float(val) if val else 0.0
            def to_int(val): return int(val) if val else 0
            def to_str(val): return str(val).strip() if val else ''
            def fmt_moeda(val): return f"{to_float(val):,.2f}"

            for c, cpl in Resultados:
                
                # TipoCarga
                tipo_carga_valor = cpl.TipoCarga if cpl and cpl.TipoCarga else ""

                # Serializa dados do CTC principal
                dados_completos = {}
                for coluna in c.__table__.columns:
                    valor = getattr(c, coluna.name)
                    if isinstance(valor, (datetime, date, time)): valor = str(valor)
                    elif isinstance(valor, Decimal): valor = float(valor)
                    elif valor is None: valor = ""
                    dados_completos[coluna.name] = valor
                
                if cpl:
                    dados_completos['TipoCarga'] = tipo_carga_valor

                # Contagem de Notas
                raw_notas = getattr(c, 'notas', '') 
                qtd_notas_calc = 0
                if raw_notas:
                    s_notas = str(raw_notas).replace('/', ',').replace(';', ',').replace('-', ',')
                    lista_n = [n for n in s_notas.split(',') if n.strip()]
                    qtd_notas_calc = len(lista_n)
                if qtd_notas_calc == 0 and to_int(c.volumes) > 0: qtd_notas_calc = 1

                # Formatação Hora
                HoraFormatada = '--:--'
                if c.hora:
                    h = str(c.hora).strip()
                    if len(h) == 4 and ':' not in h: h = f"{h[:2]}:{h[2:]}"
                    elif len(h) == 3 and ':' not in h: h = f"0{h[:1]}:{h[1:]}"
                    elif len(h) <= 2: h = f"{h.zfill(2)}:00"
                    HoraFormatada = h

                # Verificação Planejamento
                chave_ctc = f"{to_str(c.filial)}-{to_str(c.seriectc)}-{to_str(c.filialctc)}"
                info_plan = mapa_planejamento.get(chave_ctc)
                
                tem_planejamento = False
                status_plan = None
                id_plan = None
                
                if info_plan:
                    tem_planejamento = True
                    status_plan = info_plan['status']
                    id_plan = info_plan['id_plan']

                # Objeto Final
                ListaCtcs.append({
                    'id_unico': f"{to_str(c.filial)}-{to_str(c.filialctc)}",
                    'filial': to_str(c.filial),
                    'ctc': to_str(c.filialctc),
                    'serie': to_str(c.seriectc),
                    'data_emissao': c.data.strftime('%d/%m/%Y') if c.data else '',
                    'hora_emissao': HoraFormatada,
                    'prioridade': to_str(c.prioridade),
                    'status_ctc': to_str(cpl.StatusCTC) if cpl else '',
                    'origem': f"{to_str(c.cidade_orig)}/{to_str(c.uf_orig)}",
                    'destino': f"{to_str(c.cidade_dest)}/{to_str(c.uf_dest)}",
                    'unid_lastmile': to_str(c.rotafilialdest),
                    'remetente': to_str(c.remet_nome),
                    'destinatario': to_str(c.dest_nome),
                    'volumes': to_int(c.volumes),
                    'peso_taxado': to_float(c.pesotax),
                    'val_mercadoria': fmt_moeda(c.valmerc),
                    'raw_val_mercadoria': to_float(c.valmerc),
                    'raw_frete_total': to_float(c.fretetotalbruto),
                    'qtd_notas': qtd_notas_calc,
                    'tipo_carga': tipo_carga_valor,
                    'tem_planejamento': tem_planejamento,
                    'status_planejamento': status_plan,
                    'id_planejamento': id_plan,
                    'full_data': dados_completos
                })
            
            return ListaCtcs

        except Exception as e:
            LogService.Error("PlanejamentoService", "Falha crítica em BuscarCtcsAereoHoje", e)
            return []
        finally:
            SessaoSQL.close()
            if SessaoPG: SessaoPG.close()

    @staticmethod
    def ObterCtcDetalhado(Filial, Serie, Numero):
        """
        Captura detalhes completos do CTC a partir da Filial, Série e Número.
        AGORA COM JOIN NA TABELA COMPLEMENTAR PARA PEGAR O TIPO DE CARGA.
        """
        Sessao = ObterSessaoSqlServer()
        try:
            f = str(Filial).strip()
            s = str(Serie).strip()
            n = str(Numero).strip()

            # 1. ALTERAÇÃO: Trazemos a tupla (CtcEsp, CtcEspCpl)
            Query = Sessao.query(CtcEsp, CtcEspCpl).outerjoin(
                CtcEspCpl, 
                CtcEsp.filialctc == CtcEspCpl.filialctc
            ).filter(
                CtcEsp.filial == f, CtcEsp.seriectc == s, CtcEsp.filialctc == n
            )

            Resultado = Query.first()
            
            # Tentativas de busca flexível (zeros à esquerda)
            if not Resultado:
                Query = Sessao.query(CtcEsp, CtcEspCpl).outerjoin(CtcEspCpl, CtcEsp.filialctc == CtcEspCpl.filialctc).filter(
                    CtcEsp.filial == f, CtcEsp.seriectc == s, CtcEsp.filialctc == n.lstrip('0')
                )
                Resultado = Query.first()

            if not Resultado:
                 Query = Sessao.query(CtcEsp, CtcEspCpl).outerjoin(CtcEspCpl, CtcEsp.filialctc == CtcEspCpl.filialctc).filter(
                    CtcEsp.filial == f, CtcEsp.seriectc == s, CtcEsp.filialctc == n.zfill(10)
                )
                 Resultado = Query.first()

            if not Resultado: 
                LogService.Warning("PlanejamentoService", f"CTC Detalhado não encontrado: {f}-{s}-{n}")
                return None
            
            # Desempacota os objetos
            CtcEncontrado, CplEncontrado = Resultado

            DataBase = CtcEncontrado.data 
            HoraFinal = time(0, 0)
            str_hora = "00:00"

            if CtcEncontrado.hora:
                try:
                    h_str = str(CtcEncontrado.hora).strip().replace(':', '')
                    h_str = h_str.zfill(4)
                    if len(h_str) >= 4:
                        HoraFinal = datetime.strptime(h_str[:4], '%H%M').time()
                        str_hora = f"{h_str[:2]}:{h_str[2:]}"
                except: pass

            DataEmissaoReal = datetime.combine(DataBase.date(), HoraFinal)
            DataBuscaVoos = DataEmissaoReal + timedelta(hours=10)

            # 2. Captura o Tipo de Carga
            TipoCargaValor = CplEncontrado.TipoCarga if CplEncontrado else None

            return {
                'filial': CtcEncontrado.filial,
                'serie': CtcEncontrado.seriectc,
                'ctc': CtcEncontrado.filialctc,
                'data_emissao_real': DataEmissaoReal,
                'hora_formatada': str_hora,
                'data_busca': DataBuscaVoos,
                'origem_cidade': str(CtcEncontrado.cidade_orig).strip(),
                'origem_uf': str(CtcEncontrado.uf_orig).strip(),
                'destino_cidade': str(CtcEncontrado.cidade_dest).strip(),
                'destino_uf': str(CtcEncontrado.uf_dest).strip(),
                'peso': float(CtcEncontrado.peso or 0),
                'volumes': int(CtcEncontrado.volumes or 0),
                'valor': (CtcEncontrado.valmerc or 0),
                'remetente': str(CtcEncontrado.remet_nome).strip(),
                'destinatario': str(CtcEncontrado.dest_nome).strip(),
                'tipo_carga': TipoCargaValor 
            }
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro em ObterCtcDetalhado", e)
            return None
        finally:
            Sessao.close()

    @staticmethod
    def BuscarCtcsConsolidaveis(cidade_origem, uf_origem, cidade_destino, uf_destino, data_base, filial_excluir=None, ctc_excluir=None, tipo_carga=None):
        """
        Busca todos os CTCs aéreos do mesmo dia, mesma rota e MESMO TIPO DE CARGA.
        """
        Sessao = ObterSessaoSqlServer()
        try:
            # Logs substituindo prints
            LogService.Debug("PlanejamentoService", f"Iniciando busca consolidação. Rota: {cidade_origem}/{uf_origem} -> {cidade_destino}/{uf_destino}, TipoCarga: {tipo_carga}")

            if isinstance(data_base, datetime): data_base = data_base.date()
            Inicio = datetime.combine(data_base, time.min)
            Fim = datetime.combine(data_base, time.max)
            
            cidade_origem = str(cidade_origem).strip().upper()
            uf_origem = str(uf_origem).strip().upper()
            cidade_destino = str(cidade_destino).strip().upper()
            uf_destino = str(uf_destino).strip().upper()
            
            # ALTERADO: Trazemos (CtcEsp, CtcEspCpl) para poder dar print no tipo
            Query = Sessao.query(CtcEsp, CtcEspCpl).outerjoin(
                CtcEspCpl, 
                CtcEsp.filialctc == CtcEspCpl.filialctc
            ).filter(
                CtcEsp.data >= Inicio, CtcEsp.data <= Fim,
                CtcEsp.tipodoc != 'COB', CtcEsp.modal.like('AEREO%'),
                func.upper(func.trim(CtcEsp.cidade_orig)) == cidade_origem,
                func.upper(func.trim(CtcEsp.uf_orig)) == uf_origem,
                func.upper(func.trim(CtcEsp.cidade_dest)) == cidade_destino,
                func.upper(func.trim(CtcEsp.uf_dest)) == uf_destino
            )
            
            # Filtro do Tipo de Carga
            if tipo_carga:
                Query = Query.filter(CtcEspCpl.TipoCarga == str(tipo_carga).strip())
            
            if filial_excluir and ctc_excluir:  
                Query = Query.filter(~((CtcEsp.filial == str(filial_excluir).strip()) & (CtcEsp.filialctc == str(ctc_excluir).strip())))
            
            Resultados = Query.order_by(desc(CtcEsp.data), desc(CtcEsp.hora)).all()
            
            LogService.Info("PlanejamentoService", f"Encontrados {len(Resultados)} candidatos para consolidação na rota {cidade_origem}-{cidade_destino}.")

            ListaConsolidados = []
            
            for c, cpl in Resultados:
                tipo_candidato = cpl.TipoCarga if cpl else "N/A"
                # Log Debug opcional
                # LogService.Debug("PlanejamentoService", f"Candidato: {c.filialctc} | Tipo: {tipo_candidato}")

                def to_float(val): return float(val) if val else 0.0
                def to_int(val): return int(val) if val else 0
                def to_str(val): return str(val).strip() if val else ''
                
                str_hora = "00:00"
                if c.hora:
                    h_raw = str(c.hora).strip().replace(':', '').zfill(4)
                    if len(h_raw) >= 4:
                        str_hora = f"{h_raw[:2]}:{h_raw[2:]}"

                ListaConsolidados.append({
                    'filial': to_str(c.filial),
                    'ctc': to_str(c.filialctc),
                    'serie': to_str(c.seriectc),
                    'volumes': to_int(c.volumes),
                    'peso_taxado': to_float(c.pesotax),
                    'val_mercadoria': to_float(c.valmerc),
                    'remetente': to_str(c.remet_nome),
                    'destinatario': to_str(c.dest_nome),
                    'data_emissao': c.data,
                    'hora_emissao': str_hora,
                    'origem_cidade': to_str(c.cidade_orig),
                    'destino_cidade': to_str(c.cidade_dest),
                    'tipo_carga': tipo_candidato
                })
            
            return ListaConsolidados
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro em BuscarCtcsConsolidaveis", e)
            return []
        finally:
            Sessao.close()

    @staticmethod
    def UnificarConsolidacao(ctc_principal, lista_candidatos):
        """
        Recebe o CTC Principal e a Lista de Candidatos.
        Retorna um objeto 'Virtual' (Lote) somando volumes, pesos e valores.
        """
        try:
            if not lista_candidatos:
                ctc_principal['is_consolidado'] = False
                ctc_principal['lista_docs'] = [ctc_principal.copy()] 
                ctc_principal['qtd_docs'] = 1
                return ctc_principal

            unificado = ctc_principal.copy()
            
            docs = [{
                'filial': ctc_principal['filial'],
                'serie': ctc_principal['serie'],
                'ctc': ctc_principal['ctc'],
                'volumes': int(ctc_principal['volumes']),
                'peso': float(ctc_principal['peso']),
                'valor': float(ctc_principal['valor']),
                'remetente': ctc_principal['remetente'],
                'destinatario': ctc_principal['destinatario'],
                'tipo_carga': ctc_principal['tipo_carga']
            }]
            
            total_volumes = docs[0]['volumes']
            total_peso = docs[0]['peso']
            total_valor = docs[0]['valor']

            for c in lista_candidatos:
                c_doc = {
                    'filial': c['filial'],
                    'serie': c['serie'],
                    'ctc': c['ctc'],
                    'volumes': int(c['volumes']),
                    'peso': float(c['peso_taxado']),
                    'valor': float(c['val_mercadoria']),
                    'remetente': c['remetente'],
                    'destinatario': c['destinatario'],
                    'tipo_carga': c['tipo_carga']
                }
                docs.append(c_doc)
                total_volumes += c_doc['volumes']
                total_peso += c_doc['peso']
                total_valor += c_doc['valor']

            unificado['volumes'] = total_volumes
            unificado['peso'] = total_peso
            unificado['valor'] = total_valor
            
            unificado['is_consolidado'] = True
            unificado['lista_docs'] = docs
            unificado['qtd_docs'] = len(docs)
            unificado['resumo_consol'] = f"Lote com {len(docs)} CTCs"

            LogService.Info("PlanejamentoService", f"Consolidação Unificada: {len(docs)} documentos, Total Peso: {total_peso}")
            return unificado
        except Exception as e:
            LogService.Error("PlanejamentoService", "Erro em UnificarConsolidacao", e)
            return ctc_principal # Retorna o original para não quebrar tudo
    
    @staticmethod
    def RegistrarPlanejamento(dados_ctc_principal, lista_consolidados=None, usuario="Sistema", status_inicial='Em Planejamento', 
                              aero_origem=None, aero_destino=None, lista_trechos=None):
        """
        Salva ou atualiza o Planejamento, Itens e TRECHOS DE VOO.
        """
        SessaoPG = ObterSessaoSqlServer()
        if not SessaoPG: 
            LogService.Error("PlanejamentoService", "Falha de conexão com Postgres ao tentar RegistrarPlanejamento.")
            return None

        try:
            LogService.Info("PlanejamentoService", f"Iniciando Gravação de Planejamento. Usuário: {usuario}")

            def parse_dt(dt_str):
                if not dt_str: return None
                try: return datetime.fromisoformat(str(dt_str).replace('Z', ''))
                except: return None

            item_existente = SessaoPG.query(PlanejamentoItem).join(PlanejamentoCabecalho).filter(
                PlanejamentoItem.Filial == str(dados_ctc_principal['filial']),
                PlanejamentoItem.Serie == str(dados_ctc_principal['serie']),
                PlanejamentoItem.Ctc == str(dados_ctc_principal['ctc']),
                PlanejamentoCabecalho.Status == status_inicial
            ).first()

            Cabecalho = None

            if item_existente:
                LogService.Info("PlanejamentoService", f"Atualizando Planejamento Existente ID: {item_existente.Cabecalho.IdPlanejamento}")
                Cabecalho = item_existente.Cabecalho
                if aero_origem: Cabecalho.AeroportoOrigem = aero_origem
                if aero_destino: Cabecalho.AeroportoDestino = aero_destino
                
                # Limpa trechos antigos para regravar
                SessaoPG.query(PlanejamentoTrecho).filter(PlanejamentoTrecho.IdPlanejamento == Cabecalho.IdPlanejamento).delete()
            
            else:
                LogService.Info("PlanejamentoService", "Criando novo registro de Planejamento Cabecalho/Itens.")
                def get_val(key): return float(dados_ctc_principal.get(key, 0) or 0)
                
                Cabecalho = PlanejamentoCabecalho(
                    UsuarioCriacao=str(usuario),
                    Status=status_inicial,
                    AeroportoOrigem=aero_origem,
                    AeroportoDestino=aero_destino,
                    TotalVolumes=int(get_val('volumes')),
                    TotalPeso=get_val('peso'),
                    TotalValor=get_val('valor')
                )
                SessaoPG.add(Cabecalho)
                SessaoPG.flush()

                # Adiciona CTC Principal
                if dados_ctc_principal.get('is_consolidado'): info = dados_ctc_principal['lista_docs'][0]
                else: info = dados_ctc_principal
                
                ItemPrincipal = PlanejamentoItem(
                    IdPlanejamento=Cabecalho.IdPlanejamento,
                    Filial=str(dados_ctc_principal['filial']),
                    Serie=str(dados_ctc_principal['serie']),
                    Ctc=str(dados_ctc_principal['ctc']),
                    DataEmissao=dados_ctc_principal.get('data_emissao_real'),
                    Hora=dados_ctc_principal.get('hora_formatada'), 
                    Remetente=str(dados_ctc_principal.get('remetente',''))[:100],
                    Destinatario=str(dados_ctc_principal.get('destinatario',''))[:100],
                    OrigemCidade=str(dados_ctc_principal.get('origem_cidade',''))[:50],
                    DestinoCidade=str(dados_ctc_principal.get('destino_cidade',''))[:50],
                    Volumes=int(info.get('volumes', 0)),
                    PesoTaxado=float(info.get('peso', 0) or info.get('peso_taxado', 0)),
                    ValMercadoria=float(info.get('valor', 0) or info.get('val_mercadoria', 0)),
                    IndConsolidado=False
                )
                SessaoPG.add(ItemPrincipal)

                # Adiciona Consolidados
                if lista_consolidados:
                    for c in lista_consolidados:
                        SessaoPG.add(PlanejamentoItem(
                            IdPlanejamento=Cabecalho.IdPlanejamento,
                            Filial=str(c['filial']), Serie=str(c['serie']), Ctc=str(c['ctc']),
                            Volumes=int(c.get('volumes',0)), PesoTaxado=float(c.get('peso_taxado',0)),
                            ValMercadoria=float(c.get('val_mercadoria',0)),
                            Remetente=str(c.get('remetente',''))[:100], Destinatario=str(c.get('destinatario',''))[:100],
                            DataEmissao=c.get('data_emissao'),
                            Hora=c.get('hora_emissao'), 
                            OrigemCidade=str(c.get('origem_cidade', ''))[:50],
                            DestinoCidade=str(c.get('destino_cidade', ''))[:50],
                            IndConsolidado=True
                        ))

            # 3. GRAVA OS TRECHOS
            if lista_trechos and len(lista_trechos) > 0:
                LogService.Debug("PlanejamentoService", f"Gravando {len(lista_trechos)} trechos de voo.")
                for idx, trecho in enumerate(lista_trechos):
                    NovoTrecho = PlanejamentoTrecho(
                        IdPlanejamento=Cabecalho.IdPlanejamento,
                        Ordem=idx + 1,
                        CiaAerea=trecho.get('cia'),
                        NumeroVoo=trecho.get('voo'),
                        AeroportoOrigem=trecho.get('origem', {}).get('iata') if isinstance(trecho.get('origem'), dict) else trecho.get('origem'),
                        AeroportoDestino=trecho.get('destino', {}).get('iata') if isinstance(trecho.get('destino'), dict) else trecho.get('destino'),
                        DataPartida=parse_dt(trecho.get('partida_iso')),
                        DataChegada=parse_dt(trecho.get('chegada_iso'))
                    )
                    SessaoPG.add(NovoTrecho)

            SessaoPG.commit()
            LogService.Info("PlanejamentoService", f"Planejamento gravado com sucesso! ID: {Cabecalho.IdPlanejamento}")
            return Cabecalho.IdPlanejamento

        except Exception as e:
            SessaoPG.rollback()
            LogService.Error("PlanejamentoService", "Erro crítico ao gravar planejamento", e)
            return None
        finally:
            SessaoPG.close()