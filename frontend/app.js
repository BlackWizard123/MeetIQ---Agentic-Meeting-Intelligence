// ── Config ────────────────────────────────────────────────────────────────
const API = 'http://localhost:8000/api';

// ── State ─────────────────────────────────────────────────────────────────
let state = {
  rawMemo: null,
  rawTasks: null,
  rawMeetings: null,
  confirmedMemo: null,
  confirmedTasks: null,
  meetingId: null,
  uploadedFile: null,
};

// ── Screens ───────────────────────────────────────────────────────────────
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

function showUploadScreen() {
  showScreen('uploadScreen');
  document.querySelectorAll('.history-item').forEach(i => i.classList.remove('active'));
}

// ── Toast ─────────────────────────────────────────────────────────────────
function showToast(msg, type = '') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show ' + type;
  setTimeout(() => t.className = 'toast', 3000);
}

// ── History Sidebar ───────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const res = await fetch(`${API}/history`);
    const items = await res.json();
    renderHistory(items);
  } catch (e) {
    console.error('History load failed', e);
  }
}

function renderHistory(items) {
  const list = document.getElementById('historyList');
  if (!items.length) {
    list.innerHTML = '<div class="history-empty">No meetings yet</div>';
    return;
  }
  list.innerHTML = items.slice().reverse().map(item => `
    <div class="history-item" onclick="loadThread('${item.id}', this)">
      <div class="history-item-title">${item.title || 'Untitled Meeting'}</div>
      <div class="history-item-date">${item.date || ''}</div>
      <div class="history-item-people">${(item.attendees || []).join(', ')}</div>
    </div>
  `).join('');
}

// ── File Upload ───────────────────────────────────────────────────────────
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');

dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
dropzone.addEventListener('drop', e => {
  e.preventDefault();
  dropzone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelect(file);
});
dropzone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) handleFileSelect(fileInput.files[0]);
});

function handleFileSelect(file) {
  if (!file.name.endsWith('.txt')) {
    showToast('Please select a .txt file', 'error');
    return;
  }
  state.uploadedFile = file;
  document.getElementById('fileName').textContent = '📄 ' + file.name;
  document.getElementById('processBtn').disabled = false;
}

// ── Process Transcript ────────────────────────────────────────────────────
async function processTranscript() {
  if (!state.uploadedFile) return;

  const loader = document.getElementById('loader');
  const btn = document.getElementById('processBtn');
  btn.disabled = true;
  loader.classList.remove('hidden');

  const labels = [
    'Analyzing transcript…',
    'Extracting memo…',
    'Identifying tasks…',
    'Suggesting meetings…',
  ];
  let li = 0;
  const labelEl = document.getElementById('loaderLabel');
  const labelInterval = setInterval(() => {
    labelEl.textContent = labels[Math.min(li++, labels.length - 1)];
  }, 1800);

  try {
    const formData = new FormData();
    formData.append('file', state.uploadedFile);

    const res = await fetch(`${API}/process-transcript`, { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Processing failed');
    }

    const data = await res.json();
    state.rawMemo     = data.memo;
    state.rawTasks    = data.tasks;
    state.rawMeetings = data.meetings;

    populateMemo(data.memo);
    populateTasks(data.tasks);
    populateMeetings(data.meetings);

    showScreen('reviewScreen');
    showPanel('memoPanel', 1);
    showToast('Transcript processed!', 'success');
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
    btn.disabled = false;
  } finally {
    clearInterval(labelInterval);
    loader.classList.add('hidden');
  }
}

// ── Step Navigation ───────────────────────────────────────────────────────
function showPanel(panelId, stepNum) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById(panelId).classList.add('active');

  document.querySelectorAll('.step').forEach((s, i) => {
    s.classList.remove('active', 'done');
    if (i + 1 < stepNum) s.classList.add('done');
    if (i + 1 === stepNum) s.classList.add('active');
  });
}

