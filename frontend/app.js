const $ = s => document.querySelector(s);
const E = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

const paths = {heart:'M2 12h4l3-8 5 16 3-8h5', plus:'M12 5v14M5 12h14', sparkles:'m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3 3-7Z', send:'m3 3 19 9-19 9 4-9-4-9Zm4 9h15', x:'m6 6 12 12M6 18 18 6', download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5', trash:'M3 6h18M9 6V3h6v3M6 6l1 16h10l1-16M10 10v8M14 10v8', book:'M12 6c-3-3-7-3-10-2v15c3-1 7-1 10 2 3-3 7-3 10-2V4c-3-1-7-1-10 2v15', loader:'M20 12a8 8 0 1 1-8-8', table:'M3 4h18v16H3zM3 10h18M3 15h18M9 4v16', clipboard:'M9 3h6v4H9zM9 5H5v16h14V5h-4M8 12h8M8 16h5', note:'M14 2H4v20h16V8l-6-6Zm0 0v6h6M8 13h8M8 17h8'};
const icon = (name, size = 16) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name] || paths.note}"/></svg>`;
function icons(root = document) { root.querySelectorAll('[data-icon]').forEach(e => e.innerHTML = icon(e.dataset.icon)); }

const JOURNAL_KEY = 'careplan.journal.v1', ORDERS_KEY = 'careplan.orders.v1';
const state = {messages: [], busy: false, journal: [], chapters: [], orders: {time: '', text: ''}};

/* ---------- Lưu trữ nhật ký (trình duyệt) ---------- */
function loadJournal() {
  try { const raw = JSON.parse(localStorage.getItem(JOURNAL_KEY) || '[]'); return Array.isArray(raw) ? raw.filter(e => e && typeof e.text === 'string') : []; }
  catch { return []; }
}
function loadOrders() {
  try { const o = JSON.parse(localStorage.getItem(ORDERS_KEY) || 'null'); return o && typeof o.text === 'string' ? {time: String(o.time || ''), text: o.text} : {time: '', text: ''}; }
  catch { return {time: '', text: ''}; }
}
function saveOrders() {
  try { localStorage.setItem(ORDERS_KEY, JSON.stringify(state.orders)); }
  catch { toast('Không lưu được y lệnh vào trình duyệt; nội dung sẽ mất khi tải lại trang.'); }
}
function saveJournal() {
  try { localStorage.setItem(JOURNAL_KEY, JSON.stringify(state.journal)); }
  catch { toast('Không lưu được nhật ký vào trình duyệt; nội dung sẽ mất khi tải lại trang.'); }
}

