// static/js/comments.js
document.addEventListener('DOMContentLoaded', () => {

    // --- Lógica para preparar resposta ---
    // (Exposta globalmente ou encapsulada se preferir)
    window.prepareReply = function(commentId) {
        // Exemplo: Move o foco para o formulário principal e adiciona o ID do pai
        const parentInput = document.getElementById('id_parent'); // Precisa existir no form
        const mainForm = document.getElementById('main-comment-form'); // ID do seu form
        const mainTextarea = mainForm ? mainForm.querySelector('textarea') : null; // Achar a textarea

        if (parentInput && mainTextarea) {
            parentInput.value = commentId;
            mainTextarea.placeholder = `Respondendo ao comentário #${commentId}...`; // Atualiza placeholder
            mainTextarea.focus();
            // Adicionar botão/lógica para "Cancelar Resposta" que limpa parentInput.value e o placeholder
            console.log(`Preparando para responder ao comentário ${commentId}`);
        } else {
            console.error("Elementos do formulário de resposta não encontrados (parentInput ou mainTextarea).");
        }
        // Prevenir comportamento padrão só se chamado a partir de um evento (ex: onclick="prepareReply(..., event)")
        // if (event) {
        //     event.preventDefault();
        // }
    }

    // --- Lógica para Spoiler (Exemplo) ---
    const spoilerButtons = document.querySelectorAll('.spoiler-warning');
    spoilerButtons.forEach(button => {
        button.style.cursor = 'pointer'; // Indica que é clicável
        button.addEventListener('click', () => {
            const content = button.nextElementSibling; // Pega o <span> com o conteúdo
            if (content && content.classList.contains('spoiler-content')) {
                content.classList.toggle('hidden');
            }
        });
    });

    // --- Lógica para Like/Dislike (Exemplo com AJAX - PRECISA DE BACKEND) ---
    document.querySelectorAll('.like-btn, .dislike-btn').forEach(button => {
        button.addEventListener('click', async (event) => {
            event.preventDefault(); // Prevenir comportamento padrão
            const commentId = button.dataset.commentId; // Adicione data-comment-id="..." ao botão no HTML
            const action = button.classList.contains('like-btn') ? 'like' : 'dislike';
            const url = `/api/comments/${commentId}/vote/`; // SUA URL DA API AQUI!
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value; // Pega o token CSRF

            button.disabled = true; // Desabilita enquanto processa

            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({ action: action })
                });

                if (!response.ok) {
                    throw new Error(`Erro na API: ${response.statusText}`);
                }

                const data = await response.json();

                // Atualizar UI com base na resposta (data.likes, data.dislikes, data.user_vote)
                const likeCountSpan = button.closest('.flex').querySelector('.like-count'); // Ajuste seletores
                const dislikeCountSpan = button.closest('.flex').querySelector('.dislike-count'); // Ajuste seletores
                const likeIcon = button.closest('.flex').querySelector('.like-btn i');
                const dislikeIcon = button.closest('.flex').querySelector('.dislike-btn i');

                if (likeCountSpan) likeCountSpan.textContent = data.likes;
                if (dislikeCountSpan) dislikeCountSpan.textContent = data.dislikes;

                // Atualizar ícones baseado no voto do usuário (ex: data.user_vote pode ser 'like', 'dislike', ou null)
                if (likeIcon) {
                    likeIcon.classList.toggle('fas', data.user_vote === 'like');
                    likeIcon.classList.toggle('far', data.user_vote !== 'like');
                    likeIcon.classList.toggle('text-[#00B982]', data.user_vote === 'like');
                }
                 if (dislikeIcon) {
                    dislikeIcon.classList.toggle('fas', data.user_vote === 'dislike');
                    dislikeIcon.classList.toggle('far', data.user_vote !== 'dislike');
                    dislikeIcon.classList.toggle('text-red-500', data.user_vote === 'dislike'); // Ex: cor vermelha para dislike
                }


            } catch (error) {
                console.error("Erro ao votar:", error);
                alert("Ocorreu um erro ao tentar votar.");
                // Reverter UI se necessário (mais complexo)
            } finally {
                button.disabled = false; // Reabilita o botão
            }
        });
    });


    // --- Lógica para Carregar Mais Comentários (Exemplo com Fetch API) ---
    const loadMoreButton = document.getElementById('load-more-comments'); // Dê um ID ao botão no HTML
    const commentsContainer = document.getElementById('comments-container');
    let nextPageUrl = loadMoreButton ? loadMoreButton.dataset.nextPageUrl : null; // Adicione data-next-page-url="..." ao botão

    if (loadMoreButton && commentsContainer && nextPageUrl) {
        loadMoreButton.addEventListener('click', async () => {
            if (!nextPageUrl) return; // Sai se não houver próxima página

            loadMoreButton.disabled = true;
            loadMoreButton.textContent = 'Carregando...';

            try {
                const response = await fetch(nextPageUrl); // Faz a requisição GET para a próxima página
                if (!response.ok) throw new Error('Erro ao buscar mais comentários.');

                const html = await response.text(); // Pega o HTML retornado pela view

                // Processa o HTML para extrair APENAS os novos itens de comentário
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newComments = doc.querySelectorAll('#comments-container .comment-box'); // Seletor para os itens
                const newLoadMoreButtonData = doc.getElementById('load-more-comments'); // Pega dados do novo botão

                if (newComments.length > 0) {
                    newComments.forEach(comment => {
                        // Adiciona os novos comentários ao container existente
                        // IMPORTANTE: Isso pode re-adicionar listeners se não for cuidadoso.
                        // Uma abordagem melhor seria retornar JSON e construir o HTML no JS.
                        // Ou usar bibliotecas como HTMX que gerenciam isso.
                        // Para simplificar por agora, usamos innerHTML (mas CUIDADO):
                         commentsContainer.insertAdjacentHTML('beforeend', comment.outerHTML);
                    });
                     // Atualiza a URL da próxima página e reabilita o botão se houver mais
                    nextPageUrl = newLoadMoreButtonData ? newLoadMoreButtonData.dataset.nextPageUrl : null;
                    if (nextPageUrl) {
                        loadMoreButton.dataset.nextPageUrl = nextPageUrl;
                        loadMoreButton.disabled = false;
                        loadMoreButton.textContent = 'Carregar mais comentários';
                    } else {
                        loadMoreButton.remove(); // Remove o botão se não houver mais páginas
                    }
                } else {
                     loadMoreButton.remove(); // Remove se a resposta não contiver novos comentários
                }

            } catch (error) {
                console.error("Erro ao carregar mais comentários:", error);
                loadMoreButton.textContent = 'Erro ao carregar';
                // Poderia tentar reabilitar após um tempo
            }
        });
    }

    console.log("JavaScript dos comentários carregado.");

}); // Fim do DOMContentLoaded