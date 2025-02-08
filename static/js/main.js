document.addEventListener('DOMContentLoaded', function() {
    // Tab 切換功能
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;
            
            // 更新按鈕狀態
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // 更新內容顯示
            tabContents.forEach(content => {
                content.classList.remove('active');
                if (content.id === `${tabId}Tab`) {
                    content.classList.add('active');
                }
            });

            // 清空結果和錯誤顯示
            document.getElementById('result').style.display = 'none';
            document.getElementById('error').style.display = 'none';
        });
    });

    // 檔案上傳表單處理
    const uploadForm = document.getElementById('uploadForm');
    uploadForm.addEventListener('submit', handleUpload);

    // 批次上傳表單處理
    const batchForm = document.getElementById('batchForm');
    batchForm.addEventListener('submit', handleBatchUpload);

    // 查詢表單處理
    const queryForm = document.getElementById('queryForm');
    queryForm.addEventListener('submit', handleQuery);

    // 處理郵件分析表單提交
    const mailForm = document.getElementById('mailForm');
    mailForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const fileInput = document.getElementById('mailInput');
        const files = fileInput.files;
        
        if (files.length === 0) {
            showError('請選擇要分析的郵件檔案');
            return;
        }

        // 為每個檔案創建上傳任務
        for (let file of files) {
            try {
                const formData = new FormData();
                formData.append('file', file);
                
                await fetch('/analyze_mail', {
                    method: 'POST',
                    body: formData
                });
                
            } catch (error) {
                showError(`上傳 ${file.name} 時發生錯誤: ${error.message}`);
            }
        }
        
        // 清空檔案選擇
        fileInput.value = '';
    });

    // 初始化郵件分析頁面
    initMailAnalysis();

    document.getElementById('clearMailResults').addEventListener('click', function() {
        // 清空進度列表
        document.getElementById('mailProgressList').innerHTML = '';
        
        // 發送請求到後端清除狀態
        fetch('/clear_mail_status', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                console.log('分析結果已清除');
            }
        })
        .catch(error => {
            console.error('清除結果時發生錯誤:', error);
        });
    });
});

async function handleUpload(e) {
    e.preventDefault();
    
    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files[0]) {
        showError('請選擇要上傳的檔案');
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    await processRequest('/upload', {
        method: 'POST',
        body: formData
    });
}

async function handleBatchUpload(e) {
    e.preventDefault();
    
    const fileInput = document.getElementById('batchInput');
    const files = fileInput.files;
    const autoQuery = document.getElementById('autoQuery').checked;
    
    if (files.length === 0) {
        showError('請選擇要上傳的檔案');
        return;
    }

    const progressList = document.getElementById('progressList');
    const batchProgress = document.getElementById('batchProgress');
    
    progressList.innerHTML = '';
    batchProgress.style.display = 'block';

    const progressItems = {};
    for (let file of files) {
        const progressItem = createProgressItem(file.name);
        progressList.appendChild(progressItem);
        progressItems[file.name] = {
            element: progressItem,
            status: 'pending'
        };
    }

    for (let file of files) {
        try {
            updateProgress(progressItems[file.name], 'uploading');
            
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.message || '上傳失敗');
            }

            // 更新 MD5
            if (result.response && result.response[0]) {
                const md5 = result.response[0].md5;
                updateProgress(progressItems[file.name], 'analyzing', '', { md5: md5 });
                
                if (autoQuery) {
                    startStatusPolling(md5, progressItems[file.name]);
                }
            } else {
                updateProgress(progressItems[file.name], 'completed');
            }

        } catch (error) {
            console.error(`處理檔案 ${file.name} 時發生錯誤:`, error);
            updateProgress(progressItems[file.name], 'error', error.message);
        }
    }
}

function createProgressItem(filename) {
    const div = document.createElement('div');
    div.className = 'progress-item';
    div.innerHTML = `
        <div class="file-info">
            <div class="filename">${filename}</div>
            <div class="file-details">
                <span class="md5">MD5: 待取得</span>
                <span class="verdict">判定結果: 待取得</span>
            </div>
        </div>
        <div class="status status-pending">等待處理</div>
    `;
    return div;
}

function updateProgress(item, status, message = '', extraInfo = {}) {
    const statusElement = item.element.querySelector('.status');
    const md5Element = item.element.querySelector('.md5');
    const verdictElement = item.element.querySelector('.verdict');
    
    statusElement.className = `status status-${status}`;
    statusElement.textContent = message || getStatusText(status);
    
    if (extraInfo.md5) {
        md5Element.textContent = `MD5: ${extraInfo.md5}`;
    }
    
    if (extraInfo.verdict) {
        const verdictClass = getVerdictClass(extraInfo.verdict);
        verdictElement.textContent = `判定結果: ${getVerdictText(extraInfo.verdict)}`;
        verdictElement.className = `verdict ${verdictClass}`;
    }
}

