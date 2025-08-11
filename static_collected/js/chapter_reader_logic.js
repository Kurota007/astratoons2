// manga/static/manga/js/chapter_reader_logic.js
document.addEventListener('DOMContentLoaded', function() {
    // --- Seletores para elementos do NOVO layout ---
    const readerContentWrapper = document.querySelector('.reader-image-items-container');

    // --- Seletores para elementos do TEMA ASTRAVERSE (seção 9) ---
    const prevChapterBottomBtn = document.getElementById('prev-chapter-bottom-btn');
    const nextChapterBottomBtn = document.getElementById('next-chapter-bottom-btn');
    const chapterSelectTop = document.getElementById('chapter-select-top');
    const chapterSelectBottom = document.getElementById('chapter-select-bottom');
    const fullscreenBtn = document.getElementById('fullscreen-btn');
    const zoomInBtn = document.getElementById('zoom-in-btn');
    const zoomOutBtn = document.getElementById('zoom-out-btn');
    const zoomResetBtn = document.getElementById('zoom-reset-btn');
    const loadingIndicator = document.querySelector('.loading-indicator-wrapper');
    // const scrollToTopButton = document.getElementById('scrollToTopBtn'); // Assumindo que está no base.html e seu JS global

    // --- URLs de Navegação (passadas por data attributes ou script inline no HTML) ---
    // Para passar dados do Django para um JS externo, a melhor forma é usar
    // data attributes no HTML ou um pequeno script inline que define variáveis globais.
    // Vamos assumir que o HTML terá um elemento para pegar esses dados.
    const readerDataElement = document.getElementById('reader-dynamic-data');
    const previousChapterUrl = readerDataElement ? readerDataElement.dataset.previousChapterUrl : "";
    const nextChapterUrl = readerDataElement ? readerDataElement.dataset.nextChapterUrl : "";


    // --- Funções Auxiliares ---
    function goToChapter(url) {
        if (url && url.trim() !== "" && url !== "#") {
            if(loadingIndicator) loadingIndicator.classList.remove('hidden'); // Mostra loading se existir
            window.location.href = url;
        }
    }

    function applyZoom(zoomLevel) {
        if (readerContentWrapper) { // Aplica zoom no container das imagens
            readerContentWrapper.style.transform = `scale(${zoomLevel})`;
            readerContentWrapper.style.transformOrigin = 'center top';
        }
    }

    // --- Lógica de Navegação de Capítulo ---
    if (prevChapterBottomBtn) {
        prevChapterBottomBtn.disabled = !previousChapterUrl;
        prevChapterBottomBtn.addEventListener('click', () => goToChapter(previousChapterUrl));
    }
    if (nextChapterBottomBtn) {
        nextChapterBottomBtn.disabled = !nextChapterUrl;
        nextChapterBottomBtn.addEventListener('click', () => goToChapter(nextChapterUrl));
    }

    if (chapterSelectTop) {
        chapterSelectTop.addEventListener('change', (e) => goToChapter(e.target.value));
    }
    if (chapterSelectBottom) {
        chapterSelectBottom.addEventListener('change', (e) => goToChapter(e.target.value));
    }

    // --- Lógica de Zoom ---
    let currentZoom = 1;
    const zoomStep = 0.1;
    const maxZoom = 2.5;
    const minZoom = 0.5;

    if (zoomInBtn) zoomInBtn.addEventListener('click', () => {
        if (currentZoom < maxZoom) { currentZoom = parseFloat((currentZoom + zoomStep).toFixed(2)); applyZoom(currentZoom); }
    });
    if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => {
        if (currentZoom > minZoom) { currentZoom = parseFloat((currentZoom - zoomStep).toFixed(2)); applyZoom(currentZoom); }
    });
    if (zoomResetBtn) zoomResetBtn.addEventListener('click', () => { currentZoom = 1; applyZoom(currentZoom); });

    // --- Tela Cheia ---
    if (fullscreenBtn) {
         fullscreenBtn.addEventListener('click', () => {
             if (!document.fullscreenElement) { document.documentElement.requestFullscreen().catch(console.error); }
             else { if (document.exitFullscreen) document.exitFullscreen(); }
         });
         document.addEventListener('fullscreenchange', () => {
            const isFullscreen = !!document.fullscreenElement;
            const icon = fullscreenBtn.querySelector('i');
            if (icon) {
                icon.className = isFullscreen ? 'fas fa-compress' : 'fas fa-expand';
            }
            fullscreenBtn.title = isFullscreen ? 'Sair da Tela Cheia' : 'Tela Cheia'; // Adapte com {% trans %} se necessário no HTML
         });
    }
    
    // --- Comentários (exemplo AJAX, adaptar ao seu sistema) ---
    const submitCommentBtn = document.getElementById('submit-comment-btn');
    const commentTextArea = document.getElementById('comment-text-area');
    if (submitCommentBtn && commentTextArea) {
        submitCommentBtn.addEventListener('click', function() {
            const commentText = commentTextArea.value.trim();
            if (commentText) {
                // Aqui iria a lógica AJAX para enviar o comentário
                console.log("Comentário a enviar:", commentText);
                // Exemplo:
                // const chapterId = readerDataElement ? readerDataElement.dataset.chapterId : null;
                // const csrfToken = readerDataElement ? readerDataElement.dataset.csrfToken : null;
                // if (chapterId && csrfToken) { ... fetch ... }
                alert("Comentário enviado (simulação)!");
                commentTextArea.value = "";
            } else {
                alert("Por favor, escreva um comentário.");
            }
        });
    }

    // Ocultar loading inicial se existir
    if(loadingIndicator) loadingIndicator.classList.add('hidden');
});