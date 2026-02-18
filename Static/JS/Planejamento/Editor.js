/**
 * Editor.js - Cockpit de Planejamento (Enhanced)
 * Atualizado para estrutura 'base_calculo' do MalhaService
 */

let map;
let routeLayerGroup; 
let currentState = {
    estrategia: 'recomendada',
    rotaSelecionada: null
};

// Cores e Configurações das Cias
const CIA_CONFIG = {
    'AZUL': { color: '#0f4c81', icon: 'AZUL.png' },     // Azul Profundo
    'GOL':  { color: '#ff7020', icon: 'GOL.png' },      // Laranja Gol
    'LATAM': { color: '#e30613', icon: 'LATAM.png' },   // Vermelho Latam
    'DEFAULT': { color: '#6b7280', icon: 'default.png' } // Cinza
};

document.addEventListener('DOMContentLoaded', () => {
    initMap();
    
    // VERIFICA SE EXISTE PLANEJAMENTO SALVO
    if (window.planejamentoSalvo && window.planejamentoSalvo.id_planejamento) {
        IniciarModoVisualizacao(window.planejamentoSalvo);
    } else {
        // Fluxo Normal (Novo Planejamento)
        setTimeout(() => SelecionarEstrategia('recomendada'), 300);
    }
});

function IniciarModoVisualizacao(plan) {
    currentState.estrategia = 'salva';
    currentState.rotaSelecionada = plan.rota;

    EnriquecerRotaSalva(plan.rota);

    RenderizarRotaNoMapa(plan.rota);
    RenderizarTimeline(plan.rota);
    
    // --- ATUALIZAÇÃO AQUI ---
    // Se o backend mandou métricas prontas, usamos elas
    if (plan.metricas) {
        document.querySelector('#strategy-metrics .metric-item:nth-child(1) .val').innerText = 
            "R$ " + plan.metricas.custo.toLocaleString('pt-BR', {minimumFractionDigits: 2});
        
        document.querySelector('#strategy-metrics .metric-item:nth-child(2) .val').innerText = 
            plan.metricas.duracao_fmt || "--:--";
            
        document.querySelector('#strategy-metrics .metric-item:nth-child(3) .val').innerText = 
            plan.metricas.escalas;
    } else {
        // Fallback antigo
        AtualizarMetricas(plan.rota); 
    }
    // ------------------------

    // Ajusta Interface (mantido)
    document.getElementById('aviso-modo-visualizacao').classList.remove('hidden');
    document.getElementById('lbl-data-criacao').innerText = plan.data_criacao;
    document.getElementById('container-estrategias').style.display = 'none';
    document.getElementById('btn-confirmar').style.display = 'none';
    document.getElementById('btn-cancelar-plan').classList.remove('hidden');
    document.getElementById('btn-recalcular').classList.remove('hidden');
}

function EnriquecerRotaSalva(rota) {
    // Tenta encontrar lat/lon nos dados carregados de OpcoesRotas (que contém metadados de aeroportos)
    // para que o mapa desenhe as linhas corretamente.
    // Procura em todas as estratégias disponíveis
    const cacheAeroportos = {};
    
    // Helper para varrer window.opcoesRotas e popular cache
    Object.values(window.opcoesRotas).forEach(lista => {
        lista.forEach(trecho => {
            if(trecho.origem && trecho.origem.iata) cacheAeroportos[trecho.origem.iata] = trecho.origem;
            if(trecho.destino && trecho.destino.iata) cacheAeroportos[trecho.destino.iata] = trecho.destino;
        });
    });

    rota.forEach(t => {
        // Origem
        if (typeof t.origem === 'object' && cacheAeroportos[t.origem.iata]) {
            t.origem = cacheAeroportos[t.origem.iata];
        } else {
             // Fallback severo: usa lat/lon da cidade origem/destino do CTC se nao achar o aero
             // (Isso evita crash no Leaflet, mas a linha ficará reta cidade-cidade)
             if(t === rota[0]) t.origem = { iata: t.origem.iata, lat: window.origemCoords.lat, lon: window.origemCoords.lon };
        }

        // Destino
        if (typeof t.destino === 'object' && cacheAeroportos[t.destino.iata]) {
            t.destino = cacheAeroportos[t.destino.iata];
        } else {
             if(t === rota[rota.length-1]) t.destino = { iata: t.destino.iata, lat: window.destinoCoords.lat, lon: window.destinoCoords.lon };
        }
    });
}