async function startStatusPolling(md5, progressItem) {
    const maxAttempts = 30;
    const interval = 10000;
    let attempts = 0;

    const pollStatus = async () => {
        try {
            const response = await fetch('/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query_id: md5 })
            });

            const result = await response.json();
            
            if (result.response && result.response[0]) {
                const response = result.response[0];
                const status = response.status;
                
                if (status.label === 'FOUND') {
                    // 更新 MD5 和判定結果
                    const verdict = response.te?.combined_verdict || '未知';
                    updateProgress(progressItem, 'completed', '', {
                        md5: md5,
                        verdict: verdict
                    });
                    return true;
                } else if (status.label === 'NOT_FOUND' || status.label === 'PENDING') {
                    if (++attempts >= maxAttempts) {
                        updateProgress(progressItem, 'error', '查詢超時', { md5: md5 });
                        return true;
                    }
                    return false;
                } else {
                    updateProgress(progressItem, 'error', status.message || '查詢失敗', { md5: md5 });
                    return true;
                }
            }
            
            return false;
        } catch (error) {
            console.error('查詢狀態時發生錯誤:', error);
            return true;
        }
    };

    const poll = async () => {
        const finished = await pollStatus();
        if (!finished) {
            setTimeout(poll, interval);
        }
    };

    poll();
}

async function handleQuery(e) {
    e.preventDefault();
    
    const queryInput = document.getElementById('queryInput');
    const queryId = queryInput.value.trim();
    
    if (!queryId) {
        showError('請輸入查詢 ID');
        return;
    }

    await processRequest('/query', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query_id: queryId })
    });
}

async function processRequest(url, options) {
    const loadingDiv = document.getElementById('loading');
    const resultDiv = document.getElementById('result');
    const errorDiv = document.getElementById('error');

    try {
        loadingDiv.style.display = 'block';
        resultDiv.style.display = 'none';
        errorDiv.style.display = 'none';

        const response = await fetch(url, options);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || '處理請求時發生錯誤');
        }

        displayNormalizedResult(data);
    } catch (error) {
        showError(error.message);
    } finally {
        loadingDiv.style.display = 'none';
    }
}

function displayNormalizedResult(data) {
    const resultDiv = document.getElementById('result');
    const statusInfo = document.getElementById('statusInfo');
    const analysisInfo = document.getElementById('analysisInfo');
    const rawJson = document.getElementById('rawJson');

    statusInfo.innerHTML = '';
    analysisInfo.innerHTML = '';

    if (data.response && data.response[0]) {
        const response = data.response[0];
        
        // 基本資訊區塊
        addSectionTitle(statusInfo, '檔案資訊');
        addInfoItem(statusInfo, '檔案名稱', response.file_name || 'N/A');
        addInfoItem(statusInfo, '檔案類型', response.file_type || 'N/A');
        
        // 雜湊值區塊
        addSectionTitle(statusInfo, '檔案雜湊值');
        addInfoItem(statusInfo, 'MD5', response.md5 || 'N/A');
        addInfoItem(statusInfo, 'SHA1', response.sha1 || 'N/A');
        addInfoItem(statusInfo, 'SHA256', response.sha256 || 'N/A');

        // 狀態資訊區塊
        if (response.status) {
            addSectionTitle(statusInfo, '處理狀態');
            addInfoItem(statusInfo, '狀態代碼', response.status.code);
            addInfoItem(statusInfo, '狀態標籤', response.status.label);
            addInfoItem(statusInfo, '狀態訊息', response.status.message);
        }

        // 威脅分析結果
        if (response.te) {
            addSectionTitle(analysisInfo, '威脅分析結果');
            const verdict = response.te.combined_verdict || 'N/A';
            addInfoItem(analysisInfo, '綜合判定', verdict, getVerdictClass(verdict));
            addInfoItem(analysisInfo, '威脅等級', response.te.severity || 'N/A', getSeverityClass(response.te.severity));
            addInfoItem(analysisInfo, '信心指數', response.te.confidence || 'N/A');

            // Blob 分析結果
            if (response.te.blob && response.te.blob.embedded_data) {
                addSectionTitle(analysisInfo, '內容分析');
                const embedded = response.te.blob.embedded_data;
                addInfoItem(analysisInfo, '包含壓縮檔', formatBoolean(embedded.classified_as_zip));
                addInfoItem(analysisInfo, '包含內嵌檔案', formatBoolean(embedded.contains_embedded_files));
                addInfoItem(analysisInfo, '包含巨集程式碼', formatBoolean(embedded.contains_macro_and_code));
                addInfoItem(analysisInfo, '包含敏感連結', formatBoolean(embedded.contains_sensitive_links));
                addInfoItem(analysisInfo, '檔案是否加密', formatBoolean(embedded.is_file_encrypted));
            }

            // 映像分析結果
            if (response.te.images && response.te.images.length > 0) {
                addSectionTitle(analysisInfo, '映像分析');
                response.te.images.forEach((image, index) => {
                    addInfoItem(analysisInfo, `映像 ${index + 1} ID`, image.id);
                    if (image.report) {
                        addInfoItem(analysisInfo, `映像 ${index + 1} 判定`, image.report.verdict, getVerdictClass(image.report.verdict));
                    }
                });
            }
        }
    }

    // 顯示格式化的原始 JSON
    rawJson.textContent = JSON.stringify(data, null, 2);
    resultDiv.style.display = 'block';
}

