<script>
document.addEventListener('DOMContentLoaded', function () {
    const followButton = document.getElementById('follow-manga-btn');
    const followersCountDisplay = document.getElementById('followers-count-display');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '{{ csrf_token }}'; // Pega de um input ou do Django

    if (followButton) {
        followButton.addEventListener('click', function () {
            const mangaId = this.dataset.mangaId;
            const apiUrl = this.dataset.apiUrl;
            // const csrfToken = this.dataset.csrfToken; // Pode pegar daqui se preferir
            const followTextElement = this.querySelector('.follow-text');
            const iconElement = this.querySelector('i');

            if (!apiUrl || !mangaId || !csrfToken) {
                console.error("Faltando atributos data para API de favoritos.");
                alert('Erro ao tentar favoritar (configuração ausente).');
                return;
            }

            this.disabled = true;
            this.classList.add('loading'); // Adiciona classe de loading (estilize no CSS)

            fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ manga_id: mangaId })
            })
            .then(response => {
                if (!response.ok) {
                    // Tenta extrair mensagem de erro do JSON, senão mostra status
                    return response.json()
                      .then(errData => { throw new Error(errData.error || errData.message || `Erro HTTP: ${response.status}`); })
                      .catch(() => { throw new Error(`Erro HTTP: ${response.status}`); }); // Fallback se não for JSON
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'added') {
                    followTextElement.textContent = '{% trans "Seguindo" %}';
                    iconElement.classList.remove('far', 'not-following');
                    iconElement.classList.add('fas', 'following');
                    this.classList.remove('button-primary');
                    this.classList.add('button-secondary');
                    if (followersCountDisplay && data.count !== undefined) { followersCountDisplay.textContent = data.count; }
                } else if (data.status === 'removed') {
                    followTextElement.textContent = '{% trans "Favoritar" %}';
                    iconElement.classList.remove('fas', 'following');
                    iconElement.classList.add('far', 'not-following');
                    this.classList.remove('button-secondary');
                    this.classList.add('button-primary');
                    if (followersCountDisplay && data.count !== undefined) { followersCountDisplay.textContent = data.count; }
                } else {
                    // O servidor pode retornar um erro específico
                    console.error('Erro retornado pela API:', data.error || data.message || 'Status inesperado.');
                    alert(data.error || data.message || 'Ocorreu um erro.');
                }
            })
            .catch(error => {
                console.error('Erro na requisição Fetch:', error);
                alert(`Ocorreu um erro ao tentar favoritar: ${error.message}`);
            })
            .finally(() => {
                this.disabled = false;
                this.classList.remove('loading');
            });
        });
    } // Fim if (followButton)

    // Lógica do botão de compartilhar (usando API Web Share se disponível)
    const shareButton = document.getElementById('share-manga-btn');
    if (shareButton) {
        shareButton.addEventListener('click', function() {
            if (navigator.share) {
                navigator.share({
                    title: document.title,
                    text: 'Confira este mangá: {{ page.title }}', // Ajuste o texto se necessário
                    url: window.location.href
                }).then(() => console.log('Conteúdo compartilhado com sucesso!'))
                  .catch((error) => console.error('Erro ao compartilhar:', error));
            } else {
                // Fallback para navegadores sem suporte (copiar link?)
                navigator.clipboard.writeText(window.location.href).then(() => {
                     alert('Link copiado para a área de transferência!');
                }).catch(err => {
                    console.error('Falha ao copiar link: ', err);
                    alert('Compartilhamento não suportado e falha ao copiar link.');
                });
            }
        });
    } // Fim if (shareButton)

    // Lógica para "Leia mais" da sinopse
    const synopsisContent = document.getElementById('synopsis-content');
    const synopsisToggle = document.getElementById('synopsis-toggle');
    if (synopsisContent && synopsisToggle) {
        const maxHeight = 100; // Altura máxima em pixels antes de cortar (ajuste conforme necessário)
        let isClamped = false; // Estado inicial

        // Função para verificar e aplicar o clamp/botão
        function checkSynopsisHeight() {
            // Remove temporariamente a restrição para medir a altura real
            synopsisContent.style.maxHeight = 'none';
            const scrollHeight = synopsisContent.scrollHeight;
            synopsisContent.style.maxHeight = ''; // Restaura (importante!)

            // Só mostra o botão se o conteúdo for significativamente maior que o limite
            if (scrollHeight > maxHeight + 20) { // +20 de margem
                synopsisToggle.classList.remove('hidden'); // Mostra o botão
                // Aplica o clamp apenas se não estiver expandido
                if (!synopsisContent.classList.contains('expanded')) {
                     synopsisContent.classList.add('collapsed');
                     synopsisToggle.textContent = '{% trans "Leia mais" %}';
                     isClamped = true; // Atualiza estado
                }
            } else {
                // Esconde o botão se não precisar cortar
                synopsisToggle.classList.add('hidden');
                synopsisContent.classList.remove('collapsed'); // Remove classe se não precisar mais
                synopsisContent.style.maxHeight = ''; // Garante que não há limite
                synopsisContent.style.overflow = '';
                isClamped = false; // Atualiza estado
            }
        }

        // Verifica a altura ao carregar e ao redimensionar
        checkSynopsisHeight();
        window.addEventListener('resize', checkSynopsisHeight);

        // Ação do botão "Leia mais/menos"
        synopsisToggle.addEventListener('click', function() {
            if (synopsisContent.classList.contains('collapsed')) {
                // Expande
                synopsisContent.style.maxHeight = synopsisContent.scrollHeight + 'px'; // Define para altura total
                this.textContent = '{% trans "Leia menos" %}';
                synopsisContent.classList.remove('collapsed');
                synopsisContent.classList.add('expanded');
                isClamped = false;
                // Permite que a transição CSS ocorra
                // Depois da transição, remove max-height para o caso de redimensionamento
                setTimeout(() => {
                    if (synopsisContent.classList.contains('expanded')) { // Checa se ainda está expandido
                         synopsisContent.style.maxHeight = ''; // Remove max-height para permitir fluxo normal
                    }
                }, 400); // Tempo da transição + pequena margem
            } else {
                // Recolhe
                synopsisContent.style.maxHeight = maxHeight + 'px'; // Volta para altura clampada
                this.textContent = '{% trans "Leia mais" %}';
                synopsisContent.classList.add('collapsed');
                synopsisContent.classList.remove('expanded');
                isClamped = true;
            }
        });
    } // Fim if (synopsisContent && synopsisToggle)

}); // Fim DOMContentLoaded
</script>