/**
 * 天津职业技术师范大学校园AI助手 - 前端交互脚本
 */

// ==================== 配置 ====================
const CONFIG = {
    API_BASE_URL: '',  // 空字符串表示同域请求
    AI_NAME: '天职小咕',
    AI_AVATAR: 'js/avatar.png',  // 相对于 frontend 目录
    USER_AVATAR_TEXT: '我'
};

// ==================== DOM 元素 ====================
const messageList = document.getElementById('message-list');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const loadingIndicator = document.getElementById('loading-indicator');
const welcomeMessage = document.querySelector('.welcome-message');

// ==================== 状态 ====================
let isProcessing = false;
let conversationHistory = [];

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    loadAvatarImage();
    checkBackendHealth();
});

// ==================== 事件监听 ====================
function initEventListeners() {
    // 发送按钮点击
    sendBtn.addEventListener('click', sendMessage);

    // 输入框键盘事件
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // 输入框自动调整高度
    userInput.addEventListener('input', adjustTextareaHeight);
}

// ==================== 头像处理 ====================
function loadAvatarImage() {
    // 尝试加载用户指定的头像路径
    const avatarImg = new Image();
    avatarImg.onload = function() {
        CONFIG.AI_AVATAR = 'js/avatar.png';
        updateAllAvatars();
    };
    avatarImg.onerror = function() {
        // 如果加载失败，使用默认 SVG
        console.log('自定义头像加载失败，使用默认头像');
        CONFIG.AI_AVATAR = null;
    };
    avatarImg.src = 'js/avatar.png';
}

function updateAllAvatars() {
    const avatars = document.querySelectorAll('.ai-avatar img, .message-avatar img');
    avatars.forEach(img => {
        if (img.alt === CONFIG.AI_NAME || img.closest('.message.ai')) {
            img.src = CONFIG.AI_AVATAR;
        }
    });
}

function getAIAvatarHTML() {
    if (CONFIG.AI_AVATAR) {
        return `<img src="${CONFIG.AI_AVATAR}" alt="${CONFIG.AI_NAME}" onerror="this.parentElement.innerHTML='🦉'">`;
    }
    return '🦉';
}

// ==================== 消息发送 ====================
async function sendMessage() {
    if (isProcessing) return;

    const message = userInput.value.trim();
    if (!message) return;

    // 隐藏欢迎消息
    if (welcomeMessage) {
        welcomeMessage.style.display = 'none';
    }

    // 添加用户消息到界面
    addUserMessage(message);

    // 清空输入框
    userInput.value = '';
    userInput.style.height = 'auto';

    // 禁用输入
    setProcessing(true);

    try {
        // 调用后端 API
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        });

        const data = await response.json();

        if (data.success) {
            addAIMessage(data.reply);
        } else {
            addErrorMessage(data.error || '抱歉，服务暂时不可用，请稍后再试。');
        }
    } catch (error) {
        console.error('发送消息失败:', error);
        addErrorMessage('网络连接失败，请检查后端服务是否正常运行。');
    } finally {
        setProcessing(false);
    }
}

// ==================== 快速提问 ====================
function askQuestion(question) {
    userInput.value = question;
    adjustTextareaHeight();
    sendMessage();
}

// ==================== 添加消息到界面 ====================
function addUserMessage(text) {
    const messageHTML = `
        <div class="message user">
            <div class="message-avatar">${CONFIG.USER_AVATAR_TEXT}</div>
            <div class="message-content">
                <div class="message-sender">你</div>
                <div class="message-bubble">${escapeHtml(text)}</div>
            </div>
        </div>
    `;
    messageList.insertAdjacentHTML('beforeend', messageHTML);
    scrollToBottom();
}

function addAIMessage(text) {
    const formattedText = formatMessage(text);
    const messageHTML = `
        <div class="message ai">
            <div class="message-avatar">${getAIAvatarHTML()}</div>
            <div class="message-content">
                <div class="message-sender">${CONFIG.AI_NAME}</div>
                <div class="message-bubble">${formattedText}</div>
            </div>
        </div>
    `;
    messageList.insertAdjacentHTML('beforeend', messageHTML);
    scrollToBottom();
}