/* ---------- Tiện ích ---------- */
function toast(text) { const t = $('#toast'); t.textContent = text; t.hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => t.hidden = true, 3500); }
function showError(text) { $('#error').textContent = text || ''; $('#error').hidden = !text; }
function nowLocal() { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); }
function formatTime(value) {
  const d = new Date(value);
  if (isNaN(d)) return value || '';
  return d.toLocaleString('vi-VN', {hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric'});
}
function shortChapter(title) { return String(title || '').replace(/\s+/g, ' ').replace(/^QUY TRÌNH CHĂM SÓC\s*/i, '').trim(); }

/* ---------- Nhật ký ---------- */
function renderJournal() {
  const list = $('#journal-list');
  const sorted = state.journal.map((e, i) => ({...e, i})).sort((a, b) => String(b.time).localeCompare(String(a.time)));
  list.innerHTML = sorted.map(e => `<li><div class="entry-head"><time>${E(formatTime(e.time))}</time><button class="icon-button" data-del="${e.i}" aria-label="Xóa ghi chép">${icon('x', 14)}</button></div><p>${E(e.text)}</p></li>`).join('')
    || '<li class="empty">Ghi lại diễn biến theo từng thời điểm: tri giác, sinh hiệu, triệu chứng, can thiệp đã làm, đáp ứng của người bệnh…</li>';
  $('#journal-count').textContent = (state.journal.length ? `${state.journal.length} ghi chép.` : 'Chưa có ghi chép.') + ' Không ghi họ tên, mã bệnh nhân, số điện thoại. Chỉ lưu trong trình duyệt máy này.';
  $('#journal-badge').hidden = !state.journal.length; $('#journal-badge').textContent = state.journal.length;
}
function journalForRequest() {
  if (!$('#use-journal').checked) return [];
  return [...state.journal].sort((a, b) => String(a.time).localeCompare(String(b.time))).slice(-50)
    .map(e => ({time: formatTime(e.time).slice(0, 40), text: e.text.slice(0, 2000)}));
}

$('#journal-form').addEventListener('submit', ev => {
  ev.preventDefault();
  const text = $('#journal-text').value.trim();
  if (!text) return;
  state.journal.push({time: $('#journal-time').value || nowLocal(), text});
  saveJournal(); renderJournal();
  $('#journal-text').value = ''; $('#journal-time').value = nowLocal(); $('#journal-text').focus();
});
$('#journal-text').addEventListener('keydown', ev => { if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) $('#journal-form').requestSubmit(); });
$('#journal-list').addEventListener('click', ev => {
  const btn = ev.target.closest('[data-del]');
  if (!btn) return;
  state.journal.splice(Number(btn.dataset.del), 1); saveJournal(); renderJournal();
});
function confirmClick(btn, label, action) {
  btn.addEventListener('click', () => {
    const text = btn.lastChild;
    if (btn.dataset.confirm === '1') { delete btn.dataset.confirm; text.textContent = label; action(); return; }
    btn.dataset.confirm = '1'; text.textContent = 'Bấm lần nữa để xóa';
    setTimeout(() => { delete btn.dataset.confirm; text.textContent = label; }, 3000);
  });
}
confirmClick($('#clear-journal'), 'Xóa hết', () => { if (!state.journal.length) return; state.journal = []; saveJournal(); renderJournal(); toast('Đã xóa nhật ký'); });
$('#export-journal').addEventListener('click', () => {
  if (!state.journal.length) return toast('Nhật ký đang trống');
  const lines = [...state.journal].sort((a, b) => String(a.time).localeCompare(String(b.time))).map(e => `[${formatTime(e.time)}]\n${e.text}\n`);
  const blob = new Blob(['NHẬT KÝ THEO DÕI DIỄN BIẾN\n\n' + lines.join('\n')], {type: 'text/plain;charset=utf-8'});
  const a = Object.assign(document.createElement('a'), {href: URL.createObjectURL(blob), download: `nhat-ky-dien-bien-${nowLocal().slice(0, 10)}.txt`});
  a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
});

/* ---------- Y lệnh nội trú ---------- */
function renderOrders() {
  $('#orders-text').value = state.orders.text; $('#orders-time').value = state.orders.time;
  $('#orders-count').textContent = state.orders.text.length;
  $('#orders-badge').hidden = !state.orders.text.trim();
}
function ordersForRequest() {
  if (!$('#use-orders').checked || !state.orders.text.trim()) return {orders: '', ordersTime: ''};
  return {orders: state.orders.text.slice(0, 6000), ordersTime: state.orders.time ? formatTime(state.orders.time).slice(0, 40) : ''};
}
let ordersTimer;
$('#orders-text').addEventListener('input', () => {
  state.orders.text = $('#orders-text').value;
  if (state.orders.text.trim() && !state.orders.time) { state.orders.time = nowLocal(); $('#orders-time').value = state.orders.time; }
  $('#orders-count').textContent = state.orders.text.length; $('#orders-badge').hidden = !state.orders.text.trim();
  clearTimeout(ordersTimer); ordersTimer = setTimeout(saveOrders, 400);
});
$('#orders-time').addEventListener('change', () => { state.orders.time = $('#orders-time').value; saveOrders(); });
confirmClick($('#clear-orders'), 'Xóa y lệnh', () => { state.orders = {time: '', text: ''}; saveOrders(); renderOrders(); toast('Đã xóa y lệnh'); });
document.querySelectorAll('[data-side]').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('[data-side]').forEach(x => { x.classList.toggle('active', x === b); x.setAttribute('aria-selected', String(x === b)); });
  $('#journal-view').hidden = b.dataset.side !== 'journal'; $('#orders-view').hidden = b.dataset.side !== 'orders';
}));

