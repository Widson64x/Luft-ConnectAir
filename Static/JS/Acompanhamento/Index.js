/**
 * Arquivo: dashboard.js
 * Responsável pela lógica do Painel de Acompanhamento (FlightOps)
 */

var map = null;
var layerGeral = new L.LayerGroup(); 
var layerFoco = new L.LayerGroup();  

document.addEventListener('DOMContentLoaded', () => { 
    InitMap(); 
    CarregarDados(); 
});

function GetCorPorCia(texto) {
    if(!texto) return '#64748b';
    const t = texto.toUpperCase().trim(); 
    if (t.includes('LATAM') || t.includes('TAM') || /^(LA|JJ)(\s|-|\d|$)/.test(t)) return '#e30613';
    if (t.includes('GOL') || /^(G3)(\s|-|\d|$)/.test(t)) return '#ff7020';
    if (t.includes('AZUL') || /^(AD)(\s|-|\d|$)/.test(t)) return '#0d6efd';
    return '#64748b';
}

function InitMap() {
    if(map) return;
    map = L.map('mapa-voos', { zoomControl: false }).setView([-14.2350, -51.9253], 4);
    L.control.zoom({ position: 'topright' }).addTo(map);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', { attribution: '&copy; FlightOps', maxZoom: 18 }).addTo(map);
    layerGeral.addTo(map);
    layerFoco.addTo(map);
}

function CarregarDados() {
    // 1. Captura os valores dos inputs
    const inicio = document.getElementById('dataInicio').value;
    const fim = document.getElementById('dataFim').value;
    const awbBusca = document.getElementById('buscaAwb').value;
    const filialCtcBusca = document.getElementById('buscaFilialCtc').value;

    const tbody = document.querySelector('#tabela-awbs tbody');

    // 2. Estado de Carregamento
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:60px; color:var(--cor-texto-secundario);"><i class="ph-spinner ph-spin" style="font-size:28px;"></i><br><span style="margin-top:10px; display:block">Buscando cargas...</span></td></tr>`;
    
    ResetarMapaVisual(); 

    // 3. Montagem da URL usando o objeto de configuração global
    let url = `${APP_CONFIG.urls.listarAwbs}?dataInicio=${inicio}&dataFim=${fim}`;
    
    if(awbBusca) url += `&numeroAwb=${encodeURIComponent(awbBusca)}`;
    if(filialCtcBusca) url += `&filialCtc=${encodeURIComponent(filialCtcBusca)}`;

    // 4. Requisição
    fetch(url)
        .then(res => res.json())
        .then(data => {
            tbody.innerHTML = '';
            document.getElementById('lbl-total').innerText = data.length;

            if(data.length === 0) {
                tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:40px;">Nenhum registro encontrado.</td></tr>`;
                return;
            }

            data.forEach(awb => {
                PlotarRotaResumo(awb);
                const rowId = `row-${awb.CodigoId}`;
                const corCia = GetCorPorCia(awb.CiaAerea);

                // Lógica de Status (Cores das Badges)
                let badgeClass = 'badge-secondary';
                const status = awb.Status ? awb.Status.toUpperCase() : '';

                const successStatus = ['ENTREGUE', 'CARGA ENTREGUE'];
                const dangerStatus = ['RETIDA', 'ATRASADO', 'DELAY', 'CANCELADO'];
                const warningStatus = ['RECEPCAO DOCUMENTAL', 'LIBERADO PELA FISCALIZAÇÃO', 'EM PROCESSO DE LIBERAÇÃO FISCAL'];
                const infoStatus = ['CARGA ALOCADA', 'EMBARQUE CONFIRMADO', 'AGUARDANDO DESEMBARQUE', 'AGUARDANDO', 'CARGA DESEMBARCADA', 'EMBARQUE SURFACE', 'DESEMBARQUE VÔO', 'EMBARQUE VÔO'];

                if (successStatus.some(s => status.includes(s))) badgeClass = 'badge-success';
                else if (dangerStatus.some(s => status.includes(s))) badgeClass = 'badge-danger';
                else if (warningStatus.some(s => status.includes(s))) badgeClass = 'badge-warning';
                else if (infoStatus.some(s => status.includes(s))) badgeClass = 'badge-info';

                // Coluna Voo Interativo
                let htmlVoo = '<span style="color:#ccc;">-</span>';
                if(awb.Voo && awb.Voo.length > 2) {
                    htmlVoo = `<span class="voo-interativo" title="Duplo clique para detalhes do voo" 
                               ondblclick="AbrirModalVoo('${awb.Voo}', '${awb.DataStatus}', event)">
                               <i class="ph-bold ph-airplane-tilt"></i> ${awb.Voo}</span>`;
                }

                // Criação da Linha Principal
                let trMain = document.createElement('tr');
                trMain.className = 'row-main';
                trMain.id = rowId;
                trMain.onclick = (e) => { 
                    if(!e.target.closest('.voo-interativo') && !e.target.closest('td[ondblclick]')) {
                        ToggleTree(awb.Numero, rowId); 
                    }
                };
                
                trMain.innerHTML = `
                    <td style="text-align:center;">
                        <i class="ph-bold ph-caret-right" id="icon-${rowId}" style="color:#64748b;"></i>
                    </td>

                    <td style="font-weight:700; color:var(--cor-primaria); font-family:monospace; cursor:pointer;"
                        title="Duplo clique para ver detalhes completos da Carga"
                        ondblclick="AbrirModalAwbDetalhes('${awb.CodigoId}', event)">
                        ${awb.Numero}
                    </td>

                    <td><span style="font-weight:600; color:${corCia};">${awb.CiaAerea || 'INDEF'}</span></td>
                    <td><span style="font-weight:700;">${awb.Origem}</span> <i class="ph-bold ph-arrow-right" style="font-size:0.8rem; color:#ccc;"></i> <span style="font-weight:700;">${awb.Destino}</span></td>
                    <td>${htmlVoo}</td>
                    <td>${awb.Peso.toFixed(1)} kg</td>
                    <td><span class="badge ${badgeClass}">${awb.Status}</span></td>
                    <td style="color:var(--cor-texto-secundario); font-size:0.8rem;">${awb.DataStatus}</td>
                `;

                // Criação da Linha de Detalhe
                let trDetail = document.createElement('tr');
                trDetail.id = `detail-${rowId}`;
                trDetail.style.display = 'none';
                trDetail.innerHTML = `<td colspan="8" class="detail-cell"><div id="container-${rowId}" style="min-height:100px; padding:20px;">Carregando...</div></td>`;
                
                tbody.appendChild(trMain);
                tbody.appendChild(trDetail);
            });
        });
}

