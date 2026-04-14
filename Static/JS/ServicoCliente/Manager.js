/**
 * Manager.js
 * Lógica da tela de Gestão de Serviços ao Cliente
 * Refatorado com Classes, camelCase e Injeção de Rotas
 */

class GerenciadorServicosClientes {
    constructor() {
        this.modalId = 'modalServicoCliente';
        this.formServico = document.getElementById('FormServico');
        this.btnSubmit = document.getElementById('BtnSubmit');
        this.infoContagem = document.getElementById('InfoContagem');
        this.treeRoot = document.querySelector('.luft-tree-root');
        this.tbodyServicos = document.getElementById('tbody-servicos');
        this.loaderTabela = document.getElementById('loader-tabela');
        this.tabelaServicos = document.getElementById('tabela-servicos');
        this.emptyState = document.getElementById('empty-state');
        this.modal = document.getElementById(this.modalId);
        this.modalBackdrop = document.getElementById(`${this.modalId}-backdrop`);
        this.modalCloseButton = this.modal ? this.modal.querySelector('.luft-modal-close') : null;
        this.modalTitle = this.modal ? this.modal.querySelector('.luft-modal-title') : null;
        this.blocoSelecaoClientes = document.getElementById('BlocoSelecaoClientes');
        this.blocoClienteEdicao = document.getElementById('BlocoClienteEdicao');
        this.clienteEdicaoCodigo = document.getElementById('ClienteEdicaoCodigo');
        this.clienteEdicaoNome = document.getElementById('ClienteEdicaoNome');
        this.clienteEdicaoCnpj = document.getElementById('ClienteEdicaoCnpj');
        this.servicosPorId = new Map();
    }

    inicializar() {
        this.carregarListaServicos();
        this.configurarTreeview();
        this.configurarModal();
        this.resetarFormulario();
    }

    configurarModal() {
        [this.modalBackdrop, this.modalCloseButton].forEach(elemento => {
            if (elemento) {
                elemento.addEventListener('click', () => this.resetarFormulario());
            }
        });
    }

    obterControladorModal() {
        if (typeof LuftCore !== 'undefined') {
            return LuftCore;
        }

        if (typeof window !== 'undefined' && window.LuftCore) {
            return window.LuftCore;
        }

        return null;
    }

    abrirModalLuft() {
        const controladorModal = this.obterControladorModal();

        if (controladorModal?.abrirModal) {
            controladorModal.abrirModal(this.modalId);
            return;
        }

        if (this.modal && this.modalBackdrop) {
            this.modalBackdrop.classList.add('show');
            this.modal.classList.add('show');
            document.body.style.overflow = 'hidden';
        }
    }

    fecharModalLuft() {
        const controladorModal = this.obterControladorModal();

        if (controladorModal?.fecharModal) {
            controladorModal.fecharModal(this.modalId);
            return;
        }

        if (this.modal && this.modalBackdrop) {
            this.modalBackdrop.classList.remove('show');
            this.modal.classList.remove('show');
            document.body.style.overflow = '';
        }
    }

    resetarFormulario() {
        if (!this.formServico) return;

        this.formServico.reset();
        this.formServico.action = rotasServicos.salvar;

        document.querySelectorAll('.chk-cliente, .chk-grupo').forEach(checkbox => {
            checkbox.checked = false;
            checkbox.indeterminate = false;
        });

        document.querySelectorAll('.luft-tree-children').forEach(container => {
            container.style.display = 'none';
        });

        document.querySelectorAll('.toggle-icon').forEach(icone => {
            icone.classList.remove('open');
        });

        this.atualizarContagem();

        if (this.modalTitle) {
            this.modalTitle.innerHTML = '<i class="ph-bold ph-handshake text-primary"></i> Novo Serviço';
        }

        if (this.btnSubmit) {
            this.btnSubmit.innerHTML = '<i class="ph-bold ph-floppy-disk"></i> Salvar';
            this.btnSubmit.classList.remove('btn-success');
            this.btnSubmit.classList.add('btn-primary');
        }

        if (this.blocoSelecaoClientes) {
            this.blocoSelecaoClientes.classList.remove('luft-hidden');
        }

        if (this.blocoClienteEdicao) {
            this.blocoClienteEdicao.classList.add('luft-hidden');
        }

        if (this.clienteEdicaoCodigo) {
            this.clienteEdicaoCodigo.textContent = '';
        }

        if (this.clienteEdicaoNome) {
            this.clienteEdicaoNome.textContent = '';
        }

        if (this.clienteEdicaoCnpj) {
            this.clienteEdicaoCnpj.textContent = '';
        }
    }

