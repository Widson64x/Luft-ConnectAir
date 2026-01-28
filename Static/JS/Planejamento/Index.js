let DADOS_ORIGINAIS = [];
let DADOS_VISIVEIS = [];
let VISTOS = new Set();
let ORDEM_ATUAL = { col: 'data_raw', dir: 'desc' }; 

const opts = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' };
document.getElementById('data-extenso').innerText = new Date().toLocaleDateString('pt-BR', opts);

// Função para receber datas de emissão dos CTCs, e descobrir o dd/mm/yyyy, para
// Colocar na variável data-extenso para ordenação correta.
function AtualizarDataExtenso(dataStr) {
    const partes = dataStr.split('/');
    const dataObj = new Date(Number(partes[2]), Number(partes[1]) - 1, Number(partes[0]));
    document.getElementById('data-extenso').innerText = dataObj.toLocaleDateString('pt-BR', opts);
}



BuscarDados();
setInterval(BuscarDados, 10000);

async function BuscarDados() {
    try {
        const resp = await fetch(URL_API_LISTAR);
        const dadosNovos = await resp.json();

        dadosNovos.forEach(d => {
            const partes = d.data_emissao.split('/');
            const horaLimpa = d.hora_emissao.replace(':', '');
            d.data_raw = Number(`${partes[2]}${partes[1]}${partes[0]}${horaLimpa}`);
            AtualizarDataExtenso(d.data_emissao);
            // Texto de busca expandido
            d.busca_texto = `${d.ctc} ${d.remetente} ${d.destinatario} ${d.origem} ${d.destino} ${d.filial} ${d.tipo_carga}`.toLowerCase();
        });

        if (DADOS_ORIGINAIS.length === 0) {
            PopularSelectFiliais(dadosNovos);
        }

        DADOS_ORIGINAIS = dadosNovos;
        FiltrarTabela();

    } catch (e) { console.error("Erro API:", e); }
}

function FiltrarTabela() {
    const termo = document.getElementById('input-busca').value.toLowerCase();
    const prio = document.getElementById('filtro-prioridade').value;
    const filial = document.getElementById('filtro-filial').value;

    DADOS_VISIVEIS = DADOS_ORIGINAIS.filter(item => {
        const matchTexto = item.busca_texto.includes(termo);
        const matchPrio = (prio === 'TODOS') || (item.prioridade === prio);
        const matchFilial = (filial === 'TODOS') || (item.filial === filial);
        return matchTexto && matchPrio && matchFilial;
    });

    AplicarOrdenacao();
    Renderizar();
    AtualizarKPIs();
}

function Ordenar(coluna) {
    if (ORDEM_ATUAL.col === coluna) {
        ORDEM_ATUAL.dir = ORDEM_ATUAL.dir === 'asc' ? 'desc' : 'asc';
    } else {
        ORDEM_ATUAL.col = coluna;
        ORDEM_ATUAL.dir = 'desc';
    }

    document.querySelectorAll('th').forEach(th => {
        th.classList.remove('sorted-asc', 'sorted-desc');
        if (th.getAttribute('onclick') && th.getAttribute('onclick').includes(coluna)) {
            th.classList.add(`sorted-${ORDEM_ATUAL.dir}`);
        }
    });

    FiltrarTabela();
}

function AplicarOrdenacao() {
    const col = ORDEM_ATUAL.col;
    const mult = ORDEM_ATUAL.dir === 'asc' ? 1 : -1;

    DADOS_VISIVEIS.sort((a, b) => {
        let valA = a[col];
        let valB = b[col];

        if (typeof valA === 'string') valA = valA.toLowerCase();
        if (typeof valB === 'string') valB = valB.toLowerCase();

        if (valA < valB) return -1 * mult;
        if (valA > valB) return 1 * mult;
        return 0;
    });
}

