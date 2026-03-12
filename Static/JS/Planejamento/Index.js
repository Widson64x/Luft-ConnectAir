/**
 * Index.js - Controlador do Painel de Planejamento 
 * Atualizado para o padrão LuftCore
 */

let DADOS_ORIGINAIS = [];
let DADOS_VISIVEIS = [];
let ORDEM_ATUAL = { col: 'data_raw', dir: 'desc' };
let ABA_ATUAL = 'TODOS';
let isAnimating = false;

// Formatadores
const fmtMoeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const fmtNumero = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// ============================================================================
// 1. INICIALIZAÇÃO
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    AtualizarDataExtenso();
    BuscarDados();
});

function AtualizarDataExtenso() {
    const opcoes = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    const dataHoje = new Date().toLocaleDateString('pt-BR', opcoes);
    // Ajusta primeira letra para maiúscula
    const dataFormatada = dataHoje.charAt(0).toUpperCase() + dataHoje.slice(1);
    
    const elem = document.getElementById('data-extenso');
    if(elem) elem.innerText = dataFormatada;
}

// ============================================================================
// 2. API E DADOS
// ============================================================================
async function BuscarDados() {
    try {
        const tabela = document.getElementById('table-body');
        if(tabela) tabela.innerHTML = '<tr><td colspan="13" style="text-align:center; padding:60px; color:var(--luft-text-muted);"><i class="ph-bold ph-spinner ph-spin text-primary" style="font-size: 2rem; margin-bottom: 10px;"></i><br>Buscando dados no servidor...</td></tr>';

        const resp = await fetch(URL_API_LISTAR);
        if (!resp.ok) throw new Error("Erro na requisição");
        
        const dadosNovos = await resp.json();

        // Pré-processamento para busca rápida e ordenação
        dadosNovos.forEach(d => {
            // Cria campo data numérico para ordenação (YYYYMMDDHHMM)
            const partes = d.data_emissao.split('/'); // assumindo dd/mm/yyyy
            const horaLimpa = d.hora_emissao ? d.hora_emissao.replace(':', '') : '0000';
            d.data_raw = Number(`${partes[2]}${partes[1]}${partes[0]}${horaLimpa}`);

            // Texto completo para o filtro de busca
            d.busca_texto = `${d.ctc} ${d.remetente} ${d.destinatario} ${d.origem} ${d.destino} ${d.filial} ${d.tipo_carga} ${d.motivodoc} ${d.prioridade}`.toLowerCase();
            
            // Tratamento de valores numéricos
            d.peso_fisico = Number(d.peso_fisico || 0);
            d.peso_taxado = Number(d.peso_taxado || 0); // Mantém para ordenação principal
            d.raw_val_mercadoria = Number(d.raw_val_mercadoria || 0);
            d.volumes = Number(d.volumes || 0);
            d.qtd_notas = Number(d.qtd_notas || 0);
        });

        if (DADOS_ORIGINAIS.length === 0) {
            PopularSelects(dadosNovos);
        }

        DADOS_ORIGINAIS = dadosNovos;
        FiltrarTabela();

    } catch (e) {
        console.error("Erro API:", e);
        const tabela = document.getElementById('table-body');
        if(tabela) tabela.innerHTML = `<tr><td colspan="13" class="text-danger font-bold" style="text-align:center; padding:40px;"><i class="ph-bold ph-warning-circle" style="font-size:2rem;"></i><br>Erro ao carregar: ${e.message}</td></tr>`;
    }
}

