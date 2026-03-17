/**
 * Map.js - Torre de Controle Global (Expedição Aérea)
 * Refatorado com Classes, camelCase e Injeção de Dados do Backend
 */

class GerenciadorMapaGlobal {
    constructor() {
        this.mapa = null;
        this.camadaMarcadores = null;
        this.filtroAtual = 'TODOS';
    }

    inicializar() {
        this.mapa = L.map('map', { zoomControl: false }).setView([-15.7, -52], 4);
        L.control.zoom({ position: 'topright' }).addTo(this.mapa);

        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            attribution: 'Luft-ConnectAir', 
            maxZoom: 18
        }).addTo(this.mapa);

        this.camadaMarcadores = L.layerGroup().addTo(this.mapa);
        this.renderizarMapa(this.filtroAtual);
    }

    formatarDinheiroCurto(valor) {
        if (!valor) return 'R$ 0';
        if (valor >= 1000000) return 'R$ ' + (valor / 1000000).toFixed(1).replace('.', ',') + 'M';
        if (valor >= 1000) return 'R$ ' + (valor / 1000).toFixed(0) + 'k';
        return valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
    }

    mudarFiltroMapa(tipoFiltro) {
        this.filtroAtual = tipoFiltro;
        
        document.querySelectorAll('.luft-mapglobal-tab').forEach(botao => botao.classList.remove('active'));
        const botaoAtivo = document.getElementById(`btn-${tipoFiltro.toLowerCase()}`);
        if(botaoAtivo) botaoAtivo.classList.add('active');

        this.renderizarMapa(tipoFiltro);

        document.getElementById('lista-ctcs').innerHTML = `
            <div style="text-align: center; padding: 40px; color: var(--luft-text-muted);">
                <i class="ph-duotone ph-funnel" style="font-size: 3rem; display:block; margin-bottom:10px;"></i>
                Filtro aplicado: <b class="text-main">${tipoFiltro}</b>.<br>Selecione um cluster no mapa.
            </div>`;
    }

    renderizarMapa(filtro) {
        this.camadaMarcadores.clearLayers();

        dadosMapaGlobal.forEach(estado => {
            const listaFiltrada = estado.lista_ctcs.filter(ctc => {
                if (filtro === 'TODOS') return true;
                return ctc.origem_dados === filtro;
            });

            if (listaFiltrada.length === 0) return;

            const qtdDocumentos = listaFiltrada.length;
            const valorTotal = listaFiltrada.reduce((acumulado, atual) => acumulado + (atual.raw_val_mercadoria || 0), 0);
            const qtdVolumes = listaFiltrada.reduce((acumulado, atual) => acumulado + (atual.volumes || 0), 0);
            const possuiUrgencia = listaFiltrada.some(ctc => ctc.eh_urgente);

            const classeCss = possuiUrgencia ? 'map-marker is-urgente' : 'map-marker';
            const classeCabecalho = possuiUrgencia ? 'bg-red' : 'bg-blue';
            const tamanhoMarcador = 90; 

            const htmlIcone = `
                <div class="marker-bubble">
                    <div class="marker-header ${classeCabecalho}">${estado.uf}</div>
                    <div class="marker-body">
                        <div class="marker-docs">${qtdDocumentos}</div>
                        <div class="marker-vols">${qtdVolumes} vol</div>
                        <div class="marker-value">${this.formatarDinheiroCurto(valorTotal)}</div>
                    </div>
                </div>
            `;

            const iconeCustomizado = L.divIcon({
                html: htmlIcone, 
                className: classeCss, 
                iconSize: [tamanhoMarcador, tamanhoMarcador], 
                iconAnchor: [tamanhoMarcador / 2, tamanhoMarcador / 2]
            });

            const marcador = L.marker([estado.coords.lat, estado.coords.lon], { icon: iconeCustomizado });
            
            marcador.on('click', () => {
                this.carregarBarraLateral(listaFiltrada);
                this.mapa.flyTo([estado.coords.lat, estado.coords.lon], 6, { duration: 1.2 });
            });

            this.camadaMarcadores.addLayer(marcador);
        });
    }

    carregarBarraLateral(listaCtcs) {
        const container = document.getElementById('lista-ctcs');
        container.innerHTML = '';

        if(listaCtcs.length === 0) {
            container.innerHTML = '<div style="text-align:center; padding: 40px; color: var(--luft-text-muted);">Nenhum registro encontrado.</div>';
            return;
        }

        const listaOrdenada = listaCtcs.sort((a, b) => {
            if (a.eh_urgente && !b.eh_urgente) return -1;
            if (!a.eh_urgente && b.eh_urgente) return 1;
            return parseFloat(b.raw_frete_total || 0) - parseFloat(a.raw_frete_total || 0);
        });

        listaOrdenada.forEach(documento => {
            const ehUrgente = documento.eh_urgente;
            const estiloBorda = ehUrgente ? 'border-left: 4px solid var(--luft-danger);' : 'border-left: 4px solid var(--luft-primary-500);';
            const htmlCracha = ehUrgente ? `<span class="luft-badge luft-badge-danger"><i class="ph-bold ph-warning"></i> URGENTE</span>` : ``;
            
            const urlFinal = rotasMapaGlobal.montarRota
                .replace('__F__', documento.filial)
                .replace('__S__', documento.serie)
                .replace('__C__', documento.ctc);

            const cartaoHtml = `
                <div class="luft-card p-3 mb-3 hover-lift" style="${estiloBorda}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="luft-badge luft-badge-secondary font-black" style="font-family: monospace;">${documento.filial}-${documento.serie}-${documento.ctc}</span>
                        ${htmlCracha}
                    </div>
                    
                    <div class="font-bold text-main mb-1 d-flex align-items-center gap-2">
                        ${documento.origem.split('/')[0]} 
                        <i class="ph-bold ph-arrow-right text-muted" style="font-size: 0.8rem;"></i> 
                        ${documento.destino.split('/')[0]}
                    </div>
                    
                    <div class="text-xs text-muted mb-3" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${documento.remetente}">
                        <i class="ph-bold ph-user"></i> ${documento.remetente}
                    </div>

                    <div class="d-flex justify-content-between align-items-center mb-3 text-xs text-muted">
                        <span><i class="ph-bold ph-calendar-blank"></i> ${documento.data_emissao}</span>
                        <span class="font-bold text-main">${documento.origem_dados}</span>
                    </div>

                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 16px;">
                        <div class="p-2 bg-app rounded text-center">
                            <span class="text-xs text-muted d-block">Peso (Fís/Tax)</span>
                            <span class="text-sm font-bold text-main">${documento.peso_fisico} / <strong>${documento.peso_taxado}</strong></span>
                        </div>
                        <div class="p-2 bg-app rounded text-center">
                            <span class="text-xs text-muted d-block">Volumes / NFs</span>
                            <span class="text-sm font-bold text-main">${documento.volumes} / ${documento.qtd_notas}</span>
                        </div>
                        <div class="p-2 bg-app rounded text-center">
                            <span class="text-xs text-muted d-block">Mercadoria</span>
                            <span class="text-sm font-bold text-success">${this.formatarDinheiroCurto(documento.raw_val_mercadoria)}</span>
                        </div>
                    </div>

                    <div style="display: grid; grid-template-columns: 1fr 40px; gap: 8px;">
                        <a href="${urlFinal}" class="btn btn-primary d-flex align-items-center justify-content-center gap-2">
                            <i class="ph-bold ph-airplane-tilt"></i> Planejar Voo
                        </a>
                        <button class="btn btn-secondary d-flex align-items-center justify-content-center" onclick="AbrirModalGlobal('${documento.filial}', '${documento.serie}', '${documento.ctc}')" title="Ver Documento Completo">
                            <i class="ph-bold ph-file-text"></i>
                        </button>
                    </div>
                </div>
            `;
            container.innerHTML += cartaoHtml;
        });
    }
}

// Instanciação e Exposição Global
let gerenciadorMapa;
document.addEventListener("DOMContentLoaded", () => {
    gerenciadorMapa = new GerenciadorMapaGlobal();
    gerenciadorMapa.inicializar();

    window.mudarFiltroMapa = (tipo) => gerenciadorMapa.mudarFiltroMapa(tipo);
});