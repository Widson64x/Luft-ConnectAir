import os
import pandas as pd
from datetime import datetime
from sqlalchemy import desc, func, text
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.TabelaFrete import RemessaFrete, TabelaFrete
from Configuracoes import ConfiguracaoBase
from Services.LogService import LogService

class TabelaFreteService:
    DIR_TEMP = ConfiguracaoBase.DIR_TEMP
    
    # Penalidade mantida apenas como referência, não retornada visualmente
    PENALIDADE_TARIFA_MISSING = 15000.0

    @staticmethod
    def _GarantirDiretorio():
        if not os.path.exists(TabelaFreteService.DIR_TEMP):
            try:
                os.makedirs(TabelaFreteService.DIR_TEMP)
            except Exception as e:
                LogService.Error("TabelaFreteService", "Falha ao criar diretório temp", e)

    @staticmethod
    def _NormalizarTarifa(val):
        if pd.isna(val): return None
        s = str(val).strip().upper()
        if s in ['', '-', 'NAN', 'NONE', 'N/A']: return None
        try:
            clean_val = s.replace('R$', '').replace(' ', '').replace(',', '.')
            return float(clean_val)
        except:
            return None

    @staticmethod
    def _NormalizarNomeCia(cia_input):
        if not cia_input: return ""
        s = str(cia_input).upper().strip()
        if 'LATAM' in s or 'TAM' in s or 'JJ' in s or 'LA' in s: return 'LATAM'
        if 'GOL' in s or 'G3' in s or 'GLO' in s: return 'GOL'
        if 'AZUL' in s or 'AD' in s or 'AZU' in s: return 'AZUL'
        return s

    @staticmethod
    def ListarRemessas():
        Sessao = ObterSessaoSqlServer()
        try:
            return Sessao.query(RemessaFrete).order_by(desc(RemessaFrete.DataUpload)).all()
        finally:
            Sessao.close()

    @staticmethod
    def ExcluirRemessa(id_remessa):
        Sessao = ObterSessaoSqlServer()
        try:
            Remessa = Sessao.query(RemessaFrete).get(id_remessa)
            if Remessa:
                Sessao.delete(Remessa)
                Sessao.commit()
                return True, "Tabela excluída com sucesso."
            return False, "Registro não encontrado."
        except Exception as e:
            Sessao.rollback()
            return False, str(e)
        finally:
            Sessao.close()

    @staticmethod
    def ProcessarArquivo(arquivo, usuario):
        TabelaFreteService._GarantirDiretorio()
        Caminho = os.path.join(TabelaFreteService.DIR_TEMP, arquivo.filename)
        Sessao = ObterSessaoSqlServer()
        
        try:
            arquivo.save(Caminho)
            LogService.Info("TabelaFreteService", f"Analisando arquivo: {arquivo.filename}")
            
            DfRaw = None
            with pd.ExcelFile(Caminho, engine='openpyxl') as XlsFile:
                SheetName = next((s for s in XlsFile.sheet_names if 'TARIF' in s.upper()), XlsFile.sheet_names[0])
                DfRaw = pd.read_excel(XlsFile, sheet_name=SheetName, header=None)

            RowHeaderIdx, ColOrigemIdx, ColDestinoIdx = -1, -1, -1
            for i in range(min(15, len(DfRaw))):
                RowVals = [str(x).strip().upper() for x in DfRaw.iloc[i].values]
                if 'ORIGEM' in RowVals and 'DESTINO' in RowVals:
                    RowHeaderIdx = i
                    for idx, val in enumerate(RowVals):
                        if val == 'ORIGEM': ColOrigemIdx = idx
                        elif val == 'DESTINO': ColDestinoIdx = idx
                    break
            
            if RowHeaderIdx == -1: return False, "Colunas Origem/Destino não encontradas."

            MapServicos = {}
            RowServicosIdx = RowHeaderIdx - 1
            for col in range(len(DfRaw.columns)):
                if col in [ColOrigemIdx, ColDestinoIdx]: continue
                NomeServico = str(DfRaw.iloc[RowServicosIdx, col]).strip()
                if NomeServico and NomeServico.upper() not in ['NAN', 'NONE', '', 'N/A'] and " X " not in NomeServico.upper():
                    MapServicos[col] = NomeServico

            if not MapServicos: return False, "Nenhum serviço identificado."

            NovaRemessa = RemessaFrete(
                DataReferencia=datetime.now().date(),
                NomeArquivoOriginal=arquivo.filename,
                UsuarioResponsavel=usuario,
                Ativo=True
            )
            Sessao.add(NovaRemessa)
            Sessao.flush()

            ListaInsert = []
            for i in range(RowHeaderIdx + 1, len(DfRaw)):
                Row = DfRaw.iloc[i]
                RowOrigem = str(Row[ColOrigemIdx]).strip().upper()
                RowDestino = str(Row[ColDestinoIdx]).strip().upper()
                
                if RowOrigem in ['', 'NAN'] or RowDestino in ['', 'NAN']: continue
                
                Origens = [o.strip() for o in RowOrigem.split('/')]
                for Origem in Origens:
                    for ColIdx, NomeServico in MapServicos.items():
                        ValorTarifa = TabelaFreteService._NormalizarTarifa(Row[ColIdx])
                        if ValorTarifa is not None:
                            CiaBruta = NomeServico.split(' ')[0].upper()
                            CiaNormalizada = TabelaFreteService._NormalizarNomeCia(CiaBruta)

                            ListaInsert.append(TabelaFrete(
                                IdRemessa=NovaRemessa.Id,
                                Origem=Origem,
                                Destino=RowDestino,
                                CiaAerea=CiaNormalizada, 
                                Servico=NomeServico,
                                Tarifa=ValorTarifa
                            ))

            Sessao.bulk_save_objects(ListaInsert)
            Sessao.commit()
            return True, f"Sucesso! {len(ListaInsert)} tarifas importadas."

        except Exception as e:
            Sessao.rollback()
            LogService.Error("TabelaFreteService", "Erro processamento", e)
            return False, f"Erro técnico: {str(e)}"
        finally:
            if os.path.exists(Caminho): os.remove(Caminho)
            Sessao.close()
            
    @staticmethod
    def CalcularCustoEstimado(origem, destino, cia, peso):
        """
        Estratégia Tripla com Tratamento de NULL (Penalidade Virtual)
        CORREÇÃO: O Fallback SQL agora respeita a Cia Aérea para evitar mistura de dados (Logo GOL com Tarifa LATAM).
        """
        Sessao = ObterSessaoSqlServer()
        try:
            cia_normalizada = TabelaFreteService._NormalizarNomeCia(cia)
            origem = origem.strip().upper()
            destino = destino.strip().upper()

            # --- ESTRATEGIA 1: ORM Match Exato (Ignorando NULLs) ---
            QueryBase = Sessao.query(TabelaFrete).join(RemessaFrete).filter(
                RemessaFrete.Ativo == True,
                func.upper(func.trim(TabelaFrete.Origem)) == origem,
                func.upper(func.trim(TabelaFrete.Destino)) == destino,
                TabelaFrete.Tarifa != None 
            )

            Item = QueryBase.filter(TabelaFrete.CiaAerea.like(f"%{cia_normalizada}%")).order_by(TabelaFrete.Tarifa.asc()).first()
            
            # --- ESTRATEGIA 2: Fallback ORM (Qualquer Cia Válida) ---
            # ATENÇÃO: Se quiser ser RÍGIDO e nunca misturar cias, comente este bloco if/Item!
            # Mas geralmente mantemos para ter algum preço de referência se a cia principal falhar.
            # Se o problema persistir, podemos remover isso também.
            if not Item:
                # Tenta buscar especificamente a cia solicitada primeiro
                pass 

            # Retorno ORM
            if Item and Item.Tarifa is not None:
                vl_tarifa = float(Item.Tarifa)
                # Garante que devolvemos o nome da cia da tarifa encontrada, para o front saber se houve troca
                return vl_tarifa * float(peso), {
                    'tarifa_base': vl_tarifa,
                    'servico': Item.Servico,
                    'cia_tarifaria': Item.CiaAerea, 
                    'peso_calculado': float(peso),
                    'tarifa_missing': False 
                }
            
            # --- ESTRATEGIA 3: HARDCORE SQL (Fallback Final) ---
            # CORREÇÃO: Adicionado filtro de CIA para não pegar tarifa da concorrência
            LogService.Warning("TarifaMiss", f"ORM falhou para {origem}->{destino} ({cia_normalizada}). Tentando SQL Direto...")
            
            sql_raw = text("""
                SELECT TOP 1 F.Tarifa, F.Servico, F.CiaAerea
                FROM intec.dbo.Tb_PLN_Frete F
                INNER JOIN intec.dbo.Tb_PLN_RemessaFrete RF ON F.IdRemessa = RF.Id
                WHERE RF.Ativo = 1 
                  AND RTRIM(LTRIM(F.Origem)) = :origem 
                  AND RTRIM(LTRIM(F.Destino)) = :destino
                  AND F.CiaAerea LIKE :cia  -- <--- O FILTRO QUE FALTAVA
                -- Ordena: Preços válidos primeiro, NULL por último
                ORDER BY CASE WHEN F.Tarifa IS NULL THEN 1 ELSE 0 END, F.Tarifa ASC
            """)
            
            # Passamos o parâmetro cia com wildcards para flexibilidade (ex: %GOL%)
            param_cia = f"%{cia_normalizada}%"
            result = Sessao.execute(sql_raw, {'origem': origem, 'destino': destino, 'cia': param_cia}).first()
            
            if result:
                if result.Tarifa is None:
                    LogService.Warning("TarifaNull", f"Tarifa NULL (Bloqueada) para {origem}->{destino}. Aplica Penalidade.")
                    return 0.0, {
                        'tarifa_base': 0.0,
                        'servico': result.Servico,
                        'cia_tarifaria': result.CiaAerea,
                        'peso_calculado': float(peso),
                        'tarifa_missing': True # Penalidade
                    }
                else:
                    vl_tarifa = float(result.Tarifa)
                    return vl_tarifa * float(peso), {
                        'tarifa_base': vl_tarifa,
                        'servico': result.Servico,
                        'cia_tarifaria': result.CiaAerea,
                        'peso_calculado': float(peso),
                        'tarifa_missing': False
                    }

            LogService.Error("TarifaFatal", f"Nenhuma tarifa da {cia_normalizada} encontrada para {origem}->{destino}")
            return 0.0, {'tarifa_missing': True}

        except Exception as e:
            LogService.Error("TabelaFreteService", f"Erro crítico calc {origem}->{destino}", e)
            return 0.0, {'tarifa_missing': True}
        finally:
            Sessao.close()