function addSectionTitle(container, title) {
    const titleDiv = document.createElement('div');
    titleDiv.className = 'section-title';
    titleDiv.textContent = title;
    container.appendChild(titleDiv);
}

function addInfoItem(container, label, value, valueClass = '') {
    const div = document.createElement('div');
    div.className = 'info-item';
    div.innerHTML = `
        <div class="info-label">${label}</div>
        <div class="info-value ${valueClass}">${value}</div>
    `;
    container.appendChild(div);
}

function formatBoolean(value) {
    if (value === true) return '<span class="status-warning">是</span>';
    if (value === false) return '<span class="status-safe">否</span>';
    return 'N/A';
}

function getVerdictClass(verdict) {
    switch(verdict.toLowerCase()) {
        case 'malicious':
            return 'verdict-malicious';
        case 'suspicious':
            return 'verdict-suspicious';
        case 'benign':
            return 'verdict-benign';
        case 'error':
            return 'verdict-error';
        default:
            return 'verdict-unknown';
    }
}

function getVerdictText(verdict) {
    switch(verdict.toLowerCase()) {
        case 'malicious':
            return '惡意';
        case 'suspicious':
            return '可疑';
        case 'benign':
            return '安全';
        case 'error':
            return '錯誤';
        default:
            return '未知';
    }
}

function getSeverityClass(severity) {
    if (!severity) return '';
    switch(String(severity).toLowerCase()) {
        case 'high':
            return 'status-danger';
        case 'medium':
            return 'status-warning';
        case 'low':
            return 'status-safe';
        default:
            return '';
    }
}

function showError(message) {
    const errorDiv = document.getElementById('error');
    const errorMessage = document.getElementById('errorMessage');
    errorMessage.textContent = message;
    errorDiv.style.display = 'block';
}

// 初始化郵件分析頁面
function initMailAnalysis() {
    updateMailAnalysisList();
    // 每 5 秒更新一次列表
    setInterval(updateMailAnalysisList, 5000);
}

// 更新郵件分析列表
async function updateMailAnalysisList() {
    try {
        const response = await fetch('/mail_analysis_list');
        const analysisList = await response.json();
        
        const progressList = document.getElementById('mailProgressList');
        
        analysisList.forEach(analysis => {
            let mailItem = document.getElementById(`mail-${analysis.id}`);
            
            if (!mailItem) {
                mailItem = document.createElement('div');
                mailItem.id = `mail-${analysis.id}`;
                mailItem.className = 'mail-item';
                progressList.insertBefore(mailItem, progressList.firstChild);
            }
            
            mailItem.innerHTML = `
                <div class="mail-header">
                    <div class="mail-info">
                        <div class="mail-filename">${analysis.filename}</div>
                        <div class="mail-details">
                            <span class="mail-md5">MD5: ${analysis.md5}</span>
                            <span class="analysis-time">處理時間: ${analysis.duration || '處理中...'}</span>
                        </div>
                    </div>
                    <div class="mail-status status-${analysis.status}">
                        ${getStatusText(analysis.status)}
                    </div>
                </div>
                <div class="attachment-list">
                    ${analysis.attachments.map(att => `
                        <div class="attachment-item">
                            <div class="attachment-info">
                                <div class="attachment-name">${att.original_name}</div>
                                <div class="attachment-details">
                                    <span class="attachment-md5">${att.md5 || '計算中...'}</span>
                                    <span class="analysis-time">處理時間: ${att.duration || '處理中...'}</span>
                                </div>
                            </div>
                            <div class="attachment-verdict ${getVerdictClass(att.verdict)}">
                                ${att.verdict || '分析中'}
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        });
        
    } catch (error) {
        console.error('更新分析列表時發生錯誤:', error);
    }
}

