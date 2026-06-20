const API_URL = 'http://localhost:8000';

const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const loading = document.getElementById('loading');
const results = document.getElementById('results');
const previewImage = document.getElementById('previewImage');
const fullText = document.getElementById('fullText');
const linesList = document.getElementById('linesList');
const copyAllBtn = document.getElementById('copyAllBtn');
const toast = document.getElementById('toast');
const toastText = document.getElementById('toastText');


['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) {
    e.preventDefaults();
    e.stopPropagation();
}

['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => dropZone.classList.add('dragober'),false);
});

['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => 
    dropZone.classList.remove('dragover'),false);
});

dropZone.addEventListener('drop', handleDrop, false);
dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', handleFiles, false);

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    handleFiles({target: {files } });
}

function handleFiles(e) {
    const files = e.target.files;
    if (files.length > 0) {
        processImage(files[0]);
    }
}

async function processImage(file) {
    if (!file.type.startsWith('image/')) {
        showToast('Select an image file!', 'error');
        return;
    }

    results.style.display = 'none';
    loading.style.display = 'block';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_URL}/api/extract-text`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            displayResults(data);
        } else {
            showToast('Error: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('Unable to connect to the backend. Run: python app.py', 'error');
        console.error(error);
    } finally {
        loading.style.display = 'none';
    }
}

function displayResults(data) {
    previewImage.src = data.preview;
    fullText.value = data.text;

    linesList.innerHTML = '';
    data.lines.forEach((line, index) => {
        const item = document.createElement('div');
        item.className = 'line-item';
        item.innerHTML = `
            <div class="line-number">${index + 1}</div>
            <div class="line-text">${escapeHtml(line.text)}</div>
            <div class="line-confidence">${Math.round(line.confidence * 100)}%</div>

            <button class="btn btn-line"
    onclick="copyLine('${escapeHtml(line.text).replace(/'/g, "\\'")}', this)"> 
    📋 copy </button>
    `;
    linesList.appendChild(item);

    });

    results.style.display = 'block';
    results.scrollIntoView({ behavior: 'smooth', block: 'start'});
}

copyAllBtn.addEventListener('click', () => {
    fullText.ariaSelected();
    document.execCommand('copy');
    showToast('The entire text has been copied!');

    copyAllBtn.textContent = 'copied!';
    setTimeout(() => {
        copyAllBtn.textContent = '📋 Copy all';
    }, 2000);
});

function copyLine(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied: "' + text.substring(0, 30) + (text.length > 30 ?
            '...' : '') + '"');

            btn.textContent = 'Copied';
            btn.classList.add('copied');

            setTimeout(() => {
                btn.textContent = '📋 Copy';
                btn.classList.remove('copied');
            }, 2000);
    }).catch(err => {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        showToast('Copied!');
    });
}

function showToast(message, type = 'success') {
    toastText.textContent = message;
    toast.style.background = type === 'error' ? '#ef4444' : '#22c55e';
    toast.style.display = 'block';

    toast.style.animation = 'none';
    toast.offsetHeight;
    toast.style.animation = 'slideIn 0.3s, fadeOut 0.3s 2.5s forwards';

    setTimeout(() => {
        toast.style.display = 'none';
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}