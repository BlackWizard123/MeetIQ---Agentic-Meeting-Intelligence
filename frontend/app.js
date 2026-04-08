const API = '/api';

let state = {
  projects:[], employees:[], selectedProjectId:null, selectedProjectName:'',
  rawMemo:null, rawTasks:null, rawMeetings:null,
  confirmedMemo:null, confirmedTasks:null,
  meetingId:null, uploadedFile:null,
};


// ── Theme System ──────────────────────────────────────────────────────────
const THEME_LABELS = { dark: 'Dark', light: 'Light', google: 'Google Workspace' };

function initTheme() {
  const saved = localStorage.getItem('meetiq-theme') || 'dark';
  applyTheme(saved, false);
}

function applyTheme(theme, save=true) {
  document.documentElement.setAttribute('data-theme', theme === 'dark' ? '' : theme);
  if (theme === 'dark') {
    document.documentElement.removeAttribute('data-theme');
  }

  // Update Google Sans for google theme
  document.body.style.fontFamily = theme === 'google'
    ? "'Google Sans', var(--sans)" : '';

  // Update active state
  ['dark','light','google'].forEach(t => {
    document.getElementById('theme-'+t)?.classList.toggle('active', t === theme);
  });

  // Update label
  const lbl = document.getElementById('currentThemeLabel');
  if (lbl) lbl.textContent = THEME_LABELS[theme] || theme;

  if (save) localStorage.setItem('meetiq-theme', theme);
}

function setTheme(theme) {
  applyTheme(theme);
  closeProfileMenu();
  showToast(`Theme: ${THEME_LABELS[theme]}`, 'success');
}

// ── Profile Menu ──────────────────────────────────────────────────────────
function toggleProfileMenu() {
  const menu = document.getElementById('profileMenu');
  const btn  = document.getElementById('profileBtn');
  const isOpen = menu.classList.contains('open');
  menu.classList.toggle('open', !isOpen);
  btn.classList.toggle('open', !isOpen);
  // Close theme submenu when closing main menu
  if (isOpen) {
    document.getElementById('themeSubmenu')?.classList.remove('open');
  }
}

function closeProfileMenu() {
  document.getElementById('profileMenu')?.classList.remove('open');
  document.getElementById('profileBtn')?.classList.remove('open');
  document.getElementById('themeSubmenu')?.classList.remove('open');
}

function toggleThemeSubmenu() {
  document.getElementById('themeSubmenu')?.classList.toggle('open');
}

function dummyAction(action) {
  closeProfileMenu();
  showToast(`${action} — coming soon`, '');
}

// Close menu when clicking outside
document.addEventListener('click', e => {
  const menu    = document.getElementById('profileMenu');
  const btn     = document.getElementById('profileBtn');
  if (menu && btn && !menu.contains(e.target) && !btn.contains(e.target)) {
    closeProfileMenu();
  }
});

// ── Init ──────────────────────────────────────────────────────────────────
async function init() {
  initTheme();
  await loadProjects();
  await loadHistory();
  showScreen('uploadScreen');
}

// ── Auto-expand textareas ─────────────────────────────────────────────────
function autoExpand(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 400) + 'px';
}
function autoExpandAll() {
  document.querySelectorAll('textarea').forEach(t => autoExpand(t));
}
document.addEventListener('input', e => { if (e.target.tagName === 'TEXTAREA') autoExpand(e.target); });

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
function showToast(msg, type='') {
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'toast show ' + type;
  setTimeout(() => t.className = 'toast', 3500);
}

// ── Projects ──────────────────────────────────────────────────────────────
async function loadProjects() {
  try {
    const res = await fetch(`${API}/projects`);
    state.projects = await res.json();
    const sel = document.getElementById('projectSelect');
    sel.innerHTML = '<option value="">— Select Project —</option>' +
      state.projects.map(p => `<option value="${p.id}" data-name="${p.name}">${p.name}</option>`).join('');
  } catch(e) { console.error('Projects load failed', e); }
}

async function onProjectChange(sel) {
  const opt = sel.options[sel.selectedIndex];
  state.selectedProjectId   = parseInt(sel.value) || null;
  state.selectedProjectName = opt.dataset.name || '';
  if (state.selectedProjectId) {
    const res = await fetch(`${API}/projects/${state.selectedProjectId}/employees`);
    state.employees = await res.json();
  } else {
    state.employees = [];
  }
  document.getElementById('processBtn').disabled = !state.uploadedFile || !state.selectedProjectId;
}

