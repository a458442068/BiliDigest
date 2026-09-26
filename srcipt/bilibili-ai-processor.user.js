// ==UserScript==
// @name         B站视频AI处理器
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  向本地AI服务发送B站视频处理请求
// @author       You
// @match        *://*.bilibili.com/video/*
// @connect      localhost
// @connect      192.168.31.173
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// ==/UserScript==

(function () {
    'use strict';

    // ==================== 常量定义 ====================
    const DEFAULT_CONFIG = {
        serverUrl: 'http://192.168.31.173:8000',
        translate: true,
        summarize: true,
        force: false,
        showResult: true
    };

    const STORAGE_KEY = 'aiProcessorConfig';

    // ==================== 配置管理 ====================
    function loadConfig() {
        const saved = GM_getValue(STORAGE_KEY, null);
        return saved ? { ...DEFAULT_CONFIG, ...saved } : { ...DEFAULT_CONFIG };
    }

    function saveConfig(config) {
        GM_setValue(STORAGE_KEY, config);
    }

    // ==================== 视频信息提取 ====================
    function extractBV() {
        const url = window.location.href;
        const match = url.match(/BV[0-9A-Za-z]+/);
        return match ? match[0] : null;
    }

    // ==================== 样式注入 ====================
    function injectStyles() {
        const css = `
            #ai-float-btn {
                position: fixed;
                bottom: 100px;
                right: 30px;
                width: 50px;
                height: 50px;
                border-radius: 50%;
                background: linear-gradient(135deg, #00a1d6, #0088b4);
                color: white;
                font-size: 14px;
                font-weight: bold;
                border: none;
                cursor: pointer;
                z-index: 99999;
                box-shadow: 0 4px 12px rgba(0, 161, 214, 0.4);
                transition: transform 0.2s, box-shadow 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            #ai-float-btn:hover {
                transform: scale(1.1);
                box-shadow: 0 6px 16px rgba(0, 161, 214, 0.5);
            }

            #ai-panel {
                position: fixed;
                bottom: 170px;
                right: 30px;
                width: 320px;
                background: #fff;
                border-radius: 12px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
                z-index: 100000;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                display: none;
                overflow: hidden;
            }
            #ai-panel.visible {
                display: block;
            }
            #ai-panel-header {
                background: linear-gradient(135deg, #00a1d6, #0088b4);
                color: white;
                padding: 15px;
                cursor: move;
                display: flex;
                justify-content: space-between;
                align-items: center;
                user-select: none;
            }
            #ai-panel-header h3 {
                margin: 0;
                font-size: 16px;
                font-weight: 600;
            }
            #ai-panel-close {
                background: none;
                border: none;
                color: white;
                font-size: 20px;
                cursor: pointer;
                padding: 0;
                line-height: 1;
                opacity: 0.8;
            }
            #ai-panel-close:hover {
                opacity: 1;
            }
            #ai-panel-body {
                padding: 20px;
            }
            .ai-form-group {
                margin-bottom: 16px;
            }
            .ai-form-group label {
                display: block;
                font-size: 13px;
                color: #666;
                margin-bottom: 6px;
            }
            .ai-form-group input[type="text"] {
                width: 100%;
                padding: 10px 12px;
                border: 1px solid #ddd;
                border-radius: 8px;
                font-size: 14px;
                box-sizing: border-box;
                transition: border-color 0.2s;
            }
            .ai-form-group input[type="text"]:focus {
                outline: none;
                border-color: #00a1d6;
            }
            .ai-checkbox-group {
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
            }
            .ai-checkbox-item {
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 14px;
                color: #333;
                cursor: pointer;
            }
            .ai-checkbox-item input {
                width: 16px;
                height: 16px;
                accent-color: #00a1d6;
            }
            .ai-video-info {
                background: #f5f5f5;
                padding: 12px;
                border-radius: 8px;
                font-size: 13px;
                color: #666;
            }
            .ai-video-info span {
                color: #00a1d6;
                font-weight: 600;
            }
            #ai-process-btn {
                width: 100%;
                padding: 12px;
                background: linear-gradient(135deg, #00a1d6, #0088b4);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
                cursor: pointer;
                transition: opacity 0.2s;
            }
            #ai-process-btn:hover {
                opacity: 0.9;
            }
            #ai-process-btn:disabled {
                background: #ccc;
                cursor: not-allowed;
            }

            #ai-notification {
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 25px;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                font-weight: 500;
                z-index: 100001;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                display: none;
                animation: slideIn 0.3s ease;
            }
            #ai-notification.success {
                background: #52c41a;
            }
            #ai-notification.error {
                background: #ff4d4f;
            }
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }

            #ai-result-panel {
                position: fixed;
                bottom: 80px;
                right: 0;
                width: 450px;
                max-height: calc(100vh - 160px);
                background: #fff;
                border-radius: 12px 0 0 12px;
                box-shadow: -4px -4px 24px rgba(0, 0, 0, 0.15);
                z-index: 100000;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                display: none;
                overflow: hidden;
            }
            #ai-result-panel.visible {
                display: block;
                animation: slideInRight 0.3s ease;
            }
            @keyframes slideInRight {
                from {
                    transform: translateX(100%);
                }
                to {
                    transform: translateX(0);
                }
            }
            #ai-result-header {
                background: linear-gradient(135deg, #00a1d6, #0088b4);
                color: white;
                padding: 15px;
                cursor: move;
                display: flex;
                justify-content: space-between;
                align-items: center;
                user-select: none;
            }
            #ai-result-header h3 {
                margin: 0;
                font-size: 16px;
                font-weight: 600;
            }
            .ai-result-actions {
                display: flex;
                gap: 10px;
            }
            .ai-result-actions button {
                background: rgba(255, 255, 255, 0.2);
                border: none;
                color: white;
                padding: 5px 12px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 12px;
                transition: background 0.2s;
            }
            .ai-result-actions button:hover {
                background: rgba(255, 255, 255, 0.3);
            }
            #ai-result-body {
                padding: 20px;
                max-height: calc(100vh - 250px);
                overflow-y: auto;
            }
            .ai-result-section {
                margin-bottom: 20px;
            }
            .ai-result-section h4 {
                margin: 0 0 10px 0;
                font-size: 14px;
                color: #333;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .ai-result-section h4::before {
                content: '';
                width: 4px;
                height: 16px;
                background: #00a1d6;
                border-radius: 2px;
            }
            .ai-result-content {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                font-size: 14px;
                line-height: 1.6;
                color: #333;
                white-space: pre-wrap;
                word-break: break-word;
            }
            #ai-result-loading {
                display: none;
                text-align: center;
                padding: 40px;
                color: #666;
            }
            .ai-spinner {
                width: 40px;
                height: 40px;
                border: 4px solid #f3f3f3;
                border-top: 4px solid #00a1d6;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 15px;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        const style = document.createElement('style');
        style.textContent = css;
        document.head.appendChild(style);
    }

    // ==================== UI 组件 ====================
    function createFloatingButton() {
        const btn = document.createElement('button');
        btn.id = 'ai-float-btn';
        btn.textContent = 'AI';
        btn.title = 'B站视频AI处理器';
        btn.addEventListener('click', togglePanel);
        document.body.appendChild(btn);
    }

    function createPanel() {
        const config = loadConfig();
        const bv = extractBV();

        const panel = document.createElement('div');
        panel.id = 'ai-panel';
        panel.innerHTML = `
            <div id="ai-panel-header">
                <h3>B站视频AI处理器</h3>
                <button id="ai-panel-close">&times;</button>
            </div>
            <div id="ai-panel-body">
                <div class="ai-form-group">
                    <label>服务器地址:</label>
                    <input type="text" id="ai-server-url" value="${config.serverUrl}" placeholder="http://192.168.31.173:8000">
                </div>
                <div class="ai-form-group">
                    <label>选项:</label>
                    <div class="ai-checkbox-group">
                        <label class="ai-checkbox-item">
                            <input type="checkbox" id="ai-translate" ${config.translate ? 'checked' : ''}>
                            翻译
                        </label>
                        <label class="ai-checkbox-item">
                            <input type="checkbox" id="ai-summarize" ${config.summarize ? 'checked' : ''}>
                            摘要
                        </label>
                        <label class="ai-checkbox-item">
                            <input type="checkbox" id="ai-force" ${config.force ? 'checked' : ''}>
                            强制处理
                        </label>
                        <label class="ai-checkbox-item">
                            <input type="checkbox" id="ai-show-result" ${config.showResult ? 'checked' : ''}>
                            展示结果
                        </label>
                    </div>
                </div>
                <div class="ai-form-group">
                    <div class="ai-video-info">
                        当前视频: <span>${bv || '未检测到视频ID'}</span>
                    </div>
                </div>
                <button id="ai-process-btn">开始处理</button>
            </div>
        `;

        document.body.appendChild(panel);

        // 事件绑定
        document.getElementById('ai-panel-close').addEventListener('click', (e) => {
            e.stopPropagation();
            togglePanel();
        });
        document.getElementById('ai-process-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            handleProcess();
        });

        // 拖动功能
        makeDraggable(document.getElementById('ai-panel-header'), panel);
    }

    function createResultPanel() {
        const panel = document.createElement('div');
        panel.id = 'ai-result-panel';
        panel.innerHTML = `
            <div id="ai-result-header">
                <h3>处理结果</h3>
                <div class="ai-result-actions">
                    <button id="ai-result-copy">复制</button>
                    <button id="ai-result-close">&times;</button>
                </div>
            </div>
            <div id="ai-result-body">
                <div id="ai-result-loading">
                    <div class="ai-spinner"></div>
                    <p>正在处理中...</p>
                </div>
                <div id="ai-result-content"></div>
            </div>
        `;

        document.body.appendChild(panel);

        // 事件绑定
        document.getElementById('ai-result-close').addEventListener('click', (e) => {
            e.stopPropagation();
            hideResultPanel();
        });
        document.getElementById('ai-result-copy').addEventListener('click', (e) => {
            e.stopPropagation();
            copyResult();
        });

        // 拖动功能
        makeDraggable(document.getElementById('ai-result-header'), panel);
    }

    // 拖动功能实现
    function makeDraggable(handle, element) {
        let isDragging = false;
        let startX, startY, initialX, initialY;

        handle.addEventListener('mousedown', (e) => {
            if (e.target.tagName === 'BUTTON') return;
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            const rect = element.getBoundingClientRect();
            initialX = rect.left;
            initialY = rect.top;
            element.style.transition = 'none';
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const deltaX = e.clientX - startX;
            const deltaY = e.clientY - startY;
            element.style.left = (initialX + deltaX) + 'px';
            element.style.top = (initialY + deltaY) + 'px';
            element.style.right = 'auto';
        });

        document.addEventListener('mouseup', () => {
            isDragging = false;
            element.style.transition = '';
        });
    }

    function togglePanel() {
        const panel = document.getElementById('ai-panel');
        if (!panel) {
            createPanel();
            document.getElementById('ai-panel').classList.add('visible');
        } else {
            panel.classList.toggle('visible');
        }
    }

    function showNotification(message, type) {
        let notification = document.getElementById('ai-notification');
        if (!notification) {
            notification = document.createElement('div');
            notification.id = 'ai-notification';
            document.body.appendChild(notification);
        }

        notification.textContent = message;
        notification.className = type;
        notification.style.display = 'block';

        setTimeout(() => {
            notification.style.display = 'none';
        }, 3000);
    }

    function showResultPanel() {
        let panel = document.getElementById('ai-result-panel');
        if (!panel) {
            createResultPanel();
            panel = document.getElementById('ai-result-panel');
        }
        panel.classList.add('visible');
        document.getElementById('ai-result-loading').style.display = 'block';
        document.getElementById('ai-result-content').innerHTML = '';
    }

    function hideResultPanel() {
        const panel = document.getElementById('ai-result-panel');
        if (panel) {
            panel.classList.remove('visible');
        }
    }

    function copyResult() {
        const content = document.getElementById('ai-result-content');
        const text = content.innerText;
        navigator.clipboard.writeText(text).then(() => {
            const btn = document.getElementById('ai-result-copy');
            btn.textContent = '已复制';
            setTimeout(() => {
                btn.textContent = '复制';
            }, 2000);
        });
    }

    // ==================== 请求处理 ====================
    function handleProcess() {
        const bv = extractBV();
        if (!bv) {
            showNotification('未检测到视频ID', 'error');
            return;
        }

        // 收集配置
        const config = {
            serverUrl: document.getElementById('ai-server-url').value.trim(),
            translate: document.getElementById('ai-translate').checked,
            summarize: document.getElementById('ai-summarize').checked,
            force: document.getElementById('ai-force').checked,
            showResult: document.getElementById('ai-show-result').checked
        };

        // 保存配置
        saveConfig(config);

        // 关闭配置面板
        const panel = document.getElementById('ai-panel');
        if (panel) {
            panel.classList.remove('visible');
        }

        // 显示结果面板或通知
        if (config.showResult) {
            showResultPanel();
        }

        // 发送请求
        sendRequest(bv, config);
    }

    function sendRequest(bvid, config) {
        const requestData = {
            url: bvid,
            options: {
                translate: config.translate,
                summarize: config.summarize,
                force: config.force
            }
        };

        GM_xmlhttpRequest({
            method: 'POST',
            url: `${config.serverUrl}/api/v1/process`,
            headers: {
                'Content-Type': 'application/json'
            },
            data: JSON.stringify(requestData),
            onload: function (response) {
                handleResponse(response, config);
            },
            onerror: function (error) {
                handleError(error, config);
            },
            ontimeout: function () {
                handleError({ message: '请求超时' }, config);
            }
        });
    }

    function handleResponse(response, config) {
        // 恢复按钮
        const btn = document.getElementById('ai-process-btn');
        btn.disabled = false;
        btn.textContent = '开始处理';

        if (response.status >= 200 && response.status < 300) {
            try {
                const data = JSON.parse(response.responseText);
                if (config.showResult) {
                    displayResult(data);
                } else {
                    showNotification('处理成功', 'success');
                }
            } catch (e) {
                if (config.showResult) {
                    displayRawResult(response.responseText);
                } else {
                    showNotification('处理成功', 'success');
                }
            }
        } else {
            if (config.showResult) {
                displayError(`请求失败: HTTP ${response.status}`);
            } else {
                showNotification('处理失败', 'error');
            }
        }
    }

    function handleError(error, config) {
        // 恢复按钮
        const btn = document.getElementById('ai-process-btn');
        btn.disabled = false;
        btn.textContent = '开始处理';

        if (config.showResult) {
            displayError(`请求错误: ${error.message || '网络错误'}`);
        } else {
            showNotification('处理失败', 'error');
        }
    }

    function displayResult(data) {
        document.getElementById('ai-result-loading').style.display = 'none';
        const content = document.getElementById('ai-result-content');

        let html = '';

        // 只显示 transcript_clean、translation、summary
        if (data.transcript_clean) {
            html += `
                <div class="ai-result-section">
                    <h4>字幕</h4>
                    <div class="ai-result-content">${escapeHtml(data.transcript_clean)}</div>
                </div>
            `;
        }

        if (data.translation) {
            html += `
                <div class="ai-result-section">
                    <h4>翻译</h4>
                    <div class="ai-result-content">${escapeHtml(data.translation)}</div>
                </div>
            `;
        }

        if (data.summary) {
            html += `
                <div class="ai-result-section">
                    <h4>摘要</h4>
                    <div class="ai-result-content">${escapeHtml(data.summary)}</div>
                </div>
            `;
        }

        // 如果都没有，显示整个响应
        if (!html) {
            html = `
                <div class="ai-result-section">
                    <h4>处理结果</h4>
                    <div class="ai-result-content">${escapeHtml(JSON.stringify(data, null, 2))}</div>
                </div>
            `;
        }

        content.innerHTML = html;
    }

    function displayRawResult(text) {
        document.getElementById('ai-result-loading').style.display = 'none';
        const content = document.getElementById('ai-result-content');
        content.innerHTML = `
            <div class="ai-result-section">
                <h4>处理结果</h4>
                <div class="ai-result-content">${escapeHtml(text)}</div>
            </div>
        `;
    }

    function displayError(message) {
        document.getElementById('ai-result-loading').style.display = 'none';
        const content = document.getElementById('ai-result-content');
        content.innerHTML = `
            <div class="ai-result-section">
                <h4>错误</h4>
                <div class="ai-result-content" style="color: #ff4d4f;">${escapeHtml(message)}</div>
            </div>
        `;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ==================== 初始化 ====================
    function init() {
        injectStyles();
        createFloatingButton();

        // 点击其他区域关闭面板
        document.addEventListener('click', (e) => {
            const panel = document.getElementById('ai-panel');
            const resultPanel = document.getElementById('ai-result-panel');
            const btn = document.getElementById('ai-float-btn');
            const processBtn = document.getElementById('ai-process-btn');

            // 如果点击的是处理按钮，不关闭任何面板
            if (e.target === processBtn) {
                return;
            }

            // 关闭配置面板
            if (panel && panel.classList.contains('visible') &&
                !panel.contains(e.target) && !btn.contains(e.target)) {
                panel.classList.remove('visible');
            }

            // 关闭结果面板
            if (resultPanel && resultPanel.classList.contains('visible') &&
                !resultPanel.contains(e.target)) {
                resultPanel.classList.remove('visible');
            }
        });
    }

    // 等待页面加载完成
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
