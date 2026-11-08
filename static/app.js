/**
 * app.js — ArthVani SPA (ES modules, vanilla JS)
 * Royal Rose design system v2.0
 * No React/Vue; plain DOM + fetch.
 */

// ═══════════════════════════════════════════════════════════
// 1. STATE
// ═══════════════════════════════════════════════════════════

const state = {
  lang:        localStorage.getItem('av_lang')   || 'hi',
  shopName:    localStorage.getItem('av_shop')   || '',
  strings:     {},          // loaded from /api/i18n/{lang}
  unitOptions: [],          // loaded from /api/i18n
  unitLabels:  {},

  // Speak
  mediaRecorder:  null,
  audioChunks:    [],
  recTimer:       null,
  recSeconds:     0,
  waveAnim:       null,
  analyser:       null,
  audioCtx:       null,
  pendingEntry:   null,     // {parsed, transcript, readback}
  savedId:        null,     // last saved id (for undo)

  // Ledger
  ledgerPage:   0,
  ledgerLimit:  20,
  ledgerTotal:  0,
  ledgerFilter: '',
  ledgerSearch: '',
  ledgerDate:   '',

  // Reports
  reportPeriod: '7d',

  // Chart instances
  chart14d:   null,
  chartDonut: null,

  // Delete dialog target
  deleteTargetId: null,
};

// ═══════════════════════════════════════════════════════════
// 2. BOOT
// ═══════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', async () => {
  await loadI18n(state.lang);
  applyLangUI(state.lang);
  renderGreeting();
  setDate();
  loadShopName();
  checkApiHealth();
  checkMicStatus();
  wireNav();
  wireSidebar();
  wireLangButtons();
  wireSpeakTab();
  wireLedgerTab();
  wireReportsTab();
  wireSettingsTab();
  wireTopbar();
  routeHash();
  window.addEventListener('hashchange', routeHash);
});

// ═══════════════════════════════════════════════════════════
// 3. i18n
// ═══════════════════════════════════════════════════════════

async function loadI18n(lang) {
  try {
    const res  = await fetch(`/api/i18n/${lang}`);
    const data = await res.json();
    state.strings     = data;
    state.unitOptions = data._unit_options || ['kg','g','litre','dozen','packet','piece'];
    state.unitLabels  = data._unit_labels  || {};
    updateI18nDOM();
    populateUnitSelects();
  } catch(e) { console.warn('i18n load failed', e); }
}

function s(key, fallback = '') {
  return state.strings[key] || fallback || key;
}

function updateI18nDOM() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    const val = s(key);
    if (!val) return;
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
      el.placeholder = val;
    } else {
      el.textContent = val;
    }
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.placeholder = s(el.dataset.i18nPlaceholder);
  });
}

function populateUnitSelects() {
  document.querySelectorAll('#revUnit, #editUnit').forEach(sel => {
    const cur = sel.value;
    sel.innerHTML = '';
    state.unitOptions.forEach(u => {
      const opt = document.createElement('option');
      opt.value = u;
      opt.textContent = state.unitLabels[u] || u;
      sel.appendChild(opt);
    });
    if (cur) sel.value = cur;
  });
}

// ═══════════════════════════════════════════════════════════
// 4. LANGUAGE SWITCH
// ═══════════════════════════════════════════════════════════

function applyLangUI(lang) {
  document.documentElement.lang = lang === 'hi' ? 'hi' : 'en';
  ['langHi','langEn','settLangHi','settLangEn'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    const isHi = id.endsWith('Hi');
    el.classList.toggle('active', (lang === 'hi') === isHi);
    el.setAttribute('aria-pressed', String((lang === 'hi') === isHi));
  });
}

function switchLang(lang) {
  if (lang === state.lang) return;
  state.lang = lang;
  localStorage.setItem('av_lang', lang);
  applyLangUI(lang);
  loadI18n(lang).then(() => {
    renderGreeting();
    refreshDashboard();
    refreshLedger();
    refreshReports();
  });
}

// ═══════════════════════════════════════════════════════════
// 5. NAV / ROUTING
// ═══════════════════════════════════════════════════════════

function routeHash() {
  const hash = location.hash.replace('#', '') || 'dashboard';
  showTab(hash);
}

function showTab(tabId) {
  const valid = ['dashboard','speak','ledger','reports','settings'];
  if (!valid.includes(tabId)) tabId = 'dashboard';

  document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
  const sec = document.getElementById(`tab-${tabId}`);
  if (sec) sec.classList.add('active');

  document.querySelectorAll('.nav-item, .bottom-tab').forEach(el => {
    el.classList.toggle('active', el.dataset.tab === tabId);
    if (el.dataset.tab === tabId) el.setAttribute('aria-current','page');
    else el.removeAttribute('aria-current');
  });

  const title = s(`nav_${tabId}`, tabId);
  const pageTitle = document.getElementById('pageTitle');
  if (pageTitle) pageTitle.textContent = title;

  // Lazy-load data
  if (tabId === 'dashboard') refreshDashboard();
  if (tabId === 'ledger')    refreshLedger();
  if (tabId === 'reports')   refreshReports();
}

function wireNav() {
  document.querySelectorAll('.nav-item, .bottom-tab').forEach(el => {
    el.addEventListener('click', e => {
      const tab = el.dataset.tab;
      if (tab) {
        e.preventDefault();
        location.hash = `#${tab}`;
      }
    });
  });
  document.getElementById('dashSpeakBtn')?.addEventListener('click', () => { location.hash = '#speak'; });
  document.getElementById('topbarSpeakBtn')?.addEventListener('click', () => { location.hash = '#speak'; });
}

