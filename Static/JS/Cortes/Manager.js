/**
 * Manager.js
 * Lógica da tela de Gestão de Horários de Corte
 * Refatorado com Classes, camelCase e Injeção de Rotas
 */

class GerenciadorCortes {
    constructor() {
        this.tabAtual = 'planejamento';
        this.tbodyTabela = document.getElementById('table-body');
        this.toolbarAcoesLote = document.getElementById('batch-toolbar');
        this.contadorAcoesLote = document.getElementById('batch-count');
        this.modal = document.getElementById('modal-form');
        this.formCorte = document.getElementById('form-corte');
    }

    inicializar() {
        this.carregarDados();
    }

    mudarAba(novaAba) {
        if (this.tabAtual === novaAba) return;
        
        this.tabAtual = novaAba;
        
        document.querySelectorAll('.luft-tab-btn').forEach(botao => botao.classList.remove('active'));
        const botaoAtivo = document.getElementById(`tab-${novaAba}`);
        if (botaoAtivo) botaoAtivo.classList.add('active');
        
        this.carregarDados();
    }

    async carregarDados() {
        if (!this.tbodyTabela) return;

        this.tbodyTabela.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 60px; color: var(--luft-text-muted);"><i class="ph-bold ph-spinner animate-spin text-primary" style="font-size: 2.5rem;"></i><br><span class="mt-2 d-inline-block">Carregando Dados...</span></td></tr>';
        
        const checkboxTodos = document.getElementById('cb-table-all');
        if (checkboxTodos) checkboxTodos.checked = false;
        
        this.atualizarToolbar();

        try {
            const urlRequisicao = this.tabAtual === 'planejamento' ? rotasCortes.listarPlanejamento : rotasCortes.listarEmissao;
            
            const resposta = await fetch(urlRequisicao);
            if (!resposta.ok) throw new Error('Falha na comunicação');
            
            const dadosAgrupados = await resposta.json();
            this.renderizarTabela(dadosAgrupados);

        } catch (erro) {
            console.error("Erro ao buscar dados de cortes:", erro);
            this.tbodyTabela.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 60px; color: var(--luft-danger);"><i class="ph-duotone ph-warning-circle text-danger" style="font-size: 3rem; margin-bottom: 10px;"></i><br>Erro ao carregar dados do servidor.</td></tr>';
        }
    }

    renderizarTabela(dadosAgrupados) {
        this.tbodyTabela.innerHTML = '';
        
        const ufsOrdenadas = Object.keys(dadosAgrupados).sort();
        const fragmentoDom = document.createDocumentFragment();

        ufsOrdenadas.forEach(uf => {
            const dicionarioFiliais = dadosAgrupados[uf];
            let cortesDaUf = [];
            
            for (const [codigoFilial, listaCortes] of Object.entries(dicionarioFiliais)) {
                cortesDaUf.push(...listaCortes);
            }

            cortesDaUf.sort((a, b) => {
                if (!a.horario) return -1;
                if (!b.horario) return 1;
                return a.horario.localeCompare(b.horario);
            });

            if (cortesDaUf.length > 0) {
                // Cabeçalho Agrupador do Estado (UF)
                const linhaCabecalhoUf = document.createElement('tr');
                linhaCabecalhoUf.classList.add('luft-group-header');
                linhaCabecalhoUf.onclick = (evento) => { 
                    if (evento.target.tagName !== 'INPUT') this.toggleTableUfGroup(uf); 
                };
                
                linhaCabecalhoUf.innerHTML = `
                    <td style="text-align: center;">
                        <input type="checkbox" class="cb-table-uf" data-uf="${uf}" onchange="toggleTableUfCheckbox(this)">
                    </td>
                    <td colspan="3" style="background: rgba(59, 130, 246, 0.05);">
                        <i id="icon-uf-${uf}" class="ph-bold ph-caret-down luft-icon-caret collapsed text-primary" style="font-size: 1.1rem; margin-right: 8px;"></i> 
                        <strong class="text-primary font-black" style="letter-spacing: 0.5px;">ESTADO: ${uf}</strong> 
                        <span class="text-xs text-muted font-bold ml-2">(${cortesDaUf.length} regras)</span>
                    </td>
                `;
                fragmentoDom.appendChild(linhaCabecalhoUf);

                // Linhas das filiais
                cortesDaUf.forEach(item => {
                    const linhaTabela = document.createElement('tr');
                    linhaTabela.classList.add('luft-linha-tabela', 'hidden-by-collapse');
                    linhaTabela.style.display = 'none'; // Começa colapsado

                    linhaTabela.setAttribute('data-uf', uf);
                    linhaTabela.setAttribute('data-filial', item.filial);
                    linhaTabela.setAttribute('data-desc', (item.descricao || '').toLowerCase());
                    
                    linhaTabela.innerHTML = `
                        <td style="text-align: center;">
                            <input type="checkbox" class="cb-table-item" data-uf="${uf}" value="${item.id}" onchange="atualizarToolbar()">
                        </td>
                        <td><strong class="text-main">${item.filial}</strong></td>
                        <td class="text-muted font-medium">${item.descricao || '-'}</td>
                        <td style="text-align: center;">
                            <span class="luft-badge luft-badge-secondary font-black" style="font-family: monospace; font-size: 0.95rem;">${item.horario}</span>
                        </td>
                    `;
                    fragmentoDom.appendChild(linhaTabela);
                });
            }
        });

        this.tbodyTabela.appendChild(fragmentoDom);

        if (this.tbodyTabela.innerHTML === '') {
            this.tbodyTabela.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 60px; color: var(--luft-text-muted);">Nenhum horário cadastrado.</td></tr>';
        }
    }