    abrirCadastro() {
        this.resetarFormulario();
        this.abrirModalLuft();
    }

    fecharModalCadastro() {
        this.resetarFormulario();
        this.fecharModalLuft();
    }

    // --- LÓGICA DO TREEVIEW ---
    toggleTree(icone) {
        icone.classList.toggle('open');
        const containerFilhos = icone.closest('li').querySelector('.luft-tree-children');
        if (containerFilhos) {
            containerFilhos.style.display = containerFilhos.style.display === 'block' ? 'none' : 'block';
        }
    }

    atualizarContagem() {
        if (!this.infoContagem) return;
        const clientesMarcados = document.querySelectorAll('.chk-cliente:checked').length;
        this.infoContagem.textContent = `${clientesMarcados} Selecionado${clientesMarcados === 1 ? '' : 's'}`;
    }

    configurarTreeview() {
        if (!this.treeRoot) return;
        
        this.treeRoot.addEventListener('change', (evento) => {
            const alvo = evento.target;
            
            // Se clicou no checkbox do grupo pai
            if (alvo.classList.contains('chk-grupo')) {
                const liPai = alvo.closest('li');
                const checkboxesFilhos = liPai.querySelectorAll('.chk-cliente');
                checkboxesFilhos.forEach(checkbox => checkbox.checked = alvo.checked);
            }
            
            // Se clicou em um cliente específico
            if (alvo.classList.contains('chk-cliente')) {
                this.updateParentStatus(alvo);
            }
            
            this.atualizarContagem();
        });
    }

    updateParentStatus(checkboxFilho) {
        const ulPai = checkboxFilho.closest('.luft-tree-children');
        if (!ulPai) return;
        
        const liPai = ulPai.closest('li');
        const checkboxPai = liPai.querySelector('.chk-grupo');
        if (!checkboxPai) return;
        
        const todosFilhos = ulPai.querySelectorAll('.chk-cliente');
        let todosMarcados = true;
        let algumMarcado = false;

        todosFilhos.forEach(cb => {
            if (cb.checked) algumMarcado = true;
            else todosMarcados = false;
        });

        checkboxPai.checked = todosMarcados;
        checkboxPai.indeterminate = algumMarcado && !todosMarcados;
    }
    // --- FIM LÓGICA TREEVIEW ---

