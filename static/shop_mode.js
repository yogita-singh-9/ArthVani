/**
 * shop_mode.js — Hands-free shop mode for ArthVani.
 *
 * State machine:
 *   IDLE → LISTENING → TRANSCRIBING → PARSED → READBACK → AWAIT → SAVED → LISTENING
 *
 * Features:
 *   - Energy-based VAD (AnalyserNode) with adaptive noise floor
 *   - 16 kHz mono 16-bit WAV encoding in browser
 *   - Serialised API queue (one request at a time, retry on 429)
 *   - Mic paused during TTS + 400 ms tail
 *   - Screen Wake Lock
 *   - Web Audio API earcons (tick / chime / buzz)
 *   - Auto-pause after 3 min of no valid entry
 *   - Configurable daily API cap (default 300)
 *   - Command classification via /api/voice/classify
 *   - Price memory via /api/voice/transcribe
 *   - Quick mode: 3 s countdown auto-save; Strict mode: 8 s wait for yes
 *   - WhatsApp share of daily summary
 */

// ══════════════════════════════════════════════════════════
// VAD configuration (all tuneable)
// ══════════════════════════════════════════════════════════
const VAD_CONFIG = {
  silenceMs:        900,    // ms of silence = end of speech
  minSpeechMs:      600,    // ms minimum to send
  maxSpeechMs:      15000,  // ms maximum segment
  preRollMs:        300,    // ms pre-roll buffer
  energyThreshold:  0.015,  // RMS threshold (0–1); adaptive
  adaptationRate:   0.995,  // how fast noise floor decays
  sampleRate:       16000,
  channels:         1,
};

// Daily API cap
let DAILY_CAP = parseInt(localStorage.getItem('av_daily_cap') || '300', 10);
let API_CALLS_TODAY = parseInt(localStorage.getItem('av_api_date') === new Date().toDateString()
  ? localStorage.getItem('av_api_count') || '0'
  : '0', 10);

// ── Shop mode state ──────────────────────────────────────
let shopState = 'IDLE';
let shopMode  = localStorage.getItem('av_confirm_mode') || 'quick';
let highValueLimit = parseFloat(localStorage.getItem('av_high_value') || '10000');

let _audioCtx    = null;
let _analyser    = null;
let _sourceNode  = null;
let _stream      = null;
let _wakeLock    = null;
let _apiQueue    = Promise.resolve();  // serialises all API calls
let _countdownTimer = null;
let _silenceTimer   = null;
let _autoStopTimer  = null;   // 3-min auto-pause
let _pendingEntry   = null;   // last parsed entry awaiting confirmation
let _isListening    = false;  // VAD mic active
let _isTtsPlaying   = false;  // true while TTS audio plays + tail

// Pre-roll circular buffer (Float32 samples)
const PRE_ROLL_SAMPLES = Math.round(VAD_CONFIG.sampleRate * VAD_CONFIG.preRollMs / 1000);
let _preRollBuf  = new Float32Array(PRE_ROLL_SAMPLES);
let _preRollPos  = 0;
let _speechBuf   = [];        // Float32Array segments during active speech
let _inSpeech    = false;
let _speechStart = 0;
let _noiseFloor  = VAD_CONFIG.energyThreshold;

// ══════════════════════════════════════════════════════════
// EARCONS (Web Audio API — no sound files)
// ══════════════════════════════════════════════════════════

function _getAudioCtx() {
  if (!_audioCtx || _audioCtx.state === 'closed') {
    _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  return _audioCtx;
}

function playEarcon(type) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  try {
    const ctx  = _getAudioCtx();
    const gain = ctx.createGain();
    gain.connect(ctx.destination);
    const osc = ctx.createOscillator();
    osc.connect(gain);

    if (type === 'tick') {
      // Soft tick: short 880 Hz click
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.08);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.08);
    } else if (type === 'chime') {
      // Two-tone chime: 523 Hz then 659 Hz
      osc.type = 'sine';
      osc.frequency.setValueAtTime(523, ctx.currentTime);
      osc.frequency.setValueAtTime(659, ctx.currentTime + 0.12);
      gain.gain.setValueAtTime(0.1, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.4);
    } else if (type === 'buzz') {
      // Low buzz: 150 Hz sawtooth
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(150, ctx.currentTime);
      gain.gain.setValueAtTime(0.07, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.25);
    }
  } catch (e) {
    // Earcons are non-critical
  }
}

