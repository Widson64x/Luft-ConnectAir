/**
 * Editor.js - Cockpit de Planejamento (Enhanced)
 * Atualizado para estrutura 'base_calculo' do MalhaService e UI LuftCore
 */

let map;
let routeLayerGroup; 
let currentState = {
    estrategia: 'recomendada',
    rotaSelecionada: null
};

// Cores e Configurações das Cias
const CIA_CONFIG = {
    'AZUL': { color: '#0ea5e9', icon: 'AZUL.png' },     // Azul Claro (LuftCore Info)
    'GOL':  { color: '#f59e0b', icon: 'GOL.png' },      // Laranja (LuftCore Warning)
    'LATAM': { color: '#ef4444', icon: 'LATAM.png' },   // Vermelho (LuftCore Danger)
    'DEFAULT': { color: '#64748b', icon: 'default.png' } // Cinza (LuftCore Slate)
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
    
    // --- ATUALIZAÇÃO MÉTRICAS LUFTCORE ---
    if (plan.metricas) {
        document.getElementById('metrica-custo').innerText = "R$ " + plan.metricas.custo.toLocaleString('pt-BR', {minimumFractionDigits: 2});
        document.getElementById('metrica-tempo').innerText = plan.metricas.duracao_fmt || "--:--";
        document.getElementById('metrica-conexoes').innerText = plan.metricas.escalas;
    } else {
        AtualizarMetricas(plan.rota); 
    }

    // Ajusta Interface
    document.getElementById('aviso-modo-visualizacao').classList.remove('hidden');
    document.getElementById('lbl-data-criacao').innerText = plan.data_criacao;
    document.getElementById('container-estrategias').style.display = 'none';
    document.getElementById('btn-confirmar').style.display = 'none';
    document.getElementById('btn-cancelar-plan').classList.remove('hidden');
    document.getElementById('btn-recalcular').classList.remove('hidden');
}

function EnriquecerRotaSalva(rota) {
    const cacheAeroportos = {};
    
    Object.values(window.opcoesRotas).forEach(lista => {
        lista.forEach(trecho => {
            if(trecho.origem && trecho.origem.iata) cacheAeroportos[trecho.origem.iata] = trecho.origem;
            if(trecho.destino && trecho.destino.iata) cacheAeroportos[trecho.destino.iata] = trecho.destino;
        });
    });

    rota.forEach(t => {
        if (typeof t.origem === 'object' && cacheAeroportos[t.origem.iata]) {
            t.origem = cacheAeroportos[t.origem.iata];
        } else {
             if(t === rota[0]) t.origem = { iata: t.origem.iata, lat: window.origemCoords.lat, lon: window.origemCoords.lon };
        }

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

    document.getElementById('aviso-modo-visualizacao').classList.add('hidden');
    document.getElementById('container-estrategias').style.display = 'grid'; // Grid do LuftCore
    
    document.getElementById('btn-confirmar').style.display = 'inline-flex'; // Mantém o flex do botão
    document.getElementById('btn-recalcular').classList.add('hidden');
    document.getElementById('btn-cancelar-plan').classList.add('hidden');

    SelecionarEstrategia('recomendada');
};

window.CancelarPlanejamentoExistente = function() {
    if(!confirm('Tem certeza que deseja CANCELAR este planejamento? O status voltará para pendente.')) return;

    const id = window.planejamentoSalvo.id_planejamento;
    const btn = document.getElementById('btn-cancelar-plan');
    const txtOriginal = btn.innerHTML;
    btn.innerHTML = '<i class="ph-bold ph-spinner ph-spin"></i>...';
    btn.disabled = true;

    fetch(URL_CANCELAR_PLANEJAMENTO, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ id_planejamento: id })
    })
    .then(r => r.json())
    .then(d => {
        if(d.sucesso) {
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
    const key = ciaName.toUpperCase().split(' ')[0]; 
    return CIA_CONFIG[key] || CIA_CONFIG['DEFAULT'];
}

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

    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        maxZoom: 19
    }).addTo(map);

    L.control.zoom({ position: 'topright' }).addTo(map);
    routeLayerGroup = L.layerGroup().addTo(map);
}

