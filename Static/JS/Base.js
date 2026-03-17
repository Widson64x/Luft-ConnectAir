/**
 * Static/JS/Base.js
 * Configurações globais e interceptadores do sistema Luft-ConnectAir
 */

const fetchOriginal = window.fetch;

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