// ══════════════════════════════════════════════════════════
// WAV ENCODER (16 kHz, mono, 16-bit PCM)
// ══════════════════════════════════════════════════════════

function encodeWav(floatSamples, sampleRate) {
  const numSamples  = floatSamples.length;
  const numChannels = 1;
  const bitsPerSample = 16;
  const byteRate    = sampleRate * numChannels * bitsPerSample / 8;
  const blockAlign  = numChannels * bitsPerSample / 8;
  const dataSize    = numSamples * blockAlign;
  const buffer      = new ArrayBuffer(44 + dataSize);
  const view        = new DataView(buffer);

  function writeStr(offset, str) {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  }
  function writeUint32(offset, val) { view.setUint32(offset, val, true); }
  function writeUint16(offset, val) { view.setUint16(offset, val, true); }

  writeStr(0,  'RIFF');
  writeUint32(4,  36 + dataSize);
  writeStr(8,  'WAVE');
  writeStr(12, 'fmt ');
  writeUint32(16, 16);         // fmt chunk size
  writeUint16(20, 1);          // PCM
  writeUint16(22, numChannels);
  writeUint32(24, sampleRate);
  writeUint32(28, byteRate);
  writeUint16(32, blockAlign);
  writeUint16(34, bitsPerSample);
  writeStr(36, 'data');
  writeUint32(40, dataSize);

  // Convert Float32 [-1,1] to Int16
  const int16Offset = 44;
  for (let i = 0; i < numSamples; i++) {
    let s = Math.max(-1, Math.min(1, floatSamples[i]));
    view.setInt16(int16Offset + i * 2, s < 0 ? s * 32768 : s * 32767, true);
  }
  return new Blob([buffer], { type: 'audio/wav' });
}

// ══════════════════════════════════════════════════════════
// API QUEUE (serialises STT/TTS — one request at a time)
// ══════════════════════════════════════════════════════════

function queueApiCall(fn) {
  _apiQueue = _apiQueue.then(() => fn()).catch(() => {});
  return _apiQueue;
}

function _bumpApiCount() {
  API_CALLS_TODAY++;
  localStorage.setItem('av_api_count', String(API_CALLS_TODAY));
  localStorage.setItem('av_api_date',  new Date().toDateString());
  const el = document.getElementById('shopApiCount');
  if (el) el.textContent = API_CALLS_TODAY;
}

function _capReached() {
  return API_CALLS_TODAY >= DAILY_CAP;
}

// ══════════════════════════════════════════════════════════
// SCREEN WAKE LOCK
// ══════════════════════════════════════════════════════════

async function acquireWakeLock() {
  if (!('wakeLock' in navigator)) return;
  try {
    _wakeLock = await navigator.wakeLock.request('screen');
    _wakeLock.addEventListener('release', () => { _wakeLock = null; });
  } catch (e) {
    // non-fatal
  }
}

function releaseWakeLock() {
  if (_wakeLock) { _wakeLock.release().catch(() => {}); _wakeLock = null; }
}

// ══════════════════════════════════════════════════════════
// STATE MACHINE
// ══════════════════════════════════════════════════════════

function setState(s) {
  shopState = s;
  _renderShopState(s);
}

