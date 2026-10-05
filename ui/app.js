/* Lopic frontend. talks to python through the pywebview js_api bridge. */

const state = {
  gens: [],
  models: [],
  sys: null,
  selected: null,
  selectedModel: null,
  filter: 'all',
  modelFilter: 'all',
  jobs: {},
  modelJobs: {},
  logLines: [],
  connected: false,
};

const $ = (id) => document.getElementById(id);

/* ---------------- api bridge ---------------- */

/* Always return a promise. The bridge is injected a moment after page load, so a
   naive retry that returns undefined would blow up on the caller's .then(). */
function callApi(name, ...args) {
  return new Promise((resolve, reject) => {
    const attempt = (triesLeft) => {
      const api = window.pywebview && window.pywebview.api;
      if (api && typeof api[name] === 'function') {
        try {
          Promise.resolve(api[name](...args)).then(resolve, reject);
        } catch (err) {
          reject(err);
        }
        return;
      }
      if (triesLeft <= 0) {
        reject(new Error('pywebview-Bridge nicht erreichbar: ' + name));
        return;
      }
      setTimeout(() => attempt(triesLeft - 1), 120);
    };
    attempt(60);
  });
}

/* python pushes events into here */
window.onPy = {
  state: (payload) => {
    state.sys = payload.sys;
    state.jobs = payload.jobs || {};
    state.gens = payload.gens || [];
    state.models = payload.models || state.models;
    state.modelJobs = payload.modelJobs || state.modelJobs;
    renderSys();
    renderGrid();
    renderModels();
    if (state.selected) renderDetail(state.selected);
    else if (state.selectedModel) renderModelDetail(state.selectedModel);
  },
  log: (line) => appendLog(line),
  modelState: (payload) => {
    state.modelJobs[payload.id] = payload;
    const m = state.models.find((x) => x.id === payload.id);
    if (m && payload.status === 'done') m.installed = true;
    renderModels();
    if (state.selectedModel === payload.id) renderModelDetail(payload.id);
  },
  genState: (payload) => {
    const g = state.gens.find((x) => x.id === payload.id);
    if (g) {
      g.installed = payload.installed;
      g.status = payload.status;
    }
    state.jobs[payload.id] = payload;
    renderGrid();
    if (state.selected === payload.id) renderDetail(payload.id);
  },
};

/* ---------------- system bar ---------------- */

function renderSys() {
  if (!state.sys) return;
  const g = state.sys.gpu;
  $('sys-gpu').textContent = g.name.replace(/NVIDIA\s+/i, '').trim();
  $('sys-vram').textContent = g.vram_gb ? `${g.vram_gb} GB` : 'unbekannt';
  $('sys-disk').textContent = `${state.sys.disk_free_gb} GB`;
  $('sysbar').title =
    `GPU: ${g.name}\nVRAM: ${g.vram_mb} MB\nTreiber: ${g.driver}\n` +
    `Git: ${state.sys.tools.git}\nuv: ${state.sys.tools.uv}\nPython: ${state.sys.tools.python}\n` +
    `Installationsordner: ${state.sys.install_root}`;
}

/* ---------------- vram fit logic ---------------- */

/* nvidia-smi reports 8188 MB for a card marketed as 8 GB, so the raw division
   yields 7.996 and an exact-fit model would be marked red. round once, here. */
function haveVramGb() {
  return state.sys ? Math.round(state.sys.gpu.vram_mb / 1024) : 0;
}

/* shared by generators and models: fits / tight (exact) / too big.
   `need` is the requirement in whole GB, 0 meaning "no requirement". */
function vramClass(need) {
  const have = haveVramGb();
  if (!have) return 'no';
  if (!need) return 'fits';
  if (need > have) return 'no';
  if (need === have) return 'tight';
  return 'fits';
}

function vramVerdict(gen) {
  const cls = vramClass(gen.vram_min_gb);
  const txt = `${gen.vram_min_gb} GB`;
  return { cls, txt: cls === 'no' ? `${gen.vram_min_gb} GB nötig` : txt };
}

/* ---------------- catalog grid ---------------- */

