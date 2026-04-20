"""
RouteMLEngine — Motor de Aprendizado Contínuo para Rotas
=========================================================

O QUE É ISSO?
─────────────
Este módulo implementa um sistema de aprendizado de máquina que melhora
as recomendações de rota ao longo do tempo, aprendendo com as decisões
reais dos planejadores.

Em termos simples: toda vez que um planejador abre a tela de planejamento
e SALVA uma rota, o sistema registra "foram apresentadas N opções, e o
planejador escolheu esta aqui". Com o tempo, ele aprende padrões como:
  - "Rotas com GOL + 0 escalas são escolhidas 80% das vezes para perecíveis"
  - "Custo acima de R$12.000 raramente é aprovado, mesmo com 0 escalas"
  - "Trocas de CIA em conexões para o Nordeste têm histórico ruim"

Esse aprendizado é aplicado como um AJUSTE (bônus/penalidade) no score
de cada rota candidata durante a próxima análise.

COMO FUNCIONA — CICLO DE VIDA
──────────────────────────────

    ANÁLISE   → RegistrarSessaoAnalise()
                             Chamado dentro de RouteIntelligenceService.BuscarOpcoesDeRotas().
               Grava todas as rotas apresentadas + métricas de cada uma.
               Banco: Tb_PLN_ML_SessaoAnalise + Tb_PLN_ML_CandidatoSessao

  ESCOLHA   → VincularPlanejamento()
               Chamado quando o planejador SALVA um planejamento.
               Marca qual categoria foi escolhida (FoiEscolhida = True).
               As demais ficam com FoiEscolhida = False (exemplos negativos).
               Dispara auto-treino em thread background se há amostras suficientes.

  TREINO    → Treinar() / _verificar_e_treinar_automatico()
               Lê todo o histórico vinculado. Treina GradientBoostingClassifier.
               Salva modelo em: Data/ML_Models/modelo_rotas.joblib
               Dispara automaticamente a cada novo vínculo (mín. MIN_AMOSTRAS).

  PREDIÇÃO  → PredizirBonus()
               Consultado para cada candidato em _calcular_scores().
               Retorna ±pontos de ajuste APENAS quando o modelo está confiante
               (|prob - 0.5| > CONFIANCA_MINIMA). Sem modelo treinado = 0 pontos.

RELAÇÃO COM O SCORE ALGORÍTMICO
────────────────────────────────
    O score base (RouteIntelligenceService._calcular_scores) vale tipicamente ~5–130 pontos.
    O ajuste ML vale no máximo ±13 pontos.
  Score MENOR = rota MELHOR (ranking ascendente).
  O ML nunca domina sozinho — é um refinamento sobre a lógica determinística.

Treinar manualmente via script:
  from Services.Logic.RouteMLEngine import RouteMLEngine
  print(RouteMLEngine.Treinar(usuario='admin'))
  print(RouteMLEngine.Status())
"""

