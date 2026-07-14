/**
 * processing.js — SSE-based real-time progress tracking.
 * JOB_ID is injected by the Jinja2 template.
 */
(function () {
  'use strict';

  const progressBar = document.getElementById('progressBar');
  const progressLabel = document.getElementById('progressLabel');
  const progressCount = document.getElementById('progressCount');
  const statusLog = document.getElementById('statusLog');
  const statsRow = document.getElementById('statsRow');
  const statTotal = document.getElementById('statTotal');
  const statValid = document.getElementById('statValid');
  const actionDiv = document.getElementById('actionDiv');
  const cancelDiv = document.getElementById('cancelDiv');
  const cancelBtn = document.getElementById('cancelBtn');
  const errorDiv = document.getElementById('errorDiv');
  const errorMsg = document.getElementById('errorMsg');

  function addLog(message, type = '') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const time = new Date().toLocaleTimeString();
    entry.innerHTML = `<span class="text-muted me-2">[${time}]</span>${escHtml(message)}`;
    statusLog.appendChild(entry);
    statusLog.scrollTop = statusLog.scrollHeight;
  }

  function setProgress(processed, total) {
    const pct = total > 0 ? Math.round((processed / total) * 100) : 0;
    progressBar.style.width = pct + '%';
    progressBar.setAttribute('aria-valuenow', pct);
    progressCount.textContent = `${processed} / ${total}`;
  }

  function onComplete(data) {
    progressBar.style.width = '100%';
    progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped');
    progressLabel.textContent = 'Processing complete!';

    statTotal.textContent = data.total_records ?? '—';
    statValid.textContent = data.valid_records ?? '—';
    statsRow.classList.remove('d-none');
    actionDiv.classList.remove('d-none');
    if (cancelDiv) cancelDiv.classList.add('d-none');

    addLog(`✓ Done: ${data.total_records} records extracted, ${data.valid_records} valid.`, 'success');
    showToast('Processing complete! Review your data.', 'success');
  }

  function onError(message) {
    errorDiv.classList.remove('d-none');
    if (cancelDiv) cancelDiv.classList.add('d-none');
    errorMsg.textContent = message;
    progressLabel.textContent = 'Error occurred';
    addLog('✗ ' + message, 'error');
    showToast('Processing error: ' + message, 'error');
  }

  // Start SSE connection after a short delay to allow the page to render
  function startStream() {
    addLog('Connecting to processing pipeline...', '');

    // First, trigger the processing endpoint
    fetch(`/api/process/${JOB_ID}`, { method: 'POST' })
      .then(r => r.json())
      .then(() => {
        addLog('Pipeline ready. Starting OCR...', '');

        const es = new EventSource(`/api/process/${JOB_ID}/stream`);

        es.onmessage = function (event) {
          let data;
          try { data = JSON.parse(event.data); } catch { return; }

          const type = data.type;
          const msg = data.message || '';

          if (type === 'progress') {
            setProgress(data.processed, data.total);
            progressLabel.textContent = msg;
            addLog(msg, data.ocr_error ? 'warn' : '');

          } else if (type === 'complete') {
            es.close();
            onComplete(data);

          } else if (type === 'error') {
            es.close();
            onError(msg);
          }
        };

        es.onerror = function () {
          // SSE closed after complete — normal behaviour
          es.close();
        };
      })
      .catch(err => onError('Failed to start pipeline: ' + err.message));
  }

  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(startStream, 300);

    if (cancelBtn) {
      cancelBtn.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to cancel processing? All progress will be lost.')) return;
        
        cancelBtn.disabled = true;
        cancelBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Cancelling...';
        
        try {
          await fetch(`/api/process/${JOB_ID}`, { method: 'DELETE' });
          showToast('Processing cancelled.', 'info');
          addLog('Processing cancelled by user.', 'warn');
          setTimeout(() => { window.location.href = '/'; }, 1500);
        } catch (err) {
          showToast('Failed to cancel: ' + err.message, 'error');
          cancelBtn.disabled = false;
          cancelBtn.innerHTML = '<i class="bi bi-x-circle me-1"></i>Cancel Processing';
        }
      });
    }
  });

  function escHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
})();