    carregarListaServicos() {
        if (!this.loaderTabela || !this.tabelaServicos || !this.emptyState) return;

        this.loaderTabela.style.display = 'block';
        this.tabelaServicos.style.display = 'none';
        this.emptyState.style.display = 'none';

        fetch(rotasServicos.listar)
            .then(resposta => resposta.json())
            .then(dados => {
                this.tbodyServicos.innerHTML = '';
                this.servicosPorId = new Map();

                dados.forEach(item => {
                    this.servicosPorId.set(Number(item.Id), item);
                });
                
                if (dados.length === 0) {
                    this.loaderTabela.style.display = 'none';
                    this.emptyState.style.display = 'block';
                    return;
                }

                // Agrupa os dados por Nome do Grupo
                const grupos = dados.reduce((acumulador, item) => {
                    if (!acumulador[item.Grupo]) acumulador[item.Grupo] = [];
                    acumulador[item.Grupo].push(item);
                    return acumulador;
                }, {});

                const nomesGrupos = Object.keys(grupos).sort();

                nomesGrupos.forEach((nomeGrupo, indiceGrupo) => {
                    const clientesDoGrupo = grupos[nomeGrupo];
                    const nomeExibicaoGrupo = nomeGrupo === 'Z_Sem Grupo' ? 'Geral / Sem Grupo' : nomeGrupo;

                    // CABEÇALHO DO GRUPO (A "Pastinha")
                    const linhaGrupo = document.createElement('tr');
                    linhaGrupo.className = 'linha-grupo-header';
                    linhaGrupo.style.backgroundColor = 'var(--luft-bg-app)';
                    linhaGrupo.style.cursor = 'pointer';
                    linhaGrupo.innerHTML = `
                        <td colspan="5" style="padding: 12px 24px; font-weight: 700; color: var(--luft-text-main);" onclick="toggleTabelaGrupo('grupo_tabela_${indiceGrupo}')">
                            <i class="ph-bold ph-caret-down toggle-icon-tabela" id="icon_tabela_${indiceGrupo}" style="transition: transform 0.2s; display: inline-block;"></i>
                            <i class="ph-bold ph-folders" style="margin-left: 8px; margin-right: 8px; color: var(--luft-primary-600);"></i>
                            ${nomeExibicaoGrupo} 
                            <span style="font-size: 0.8rem; color: var(--luft-text-muted); font-weight: 600; margin-left: 6px;">(${clientesDoGrupo.length} serviço(s))</span>
                        </td>
                    `;
                    this.tbodyServicos.appendChild(linhaGrupo);

                    // CLIENTES DO GRUPO
                    clientesDoGrupo.forEach(item => {
                        const tr = document.createElement('tr');
                        tr.className = `linha-grupo-tabela grupo_tabela_${indiceGrupo}`; 
                        
                        const urlExcluir = rotasServicos.excluirBase.replace('0', item.Id);
                        const nomeExibicao = item.Fantasia || item.RazaoSocial || 'Nome não cadastrado';

                        tr.innerHTML = `
                            <td style="padding-left: 40px;"> 
                                <div style="font-size: 0.75rem; font-weight: 800; color: var(--luft-primary-600); margin-bottom: 2px;">
                                    CÓD: ${item.CodigoCliente}
                                </div>
                                <div style="font-weight: 700; color: var(--luft-text-main);">
                                    ${nomeExibicao}
                                </div>
                                <div style="font-size: 0.75rem; color: var(--luft-text-muted); margin-top: 2px; font-family: monospace;">
                                    CNPJ: ${item.Cnpj || 'N/A'}
                                </div>
                            </td>
                            <td>
                                <div style="margin-bottom: 4px; font-size: 0.85rem;"><strong class="text-muted">Validade:</strong> <span class="font-bold text-main">${item.DurabilidadeGelo}</span></div>
                                <div style="font-size: 0.85rem;"><strong class="text-muted">Troca:</strong> ${this.obterBadgeAutorizacao(item.AutorizacaoTrocaGelo)}</div>
                            </td>
                            <td>${this.obterBadgeAutorizacao(item.AutorizacaoArmazenagem)}</td>
                            <td>${this.obterBadgeServico(item.ServicoContratado)}</td>
                            <td style="text-align: center;">
                                <div class="d-flex justify-content-center gap-2">
                                    <button type="button" class="btn btn-secondary text-primary d-flex align-items-center justify-content-center" style="width: 36px; height: 36px; padding: 0;" title="Editar"
                                        onclick="prepararEdicao(${item.Id})">
                                        <i class="ph-bold ph-pencil-simple text-lg"></i>
                                    </button>
                                    
                                    <form action="${urlExcluir}" method="POST" style="display:inline;" onsubmit="return confirm('Tem certeza que deseja excluir as parametrizações deste cliente?');">
                                        <button type="submit" class="btn btn-secondary text-danger d-flex align-items-center justify-content-center" style="width: 36px; height: 36px; padding: 0;" title="Excluir">
                                            <i class="ph-bold ph-trash text-lg"></i>
                                        </button>
                                    </form>
                                </div>
                            </td>
                        `;
                        this.tbodyServicos.appendChild(tr);
                    });
                });

                this.loaderTabela.style.display = 'none';
                this.tabelaServicos.style.display = 'table';
            })
            .catch(erro => {
                console.error("Erro ao carregar lista de serviços:", erro);
                this.loaderTabela.innerHTML = `<p class="text-danger font-bold"><i class="ph-bold ph-warning"></i> Erro ao carregar dados do servidor.</p>`;
            });
    }

    obterBadgeAutorizacao(valor) {
        if(valor === 'SIM') return `<span class="luft-badge luft-badge-success">SIM</span>`;
        if(valor === 'NÃO') return `<span class="luft-badge luft-badge-danger">NÃO</span>`;
        return `<span class="luft-badge luft-badge-warning">SOB AUTORIZAÇÃO</span>`;
    }