// ── Memo ──────────────────────────────────────────────────────────────────
function populateMemo(memo) {
  document.getElementById('memoTitle').value     = memo.title || '';
  document.getElementById('memoDate').value      = memo.date || '';
  document.getElementById('memoAttendees').value = (memo.attendees || []).join(', ');
  document.getElementById('memoSummary').value   = memo.summary || '';
  document.getElementById('memoDecisions').value = (memo.decisions || []).join('\n');
  document.getElementById('memoBlockers').value  = (memo.blockers || []).join('\n');
  document.getElementById('memoNextSteps').value = (memo.next_steps || []).join('\n');
}

function resetMemo() {
  if (state.rawMemo) populateMemo(state.rawMemo);
  showToast('Memo reset to original');
}

function getMemoFromForm() {
  return {
    title:      document.getElementById('memoTitle').value.trim(),
    date:       document.getElementById('memoDate').value.trim(),
    attendees:  document.getElementById('memoAttendees').value.split(',').map(s => s.trim()).filter(Boolean),
    summary:    document.getElementById('memoSummary').value.trim(),
    decisions:  document.getElementById('memoDecisions').value.split('\n').map(s => s.trim()).filter(Boolean),
    blockers:   document.getElementById('memoBlockers').value.split('\n').map(s => s.trim()).filter(Boolean),
    next_steps: document.getElementById('memoNextSteps').value.split('\n').map(s => s.trim()).filter(Boolean),
  };
}

function confirmMemo() {
  state.confirmedMemo = getMemoFromForm();
  showPanel('tasksPanel', 2);
  showToast('Memo confirmed ✓', 'success');
}

// ── Tasks ─────────────────────────────────────────────────────────────────
function populateTasks(tasks) {
  const grid = document.getElementById('tasksGrid');
  grid.innerHTML = '';
  tasks.forEach(task => grid.appendChild(makeTaskCard(task)));
}

function makeTaskCard(task) {
  const card = document.createElement('div');
  card.className = 'card';
  card.dataset.id = task.id;

  const badge = task.priority || 'Medium';
  const badgeClass = { High: 'badge-high', Medium: 'badge-medium', Low: 'badge-low' }[badge] || 'badge-medium';

  card.innerHTML = `
    <div class="card-top">
      <span class="card-badge ${badgeClass}">${badge}</span>
      <button class="btn-danger" onclick="removeCard(this, 'tasksGrid')">✕</button>
    </div>
    <div class="card-field">
      <label>TASK TITLE</label>
      <input class="card-input" value="${esc(task.title)}" placeholder="Task title" />
    </div>
    <div class="card-row">
      <div class="card-field">
        <label>ASSIGNEE</label>
        <input class="card-input" value="${esc(task.assignee)}" placeholder="Name" />
      </div>
      <div class="card-field">
        <label>DUE DATE</label>
        <input class="card-input" value="${esc(task.due_date)}" placeholder="YYYY-MM-DD" />
      </div>
    </div>
    <div class="card-field">
      <label>PRIORITY</label>
      <select class="card-select" onchange="updateBadge(this)">
        <option ${badge==='High'?'selected':''}>High</option>
        <option ${badge==='Medium'?'selected':''}>Medium</option>
        <option ${badge==='Low'?'selected':''}>Low</option>
      </select>
    </div>
    <div class="card-field">
      <label>NOTES</label>
      <textarea class="card-textarea" rows="2" placeholder="Additional context">${esc(task.notes || '')}</textarea>
    </div>
  `;
  return card;
}

function addTask() {
  const task = { id: 't_' + Date.now(), title: '', assignee: '', due_date: 'TBD', priority: 'Medium', notes: '' };
  document.getElementById('tasksGrid').appendChild(makeTaskCard(task));
}

function updateBadge(select) {
  const card = select.closest('.card');
  const badge = card.querySelector('.card-badge');
  const val = select.value;
  badge.className = 'card-badge ' + ({ High: 'badge-high', Medium: 'badge-medium', Low: 'badge-low' }[val] || 'badge-medium');
  badge.textContent = val;
}

