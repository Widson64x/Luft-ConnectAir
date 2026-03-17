/**
 * HomeDashboard.js
 * Lógica do painel principal (Dashboard) do Luft-ConnectAir
 * Refatorado com Classes, camelCase e Rotas Injetadas
 */

class GerenciadorDashboard {
    constructor() {
        this.elementoRelogio = document.getElementById('local-clock');
        this.elementoVoosAtivos = document.getElementById('voos-ativos');
        this.elementoStatusApi = document.getElementById('status-api');
    }

    inicializar() {
        this.iniciarRelogio();
        this.carregarEstatisticas();
        
        // Atualiza as estatísticas a cada 60 segundos
        setInterval(() => this.carregarEstatisticas(), 60000);
    }

    iniciarRelogio() {
        const atualizarHora = () => {
            if (!this.elementoRelogio) return;
            const agora = new Date();
            const opcoes = { 
                timeZone: 'America/Sao_Paulo', 
                hour12: false, 
                hour: '2-digit', 
                minute: '2-digit', 
                second: '2-digit' 
            };
            this.elementoRelogio.innerText = agora.toLocaleTimeString('pt-BR', opcoes);
        };
        
        atualizarHora(); // Chama imediatamente
        setInterval(atualizarHora, 1000); // Atualiza a cada segundo
    }

    async carregarEstatisticas() {
        if (!this.elementoVoosAtivos || !this.elementoStatusApi) return;

        try {
            // Usa o interceptador de fetch do Base.js automaticamente
            const resposta = await fetch(rotasDashboard.apiVoosHoje);
            if (!resposta.ok) throw new Error('Erro na comunicação com a API de estatísticas');
            
            const totalVoos = await resposta.json();
            
            this.elementoVoosAtivos.innerText = totalVoos;
            
            this.elementoStatusApi.innerText = "Online";
            this.elementoStatusApi.classList.remove("text-danger");
            this.elementoStatusApi.classList.add("text-success");

        } catch (erro) {
            console.warn("Falha ao carregar estatísticas do dashboard:", erro);
            
            this.elementoStatusApi.innerText = "Off-line";
            this.elementoStatusApi.classList.remove("text-success");
            this.elementoStatusApi.classList.add("text-danger");
        }
    }
}

// Instanciação Global
document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new GerenciadorDashboard();
    dashboard.inicializar();
});