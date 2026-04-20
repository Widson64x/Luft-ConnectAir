from dataclasses import dataclass, replace
from typing import Callable


# ─────────────────────────────────────────────────────────────────────────────
#  PESOS DO ALGORITMO DE SCORE
#  Altere aqui para ajustar o comportamento do roteamento sem tocar na lógica.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ScoringWeights:
    """
    Todos os pesos fixos são expressos em uma escala de 0–100 pontos.
    Score MENOR = rota MELHOR; o candidato com menor total vence.

    Ordem por impacto máximo (maior → menor):
      sem_tarifa / custo_alto (100) > perecível desalinhado (65) > serviço alinhado (35)
      > escala (20/hop) > multiplicadores contínuos > troca de CIA (2) > desvio (3)
    """

    # ─── 1. PENALIDADES ABSOLUTAS — impacto máximo ────────────────────────────
    # Acionadas quando a situação é inviável: custo desconhecido ou aprovação impossível.
    penalidade_sem_tarifa: float = 100.0   # sem tarifa → não sabemos o custo real
    penalidade_custo_alto: float = 100.0   # custo acima do limiar → inviável para aprovação

    # ─── 2. PERECÍVEL E SERVIÇO CONTRATADO ────────────────────────────────────
    # Define se a rota é adequada para o tipo de carga e o contrato do cliente.
    # Juntos formam um delta de 100 pts: erro = +65, acerto = −35.
    penalidade_perecivel_desalinhado: float = 65.0   # perecível expresso sem serviço correto
    bonus_servico_alinhado:           float = 35.0   # serviço correto → rota favorecida

    # ─── 3. ESCALAS E TROCAS DE CIA ───────────────────────────────────────────
    # 20 pts por escala ≈ equivale a 2 800 min de voo direto.
    # Deliberadamente alto: conexões só vencem quando não há alternativa direta.
    peso_conexao:         float = 20.0   # pts por escala (conexão intermediária)
    penalidade_troca_cia: float = 2.0    # pts por troca de companhia em escala

    # ─── 4. MULTIPLICADORES CONTÍNUOS ─────────────────────────────────────────
    # Aplicados sobre valores reais; o impacto cresce proporcionalmente ao valor.
    #   peso_tempo:  rota de 300 min  → +2.1 pts   |  rota de 600 min  → +4.2 pts
    #   peso_custo:  tarifa R$ 5.000  → +5.0 pts   |  tarifa R$ 10.000 → +10 pts
    peso_tempo:  float = 0.007   # pts/minuto
    peso_custo:  float = 0.001   # pts/R$

    # ─── 5. PARCERIA DAS CIAS ──────────────────────────────────────────────────
    # Bônus exponencial: CIAs premium são desproporcionalmente mais valorizadas.
    # fator_parceria: expoente da curva (>1 = separação forte entre scores)
    # divisor_parceria: calibra a magnitude → score 100 ≈ +2 pts de bônus
    fator_parceria:   float = 2.2
    divisor_parceria: float = 7_500.0

    # ─── 6. DESVIO GEOGRÁFICO ──────────────────────────────────────────────────
    # Penaliza rotas com retrocesso: razão dist_percorrida / dist_direta − 1.
    # Ex.: desvio 1.5× (50% além do direto) → (1.5 − 1.0) × 3 = 1.5 pts.
    penalidade_desvio: float = 3.0

    # ─── LIMIARES EM R$ (não são pesos de score) ──────────────────────────────
    # Usados para classificar o custo antes de aplicar a penalidade correta.
    limiar_custo_alto:        float = 14_000.0
    limiar_custo_recomendada: float = 10_000.0


PESOS_PADRAO = ScoringWeights()