function PlotarRotaResumo(awb) {
    if(awb.RotaMap && awb.RotaMap.Origem) {
        const linha = L.polyline([awb.RotaMap.Origem, awb.RotaMap.Destino], { color: GetCorPorCia(awb.CiaAerea), weight: 2, opacity: 0.4, dashArray: '3, 6' });
        linha.awbNumero = awb.Numero; 
        linha.addTo(layerGeral);
    }
}

function ToggleTree(numeroAwb, rowId) {
    const trMain = document.getElementById(rowId);
    const trDetail = document.getElementById(`detail-${rowId}`);
    const icon = document.getElementById(`icon-${rowId}`);
    const container = document.getElementById(`container-${rowId}`);
    
    document.querySelectorAll('[id^="detail-"]').forEach(el => { if(el.id !== `detail-${rowId}`) el.style.display = 'none'; });
    document.querySelectorAll('.row-main').forEach(el => { if(el.id !== rowId) el.classList.remove('active'); });

    if (trDetail.style.display === 'none') {
        trMain.classList.add('active');
        trDetail.style.display = 'table-row';
        icon.style.transform = 'rotate(90deg)';
        FocarRotaNoMapa(numeroAwb);
        
        // Uso da URL configurada
        fetch(`${APP_CONFIG.urls.historico}${encodeURIComponent(numeroAwb)}`)
            .then(res => res.json())
            .then(resp => {
                RenderizarTimeline(resp, container);
                DesenharRotaReal(resp, numeroAwb);
            });
    } else {
        trMain.classList.remove('active');
        trDetail.style.display = 'none';
        icon.style.transform = 'rotate(0deg)';
        ResetarMapaVisual();
    }
}

function RenderizarTimeline(data, container) {
    const historico = data.Historico || [];
    if(historico.length === 0) { container.innerHTML = `Sem histórico.`; return; }

    let html = `<div class="timeline-container">`;
    historico.forEach((h, index) => {
        let statusClass = index === 0 && !h.Status.includes('ENTREGUE') ? 'active' : 'completed';
        
        let vooDisplay = '';
        if(h.Voo && h.Voo.length > 2) {
            vooDisplay = `<span class="voo-interativo" style="background:#e0f2fe; color:#0369a1; padding:2px 8px; border-radius:4px;"
                          ondblclick="AbrirModalVoo('${h.Voo}', '${h.Data}', event)">
                          <i class="ph-airplane-tilt"></i> ${h.Voo}</span>`;
        }

        html += `
            <div class="tl-item" style="display:flex; gap:20px; padding-bottom:20px; position:relative;">
                <div style="position:absolute; left:7px; top:20px; bottom:0; width:2px; background:#e2e8f0;"></div>
                <div style="width:16px; height:16px; border-radius:50%; background:${statusClass === 'active' ? '#fff' : '#10b981'}; border:2px solid ${statusClass === 'active' ? '#f59e0b' : '#10b981'}; z-index:2;"></div>
                <div style="flex:1;">
                    <div style="font-weight:700; color:#1e293b;">${h.Status}</div>
                    <div style="font-size:0.8rem; color:#64748b;">${h.Data}</div>
                    <div style="margin-top:6px; font-size:0.8rem; display:flex; gap:12px;">
                        <span style="background:#f1f5f9; padding:2px 8px; border-radius:4px;"><i class="ph-map-pin"></i> ${h.Local}</span>
                        ${vooDisplay}
                    </div>
                </div>
            </div>`;
    });
    html += `</div>`;
    container.innerHTML = html;
}