function getTasksFromGrid() {
  return Array.from(document.querySelectorAll('#tasksGrid .card')).map((card, i) => {
    const inputs = card.querySelectorAll('.card-input');
    const select = card.querySelector('.card-select');
    const textarea = card.querySelector('.card-textarea');
    return {
      id: card.dataset.id || ('t_' + i),
      title:    inputs[0].value.trim(),
      assignee: inputs[1].value.trim(),
      due_date: inputs[2].value.trim() || 'TBD',
      priority: select.value,
      notes:    textarea.value.trim(),
    };
  });
}

function confirmTasks() {
  state.confirmedTasks = getTasksFromGrid();
  showPanel('meetingsPanel', 3);
  showToast('Tasks confirmed ✓', 'success');
}

// ── Meetings ──────────────────────────────────────────────────────────────
function populateMeetings(meetings) {
  const grid = document.getElementById('meetingsGrid');
  grid.innerHTML = '';
  meetings.forEach(mtg => grid.appendChild(makeMeetingCard(mtg)));
}

function makeMeetingCard(mtg) {
  const card = document.createElement('div');
  card.className = 'card';
  card.dataset.id = mtg.id;

  card.innerHTML = `
    <div class="card-top">
      <span class="card-badge badge-meeting">MEETING</span>
      <button class="btn-danger" onclick="removeCard(this, 'meetingsGrid')">✕</button>
    </div>
    <div class="card-field">
      <label>MEETING TITLE</label>
      <input class="card-input" value="${esc(mtg.title)}" placeholder="Meeting title" />
    </div>
    <div class="card-field">
      <label>PURPOSE</label>
      <textarea class="card-textarea" rows="2" placeholder="Why is this meeting needed?">${esc(mtg.purpose || '')}</textarea>
    </div>
    <div class="card-row">
      <div class="card-field">
        <label>DATE</label>
        <input class="card-input" value="${esc(mtg.suggested_date)}" placeholder="YYYY-MM-DD" />
      </div>
      <div class="card-field">
        <label>DURATION (MIN)</label>
        <input class="card-input" type="number" value="${mtg.duration_mins || 30}" />
      </div>
    </div>
    <div class="card-field">
      <label>RECIPIENTS</label>
      <input class="card-input" value="${esc((mtg.recipients||[]).join(', '))}" placeholder="Comma separated names" />
    </div>
    <div class="card-field">
      <label>AGENDA</label>
      <textarea class="card-textarea" rows="2" placeholder="Agenda items">${esc(mtg.agenda || '')}</textarea>
    </div>
  `;
  return card;
}

function addMeeting() {
  const mtg = { id: 'm_' + Date.now(), title: '', purpose: '', suggested_date: 'TBD', duration_mins: 30, recipients: [], agenda: '' };
  document.getElementById('meetingsGrid').appendChild(makeMeetingCard(mtg));
}

function getMeetingsFromGrid() {
  return Array.from(document.querySelectorAll('#meetingsGrid .card')).map((card, i) => {
    const inputs  = card.querySelectorAll('.card-input');
    const textareas = card.querySelectorAll('.card-textarea');
    return {
      id:             card.dataset.id || ('m_' + i),
      title:          inputs[0].value.trim(),
      purpose:        textareas[0].value.trim(),
      suggested_date: inputs[1].value.trim() || 'TBD',
      duration_mins:  parseInt(inputs[2].value) || 30,
      recipients:     inputs[3].value.split(',').map(s => s.trim()).filter(Boolean),
      agenda:         textareas[1].value.trim(),
    };
  });
}