// --- 2. Seleção de Estratégia ---
window.SelecionarEstrategia = function(tipo) {
    currentState.estrategia = tipo;

    // 1. Atualiza UI das Abas
    document.querySelectorAll('.luft-strategy-btn').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`tab-${tipo}`);
    if(btn) btn.classList.add('active');

    // 2. Recupera a rota
    const rotas = window.opcoesRotas[tipo];
    currentState.rotaSelecionada = rotas;

    // 3. Renderização
    if (rotas && rotas.length > 0) {
        RenderizarRotaNoMapa(rotas);
        RenderizarTimeline(rotas);
        AtualizarMetricas(rotas);
    } else {
        routeLayerGroup.clearLayers();
        document.getElementById('timeline-content').innerHTML = `
            <div style="text-align: center; padding: 60px 20px; color: var(--luft-text-muted);">
                <i class="ph-duotone ph-airplane-slash text-muted" style="font-size: 3rem; margin-bottom: 10px;"></i>
                <p class="font-bold text-main">Nenhuma rota encontrada</p>
                <p class="text-xs">Não há voos para esta estratégia.</p>
            </div>`;
        AtualizarMetricas(null);
    }
    
    AtualizarBotaoSalvar(rotas);
};

function AtualizarBotaoSalvar(rotas) {
    const btnSalvar = document.getElementById('btn-confirmar');
    if(!rotas || rotas.length === 0) {
        btnSalvar.disabled = true;
        btnSalvar.innerHTML = '<i class="ph-bold ph-warning"></i> Indisponível';
        btnSalvar.classList.remove('btn-success');
        btnSalvar.classList.add('btn-secondary');
        btnSalvar.style.cursor = 'not-allowed';
    } else {
        btnSalvar.disabled = false;
        btnSalvar.innerHTML = '<i class="ph-bold ph-check-circle"></i> Confirmar Rota';
        btnSalvar.classList.remove('btn-secondary');
        btnSalvar.classList.add('btn-success');
        btnSalvar.style.cursor = 'pointer';
    }
}

// --- 3. Renderização Visual (Mapa Rico) ---

