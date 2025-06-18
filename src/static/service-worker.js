const CACHE_NAME = 'lei-seca-v1'; // Nome do cache, mude-o a cada nova versão para forçar atualização
const urlsToCache = [
    '/',
    '/auth/login',
    '/auth/signup',
    '/static/css/output.css',
    '/static/manifest.json',
    '/static/icons/icon-72x72.png',
    '/static/icons/icon-96x96.png',
    '/static/icons/icon-128x128.png',
    '/static/icons/icon-144x144.png',
    '/static/icons/icon-152x152.png',
    '/static/icons/icon-192x192.png',
    '/static/icons/icon-384x384.png',
    '/static/icons/icon-512x512.png',
    '/static/logo_livro.webp', // Sua logo para o cabeçalho
    // Adicione outras URLs estáticas importantes que você queira cachear
    // Por exemplo, fontes do Google Fonts, Font Awesome CSS (se não for carregado via CDN com versionamento)
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://cdn.quilljs.com/1.3.6/quill.snow.css',
    'https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-solid-900.woff2', // Exemplo de fonte do Font Awesome
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-regular-400.woff2',
    // Adicione as URLs dos seus áudios se quiser que funcionem offline (considere o tamanho)
    'https://audios-estudoleieca.s3.us-west-2.amazonaws.com/alpha_wave.mp3',
    'https://audios-estudoleieca.s3.us-west-2.amazonaws.com/beta_wave.mp3',
    'https://audios-estudoleieca.s3.us-west-2.amazonaws.com/theta_wave.mp3',
    'https://audios-estudoleieca.s3.us-west-2.amazonaws.com/classical_music.mp3',
    'https://audios-estudoleieca.s3.us-west-2.amazonaws.com/white_noise.mp3'
];

// Evento 'install': Quando o Service Worker é instalado
self.addEventListener('install', event => {
    console.log('[Service Worker] Instalando Service Worker...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[Service Worker] Cacheando arquivos essenciais.');
                return cache.addAll(urlsToCache);
            })
            .catch(error => {
                console.error('[Service Worker] Falha ao cachear durante a instalação:', error);
            })
    );
});

// Evento 'activate': Quando o Service Worker é ativado
self.addEventListener('activate', event => {
    console.log('[Service Worker] Ativando Service Worker...');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log(`[Service Worker] Deletando cache antigo: ${cacheName}`);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
            console.log('[Service Worker] Cache antigo limpo. Service Worker ativado.');
            return self.clients.claim(); // Garante que o Service Worker assume o controle da página imediatamente
        })
    );
});

// Evento 'fetch': Intercepta requisições de rede
self.addEventListener('fetch', event => {
    // Ignorar requisições de API para garantir que o conteúdo dinâmico esteja sempre atualizado
    if (event.request.url.includes('/api/') || event.request.method !== 'GET') {
        return;
    }

    event.respondWith(
        caches.match(event.request)
            .then(response => {
                // Cache hit - retorna a resposta do cache
                if (response) {
                    console.log(`[Service Worker] Servindo do cache: ${event.request.url}`);
                    return response;
                }

                // Cache miss - tenta buscar da rede
                console.log(`[Service Worker] Buscando da rede: ${event.request.url}`);
                return fetch(event.request)
                    .then(networkResponse => {
                        // Se a requisição foi bem-sucedida, clona a resposta e a adiciona ao cache
                        if (networkResponse.ok) {
                            const responseToCache = networkResponse.clone();
                            caches.open(CACHE_NAME).then(cache => {
                                cache.put(event.request, responseToCache);
                            });
                        }
                        return networkResponse;
                    })
                    .catch(error => {
                        console.error(`[Service Worker] Falha na requisição e sem cache para: ${event.request.url}`, error);
                        // Você pode retornar uma página offline aqui se desejar
                        // return caches.match('/offline.html'); 
                    });
            })
    );
});