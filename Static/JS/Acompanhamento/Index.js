/**
 * Index.js
 * Responsável pela lógica do Painel de Acompanhamento (Luft-ConnectAir)
 * Refatorado com Classes, camelCase e Rotas Injetadas
 */

class GerenciadorAcompanhamento {
    constructor() {
        this.mapa = null;
        this.camadaGeral = new L.LayerGroup(); 
        this.camadaFoco = new L.LayerGroup();  
        
        // Otimização: Renderizador Canvas para melhor performance em rotas complexas
        this.renderizadorCanvas = L.canvas({ padding: 0.5 });
    }

    inicializar() {
        this.inicializarMapa();
        this.carregarDados();
    }

    obterCorPorCia(texto) {
        if (!texto) return 'var(--luft-text-muted)';
        const termo = texto.toUpperCase().trim(); 
        if (termo.includes('LATAM') || termo.includes('TAM') || /^(LA|JJ)(\s|-|\d|$)/.test(termo)) return '#e30613';
        if (termo.includes('GOL') || /^(G3)(\s|-|\d|$)/.test(termo)) return '#ff7020';
        if (termo.includes('AZUL') || /^(AD)(\s|-|\d|$)/.test(termo)) return '#0d6efd';
        return '#64748b'; // Cor padrão (Slate)
    }

