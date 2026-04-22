/**
 * Index.js
 * Lógica da tela de Otimizador de Escalas (Painel e Mapa)
 * Refatorado com Classes, camelCase e Injeção de Rotas
 */

class GerenciadorEscalas {
    constructor() {
        this.mapa = null;
        this.camadaVoos = null;
        this.camadaAeroportos = null;
        
        this.baseAeroportos = [];
        this.dadosUltimaBusca = null;

        // Mapeamento de UI
        this.btnBuscar = document.getElementById('btn-buscar');
        this.areaResultados = document.getElementById('area-resultados');
        this.listaOpcoes = document.getElementById('lista-opcoes');
        
        this.inputInicio = document.getElementById('data-inicio');
        this.inputFim = document.getElementById('data-fim');
        this.inputOrigem = document.getElementById('origem');
        this.inputDestino = document.getElementById('destino');
        this.inputPeso = document.getElementById('peso');
    }

    inicializar() {
        this.inicializarMapa();
        this.carregarAeroportos();
        
        // Define a data de hoje como padrão para os inputs de data
        if (this.inputInicio && this.inputFim) {
            const hojeIso = new Date().toISOString().split('T')[0];
            this.inputInicio.value = hojeIso;
            this.inputFim.value = hojeIso;
        }
    }