// ── History ───────────────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const res = await fetch(`${API}/history`);
    renderHistory(await res.json());
  } catch(e) {}
}
function renderHistory(items) {
  const list = document.getElementById('historyList');
  if (!items.length) { list.innerHTML = '<div class="history-empty">No meetings yet</div>'; return; }
  list.innerHTML = items.slice().reverse().map(item => `
    <div class="history-item" onclick="loadThread('${item.id}', this)">
      <div class="history-item-title">${item.title||'Untitled'}</div>
      <div class="history-item-date">${item.date||''}</div>
      <div class="history-item-people">${(item.attendees||[]).join(', ')}</div>
    </div>`).join('');
}

// ── File Upload ───────────────────────────────────────────────────────────
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
dropzone.addEventListener('drop', e => { e.preventDefault(); dropzone.classList.remove('drag-over'); if(e.dataTransfer.files[0]) handleFileSelect(e.dataTransfer.files[0]); });
dropzone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => { if(fileInput.files[0]) handleFileSelect(fileInput.files[0]); });

function handleFileSelect(file) {
  if (!file.name.endsWith('.txt')) { showToast('Please select a .txt file','error'); return; }
  state.uploadedFile = file;
  document.getElementById('fileName').textContent = '📄 ' + file.name;
  document.getElementById('processBtn').disabled = !state.selectedProjectId;
}

// ── Process Transcript ────────────────────────────────────────────────────
async function processTranscript() {
  if (!state.uploadedFile || !state.selectedProjectId) return;
  const loader = document.getElementById('loader');
  const btn    = document.getElementById('processBtn');
  btn.disabled = true; loader.classList.remove('hidden');
  const labels = ['Analyzing transcript…','Extracting memo…','Identifying tasks…','Matching employee skills…','Suggesting meetings…'];
  let li = 0;
  const lbl = document.getElementById('loaderLabel');
  const iv  = setInterval(() => { lbl.textContent = labels[Math.min(li++,labels.length-1)]; }, 2500);
  try {
    const formData = new FormData();
    formData.append('file', state.uploadedFile);
    const res = await fetch(`${API}/process-transcript?project_id=${state.selectedProjectId}`,{method:'POST',body:formData});
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail||'Failed'); }
    const data = await res.json();
    state.rawMemo=data.memo; state.rawTasks=data.tasks; state.rawMeetings=data.meetings;
    if (data.employees?.length) state.employees = data.employees;
    populateMemo(data.memo);
    populateTasks(data.tasks);
    populateMeetings(data.meetings);
    showScreen('reviewScreen');
    showPanel('memoPanel',1);
    setTimeout(autoExpandAll, 100);
    showToast('Transcript processed! ✓','success');
  } catch(e) {
    showToast('Error: '+e.message,'error');
    btn.disabled = false;
  } finally { clearInterval(iv); loader.classList.add('hidden'); }
}

// ── Panels ────────────────────────────────────────────────────────────────
function showPanel(panelId, stepNum) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById(panelId).classList.add('active');
  document.querySelectorAll('.step').forEach((s,i) => {
    s.classList.remove('active','done');
    if (i+1 < stepNum) s.classList.add('done');
    if (i+1 === stepNum) s.classList.add('active');
  });
  setTimeout(autoExpandAll, 50);
}

// ── Memo ──────────────────────────────────────────────────────────────────
function setVal(id, val) {
  const el = document.getElementById(id);
  if (!el) return;
  el.value = val;
  if (el.tagName === 'TEXTAREA') setTimeout(() => autoExpand(el), 10);
}
function lines(arr) { return Array.isArray(arr) ? arr.join('\n') : (arr||''); }

function populateMemo(memo) {
  setVal('memoTitle',    memo.title||'');
  setVal('memoDate',     memo.date||'');
  setVal('memoProject',  memo.project||state.selectedProjectName||'');
  setVal('memoAttendees',(memo.attendees||[]).join(', '));
  setVal('memoSummary',  lines(memo.summary_points||memo.summary||[]));
  setVal('memoDecisions',lines(memo.key_decisions||memo.decisions||[]));
  setVal('memoBlockers', lines(memo.blockers||[]));
  setVal('memoRisks',    lines(memo.risks||[]));
  setVal('memoDependencies', lines(memo.dependencies||[]));
  setVal('memoNextSteps',    lines(memo.next_steps||[]));
  setVal('memoManagerActions', lines(memo.manager_actions||[]));
  setVal('memoOpenQuestions',  lines(memo.open_questions||[]));
  setVal('memoHighlights',     lines(memo.highlights||[]));
  const fu = document.getElementById('memoFollowUp');
  if (fu) fu.checked = !!memo.follow_up_required;
}
function resetMemo() { if(state.rawMemo) populateMemo(state.rawMemo); showToast('Memo reset'); }
function getLines(id) { return (document.getElementById(id)?.value||'').split('\n').map(s=>s.trim()).filter(Boolean); }

