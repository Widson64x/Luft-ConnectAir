/**
 * Index.js
 * Lógica da tela de Gestão de Reversa (Controle de Devoluções)
 * Refatorado com Classes, camelCase e Injeção de Rotas
 */

class GerenciadorReversa {
    constructor() {
        this.filtroAtual = 'todos';
        this.inputBusca = document.getElementById('searchInput');
        this.linhasTabela = document.querySelectorAll('.data-row');
        this.labelUltimaAtualizacao = document.getElementById('last-update');
        this.checkboxesAcao = document.querySelectorAll('.chk-action');
    }

    inicializar() {
        if (this.labelUltimaAtualizacao) {
            this.labelUltimaAtualizacao.innerText = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
        }
        
        this.filtrarTabela();

        // Adiciona ouvintes de evento para os checkboxes individuais
        this.checkboxesAcao.forEach(checkbox => {
            checkbox.addEventListener('change', (evento) => this.manipularCheckbox(evento));
        });
    }

    definirFiltro(tipoFiltro, elementoBotao) {
        this.filtroAtual = tipoFiltro;
        
        document.querySelectorAll('.luft-tab-btn').forEach(botao => botao.classList.remove('active'));
        if (elementoBotao) elementoBotao.classList.add('active');

        const checkboxTodos = document.getElementById('chk-todos');
        if (checkboxTodos) checkboxTodos.checked = false;

        this.filtrarTabela();
    }

    filtrarTabela() {
        if (!this.inputBusca) return;
        
        const textoBusca = this.inputBusca.value.toLowerCase();
        
        let contagemTotal = 0;
        let contagemPendente = 0;
        let contagemLiberado = 0;
        let contagemVisivel = 0;
        let possuiDadosVisiveis = false;

        this.linhasTabela.forEach(linha => {
            const statusLinha = linha.dataset.status;
            const textoConteudo = linha.dataset.search.toLowerCase();
            const correspondeBusca = textoConteudo.includes(textoBusca);

            if (correspondeBusca) {
                contagemTotal++;
                if (statusLinha === 'pendente') contagemPendente++;
                if (statusLinha === 'liberado') contagemLiberado++;
            }

            const correspondeFiltro = (this.filtroAtual === 'todos') || (this.filtroAtual === statusLinha);

            if (correspondeBusca && correspondeFiltro) {
                linha.style.display = '';
                contagemVisivel++;
                possuiDadosVisiveis = true;
            } else {
                linha.style.display = 'none';
            }
        });

        this.animarValorMetrica("count-total", contagemTotal);
        this.animarValorMetrica("count-pendente", contagemPendente);
        this.animarValorMetrica("count-liberado", contagemLiberado);

        const linhaSemBusca = document.getElementById('no-search-results');
        if (linhaSemBusca) {
            linhaSemBusca.style.display = (!possuiDadosVisiveis && this.linhasTabela.length > 0) ? '' : 'none';
        }

        const labelVisiveis = document.getElementById('visible-count');
        if (labelVisiveis) labelVisiveis.innerText = contagemVisivel;
    }

    animarValorMetrica(idElemento, valor) {
        const elemento = document.getElementById(idElemento);
        if (elemento) elemento.innerText = valor;
    }