function _renderShopState(s) {
  const ring  = document.getElementById('shopStateRing');
  const label = document.getElementById('shopStateLabel');
  const hint  = document.getElementById('shopHint');
  const actions = document.getElementById('shopActions');
  const str   = window._shopStrings || {};

  if (!ring) return;

  // Remove old state classes
  ['state-idle','state-listening','state-transcribing','state-readback','state-saved','state-paused']
    .forEach(c => ring.classList.remove(c));

  const labelMap = {
    IDLE:         str.state_idle        || 'Tap to start',
    LISTENING:    str.state_listening   || 'Listening…',
    TRANSCRIBING: str.state_transcribing|| 'Understanding…',
    PARSED:       str.state_parsed      || 'Entry ready',
    READBACK:     str.state_readback    || 'Speaking…',
    AWAIT:        str.state_await       || 'Say yes or no',
    SAVED:        str.state_saved       || 'Saved!',
    PAUSED:       str.state_paused      || 'Paused — tap to resume',
  };

  if (label) label.textContent = labelMap[s] || s;

  if (hint) hint.textContent = '';
  if (actions) actions.style.display = 'none';

  if (s === 'LISTENING')    { ring.classList.add('state-listening'); playEarcon('tick'); }
  if (s === 'TRANSCRIBING') ring.classList.add('state-transcribing');
  if (s === 'READBACK')     ring.classList.add('state-readback');
  if (s === 'SAVED')        { ring.classList.add('state-saved'); playEarcon('chime'); }
  if (s === 'PAUSED')       ring.classList.add('state-paused');
  if (s === 'AWAIT' && actions)  actions.style.display = 'flex';
}

// ══════════════════════════════════════════════════════════
// VAD LOOP
// ══════════════════════════════════════════════════════════

function _rms(buf) {
  let sum = 0;
  for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
  return Math.sqrt(sum / buf.length);
}

function _startVadLoop() {
  if (!_analyser) return;
  const bufferSize = 2048;
  const buf = new Float32Array(bufferSize);
  let silenceStart = null;
  let speechSegStart = null;

  function loop() {
    if (!_isListening || _isTtsPlaying) {
      requestAnimationFrame(loop);
      return;
    }
    _analyser.getFloatTimeDomainData(buf);
    const energy = _rms(buf);

    // Adapt noise floor slowly downward
    _noiseFloor = _noiseFloor * VAD_CONFIG.adaptationRate + energy * (1 - VAD_CONFIG.adaptationRate);
    const threshold = Math.max(VAD_CONFIG.energyThreshold, _noiseFloor * 1.8);

    // Fill pre-roll ring buffer
    _preRollBuf.copyWithin(0, bufferSize < PRE_ROLL_SAMPLES ? PRE_ROLL_SAMPLES - bufferSize : 0);
    const writeStart = Math.max(0, PRE_ROLL_SAMPLES - bufferSize);
    _preRollBuf.set(buf.subarray(0, Math.min(bufferSize, PRE_ROLL_SAMPLES)), writeStart);

    if (energy > threshold) {
      if (!_inSpeech) {
        _inSpeech   = true;
        _speechStart = Date.now();
        silenceStart = null;
        speechSegStart = performance.now();
        // Include pre-roll
        _speechBuf = [new Float32Array(_preRollBuf)];
      }
      silenceStart = null;
      _speechBuf.push(new Float32Array(buf));

      // Max segment check
      if (Date.now() - _speechStart > VAD_CONFIG.maxSpeechMs) {
        _endSpeechSegment();
      }
    } else if (_inSpeech) {
      _speechBuf.push(new Float32Array(buf));
      if (silenceStart === null) silenceStart = Date.now();
      else if (Date.now() - silenceStart > VAD_CONFIG.silenceMs) {
        _endSpeechSegment();
      }
    }

    requestAnimationFrame(loop);
  }
  loop();
}

function _endSpeechSegment() {
  if (!_inSpeech) return;
  _inSpeech    = false;
  const duration = Date.now() - _speechStart;

  if (duration < VAD_CONFIG.minSpeechMs) {
    _speechBuf = [];
    return;
  }

  // Merge all Float32 chunks
  const totalLen = _speechBuf.reduce((s, c) => s + c.length, 0);
  const merged   = new Float32Array(totalLen);
  let offset = 0;
  for (const chunk of _speechBuf) { merged.set(chunk, offset); offset += chunk.length; }
  _speechBuf = [];

  // Resample to 16 kHz if audio context is running at different rate
  const wavBlob = encodeWav(merged, VAD_CONFIG.sampleRate);
  _onSpeechSegment(wavBlob);
}

// ══════════════════════════════════════════════════════════
// SPEECH SEGMENT HANDLER
// ══════════════════════════════════════════════════════════

