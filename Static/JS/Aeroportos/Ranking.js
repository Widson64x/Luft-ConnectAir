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
            todos.sort((a, b) => b.importancia - a.importancia);
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
        const corEstilo = this.obterCorEstilo(aeroporto.importancia);
        const corBorda = this.obterCorBorda(aeroporto.importancia);
        const corFundoClaro = this.obterCorFundoClaro(aeroporto.importancia);
        
        const mostrarUf = this.estadoAtual.modo === 'GLOBAL' || aeroporto.ufOrigem;
        const htmlUf = mostrarUf ? `<span class="luft-badge luft-badge-secondary font-black">${aeroporto.ufOrigem || ''}</span>` : '';

        return `
            <div class="luft-card p-4 hover-lift" id="card-${aeroporto.id_aeroporto}" style="border-top: 4px solid ${corEstilo};">
                <div class="d-flex justify-content-between align-items-start mb-3">
                    <div class="font-black text-main text-2xl" style="font-family: monospace; letter-spacing: 1px;">${aeroporto.iata || '---'}</div>
                    ${htmlUf}
                </div>
                
                <div class="mb-4">
                    <h3 class="font-bold text-main m-0 mb-1 text-md" title="${aeroporto.nome}" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${aeroporto.nome}</h3>
                    <p class="text-xs text-muted font-medium d-flex align-items-center gap-1">
                        <i class="ph-fill ph-map-pin"></i> ${aeroporto.regiao || 'Região Desconhecida'}
                    </p>
                </div>
                
                <div class="bg-app p-3 rounded border" style="border-color: var(--luft-border);">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="text-xs font-bold text-muted text-uppercase">Importância</span>
                        <span class="font-black" id="badge-${aeroporto.id_aeroporto}" style="color: ${corEstilo}; font-size: 1.1rem;">
                            ${aeroporto.importancia}%
                        </span>
                    </div>
                    <div class="luft-range-wrapper" style="background: ${corFundoClaro}; border: 1px solid ${corBorda};">
                        <div class="luft-range-fill" id="fill-${aeroporto.id_aeroporto}" style="width: ${aeroporto.importancia}%; background: ${corEstilo};"></div>
                        <input type="range" min="0" max="100" value="${aeroporto.importancia}" 
                               class="luft-range-input" 
                               oninput="atualizarInput(${aeroporto.id_aeroporto}, this.value, '${aeroporto.ufOrigem}')"
                               data-id="${aeroporto.id_aeroporto}">
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
        
        const badge = document.getElementById(`badge-${id}`);
        const fill = document.getElementById(`fill-${id}`);
        const card = document.getElementById(`card-${id}`);
        
        const cor = this.obterCorEstilo(valor);
        const corBorda = this.obterCorBorda(valor);
        const corFundoClaro = this.obterCorFundoClaro(valor);
        
        if (badge) { badge.innerText = `${valor}%`; badge.style.color = cor; }
        if (fill) { fill.style.width = `${valor}%`; fill.style.background = cor; }
        if (card) { card.style.borderTopColor = cor; }

        const ufAlvo = (ufRef && ufRef !== 'undefined') ? ufRef : this.estadoAtual.ufSelecionada;
        if (ufAlvo && dadosRanking[ufAlvo]) {
            const indice = dadosRanking[ufAlvo].findIndex(aeroporto => aeroporto.id_aeroporto === id);
            if (indice >= 0) dadosRanking[ufAlvo][indice].importancia = valor;
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
});