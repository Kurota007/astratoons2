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

            } else {
                console.error(`Elemento com ID '${elementId}' não encontrado.`);
            }
        })
        .catch(error => {
            console.error(`Falha ao carregar componente de ${url}:`, error);
        });
};

// Executar o carregamento após o DOM estar pronto
document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM carregado, tentando carregar componentes...");

    // --- Caminhos para os componentes HTML ---
    // Ajuste estes caminhos conforme a localização REAL de navbar.html e footer.html
    // relativo ao ARQUIVO HTML QUE ESTÁ SENDO VISTO (ex: comics.html)
    // Assumindo que navbar/footer estão em 'templates/includes/' e
    // comics.html está em 'templates/', então o caminho é './includes/...' ou apenas 'includes/...'
    // Se comics.html está em templates/manga/ e includes está em templates/includes/, seria '../includes/...'

    // *** VERIFIQUE ESTES CAMINHOS CUIDADOSAMENTE ***
    const navbarURL = 'includes/navbar.html'; // Ajuste se necessário!
    const footerURL = 'includes/footer.html'; // Ajuste se necessário!

    loadHTMLComponent(navbarURL, 'navbar-placeholder');
    loadHTMLComponent(footerURL, 'footer-placeholder');
});