async function _onSpeechSegment(wavBlob) {
  if (shopState !== 'LISTENING') return;
  if (_capReached()) {
    _showHint('Daily API limit reached. Shop mode paused.');
    _pauseShopMode();
    return;
  }

  setState('TRANSCRIBING');
  _resetAutoStop();

  queueApiCall(async () => {
    _bumpApiCount();

    const lang = window.state?.lang || 'hi';
    const mode = shopMode;
    const highValue = highValueLimit;

    const form = new FormData();
    form.append('audio_file', wavBlob, 'speech.wav');
    form.append('language', lang);
    form.append('mode', mode);
    form.append('high_value', highValue);

    let result;
    try {
      const res = await fetch('/api/voice/transcribe', { method: 'POST', body: form });
      if (res.status === 429) {
        await new Promise(r => setTimeout(r, 3000));
        const res2 = await fetch('/api/voice/transcribe', { method: 'POST', body: form });
        result = await res2.json();
      } else {
        result = await res.json();
      }
    } catch (e) {
      playEarcon('buzz');
      setState('LISTENING');
      return;
    }

    const transcript = result.transcript || '';
    const parsed     = result.parsed;

    // Show transcript
    const heardEl = document.getElementById('shopHeard');
    if (heardEl) heardEl.textContent = transcript;

    // Classify: is it a command or an entry?
    if (!parsed || parsed.needs_review || !parsed.item) {
      // Try command classification first
      await _handleAsCommand(transcript, lang);
      return;
    }

    // Show parsed entry
    _pendingEntry = result;
    _showParsedEntry(result);

    if (result.explicit_required) {
      await _doReadback(result, true);
    } else {
      await _doReadback(result, false);
    }
  });
}

async function _handleAsCommand(text, lang) {
  try {
    const res = await fetch('/api/voice/classify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, language: lang }),
    });
    const intent = await res.json();

    if (intent.intent === 'undo') {
      await _handleUndo(lang);
    } else if (intent.intent === 'pause') {
      _pauseShopMode();
    } else if (intent.intent === 'query') {
      await _handleQuery(intent.query_type, intent.item, lang);
    } else {
      // Unknown — ignore silently, go back to listening
      setState('LISTENING');
    }
  } catch (e) {
    setState('LISTENING');
  }
}

// ══════════════════════════════════════════════════════════
// CONFIRMATION FLOW
// ══════════════════════════════════════════════════════════

function _showParsedEntry(result) {
  const totalEl = document.getElementById('shopTotal');
  const memNote = document.getElementById('shopMemoryNote');

  if (totalEl && result.parsed?.total != null) {
    totalEl.textContent = '₹' + _fmtInr(result.parsed.total);
  }
  if (memNote) {
    memNote.style.display = result.filled_from_memory ? 'block' : 'none';
  }
}

async function _doReadback(result, explicitRequired) {
  setState('READBACK');

  // Pause mic during TTS
  _isTtsPlaying = true;

  const readbackText = result.short_readback || result.readback || '';
  const lang = window.state?.lang || 'hi';

  try {
    const ttsRes = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: readbackText, language: lang }),
    });
    _bumpApiCount();

    if (ttsRes.ok) {
      const audioBlob = await ttsRes.blob();
      const url = URL.createObjectURL(audioBlob);
      await _playAudioUrl(url);
      URL.revokeObjectURL(url);
    }
  } catch (e) {
    // TTS failed — continue anyway
  }

  // 400 ms tail after TTS finishes
  await new Promise(r => setTimeout(r, 400));
  _isTtsPlaying = false;

  // Now enter AWAIT state
  setState('AWAIT');
  _startConfirmationCountdown(result, explicitRequired);
}