function getMemoFromForm() {
  return {
    title:           document.getElementById('memoTitle')?.value.trim()||'',
    date:            document.getElementById('memoDate')?.value.trim()||'',
    project:         document.getElementById('memoProject')?.value.trim()||'',
    attendees:       (document.getElementById('memoAttendees')?.value||'').split(',').map(s=>s.trim()).filter(Boolean),
    summary_points:  getLines('memoSummary'),
    key_decisions:   getLines('memoDecisions'),
    blockers:        getLines('memoBlockers'),
    risks:           getLines('memoRisks'),
    dependencies:    getLines('memoDependencies'),
    next_steps:      getLines('memoNextSteps'),
    manager_actions: getLines('memoManagerActions'),
    open_questions:  getLines('memoOpenQuestions'),
    highlights:      getLines('memoHighlights'),
    follow_up_required: document.getElementById('memoFollowUp')?.checked||false,
  };
}
function confirmMemo() {
  state.confirmedMemo = getMemoFromForm();
  showPanel('tasksPanel',2);
  showToast('Memo confirmed ✓','success');
}

// ── Employee Dropdown ─────────────────────────────────────────────────────
function employeeDropdown(cls, selectedName='') {
  const opts = `<option value="">— None —</option>` +
    state.employees.map(e => {
      const wl = e.workload_pct>=80?'🔴':e.workload_pct>=40?'🟡':'🟢';
      return `<option value="${e.name}" data-email="${e.email||''}" ${e.name===selectedName?'selected':''}>
        ${wl} ${e.name} (${e.role} · ${e.level} · ${e.workload_pct}% load)
      </option>`;
    }).join('');
  return `<select class="card-select ${cls}">${opts}</select>`;
}

// ── Tasks ─────────────────────────────────────────────────────────────────
function populateTasks(tasks) {
  const grid = document.getElementById('tasksGrid');
  grid.innerHTML = '';
  if (!tasks || !tasks.length) {
    grid.innerHTML = '<div class="empty-state">No tasks extracted. Click "+ Add Task" to add manually.</div>';
    return;
  }
  tasks.forEach(t => {
    try { grid.appendChild(makeTaskCard(t)); }
    catch(e) { console.error('Task card error:', e, t); }
  });
}

function makeTaskCard(task) {
  const card = document.createElement('div');
  card.className = 'card'; card.dataset.id = task.id||('t_'+Date.now());
  const badge = task.priority||'Medium';
  const bc = {High:'badge-high',Medium:'badge-medium',Low:'badge-low'}[badge]||'badge-medium';

  const assigneeEmp = state.employees.find(e => e.name === task.assignee);
  const currentTasksHtml = assigneeEmp?.current_tasks?.length
    ? `<div class="current-tasks-box">
        <div class="current-tasks-label">⚠ ${esc(assigneeEmp.name)}'s active tasks (${assigneeEmp.current_tasks.length})</div>
        ${assigneeEmp.current_tasks.map(t =>
          `<div class="current-task-item">
            <span class="ct-priority ct-${(t.priority||'medium').toLowerCase()}">${t.priority||''}</span>
            ${esc(t.title||'')}
          </div>`).join('')}
      </div>` : '';

  const skillMatchHtml = task.skill_match
    ? `<div class="skill-match skill-${(task.skill_match||'').toLowerCase()}">Skill match: ${task.skill_match}</div>` : '';

  card.innerHTML = `
    <div class="card-top">
      <span class="card-badge ${bc}">${badge}</span>
      <button class="btn-danger" onclick="this.closest('.card').remove()">✕</button>
    </div>
    <div class="card-field"><label>TASK TITLE</label>
      <input class="card-input task-title" value="${esc(task.title||'')}" placeholder="Task title"/></div>
    <div class="card-field"><label>DESCRIPTION</label>
      <textarea class="card-textarea task-desc" placeholder="What needs to be done">${esc(task.description||'')}</textarea></div>
    <div class="card-field"><label>ASSIGNEE</label>
      <div class="assignee-wrap">${employeeDropdown('task-assignee', task.assignee||'')}</div></div>
    <div class="current-tasks-wrap">${currentTasksHtml}</div>
    <div class="card-row">
      <div class="card-field"><label>COMPANION</label>${employeeDropdown('task-companion', task.companion||'')}</div>
      <div class="card-field"><label>GUIDE</label>${employeeDropdown('task-guide', task.guide||'')}</div>
    </div>
    <div class="card-field"><label>STATUS CHECKER</label>
      <input class="card-input task-checker" value="${esc(task.checker||'hariharan-projectmanager')}"/></div>
    <div class="card-row">
      <div class="card-field"><label>PRIORITY</label>
        <select class="card-select task-priority" onchange="updateBadge(this)">
          <option ${badge==='High'?'selected':''}>High</option>
          <option ${badge==='Medium'?'selected':''}>Medium</option>
          <option ${badge==='Low'?'selected':''}>Low</option>
        </select>
      </div>
      <div class="card-field"><label>DUE DATE</label>
        <input class="card-input task-due" value="${esc(task.due_date||'TBD')}" placeholder="YYYY-MM-DD"/></div>
    </div>
    <div class="card-row">
      <div class="card-field"><label>ASSIGNED DATE</label>
        <input class="card-input task-assigned-date" value="${esc(task.assigned_date||new Date().toISOString().slice(0,10))}"/></div>
      <div class="card-field"><label>TOTAL DAYS</label>
        <input class="card-input task-total-days" type="number" value="${task.total_days||''}" placeholder="e.g. 3"/></div>
    </div>
    <div class="card-field"><label>SKILLS REQUIRED</label>
      <input class="card-input task-skills" value="${esc((task.skills_required||[]).join(', '))}" placeholder="Python, React…"/></div>
    <div class="card-field"><label>NOTES</label>
      <textarea class="card-textarea task-notes" placeholder="Additional context">${esc(task.notes||'')}</textarea></div>
    <div class="card-field"><label>ESCALATION DETAILS</label>
      <textarea class="card-textarea task-escalation" placeholder="What happens if delayed?">${esc(task.escalation_details||'')}</textarea></div>
    ${skillMatchHtml}
  `;

  // Update current tasks display when assignee changes
  card.querySelector('.task-assignee').addEventListener('change', function() {
    const emp = state.employees.find(e => e.name === this.value);
    const wrap = card.querySelector('.current-tasks-wrap');
    if (!wrap) return;
    if (emp?.current_tasks?.length) {
      wrap.innerHTML = `<div class="current-tasks-box">
        <div class="current-tasks-label">⚠ ${esc(emp.name)}'s active tasks (${emp.current_tasks.length})</div>
        ${emp.current_tasks.map(t => `<div class="current-task-item">
          <span class="ct-priority ct-${(t.priority||'medium').toLowerCase()}">${t.priority||''}</span>${esc(t.title||'')}
        </div>`).join('')}
      </div>`;
    } else { wrap.innerHTML = ''; }
  });

  setTimeout(() => card.querySelectorAll('textarea').forEach(t => autoExpand(t)), 50);
  return card;
}

