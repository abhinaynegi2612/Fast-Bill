// Bill Analyzer Dashboard JavaScript

const API_BASE_URL = 'http://localhost:8000/api/v1';

// State
const state = {
    files: {
        original: null,
        suspected: null,
        reader: null
    },
    fileIds: {
        original: null,
        suspected: null,
        reader: null
    },
    billData: null,
    isProcessing: false
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    setupTabs();
    setupDragDrop();
    setupButtons();
    setInterval(checkHealth, 30000); // Check health every 30s
});

// Health Check
async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const data = await response.json();
        
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.querySelector('.status-text');
        
        if (data.status === 'healthy') {
            statusDot.classList.add('online');
            statusDot.classList.remove('offline');
            statusText.textContent = 'API Online';
        } else {
            throw new Error('API unhealthy');
        }
    } catch (error) {
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.querySelector('.status-text');
        statusDot.classList.add('offline');
        statusDot.classList.remove('online');
        statusText.textContent = 'API Offline';
    }
}

// Tab Navigation
function setupTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;
            
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        });
    });
}

// Drag & Drop Setup
function setupDragDrop() {
    const setups = [
        { dropZone: 'originalDrop', fileInput: 'originalFile', type: 'original' },
        { dropZone: 'suspectedDrop', fileInput: 'suspectedFile', type: 'suspected' },
        { dropZone: 'readerDrop', fileInput: 'readerFile', type: 'reader' }
    ];
    
    setups.forEach(({ dropZone, fileInput, type }) => {
        const zone = document.getElementById(dropZone);
        const input = document.getElementById(fileInput);
        
        zone.addEventListener('click', () => input.click());
        
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        });
        
        zone.addEventListener('dragleave', () => {
            zone.classList.remove('dragover');
        });
        
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFile(files[0], type);
            }
        });
        
        input.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFile(e.target.files[0], type);
            }
        });
    });
}

// Handle File Selection
function handleFile(file, type) {
    const validTypes = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg'];
    
    if (!validTypes.includes(file.type) && !file.name.match(/\.(pdf|png|jpg|jpeg)$/i)) {
        alert('Please upload a valid PDF or image file');
        return;
    }
    
    state.files[type] = file;
    updateFileUI(type, file);
    
    if (type === 'reader') {
        document.getElementById('parseBtn').disabled = false;
    } else {
        checkForgeryButton();
    }
}

// Update File UI
function updateFileUI(type, file) {
    const infoId = type === 'original' ? 'originalInfo' : 
                   type === 'suspected' ? 'suspectedInfo' : 'readerInfo';
    const contentSelector = `#${type === 'original' ? 'originalDrop' : 
                              type === 'suspected' ? 'suspectedDrop' : 'readerDrop'} .upload-content`;
    
    const info = document.getElementById(infoId);
    const content = document.querySelector(contentSelector);
    
    info.classList.remove('hidden');
    content.classList.add('hidden');
    
    document.getElementById(`${type}Filename`).textContent = file.name;
    document.getElementById(`${type}Filesize`).textContent = formatFileSize(file.size);
}

// Remove File
function removeFile(type) {
    state.files[type] = null;
    state.fileIds[type] = null;
    
    const infoId = type === 'original' ? 'originalInfo' : 
                   type === 'suspected' ? 'suspectedInfo' : 'readerInfo';
    const contentSelector = `#${type === 'original' ? 'originalDrop' : 
                              type === 'suspected' ? 'suspectedDrop' : 'readerDrop'} .upload-content`;
    
    document.getElementById(infoId).classList.add('hidden');
    document.querySelector(contentSelector).classList.remove('hidden');
    
    document.getElementById(`${type}File`).value = '';
    
    if (type === 'reader') {
        document.getElementById('parseBtn').disabled = true;
        document.getElementById('parsedData').classList.add('hidden');
        document.getElementById('commandInput').disabled = true;
        document.getElementById('sendBtn').disabled = true;
        state.billData = null;
    } else {
        checkForgeryButton();
    }
}

// Format File Size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Check Forgery Button State
function checkForgeryButton() {
    const btn = document.getElementById('forgeryAnalyze');
    btn.disabled = !(state.files.original && state.files.suspected);
}

