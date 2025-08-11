// static/js/manga_detail.js

document.addEventListener('DOMContentLoaded', function() {

    // ========================================
    // ===       LÓGICA DAS ABAS (TABS)     ===
    // ========================================
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    if (tabButtons.length > 0 && tabContents.length > 0) {
        // Função para mostrar a tab correta
        function showTab(tabId) {
            let foundTabContent = false;
            tabContents.forEach(content => {
                if (content.id === `tab-content-${tabId}`) {
                    content.classList.remove('hidden'); // Mostra o conteúdo da tab ativa
                    content.classList.add('active'); // Adiciona classe ativa (opcional, se o CSS usar)
                    foundTabContent = true;
                } else {
                    content.classList.add('hidden'); // Esconde as outras
                    content.classList.remove('active');
                }
            });

            // Fallback se a tabId não existir (mostra a primeira)
            if (!foundTabContent && tabContents.length > 0) {
                tabContents[0].classList.remove('hidden');
                tabContents[0].classList.add('active');
                // Ajusta qual botão fica ativo para o fallback
                tabId = tabButtons.length > 0 ? tabButtons[0].dataset.tab : '';
                console.warn(`Tab ID "${tabId}" não encontrada, mostrando a primeira tab.`);
            }

            // Atualiza a classe ativa nos botões das tabs
            tabButtons.forEach(button => {
                 if (button.dataset.tab === tabId) {
                     button.classList.add('active'); // Classe que o CSS usa para estilizar
                 } else {
                     button.classList.remove('active');
                 }
            });
             // Opcional: Salvar no localStorage
             // localStorage.setItem('activeMangaTab', tabId);
            // console.log(`Tab ativa: ${tabId}`);
        }

        // Adiciona o evento de clique para cada botão de tab
        tabButtons.forEach(button => {
            button.addEventListener('click', function(event) {
                event.preventDefault(); // Previne comportamento padrão
                const tabId = this.dataset.tab; // Pega o ID da tab do atributo data-tab
                showTab(tabId);
            });
        });

        // Determina a tab inicial a ser exibida
        let initialTab = 'chapters'; // Tab padrão
        // Verifica se a URL contém a âncora para os comentários
        if (window.location.hash === '#comments-section') {
            initialTab = 'comments';
        }
        // Poderia adicionar lógica para ler do localStorage aqui, se implementado
        // const savedTab = localStorage.getItem('activeMangaTab');
        // if (savedTab) { initialTab = savedTab; }

        // Mostra a tab inicial
        showTab(initialTab);

    } else {
        console.warn("Elementos das tabs (.tab-button ou .tab-content) não encontrados.");
    }

    // ========================================
    // ===     LÓGICA DE SPOILER (Comentários) ===
    // ========================================
    // Encontra todos os botões/spans de aviso de spoiler
    const spoilerWarnings = document.querySelectorAll('.spoiler-warning');
    spoilerWarnings.forEach(warning => {
        warning.style.cursor = 'pointer'; // Indica que é clicável
        warning.setAttribute('title', 'Clique para revelar/esconder spoiler'); // Tooltip
        warning.addEventListener('click', () => {
            const content = warning.nextElementSibling; // Pega o próximo elemento (o conteúdo)
            // Verifica se o próximo elemento existe e tem a classe correta
            if (content && content.classList.contains('spoiler-content')) {
                content.classList.toggle('hidden'); // Alterna a classe 'hidden'
            } else {
                 console.warn("Conteúdo do spoiler não encontrado após o aviso:", warning);
            }
        });
    });

    // ==============================================================
    // === PLACEHOLDERS PARA OUTRAS FUNCIONALIDADES (IMPLEMENTAR) ===
    // ==============================================================

    // --- Lógica do Botão Seguir/Favoritar (AJAX) ---
    const followBtn = document.getElementById('follow-manga-btn');
    if (followBtn) {
        // Adicionar o event listener que faz a chamada fetch para a API
        // Exemplo (precisa da API /api/manga/follow/ funcionando):
        /*
        followBtn.addEventListener('click', async function() {
            const mangaId = this.dataset.mangaId;
            const isCurrentlyFollowing = this.dataset.isFollowing === 'true';
            const icon = this.querySelector('i');
            const textSpan = this.querySelector('.follow-text');
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            const apiUrl = '/api/manga/follow/'; // SUBSTITUA PELA SUA URL REAL

            // UI Otimista (atualiza antes da resposta) - Mover para cá se preferir
            this.disabled = true;

            try {
                const response = await fetch(apiUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({ manga_id: mangaId })
                });
                const data = await response.json();

                if (response.ok && data.status === 'ok') {
                    // Atualiza estado e UI com base na resposta
                    this.dataset.isFollowing = data.is_following.toString();
                    if (data.is_following) {
                        icon.classList.remove('fa-bookmark'); // Ou fa-heart?
                        icon.classList.add('fa-bookmark');    // Ou fa-check?
                        textSpan.textContent = 'Seguindo';
                        this.classList.remove('button-primary'); // Ajuste classes se necessário
                        this.classList.add('button-success');
                    } else {
                        icon.classList.remove('fa-bookmark'); // Ou fa-check?
                        icon.classList.add('fa-bookmark');    // Ou fa-heart?
                        textSpan.textContent = 'Favoritar';
                         this.classList.remove('button-success');
                         this.classList.add('button-primary');
                    }
                    // Atualizar contagem de seguidores se existir elemento
                    const followersElem = document.querySelector('.followers-count-value'); // Adicione essa classe/id no HTML
                    if (followersElem && data.followers_count !== undefined) {
                         followersElem.textContent = data.followers_count;
                    }
                     console.log('Status de seguir atualizado:', data.action);
                } else {
                    console.error('Erro ao seguir:', data.message);
                    alert('Erro: ' + data.message);
                    // Reverter UI otimista (precisaria guardar estado anterior)
                }

            } catch (error) {
                console.error('Erro de rede ao seguir:', error);
                alert('Erro de rede ao tentar seguir.');
                 // Reverter UI otimista
            } finally {
                 this.disabled = false;
            }
        });
        */
        console.log("Botão Seguir/Favoritar encontrado.");
    }

    // --- Lógica do Botão Compartilhar ---
    const shareBtn = document.getElementById('share-manga-btn');
     if (shareBtn) {
         shareBtn.addEventListener('click', () => {
             const shareData = {
                 title: document.title, // Usa o título da página atual
                 text: `Confira "${document.querySelector('.page-title')?.textContent || 'esta obra'}" no Astraverse!`, // Tenta pegar o título do h1
                 url: window.location.href
             };
             if (navigator.share && navigator.canShare(shareData)) { // Verifica se pode compartilhar
                 navigator.share(shareData)
                   .then(() => console.log('Compartilhado com sucesso'))
                   .catch((error) => console.log('Erro ao compartilhar:', error));
             } else {
                 // Fallback: copiar link para clipboard
                 navigator.clipboard.writeText(window.location.href).then(() => {
                    // Talvez mostrar uma notificação customizada em vez de alert
                    alert('Link copiado para a área de transferência!');
                 }).catch(err => {
                    console.error('Erro ao copiar link: ', err);
                    alert('Não foi possível copiar o link.');
                 });
             }
         });
         console.log("Botão Compartilhar encontrado.");
     }

     // --- Lógica do Botão Notificar (NÃO FUNCIONAL) ---
     const notifyBtn = document.getElementById('notify-manga-btn');
     if(notifyBtn) {
         notifyBtn.addEventListener('click', () => {
             alert('Funcionalidade de notificação ainda não implementada.');
         });
         console.log("Botão Notificar encontrado.");
     }


    // --- Lógica Avançada de Comentários (AJAX para like/dislike, replies, load more) ---
    // Esta parte pode ficar aqui ou ser movida para static/js/comments.js
    // e incluída separadamente no base.html ou neste template.
    // O código para isso seria similar ao exemplo que dei anteriormente
    // envolvendo fetch API para interagir com o backend.

    // Exemplo: Função preparar resposta (precisa do <input type="hidden" id="id_parent"> no form)
    window.prepareReply = function(commentId) {
        const parentInput = document.getElementById('id_parent');
        const mainForm = document.getElementById('main-comment-form');
        const mainTextarea = mainForm ? mainForm.querySelector('textarea') : null;

        if (parentInput && mainTextarea) {
            parentInput.value = commentId;
            const commentAuthor = document.querySelector(`#comment-${commentId} .comment-author-name`)?.textContent || `Comentário #${commentId}`;
            mainTextarea.placeholder = `Respondendo a ${commentAuthor}...`;
            mainTextarea.focus();
            // Adicionar um botão/link "Cancelar Resposta" seria útil aqui
            console.log(`Preparando para responder ao comentário ${commentId}`);
        } else {
            console.error("Elementos do formulário de resposta não encontrados.");
        }
         // Prevenir comportamento padrão se chamado por evento onclick em um <a>
         if (window.event) { window.event.preventDefault(); }
    }

    console.log("JavaScript da página de detalhes do mangá (manga_detail.js) finalizado.");

}); // Fim do DOMContentLoaded