function wireSidebar() {
  const sidebar  = document.getElementById('sidebar');
  const toggle   = document.getElementById('menuToggle');
  let overlay    = document.getElementById('sidebarOverlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'sidebarOverlay';
    document.body.appendChild(overlay);
  }
  toggle?.addEventListener('click', () => {
    const open = sidebar.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(open));
    overlay.classList.toggle('show', open);
  });
  overlay.addEventListener('click', () => {
    sidebar.classList.remove('open');
    overlay.classList.remove('show');
    toggle?.setAttribute('aria-expanded', 'false');
  });
}

function wireLangButtons() {
  document.getElementById('langHi')?.addEventListener('click', () => switchLang('hi'));
  document.getElementById('langEn')?.addEventListener('click', () => switchLang('en'));
  document.getElementById('settLangHi')?.addEventListener('click', () => switchLang('hi'));
  document.getElementById('settLangEn')?.addEventListener('click', () => switchLang('en'));
}

function wireTopbar() {
  document.getElementById('shopEditBtn')?.addEventListener('click', () => {
    location.hash = '#settings';
    setTimeout(() => document.getElementById('shopNameInput')?.focus(), 300);
  });
}

// ═══════════════════════════════════════════════════════════
// 6. SHOP NAME
// ═══════════════════════════════════════════════════════════

function loadShopName() {
  const name = localStorage.getItem('av_shop') || '';
  const display = document.getElementById('shopNameDisplay');
  const input   = document.getElementById('shopNameInput');
  if (display && name) display.textContent = name;
  if (input)  input.value = name;
}

function wireSettingsTab() {
  document.getElementById('saveShopName')?.addEventListener('click', () => {
    const val = document.getElementById('shopNameInput')?.value.trim();
    if (!val) return;
    localStorage.setItem('av_shop', val);
    state.shopName = val;
    const disp = document.getElementById('shopNameDisplay');
    if (disp) disp.textContent = val;
    showToast(s('saved','Saved!'), 'success');
  });
  document.getElementById('settLoadDemo')?.addEventListener('click', loadDemoData);
  document.getElementById('settClearDemo')?.addEventListener('click', clearDemoData);
  document.getElementById('ledgerDemoBtn')?.addEventListener('click', loadDemoData);

  // Test connection button
  document.getElementById('testConnBtn')?.addEventListener('click', async () => {
    const btn    = document.getElementById('testConnBtn');
    const result = document.getElementById('diagResult');
    if (!btn || !result) return;
    btn.disabled    = true;
    btn.textContent = s('testing','Testing…');
    result.style.display = 'none';
    try {
      const res  = await fetch('/api/diagnostics');
      const data = await res.json();
      const rows = [
        { label: 'API key configured', ok: data.api_key_configured },
        { label: 'ffmpeg available',   ok: data.ffmpeg_available   },
        { label: 'STT reachable',      ok: data.stt_reachable      },
        { label: 'TTS reachable',      ok: data.tts_reachable      },
      ];
      result.innerHTML = rows.map(r =>
        `<div class="diag-row">
          <span class="diag-dot ${r.ok ? 'ok' : 'err'}"></span>
          <span>${r.label}</span>
          <strong>${r.ok ? '✓ OK' : '✗ Not found'}</strong>
        </div>`
      ).join('');
      result.style.display = '';
    } catch {
      result.textContent   = s('error_network','Network error — is the server running?');
      result.style.display = '';
    } finally {
      btn.disabled    = false;
      btn.textContent = s('test_connection','Test connection');
    }
  });
}

// ═══════════════════════════════════════════════════════════
// 7. API STATUS
// ═══════════════════════════════════════════════════════════

async function checkApiHealth() {
  const chip = document.getElementById('apiStatusChip');
  if (!chip) return;
  try {
    const res  = await fetch('/api/health');
    const data = await res.json();
    chip.classList.toggle('ok',  data.api_key_configured);
    chip.classList.toggle('err', !data.api_key_configured);
  } catch {
    chip.classList.add('err');
  }
}

async function checkMicStatus() {
  const chip = document.getElementById('micStatusChip');
  if (!chip) return;
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const hasMic  = devices.some(d => d.kind === 'audioinput');
    chip.classList.toggle('ok',  hasMic);
    chip.classList.toggle('err', !hasMic);
  } catch {
    chip.classList.add('err');
  }
}

// ═══════════════════════════════════════════════════════════
// 8. DASHBOARD
// ═══════════════════════════════════════════════════════════

async function refreshDashboard() {
  try {
    const res  = await fetch('/api/summary');
    const data = await res.json();
    renderStats(data.today);
    renderChart(data.series_14d);
    renderTopItems(data.top_items || []);
    renderRecent(data.recent || []);
  } catch(e) { console.warn('dashboard error', e); }
}

function renderStats(today) {
  if (!today) return;
  animateCount('statSales',     today.sales,     true);
  animateCount('statPurchases', today.purchases,  true);
  animateCount('statNet',       today.net,        true);
  animateCount('statEntries',   today.count,      false);
}