function RenderizarRotaNoMapa(listaTrechos) {
    routeLayerGroup.clearLayers();
    if (!listaTrechos || listaTrechos.length === 0) return;

    const allLatlngs = [];
    
    const cityOrigem = [window.origemCoords.lat, window.origemCoords.lon];
    const cityDestino = [window.destinoCoords.lat, window.destinoCoords.lon];
    const aeroOrigem = [listaTrechos[0].origem.lat, listaTrechos[0].origem.lon];
    const aeroDestino = [listaTrechos[listaTrechos.length-1].destino.lat, listaTrechos[listaTrechos.length-1].destino.lon];

    // --- A. TRECHO COLETA ---
    L.polyline([cityOrigem, aeroOrigem], {
        color: 'var(--luft-text-muted)', 
        weight: 3, dashArray: '5, 10', opacity: 0.7
    }).addTo(routeLayerGroup);

    const iconColeta = L.divIcon({
        className: '',
        html: `<div style="background: var(--luft-text-muted); color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid white; box-shadow: var(--luft-shadow-md);"><i class="ph-fill ph-truck"></i></div>`,
        iconSize: [32, 32], iconAnchor: [16, 16]
    });
    L.marker(cityOrigem, { icon: iconColeta }).addTo(routeLayerGroup)
     .bindPopup(`<div class="font-bold text-main">Coleta na Origem</div><div class="text-xs text-muted">${window.ctc.origem_cidade}</div>`);
     
    allLatlngs.push(cityOrigem);

    // --- B. TRECHOS AÉREOS ---
    listaTrechos.forEach((trecho, index) => {
        const origem = [trecho.origem.lat, trecho.origem.lon];
        const destino = [trecho.destino.lat, trecho.destino.lon];
        const ciaInfo = getCiaConfig(trecho.cia);

        const baseCalc = trecho.base_calculo || {};
        const idFrete = baseCalc.id_frete || 'N/A'; 
        const tarifa = baseCalc.tarifa || 0;
        const servico = baseCalc.servico || 'STD';
        const custoTrechoFmt = baseCalc.custo_trecho_fmt || 'R$ 0,00';

        const polyline = L.polyline([origem, destino], {
            color: ciaInfo.color, weight: 4, opacity: 0.9
        }).addTo(routeLayerGroup);

        if (index === 0) {
            L.circleMarker(origem, { color: ciaInfo.color, radius: 5, fillOpacity: 1, fillColor: '#fff' })
             .addTo(routeLayerGroup).bindTooltip(`<b style="font-family: monospace;">${trecho.origem.iata}</b>`, {permanent: true, direction: 'top'});
        }
        L.circleMarker(destino, { color: ciaInfo.color, radius: 5, fillOpacity: 1, fillColor: '#fff' })
         .addTo(routeLayerGroup).bindTooltip(`<b style="font-family: monospace;">${trecho.destino.iata}</b>`, {permanent: true, direction: 'top'});
        
        allLatlngs.push(origem);
        allLatlngs.push(destino);

        const midLat = (trecho.origem.lat + trecho.destino.lat) / 2;
        const midLon = (trecho.origem.lon + trecho.destino.lon) / 2;
        const angle = calculateBearing(trecho.origem.lat, trecho.origem.lon, trecho.destino.lat, trecho.destino.lon);

        const planeIcon = L.divIcon({
            className: '',
            html: `<i class="ph-fill ph-airplane" style="font-size: 26px; color: ${ciaInfo.color}; transform: rotate(${angle - 90}deg); filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));"></i>`,
            iconSize: [30, 30], iconAnchor: [15, 15]
        });
        const planeMarker = L.marker([midLat, midLon], { icon: planeIcon }).addTo(routeLayerGroup);

        // Popup com padrão LuftCore
        const popupContent = `
            <div style="min-width: 260px; padding-left: 8px; border-left: 4px solid ${ciaInfo.color}">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <img src="/Luft-ConnectAir/Static/Img/Logos/${ciaInfo.icon}" style="width: 24px; height: 24px; object-fit: contain;" onerror="this.style.display='none'">
                        <div>
                            <div style="font-weight: 800; color: #1e293b; line-height: 1;">${trecho.cia}</div>
                            <div style="font-size: 0.75rem; color: #64748b; font-weight: 600;">Voo ${trecho.voo}</div>
                        </div>
                    </div>
                    <div style="font-size: 0.75rem; font-weight: 700; color: #64748b;">${trecho.data.substring(0,5)}</div>
                </div>
                
                <div style="display: flex; align-items: center; justify-content: space-between; background: #f8fafc; padding: 10px; border-radius: 8px; margin-bottom: 12px; border: 1px solid #e2e8f0;">
                    <div style="text-align: center;">
                        <div style="font-weight: 900; color: #0f172a; font-size: 1.1rem;">${trecho.origem.iata}</div>
                        <div style="font-size: 0.7rem; color: #64748b; font-weight: 700;">${trecho.horario_saida}</div>
                    </div>
                    <i class="ph-fill ph-airplane" style="color: #cbd5e1; font-size: 1.2rem;"></i>
                    <div style="text-align: center;">
                        <div style="font-weight: 900; color: #0f172a; font-size: 1.1rem;">${trecho.destino.iata}</div>
                        <div style="font-size: 0.7rem; color: #64748b; font-weight: 700;">${trecho.horario_chegada}</div>
                    </div>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                    <div style="background: #f8fafc; padding: 6px; border-radius: 6px; border: 1px solid #e2e8f0;">
                        <span style="font-size: 0.65rem; color: #64748b; display: block; text-transform: uppercase; font-weight: 700;">ID Frete</span>
                        <span style="font-weight: 700; color: #0f172a; font-size: 0.85rem;">#${idFrete}</span>
                    </div>
                    <div style="background: #f8fafc; padding: 6px; border-radius: 6px; border: 1px solid #e2e8f0;">
                        <span style="font-size: 0.65rem; color: #64748b; display: block; text-transform: uppercase; font-weight: 700;">Serviço</span>
                        <span style="font-weight: 700; color: #0f172a; font-size: 0.85rem;">${servico}</span>
                    </div>
                    <div style="background: #f8fafc; padding: 6px; border-radius: 6px; border: 1px solid #e2e8f0;">
                        <span style="font-size: 0.65rem; color: #64748b; display: block; text-transform: uppercase; font-weight: 700;">Tarifa/kg</span>
                        <span style="font-weight: 700; color: #0f172a; font-size: 0.85rem;">${formatMoney(tarifa)}</span>
                    </div>
                    <div style="background: #f0fdf4; padding: 6px; border-radius: 6px; border: 1px solid #bbf7d0;">
                        <span style="font-size: 0.65rem; color: #16a34a; display: block; text-transform: uppercase; font-weight: 700;">Total Trecho</span>
                        <span style="font-weight: 900; color: #15803d; font-size: 0.85rem;">${custoTrechoFmt}</span>
                    </div>
                </div>
            </div>
        `;
        polyline.bindPopup(popupContent, { minWidth: 260 });
        planeMarker.bindPopup(popupContent, { minWidth: 260 });
    });

    // --- C. TRECHO ENTREGA ---
    L.polyline([aeroDestino, cityDestino], {
        color: 'var(--luft-text-muted)', 
        weight: 3, dashArray: '5, 10', opacity: 0.7
    }).addTo(routeLayerGroup);

    const iconEntrega = L.divIcon({
        className: '',
        html: `<div style="background: var(--luft-success); color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid white; box-shadow: var(--luft-shadow-md);"><i class="ph-fill ph-flag-checkered"></i></div>`,
        iconSize: [32, 32], iconAnchor: [16, 16]
    });
    L.marker(cityDestino, { icon: iconEntrega }).addTo(routeLayerGroup)
     .bindPopup(`<div class="font-bold text-main">Entrega no Destino</div><div class="text-xs text-muted">${window.ctc.destino_cidade}</div>`);
     
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

    if (!listaTrechos || listaTrechos.length === 0) return;

    let html = '<div style="padding: 16px;">';
    listaTrechos.forEach((trecho, idx) => {
        const ciaInfo = getCiaConfig(trecho.cia);
        
        const baseCalc = trecho.base_calculo || {};
        const idFrete = baseCalc.id_frete || 'N/A';
        const tarifa = baseCalc.tarifa || 0;
        const servico = baseCalc.servico || 'STD';
        const custoTrechoFmt = baseCalc.custo_trecho_fmt || 'R$ 0,00';

        if (idx > 0) {
            html += `<div class="text-center my-3 text-xs font-bold text-muted" style="text-transform: uppercase;"><i class="ph-bold ph-arrows-left-right"></i> Conexão em ${trecho.origem.iata}</div>`;
        }

        html += `
            <div class="luft-card p-3 mb-2 hover-lift" onclick="map.flyTo([${trecho.origem.lat}, ${trecho.origem.lon}], 8)" style="cursor: pointer; border-left: 4px solid ${ciaInfo.color}">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <div class="d-flex align-items-center gap-2">
                         <div class="d-flex align-items-center justify-content-center bg-app rounded border" style="width: 32px; height: 32px;">
                            <img src="/Luft-ConnectAir/Static/Img/Logos/${ciaInfo.icon}" style="max-width: 20px; max-height: 20px;" onerror="this.src='https://placehold.co/40x40?text=A'">
                         </div>
                         <div>
                            <div class="font-bold text-main" style="line-height: 1;">${trecho.cia} ${trecho.voo}</div>
                            <div class="text-xs text-muted">Data: ${trecho.data.substring(0,5)}</div>
                         </div>
                    </div>
                </div>
                
                <div class="d-flex justify-content-between align-items-center bg-app p-3 rounded mb-3 border">
                    <div class="text-center">
                        <div class="font-black text-main text-lg" style="line-height: 1;">${trecho.origem.iata}</div>
                        <div class="text-xs font-bold text-muted">${trecho.horario_saida}</div>
                    </div>
                    <i class="ph-bold ph-airplane-tilt" style="color: ${ciaInfo.color}; font-size: 1.5rem;"></i>
                    <div class="text-center">
                        <div class="font-black text-main text-lg" style="line-height: 1;">${trecho.destino.iata}</div>
                        <div class="text-xs font-bold text-muted">${trecho.horario_chegada}</div>
                    </div>
                </div>

                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; text-align: center;">
                    <div class="bg-panel p-2 rounded border">
                        <span class="text-xs text-muted d-block mb-1 font-bold">ID Frete</span>
                        <span class="font-bold text-main text-xs">#${idFrete}</span>
                    </div>
                    <div class="bg-panel p-2 rounded border">
                        <span class="text-xs text-muted d-block mb-1 font-bold">Serviço</span>
                        <span class="font-bold text-main text-xs">${servico}</span>
                    </div>
                    <div class="bg-panel p-2 rounded border">
                        <span class="text-xs text-muted d-block mb-1 font-bold">Tarifa</span>
                        <span class="font-bold text-main text-xs">${formatMoney(tarifa)}</span>
                    </div>
                    <div class="bg-panel p-2 rounded border" style="background: rgba(34, 197, 94, 0.1); border-color: rgba(34, 197, 94, 0.2) !important;">
                        <span class="text-xs text-success font-bold d-block mb-1">Custo</span>
                        <span class="font-black text-success text-xs">${custoTrechoFmt}</span>
                    </div>
                </div>
            </div>
        `;
    });
    html += '</div>';
    container.innerHTML = html;
}

