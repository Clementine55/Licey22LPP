// --- 4. UI (Управление интерфейсом) ---
const UI = {
    init: () => {
        // 1. Сначала вешаем обработчики на кнопки (один раз на всю жизнь приложения)
        const printBtn = document.getElementById('btn-submit-print');
        if (printBtn) {
            // Используем .onclick вместо .addEventListener — это гарантирует, 
            // что обработчик всегда будет только один.
            printBtn.onclick = API.submitPrintJob;
        }

        // 2. Дальше твоя стандартная логика авторизации
        if (Utils.getToken()) { 
            UI.showScreen('app-screen'); 
            UI.loadData(); 
        } else { 
            UI.showScreen('login-screen'); 
        }
    },

    showScreen: (id) => {
        document.getElementById('login-screen').classList.remove('flex'); document.getElementById('login-screen').classList.add('hidden');
        document.getElementById('app-screen').classList.remove('flex'); document.getElementById('app-screen').classList.add('hidden');
        document.getElementById(id).classList.remove('hidden'); document.getElementById(id).classList.add('flex');
    },

    handleLogin: async () => {
        const err = document.getElementById('login-error'); err.classList.add('hidden');
        try {
            const data = await API.login(document.getElementById('email').value, document.getElementById('password').value);
            Utils.setToken(data.token);
            UI.init();
        } catch (e) { err.innerText = e.message; err.classList.remove('hidden'); }
    },

    handleLogout: () => { 
        // 1. Очищаем локальные данные браузера
        Utils.clearToken(); 
        
        // 2. Убиваем сессию на сервере Authentik
        window.location.href = '/outpost.goauthentik.io/sign_out';
    },

    loadData: async () => {
        try {
            // Загрузка профиля
            const user = await API.getUser();
            document.getElementById('user-profile').classList.remove('hidden');
            document.getElementById('user-name').innerText = user.name;
            document.getElementById('user-avatar').innerHTML = user.avatar_url ? `<img src="${user.avatar_url}">` : user.name.charAt(0).toUpperCase();

            // Загрузка библиотек
            const data = await API.getLibraries();
            const list = document.getElementById('libraries'); 
            list.innerHTML = '';
            
            // 1. Группируем библиотеки по категориям
            const grouped = {};
            data.libraries.forEach(lib => {
                if (!grouped[lib.category]) grouped[lib.category] = [];
                grouped[lib.category].push(lib);
            });

            // 2. Отрисовываем группы на экране
            for (const [category, libs] of Object.entries(grouped)) {
                // Создаем заголовок группы (например: "Мои библиотеки" или "Тренинг 2026")
                const header = document.createElement('div');
                header.className = 'library-group-header';
                header.innerText = category;
                list.appendChild(header);

                // Добавляем сами папки под этот заголовок
                libs.forEach(lib => {
                    const div = document.createElement('div'); 
                    div.className = 'library-item'; 
                    div.innerHTML = `<span class="lib-icon">📚</span><span>${lib.name}</span>`;
                    
                    div.onclick = () => {
                        document.querySelectorAll('.library-item').forEach(el => el.classList.remove('active')); 
                        div.classList.add('active');
                        State.repoId = lib.id; State.currentPath = '/'; UI.loadDirectory();
                    };
                    list.appendChild(div);
                });
            }
        } catch (e) { console.error(e); }
    },

    loadDirectory: async () => {
        if (!State.repoId) return;
        document.getElementById('current-path').innerText = `Путь: ${State.currentPath}`;
        const fileList = document.getElementById('file-list'); fileList.innerHTML = '<p>Загрузка...</p>';

        try {
            const data = await API.getDirectory(State.repoId, State.currentPath);
            fileList.innerHTML = '';

            if (State.currentPath !== '/') {
                const backBtn = document.createElement('div'); backBtn.className = 'item-row';
                backBtn.innerHTML = `<div class="item-icon">⬅️</div><div class="item-details"><div class="item-name">Назад</div></div>`;
                backBtn.onclick = () => {
                    const parts = State.currentPath.split('/').filter(p => p); parts.pop();
                    State.currentPath = parts.length === 0 ? '/' : '/' + parts.join('/'); UI.loadDirectory();
                };
                fileList.appendChild(backBtn);
            }

            data.content.forEach(item => {
                const div = document.createElement('div'); div.className = 'item-row';
                if (item.type === 'dir') {
                    div.innerHTML = `<div class="item-icon">📁</div><div class="item-details"><div class="item-name">${item.name}</div></div>`;
                    div.onclick = () => { State.currentPath = State.currentPath === '/' ? `/${item.name}` : `${State.currentPath}/${item.name}`; UI.loadDirectory(); };
                } else {
                    const fullPath = State.currentPath === '/' ? `/${item.name}` : `${State.currentPath}/${item.name}`;
                    const conf = Utils.getFileConfig(item.name);
                    div.innerHTML = `
                        <div class="item-icon">${conf.icon}</div>
                        <div class="item-details"><div class="item-name" title="${item.name}">${item.name}</div><div class="item-meta">${item.size_kb} KB</div></div>
                        ${conf.print ? `<button class="print-btn" onclick="UI.openPrintModal('${item.name}', '${fullPath}')">🖨️ Печать</button>` : `<span style="font-size:12px;color:var(--text-muted);">Не поддерживается</span>`}
                    `;
                }
                fileList.appendChild(div);
            });
        } catch (e) { fileList.innerHTML = `<p style="color:var(--danger)">Ошибка загрузки</p>`; }
    },

    openPrintModal: async (name, path) => {
        document.getElementById('btn-submit-print').disabled = false;
        document.getElementById('print-status').innerText = ''; 
        
        // --- ВОТ ТЕ САМЫЕ ДВЕ СТРОЧКИ, КОТОРЫЕ МЫ ПОТЕРЯЛИ ---
        State.pendingFile = { name, path };
        document.getElementById('modal-filename').innerText = name;
        
        await UI.loadPrinters();
        
        // --- ЗАПУСКАЕМ ЖИВОЕ ОБНОВЛЕНИЕ СТАТУСА ---
        if (State.statusInterval) clearInterval(State.statusInterval);
        // Каждые 3 секунды дергаем статус в "тихом" режиме
        State.statusInterval = setInterval(() => UI.checkPrinterStatus(true), 3000);
        
        const ext = name.split('.').pop().toLowerCase();
        const isExcel = ['xls', 'xlsx', 'ods', 'csv'].includes(ext);
        
        const excelSettingsBlock = document.getElementById('excel-settings');
        if (isExcel) {
            excelSettingsBlock.classList.remove('hidden');
            // Для экселя по умолчанию альбомная
            document.getElementById('print-orientation').value = 'landscape';
        } else {
            excelSettingsBlock.classList.add('hidden');
            // Для ворда принудительно ставим стандартные параметры, чтобы они не ломали превью
            document.getElementById('print-orientation').value = 'portrait';
            document.getElementById('print-scale-mode').value = '100';
            document.getElementById('print-margins').value = 'normal';
        }

        document.getElementById('print-modal').classList.remove('hidden');
        UI.refreshPreview();
    },

    closePrintModal: () => {
        const overlay = document.getElementById('print-modal');
        overlay.classList.add('closing'); // Запускаем анимацию исчезновения
        
        // Ждем 200мс (время анимации), затем скрываем полностью
        setTimeout(() => {
            overlay.classList.remove('closing');
            overlay.classList.add('hidden');
        }, 200);
        
        // --- УБИВАЕМ ТАЙМЕР ПРИ ЗАКРЫТИИ ОКНА ---
        if (State.statusInterval) {
            clearInterval(State.statusInterval);
            State.statusInterval = null;
        }
    },

    showSuccessModal: () => {
        document.getElementById('success-modal').classList.remove('hidden');
    },

    closeSuccessModal: () => {
        const overlay = document.getElementById('success-modal');
        overlay.classList.add('closing'); // Запускаем анимацию улетания вверх
        
        setTimeout(() => {
            overlay.classList.remove('closing');
            overlay.classList.add('hidden');
            
            // Если окно печати еще открыто, закрываем и его тоже
            if (!document.getElementById('print-modal').classList.contains('hidden')) {
                UI.closePrintModal();
            }
        }, 200);
    },
    
    toggleCustomScale: () => {
        const mode = document.getElementById('print-scale-mode').value;
        const el = document.getElementById('print-scale-custom');
        mode === 'custom' ? el.classList.remove('hidden') : el.classList.add('hidden');
    },

    refreshPreview: async () => {
        // БЛОКИРУЕМ КНОПКУ ПЕЧАТИ НА ВРЕМЯ РЕНДЕРА
        const btnPrint = document.getElementById('btn-submit-print');
        if (btnPrint) btnPrint.disabled = true;

        document.getElementById('preview-loading').classList.remove('hidden');
        document.getElementById('preview-iframe').classList.add('hidden');

        const options = {
            orientation: document.getElementById('print-orientation').value,
            margins: document.getElementById('print-margins').value,
            paperSize: document.getElementById('print-paper-size').value, 
            pages: document.getElementById('print-pages').value,
            scale: document.getElementById('print-scale-mode').value === 'custom' ? document.getElementById('print-scale-custom').value : document.getElementById('print-scale-mode').value
        };

        try {
            const blob = await API.getPreviewBlob(State.repoId, State.pendingFile.path, options);
            const iframe = document.getElementById('preview-iframe');
            iframe.src = URL.createObjectURL(blob) + '#view=FitH&pagemode=none&navpanes=0';
            document.getElementById('preview-loading').classList.add('hidden');
            iframe.classList.remove('hidden');
            
            // РАЗБЛОКИРУЕМ КНОПКУ ТОЛЬКО ПОСЛЕ УСПЕШНОГО ПОЛУЧЕНИЯ PDF
            if (btnPrint) btnPrint.disabled = false;
        } catch (e) {
            document.getElementById('preview-loading').innerHTML = '<p style="color:var(--danger)">❌ Ошибка предпросмотра</p>';
        }
    },

    setPrintStatus: (text, color) => {
        const el = document.getElementById('print-status');
        el.innerText = text; el.style.color = color;
        el.classList.remove('hidden');
    },

    checkPrinterStatus: async (silent = false) => {
        const select = document.getElementById('printer-select');
        const statusEl = document.getElementById('printer-status');
        if (!select || !select.value) return;
        
        // Показываем часики только если пользователь сам сменил принтер руками
        if (!silent) statusEl.innerHTML = 'Проверка связи... ⏳';
        
        try {
            const data = await API.getPrinterStatus(select.value);
            statusEl.innerHTML = data.message;
        } catch (e) {
            statusEl.innerHTML = '🔴 Ошибка проверки статуса';
        }
    },

    loadPrinters: async () => {
        const select = document.getElementById('printer-select');
        select.innerHTML = '<option>Загрузка принтеров...</option>';
        try {
            const data = await API.getPrinters();
            select.innerHTML = ''; 
            
            if (!data.printers || data.printers.length === 0) {
                select.innerHTML = '<option disabled>Нет доступных принтеров</option>';
                document.getElementById('printer-status').innerText = '🔴 Принтеры не найдены';
                return;
            }
            
            // ДОСТАЕМ ПОСЛЕДНИЙ ПРИНТЕР ИЗ ПАМЯТИ
            const savedPrinter = localStorage.getItem('last_printer');

            data.printers.forEach(printer => {
                const opt = document.createElement('option');
                opt.value = printer;
                opt.innerText = printer;
                select.appendChild(opt);
            });

            // Если сохраненный принтер всё ещё существует в системе, выбираем его
            if (savedPrinter && data.printers.includes(savedPrinter)) {
                select.value = savedPrinter;
            }

            // Сразу проверяем статус выбранного принтера
            UI.checkPrinterStatus();

        } catch (e) {
            select.innerHTML = '<option disabled>Ошибка загрузки списка</option>';
        }
    },
};

// Запуск приложения
UI.init();