function addTask() {
  const t = {id:'t_'+Date.now(),title:'',description:'',assignee:'',companion:'',
    guide:'',checker:'hariharan-projectmanager',due_date:'TBD',priority:'Medium',
    notes:'',escalation_details:'',skills_required:[],total_days:null};
  document.getElementById('tasksGrid').appendChild(makeTaskCard(t));
}

function updateBadge(sel) {
  const badge = sel.closest('.card').querySelector('.card-badge');
  const val   = sel.value;
  badge.className = 'card-badge '+({High:'badge-high',Medium:'badge-medium',Low:'badge-low'}[val]||'badge-medium');
  badge.textContent = val;
}

function getTasksFromGrid() {
  return Array.from(document.querySelectorAll('#tasksGrid .card')).map((card,i) => {
    const g = s => card.querySelector(s);
    const asel = g('.task-assignee');
    return {
      id:                 card.dataset.id||'t_'+i,
      title:              g('.task-title')?.value.trim()||'',
      description:        g('.task-desc')?.value.trim()||'',
      assignee:           asel?.value||'',
      assignee_email:     asel?.options[asel.selectedIndex]?.dataset.email||'',
      companion:          g('.task-companion')?.value||'',
      guide:              g('.task-guide')?.value||'',
      checker:            g('.task-checker')?.value||'hariharan-projectmanager',
      priority:           g('.task-priority')?.value||'Medium',
      due_date:           g('.task-due')?.value||'TBD',
      assigned_date:      g('.task-assigned-date')?.value||'',
      total_days:         parseInt(g('.task-total-days')?.value)||null,
      skills_required:    (g('.task-skills')?.value||'').split(',').map(s=>s.trim()).filter(Boolean),
      notes:              g('.task-notes')?.value.trim()||'',
      escalation_details: g('.task-escalation')?.value.trim()||'',
    };
  });
}

function confirmTasks() {
  state.confirmedTasks = getTasksFromGrid();
  showPanel('meetingsPanel',3);
  showToast('Tasks confirmed ✓','success');
}

// ── Meetings ──────────────────────────────────────────────────────────────
function populateMeetings(meetings) {
  const grid = document.getElementById('meetingsGrid');
  grid.innerHTML = '';
  if (!meetings || !meetings.length) {
    grid.innerHTML = '<div class="empty-state">No follow-up meetings suggested. Click "+ Add Meeting" to add one.</div>';
    return;
  }
  meetings.forEach(m => {
    try { grid.appendChild(makeMeetingCard(m)); }
    catch(e) { console.error('Meeting card error:', e); }
  });
}