// --- AÇÕES DOS BOTÕES ---

window.AtivarModoEdicao = function() {
    if(!confirm('Deseja descartar a visualização atual e calcular novas rotas?')) return;

    // Reseta UI
    document.getElementById('aviso-modo-visualizacao').classList.add('hidden');
    document.getElementById('container-estrategias').style.display = 'flex'; // Mostra abas
    
    document.getElementById('btn-confirmar').style.display = 'inline-block';
    document.getElementById('btn-recalcular').classList.add('hidden');
    
    // Opcional: Manter o botão de cancelar visivel ou esconder. Vou esconder para forçar o fluxo de "Salvar Novo".
    document.getElementById('btn-cancelar-plan').classList.add('hidden');

    // Seleciona a primeira estratégia disponível
    SelecionarEstrategia('recomendada');
};

window.CancelarPlanejamentoExistente = function() {
    if(!confirm('Tem certeza que deseja CANCELAR este planejamento? O status voltará para pendente.')) return;

    const id = window.planejamentoSalvo.id_planejamento;
    const btn = document.getElementById('btn-cancelar-plan');
    const txtOriginal = btn.innerHTML;
    btn.innerHTML = '...';
    btn.disabled = true;

    fetch(URL_CANCELAR_PLANEJAMENTO, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ id_planejamento: id })
    })
    .then(r => r.json())
    .then(d => {
        if(d.sucesso) {
            alert('Planejamento cancelado.');
            window.location.href = '/Luft-ConnectAir/Planejamento/Dashboard';
        } else {
            alert('Erro: ' + d.msg);
            btn.innerHTML = txtOriginal;
            btn.disabled = false;
        }
    });
};

function getCiaConfig(ciaName) {
    if (!ciaName) return CIA_CONFIG['DEFAULT'];
    const key = ciaName.toUpperCase().split(' ')[0]; // Pega primeira palavra (AZUL LINHAS...)
    return CIA_CONFIG[key] || CIA_CONFIG['DEFAULT'];
}

// Função Utilitária para Formatar Moeda (Apenas para fallbacks ou displays extras)
function formatMoney(value) {
    if (value === undefined || value === null) return 'R$ 0,00';
    if (typeof value === 'string' && value.includes('R$')) return value;
    return parseFloat(value).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

// --- 1. Inicialização do Mapa ---
function initMap() {
    const lat = window.origemCoords.lat || -15.79;
    const lon = window.origemCoords.lon || -47.88;

    map = L.map('map', { zoomControl: false, attributionControl: false }).setView([lat, lon], 5);

    // Tiles Clean
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        maxZoom: 19
    }).addTo(map);

    L.control.zoom({ position: 'topright' }).addTo(map);
    routeLayerGroup = L.layerGroup().addTo(map);
}