function applyFilter() {
  const f = state.filter;
  let list = state.gens;
  if (f === 'fits') list = list.filter((g) => vramVerdict(g).cls !== 'no');
  else if (f === 'installed') list = list.filter((g) => g.installed);
  else if (f === 'easy') list = list.filter((g) => g.easy);
  $('cat-count').textContent = `${list.length} von ${state.gens.length}`;
  return list;
}

function renderGrid() {
  const grid = $('grid');
  const list = applyFilter();
  if (!list.length) {
    grid.innerHTML = `<div class="empty-detail" style="grid-column:1/-1;height:180px">
      <p>Keine Generatoren für diesen Filter.</p></div>`;
    return;
  }
  grid.innerHTML = list.map(cardHtml).join('');
  grid.querySelectorAll('.card').forEach((el) => {
    el.onclick = () => select(el.dataset.id);
  });
}

function cardHtml(g) {
  const v = vramVerdict(g);
  const job = state.jobs[g.id];
  const busy = job && job.status === 'running';
  let stateHtml = '';
  if (busy) {
    const pct = Math.round((job.progress || 0) * 100);
    stateHtml = `<div class="card-state busy"><span class="dot pulse"></span>Installiert ${pct}%</div>
                 <div class="card-prog"><i style="width:${pct}%"></i></div>`;
  } else if (g.installed) {
    stateHtml = `<div class="card-state installed"><span class="dot"></span>Installiert</div>`;
  }
  return `
  <article class="card ${state.selected === g.id ? 'selected' : ''}"
           data-id="${g.id}" style="--c1:${g.color}">
    <div class="card-top">
      <div style="flex:1 1 auto;min-width:0">
        <h3>${g.name}</h3>
        <p class="tagline">${g.tagline}</p>
      </div>
      <div class="badge-stack">
        <span class="badge ${v.cls}">${v.txt}</span>
        ${g.easy ? '<span class="badge easy">einsteiger</span>' : ''}
      </div>
    </div>
    <div class="card-meta">
      <span class="meta">${g.size_gb} GB</span>
      <span class="meta">${g.license}</span>
    </div>
    ${stateHtml}
  </article>`;
}

/* ---------------- detail panel ---------------- */

function select(id) {
  state.selected = id;
  renderGrid();
  renderDetail(id);
  callApi('on_select', id);
}

function idleHtml() {
  const s = state.sys;
  const gpu = s ? s.gpu : null;
  return `
  <div class="empty-detail">
    <div class="idle-head">
      <div class="idle-icon" aria-hidden="true"></div>
      <div>
        <h3>Waehle einen Generator</h3>
        <p>Klick links auf eine Karte &ndash; du siehst Beschreibung, Anforderungen und die Installationsschritte.</p>
      </div>
    </div>

    ${gpu ? `<div class="idle-sec">
      <h4>Dein System</h4>
      <div class="specs">
        <div class="spec"><span class="k">GPU</span><span class="v">${gpu.name}</span></div>
        <div class="spec"><span class="k">VRAM</span><span class="v">${gpu.vram_gb} GB</span></div>
        <div class="spec"><span class="k">Speicher frei</span><span class="v">${s.disk_free_gb} GB</span></div>
        <div class="spec"><span class="k">Git</span><span class="v">${s.tools.git.replace('git version ', '')}</span></div>
        <div class="spec"><span class="k">Installationsordner</span><span class="v">${s.install_root}</span></div>
      </div>
    </div>` : ''}

    <div class="idle-sec">
      <h4>So funktioniert's</h4>
      <ol class="idle-steps">
        <li><b>Generator waehlen</b> &ndash; jede Karte erklaert, was das Programm kann.</li>
        <li><b>Installieren</b> &ndash; Lopic holt den Quellcode, legt ein eigenes Python-Environment an
            und installiert CUDA-Torch passend fuer deine Grafikkarte.</li>
        <li><b>Starten</b> &ndash; der Generator laeuft fensterlos im Hintergrund und ist im Browser erreichbar.</li>
      </ol>
    </div>

    <div class="idle-hint">
      Jeder Generator bekommt sein eigenes <code>venv</code>, damit sich Forge, ComfyUI &amp; Co.
      nicht gegenseitig in die Quere kommen. Alles bleibt lokal &ndash; keine Daten verlassen deinen PC.
    </div>
  </div>`;
}

