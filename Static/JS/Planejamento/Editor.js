/**
 * Editor.js
 * Lógica de Mapas, Animação e Interação do Planejamento Visual
 */

// --- EXTENSÕES DO LEAFLET (Interpolation) ---
L.interpolatePosition = function(t, i, n, o) {
    var e = o / n;
    e = e > 0 ? e : 0, e = e > 1 ? 1 : e;
    return L.latLng(t.lat + e * (i.lat - t.lat), t.lng + e * (i.lng - t.lng))
};

L.Marker.MovingMarker = L.Marker.extend({
    initialize: function(t, i, n) {
        L.Marker.prototype.initialize.call(this, t[0], n), this._latlngs = t.map(t => L.latLng(t)), this._durations = i, this._currentDuration = 0, this._currentIndex = 0, this._state = null, this._startTime = 0, this._startTimeStamp = 0, this._pauseStartTime = 0, this._animId = 0, this._animRequested = !1, this._currentLine = []
    },
    isRunning: function() { return "run" === this._state },
    isPaused: function() { return "paused" === this._state },
    isEnded: function() { return "ended" === this._state },
    start: function() { this.isRunning() || (this.isPaused() ? this.resume() : (this._loadLine(0), this._startAnimation(), this.fire("start"))) },
    resume: function() { this.isPaused() && (this._currentLine[0] = this.getLatLng(), this._currentDuration -= this._pauseStartTime - this._startTime, this._startAnimation()) },
    pause: function() { this.isRunning() && (this._pauseStartTime = Date.now(), this._state = "paused", this._stopAnimation(), this._updatePosition()) },
    stop: function(t) { this.isEnded() || (this._stopAnimation(), void 0 === t && (t = 0, this._updatePosition()), this._state = "ended", this.fire("end", { elapsedTime: t })) },
    _startAnimation: function() { this._state = "run", this._animId = L.Util.requestAnimFrame(function(t) { this._startTime = Date.now(), this._startTimeStamp = t, this._animate(t) }, this), this._animRequested = !0 },
    _stopAnimation: function() { this._animRequested && (L.Util.cancelAnimFrame(this._animId), this._animRequested = !1) },
    _loadLine: function(t) { this._currentIndex = t, this._currentDuration = this._durations[t], this._currentLine = [this._latlngs[t], this._latlngs[t + 1]] },
    _updatePosition: function() { var t = Date.now() - this._startTime; this._animate(this._startTimeStamp + t, !0) },
    _animate: function(t, i) {
        this._animRequested = !1;
        var n = Date.now() - this._startTime, o = this._currentDuration;
        if (n < o) {
            var e = L.interpolatePosition(this._currentLine[0], this._currentLine[1], o, n);
            this.setLatLng(e), i || (this._animId = L.Util.requestAnimFrame(this._animate, this), this._animRequested = !0)
        } else this.setLatLng(this._currentLine[1]), this._currentIndex < this._latlngs.length - 2 ? (this._loadLine(this._currentIndex + 1), this._startAnimation()) : (this._state = "ended", this.fire("end", { elapsedTime: n }))
    },
    addLatLng: function(t, i) { this._latlngs.push(L.latLng(t)), this._durations.push(i) },
    moveTo: function(t, i) { this._stopAnimation(), this._latlngs = [this.getLatLng(), L.latLng(t)], this._durations = [i], this.start() }
});
L.Marker.movingMarker = function(t, i, n) { return new L.Marker.MovingMarker(t, i, n) };


// --- VARIÁVEIS GLOBAIS DE CONTROLE ---
let map, markerAnim;
let vooSelecionado = null;


// --- FUNÇÕES DE TEMPLATE (POPUPS) ---
function GetPopupCtc() {
    // Usa a variável global 'ctc' definida no HTML
    return `
        <div class="pop-header"><span>CTC ${ctc.ctc}</span><i class="ph-fill ph-truck"></i></div>
        <div class="pop-body">
            <div class="pop-row"><span style="color:var(--cor-texto-secundario)">Volumes:</span> <strong>${ctc.volumes}</strong></div>
            <div class="pop-row"><span style="color:var(--cor-texto-secundario)">Peso:</span> <strong>${ctc.peso}kg</strong></div>
            <div style="margin-top:10px; text-align:center;">
                <button onclick="AbrirModalGlobal('${ctc.filial}', '${ctc.serie}', '${ctc.ctc}')" style="background:var(--cor-primaria); color:white; border:none; padding:6px 14px; border-radius:6px; cursor:pointer; font-size:0.8rem; font-weight:600;">Ver Detalhes</button>
            </div>
        </div>
    `;
}

function GetPopupLocal(t, n, u) {
    return `<div class="pop-header"><span>${t}</span><i class="ph-fill ph-map-pin"></i></div><div class="pop-body"><div style="font-weight:700; margin-bottom:4px;">${n}</div><div style="color:var(--cor-texto-secundario);">${u}</div></div>`;
}