    inicializarMapa() {
        // Renderizador canvas é mais performático para muitas rotas
        this.mapa = L.map('mapa-rotas', { 
            zoomControl: false,
            renderer: L.canvas({ padding: 0.5 }) 
        }).setView([-15.79, -47.88], 4);

        L.control.zoom({ position: 'topright' }).addTo(this.mapa);
        
        // Camada do CartoDB (Voyager)
        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; Luft-ConnectAir', 
            maxZoom: 19
        }).addTo(this.mapa);

        this.camadaAeroportos = L.layerGroup().addTo(this.mapa);
        this.camadaVoos = L.layerGroup().addTo(this.mapa);
    }

    async carregarAeroportos() {
        try {
            const resposta = await fetch(rotasEscalas.listarAeroportos);
            this.baseAeroportos = await resposta.json();
            
            const dataList = document.getElementById('lista-aeroportos');
            if (!dataList) return;
            
            dataList.innerHTML = '';
            
            this.baseAeroportos.forEach(aeroporto => {
                const opcao = document.createElement('option');
                opcao.value = aeroporto.iata;
                opcao.label = `${aeroporto.nome} (${aeroporto.cidade})`;
                dataList.appendChild(opcao);
            });
        } catch(erro) {
            console.error("Erro ao carregar lista de aeroportos:", erro);
        }
    }

    async buscarOpcoes() {
        const parametros = {
            inicio: this.inputInicio.value,
            fim: this.inputFim.value,
            origem: this.inputOrigem.value.toUpperCase().trim(),
            destino: this.inputDestino.value.toUpperCase().trim(),
            peso: this.inputPeso.value
        };

        if (!parametros.inicio || !parametros.fim || !parametros.origem || !parametros.destino) {
            LuftCore.notificar('Por favor, preencha todos os campos obrigatórios (Datas, Origem e Destino).', 'warning');
            return;
        }

        this.btnBuscar.disabled = true;
            this.btnBuscar.innerHTML = `<i class="ph-bold ph-spinner animate-spin"></i> Processando malha...`;
        this.listaOpcoes.innerHTML = '';
        this.areaResultados.style.display = 'none';
        
        this.limparMapa();

        try {
            const queryParams = new URLSearchParams(parametros).toString();
            const urlCompleta = `${rotasEscalas.otimizarRotas}?${queryParams}`;
            
            const resposta = await fetch(urlCompleta);
            const retornoJson = await resposta.json();

            if (retornoJson.status !== 'sucesso') {
                LuftCore.notificar(retornoJson.mensagem || retornoJson.erro || 'Falha ao calcular rotas.', 'danger');
                return;
            }

            this.dadosUltimaBusca = retornoJson.dados;
            this.renderizarCards(this.dadosUltimaBusca);
            this.areaResultados.style.display = 'block';

            // Auto-seleciona a melhor opção disponível para exibição imediata
            if (this.dadosUltimaBusca.recomendada && this.dadosUltimaBusca.recomendada.length > 0) {
                this.selecionarOpcao('recomendada');
            } else {
                const chaves = Object.keys(this.dadosUltimaBusca);
                for (let chave of chaves) {
                    if (this.dadosUltimaBusca[chave] && this.dadosUltimaBusca[chave].length > 0) {
                        this.selecionarOpcao(chave);
                        break;
                    }
                }
            }

        } catch (erro) {
            console.error(erro);
            LuftCore.notificar('Erro de comunicação com o servidor ao calcular rotas.', 'danger');
        } finally {
            this.btnBuscar.disabled = false;
            this.btnBuscar.innerHTML = `<i class="ph-bold ph-lightning"></i> Calcular Melhores Rotas`;
        }
    }

    obterUrlLogo(nomeCia) {
        if (!nomeCia) return null;
        
        const termo = nomeCia.toUpperCase().trim();
        let arquivoLogo = '';

        if (termo.includes('LATAM') || termo === 'JJ' || termo === 'LA') arquivoLogo = 'LATAM.png';
        else if (termo.includes('AZUL') || termo === 'AD') arquivoLogo = 'AZUL.png';
        else if (termo.includes('GOL') || termo === 'G3') arquivoLogo = 'GOL.png';
        
        if (!arquivoLogo) return null;
        return `${rotasEscalas.baseLogos}${arquivoLogo}`;
    }

    obterCorCia(nomeCia) {
        if (!nomeCia) return '#64748b'; // Slate (Default)
        
        const termo = nomeCia.toUpperCase().trim();
        if (termo.includes('LATAM') || termo === 'JJ' || termo === 'LA') return '#e30613';
        if (termo.includes('AZUL') || termo === 'AD') return '#009FE3';
        if (termo.includes('GOL') || termo === 'G3') return '#FF7020';
        
        return '#64748b';
    }

    renderizarCards(dadosDeRotas) {
        this.listaOpcoes.innerHTML = '';
        
        const configuracoesCards = {
            'recomendada': { label: 'Recomendada', badgeClass: 'luft-badge-success', icon: 'ph-star' },
            'direta': { label: 'Voo Direto', badgeClass: 'luft-badge-success', icon: 'ph-airplane-tilt' },
            'rapida': { label: 'Mais Rápida', badgeClass: 'luft-badge-info', icon: 'ph-timer' },
            'economica': { label: 'Mais Econômica', badgeClass: 'luft-badge-warning', icon: 'ph-currency-dollar' },
            'conexao_mesma_cia': { label: 'Mesma Cia', badgeClass: 'luft-badge-primary', icon: 'ph-arrows-left-right' },
            'interline': { label: 'Interline', badgeClass: 'luft-badge-secondary', icon: 'ph-shuffle' }
        };

        Object.keys(configuracoesCards).forEach(chaveDeRota => {
            const listaTrechos = dadosDeRotas[chaveDeRota];
            if (!listaTrechos || listaTrechos.length === 0) return;

            const metadadosGlobais = listaTrechos[0]; 
            const totalConexoes = listaTrechos.length - 1;
            const possuiAvisoTarifa = metadadosGlobais.sem_tarifa; 

            // HTML dos Mini-Logos Sobrepostos (Cias Aéreas)
            let htmlLogosCias = '<div class="luft-cia-list">';
            listaTrechos.forEach((trecho, indice) => {
                const urlImagemLogo = this.obterUrlLogo(trecho.cia);
                if (urlImagemLogo) {
                    htmlLogosCias += `
                        <div class="luft-cia-logo-box" title="${trecho.cia}" style="z-index: ${10 - indice}; margin-left: ${indice > 0 ? '-8px' : '0'};">
                            <img src="${urlImagemLogo}" class="luft-cia-logo" alt="${trecho.cia}">
                        </div>
                    `;
                } else {
                    htmlLogosCias += `<span style="font-size:0.7rem; font-weight:700; margin-left:4px;">${trecho.cia}</span>`;
                }
            });
            htmlLogosCias += '</div>';

            const elementoCard = document.createElement('div');
            elementoCard.className = 'luft-option-card';
            elementoCard.id = `card-${chaveDeRota}`;
            
            const htmlCabecalhoCard = `
                <div onclick="selecionarOpcao('${chaveDeRota}')">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="luft-badge ${configuracoesCards[chaveDeRota].badgeClass}">
                            <i class="ph-bold ${configuracoesCards[chaveDeRota].icon}"></i> ${configuracoesCards[chaveDeRota].label}
                        </span>
                        <div class="d-flex align-items-center gap-2">
                            ${possuiAvisoTarifa ? `<i class="ph-fill ph-warning-circle text-warning" title="Tarifa Parcial/Ausente"></i>` : ''}
                            <span class="text-xs font-bold text-muted">${totalConexoes === 0 ? 'Direto' : totalConexoes + ' Conexões'}</span>
                        </div>
                    </div>
                    
                    <div class="d-flex justify-content-between align-items-baseline" style="font-family: 'Inter', sans-serif;">
                        <span class="font-black text-primary" style="font-size: 1.1rem;">${metadadosGlobais.total_custo || 'R$ 0,00'}</span>
                        <span class="font-bold text-main" style="font-size: 0.9rem;">${metadadosGlobais.total_duracao || '--:--'}</span>
                    </div>

                    <div class="d-flex justify-content-between align-items-center mt-3 pt-2" style="border-top: 1px dashed var(--luft-border);">
                        ${htmlLogosCias}
                        <button class="luft-btn-expand" onclick="toggleDetalhesCard(event, '${chaveDeRota}')" title="Ver detalhes por voo">
                            <i class="ph-bold ph-caret-down" id="icon-expand-${chaveDeRota}"></i>
                        </button>
                    </div>
                </div>
            `;

            let htmlDetalhesOcultos = `<div id="detalhes-${chaveDeRota}" style="display:none; margin-top:12px; border-top:1px dashed var(--luft-border); padding-top:12px;">`;
            
            listaTrechos.forEach(trecho => {
                const baseCalculo = trecho.base_calculo || {};
                const urlLogoPequeno = this.obterUrlLogo(trecho.cia); 
                
                const valorTarifa = parseFloat(baseCalculo.tarifa) || 0;
                const pesoUtilizado = parseFloat(baseCalculo.peso_usado) || 0;
                const custoTotalTrecho = valorTarifa * pesoUtilizado;
                
                const formatacaoTarifa = valorTarifa > 0 ? `R$ ${valorTarifa.toFixed(2)}` : '<span class="text-danger">--</span>';
                const formatacaoCusto = custoTotalTrecho > 0 ? `R$ ${custoTotalTrecho.toFixed(2)}` : 'R$ 0,00';
                const servicoAplicado = baseCalculo.servico || 'STD';
                
                htmlDetalhesOcultos += `
                    <div class="p-2 mb-2 bg-app rounded border" style="font-size:0.8rem; border-left: 3px solid var(--luft-primary-500);">
                        <div class="d-flex justify-content-between align-items-center font-bold text-main mb-1">
                            <span>${trecho.origem.iata} <i class="ph-bold ph-arrow-right text-muted" style="font-size:0.7rem;"></i> ${trecho.destino.iata}</span>
                            
                            <div class="d-flex align-items-center gap-2">
                                ${urlLogoPequeno ? `<img src="${urlLogoPequeno}" style="width:16px; height:16px; object-fit:contain; background:#fff; border-radius:50%;">` : ''}
                                <span class="text-primary">${trecho.voo}</span>
                            </div>
                        </div>
                        
                        <div class="d-flex justify-content-between text-xs text-muted mb-2">
                            <span>Serviço: <strong class="text-main">${servicoAplicado}</strong></span>
                            <span>Tarifa: ${formatacaoTarifa}</span>
                        </div>

                        <div class="d-flex justify-content-between align-items-center pt-1" style="border-top:1px solid var(--luft-border);">
                            <span class="font-bold text-muted">Custo Voo:</span>
                            <strong class="text-main">${formatacaoCusto}</strong>
                        </div>
                    </div>
                `;
            });
            htmlDetalhesOcultos += `</div>`;

            elementoCard.innerHTML = htmlCabecalhoCard + htmlDetalhesOcultos;
            this.listaOpcoes.appendChild(elementoCard);
        });
    }

    toggleDetalhesCard(evento, chaveDeRota) {
        evento.stopPropagation(); // Evita que o click se propague e ative o card inteiro
        
        const divDetalhes = document.getElementById(`detalhes-${chaveDeRota}`);
        const iconeExpansao = document.getElementById(`icon-expand-${chaveDeRota}`);
        
        if (!divDetalhes || !iconeExpansao) return;

        if (divDetalhes.style.display === 'none') {
            divDetalhes.style.display = 'block';
            iconeExpansao.classList.replace('ph-caret-down', 'ph-caret-up');
        } else {
            divDetalhes.style.display = 'none';
            iconeExpansao.classList.replace('ph-caret-up', 'ph-caret-down');
        }
    }

    selecionarOpcao(chaveDeRota) {
        // Remove destaque visual de todos os cards e aplica no selecionado
        document.querySelectorAll('.luft-option-card').forEach(card => card.classList.remove('active'));
        const cardSelecionado = document.getElementById(`card-${chaveDeRota}`);
        if (cardSelecionado) cardSelecionado.classList.add('active');

        this.limparMapa();
        
        const listaTrechos = this.dadosUltimaBusca[chaveDeRota];
        if (!listaTrechos) return;

        const coordenadasDeLimites = [];
        
        listaTrechos.forEach((trecho, indice) => {
            const pontoOrigem = [trecho.origem.lat, trecho.origem.lon];
            const pontoDestino = [trecho.destino.lat, trecho.destino.lon];
            
            coordenadasDeLimites.push(pontoOrigem); 
            coordenadasDeLimites.push(pontoDestino);

            const baseCalculo = trecho.base_calculo || {};
            const valorTarifa = parseFloat(baseCalculo.tarifa) || 0;
            const pesoUtilizado = parseFloat(baseCalculo.peso_usado) || 0;
            const custoTrecho = valorTarifa * pesoUtilizado;
            
            const custoFormatado = custoTrecho > 0 ? `R$ ${custoTrecho.toFixed(2)}` : 'R$ 0,00';
            const tarifaFormatada = valorTarifa > 0 ? `R$ ${valorTarifa.toFixed(2)}/kg` : 'N/A';
            
            const corLinha = this.obterCorCia(trecho.cia);
            const urlLogoCia = this.obterUrlLogo(trecho.cia);
            
            const htmlLogoCia = urlLogoCia 
                ? `<img src="${urlLogoCia}" style="width: 20px; height: 20px; object-fit: contain; background: #fff; border-radius: 50%; padding: 2px; margin-right: 6px;">`
                : '';

            // Desenha a linha no mapa
            const polilinhaVoo = L.polyline([pontoOrigem, pontoDestino], { 
                color: corLinha, 
                weight: 4, 
                opacity: 0.9,
                lineCap: 'round',
                lineJoin: 'round'
            }).addTo(this.camadaVoos);

            // Conteúdo Informativo do Popup do Trecho Aéreo
            const conteudoPopup = `
                <div style="font-family:'Inter', sans-serif; min-width:260px;">
                    <div style="background:${corLinha}; padding:10px 12px; color:white; display:flex; justify-content:space-between; align-items:center;">
                        <div style="display:flex; align-items:center;">
                            ${htmlLogoCia}
                            <span style="font-size:0.95rem; font-weight:800;">${trecho.cia} ${trecho.voo}</span>
                        </div>
                        <span style="font-size:0.7rem; font-weight:700; background:rgba(255,255,255,0.25); padding:3px 8px; border-radius:12px;">${baseCalculo.servico || 'STD'}</span>
                    </div>
                    
                    <div style="padding:14px;">
                        
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                            <div style="text-align:center;">
                                <div style="font-size:1.2rem; font-weight:900;">${trecho.origem.iata}</div>
                                <div style="font-size:0.65rem; color:var(--luft-text-muted); margin-top:-2px;">Saída</div>
                            </div>
                            
                            <div style="flex:1; display:flex; flex-direction:column; align-items:center; padding:0 10px;">
                                <i class="ph-fill ph-airplane-in-flight" style="color:${corLinha}; font-size:1.2rem;"></i>
                                <div style="width:100%; height:1px; background:${corLinha}; opacity:0.3; margin-top:-8px; z-index:-1;"></div>
                                <span style="font-size:0.65rem; color:var(--luft-text-muted); margin-top:4px;">${trecho.data}</span>
                            </div>

                            <div style="text-align:center;">
                                <div style="font-size:1.2rem; font-weight:900;">${trecho.destino.iata}</div>
                                <div style="font-size:0.65rem; color:var(--luft-text-muted); margin-top:-2px;">Chegada</div>
                            </div>
                        </div>
                        
                        <div style="display:flex; justify-content:space-between; margin-bottom:14px; background:var(--luft-bg-app); padding:6px 10px; border-radius:6px;">
                            <strong style="font-size:0.9rem;">${trecho.horario_saida}</strong>
                            <strong style="font-size:0.9rem;">${trecho.horario_chegada}</strong>
                        </div>

                        <div style="background:var(--luft-bg-app); padding:10px; border-radius:8px; border:1px solid var(--luft-border);">
                            <div style="display:flex; justify-content:space-between; margin-bottom:6px; font-size:0.8rem;">
                                <span style="color:var(--luft-text-muted);">Tarifa (${trecho.peso_calculado || '100'}kg):</span>
                                <span style="font-weight:600;">${tarifaFormatada}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; border-top:1px dashed var(--luft-border); padding-top:6px; align-items:center;">
                                <span style="font-weight:700; color:var(--luft-text-muted); font-size:0.8rem;">Custo Total:</span>
                                <span style="font-weight:800; color:${corLinha}; font-size:1rem;">${custoFormatado}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            polilinhaVoo.bindPopup(conteudoPopup);

            // Marca o ponto de origem
            L.circleMarker(pontoOrigem, { 
                radius: 5, color: '#334155', fillColor: '#fff', fillOpacity: 1 
            }).addTo(this.camadaVoos).bindTooltip(trecho.origem.iata, { permanent: true, direction: 'left', className: 'font-bold' });
            
            // Se for o último trecho, marca o destino em verde (Chegada)
            if (indice === listaTrechos.length - 1) {
                L.circleMarker(pontoDestino, { 
                    radius: 6, color: '#0f172a', fillColor: '#10b981', fillOpacity: 1 
                }).addTo(this.camadaVoos).bindTooltip(trecho.destino.iata, { permanent: true, direction: 'right', className: 'font-bold' });
            }
        });

        // Ajusta a visão do mapa para englobar toda a rota
        if (coordenadasDeLimites.length > 0) {
            this.mapa.fitBounds(L.latLngBounds(coordenadasDeLimites), { 
                paddingTopLeft: [450, 100],  // Compensa o espaço ocupado pelo painel flutuante
                paddingBottomRight: [100, 100] 
            });
        }
    }

    limparMapa() {
        if (this.camadaVoos) {
            this.camadaVoos.clearLayers();
        }
    }
}

// Instanciação Global e Exposição para a Interface HTML
let gerenciadorEscalas;

document.addEventListener('DOMContentLoaded', () => {
    gerenciadorEscalas = new GerenciadorEscalas();
    gerenciadorEscalas.inicializar();

    // Mapeamento das funções chamadas no HTML (onclick)
    window.buscarOpcoes = () => gerenciadorEscalas.buscarOpcoes();
    window.toggleDetalhesCard = (evento, chave) => gerenciadorEscalas.toggleDetalhesCard(evento, chave);
    window.selecionarOpcao = (chave) => gerenciadorEscalas.selecionarOpcao(chave);
});