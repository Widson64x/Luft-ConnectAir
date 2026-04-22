/**
 * Manager.js
 * Lógica da tela de Gestão de Malha Aérea (Upload e Histórico)
 * Refatorado com Classes, camelCase e Injeção de Rotas
 */

class GerenciadorMalha {
    constructor() {
        this.inputArquivo = document.getElementById('inputArquivoExcel');
        this.areaUpload = document.getElementById('area-upload');
        this.formUpload = document.getElementById('form-upload-malha');
        this.formSubstituicao = document.getElementById('form-substituicao');
        this.botoesExcluir = document.querySelectorAll('.btn-excluir-malha');
    }

    inicializar() {
        this.configurarArrastarESoltar();
        this.configurarEnvioArquivo();
        this.configurarBotoesExclusao();
        this.configurarModalSubstituicao();
    }

    configurarEnvioArquivo() {
        if (!this.inputArquivo || !this.areaUpload) return;

        // Clique na área abre o seletor nativo
        this.areaUpload.addEventListener('click', () => this.inputArquivo.click());

        // Mudança no input dispara o formulário
        this.inputArquivo.addEventListener('change', (evento) => {
            if (evento.target.files.length > 0) {
                this.processarUpload(evento.target.files[0]);
            }
        });
    }

    configurarArrastarESoltar() {
        if (!this.areaUpload || !this.inputArquivo) return;

        // Previne o comportamento padrão do navegador (abrir o arquivo em nova aba)
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(nomeEvento => {
            this.areaUpload.addEventListener(nomeEvento, this.prevenirPadrao, false);
        });

        // Adiciona classe de destaque ao arrastar por cima
        ['dragenter', 'dragover'].forEach(nomeEvento => {
            this.areaUpload.addEventListener(nomeEvento, () => {
                this.areaUpload.classList.add('drag-ativo');
            }, false);
        });

        // Remove classe de destaque ao sair
        ['dragleave', 'drop'].forEach(nomeEvento => {
            this.areaUpload.addEventListener(nomeEvento, () => {
                this.areaUpload.classList.remove('drag-ativo');
            }, false);
        });

        // Captura o arquivo solto
        this.areaUpload.addEventListener('drop', (evento) => {
            const transferenciaDeDados = evento.dataTransfer;
            const arquivos = transferenciaDeDados.files;
            
            if (arquivos.length > 0) {
                this.inputArquivo.files = arquivos;
                this.processarUpload(arquivos[0]);
            }
        }, false);
    }

    prevenirPadrao(evento) {
        evento.preventDefault();
        evento.stopPropagation();
    }

    processarUpload(arquivo) {
        const nomeArquivo = arquivo.name;
        
        // Verifica a extensão
        if (!nomeArquivo.toLowerCase().endsWith('.xlsx')) {
            LuftCore.notificar('Por favor, envie apenas arquivos do Excel (.xlsx).', 'warning');
            this.inputArquivo.value = ''; // Reseta o input
            return;
        }

        // Altera visualmente a área para o estado de "Carregando"
        this.areaUpload.innerHTML = `
            <i class="ph-bold ph-spinner animate-spin text-primary" style="font-size: 3rem; margin-bottom: 16px;"></i>
            <div class="font-bold text-main" style="word-break: break-all;">Processando ${nomeArquivo}...</div>
            <div class="text-xs text-muted mt-1">Aguarde, extraindo dados da planilha.</div>
        `;
        this.areaUpload.style.pointerEvents = 'none';
        
        // Dispara o envio do formulário
        this.formUpload.submit();
    }

    configurarBotoesExclusao() {
        this.botoesExcluir.forEach(botao => {
            botao.addEventListener('click', (evento) => {
                evento.preventDefault(); 
                
                const urlExclusao = botao.getAttribute('href');
                
                if (confirm('ATENÇÃO: Isso apagará permanentemente todos os voos vinculados a esta versão da malha.\nDeseja continuar?')) {
                    // Feedback visual no botão
                    botao.innerHTML = '<i class="ph-bold ph-spinner animate-spin text-lg"></i>';
                    botao.style.pointerEvents = 'none';
                    botao.classList.remove('text-danger');
                    botao.classList.add('text-muted');
                    
                    window.location.href = urlExclusao;
                }
            });
        });
    }

    configurarModalSubstituicao() {
        if (this.formSubstituicao) {
            this.formSubstituicao.addEventListener('submit', () => {
                const botaoConfirmar = document.getElementById('btn-confirmar-substituicao');
                if (botaoConfirmar) {
                    botaoConfirmar.innerHTML = '<i class="ph-bold ph-spinner animate-spin"></i> Atualizando Malha...';
                    botaoConfirmar.disabled = true;
                }
            });
        }
    }
}

// Instanciação Global
document.addEventListener('DOMContentLoaded', () => {
    const gerenciadorMalha = new GerenciadorMalha();
    gerenciadorMalha.inicializar();
});