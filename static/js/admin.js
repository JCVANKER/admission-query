/**
 * 录取查询系统 - 管理后台 JS
 */

let currentPage = 1;
let searchTerm = '';
let searchTimer = null;
let uploadClassType = 'kete';

// ── 初始化 ──
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadList(1);
    loadLogs(1);
    initFileDrop();
});

// ── 班型选择 ──
function setUploadClassType(type) { uploadClassType = type; }

// ── 上传方式切换 ──
function switchUploadTab(tab) {
    document.querySelectorAll('.upload-tabs .tab-btn').forEach(b => b.classList.remove('active'));
    if (tab === 'text') {
        document.querySelector('.upload-tabs .tab-btn:nth-child(1)').classList.add('active');
    } else {
        document.querySelector('.upload-tabs .tab-btn:nth-child(2)').classList.add('active');
    }
    document.getElementById('upload-panel-text').style.display = tab === 'text' ? 'block' : 'none';
    document.getElementById('upload-panel-file').style.display = tab === 'file' ? 'block' : 'none';
}

// ═══════════════════════════════════════════
// 上传
// ═══════════════════════════════════════════

async function doUpload() {
    const msgEl = document.getElementById('uploadMsg');
    msgEl.textContent = '';
    msgEl.className = 'upload-msg';

    const isFileMode = document.getElementById('upload-panel-file').style.display !== 'none';
    let rawText = '';

    if (isFileMode) {
        const fileInput = document.getElementById('fileInput');
        if (!fileInput.files.length) {
            msgEl.textContent = '请先选择文件';
            msgEl.className = 'upload-msg err';
            return;
        }
        rawText = await fileInput.files[0].text();
    } else {
        rawText = document.getElementById('textInput').value.trim();
    }

    if (!rawText) {
        msgEl.textContent = '请输入名单内容';
        msgEl.className = 'upload-msg err';
        return;
    }

    const names = parseInput(rawText);
    if (!names.length) {
        msgEl.textContent = '未能解析到有效数据';
        msgEl.className = 'upload-msg err';
        return;
    }

    msgEl.textContent = `正在上传 ${names.length} 条记录...`;
    msgEl.className = 'upload-msg';

    try {
        const resp = await fetch('/api/admin/upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ names, class_type: uploadClassType })
        });
        const data = await resp.json();

        if (data.success) {
            msgEl.textContent = `✅ 成功导入 ${data.inserted} 条，跳过 ${data.skipped} 条重复`;
            msgEl.className = 'upload-msg ok';
            loadStats();
            loadList(1);
            document.getElementById('textInput').value = '';
            document.getElementById('fileInput').value = '';
        } else {
            msgEl.textContent = data.message || '上传失败';
            msgEl.className = 'upload-msg err';
        }
    } catch (err) {
        msgEl.textContent = '网络错误，请重试';
        msgEl.className = 'upload-msg err';
    }
}

function parseInput(text) {
    const lines = text.split('\n').filter(l => l.trim());
    const result = [];
    for (const line of lines) {
        const name = line.trim();
        if (name) result.push({ name, category: '' });
    }
    return result;
}

// ── 文件拖拽 ──
function initFileDrop() {
    const dropZone = document.getElementById('dropZone');
    if (!dropZone) return;
    const fileInput = document.getElementById('fileInput');
    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
        dropZone.querySelector('p').textContent = `📄 ${fileInput.files[0]?.name || '已选择文件'}`;
    });
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            dropZone.querySelector('p').textContent = `📄 ${e.dataTransfer.files[0].name}`;
        }
    });
}

// ═══════════════════════════════════════════
// 名单管理
// ═══════════════════════════════════════════