function GetPopupAero(i, n) {
    return `<div class="pop-header"><span>${i}</span><i class="ph-fill ph-airplane"></i></div><div class="pop-body">${n}</div>`;
}

function criarIcone(tipo) {
    let cls = 'pin-truck', ico = 'ph-truck';
    if (tipo === 'origem') { cls = 'pin-origem'; ico = 'ph-package'; }
    if (tipo === 'destino') { cls = 'pin-destino'; ico = 'ph-flag-checkered'; }
    if (tipo === 'plane') { cls = 'pin-plane'; ico = 'ph-airplane-tilt'; }
    return L.divIcon({
        className: 'custom-div-icon',
        html: `<div class="marker-pin ${cls}"><i class="ph-fill ${ico}"></i></div>`,
        iconSize: [40, 50], iconAnchor: [20, 50], popupAnchor: [0, -50]
    });
}


// --- INICIALIZAÇÃO E LOGICA DO MAPA ---
document.addEventListener("DOMContentLoaded", function() {
    // Inicializa Mapa
    map = L.map('map', { zoomControl: false }).setView([-14.2, -51.9], 4);
    L.control.zoom({ position: 'topright' }).addTo(map);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', { maxZoom: 18 }).addTo(map);

    // Marcadores Origem/Destino (Usa variáveis globais 'origem' e 'destino')
    if (origem.lat) L.marker([origem.lat, origem.lon], { icon: criarIcone('origem') }).addTo(map).bindPopup(GetPopupLocal('Origem', GLOBAL_ORIGEM_NOME, GLOBAL_ORIGEM_UF));
    if (destino.lat) L.marker([destino.lat, destino.lon], { icon: criarIcone('destino') }).addTo(map).bindPopup(GetPopupLocal('Destino', GLOBAL_DESTINO_NOME, GLOBAL_DESTINO_UF));

    // Traçar Rotas
    if (rotas && rotas.length > 0) {
        const layers = L.featureGroup();
        let pontosAnimacao = [];
        let pontoAtual = [origem.lat, origem.lon];

        pontosAnimacao.push({ loc: pontoAtual, duracao: 0, tipo: 'inicio' });

        rotas.forEach((voo, i) => {
            const pO = [voo.origem.lat, voo.origem.lon], pD = [voo.destino.lat, voo.destino.lon];
            let cor = '#333';
            if (voo.cia.includes('AZUL') || voo.cia.includes('AD')) cor = '#0055a4';
            else if (voo.cia.includes('LATAM') || voo.cia.includes('LA')) cor = '#e60000';
            else if (voo.cia.includes('GOL') || voo.cia.includes('G3')) cor = '#ff6600';

            // Rodoviário até o Aeroporto
            if (i === 0) {
                L.polyline([pontoAtual, pO], { color: '#999', dashArray: '8,12', weight: 3 }).addTo(layers);
                pontosAnimacao.push({ loc: pO, duracao: 3000, tipo: 'road' });
            }

            // Trecho Aéreo
            L.polyline([pO, pD], { color: cor, weight: 4 }).addTo(layers);
            L.circleMarker(pO, { radius: 5, color: cor, fillColor: '#fff', fillOpacity: 1 }).addTo(layers).bindPopup(GetPopupAero(voo.origem.iata, voo.origem.nome));
            L.circleMarker(pD, { radius: 5, color: cor, fillColor: '#fff', fillOpacity: 1 }).addTo(layers).bindPopup(GetPopupAero(voo.destino.iata, voo.destino.nome));

            pontosAnimacao.push({ loc: pD, duracao: 8000, tipo: 'air', cor: cor, flightIndex: i });
            pontoAtual = pD;
        });

        // Rodoviário até o Cliente
        const pFinal = [destino.lat, destino.lon];
        L.polyline([pontoAtual, pFinal], { color: '#999', dashArray: '8,12', weight: 3 }).addTo(layers);
        pontosAnimacao.push({ loc: pFinal, duracao: 3000, tipo: 'road' });

        layers.addTo(map);
        setTimeout(() => map.fitBounds(layers.getBounds(), { paddingTopLeft: [450, 50], paddingBottomRight: [50, 50] }), 500);

        window.dadosAnimacao = pontosAnimacao;
        window.iconTruck = criarIcone('truck');
        window.iconPlane = criarIcone('plane');
        setTimeout(IniciarLoop, 1500);
    }
    
    // Auto-select primeiro voo
    const primeiroCard = document.getElementById('card-flight-0');
    if (primeiroCard) {
        primeiroCard.click();
    }
});