// ============================================================================
// 3. TABELA E RENDERIZAÇÃO
// ============================================================================
function Renderizar() {
    const tbody = document.getElementById('table-body');
    const contador = document.getElementById('contador-registros');
    
    // Proteção contra erro de elemento nulo
    if (!tbody || !contador) return;

    tbody.innerHTML = '';

    if (DADOS_VISIVEIS.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="13" style="text-align: center; padding: 60px; color: var(--luft-text-muted);">
                    <i class="ph-duotone ph-magnifying-glass" style="font-size: 3rem; margin-bottom: 15px; color: var(--luft-border);"></i><br>
                    <span class="font-bold text-main">Nenhum registro encontrado</span><br>
                    <span class="text-xs">Altere os filtros ou pesquise novamente.</span>
                </td>
            </tr>`;
        contador.innerText = 'Mostrando 0 registros';
        return;
    }

    // Fragmento para melhor performance
    const fragment = document.createDocumentFragment();

    DADOS_VISIVEIS.forEach(row => {
        const tr = document.createElement('tr');
        
        // --- LÓGICA DE PRIORIDADE (3 TIPOS) ---
        const prio = (row.prioridade || 'NORMAL').toUpperCase();
        let iconPrio = '<i class="ph-bold ph-minus" title="NORMAL"></i>'; // Default Normal
        let classPrio = 'text-muted';

        if (prio === 'S' || prio === 'URGENTE') {
            classPrio = 'text-danger font-black'; 
            iconPrio = '<i class="ph-fill ph-warning-circle text-lg"></i>';
        } 
        else if (prio === 'AGENDADA') {
            classPrio = 'text-warning font-black'; 
            iconPrio = '<i class="ph-fill ph-clock-countdown text-lg"></i>';
        } 
        
        // Badge de Tipo (Origem Dados)
        let badgeOrigem = '';
        if(row.origem_dados === 'DIARIO') badgeOrigem = '<span class="luft-badge luft-badge-info">Do Dia</span>';
        else if(row.origem_dados === 'BACKLOG') badgeOrigem = '<span class="luft-badge luft-badge-warning">Backlog</span>';
        else if(row.origem_dados === 'REVERSA') badgeOrigem = '<span class="luft-badge luft-badge-secondary">Reversa</span>';

        // Link de Montagem
        const linkMontar = URL_BASE_MONTAR
            .replace('__F__', row.filial)
            .replace('__S__', row.serie)
            .replace('__C__', row.ctc);

        tr.innerHTML = `
            <td style="text-align: center; min-width: 110px;">
                <div class="d-flex align-items-center justify-content-center gap-2">
                    <button class="btn btn-secondary d-flex align-items-center justify-content-center" style="padding: 6px; width: 36px; height: 36px;" onclick="AbrirModalGlobal('${row.filial}', '${row.serie}', '${row.ctc}')" title="Ver Detalhes">
                        <i class="ph-bold ph-file-text" style="font-size: 1.1rem;"></i>
                    </button>
                    <a href="${linkMontar}" class="btn btn-primary d-flex align-items-center justify-content-center" style="padding: 6px; width: 36px; height: 36px;" title="Planejar Rota">
                        <i class="ph-bold ph-airplane-tilt" style="font-size: 1.1rem;"></i>
                    </a>
                </div>
            </td>
            <td>
                ${row.tem_planejamento 
                    ? `<span class="luft-badge luft-badge-success"><i class="ph-fill ph-check-circle"></i> ${row.status_planejamento}</span>`
                    : `<span class="luft-badge luft-badge-warning"><i class="ph-fill ph-clock"></i> Pendente</span>`
                }
            </td>
            <td style="text-align: center;" class="${classPrio}">${iconPrio}</td>
            <td>${badgeOrigem}</td>
            <td>
                <span class="font-bold text-main d-block" style="font-family: monospace; font-size: 1rem;">${row.ctc}</span>
                <span class="text-xs text-muted">Sér. ${row.serie} | ${row.filial}</span>
            </td>
            <td style="text-align: center;" class="font-medium text-main">${row.unid_lastmile || '-'}</td>
            <td>
                <span class="font-bold text-main d-block">${row.data_emissao}</span>
                <span class="text-xs text-muted"><i class="ph-bold ph-clock"></i> ${row.hora_emissao}</span>
            </td>
            <td>
                <div class="d-flex align-items-center gap-2 font-bold text-main mb-1">
                    ${row.origem.split('/')[0]}
                    <i class="ph-bold ph-arrow-right text-muted" style="font-size: 0.8rem;"></i>
                    ${row.destino.split('/')[0]}
                </div>
                <span class="text-xs text-muted" style="max-width: 150px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: inline-block;">
                    ${row.origem.split('/')[1] || ''} &rarr; ${row.destino.split('/')[1] || ''}
                </span>
            </td>
            <td>
                <div class="font-medium text-main mb-1" style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${row.remetente}">
                    ${row.remetente}
                </div>
                <span class="luft-badge luft-badge-secondary" style="font-size: 0.65rem;">${row.tipo_carga || 'NORMAL'}</span>
            </td>
            <td style="text-align: center;" class="font-black text-main">${row.qtd_notas}</td>
            <td style="text-align: right;" class="font-bold text-main">${row.volumes}</td>
            <td style="text-align: right; line-height: 1.3;">
                <div class="text-xs text-muted">${fmtNumero.format(row.peso_fisico)} Fís</div>
                <div class="font-black text-main">${fmtNumero.format(row.peso_taxado)} Tax</div>
            </td>
            <td style="text-align: right; font-weight: 800; color: var(--luft-success);">${fmtMoeda.format(row.raw_val_mercadoria)}</td>
        `;
        fragment.appendChild(tr);
    });

    tbody.appendChild(fragment);
    contador.innerText = `Mostrando ${DADOS_VISIVEIS.length} registros`;
    
    AtualizarKPIs();
}

// ============================================================================
// 4. LÓGICA DE FILTROS E ABAS
// ============================================================================

// Animação e Troca de Aba
function MudarAba(tipo) {
    if (ABA_ATUAL === tipo || isAnimating) return;

    isAnimating = true;
    const container = document.getElementById('transition-container');
    
    // Atualiza Botões com a nova classe do LuftCore (luft-tab-btn)
    document.querySelectorAll('.luft-tab-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`tab-${tipo.toLowerCase()}`).classList.add('active');

    // Opacidade para transição suave
    if(container) {
        container.style.transition = 'opacity 0.2s';
        container.style.opacity = '0';
    }

    setTimeout(() => {
        ABA_ATUAL = tipo;
        FiltrarTabela(); // Renderiza com os novos dados
        
        // Retorna a opacidade
        if(container) {
            container.style.opacity = '1';
        }

        setTimeout(() => {
            isAnimating = false;
        }, 200);

    }, 200);
}

function FiltrarTabela() {
    const termo = document.getElementById('input-busca')?.value.toLowerCase() || '';
    const prio = document.getElementById('filtro-prioridade')?.value || 'TODOS';
    const filial = document.getElementById('filtro-filial')?.value || 'TODOS';
    const motivo = document.getElementById('filtro-motivo')?.value || 'TODOS';

    DADOS_VISIVEIS = DADOS_ORIGINAIS.filter(item => {
        // Filtro de Texto
        const matchTexto = !termo || item.busca_texto.includes(termo);
        
        // Filtros Select (3 Prioridades)
        let matchPrio = true;
        const pItem = (item.prioridade || 'NORMAL').toUpperCase();

        if (prio !== 'TODOS') {
            if (prio === 'URGENTE') {
                matchPrio = (pItem === 'S' || pItem === 'URGENTE');
            } else if (prio === 'AGENDADA') {
                matchPrio = (pItem === 'AGENDADA');
            } else if (prio === 'NORMAL') {
                // Normal é tudo que NÃO é Urgente nem Agendada
                matchPrio = (pItem !== 'S' && pItem !== 'URGENTE' && pItem !== 'AGENDADA');
            }
        }
                          
        const matchFilial = (filial === 'TODOS') || (item.filial === filial);
        const matchMotivo = (motivo === 'TODOS') || (item.motivodoc === motivo);
        
        // Filtro da Aba
        const matchAba = (ABA_ATUAL === 'TODOS') || (item.origem_dados === ABA_ATUAL);

        return matchTexto && matchPrio && matchFilial && matchMotivo && matchAba;
    });

    AplicarOrdenacao();
    Renderizar();
}

function AtualizarKPIs() {
    const elTotal = document.getElementById('kpi-total');
    const elPeso = document.getElementById('kpi-peso');
    const elValor = document.getElementById('kpi-valor');
    const elNotas = document.getElementById('kpi-notas');

    if (!elTotal) return; 

    let totalPeso = 0;
    let totalValor = 0;
    let totalNotas = 0;

    DADOS_VISIVEIS.forEach(d => {
        totalPeso += d.peso_taxado;
        totalValor += d.raw_val_mercadoria;
        totalNotas += d.qtd_notas;
    });

    elTotal.innerText = DADOS_VISIVEIS.length;
    elPeso.innerText = fmtNumero.format(totalPeso);
    elValor.innerText = totalValor.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    elNotas.innerText = totalNotas;
}

// ============================================================================
// 5. HELPER FUNCTIONS
// ============================================================================

function Ordenar(coluna) {
    if (ORDEM_ATUAL.col === coluna) {
        ORDEM_ATUAL.dir = ORDEM_ATUAL.dir === 'asc' ? 'desc' : 'asc';
    } else {
        ORDEM_ATUAL.col = coluna;
        ORDEM_ATUAL.dir = 'asc';
    }
    
    // Atualiza ícones de ordenação para padrão cinza
    document.querySelectorAll('.luft-planejamento-tabela th i').forEach(i => i.className = 'ph-bold ph-caret-up-down text-muted');
    
    // Pinta o ícone da coluna ativa de azul primário
    const thAtual = document.querySelector(`th[onclick="Ordenar('${coluna}')"] i`);
    if(thAtual) {
        thAtual.className = ORDEM_ATUAL.dir === 'asc' ? 'ph-bold ph-caret-up text-primary' : 'ph-bold ph-caret-down text-primary';
    }

    AplicarOrdenacao();
    Renderizar();
}

function AplicarOrdenacao() {
    const col = ORDEM_ATUAL.col;
    const dir = ORDEM_ATUAL.dir === 'asc' ? 1 : -1;

    DADOS_VISIVEIS.sort((a, b) => {
        let valA = a[col];
        let valB = b[col];

        if (typeof valA === 'string') valA = valA.toLowerCase();
        if (typeof valB === 'string') valB = valB.toLowerCase();

        if (valA < valB) return -1 * dir;
        if (valA > valB) return 1 * dir;
        return 0;
    });
}

function PopularSelects(dados) {
    const filiais = new Set();
    const motivos = new Set();

    dados.forEach(d => {
        if(d.filial) filiais.add(d.filial);
        if(d.motivodoc) motivos.add(d.motivodoc);
    });

    const selFilial = document.getElementById('filtro-filial');
    const selMotivo = document.getElementById('filtro-motivo');

    if(selFilial) {
        Array.from(filiais).sort().forEach(f => {
            selFilial.innerHTML += `<option value="${f}">${f}</option>`;
        });
    }

    if(selMotivo) {
        Array.from(motivos).sort().forEach(m => {
            selMotivo.innerHTML += `<option value="${m}">${m}</option>`;
        });
    }
}