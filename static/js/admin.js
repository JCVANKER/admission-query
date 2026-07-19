/**
 * 录取查询系统 - 管理后台 JS
 */

let currentPage = 1;
let searchTerm = '';
let searchTimer = null;

// ── 初始化 ──
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadList(1);
    initFileDrop();
});

// ── 标签切换 ──
function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelector(`.tab-btn:nth-child(${tab === 'text' ? 1 : tab === 'csv' ? 2 : 3})`).classList.add('active');
    document.getElementById(`panel-${tab}`).classList.add('active');
}

// ── 上传 ──
async function doUpload() {
    const activePanel = document.querySelector('.tab-panel.active');
    const panelId = activePanel.id;
    const msgEl = document.getElementById('uploadMsg');
    msgEl.textContent = '';
    msgEl.className = 'upload-msg';

    let rawText = '';

    if (panelId === 'panel-text') {
        rawText = document.getElementById('textInput').value.trim();
    } else if (panelId === 'panel-csv') {
        rawText = document.getElementById('csvInput').value.trim();
    } else if (panelId === 'panel-file') {
        const fileInput = document.getElementById('fileInput');
        if (!fileInput.files.length) {
            msgEl.textContent = '请先选择文件';
            msgEl.className = 'upload-msg err';
            return;
        }
        rawText = await fileInput.files[0].text();
    }

    if (!rawText) {
        msgEl.textContent = '请输入名单内容';
        msgEl.className = 'upload-msg err';
        return;
    }

    const names = parseInput(rawText, panelId === 'panel-csv');
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
            body: JSON.stringify({ names })
        });
        const data = await resp.json();

        if (data.success) {
            msgEl.textContent = `✅ 成功导入 ${data.inserted} 条，跳过 ${data.skipped} 条重复`;
            msgEl.className = 'upload-msg ok';
            loadStats();
            loadList(1);
            // 清空输入
            document.querySelectorAll('textarea').forEach(t => t.value = '');
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

function parseInput(text, isCsv) {
    const lines = text.split('\n').filter(l => l.trim());
    const result = [];

    if (isCsv) {
        // 跳过表头（第一行如果包含"姓名"）
        const start = lines[0] && lines[0].includes('姓名') ? 1 : 0;
        for (let i = start; i < lines.length; i++) {
            const parts = lines[i].split(',').map(s => s.trim());
            if (parts[0]) {
                result.push({
                    name: parts[0],
                    exam_number: parts[1] || '',
                    category: parts[2] || ''
                });
            }
        }
    } else {
        for (const line of lines) {
            const parts = line.split(/[,，\t]+/).map(s => s.trim());
            if (parts[0]) {
                result.push({
                    name: parts[0],
                    exam_number: parts[1] || '',
                    category: parts[2] || ''
                });
            }
        }
    }

    return result;
}

// ── 文件拖拽 ──
function initFileDrop() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');

    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
        dropZone.querySelector('p').textContent = `📄 ${fileInput.files[0]?.name || '已选择文件'}`;
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });
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

// ── 列表加载 ──
async function loadList(page) {
    currentPage = page;
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">加载中...</td></tr>';

    try {
        const params = new URLSearchParams({ page, per_page: 50 });
        if (searchTerm) params.set('search', searchTerm);

        const resp = await fetch(`/api/admin/list?${params.toString()}`);
        const data = await resp.json();

        if (!data.items.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">暂无数据</td></tr>';
            renderPagination(0, page);
            return;
        }

        tbody.innerHTML = data.items.map(item => `
            <tr>
                <td>${item.id}</td>
                <td><strong>${escapeHtml(item.name)}</strong></td>
                <td>${escapeHtml(item.exam_number) || '-'}</td>
                <td>${escapeHtml(item.category) || '-'}</td>
                <td>${item.created_at || '-'}</td>
                <td><button class="btn-delete" onclick="doDelete(${item.id})">删除</button></td>
            </tr>
        `).join('');

        renderPagination(data.total, page);
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">加载失败，请刷新重试</td></tr>';
    }
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

// ── 搜索（防抖） ──
function debounceSearch() {
    searchTerm = document.getElementById('searchInput').value.trim();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => loadList(1), 300);
}

// ── 删除 ──
async function doDelete(id) {
    if (!confirm('确定要删除这条记录吗？')) return;
    try {
        const resp = await fetch(`/api/admin/delete/${id}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) {
            loadList(currentPage);
            loadStats();
        }
    } catch (err) {
        alert('删除失败，请重试');
    }
}

// ── 清空 ──
async function doClearAll() {
    if (!confirm('确定要清空全部录取名单吗？此操作不可恢复！')) return;
    try {
        const resp = await fetch('/api/admin/clear', { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) {
            loadList(1);
            loadStats();
        }
    } catch (err) {
        alert('清空失败，请重试');
    }
}

// ── 统计 ──
async function loadStats() {
    try {
        const resp = await fetch('/api/admin/stats');
        const data = await resp.json();
        document.getElementById('totalBadge').textContent = `总计: ${data.total} 人`;
    } catch (err) { /* ignore */ }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
