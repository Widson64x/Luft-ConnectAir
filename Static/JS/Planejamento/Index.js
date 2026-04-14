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

    normalizarTexto(valor) {
        return String(valor ?? '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase();
    }

    coletarValoresBusca(valor) {
        if (valor === null || valor === undefined) {
            return [];
        }

        if (Array.isArray(valor)) {
            return valor.flatMap(item => this.coletarValoresBusca(item));
        }

        if (typeof valor === 'object') {
            return Object.values(valor).flatMap(item => this.coletarValoresBusca(item));
        }

        return [String(valor)];
    }

    inicializar() {
        this.atualizarDataExtenso();
        this.buscarDados();
        this.configurarOuvintes();
    }

    configurarOuvintes() {
        const campoBusca = document.getElementById('input-busca');
        const filtroStatus = document.getElementById('filtro-status');
        const filtroPrioridade = document.getElementById('filtro-prioridade');
        const filtroFilial = document.getElementById('filtro-filial');
        const filtroMotivo = document.getElementById('filtro-motivo');

        if (campoBusca) campoBusca.addEventListener('input', () => this.filtrarTabela());
        if (filtroStatus) filtroStatus.addEventListener('change', () => this.filtrarTabela());
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
            item.pesoFisico = Number(item.peso_fisico || 0);
            item.pesoTaxado = Number(item.peso_taxado || 0); 
            item.valorMercadoria = Number(item.raw_val_mercadoria || 0);
            item.volumes = Number(item.volumes || 0);
            item.quantidadeNotas = Number(item.qtd_notas || 0);
            
            item.freteTotal = Number(item.raw_frete_total || 0);
            item.tarifaEstimada = Number(item.tarifa_estimada || 5.50);

            // --- CÁLCULOS INDIVIDUAIS POR CTC (Necessário para a ordenação funcionar) ---
            item.custoEstimadoInd = item.pesoTaxado * item.tarifaEstimada;
            item.lucroEstimadoInd = item.freteTotal - item.custoEstimadoInd;
            // Evita divisão por zero
            item.margemEstimadaInd = item.freteTotal > 0 ? (item.lucroEstimadoInd / item.freteTotal) * 100 : 0;
            item.statusPlanejamentoFiltro = item.tem_planejamento
                ? String(item.status_planejamento || 'SEM STATUS').trim().toUpperCase()
                : 'PENDENTE';
            item.buscaTexto = this.normalizarTexto(this.coletarValoresBusca(item).join(' '));
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
            // Aumentei o colspan para 16 por causa das novas colunas
            corpoTabela.innerHTML = `
                <tr>
                    <td colspan="16" style="text-align: center; padding: 60px; color: var(--luft-text-muted);">
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
            const clienteNome = linha.cliente_nome || linha.remetente || '-';
            
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

            const linkMontagem = rotasPlanejamento.montarRota
                .replace('__F__', linha.filial)
                .replace('__S__', linha.serie)
                .replace('__C__', linha.ctc);

            // Regra Visual: Se a margem for negativa, fica vermelho para alertar o usuário!
            const isPrejuizo = linha.margemEstimadaInd < 0;
            const corLucro = isPrejuizo ? '#ef4444' : '#3b82f6'; // Vermelho ou Azul
            const bgMargem = isPrejuizo ? 'rgba(239, 68, 68, 0.1)' : 'rgba(59, 130, 246, 0.1)';

            tr.innerHTML = `
                <td style="text-align: center; min-width: 110px;">
                    <div class="d-flex align-items-center justify-content-center gap-2">
                        <button class="btn btn-secondary d-flex align-items-center justify-content-center" style="padding: 6px; width: 36px; height: 36px;" onclick="AbrirModalGlobal('${linha.filial}', '${linha.serie}', '${linha.ctc}')" title="Ver Detalhes">
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
                    <div class="font-medium text-main mb-1" style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${clienteNome}">
                        ${clienteNome}
                    </div>
                    <span class="luft-badge luft-badge-secondary" style="font-size: 0.65rem;">${linha.tipo_carga || 'NORMAL'}</span>
                </td>
                <td style="text-align: center;" class="font-black text-main">${linha.quantidadeNotas}</td>
                <td style="text-align: right;" class="font-bold text-main">${linha.volumes}</td>
                <td style="text-align: right; line-height: 1.3;">
                    <div class="text-xs text-muted">${this.formatadorNumero.format(linha.pesoFisico)} Fís</div>
                    <div class="font-black text-main">${this.formatadorNumero.format(linha.pesoTaxado)} Tax</div>
                </td>
                <td style="text-align: right; font-weight: 800; color: var(--luft-text-muted);">${this.formatadorMoeda.format(linha.valorMercadoria)}</td>
                
                <td style="text-align: right; font-weight: 700; color: #10b981;">${this.formatadorMoeda.format(linha.freteTotal)}</td>
                <td style="text-align: right; font-weight: 600; color: #ef4444;">${this.formatadorMoeda.format(linha.custoEstimadoInd)}</td>
                <td style="text-align: right;">
                    <div class="font-black" style="color: ${corLucro}; font-size: 1rem;">
                        ${this.formatadorMoeda.format(linha.lucroEstimadoInd)}
                    </div>
                    <div style="color: ${corLucro}; font-weight: 700; font-size: 0.75rem; background: ${bgMargem}; padding: 2px 6px; border-radius: 4px; display: inline-block; margin-top: 2px;">
                        ${this.formatadorNumero.format(linha.margemEstimadaInd)}%
                    </div>
                </td>
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
        const termoBusca = this.normalizarTexto(elementoBusca ? elementoBusca.value : '');

        const elementoStatus = document.getElementById('filtro-status');
        const filtroStatus = elementoStatus ? elementoStatus.value : 'TODOS';
        
        const elementoPrioridade = document.getElementById('filtro-prioridade');
        const filtroPrioridade = elementoPrioridade ? elementoPrioridade.value : 'TODOS';
        
        const elementoFilial = document.getElementById('filtro-filial');
        const filtroFilial = elementoFilial ? elementoFilial.value : 'TODOS';
        
        const elementoMotivo = document.getElementById('filtro-motivo');
        const filtroMotivo = elementoMotivo ? elementoMotivo.value : 'TODOS';

        this.dadosVisiveis = this.dadosOriginais.filter(item => {
            const combinouTexto = !termoBusca || item.buscaTexto.includes(termoBusca);
            const combinouStatus = (filtroStatus === 'TODOS') || (item.statusPlanejamentoFiltro === filtroStatus);
            
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

            return combinouTexto && combinouStatus && combinouPrioridade && combinouFilial && combinouMotivo && combinouAba;
        });

        this.aplicarOrdenacao();
        this.renderizarTabela();
    }

    atualizarIndicadoresDeDesempenho() {
        const elementoTotal = document.getElementById('kpi-total');
        const elementoPeso = document.getElementById('kpi-peso');
        const elementoValor = document.getElementById('kpi-valor');
        const elementoNotas = document.getElementById('kpi-notas');
        
        // Elementos de Rentabilidade
        const elementoFreteTotal = document.getElementById('kpi-frete-total');
        const elementoCustoEstimado = document.getElementById('kpi-custo-estimado');
        const elementoLucro = document.getElementById('kpi-lucro');
        const elementoMargem = document.getElementById('kpi-margem');

        if (!elementoTotal) return; 

        let pesoAcumulado = 0;
        let valorAcumulado = 0;
        let notasAcumuladas = 0;
        
        // Variáveis de Gestão de Lucro
        let freteTotalAcumulado = 0; // Receita
        let custoEstimadoAcumulado = 0; // Despesa Aérea Teórica

        this.dadosVisiveis.forEach(dado => {
            pesoAcumulado += dado.pesoTaxado;
            valorAcumulado += dado.valorMercadoria;
            notasAcumuladas += dado.quantidadeNotas;

            // 1. Receita: Soma do raw_frete_total
            freteTotalAcumulado += dado.freteTotal;

            // 2. Custo Estimado: Usa expressamente o Peso Taxado (Peso Cubado do Aéreo) * Tarifa
            custoEstimadoAcumulado += (dado.pesoTaxado * dado.tarifaEstimada);
        });

        elementoTotal.innerText = this.dadosVisiveis.length;
        elementoPeso.innerText = this.formatadorNumero.format(pesoAcumulado);
        elementoValor.innerText = valorAcumulado.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        elementoNotas.innerText = notasAcumuladas;
        
        // Atualiza os Cards de Receita e Custo
        if (elementoFreteTotal) elementoFreteTotal.innerText = this.formatadorNumero.format(freteTotalAcumulado);
        if (elementoCustoEstimado) elementoCustoEstimado.innerText = this.formatadorNumero.format(custoEstimadoAcumulado);

        // --- MATEMÁTICA DA RENTABILIDADE ---
        // Lucro Bruto = Receita (Frete do CTC) - Despesa (Custo Estimado do Aéreo)
        const lucroEstimado = freteTotalAcumulado - custoEstimadoAcumulado;
        
        // Margem % = (Lucro / Receita) * 100
        const margemPercentual = freteTotalAcumulado > 0 ? (lucroEstimado / freteTotalAcumulado) * 100 : 0;

        // Atualiza a tela formatando como números decimais no padrão brasileiro
        if (elementoLucro) {
            elementoLucro.innerText = this.formatadorNumero.format(lucroEstimado);
        }
        
        if (elementoMargem) {
            elementoMargem.innerText = this.formatadorNumero.format(margemPercentual);
            
            // Dica visual de UX: Deixa o lucro/margem vermelho se for prejuízo
            if (margemPercentual < 0) {
                elementoMargem.style.color = '#ef4444'; // Vermelho
                if(elementoLucro) elementoLucro.style.color = '#ef4444';
            } else {
                elementoMargem.style.color = '#8b5cf6'; // Roxo padrão
                if(elementoLucro) elementoLucro.style.color = '#3b82f6'; // Azul padrão
            }
        }
    }

    ordenarTabela(colunaDesejada) {
        if (this.ordemAtual.coluna === colunaDesejada) {
            this.ordemAtual.direcao = this.ordemAtual.direcao === 'asc' ? 'desc' : 'asc';
        } else {
            this.ordemAtual.coluna = colunaDesejada;
            this.ordemAtual.direcao = 'asc';
        }
        
        document.querySelectorAll('.luft-planejamento-tabela th i').forEach(icone => icone.className = 'ph-bold ph-caret-up-down text-muted');
        
        const cabecalhoAtual = document.querySelector(`th[onclick="Ordenar('${colunaDesejada}')"] i`);
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
        // Usamos um Map para guardar a relação: código da filial (chave) -> nome da filial (valor)
        const mapaFiliais = new Map();
        const conjuntoStatus = new Set(['PENDENTE']);
        const conjuntoMotivos = new Set();

        dadosParaProcessar.forEach(item => {
            if (item.filial) {
                mapaFiliais.set(item.filial, item.nomefilial || item.filial);
            }
            if (item.tem_planejamento && item.status_planejamento) {
                conjuntoStatus.add(String(item.status_planejamento).trim().toUpperCase());
            }
            if (item.motivodoc) conjuntoMotivos.add(item.motivodoc);
        });

        const selecaoStatus = document.getElementById('filtro-status');
        const selecaoFilial = document.getElementById('filtro-filial');
        const selecaoMotivo = document.getElementById('filtro-motivo');

        if (selecaoStatus) {
            Array.from(conjuntoStatus).sort().forEach(status => {
                selecaoStatus.innerHTML += `<option value="${status}">${status}</option>`;
            });
        }

        if (selecaoFilial) {
            Array.from(mapaFiliais.entries())
                .sort((a, b) => String(a[1]).localeCompare(String(b[1])))
                .forEach(([codigo, nome]) => {
                    selecaoFilial.innerHTML += `<option value="${codigo}">${nome}</option>`;
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

    window.Ordenar = (coluna) => gerenciador.ordenarTabela(coluna);
    window.FiltrarTabela = () => gerenciador.filtrarTabela();
    window.MudarAba = (aba) => gerenciador.mudarAbaVisivel(aba);
});