/**
 * Ranking.js - Atualizado para LuftCore UI
 * - Infinite Scroll, Debounce, DOM Otimizado.
 */

let EstadoAtual = {
    modo: 'GLOBAL', 
    ufSelecionada: null,
    listaCompletaFiltrada: [], 
    itensRenderizados: 0,      
    ITENS_POR_PAGINA: 50       
};

let CacheGlobal = null; 
let TimeoutPesquisa = null; 

document.addEventListener('DOMContentLoaded', () => {
    ConfigurarScrollInfinito();
    AtivarModoGlobal(); 
});

// --- MODOS DE NAVEGAÇÃO ---

function AtivarModoGlobal() {
    EstadoAtual.modo = 'GLOBAL';
    EstadoAtual.ufSelecionada = null;
    ResetarSidebar();
    document.getElementById('btn-global').classList.add('active');

    if (!CacheGlobal) {
        let todos = [];
        Object.keys(window.DadosRanking).forEach(uf => {
            const aeroportosUf = window.DadosRanking[uf].map(a => ({...a, ufOrigem: uf}));
            todos = [...todos, ...aeroportosUf];
        });
        todos.sort((a, b) => b.importancia - a.importancia);
        CacheGlobal = todos;
    }

    AtualizarHeader('Visão Global', 'Ordenado por Índice de Importância');
    
    EstadoAtual.listaCompletaFiltrada = CacheGlobal;
    ResetarRenderizacao();
}

function SelecionarUf(uf) {
    EstadoAtual.modo = 'UF';
    EstadoAtual.ufSelecionada = uf;

    ResetarSidebar();
    const btnUf = document.getElementById(`uf-${uf}`);
    if(btnUf) btnUf.classList.add('active');

    const lista = window.DadosRanking[uf] || [];
    
    AtualizarHeader(`Aeroportos de ${uf}`, 'Ajuste a prioridade local');
    
    EstadoAtual.listaCompletaFiltrada = lista;
    ResetarRenderizacao();
}

function ResetarSidebar() {
    document.querySelectorAll('.luft-uf-item').forEach(el => el.classList.remove('active'));
    const input = document.getElementById('global-search');
    if(input && EstadoAtual.modo !== 'GLOBAL') input.value = '';
}

// --- PESQUISA ---

function FiltrarGlobal(termo) {
    clearTimeout(TimeoutPesquisa);
    TimeoutPesquisa = setTimeout(() => { ExecutarFiltro(termo); }, 300);
}

function ExecutarFiltro(termo) {
    termo = termo.toLowerCase().trim();

    if (termo === '') {
        if (EstadoAtual.modo === 'GLOBAL') AtivarModoGlobal();
        else SelecionarUf(EstadoAtual.ufSelecionada);
        return;
    }

    document.querySelectorAll('.luft-uf-item').forEach(el => el.classList.remove('active'));
    if (!CacheGlobal) AtivarModoGlobal(); 

    const resultados = CacheGlobal.filter(a => {
        return (a.iata && a.iata.toLowerCase().includes(termo)) ||
               (a.nome && a.nome.toLowerCase().includes(termo)) ||
               (a.regiao && a.regiao.toLowerCase().includes(termo));
    });

    AtualizarHeader('Resultados da Busca', `${resultados.length} aeroportos encontrados`);
    
    EstadoAtual.listaCompletaFiltrada = resultados;
    ResetarRenderizacao();
}

// --- RENDERIZAÇÃO INTELIGENTE ---

function ConfigurarScrollInfinito() {
    const container = document.getElementById('container-aeroportos');
    container.addEventListener('scroll', () => {
        if (container.scrollTop + container.clientHeight >= container.scrollHeight - 100) {
            RenderizarProximoLote();
        }
    });
}