    obterBadgeServico(valor) {
        if(valor === 'EXPRESSO') return `<span class="luft-badge luft-badge-warning"><i class="ph-fill ph-lightning"></i> EXPRESSO</span>`;
        if(valor === 'DEPENDE_DO_DESTINO') return `<span class="luft-badge luft-badge-info"><i class="ph-fill ph-star"></i> DEPENDE DO DESTINO</span>`;
        return `<span class="luft-badge luft-badge-success"><i class="ph-fill ph-truck"></i> ECONÔMICO</span>`;
    }

    toggleTabelaGrupo(classeGrupo) {
        const linhas = document.querySelectorAll('.' + classeGrupo);
        const idIcone = classeGrupo.replace('grupo_tabela_', 'icon_tabela_');
        const icone = document.getElementById(idIcone);
        
        let estaOculto = false;
        if (linhas.length > 0) {
            estaOculto = linhas[0].style.display === 'none';
        }

        linhas.forEach(linha => {
            linha.style.display = estaOculto ? 'table-row' : 'none';
        });

        if (icone) {
            icone.style.transform = estaOculto ? 'rotate(0deg)' : 'rotate(-90deg)';
        }
    }

    prepararEdicao(id) {
        const item = this.servicosPorId.get(Number(id));
        if (!item) return;

        this.resetarFormulario();

        document.getElementById('DurabilidadeGelo').value = item.DurabilidadeGelo || '';
        document.getElementById('AutorizacaoTrocaGelo').value = item.AutorizacaoTrocaGelo || 'SIM';
        document.getElementById('AutorizacaoArmazenagem').value = item.AutorizacaoArmazenagem || 'SIM';
        document.getElementById('ServicoContratado').value = item.ServicoContratado || '';

        const checkboxEdicao = document.getElementById('cliente_' + item.CodigoCliente);
        if (checkboxEdicao) {
            checkboxEdicao.checked = true;
            this.updateParentStatus(checkboxEdicao);
            
            const ulPai = checkboxEdicao.closest('.luft-tree-children');
            if (ulPai) {
                ulPai.style.display = 'block';
                const icone = ulPai.closest('li').querySelector('.toggle-icon');
                if (icone) icone.classList.add('open');
            }
        }
        
        this.atualizarContagem();

        this.formServico.action = rotasServicos.editarBase.replace('0', id);
        if (this.modalTitle) {
            this.modalTitle.innerHTML = '<i class="ph-bold ph-pencil-simple text-warning"></i> Editar Serviço';
        }
        
        this.btnSubmit.innerHTML = '<i class="ph-bold ph-check-circle"></i> Atualizar';
        this.btnSubmit.classList.remove('btn-success');
        this.btnSubmit.classList.add('btn-primary');

        if (this.blocoSelecaoClientes) {
            this.blocoSelecaoClientes.classList.add('luft-hidden');
        }

        if (this.blocoClienteEdicao) {
            this.blocoClienteEdicao.classList.remove('luft-hidden');
        }

        if (this.clienteEdicaoCodigo) {
            this.clienteEdicaoCodigo.textContent = `COD ${item.CodigoCliente}`;
        }

        if (this.clienteEdicaoNome) {
            this.clienteEdicaoNome.textContent = item.Fantasia || item.RazaoSocial || 'Cliente';
        }

        if (this.clienteEdicaoCnpj) {
            this.clienteEdicaoCnpj.textContent = item.Cnpj || '';
        }

        this.abrirModalLuft();
    }

    cancelarEdicao() {
        this.resetarFormulario();
    }
}

// Instanciação Global e Exposição para a UI (onclick e onchange no HTML)
let gerenciadorServicosClientes;

document.addEventListener("DOMContentLoaded", () => {
    gerenciadorServicosClientes = new GerenciadorServicosClientes();
    gerenciadorServicosClientes.inicializar();

    // Mapeamento global para os eventos inline
    window.toggleTree = (icone) => gerenciadorServicosClientes.toggleTree(icone);
    window.abrirCadastro = () => gerenciadorServicosClientes.abrirCadastro();
    window.carregarListaServicos = () => gerenciadorServicosClientes.carregarListaServicos();
    window.fecharModalCadastro = () => gerenciadorServicosClientes.fecharModalCadastro();
    window.toggleTabelaGrupo = (classeGrupo) => gerenciadorServicosClientes.toggleTabelaGrupo(classeGrupo);
    window.prepararEdicao = (id) => gerenciadorServicosClientes.prepararEdicao(id);
});