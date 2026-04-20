"""
RouteMLEngine — Motor de Aprendizado Contínuo para Rotas
=========================================================

Fluxo:
  1. BuscarOpcoesDeRotas() (MalhaService)
         → chama RegistrarSessaoAnalise() internamente logo após AnalisarEEncontrarRotas()
         → grava Tb_PLN_ML_SessaoAnalise + Tb_PLN_ML_CandidatoSessao
  2. salvarPlanejamento() (Routes/Planejamento.py)
         → chama VincularPlanejamento() para marcar a escolha do planejador
         → vincula a sessão ao Tb_PLN_PlanejamentoCabecalho e seta FoiEscolhida = 1
  3. Treinar(usuario)  — manual/periódico
         → lê histórico do banco (min. 20 candidatos vinculados)
         → treina GradientBoostingClassifier, salva .joblib em Models/ML_Models/
         → grava metadados em Tb_PLN_ML_ModeloVersao + Tb_PLN_ML_FeatureImportancia
  4. PredizirBonus(features)  — interno, chamado em _calcular_scores
         → zero impacto enquanto não houver modelo treinado

Treinar via script:
  from Services.Logic.RouteMLEngine import RouteMLEngine
  print(RouteMLEngine.Treinar(usuario='admin'))
  print(RouteMLEngine.Status())
"""

import json
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Optional

from Configuracoes import ConfiguracaoAtual
from Services.LogService import LogService

try:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import cross_val_score
    import joblib
    _ML_DISPONIVEL = True
except ImportError:
    _ML_DISPONIVEL = False