/* ---------- Hiển thị câu trả lời ---------- */
function renderAnswer(text, sources) {
  const lines = E(text).split('\n');
  let html = '', inList = false;
  for (const raw of lines) {
    const line = raw.trim();
    const bullet = /^[-*•]\s+/.test(line);
    if (bullet && !inList) { html += '<ul>'; inList = true; }
    if (!bullet && inList) { html += '</ul>'; inList = false; }
    if (!line) continue;
    const body = line.replace(/^[-*•]\s+/, '').replace(/^#{1,4}\s+/, '').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html += bullet ? `<li>${body}</li>` : `<p>${body}</p>`;
  }
  if (inList) html += '</ul>';
  return html.replace(/\[S(\d+)\]/g, (m, n) => {
    const s = sources[Number(n) - 1];
    return s ? `<button class="cite" data-source="${E(s.id)}" title="Trang ${s.page}">S${n}</button>` : '';
  });
}
/* ---------- Bảng kế hoạch ---------- */
const PLAN_COLUMNS = ['Chẩn đoán / vấn đề', 'Mục tiêu', 'Can thiệp điều dưỡng', 'Lượng giá', 'Lý do chọn', 'Nguồn'];
function sourceLabel(sources, id) { const i = sources.findIndex(s => s.id === id); return i < 0 ? null : {n: i + 1, s: sources[i]}; }
function planCells(row, sources) {
  const refs = row.sourceIds.map(id => sourceLabel(sources, id)).filter(Boolean);
  return [row.diagnosis, row.goal, row.interventions.map(x => '- ' + x).join('\n'), row.evaluation, row.reason,
    refs.length ? refs.map(r => `S${r.n} (tr. ${r.s.page})`).join(', ') : 'Chưa có nguồn'];
}
function renderPlan(m, index) {
  const sources = m.sources || [];
  const rows = m.plan.map((row, i) => {
    const refs = row.sourceIds.map(id => sourceLabel(sources, id)).filter(Boolean);
    const src = refs.length
      ? refs.map(r => `<button class="cite" data-source="${E(r.s.id)}" title="Trang ${r.s.page}">S${r.n}</button><small>tr. ${r.s.page}</small>`).join('<br>')
      : '<span class="no-source" title="Không tìm thấy nội dung tương ứng trong sách; cần điều dưỡng xác nhận">Chưa có nguồn</span>';
    return `<tr class="${refs.length ? '' : 'unsourced'}"><td class="num">${i + 1}</td><td><strong>${E(row.diagnosis)}</strong></td><td>${E(row.goal)}</td>
      <td>${row.interventions.length ? `<ul>${row.interventions.map(x => `<li>${E(x)}</li>`).join('')}</ul>` : ''}</td>
      <td>${E(row.evaluation)}</td><td class="reason">${E(row.reason)}</td><td class="src">${src}</td></tr>`;
  }).join('');
  const table = m.plan.length ? `<div class="plan-wrap"><table class="plan-table"><thead><tr><th>#</th>${PLAN_COLUMNS.map(c => `<th>${c}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div>` : '';
  const missing = m.missing?.length ? `<div class="missing"><b>Cần bổ sung</b><ul>${m.missing.map(x => `<li>${E(x)}</li>`).join('')}</ul></div>` : '';
  const actions = m.plan.length ? `<div class="plan-actions"><button class="ghost-button" data-copy="${index}">${icon('note', 14)}Sao chép bảng</button><button class="ghost-button" data-csv="${index}">${icon('download', 14)}Xuất CSV</button><span>Bản nháp, cần điều dưỡng rà soát trước khi dùng.</span></div>` : '';
  return `<article class="message assistant wide"><div class="avatar">${icon('sparkles')}</div><div class="bubble"><div class="plan-title">${icon('table', 14)}Bảng kế hoạch điều dưỡng · ${m.plan.length} đầu mục</div>${m.content ? renderAnswer(m.content, sources) : ''}${table}${missing}${actions}</div></article>`;
}
function planToText(m) {
  const sources = m.sources || [];
  return (m.content ? m.content + '\n' : '') + m.plan.map((r, i) => {
    const c = planCells(r, sources);
    return `${i + 1}. ${c[0]} | Mục tiêu: ${c[1]} | Can thiệp: ${r.interventions.join('; ')} | Lượng giá: ${c[3]} | Lý do: ${c[4]} | Nguồn: ${c[5]}`;
  }).join('\n');
}
async function copyPlan(m) {
  const sources = m.sources || [];
  const body = m.plan.map((r, i) => `<tr><td>${i + 1}</td>${planCells(r, sources).map(c => `<td>${E(c).replace(/\n/g, '<br>')}</td>`).join('')}</tr>`).join('');
  const html = `<table border="1" cellpadding="4" style="border-collapse:collapse"><tr><th>#</th>${PLAN_COLUMNS.map(c => `<th>${c}</th>`).join('')}</tr>${body}</table>`;
  const tsv = ['#\t' + PLAN_COLUMNS.join('\t'), ...m.plan.map((r, i) => `${i + 1}\t` + planCells(r, sources).map(c => c.replace(/\s*\n\s*/g, ' ')).join('\t'))].join('\n');
  try {
    await navigator.clipboard.write([new ClipboardItem({'text/html': new Blob([html], {type: 'text/html'}), 'text/plain': new Blob([tsv], {type: 'text/plain'})})]);
  } catch {
    try { await navigator.clipboard.writeText(tsv); } catch { return toast('Trình duyệt không cho sao chép; dùng Xuất CSV.'); }
  }
  toast('Đã sao chép bảng: dán được vào Word hoặc Excel');
}
function exportPlanCsv(m) {
  const q = v => `"${String(v).replace(/"/g, '""')}"`;
  const lines = [['#', ...PLAN_COLUMNS].map(q).join(','), ...m.plan.map((r, i) => [i + 1, ...planCells(r, m.sources || [])].map(q).join(','))];
  const blob = new Blob(['﻿' + lines.join('\r\n')], {type: 'text/csv;charset=utf-8'});
  const a = Object.assign(document.createElement('a'), {href: URL.createObjectURL(blob), download: `ke-hoach-dieu-duong-${nowLocal().slice(0, 10)}.csv`});
  a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function renderMessages() {
  $('#welcome').hidden = state.messages.length > 0;
  $('#messages').innerHTML = state.messages.map((m, index) => {
    if (m.kind === 'plan') return renderPlan(m, index);
    if (m.role === 'user') {
      const ctx = [m.withJournal ? `${m.withJournal} ghi chép nhật ký` : '', m.withOrders ? 'y lệnh nội trú' : ''].filter(Boolean).join(' · ');
      return `<article class="message user"><div class="bubble">${E(m.content).replace(/\n/g, '<br>')}</div>${ctx ? `<span class="meta">${icon('note', 12)} kèm ${ctx}</span>` : ''}</article>`;
    }
    if (m.pending) return `<article class="message assistant"><div class="avatar">${icon('sparkles')}</div><div class="bubble pending"><span class="spin">${icon('loader')}</span>${m.planMode ? 'Đang tìm nguồn và lập bảng kế hoạch… (có thể mất 1–2 phút)' : 'Đang tìm nguồn và soạn câu trả lời…'}</div></article>`;
    const sources = m.sources || [];
    const cited = sources.filter(s => (m.cited || []).includes(s.id));
    const listed = cited.length ? cited : sources;
    const refs = listed.length ? `<div class="refs"><b>${cited.length ? 'Nguồn đã trích' : 'Nguồn tìm được'}</b>${listed.map(s => `<button class="ref" data-source="${E(s.id)}"><span>S${sources.indexOf(s) + 1}</span>Tr. ${s.page} · ${E(shortChapter(s.chapter))}</button>`).join('')}</div>` : '';
    const mode = m.mode && m.mode !== 'hybrid' ? `<span class="meta">Tìm kiếm: ${E(m.mode)}</span>` : '';
    return `<article class="message assistant"><div class="avatar">${icon('sparkles')}</div><div class="bubble ${m.status === 'no_evidence' ? 'muted' : ''}">${renderAnswer(m.content, sources)}${refs}${mode}</div></article>`;
  }).join('');
  const area = $('#chat-area'); area.scrollTop = area.scrollHeight;
}

/* ---------- Gửi câu hỏi ---------- */
async function ask(question, mode = 'auto') {
  if (state.busy || !question.trim()) return;
  showError('');
  const history = state.messages.filter(m => !m.pending && (m.content || m.plan?.length)).slice(-10)
    .map(m => ({role: m.role, content: (m.kind === 'plan' ? planToText(m) : m.content).slice(0, 4000)}));
  const journal = journalForRequest(), orders = ordersForRequest();
  state.messages.push({role: 'user', content: question, withJournal: journal.length, withOrders: !!orders.orders});
  state.messages.push({role: 'assistant', pending: true, planMode: mode === 'plan' || /k(ế|e) ho(ạ|a)ch/i.test(question)});
  state.busy = true; $('#send').disabled = $('#plan-button').disabled = true; renderMessages();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ((state.timeout || 90) + 15) * 1000);
  try {
    const res = await fetch('/api/chat', {method: 'POST', headers: {'Content-Type': 'application/json'}, signal: controller.signal,
      body: JSON.stringify({message: question, messages: history, journal, ...orders, chapter: $('#chapter').value, mode})});
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const d = data.detail;
      const msg = typeof d === 'string' ? d : d?.error || (Array.isArray(d) ? 'Dữ liệu gửi đi không hợp lệ (quá dài?).' : `Lỗi máy chủ (HTTP ${res.status}).`);
      throw new Error(d?.request_id ? `${msg} Mã yêu cầu: ${d.request_id}` : msg);
    }
    state.messages.pop();
    state.messages.push({role: 'assistant', content: data.answer, sources: data.sources, cited: data.citedSourceIds, status: data.status, mode: data.retrieval_mode,
      kind: data.kind, plan: data.plan || [], missing: data.missingInfo || []});
  } catch (err) {
    state.messages.pop(); state.messages.pop();
    $('#question').value = question;
    showError(err.name === 'AbortError' ? 'Máy chủ phản hồi quá lâu. Thử lại sau.' : (err.message || 'Không kết nối được máy chủ. Kiểm tra cửa sổ start.cmd còn mở.'));
  } finally {
    clearTimeout(timer); state.busy = false; $('#send').disabled = $('#plan-button').disabled = false; renderMessages();
  }
}
$('#composer').addEventListener('submit', ev => { ev.preventDefault(); const q = $('#question').value.trim(); if (!q) return; $('#question').value = ''; ask(q); });
$('#question').addEventListener('keydown', ev => { if (ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing) { ev.preventDefault(); $('#composer').requestSubmit(); } });
document.querySelectorAll('.suggestions [data-q]').forEach(b => b.addEventListener('click', () => ask(b.dataset.q, b.dataset.mode || 'auto')));
$('#plan-button').addEventListener('click', () => {
  const typed = $('#question').value.trim();
  if (!typed && !state.journal.length && !state.orders.text.trim()) return toast('Ghi nhật ký diễn biến, y lệnh hoặc mô tả người bệnh trước khi lập bảng.');
  $('#question').value = '';
  ask(typed || 'Lập bảng kế hoạch điều dưỡng cho người bệnh theo nhật ký diễn biến và y lệnh.', 'plan');
});
$('#new-chat').addEventListener('click', () => { if (state.busy) return; state.messages = []; showError(''); renderMessages(); $('#question').focus(); });

