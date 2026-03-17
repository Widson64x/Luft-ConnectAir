/**
 * Manager.js
 * Lógica da tela de Gestão da Base de Cidades (Upload e Histórico)
 * Refatorado com Classes, camelCase e Injeção de Rotas
 */

class GerenciadorCidadesManager {
    constructor() {
        this.inputArquivo = document.getElementById('inputArquivoExcel');
        this.areaUpload = document.getElementById('area-upload');
        this.formUpload = document.getElementById('form-upload-cidades');
        this.formSubstituicao = document.getElementById('form-substituicao');
        this.botoesExcluir = document.querySelectorAll('.btn-excluir-base');
    }

    inicializar() {
        this.configurarArrastarESoltar();
        this.configurarEnvioArquivo();
        this.configurarBotoesExclusao();
        this.configurarModalSubstituicao();
    }

    configurarEnvioArquivo() {
        if (!this.inputArquivo || !this.areaUpload) return;

        this.areaUpload.addEventListener('click', () => this.inputArquivo.click());

        this.inputArquivo.addEventListener('change', (evento) => {
            if (evento.target.files.length > 0) {
                this.processarUpload(evento.target.files[0]);
            }
        });
    }

    configurarArrastarESoltar() {
        if (!this.areaUpload || !this.inputArquivo) return;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(nomeEvento => {
            this.areaUpload.addEventListener(nomeEvento, this.prevenirPadrao, false);
        });

        ['dragenter', 'dragover'].forEach(nomeEvento => {
            this.areaUpload.addEventListener(nomeEvento, () => {
                this.areaUpload.classList.add('drag-ativo');
            }, false);
        });

        ['dragleave', 'drop'].forEach(nomeEvento => {
            this.areaUpload.addEventListener(nomeEvento, () => {
                this.areaUpload.classList.remove('drag-ativo');
            }, false);
        });

        this.areaUpload.addEventListener('drop', (evento) => {
            const arquivos = evento.dataTransfer.files;
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
        
        if (!nomeArquivo.toLowerCase().endsWith('.xlsx')) {
            alert('Por favor, envie apenas arquivos do formato Excel (.xlsx).');
            this.inputArquivo.value = ''; 
            return;
        }

        this.areaUpload.innerHTML = `
            <i class="ph-bold ph-spinner ph-spin text-primary" style="font-size: 3rem; margin-bottom: 16px;"></i>
            <div class="font-bold text-main" style="word-break: break-all;">Processando ${nomeArquivo}...</div>
            <div class="text-xs text-muted mt-1">Aguarde, importando a base de municípios.</div>
        `;
        this.areaUpload.style.pointerEvents = 'none';
        
        this.formUpload.submit();
    }

    configurarBotoesExclusao() {
        this.botoesExcluir.forEach(botao => {
            botao.addEventListener('click', (evento) => {
                evento.preventDefault(); 
                
                const urlExclusao = botao.getAttribute('href');
                
                if (confirm('ATENÇÃO: Isso apagará toda a base de cidades atual.\nDeseja continuar?')) {
                    botao.innerHTML = '<i class="ph-bold ph-spinner ph-spin text-lg"></i>';
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
                    botaoConfirmar.innerHTML = '<i class="ph-bold ph-spinner ph-spin"></i> Atualizando...';
                    botaoConfirmar.disabled = true;
                }
            });
        }
    }
}

// Instanciação Global
document.addEventListener('DOMContentLoaded', () => {
    const gerenciadorCidades = new GerenciadorCidadesManager();
    gerenciadorCidades.inicializar();
});