function Renderizar() {
    const tbody = document.getElementById('table-body');
    document.getElementById('contador-linhas').innerText = `${DADOS_VISIVEIS.length} registros`;

    if (DADOS_VISIVEIS.length === 0) {
        tbody.innerHTML = `<tr><td colspan="15"><div class="empty-state"><i class="ph-duotone ph-magnifying-glass"></i><span>Nenhum registro encontrado.</span></div></td></tr>`;
        return;
    }

    const html = DADOS_VISIVEIS.map(r => {
        const novo = !VISTOS.has(r.id_unico);
        if (novo) VISTOS.add(r.id_unico);
        const classeAnim = novo ? 'new-row' : '';
        
        const badgeClass = r.prioridade === 'URGENTE' ? 'prio-urgent' : 'prio-normal';
        const linkMontar = URL_BASE_MONTAR.replace('__F__', r.filial).replace('__S__', r.serie).replace('__C__', r.ctc);

        let htmlStatus = '<span class="badge-status status-pendente">Pendente</span>';
        let htmlAcao = `<a href="${linkMontar}" class="btn-plan" title="Criar Planejamento"><i class="ph-bold ph-airplane-takeoff"></i></a>`;

        if (r.tem_planejamento) {
            let clsStatus = 'status-em-plan';
            if (r.status_planejamento === 'Confirmado') clsStatus = 'status-ok';
            htmlStatus = `<span class="badge-status ${clsStatus}">${r.status_planejamento}</span>`;
            htmlAcao = `<a href="${linkMontar}" class="btn-plan btn-edit" title="Editar Planejamento"><i class="ph-bold ph-pencil-simple"></i></a>`;
        }

        return `
        <tr class="${classeAnim}">
            <td style="text-align:center;">
                <div style="display:flex; justify-content:center; gap:5px;">
                    ${htmlAcao}
                    <button class="btn-plan" onclick="AbrirModalGlobal('${r.filial}', '${r.serie}', '${r.ctc}')" title="Ver Documento"><i class="ph-bold ph-file-text"></i></button>
                </div>
            </td>
            <td style="text-align:center;">${htmlStatus}</td>
            <td style="text-align:center; font-weight: 600;">${r.filial}</td>
            <td class="col-ctc">${r.ctc}</td>
            
            <td style="font-weight: 500; color: #4b5563;">${r.tipo_carga || '-'}</td>
            
            <td>
                <div style="font-weight: 600;">${r.hora_emissao}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">${r.data_emissao.substring(0,5)}</div>
            </td>
            <td style="text-align:center;"><span class="badge-prio ${badgeClass}">${r.prioridade || 'NOR'}</span></td>
            <td style="text-align:center;">${r.status_ctc}</td>
            <td style="text-align:center; font-weight:600; color:#555;">${r.unid_lastmile}</td>
            <td>
                <div class="col-route">${r.origem} <i class="ph-bold ph-arrow-right"></i> ${r.destino}</div>
            </td>
            <td>
                <div style="font-size: 0.8rem; font-weight:600;">${r.remetente.substring(0,15)}...</div>
                <div style="font-size: 0.75rem; color:var(--text-muted);">${r.destinatario.substring(0,15)}...</div>
            </td>
            <td style="text-align:right;">${r.volumes}</td>
            <td style="text-align:right; font-weight:600;">${r.val_mercadoria}</td>
            <td style="text-align:right;">${r.peso_taxado.toLocaleString('pt-BR')} kg</td>
        </tr>
        `;
    }).join('');

    tbody.innerHTML = html;
}

function AtualizarKPIs() {
    const totalDocs = DADOS_VISIVEIS.length;
    const totalPeso = DADOS_VISIVEIS.reduce((acc, curr) => acc + (curr.peso_taxado || 0), 0);
    const totalFat = DADOS_VISIVEIS.reduce((acc, curr) => acc + (curr.raw_frete_total || 0), 0);

    document.getElementById('kpi-docs').innerText = totalDocs;
    document.getElementById('kpi-peso').innerText = totalPeso.toLocaleString('pt-BR', {maximumFractionDigits:0}) + ' kg';
    document.getElementById('kpi-fat').innerText = totalFat.toLocaleString('pt-BR', {style:'currency', currency:'BRL'});
}

function PopularSelectFiliais(dados) {
    const filiais = [...new Set(dados.map(d => d.filial))].sort();
    const select = document.getElementById('filtro-filial');
    while (select.options.length > 1) { select.remove(1); }
    filiais.forEach(f => {
        const opt = document.createElement('option');
        opt.value = f; opt.innerText = `Filial ${f}`;
        select.appendChild(opt);
    });
}