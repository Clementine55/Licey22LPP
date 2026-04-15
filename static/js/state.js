// --- 1. STATE (Хранилище состояния) ---
const State = {
    repoId: null,
    currentPath: '/',
    pendingFile: null, // Объект {path, name}
    statusInterval: null
};