function animateCount(id, target, isCurrency) {
  const el = document.getElementById(id);
  if (!el) return;
  const start = 0, dur = 800;
  const st = performance.now();
  function step(now) {
    const p = Math.min((now - st) / dur, 1);
    const val = start + (target - start) * easeOut(p);
    el.textContent = isCurrency ? fmtInr(val) : Math.round(val).toString();
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
function easeOut(t) { return 1 - Math.pow(1 - t, 3); }

function renderChart(series) {
  if (!series || !series.length) return;
  const canvas = document.getElementById('chart14d');
  if (!canvas || typeof Chart === 'undefined') return;

  const labels = series.map(d => {
    const [,m,day] = d.date.split('-');
    return `${day}/${m}`;
  });
  const sales     = series.map(d => d.sales);
  const purchases = series.map(d => d.purchases);

  if (state.chart14d) state.chart14d.destroy();
  state.chart14d = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: s('today_sales','Sales'), data: sales, backgroundColor: 'rgba(184,51,106,.75)', borderRadius: 6, borderSkipped: false },
        { label: s('today_purchases','Purchases'), data: purchases, backgroundColor: 'rgba(99,102,241,.55)', borderRadius: 6, borderSkipped: false },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { font: { family: 'Poppins' }, color: '#7A5568' } } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#7A5568', font: { size: 11 } } },
        y: { grid: { color: 'rgba(248,200,220,.4)' }, ticks: { color: '#7A5568', callback: v => '₹'+v } },
      },
    },
  });
}

function renderTopItems(items) {
  const el = document.getElementById('topItemsList');
  if (!el) return;
  if (!items.length) { el.innerHTML = `<p style="color:var(--text-sec);font-size:.88rem">${s('empty_table','No data')}</p>`; return; }
  const max = items[0].total || 1;
  el.innerHTML = items.map(it => `
    <div class="top-item">
      <span class="top-item-name">${esc(it.item)}</span>
      <div class="top-item-bar-wrap"><div class="top-item-bar" style="width:${Math.round(it.total/max*100)}%"></div></div>
      <span class="top-item-amt">${fmtInr(it.total)}</span>
    </div>
  `).join('');
}

function renderRecent(rows) {
  const el = document.getElementById('recentEntriesList');
  if (!el) return;
  if (!rows.length) { el.innerHTML = `<p style="color:var(--text-sec);font-size:.88rem">${s('empty_table','No entries')}</p>`; return; }
  el.innerHTML = rows.map(r => `
    <div class="recent-row">
      <span class="recent-item">${esc(r.item)}</span>
      <span class="pill pill-${r.entry_type}">${r.entry_type === 'sale' ? s('sale','Sale') : s('purchase','Purchase')}</span>
      <span class="recent-total">${fmtInr(r.total)}</span>
    </div>
  `).join('');
}

function renderGreeting() {
  const el = document.getElementById('greeting');
  if (!el) return;
  const h = new Date().getHours();
  let key = h < 12 ? 'greeting_morning' : h < 17 ? 'greeting_afternoon' : 'greeting_evening';
  const shop = localStorage.getItem('av_shop') || '';
  const greet = s(key, h < 12 ? (state.lang === 'hi' ? 'सुप्रभात' : 'Good morning') : h < 17 ? (state.lang === 'hi' ? 'नमस्ते' : 'Good afternoon') : (state.lang === 'hi' ? 'शुभ संध्या' : 'Good evening'));
  el.textContent = shop ? `${greet}, ${shop}` : greet;
}

function setDate() {
  const el = document.getElementById('topbarDate');
  if (!el) return;
  const now = new Date();
  el.textContent = now.toLocaleDateString(state.lang === 'hi' ? 'hi-IN' : 'en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

// ═══════════════════════════════════════════════════════════
// 9. SPEAK TAB
// ═══════════════════════════════════════════════════════════

function wireSpeakTab() {
  document.getElementById('micBtn')?.addEventListener('click', toggleRecording);
  document.addEventListener('keydown', e => {
    if (e.code === 'Space' && document.getElementById('tab-speak')?.classList.contains('active') && !e.target.closest('input,textarea,select')) {
      e.preventDefault();
      toggleRecording();
    }
  });

  document.getElementById('saveBtn')?.addEventListener('click', saveEntry);
  document.getElementById('rerecordBtn')?.addEventListener('click', reRecord);
  document.getElementById('discardBtn')?.addEventListener('click', discardEntry);
  document.getElementById('replayBtn')?.addEventListener('click', replayTts);
  document.getElementById('manualParseBtn')?.addEventListener('click', manualParse);

  // Live total update
  ['revQty','revPrice'].forEach(id => {
    document.getElementById(id)?.addEventListener('input', updateLiveTotal);
  });

  // Type buttons
  document.querySelectorAll('.type-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.type-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });

  // Example chips → fill manual text
  document.querySelectorAll('#exampleChips .chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const txt = document.getElementById('manualText');
      if (txt) {
        txt.value = chip.textContent;
        document.querySelector('.type-fallback')?.setAttribute('open', '');
        txt.focus();
      }
    });
  });
}

// ── Recording ────────────────────────────────────────────