/* ---------- Xem nguồn ---------- */
const ALLOWED = new Set(['TABLE', 'THEAD', 'TBODY', 'TR', 'TD', 'TH', 'BR', 'SUP', 'SUB', 'B', 'STRONG', 'I', 'EM', 'P', 'UL', 'OL', 'LI']);
function sanitize(text) {
  const doc = new DOMParser().parseFromString(`<div>${text}</div>`, 'text/html');
  const clean = node => {
    for (const child of [...node.childNodes]) {
      if (child.nodeType === 3) continue;
      if (child.nodeType !== 1 || !ALLOWED.has(child.tagName)) { child.replaceWith(document.createTextNode(child.textContent || '')); continue; }
      for (const attr of [...child.attributes]) if (!['colspan', 'rowspan'].includes(attr.name)) child.removeAttribute(attr.name);
      clean(child);
    }
  };
  const root = doc.body.firstChild; clean(root); return root.innerHTML;
}
function findSource(id) { for (const m of state.messages) { const s = (m.sources || []).find(x => x.id === id); if (s) return s; } return null; }
function openSource(id) {
  const s = findSource(id); if (!s) return;
  $('#modal-eyebrow').textContent = `Trang ${s.page} · ${s.id}`;
  $('#modal-title').textContent = shortChapter(s.chapter);
  const flags = s.reviewFlags || [];
  $('#modal-flags').hidden = !flags.length;
  $('#modal-flags').textContent = flags.length ? 'Cần đối chiếu ảnh gốc: ' + flags.join(', ') : '';
  $('#modal-text').innerHTML = sanitize(s.text);
  $('#modal-image').innerHTML = `<img src="/api/page-image/${Number(s.page)}" alt="Ảnh trang ${Number(s.page)}" loading="lazy">`;
  switchView('text'); $('#modal').hidden = false; $('#modal-close').focus();
}
function switchView(view) {
  document.querySelectorAll('.modal-tabs button').forEach(b => b.classList.toggle('active', b.dataset.view === view));
  $('#modal-text').hidden = view !== 'text'; $('#modal-image').hidden = view !== 'image';
}
document.querySelectorAll('.modal-tabs button').forEach(b => b.addEventListener('click', () => switchView(b.dataset.view)));
$('#messages').addEventListener('click', ev => {
  const b = ev.target.closest('[data-source]'); if (b) return openSource(b.dataset.source);
  const c = ev.target.closest('[data-copy]'); if (c) return copyPlan(state.messages[Number(c.dataset.copy)]);
  const v = ev.target.closest('[data-csv]'); if (v) return exportPlanCsv(state.messages[Number(v.dataset.csv)]);
});
$('#modal-close').addEventListener('click', () => $('#modal').hidden = true);
$('#modal').addEventListener('click', ev => { if (ev.target.id === 'modal') $('#modal').hidden = true; });
document.addEventListener('keydown', ev => { if (ev.key === 'Escape') $('#modal').hidden = true; });

/* ---------- Khởi động ---------- */
async function init() {
  icons();
  state.journal = loadJournal(); state.orders = loadOrders(); renderOrders();
  $('#journal-time').value = nowLocal();
  renderJournal(); renderMessages();
  try {
    const st = await (await fetch('/api/status')).json();
    state.timeout = st.timeout_seconds;
    const el = $('#status');
    el.classList.add(st.configured ? 'ok' : 'warn');
    el.lastChild.textContent = st.configured ? `${st.model.split('/').pop()} · ${st.retrieval}` : 'Chưa có API key';
  } catch { $('#status').classList.add('warn'); $('#status').lastChild.textContent = 'Mất kết nối máy chủ'; }
  try {
    const kb = await (await fetch('/api/knowledge')).json();
    $('#chapter').insertAdjacentHTML('beforeend', kb.chapters.map(c => `<option value="${E(c.id)}">${E(shortChapter(c.title))}</option>`).join(''));
  } catch { /* bộ lọc quy trình là tùy chọn */ }
}
init();