function makeMeetingCard(mtg) {
  const card = document.createElement('div');
  card.className = 'card'; card.dataset.id = mtg.id||('m_'+Date.now());
  card.innerHTML = `
    <div class="card-top">
      <span class="card-badge badge-meeting">MEETING</span>
      <button class="btn-danger" onclick="this.closest('.card').remove()">✕</button>
    </div>
    <div class="card-field"><label>MEETING TITLE</label>
      <input class="card-input mtg-title" value="${esc(mtg.title||'')}"/></div>
    <div class="card-field"><label>PURPOSE</label>
      <textarea class="card-textarea mtg-purpose">${esc(mtg.purpose||'')}</textarea></div>
    <div class="card-row">
      <div class="card-field"><label>DATE & TIME</label>
        <input class="card-input mtg-date" type="datetime-local"
          value="${mtg.suggested_date && mtg.suggested_date !== 'TBD'
            ? (mtg.suggested_date.includes('T') ? mtg.suggested_date : mtg.suggested_date + 'T10:00')
            : ''}"/></div>
      <div class="card-field"><label>DURATION (MIN)</label>
        <input class="card-input mtg-duration" type="number" value="${mtg.duration_mins||30}"/></div>
    </div>
    <div class="card-field"><label>RECIPIENTS</label>
      <input class="card-input mtg-recipients" value="${esc((mtg.recipients||[]).join(', '))}"/></div>
    <div class="card-field"><label>AGENDA</label>
      <textarea class="card-textarea mtg-agenda">${esc(mtg.agenda||'')}</textarea></div>
  `;
  setTimeout(() => card.querySelectorAll('textarea').forEach(t => autoExpand(t)), 50);
  return card;
}

function addMeeting() {
  const m = {id:'m_'+Date.now(),title:'',purpose:'',suggested_date:'TBD',duration_mins:30,recipients:[],agenda:''};
  document.getElementById('meetingsGrid').appendChild(makeMeetingCard(m));
}

function getMeetingsFromGrid() {
  return Array.from(document.querySelectorAll('#meetingsGrid .card')).map((card,i) => {
    const g = s => card.querySelector(s);
    return {
      id:             card.dataset.id||'m_'+i,
      title:          g('.mtg-title')?.value.trim()||'',
      purpose:        g('.mtg-purpose')?.value.trim()||'',
      suggested_date: g('.mtg-date')?.value.trim()||'TBD',
      duration_mins:  parseInt(g('.mtg-duration')?.value)||30,
      recipients:     (g('.mtg-recipients')?.value||'').split(',').map(s=>s.trim()).filter(Boolean),
      agenda:         g('.mtg-agenda')?.value.trim()||'',
    };
  });
}

// ── Schedule All ──────────────────────────────────────────────────────────
async function scheduleAll() {
  const btn = document.getElementById('scheduleAllBtn');
  btn.textContent = 'Scheduling…'; btn.disabled = true;
  const memo     = state.confirmedMemo || getMemoFromForm();
  const tasks    = state.confirmedTasks || getTasksFromGrid();
  const meetings = getMeetingsFromGrid();
  try {
    const fRes = await fetch(`${API}/finalize`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({memo,tasks,meetings,
        project_id:state.selectedProjectId,project_name:state.selectedProjectName}),
    });
    if (!fRes.ok) throw new Error('Finalize failed');
    const fData = await fRes.json();
    state.meetingId = fData.meeting_id;

    await fetch(`${API}/schedule`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({meeting_id:state.meetingId,tasks,meetings}),
    });

    document.getElementById('finalizeBar').style.display='flex';
    if (fData.sheet_url)   document.getElementById('sheetLink').href   = fData.sheet_url;
    if (fData.tracker_url) document.getElementById('trackerLink').href = fData.tracker_url;
    showToast('All scheduled successfully! ✓','success');
    loadHistory();
  } catch(e) {
    showToast('Error: '+e.message,'error');
  } finally { btn.textContent='Schedule All ↗'; btn.disabled=false; }
}