// 獲取狀態文字
function getStatusText(status) {
    switch(status) {
        case 'analyzing':
            return '分析中';
        case 'completed':
            return '完成';
        case 'error':
            return '錯誤';
        default:
            return '未知';
    }
}

async function pollBatchStatus(batchId, items) {
    const maxAttempts = 300;
    const interval = 2000;
    let attempts = 0;
    
    const checkStatus = async () => {
        try {
            const response = await fetch(`/batch_status/${batchId}`);
            const result = await response.json();
            
            // 更新進度資訊
            const progressInfo = document.getElementById('batchProgressInfo');
            if (progressInfo) {
                progressInfo.textContent = `處理進度: ${result.completed_files}/${result.total_files} 檔案完成`;
            }
            
            // 更新每個檔案的狀態
            result.files.forEach(file => {
                const item = items.find(i => i.filename === file.filename);
                if (item) {
                    updateProgress(item, file.status, '', {
                        md5: file.md5,
                        result: file.result
                    });
                }
            });
            
            // 檢查是否完成
            if (result.status === 'completed') {
                return true;
            } else if (result.status === 'error') {
                showError('批次處理發生錯誤');
                return true;
            } else if (++attempts >= maxAttempts) {
                showError('批次處理超時');
                return true;
            }
            
            return false;
            
        } catch (error) {
            console.error('檢查狀態時發生錯誤:', error);
            return true;
        }
    };
    
    const poll = async () => {
        const finished = await checkStatus();
        if (!finished) {
            setTimeout(poll, interval);
        }
    };
    
    poll();
}

function updateBatchProgress(batchId) {
    fetch(`/batch_status/${batchId}`)
        .then(response => response.json())
        .then(data => {
            const progressList = document.getElementById('progressList');
            progressList.innerHTML = '';

            // 顯示每個檔案的狀態
            data.files.forEach(file => {
                const fileDiv = document.createElement('div');
                fileDiv.className = 'file-status';
                
                // 獲取判定結果
                let verdict = '未知';
                let verdictClass = 'verdict-unknown';
                let severity = file.combined_verdict?.severity || '未知';
                let confidence = file.combined_verdict?.confidence || '未知';
                
                if (file.result && file.result.response && file.result.response[0] && 
                    file.result.response[0].te && file.result.response[0].te.combined_verdict) {
                    const combinedVerdict = file.result.response[0].te.combined_verdict.toLowerCase();
                    switch(combinedVerdict) {
                        case 'malicious':
                            verdictClass = 'verdict-malicious';
                            verdict = '惡意';
                            break;
                        case 'benign':
                            verdictClass = 'verdict-benign';
                            verdict = '安全';
                            break;
                        case 'suspicious':
                            verdictClass = 'verdict-suspicious';
                            verdict = '可疑';
                            break;
                        case 'error':
                            verdictClass = 'verdict-error';
                            verdict = '錯誤';
                            break;
                        default:
                            verdictClass = 'verdict-unknown';
                            verdict = '未知';
                    }
                }

                let status = '處理中';
                let statusClass = 'analyzing';
                switch(file.status) {
                    case 'completed':
                        status = '完成';
                        statusClass = 'completed';
                        break;
                    case 'error':
                        status = '錯誤';
                        statusClass = 'error';
                        break;
                    default:
                        status = '處理中';
                        statusClass = 'analyzing';
                }

                fileDiv.innerHTML = `
                    <div class="file-info">
                        <span class="filename">${file.filename}</span>
                        <span class="file-md5">${file.md5 || 'N/A'}</span>
                    </div>
                    <div class="file-status-info">
                        <span class="status ${statusClass}">${status}</span>
                        <span class="severity">威脅等級: ${severity}</span>
                        <span class="confidence">信心指數: ${confidence}</span>
                        <span class="duration">${file.duration || '處理中...'}</span>
                    </div>
                    <div class="file-verdict">
                        <span class="verdict ${verdictClass}">判定結果: ${verdict}</span>
                    </div>
                `;
                progressList.appendChild(fileDiv);
            });

            // 如果批次處理還在進行中，繼續更新
            if (data.status === 'processing' && document.getElementById('autoQuery').checked) {
                setTimeout(() => updateBatchProgress(batchId), 3000);
            }
        })
        .catch(error => {
            console.error('更新批次進度時發生錯誤:', error);
        });
}

// ... 其他 JavaScript 函數 ... 
// ... 其他 JavaScript 函數 ... 