async function toggleRecording() {
  if (state.mediaRecorder && state.mediaRecorder.state === 'recording') {
    stopRecording();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch(e) {
    showToast(s('error_mic_denied', 'Microphone access denied. Please allow mic in browser settings.'), 'error');
    return;
  }
  checkMicStatus();

  state.audioChunks  = [];
  state.audioCtx     = new (window.AudioContext || window.webkitAudioContext)();
  const source       = state.audioCtx.createMediaStreamSource(stream);
  state.analyser     = state.audioCtx.createAnalyser();
  state.analyser.fftSize = 256;
  source.connect(state.analyser);
  drawWaveform();

  const mimeType = getSupportedMimeType();
  state.mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
  state.mediaRecorder.addEventListener('dataavailable', e => { if (e.data.size > 0) state.audioChunks.push(e.data); });
  state.mediaRecorder.addEventListener('stop', onRecordStop);
  state.mediaRecorder.start(100);

  // UI
  const btn = document.getElementById('micBtn');
  if (btn) { btn.classList.add('recording'); btn.setAttribute('aria-pressed','true'); }
  document.getElementById('micTimer').textContent = '0s';
  setStep(0);

  state.recSeconds = 0;
  state.recTimer   = setInterval(() => {
    state.recSeconds++;
    const timer = document.getElementById('micTimer');
    if (timer) timer.textContent = `${state.recSeconds}s`;
    if (state.recSeconds >= 60) stopRecording();  // max 60s
  }, 1000);
}

function stopRecording() {
  if (state.mediaRecorder?.state === 'recording') state.mediaRecorder.stop();
  clearInterval(state.recTimer);
  cancelAnimationFrame(state.waveAnim);
  state.audioCtx?.close();
  const btn = document.getElementById('micBtn');
  if (btn) { btn.classList.remove('recording'); btn.setAttribute('aria-pressed','false'); }
  document.getElementById('micTimer').textContent = '';
  clearWaveform();
}

function getSupportedMimeType() {
  const types = ['audio/webm;codecs=opus','audio/webm','audio/ogg;codecs=opus','audio/ogg','audio/mp4'];
  return types.find(t => MediaRecorder.isTypeSupported(t)) || '';
}

async function onRecordStop() {
  const blob = new Blob(state.audioChunks, { type: state.mediaRecorder.mimeType || 'audio/webm' });
  if (blob.size < 1000) { showToast(s('error_no_audio','No audio received.'), 'error'); return; }
  setStep(1);

  // Convert to 16 kHz mono PCM WAV before sending to Gnani
  let wavBlob;
  try {
    wavBlob = await convertToWav(blob);
  } catch (e) {
    console.warn('WAV conversion failed, sending raw blob:', e);
    wavBlob = blob;  // fallback; server _ensure_wav will try pydub
  }

  await sendAudio(wavBlob);
}

/**
 * Convert any browser audio blob to 16 kHz mono 16-bit PCM WAV.
 * Uses Web Audio API — no server ffmpeg required.
 */
async function convertToWav(blob) {
  // 1. Decode the browser blob (webm/opus, mp4/aac, etc.)
  const arrayBuffer = await blob.arrayBuffer();
  const tempCtx = new (window.AudioContext || window.webkitAudioContext)();
  let decoded;
  try {
    decoded = await tempCtx.decodeAudioData(arrayBuffer);
  } finally {
    await tempCtx.close();
  }

  // 2. Silence check: compute RMS on first channel
  const rawPcm = decoded.getChannelData(0);
  let sumSq = 0;
  for (let i = 0; i < rawPcm.length; i++) sumSq += rawPcm[i] * rawPcm[i];
  const rms = Math.sqrt(sumSq / rawPcm.length);
  if (rms < 0.001) {
    throw new Error(s('error_silence', "I couldn't hear anything. Please try again."));
  }

  // 3. Resample to 16000 Hz mono via OfflineAudioContext
  const targetRate = 16000;
  const numFrames  = Math.ceil(decoded.duration * targetRate);
  const offCtx     = new OfflineAudioContext(1, numFrames, targetRate);
  const src        = offCtx.createBufferSource();
  src.buffer       = decoded;

  // Mix down to mono by summing channels via ChannelMergerNode
  if (decoded.numberOfChannels > 1) {
    const merger = offCtx.createChannelMerger(decoded.numberOfChannels);
    for (let ch = 0; ch < decoded.numberOfChannels; ch++) {
      src.connect(merger, 0, ch);
    }
    // Create a gain to average the channels
    const gain = offCtx.createGain();
    gain.gain.value = 1 / decoded.numberOfChannels;
    merger.connect(gain);
    gain.connect(offCtx.destination);
  } else {
    src.connect(offCtx.destination);
  }
  src.start(0);
  const resampled = await offCtx.startRendering();

  // 4. Convert Float32 PCM → Int16
  const pcmFloat = resampled.getChannelData(0);
  const int16    = new Int16Array(pcmFloat.length);
  for (let i = 0; i < pcmFloat.length; i++) {
    const clamped = Math.max(-1, Math.min(1, pcmFloat[i]));
    int16[i] = clamped < 0 ? clamped * 32768 : clamped * 32767;
  }

  // 5. Write RIFF/WAV header + PCM data
  const dataLen   = int16.byteLength;
  const wavBuffer = new ArrayBuffer(44 + dataLen);
  const v         = new DataView(wavBuffer);
  const write4    = (off, str) => { for (let i = 0; i < 4; i++) v.setUint8(off + i, str.charCodeAt(i)); };
  const write2    = (off, n)   => v.setUint16(off, n, true);
  const write4i   = (off, n)   => v.setUint32(off, n, true);

  write4 (0,  'RIFF');
  write4i(4,  36 + dataLen);       // ChunkSize
  write4 (8,  'WAVE');
  write4 (12, 'fmt ');
  write4i(16, 16);                 // Subchunk1Size (PCM)
  write2 (20, 1);                  // AudioFormat = PCM
  write2 (22, 1);                  // NumChannels = mono
  write4i(24, targetRate);         // SampleRate
  write4i(28, targetRate * 2);     // ByteRate = SampleRate × NumChannels × BitsPerSample/8
  write2 (32, 2);                  // BlockAlign = NumChannels × BitsPerSample/8
  write2 (34, 16);                 // BitsPerSample
  write4 (36, 'data');
  write4i(40, dataLen);            // Subchunk2Size
  new Uint8Array(wavBuffer, 44).set(new Uint8Array(int16.buffer));

  return new Blob([wavBuffer], { type: 'audio/wav' });
}

async function sendAudio(wavBlob) {
  const form = new FormData();
  form.append('audio_file', wavBlob, 'recording.wav');
  form.append('language', state.lang);
  try {
    const res  = await fetch('/api/transcribe', { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) { showToast(data.detail || s('error_stt','STT failed'), 'error'); setStep(0); return; }
    setStep(2);
    showTranscript(data.transcript);
    showReviewCard(data.parsed, data.transcript, data.readback);
    await playTts(data.readback);
  } catch(e) {
    if (e.message && e.message.includes("couldn't hear")) {
      showToast(e.message, 'warning');
    } else {
      showToast(s('error_network','Network error.'), 'error');
    }
    setStep(0);
  }
}

// ── Waveform ─────────────────────────────────────────────

function drawWaveform() {
  const canvas = document.getElementById('waveform');
  if (!canvas || !state.analyser) return;
  const ctx    = canvas.getContext('2d');
  const buf    = new Uint8Array(state.analyser.frequencyBinCount);
  function loop() {
    state.waveAnim = requestAnimationFrame(loop);
    state.analyser.getByteFrequencyData(buf);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const barW = canvas.width / buf.length * 2.5;
    let x = 0;
    buf.forEach(val => {
      const h = (val / 255) * canvas.height;
      const g = ctx.createLinearGradient(0, canvas.height - h, 0, canvas.height);
      g.addColorStop(0, '#E85D9A');
      g.addColorStop(1, '#B8336A');
      ctx.fillStyle = g;
      ctx.fillRect(x, canvas.height - h, barW - 1, h);
      x += barW;
    });
  }
  loop();
}

function clearWaveform() {
  const canvas = document.getElementById('waveform');
  if (!canvas) return;
  canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
}

// ── Stepper ───────────────────────────────────────────────

function setStep(n) {
  for (let i = 0; i <= 3; i++) {
    const el = document.getElementById(`step${i}`);
    if (!el) continue;
    el.classList.remove('active', 'done');
    if (i < n)  el.classList.add('done');
    if (i === n) el.classList.add('active');
  }
}

// ── Transcript bubble ─────────────────────────────────────

function showTranscript(text) {
  const bubble = document.getElementById('transcriptBubble');
  const txt    = document.getElementById('transcriptText');
  if (txt)    txt.textContent = text || '';
  if (bubble) bubble.style.display = text ? '' : 'none';
}

// ── Review card ───────────────────────────────────────────

function showReviewCard(parsed, transcript, readback) {
  state.pendingEntry = { parsed, transcript, readback };
  const card = document.getElementById('reviewCard');
  if (!card) return;

  // Fill fields
  document.getElementById('revItem').value  = parsed.item    || '';
  document.getElementById('revQty').value   = parsed.quantity ?? '';
  document.getElementById('revPrice').value = parsed.price   ?? '';
  const unit = parsed.unit || 'piece';
  document.getElementById('revUnit').value  = unit;

  // Type toggle
  const isP = parsed.entry_type === 'purchase';
  document.getElementById('typeSale').classList.toggle('active', !isP);
  document.getElementById('typePurchase').classList.toggle('active', isP);

  // Warning
  const warn = document.getElementById('reviewWarn');
  if (warn) warn.style.display = parsed.needs_review ? '' : 'none';

  // Highlight missing
  ['revItem','revQty','revPrice'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle('error', !el.value);
  });

  updateLiveTotal();
  card.style.display = '';
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function updateLiveTotal() {
  const qty   = parseFloat(document.getElementById('revQty')?.value)   || 0;
  const price = parseFloat(document.getElementById('revPrice')?.value) || 0;
  const total = Math.round(qty * price * 100) / 100;
  const el    = document.getElementById('revTotal');
  if (el) el.textContent = fmtInr(total);
}

// ── TTS ───────────────────────────────────────────────────

async function playTts(text) {
  if (!text) return;
  try {
    const res = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, language: state.lang }),
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const audio = document.getElementById('ttsAudio');
    if (audio) { audio.src = url; await audio.play().catch(() => {}); }
  } catch { /* TTS is best-effort */ }
}

