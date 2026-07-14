/**
 * upload.js — File upload with drag-and-drop, validation, and redirect to processing page.
 */
(function () {
  'use strict';

  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const fileList = document.getElementById('fileList');
  const actionRow = document.getElementById('actionRow');
  const uploadBtn = document.getElementById('uploadBtn');
  const clearBtn = document.getElementById('clearBtn');
  const fileSummary = document.getElementById('fileSummary');
  const uploadForm = document.getElementById('uploadForm');

  let selectedFiles = [];

  // ── Drag and drop ──────────────────────────────────────────────────────────
  ['dragenter', 'dragover'].forEach(evt => {
    dropZone.addEventListener(evt, e => { e.preventDefault(); dropZone.classList.add('dragover'); });
  });
  ['dragleave', 'drop'].forEach(evt => {
    dropZone.addEventListener(evt, e => { e.preventDefault(); dropZone.classList.remove('dragover'); });
  });
  dropZone.addEventListener('drop', e => addFiles(Array.from(e.dataTransfer.files)));
  dropZone.addEventListener('click', e => {
    if (!e.target.closest('label')) fileInput.click();
  });
  fileInput.addEventListener('change', () => addFiles(Array.from(fileInput.files)));

  // ── Paste event ────────────────────────────────────────────────────────────
  document.addEventListener('paste', e => {
    if (!e.clipboardData) return;
    
    let pastedFiles = [];
    
    // Try to get image from clipboard items (works for Snipping Tool)
    if (e.clipboardData.items) {
      for (let i = 0; i < e.clipboardData.items.length; i++) {
        const item = e.clipboardData.items[i];
        if (item.type.indexOf('image') !== -1) {
          const file = item.getAsFile();
          if (file) {
            const ext = file.type === 'image/jpeg' ? 'jpg' : 'png';
            pastedFiles.push(new File([file], `pasted-image-${Date.now()}-${i}.${ext}`, { type: file.type }));
          }
        }
      }
    }
    
    // Fallback to clipboardData.files
    if (pastedFiles.length === 0 && e.clipboardData.files && e.clipboardData.files.length > 0) {
      pastedFiles = Array.from(e.clipboardData.files).map((file, i) => {
        if (file.type.startsWith('image/')) {
          const ext = file.type === 'image/jpeg' ? 'jpg' : 'png';
          return new File([file], `pasted-image-${Date.now()}-${i}.${ext}`, { type: file.type });
        }
        return file;
      });
    }

    if (pastedFiles.length > 0) {
      e.preventDefault();
      addFiles(pastedFiles);
    }
  });

  // ── File management ────────────────────────────────────────────────────────
  function addFiles(newFiles) {
    const allowed = ['application/pdf', 'image/png', 'image/jpeg'];
    const MAX_MB = 50;

    newFiles.forEach(f => {
      if (!allowed.includes(f.type) && !f.name.match(/\.(pdf|png|jpg|jpeg)$/i)) {
        showToast(`'${f.name}' is not a supported file type.`, 'error');
        return;
      }
      if (f.size > MAX_MB * 1024 * 1024) {
        showToast(`'${f.name}' exceeds 50 MB limit.`, 'error');
        return;
      }
      if (!selectedFiles.find(x => x.name === f.name && x.size === f.size)) {
        selectedFiles.push(f);
      }
    });

    renderFileList();
  }

  function removeFile(index) {
    selectedFiles.splice(index, 1);
    renderFileList();
  }

  function renderFileList() {
    if (selectedFiles.length === 0) {
      fileList.classList.add('d-none');
      actionRow.style.display = 'none !important';
      actionRow.classList.add('d-none');
      return;
    }

    fileList.classList.remove('d-none');
    actionRow.classList.remove('d-none');
    actionRow.style.removeProperty('display');

    const totalMB = (selectedFiles.reduce((s, f) => s + f.size, 0) / 1e6).toFixed(1);
    fileSummary.textContent = `${selectedFiles.length} file(s) · ${totalMB} MB total`;

    fileList.innerHTML = selectedFiles.map((f, i) => {
      const icon = f.name.endsWith('.pdf') ? 'bi-file-earmark-pdf-fill' : 'bi-file-earmark-image-fill';
      const size = (f.size / 1024).toFixed(0) + ' KB';
      return `
        <div class="file-item">
          <i class="bi ${icon} file-item-icon"></i>
          <span class="file-item-name">${escHtml(f.name)}</span>
          <span class="file-item-meta">${size}</span>
          <button class="file-item-remove" onclick="removeFile(${i})" title="Remove">
            <i class="bi bi-x-lg"></i>
          </button>
        </div>`;
    }).join('');
  }

  // Expose so inline onclick works
  window.removeFile = removeFile;

  clearBtn.addEventListener('click', () => {
    selectedFiles = [];
    fileInput.value = '';
    renderFileList();
  });

  // ── Upload ─────────────────────────────────────────────────────────────────
  uploadForm.addEventListener('submit', async e => {
    e.preventDefault();
    if (selectedFiles.length === 0) {
      showToast('Please select at least one file.', 'warning');
      return;
    }

    setLoading(true);

    const formData = new FormData();
    selectedFiles.forEach(f => formData.append('files', f));

    try {
      const resp = await fetch('/api/upload', { method: 'POST', body: formData });
      const data = await resp.json();

      if (!resp.ok) {
        throw new Error(data.detail || 'Upload failed');
      }

      showToast(`Upload successful! ${data.total_pages} page(s) to process.`, 'success');

      // Redirect to processing page
      setTimeout(() => {
        window.location.href = `/processing/${data.job_id}`;
      }, 800);

    } catch (err) {
      showToast(err.message, 'error');
      setLoading(false);
    }
  });

  function setLoading(loading) {
    const text = uploadBtn.querySelector('.btn-text');
    const spinner = uploadBtn.querySelector('.spinner-border');
    uploadBtn.disabled = loading;
    text.classList.toggle('d-none', loading);
    spinner.classList.toggle('d-none', !loading);
  }

  function escHtml(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
})();
