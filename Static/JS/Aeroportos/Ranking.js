/**
 * Ranking.js
 * Lógica da tela de Priorização de Aeroportos
 * Refatorado com Classes, camelCase e Rotas Injetadas
 */

class GerenciadorRanking {
    constructor() {
        this.estadoAtual = {
            modo: 'GLOBAL', 
            ufSelecionada: null,
            listaCompletaFiltrada: [], 
            itensRenderizados: 0,      
            itensPorPagina: 50       
        };
        
        this.cacheGlobal = null; 
        this.timeoutPesquisa = null;
    }

    inicializar() {
        this.configurarScrollInfinito();
        this.ativarModoGlobal(); 
    }

    ativarModoGlobal() {
        this.estadoAtual.modo = 'GLOBAL';
        this.estadoAtual.ufSelecionada = null;
        this.resetarSidebar();
        
        const botaoGlobal = document.getElementById('btn-global');
        if (botaoGlobal) botaoGlobal.classList.add('active');

        if (!this.cacheGlobal) {
            let todos = [];
            Object.keys(dadosRanking).forEach(uf => {
                const aeroportosUf = dadosRanking[uf].map(aeroporto => ({...aeroporto, ufOrigem: uf}));
                todos = [...todos, ...aeroportosUf];
            });
            todos.sort((a, b) => {
                const efA = (a.importancia || 0) > 0 ? (a.importancia || 0) : (a.importancia_uso || 0);
                const efB = (b.importancia || 0) > 0 ? (b.importancia || 0) : (b.importancia_uso || 0);
                return efB - efA;
            });
            this.cacheGlobal = todos;
        }

        this.atualizarHeader('Visão Global', 'Ordenado por Índice de Importância');
        
        this.estadoAtual.listaCompletaFiltrada = this.cacheGlobal;
        this.resetarRenderizacao();
    }

    selecionarUf(uf) {
        this.estadoAtual.modo = 'UF';
        this.estadoAtual.ufSelecionada = uf;

        this.resetarSidebar();
        const botaoUf = document.getElementById(`uf-${uf}`);
        if (botaoUf) botaoUf.classList.add('active');

        const lista = dadosRanking[uf] || [];
        
        this.atualizarHeader(`Aeroportos de ${uf}`, 'Ajuste a prioridade local');
        
        this.estadoAtual.listaCompletaFiltrada = lista;
        this.resetarRenderizacao();
    }

    resetarSidebar() {
        document.querySelectorAll('.luft-uf-item').forEach(elemento => elemento.classList.remove('active'));
        const inputPesquisa = document.getElementById('global-search');
        if (inputPesquisa && this.estadoAtual.modo !== 'GLOBAL') {
            inputPesquisa.value = '';
        }
    }

    filtrarGlobal(termo) {
        clearTimeout(this.timeoutPesquisa);
        this.timeoutPesquisa = setTimeout(() => { this.executarFiltro(termo); }, 300);
    }

    executarFiltro(termo) {
        termo = termo.toLowerCase().trim();

        if (termo === '') {
            if (this.estadoAtual.modo === 'GLOBAL') {
                this.ativarModoGlobal();
            } else {
                this.selecionarUf(this.estadoAtual.ufSelecionada);
            }
            return;
        }

        document.querySelectorAll('.luft-uf-item').forEach(elemento => elemento.classList.remove('active'));
        if (!this.cacheGlobal) this.ativarModoGlobal(); 

        const resultados = this.cacheGlobal.filter(aeroporto => {
            return (aeroporto.iata && aeroporto.iata.toLowerCase().includes(termo)) ||
                   (aeroporto.nome && aeroporto.nome.toLowerCase().includes(termo)) ||
                   (aeroporto.regiao && aeroporto.regiao.toLowerCase().includes(termo));
        });

        this.atualizarHeader('Resultados da Busca', `${resultados.length} aeroportos encontrados`);
        
        this.estadoAtual.listaCompletaFiltrada = resultados;
        this.resetarRenderizacao();
    }

    configurarScrollInfinito() {
        const container = document.getElementById('container-aeroportos');
        container.addEventListener('scroll', () => {
            if (container.scrollTop + container.clientHeight >= container.scrollHeight - 100) {
                this.renderizarProximoLote();
            }
        });
    }

