/**
 * 录取查询系统 - 管理后台 JS v2
 * 新增：Toast 通知系统、移动端卡片视图、班型卡片选择器
 */

let currentPage = 1;
let searchTerm = '';
let searchTimer = null;
let uploadClassType = 'kete';

// ── 初始化 ──
document.addEventListener('DOMContentLoaded', () => {
    initToast();
    loadStats();
    loadList(1);
    loadLogs(1);
    loadAuditLogs(1);
    initFileDrop();
    // 移动端自动启用卡片视图
    if (window.innerWidth < 768) {
        enableCardView();
    }
});

// ── 窗口大小变化时切换表格视图 ──
window.addEventListener('resize', () => {
    if (window.innerWidth < 768) {
        enableCardView();
    } else {
        disableCardView();
    }
});

function enableCardView() {
    document.querySelectorAll('.table-wrapper').forEach(w => w.classList.add('card-view'));
}
function disableCardView() {
    document.querySelectorAll('.table-wrapper').forEach(w => w.classList.remove('card-view'));
}

// ═══════════════════════════════════════════
// Toast 通知系统（替代 alert）
// ═══════════════════════════════════════════

let toastIdCounter = 0;

function initToast() {
    if (!document.getElementById('toastContainer')) {
        const container = document.createElement('div');
        container.className = 'toast-container';
        container.id = 'toastContainer';
        document.body.appendChild(container);
    }
}