// ── Thread View ───────────────────────────────────────────────────────────
async function loadThread(meetingId, el, forceRefresh=false) {
  document.querySelectorAll('.history-item').forEach(i=>i.classList.remove('active'));
  el.classList.add('active');
  showScreen('threadScreen');
  document.getElementById('threadTitle').textContent = 'Loading briefing…';
  document.getElementById('threadGrid').innerHTML = '<div class="loading-msg">Loading briefing…</div>';
  document.getElementById('refreshBriefingBtn').dataset.meetingId = meetingId;
  document.getElementById('refreshBriefingBtn').dataset.el = '';
  window._threadEl = el;

  const pid = state.selectedProjectId ? `&project_id=${state.selectedProjectId}` : '';
  const url = `${API}/history/${meetingId}?refresh=${forceRefresh}${pid}`;

  try {
    const res  = await fetch(url);
    if (!res.ok) throw new Error('Failed to load briefing');
    const data = await res.json();
    const meta = data.meta||{};
    document.getElementById('threadTitle').textContent = meta.title||'Meeting Briefing';

    // Show cache indicator
    const cacheTag = data.from_cache
      ? '<span class="cache-tag">⚡ Cached</span>'
      : '<span class="cache-tag fresh">✨ Fresh</span>';
    document.getElementById('threadMeta').innerHTML = `
      <div class="thread-meta-item"><span class="thread-meta-label">DATE</span><span class="thread-meta-value">${meta.date||'—'}</span></div>
      <div class="thread-meta-item"><span class="thread-meta-label">ATTENDEES</span><span class="thread-meta-value">${(meta.attendees||[]).join(', ')||'—'}</span></div>
      <div class="thread-meta-item">${cacheTag}</div>
    `;
    renderBriefing(data.briefing);
  } catch(e) {
    document.getElementById('threadGrid').innerHTML = `<div style="color:var(--red);padding:20px">${e.message}</div>`;
  }
}

async function refreshBriefing() {
  const btn = document.getElementById('refreshBriefingBtn');
  const mid = btn.dataset.meetingId;
  if (!mid) return;
  btn.textContent = 'Refreshing…'; btn.disabled = true;
  document.getElementById('threadGrid').innerHTML = '<div class="loading-msg">Regenerating briefing with latest data…</div>';
  await loadThread(mid, window._threadEl, true);
  btn.textContent = '↺ Refresh'; btn.disabled = false;
  showToast('Briefing refreshed ✓','success');
}

function renderBriefing(b) {
  if (!b) return;
  const sections = [
    {title:'What Was Discussed', key:'what_was_discussed', type:'list'},
    {title:'What Was Decided',   key:'what_was_decided',   type:'list'},
    {title:'What to Follow Up',  key:'what_to_follow_up',  type:'list'},
    {title:'Risks to Watch',     key:'risks_to_watch',     type:'list'},
    {title:'Open Questions',     key:'open_questions',     type:'list'},
    {title:'Suggested Agenda',   key:'suggested_agenda',   type:'list'},
  ];
  let html = sections.map(sec => {
    const val = b[sec.key];
    if (!val || (Array.isArray(val) && !val.length)) return '';
    const content = Array.isArray(val)
      ? `<ul>${val.map(v=>`<li>${v}</li>`).join('')}</ul>`
      : `<p>${val}</p>`;
    return `<div class="thread-card"><div class="thread-card-title">${sec.title}</div>${content}</div>`;
  }).join('');

  if (b.employee_status?.length) {
    html += `<div class="thread-card full-width">
      <div class="thread-card-title">Team Status</div>
      <table class="emp-table">
        <thead><tr><th>Name</th><th>Role</th><th>Current Tasks</th><th>Completed</th><th>Workload</th><th>Flag</th></tr></thead>
        <tbody>${b.employee_status.map(e => {
          const fc = {Overloaded:'var(--red)',Blocked:'var(--yellow)','On Track':'var(--accent)',Free:'var(--text3)'}[e.flag]||'var(--text2)';
          const tasks = e.current_tasks?.length
            ? e.current_tasks.map(t=>`<div class="mini-task"><span class="ct-priority ct-${(t.priority||'medium').toLowerCase()}">${t.priority||''}</span>${esc(t.title||'')}</div>`).join('')
            : '<span style="color:var(--text3)">No active tasks</span>';
          const done = e.completed_tasks?.length ? `<span style="color:var(--accent)">${e.completed_tasks.length} done</span>` : '—';
          return `<tr><td><strong>${esc(e.name||'')}</strong></td><td style="color:var(--text2)">${esc(e.role||'')}</td><td>${tasks}</td><td>${done}</td><td>${e.workload||'—'}</td><td style="color:${fc};font-weight:600">${e.flag||'—'}</td></tr>`;
        }).join('')}</tbody>
      </table>
    </div>`;
  }
  document.getElementById('threadGrid').innerHTML = html;
}

// ── Task Tracker ──────────────────────────────────────────────────────────
function showTrackerScreen() {
  showScreen('trackerScreen');
  loadTrackerProjects();
}
function renderTrackerProjects() {
  document.getElementById('trackerProjects').innerHTML = state.projects.map(p =>
    `<div class="tracker-project-card" onclick="loadTrackerTasks(${p.id},'${p.name}',this)">
      <div class="tracker-project-name">${p.name}</div>
      <div class="tracker-project-desc">${p.description||''}</div>
    </div>`).join('');
}

