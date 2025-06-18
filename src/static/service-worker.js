const CACHE_NAME = 'lei-seca-v7'; // <<< ALTERAÇÃO AQUI >>> Mude o nome do cache para forçar a atualização!
const OFFLINE_URL = '/static/offline.html'; // <<< ALTERAÇÃO AQUI >>> Adicione a URL da sua página offline

const urlsToCache = [
    '/',
    '/auth/login',
    '/auth/signup',
    OFFLINE_URL, // <<< ALTERAÇÃO AQUI >>> Adicione a página offline ao cache
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
    '/static/logo_livro.webp',
    '/favicon.ico', // Certifique-se de que o favicon também é cacheado
    // Adicione outras URLs estáticas importantes que você queira cachear
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://cdn.quilljs.com/1.3.6/quill.snow.css',
    'https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-solid-900.woff2',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-regular-400.woff2',
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
                // Adiciona todas as URLs para cache, incluindo a página offline
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
            return self.clients.claim();
        })
    );
});

// Evento 'fetch': Intercepta requisições de rede
self.addEventListener('fetch', event => {
    // Ignorar requisições de API (JSON) e outros métodos que não sejam GET
    if (event.request.url.includes('/api/') || event.request.method !== 'GET') {
        return;
    }

    // <<< ALTERAÇÃO AQUI >>>
    event.respondWith(
        fetch(event.request) // Tenta buscar da rede primeiro (Network-first)
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
            .catch(() => {
                // Se a requisição de rede falhou (offline ou erro), tenta buscar do cache
                console.log(`[Service Worker] Rede falhou para: ${event.request.url}. Tentando cache...`);
                return caches.match(event.request)
                    .then(cachedResponse => {
                        if (cachedResponse) {
                            console.log(`[Service Worker] Servindo do cache: ${event.request.url}`);
                            return cachedResponse;
                        }
                        // Se não encontrou no cache, e não é uma requisição para a página offline, redireciona para a página offline
                        console.log(`[Service Worker] Sem cache para: ${event.request.url}. Redirecionando para offline.html`);
                        return caches.match(OFFLINE_URL);
                    });
            })
    );
    // <<< FIM DA ALTERAÇÃO >>>
});
