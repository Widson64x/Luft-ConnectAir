"""
LimparDadosML.py — Limpeza das tabelas de Machine Learning

Uso:
    # Ver contagens sem alterar nada (dry-run)
    python Scripts/LimparDadosML.py

    # Apagar tudo (sessões + candidatos + modelos + importâncias)
    python Scripts/LimparDadosML.py --confirmar

    # Só sessões sem vínculo (lixo descartado antes de salvar planejamento)
    python Scripts/LimparDadosML.py --modo sessoes --confirmar

    # Só o modelo treinado (reset para retreinar do zero, mantém histórico)
    python Scripts/LimparDadosML.py --modo modelo --confirmar

Modos disponíveis via --modo:
    tudo        Apaga todos os dados: sessões, candidatos, modelos e importâncias (default)
    sessoes     Apaga apenas sessões não vinculadas a um planejamento (histórico descartado)
    modelo      Apaga apenas versões do modelo e importâncias (mantém histórico de sessões)
"""

import sys
import os
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.MachineLearning import (
    ML_SessaoAnalise,
    ML_CandidatoSessao,
    ML_ModeloVersao,
    ML_FeatureImportancia,
)


# ─────────────────────────────────────────────────────────────────────────────
# CONTAGENS
# ─────────────────────────────────────────────────────────────────────────────

def _exibir_contagens(db):
    sessoes_total     = db.query(ML_SessaoAnalise).count()
    sessoes_vinculadas = db.query(ML_SessaoAnalise).filter(ML_SessaoAnalise.IdPlanejamento != None).count()
    sessoes_livres    = sessoes_total - sessoes_vinculadas
    candidatos        = db.query(ML_CandidatoSessao).count()
    modelos           = db.query(ML_ModeloVersao).count()
    importancias      = db.query(ML_FeatureImportancia).count()

    print("\n📊 Estado atual das tabelas ML:")
    print(f"   Sessões totais       : {sessoes_total:>6}  ({sessoes_vinculadas} vinculadas a planejamentos, {sessoes_livres} sem vínculo)")
    print(f"   Candidatos           : {candidatos:>6}")
    print(f"   Versões de modelo    : {modelos:>6}")
    print(f"   Feature importâncias : {importancias:>6}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# MODOS DE LIMPEZA
# ─────────────────────────────────────────────────────────────────────────────

def _limpar_tudo(db):
    """Apaga tudo: importâncias → modelos → candidatos → sessões (respeita FKs)."""
    imp  = db.query(ML_FeatureImportancia).delete()
    mod  = db.query(ML_ModeloVersao).delete()
    cand = db.query(ML_CandidatoSessao).delete()
    sess = db.query(ML_SessaoAnalise).delete()
    print(f"   🗑  Importâncias removidas : {imp}")
    print(f"   🗑  Modelos removidos      : {mod}")
    print(f"   🗑  Candidatos removidos   : {cand}")
    print(f"   🗑  Sessões removidas      : {sess}")


def _limpar_sessoes_livres(db):
    """Remove apenas sessões sem vínculo com planejamento (e seus candidatos via cascade)."""
    sessoes = (
        db.query(ML_SessaoAnalise)
        .filter(ML_SessaoAnalise.IdPlanejamento == None)
        .all()
    )
    removidas = 0
    for s in sessoes:
        db.delete(s)
        removidas += 1
    print(f"   🗑  Sessões sem vínculo removidas: {removidas} (candidatos removidos via cascade)")


def _limpar_modelo(db):
    """Remove versões de modelo e suas importâncias (mantém histórico de sessões)."""
    imp = db.query(ML_FeatureImportancia).delete()
    mod = db.query(ML_ModeloVersao).delete()
    print(f"   🗑  Importâncias removidas : {imp}")
    print(f"   🗑  Modelos removidos      : {mod}")

    # Remove o arquivo joblib se existir
    from pathlib import Path
    from Configuracoes import ConfiguracaoAtual
    caminho_modelo = Path(ConfiguracaoAtual.DIR_MODELS) / 'modelo_rotas.joblib'
    if caminho_modelo.exists():
        caminho_modelo.unlink()
        print(f"   🗑  Arquivo joblib removido: {caminho_modelo}")
    else:
        print(f"   ℹ  Arquivo joblib não encontrado (já removido ou nunca treinado)")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────

def Executar():
    parser = argparse.ArgumentParser(
        description='Limpeza das tabelas de Machine Learning do Luft-ConnectAir'
    )
    parser.add_argument(
        '--confirmar',
        action='store_true',
        help='Executa a limpeza real. Sem esta flag apenas exibe as contagens (dry-run).'
    )
    parser.add_argument(
        '--modo',
        choices=['tudo', 'sessoes', 'modelo'],
        default='tudo',
        help='tudo=apaga tudo | sessoes=só sessões sem vínculo | modelo=só versões de modelo'
    )
    args = parser.parse_args()

    db = ObterSessaoSqlServer()
    try:
        _exibir_contagens(db)

        if not args.confirmar:
            print("ℹ  Modo dry-run. Nenhuma alteração foi feita.")
            print("   Adicione --confirmar para executar a limpeza.\n")
            return

        descricoes = {
            'tudo':    'TODOS os dados ML (sessões, candidatos, modelos, importâncias)',
            'sessoes': 'sessões SEM vínculo com planejamento (e seus candidatos)',
            'modelo':  'versões de modelo e importâncias (mantém histórico de sessões)',
        }
        print(f"⚠  Modo: {args.modo.upper()} — serão removidos: {descricoes[args.modo]}")
        confirmacao = input("   Confirme digitando 'SIM': ").strip().upper()
        if confirmacao != 'SIM':
            print("   Operação cancelada.\n")
            return

        print("\n🔨 Executando limpeza...")
        if args.modo == 'tudo':
            _limpar_tudo(db)
        elif args.modo == 'sessoes':
            _limpar_sessoes_livres(db)
        elif args.modo == 'modelo':
            _limpar_modelo(db)

        db.commit()
        print("\n✅ Limpeza concluída com sucesso.\n")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Erro durante a limpeza: {e}\n")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    Executar()