    toggleTableUfGroup(uf) {
        const iconeDirecao = document.getElementById(`icon-uf-${uf}`);
        const linhasDoGrupo = document.querySelectorAll(`.luft-linha-tabela[data-uf="${uf}"]`);
        
        if (!iconeDirecao) return;

        const estaRecolhido = iconeDirecao.classList.contains('collapsed');
        
        if (estaRecolhido) {
            iconeDirecao.classList.remove('collapsed');
            linhasDoGrupo.forEach(linha => { 
                linha.style.display = ''; 
                linha.classList.remove('hidden-by-collapse'); 
            });
        } else {
            iconeDirecao.classList.add('collapsed');
            linhasDoGrupo.forEach(linha => { 
                linha.style.display = 'none'; 
                linha.classList.add('hidden-by-collapse'); 
            });
        }
        
        // Re-aplica filtro após expansão/contração
        this.filtrarTabelaFrontend();
    }

    filtrarTabelaFrontend() {
        const elementoBusca = document.getElementById('filtro-busca');
        if (!elementoBusca) return;

        const termoBusca = elementoBusca.value.toLowerCase();
        const linhasTabela = document.querySelectorAll('.luft-linha-tabela');
        
        linhasTabela.forEach(linha => {
            if (linha.classList.contains('hidden-by-collapse')) return;

            const filialId = linha.getAttribute('data-filial').toLowerCase();
            const descricao = linha.getAttribute('data-desc');
            
            if (filialId.includes(termoBusca) || descricao.includes(termoBusca)) {
                linha.style.display = '';
            } else {
                linha.style.display = 'none';
            }
        });
    }

    toggleAllTable(checkboxPrincipal) {
        const todosCheckboxes = document.querySelectorAll('.cb-table-uf, .cb-table-item');
        todosCheckboxes.forEach(checkbox => checkbox.checked = checkboxPrincipal.checked);
        this.atualizarToolbar();
    }
    
    toggleTableUfCheckbox(checkboxUf) {
        const ufAlvo = checkboxUf.getAttribute('data-uf');
        const checkboxesItensDaUf = document.querySelectorAll(`.cb-table-item[data-uf="${ufAlvo}"]`);
        checkboxesItensDaUf.forEach(checkbox => checkbox.checked = checkboxUf.checked);
        this.atualizarToolbar();
    }
    
    atualizarToolbar() {
        if (!this.toolbarAcoesLote || !this.contadorAcoesLote) return;

        const itensSelecionados = document.querySelectorAll('.cb-table-item:checked').length;
        this.contadorAcoesLote.innerText = itensSelecionados;
        
        if (itensSelecionados > 0) {
            this.toolbarAcoesLote.classList.add('visible');
        } else {
            this.toolbarAcoesLote.classList.remove('visible');
        }
    }

    // --- MANIPULAÇÃO DA ÁRVORE (TREE VIEW) DO MODAL ---
    toggleTreeNode(targetId, iconeElemento) {
        const elementoAlvo = document.getElementById(targetId);
        if (!elementoAlvo || !iconeElemento) return;

        const estaRecolhido = elementoAlvo.classList.contains('collapsed');
        
        if (estaRecolhido) {
            elementoAlvo.classList.remove('collapsed');
            iconeElemento.classList.remove('collapsed');
        } else {
            elementoAlvo.classList.add('collapsed');
            iconeElemento.classList.add('collapsed');
        }
    }

    toggleTreeAll(checkboxPrincipal) {
        const checkboxesArvore = document.querySelectorAll('.cb-tree-uf, .cb-tree-filial');
        checkboxesArvore.forEach(checkbox => checkbox.checked = checkboxPrincipal.checked);
    }
    
    toggleTreeUf(checkboxUf) {
        const ufAlvo = checkboxUf.value;
        const checkboxesFiliaisDaUf = document.querySelectorAll(`.cb-tree-filial[data-uf="${ufAlvo}"]`);
        checkboxesFiliaisDaUf.forEach(checkbox => checkbox.checked = checkboxUf.checked);
    }

    // --- CONTROLE DE MODAL E REQUISIÇÕES ---
    abrirModal(modoEdicao) {
        if (!this.formCorte || !this.modal) return;

        this.formCorte.reset();
        document.getElementById('input-is-edit').value = modoEdicao;
        
        const elementoTitulo = document.getElementById('modal-title-text');
        const containerArvore = document.getElementById('container-tree');

        if (modoEdicao) {
            if (elementoTitulo) elementoTitulo.innerText = "Editar Horários Selecionados";
            if (containerArvore) containerArvore.style.display = 'none';
        } else {
            if (elementoTitulo) elementoTitulo.innerText = "Nova Regra em Massa";
            if (containerArvore) containerArvore.style.display = 'block';
            
            document.querySelectorAll('.cb-tree-all, .cb-tree-uf, .cb-tree-filial').forEach(checkbox => checkbox.checked = false);
        }

        this.modal.classList.add('open');
    }