function replayTts() {
  if (state.pendingEntry?.readback) playTts(state.pendingEntry.readback);
}

// ── Save / Re-record / Discard ────────────────────────────

async function saveEntry() {
  const item  = document.getElementById('revItem')?.value.trim();
  const qty   = parseFloat(document.getElementById('revQty')?.value);
  const price = parseFloat(document.getElementById('revPrice')?.value);
  const unit  = document.getElementById('revUnit')?.value;
  const type  = document.querySelector('.type-btn.active')?.dataset.type || 'sale';

  if (!item || isNaN(qty) || isNaN(price)) {
    showToast(s('needs_review','Please fill all required fields.'), 'warning');
    ['revItem','revQty','revPrice'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.classList.toggle('error', !el.value);
    });
    return;
  }

  const payload = {
    item, quantity: qty, unit, price, entry_type: type,
    language:   state.lang,
    transcript: state.pendingEntry?.transcript || '',
  };

  const btn = document.getElementById('saveBtn');
  if (btn) { btn.disabled = true; btn.textContent = s('processing','Saving…'); }

  try {
    const res  = await fetch('/api/entries', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) { showToast(data.detail || s('error_save','Save failed.'), 'error'); return; }

    state.savedId = data.id;
    setStep(3);
    resetReviewCard();
    showToast(s('saved','Entry saved!'), 'success', true);  // with undo
    refreshDashboard();
    refreshLedger();
  } catch {
    showToast(s('error_network','Network error.'), 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = s('save_entry','Save entry'); }
  }
}

