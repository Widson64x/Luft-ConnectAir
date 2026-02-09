/**
 * Index.js - Controlador do Painel de Planejamento (Versão Modern UI)
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
        if(tabela) tabela.innerHTML = '<tr><td colspan="11" style="text-align:center; padding:20px;">Carregando dados...</td></tr>';

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
            d.peso_taxado = Number(d.peso_taxado || 0);
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
        if(tabela) tabela.innerHTML = `<tr><td colspan="11" style="color:red; text-align:center;">Erro ao carregar: ${e.message}</td></tr>`;
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
                <td colspan="11" style="text-align: center; padding: 40px; color: var(--text-secondary);">
                    <i class="ph-duotone ph-magnifying-glass" style="font-size: 32px; margin-bottom: 10px;"></i><br>
                    Nenhum registro encontrado para os filtros atuais.
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
        let stylePrio = 'color: #cbd5e1; opacity: 0.5;';

        if (prio === 'S' || prio === 'URGENTE') {
            // Vermelho + Ícone de Sirene/Alerta
            stylePrio = 'color: #ef4444; font-size: 18px;'; 
            iconPrio = '<i class="ph-fill ph-warning-circle" title="URGENTE"></i>';
        } 
        else if (prio === 'AGENDADA') {
            // Laranja/Azul + Ícone de Relógio/Calendário
            stylePrio = 'color: #f59e0b; font-size: 18px;'; 
            iconPrio = '<i class="ph-fill ph-clock-countdown" title="AGENDADA"></i>';
        } 
        else {
            // Cinza + Menos (Normal)
            stylePrio = 'color: #cbd5e1; opacity: 0.5;'; 
            iconPrio = '<i class="ph-bold ph-minus" title="NORMAL"></i>';
        }
        
        // Badge de Tipo (Origem Dados)
        let badgeOrigem = '';
        if(row.origem_dados === 'DIARIO') badgeOrigem = '<span class="badge badge-origem-DIARIO">Do Dia</span>';
        else if(row.origem_dados === 'BACKLOG') badgeOrigem = '<span class="badge badge-origem-BACKLOG">Backlog</span>';
        else if(row.origem_dados === 'REVERSA') badgeOrigem = '<span class="badge badge-origem-REVERSA">Reversa</span>';

        // Link de Montagem
        const linkMontar = URL_BASE_MONTAR
            .replace('__F__', row.filial)
            .replace('__S__', row.serie)
            .replace('__C__', row.ctc);

        tr.innerHTML = `
            <td style="text-align: center;">
                <button class="btn-tabela-acao" onclick="AbrirModalGlobal('${row.filial}', '${row.serie}', '${row.ctc}')">
                    <i class="ph-bold ph-file-text"></i>
                </button>
                <a href="${linkMontar}" class="btn-tabela-acao" style="color: var(--primary-color);">
                    <i class="ph-bold ph-airplane-tilt"></i>
                </a>
            </td>
            <td>
                ${row.tem_planejamento 
                    ? `<span class="status-badge st-ok"><div class="status-dot" style="background:#16a34a"></div> ${row.status_planejamento}</span>`
                    : `<span class="status-badge st-pendente"><div class="status-dot"></div> Pendente</span>`
                }
            </td>
            <td style="text-align: center; ${stylePrio}">${iconPrio}</td>
            <td>${badgeOrigem}</td>
            <td>
                <span class="txt-destaque">${row.ctc}</span>
                <span class="txt-secondary">Sér. ${row.serie} | ${row.filial}</span>
            </td>
            <td style="text-align: center;">${row.unid_lastmile || '-'}</td>
            <td>
                <span style="font-weight:600">${row.data_emissao}</span>
                <span class="txt-secondary">${row.hora_emissao}</span>
            </td>
            <td>
                <div style="display:flex; align-items:center; gap:5px;">
                    <span style="font-weight:600">${row.origem.split('/')[0]}</span>
                    <i class="ph-bold ph-arrow-right flow-icon"></i>
                    <span style="font-weight:600">${row.destino.split('/')[0]}</span>
                </div>
                <span class="txt-secondary">${row.origem.split('/')[1]} &rarr; ${row.destino.split('/')[1]}</span>
            </td>
            <td>
                <div style="max-width: 350px; overflow: hidden; text-overflow: ellipsis;" title="${row.remetente}">
                    ${row.remetente}
                </div>
                <span class="badge" style="background:#f1f5f9; color:#475569; margin-top:2px;">${row.tipo_carga || 'NORMAL'}</span>
            </td>
            <td style="text-align: center;">${row.qtd_notas}</td>
            <td style="text-align: right;">${row.volumes}</td>
            <td style="text-align: right;">${fmtNumero.format(row.peso_taxado)}</td>
            <td style="text-align: right; color: var(--text-secondary);">${fmtMoeda.format(row.raw_val_mercadoria)}</td>
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
    
    // Atualiza Botões
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`tab-${tipo.toLowerCase()}`).classList.add('active');

    // Animação de Saída
    if(container) {
        container.classList.remove('slide-in-right');
        container.classList.add('slide-out-left');
    }

    setTimeout(() => {
        ABA_ATUAL = tipo;
        FiltrarTabela(); // Renderiza com os novos dados
        
        // Animação de Entrada
        if(container) {
            container.classList.remove('slide-out-left');
            void container.offsetWidth; // Trigger Reflow
            container.classList.add('slide-in-right');
        }

        setTimeout(() => {
            if(container) container.classList.remove('slide-in-right');
            isAnimating = false;
        }, 400);

    }, 400);
}

function FiltrarTabela() {
    const termo = document.getElementById('input-busca')?.value.toLowerCase() || '';
    const prio = document.getElementById('filtro-prioridade')?.value || 'TODOS';
    const filial = document.getElementById('filtro-filial')?.value || 'TODOS';
    const motivo = document.getElementById('filtro-motivo')?.value || 'TODOS';

    DADOS_VISIVEIS = DADOS_ORIGINAIS.filter(item => {
        // Filtro de Texto
        const matchTexto = !termo || item.busca_texto.includes(termo);
        
        // --- ATUALIZADO: Filtros Select (3 Prioridades) ---
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
    // IDs atualizados conforme o novo HTML
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
    
    document.querySelectorAll('th i').forEach(i => i.className = 'ph-bold ph-caret-up-down sort-icon');
    const thAtual = document.querySelector(`th[onclick="Ordenar('${coluna}')"] i`);
    if(thAtual) {
        thAtual.className = ORDEM_ATUAL.dir === 'asc' ? 'ph-bold ph-caret-up' : 'ph-bold ph-caret-down';
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