function renderDetail(id) {
  const g = state.gens.find((x) => x.id === id);
  const inner = $('detail-inner');
  if (!g) {
    inner.innerHTML = idleHtml();
    return;
  }
  const v = vramVerdict(g);
  const job = state.jobs[id];
  const busy = job && job.status === 'running';
  const vramWarn =
    v.cls === 'no'
      ? `<div class="note">Achtung: ${g.name} verlangt mindestens ${g.vram_min_gb} GB VRAM.
         Deine GPU hat ${state.sys ? state.sys.gpu.vram_gb : '?'} GB &ndash; er laeuft, aber sehr langsam oder gar nicht.</div>`
      : '';

  inner.className = 'detail-inner' + (busy ? ' installing' : '');
  inner.innerHTML = `
    <div style="--c1:${g.color}">
      <div class="d-head">
        <div style="flex:1 1 auto;min-width:0">
          <h3>${g.name}</h3>
          <p class="sub">${g.license} &middot; ${g.size_gb} GB &middot; benoetigt ${g.vram_min_gb} GB VRAM</p>
        </div>
        <span class="badge ${v.cls}">${v.txt}</span>
      </div>

      <p class="d-body">${g.description}</p>
      ${vramWarn}

      <div class="d-sec">
        <h4>Das kann es</h4>
        <ul class="feat">${g.features.map((f) => `<li>${f}</li>`).join('')}</ul>
      </div>

      <div class="d-sec">
        <h4>Technik</h4>
        <div class="specs">
          <div class="spec"><span class="k">Python</span><span class="v">${g.python}</span></div>
          <div class="spec"><span class="k">Start</span><span class="v">${g.entry || g.package_install + ' (Paket)'}</span></div>
          <div class="spec"><span class="k">Quelle</span><span class="v">${g.repo.split('/').pop().replace('.git', '')}</span></div>
          <div class="spec"><span class="k">Ordner</span><span class="v">${g.folder}</span></div>
        </div>
        ${g.py_note ? `<p class="py-note">${g.py_note}</p>` : ''}
      </div>

      <div class="d-sec">
        <h4>Installation</h4>
        <ol class="steps">
          ${g.steps.map((s) => `<li>${s}</li>`).join('')}
        </ol>
      </div>

      ${busy ? `<div class="d-sec"><h4>Live-Log</h4><div class="log" id="logbox"></div></div>` : ''}

      <div class="actions">
        ${g.installed
          ? `<button class="btn primary" onclick="callApi('launch', '${g.id}')">Starten</button>
             <button class="btn" onclick="callApi('stop', '${g.id}')">Stoppen</button>
             <button class="btn" onclick="callApi('open_folder', '${g.id}')" title="Ordner im Explorer öffnen">Ordner</button>
             <button class="btn danger" onclick="callApi('uninstall', '${g.id}')">Entfernen</button>`
          : busy
            ? `<button class="btn primary" disabled>Installation laeuft &hellip; ${Math.round((job.progress||0)*100)}%</button>`
            : `<button class="btn primary" onclick="callApi('install', '${g.id}')">Installieren</button>`}
      </div>
    </div>`;

  const box = $('logbox');
  if (box) {
    if (state.logLines.length) {
      box.innerHTML = state.logLines.slice(-120).map(logHtml).join('');
    }
    box.scrollTop = box.scrollHeight;
  }
}

function logHtml(line) {
  const cls = line.startsWith('OK') ? 'ok'
    : line.startsWith('FEHLER') ? 'err'
    : line.startsWith('>>>') ? 'hi' : '';
  const t = new Date().toLocaleTimeString('de-DE', { hour12: false });
  return `<div><span class="t">${t}</span> <span class="${cls}">${escapeHtml(line)}</span></div>`;
}