// --- FUNÇÕES DE ANIMAÇÃO ---
function IniciarLoop() {
    if (!window.dadosAnimacao) return;
    const pontos = window.dadosAnimacao;
    let index = 0;

    ResetarIcones();

    if (markerAnim) markerAnim.remove();

    markerAnim = L.Marker.movingMarker([pontos[0].loc], [1000], { icon: window.iconTruck, zIndexOffset: 2000 }).addTo(map);
    markerAnim.bindPopup(GetPopupCtc());

    function AnimarProximo() {
        if (index >= pontos.length - 1) {
            setTimeout(() => { AtualizarUI('coleta', 0); IniciarLoop(); }, 4000);
            return;
        }
        const pProx = pontos[index + 1];

        if (pProx.tipo === 'air') {
            markerAnim.setIcon(window.iconPlane);
            AtualizarUI('aereo', 50);
            SincronizarAviaoSidebar(pProx.duracao, pProx.flightIndex);
            HighlightCardVoo(pProx.flightIndex);
        } else {
            markerAnim.setIcon(window.iconTruck);
            RemoverHighlightVoo();
            if (index === 0) AtualizarUI('coleta', 10);
            else AtualizarUI('entrega', 100);
        }

        markerAnim.moveTo(pProx.loc, pProx.duracao);
        markerAnim.once('end', function() {
            setTimeout(() => { index++; AnimarProximo(); }, 500);
        });
    }
    AnimarProximo();
}

function SincronizarAviaoSidebar(duracaoTotal, flightIndex) {
    const icon = document.getElementById('plane-icon-' + flightIndex);
    if (!icon) return;
    let startTime = null;

    function step(timestamp) {
        if (!startTime) startTime = timestamp;
        const progress = timestamp - startTime;
        const percent = Math.min(progress / duracaoTotal, 1);
        icon.style.left = (percent * 100) + '%';
        if (progress < duracaoTotal) { window.requestAnimationFrame(step); }
    }
    window.requestAnimationFrame(step);
}

function ResetarIcones() {
    document.querySelectorAll('.flight-icon-controlled').forEach(el => { el.style.left = '0%'; });
    RemoverHighlightVoo();
}

function HighlightCardVoo(idx) {
    RemoverHighlightVoo();
    const card = document.getElementById('card-flight-' + idx);
    if (card) {
        card.classList.add('active-flight');
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

function RemoverHighlightVoo() {
    document.querySelectorAll('.flight-segment').forEach(c => c.classList.remove('active-flight'));
}

function AtualizarUI(stepId, progresso) {
    document.querySelectorAll('.step-item').forEach(s => s.classList.remove('active'));
    const el = document.getElementById('step-' + stepId);
    if (el) { el.classList.add('active'); }
    const line = document.getElementById('progress-line');
    if (line) line.style.height = progresso + '%';
}


// --- INTERAÇÃO E SALVAMENTO ---
function toggleListaConsolidada() {
    var el = document.getElementById('lista-docs-consolidacao');
    el.style.display = (el.style.display === 'none') ? 'block' : 'none';
}

function SelecionarVoo(index, dadosVoo) {
    document.querySelectorAll('.flight-segment').forEach(el => {
        el.classList.remove('selected-flight');
    });

    const card = document.getElementById('card-flight-' + index);
    if (card) card.classList.add('selected-flight');

    function toIso(dataStr, horaStr) {
        if (!dataStr || !horaStr) return null;
        const parts = dataStr.split('/');
        return `${parts[2]}-${parts[1]}-${parts[0]}T${horaStr}:00`;
    }

    vooSelecionado = {
        cia: dadosVoo.cia,
        numero: dadosVoo.voo,
        partida: toIso(dadosVoo.data, dadosVoo.horario_saida),
        chegada: toIso(dadosVoo.data, dadosVoo.horario_chegada)
    };
    console.log("Voo Selecionado:", vooSelecionado);
}

function ConfirmarPlanejamento() {
    if (!rotas || rotas.length === 0) {
        alert("Não há rota aérea definida para gravar.");
        return;
    }

    const trechosFormatados = rotas.map(voo => {
        let dtParts = voo.data.split('/');
        let dataIsoBase = `${dtParts[2]}-${dtParts[1]}-${dtParts[0]}`;
        return {
            cia: voo.cia,
            voo: voo.voo,
            origem: voo.origem.iata,
            destino: voo.destino.iata,
            partida_iso: `${dataIsoBase}T${voo.horario_saida}:00`,
            chegada_iso: `${dataIsoBase}T${voo.horario_chegada}:00`
        };
    });

    const payload = {
        filial: ctc.filial,
        serie: ctc.serie,
        ctc: ctc.ctc,
        rota_completa: trechosFormatados
    };

    const btn = event.target.closest('button'); // Ajuste para garantir que pegue o button mesmo clicando no ícone
    const originalText = btn.innerHTML;
    
    btn.innerHTML = '<i class="ph-bold ph-spinner ph-spin"></i> Gravando...';
    btn.disabled = true;

    fetch(URL_GRAVAR_PLANEJAMENTO, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(r => r.json())
        .then(d => {
            if (d.sucesso) {
                btn.innerHTML = '<i class="ph-bold ph-check"></i> Salvo!';
                btn.style.background = '#10b981';
                setTimeout(() => alert('Planejamento Salvo! ID: ' + d.id_planejamento), 500);
            } else {
                alert('Erro: ' + d.msg);
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        })
        .catch(err => {
            console.error(err);
            alert("Erro de comunicação.");
            btn.disabled = false;
            btn.innerHTML = originalText;
        });
}