// Setup Buttons
function setupButtons() {
    document.getElementById('forgeryAnalyze').addEventListener('click', runForgeryDetection);
    document.getElementById('parseBtn').addEventListener('click', parseBill);
    document.getElementById('commandInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendCustomCommand();
    });
}

// Run Forgery Detection
async function runForgeryDetection() {
    if (state.isProcessing) return;
    state.isProcessing = true;
    
    const btn = document.getElementById('forgeryAnalyze');
    const btnText = btn.querySelector('.btn-text');
    const spinner = btn.querySelector('.spinner');
    
    btnText.textContent = 'Analyzing...';
    spinner.classList.remove('hidden');
    btn.disabled = true;
    
    try {
        // Upload both files
        const [originalId, suspectedId] = await Promise.all([
            uploadFile(state.files.original),
            uploadFile(state.files.suspected)
        ]);
        
        state.fileIds.original = originalId;
        state.fileIds.suspected = suspectedId;
        
        // Run forgery detection
        const formData = new FormData();
        formData.append('original_file_id', originalId);
        formData.append('suspected_file_id', suspectedId);
        
        const response = await fetch(`${API_BASE_URL}/detect-forgery`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error('Forgery detection failed');
        
        const result = await response.json();
        displayForgeryResults(result);
        
    } catch (error) {
        alert('Error: ' + error.message);
        console.error(error);
    } finally {
        state.isProcessing = false;
        btnText.textContent = 'Detect Forgery';
        spinner.classList.add('hidden');
        btn.disabled = false;
    }
}

// Upload File
async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        body: formData
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Upload failed');
    }
    
    const data = await response.json();
    return data.file_id;
}

// Display Forgery Results
function displayForgeryResults(result) {
    const resultsDiv = document.getElementById('forgeryResults');
    resultsDiv.classList.remove('hidden');
    
    // Verdict
    const verdict = document.getElementById('verdict');
    const verdictText = verdict.querySelector('.verdict-text');
    const verdictIcon = verdict.querySelector('.verdict-icon');
    
    if (result.tampered) {
        verdict.className = 'verdict tampered';
        verdictIcon.textContent = '⚠';
        verdictText.textContent = 'Tampering Detected';
    } else {
        verdict.className = 'verdict authentic';
        verdictIcon.textContent = '✓';
        verdictText.textContent = 'Bill Appears Authentic';
    }
    
    // Confidence
    document.getElementById('confidence').innerHTML = `
        <div class="confidence-value">${result.confidence}%</div>
        <div class="confidence-label">Confidence</div>
    `;
    
    // Reasons
    const reasonsList = document.getElementById('reasonsList');
    reasonsList.innerHTML = result.reasons.length > 0 
        ? result.reasons.map(r => `<li>${r}</li>`).join('')
        : '<li>No suspicious activity detected</li>';
    
    // Checks
    const checksList = document.getElementById('checksList');
    checksList.innerHTML = result.checks.map(check => `
        <div class="check-item ${check.passed ? 'passed' : 'failed'}">
            <div class="check-icon">${check.passed ? '✓' : '✗'}</div>
            <div class="check-details">
                <div class="check-name">${check.check_name}</div>
                <div class="check-desc">${check.details}</div>
            </div>
        </div>
    `).join('');
    
    // Metadata
    document.getElementById('originalMetadata').textContent = 
        JSON.stringify(result.original_metadata, null, 2);
    document.getElementById('suspectedMetadata').textContent = 
        JSON.stringify(result.suspected_metadata, null, 2);
    
    // Scroll to results
    resultsDiv.scrollIntoView({ behavior: 'smooth' });
}