function _startConfirmationCountdown(result, explicitRequired) {
  const timeoutSecs = result.timeout_secs || (explicitRequired ? 8 : 3);
  const hint = document.getElementById('shopHint');
  const str  = window._shopStrings || {};

  let remaining = timeoutSecs;

  if (!explicitRequired) {
    // Quick mode: show countdown
    _countdownTimer = setInterval(() => {
      remaining--;
      if (hint) hint.textContent = `${str.say_no_to_cancel || "Say 'no' to cancel"} (${remaining}s)`;
      if (remaining <= 0) {
        clearInterval(_countdownTimer);
        _countdownTimer = null;
        _saveEntry(result);
      }
    }, 1000);
    if (hint) hint.textContent = `${str.say_no_to_cancel || "Say 'no' to cancel"} (${remaining}s)`;
  } else {
    // Strict mode: wait for yes; timeout = not saved
    if (hint) hint.textContent = str.state_await || 'Say yes or no';
    _countdownTimer = setTimeout(() => {
      _countdownTimer = null;
      // No answer = not saved; show as pending, go back to listening
      _pendingEntry = null;
      const totalEl = document.getElementById('shopTotal');
      if (totalEl) totalEl.textContent = '';
      setState('LISTENING');
    }, timeoutSecs * 1000);
  }

  // Start listening for yes/no WHILE in AWAIT
  _listenForConfirmation(result);
}

function _listenForConfirmation(result) {
  // We rely on the main VAD loop — speech captured during AWAIT is rerouted
  // through _handleAwaitUtterance
  _awaitingConfirmation = result;
}

let _awaitingConfirmation = null;

// Called from VAD when in AWAIT state
async function _handleAwaitUtterance(text) {
  const lang = window.state?.lang || 'hi';
  try {
    const res = await fetch('/api/voice/classify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, language: lang }),
    });
    const intent = await res.json();

    if (intent.intent === 'yes') {
      _clearCountdown();
      _saveEntry(_awaitingConfirmation);
    } else if (intent.intent === 'no') {
      _clearCountdown();
      _cancelEntry();
    }
    // other intents ignored while in AWAIT
  } catch (e) {}
}

function _clearCountdown() {
  if (_countdownTimer !== null) {
    clearInterval(_countdownTimer);
    clearTimeout(_countdownTimer);
    _countdownTimer = null;
  }
  _awaitingConfirmation = null;
}

async function _saveEntry(result) {
  const lang = window.state?.lang || 'hi';
  const p = result.parsed;
  if (!p || !p.item) { setState('LISTENING'); return; }

  try {
    const saveRes = await fetch('/api/entries', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        item:        p.item,
        quantity:    p.quantity,
        unit:        p.unit,
        price:       p.price,
        entry_type:  p.entry_type || 'sale',
        language:    lang,
        transcript:  result.transcript || '',
      }),
    });
    if (saveRes.ok) {
      const saved = await saveRes.json();
      window._shopLastSavedId = saved.id;
      setState('SAVED');
      _pendingEntry = null;

      // Refresh dashboard in background
      if (typeof refreshDashboard === 'function') {
        setTimeout(refreshDashboard, 300);
      }

      // After 1.5 s, resume listening
      setTimeout(() => {
        const totalEl = document.getElementById('shopTotal');
        if (totalEl) totalEl.textContent = '';
        const heardEl = document.getElementById('shopHeard');
        if (heardEl) heardEl.textContent = '';
        setState('LISTENING');
      }, 1500);
    } else {
      playEarcon('buzz');
      setState('LISTENING');
    }
  } catch (e) {
    playEarcon('buzz');
    setState('LISTENING');
  }
}

function _cancelEntry() {
  _pendingEntry = null;
  _awaitingConfirmation = null;
  const totalEl = document.getElementById('shopTotal');
  if (totalEl) totalEl.textContent = '';
  const heardEl = document.getElementById('shopHeard');
  if (heardEl) heardEl.textContent = '';
  setState('LISTENING');
}

// ══════════════════════════════════════════════════════════
// COMMAND HANDLERS
// ══════════════════════════════════════════════════════════