class RouteMLEngine:
    """
    Motor de aprendizado para melhoria contínua das recomendações de rota.
    Usa GradientBoostingClassifier treinado com o histórico de decisões dos planejadores.

    Armazenamento histórico: Tb_PLN_ML_SessaoAnalise + Tb_PLN_ML_CandidatoSessao (SQL Server)
    Modelo binário:          Models/ML_Models/modelo_rotas.joblib (joblib)
    Versionamento de modelo: Tb_PLN_ML_ModeloVersao + Tb_PLN_ML_FeatureImportancia (SQL Server)
    """

    DIR_ML         = Path(ConfiguracaoAtual.DIR_MODELS)
    CAMINHO_MODELO = DIR_ML / "modelo_rotas.joblib"
    MIN_AMOSTRAS   = 20

    # Garante que a pasta existe na inicialização
    DIR_ML.mkdir(parents=True, exist_ok=True)

    # Vetor de features — a ordem DEVE ser respeitada em todo o código
    FEATURES: list[str] = [
        'duracao',
        'custo',
        'escalas',
        'trocas_cia',
        'indice_parceria',
        'sem_tarifa',
        'eh_perecivel_expresso',
        'servico_alinhado',
    ]

    _modelo: Optional[object] = None
    _scaler: Optional[object] = None
    _aeroportos_conhecidos: Optional[set] = None

    # ─────────────────────────────────────────────────────────────────────────
    # PREDIÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def PredizirBonus(cls, features: dict, aero_orig: str = None, aero_dest: str = None) -> float:
        """
        Retorna um ajuste de score baseado no histórico de decisões.
        Escala: +/- 2 000 pontos. Retorna 0.0 se o modelo não estiver treinado
        ou se origem/destino não foram vistos durante o treinamento.

        Interpretação:
          - prob ≈ 1.0 (muito provável ser escolhida) → bônus de -2 000 (score cai = melhor posição)
          - prob ≈ 0.0 (raramente escolhida)          → penalidade de +2 000
          - prob ≈ 0.5 (modelo incerto)               → sem impacto
        """
        if not cls._carregar_modelo():
            return 0.0
        # Aeroportos fora do conjunto de treinamento → modelo não tem base para opinar
        if cls._aeroportos_conhecidos and (aero_orig or aero_dest):
            orig_ok = (not aero_orig) or (aero_orig in cls._aeroportos_conhecidos)
            dest_ok = (not aero_dest) or (aero_dest in cls._aeroportos_conhecidos)
            if not orig_ok or not dest_ok:
                return 0.0
        X = np.array([[features.get(f, 0) for f in cls.FEATURES]])
        prob = cls._modelo.predict_proba(cls._scaler.transform(X))[0][1]
        return (0.5 - prob) * 4_000.0

    # ─────────────────────────────────────────────────────────────────────────
    # REGISTRO DE SESSÃO (chamado dentro de BuscarOpcoesDeRotas)
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def RegistrarSessaoAnalise(
        cls,
        opcoes_brutas: dict,
        filial: str,
        serie: str,
        ctc: str,
        tipo_carga: str,
        servico_contratado: str,
        usuario: str = '',
    ) -> Optional[int]:
        """
        Persiste a sessão de análise e cada candidato de rota no banco de dados.
        Deve ser chamado com OpcoesBrutas (vindas de AnalisarEEncontrarRotas),
        antes da formatação visual — os candidatos ainda carregam '_ml_features',
        '_score_base' e '_bonus_ml'.

        Retorna o IdSessao criado, ou None em caso de falha.
        Nunca levanta exceção — o fluxo principal nunca deve ser bloqueado aqui.
        """
        try:
            from Conexoes import ObterSessaoSqlServer
            from Models.SQL_SERVER.MachineLearning import ML_SessaoAnalise, ML_CandidatoSessao
            from Services.Logic.RouteConfig import ContextoRota, resolver_contexto

            ctx = ContextoRota(tipo_carga, servico_contratado)
            _, pesos = resolver_contexto(ctx)

            candidatos_validos = {k: v for k, v in opcoes_brutas.items() if v and '_ml_features' in v}
            if not candidatos_validos:
                return None

            db = ObterSessaoSqlServer()
            try:
                sessao = ML_SessaoAnalise(
                    Filial=str(filial or ''),
                    Serie=str(serie or ''),
                    Ctc=str(ctc or ''),
                    TipoCarga=str(tipo_carga or ''),
                    ServicoContratado=str(servico_contratado or ''),
                    ContextoDescricao=f"{ctx.tipo_carga}/{ctx.servico_contratado}",
                    PesoTempo=float(pesos.peso_tempo),
                    PesoCusto=float(pesos.peso_custo),
                    TotalCandidatos=len(candidatos_validos),
                    CategoriaPreenchidas=len(candidatos_validos),
                    UsuarioAnalise=str(usuario or ''),
                )
                db.add(sessao)
                db.flush()

                for categoria, candidato in candidatos_validos.items():
                    f = candidato['_ml_features']
                    m = candidato.get('metricas', {})
                    rota_voos = candidato.get('rota', [])
                    aero_orig = rota_voos[0].AeroportoOrigem.strip().upper() if rota_voos else None
                    aero_dest = rota_voos[-1].AeroportoDestino.strip().upper() if rota_voos else None

                    db.add(ML_CandidatoSessao(
                        IdSessao=sessao.IdSessao,
                        Categoria=str(categoria),
                        AeroportoOrigem=aero_orig,
                        AeroportoDestino=aero_dest,
                        Duracao=float(f.get('duracao', 0)),
                        Custo=float(f.get('custo', 0)),
                        Escalas=int(f.get('escalas', 0)),
                        TrocasCia=int(f.get('trocas_cia', 0)),
                        IndiceParceria=float(f.get('indice_parceria', 50)),
                        SemTarifa=bool(f.get('sem_tarifa', 0)),
                        EhPerecivel=bool(f.get('eh_perecivel_expresso', 0)),
                        ServicoAlinhado=bool(f.get('servico_alinhado', 0)),
                        ScoreBase=float(candidato.get('_score_base', m.get('score', 0))),
                        BonusML=float(candidato.get('_bonus_ml', 0)),
                        ScoreFinal=float(m.get('score', 0)),
                        FoiEscolhida=False,
                    ))

                db.commit()
                LogService.Debug(
                    "RouteIntelligence",
                    f"ML: sessão {sessao.IdSessao} registrada "
                    f"({len(candidatos_validos)} candidatos | {filial}-{serie}-{ctc})"
                )
                return sessao.IdSessao
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
        except Exception as e:
            LogService.Warning("RouteIntelligence", f"ML: RegistrarSessaoAnalise falhou silenciosamente: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # VINCULAÇÃO AO PLANEJAMENTO (chamado em salvarPlanejamento)
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def VincularPlanejamento(
        cls,
        filial: str,
        serie: str,
        ctc: str,
        id_planejamento: int,
        categoria_escolhida: str,
    ) -> None:
        """
        Localiza a sessão mais recente ainda não vinculada para o CTC informado,
        vincula-a ao planejamento salvo e marca a categoria escolhida (FoiEscolhida = True).
        As demais categorias da sessão ficam com FoiEscolhida = False (label de treino negativo).
        Nunca levanta exceção.
        """
        try:
            from Conexoes import ObterSessaoSqlServer
            from Models.SQL_SERVER.MachineLearning import ML_SessaoAnalise

            db = ObterSessaoSqlServer()
            try:
                sessao = (
                    db.query(ML_SessaoAnalise)
                    .filter(
                        ML_SessaoAnalise.Filial == str(filial),
                        ML_SessaoAnalise.Serie  == str(serie),
                        ML_SessaoAnalise.Ctc    == str(ctc),
                        ML_SessaoAnalise.IdPlanejamento == None,
                    )
                    .order_by(ML_SessaoAnalise.DataAnalise.desc())
                    .first()
                )
                if not sessao:
                    LogService.Warning(
                        "RouteIntelligence",
                        f"ML: nenhuma sessão não vinculada para {filial}-{serie}-{ctc}"
                    )
                    return

                sessao.IdPlanejamento    = int(id_planejamento)
                sessao.CategoriaEscolhida = str(categoria_escolhida or '')
                sessao.DataVinculo       = datetime.now()

                for candidato in sessao.Candidatos:
                    candidato.FoiEscolhida = (candidato.Categoria == categoria_escolhida)

                db.commit()
                LogService.Debug(
                    "RouteIntelligence",
                    f"ML: sessão {sessao.IdSessao} → planejamento {id_planejamento} "
                    f"(escolha: '{categoria_escolhida}')"
                )
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
        except Exception as e:
            LogService.Warning("RouteIntelligence", f"ML: VincularPlanejamento falhou silenciosamente: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # DESVINCULAÇÃO (chamado em cancelarPlanejamento)
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def DesvincularPlanejamento(cls, id_planejamento: int) -> None:
        """
        Remove o vínculo ML de todas as sessões associadas ao planejamento cancelado.
        Reseta IdPlanejamento, CategoriaEscolhida, DataVinculo e FoiEscolhida dos candidatos,
        para que esses dados não contaminem o treinamento.
        Nunca levanta exceção.
        """
        try:
            from Conexoes import ObterSessaoSqlServer
            from Models.SQL_SERVER.MachineLearning import ML_SessaoAnalise

            db = ObterSessaoSqlServer()
            try:
                sessoes = (
                    db.query(ML_SessaoAnalise)
                    .filter(ML_SessaoAnalise.IdPlanejamento == int(id_planejamento))
                    .all()
                )
                for sessao in sessoes:
                    sessao.IdPlanejamento     = None
                    sessao.CategoriaEscolhida = None
                    sessao.DataVinculo        = None
                    for candidato in sessao.Candidatos:
                        candidato.FoiEscolhida = None
                db.commit()
                LogService.Debug(
                    "RouteIntelligence",
                    f"ML: sessões do planejamento {id_planejamento} desvinculadas."
                )
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
        except Exception as e:
            LogService.Warning("RouteIntelligence", f"ML: DesvincularPlanejamento falhou silenciosamente: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # TREINAMENTO
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def Treinar(cls, usuario: str = 'sistema') -> dict:
        """
        Treina um novo modelo com o histórico acumulado no banco de dados.
        Persiste metadados em Tb_PLN_ML_ModeloVersao e importâncias em
        Tb_PLN_ML_FeatureImportancia. O binário .joblib é salvo em Data/ML/.

        Retorna dict de diagnóstico:
          {'status': 'ok', 'amostras': 42, 'auc_cv': 0.87, 'importancias': {...}}
          {'status': 'amostras_insuficientes', 'amostras': 8, 'necessario': 20}
          {'status': 'sklearn_indisponivel'}
        """
        if not _ML_DISPONIVEL:
            return {'status': 'sklearn_indisponivel — instale scikit-learn e joblib'}

        try:
            registros = cls._ler_historico_db()
        except Exception as e:
            return {'status': f'erro_leitura_db: {e}'}

        n = len(registros)
        if n < cls.MIN_AMOSTRAS:
            return {'status': 'amostras_insuficientes', 'amostras': n, 'necessario': cls.MIN_AMOSTRAS}

        X = np.array([[r.get(f, 0) for f in cls.FEATURES] for r in registros])
        y = np.array([r['escolhida'] for r in registros])

        scaler = StandardScaler()
        X_s    = scaler.fit_transform(X)

        modelo = GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)
        modelo.fit(X_s, y)

        cv_k = min(5, n // 4)
        auc  = float(cross_val_score(modelo, X_s, y, cv=cv_k, scoring='roc_auc').mean())

        # Coleta os aeroportos vistos no treinamento para validação futura de inferência
        aeroportos_conhecidos = set()
        for r in registros:
            if r.get('aero_orig'):
                aeroportos_conhecidos.add(r['aero_orig'])
            if r.get('aero_dest'):
                aeroportos_conhecidos.add(r['aero_dest'])

        cls.DIR_ML.mkdir(parents=True, exist_ok=True)
        caminho = str(cls.CAMINHO_MODELO)
        joblib.dump({'modelo': modelo, 'scaler': scaler, 'aeroportos_conhecidos': aeroportos_conhecidos}, caminho)
        cls._modelo, cls._scaler, cls._aeroportos_conhecidos = modelo, scaler, aeroportos_conhecidos

        importancias = dict(zip(cls.FEATURES, modelo.feature_importances_.tolist()))

        try:
            from Conexoes import ObterSessaoSqlServer
            from Models.SQL_SERVER.MachineLearning import ML_ModeloVersao, ML_FeatureImportancia

            db = ObterSessaoSqlServer()
            try:
                db.query(ML_ModeloVersao).filter_by(IsAtivo=True).update({'IsAtivo': False})
                versao = ML_ModeloVersao(
                    TotalAmostras=n,
                    AucCrossVal=round(auc, 4),
                    IsAtivo=True,
                    CaminhoArquivo=caminho,
                    Algoritmo='GradientBoostingClassifier',
                    ParametrosJson=json.dumps({'n_estimators': 100, 'max_depth': 3, 'random_state': 42}),
                    UsuarioTreino=str(usuario),
                )
                db.add(versao)
                db.flush()
                for nome, imp in importancias.items():
                    db.add(ML_FeatureImportancia(
                        IdModelo=versao.IdModelo,
                        NomeFeature=nome,
                        Importancia=float(imp),
                    ))
                db.commit()
                LogService.Info(
                    "RouteIntelligence",
                    f"ML: modelo v{versao.IdModelo} treinado | {n} amostras | AUC={auc:.3f}"
                )
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
        except Exception as e:
            LogService.Warning("RouteIntelligence", f"ML: falha ao persistir versão do modelo: {e}")

        return {
            'status': 'ok',
            'amostras': n,
            'auc_cv': round(auc, 3),
            'importancias': importancias,
        }

    @classmethod
    def Status(cls) -> dict:
        """Retorna o estado atual do motor ML para diagnóstico e monitoramento."""
        try:
            from Conexoes import ObterSessaoSqlServer
            from Models.SQL_SERVER.MachineLearning import ML_CandidatoSessao, ML_ModeloVersao, ML_SessaoAnalise

            db = ObterSessaoSqlServer()
            try:
                total_candidatos = (
                    db.query(ML_CandidatoSessao)
                    .join(ML_SessaoAnalise, ML_CandidatoSessao.IdSessao == ML_SessaoAnalise.IdSessao)
                    .filter(ML_SessaoAnalise.IdPlanejamento != None)
                    .count()
                )
                total_sessoes = (
                    db.query(ML_SessaoAnalise)
                    .filter(ML_SessaoAnalise.IdPlanejamento != None)
                    .count()
                )
                modelo_ativo = db.query(ML_ModeloVersao).filter_by(IsAtivo=True).first()
                return {
                    'sklearn_disponivel': _ML_DISPONIVEL,
                    'modelo_treinado':    cls.CAMINHO_MODELO.exists(),
                    'sessoes_vinculadas': total_sessoes,
                    'amostras':           total_candidatos,
                    'faltam_para_treino': max(0, cls.MIN_AMOSTRAS - total_candidatos),
                    'ultima_versao': {
                        'id':       modelo_ativo.IdModelo,
                        'data':     str(modelo_ativo.DataTreino),
                        'auc':      modelo_ativo.AucCrossVal,
                        'amostras': modelo_ativo.TotalAmostras,
                    } if modelo_ativo else None,
                }
            finally:
                db.close()
        except Exception as e:
            return {
                'sklearn_disponivel': _ML_DISPONIVEL,
                'modelo_treinado':    cls.CAMINHO_MODELO.exists(),
                'erro': str(e),
            }

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS PRIVADOS
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def _ler_historico_db(cls) -> list[dict]:
        """
        Retorna todos os candidatos de sessões vinculadas a um planejamento.
        Cada item: {feature: valor, ..., 'escolhida': 0/1}
        """
        from Conexoes import ObterSessaoSqlServer
        from Models.SQL_SERVER.MachineLearning import ML_CandidatoSessao, ML_SessaoAnalise

        db = ObterSessaoSqlServer()
        try:
            candidatos = (
                db.query(ML_CandidatoSessao)
                .join(ML_SessaoAnalise, ML_CandidatoSessao.IdSessao == ML_SessaoAnalise.IdSessao)
                .filter(ML_SessaoAnalise.IdPlanejamento != None)
                .all()
            )
            return [
                {
                    'duracao':               float(c.Duracao or 0),
                    'custo':                 float(c.Custo or 0),
                    'escalas':               int(c.Escalas or 0),
                    'trocas_cia':            int(c.TrocasCia or 0),
                    'indice_parceria':       float(c.IndiceParceria or 50),
                    'sem_tarifa':            int(c.SemTarifa or 0),
                    'eh_perecivel_expresso': int(c.EhPerecivel or 0),
                    'servico_alinhado':      int(c.ServicoAlinhado or 0),
                    'escolhida':             int(c.FoiEscolhida or 0),
                    'aero_orig':             str(c.AeroportoOrigem or '').strip().upper() or None,
                    'aero_dest':             str(c.AeroportoDestino or '').strip().upper() or None,
                }
                for c in candidatos
            ]
        finally:
            db.close()

    @classmethod
    def _carregar_modelo(cls) -> bool:
        """Lazy-load: carrega do disco apenas na primeira predição."""
        if cls._modelo is not None:
            return True
        if not _ML_DISPONIVEL or not cls.CAMINHO_MODELO.exists():
            return False
        try:
            bundle = joblib.load(cls.CAMINHO_MODELO)
            cls._modelo  = bundle['modelo']
            cls._scaler  = bundle['scaler']
            cls._aeroportos_conhecidos = bundle.get('aeroportos_conhecidos', set())
            return True
        except Exception:
            return False