function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };

    const id = 'toast-' + (++toastIdCounter);
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.id = id;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <span class="toast-msg">${escapeHtml(message)}</span>
        <button class="toast-close" onclick="dismissToast('${id}')">&times;</button>
    `;
    container.appendChild(toast);

    if (duration > 0) {
        setTimeout(() => dismissToast(id), duration);
    }
}

function dismissToast(id) {
    const toast = document.getElementById(id);
    if (!toast) return;
    toast.classList.add('toast-out');
    setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 300);
}

// ── 确认对话框（使用原生 confirm，但可扩展为自定义弹窗） ──
function showConfirm(message, onConfirm, onCancel) {
    if (confirm(message)) {
        if (onConfirm) onConfirm();
    } else {
        if (onCancel) onCancel();
    }
}

// ── 班型选择（卡片式） ──
function setUploadClassType(type) {
    uploadClassType = type;
    document.querySelectorAll('.class-type-card').forEach(c => c.classList.remove('active'));
    const card = type === 'yucai' ? document.getElementById('classCardYucai') : document.getElementById('classCardKete');
    if (card) card.classList.add('active');
}

// ── 上传方式切换 ──
function switchUploadTab(tab) {
    document.querySelectorAll('.upload-tabs .tab-btn').forEach(b => {
        if (!b.classList.contains('tab-download')) {
            b.classList.remove('active');
        }
    });
    const btns = document.querySelectorAll('.upload-tabs .tab-btn:not(.tab-download)');
    if (tab === 'text' && btns[0]) btns[0].classList.add('active');
    if (tab === 'file' && btns[1]) btns[1].classList.add('active');
    document.getElementById('upload-panel-text').style.display = tab === 'text' ? 'block' : 'none';
    document.getElementById('upload-panel-file').style.display = tab === 'file' ? 'block' : 'none';
}

// ═══════════════════════════════════════════
// 上传
// ═══════════════════════════════════════════

let _pendingNames = null;

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
            showToast('请先选择要上传的文件', 'warning');
            return;
        }
        const file = fileInput.files[0];
        const fileName = file.name.toLowerCase();
        if (fileName.endsWith('.xlsx')) {
            try {
                const buffer = await file.arrayBuffer();
                const workbook = XLSX.read(buffer, { type: 'array' });
                const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                const rows = XLSX.utils.sheet_to_json(firstSheet, { header: 1 });
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
                showToast('xlsx 文件解析失败', 'error');
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
        showToast('请输入名单内容', 'warning');
        return;
    }

    const names = parseInput(rawText);
    if (!names.length) {
        msgEl.textContent = '未能解析到有效数据';
        msgEl.className = 'upload-msg err';
        showToast('未能解析到有效数据', 'error');
        return;
    }

    _pendingNames = names;
    showPreviewModal(names);
}

function showPreviewModal(names) {
    const classTypeName = uploadClassType === 'yucai' ? '育才班' : '科特班';

    const previewItems = names.slice(0, 20);
    const moreCount = names.length - previewItems.length;

    let tableRows = previewItems.map((item, i) =>
        `<tr><td>${i + 1}</td><td><strong>${escapeHtml(item.name)}</strong></td><td>${classTypeName}</td></tr>`
    ).join('');

    if (moreCount > 0) {
        tableRows += `<tr><td colspan="3" style="text-align:center;color:var(--text-muted);padding:10px;">... 还有 ${moreCount} 条记录</td></tr>`;
    }

    const html = `
    <div class="modal-overlay" id="previewModal">
        <div class="modal-content preview-modal">
            <h3>📋 名单预览确认</h3>
            <div class="preview-info">
                <span>班型：<strong>${classTypeName}</strong></span>
                <span>共 <strong>${names.length}</strong> 条记录</span>
            </div>
            <div class="preview-table-wrap">
                <table class="preview-table">
                    <thead><tr><th>序号</th><th>姓名</th><th>班型</th></tr></thead>
                    <tbody>${tableRows}</tbody>
                </table>
            </div>
            <p class="preview-warning">⚠️ 请仔细核对名单，确认后将立即入库</p>
            <div class="modal-buttons">
                <button class="btn-cancel" onclick="closePreviewModal()">取消</button>
                <button class="btn-primary" onclick="confirmUpload()">✅ 确认上传</button>
            </div>
        </div>
    </div>`;

    const existing = document.getElementById('previewModal');
    if (existing) existing.remove();
    document.body.insertAdjacentHTML('beforeend', html);

    // 点击遮罩关闭
    document.getElementById('previewModal').addEventListener('click', function(e) {
        if (e.target === this) closePreviewModal();
    });
}

function closePreviewModal() {
    const modal = document.getElementById('previewModal');
    if (modal) modal.remove();
    _pendingNames = null;
}

async function confirmUpload() {
    if (!_pendingNames) return;
    const names = _pendingNames;
    _pendingNames = null;

    const modal = document.getElementById('previewModal');
    if (modal) modal.remove();

    const msgEl = document.getElementById('uploadMsg');
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
            showToast(`成功导入 ${data.inserted} 条记录`, 'success');
            loadStats();
            loadList(1);
            loadAuditLogs(1);
            document.getElementById('textInput').value = '';
            document.getElementById('fileInput').value = '';
            const dz = document.getElementById('dropZone');
            if (dz) dz.querySelector('p').textContent = '📂 点击选择文件或拖拽到此处';
        } else {
            msgEl.textContent = data.message || '上传失败';
            msgEl.className = 'upload-msg err';
            showToast(data.message || '上传失败', 'error');
        }
    } catch (err) {
        msgEl.textContent = '网络错误，请重试';
        msgEl.className = 'upload-msg err';
        showToast('网络错误，请重试', 'error');
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
    const isCardView = window.innerWidth < 768;

    tbody.innerHTML = `<tr><td colspan="${colspan}" class="loading-cell">⏳ 加载中...</td></tr>`;

    try {
        const params = new URLSearchParams({ page, per_page: 50 });
        if (searchTerm) params.set('search', searchTerm);
        const classFilter = document.getElementById('listClassFilter').value;
        if (classFilter) params.set('class_type', classFilter);

        const resp = await fetch(`/api/admin/list?${params.toString()}`);
        if (resp.status === 401) { window.location.href = '/admin'; return; }
        const data = await resp.json();

        if (!data.items.length) {
            tbody.innerHTML = `<tr><td colspan="${colspan}" class="loading-cell">
                <div class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <div class="empty-state-text">暂无数据</div>
                </div>
            </td></tr>`;
            renderPagination(0, page);
            return;
        }

        tbody.innerHTML = data.items.map(item => {
            const classTypeName = item.class_type === 'yucai' ? '育才班' : '科特班';
            return `
            <tr>
                <td data-label="选择"><input type="checkbox" class="list-check" value="${item.id}"></td>
                <td data-label="姓名"><strong>${escapeHtml(item.name)}</strong></td>
                <td data-label="班型"><span style="display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.78rem;font-weight:600;background:${item.class_type === 'yucai' ? '#fef3c7' : '#eff6ff'};color:${item.class_type === 'yucai' ? '#d97706' : '#2563eb'};border:1px solid ${item.class_type === 'yucai' ? '#fde68a' : '#bfdbfe'};">${classTypeName}</span></td>
                <td data-label="添加时间">${item.created_at || '-'}</td>
                <td data-label="操作">
                    <button class="btn-edit" onclick="doEdit(${item.id}, '${escapeHtml(item.name)}', '${item.class_type}')">✏️ 编辑</button>
                    <button class="btn-delete" onclick="doDelete(${item.id})">🗑 删除</button>
                </td>
            </tr>
            `;
        }).join('');

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

// 通用删除确认密码输入
function promptDeletePassword() {
    const pwd = prompt('⚠️ 该操作风险较高，请输入操作确认密码：');
    if (pwd === null) return null; // 用户取消
    if (!pwd.trim()) {
        showToast('密码不能为空', 'warning');
        return '';
    }
    return pwd.trim();
}

async function doBatchChangeClassType() {
    const ids = getSelectedIds();
    if (!ids.length) {
        showToast('请先勾选要修改的记录', 'warning');
        return;
    }

    const targetType = confirm(`确定要修改选中的 ${ids.length} 条记录吗？\n\n点击「确定」改为「科特班」，点击「取消」改为「育才班」。`)
        ? 'kete' : 'yucai';
    const targetName = targetType === 'kete' ? '科特班' : '育才班';

    showConfirm(`确定将选中的 ${ids.length} 条记录改为「${targetName}」吗？`, async () => {
        try {
            const resp = await fetch('/api/admin/batch-change-class-type', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids, class_type: targetType })
            });
            const data = await resp.json();
            if (data.success) {
                showToast(`成功修改 ${data.updated} 条记录为${targetName}`, 'success');
                loadList(currentPage);
                loadStats();
                loadAuditLogs(1);
            } else {
                showToast(data.message || '修改失败', 'error');
            }
        } catch (err) {
            showToast('修改失败，请重试', 'error');
        }
    });
}

async function doBatchDelete() {
    const ids = getSelectedIds();
    if (!ids.length) {
        showToast('请先勾选要删除的记录', 'warning');
        return;
    }
    showConfirm(`确定要删除选中的 ${ids.length} 条记录吗？`, async () => {
        const password = promptDeletePassword();
        if (password === null) return;
        if (!password) {
            showToast('未输入确认密码，操作已取消', 'warning');
            return;
        }

        try {
            const resp = await fetch('/api/admin/batch-delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids, password })
            });
            const data = await resp.json();
            if (data.success) {
                showToast(`成功删除 ${ids.length} 条记录`, 'success');
                loadList(currentPage);
                loadStats();
                loadAuditLogs(1);
            } else {
                showToast(data.message || '删除失败', 'error');
            }
        } catch (err) {
            showToast('删除失败，请重试', 'error');
        }
    });
}

async function doDelete(id) {
    showConfirm('确定要删除这条记录吗？', async () => {
        const password = promptDeletePassword();
        if (password === null) return;
        if (!password) {
            showToast('未输入确认密码，操作已取消', 'warning');
            return;
        }

        try {
            const resp = await fetch(`/api/admin/delete/${id}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });
            const data = await resp.json();
            if (data.success) {
                showToast('删除成功', 'success');
                loadList(currentPage);
                loadStats();
                loadAuditLogs(1);
            } else {
                showToast(data.message || '删除失败', 'error');
            }
        } catch (err) {
            showToast('删除失败，请重试', 'error');
        }
    });
}

