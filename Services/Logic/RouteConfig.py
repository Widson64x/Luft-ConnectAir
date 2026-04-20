from dataclasses import dataclass, replace
from typing import Callable


# ─────────────────────────────────────────────────────────────────────────────
#  PESOS DO ALGORITMO DE SCORE
#  Altere aqui para ajustar o comportamento do roteamento sem tocar na lógica.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ScoringWeights:
    peso_tempo:                         float = 1.0
    peso_conexao:                       float = 3_000.0  # Penalidade por escala — favorece esperar um voo direto
    peso_custo:                         float = 0.15
    fator_parceria:                     float = 2.2
    penalidade_sem_tarifa:              float = 15_000.0
    penalidade_custo_alto:              float = 15_000.0
    penalidade_troca_cia:               float = 300.0
    penalidade_desvio:                  float = 400.0   # Por múltiplo de distância direta (retrocesso geográfico)
    bonus_servico_alinhado:             float = 5_000.0
    penalidade_perecivel_desalinhado:   float = 10_000.0
    limiar_custo_alto:                  float = 14_000.0
    limiar_custo_recomendada:           float = 10_000.0


PESOS_PADRAO = ScoringWeights()


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