// --- 2. Seleção de Estratégia (Atualizado para novas chaves) ---
window.SelecionarEstrategia = function(tipo) {
    currentState.estrategia = tipo;

    // 1. Atualiza UI das Abas
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`tab-${tipo}`);
    if(btn) btn.classList.add('active');

    // 2. Recupera a rota do objeto global injetado pelo backend
    // As chaves agora são: 'recomendada', 'direta', 'rapida', 'economica', 'conexao_mesma_cia', 'interline'
    const rotas = window.opcoesRotas[tipo];
    currentState.rotaSelecionada = rotas;

    // 3. Renderização
    if (rotas && rotas.length > 0) {
        RenderizarRotaNoMapa(rotas);
        RenderizarTimeline(rotas);
        AtualizarMetricas(rotas);
    } else {
        // Limpa visual se não houver rota para essa estratégia (ex: Sem voo direto)
        routeLayerGroup.clearLayers();
        document.getElementById('timeline-content').innerHTML = `
            <div class="empty-state">
                <i class="ph-duotone ph-airplane-slash"></i>
                <p>Nenhuma rota encontrada para esta categoria.</p>
            </div>`;
        AtualizarMetricas(null);
    }
    
    // 4. Atualiza estado do botão Salvar
    AtualizarBotaoSalvar(rotas);
};

// Função auxiliar para controlar o botão de confirmação
function AtualizarBotaoSalvar(rotas) {
    const btnSalvar = document.getElementById('btn-confirmar');
    if(!rotas || rotas.length === 0) {
        btnSalvar.disabled = true;
        btnSalvar.innerHTML = '<i class="ph-bold ph-warning"></i> Indisponível';
        btnSalvar.style.background = '#9ca3af'; // Cinza disabled
        btnSalvar.style.cursor = 'not-allowed';
    } else {
        btnSalvar.disabled = false;
        btnSalvar.innerHTML = '<i class="ph-bold ph-check-circle"></i> Confirmar Rota';
        btnSalvar.style.background = ''; // Volta ao CSS original (verde/azul)
        btnSalvar.style.cursor = 'pointer';
    }
}
// --- 3. Renderização Visual (Mapa Rico) ---

