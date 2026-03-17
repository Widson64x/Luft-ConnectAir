/**
 * Editor.js - Cockpit de Planejamento 
 * Refatorado com Classes, camelCase e Rotas Injetadas
 */

class GerenciadorEditor {
    constructor() {
        this.mapa = null;
        this.camadaRotas = null;
        
        this.estadoAtual = {
            estrategia: 'recomendada',
            rotaSelecionada: null
        };

        this.configuracoesCias = {
            'AZUL': { cor: '#0ea5e9', icone: 'AZUL.png' },     
            'GOL':  { cor: '#f59e0b', icone: 'GOL.png' },      
            'LATAM': { cor: '#ef4444', icone: 'LATAM.png' },   
            'DEFAULT': { cor: '#64748b', icone: 'default.png' } 
        };
    }

    inicializar() {
        this.inicializarMapa();
        
        if (dadosEditor.planejamentoSalvo && dadosEditor.planejamentoSalvo.id_planejamento) {
            this.iniciarModoVisualizacao(dadosEditor.planejamentoSalvo);
        } else {
            setTimeout(() => this.selecionarEstrategia('recomendada'), 300);
        }
    }

    inicializarMapa() {
        const lat = dadosEditor.origemCoords.lat || -15.79;
        const lon = dadosEditor.origemCoords.lon || -47.88;

        this.mapa = L.map('map', { zoomControl: false, attributionControl: false }).setView([lat, lon], 5);

        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            maxZoom: 19
        }).addTo(this.mapa);

        L.control.zoom({ position: 'topright' }).addTo(this.mapa);
        this.camadaRotas = L.layerGroup().addTo(this.mapa);
    }

    iniciarModoVisualizacao(planejamento) {
        this.estadoAtual.estrategia = 'salva';
        this.estadoAtual.rotaSelecionada = planejamento.rota;

        this.enriquecerRotaSalva(planejamento.rota);
        this.renderizarRotaNoMapa(planejamento.rota);
        this.renderizarLinhaDoTempo(planejamento.rota);
        
        if (planejamento.metricas) {
            document.getElementById('metrica-custo').innerText = "R$ " + planejamento.metricas.custo.toLocaleString('pt-BR', {minimumFractionDigits: 2});
            document.getElementById('metrica-tempo').innerText = planejamento.metricas.duracao_fmt || "--:--";
            document.getElementById('metrica-conexoes').innerText = planejamento.metricas.escalas;
        } else {
            this.atualizarMetricas(planejamento.rota); 
        }

        document.getElementById('aviso-modo-visualizacao').classList.remove('hidden');
        document.getElementById('lbl-data-criacao').innerText = planejamento.data_criacao;
        document.getElementById('container-estrategias').style.display = 'none';
        document.getElementById('btn-confirmar').style.display = 'none';
        document.getElementById('btn-cancelar-plan').classList.remove('hidden');
        document.getElementById('btn-recalcular').classList.remove('hidden');
    }

    enriquecerRotaSalva(rota) {
        const cacheAeroportos = {};
        
        Object.values(dadosEditor.opcoesRotas).forEach(lista => {
            lista.forEach(trecho => {
                if(trecho.origem && trecho.origem.iata) cacheAeroportos[trecho.origem.iata] = trecho.origem;
                if(trecho.destino && trecho.destino.iata) cacheAeroportos[trecho.destino.iata] = trecho.destino;
            });
        });

        rota.forEach(trecho => {
            if (typeof trecho.origem === 'object' && cacheAeroportos[trecho.origem.iata]) {
                trecho.origem = cacheAeroportos[trecho.origem.iata];
            } else if (trecho === rota[0]) {
                 trecho.origem = { iata: trecho.origem.iata, lat: dadosEditor.origemCoords.lat, lon: dadosEditor.origemCoords.lon };
            }

            if (typeof trecho.destino === 'object' && cacheAeroportos[trecho.destino.iata]) {
                trecho.destino = cacheAeroportos[trecho.destino.iata];
            } else if (trecho === rota[rota.length-1]) {
                 trecho.destino = { iata: trecho.destino.iata, lat: dadosEditor.destinoCoords.lat, lon: dadosEditor.destinoCoords.lon };
            }
        });
    }

    ativarModoEdicao() {
        if(!confirm('Deseja descartar a visualização atual e calcular novas rotas?')) return;

        document.getElementById('aviso-modo-visualizacao').classList.add('hidden');
        document.getElementById('container-estrategias').style.display = 'grid'; 
        
        document.getElementById('btn-confirmar').style.display = 'inline-flex'; 
        document.getElementById('btn-recalcular').classList.add('hidden');
        document.getElementById('btn-cancelar-plan').classList.add('hidden');

        this.selecionarEstrategia('recomendada');
    }

    async cancelarPlanejamentoExistente() {
        if(!confirm('Tem certeza que deseja CANCELAR este planejamento? O status voltará para pendente.')) return;

        const id = dadosEditor.planejamentoSalvo.id_planejamento;
        const botao = document.getElementById('btn-cancelar-plan');
        const textoOriginal = botao.innerHTML;
        botao.innerHTML = '<i class="ph-bold ph-spinner ph-spin"></i>...';
        botao.disabled = true;

        try {
            const resposta = await fetch(rotasEditor.cancelarPlanejamento, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}, // Interceptador lidará com o XMLHttpRequest
                body: JSON.stringify({ id_planejamento: id })
            });
            const dados = await resposta.json();
            
            if(dados.sucesso) {
                window.location.href = rotasEditor.dashboard;
            } else {
                alert('Erro: ' + dados.msg);
                botao.innerHTML = textoOriginal;
                botao.disabled = false;
            }
        } catch (erro) {
            console.error(erro);
            botao.innerHTML = textoOriginal;
            botao.disabled = false;
        }
    }

    obterConfiguracaoCia(nomeCia) {
        if (!nomeCia) return this.configuracoesCias['DEFAULT'];
        const chave = nomeCia.toUpperCase().split(' ')[0]; 
        return this.configuracoesCias[chave] || this.configuracoesCias['DEFAULT'];
    }

    formatarMoeda(valor) {
        if (valor === undefined || valor === null) return 'R$ 0,00';
        if (typeof valor === 'string' && valor.includes('R$')) return valor;
        return parseFloat(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }

    selecionarEstrategia(tipoEstrategia) {
        this.estadoAtual.estrategia = tipoEstrategia;

        document.querySelectorAll('.luft-strategy-btn').forEach(botao => botao.classList.remove('active'));
        const botaoAtivo = document.getElementById(`tab-${tipoEstrategia}`);
        if(botaoAtivo) botaoAtivo.classList.add('active');

        const rotas = dadosEditor.opcoesRotas[tipoEstrategia];
        this.estadoAtual.rotaSelecionada = rotas;

        if (rotas && rotas.length > 0) {
            this.renderizarRotaNoMapa(rotas);
            this.renderizarLinhaDoTempo(rotas);
            this.atualizarMetricas(rotas);
        } else {
            this.camadaRotas.clearLayers();
            document.getElementById('timeline-content').innerHTML = `
                <div style="text-align: center; padding: 60px 20px; color: var(--luft-text-muted);">
                    <i class="ph-duotone ph-airplane-slash text-muted" style="font-size: 3rem; margin-bottom: 10px;"></i>
                    <p class="font-bold text-main">Nenhuma rota encontrada</p>
                    <p class="text-xs">Não há voos para esta estratégia.</p>
                </div>`;
            this.atualizarMetricas(null);
        }
        
        this.atualizarBotaoSalvar(rotas);
    }

    atualizarBotaoSalvar(rotas) {
        const botaoSalvar = document.getElementById('btn-confirmar');
        if(!rotas || rotas.length === 0) {
            botaoSalvar.disabled = true;
            botaoSalvar.innerHTML = '<i class="ph-bold ph-warning"></i> Indisponível';
            botaoSalvar.classList.remove('btn-success');
            botaoSalvar.classList.add('btn-secondary');
            botaoSalvar.style.cursor = 'not-allowed';
        } else {
            botaoSalvar.disabled = false;
            botaoSalvar.innerHTML = '<i class="ph-bold ph-check-circle"></i> Confirmar Rota';
            botaoSalvar.classList.remove('btn-secondary');
            botaoSalvar.classList.add('btn-success');
            botaoSalvar.style.cursor = 'pointer';
        }
    }

    renderizarRotaNoMapa(listaTrechos) {
        this.camadaRotas.clearLayers();
        if (!listaTrechos || listaTrechos.length === 0) return;

        const todasCoordenadas = [];
        const cidadeOrigem = [dadosEditor.origemCoords.lat, dadosEditor.origemCoords.lon];
        const cidadeDestino = [dadosEditor.destinoCoords.lat, dadosEditor.destinoCoords.lon];
        const aeroOrigem = [listaTrechos[0].origem.lat, listaTrechos[0].origem.lon];
        const aeroDestino = [listaTrechos[listaTrechos.length-1].destino.lat, listaTrechos[listaTrechos.length-1].destino.lon];

        // Trecho Coleta
        L.polyline([cidadeOrigem, aeroOrigem], {
            color: 'var(--luft-text-muted)', weight: 3, dashArray: '5, 10', opacity: 0.7
        }).addTo(this.camadaRotas);

        const iconeColeta = L.divIcon({
            className: '',
            html: `<div style="background: var(--luft-text-muted); color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid white; box-shadow: var(--luft-shadow-md);"><i class="ph-fill ph-truck"></i></div>`,
            iconSize: [32, 32], iconAnchor: [16, 16]
        });
        L.marker(cidadeOrigem, { icon: iconeColeta }).addTo(this.camadaRotas)
         .bindPopup(`<div class="font-bold text-main">Coleta na Origem</div><div class="text-xs text-muted">${dadosEditor.ctc.origem_cidade}</div>`);
         
        todasCoordenadas.push(cidadeOrigem);

        // Trechos Aéreos
        listaTrechos.forEach((trecho, indice) => {
            const origem = [trecho.origem.lat, trecho.origem.lon];
            const destino = [trecho.destino.lat, trecho.destino.lon];
            const ciaInfo = this.obterConfiguracaoCia(trecho.cia);

            const baseCalculo = trecho.base_calculo || {};
            const idFrete = baseCalculo.id_frete || 'N/A'; 
            const tarifa = baseCalculo.tarifa || 0;
            const servico = baseCalculo.servico || 'STD';
            const custoTrechoFmt = baseCalculo.custo_trecho_fmt || 'R$ 0,00';

            const polyline = L.polyline([origem, destino], {
                color: ciaInfo.cor, weight: 4, opacity: 0.9
            }).addTo(this.camadaRotas);

            if (indice === 0) {
                L.circleMarker(origem, { color: ciaInfo.cor, radius: 5, fillOpacity: 1, fillColor: '#fff' })
                 .addTo(this.camadaRotas).bindTooltip(`<b style="font-family: monospace;">${trecho.origem.iata}</b>`, {permanent: true, direction: 'top'});
            }
            L.circleMarker(destino, { color: ciaInfo.cor, radius: 5, fillOpacity: 1, fillColor: '#fff' })
             .addTo(this.camadaRotas).bindTooltip(`<b style="font-family: monospace;">${trecho.destino.iata}</b>`, {permanent: true, direction: 'top'});
            
            todasCoordenadas.push(origem);
            todasCoordenadas.push(destino);

            const meioLat = (trecho.origem.lat + trecho.destino.lat) / 2;
            const meioLon = (trecho.origem.lon + trecho.destino.lon) / 2;
            const angulo = this.calcularDirecaoVoo(trecho.origem.lat, trecho.origem.lon, trecho.destino.lat, trecho.destino.lon);

            const iconeAviao = L.divIcon({
                className: '',
                html: `<i class="ph-fill ph-airplane" style="font-size: 26px; color: ${ciaInfo.cor}; transform: rotate(${angulo - 90}deg); filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));"></i>`,
                iconSize: [30, 30], iconAnchor: [15, 15]
            });
            const marcadorAviao = L.marker([meioLat, meioLon], { icon: iconeAviao }).addTo(this.camadaRotas);

            const conteudoPopup = `
                <div style="min-width: 260px; padding-left: 8px; border-left: 4px solid ${ciaInfo.cor}">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <img src="/Luft-ConnectAir/Static/Img/Logos/${ciaInfo.icone}" style="width: 24px; height: 24px; object-fit: contain;" onerror="this.style.display='none'">
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
                            <span style="font-weight: 700; color: #0f172a; font-size: 0.85rem;">${this.formatarMoeda(tarifa)}</span>
                        </div>
                        <div style="background: #f0fdf4; padding: 6px; border-radius: 6px; border: 1px solid #bbf7d0;">
                            <span style="font-size: 0.65rem; color: #16a34a; display: block; text-transform: uppercase; font-weight: 700;">Total Trecho</span>
                            <span style="font-weight: 900; color: #15803d; font-size: 0.85rem;">${custoTrechoFmt}</span>
                        </div>
                    </div>
                </div>
            `;
            polyline.bindPopup(conteudoPopup, { minWidth: 260 });
            marcadorAviao.bindPopup(conteudoPopup, { minWidth: 260 });
        });

        // Trecho Entrega
        L.polyline([aeroDestino, cidadeDestino], {
            color: 'var(--luft-text-muted)', weight: 3, dashArray: '5, 10', opacity: 0.7
        }).addTo(this.camadaRotas);

        const iconeEntrega = L.divIcon({
            className: '',
            html: `<div style="background: var(--luft-success); color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid white; box-shadow: var(--luft-shadow-md);"><i class="ph-fill ph-flag-checkered"></i></div>`,
            iconSize: [32, 32], iconAnchor: [16, 16]
        });
        L.marker(cidadeDestino, { icon: iconeEntrega }).addTo(this.camadaRotas)
         .bindPopup(`<div class="font-bold text-main">Entrega no Destino</div><div class="text-xs text-muted">${dadosEditor.ctc.destino_cidade}</div>`);
         
        todasCoordenadas.push(cidadeDestino);

        if(todasCoordenadas.length > 0) {
            this.mapa.fitBounds(L.latLngBounds(todasCoordenadas), { 
                paddingTopLeft: [450, 80], 
                paddingBottomRight: [80, 80]
            });
        }
    }

    calcularDirecaoVoo(latOrigem, lonOrigem, latDestino, lonDestino) {
        const radLatOrigem = latOrigem * (Math.PI / 180);
        const radLonOrigem = lonOrigem * (Math.PI / 180);
        const radLatDestino = latDestino * (Math.PI / 180);
        const radLonDestino = lonDestino * (Math.PI / 180);

        const eixoY = Math.sin(radLonDestino - radLonOrigem) * Math.cos(radLatDestino);
        const eixoX = Math.cos(radLatOrigem) * Math.sin(radLatDestino) -
                  Math.sin(radLatOrigem) * Math.cos(radLatDestino) * Math.cos(radLonDestino - radLonOrigem);

        let direcao = Math.atan2(eixoY, eixoX);
        direcao = direcao * (180 / Math.PI);
        return (direcao + 360) % 360;
    }

    renderizarLinhaDoTempo(listaTrechos) {
        const container = document.getElementById('timeline-content');
        container.innerHTML = '';

        if (!listaTrechos || listaTrechos.length === 0) return;

        let html = '<div style="padding: 16px;">';
        listaTrechos.forEach((trecho, indice) => {
            const ciaInfo = this.obterConfiguracaoCia(trecho.cia);
            
            const baseCalculo = trecho.base_calculo || {};
            const idFrete = baseCalculo.id_frete || 'N/A';
            const tarifa = baseCalculo.tarifa || 0;
            const servico = baseCalculo.servico || 'STD';
            const custoTrechoFmt = baseCalculo.custo_trecho_fmt || 'R$ 0,00';

            if (indice > 0) {
                html += `<div class="text-center my-3 text-xs font-bold text-muted" style="text-transform: uppercase;"><i class="ph-bold ph-arrows-left-right"></i> Conexão em ${trecho.origem.iata}</div>`;
            }

            html += `
                <div class="luft-card p-3 mb-2 hover-lift" onclick="focarNoMapa(${trecho.origem.lat}, ${trecho.origem.lon})" style="cursor: pointer; border-left: 4px solid ${ciaInfo.cor}">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div class="d-flex align-items-center gap-2">
                             <div class="d-flex align-items-center justify-content-center bg-app rounded border" style="width: 32px; height: 32px;">
                                <img src="/Luft-ConnectAir/Static/Img/Logos/${ciaInfo.icone}" style="max-width: 20px; max-height: 20px;" onerror="this.src='https://placehold.co/40x40?text=A'">
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
                        <i class="ph-bold ph-airplane-tilt" style="color: ${ciaInfo.cor}; font-size: 1.5rem;"></i>
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
                            <span class="font-bold text-main text-xs">${this.formatarMoeda(tarifa)}</span>
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

    atualizarMetricas(listaTrechos) {
        const elementoCusto = document.getElementById('metrica-custo');
        const elementoTempo = document.getElementById('metrica-tempo');
        const elementoConexoes = document.getElementById('metrica-conexoes');

        if(!listaTrechos || listaTrechos.length === 0) {
            if(elementoCusto) elementoCusto.innerText = '--';
            if(elementoTempo) elementoTempo.innerText = '--';
            if(elementoConexoes) elementoConexoes.innerText = '--';
            return;
        }
        
        const resumo = listaTrechos[0]; 
        
        if(elementoCusto) elementoCusto.innerText = resumo.total_custo_fmt || this.formatarMoeda(resumo.total_custo_raw); 
        if(elementoTempo) elementoTempo.innerText = resumo.total_duracao || '--:--';
        
        const quantidadeEscalas = listaTrechos.length - 1;
        let textoEscalas = "Direto";
        if (quantidadeEscalas === 1) textoEscalas = "1 Conexão";
        if (quantidadeEscalas > 1) textoEscalas = `${quantidadeEscalas} Conexões`;
        
        if(elementoConexoes) elementoConexoes.innerText = textoEscalas;
    }

    async confirmarPlanejamento() {
        if (!this.estadoAtual.rotaSelecionada) return;
        const botao = document.getElementById('btn-confirmar');
        const textoOriginal = botao.innerHTML;
        
        botao.disabled = true;
        botao.innerHTML = '<i class="ph-bold ph-spinner ph-spin"></i> Processando...';

        const rotaFormatada = this.estadoAtual.rotaSelecionada.map(trecho => {
            const base = trecho.base_calculo || {};
            return {
                cia: trecho.cia,
                voo: trecho.voo,
                origem: trecho.origem.iata,
                destino: trecho.destino.iata,
                partida_iso: this.inverterData(trecho.data) + 'T' + trecho.horario_saida + ':00',
                chegada_iso: this.inverterData(trecho.data) + 'T' + trecho.horario_chegada + ':00',
                
                id_frete: base.id_frete || null,         
                tipo_servico: base.servico || null,      
                valor_tarifa: base.tarifa || 0,
                peso_cobrado: base.peso_usado || 0,
                custo_calculado: base.custo_trecho || 0
            };
        });

        const dadosPayload = {
            filial: dadosEditor.ctc.filial,
            serie: dadosEditor.ctc.serie,
            ctc: dadosEditor.ctc.ctc,
            rota_completa: rotaFormatada,
            estrategia: this.estadoAtual.estrategia
        };

        try {
            const resposta = await fetch(rotasEditor.salvarPlanejamento, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(dadosPayload)
            });
            const dados = await resposta.json();

            if(dados.sucesso) {
                botao.innerHTML = '<i class="ph-bold ph-check"></i> Sucesso!';
                botao.classList.remove('btn-primary');
                botao.classList.add('btn-info');
                setTimeout(() => {
                    window.location.href = rotasEditor.dashboard;
                }, 1000);
            } else {
                alert('Erro: ' + (dados.msg || 'Erro desconhecido'));
                botao.innerHTML = textoOriginal;
                botao.disabled = false;
            }
        } catch (erro) {
            console.error(erro);
            alert('Erro de comunicação.');
            botao.innerHTML = textoOriginal;
            botao.disabled = false;
        }
    }

    inverterData(stringData) {
        if(!stringData) return '';
        const partes = stringData.split('/');
        return `${partes[2]}-${partes[1]}-${partes[0]}`;
    }
}

// Instanciação Global
let editor;
document.addEventListener('DOMContentLoaded', () => {
    editor = new GerenciadorEditor();
    editor.inicializar();

    // Expõe as funções para a UI
    window.selecionarEstrategia = (tipo) => editor.selecionarEstrategia(tipo);
    window.ativarModoEdicao = () => editor.ativarModoEdicao();
    window.cancelarPlanejamentoExistente = () => editor.cancelarPlanejamentoExistente();
    window.confirmarPlanejamento = () => editor.confirmarPlanejamento();
    window.focarNoMapa = (lat, lon) => editor.mapa.flyTo([lat, lon], 8);

    window.abrirModalLote = () => {
        const fundo = document.getElementById('modal-lote-backdrop');
        if(fundo) fundo.classList.remove('hidden'); 
    };

    window.fecharModalLote = (evento) => {
        if (evento && !evento.target.classList.contains('luft-modal-lote-backdrop') && !evento.target.classList.contains('btn-icon-only')) return;
        const fundo = document.getElementById('modal-lote-backdrop');
        if(fundo) fundo.classList.add('hidden'); 
    };
});