/**
 * 录取查询系统 - 用户查询页 JS
 */

let captchaToken = '';

// 初始化：加载验证码
document.addEventListener('DOMContentLoaded', () => {
    refreshCaptcha();
});

async function refreshCaptcha() {
    const exprEl = document.getElementById('captchaExpr');
    exprEl.textContent = '加载中...';
    try {
        const resp = await fetch('/api/captcha');
        const data = await resp.json();
        captchaToken = data.token;
        exprEl.textContent = data.expression;
    } catch (err) {
        exprEl.textContent = '加载失败';
    }
}

async function doQuery() {
    const nameInput = document.getElementById('nameInput');
    const captchaInput = document.getElementById('captchaInput');
    const queryBtn = document.getElementById('queryBtn');
    const resultArea = document.getElementById('resultArea');
    const resultCard = document.getElementById('resultCard');

    const name = nameInput.value.trim();
    const captchaAnswer = captchaInput.value.trim();
    const classType = window.APP_CLASS_TYPE || 'kete';

    if (!name) {
        shakeElement(nameInput);
        nameInput.focus();
        return;
    }

    if (!captchaAnswer) {
        shakeElement(captchaInput);
        captchaInput.focus();
        return;
    }

    // 按钮加载态
    queryBtn.disabled = true;
    queryBtn.textContent = '查询中...';

    try {
        const params = new URLSearchParams();
        params.set('name', name);
        params.set('class_type', classType);
        params.set('captcha_token', captchaToken);
        params.set('captcha_answer', captchaAnswer);

        const resp = await fetch(`/api/query?${params.toString()}`);
        const data = await resp.json();

        if (!data.success) {
            // 验证码错误等，刷新验证码但保留姓名
            refreshCaptcha();
            captchaInput.value = '';
            showFailResult(data.message);
        } else if (data.admitted) {
            // 录取成功 → 跳转到独立结果页，保持班型路径
            const redirectParams = new URLSearchParams();
            redirectParams.set('name', data.name);
            if (data.category) redirectParams.set('category', data.category);
            if (data.grade) redirectParams.set('grade', data.grade);
            if (data.score) redirectParams.set('score', data.score);
            window.location.href = '/' + classType + '/result?' + redirectParams.toString();
            return;
        } else {
            refreshCaptcha();
            captchaInput.value = '';
            showFailResult('该学员未通过北大-点猫科技人工智能教育联合实验室英才计划录取线', '请联系班主任老师进行其他班型学分测验');
        }
    } catch (err) {
        refreshCaptcha();
        captchaInput.value = '';
        showFailResult('网络错误，请稍后重试');
    } finally {
        queryBtn.disabled = false;
        queryBtn.textContent = '查询录取结果';
    }
}

function showFailResult(title, subtitle) {
    const resultArea = document.getElementById('resultArea');
    const resultCard = document.getElementById('resultCard');
    resultCard.className = 'result-card fail';
    let html = `<div class="result-icon">😞</div><h2>${title}</h2>`;
    if (subtitle) {
        html += `<p style="color:rgba(255,255,255,0.6);margin-top:8px;font-size:0.85rem;">${subtitle}</p>`;
    }
    resultCard.innerHTML = html;
    resultArea.style.display = 'block';
    resultArea.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// 回车触发查询
document.getElementById('nameInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') doQuery();
});
document.getElementById('captchaInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') doQuery();
});

// 刷新验证码按钮
document.getElementById('captchaRefresh').addEventListener('click', () => {
    document.getElementById('captchaInput').value = '';
    refreshCaptcha();
});

function shakeElement(el) {
    el.style.animation = 'none';
    el.offsetHeight;
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
