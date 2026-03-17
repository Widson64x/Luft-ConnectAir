/**
 * Index.js - Controlador do Painel de Planejamento 
 * Reestruturado com Classes e padronização camelCase
 */

class GerenciadorPlanejamento {
    constructor() {
        this.dadosOriginais = [];
        this.dadosVisiveis = [];
        this.ordemAtual = { coluna: 'dataRaw', direcao: 'desc' };
        this.abaAtual = 'TODOS';
        this.estaAnimando = false;

        this.formatadorMoeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
        this.formatadorNumero = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    inicializar() {
        this.atualizarDataExtenso();
        this.buscarDados();
        this.configurarOuvintes();
    }

    configurarOuvintes() {
        const campoBusca = document.getElementById('input-busca');
        const filtroPrioridade = document.getElementById('filtro-prioridade');
        const filtroFilial = document.getElementById('filtro-filial');
        const filtroMotivo = document.getElementById('filtro-motivo');

        if (campoBusca) campoBusca.addEventListener('input', () => this.filtrarTabela());
        if (filtroPrioridade) filtroPrioridade.addEventListener('change', () => this.filtrarTabela());
        if (filtroFilial) filtroFilial.addEventListener('change', () => this.filtrarTabela());
        if (filtroMotivo) filtroMotivo.addEventListener('change', () => this.filtrarTabela());
    }

    atualizarDataExtenso() {
        const opcoesData = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        const dataHoje = new Date().toLocaleDateString('pt-BR', opcoesData);
        const dataFormatada = dataHoje.charAt(0).toUpperCase() + dataHoje.slice(1);
        
        const elementoData = document.getElementById('data-extenso');
        if (elementoData) elementoData.innerText = dataFormatada;
    }

    async buscarDados() {
        const corpoTabela = document.getElementById('table-body');
        if (corpoTabela) {
            corpoTabela.innerHTML = '<tr><td colspan="13" style="text-align:center; padding:60px; color:var(--luft-text-muted);"><i class="ph-bold ph-spinner ph-spin text-primary" style="font-size: 2rem; margin-bottom: 10px;"></i><br>Buscando dados no servidor...</td></tr>';
        }

        try {
            // Utilizando a rota injetada do HTML!
            const resposta = await fetch(rotasPlanejamento.listarCtcs);
            if (!resposta.ok) throw new Error("Falha na comunicação com o servidor");
            
            const dadosNovos = await resposta.json();
            this.processarDados(dadosNovos);

        } catch (erro) {
            console.error("Erro ao buscar dados:", erro);
            if (corpoTabela) {
                corpoTabela.innerHTML = `<tr><td colspan="13" class="text-danger font-bold" style="text-align:center; padding:40px;"><i class="ph-bold ph-warning-circle" style="font-size:2rem;"></i><br>Erro ao carregar: ${erro.message}</td></tr>`;
            }
        }
    }

    processarDados(dados) {
        dados.forEach(item => {
            const partesData = item.data_emissao.split('/'); 
            const horaLimpa = item.hora_emissao ? item.hora_emissao.replace(':', '') : '0000';
            
            item.dataRaw = Number(`${partesData[2]}${partesData[1]}${partesData[0]}${horaLimpa}`);
            item.buscaTexto = `${item.ctc} ${item.remetente} ${item.destinatario} ${item.origem} ${item.destino} ${item.filial} ${item.tipo_carga} ${item.motivodoc} ${item.prioridade}`.toLowerCase();
            
            item.pesoFisico = Number(item.peso_fisico || 0);
            item.pesoTaxado = Number(item.peso_taxado || 0); 
            item.valorMercadoria = Number(item.raw_val_mercadoria || 0);
            item.volumes = Number(item.volumes || 0);
            item.quantidadeNotas = Number(item.qtd_notas || 0);
        });

        if (this.dadosOriginais.length === 0) {
            this.popularListasSelecao(dados);
        }

        this.dadosOriginais = dados;
        this.filtrarTabela();
    }

    renderizarTabela() {
        const corpoTabela = document.getElementById('table-body');
        const contadorRegistros = document.getElementById('contador-registros');
        
        if (!corpoTabela || !contadorRegistros) return;

        corpoTabela.innerHTML = '';

        if (this.dadosVisiveis.length === 0) {
            corpoTabela.innerHTML = `
                <tr>
                    <td colspan="13" style="text-align: center; padding: 60px; color: var(--luft-text-muted);">
                        <i class="ph-duotone ph-magnifying-glass" style="font-size: 3rem; margin-bottom: 15px; color: var(--luft-border);"></i><br>
                        <span class="font-bold text-main">Nenhum registro encontrado</span><br>
                        <span class="text-xs">Altere os filtros ou pesquise novamente.</span>
                    </td>
                </tr>`;
            contadorRegistros.innerText = 'Mostrando 0 registros';
            return;
        }

        const fragmentoDom = document.createDocumentFragment();

        this.dadosVisiveis.forEach(linha => {
            const tr = document.createElement('tr');
            
            const prioridade = (linha.prioridade || 'NORMAL').toUpperCase();
            let iconePrioridade = '<i class="ph-bold ph-minus" title="NORMAL"></i>'; 
            let classePrioridade = 'text-muted';

            if (prioridade === 'S' || prioridade === 'URGENTE') {
                classePrioridade = 'text-danger font-black'; 
                iconePrioridade = '<i class="ph-fill ph-warning-circle text-lg"></i>';
            } 
            else if (prioridade === 'AGENDADA') {
                classePrioridade = 'text-warning font-black'; 
                iconePrioridade = '<i class="ph-fill ph-clock-countdown text-lg"></i>';
            } 
            
            let crachaOrigem = '';
            if (linha.origem_dados === 'DIARIO') crachaOrigem = '<span class="luft-badge luft-badge-info">Do Dia</span>';
            else if (linha.origem_dados === 'BACKLOG') crachaOrigem = '<span class="luft-badge luft-badge-warning">Backlog</span>';
            else if (linha.origem_dados === 'REVERSA') crachaOrigem = '<span class="luft-badge luft-badge-secondary">Reversa</span>';

            // Utilizando a rota injetada e substituindo os placeholders
            const linkMontagem = rotasPlanejamento.montarRota
                .replace('__F__', linha.filial)
                .replace('__S__', linha.serie)
                .replace('__C__', linha.ctc);

            tr.innerHTML = `
                <td style="text-align: center; min-width: 110px;">
                    <div class="d-flex align-items-center justify-content-center gap-2">
                        <button class="btn btn-secondary d-flex align-items-center justify-content-center" style="padding: 6px; width: 36px; height: 36px;" onclick="AbrirModalGlobal('26', '1', '2601233063')" title="Ver Detalhes">
                            <i class="ph-bold ph-file-text" style="font-size: 1.1rem;"></i>
                        </button>
                        <a href="${linkMontagem}" class="btn btn-primary d-flex align-items-center justify-content-center" style="padding: 6px; width: 36px; height: 36px;" title="Planejar Rota">
                            <i class="ph-bold ph-airplane-tilt" style="font-size: 1.1rem;"></i>
                        </a>
                    </div>
                </td>
                <td>
                    ${linha.tem_planejamento 
                        ? `<span class="luft-badge luft-badge-success"><i class="ph-fill ph-check-circle"></i> ${linha.status_planejamento}</span>`
                        : `<span class="luft-badge luft-badge-warning"><i class="ph-fill ph-clock"></i> Pendente</span>`
                    }
                </td>
                <td style="text-align: center;" class="${classePrioridade}">${iconePrioridade}</td>
                <td>${crachaOrigem}</td>
                <td>
                    <span class="font-bold text-main d-block" style="font-family: monospace; font-size: 1rem;">${linha.ctc}</span>
                    <span class="text-xs text-muted">Sér. ${linha.serie} | ${linha.filial}</span>
                </td>
                <td style="text-align: center;" class="font-medium text-main">${linha.unid_lastmile || '-'}</td>
                <td>
                    <span class="font-bold text-main d-block">${linha.data_emissao}</span>
                    <span class="text-xs text-muted"><i class="ph-bold ph-clock"></i> ${linha.hora_emissao}</span>
                </td>
                <td>
                    <div class="d-flex align-items-center gap-2 font-bold text-main mb-1">
                        ${linha.origem.split('/')[0]}
                        <i class="ph-bold ph-arrow-right text-muted" style="font-size: 0.8rem;"></i>
                        ${linha.destino.split('/')[0]}
                    </div>
                    <span class="text-xs text-muted" style="max-width: 150px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: inline-block;">
                        ${linha.origem.split('/')[1] || ''} &rarr; ${linha.destino.split('/')[1] || ''}
                    </span>
                </td>
                <td>
                    <div class="font-medium text-main mb-1" style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${linha.remetente}">
                        ${linha.remetente}
                    </div>
                    <span class="luft-badge luft-badge-secondary" style="font-size: 0.65rem;">${linha.tipo_carga || 'NORMAL'}</span>
                </td>
                <td style="text-align: center;" class="font-black text-main">${linha.quantidadeNotas}</td>
                <td style="text-align: right;" class="font-bold text-main">${linha.volumes}</td>
                <td style="text-align: right; line-height: 1.3;">
                    <div class="text-xs text-muted">${this.formatadorNumero.format(linha.pesoFisico)} Fís</div>
                    <div class="font-black text-main">${this.formatadorNumero.format(linha.pesoTaxado)} Tax</div>
                </td>
                <td style="text-align: right; font-weight: 800; color: var(--luft-success);">${this.formatadorMoeda.format(linha.valorMercadoria)}</td>
            `;
            fragmentoDom.appendChild(tr);
        });

        corpoTabela.appendChild(fragmentoDom);
        contadorRegistros.innerText = `Mostrando ${this.dadosVisiveis.length} registros`;
        
        this.atualizarIndicadoresDeDesempenho();
    }

    mudarAbaVisivel(tipoAba) {
        if (this.abaAtual === tipoAba || this.estaAnimando) return;

        this.estaAnimando = true;
        const containerTransorte = document.getElementById('transition-container');
        
        document.querySelectorAll('.luft-tab-btn').forEach(botao => botao.classList.remove('active'));
        const botaoAtivo = document.getElementById(`tab-${tipoAba.toLowerCase()}`);
        if(botaoAtivo) botaoAtivo.classList.add('active');

        if (containerTransorte) {
            containerTransorte.style.transition = 'opacity 0.2s';
            containerTransorte.style.opacity = '0';
        }

        setTimeout(() => {
            this.abaAtual = tipoAba;
            this.filtrarTabela(); 
            
            if (containerTransorte) containerTransorte.style.opacity = '1';

            setTimeout(() => { this.estaAnimando = false; }, 200);
        }, 200);
    }

    filtrarTabela() {
        const elementoBusca = document.getElementById('input-busca');
        const termoBusca = elementoBusca ? elementoBusca.value.toLowerCase() : '';
        
        const elementoPrioridade = document.getElementById('filtro-prioridade');
        const filtroPrioridade = elementoPrioridade ? elementoPrioridade.value : 'TODOS';
        
        const elementoFilial = document.getElementById('filtro-filial');
        const filtroFilial = elementoFilial ? elementoFilial.value : 'TODOS';
        
        const elementoMotivo = document.getElementById('filtro-motivo');
        const filtroMotivo = elementoMotivo ? elementoMotivo.value : 'TODOS';

        this.dadosVisiveis = this.dadosOriginais.filter(item => {
            const combinouTexto = !termoBusca || item.buscaTexto.includes(termoBusca);
            
            let combinouPrioridade = true;
            const prioridadeItem = (item.prioridade || 'NORMAL').toUpperCase();

            if (filtroPrioridade !== 'TODOS') {
                if (filtroPrioridade === 'URGENTE') {
                    combinouPrioridade = (prioridadeItem === 'S' || prioridadeItem === 'URGENTE');
                } else if (filtroPrioridade === 'AGENDADA') {
                    combinouPrioridade = (prioridadeItem === 'AGENDADA');
                } else if (filtroPrioridade === 'NORMAL') {
                    combinouPrioridade = (prioridadeItem !== 'S' && prioridadeItem !== 'URGENTE' && prioridadeItem !== 'AGENDADA');
                }
            }
                              
            const combinouFilial = (filtroFilial === 'TODOS') || (item.filial === filtroFilial);
            const combinouMotivo = (filtroMotivo === 'TODOS') || (item.motivodoc === filtroMotivo);
            const combinouAba = (this.abaAtual === 'TODOS') || (item.origem_dados === this.abaAtual);

            return combinouTexto && combinouPrioridade && combinouFilial && combinouMotivo && combinouAba;
        });

        this.aplicarOrdenacao();
        this.renderizarTabela();
    }

    atualizarIndicadoresDeDesempenho() {
        const elementoTotal = document.getElementById('kpi-total');
        const elementoPeso = document.getElementById('kpi-peso');
        const elementoValor = document.getElementById('kpi-valor');
        const elementoNotas = document.getElementById('kpi-notas');

        if (!elementoTotal) return; 

        let pesoAcumulado = 0;
        let valorAcumulado = 0;
        let notasAcumuladas = 0;

        this.dadosVisiveis.forEach(dado => {
            pesoAcumulado += dado.pesoTaxado;
            valorAcumulado += dado.valorMercadoria;
            notasAcumuladas += dado.quantidadeNotas;
        });

        elementoTotal.innerText = this.dadosVisiveis.length;
        elementoPeso.innerText = this.formatadorNumero.format(pesoAcumulado);
        elementoValor.innerText = valorAcumulado.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        elementoNotas.innerText = notasAcumuladas;
    }

    ordenarTabela(colunaDesejada) {
        if (this.ordemAtual.coluna === colunaDesejada) {
            this.ordemAtual.direcao = this.ordemAtual.direcao === 'asc' ? 'desc' : 'asc';
        } else {
            this.ordemAtual.coluna = colunaDesejada;
            this.ordemAtual.direcao = 'asc';
        }
        
        document.querySelectorAll('.luft-planejamento-tabela th i').forEach(icone => icone.className = 'ph-bold ph-caret-up-down text-muted');
        
        const cabecalhoAtual = document.querySelector(`th[onclick="ordenarTabela('${colunaDesejada}')"] i`);
        if (cabecalhoAtual) {
            cabecalhoAtual.className = this.ordemAtual.direcao === 'asc' ? 'ph-bold ph-caret-up text-primary' : 'ph-bold ph-caret-down text-primary';
        }

        this.aplicarOrdenacao();
        this.renderizarTabela();
    }

    aplicarOrdenacao() {
        const colunaReferencia = this.ordemAtual.coluna;
        const modificadorDirecao = this.ordemAtual.direcao === 'asc' ? 1 : -1;

        this.dadosVisiveis.sort((itemA, itemB) => {
            let valorA = itemA[colunaReferencia];
            let valorB = itemB[colunaReferencia];

            if (typeof valorA === 'string') valorA = valorA.toLowerCase();
            if (typeof valorB === 'string') valorB = valorB.toLowerCase();

            if (valorA < valorB) return -1 * modificadorDirecao;
            if (valorA > valorB) return 1 * modificadorDirecao;
            return 0;
        });
    }

    popularListasSelecao(dadosParaProcessar) {
        const conjuntoFiliais = new Set();
        const conjuntoMotivos = new Set();

        dadosParaProcessar.forEach(item => {
            if (item.filial) conjuntoFiliais.add(item.filial);
            if (item.motivodoc) conjuntoMotivos.add(item.motivodoc);
        });

        const selecaoFilial = document.getElementById('filtro-filial');
        const selecaoMotivo = document.getElementById('filtro-motivo');

        if (selecaoFilial) {
            Array.from(conjuntoFiliais).sort().forEach(filial => {
                selecaoFilial.innerHTML += `<option value="${filial}">${filial}</option>`;
            });
        }

        if (selecaoMotivo) {
            Array.from(conjuntoMotivos).sort().forEach(motivo => {
                selecaoMotivo.innerHTML += `<option value="${motivo}">${motivo}</option>`;
            });
        }
    }
}

// Inicialização da classe e exposição de métodos para botões HTML existentes
document.addEventListener('DOMContentLoaded', () => {
    const gerenciador = new GerenciadorPlanejamento();
    gerenciador.inicializar();

    // Expõe os métodos no escopo global para que os on-clicks do HTML continuem funcionando
    window.Ordenar = (coluna) => gerenciador.ordenarTabela(coluna);
    window.MudarAba = (aba) => gerenciador.mudarAbaVisivel(aba);
});