# ─────────────────────────────────────────────────────────────────────────────
#  REGRAS OPERACIONAIS DE BUSCA
#  Estas regras valem para qualquer engine de roteamento (grafo, ML, IA, etc.).
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RouteSearchRules:
    """
    Parâmetros operacionais compartilhados por todos os montadores de rota.
    A ideia é centralizar aqui tudo que não depende da engine em si.
    """

    dias_adicionais_busca: int = 30
    max_trechos: int = 3
    min_horas_conexao: int = 3
    max_horas_conexao: int = 36
    score_parceria_padrao: float = 50.0
    score_parceria_minimo_elegivel: float = 0.0
    limiar_bonus_ml_relevante: float = 1.0

    @property
    def max_conexoes(self) -> int:
        return max(0, self.max_trechos - 1)


REGRAS_BUSCA_PADRAO = RouteSearchRules()


# ─────────────────────────────────────────────────────────────────────────────
#  CONTEXTO DA BUSCA
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ContextoRota:
    """Encapsula o tipo de carga e o serviço contratado para a busca."""

    tipo_carga:         str
    servico_contratado: str

    def __post_init__(self):
        self.tipo_carga         = (self.tipo_carga or 'GERAL').upper().strip()
        self.servico_contratado = (self.servico_contratado or 'PADRÃO').upper().strip()

    @property
    def eh_perecivel(self) -> bool:
        return self.tipo_carga == 'PERECIVEL'

    @property
    def eh_expresso(self) -> bool:
        return 'EXPRESSO' in self.servico_contratado

    @property
    def eh_perecivel_expresso(self) -> bool:
        return self.eh_perecivel and self.eh_expresso


# ─────────────────────────────────────────────────────────────────────────────
#  DEPARA DE SERVIÇOS IDEAIS
#  Ordem importa: o primeiro predicado que der True vence.
#  Para mudar regras, altere APENAS esta lista — não toque na lógica do serviço.
# ─────────────────────────────────────────────────────────────────────────────
#
#  Estrutura de cada regra:
#    (predicado: ContextoRota → bool, [serviços ideais], {multiplicadores de pesos})
#
#  Multiplicadores disponíveis: 'peso_tempo', 'peso_custo'
#  (ex.: 0.0 zera o fator, 5.0 multiplica por 5)
#
ServicoRule = tuple[Callable[['ContextoRota'], bool], list[str], dict[str, float]]

REGRAS_SERVICO: list[ServicoRule] = [
    (
        lambda ctx: ctx.eh_perecivel_expresso,
        ['GOL LOG SAÚDE', 'GOL LOG RAPIDO', 'LATAM EXPRESSO (VELOZ)', 'LATAM RESERVADO'],
        {'peso_custo': 0.0, 'peso_tempo': 5.0},
    ),
    (
        lambda ctx: ctx.eh_expresso,
        ['GOL LOG SAÚDE', 'GOL LOG RAPIDO', 'GOL LOG ECONOMICO (SBY)',
         'LATAM CONVENCIONAL (ESTANDAR MEDS)', 'LATAM EXPRESSO (VELOZ)', 'LATAM RESERVADO'],
        {'peso_custo': 0.5, 'peso_tempo': 3.0},
    ),
    (
        lambda ctx: True,   # default — sempre casa
        ['GOL LOG ECONOMICO (SBY)', 'LATAM CONVENCIONAL (ESTANDAR MEDS)'],
        {},
    ),
]


def resolver_contexto(ctx: ContextoRota) -> tuple[list[str], ScoringWeights]:
    """
    Aplica as REGRAS_SERVICO e retorna (serviços_ideais, pesos_dinâmicos).
    Os pesos base do PESOS_PADRAO são mantidos; apenas os multiplicadores da regra são aplicados.
    """
    for predicado, servicos, mult in REGRAS_SERVICO:
        if predicado(ctx):
            pesos = replace(
                PESOS_PADRAO,
                peso_tempo=PESOS_PADRAO.peso_tempo * mult.get('peso_tempo', 1.0),
                peso_custo=PESOS_PADRAO.peso_custo * mult.get('peso_custo', 1.0),
            )
            return servicos, pesos
    return [], PESOS_PADRAO


def normalizar_iatas(iatas: str | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(iatas, str):
        iatas = [iatas]
    return [str(iata or '').strip().upper() for iata in iatas if str(iata or '').strip()]