async function _handleUndo(lang) {
  try {
    const id = window._shopLastSavedId;
    const str = window._shopStrings || {};
    if (!id) {
      await _speakAndReturn(str.nothing_to_undo || 'No entry to undo.', lang);
      return;
    }
    await fetch(`/api/entries/${id}`, { method: 'DELETE' });
    window._shopLastSavedId = null;
    const heardEl = document.getElementById('shopHeard');
    if (heardEl) heardEl.textContent = str.undo_confirmed || 'Last entry removed.';
    await _speakAndReturn(str.undo_confirmed || 'Last entry removed.', lang);
    if (typeof refreshDashboard === 'function') setTimeout(refreshDashboard, 300);
  } catch (e) {
    setState('LISTENING');
  }
}

async function _handleQuery(queryType, item, lang) {
  try {
    const res = await fetch('/api/voice/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query_type: queryType, language: lang, item: item || null }),
    });
    _bumpApiCount();
    const data = await res.json();
    const spoken = data.spoken || '';

    const heardEl = document.getElementById('shopHeard');
    if (heardEl) heardEl.textContent = spoken;

    // Show summary + WhatsApp button for daily_summary
    if (queryType === 'daily_summary' && data.data) {
      _showDailySummary(data.data, spoken, lang);
    }

    await _speakAndReturn(spoken, lang);
  } catch (e) {
    setState('LISTENING');
  }
}

function _showDailySummary(data, spoken, lang) {
  const sumRow  = document.getElementById('shopSummaryRow');
  const sumText = document.getElementById('shopSummaryText');
  const waBtn   = document.getElementById('shopWaBtn');

  if (!sumRow) return;
  sumRow.style.display = 'flex';

  if (sumText) sumText.textContent = spoken;

  if (waBtn) {
    const shopName = localStorage.getItem('av_shop') || 'ArthVani';
    const str  = window._shopStrings || {};
    const date = data.date || new Date().toISOString().slice(0, 10);
    const msg  = `*${shopName}* — ${date}\n`
      + `${str.today_sales || 'Sales'}: ₹${_fmtInr(data.sales || 0)}\n`
      + `${str.today_purchases || 'Purchases'}: ₹${_fmtInr(data.purchases || 0)}\n`
      + `${str.today_net || 'Net'}: ₹${_fmtInr(data.net || 0)}\n`
      + `${str.today_entries || 'Entries'}: ${data.count || 0}\n`
      + `_via ArthVani_`;
    waBtn.href = `https://wa.me/?text=${encodeURIComponent(msg)}`;
  }
}

async function _speakAndReturn(text, lang) {
  if (!text) { setState('LISTENING'); return; }
  _isTtsPlaying = true;
  try {
    const res = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, language: lang }),
    });
    _bumpApiCount();
    if (res.ok) {
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      await _playAudioUrl(url);
      URL.revokeObjectURL(url);
    }
  } catch (e) {}
  await new Promise(r => setTimeout(r, 400));
  _isTtsPlaying = false;
  setState('LISTENING');
}

function _playAudioUrl(url) {
  return new Promise(resolve => {
    const audio = new Audio(url);
    audio.onended  = resolve;
    audio.onerror  = resolve;
    audio.play().catch(resolve);
  });
}

// ══════════════════════════════════════════════════════════
// AUTO-PAUSE (3 min of no valid entry)
// ══════════════════════════════════════════════════════════

function _resetAutoStop() {
  if (_autoStopTimer) clearTimeout(_autoStopTimer);
  _autoStopTimer = setTimeout(() => {
    if (shopState === 'LISTENING') {
      _pauseShopMode(true);
    }
  }, 3 * 60 * 1000);
}

function _pauseShopMode(auto = false) {
  _isListening = false;
  setState('PAUSED');
  _clearCountdown();
  if (auto) {
    const str = window._shopStrings || {};
    const heardEl = document.getElementById('shopHeard');
    if (heardEl) heardEl.textContent = str.auto_paused || 'Paused after 3 min of silence';
  }
}

function _showHint(text) {
  const hint = document.getElementById('shopHint');
  if (hint) hint.textContent = text;
}

// ══════════════════════════════════════════════════════════
// START / STOP SHOP MODE
// ══════════════════════════════════════════════════════════