function FocarRotaNoMapa(numeroAwb) {
    layerGeral.eachLayer(l => l.setStyle({ opacity: l.awbNumero === numeroAwb ? 0 : 0.05 }));
    layerFoco.clearLayers();
}

function DesenharRotaReal(data, numeroAwb) {
    const trajetos = data.TrajetoCompleto || [];
    const pendente = data.RotaPendente;
    let bounds = [];
    
    const iconDot = (c) => L.divIcon({ html: `<div style="background:${c}; width:12px; height:12px; border:2px solid #fff; border-radius:50%; box-shadow:0 2px 4px rgba(0,0,0,0.3);"></div>` });
    const iconPlane = (c) => L.divIcon({ html: `<div style="background:${c}; width:26px; height:26px; display:flex; align-items:center; justify-content:center; border:2px solid #fff; border-radius:6px;"><i class="ph-fill ph-airplane-tilt" style="color:#fff; font-size:16px;"></i></div>`, iconSize: [26, 26] });

    if(trajetos.length > 0) {
        L.marker(trajetos[0].CoordOrigem, { icon: iconDot('#10b981') }).addTo(layerFoco).bindPopup(`Origem: ${trajetos[0].Origem}`);
        bounds.push(trajetos[0].CoordOrigem);

        trajetos.forEach((leg, idx) => {
            L.polyline([leg.CoordOrigem, leg.CoordDestino], { color: GetCorPorCia(leg.Voo), weight: 4, opacity: 0.9 }).addTo(layerFoco);
            
            if(idx === trajetos.length - 1) {
                let ic = pendente ? iconPlane('#f59e0b') : iconPlane('#10b981');
                L.marker(leg.CoordDestino, { icon: ic }).addTo(layerFoco);
            } else {
                L.marker(leg.CoordDestino, { icon: iconDot('#fff') }).addTo(layerFoco);
            }
            bounds.push(leg.CoordDestino);
        });
    } else if (pendente) {
            L.marker(pendente.CoordOrigem, { icon: iconPlane('#ef4444') }).addTo(layerFoco);
            bounds.push(pendente.CoordOrigem);
    }

    if (pendente) {
        L.polyline([pendente.CoordOrigem, pendente.CoordDestino], { color: '#94a3b8', weight: 3, dashArray: '5, 10' }).addTo(layerFoco);
        L.marker(pendente.CoordDestino, { icon: iconDot('#cbd5e1') }).addTo(layerFoco);
        bounds.push(pendente.CoordDestino);
    }

    if(bounds.length > 0) map.fitBounds(bounds, { padding: [60, 60] });
}

function ResetarMapaVisual() {
    layerFoco.clearLayers();
    layerGeral.eachLayer(l => l.setStyle({ opacity: 0.3 }));
    map.setView([-14.2350, -51.9253], 4);
}

// --- FUNÇÕES DO MODAL DE VOO ---
function AbrirModalVoo(numero, dataRef, event) {
    if(event) { event.stopPropagation(); event.preventDefault(); } 
    
    const modal = document.getElementById('modal-voo');
    modal.style.display = 'flex'; 
    
    document.getElementById('mv-numero').innerText = 'BUSCANDO...';
    
    // Uso da URL configurada
    const url = `${APP_CONFIG.urls.detalhesVoo}?numeroVoo=${numero}&dataRef=${dataRef}`;

    fetch(url)
        .then(r => r.json())
        .then(resp => {
            if(resp.sucesso) {
                const d = resp.dados;
                document.getElementById('mv-cia').innerText = d.Cia;
                document.getElementById('mv-numero').innerText = `${d.Cia} ${d.Numero}`;
                document.getElementById('mv-origem').innerText = d.OrigemIata;
                document.getElementById('mv-origem-nome').innerText = d.OrigemNome;
                document.getElementById('mv-destino').innerText = d.DestinoIata;
                document.getElementById('mv-destino-nome').innerText = d.DestinoNome;
                document.getElementById('mv-data').innerText = d.Data;
                document.getElementById('mv-saida').innerText = d.HorarioSaida;
                document.getElementById('mv-chegada').innerText = d.HorarioChegada;

                const head = document.getElementById('mv-header');
                head.className = 'm-header'; 
                const cia = d.Cia.toUpperCase();
                if(cia.includes('LATAM') || cia.includes('LA')) head.classList.add('mh-latam');
                else if(cia.includes('GOL') || cia.includes('G3')) head.classList.add('mh-gol');
                else if(cia.includes('AZUL') || cia.includes('AD')) head.classList.add('mh-azul');
                else head.classList.add('mh-default');

            } else {
                alert(resp.msg || "Detalhes não encontrados.");
                FecharModalVoo();
            }
        })
        .catch(() => {
            alert("Erro ao buscar detalhes do voo.");
            FecharModalVoo();
        });
}

function FecharModalVoo() {
    document.getElementById('modal-voo').style.display = 'none';
}