    fecharModal() {
        if (this.modal) this.modal.classList.remove('open');
    }

    async salvarRegistro(eventoSubmit) {
        eventoSubmit.preventDefault();
        
        const modoEdicao = document.getElementById('input-is-edit').value === 'true';
        const botaoSubmeter = document.getElementById('btn-submit-form');
        const textoOriginalBotao = botaoSubmeter.innerHTML;

        let payloadRequest = {
            horario: document.getElementById('input-horario').value,
            descricao: document.getElementById('input-descricao').value,
            ids: [], 
            filiais: []
        };

        if (modoEdicao) {
            document.querySelectorAll('.cb-table-item:checked').forEach(checkbox => payloadRequest.ids.push(checkbox.value));
        } else {
            document.querySelectorAll('.cb-tree-filial:checked').forEach(checkbox => payloadRequest.filiais.push(checkbox.value));
            
            if (payloadRequest.filiais.length === 0) {
                return LuftCore.notificar('Por favor, selecione pelo menos uma filial na árvore de seleção.', 'warning');
            }
        }

        botaoSubmeter.disabled = true;
        botaoSubmeter.innerHTML = '<i class="ph-bold ph-spinner animate-spin"></i> Salvando...';

        const urlDestino = this.tabAtual === 'planejamento' ? rotasCortes.salvarPlanejamento : rotasCortes.salvarEmissao;
        
        try {
            const respostaServidor = await fetch(urlDestino, { 
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify(payloadRequest) 
            });

            if (respostaServidor.ok) {
                this.fecharModal();
                this.carregarDados();
            } else {
                const retornoErro = await respostaServidor.json();
                LuftCore.notificar('Erro ao salvar: ' + (retornoErro.msg || 'Falha desconhecida'), 'danger');
            }
        } catch (erroDeRede) { 
            console.error(erroDeRede);
            LuftCore.notificar('Erro de conexão ao servidor ao tentar salvar.', 'danger');
        } finally {
            botaoSubmeter.disabled = false;
            botaoSubmeter.innerHTML = textoOriginalBotao;
        }
    }

    async excluirSelecionados() {
        const idsParaExclusao = Array.from(document.querySelectorAll('.cb-table-item:checked')).map(checkbox => checkbox.value);
        
        if (idsParaExclusao.length === 0) return;
        if (!confirm(`Tem certeza que deseja excluir permanentemente ${idsParaExclusao.length} regra(s) de horário?`)) return;

        // Substitui o placeholder __TIPO__ pela aba atual dinamicamente
        const urlExclusao = rotasCortes.excluirEmMassa.replace('__TIPO__', this.tabAtual);
        
        try {
            const respostaServidor = await fetch(urlExclusao, { 
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify({ ids: idsParaExclusao }) 
            });

            if (respostaServidor.ok) {
                this.carregarDados();
            } else {
                const retornoErro = await respostaServidor.json();
                LuftCore.notificar('Erro ao excluir as regras: ' + (retornoErro.msg || 'Falha desconhecida'), 'danger');
            }
        } catch (erroDeRede) { 
            console.error(erroDeRede);
            LuftCore.notificar('Erro de conexão ao servidor ao tentar excluir.', 'danger');
        }
    }
}

// Instanciação Global e Exposição para a Interface HTML (onchange, onclick, onkeyup)
let gerenciadorCortes;

document.addEventListener('DOMContentLoaded', () => {
    gerenciadorCortes = new GerenciadorCortes();
    gerenciadorCortes.inicializar();

    // Mapeamento global para os eventos inline mantidos no HTML para performance
    window.mudarAba = (nova) => gerenciadorCortes.mudarAba(nova);
    window.filtrarTabelaFrontend = () => gerenciadorCortes.filtrarTabelaFrontend();
    window.toggleAllTable = (elemento) => gerenciadorCortes.toggleAllTable(elemento);
    window.toggleTableUfCheckbox = (elemento) => gerenciadorCortes.toggleTableUfCheckbox(elemento);
    window.atualizarToolbar = () => gerenciadorCortes.atualizarToolbar();
    window.toggleTreeNode = (alvo, icone) => gerenciadorCortes.toggleTreeNode(alvo, icone);
    window.toggleTreeAll = (elemento) => gerenciadorCortes.toggleTreeAll(elemento);
    window.toggleTreeUf = (elemento) => gerenciadorCortes.toggleTreeUf(elemento);
    window.abrirModal = (modoEdicao) => gerenciadorCortes.abrirModal(modoEdicao);
    window.fecharModal = () => gerenciadorCortes.fecharModal();
    window.salvarRegistro = (evento) => gerenciadorCortes.salvarRegistro(evento);
    window.excluirSelecionados = () => gerenciadorCortes.excluirSelecionados();
});