// --- 5. Atualização das Métricas ---
function AtualizarMetricas(listaTrechos) {
    const elCusto = document.getElementById('metrica-custo');
    const elTempo = document.getElementById('metrica-tempo');
    const elConex = document.getElementById('metrica-conexoes');

    if(!listaTrechos || listaTrechos.length === 0) {
        if(elCusto) elCusto.innerText = '--';
        if(elTempo) elTempo.innerText = '--';
        if(elConex) elConex.innerText = '--';
        return;
    }
    
    const resumo = listaTrechos[0]; 
    
    if(elCusto) elCusto.innerText = resumo.total_custo_fmt || formatMoney(resumo.total_custo_raw); 
    if(elTempo) elTempo.innerText = resumo.total_duracao || '--:--';
    
    const qtdEscalas = listaTrechos.length - 1;
    let textoEscalas = "Direto";
    if (qtdEscalas === 1) textoEscalas = "1 Conexão";
    if (qtdEscalas > 1) textoEscalas = `${qtdEscalas} Conexões`;
    
    if(elConex) elConex.innerText = textoEscalas;
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
            
            id_frete: base.id_frete || null,         
            tipo_servico: base.servico || null,      
            valor_tarifa: base.tarifa || 0,
            peso_cobrado: base.peso_usado || 0,
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
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-info');
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
    }
};

window.FecharModalLote = function(event) {
    if (event && !event.target.classList.contains('luft-modal-lote-backdrop') && !event.target.classList.contains('btn-icon-only')) return;

    const backdrop = document.getElementById('modal-lote-backdrop');
    if(backdrop) {
        backdrop.classList.add('hidden'); 
    }
};