class GerenciadorCiasAereas {
    constructor() {
        this.modalNovaCia = document.getElementById('modal-nova-cia');
        this.inputNovaCia = document.getElementById('input-nova-cia');
        this.inputNovoScore = document.getElementById('input-novo-score');
        this.lblNovoScore = document.getElementById('lbl-novo-score');

        this.configurarRanges();

        if (this.inputNovoScore) {
            this.inputNovoScore.addEventListener('input', () => this.atualizarPreviewNovaCia(this.inputNovoScore.value));
        }
    }

    obterEstadoScore(valor) {
        const score = Number(valor);

        if (score < 40) {
            return { classe: 'score-1', cor: '#dc2626', texto: 'Prioridade baixa' };
        }

        if (score < 80) {
            return { classe: 'score-3', cor: '#d97706', texto: 'Prioridade moderada' };
        }

        return { classe: 'score-5', cor: '#16a34a', texto: 'Prioridade alta' };
    }

    aplicarEstiloRange(elemento, valor) {
        if (!elemento) return;

        const estado = this.obterEstadoScore(valor);
        elemento.style.setProperty('--score-value', String(valor));
        elemento.style.setProperty('--score-accent', estado.cor);
    }

    configurarRanges() {
        document.querySelectorAll('.score-range').forEach(range => {
            this.aplicarEstiloRange(range, Number(range.value || 0));
        });

        if (this.inputNovoScore) {
            this.aplicarEstiloRange(this.inputNovoScore, Number(this.inputNovoScore.value || 50));
        }
    }

    atualizarPreviewNovaCia(valor) {
        const estado = this.obterEstadoScore(valor);

        this.aplicarEstiloRange(this.inputNovoScore, valor);

        if (this.lblNovoScore) {
            this.lblNovoScore.innerText = `${valor}%`;
            this.lblNovoScore.className = `score-badge ${estado.classe}`;
        }
    }

    atualizarLabel(cia, valor) {
        const lbl = document.getElementById(`lbl-${cia}`);
        const range = document.getElementById(`range-${cia}`);
        const subtitulo = document.getElementById(`sub-${cia}`);
        const status = document.getElementById(`status-${cia}`);
        const estado = this.obterEstadoScore(valor);

        this.aplicarEstiloRange(range, valor);

        if (!lbl) return;

        lbl.innerText = valor + '%';
        lbl.className = 'score-badge';
        const nivel = Math.floor(Number(valor) / 20);
        lbl.classList.add(`score-${nivel}`);

        if (subtitulo) subtitulo.innerText = estado.texto;
        if (status) status.innerText = estado.texto;
    }

    async salvarPreferencia(cia, valor) {
        try {
            const resposta = await fetch(API_SALVAR, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cia: cia, score: valor })
            });
            const dados = await resposta.json();
            if (!dados.sucesso) LuftCore.notificar('Erro ao salvar preferência.', 'danger');
        } catch (erro) {
            console.error(erro);
            LuftCore.notificar('Erro de conexão ao salvar.', 'danger');
        }
    }

    abrirModalNovaCia() {
        if (this.inputNovaCia) this.inputNovaCia.value = '';
        if (this.inputNovoScore) {
            this.inputNovoScore.value = 50;
            this.atualizarPreviewNovaCia(50);
        }
        if (this.modalNovaCia) {
            this.modalNovaCia.classList.remove('hidden');
            setTimeout(() => this.modalNovaCia.classList.add('visible'), 10);
        }
    }

    fecharModalNovaCia(evento) {
        if (evento && !evento.target.classList.contains('modal-backdrop')) return;
        if (this.modalNovaCia) {
            this.modalNovaCia.classList.remove('visible');
            setTimeout(() => this.modalNovaCia.classList.add('hidden'), 300);
        }
    }

    async salvarNovaCia() {
        if (!this.inputNovaCia || !this.inputNovoScore) return;
        
        const nome = this.inputNovaCia.value.trim().toUpperCase();
        const score = this.inputNovoScore.value;

        if (!nome) { 
            LuftCore.notificar('Digite o nome da Cia.', 'warning');
            return; 
        }

        try {
            const resposta = await fetch(API_SALVAR, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cia: nome, score: score })
            });
            const dados = await resposta.json();
            
            if (dados.sucesso) {
                location.reload(); 
            } else {
                LuftCore.notificar('Erro ao criar companhia.', 'danger');
            }
        } catch (erro) {
            console.error(erro);
            LuftCore.notificar('Erro de conexão ao salvar.', 'danger');
        }
    }
}

const gerenciadorCias = new GerenciadorCiasAereas();

// Expõe os métodos com os nomes originais para o HTML
window.AtualizarLabel = (cia, valor) => gerenciadorCias.atualizarLabel(cia, valor);
window.SalvarPreferencia = (cia, valor) => gerenciadorCias.salvarPreferencia(cia, valor);
window.AbrirModalNovaCia = () => gerenciadorCias.abrirModalNovaCia();
window.FecharModalNovaCia = (evento) => gerenciadorCias.fecharModalNovaCia(evento);
window.SalvarNovaCia = () => gerenciadorCias.salvarNovaCia();