let trackerCurrentProject = null;

async function loadTrackerTasks(projectId, projectName, el) {
  document.querySelectorAll('.tracker-project-card').forEach(c=>c.classList.remove('active'));
  el.classList.add('active');
  trackerCurrentProject = {id:projectId,name:projectName};
  document.getElementById('trackerTableSection').style.display='block';
  document.getElementById('trackerProjectTitle').textContent = projectName+' — Tasks';
  document.getElementById('trackerTableBody').innerHTML = '<tr><td colspan="9" style="color:var(--text3);padding:20px;text-align:center">Loading…</td></tr>';
  const res   = await fetch(`${API}/projects/${projectId}/tasks`);
  const tasks = await res.json();
  renderTrackerTable(tasks);
}

function renderTrackerTable(tasks) {
  const tbody = document.getElementById('trackerTableBody');
  if (!tasks.length) {
    tbody.innerHTML='<tr><td colspan="9" style="color:var(--text3);padding:20px;text-align:center">No tasks yet</td></tr>';
    return;
  }
  tbody.innerHTML = tasks.map(t => {
    const statusOpts = ['pending','in-progress','done'].map(s =>
      `<option ${t.status===s?'selected':''} value="${s}">${s}</option>`).join('');
    const priColor = {High:'var(--red)',Medium:'var(--yellow)',Low:'var(--accent)'}[t.priority]||'var(--text2)';
    return `<tr data-id="${t.id}">
      <td>${t.id}</td>
      <td><input class="tbl-input" value="${esc(t.title||'')}"/></td>
      <td>${esc(t.assignee_name||'—')}</td>
      <td>${esc(t.companion_name||'—')}</td>
      <td>${esc(t.guide_name||'—')}</td>
      <td style="color:${priColor};font-weight:600;text-align:center">${t.priority||'—'}</td>
      <td><select class="tbl-select status-sel">${statusOpts}</select></td>
      <td>${t.due_date?String(t.due_date).slice(0,10):'TBD'}</td>
      <td><textarea class="tbl-textarea" rows="1">${esc(t.notes||'')}</textarea></td>
    </tr>`;
  }).join('');
}