    async alternarTodos(checkboxOrigem) {
        const estaMarcado = checkboxOrigem.checked;
        const checkboxesParaAtualizar = [];

        // Filtra apenas as linhas que estão visíveis para aplicar a ação em lote
        this.linhasTabela.forEach(linha => {
            if (linha.style.display !== 'none') {
                const checkboxLinha = linha.querySelector('.chk-action');
                if (checkboxLinha && checkboxLinha.checked !== estaMarcado) {
                    checkboxLinha.checked = estaMarcado;
                    checkboxesParaAtualizar.push(checkboxLinha);
                }
            }
        });

        if (checkboxesParaAtualizar.length === 0) return;
        checkboxOrigem.disabled = true;

        // Dispara as requisições em paralelo
        const promessas = checkboxesParaAtualizar.map(async (checkbox) => {
            const payload = {
                filial: checkbox.dataset.filial,
                serie: checkbox.dataset.serie,
                ctc: checkbox.dataset.ctc,
                liberado: estaMarcado
            };

            const displayStatus = document.getElementById(`status-display-${payload.filial}-${payload.ctc}`);
            const htmlOriginal = displayStatus.innerHTML;

            displayStatus.innerHTML = `<div class="text-xs font-bold text-primary"><i class="ph-bold ph-spinner animate-spin"></i> Salvando...</div>`;
            checkbox.disabled = true;

            try {
                const resposta = await fetch(rotasReversa.atualizarStatus, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const jsonRetorno = await resposta.json();

                if (jsonRetorno.sucesso) {
                    const linhaPai = checkbox.closest('tr');
                    linhaPai.dataset.status = estaMarcado ? 'liberado' : 'pendente';

                    if (estaMarcado) {
                        displayStatus.innerHTML = `
                            <div class="luft-badge luft-badge-success"><i class="ph-fill ph-check-circle"></i> Liberado</div>
                            <div class="text-xs text-muted mt-1 font-medium">Lote</div>
                        `;
                    } else {
                        displayStatus.innerHTML = `<div class="luft-badge luft-badge-warning"><i class="ph-fill ph-clock"></i> Pendente</div>`;
                    }
                } else {
                    throw new Error(jsonRetorno.msg);
                }
            } catch (erro) {
                console.error(erro);
                checkbox.checked = !estaMarcado; // Reverte visualmente em caso de erro
                displayStatus.innerHTML = htmlOriginal;
            } finally {
                checkbox.disabled = false;
            }
        });

        await Promise.all(promises);
        checkboxOrigem.disabled = false;
        
        // Re-aplica os filtros após terminar de atualizar os status (pode ocultar itens dependendo da aba ativa)
        this.filtrarTabela();
    }

    async manipularCheckbox(eventoMudanca) {
        const checkbox = eventoMudanca.target;
        const estaMarcado = checkbox.checked;
        const linhaPai = checkbox.closest('tr');

        const payload = {
            filial: checkbox.dataset.filial,
            serie: checkbox.dataset.serie,
            ctc: checkbox.dataset.ctc,
            liberado: estaMarcado
        };

        const displayStatus = document.getElementById(`status-display-${payload.filial}-${payload.ctc}`);
        const htmlOriginal = displayStatus.innerHTML;

        displayStatus.innerHTML = `<div class="text-xs font-bold text-primary"><i class="ph-bold ph-spinner animate-spin"></i> Salvando...</div>`;
        checkbox.disabled = true;

        try {
            const resposta = await fetch(rotasReversa.atualizarStatus, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const jsonRetorno = await resposta.json();

            if (jsonRetorno.sucesso) {
                const novoStatus = estaMarcado ? 'liberado' : 'pendente';
                linhaPai.dataset.status = novoStatus;

                if (estaMarcado) {
                    displayStatus.innerHTML = `
                        <div class="luft-badge luft-badge-success"><i class="ph-fill ph-check-circle"></i> Liberado</div>
                        <div class="text-xs text-muted mt-1 font-medium">Agora</div>
                    `;
                } else {
                    displayStatus.innerHTML = `<div class="luft-badge luft-badge-warning"><i class="ph-fill ph-clock"></i> Pendente</div>`;
                }
                
                // Re-aplica filtros se necessário (se estivermos na aba de 'Pendente', por exemplo, ele some da tela ao ser liberado)
                this.filtrarTabela();
            } else {
                throw new Error(jsonRetorno.msg);
            }
        } catch (erro) {
            console.error(erro);
            LuftCore.notificar('Erro ao comunicar com o servidor: ' + erro.message, 'danger');
            checkbox.checked = !estaMarcado;
            displayStatus.innerHTML = htmlOriginal;
        } finally {
            checkbox.disabled = false;
        }
    }
}

// Instanciação Global e Mapeamento para Eventos Inline do HTML
let gerenciadorReversa;

document.addEventListener('DOMContentLoaded', () => {
    gerenciadorReversa = new GerenciadorReversa();
    gerenciadorReversa.inicializar();

    // Expondo as funções necessárias para a View (onclick, onkeyup)
    window.definirFiltro = (tipoFiltro, botao) => gerenciadorReversa.definirFiltro(tipoFiltro, botao);
    window.filtrarTabela = () => gerenciadorReversa.filtrarTabela();
    window.alternarTodos = (checkboxOrigem) => gerenciadorReversa.alternarTodos(checkboxOrigem);
});