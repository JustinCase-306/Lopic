/* Lopic frontend. talks to python through the pywebview js_api bridge. */

const state = {
  gens: [],
  sys: null,
  selected: null,
  filter: 'all',
  jobs: {},
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
    renderSys();
    renderGrid();
    if (state.selected) renderDetail(state.selected);
  },
  log: (line) => appendLog(line),
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

function vramVerdict(gen) {
  const have = state.sys ? state.sys.gpu.vram_mb / 1024 : 0;
  if (!have) return { cls: 'no', txt: 'VRAM?' };
  if (gen.vram_min_gb > have) return { cls: 'no', txt: `${gen.vram_min_gb} GB nötig` };
  if (gen.vram_min_gb > have * 0.7) return { cls: 'tight', txt: `${gen.vram_min_gb} GB` };
  return { cls: 'fits', txt: `${gen.vram_min_gb} GB` };
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

/* ---------------- filters ---------------- */

$('filters').addEventListener('click', (e) => {
  const btn = e.target.closest('.chip');
  if (!btn) return;
  state.filter = btn.dataset.filter;
  document.querySelectorAll('.chip').forEach((c) => c.classList.toggle('active', c === btn));
  renderGrid();
});

/* ---------------- boot ---------------- */

function boot() {
  return callApi('bootstrap').then((payload) => {
    if (!payload) return;
    state.sys = payload.sys;
    state.gens = payload.gens;
    state.jobs = payload.jobs || {};
    renderSys();
    renderGrid();
    renderDetail(state.selected);  // paint the idle panel on first boot
  });
}

/* python kicks us: pywebview 6 injects api.js on before_load, so the DOM
   pywebviewready event fires before inline scripts exist. never rely on it. */
window.lopicBoot = boot;