async function updateTracker() {
  const rows = document.querySelectorAll('#trackerTableBody tr[data-id]');
  let ok = 0;
  for (const row of rows) {
    try {
      await fetch(`${API}/tasks/${row.dataset.id}`,{
        method:'PUT',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          status: row.querySelector('.status-sel')?.value||'pending',
          notes:  row.querySelector('.tbl-textarea')?.value.trim()||'',
        }),
      });
      ok++;
    } catch(e) {}
  }
  showToast(`Updated ${ok} tasks ✓`,'success');
  if (trackerCurrentProject) {
    const el = document.querySelector('.tracker-project-card.active');
    if (el) loadTrackerTasks(trackerCurrentProject.id, trackerCurrentProject.name, el);
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────
function esc(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

init();

// ── Transcript Library ────────────────────────────────────────────────────
function showTranscriptScreen() {
  showScreen('transcriptScreen');
  loadTranscriptLibrary();
}

async function loadTranscriptLibrary() {
  const container = document.getElementById('transcriptList');
  container.innerHTML = '<div class="loading-msg">Loading transcripts…</div>';
  try {
    const res   = await fetch(`${API}/history`);
    const items = await res.json();
    if (!items.length) {
      container.innerHTML = '<div class="empty-state">No transcripts yet. Process a meeting to get started.</div>';
      return;
    }
    // Group by project
    const byProject = {};
    items.slice().reverse().forEach(item => {
      const proj = item.project || 'Unknown Project';
      if (!byProject[proj]) byProject[proj] = [];
      byProject[proj].push(item);
    });
    container.innerHTML = Object.entries(byProject).map(([proj, meetings]) => `
      <div class="transcript-project-group">
        <div class="transcript-project-label">${proj}</div>
        <div class="transcript-cards">
          ${meetings.map(m => `
            <div class="transcript-card" onclick="showTranscriptDetail('${m.id}')">
              <div class="transcript-card-top">
                <div class="transcript-card-title">${m.title || 'Untitled Meeting'}</div>
                <div class="transcript-card-date">${m.date || '—'}</div>
              </div>
              <div class="transcript-card-attendees">${(m.attendees||[]).join(', ') || '—'}</div>
              <div class="transcript-card-id">ID: ${m.id}</div>
            </div>`).join('')}
        </div>
      </div>`).join('');
  } catch(e) {
    container.innerHTML = `<div style="color:var(--red);padding:20px">Failed to load: ${e.message}</div>`;
  }
}

async function showTranscriptDetail(meetingId) {
  document.getElementById('transcriptDetail').style.display = 'block';
  document.getElementById('transcriptDetailContent').innerHTML = '<div class="loading-msg">Loading…</div>';

  try {
    const res  = await fetch(`${API}/transcript/${meetingId}`);
    const data = await res.json();
    const memo = data.memo || {};
    const tasks = data.tasks || [];
    const meetings = data.meetings || [];

    const listHtml = (arr) => arr.length
      ? `<ul>${arr.map(i => `<li>${esc(i)}</li>`).join('')}</ul>`
      : '<span style="color:var(--text3)">None</span>';

    document.getElementById('transcriptDetailContent').innerHTML = `
      <div class="detail-header">
        <div>
          <div class="panel-eyebrow">TRANSCRIPT DETAIL</div>
          <h3 class="detail-title">${esc(memo.title||'Untitled')}</h3>
          <div class="detail-meta">${esc(memo.date||'')} &nbsp;·&nbsp; ${(memo.attendees||[]).join(', ')}</div>
        </div>
        <button class="btn-ghost" onclick="document.getElementById('transcriptDetail').style.display='none'">✕ Close</button>
      </div>

      <div class="detail-grid">
        <div class="detail-card full">
          <div class="detail-card-label">SUMMARY</div>
          ${listHtml(memo.summary_points||[])}
        </div>
        <div class="detail-card">
          <div class="detail-card-label">KEY DECISIONS</div>
          ${listHtml(memo.key_decisions||[])}
        </div>
        <div class="detail-card">
          <div class="detail-card-label">BLOCKERS</div>
          ${listHtml(memo.blockers||[])}
        </div>
        <div class="detail-card">
          <div class="detail-card-label">RISKS</div>
          ${listHtml(memo.risks||[])}
        </div>
        <div class="detail-card">
          <div class="detail-card-label">MANAGER ACTIONS</div>
          ${listHtml(memo.manager_actions||[])}
        </div>
        <div class="detail-card full">
          <div class="detail-card-label">NEXT STEPS</div>
          ${listHtml(memo.next_steps||[])}
        </div>
        <div class="detail-card full">
          <div class="detail-card-label">TASKS (${tasks.length})</div>
          <table class="detail-table">
            <thead><tr><th>Task</th><th>Assignee</th><th>Guide</th><th>Priority</th><th>Due</th></tr></thead>
            <tbody>
              ${tasks.map(t => `<tr>
                <td>${esc(t.title||'')}</td>
                <td>${esc(t.assignee||'—')}</td>
                <td>${esc(t.guide||'—')}</td>
                <td style="color:${{High:'var(--red)',Medium:'var(--yellow)',Low:'var(--accent)'}[t.priority]||'var(--text2)'}; font-weight:600">${t.priority||'—'}</td>
                <td style="font-family:var(--mono);font-size:11px">${esc(t.due_date||'TBD')}</td>
              </tr>`).join('')}
            </tbody>
          </table>
        </div>
        <div class="detail-card full">
          <div class="detail-card-label">SCHEDULED MEETINGS (${meetings.length})</div>
          ${meetings.map(m => `
            <div class="detail-meeting-row">
              <strong>${esc(m.title||'')}</strong>
              <span style="color:var(--text3);font-family:var(--mono);font-size:11px">${esc(m.suggested_date||'TBD')}</span>
              <span style="color:var(--text2);font-size:12px">${esc(m.purpose||'')}</span>
            </div>`).join('') || '<span style="color:var(--text3)">None</span>'}
        </div>
      </div>
    `;
  } catch(e) {
    document.getElementById('transcriptDetailContent').innerHTML =
      `<div style="color:var(--red);padding:20px">Failed: ${e.message}</div>`;
  }
}

// ── Sheet links in tracker ────────────────────────────────────────────────
async function loadTrackerProjects() {
  try {
    const [projRes, linksRes] = await Promise.all([
      fetch(`${API}/projects`),
      fetch(`${API}/sheet-links`),
    ]);
    state.projects  = await projRes.json();
    const links     = await linksRes.json();

    document.getElementById('trackerProjects').innerHTML = state.projects.map(p => {
      const sl  = links[p.name] || {};
      const logUrl     = sl.log     ? `<a href="${sl.log}"     target="_blank" class="sheet-pill">📊 Meeting Log ↗</a>` : '';
      const trackerUrl = sl.tracker ? `<a href="${sl.tracker}" target="_blank" class="sheet-pill">📋 Task Tracker ↗</a>` : '';
      return `
        <div class="tracker-project-card" onclick="loadTrackerTasks(${p.id},'${p.name}',this)">
          <div class="tracker-project-name">${p.name}</div>
          <div class="tracker-project-desc">${p.description||''}</div>
          <div class="sheet-pills">${logUrl}${trackerUrl}</div>
        </div>`;
    }).join('');
  } catch(e) { console.error(e); }
}