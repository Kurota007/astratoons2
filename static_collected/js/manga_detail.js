// <script>  // Remova esta tag se estiver em um arquivo .js externo
document.addEventListener('DOMContentLoaded', function () {
    const followButton = document.getElementById('follow-manga-btn');
    const followersCountDisplay = document.getElementById('followers-count-display');
    // Tenta pegar o CSRF token de um input hidden ou de uma variável global do Django
    const csrfTokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
    const csrfToken = csrfTokenInput ? csrfTokenInput.value : '{{ csrf_token }}'; // Fallback para {{ csrf_token }} se não encontrar input

    if (followButton) {
        followButton.addEventListener('click', function () {
            const mangaId = this.dataset.mangaId;
            const apiUrl = this.dataset.apiUrl;
            const followTextElement = this.querySelector('.follow-text');
            const iconElement = this.querySelector('i');

            if (!apiUrl || !mangaId) { // CSRF Token é verificado no fetch, mas é bom ter aqui
                console.error("Faltando atributos data para API de favoritos (mangaId ou apiUrl).");
                alert('Erro ao tentar favoritar (configuração ausente no botão).');
                return;
            }
            if (!csrfToken || csrfToken === 'NOTPROVIDED') { // 'NOTPROVIDED' seria se {{ csrf_token }} não renderizasse
                console.error("CSRF Token não encontrado na página.");
                alert('Erro de segurança ao tentar favoritar. Recarregue a página.');
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
                body: JSON.stringify({ manga_id: mangaId }) // Envia manga_id como esperado pela sua view Python
            })
            .then(response => {
                if (!response.ok) {
                    // Tenta extrair mensagem de erro do JSON, senão mostra status
                    return response.json()
                      .then(errData => {
                          // Sua view retorna 'message' no erro, ou 'error' pode ser um fallback
                          throw new Error(errData.message || errData.error || `Erro HTTP: ${response.status}`);
                      })
                      .catch(() => { throw new Error(`Erro HTTP: ${response.status}`); }); // Fallback se não for JSON
                }
                return response.json();
            })
            .then(data => {
                // Sua view retorna 'action' ('added'/'removed') e 'is_favorited' e 'manga_id'
                // O JS original usava data.status, mas sua view usa data.action
                if (data.action === 'added') {
                    followTextElement.textContent = '{% trans "Seguindo" %}'; // Você precisará que o Django processe isso se o JS estiver em template
                                                                           // Se for JS externo, use texto literal: "Seguindo"
                    iconElement.classList.remove('far', 'not-following');
                    iconElement.classList.add('fas', 'following'); // Assumindo que 'following' é o estilo para coração preenchido
                    this.classList.remove('button-primary'); // Classes do seu tema
                    this.classList.add('button-secondary');
                    // Atualiza a contagem se o elemento existir e o dado for enviado
                    if (followersCountDisplay && data.count !== undefined) { // Seu backend não envia 'count' no JSON de sucesso
                        // Você precisaria ajustar o backend para enviar a nova contagem ou fazer outra requisição
                        // Por ora, vamos apenas supor que se adicionou, incrementa, se removeu, decrementa
                        let currentCount = parseInt(followersCountDisplay.textContent);
                        if (!isNaN(currentCount)) {
                            followersCountDisplay.textContent = currentCount + 1;
                        }
                    } else if (followersCountDisplay) { // Se o backend enviasse data.followers_count
                        // followersCountDisplay.textContent = data.followers_count;
                    }

                } else if (data.action === 'removed') {
                    followTextElement.textContent = '{% trans "Favoritar" %}'; // Ou "Favoritar"
                    iconElement.classList.remove('fas', 'following');
                    iconElement.classList.add('far', 'not-following');
                    this.classList.remove('button-secondary');
                    this.classList.add('button-primary');
                    if (followersCountDisplay && data.count !== undefined) {
                        followersCountDisplay.textContent = data.count;
                    } else if (followersCountDisplay) {
                        let currentCount = parseInt(followersCountDisplay.textContent);
                        if (!isNaN(currentCount) && currentCount > 0) {
                            followersCountDisplay.textContent = currentCount - 1;
                        }
                    }

                } else {
                    // O servidor pode retornar um erro específico na estrutura de dados de sucesso
                    // Sua view usa data.message para erros no JSON de status 200, mas isso é incomum.
                    // Geralmente erros vêm com status HTTP != 2xx.
                    console.error('Erro retornado pela API (inesperado na resposta de sucesso):', data.message || data.error || 'Status inesperado.');
                    alert(data.message || data.error || 'Ocorreu um erro ao processar a resposta.');
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
    const shareButton = document.getElementById('share-manga-btn'); // Seu HTML não tem botão com este ID
    if (shareButton) {
        shareButton.addEventListener('click', function() {
            const shareTitle = document.title; // Ou um título específico do mangá
            // Seu HTML tem {{ page.title }} que pode não estar disponível em um JS externo
            // Você precisaria passar o título do mangá para o JS, talvez via data-attribute no shareButton
            const shareText = this.dataset.shareText || `Confira este mangá: ${shareTitle}`;
            const shareUrl = this.dataset.shareUrl || window.location.href;

            if (navigator.share) {
                navigator.share({
                    title: shareTitle,
                    text: shareText,
                    url: shareUrl
                }).then(() => console.log('Conteúdo compartilhado com sucesso!'))
                  .catch((error) => console.error('Erro ao compartilhar:', error));
            } else {
                // Fallback para navegadores sem suporte (copiar link?)
                navigator.clipboard.writeText(shareUrl).then(() => {
                     alert('Link copiado para a área de transferência!');
                }).catch(err => {
                    console.error('Falha ao copiar link: ', err);
                    alert('Compartilhamento não suportado e falha ao copiar link.');
                });
            }
        });
    } // Fim if (shareButton)

    // Lógica para "Leia mais" da sinopse
    const synopsisContent = document.getElementById('synopsis-content'); // Seu HTML não tem sinopse com este ID
    const synopsisToggle = document.getElementById('synopsis-toggle');   // Seu HTML não tem botão com este ID
    if (synopsisContent && synopsisToggle) {
        const maxHeight = 100; // Altura máxima em pixels antes de cortar (ajuste conforme necessário)
        // let isClamped = false; // Estado inicial // Removido 'isClamped' pois não era usado efetivamente para controle de estado fora da função

        // Função para verificar e aplicar o clamp/botão
        function checkSynopsisHeight() {
            synopsisContent.style.maxHeight = 'none'; // Mede a altura real
            const scrollHeight = synopsisContent.scrollHeight;
            synopsisContent.style.maxHeight = ''; // Restaura

            if (scrollHeight > maxHeight + 20) { // +20 de margem
                synopsisToggle.classList.remove('hidden');
                if (!synopsisContent.classList.contains('expanded')) {
                     synopsisContent.classList.add('collapsed');
                     // Se for JS externo, use texto literal. Se for em template, {{% trans ... %}} é processado pelo Django.
                     synopsisToggle.textContent = 'Leia mais'; // '{% trans "Leia mais" %}';
                }
            } else {
                synopsisToggle.classList.add('hidden');
                synopsisContent.classList.remove('collapsed', 'expanded');
                synopsisContent.style.maxHeight = '';
                synopsisContent.style.overflow = '';
            }
        }

        checkSynopsisHeight();
        window.addEventListener('resize', checkSynopsisHeight);

        synopsisToggle.addEventListener('click', function() {
            if (synopsisContent.classList.contains('collapsed')) {
                synopsisContent.style.maxHeight = synopsisContent.scrollHeight + 'px';
                this.textContent = 'Leia menos'; // '{% trans "Leia menos" %}';
                synopsisContent.classList.remove('collapsed');
                synopsisContent.classList.add('expanded');
                setTimeout(() => {
                    if (synopsisContent.classList.contains('expanded')) {
                         synopsisContent.style.maxHeight = '';
                    }
                }, 400);
            } else {
                synopsisContent.style.maxHeight = maxHeight + 'px';
                this.textContent = 'Leia mais'; // '{% trans "Leia mais" %}';
                synopsisContent.classList.add('collapsed');
                synopsisContent.classList.remove('expanded');
            }
        });
    } // Fim if (synopsisContent && synopsisToggle)

}); // Fim DOMContentLoaded
// </script> // Remova esta tag se estiver em um arquivo .js externo