async function doEdit(id, currentName, currentClassType) {
    const newName = prompt('请输入新的姓名：', currentName);
    if (newName === null) return;
    const newNameTrim = newName.trim();
    if (!newNameTrim) {
        showToast('姓名不能为空', 'warning');
        return;
    }

    const newClassType = confirm('当前班型：' + (currentClassType === 'yucai' ? '育才班' : '科特班') + '\n\n点击「确定」切换为「科特班」，点击「取消」切换为「育才班」')
        ? 'kete' : 'yucai';

    try {
        const resp = await fetch(`/api/admin/update/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newNameTrim, class_type: newClassType })
        });
        const data = await resp.json();
        if (data.success) {
            showToast('编辑成功', 'success');
            loadList(currentPage);
            loadStats();
            loadAuditLogs(1);
        } else {
            showToast(data.message || '编辑失败', 'error');
        }
    } catch (err) {
        showToast('网络错误，请重试', 'error');
    }
}

async function doClearAll() {
    showConfirm('确定要清空全部录取名单吗？此操作不可恢复！', async () => {
        const password = promptDeletePassword();
        if (password === null) return;
        if (!password) {
            showToast('未输入确认密码，操作已取消', 'warning');
            return;
        }

        try {
            const resp = await fetch('/api/admin/clear', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });
            const data = await resp.json();
            if (data.success) {
                showToast('已清空全部录取名单', 'success');
                loadList(1);
                loadStats();
                loadAuditLogs(1);
            } else {
                showToast(data.message || '清空失败', 'error');
            }
        } catch (err) {
            showToast('清空失败，请重试', 'error');
        }
    });
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
    html += `<button class="page-btn" onclick="loadList(1)" ${page === 1 ? 'disabled' : ''} title="首页">«</button>`;
    html += `<button class="page-btn" onclick="loadList(${page - 1})" ${page === 1 ? 'disabled' : ''} title="上一页">‹</button>`;
    const start = Math.max(1, page - 2);
    const end = Math.min(totalPages, page + 2);
    if (start > 1) html += `<span class="page-info">...</span>`;
    for (let i = start; i <= end; i++) {
        html += `<button class="page-btn${i === page ? ' active' : ''}" onclick="loadList(${i})">${i}</button>`;
    }
    if (end < totalPages) html += `<span class="page-info">...</span>`;
    html += `<button class="page-btn" onclick="loadList(${page + 1})" ${page === totalPages ? 'disabled' : ''} title="下一页">›</button>`;
    html += `<button class="page-btn" onclick="loadList(${totalPages})" ${page === totalPages ? 'disabled' : ''} title="末页">»</button>`;
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
    const colspan = 6;

    tbody.innerHTML = `<tr><td colspan="${colspan}" class="loading-cell">⏳ 加载中...</td></tr>`;

    try {
        const params = new URLSearchParams({ page, per_page: 50 });
        if (logSearchTerm) params.set('search', logSearchTerm);
        const classFilter = document.getElementById('logClassFilter').value;
        if (classFilter) params.set('class_type', classFilter);

        const resp = await fetch(`/api/admin/logs?${params.toString()}`);
        if (resp.status === 401) { window.location.href = '/admin'; return; }
        const data = await resp.json();

        if (!data.items.length) {
            tbody.innerHTML = `<tr><td colspan="${colspan}" class="loading-cell">
                <div class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <div class="empty-state-text">暂无数据</div>
                </div>
            </td></tr>`;
            renderLogPagination(0, page);
            return;
        }

        tbody.innerHTML = data.items.map(item => {
            const rowClass = item.admitted ? 'log-row-admitted' : 'log-row-rejected';
            const hasNeeds = item.needs && item.needs.trim() !== '';
            const classTypeName = item.class_type === 'yucai' ? '育才班' : item.class_type === 'kete' ? '科特班' : '-';
            const statusHtml = item.admitted
                ? `<span class="log-status admitted">✅ 已录取${hasNeeds ? ' (已提交需求)' : ''}</span>`
                : `<span class="log-status rejected">❌ 未录取</span>`;

            return `
                <tr class="${rowClass}">
                    <td data-label="选择"><input type="checkbox" class="log-check" value="${item.id}"></td>
                    <td data-label="姓名"><strong>${escapeHtml(item.name)}</strong></td>
                    <td data-label="班型">${classTypeName}</td>
                    <td data-label="录取状态">${statusHtml}</td>
                    <td data-label="培养需求">${hasNeeds ? item.needs.split(',').map(n => `<span class="confirmed-badge">${escapeHtml(n)}</span>`).join(' ') : '-'}</td>
                    <td data-label="查询时间">${item.created_at || '-'}</td>
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
    if (!ids.length) {
        showToast('请先勾选要删除的记录', 'warning');
        return;
    }
    showConfirm(`确定要删除选中的 ${ids.length} 条日志吗？`, async () => {
        try {
            const resp = await fetch('/api/admin/logs/batch-delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids })
            });
            const data = await resp.json();
            if (data.success) {
                showToast(`成功删除 ${ids.length} 条日志`, 'success');
                loadLogs(logCurrentPage);
                loadAuditLogs(1);
            }
        } catch (err) {
            showToast('删除失败，请重试', 'error');
        }
    });
}

async function doClearAllLogs() {
    showConfirm('确定要清空全部查询日志吗？此操作不可恢复！', async () => {
        try {
            const resp = await fetch('/api/admin/logs/clear', { method: 'DELETE' });
            const data = await resp.json();
            if (data.success) {
                showToast('已清空全部查询日志', 'success');
                loadLogs(1);
                loadAuditLogs(1);
            }
        } catch (err) {
            showToast('清空失败，请重试', 'error');
        }
    });
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
    html += `<button class="page-btn" onclick="loadLogs(1)" ${page === 1 ? 'disabled' : ''} title="首页">«</button>`;
    html += `<button class="page-btn" onclick="loadLogs(${page - 1})" ${page === 1 ? 'disabled' : ''} title="上一页">‹</button>`;
    const start = Math.max(1, page - 2);
    const end = Math.min(totalPages, page + 2);
    if (start > 1) html += `<span class="page-info">...</span>`;
    for (let i = start; i <= end; i++) {
        html += `<button class="page-btn${i === page ? ' active' : ''}" onclick="loadLogs(${i})">${i}</button>`;
    }
    if (end < totalPages) html += `<span class="page-info">...</span>`;
    html += `<button class="page-btn" onclick="loadLogs(${page + 1})" ${page === totalPages ? 'disabled' : ''} title="下一页">›</button>`;
    html += `<button class="page-btn" onclick="loadLogs(${totalPages})" ${page === totalPages ? 'disabled' : ''} title="末页">»</button>`;
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
function doExportLogsXlsx() {
    window.location.href = '/api/admin/logs/export_xlsx';
}
function doExportList() {
    window.location.href = '/api/admin/list/export';
}
function doExportListXlsx() {
    window.location.href = '/api/admin/list/export_xlsx';
}

// ═══════════════════════════════════════════
// 操作日志
// ═══════════════════════════════════════════

let auditLogPage = 1;

async function loadAuditLogs(page) {
    auditLogPage = page;
    const tbody = document.getElementById('auditLogTableBody');
    tbody.innerHTML = `<tr><td colspan="4" class="loading-cell">⏳ 加载中...</td></tr>`;

    try {
        const params = new URLSearchParams({ page, per_page: 50 });
        const resp = await fetch(`/api/admin/audit-logs?${params.toString()}`);
        if (resp.status === 401) { window.location.href = '/admin'; return; }
        const data = await resp.json();

        if (!data.items.length) {
            tbody.innerHTML = `<tr><td colspan="4" class="loading-cell">
                <div class="empty-state">
                    <div class="empty-state-icon">📝</div>
                    <div class="empty-state-text">暂无操作记录</div>
                </div>
            </td></tr>`;
            renderAuditLogPagination(0, page);
            return;
        }

        const actionColors = {
            '上传录取名单': '#059669',
            '删除录取名单': '#dc2626',
            '批量删除录取名单': '#dc2626',
            '清空录取名单': '#dc2626',
            '编辑录取名单': '#6366f1',
            '批量删除查询日志': '#d97706',
            '清空查询日志': '#d97706',
        };
        const actionIcons = {
            '上传录取名单': '📤',
            '删除录取名单': '🗑',
            '批量删除录取名单': '🗑',
            '清空录取名单': '🗑',
            '编辑录取名单': '✏️',
            '批量删除查询日志': '🗑',
            '清空查询日志': '🗑',
        };

        tbody.innerHTML = data.items.map(item => {
            const color = actionColors[item.action] || '#6366f1';
            const icon = actionIcons[item.action] || '📋';
            return `
                <tr>
                    <td data-label="操作"><span class="audit-tag" style="background:${color}15;color:${color};border:1px solid ${color}30;">${icon} ${escapeHtml(item.action)}</span></td>
                    <td data-label="对象">${escapeHtml(item.target || '-')}</td>
                    <td data-label="详情">${escapeHtml(item.detail || '-')}</td>
                    <td data-label="操作时间" style="color:var(--text-secondary);font-size:0.82rem;">${item.created_at || '-'}</td>
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
    html += `<button class="page-btn" onclick="loadAuditLogs(1)" ${page === 1 ? 'disabled' : ''} title="首页">«</button>`;
    html += `<button class="page-btn" onclick="loadAuditLogs(${page - 1})" ${page === 1 ? 'disabled' : ''} title="上一页">‹</button>`;
    const start = Math.max(1, page - 2);
    const end = Math.min(totalPages, page + 2);
    if (start > 1) html += `<span class="page-info">...</span>`;
    for (let i = start; i <= end; i++) {
        html += `<button class="page-btn${i === page ? ' active' : ''}" onclick="loadAuditLogs(${i})">${i}</button>`;
    }
    if (end < totalPages) html += `<span class="page-info">...</span>`;
    html += `<button class="page-btn" onclick="loadAuditLogs(${page + 1})" ${page === totalPages ? 'disabled' : ''} title="下一页">›</button>`;
    html += `<button class="page-btn" onclick="loadAuditLogs(${totalPages})" ${page === totalPages ? 'disabled' : ''} title="末页">»</button>`;
    html += `<span class="page-info">共 ${total} 条</span>`;
    pagination.innerHTML = html;
}

async function doClearAllAuditLogs() {
    showConfirm('确定要清空全部操作日志吗？此操作不可恢复！', async () => {
        try {
            const resp = await fetch('/api/admin/audit-logs/clear', { method: 'DELETE' });
            const data = await resp.json();
            if (data.success) {
                showToast('已清空操作日志', 'success');
                loadAuditLogs(1);
            }
        } catch (err) {
            showToast('清空失败，请重试', 'error');
        }
    });
}

// ═══════════════════════════════════════════
// 统计概览
// ═══════════════════════════════════════════

async function loadStats() {
    try {
        const resp = await fetch('/api/admin/stats');
        if (resp.status === 401) return;
        const data = await resp.json();

        document.getElementById('totalBadge').innerHTML = '<span style="font-size:0.7rem;">📋</span> 总计: ' + data.total + ' 人';
        document.getElementById('keteBadge').innerHTML = '<span style="font-size:0.7rem;">🔵</span> 科特班: ' + (data.kete || 0) + ' 人';
        document.getElementById('yucaiBadge').innerHTML = '<span style="font-size:0.7rem;">🟡</span> 育才班: ' + (data.yucai || 0) + ' 人';

        document.getElementById('statTotal').textContent = data.total;
        document.getElementById('statVisitors').textContent = data.visitors;
        document.getElementById('statTodayQueries').textContent = data.today_queries;
        document.getElementById('statConfirmed').textContent = data.today_confirmed;
        document.getElementById('statQueryRate').textContent = data.query_rate + '%';
        document.getElementById('statNeedRate').textContent = data.need_rate + '%';
    } catch (err) { /* ignore */ }
}

// ═══════════════════════════════════════════
// 工具函数
// ═══════════════════════════════════════════

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
