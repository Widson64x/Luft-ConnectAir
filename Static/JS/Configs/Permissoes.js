class GerenciadorPermissoes {
    constructor() {
        this.PODE_EDITAR = configPermissoes.podeEditar;
        this.MODO = 'Grupo'; 
        this.ID_ATUAL = null;
        this.DADOS_ATUAIS = null;
    }

    mudarAba(novaAba) {
        document.querySelectorAll('.luft-tab-btn').forEach(b => b.classList.remove('ativo'));
        event.currentTarget.classList.add('ativo');

        document.getElementById('listaGrupos').classList.toggle('d-none', novaAba !== 'grupo');
        document.getElementById('listaGrupos').classList.toggle('d-block', novaAba === 'grupo');
        document.getElementById('listaUsuarios').classList.toggle('d-none', novaAba !== 'usuario');
        document.getElementById('listaUsuarios').classList.toggle('d-block', novaAba === 'usuario');
        
        document.getElementById('painelPermissoes').classList.remove('d-flex');
        document.getElementById('painelPermissoes').classList.add('d-none');
        document.getElementById('estadoVazio').classList.remove('d-none');
        
        document.getElementById('msgVazio').innerText = (novaAba === 'grupo') ? 'Selecione um grupo ao lado' : 'Selecione um usuário ao lado';
        
        this.MODO = (novaAba === 'grupo') ? 'Grupo' : 'Usuario';
        this.ID_ATUAL = null;
        document.querySelectorAll('.luft-list-item').forEach(i => i.classList.remove('ativo'));
    }

    async carregarGrupo(el, id, nome) {
        if(this.MODO !== 'Grupo') return;
        this.ID_ATUAL = id;
        this.ativarItemLista(el);
        this.prepararPainel(nome, 'Editando permissões gerais do grupo');

        try {
            const resp = await fetch(`${configPermissoes.urls.buscarAcessosGrupo}?idGrupo=${id}`);
            const dados = await resp.json();
            const ativos = new Set(dados.ids_ativos);
            
            document.querySelectorAll('.check-perm').forEach(chk => {
                const idPerm = parseInt(chk.dataset.id);
                chk.checked = ativos.has(idPerm);
                chk.disabled = !this.PODE_EDITAR;
                this.configurarVisualUsuario(idPerm, null, null, null); 
            });
        } catch (e) { LuftCore.notificar('Erro ao carregar grupo.', 'danger'); console.error(e); }
    }

    async carregarUsuario(el, id, nome) {
        if(this.MODO !== 'Usuario') return;
        this.ID_ATUAL = id;
        this.ativarItemLista(el);
        this.prepararPainel(nome, 'Editando exceções e heranças');

        try {
            const resp = await fetch(`${configPermissoes.urls.buscarAcessosUsuario}?idUsuario=${id}`);
            this.DADOS_ATUAIS = await resp.json();
            
            const heranca = new Set(this.DADOS_ATUAIS.heranca_grupo);
            const permitidos = new Set(this.DADOS_ATUAIS.usuario_permitidos);
            const bloqueados = new Set(this.DADOS_ATUAIS.usuario_bloqueados);

            document.querySelectorAll('.check-perm').forEach(chk => {
                const idPerm = parseInt(chk.dataset.id);
                let isChecked = false;
                let tipoStatus = 'herdado';

                if (permitidos.has(idPerm)) {
                    isChecked = true;
                    tipoStatus = 'forcado';
                } else if (bloqueados.has(idPerm)) {
                    isChecked = false;
                    tipoStatus = 'bloqueado';
                } else {
                    isChecked = heranca.has(idPerm);
                    tipoStatus = 'herdado';
                }

                chk.checked = isChecked;
                chk.disabled = !this.PODE_EDITAR;
                this.configurarVisualUsuario(idPerm, tipoStatus, isChecked, heranca.has(idPerm));
            });
        } catch (e) { LuftCore.notificar('Erro ao carregar usuário.', 'danger'); console.error(e); }
    }

    async processarClick(chk) {
        if (!this.PODE_EDITAR) {
            chk.checked = !chk.checked;
            LuftCore.notificar('Você não tem permissão para editar.', 'warning');
            return;
        }

        if (!this.ID_ATUAL) return;
        const idPerm = chk.dataset.id;
        const novoEstado = chk.checked; 

        if (this.MODO === 'Grupo') {
            await this.enviarAPI('Grupo', this.ID_ATUAL, idPerm, novoEstado ? 'Adicionar' : 'Remover');
            return;
        }

        if (this.MODO === 'Usuario') {
            const acao = novoEstado ? 'Permitir' : 'Bloquear';
            await this.enviarAPI('Usuario', this.ID_ATUAL, idPerm, acao);
            this.configurarVisualUsuario(idPerm, novoEstado ? 'forcado' : 'bloqueado', novoEstado, null);
        }
    }

    async resetarPermissao(idPerm) {
        if (!confirm('Voltar a herdar do grupo?')) return;
        await this.enviarAPI('Usuario', this.ID_ATUAL, idPerm, 'Resetar');
        const heranca = new Set(this.DADOS_ATUAIS.heranca_grupo);
        const herdaAtivo = heranca.has(parseInt(idPerm));
        
        const chk = document.getElementById('chk-' + idPerm);
        chk.checked = herdaAtivo;
        this.configurarVisualUsuario(idPerm, 'herdado', herdaAtivo, null);
    }

    configurarVisualUsuario(idPerm, tipoStatus, isChecked, herancaValor) {
        const badgeInherit = document.getElementById(`badge-inherit-${idPerm}`);
        const badgeAllow = document.getElementById(`badge-allow-${idPerm}`);
        const badgeDeny = document.getElementById(`badge-deny-${idPerm}`);
        const btnReset = document.getElementById(`btn-reset-${idPerm}`);

        if(badgeInherit) badgeInherit.style.display = 'none';
        if(badgeAllow) badgeAllow.style.display = 'none';
        if(badgeDeny) badgeDeny.style.display = 'none';
        if(btnReset) btnReset.style.display = 'none';

        if (this.MODO === 'Grupo') return;

        if (tipoStatus === 'herdado') badgeInherit.style.display = 'inline-block';
        else if (tipoStatus === 'forcado') { badgeAllow.style.display = 'inline-block'; btnReset.style.display = 'inline-block'; }
        else if (tipoStatus === 'bloqueado') { badgeDeny.style.display = 'inline-block'; btnReset.style.display = 'inline-block'; }
    }

    async enviarAPI(tipo, alvo, perm, acao) {
        try {
            const resp = await fetch(configPermissoes.urls.salvarVinculo, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ Tipo: tipo, IdAlvo: alvo, IdPermissao: perm, Acao: acao })
            });
            const d = await resp.json();
            if(!d.sucesso) LuftCore.notificar('Erro: ' + d.erro, 'danger');
        } catch(e) { console.error(e); LuftCore.notificar('Erro de conexão', 'danger'); }
    }

    ativarItemLista(el) {
        document.querySelectorAll('.luft-list-item').forEach(i => i.classList.remove('ativo'));
        el.classList.add('ativo');
    }
    
    prepararPainel(titulo, subtitulo) {
        document.getElementById('estadoVazio').classList.add('d-none');
        document.getElementById('painelPermissoes').classList.remove('d-none');
        document.getElementById('painelPermissoes').classList.add('d-flex');
        
        document.getElementById('tituloSelecionado').innerText = titulo;
        document.getElementById('subtituloSelecionado').innerText = subtitulo;
        document.querySelector('.luft-panel-scroll').scrollTop = 0;
    }

    filtrarLateral(val) {
        val = val.toLowerCase();
        const listaId = this.MODO === 'Grupo' ? 'listaGrupos' : 'listaUsuarios';
        document.querySelectorAll(`#${listaId} .luft-list-item`).forEach(el => {
            el.style.display = el.innerText.toLowerCase().includes(val) ? 'flex' : 'none';
        });
    }

    filtrarPermissoes(val) {
        val = val.toLowerCase();
        document.querySelectorAll('.luft-perm-item').forEach(el => {
            el.style.display = el.innerText.toLowerCase().includes(val) ? 'flex' : 'none';
        });
        document.querySelectorAll('.luft-category-block').forEach(cat => {
            const visible = cat.querySelectorAll('.luft-perm-item[style="display: flex;"], .luft-perm-item:not([style*="display: none"])').length > 0;
            cat.style.display = visible ? 'block' : 'none';
        });
    }

    preverChave() {
        const mod = document.querySelector('input[name="modulo"]').value.toUpperCase().trim().replace(/ /g, '_') || 'MODULO';
        const acao = document.querySelector('select[name="acao"]').value.toUpperCase().trim() || 'ACAO';
        const exc = document.getElementById('inputExcecao').value.toUpperCase().trim().replace(/ /g, '_');
        
        let preview = `${mod}`;
        if(exc) preview += `.${exc}`;
        preview += `.${acao}`;
        
        document.getElementById('chavePreview').innerText = preview;
    }
}

const gerenciadorPermissoes = new GerenciadorPermissoes();

window.MudarAba = (novaAba) => gerenciadorPermissoes.mudarAba(novaAba);
window.CarregarGrupo = (el, id, nome) => gerenciadorPermissoes.carregarGrupo(el, id, nome);
window.CarregarUsuario = (el, id, nome) => gerenciadorPermissoes.carregarUsuario(el, id, nome);
window.ProcessarClick = (chk) => gerenciadorPermissoes.processarClick(chk);
window.ResetarPermissao = (idPerm) => gerenciadorPermissoes.resetarPermissao(idPerm);
window.FiltrarLateral = (val) => gerenciadorPermissoes.filtrarLateral(val);
window.FiltrarPermissoes = (val) => gerenciadorPermissoes.filtrarPermissoes(val);
window.PreverChave = () => gerenciadorPermissoes.preverChave();