// ── Schedule All ──────────────────────────────────────────────────────────
async function scheduleAll() {
  const btn = document.getElementById('scheduleAllBtn');
  btn.textContent = 'Scheduling…';
  btn.disabled = true;

  const memo     = state.confirmedMemo || getMemoFromForm();
  const tasks    = state.confirmedTasks || getTasksFromGrid();
  const meetings = getMeetingsFromGrid();

  try {
    // Step 1: Finalize (saves to JSON + updates Sheets)
    const finalizeRes = await fetch(`${API}/finalize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ memo, tasks, meetings }),
    });
    if (!finalizeRes.ok) throw new Error('Finalize failed');
    const finalizeData = await finalizeRes.json();
    state.meetingId = finalizeData.meeting_id;

    // Step 2: Schedule to Google Calendar + Tasks
    const scheduleRes = await fetch(`${API}/schedule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ meeting_id: state.meetingId, tasks, meetings }),
    });
    if (!scheduleRes.ok) throw new Error('Schedule failed');

    // Show success bar
    const bar = document.getElementById('finalizeBar');
    bar.style.display = 'flex';
    if (finalizeData.sheet_url) {
      document.getElementById('sheetLink').href = finalizeData.sheet_url;
    }

    showToast('All scheduled successfully! ✓', 'success');
    loadHistory(); // Refresh sidebar

  } catch (e) {
    showToast('Error: ' + e.message, 'error');
    btn.textContent = 'Schedule All ↗';
    btn.disabled = false;
  } finally {
    btn.textContent = 'Schedule All ↗';
    btn.disabled = false;
  }
}

// ── Thread View ───────────────────────────────────────────────────────────
async function loadThread(meetingId, el) {
  document.querySelectorAll('.history-item').forEach(i => i.classList.remove('active'));
  el.classList.add('active');

  showScreen('threadScreen');
  document.getElementById('threadTitle').textContent = 'Loading briefing…';
  document.getElementById('threadGrid').innerHTML = '<div style="padding:20px;color:var(--text3);font-family:var(--mono);font-size:13px;">Generating briefing…</div>';

  try {
    const res = await fetch(`${API}/history/${meetingId}`);
    if (!res.ok) throw new Error('Failed to load briefing');
    const data = await res.json();

    const meta = data.meta || {};
    document.getElementById('threadTitle').textContent = meta.title || 'Meeting Briefing';
    document.getElementById('threadMeta').innerHTML = `
      <div class="thread-meta-item">
        <span class="thread-meta-label">DATE</span>
        <span class="thread-meta-value">${meta.date || '—'}</span>
      </div>
      <div class="thread-meta-item">
        <span class="thread-meta-label">ATTENDEES</span>
        <span class="thread-meta-value">${(meta.attendees || []).join(', ') || '—'}</span>
      </div>
    `;

    renderBriefing(data.briefing);
  } catch (e) {
    document.getElementById('threadGrid').innerHTML = `<div style="color:var(--red);padding:20px;">${e.message}</div>`;
  }
}

function renderBriefing(b) {
  if (!b) return;

  const sections = [
    { title: 'What Was Discussed',  key: 'what_was_discussed',  type: 'text' },
    { title: 'What Was Decided',    key: 'what_was_decided',    type: 'list' },
    { title: 'What to Follow Up',   key: 'what_to_follow_up',   type: 'list' },
    { title: 'Open Questions',      key: 'open_questions',      type: 'list' },
    { title: 'Suggested Agenda',    key: 'suggested_agenda',    type: 'list' },
  ];

  document.getElementById('threadGrid').innerHTML = sections.map(sec => {
    const val = b[sec.key];
    if (!val || (Array.isArray(val) && !val.length)) return '';
    const content = sec.type === 'text'
      ? `<p>${val}</p>`
      : `<ul>${(val || []).map(v => `<li>${v}</li>`).join('')}</ul>`;
    return `
      <div class="thread-card">
        <div class="thread-card-title">${sec.title}</div>
        ${content}
      </div>
    `;
  }).join('');
}

// ── Helpers ───────────────────────────────────────────────────────────────
function removeCard(btn, gridId) {
  btn.closest('.card').remove();
}

function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// ── Init ──────────────────────────────────────────────────────────────────
loadHistory();