async function startShopMode() {
  // Browsers require a user gesture for mic permission
  try {
    _stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate:   VAD_CONFIG.sampleRate,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });
  } catch (e) {
    const str = window._shopStrings || {};
    alert(str.error_mic_denied || 'Microphone access denied.');
    return;
  }

  // Build audio graph
  const ctx = new (window.AudioContext || window.webkitAudioContext)({
    sampleRate: VAD_CONFIG.sampleRate,
  });
  _audioCtx  = ctx;
  _analyser  = ctx.createAnalyser();
  _analyser.fftSize = 2048;
  _sourceNode = ctx.createMediaStreamSource(_stream);
  _sourceNode.connect(_analyser);

  _isListening  = true;
  _isTtsPlaying = false;
  _speechBuf    = [];
  _inSpeech     = false;
  _noiseFloor   = VAD_CONFIG.energyThreshold;

  // Show panel
  document.body.classList.add('shop-mode-active');
  document.body.style.overscrollBehaviorY = 'none';
  document.getElementById('shopModeEntry').style.display = 'none';
  document.getElementById('shopModePanel').style.display = 'flex';

  // Load strings reference
  window._shopStrings = window.state?.strings || {};

  setState('LISTENING');
  _startVadLoop();
  _resetAutoStop();
  await acquireWakeLock();

  // Reset summary row
  const sumRow = document.getElementById('shopSummaryRow');
  if (sumRow) sumRow.style.display = 'none';

  // Update API counter display
  const countEl = document.getElementById('shopApiCount');
  if (countEl) countEl.textContent = API_CALLS_TODAY;
}

async function stopShopMode() {
  _isListening  = false;
  _isTtsPlaying = false;
  _clearCountdown();
  if (_autoStopTimer) { clearTimeout(_autoStopTimer); _autoStopTimer = null; }

  if (_stream) {
    _stream.getTracks().forEach(t => t.stop());
    _stream = null;
  }
  if (_sourceNode) { _sourceNode.disconnect(); _sourceNode = null; }
  if (_audioCtx && _audioCtx.state !== 'closed') {
    await _audioCtx.close().catch(() => {});
    _audioCtx = null;
  }
  _analyser = null;

  releaseWakeLock();

  document.body.classList.remove('shop-mode-active');
  document.body.style.overscrollBehaviorY = '';
  document.getElementById('shopModeEntry').style.display = 'flex';
  document.getElementById('shopModePanel').style.display = 'none';

  shopState = 'IDLE';
}

// ══════════════════════════════════════════════════════════
// FORMATTING HELPER
// ══════════════════════════════════════════════════════════

function _fmtInr(amount) {
  if (amount == null) return '—';
  const n = Math.round(amount);
  const s = String(n);
  if (s.length <= 3) return s;
  const last3 = s.slice(-3);
  const rest   = s.slice(0, -3);
  return rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' + last3;
}

// ══════════════════════════════════════════════════════════
// WIRE UP DOM EVENTS
// ══════════════════════════════════════════════════════════

