class GerenciadorCiasAereas {
    constructor() {
        this.modalNovaCia = document.getElementById('modal-nova-cia');
        this.inputNovaCia = document.getElementById('input-nova-cia');
        this.inputNovoScore = document.getElementById('input-novo-score');
    }

    atualizarLabel(cia, valor) {
        const lbl = document.getElementById(`lbl-${cia}`);
        if (!lbl) return;
        lbl.innerText = valor + '%';
        lbl.className = 'score-badge';
        const nivel = Math.floor(valor / 20);
        lbl.classList.add(`score-${nivel}`);
    }

    async salvarPreferencia(cia, valor) {
        try {
            const resposta = await fetch(API_SALVAR, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cia: cia, score: valor })
            });
            const dados = await resposta.json();
            if (!dados.sucesso) alert('Erro ao salvar preferência.');
        } catch (erro) {
            console.error(erro);
            alert("Erro de conexão ao salvar.");
        }
    }

    abrirModalNovaCia() {
        if (this.inputNovaCia) this.inputNovaCia.value = '';
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
            alert('Digite o nome da Cia.'); 
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
                alert('Erro ao criar companhia.');
            }
        } catch (erro) {
            console.error(erro);
            alert("Erro de conexão ao salvar.");
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