    resetarRenderizacao() {
        const container = document.getElementById('container-aeroportos');
        container.scrollTop = 0; 
        container.innerHTML = '';
        this.estadoAtual.itensRenderizados = 0;
        
        if (this.estadoAtual.listaCompletaFiltrada.length === 0) {
            container.innerHTML = `
                <div style="grid-column: 1/-1; text-align: center; padding: 60px; color: var(--luft-text-muted);">
                    <i class="ph-duotone ph-airplane-slash text-muted" style="font-size: 3.5rem; margin-bottom:15px;"></i>
                    <p class="font-bold text-main text-lg">Nenhum aeroporto encontrado.</p>
                </div>`;
            return;
        }

        this.renderizarProximoLote();
    }

    renderizarProximoLote() {
        const total = this.estadoAtual.listaCompletaFiltrada.length;
        if (this.estadoAtual.itensRenderizados >= total) return; 

        const inicio = this.estadoAtual.itensRenderizados;
        const fim = Math.min(inicio + this.estadoAtual.itensPorPagina, total);
        
        const lote = this.estadoAtual.listaCompletaFiltrada.slice(inicio, fim);
        const htmlLote = lote.map(aeroporto => this.construirCardHTML(aeroporto)).join('');
        
        const container = document.getElementById('container-aeroportos');
        container.insertAdjacentHTML('beforeend', htmlLote);

        this.estadoAtual.itensRenderizados = fim;
    }

    construirCardHTML(aeroporto) {
        const importanciaManual = aeroporto.importancia ?? 0;
        const importanciaUso    = aeroporto.importancia_uso ?? 0;
        const efetivo = importanciaManual > 0 ? importanciaManual : importanciaUso;

        const corEstilo     = this.obterCorEstilo(efetivo);
        const corBorda      = this.obterCorBorda(efetivo);
        const corFundoClaro = this.obterCorFundoClaro(efetivo);

        const mostrarUf = this.estadoAtual.modo === 'GLOBAL' || aeroporto.ufOrigem;
        const htmlUf    = mostrarUf ? `<span class="luft-badge luft-badge-secondary font-black">${aeroporto.ufOrigem || ''}</span>` : '';

        let corBadgeEfetivo, textoBadgeEfetivo;
        if (importanciaManual > 0) {
            textoBadgeEfetivo = 'Manual';
            corBadgeEfetivo   = 'background:rgba(34,197,94,0.15);color:var(--luft-success);';
        } else if (importanciaUso > 0) {
            textoBadgeEfetivo = 'Por Uso';
            corBadgeEfetivo   = 'background:rgba(59,130,246,0.15);color:var(--luft-primary-600);';
        } else {
            textoBadgeEfetivo = 'Sem Dados';
            corBadgeEfetivo   = 'background:var(--luft-border);color:var(--luft-text-muted);';
        }

        return `
            <div class="luft-card p-4 hover-lift" id="card-${aeroporto.id_aeroporto}" style="border-top: 4px solid ${corEstilo};">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <div class="font-black text-main text-2xl" style="font-family: monospace; letter-spacing: 1px;">${aeroporto.iata || '---'}</div>
                    <div class="d-flex gap-2 align-items-center">
                        <span id="badge-efetivo-${aeroporto.id_aeroporto}" class="text-xs font-bold px-2 py-1 rounded" style="${corBadgeEfetivo}">${textoBadgeEfetivo}</span>
                        ${htmlUf}
                    </div>
                </div>

                <div class="mb-3">
                    <h3 class="font-bold text-main m-0 mb-1 text-md" title="${aeroporto.nome}" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${aeroporto.nome}</h3>
                    <p class="text-xs text-muted font-medium d-flex align-items-center gap-1">
                        <i class="ph-fill ph-map-pin"></i> ${aeroporto.regiao || 'Região Desconhecida'}
                    </p>
                </div>

                <div class="bg-app p-3 rounded border mb-2" style="border-color:var(--luft-border);">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="text-xs font-bold text-muted text-uppercase d-flex align-items-center gap-1">
                            <i class="ph-bold ph-pencil-simple"></i> Manual
                        </span>
                        <span class="font-black" id="badge-${aeroporto.id_aeroporto}" style="color:${importanciaManual > 0 ? corEstilo : 'var(--luft-text-muted)'};font-size:1.1rem;">${importanciaManual}%</span>
                    </div>
                    <div id="manual-wrapper-${aeroporto.id_aeroporto}" class="luft-range-wrapper" style="background:${importanciaManual > 0 ? corFundoClaro : 'var(--luft-border)'};border:1px solid ${importanciaManual > 0 ? corBorda : 'transparent'};">
                        <div class="luft-range-fill" id="fill-${aeroporto.id_aeroporto}" style="width:${importanciaManual}%;background:${importanciaManual > 0 ? corEstilo : 'var(--luft-text-muted)'};">​</div>
                        <input type="range" min="0" max="100" value="${importanciaManual}"
                               class="luft-range-input"
                               oninput="atualizarInput(${aeroporto.id_aeroporto}, this.value, '${aeroporto.ufOrigem}')"
                               data-id="${aeroporto.id_aeroporto}">
                    </div>
                </div>

                <div id="uso-section-${aeroporto.id_aeroporto}" class="p-3 rounded border" style="border-color:var(--luft-border);background:var(--luft-bg-app);opacity:${importanciaManual > 0 ? '0.5' : '1'};transition:opacity 0.2s;">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="text-xs font-bold text-muted text-uppercase d-flex align-items-center gap-1">
                            <i class="ph-bold ph-chart-bar"></i> Por Uso
                        </span>
                        <span class="font-bold" style="font-size:0.9rem;color:${importanciaManual > 0 ? 'var(--luft-text-muted)' : 'var(--luft-primary-500)'};">${importanciaUso}%</span>
                    </div>
                    <div class="luft-range-wrapper" style="background:var(--luft-border);border:none;height:6px;">
                        <div style="position:absolute;top:0;left:0;height:100%;border-radius:4px;width:${importanciaUso}%;background:${importanciaManual > 0 ? 'var(--luft-text-muted)' : 'var(--luft-primary-500)'};transition:width 0.3s;"></div>
                    </div>
                </div>
            </div>
        `;
    }