function reRecord() {
  resetReviewCard();
  setStep(0);
  showTranscript('');
}

function discardEntry() {
  resetReviewCard();
  setStep(0);
  showTranscript('');
  showToast(s('discarded','Entry discarded.'), 'warning');
}

function resetReviewCard() {
  state.pendingEntry = null;
  const card = document.getElementById('reviewCard');
  if (card) card.style.display = 'none';
  ['revItem','revQty','revPrice'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.value = ''; el.classList.remove('error'); }
  });
  document.getElementById('revTotal').textContent = '₹0.00';
}

// ── Manual parse ──────────────────────────────────────────

async function manualParse() {
  const text = document.getElementById('manualText')?.value.trim();
  if (!text) return;
  try {
    const res  = await fetch('/api/parse-text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, language: state.lang }),
    });
    const data = await res.json();
    if (!res.ok) { showToast(data.detail || s('error_stt','Parse failed'), 'error'); return; }
    setStep(2);
    showTranscript(text);
    showReviewCard(data.parsed, text, data.readback);
    await playTts(data.readback);
    location.hash = '#speak';
  } catch {
    showToast(s('error_network','Network error.'), 'error');
  }
}

// ═══════════════════════════════════════════════════════════
// 10. LEDGER TAB
// ═══════════════════════════════════════════════════════════

function wireLedgerTab() {
  let searchTimer;
  document.getElementById('ledgerSearch')?.addEventListener('input', e => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.ledgerSearch = e.target.value; state.ledgerPage = 0; refreshLedger(); }, 350);
  });

  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.ledgerFilter = btn.dataset.filter || '';
      state.ledgerPage   = 0;
      refreshLedger();
    });
  });

  document.getElementById('dateRangeSelect')?.addEventListener('change', e => {
    state.ledgerDate = e.target.value;
    state.ledgerPage = 0;
    refreshLedger();
  });

  document.getElementById('pagePrev')?.addEventListener('click', () => { if (state.ledgerPage > 0) { state.ledgerPage--; refreshLedger(); } });
  document.getElementById('pageNext')?.addEventListener('click', () => { state.ledgerPage++; refreshLedger(); });

  document.getElementById('exportXlsx')?.addEventListener('click', () => { window.location = `/api/export.xlsx?lang=${state.lang}`; });
  document.getElementById('exportCsv')?.addEventListener('click',  () => { window.location = `/api/export.csv?lang=${state.lang}`; });

  wireDeleteDialog();
  wireEditDialog();
}

function getDateRange(preset) {
  if (!preset) return { from: null, to: null };
  const now     = new Date();
  const toStr   = ymd(now);
  if (preset === 'today') return { from: toStr, to: toStr };
  const days    = preset === '7d' ? 6 : 29;
  const from    = new Date(now); from.setDate(from.getDate() - days);
  return { from: ymd(from), to: toStr };
}

function ymd(d) { return d.toISOString().slice(0,10); }

async function refreshLedger() {
  const { from, to } = getDateRange(state.ledgerDate);
  const params = new URLSearchParams({
    limit:  state.ledgerLimit,
    offset: state.ledgerPage * state.ledgerLimit,
    sort:   'created_at DESC',
  });
  if (state.ledgerFilter)  params.set('filter', state.ledgerFilter);
  if (state.ledgerSearch)  params.set('search', state.ledgerSearch);
  if (from) params.set('date_from', from);
  if (to)   params.set('date_to', to);

  try {
    const res  = await fetch(`/api/entries?${params}`);
    const data = await res.json();
    state.ledgerTotal = data.total;
    renderLedger(data.entries, data.total);
    updatePagination();
  } catch(e) { console.warn('ledger error', e); }
}

function renderLedger(rows, total) {
  const body  = document.getElementById('ledgerBody');
  const foot  = document.getElementById('ledgerFoot');
  const empty = document.getElementById('ledgerEmpty');
  if (!body) return;

  if (!rows.length) {
    body.innerHTML = '';
    foot.innerHTML = '';
    if (empty) empty.style.display = '';
    return;
  }
  if (empty) empty.style.display = 'none';

  const lang = state.lang;
  body.innerHTML = rows.map(r => `
    <tr>
      <td>${fmtDate(r.created_at)}</td>
      <td>${fmtTime(r.created_at)}</td>
      <td><span class="pill pill-${r.entry_type}">${r.entry_type === 'sale' ? s('sale','Sale') : s('purchase','Purch.')}</span></td>
      <td class="cell-item">${esc(r.item)}</td>
      <td>${r.quantity}</td>
      <td>${s(r.unit, r.unit) || r.unit || ''}</td>
      <td>${fmtInr(r.price)}</td>
      <td class="cell-total">${fmtInr(r.total)}</td>
      <td class="row-actions">
        <button class="row-action-btn" onclick="openEditDialog(${r.id})" title="${s('edit','Edit')}" aria-label="${s('edit','Edit')} ${esc(r.item)}">✏️</button>
        <button class="row-action-btn del" onclick="openDeleteDialog(${r.id})" title="${s('delete','Delete')}" aria-label="${s('delete','Delete')} ${esc(r.item)}">🗑️</button>
      </td>
    </tr>
  `).join('');

  // Totals footer
  const totSales = rows.filter(r => r.entry_type === 'sale').reduce((a,b) => a + b.total, 0);
  const totPurch = rows.filter(r => r.entry_type === 'purchase').reduce((a,b) => a + b.total, 0);
  foot.innerHTML = `
    <tr>
      <td colspan="6" style="text-align:right;font-weight:600">${s('total','Total')} (${rows.length} ${s('today_entries','entries')})</td>
      <td>${s('sale','Sales')}: ${fmtInr(totSales)}</td>
      <td colspan="2">${s('purchase','Purch.')}: ${fmtInr(totPurch)}</td>
    </tr>
  `;
}

