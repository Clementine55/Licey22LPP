// --- 3. API (Взаимодействие с сервером) ---
const API = {
    base: '/api',
    
    request: async (endpoint, options = {}) => {
        const headers = { 'Content-Type': 'application/json' };
        if (Utils.getToken()) headers['x-token'] = Utils.getToken();
        
        const response = await fetch(`${API.base}${endpoint}`, { ...options, headers: {...headers, ...options.headers} });
        if (response.status === 401) { UI.handleLogout(); throw new Error("Unauthorized"); }
        
        // Если ожидаем бинарник (PDF)
        if (options.expectBlob) {
            if (!response.ok) throw new Error("Failed to fetch blob");
            return await response.blob();
        }
        
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Server error");
        return data;
    },

    login: (username, password) => API.request('/login', { method: 'POST', body: JSON.stringify({username, password}) }),
    getUser: () => API.request('/user'),
    getLibraries: () => API.request('/libraries'),
    getDirectory: (repoId, path) => API.request(`/directory?repo_id=${repoId}&path=${encodeURIComponent(path)}`),
    
    getPreviewBlob: (repoId, file, options) => {
        const query = `repo_id=${repoId}&file_path=${encodeURIComponent(file)}&orientation=${options.orientation}&margins=${options.margins}&scale=${options.scale}&pages=${encodeURIComponent(options.pages)}&paper_size=${options.paperSize}`;
        return API.request(`/preview?${query}`, { expectBlob: true });
    },

    submitPrintJob: async () => {
        UI.setPrintStatus('Обработка и печать... ⏳', 'var(--text-muted)');
        document.getElementById('btn-submit-print').disabled = true;

        localStorage.setItem('last_printer', document.getElementById('printer-select').value);

        const payload = {
            repo_id: State.repoId,
            file_path: State.pendingFile.path,
            printer_name: document.getElementById('printer-select').value,
            copies: parseInt(document.getElementById('print-copies').value) || 1,
            pages: document.getElementById('print-pages').value || 'all',
            orientation: document.getElementById('print-orientation').value,
            margins: document.getElementById('print-margins').value,
            paper_size: document.getElementById('print-paper-size').value,
            duplex: document.getElementById('print-duplex').value,
            scale: String(document.getElementById('print-scale-mode').value === 'custom' ? document.getElementById('print-scale-custom').value : document.getElementById('print-scale-mode').value)
        };

        try {
            await API.request('/print', { method: 'POST', body: JSON.stringify(payload) });
            
            // Прячем серый текст "Обработка и печать... ⏳"
            document.getElementById('print-status').classList.add('hidden'); 
            
            // Вызываем новое красивое окно
            UI.showSuccessModal(); 
            
            // Разблокируем кнопку на случай, если пользователь захочет распечатать еще раз
            document.getElementById('btn-submit-print').disabled = false;
        } catch (e) {
            UI.setPrintStatus(`❌ Ошибка: ${e.message}`, 'var(--danger)');
            document.getElementById('btn-submit-print').disabled = false;
        }
    },

    getPrinters: () => API.request('/printers'),
    getPrinterStatus: (name) => API.request(`/printer/${name}/status`),


};