async function loadList(page) {
    currentPage = page;
    const tbody = document.getElementById('tableBody');
    const colspan = 5;
    tbody.innerHTML = `<tr><td colspan="${colspan}" class="loading-cell">加载中...</td></tr>`;

    try {
        const params = new URLSearchParams({ page, per_page: 50 });
        if (searchTerm) params.set('search', searchTerm);
        const classFilter = document.getElementById('listClassFilter').value;
        if (classFilter) params.set('class_type', classFilter);

        const resp = await fetch(`/api/admin/list?${params.toString()}`);
        if (resp.status === 401) { window.location.href = '/admin'; return; }
        const data = await resp.json();

        if (!data.items.length) {
            tbody.innerHTML = `<tr><td colspan="${colspan}" class="loading-cell">暂无数据</td></tr>`;
            renderPagination(0, page);
            return;
        }

        tbody.innerHTML = data.items.map(item => `
            <tr>
                <td><input type="checkbox" class="list-check" value="${item.id}"></td>
                <td><strong>${escapeHtml(item.name)}</strong></td>
                <td>${item.class_type === 'yucai' ? '育才班' : '科特班'}</td>
                <td>${item.created_at || '-'}</td>
                <td><button class="btn-delete" onclick="doDelete(${item.id})">删除</button></td>
            </tr>
        `).join('');

        renderPagination(data.total, page);
        document.getElementById('selectAll').checked = false;
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="${colspan}" class="loading-cell">加载失败，请刷新重试</td></tr>`;
    }
}

function toggleSelectAll() {
    const checked = document.getElementById('selectAll').checked;
    document.querySelectorAll('.list-check').forEach(cb => cb.checked = checked);
}

function getSelectedIds() {
    return [...document.querySelectorAll('.list-check:checked')].map(cb => parseInt(cb.value));
}

async function doBatchDelete() {
    const ids = getSelectedIds();
    if (!ids.length) { alert('请先勾选要删除的记录'); return; }
    if (!confirm(`确定要删除选中的 ${ids.length} 条记录吗？`)) return;

    try {
        const resp = await fetch('/api/admin/batch-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids })
        });
        const data = await resp.json();
        if (data.success) {
            loadList(currentPage);
            loadStats();
        }
    } catch (err) { alert('删除失败，请重试'); }
}

async function doDelete(id) {
    if (!confirm('确定要删除这条记录吗？')) return;
    try {
        const resp = await fetch(`/api/admin/delete/${id}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) { loadList(currentPage); loadStats(); }
    } catch (err) { alert('删除失败，请重试'); }
}

async function doClearAll() {
    if (!confirm('确定要清空全部录取名单吗？此操作不可恢复！')) return;
    try {
        const resp = await fetch('/api/admin/clear', { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) { loadList(1); loadStats(); }
    } catch (err) { alert('清空失败，请重试'); }
}

function renderPagination(total, page) {
    const pagination = document.getElementById('pagination');
    const perPage = 50;
    const totalPages = Math.ceil(total / perPage);
    if (totalPages <= 1) {
        pagination.innerHTML = `<span class="page-info">共 ${total} 条</span>`;
        return;
    }
    let html = '';
    html += `<button class="page-btn" onclick="loadList(1)" ${page === 1 ? 'disabled' : ''}>«</button>`;
    html += `<button class="page-btn" onclick="loadList(${page - 1})" ${page === 1 ? 'disabled' : ''}>‹</button>`;
    const start = Math.max(1, page - 2);
    const end = Math.min(totalPages, page + 2);
    for (let i = start; i <= end; i++) {
        html += `<button class="page-btn${i === page ? ' active' : ''}" onclick="loadList(${i})">${i}</button>`;
    }
    html += `<button class="page-btn" onclick="loadList(${page + 1})" ${page === totalPages ? 'disabled' : ''}>›</button>`;
    html += `<button class="page-btn" onclick="loadList(${totalPages})" ${page === totalPages ? 'disabled' : ''}>»</button>`;
    html += `<span class="page-info">共 ${total} 条</span>`;
    pagination.innerHTML = html;
}

function debounceSearch() {
    searchTerm = document.getElementById('searchInput').value.trim();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => loadList(1), 300);
}

// ═══════════════════════════════════════════
// 查询日志
// ═══════════════════════════════════════════

let logCurrentPage = 1;
let logSearchTerm = '';
let logSearchTimer = null;

