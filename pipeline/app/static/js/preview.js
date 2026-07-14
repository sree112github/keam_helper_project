/**
 * preview.js — Server-side paginated table with search, sort, inline edit, and insert.
 * JOB_ID is injected by the Jinja2 template.
 */
(function () {
  'use strict';

  // ── State ──────────────────────────────────────────────────────────────────
  let state = {
    page: 1,
    perPage: 25,
    search: '',
    sortBy: 'course',
    sortOrder: 'asc',
    totalRecords: 0,
    stats: null,
  };

  // ── DOM refs ───────────────────────────────────────────────────────────────
  const tableBody = document.getElementById('tableBody');
  const searchInput = document.getElementById('searchInput');
  const sortField = document.getElementById('sortField');
  const sortOrderBtn = document.getElementById('sortOrderBtn');
  const sortIcon = document.getElementById('sortIcon');
  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');
  const paginationInfo = document.getElementById('paginationInfo');
  const insertBtn = document.getElementById('insertBtn');
  
  const globalYearInput = document.getElementById('globalYear');
  const globalRoundInput = document.getElementById('globalRound');

  const editModal = new bootstrap.Modal(document.getElementById('editModal'));
  const insertModal = new bootstrap.Modal(document.getElementById('insertModal'));
  const resultModal = new bootstrap.Modal(document.getElementById('resultModal'));

  // ── Fetch & render ─────────────────────────────────────────────────────────
  async function loadPage() {
    const params = new URLSearchParams({
      page: state.page,
      per_page: state.perPage,
      sort_by: state.sortBy,
      sort_order: state.sortOrder,
    });
    if (state.search) params.set('search', state.search);

    try {
      const resp = await fetch(`/api/preview/${JOB_ID}?${params}`);
      if (!resp.ok) throw new Error((await resp.json()).detail || 'Load failed');
      const data = await resp.json();

      state.totalRecords = data.total;
      state.stats = data.stats;
      state.records = data.records; // save for edit

      renderStats(data.stats);
      renderTable(data.records);
      renderPagination(data.total, data.page, data.total_pages);
      insertBtn.disabled = data.stats.valid === 0 || data.stats.govt_records === 0;

    } catch (err) {
      tableBody.innerHTML = `<tr><td colspan="10" class="text-center py-4 text-danger">Error: ${escHtml(err.message)}</td></tr>`;
      showToast(err.message, 'error');
    }
  }

  function renderStats(stats) {
    document.querySelector('#chipTotal span').textContent = stats.total;
    document.querySelector('#chipValid span').textContent = stats.valid;
    document.querySelector('#chipInvalid span').textContent = stats.invalid;
    document.querySelector('#chipNew span').textContent = stats.new_records;
    document.querySelector('#chipUpdate span').textContent = stats.update_records;
  }

  let currentRankCategories = [];

  // ── Helper to collect all rank categories in the dataset ─────────────────
  function getUniqueRankCategories(records) {
    const cats = new Set();
    records.forEach(r => {
      if (r.ranks) {
        Object.keys(r.ranks).forEach(k => cats.add(k));
      }
    });

    // Exact order requested by user, plus any extra categories appended at the end
    const ORDER = ["SM", "EZ", "MU", "BH", "LA", "DV", "VK", "BX", "KN", "KU", "SC", "ST", "EW"];
    
    return Array.from(cats).sort((a, b) => {
      const idxA = ORDER.indexOf(a);
      const idxB = ORDER.indexOf(b);
      
      if (idxA !== -1 && idxB !== -1) return idxA - idxB; // Both in ORDER
      if (idxA !== -1) return -1;                         // Only A in ORDER
      if (idxB !== -1) return 1;                          // Only B in ORDER
      return a.localeCompare(b);                          // Neither in ORDER
    });
  }

  function renderHeader(categories) {
    const header = document.getElementById('tableHeader');
    if (!header) return;

    const rankHeaders = categories.map(cat => `
      <th class="text-end" style="width: 80px;">${escHtml(cat)}</th>
    `).join('');

    header.innerHTML = `
      <tr>
        <th class="sticky-col-idx">#</th>
        <th class="sticky-col-code">Code</th>
        <th style="min-width: 250px;">College Name</th>
        <th style="width: 70px;">Type</th>
        <th style="min-width: 200px;">Course</th>
        ${rankHeaders}
        <th style="min-width: 120px;">Other Categories</th>
        <th style="width: 85px;">Year</th>
        <th style="min-width: 150px;">Round</th>
        <th style="width: 90px;">Status</th>
        <th style="width: 60px;">Valid</th>
        <th style="width: 80px;">Actions</th>
      </tr>
    `;
  }

  function renderTable(records) {
    if (!records.length) {
      tableBody.innerHTML = `<tr><td colspan="15" class="text-center py-5 text-muted">
        <i class="bi bi-inbox fs-2 d-block mb-2"></i>No records found.
      </td></tr>`;
      return;
    }

    currentRankCategories = getUniqueRankCategories(records);
    renderHeader(currentRankCategories);

    tableBody.innerHTML = records.map(r => {
      const cName = r.college_name ?? r.name ?? '';
      const cType = r.college_type ?? r.type ?? 'G';

      const statusBadge = r.db_status === 'update'
        ? `<span class="badge-update">UPDATE</span>`
        : `<span class="badge-new">NEW</span>`;

      const validIcon = r.is_valid
        ? `<i class="bi bi-check-circle-fill badge-valid" title="Valid"></i>`
        : `<i class="bi bi-x-circle-fill badge-invalid"
              title="${escHtml(r.validation_errors.join('\n'))}"
              data-bs-toggle="tooltip" data-bs-placement="left"></i>`;

      const rankCells = currentRankCategories.map(cat => {
        const val = r.ranks && r.ranks[cat] !== undefined && r.ranks[cat] !== null ? r.ranks[cat] : '';
        return `
          <td>
            <input type="number" 
                   class="excel-cell-input cell-rank-input text-end" 
                   data-category="${escHtml(cat)}" 
                   value="${escHtml(val)}" 
                   placeholder="—"
                   data-original-val="${escHtml(val)}">
          </td>
        `;
      }).join('');

      return `
        <tr class="${r.is_valid ? '' : 'invalid'}" data-idx="${r.index}">
          <td class="sticky-col-idx text-muted small">${r.index + 1}</td>
          <td class="sticky-col-code">
            <input type="text" 
                   class="excel-cell-input cell-code text-center text-uppercase fw-semibold" 
                   value="${escHtml(r.college_code)}" 
                   maxlength="4"
                   data-original-val="${escHtml(r.college_code)}">
          </td>
          <td>
            <input type="text" 
                   class="excel-cell-input cell-name" 
                   value="${escHtml(cName)}"
                   data-original-val="${escHtml(cName)}">
          </td>
          <td class="text-center">
            <select class="excel-cell-select cell-type text-center fw-semibold text-info" data-original-val="${escHtml(cType)}">
              <option value="G" ${cType === 'G' ? 'selected' : ''}>G</option>
              <option value="S" ${cType === 'S' ? 'selected' : ''}>S</option>
            </select>
          </td>
          <td>
            <input type="text" 
                   class="excel-cell-input cell-course" 
                   value="${escHtml(r.course)}"
                   data-original-val="${escHtml(r.course)}">
          </td>
          
          ${rankCells}
          
          <td>
            <input type="text" 
                   class="excel-cell-input cell-other" 
                   value="${escHtml(r.other_categories ?? '')}"
                   placeholder="e.g. FW:123, SD:456"
                   data-original-val="${escHtml(r.other_categories ?? '')}">
          </td>
          
          <td>
            <input type="number" 
                   class="excel-cell-input cell-year text-center" 
                   value="${escHtml(getGlobalYear() ?? r.year ?? '')}" 
                   placeholder="2026"
                   data-original-val="${escHtml(getGlobalYear() ?? r.year ?? '')}">
          </td>
          <td>
            <input type="text" 
                   class="excel-cell-input cell-round text-start text-muted" 
                   value="${escHtml(getGlobalRound() ?? r.round ?? '')}" 
                   placeholder="Allotment Phase"
                   data-original-val="${escHtml(getGlobalRound() ?? r.round ?? '')}">
          </td>
          <td class="text-center text-nowrap">${statusBadge}</td>
          <td class="text-center cell-valid-icon">${validIcon}</td>
          <td class="text-center">
            <div class="d-flex justify-content-center gap-1">
              <button class="btn btn-xs btn-outline-secondary py-0 px-1" onclick="openEdit(${r.index})" title="Edit JSON">
                <i class="bi bi-code-slash" style="font-size: 11px;"></i>
              </button>
              <button class="btn btn-xs btn-outline-danger py-0 px-1" onclick="deleteRecord(${r.index})" title="Delete">
                <i class="bi bi-trash" style="font-size: 11px;"></i>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    // Re-bind tooltips
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el =>
      new bootstrap.Tooltip(el)
    );

    // Bind event listeners to the inline inputs
    bindExcelEvents();
  }

  function bindExcelEvents() {
    const inputs = tableBody.querySelectorAll('.excel-cell-input, .excel-cell-select');
    
    inputs.forEach(input => {
      // Store original value on focus if not already set
      input.addEventListener('focus', () => {
        if (!input.hasAttribute('data-original-val')) {
          input.setAttribute('data-original-val', input.value);
        }
      });

      // Save on blur
      input.addEventListener('blur', () => {
        handleCellSave(input);
      });

      // Keyboard navigation
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          input.blur();
          
          // Move to cell below
          const cell = input.closest('td');
          const row = input.closest('tr');
          const colIndex = Array.from(cell.parentNode.children).indexOf(cell);
          const nextRow = row.nextElementSibling;
          if (nextRow) {
            const nextCell = nextRow.children[colIndex];
            const nextInput = nextCell ? nextCell.querySelector('.excel-cell-input, .excel-cell-select') : null;
            if (nextInput) nextInput.focus();
          }
        }
        
        // Navigation keys with Alt
        if (e.altKey) {
          const cell = input.closest('td');
          if (!cell) return;
          const row = input.closest('tr');
          const colIndex = Array.from(cell.parentNode.children).indexOf(cell);
          
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            const nextRow = row.nextElementSibling;
            if (nextRow) {
              const nextCell = nextRow.children[colIndex];
              const nextInput = nextCell ? nextCell.querySelector('.excel-cell-input, .excel-cell-select') : null;
              if (nextInput) nextInput.focus();
            }
          } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            const prevRow = row.previousElementSibling;
            if (prevRow) {
              const prevCell = prevRow.children[colIndex];
              const prevInput = prevCell ? prevCell.querySelector('.excel-cell-input, .excel-cell-select') : null;
              if (prevInput) prevInput.focus();
            }
          } else if (e.key === 'ArrowLeft') {
            e.preventDefault();
            const prevCell = cell.previousElementSibling;
            const prevInput = prevCell ? prevCell.querySelector('.excel-cell-input, .excel-cell-select') : null;
            if (prevInput) prevInput.focus();
          } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            const nextCell = cell.nextElementSibling;
            const nextInput = nextCell ? nextCell.querySelector('.excel-cell-input, .excel-cell-select') : null;
            if (nextInput) nextInput.focus();
          }
        }
      });
    });
  }

  async function handleCellSave(input) {
    const originalVal = input.getAttribute('data-original-val');
    const newVal = input.value;
    
    // Only save if value changed
    if (originalVal === newVal) return;
    
    const row = input.closest('tr');
    if (!row) return;
    
    const idx = parseInt(row.getAttribute('data-idx'));
    
    // Visual indicators
    row.classList.add('row-saving');
    
    const yearVal = row.querySelector('.cell-year').value;
    const roundVal = row.querySelector('.cell-round').value;
    const codeVal = row.querySelector('.cell-code').value;
    const nameVal = row.querySelector('.cell-name').value;
    const typeVal = row.querySelector('.cell-type').value;
    const courseVal = row.querySelector('.cell-course').value;
    const otherVal = row.querySelector('.cell-other').value;
    
    const ranks = {};
    row.querySelectorAll('.cell-rank-input').forEach(rankInput => {
      const cat = rankInput.getAttribute('data-category');
      const val = rankInput.value.trim();
      ranks[cat] = val === '' ? null : parseInt(val);
    });
    
    const payload = {
      year: parseInt(yearVal) || null,
      round: roundVal.trim(),
      college_code: codeVal.trim().toUpperCase(),
      college_name: nameVal.trim(),
      college_type: typeVal,
      course: courseVal.trim(),
      ranks,
      other_categories: otherVal.trim(),
    };
    
    try {
      const resp = await fetch(`/api/preview/${JOB_ID}/records/${idx}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) throw new Error((await resp.json()).detail || 'Update failed');
      const updatedRecord = await resp.json();
      
      // Update original value attribute
      input.setAttribute('data-original-val', newVal);
      
      // Remove saving state, add success flash
      row.classList.remove('row-saving');
      row.classList.add('row-saved-success');
      setTimeout(() => row.classList.remove('row-saved-success'), 1000);
      
      // Update validation errors display
      const validIconCell = row.querySelector('.cell-valid-icon');
      const existingTooltipEl = validIconCell.querySelector('[data-bs-toggle="tooltip"]');
      if (existingTooltipEl) {
        const tooltipInstance = bootstrap.Tooltip.getInstance(existingTooltipEl);
        if (tooltipInstance) tooltipInstance.dispose();
      }
      
      if (updatedRecord.is_valid) {
        row.classList.remove('invalid');
        validIconCell.innerHTML = `<i class="bi bi-check-circle-fill badge-valid" title="Valid"></i>`;
      } else {
        row.classList.add('invalid');
        const errorsEscaped = escHtml(updatedRecord.validation_errors.join('\n'));
        validIconCell.innerHTML = `<i class="bi bi-x-circle-fill badge-invalid"
              title="${errorsEscaped}"
              data-bs-toggle="tooltip" data-bs-placement="left"></i>`;
        new bootstrap.Tooltip(validIconCell.querySelector('[data-bs-toggle="tooltip"]'));
      }
      
      // Update stats in the background
      const statsResp = await fetch(`/api/preview/${JOB_ID}/stats`);
      if (statsResp.ok) {
        const statsData = await statsResp.json();
        state.stats = statsData;
        renderStats(statsData);
        insertBtn.disabled = statsData.valid === 0 || statsData.govt_records === 0;
      }
      
    } catch (err) {
      row.classList.remove('row-saving');
      showToast(err.message, 'error');
      // Revert input to original
      input.value = originalVal;
    }
  }

  function renderPagination(total, page, totalPages) {
    const from = total === 0 ? 0 : (page - 1) * state.perPage + 1;
    const to = Math.min(page * state.perPage, total);
    paginationInfo.textContent = `${from}–${to} of ${total}`;
    prevBtn.disabled = page <= 1;
    nextBtn.disabled = page >= totalPages;
  }

  // ── Controls ───────────────────────────────────────────────────────────────
  let searchTimer;
  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.search = searchInput.value.trim();
      state.page = 1;
      loadPage();
    }, 300);
  });

  sortField.addEventListener('change', () => {
    state.sortBy = sortField.value;
    state.page = 1;
    loadPage();
  });

  sortOrderBtn.addEventListener('click', () => {
    state.sortOrder = state.sortOrder === 'asc' ? 'desc' : 'asc';
    sortIcon.className = state.sortOrder === 'asc'
      ? 'bi bi-sort-alpha-down' : 'bi bi-sort-alpha-up-alt';
    state.page = 1;
    loadPage();
  });

  prevBtn.addEventListener('click', () => { state.page--; loadPage(); });
  nextBtn.addEventListener('click', () => { state.page++; loadPage(); });

  // ── Global Settings ────────────────────────────────────────────────────────
  function getGlobalYear() { return parseInt(globalYearInput.value) || null; }
  function getGlobalRound() { return globalRoundInput.value.trim() || null; }

  function initGlobals() {
    globalYearInput.value = localStorage.getItem('keamGlobalYear') || '2026';
    globalRoundInput.value = localStorage.getItem('keamGlobalRound') || 'First Phase Allotment';

    const saveAndRender = () => {
      localStorage.setItem('keamGlobalYear', globalYearInput.value);
      localStorage.setItem('keamGlobalRound', globalRoundInput.value);
      loadPage(); // Re-render to show updated fallbacks
    };

    globalYearInput.addEventListener('input', saveAndRender);
    globalRoundInput.addEventListener('input', saveAndRender);
  }

  // ── Edit record ────────────────────────────────────────────────────────────
  window.openEdit = async function (idx) {
    const record = state.records.find(r => r.index === idx);
    if (!record) { showToast('Record not found.', 'error'); return; }

    document.getElementById('editIdx').value = idx;
    document.getElementById('editYear').value = getGlobalYear() ?? record.year ?? '';
    document.getElementById('editRound').value = getGlobalRound() ?? record.round ?? '';
    document.getElementById('editCode').value = record.college_code ?? '';
    document.getElementById('editName').value = record.name ?? record.college_name ?? '';
    document.getElementById('editType').value = record.type ?? record.college_type ?? 'G';
    document.getElementById('editCourse').value = record.course ?? '';
    document.getElementById('editOther').value = record.other_categories ?? '';
    document.getElementById('editRanks').value = JSON.stringify(record.ranks ?? {}, null, 2);
    document.getElementById('editError').classList.add('d-none');

    editModal.show();
  };

  document.getElementById('saveEditBtn').addEventListener('click', async () => {
    const idx = parseInt(document.getElementById('editIdx').value);
    const ranksRaw = document.getElementById('editRanks').value.trim();
    let ranks;
    try {
      ranks = JSON.parse(ranksRaw);
    } catch (e) {
      document.getElementById('editError').textContent = 'Invalid ranks JSON: ' + e.message;
      document.getElementById('editError').classList.remove('d-none');
      return;
    }

    const payload = {
      year: parseInt(document.getElementById('editYear').value) || null,
      round: document.getElementById('editRound').value.trim(),
      college_code: document.getElementById('editCode').value.trim().toUpperCase(),
      college_name: document.getElementById('editName').value.trim(),
      college_type: document.getElementById('editType').value,
      course: document.getElementById('editCourse').value.trim(),
      ranks,
      other_categories: document.getElementById('editOther').value.trim(),
    };

    try {
      const resp = await fetch(`/api/preview/${JOB_ID}/records/${idx}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) throw new Error((await resp.json()).detail || 'Update failed');
      editModal.hide();
      showToast('Record updated.', 'success');
      loadPage();
    } catch (err) {
      document.getElementById('editError').textContent = err.message;
      document.getElementById('editError').classList.remove('d-none');
    }
  });

  // ── Delete record ──────────────────────────────────────────────────────────
  window.deleteRecord = async function (idx) {
    if (!confirm('Delete this record from the batch?')) return;
    try {
      const resp = await fetch(`/api/preview/${JOB_ID}/records/${idx}`, { method: 'DELETE' });
      if (!resp.ok && resp.status !== 204) throw new Error('Delete failed');
      showToast('Record deleted.', 'success');
      loadPage();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  // ── Insert flow ────────────────────────────────────────────────────────────
  insertBtn.addEventListener('click', async () => {
    const stats = state.stats;
    if (!stats) return;
    document.getElementById('insertSummary').innerHTML =
      `Valid records:    ${stats.valid}\n` +
      `Gov't records:    ${stats.govt_records}\n` +
      `New to insert:    ${stats.new_records}\n` +
      `Will update:      ${stats.update_records}\n` +
      `Will skip (S):    ${stats.non_govt_records}`;
      
    // Fetch all records for the JSON preview
    document.getElementById('jsonPreviewArea').textContent = "Generating payload preview...";
    try {
      const resp = await fetch(`/api/preview/${JOB_ID}?per_page=1000`);
      const data = await resp.json();
      
      const globalYear = getGlobalYear();
      const globalRound = getGlobalRound();

      // The backend insert.py filters to valid & G-colleges and applies fallbacks
      const validRecords = data.records.filter(r => r.college_type === 'G');
      
      const finalJson = validRecords.map(r => ({
        year: globalYear ?? r.year ?? null,
        round: globalRound ?? r.round ?? null,
        course: r.course,
        college_code: r.college_code,
        college_name: r.college_name,
        college_type: r.college_type,
        ranks: r.ranks,
        other_categories: r.other_categories
      }));

      document.getElementById('jsonPreviewArea').textContent = JSON.stringify(finalJson, null, 2);
    } catch (e) {
      document.getElementById('jsonPreviewArea').textContent = "Failed to load JSON preview.";
    }

    insertModal.show();
  });

  document.getElementById('confirmInsertBtn').addEventListener('click', async () => {
    const btn = document.getElementById('confirmInsertBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Inserting...';

    try {
      const payload = {
        global_year: getGlobalYear(),
        global_round: getGlobalRound()
      };

      const resp = await fetch(`/api/insert/${JOB_ID}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Insert failed');

      insertModal.hide();

      document.getElementById('resultBody').innerHTML = `
        <div class="text-center mb-3">
          <i class="bi bi-check-circle-fill text-success fs-1"></i>
        </div>
        <p class="fw-semibold">${escHtml(data.message)}</p>
        <ul class="list-unstyled">
          <li><i class="bi bi-plus-circle-fill text-success me-2"></i>${data.inserted} new records inserted</li>
          <li><i class="bi bi-arrow-repeat text-warning me-2"></i>${data.updated} records updated</li>
          <li><i class="bi bi-skip-forward-fill text-muted me-2"></i>${data.skipped} records skipped (non-govt)</li>
          ${data.errors.length ? `<li class="text-danger mt-2"><i class="bi bi-exclamation-triangle me-1"></i>${escHtml(data.errors.join(', '))}</li>` : ''}
        </ul>`;

      resultModal.show();
      showToast('Data inserted successfully!', 'success');

    } catch (err) {
      insertModal.hide();
      showToast('Insert failed: ' + err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-database-fill-add me-2"></i>Insert Now';
    }
  });

  // ── Init ───────────────────────────────────────────────────────────────────
  function escHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');
  }

  initGlobals();
  loadPage();
})();
