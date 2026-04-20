import sys
sys.path.insert(0, '.')
from Services.PlanejamentoService import PlanejamentoService

cache = PlanejamentoService._ObterMapaCache()

diario  = PlanejamentoService.BuscarCtcsDiario(cache)
reversa = PlanejamentoService.BuscarCtcsReversa(cache)
backlog = PlanejamentoService.BuscarCtcsBacklog(cache)

todos = diario + reversa + backlog

# Aeroportos conhecidos pelo modelo v5
AEROS_CONHECIDOS = {'BSB', 'CGH', 'CNF', 'CWB', 'FOR', 'GIG', 'GRU', 'JOI', 'MAO', 'NVT', 'POA', 'REC', 'SSA'}

MAPA_UF_IATA = {
    'SP': 'GRU', 'RJ': 'GIG', 'MG': 'CNF', 'RS': 'POA', 'PR': 'CWB',
    'SC': 'FLN', 'BA': 'SSA', 'PE': 'REC', 'CE': 'FOR', 'AM': 'MAO',
    'PA': 'BEL', 'GO': 'BSB', 'DF': 'BSB', 'MT': 'CGB', 'MS': 'CGR',
    'ES': 'VIX', 'MA': 'SLZ', 'PB': 'JPA', 'RN': 'NAT', 'AL': 'MCZ',
    'SE': 'AJU', 'PI': 'THE', 'RO': 'PVH', 'RR': 'BVB', 'AP': 'MCP',
    'AC': 'RBR', 'TO': 'PMW'
}

def motor(uf_o, uf_d):
    a_o = MAPA_UF_IATA.get(uf_o, '???')
    a_d = MAPA_UF_IATA.get(uf_d, '???')
    if a_o in AEROS_CONHECIDOS and a_d in AEROS_CONHECIDOS:
        return 'ML', a_o, a_d
    return 'GRAFO', a_o, a_d

print(f"{'BLOCO':7} | {'CTC':12} | {'PESO':>7} | {'ROTA UF':9} | {'AERO':12} | {'TIPO':10} | {'JA PLAN':8} | MOTOR ESPERADO")
print("-" * 110)

ml_candidates = []
grafo_candidates = []

for c in todos:
    fd   = c.get('full_data', {})
    uf_o = fd.get('uf_orig', '?')
    uf_d = fd.get('uf_dest', '?')
    bloco  = c.get('origem_dados', '?')
    ctc    = c.get('ctc', '?')
    peso   = c.get('peso_taxado', 0) or 0
    tipo   = c.get('tipo_carga', '') or ''
    ja_pl  = 'SIM' if c.get('tem_planejamento') else 'nao'
    mot, a_o, a_d = motor(uf_o, uf_d)
    
    linha = f"{bloco:7} | {ctc:12} | {peso:6.1f}kg | {uf_o:2}->{uf_d:2}     | {a_o}->{a_d:6} | {tipo:10} | {ja_pl:8} | {mot}"
    print(linha)
    if mot == 'ML':
        ml_candidates.append(c)
    else:
        grafo_candidates.append(c)

print()
print(f"=== RESUMO ===")
print(f"Total: {len(todos)} CTCs  (Diario:{len(diario)}  Reversa:{len(reversa)}  Backlog:{len(backlog)})")
print(f"Candidatos ML   (ambos aeroportos conhecidos): {len(ml_candidates)}")
print(f"Candidatos GRAFO (algum aeroporto desconhecido): {len(grafo_candidates)}")

print()
print("=== TOP ML (sem planejamento, peso > 20kg) ===")
top_ml = [c for c in ml_candidates if not c.get('tem_planejamento') and (c.get('peso_taxado') or 0) > 20]
for c in sorted(top_ml, key=lambda x: x.get('peso_taxado', 0), reverse=True)[:10]:
    fd = c.get('full_data', {})
    print(f"  CTC {c['ctc']} | {c.get('peso_taxado',0):.1f}kg | {fd.get('uf_orig')}->{fd.get('uf_dest')} | {c.get('tipo_carga')} | {c.get('origem_dados')}")

print()
print("=== TOP GRAFO (sem planejamento, peso > 20kg) ===")
top_gf = [c for c in grafo_candidates if not c.get('tem_planejamento') and (c.get('peso_taxado') or 0) > 20]
for c in sorted(top_gf, key=lambda x: x.get('peso_taxado', 0), reverse=True)[:10]:
    fd = c.get('full_data', {})
    _, a_o, a_d = motor(fd.get('uf_orig',''), fd.get('uf_dest',''))
    print(f"  CTC {c['ctc']} | {c.get('peso_taxado',0):.1f}kg | {fd.get('uf_orig')}->{fd.get('uf_dest')} ({a_o}->{a_d}) | {c.get('tipo_carga')} | {c.get('origem_dados')}")