async function loadLogs(page) {
    logCurrentPage = page;
    const tbody = document.getElementById('logTableBody');
    const colspan = 7;
    tbody.innerHTML = `<tr><td colspan="${colspan}" class="loading-cell">加载中...</td></tr>`;

    try {
        const params = new URLSearchParams({ page, per_page: 50 });
        if (logSearchTerm) params.set('search', logSearchTerm);
        const classFilter = document.getElementById('logClassFilter').value;
        if (classFilter) params.set('class_type', classFilter);

        const resp = await fetch(`/api/admin/logs?${params.toString()}`);
        if (resp.status === 401) { window.location.href = '/admin'; return; }
        const data = await resp.json();

        if (!data.items.length) {
            tbody.innerHTML = `<tr><td colspan="${colspan}" class="loading-cell">暂无数据</td></tr>`;
            renderLogPagination(0, page);
            return;
        }

        tbody.innerHTML = data.items.map(item => `
            <tr>
                <td><input type="checkbox" class="log-check" value="${item.id}"></td>
                <td><strong>${escapeHtml(item.name)}</strong></td>
                <td>${item.class_type === 'yucai' ? '育才班' : item.class_type === 'kete' ? '科特班' : '-'}</td>
                <td style="color:${item.admitted ? '#059669' : '#dc2626'};font-weight:600;">${item.admitted ? '✅ 已录取' : '❌ 未录取'}</td>
                <td>${item.schedule_date || '-'}</td>
                <td>${item.schedule_time || '-'}</td>
                <td>${item.created_at || '-'}</td>
            </tr>
        `).join('');

        renderLogPagination(data.total, page);
        document.getElementById('logSelectAll').checked = false;
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="${colspan}" class="loading-cell">加载失败，请刷新重试</td></tr>`;
    }
}

function toggleLogSelectAll() {
    const checked = document.getElementById('logSelectAll').checked;
    document.querySelectorAll('.log-check').forEach(cb => cb.checked = checked);
}

function getSelectedLogIds() {
    return [...document.querySelectorAll('.log-check:checked')].map(cb => parseInt(cb.value));
}

async function doBatchDeleteLogs() {
    const ids = getSelectedLogIds();
    if (!ids.length) { alert('请先勾选要删除的记录'); return; }
    if (!confirm(`确定要删除选中的 ${ids.length} 条日志吗？`)) return;

    try {
        const resp = await fetch('/api/admin/logs/batch-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids })
        });
        const data = await resp.json();
        if (data.success) loadLogs(logCurrentPage);
    } catch (err) { alert('删除失败，请重试'); }
}

async function doClearAllLogs() {
    if (!confirm('确定要清空全部查询日志吗？此操作不可恢复！')) return;
    try {
        const resp = await fetch('/api/admin/logs/clear', { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) loadLogs(1);
    } catch (err) { alert('清空失败，请重试'); }
}

function renderLogPagination(total, page) {
    const pagination = document.getElementById('logPagination');
    const perPage = 50;
    const totalPages = Math.ceil(total / perPage);
    if (totalPages <= 1) {
        pagination.innerHTML = `<span class="page-info">共 ${total} 条</span>`;
        return;
    }
    let html = '';
    html += `<button class="page-btn" onclick="loadLogs(1)" ${page === 1 ? 'disabled' : ''}>«</button>`;
    html += `<button class="page-btn" onclick="loadLogs(${page - 1})" ${page === 1 ? 'disabled' : ''}>‹</button>`;
    const start = Math.max(1, page - 2);
    const end = Math.min(totalPages, page + 2);
    for (let i = start; i <= end; i++) {
        html += `<button class="page-btn${i === page ? ' active' : ''}" onclick="loadLogs(${i})">${i}</button>`;
    }
    html += `<button class="page-btn" onclick="loadLogs(${page + 1})" ${page === totalPages ? 'disabled' : ''}>›</button>`;
    html += `<button class="page-btn" onclick="loadLogs(${totalPages})" ${page === totalPages ? 'disabled' : ''}>»</button>`;
    html += `<span class="page-info">共 ${total} 条</span>`;
    pagination.innerHTML = html;
}

function debounceLogSearch() {
    logSearchTerm = document.getElementById('logSearchInput').value.trim();
    clearTimeout(logSearchTimer);
    logSearchTimer = setTimeout(() => loadLogs(1), 300);
}

function doExportLogs() {
    window.location.href = '/api/admin/logs/export';
}

// ═══════════════════════════════════════════
// 工具
// ═══════════════════════════════════════════

async function loadStats() {
    try {
        const resp = await fetch('/api/admin/stats');
        const data = await resp.json();
        document.getElementById('totalBadge').textContent = `总计: ${data.total} 人`;
        document.getElementById('keteBadge').textContent = `科特班: ${data.kete} 人`;
        document.getElementById('yucaiBadge').textContent = `育才班: ${data.yucai} 人`;
    } catch (err) { /* ignore */ }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
