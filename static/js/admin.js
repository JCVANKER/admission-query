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
    loadAuditLogs(1);
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
        const file = fileInput.files[0];
        const fileName = file.name.toLowerCase();
        // xlsx 文件用 SheetJS 解析
        if (fileName.endsWith('.xlsx')) {
            try {
                const buffer = await file.arrayBuffer();
                const workbook = XLSX.read(buffer, { type: 'array' });
                const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                const rows = XLSX.utils.sheet_to_json(firstSheet, { header: 1 });
                // 提取所有行的第一列（姓名列），跳过空行
                const nameList = [];
                for (const row of rows) {
                    if (row && row.length > 0 && row[0]) {
                        const cellVal = String(row[0]).trim();
                        if (cellVal) nameList.push(cellVal);
                    }
                }
                rawText = nameList.join('\n');
            } catch (err) {
                msgEl.textContent = 'xlsx 文件解析失败，请检查格式';
                msgEl.className = 'upload-msg err';
                return;
            }
        } else {
            rawText = await file.text();
        }
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
            loadAuditLogs(1);
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
            loadAuditLogs(1);
        }
    } catch (err) { alert('删除失败，请重试'); }
}

async function doDelete(id) {
    if (!confirm('确定要删除这条记录吗？')) return;
    try {
        const resp = await fetch(`/api/admin/delete/${id}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) { loadList(currentPage); loadStats(); loadAuditLogs(1); }
    } catch (err) { alert('删除失败，请重试'); }
}

async function doClearAll() {
    if (!confirm('确定要清空全部录取名单吗？此操作不可恢复！')) return;
    try {
        const resp = await fetch('/api/admin/clear', { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) { loadList(1); loadStats(); loadAuditLogs(1); }
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
// 查询日志（颜色标记 + 确认状态）
// ═══════════════════════════════════════════

let logCurrentPage = 1;
let logSearchTerm = '';
let logSearchTimer = null;

async function loadLogs(page) {
    logCurrentPage = page;
    const tbody = document.getElementById('logTableBody');
    const colspan = 6;
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

        tbody.innerHTML = data.items.map(item => {
            // 行颜色：已录取绿色背景，未录取红色背景
            const rowClass = item.admitted ? 'log-row-admitted' : 'log-row-rejected';
            const hasNeeds = item.needs && item.needs.trim() !== '';
            const statusHtml = item.admitted
                ? `<span class="log-status admitted">✅ 已录取${hasNeeds ? ' (已提交需求)' : ''}</span>`
                : `<span class="log-status rejected">❌ 未录取</span>`;

            return `
                <tr class="${rowClass}">
                    <td><input type="checkbox" class="log-check" value="${item.id}"></td>
                    <td><strong>${escapeHtml(item.name)}</strong></td>
                    <td>${item.class_type === 'yucai' ? '育才班' : item.class_type === 'kete' ? '科特班' : '-'}</td>
                    <td>${statusHtml}</td>
                    <td>${hasNeeds ? item.needs.split(',').map(n => `<span class="confirmed-badge">${n}</span>`).join(' ') : '-'}</td>
                    <td>${item.created_at || '-'}</td>
                </tr>
            `;
        }).join('');

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
        if (data.success) { loadLogs(logCurrentPage); loadAuditLogs(1); }
    } catch (err) { alert('删除失败，请重试'); }
}

async function doClearAllLogs() {
    if (!confirm('确定要清空全部查询日志吗？此操作不可恢复！')) return;
    try {
        const resp = await fetch('/api/admin/logs/clear', { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) { loadLogs(1); loadAuditLogs(1); }
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
// 操作日志
// ═══════════════════════════════════════════

let auditLogPage = 1;

async function loadAuditLogs(page) {
    auditLogPage = page;
    const tbody = document.getElementById('auditLogTableBody');
    tbody.innerHTML = `<tr><td colspan="4" class="loading-cell">加载中...</td></tr>`;

    try {
        const params = new URLSearchParams({ page, per_page: 50 });
        const resp = await fetch(`/api/admin/audit-logs?${params.toString()}`);
        if (resp.status === 401) { window.location.href = '/admin'; return; }
        const data = await resp.json();

        if (!data.items.length) {
            tbody.innerHTML = `<tr><td colspan="4" class="loading-cell">暂无操作记录</td></tr>`;
            renderAuditLogPagination(0, page);
            return;
        }

        // 操作类型颜色映射
        const actionColors = {
            '上传录取名单': '#059669',
            '删除录取名单': '#dc2626',
            '批量删除录取名单': '#dc2626',
            '清空录取名单': '#dc2626',
            '批量删除查询日志': '#d97706',
            '清空查询日志': '#d97706',
        };

        tbody.innerHTML = data.items.map(item => {
            const color = actionColors[item.action] || '#6366f1';
            return `
                <tr>
                    <td><span style="display:inline-block;padding:2px 8px;border-radius:12px;font-size:0.78rem;font-weight:600;background:${color}15;color:${color};border:1px solid ${color}30;">${escapeHtml(item.action)}</span></td>
                    <td>${escapeHtml(item.target || '-')}</td>
                    <td>${escapeHtml(item.detail || '-')}</td>
                    <td style="color:var(--text-secondary);font-size:0.82rem;">${item.created_at || '-'}</td>
                </tr>
            `;
        }).join('');

        renderAuditLogPagination(data.total, page);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="4" class="loading-cell">加载失败，请刷新重试</td></tr>`;
    }
}

function renderAuditLogPagination(total, page) {
    const pagination = document.getElementById('auditLogPagination');
    const perPage = 50;
    const totalPages = Math.ceil(total / perPage);
    if (totalPages <= 1) {
        pagination.innerHTML = `<span class="page-info">共 ${total} 条</span>`;
        return;
    }
    let html = '';
    html += `<button class="page-btn" onclick="loadAuditLogs(1)" ${page === 1 ? 'disabled' : ''}>«</button>`;
    html += `<button class="page-btn" onclick="loadAuditLogs(${page - 1})" ${page === 1 ? 'disabled' : ''}>‹</button>`;
    const start = Math.max(1, page - 2);
    const end = Math.min(totalPages, page + 2);
    for (let i = start; i <= end; i++) {
        html += `<button class="page-btn${i === page ? ' active' : ''}" onclick="loadAuditLogs(${i})">${i}</button>`;
    }
    html += `<button class="page-btn" onclick="loadAuditLogs(${page + 1})" ${page === totalPages ? 'disabled' : ''}>›</button>`;
    html += `<button class="page-btn" onclick="loadAuditLogs(${totalPages})" ${page === totalPages ? 'disabled' : ''}>»</button>`;
    html += `<span class="page-info">共 ${total} 条</span>`;
    pagination.innerHTML = html;
}

async function doClearAllAuditLogs() {
    if (!confirm('确定要清空全部操作日志吗？此操作不可恢复！')) return;
    try {
        const resp = await fetch('/api/admin/audit-logs/clear', { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) loadAuditLogs(1);
    } catch (err) { alert('清空失败，请重试'); }
}

// ═══════════════════════════════════════════
// 统计概览
// ═══════════════════════════════════════════

async function loadStats() {
    try {
        const resp = await fetch('/api/admin/stats');
        if (resp.status === 401) return;
        const data = await resp.json();

        // 导航栏徽章
        document.getElementById('totalBadge').textContent = `总计: ${data.total} 人`;
        document.getElementById('keteBadge').textContent = `科特班: ${data.kete} 人`;
        document.getElementById('yucaiBadge').textContent = `育才班: ${data.yucai} 人`;

        // 统计卡片
        document.getElementById('statTotal').textContent = data.total;
        document.getElementById('statTodayQueries').textContent = data.today_queries;
        document.getElementById('statTotalQueries').textContent = data.total_queries;
        document.getElementById('statConfirmed').textContent = data.confirmed;
        document.getElementById('statRate').textContent = data.admission_rate + '%';
        document.getElementById('statTodayNew').textContent = data.today_new;
    } catch (err) { /* ignore */ }
}

// ═══════════════════════════════════════════
// 工具
// ═══════════════════════════════════════════

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
