// --- 2. UTILS (Вспомогательные функции) ---
const Utils = {
    getFileConfig: (name) => {
        const ext = name.split('.').pop().toLowerCase();
        const types = {
            'pdf': { icon: '📕', print: true },
            'doc': { icon: '📘', print: true }, 'docx': { icon: '📘', print: true }, 'rtf': { icon: '📘', print: true },
            'xls': { icon: '📗', print: true }, 'xlsx': { icon: '📗', print: true }, 'csv': { icon: '📗', print: true },
            'ppt': { icon: '📙', print: true }, 'pptx': { icon: '📙', print: true },
            'txt': { icon: '📝', print: true }, 'md': { icon: '📝', print: true },
            'jpg': { icon: '🖼️', print: true }, 'png': { icon: '🖼️', print: true },
            'zip': { icon: '📦', print: false }, 'rar': { icon: '📦', print: false },
            'mp3': { icon: '🎬', print: false }, 'mp4': { icon: '🎬', print: false }
        };
        return types[ext] || { icon: '📄', print: false };
    }
};