function appendLog(line) {
  state.logLines.push(line);
  if (state.logLines.length > 400) state.logLines = state.logLines.slice(-300);
  const box = $('logbox');
  if (box) {
    box.insertAdjacentHTML('beforeend', logHtml(line));
    while (box.children.length > 160) box.removeChild(box.firstChild);
    box.scrollTop = box.scrollHeight;
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

/* ---------------- model tab ---------------- */

function fmtBytes(n) {
  if (!n) return '–';
  const gb = n / 1073741824;
  return gb >= 1 ? gb.toFixed(2) + ' GB' : (n / 1048576).toFixed(0) + ' MB';
}

function modelVerdict(m) {
  if (m.gated) return { cls: 'tight', txt: 'Konto nötig' };
  if (!m.vram_gb) {
    return { cls: 'fits', txt: m.family === 'Zubehör' ? 'Zubehör' : 'egal' };
  }
  const cls = vramClass(m.vram_gb);
  const labels = {
    no: m.vram_gb + ' GB nötig',
    tight: m.vram_gb + ' GB exakt',
    fits: m.vram_gb + ' GB',
  };
  return { cls, txt: labels[cls] };
}

function modelTotal(m) {
  return (m.files || []).reduce((a, f) => a + f.size, 0);
}

function renderModels() {
  const grid = $('grid-models');
  const list = state.models || [];
  const f = state.modelFilter || 'all';
  let shown = list;
  if (f === 'fits') shown = list.filter((m) => modelVerdict(m).cls !== 'no');
  else if (f === 'installed') shown = list.filter((m) => m.installed);
  else if (f === 'easy') shown = list.filter((m) => m.vram_gb <= 4);
  $('cat-count').textContent = `${shown.length} von ${list.length}`;
  if (!shown.length) {
    grid.innerHTML = `<div class="empty-detail" style="grid-column:1/-1;height:180px">
      <p>Keine Modelle für diesen Filter.</p></div>`;
    return;
  }
  grid.innerHTML = shown.map(modelCardHtml).join('');
  grid.querySelectorAll('.card').forEach((el) => {
    el.onclick = () => selectModel(el.dataset.id);
  });
}

function modelCardHtml(m) {
  const v = modelVerdict(m);
  const job = state.modelJobs[m.id];
  const busy = job && job.status === 'running';
  let st = '';
  if (busy) {
    const pct = Math.round(job.progress * 100);
    st = `<div class="card-state busy"><span class="dot pulse"></span>Laedt ${pct}%</div>
          <div class="card-prog"><i style="width:${pct}%"></i></div>`;
  } else if (m.installed) {
    st = `<div class="card-state installed"><span class="dot"></span>Vorhanden</div>`;
  }
  return `
  <article class="card ${state.selectedModel === m.id ? 'selected' : ''}"
           data-id="${m.id}" style="--c1:${m.color}">
    <div class="card-top">
      <div style="flex:1 1 auto;min-width:0">
        <h3>${m.name}</h3>
        <p class="tagline">${m.tagline}</p>
      </div>
      <div class="badge-stack"><span class="badge ${v.cls}">${v.txt}</span></div>
    </div>
    <div class="card-meta">
      <span class="meta">${m.files.length ? fmtBytes(modelTotal(m)) : 'nur manuell'}</span>
      <span class="meta">${m.family}</span>
      <span class="meta">${m.files.length} Datei${m.files.length === 1 ? '' : 'en'}</span>
    </div>
    ${st}
  </article>`;
}

function selectModel(id) {
  state.selectedModel = id;
  renderModels();
  renderModelDetail(id);
  callApi('on_select_model', id);
}

function renderModelDetail(id) {
  const m = (state.models || []).find((x) => x.id === id);
  const inner = $('detail-inner');
  if (!m) { inner.innerHTML = idleHtml(); return; }
  const v = modelVerdict(m);
  const job = state.modelJobs[m.id];
  const busy = job && job.status === 'running';
  let vramWarn = '';
  if (v.cls === 'no') {
    vramWarn = `<div class="note">Braucht etwa ${m.vram_gb} GB VRAM, du hast `
      + `${state.sys ? state.sys.gpu.vram_gb : '?'} GB. Laeuft hoechstens sehr langsam.`;
  } else if (v.cls === 'tight' && m.vram_gb) {
    vramWarn = `<div class="note">Passt genau auf deine `
      + `${state.sys ? state.sys.gpu.vram_gb : '?'} GB.`
      + ` Am besten mit Low-VRAM-Modus.</div>`;
  }

  inner.className = 'detail-inner' + (busy ? ' installing' : '');
  inner.innerHTML = `
    <div style="--c1:${m.color}">
      <div class="d-head">
        <div style="flex:1 1 auto;min-width:0">
          <h3>${m.name}</h3>
          <p class="sub">${m.family} &middot; ${m.files.length ? fmtBytes(modelTotal(m)) : 'manuell laden'} &middot; ${m.kind}</p>
        </div>
        <span class="badge ${v.cls}">${v.txt}</span>
      </div>

      <p class="d-body">${m.note}</p>
      ${vramWarn}
      ${m.gated ? `<div class="note">Dieses Modell liegt hinter einer Anmeldung bei
        <a href="${m.home}" target="_blank">${m.home.split('/').slice(-2).join('/')}</a>
        (Name, Land, Verwendungszweck). Lopic laedt es nicht automatisch.</div>` : ''}

      <div class="d-sec">
        <h4>Lizenz</h4>
        <div class="specs">
          <div class="spec"><span class="k">Kurz</span><span class="v">${m.license}</span></div>
          <div class="spec"><span class="k">Bedeutung</span><span class="v">${m.license_text || ''}</span></div>
          <div class="spec"><span class="k">Quelle</span><span class="v">${(m.files[0] || {}).repo || '–'}</span></div>
        </div>
      </div>

      <div class="d-sec">
        <h4>Dateien</h4>
        <div class="specs">
          ${(m.files || []).map((f) => `<div class="spec">
            <span class="k" style="max-width:64%;word-break:break-all">${f.name}</span>
            <span class="v">${fmtBytes(f.size)}</span></div>`).join('')}
        </div>
      </div>

      ${busy ? `<div class="d-sec"><h4>Live-Log</h4><div class="log" id="logbox"></div></div>` : ''}

      <div class="actions">
        ${m.gated
          ? `<button class="btn" onclick="window.open('${m.home}', '_blank')">Seite oeffnen</button>`
          : m.installed
            ? `<button class="btn primary" onclick="callApi('download_model', '${m.id}')">Erneut laden</button>`
            : busy
              ? `<button class="btn primary" disabled>Laedt &hellip; ${Math.round(job.progress * 100)}%</button>`
              : `<button class="btn primary" onclick="callApi('download_model', '${m.id}')">Modell laden</button>`}
        <button class="btn" onclick="callApi('model_folder')">Zielordner</button>
      </div>
    </div>`;
  const box = $('logbox');
  if (box) box.scrollTop = box.scrollHeight;
}

/* ---------------- tabs ---------------- */

$('tabs').addEventListener('click', (e) => {
  const btn = e.target.closest('.tab');
  if (!btn) return;
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t === btn));
  const models = btn.dataset.tab === 'models';
  $('grid').classList.toggle('hidden', models);
  $('grid-models').classList.toggle('hidden', !models);
  state.modelFilter = 'all';
  $('filters').querySelectorAll('.chip').forEach((c) => {
    const label = { all: 'Alle', fits: 'Passt auf meine GPU', installed: 'Vorhanden', easy: 'Schnell' }[c.dataset.filter];
    c.textContent = label;
    c.classList.toggle('active', c.dataset.filter === 'all');
  });
  if (models) renderModels(); else renderGrid();
});

/* ---------------- filters ---------------- */

$('filters').addEventListener('click', (e) => {
  const btn = e.target.closest('.chip');
  if (!btn) return;
  document.querySelectorAll('.chip').forEach((c) => c.classList.toggle('active', c === btn));
  // the chips are shared by both tabs, so write to whichever filter is active
  // and re-render only that grid. previously this always wrote state.filter
  // and called renderGrid, so the model tab never filtered anything.
  if ($('grid-models').classList.contains('hidden')) {
    state.filter = btn.dataset.filter;
    renderGrid();
  } else {
    state.modelFilter = btn.dataset.filter;
    renderModels();
  }
});

/* ---------------- boot ---------------- */

function boot() {
  return callApi('bootstrap').then((payload) => {
    if (!payload) return;
    state.sys = payload.sys;
    state.gens = payload.gens;
    state.jobs = payload.jobs || {};
    state.models = payload.models || [];
    state.modelJobs = payload.modelJobs || {};
    renderSys();
    renderGrid();
    renderModels();
    renderDetail(state.selected);  // paint the idle panel on first boot
  });
}

/* python kicks us: pywebview 6 injects api.js on before_load, so the DOM
   pywebviewready event fires before inline scripts exist. never rely on it. */
window.lopicBoot = boot;