
// --- FUNÇÃO DO MENU EXPANSÍVEL (Submenu) ---
function ToggleMenu(btn) {
    // Se a sidebar estiver colapsada, expandir ela primeiro para ver o submenu
    const sidebar = document.getElementById('sidebar');
    if(sidebar.classList.contains('collapsed')) {
        ToggleSidebar(); // Abre a sidebar
        // Pequeno delay para abrir o submenu suavemente
        setTimeout(() => {
            toggleSubmenuLogic(btn);
        }, 100);
    } else {
        toggleSubmenuLogic(btn);
    }
}

function toggleSubmenuLogic(btn) {
    btn.classList.toggle('ativo');
    const submenu = btn.nextElementSibling;
    submenu.classList.toggle('aberto');
}

// --- FUNÇÃO TOGGLE SIDEBAR ---
function ToggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('collapsed');
    
    // Salvar estado no localStorage
    const isCollapsed = sidebar.classList.contains('collapsed');
    localStorage.setItem('sidebar-collapsed', isCollapsed);
}

// --- TEMA E INICIALIZAÇÃO ---
function AlternarTema() {
    const html = document.documentElement;
    const novoTema = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', novoTema);
    localStorage.setItem('tema', novoTema);
    
    // Atualiza ícones em todos os botões de tema
    const icons = document.querySelectorAll('.action-btn i.ph-moon, .action-btn i.ph-sun');
    icons.forEach(icon => {
        if(novoTema === 'dark') {
            icon.classList.replace('ph-moon', 'ph-sun');
        } else {
            icon.classList.replace('ph-sun', 'ph-moon');
        }
    });
}

// Inicialização ao carregar a página
document.addEventListener("DOMContentLoaded", function() {
    // 1. Restaurar Tema
    const temaSalvo = localStorage.getItem('tema');
    if (temaSalvo) {
        document.documentElement.setAttribute('data-theme', temaSalvo);
        const icons = document.querySelectorAll('.action-btn i.ph-moon, .action-btn i.ph-sun');
        icons.forEach(icon => {
            if(temaSalvo === 'dark') icon.classList.replace('ph-moon', 'ph-sun');
        });
    }

    // 2. Restaurar Sidebar
    const sidebarSalva = localStorage.getItem('sidebar-collapsed');
    if (sidebarSalva === 'true') {
        document.getElementById('sidebar').classList.add('collapsed');
    }

    // 3. Alertas
    const alerts = document.querySelectorAll('.alert');
    if (alerts.length > 0) {
        setTimeout(() => {
            alerts.forEach(alert => {
                alert.style.transition = 'all 0.5s ease';
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-20px)';
                setTimeout(() => alert.remove(), 500);
            });
        }, 5000);
    }
});