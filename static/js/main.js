/**
 * 录取查询系统 - 用户查询页 JS
 */

async function doQuery() {
    const nameInput = document.getElementById('nameInput');
    const examInput = document.getElementById('examInput');
    const queryBtn = document.getElementById('queryBtn');
    const resultArea = document.getElementById('resultArea');
    const resultCard = document.getElementById('resultCard');

    const name = nameInput.value.trim();
    const examNumber = examInput.value.trim();

    if (!name && !examNumber) {
        shakeElement(nameInput);
        nameInput.focus();
        return;
    }

    // 按钮加载态
    queryBtn.disabled = true;
    queryBtn.innerHTML = '<span>⏳</span> 查询中...';

    try {
        const params = new URLSearchParams();
        if (name) params.set('name', name);
        if (examNumber) params.set('exam_number', examNumber);

        const resp = await fetch(`/api/query?${params.toString()}`);
        const data = await resp.json();

        resultArea.style.display = 'block';

        if (!data.success) {
            resultCard.className = 'result-card fail';
            resultCard.innerHTML = `
                <div class="result-icon">⚠️</div>
                <h2>${data.message}</h2>
            `;
        } else if (data.admitted) {
            resultCard.className = 'result-card success';
            let detailHtml = `<p><strong>姓名：</strong>${escapeHtml(data.name)}</p>`;
            if (data.exam_number) detailHtml += `<p><strong>准考证号：</strong>${escapeHtml(data.exam_number)}</p>`;
            if (data.category) detailHtml += `<p><strong>类别：</strong>${escapeHtml(data.category)}</p>`;
            resultCard.innerHTML = `
                <div class="result-icon">🎉</div>
                <h2>恭喜！您已被录取！</h2>
                <div class="result-detail">${detailHtml}</div>
            `;
        } else {
            resultCard.className = 'result-card fail';
            resultCard.innerHTML = `
                <div class="result-icon">😞</div>
                <h2>未查询到录取信息</h2>
                <p style="color:var(--text-secondary);margin-top:4px;">请核对姓名和准考证号是否正确</p>
            `;
        }

        // 滚动到结果
        resultArea.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (err) {
        resultArea.style.display = 'block';
        resultCard.className = 'result-card fail';
        resultCard.innerHTML = `
            <div class="result-icon">⚠️</div>
            <h2>网络错误，请稍后重试</h2>
        `;
    } finally {
        queryBtn.disabled = false;
        queryBtn.innerHTML = '<span>🔍</span> 查询录取结果';
    }
}

// 回车触发查询
document.getElementById('nameInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') doQuery();
});
document.getElementById('examInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') doQuery();
});

function shakeElement(el) {
    el.style.animation = 'none';
    el.offsetHeight; // reflow
    el.style.animation = 'shake 0.4s ease';
    setTimeout(() => { el.style.animation = ''; }, 400);
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// 添加 shake 动画
const shakeStyle = document.createElement('style');
shakeStyle.textContent = `
@keyframes shake {
    0%, 100% { transform: translateX(0); }
    20% { transform: translateX(-6px); }
    40% { transform: translateX(6px); }
    60% { transform: translateX(-4px); }
    80% { transform: translateX(4px); }
}`;
document.head.appendChild(shakeStyle);
