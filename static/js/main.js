// Função reutilizável para carregar HTML em um elemento
const loadHTMLComponent = (url, elementId) => {
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Erro ao carregar ${url}: ${response.statusText}`);
            }
            return response.text();
        })
        .then(html => {
            const element = document.getElementById(elementId);
            if (element) {
                element.innerHTML = html;
                console.log(`${elementId} carregado de ${url}`);

                // *** IMPORTANTE: Inicializar o dropdown DEPOIS que o navbar for carregado ***
                if (elementId === 'navbar-placeholder') {
                    initializeProfileDropdown();
                }

            } else {
                console.error(`Elemento com ID '${elementId}' não encontrado.`);
            }
        })
        .catch(error => {
            console.error(`Falha ao carregar componente de ${url}:`, error);
        });
};

// Função para inicializar o dropdown do perfil
function initializeProfileDropdown() {
    const profileTrigger = document.getElementById('profileDropdownTrigger');
    const dropdownMenu = document.getElementById('profileDropdownMenu');

    // Verifica se os elementos do dropdown existem
    if (profileTrigger && dropdownMenu) {
        console.log("Gatilho e menu do dropdown de perfil encontrados. Adicionando listeners.");

        profileTrigger.addEventListener('click', function(event) {
            event.stopPropagation(); // Impede que o clique no botão se propague para o document

            // Alterna a classe 'active' no menu para mostrar/esconder
            const isActive = dropdownMenu.classList.toggle('active'); // toggle retorna true se a classe foi adicionada, false se removida
            
            // Atualiza o atributo aria-expanded para acessibilidade
            profileTrigger.setAttribute('aria-expanded', isActive.toString());

            // Se o menu foi aberto, adiciona um listener para fechar ao clicar fora
            if (isActive) {
                // Fecha outros dropdowns (se você tiver mais algum no futuro)
                document.querySelectorAll('.dropdown-menu.active').forEach(openMenu => {
                    if (openMenu !== dropdownMenu) {
                        openMenu.classList.remove('active');
                        // Encontra o gatilho correspondente e atualiza o aria-expanded
                        const otherTriggerId = openMenu.id.replace('Menu', 'Trigger'); // Supõe um padrão de ID
                        const otherTrigger = document.getElementById(otherTriggerId);
                        if (otherTrigger) {
                            otherTrigger.setAttribute('aria-expanded', 'false');
                        }
                    }
                });

                // Adiciona listener para fechar ao clicar fora
                // É importante remover este listener quando o menu é fechado para não acumular listeners
                document.addEventListener('click', closeDropdownOnClickOutside, { once: true });
            }
        });

        // Impede que cliques dentro do menu fechem o menu (se o listener de click outside estiver no document)
        dropdownMenu.addEventListener('click', function(event) {
            event.stopPropagation();
        });

    } else {
        if (!profileTrigger) {
            console.error("Elemento #profileDropdownTrigger NÃO encontrado após carregar o navbar.");
        }
        if (!dropdownMenu) {
            console.error("Elemento #profileDropdownMenu NÃO encontrado após carregar o navbar.");
        }
    }
}

// Função para fechar o dropdown quando clicar fora
function closeDropdownOnClickOutside(event) {
    const profileTrigger = document.getElementById('profileDropdownTrigger');
    const dropdownMenu = document.getElementById('profileDropdownMenu');

    // Verifica se o clique foi fora do menu E fora do botão gatilho
    if (dropdownMenu && profileTrigger && 
        dropdownMenu.classList.contains('active') && 
        !dropdownMenu.contains(event.target) && 
        !profileTrigger.contains(event.target)) {
        
        dropdownMenu.classList.remove('active');
        profileTrigger.setAttribute('aria-expanded', 'false');
        // O listener já é { once: true }, então se auto-remove.
    }
}


// Executar o carregamento dos componentes HTML após o DOM estar pronto
document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM carregado, tentando carregar componentes HTML...");

    const navbarURL = 'includes/navbar.html'; // Certifique-se que este caminho está correto
    const footerURL = 'includes/footer.html'; // Certifique-se que este caminho está correto

    loadHTMLComponent(navbarURL, 'navbar-placeholder');
    loadHTMLComponent(footerURL, 'footer-placeholder');

    // Se o navbar NÃO for carregado dinamicamente, você pode chamar initializeProfileDropdown() aqui diretamente:
    // initializeProfileDropdown();
});