    atualizarHeader(titulo, subtitulo) {
        document.getElementById('titulo-view').innerText = titulo;
        document.getElementById('subtitulo-view').innerText = subtitulo;
    }

    atualizarInput(id, valor, ufRef) {
        valor = parseInt(valor);
        const ufAlvo = (ufRef && ufRef !== 'undefined') ? ufRef : this.estadoAtual.ufSelecionada;

        // Busca o valor de uso atual no dado
        let importanciaUso = 0;
        if (ufAlvo && dadosRanking[ufAlvo]) {
            const item = dadosRanking[ufAlvo].find(a => a.id_aeroporto === id);
            if (item) importanciaUso = item.importancia_uso ?? 0;
        }

        const efetivo    = valor > 0 ? valor : importanciaUso;
        const cor        = this.obterCorEstilo(efetivo);
        const corBorda   = this.obterCorBorda(efetivo);
        const corFundo   = this.obterCorFundoClaro(efetivo);

        const badge         = document.getElementById(`badge-${id}`);
        const fill          = document.getElementById(`fill-${id}`);
        const manualWrapper = document.getElementById(`manual-wrapper-${id}`);
        const usoSection    = document.getElementById(`uso-section-${id}`);
        const card          = document.getElementById(`card-${id}`);
        const badgeEfetivo  = document.getElementById(`badge-efetivo-${id}`);

        if (badge) { badge.innerText = `${valor}%`; badge.style.color = valor > 0 ? cor : 'var(--luft-text-muted)'; }
        if (fill)  { fill.style.width = `${valor}%`; fill.style.background = valor > 0 ? cor : 'var(--luft-text-muted)'; }
        if (manualWrapper) {
            manualWrapper.style.background   = valor > 0 ? corFundo : 'var(--luft-border)';
            manualWrapper.style.borderColor  = valor > 0 ? corBorda  : 'transparent';
        }
        if (usoSection) usoSection.style.opacity = valor > 0 ? '0.5' : '1';
        if (card) card.style.borderTopColor = cor;

        if (badgeEfetivo) {
            if (valor > 0) {
                badgeEfetivo.textContent = 'Manual';
                badgeEfetivo.style.background = 'rgba(34,197,94,0.15)';
                badgeEfetivo.style.color      = 'var(--luft-success)';
            } else if (importanciaUso > 0) {
                badgeEfetivo.textContent = 'Por Uso';
                badgeEfetivo.style.background = 'rgba(59,130,246,0.15)';
                badgeEfetivo.style.color      = 'var(--luft-primary-600)';
            } else {
                badgeEfetivo.textContent = 'Sem Dados';
                badgeEfetivo.style.background = 'var(--luft-border)';
                badgeEfetivo.style.color      = 'var(--luft-text-muted)';
            }
        }

        if (ufAlvo && dadosRanking[ufAlvo]) {
            const indice = dadosRanking[ufAlvo].findIndex(aeroporto => aeroporto.id_aeroporto === id);
            if (indice >= 0) dadosRanking[ufAlvo][indice].importancia = valor;
        }
    }