function updatePagination() {
  const total = state.ledgerTotal;
  const page  = state.ledgerPage;
  const limit = state.ledgerLimit;
  const totalPages = Math.ceil(total / limit) || 1;

  const info = document.getElementById('pageInfo');
  if (info) info.textContent = `${page + 1} / ${totalPages}  (${total} ${s('today_entries','entries')})`;
  const prev = document.getElementById('pagePrev');
  const next = document.getElementById('pageNext');
  if (prev) prev.disabled = page === 0;
  if (next) next.disabled = page >= totalPages - 1;
}

// ── Edit dialog ───────────────────────────────────────────

function wireEditDialog() {
  document.getElementById('editQty')?.addEventListener('input',   updateEditTotal);
  document.getElementById('editPrice')?.addEventListener('input', updateEditTotal);
  document.getElementById('editSaveBtn')?.addEventListener('click', saveEdit);
  document.getElementById('editCancelBtn')?.addEventListener('click', () => document.getElementById('editDialog')?.close());
}

function updateEditTotal() {
  const qty   = parseFloat(document.getElementById('editQty')?.value)   || 0;
  const price = parseFloat(document.getElementById('editPrice')?.value) || 0;
  const el    = document.getElementById('editTotal');
  if (el) el.textContent = fmtInr(Math.round(qty * price * 100) / 100);
}

async function openEditDialog(id) {
  // Fetch fresh data
  const res  = await fetch(`/api/entries?limit=1000`);
  const data = await res.json();
  const row  = (data.entries || []).find(r => r.id === id);
  if (!row) return;

  document.getElementById('editId').value    = id;
  document.getElementById('editItem').value  = row.item;
  document.getElementById('editQty').value   = row.quantity;
  document.getElementById('editPrice').value = row.price;
  document.getElementById('editUnit').value  = row.unit || 'piece';
  updateEditTotal();
  document.getElementById('editDialog')?.showModal();
}
window.openEditDialog = openEditDialog;