function ResetarRenderizacao() {
    const container = document.getElementById('container-aeroportos');
    container.scrollTop = 0; 
    container.innerHTML = '';
    EstadoAtual.itensRenderizados = 0;
    
    if (EstadoAtual.listaCompletaFiltrada.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 60px; color: var(--luft-text-muted);">
                <i class="ph-duotone ph-airplane-slash text-muted" style="font-size: 3.5rem; margin-bottom:15px;"></i>
                <p class="font-bold text-main text-lg">Nenhum aeroporto encontrado.</p>
            </div>`;
        return;
    }

    RenderizarProximoLote();
}

function RenderizarProximoLote() {
    const total = EstadoAtual.listaCompletaFiltrada.length;
    if (EstadoAtual.itensRenderizados >= total) return; 

    const inicio = EstadoAtual.itensRenderizados;
    const fim = Math.min(inicio + EstadoAtual.ITENS_POR_PAGINA, total);
    
    const lote = EstadoAtual.listaCompletaFiltrada.slice(inicio, fim);
    const htmlLote = lote.map(aero => ConstruirCardHTML(aero)).join('');
    
    const container = document.getElementById('container-aeroportos');
    container.insertAdjacentHTML('beforeend', htmlLote);

    EstadoAtual.itensRenderizados = fim;
}

function ConstruirCardHTML(aero) {
    const colorStyle = GetColorStyle(aero.importancia);
    const borderColor = GetBorderColor(aero.importancia);
    const bgLightColor = GetBgLightColor(aero.importancia);
    
    const mostrarUf = EstadoAtual.modo === 'GLOBAL' || aero.ufOrigem;
    const htmlUf = mostrarUf ? `<span class="luft-badge luft-badge-secondary font-black">${aero.ufOrigem || ''}</span>` : '';

    return `
        <div class="luft-card p-4 hover-lift" id="card-${aero.id_aeroporto}" style="border-top: 4px solid ${colorStyle};">
            <div class="d-flex justify-content-between align-items-start mb-3">
                <div class="font-black text-main text-2xl" style="font-family: monospace; letter-spacing: 1px;">${aero.iata || '---'}</div>
                ${htmlUf}
            </div>
            
            <div class="mb-4">
                <h3 class="font-bold text-main m-0 mb-1 text-md" title="${aero.nome}" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${aero.nome}</h3>
                <p class="text-xs text-muted font-medium d-flex align-items-center gap-1">
                    <i class="ph-fill ph-map-pin"></i> ${aero.regiao || 'Região Desconhecida'}
                </p>
            </div>
            
            <div class="bg-app p-3 rounded border" style="border-color: var(--luft-border);">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="text-xs font-bold text-muted text-uppercase">Importância</span>
                    <span class="font-black" id="badge-${aero.id_aeroporto}" style="color: ${colorStyle}; font-size: 1.1rem;">
                        ${aero.importancia}%
                    </span>
                </div>
                <div class="luft-range-wrapper" style="background: ${bgLightColor}; border: 1px solid ${borderColor};">
                    <div class="luft-range-fill" id="fill-${aero.id_aeroporto}" style="width: ${aero.importancia}%; background: ${colorStyle};"></div>
                    <input type="range" min="0" max="100" value="${aero.importancia}" 
                           class="luft-range-input" 
                           oninput="AtualizarInput(${aero.id_aeroporto}, this.value, '${aero.ufOrigem}')"
                           data-id="${aero.id_aeroporto}">
                </div>
            </div>
        </div>
    `;
}

function AtualizarHeader(titulo, subtitulo) {
    document.getElementById('titulo-view').innerText = titulo;
    document.getElementById('subtitulo-view').innerText = subtitulo;
}

// --- UPDATE E SALVAMENTO ---

function AtualizarInput(id, valor, ufRef) {
    valor = parseInt(valor);
    
    const badge = document.getElementById(`badge-${id}`);
    const fill = document.getElementById(`fill-${id}`);
    const card = document.getElementById(`card-${id}`);
    
    const color = GetColorStyle(valor);
    const borderColor = GetBorderColor(valor);
    const bgLightColor = GetBgLightColor(valor);
    
    if(badge) { badge.innerText = `${valor}%`; badge.style.color = color; }
    if(fill) { fill.style.width = `${valor}%`; fill.style.background = color; }
    if(card) { card.style.borderTopColor = color; }

    const ufAlvo = (ufRef && ufRef !== 'undefined') ? ufRef : EstadoAtual.ufSelecionada;
    if(ufAlvo && window.DadosRanking[ufAlvo]) {
        const index = window.DadosRanking[ufAlvo].findIndex(x => x.id_aeroporto === id);
        if(index >= 0) window.DadosRanking[ufAlvo][index].importancia = valor;
    }
}

function SalvarRankingAtual() {
    const btn = document.querySelector('.btn-save');
    const text = btn.querySelector('.btn-text');
    const originalText = text.innerText;
    
    text.innerText = 'Processando...';
    btn.disabled = true;
    btn.innerHTML = `<i class="ph-bold ph-spinner ph-spin text-lg"></i> <span class="btn-text">Salvando...</span>`;

    const promises = Object.keys(window.DadosRanking).map(uf => {
        return fetch('/Luft-ConnectAir/Aeroportos/API/SalvarRanking', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ uf: uf, aeroportos: window.DadosRanking[uf] })
        }).then(r => r.json());
    });

    Promise.all(promises)
    .then(results => {
        const falhas = results.filter(r => !r.sucesso);
        if(falhas.length === 0) {
            btn.innerHTML = `<i class="ph-bold ph-check-circle text-lg"></i> <span class="btn-text">Tudo Salvo!</span>`;
            setTimeout(() => {
                btn.innerHTML = `<i class="ph-bold ph-floppy-disk text-lg"></i> <span class="btn-text">${originalText}</span>`;
                btn.disabled = false;
            }, 2000);
        } else {
            alert(`Erro ao salvar ${falhas.length} estados.`);
            btn.innerHTML = `<i class="ph-bold ph-floppy-disk text-lg"></i> <span class="btn-text">${originalText}</span>`;
            btn.disabled = false;
        }
    })
    .catch(err => {
        console.error(err);
        alert('Erro de comunicação.');
        btn.innerHTML = `<i class="ph-bold ph-floppy-disk text-lg"></i> <span class="btn-text">${originalText}</span>`;
        btn.disabled = false;
    });
}

// Helpers de Cores LuftCore
function GetColorStyle(val) {
    if (val < 30) return 'var(--luft-danger)';
    if (val < 70) return 'var(--luft-warning)';
    return 'var(--luft-success)';
}

function GetBorderColor(val) {
    if (val < 30) return 'rgba(239, 68, 68, 0.2)';
    if (val < 70) return 'rgba(245, 158, 11, 0.2)';
    return 'rgba(34, 197, 94, 0.2)';
}

function GetBgLightColor(val) {
    if (val < 30) return 'rgba(239, 68, 68, 0.05)';
    if (val < 70) return 'rgba(245, 158, 11, 0.05)';
    return 'rgba(34, 197, 94, 0.05)';
}