function RenderizarRotaNoMapa(listaTrechos) {
    routeLayerGroup.clearLayers();
    if (!listaTrechos || listaTrechos.length === 0) return;

    const allLatlngs = [];
    
    // Dados das Pontas (Cidades)
    const cityOrigem = [window.origemCoords.lat, window.origemCoords.lon];
    const cityDestino = [window.destinoCoords.lat, window.destinoCoords.lon];
    
    // Dados dos Aeroportos das Pontas
    const aeroOrigem = [listaTrechos[0].origem.lat, listaTrechos[0].origem.lon];
    const aeroDestino = [listaTrechos[listaTrechos.length-1].destino.lat, listaTrechos[listaTrechos.length-1].destino.lon];

    // --- A. TRECHO COLETA (Cidade -> Aeroporto) ---
    L.polyline([cityOrigem, aeroOrigem], {
        color: '#6b7280', // Cinza
        weight: 3,
        dashArray: '5, 10', // Pontilhado largo
        opacity: 0.7
    }).addTo(routeLayerGroup);

    const iconColeta = L.divIcon({
        className: 'ground-marker origin',
        html: `<i class="ph-fill ph-truck"></i>`,
        iconSize: [32, 32], iconAnchor: [16, 16]
    });
    L.marker(cityOrigem, { icon: iconColeta }).addTo(routeLayerGroup)
     .bindPopup(`<b>Coleta na Origem</b><br>${window.ctc.origem_cidade}`);
     
    allLatlngs.push(cityOrigem);

    // --- B. TRECHOS AÉREOS (Aeroporto -> Aeroporto) ---
    listaTrechos.forEach((trecho, index) => {
        const origem = [trecho.origem.lat, trecho.origem.lon];
        const destino = [trecho.destino.lat, trecho.destino.lon];
        const ciaInfo = getCiaConfig(trecho.cia);

        // -- DADOS FINANCEIROS (Backend) --
        const baseCalc = trecho.base_calculo || {};
        const tarifa = baseCalc.tarifa || 0;
        const servico = baseCalc.servico || 'STD';
        
        // Uso direto do valor calculado pelo backend
        const custoTrechoFmt = baseCalc.custo_trecho_fmt || 'R$ 0,00';

        // Linha do Voo
        const polyline = L.polyline([origem, destino], {
            color: ciaInfo.color, weight: 4, opacity: 0.9
        }).addTo(routeLayerGroup);

        // Marcadores Aeroportos
        if (index === 0) {
            L.circleMarker(origem, { color: ciaInfo.color, radius: 5, fillOpacity: 1, fillColor: '#fff' })
             .addTo(routeLayerGroup).bindTooltip(trecho.origem.iata, {permanent: true, direction: 'top', className: 'aero-label'});
        }
        L.circleMarker(destino, { color: ciaInfo.color, radius: 5, fillOpacity: 1, fillColor: '#fff' })
         .addTo(routeLayerGroup).bindTooltip(trecho.destino.iata, {permanent: true, direction: 'top', className: 'aero-label'});;
        
        allLatlngs.push(origem);
        allLatlngs.push(destino);

        // Avião Rotacionado
        const midLat = (trecho.origem.lat + trecho.destino.lat) / 2;
        const midLon = (trecho.origem.lon + trecho.destino.lon) / 2;
        const angle = calculateBearing(trecho.origem.lat, trecho.origem.lon, trecho.destino.lat, trecho.destino.lon);

        const planeIcon = L.divIcon({
            className: 'plane-icon-marker',
            html: `<i class="ph-fill ph-airplane" style="font-size: 26px; color: ${ciaInfo.color}; transform: rotate(${angle - 90}deg); filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));"></i>`,
            iconSize: [30, 30], iconAnchor: [15, 15]
        });
        const planeMarker = L.marker([midLat, midLon], { icon: planeIcon }).addTo(routeLayerGroup);

        // Popup Rico
        const popupContent = `
            <div class="flight-popup-card">
                <div class="popup-header" style="border-left: 4px solid ${ciaInfo.color}">
                    <div class="cia-info">
                        <img src="/Luft-ConnectAir/Static/Img/Logos/${ciaInfo.icon}" class="popup-cia-logo" onerror="this.style.display='none'">
                        <div class="cia-texts">
                            <span class="cia-name">${trecho.cia}</span>
                            <span class="flight-number">Voo ${trecho.voo}</span>
                        </div>
                    </div>
                    <div class="popup-date">${trecho.data.substring(0,5)}</div>
                </div>
                
                <div class="popup-body">
                    <div class="popup-route-row">
                        <div class="node">
                            <span class="iata">${trecho.origem.iata}</span>
                            <span class="time">${trecho.horario_saida}</span>
                        </div>
                        <div class="route-line">
                            <i class="ph-fill ph-airplane"></i>
                        </div>
                        <div class="node">
                            <span class="iata">${trecho.destino.iata}</span>
                            <span class="time">${trecho.horario_chegada}</span>
                        </div>
                    </div>

                    <div class="popup-finance-grid">
                        <div class="fin-item">
                            <span class="label">Serviço</span>
                            <span class="value">${servico}</span>
                        </div>
                        <div class="fin-item">
                            <span class="label">Tarifa/kg</span>
                            <span class="value">${formatMoney(tarifa)}</span>
                        </div>
                        <div class="fin-item total">
                            <span class="label">Total Trecho</span>
                            <span class="value">${custoTrechoFmt}</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        polyline.bindPopup(popupContent);
        planeMarker.bindPopup(popupContent);
    });

    // --- C. TRECHO ENTREGA (Aeroporto -> Cidade) ---
    L.polyline([aeroDestino, cityDestino], {
        color: '#6b7280', // Cinza
        weight: 3,
        dashArray: '5, 10',
        opacity: 0.7
    }).addTo(routeLayerGroup);

    const iconEntrega = L.divIcon({
        className: 'ground-marker dest',
        html: `<i class="ph-fill ph-flag-checkered"></i>`,
        iconSize: [32, 32], iconAnchor: [16, 16]
    });
    L.marker(cityDestino, { icon: iconEntrega }).addTo(routeLayerGroup)
     .bindPopup(`<b>Entrega no Destino</b><br>${window.ctc.destino_cidade}`);
     
    allLatlngs.push(cityDestino);

    // Ajustar Zoom
    if(allLatlngs.length > 0) {
        map.fitBounds(L.latLngBounds(allLatlngs), { 
            paddingTopLeft: [450, 80], 
            paddingBottomRight: [80, 80]
        });
    }
}

function calculateBearing(startLat, startLng, destLat, destLng) {
    const startLatRad = startLat * (Math.PI / 180);
    const startLngRad = startLng * (Math.PI / 180);
    const destLatRad = destLat * (Math.PI / 180);
    const destLngRad = destLng * (Math.PI / 180);

    const y = Math.sin(destLngRad - startLngRad) * Math.cos(destLatRad);
    const x = Math.cos(startLatRad) * Math.sin(destLatRad) -
              Math.sin(startLatRad) * Math.cos(destLatRad) * Math.cos(destLngRad - startLngRad);

    let brng = Math.atan2(y, x);
    brng = brng * (180 / Math.PI);
    return (brng + 360) % 360;
}

// --- 4. Renderização Timeline (Sidebar) ---
function RenderizarTimeline(listaTrechos) {
    const container = document.getElementById('timeline-content');
    container.innerHTML = '';

    if (!listaTrechos || listaTrechos.length === 0) {
        container.innerHTML = `<div style="text-align: center; padding: 40px; opacity: 0.7;">...</div>`;
        return;
    }

    let html = '';
    listaTrechos.forEach((trecho, idx) => {
        const ciaInfo = getCiaConfig(trecho.cia);
        
        // -- DADOS FINANCEIROS (Backend) --
        const baseCalc = trecho.base_calculo || {};
        const tarifa = baseCalc.tarifa || 0;
        const servico = baseCalc.servico || 'STD';
        // Uso direto
        const custoTrechoFmt = baseCalc.custo_trecho_fmt || 'R$ 0,00';

        if (idx > 0) {
            html += `<div class="connection-line"><i class="ph-bold ph-clock-clockwise"></i> Conexão em ${trecho.origem.iata}</div>`;
        }

        html += `
            <div class="flight-card" onclick="map.flyTo([${trecho.origem.lat}, ${trecho.origem.lon}], 8)">
                <div class="flight-header">
                    <div class="cia-logo-box">
                         <img src="/Luft-ConnectAir/Static/Img/Logos/${ciaInfo.icon}" class="cia-logo" onerror="this.src='https://placehold.co/40x40?text=A'">
                    </div>
                    <span class="cia-name">${trecho.cia} ${trecho.voo}</span>
                    <span class="flight-date">${trecho.data.substring(0,5)}</span>
                </div>
                
                <div class="flight-route">
                    <div class="airport-block">
                        <div class="airport-code">${trecho.origem.iata}</div>
                        <div class="flight-time">${trecho.horario_saida}</div>
                    </div>
                    <div class="flight-arrow-anim"><i class="ph-bold ph-airplane-tilt" style="color: ${ciaInfo.color}"></i></div>
                    <div class="airport-block">
                        <div class="airport-code">${trecho.destino.iata}</div>
                        <div class="flight-time">${trecho.horario_chegada}</div>
                    </div>
                </div>

                <div class="flight-footer">
                    <div class="info-badge">
                        <span class="label">Serviço</span>
                        <br>
                        <span class="value">${servico}</span>
                    </div>
                    <div class="info-badge">
                        <span class="label">Tarifa</span>
                        <br>
                        <span class="value">${formatMoney(tarifa)}</span>
                    </div>
                    <div class="info-badge cost">
                        <span class="label">Custo</span>
                        <br>
                        <span class="value">${custoTrechoFmt}</span>
                    </div>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

// --- 5. Atualização das Métricas (Refinada) ---
function AtualizarMetricas(listaTrechos) {
    const container = document.getElementById('strategy-metrics');
    const els = container.children; // [0]=Custo, [1]=Tempo, [2]=Conexões
    
    if(!listaTrechos || listaTrechos.length === 0) {
        container.style.opacity = '0.5';
        els[0].querySelector('.val').innerText = '--';
        els[1].querySelector('.val').innerText = '--';
        els[2].querySelector('.val').innerText = '--';
        return;
    }
    
    const resumo = listaTrechos[0]; 
    
    // Custo Total
    els[0].querySelector('.val').innerText = resumo.total_custo_fmt || formatMoney(resumo.total_custo_raw); 
    
    // Tempo Total
    els[1].querySelector('.val').innerText = resumo.total_duracao || '--:--';
    
    // Quantidade de Escalas (Qtd Trechos - 1)
    const qtdEscalas = listaTrechos.length - 1;
    let textoEscalas = "Direto";
    if (qtdEscalas === 1) textoEscalas = "1 Conexão";
    if (qtdEscalas > 1) textoEscalas = `${qtdEscalas} Conexões`;
    
    els[2].querySelector('.val').innerText = textoEscalas;
    
    container.style.opacity = '1';
}

// --- 6. Salvar e Modals ---
window.ConfirmarPlanejamento = function() {
    if (!currentState.rotaSelecionada) return;
    const btn = document.getElementById('btn-confirmar');
    const originalText = btn.innerHTML;
    
    btn.disabled = true;
    btn.innerHTML = '<i class="ph-bold ph-spinner ph-spin"></i> Processando...';

    const rotaFormatada = currentState.rotaSelecionada.map(trecho => {
        const base = trecho.base_calculo || {};
        return {
            cia: trecho.cia,
            voo: trecho.voo,
            origem: trecho.origem.iata,
            destino: trecho.destino.iata,
            partida_iso: InverterData(trecho.data) + 'T' + trecho.horario_saida + ':00',
            chegada_iso: InverterData(trecho.data) + 'T' + trecho.horario_chegada + ':00',
            
            // Mapeando dados para salvar
            servico: base.servico || null,
            valor_tarifa: base.tarifa || 0,
            peso_cobrado: base.peso_usado || 0,
            // (Opcional) Passar o custo calculado se o backend de salvamento precisar
            custo_calculado: base.custo_trecho || 0
        };
    });

    const payload = {
        filial: window.ctc.filial,
        serie: window.ctc.serie,
        ctc: window.ctc.ctc,
        rota_completa: rotaFormatada,
        estrategia: currentState.estrategia
    };

    fetch(URL_GRAVAR_PLANEJAMENTO, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(r => r.json())
    .then(data => {
        if(data.sucesso) {
            btn.innerHTML = '<i class="ph-bold ph-check"></i> Sucesso!';
            btn.style.background = 'var(--cor-sucesso)';
            setTimeout(() => {
                window.location.href = '/Luft-ConnectAir/Planejamento/Dashboard';
            }, 1000);
        } else {
            alert('Erro: ' + (data.msg || 'Erro desconhecido'));
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    })
    .catch(err => {
        console.error(err);
        alert('Erro de comunicação.');
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
};

function InverterData(strData) {
    if(!strData) return '';
    const parts = strData.split('/');
    return `${parts[2]}-${parts[1]}-${parts[0]}`;
}

window.AbrirModalLote = function() {
    const backdrop = document.getElementById('modal-lote-backdrop');
    if(backdrop) {
        backdrop.classList.remove('hidden'); 
        setTimeout(() => backdrop.classList.add('visible'), 10);
    }
};

window.FecharModalLote = function(event) {
    if (event && !event.target.classList.contains('modal-backdrop') && !event.target.classList.contains('btn-close')) return;

    const backdrop = document.getElementById('modal-lote-backdrop');
    if(backdrop) {
        backdrop.classList.remove('visible'); 
        setTimeout(() => backdrop.classList.add('hidden'), 300); 
    }
};