async function saveEdit() {
  const id    = parseInt(document.getElementById('editId')?.value);
  const item  = document.getElementById('editItem')?.value.trim();
  const qty   = parseFloat(document.getElementById('editQty')?.value);
  const price = parseFloat(document.getElementById('editPrice')?.value);
  const unit  = document.getElementById('editUnit')?.value;
  if (!item || isNaN(qty) || isNaN(price)) return;

  try {
    const res = await fetch(`/api/entries/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ item, quantity: qty, price, unit }),
    });
    if (!res.ok) { showToast(s('error_save','Save failed.'), 'error'); return; }
    document.getElementById('editDialog')?.close();
    showToast(s('saved','Saved!'), 'success');
    refreshLedger();
    refreshDashboard();
  } catch { showToast(s('error_network','Network error.'), 'error'); }
}

// ── Delete dialog ─────────────────────────────────────────

function wireDeleteDialog() {
  document.getElementById('deleteConfirmBtn')?.addEventListener('click', confirmDelete);
  document.getElementById('deleteCancelBtn')?.addEventListener('click', () => document.getElementById('deleteDialog')?.close());
}

function openDeleteDialog(id) {
  state.deleteTargetId = id;
  document.getElementById('deleteDialog')?.showModal();
}
window.openDeleteDialog = openDeleteDialog;

async function confirmDelete() {
  const id = state.deleteTargetId;
  document.getElementById('deleteDialog')?.close();
  if (!id) return;
  try {
    await fetch(`/api/entries/${id}`, { method: 'DELETE' });
    showToast(s('delete_done','Entry deleted.'), 'success');
    refreshLedger();
    refreshDashboard();
  } catch { showToast(s('error_network','Network error.'), 'error'); }
}

// ═══════════════════════════════════════════════════════════
// 11. REPORTS TAB
// ═══════════════════════════════════════════════════════════

function wireReportsTab() {
  document.getElementById('reportPeriod')?.addEventListener('change', e => {
    state.reportPeriod = e.target.value;
    refreshReports();
  });
  document.getElementById('reportExportXlsx')?.addEventListener('click', () => {
    window.location = `/api/export.xlsx?lang=${state.lang}`;
  });
}

async function refreshReports() {
  try {
    const res  = await fetch('/api/summary');
    const data = await res.json();

    const period = state.reportPeriod;
    const { from, to } = getDateRange(period);
    const params = new URLSearchParams({ limit: 500, offset: 0 });
    if (from) params.set('date_from', from);
    if (to)   params.set('date_to', to);
    const eRes  = await fetch(`/api/entries?${params}`);
    const eData = await eRes.json();
    const entries = eData.entries || [];

    const totSales = entries.filter(r=>r.entry_type==='sale').reduce((a,b)=>a+b.total,0);
    const totPurch = entries.filter(r=>r.entry_type==='purchase').reduce((a,b)=>a+b.total,0);

    // Donut chart
    renderDonut(totSales, totPurch);

    // Top items
    const itemMap = {};
    entries.filter(r=>r.entry_type==='sale').forEach(r => {
      itemMap[r.item] = (itemMap[r.item]||0) + r.total;
    });
    const topItems = Object.entries(itemMap).sort((a,b)=>b[1]-a[1]).slice(0,5);
    const repTop = document.getElementById('reportTopItems');
    if (repTop) {
      repTop.innerHTML = topItems.map(([item, total]) => `
        <div class="report-summary-row">
          <span>${esc(item)}</span>
          <strong>${fmtInr(total)}</strong>
        </div>
      `).join('') || `<p style="color:var(--text-sec)">${s('empty_table','No data')}</p>`;
    }

    // Summary
    const repSum = document.getElementById('reportSummary');
    if (repSum) {
      repSum.innerHTML = `
        <div class="report-summary-row"><span>${s('today_sales','Sales')}</span><strong style="color:var(--success)">${fmtInr(totSales)}</strong></div>
        <div class="report-summary-row"><span>${s('today_purchases','Purchases')}</span><strong style="color:var(--raspberry)">${fmtInr(totPurch)}</strong></div>
        <div class="report-summary-row"><span>${s('today_net','Net')}</span><strong style="color:var(--plum-dk)">${fmtInr(totSales-totPurch)}</strong></div>
        <div class="report-summary-row"><span>${s('today_entries','Entries')}</span><strong>${entries.length}</strong></div>
      `;
    }
  } catch(e) { console.warn('reports error', e); }
}

function renderDonut(sales, purchases) {
  const canvas = document.getElementById('reportDonut');
  if (!canvas || typeof Chart === 'undefined') return;
  if (state.chartDonut) state.chartDonut.destroy();
  state.chartDonut = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: [s('today_sales','Sales'), s('today_purchases','Purchases')],
      datasets: [{
        data: [sales || 0, purchases || 0],
        backgroundColor: ['rgba(219,39,119,.8)', 'rgba(99,102,241,.75)'],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'bottom', labels: { font: { family: 'Poppins' }, color: '#7A5568', padding: 16 } },
      },
      cutout: '65%',
    },
  });
}

// ═══════════════════════════════════════════════════════════
// 12. DEMO DATA
// ═══════════════════════════════════════════════════════════

async function loadDemoData() {
  try {
    const res  = await fetch('/api/demo/load', { method: 'POST' });
    const data = await res.json();
    showToast(data.message || s('demo_loaded','Demo loaded!'), 'success');
    refreshDashboard();
    refreshLedger();
  } catch { showToast(s('error_network','Network error.'), 'error'); }
}

async function clearDemoData() {
  try {
    const res  = await fetch('/api/demo/clear', { method: 'POST' });
    const data = await res.json();
    showToast(data.message || s('clear_demo','Demo cleared.'), 'success');
    refreshDashboard();
    refreshLedger();
  } catch { showToast(s('error_network','Network error.'), 'error'); }
}

// ═══════════════════════════════════════════════════════════
// 13. TOAST
// ═══════════════════════════════════════════════════════════

function showToast(message, type = '', withUndo = false) {
  const area = document.getElementById('toastArea');
  if (!area) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.setAttribute('role', 'status');

  const msgSpan = document.createElement('span');
  msgSpan.textContent = message;
  toast.appendChild(msgSpan);

  if (withUndo && state.savedId) {
    const undoBtn = document.createElement('button');
    undoBtn.className = 'toast-undo';
    undoBtn.textContent = s('undo','Undo');
    const savedId = state.savedId;
    let undone = false;
    undoBtn.addEventListener('click', async () => {
      if (undone) return;
      undone = true;
      await fetch(`/api/entries/${savedId}`, { method: 'DELETE' });
      toast.remove();
      showToast(s('undo_done','Entry removed.'), 'success');
      refreshDashboard();
      refreshLedger();
    });
    toast.appendChild(undoBtn);
  }

  area.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity .3s'; setTimeout(() => toast.remove(), 350); }, 5000);
}

// ═══════════════════════════════════════════════════════════
// 14. UTILITY
// ═══════════════════════════════════════════════════════════

function fmtInr(n) {
  if (n == null || isNaN(n)) return '₹0';
  // Indian number format: 1,23,456.00
  const abs   = Math.abs(n);
  const fixed = abs.toFixed(2);
  const [int, dec] = fixed.split('.');
  let result = '';
  if (int.length <= 3) {
    result = int;
  } else {
    result = int.slice(-3);
    let rem = int.slice(0, -3);
    while (rem.length > 2) { result = rem.slice(-2) + ',' + result; rem = rem.slice(0,-2); }
    if (rem) result = rem + ',' + result;
  }
  return (n < 0 ? '-' : '') + '₹' + result + '.' + dec;
}

function fmtDate(ts) {
  if (!ts) return '';
  const [date] = ts.split('T');
  const [y,m,d] = date.split('-');
  return `${d}-${m}-${y}`;
}

function fmtTime(ts) {
  if (!ts) return '';
  return ts.slice(11, 16);
}

function esc(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