import json
import threading
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

    # ─────────────────────────────────────────────────────────────────────────────
    # VETOR DE FEATURES — O que o modelo aprende e o que cada uma representa
    #
    # A ORDEM é contrato: deve ser idêntica em treino, predição e banco de dados.
    # Para adicionar uma feature nova: inclua aqui, em RegistrarSessaoAnalise,
    # em _ler_historico_db e em _calcular_scores (RouteIntelligenceService).
    # ─────────────────────────────────────────────────────────────────────────────
    FEATURES: list[str] = [
        # Tempo total da rota em minutos. Mais rápido = historicamente mais escolhido.
        'duracao',

        # Custo estimado total (R$) para o peso da remessa nesta rota.
        # Valor 0 com sem_tarifa=True significa "sem precificação" — não é gratuito.
        'custo',

        # Número de conexões (escalas). Cada escala = risco de extravio e atraso.
        'escalas',

        # Quantas vezes a carga muda de companhia aérea ao longo da rota.
        # Troca de CIA = SLA diferente por trecho, mais manuseio, mais risco.
        'trocas_cia',

        # Média do score de parceria das CIAs envolvidas na rota (0–100).
        # Reflete histórico de cumprimento de prazos e acordos comerciais.
        'indice_parceria',

        # 1 se algum trecho da rota não tem tarifa cadastrada no sistema.
        # Custo será estimado — imprecisão que o planejador geralmente evita.
        'sem_tarifa',

        # 1 se a carga é PERECÍVEL e o serviço contratado é EXPRESSO (ambos juntos).
        # Nesse cenário, planejadores consistentemente priorizam velocidade sobre custo.
        'eh_perecivel_expresso',

        # 1 se o serviço disponível na rota bate com o serviço contratado pelo cliente.
        # Ex.: cliente pediu "GOL LOG SAÚDE" e a rota oferece "GOL LOG SAÚDE".
        'servico_alinhado',
    ]

    _modelo: Optional[object] = None
    _scaler: Optional[object] = None
    _aeroportos_conhecidos: Optional[set] = None
    _treinando: bool = False  # flag para evitar treinamentos concorrentes

    # Limiar de confiança do modelo. O ajuste ML só é aplicado quando
    # |prob - 0.5| > CONFIANCA_MINIMA. Evita que sinais fracos (prob ≈ 0.5)
    # gerem ruído no ranking dos candidatos.
    CONFIANCA_MINIMA: float = 0.25

    # Mínimo de novas amostras desde o último treino para disparar re-treino automático.
    DELTA_RETREINO_MIN: int = 10

    # ─────────────────────────────────────────────────────────────────────────
    # PREDIÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def PredizirBonus(cls, features: dict, aero_orig: str = None, aero_dest: str = None) -> float:
        """
        Ajusta o score de uma rota candidata com base no aprendizado histórico.

        COMO FUNCIONA:
          O modelo foi treinado com as decisões reais dos planejadores. Para cada
          sessão de análise, sabe-se quais rotas foram apresentadas e qual foi escolhida.
          O GradientBoostingClassifier aprende padrões implícitos nessas decisões.

          A saída do modelo é uma PROBABILIDADE (0.0–1.0):
            "qual a chance de esta rota ser escolhida, dado seu perfil de features?"

          Essa probabilidade é convertida em ajuste de score:
            - prob ≈ 1.0  → bônus negativo  (score cai  → rota SOBE no ranking)  ✓
            - prob ≈ 0.0  → penalidade      (score sobe → rota DESCE no ranking) ✗
            - prob ≈ 0.5  → modelo incerto  → ajuste ZERO (não aplica)

        LIMIAR DE CONFIANÇA:
          O ajuste só é aplicado quando |prob - 0.5| > CONFIANCA_MINIMA (padrão: 0.25).
          Quando o modelo está em dúvida, o score algorítmico de RouteConfig já basta.
          Isso evita que predições fracas contaminem o ranking.

        Retorna 0.0 se: modelo não treinado | aeroporto fora da cobertura | confiança baixa.
        Escala máxima do ajuste: ±13 pontos (sobre um score base típico de 5–130).
        """
        if not cls._carregar_modelo():
            return 0.0

        # Aeroportos que o modelo nunca viu durante o treinamento → sem base histórica
        if cls._aeroportos_conhecidos and (aero_orig or aero_dest):
            orig_ok = (not aero_orig) or (aero_orig in cls._aeroportos_conhecidos)
            dest_ok = (not aero_dest) or (aero_dest in cls._aeroportos_conhecidos)
            if not orig_ok or not dest_ok:
                return 0.0

        X    = np.array([[features.get(f, 0) for f in cls.FEATURES]])
        prob = cls._modelo.predict_proba(cls._scaler.transform(X))[0][1]

        # Só aplica o ajuste quando o modelo está suficientemente confiante
        confianca = abs(prob - 0.5)
        if confianca < cls.CONFIANCA_MINIMA:
            return 0.0

        # Fórmula: (0.5 - prob) × 26
        #   prob = 0.9 → (0.5 - 0.9) × 26 = −10.4  (bônus: rota favorecida)
        #   prob = 0.1 → (0.5 - 0.1) × 26 = +10.4  (penalidade: rota desfavorecida)
        return (0.5 - prob) * 26.0

    @classmethod
    def ExplicarDecisao(cls, features: dict, aero_orig: str = None, aero_dest: str = None) -> dict:
        """
        Retorna um dicionário legível explicando por que o ML ajusta (ou não) o score
        de uma rota. Útil para logging detalhado, auditoria e telas de diagnóstico futuras.

        Exemplo de retorno quando aplicado:
          {
            'aplicado':  True,
            'prob':      0.87,
            'ajuste':    -9.6,
            'direcao':   'favorável',
            'confianca': 'alta',
            'principais_fatores': [
              {'feature': 'escalas',        'importancia': 0.350, 'valor': 0},
              {'feature': 'custo',          'importancia': 0.280, 'valor': 1250.0},
              {'feature': 'indice_parceria','importancia': 0.200, 'valor': 85.0},
            ]
          }

        Exemplo quando não aplicado:
          {'aplicado': False, 'motivo': 'confiança insuficiente (0.12 < 0.25)'}
        """
        if not cls._carregar_modelo():
            return {'aplicado': False, 'motivo': 'modelo não treinado'}

        if cls._aeroportos_conhecidos and (aero_orig or aero_dest):
            orig_ok = (not aero_orig) or (aero_orig in cls._aeroportos_conhecidos)
            dest_ok = (not aero_dest) or (aero_dest in cls._aeroportos_conhecidos)
            if not orig_ok or not dest_ok:
                return {'aplicado': False, 'motivo': f'aeroporto fora da cobertura ({aero_orig}/{aero_dest})'}

        X         = np.array([[features.get(f, 0) for f in cls.FEATURES]])
        prob      = cls._modelo.predict_proba(cls._scaler.transform(X))[0][1]
        confianca = abs(prob - 0.5)

        if confianca < cls.CONFIANCA_MINIMA:
            return {
                'aplicado': False,
                'prob':     round(prob, 3),
                'motivo':   f'confiança insuficiente ({confianca:.2f} < {cls.CONFIANCA_MINIMA})',
            }

        ajuste = (0.5 - prob) * 26.0
        nivel  = 'muito alta' if confianca > 0.4 else ('alta' if confianca > 0.3 else 'moderada')

        # Identifica as features que mais influenciaram a decisão do modelo
        importancias  = cls._modelo.feature_importances_
        contribuicoes = sorted(
            zip(cls.FEATURES, importancias, [features.get(f, 0) for f in cls.FEATURES]),
            key=lambda x: -x[1],
        )
        principais = [
            {'feature': f, 'importancia': round(float(imp), 3), 'valor': round(float(val), 4)}
            for f, imp, val in contribuicoes[:3]
        ]

        return {
            'aplicado':           True,
            'prob':               round(prob, 3),
            'ajuste':             round(ajuste, 1),
            'direcao':            'favorável' if ajuste < 0 else 'desfavorável',
            'confianca':          nivel,
            'principais_fatores': principais,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # REGISTRO DE SESSÃO (chamado dentro de RouteIntelligenceService.BuscarOpcoesDeRotas)
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
            from Services.Logic.RouteConfig import ContextoRota, REGRAS_BUSCA_PADRAO, resolver_contexto

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
                        IndiceParceria=float(f.get('indice_parceria', REGRAS_BUSCA_PADRAO.score_parceria_padrao)),
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

            # Dispara auto-treino em background sem bloquear o fluxo principal
            threading.Thread(
                target=cls._verificar_e_treinar_automatico,
                args=('sistema',),
                daemon=True,
                name='ml-auto-treino',
            ).start()

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
                        # False (não None) — coluna FoiEscolhida é NOT NULL no banco
                        candidato.FoiEscolhida = False
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

        # Loga os fatores mais decisivos para facilitar diagnóstico
        top3     = sorted(importancias.items(), key=lambda x: -x[1])[:3]
        top3_fmt = ', '.join(f"{k}={v:.1%}" for k, v in top3)
        LogService.Info("RouteIntelligence", f"ML: principais fatores do novo modelo: {top3_fmt}")

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
    # AUTO-TREINO (chamado em background após VincularPlanejamento)
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def _verificar_e_treinar_automatico(cls, usuario: str = 'sistema') -> None:
        """
        Verificação silenciosa — chamada em thread daemon após cada vínculo de planejamento.

        Regra de disparo:
          - Primeiro treino : total_amostras >= MIN_AMOSTRAS e nenhum modelo ativo.
          - Re-treino       : novas amostras desde o último treino >= max(DELTA_RETREINO_MIN,
                              20 % do total de amostras do último treino).

        Nunca levanta exceção; nunca bloqueia a thread principal.
        """
        if cls._treinando:
            return
        try:
            cls._treinando = True
            from Conexoes import ObterSessaoSqlServer
            from Models.SQL_SERVER.MachineLearning import ML_CandidatoSessao, ML_ModeloVersao, ML_SessaoAnalise

            db = ObterSessaoSqlServer()
            try:
                total = (
                    db.query(ML_CandidatoSessao)
                    .join(ML_SessaoAnalise, ML_CandidatoSessao.IdSessao == ML_SessaoAnalise.IdSessao)
                    .filter(ML_SessaoAnalise.IdPlanejamento != None)
                    .count()
                )
                if total < cls.MIN_AMOSTRAS:
                    LogService.Debug(
                        "RouteIntelligence",
                        f"ML auto-treino: {total}/{cls.MIN_AMOSTRAS} amostras — aguardando mais dados",
                    )
                    return

                modelo_ativo = db.query(ML_ModeloVersao).filter_by(IsAtivo=True).first()
                ultimo_total = modelo_ativo.TotalAmostras if modelo_ativo else 0
                novas        = total - ultimo_total
                delta_min    = max(cls.DELTA_RETREINO_MIN, int(ultimo_total * 0.20))

                if ultimo_total == 0:
                    LogService.Info(
                        "RouteIntelligence",
                        f"ML auto-treino: {total} amostras disponíveis — primeiro treinamento",
                    )
                elif novas >= delta_min:
                    LogService.Info(
                        "RouteIntelligence",
                        f"ML auto-treino: +{novas} novas amostras (mín={delta_min}) — re-treinamento",
                    )
                else:
                    LogService.Debug(
                        "RouteIntelligence",
                        f"ML auto-treino: +{novas}/{delta_min} novas amostras — re-treino ainda não necessário",
                    )
                    return
            finally:
                db.close()

            resultado = cls.Treinar(usuario=usuario)
            LogService.Info("RouteIntelligence", f"ML auto-treino concluído: {resultado}")

        except Exception as e:
            LogService.Warning("RouteIntelligence", f"ML: auto-treino falhou silenciosamente: {e}")
        finally:
            cls._treinando = False

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
        from Services.Logic.RouteConfig import REGRAS_BUSCA_PADRAO

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
                    'indice_parceria':       float(c.IndiceParceria or REGRAS_BUSCA_PADRAO.score_parceria_padrao),
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
