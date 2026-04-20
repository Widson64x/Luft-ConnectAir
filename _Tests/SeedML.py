"""
_Tests/SeedML.py — Gerador de dados sintéticos para testar o ML de rotas
=========================================================================

Insere sessões e candidatos diretamente nas tabelas ML, marcando escolhas
realistas para permitir treinar e validar o modelo sem precisar de planejamentos
reais em produção.

Uso:
    # Gerar 50 sessões sintéticas (usa IDs de planejamentos já existentes no banco)
    python _Tests/SeedML.py --qtd 50

    # Gerar 30 sessões (default)
    python _Tests/SeedML.py

    # Treinar o modelo com os dados gerados
    python _Tests/SeedML.py --treinar

    # Ver status do ML após gerar
    python _Tests/SeedML.py --status

    # Remover APENAS os dados gerados por este script (tag __TESTE__)
    python _Tests/SeedML.py --limpar

Marcação de dados de teste:
    Todas as sessões geradas recebem UsuarioAnalise = '__TESTE__'
    para serem facilmente identificadas e removidas sem afetar dados reais.
"""

import sys
import os
import argparse
import random
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import text
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.MachineLearning import (
    ML_SessaoAnalise,
    ML_CandidatoSessao,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES DE GERAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

TAG_TESTE = '__TESTE__'

# Categorias reais definidas em RouteIntelligenceService._categorizar
CATEGORIAS = [
    'recomendada',
    'direta',
    'rapida',
    'economica',
    'conexao_mesma_cia',
    'interline',
]

AEROPORTOS = [
    ('GRU', 'FOR'), ('GRU', 'SSA'), ('GRU', 'REC'), ('GRU', 'CGH'),
    ('GIG', 'BSB'), ('GIG', 'CWB'), ('CGH', 'POA'), ('BSB', 'MAO'),
    ('SSA', 'FOR'), ('FOR', 'REC'), ('POA', 'GRU'), ('CWB', 'GIG'),
]

# Valores reais normalizados por PlanejamentoService._NormalizarServicoContratado
TIPOS_CARGA = ['SECA', 'SECA', 'SECA', 'SECA', 'REFRIGERADO', 'PERECIVEL']
SERVICOS    = ['ECONÔMICO', 'ECONÔMICO', 'ECONÔMICO', 'EXPRESSO', 'STANDARD']

# Formato real: filial numérica 2 dígitos, serie numérica
FILIAIS = ['26', '27', '28', '34', '51', '52']
SERIES  = ['1', '2', '3']


# ─────────────────────────────────────────────────────────────────────────────
# GERAÇÃO DE CANDIDATOS SINTÉTICOS
# ─────────────────────────────────────────────────────────────────────────────

def _gerar_candidatos(
    num_categorias: int,
    aero_orig: str,
    aero_dest: str,
    peso_tempo: float,
    peso_custo: float,
    eh_perecivel_expresso: bool,
) -> list[dict]:
    """
    Gera entre 2 e num_categorias candidatos com features alinhadas às categorias
    reais do RouteIntelligenceService. Score espelha _calcular_scores:
      menor score = melhor candidato (ordenação ascendente).
    """
    candidatos = []
    categorias = random.sample(CATEGORIAS, k=min(num_categorias, len(CATEGORIAS)))

    for cat in categorias:
        # Distribuição de features coerente com o que cada categoria representa
        if cat == 'rapida':
            duracao  = random.uniform(1.5, 5.0)
            custo    = random.uniform(800, 2500)
            escalas  = random.randint(0, 1)
            trocas_cia = random.choices([0, 1], weights=[70, 30])[0]
        elif cat == 'economica':
            duracao  = random.uniform(5.0, 15.0)
            custo    = random.uniform(150, 700)
            escalas  = random.randint(1, 4)
            trocas_cia = random.choices([0, 1, 2], weights=[50, 35, 15])[0]
        elif cat == 'direta':
            duracao  = random.uniform(2.0, 8.0)
            custo    = random.uniform(400, 1500)
            escalas  = 0
            trocas_cia = 0
        elif cat == 'conexao_mesma_cia':
            duracao  = random.uniform(3.0, 10.0)
            custo    = random.uniform(300, 1200)
            escalas  = random.randint(1, 3)
            trocas_cia = 0
        elif cat == 'interline':
            duracao  = random.uniform(4.0, 12.0)
            custo    = random.uniform(500, 2000)
            escalas  = random.randint(1, 3)
            trocas_cia = random.randint(1, 2)
        else:  # recomendada — equilíbrio entre velocidade e custo
            duracao  = random.uniform(2.0, 8.0)
            custo    = random.uniform(400, 1400)
            escalas  = random.randint(0, 2)
            trocas_cia = random.choices([0, 1], weights=[75, 25])[0]

        indice_parceria  = random.uniform(20, 100)
        sem_tarifa       = random.choices([False, True], weights=[85, 15])[0]
        servico_alinhado = random.choices([True, False], weights=[65, 35])[0]

        # Score espelhando _calcular_scores: menor = melhor
        fator_custo = 15_000.0 if sem_tarifa else custo * peso_custo
        score_base = round(
            duracao          * peso_tempo
            + escalas        * 150.0
            + trocas_cia     * 300.0
            + fator_custo
            - (indice_parceria ** 2.2) / 50.0
            - (5_000.0 if servico_alinhado else 0)
            + random.uniform(-200, 200),   # ruído humano
            2,
        )

        candidatos.append({
            'categoria':        cat,
            'aero_orig':        aero_orig,
            'aero_dest':        aero_dest,
            'duracao':          round(duracao, 2),
            'custo':            round(custo, 2),
            'escalas':          escalas,
            'trocas_cia':       trocas_cia,
            'indice_parceria':  round(indice_parceria, 2),
            'sem_tarifa':       sem_tarifa,
            'eh_perecivel':     eh_perecivel_expresso,
            'servico_alinhado': servico_alinhado,
            'score_base':       score_base,
        })

    return candidatos


def _escolher_categoria(candidatos: list[dict]) -> str:
    """
    Simula a escolha do planejador: geralmente o melhor score,
    mas com 25% de chance de escolher outra (comportamento humano real).
    """
    if not candidatos:
        return ''
    ordenados = sorted(candidatos, key=lambda c: c['score_base'])
    if random.random() < 0.25 and len(ordenados) > 1:
        return random.choice(ordenados[1:])['categoria']
    return ordenados[0]['categoria']


# ─────────────────────────────────────────────────────────────────────────────
# SEED PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def _buscar_ids_planejamento(db, limite: int = 200) -> list[int]:
    """Busca IDs de planejamentos existentes para usar como FK nas sessões de teste."""
    sql = text(
        f"SELECT TOP {int(limite)} IdPlanejamento "
        "FROM [intec].[dbo].[Tb_PLN_PlanejamentoCabecalho] "
        "WHERE Status != 'Cancelado'"
    )
    rows = db.execute(sql).fetchall()
    return [r[0] for r in rows]


def gerar_seed(qtd: int = 30) -> None:
    db = ObterSessaoSqlServer()
    try:
        ids_plan = _buscar_ids_planejamento(db)
        if not ids_plan:
            print("⚠  Nenhum planejamento encontrado no banco.")
            print("   As sessões serão geradas SEM vínculo (IdPlanejamento = NULL).")
            print("   Isso NÃO contará para o treinamento do modelo.\n")
            sem_vinculo = True
        else:
            sem_vinculo = False
            print(f"ℹ  {len(ids_plan)} planejamentos disponíveis para referência de FK.\n")

        geradas = 0
        vinculadas = 0
        total_candidatos = 0

        print(f"🔨 Gerando {qtd} sessões sintéticas...")

        for i in range(qtd):
            filial = random.choice(FILIAIS)
            serie  = random.choice(SERIES)
            ctc    = str(random.randint(1000000000, 9999999999))  # formato real: 10 dígitos numéricos
            tipo_carga = random.choice(TIPOS_CARGA)
            servico    = random.choice(SERVICOS)
            aero_orig, aero_dest = random.choice(AEROPORTOS)

            # Pesos espelhando resolver_contexto() de RouteConfig.py
            eh_perecivel_expresso = (tipo_carga == 'PERECIVEL' and 'EXPRESSO' in servico)
            if eh_perecivel_expresso:
                peso_tempo, peso_custo = 5.0, 0.0
            elif 'EXPRESSO' in servico:
                peso_tempo, peso_custo = 3.0, 0.5
            else:
                peso_tempo, peso_custo = 1.0, 0.15

            # Data retroativa aleatória (últimos 90 dias)
            data_analise = datetime.now() - timedelta(days=random.randint(0, 90),
                                                       hours=random.randint(0, 23))

            num_cats = random.choices([2, 3, 4, 5, 6], weights=[10, 20, 35, 25, 10])[0]
            candidatos = _gerar_candidatos(num_cats, aero_orig, aero_dest, peso_tempo, peso_custo, eh_perecivel_expresso)
            categoria_escolhida = _escolher_categoria(candidatos)

            sessao = ML_SessaoAnalise(
                Filial=filial,
                Serie=serie,
                Ctc=ctc,
                TipoCarga=tipo_carga,
                ServicoContratado=servico,
                ContextoDescricao=f"{tipo_carga}/{servico}",
                PesoTempo=peso_tempo,
                PesoCusto=peso_custo,
                TotalCandidatos=len(candidatos),
                CategoriaPreenchidas=len(candidatos),
                CategoriaEscolhida=categoria_escolhida,
                DataAnalise=data_analise,
                UsuarioAnalise=TAG_TESTE,
            )

            if not sem_vinculo:
                sessao.IdPlanejamento = random.choice(ids_plan)
                sessao.DataVinculo    = data_analise + timedelta(minutes=random.randint(2, 60))
                vinculadas += 1

            db.add(sessao)
            db.flush()

            for cand in candidatos:
                db.add(ML_CandidatoSessao(
                    IdSessao=sessao.IdSessao,
                    Categoria=cand['categoria'],
                    AeroportoOrigem=cand['aero_orig'],
                    AeroportoDestino=cand['aero_dest'],
                    Duracao=cand['duracao'],
                    Custo=cand['custo'],
                    Escalas=cand['escalas'],
                    TrocasCia=cand['trocas_cia'],
                    IndiceParceria=cand['indice_parceria'],
                    SemTarifa=cand['sem_tarifa'],
                    EhPerecivel=cand['eh_perecivel'],
                    ServicoAlinhado=cand['servico_alinhado'],
                    ScoreBase=cand['score_base'],
                    BonusML=0.0,
                    ScoreFinal=cand['score_base'],
                    FoiEscolhida=(cand['categoria'] == categoria_escolhida),
                ))
                total_candidatos += 1

            geradas += 1

            if geradas % 10 == 0:
                print(f"   ... {geradas}/{qtd} sessões inseridas")

        db.commit()

        print(f"\n✅ Seed concluído:")
        print(f"   Sessões geradas     : {geradas}")
        print(f"   Sessões vinculadas  : {vinculadas}  {'(disponíveis para treino)' if vinculadas else ''}")
        print(f"   Candidatos inseridos: {total_candidatos}")
        if sem_vinculo:
            print(f"\n   ⚠  Sem vínculo — para treinar, vincule manualmente ou gere planejamentos reais.")
        else:
            print(f"\n   ℹ  Para treinar o modelo agora, rode com --treinar")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Erro durante a geração: {e}")
        sys.exit(1)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# LIMPEZA DOS DADOS DE TESTE
# ─────────────────────────────────────────────────────────────────────────────

def limpar_seed() -> None:
    db = ObterSessaoSqlServer()
    try:
        # Conta antes de deletar
        total = (
            db.query(ML_SessaoAnalise)
            .filter(ML_SessaoAnalise.UsuarioAnalise == TAG_TESTE)
            .count()
        )
        if total == 0:
            print("ℹ  Nenhum dado de teste encontrado (tag '__TESTE__').")
            return

        print(f"🔨 Removendo {total} sessões de teste (DELETE SQL direto)...")

        # Subquery com IDs das sessões de teste
        ids_subquery = (
            db.query(ML_SessaoAnalise.IdSessao)
            .filter(ML_SessaoAnalise.UsuarioAnalise == TAG_TESTE)
            .subquery()
        )

        # DELETE dos candidatos primeiro (FK), depois das sessões
        from Models.SQL_SERVER.MachineLearning import ML_CandidatoSessao
        cands_del = (
            db.query(ML_CandidatoSessao)
            .filter(ML_CandidatoSessao.IdSessao.in_(
                db.query(ML_SessaoAnalise.IdSessao)
                .filter(ML_SessaoAnalise.UsuarioAnalise == TAG_TESTE)
            ))
            .delete(synchronize_session=False)
        )
        sess_del = (
            db.query(ML_SessaoAnalise)
            .filter(ML_SessaoAnalise.UsuarioAnalise == TAG_TESTE)
            .delete(synchronize_session=False)
        )
        db.commit()
        print(f"✅ {sess_del} sessões e {cands_del} candidatos removidos.\n")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Erro ao limpar dados de teste: {e}")
        sys.exit(1)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# STATUS
# ─────────────────────────────────────────────────────────────────────────────

def exibir_status() -> None:
    from Services.Logic.RouteMLEngine import RouteMLEngine
    status = RouteMLEngine.Status()
    print("\n📊 Status do ML:")
    for k, v in status.items():
        print(f"   {k:<25}: {v}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────

def Executar():
    parser = argparse.ArgumentParser(
        description='Gerador de dados sintéticos para teste do ML de rotas'
    )
    parser.add_argument('--qtd',     type=int, default=30, help='Número de sessões a gerar (default: 30)')
    parser.add_argument('--treinar', action='store_true',  help='Treina o modelo após gerar os dados')
    parser.add_argument('--status',  action='store_true',  help='Exibe o status atual do ML (sem gerar dados)')
    parser.add_argument('--limpar',  action='store_true',  help='Remove apenas os dados gerados por este script')
    args = parser.parse_args()

    if args.limpar:
        limpar_seed()
        return

    if args.status:
        exibir_status()
        return

    gerar_seed(qtd=args.qtd)

    if args.treinar:
        print("\n🤖 Iniciando treinamento do modelo...")
        from Services.Logic.RouteMLEngine import RouteMLEngine
        resultado = RouteMLEngine.Treinar(usuario=TAG_TESTE)
        print(f"\n📋 Resultado do treinamento:")
        for k, v in resultado.items():
            print(f"   {k:<25}: {v}")
        print()

    if not args.treinar:
        exibir_status()


if __name__ == '__main__':
    Executar()