function addErrorMessage(text) {
    const messageHTML = `
        <div class="message ai">
            <div class="message-avatar">${getAIAvatarHTML()}</div>
            <div class="message-content">
                <div class="message-sender">${CONFIG.AI_NAME}</div>
                <div class="message-bubble error-message">${escapeHtml(text)}</div>
            </div>
        </div>
    `;
    messageList.insertAdjacentHTML('beforeend', messageHTML);
    scrollToBottom();
}

// ==================== 消息格式化 ====================
function formatMessage(text) {
    // 转义 HTML
    let formatted = escapeHtml(text);

    // 处理换行
    formatted = formatted.replace(/\n/g, '<br>');

    // 处理粗体 **text**
    formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // 处理斜体 *text*
    formatted = formatted.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // 处理代码 `code`
    formatted = formatted.replace(/`(.+?)`/g, '<code>$1</code>');

    // 处理链接 [text](url)
    formatted = formatted.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

    return formatted;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== UI 控制 ====================
function setProcessing(processing) {
    isProcessing = processing;

    if (processing) {
        sendBtn.disabled = true;
        loadingIndicator.classList.remove('hidden');
    } else {
        sendBtn.disabled = false;
        loadingIndicator.classList.add('hidden');
    }
}

function adjustTextareaHeight() {
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
}

function scrollToBottom() {
    const chatContainer = document.querySelector('.chat-container');
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// ==================== 后端健康检查 ====================
async function checkBackendHealth() {
    const loader = document.getElementById('startup-loader');
    const maxRetries = 60;  // 最多重试60次（约2分钟）
    let retries = 0;

    const checkHealth = async () => {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}/api/health`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            });

            const data = await response.json();
            console.log('后端状态:', data);

            // 如果状态是 ready，隐藏 Loading
            if (data.status === 'ready') {
                if (loader) {
                    loader.classList.add('hidden');
                }
                console.log('[OK] 后端服务已就绪');
                return;
            }

            // 如果正在初始化，继续等待
            if (data.status === 'initializing') {
                retries++;
                if (retries < maxRetries) {
                    console.log(`后端正在初始化，等待中... (${retries}/${maxRetries})`);
                    setTimeout(checkHealth, 2000);  // 每2秒检查一次
                } else {
                    // 超时，显示连接错误
                    if (loader) {
                        loader.classList.add('hidden');
                    }
                    showConnectionError('后端服务启动超时，请刷新页面重试。');
                }
            }
        } catch (error) {
            // 后端未启动或连接失败，继续等待
            retries++;
            if (retries < maxRetries) {
                console.log(`等待后端服务启动... (${retries}/${maxRetries})`);
                setTimeout(checkHealth, 2000);
            } else {
                // 超时
                if (loader) {
                    loader.classList.add('hidden');
                }
                console.error('后端连接失败:', error);
                showConnectionError();
            }
        }
    };

    // 开始检查
    await checkHealth();
}

function showConnectionError(customMessage) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'connection-error';
    const message = customMessage || '无法连接到后端服务，请确保 Flask 服务已启动<br><code style="background: rgba(0,0,0,0.05); padding: 4px 8px; border-radius: 4px; margin-top: 8px; display: inline-block;">python backend/app.py</code>';
    errorDiv.innerHTML = `
        <div style="
            background: #fef3c7;
            border: 1px solid #f59e0b;
            color: #92400e;
            padding: 12px 16px;
            border-radius: 8px;
            margin: 0 24px 16px;
            font-size: 13px;
            text-align: center;
        ">
            <strong>⚠️ 连接提示</strong><br>
            ${message}
        </div>
    `;

    const header = document.querySelector('.chat-header');
    header.insertAdjacentElement('afterend', errorDiv);
}

// ==================== 工具函数 ====================
// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 导出全局函数供 HTML 调用
window.askQuestion = askQuestion;
window.sendMessage = sendMessage;