    async recalcularUso() {
        const botao = document.getElementById('btn-recalcular-uso');
        const textoOriginal = botao.innerHTML;
        botao.innerHTML = `<i class="ph-bold ph-spinner ph-spin text-lg"></i> Calculando...`;
        botao.disabled = true;

        try {
            const resp = await fetch(rotasRanking.recalcularUso, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const json = await resp.json();
            if (json.sucesso) {
                botao.innerHTML = `<i class="ph-bold ph-check text-lg"></i> ${json.msg}`;
                setTimeout(() => window.location.reload(), 1800);
            } else {
                alert(`Erro: ${json.msg}`);
                botao.innerHTML = textoOriginal;
                botao.disabled = false;
            }
        } catch (e) {
            alert('Erro de comunicação.');
            botao.innerHTML = textoOriginal;
            botao.disabled = false;
        }
    }

    async salvarRankingAtual() {
        const botao = document.querySelector('.btn-save');
        const texto = botao.querySelector('.btn-text');
        const textoOriginal = texto.innerText;
        
        texto.innerText = 'Processando...';
        botao.disabled = true;
        botao.innerHTML = `<i class="ph-bold ph-spinner ph-spin text-lg"></i> <span class="btn-text">Salvando...</span>`;

        const promessas = Object.keys(dadosRanking).map(uf => {
            return fetch(rotasRanking.salvarRanking, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ uf: uf, aeroportos: dadosRanking[uf] })
            }).then(resposta => resposta.json());
        });

        try {
            const resultados = await Promise.all(promessas);
            const falhas = resultados.filter(resultado => !resultado.sucesso);
            
            if (falhas.length === 0) {
                botao.innerHTML = `<i class="ph-bold ph-check-circle text-lg"></i> <span class="btn-text">Tudo Salvo!</span>`;
                setTimeout(() => {
                    botao.innerHTML = `<i class="ph-bold ph-floppy-disk text-lg"></i> <span class="btn-text">${textoOriginal}</span>`;
                    botao.disabled = false;
                }, 2000);
            } else {
                alert(`Erro ao salvar ${falhas.length} estados.`);
                botao.innerHTML = `<i class="ph-bold ph-floppy-disk text-lg"></i> <span class="btn-text">${textoOriginal}</span>`;
                botao.disabled = false;
            }
        } catch (erro) {
            console.error(erro);
            alert('Erro de comunicação.');
            botao.innerHTML = `<i class="ph-bold ph-floppy-disk text-lg"></i> <span class="btn-text">${textoOriginal}</span>`;
            botao.disabled = false;
        }
    }

    obterCorEstilo(valor) {
        if (valor < 30) return 'var(--luft-danger)';
        if (valor < 70) return 'var(--luft-warning)';
        return 'var(--luft-success)';
    }

    obterCorBorda(valor) {
        if (valor < 30) return 'rgba(239, 68, 68, 0.2)';
        if (valor < 70) return 'rgba(245, 158, 11, 0.2)';
        return 'rgba(34, 197, 94, 0.2)';
    }

    obterCorFundoClaro(valor) {
        if (valor < 30) return 'rgba(239, 68, 68, 0.05)';
        if (valor < 70) return 'rgba(245, 158, 11, 0.05)';
        return 'rgba(34, 197, 94, 0.05)';
    }
}

// Instanciação Global e Exposição para a UI
let gerenciadorRanking;

document.addEventListener('DOMContentLoaded', () => {
    gerenciadorRanking = new GerenciadorRanking();
    gerenciadorRanking.inicializar();

    // Expondo os métodos globais necessários para os eventos oninput, onclick, onkeyup
    window.ativarModoGlobal = () => gerenciadorRanking.ativarModoGlobal();
    window.selecionarUf = (uf) => gerenciadorRanking.selecionarUf(uf);
    window.filtrarGlobal = (termo) => gerenciadorRanking.filtrarGlobal(termo);
    window.atualizarInput = (id, valor, ufRef) => gerenciadorRanking.atualizarInput(id, valor, ufRef);
    window.salvarRankingAtual = () => gerenciadorRanking.salvarRankingAtual();
    window.recalcularUso = () => gerenciadorRanking.recalcularUso();
});