    inicializarMapa() {
        if (this.mapa) return;
        
        this.mapa = L.map('mapa-voos', { 
            zoomControl: false,
            renderer: this.renderizadorCanvas 
        }).setView([-14.2350, -51.9253], 4);

        L.control.zoom({ position: 'topright' }).addTo(this.mapa);
        
        // Mapa base (CartoDB Light)
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', { 
            attribution: '&copy; Luft-ConnectAir', 
            maxZoom: 18 
        }).addTo(this.mapa);

        this.camadaGeral.addTo(this.mapa);
        this.camadaFoco.addTo(this.mapa);
    }

    obterPontosCurva(latlng1, latlng2) {
        const lat1 = latlng1[0], lng1 = latlng1[1];
        const lat2 = latlng2[0], lng2 = latlng2[1];
        
        // Se for muito perto, desenha reta para economizar processamento
        if (Math.abs(lat1 - lat2) < 2 && Math.abs(lng1 - lng2) < 2) {
            return [latlng1, latlng2];
        }

        const offsetX = lng2 - lng1;
        const offsetY = lat2 - lat1;
        const raio = Math.sqrt(Math.pow(offsetX, 2) + Math.pow(offsetY, 2));
        const anguloTheta = Math.atan2(offsetY, offsetX);
        
        const compensacaoTheta = (3.14 / 10); 
        const raio2 = (raio / 2) / (Math.cos(compensacaoTheta));
        const theta2 = anguloTheta + compensacaoTheta;
        const meioX = (lng1 + lng2) / 2 + Math.cos(theta2) * raio2; 
        const meioY = (lat1 + lat2) / 2 + Math.sin(theta2) * raio2;
        
        // Gera 20 pontos interpolados para criar a curva suave
        const pontos = [];
        for (let i = 0; i <= 20; i++) {
            const t = i / 20;
            const lat = (1 - t) * (1 - t) * lat1 + 2 * (1 - t) * t * meioY + t * t * lat2;
            const lng = (1 - t) * (1 - t) * lng1 + 2 * (1 - t) * t * meioX + t * t * lng2;
            pontos.push([lat, lng]);
        }
        return pontos;
    }

    async carregarDados() {
        const inicio = document.getElementById('dataInicio').value;
        const fim = document.getElementById('dataFim').value;
        const awbBusca = document.getElementById('buscaAwb').value;
        const filialCtcBusca = document.getElementById('buscaFilialCtc').value;

        const corpoTabela = document.querySelector('#tabela-awbs tbody');

        corpoTabela.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:60px; color:var(--luft-text-muted);"><i class="ph-spinner ph-spin text-primary" style="font-size:28px;"></i><br><span style="margin-top:10px; display:block">Buscando cargas...</span></td></tr>`;
        
        this.resetarMapaVisual(); 

        let urlBusca = `${rotasAcompanhamento.listarAwbs}?dataInicio=${inicio}&dataFim=${fim}`;
        if (awbBusca) urlBusca += `&numeroAwb=${encodeURIComponent(awbBusca)}`;
        if (filialCtcBusca) urlBusca += `&filialCtc=${encodeURIComponent(filialCtcBusca)}`;

        try {
            const resposta = await fetch(urlBusca);
            const dados = await resposta.json();
            
            corpoTabela.innerHTML = '';
            document.getElementById('lbl-total').innerText = dados.length;

            if (dados.length === 0) {
                corpoTabela.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:40px; color:var(--luft-text-muted);">Nenhum registro encontrado.</td></tr>`;
                return;
            }

            dados.forEach(awb => {
                this.plotarRotaResumo(awb);
                const idLinha = `row-${awb.CodigoId}`;
                const corCia = this.obterCorPorCia(awb.CiaAerea);

                let classeCracha = 'luft-badge luft-badge-secondary';
                const status = awb.Status ? awb.Status.toUpperCase() : '';

                const statusSucesso = ['ENTREGUE', 'CARGA ENTREGUE'];
                const statusPerigo = ['RETIDA', 'ATRASADO', 'DELAY', 'CANCELADO'];
                const statusAviso = ['RECEPCAO DOCUMENTAL', 'LIBERADO PELA FISCALIZAÇÃO', 'EM PROCESSO DE LIBERAÇÃO FISCAL'];
                const statusInfo = ['CARGA ALOCADA', 'EMBARQUE CONFIRMADO', 'AGUARDANDO DESEMBARQUE', 'AGUARDANDO', 'CARGA DESEMBARCADA', 'EMBARQUE SURFACE', 'DESEMBARQUE VÔO', 'EMBARQUE VÔO'];

                if (statusSucesso.some(s => status.includes(s))) classeCracha = 'luft-badge luft-badge-success';
                else if (statusPerigo.some(s => status.includes(s))) classeCracha = 'luft-badge luft-badge-danger';
                else if (statusAviso.some(s => status.includes(s))) classeCracha = 'luft-badge luft-badge-warning';
                else if (statusInfo.some(s => status.includes(s))) classeCracha = 'luft-badge luft-badge-info';

                let htmlVoo = '<span style="color:var(--luft-text-muted);">-</span>';
                if (awb.Voo && awb.Voo.length > 2) {
                    htmlVoo = `<span class="voo-interativo" title="Duplo clique para detalhes do voo" 
                               ondblclick="abrirModalVoo('${awb.Voo}', '${awb.DataStatus}', event)">
                               <i class="ph-bold ph-airplane-tilt"></i> ${awb.Voo}</span>`;
                }

                const linhaPrincipal = document.createElement('tr');
                linhaPrincipal.className = 'row-main';
                linhaPrincipal.id = idLinha;
                linhaPrincipal.onclick = (evento) => { 
                    if (!evento.target.closest('.voo-interativo') && !evento.target.closest('td[ondblclick]')) {
                        this.alternarArvore(awb.Numero, idLinha); 
                    }
                };
                
                // Nota: O método AbrirModalAwbDetalhes é presumivelmente uma função global do _ModalAwb.html
                linhaPrincipal.innerHTML = `
                    <td style="text-align:center;">
                        <i class="ph-bold ph-caret-right transition-transform" id="icon-${idLinha}" style="color:var(--luft-text-muted);"></i>
                    </td>
                    <td style="font-weight:700; color:var(--luft-primary-600); font-family:monospace; cursor:pointer;"
                        title="Duplo clique para ver detalhes completos da Carga"
                        ondblclick="if(typeof AbrirModalAwbDetalhes !== 'undefined') AbrirModalAwbDetalhes('${awb.CodigoId}', event)">
                        ${awb.Numero}
                    </td>
                    <td><span style="font-weight:600; color:${corCia};">${awb.CiaAerea || 'INDEF'}</span></td>
                    <td><span style="font-weight:700;">${awb.Origem}</span> <i class="ph-bold ph-arrow-right" style="font-size:0.8rem; color:var(--luft-text-muted);"></i> <span style="font-weight:700;">${awb.Destino}</span></td>
                    <td>${htmlVoo}</td>
                    <td>${awb.Peso.toFixed(1)} kg</td>
                    <td><span class="${classeCracha}">${awb.Status}</span></td>
                    <td style="color:var(--luft-text-muted); font-size:0.8rem;">${awb.DataStatus}</td>
                `;

                const linhaDetalhe = document.createElement('tr');
                linhaDetalhe.id = `detail-${idLinha}`;
                linhaDetalhe.style.display = 'none';
                linhaDetalhe.innerHTML = `<td colspan="8" class="detail-cell"><div id="container-${idLinha}" style="min-height:100px; padding:20px;">Carregando...</div></td>`;
                
                corpoTabela.appendChild(linhaPrincipal);
                corpoTabela.appendChild(linhaDetalhe);
            });

        } catch (erro) {
            console.error("Erro ao carregar dados de acompanhamento:", erro);
            corpoTabela.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:40px; color:var(--luft-danger);">Erro ao buscar registros. Tente novamente.</td></tr>`;
        }
    }

    plotarRotaResumo(awb) {
        if (awb.RotaMap && awb.RotaMap.Origem) {
            const pontos = this.obterPontosCurva(awb.RotaMap.Origem, awb.RotaMap.Destino);
            
            const linha = L.polyline(pontos, { 
                color: this.obterCorPorCia(awb.CiaAerea), 
                weight: 1.5, 
                opacity: 0.5, 
                dashArray: '3, 6',
                renderer: this.renderizadorCanvas, 
                smoothFactor: 1 
            });
            linha.awbNumero = awb.Numero; 
            linha.addTo(this.camadaGeral);
        }
    }

    alternarArvore(numeroAwb, idLinha) {
        const linhaPrincipal = document.getElementById(idLinha);
        const linhaDetalhe = document.getElementById(`detail-${idLinha}`);
        const icone = document.getElementById(`icon-${idLinha}`);
        const containerDados = document.getElementById(`container-${idLinha}`);
        
        document.querySelectorAll('[id^="detail-"]').forEach(elemento => { if (elemento.id !== `detail-${idLinha}`) elemento.style.display = 'none'; });
        document.querySelectorAll('.row-main').forEach(elemento => { if (elemento.id !== idLinha) elemento.classList.remove('active'); });

        if (linhaDetalhe.style.display === 'none') {
            linhaPrincipal.classList.add('active');
            linhaDetalhe.style.display = 'table-row';
            icone.style.transform = 'rotate(90deg)';
            this.focarRotaNoMapa(numeroAwb);
            
            fetch(`${rotasAcompanhamento.historico}${encodeURIComponent(numeroAwb)}`)
                .then(resposta => resposta.json())
                .then(dadosRetorno => {
                    this.renderizarLinhaDoTempo(dadosRetorno, containerDados);
                    this.desenharRotaReal(dadosRetorno, numeroAwb);
                });
        } else {
            linhaPrincipal.classList.remove('active');
            linhaDetalhe.style.display = 'none';
            icone.style.transform = 'rotate(0deg)';
            this.resetarMapaVisual();
        }
    }

    renderizarLinhaDoTempo(dados, container) {
        const historico = dados.Historico || [];
        if (historico.length === 0) { 
            container.innerHTML = `<span class="text-muted">Sem histórico.</span>`; 
            return; 
        }

        let htmlTimeline = `<div class="timeline-container" style="padding: 20px 40px;">`;
        historico.forEach((registro, indice) => {
            let classeStatus = indice === 0 && !registro.Status.includes('ENTREGUE') ? 'active' : 'completed';
            
            let displayVoo = '';
            if (registro.Voo && registro.Voo.length > 2) {
                displayVoo = `<span class="voo-interativo" style="background:rgba(14, 165, 233, 0.1); color:var(--luft-info); padding:2px 8px; border-radius:4px;"
                              ondblclick="abrirModalVoo('${registro.Voo}', '${registro.Data}', event)">
                              <i class="ph-bold ph-airplane-tilt"></i> ${registro.Voo}</span>`;
            }

            htmlTimeline += `
                <div class="tl-item" style="display:flex; gap:20px; padding-bottom:20px; position:relative;">
                    <div style="position:absolute; left:7px; top:20px; bottom:0; width:2px; background:var(--luft-border);"></div>
                    <div style="width:16px; height:16px; border-radius:50%; background:${classeStatus === 'active' ? 'var(--luft-bg-panel)' : '#10b981'}; border:2px solid ${classeStatus === 'active' ? '#f59e0b' : '#10b981'}; z-index:2;"></div>
                    <div style="flex:1;">
                        <div style="font-weight:700; color:var(--luft-text-main);">${registro.Status}</div>
                        <div style="font-size:0.8rem; color:var(--luft-text-muted);">${registro.Data}</div>
                        <div style="margin-top:6px; font-size:0.8rem; display:flex; gap:12px;">
                            <span style="background:var(--luft-bg-app); color:var(--luft-text-main); padding:2px 8px; border-radius:4px;"><i class="ph-bold ph-map-pin"></i> ${registro.Local}</span>
                            ${displayVoo}
                        </div>
                    </div>
                </div>`;
        });
        htmlTimeline += `</div>`;
        container.innerHTML = htmlTimeline;
    }

    focarRotaNoMapa(numeroAwb) {
        this.camadaGeral.eachLayer(camada => camada.setStyle({ opacity: camada.awbNumero === numeroAwb ? 0 : 0.03 }));
        this.camadaFoco.clearLayers();
    }

    desenharRotaReal(dados, numeroAwb) {
        const trajetos = dados.TrajetoCompleto || [];
        const pendente = dados.RotaPendente;
        let limitesMapa = [];
        
        const iconePonto = (cor) => L.divIcon({ html: `<div style="background:${cor}; width:12px; height:12px; border:2px solid #fff; border-radius:50%; box-shadow:0 2px 4px rgba(0,0,0,0.3);"></div>`, className: '' });
        const iconeAviao = (cor) => L.divIcon({ html: `<div style="background:${cor}; width:26px; height:26px; display:flex; align-items:center; justify-content:center; border:2px solid #fff; border-radius:6px; box-shadow:0 2px 4px rgba(0,0,0,0.2);"><i class="ph-fill ph-airplane-tilt" style="color:#fff; font-size:16px;"></i></div>`, iconSize: [26, 26], className: '' });

        if (trajetos.length > 0) {
            L.marker(trajetos[0].CoordOrigem, { icon: iconePonto('#10b981') }).addTo(this.camadaFoco).bindPopup(`Origem: ${trajetos[0].Origem}`);
            limitesMapa.push(trajetos[0].CoordOrigem);

            trajetos.forEach((trecho, indice) => {
                const pontos = this.obterPontosCurva(trecho.CoordOrigem, trecho.CoordDestino);
                
                L.polyline(pontos, { 
                    color: this.obterCorPorCia(trecho.Voo), 
                    weight: 3, 
                    opacity: 0.9,
                    renderer: this.renderizadorCanvas,
                    lineCap: 'round'
                }).addTo(this.camadaFoco);
                
                if (indice === trajetos.length - 1) {
                    let iconeFim = pendente ? iconeAviao('#f59e0b') : iconeAviao('#10b981');
                    L.marker(trecho.CoordDestino, { icon: iconeFim }).addTo(this.camadaFoco);
                } else {
                    L.marker(trecho.CoordDestino, { icon: iconePonto('#64748b') }).addTo(this.camadaFoco);
                }
                limitesMapa.push(trecho.CoordDestino);
            });
        } else if (pendente) {
            L.marker(pendente.CoordOrigem, { icon: iconeAviao('#ef4444') }).addTo(this.camadaFoco);
            limitesMapa.push(pendente.CoordOrigem);
        }

        if (pendente) {
            const pontosPendentes = this.obterPontosCurva(pendente.CoordOrigem, pendente.CoordDestino);
            L.polyline(pontosPendentes, { 
                color: '#94a3b8', 
                weight: 2, 
                dashArray: '5, 8',
                opacity: 0.8,
                renderer: this.renderizadorCanvas 
            }).addTo(this.camadaFoco);
            
            L.marker(pendente.CoordDestino, { icon: iconePonto('#cbd5e1') }).addTo(this.camadaFoco);
            limitesMapa.push(pendente.CoordDestino);
        }

        if (limitesMapa.length > 0) this.mapa.fitBounds(limitesMapa, { padding: [80, 80] });
    }

    resetarMapaVisual() {
        this.camadaFoco.clearLayers();
        this.camadaGeral.eachLayer(camada => camada.setStyle({ opacity: 0.3 }));
        this.mapa.setView([-14.2350, -51.9253], 4);
    }

    async abrirModalVoo(numero, dataRef, evento) {
        if (evento) { evento.stopPropagation(); evento.preventDefault(); } 
        
        const modal = document.getElementById('modal-voo');
        modal.style.display = 'flex'; 
        
        document.getElementById('mv-numero').innerText = 'BUSCANDO...';
        
        const urlReq = `${rotasAcompanhamento.detalhesVoo}?numeroVoo=${numero}&dataRef=${dataRef}`;

        try {
            const resposta = await fetch(urlReq);
            const dadosRetorno = await resposta.json();

            if (dadosRetorno.sucesso) {
                const info = dadosRetorno.dados;
                document.getElementById('mv-cia').innerText = info.Cia;
                document.getElementById('mv-numero').innerText = `${info.Cia} ${info.Numero}`;
                document.getElementById('mv-origem').innerText = info.OrigemIata;
                document.getElementById('mv-origem-nome').innerText = info.OrigemNome;
                document.getElementById('mv-destino').innerText = info.DestinoIata;
                document.getElementById('mv-destino-nome').innerText = info.DestinoNome;
                document.getElementById('mv-data').innerText = info.Data;
                document.getElementById('mv-saida').innerText = info.HorarioSaida;
                document.getElementById('mv-chegada').innerText = info.HorarioChegada;

                const cabecalho = document.getElementById('mv-header');
                cabecalho.className = 'm-header'; 
                const siglaCia = info.Cia.toUpperCase();

                if (siglaCia.includes('LATAM') || siglaCia.includes('LA')) cabecalho.classList.add('mh-latam');
                else if (siglaCia.includes('GOL') || siglaCia.includes('G3')) cabecalho.classList.add('mh-gol');
                else if (siglaCia.includes('AZUL') || siglaCia.includes('AD')) cabecalho.classList.add('mh-azul');
                else cabecalho.classList.add('mh-default');

            } else {
                alert(dadosRetorno.msg || "Detalhes não encontrados.");
                this.fecharModalVoo();
            }
        } catch (erro) {
            console.error(erro);
            alert("Erro ao buscar detalhes do voo.");
            this.fecharModalVoo();
        }
    }

    fecharModalVoo() {
        document.getElementById('modal-voo').style.display = 'none';
    }
}

// Instanciação Global e Mapeamento de Funções para a Interface
let gerenciadorAcompanhamento;

document.addEventListener('DOMContentLoaded', () => { 
    gerenciadorAcompanhamento = new GerenciadorAcompanhamento();
    gerenciadorAcompanhamento.inicializar();

    // Expõe as funções para a UI que ainda utilizam eventos inline (onclick, ondblclick)
    window.carregarDados = () => gerenciadorAcompanhamento.carregarDados();
    window.abrirModalVoo = (numero, dataRef, evento) => gerenciadorAcompanhamento.abrirModalVoo(numero, dataRef, evento);
    window.fecharModalVoo = () => gerenciadorAcompanhamento.fecharModalVoo();
});