// Parse Bill
async function parseBill() {
    if (state.isProcessing || !state.files.reader) return;
    state.isProcessing = true;
    
    const btn = document.getElementById('parseBtn');
    const btnText = btn.querySelector('.btn-text');
    const spinner = btn.querySelector('.spinner');
    
    btnText.textContent = 'Parsing...';
    spinner.classList.remove('hidden');
    btn.disabled = true;
    
    try {
        // Upload file
        const fileId = await uploadFile(state.files.reader);
        state.fileIds.reader = fileId;
        
        // Parse bill
        const response = await fetch(`${API_BASE_URL}/parse/${fileId}`, {
            method: 'POST'
        });
        
        if (!response.ok) throw new Error('Parsing failed');
        
        const data = await response.json();
        state.billData = data;
        
        displayParsedData(data);
        
        // Enable chat
        document.getElementById('commandInput').disabled = false;
        document.getElementById('sendBtn').disabled = false;
        
        // Add welcome message to chat
        addBotMessage(`Bill parsed successfully! You have ${data.items?.length || 0} items totaling ₹${data.total_amount?.toFixed(2) || '0.00'}. Ask me anything about this bill.`);
        
    } catch (error) {
        alert('Error: ' + error.message);
        console.error(error);
    } finally {
        state.isProcessing = false;
        btnText.textContent = 'Parse Bill';
        spinner.classList.add('hidden');
        btn.disabled = false;
    }
}

// Display Parsed Data
function displayParsedData(data) {
    document.getElementById('parsedData').classList.remove('hidden');
    
    document.getElementById('vendorName').textContent = data.vendor_name || '-';
    document.getElementById('billNumber').textContent = data.bill_number || '-';
    document.getElementById('billDate').textContent = data.bill_date || '-';
    document.getElementById('itemCount').textContent = data.items?.length || 0;
    document.getElementById('subtotal').textContent = `₹${data.subtotal?.toFixed(2) || '0.00'}`;
    document.getElementById('gstAmount').textContent = 
        `₹${data.gst_amount?.toFixed(2) || '0.00'} (${data.gst_rate || 0}%)`;
    document.getElementById('totalAmount').textContent = `₹${data.total_amount?.toFixed(2) || '0.00'}`;
    
    // Items table
    const tbody = document.getElementById('itemsTableBody');
    tbody.innerHTML = (data.items || []).map(item => `
        <tr>
            <td>${item.name}</td>
            <td>${item.quantity} ${item.unit}</td>
            <td>₹${item.price.toFixed(2)}</td>
            <td>₹${item.amount.toFixed(2)}</td>
        </tr>
    `).join('');
}

// Send Command
async function sendCommand(command) {
    if (!state.fileIds.reader || state.isProcessing) return;
    
    addUserMessage(command);
    await processCommand(command);
}

function sendCustomCommand() {
    const input = document.getElementById('commandInput');
    const command = input.value.trim();
    
    if (!command) return;
    
    sendCommand(command);
    input.value = '';
}

// Process Command
async function processCommand(command) {
    state.isProcessing = true;
    
    const chatHistory = document.getElementById('chatHistory');
    
    try {
        const formData = new FormData();
        formData.append('file_id', state.fileIds.reader);
        formData.append('command', command);
        
        const response = await fetch(`${API_BASE_URL}/query`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error('Query failed');
        
        const result = await response.json();
        addBotMessage(result.answer);
        
    } catch (error) {
        addBotMessage('Sorry, I could not process that query. Error: ' + error.message);
        console.error(error);
    } finally {
        state.isProcessing = false;
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
}

// Add Messages to Chat
function addUserMessage(text) {
    const chatHistory = document.getElementById('chatHistory');
    const welcome = chatHistory.querySelector('.welcome-msg');
    if (welcome) welcome.remove();
    
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    const msg = document.createElement('div');
    msg.className = 'message user';
    msg.innerHTML = `
        <div class="message-content">${escapeHtml(text)}</div>
        <div class="message-time">${time}</div>
    `;
    
    chatHistory.appendChild(msg);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function addBotMessage(text) {
    const chatHistory = document.getElementById('chatHistory');
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    const msg = document.createElement('div');
    msg.className = 'message bot';
    msg.innerHTML = `
        <div class="message-content">${escapeHtml(text).replace(/\n/g, '<br>')}</div>
        <div class="message-time">${time}</div>
    `;
    
    chatHistory.appendChild(msg);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export to CSV
async function exportToCSV() {
    if (!state.fileIds.reader) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/bill/${state.fileIds.reader}/dataframe`);
        
        if (!response.ok) throw new Error('Export failed');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `bill_${state.fileIds.reader}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
    } catch (error) {
        alert('Export failed: ' + error.message);
        console.error(error);
    }
}