function wireShopMode() {
  const startBtn = document.getElementById('shopStartBtn');
  const stopBtn  = document.getElementById('shopStopBtn');
  const yesBtn   = document.getElementById('shopYesBtn');
  const noBtn    = document.getElementById('shopNoBtn');

  if (startBtn) startBtn.addEventListener('click', startShopMode);
  if (stopBtn)  stopBtn.addEventListener('click', stopShopMode);

  if (yesBtn) yesBtn.addEventListener('click', () => {
    _clearCountdown();
    if (_awaitingConfirmation) _saveEntry(_awaitingConfirmation);
    else if (_pendingEntry) _saveEntry(_pendingEntry);
  });

  if (noBtn) noBtn.addEventListener('click', () => {
    _clearCountdown();
    _cancelEntry();
  });

  // Paused state: tap ring to resume
  const ring = document.getElementById('shopStateRing');
  if (ring) ring.addEventListener('click', () => {
    if (shopState === 'PAUSED') {
      _isListening = true;
      setState('LISTENING');
      _resetAutoStop();
    }
  });

  // Settings: confirmation mode
  const modeQuick  = document.getElementById('modeQuick');
  const modeStrict = document.getElementById('modeStrict');
  const modeDesc   = document.getElementById('modeDesc');

  function _applyMode(mode) {
    shopMode = mode;
    localStorage.setItem('av_confirm_mode', mode);
    [modeQuick, modeStrict].forEach(b => b && b.classList.remove('active'));
    const active = mode === 'quick' ? modeQuick : modeStrict;
    if (active) active.classList.add('active');
    if (modeDesc) {
      const str = window.state?.strings || {};
      modeDesc.textContent = mode === 'quick'
        ? (str.confirm_mode_desc_quick || 'Auto-saves after 3 seconds unless you say no.')
        : (str.confirm_mode_desc_strict || 'Waits for your yes — no answer means not saved.');
    }
  }

  _applyMode(shopMode);
  if (modeQuick)  modeQuick.addEventListener('click',  () => _applyMode('quick'));
  if (modeStrict) modeStrict.addEventListener('click', () => _applyMode('strict'));

  const saveVoiceBtn = document.getElementById('saveVoiceSettings');
  if (saveVoiceBtn) saveVoiceBtn.addEventListener('click', () => {
    const capEl = document.getElementById('dailyCapInput');
    const hvEl  = document.getElementById('highValueInput');
    if (capEl) {
      DAILY_CAP = parseInt(capEl.value, 10) || 300;
      localStorage.setItem('av_daily_cap', String(DAILY_CAP));
    }
    if (hvEl) {
      highValueLimit = parseFloat(hvEl.value) || 10000;
      localStorage.setItem('av_high_value', String(highValueLimit));
    }
  });

  // Load saved values into settings inputs
  const capEl = document.getElementById('dailyCapInput');
  const hvEl  = document.getElementById('highValueInput');
  if (capEl) capEl.value = DAILY_CAP;
  if (hvEl)  hvEl.value  = highValueLimit;

  // Update the string reference when language changes
  document.addEventListener('av:langchanged', () => {
    window._shopStrings = window.state?.strings || {};
  });

  // Handle page visibility changes (pause listening if user leaves app / locks screen)
  let _wasListeningOnHide = false;
  document.addEventListener('visibilitychange', () => {
    if (shopState === 'IDLE') return;
    if (document.hidden) {
      if (_isListening) {
        _wasListeningOnHide = true;
        _isListening = false;
        const lbl = document.getElementById('shopStateLabel');
        if (lbl) {
          const isHi = (window.state?.lang === 'hi');
          lbl.textContent = isHi ? 'रुक गया – चालू करने के लिए टैप करें' : 'Paused – tap to resume';
        }
        const ring = document.getElementById('shopStateRing');
        if (ring) {
          ring.style.cursor = 'pointer';
          ring.onclick = () => {
            ring.style.cursor = '';
            ring.onclick = null;
            if (_audioCtx && _audioCtx.state === 'suspended') {
              _audioCtx.resume();
            }
            _isListening = true;
            setState('LISTENING');
            _startVadLoop();
          };
        }
      }
    } else {
      if (_wasListeningOnHide) {
        _wasListeningOnHide = false;
        const lbl = document.getElementById('shopStateLabel');
        if (lbl) {
          const isHi = (window.state?.lang === 'hi');
          lbl.textContent = isHi ? 'रुक गया – चालू करने के लिए टैप करें' : 'Paused – tap to resume';
        }
        const ring = document.getElementById('shopStateRing');
        if (ring) {
          ring.style.cursor = 'pointer';
          ring.onclick = () => {
            ring.style.cursor = '';
            ring.onclick = null;
            if (_audioCtx && _audioCtx.state === 'suspended') {
              _audioCtx.resume();
            }
            _isListening = true;
            setState('LISTENING');
            _startVadLoop();
          };
        }
      }
    }
  });

  // Keep active transcript and status visible above on-screen keyboard
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', () => {
      const panel = document.getElementById('shopModePanel');
      if (!panel || panel.style.display === 'none') return;
      const vh = window.visualViewport.height;
      panel.style.maxHeight = `${vh}px`;
    });
  }
}

// Export wireShopMode for app.js to call
window.wireShopMode = wireShopMode;
window.startShopMode = startShopMode;
window.stopShopMode  = stopShopMode;

