/**
 * Static/JS/Base.js
 * Configurações globais e interceptadores do sistema Luft-ConnectAir
 */

const fetchOriginal = window.fetch.bind(window);

// Interceptador global para injetar o cabeçalho exigido pelo @require_ajax
window.fetch = async function(recurso, configuracao = {}) {
    if (!configuracao.headers) {
        configuracao.headers = {};
    }

    if (configuracao.headers instanceof Headers) {
        configuracao.headers.append('X-Requested-With', 'XMLHttpRequest');
        if (!configuracao.headers.has('Accept')) {
            configuracao.headers.append('Accept', 'application/json');
        }
    } else {
        configuracao.headers['X-Requested-With'] = 'XMLHttpRequest';
        if (!configuracao.headers['Accept']) {
            configuracao.headers['Accept'] = 'application/json';
        }
    }

    return fetchOriginal(recurso, configuracao);
};

(function inicializarControleSessao() {
    const elementoConfiguracao = document.getElementById('luft-session-config');
    const configuracaoSessao = elementoConfiguracao ? JSON.parse(elementoConfiguracao.textContent || '{}') : null;
    if (!configuracaoSessao || !configuracaoSessao.keepaliveUrl || !configuracaoSessao.logoutUrl) {
        return;
    }

    const chaveAtividade = 'luft-connectair.ultima-atividade';
    const timeoutMs = Number(configuracaoSessao.timeoutMinutos || 30) * 60 * 1000;
    const keepaliveMs = Number(configuracaoSessao.keepaliveIntervaloSegundos || 240) * 1000;
    const intervaloVerificacaoMs = 60 * 1000;
    const throttleAtividadeMs = 15 * 1000;

    let ultimoRegistroLocal = 0;
    let ultimoKeepalive = 0;
    let keepaliveEmAndamento = false;
    let encerrandoSessao = false;

    function agora() {
        return Date.now();
    }

    function lerUltimaAtividade() {
        const valorSalvo = Number(window.localStorage.getItem(chaveAtividade));
        if (Number.isFinite(valorSalvo) && valorSalvo > 0) {
            return valorSalvo;
        }

        return ultimoRegistroLocal || agora();
    }

    function registrarAtividade(forcar = false) {
        const timestamp = agora();
        if (!forcar && timestamp - ultimoRegistroLocal < throttleAtividadeMs) {
            return;
        }

        ultimoRegistroLocal = timestamp;
        window.localStorage.setItem(chaveAtividade, String(timestamp));
    }

    function encerrarSessaoPorInatividade() {
        if (encerrandoSessao) {
            return;
        }

        encerrandoSessao = true;
        window.localStorage.removeItem(chaveAtividade);
        window.location.href = configuracaoSessao.logoutUrl;
    }

    async function enviarKeepalive() {
        if (keepaliveEmAndamento || document.visibilityState !== 'visible') {
            return;
        }

        const agoraMs = agora();
        const ultimaAtividade = lerUltimaAtividade();

        if (agoraMs - ultimaAtividade >= timeoutMs) {
            encerrarSessaoPorInatividade();
            return;
        }

        if (agoraMs - ultimoKeepalive < keepaliveMs) {
            return;
        }

        keepaliveEmAndamento = true;
        try {
            const resposta = await window.fetch(configuracaoSessao.keepaliveUrl, {
                method: 'POST',
                credentials: 'same-origin',
                cache: 'no-store'
            });

            if (!resposta.ok) {
                if (resposta.status === 401 || resposta.redirected) {
                    window.location.href = resposta.url || configuracaoSessao.logoutUrl;
                }
                return;
            }

            ultimoKeepalive = agoraMs;
        } catch (erro) {
            console.warn('Falha ao renovar a sessão automaticamente.', erro);
        } finally {
            keepaliveEmAndamento = false;
        }
    }

    function verificarInatividade() {
        if (agora() - lerUltimaAtividade() >= timeoutMs) {
            encerrarSessaoPorInatividade();
            return;
        }

        void enviarKeepalive();
    }

    const eventosAtividade = ['click', 'keydown', 'mousemove', 'scroll', 'touchstart', 'focus'];
    eventosAtividade.forEach((nomeEvento) => {
        window.addEventListener(nomeEvento, () => registrarAtividade(false), { passive: true });
    });

    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            registrarAtividade(true);
            void enviarKeepalive();
        }
    });

    window.addEventListener('storage', (evento) => {
        if (evento.key !== chaveAtividade) {
            return;
        }

        if (evento.newValue) {
            ultimoRegistroLocal = Number(evento.newValue) || ultimoRegistroLocal;
            return;
        }

        if (!document.hidden) {
            encerrarSessaoPorInatividade();
        }
    });

    registrarAtividade(true);
    ultimoKeepalive = agora();

    window.setInterval(verificarInatividade, intervaloVerificacaoMs);
    window.setInterval(() => {
        if (agora() - lerUltimaAtividade() < timeoutMs) {
            void enviarKeepalive();
        }
    }, keepaliveMs);
})();