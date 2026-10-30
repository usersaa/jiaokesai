/* ============================================================
 * app.js —— 校园共享电单车 P 点标定地图（精简版）
 *
 * 仅保留最基础功能：
 *   1. 校园底图（2D / 3D、标准 / 卫星）
 *   2. P 点标定：地图点击采集坐标，可改名 / 改容量 / 删除
 *   3. 导出 / 导入 JSON（数据存 localStorage，刷新不丢）
 *
 * 数据全部存 localStorage。
 * ============================================================ */

const LS_KEY = 'lzjtu_stations_v1';

let map = null;
let infoWindow = null;
let satelliteLayer = null;
let satelliteOn = false;    // 是否处于卫星底图
let initCenter = null;      // 初始视野
let initZoom = null;

let stations = [];          // 点位数组
let markers = new Map();    // id -> AMap.Marker
let selectedId = null;
let editMode = false;
let viewMode = '2D';
let suppressMapClick = false;

const $ = (id) => document.getElementById(id);

/* ============================ 启动 ============================ */

boot();

async function boot() {
  setStatus('正在加载高德地图…');
  try {
    const AMap = await AMapLoader.load({
      key: window.AMAP_CONFIG.key,
      version: window.AMAP_CONFIG.version,
      plugins: ['AMap.ToolBar', 'AMap.Scale']   // 仅基础控件
    });
    window.AMap = AMap;
    initMap(AMap);
    loadFromStorage();
    renderAll();
    bindUI();
    setStatus('就绪。点击「标定模式」开始采集 P 点。');
  } catch (e) {
    console.error(e);
    setStatus('地图加载失败：' + (e && e.message ? e.message : e));
  }
}

function initMap(AMap) {
  // 支持 ?lng= / &lat= / &zoom= 快速定位（便于调试与分享视角）
  const q = new URLSearchParams(location.search);
  initCenter = [
    parseFloat(q.get('lng')) || window.CAMPUS.center[0],
    parseFloat(q.get('lat')) || window.CAMPUS.center[1]
  ];
  initZoom = parseFloat(q.get('zoom')) || window.CAMPUS.zoom;

  infoWindow = new AMap.InfoWindow({ offset: new AMap.Pixel(0, -14), isCustom: false });

  $('campus-title').textContent = window.CAMPUS.name + ' · P 点标定';

  // 起始为 2D
  buildMap('2D');
  updateViewButtons('2D');
}

/* 用指定的 viewMode 创建地图实例。
 * 说明：高德 JS API 2.0 的 viewMode 是「初始化参数」，3D 必须在创建时指定才会
 * 加载 WebGL 引擎；运行时靠 setStatus 切换在部分环境下不可靠（实测切回 2D 不压平）。
 * 因此这里采用「销毁重建」：2D 用真正的 2D 引擎、3D 用真正的 3D 引擎，行为确定。 */
function buildMap(mode) {
  const AMap = window.AMap;

  // 记录当前视野，重建后保持
  let center = initCenter ? initCenter.slice() : window.CAMPUS.center.slice();
  let zoom = initZoom || window.CAMPUS.zoom;
  if (map) {
    try {
      const c = map.getCenter();
      if (c) { center = [c.getLng(), c.getLat()]; }
      const z = map.getZoom();
      if (z) zoom = z;
    } catch (e) { /* ignore */ }
    map.destroy();
    map = null;
  }

  const pitch = mode === '3D' ? window.CAMPUS.pitch : 0;

  map = new AMap.Map('container', {
    viewMode: mode,          // '2D' | '3D'（3D 才会加载 WebGL）
    pitch: pitch,            // 3D 初始俯仰角；2D 为 0
    rotation: 0,
    zoom: zoom,
    center: center,
    resizeEnable: true,
    mapStyle: 'amap://styles/normal'
  });

  map.addControl(new AMap.ToolBar({ position: { top: '70px', right: '16px' } }));
  map.addControl(new AMap.Scale({ position: { bottom: '20px', left: '16px' } }));

  map.on('click', onMapClick);
  map.on('mousemove', (e) => {
    $('cursor-pos').textContent =
      e.lnglat.getLng().toFixed(6) + ', ' + e.lnglat.getLat().toFixed(6);
  });

  if (satelliteOn) {
    satelliteLayer = new AMap.TileLayer.Satellite();
    map.setLayers([satelliteLayer]);
  }

  if (editMode) map.setDefaultCursor('crosshair');

  viewMode = mode;
  renderMarkers();
}

/* ============================ 交互绑定 ============================ */

function bindUI() {
  $('btn-edit').onclick = toggleEditMode;
  $('btn-clear').onclick = clearAll;
  $('btn-2d').onclick = () => switchView('2D');
  $('btn-3d').onclick = () => switchView('3D');
  $('btn-sat').onclick = toggleSatellite;
  $('btn-fit').onclick = fitView;
  $('btn-export').onclick = exportJSON;
  $('btn-import').onclick = () => $('file-input').click();
  $('file-input').onchange = importJSON;

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && editMode) { toggleEditMode(); return; }
    if ((e.key === 'Delete' || e.key === 'Backspace') && selectedId &&
        document.activeElement === document.body) {
      deleteStation(selectedId);
    }
  });
}

function setStatus(t) { $('status-text').textContent = t; }

/* ============================ 标定模式 ============================ */

function toggleEditMode() {
  editMode = !editMode;
  $('btn-edit').classList.toggle('active', editMode);
  $('edit-banner').classList.toggle('show', editMode);
  map.setDefaultCursor(editMode ? 'crosshair' : 'default');
  setStatus(editMode
    ? '标定模式：点击地图新增点位；按 Esc 退出'
    : '已退出标定模式');
}

function onMapClick(e) {
  if (suppressMapClick) return;
  if (!editMode) return;

  const lng = +e.lnglat.getLng().toFixed(6);
  const lat = +e.lnglat.getLat().toFixed(6);

  // 直接落点，不打断标定节奏；名称/容量可稍后在右侧列表编辑
  const id = nextId();
  stations.push({
    id,
    name: '待命名点位',
    lng, lat,
    capacity: null,
    func: 'other',
    count: null
  });
  saveToStorage();
  renderAll();
  setStatus(`已新增 ${id}（共 ${stations.length} 个），可在右侧列表编辑名称 / 容量`);
}

function nextId() {
  let max = 0;
  stations.forEach(s => {
    const m = /^P(\d+)$/.exec(s.id || '');
    if (m) max = Math.max(max, parseInt(m[1], 10));
  });
  return 'P' + String(max + 1).padStart(2, '0');
}

/* ============================ 渲染 ============================ */

function renderAll() {
  renderMarkers();
  renderSidebar();
  $('station-count').textContent = stations.length + ' 个';
}

function statusOf(st) {
  if (st.count == null || !st.capacity) return null;
  const r = st.count / st.capacity;
  if (r < window.STATUS_RULE.lowRatio) return 'low';
  if (r > window.STATUS_RULE.highRatio) return 'high';
  return 'normal';
}

function markerColor(st) {
  const s = statusOf(st);
  if (s === 'low') return '#c9302c';
  if (s === 'high') return '#e08a1e';
  if (s === 'normal') return '#185FA5';
  const f = window.FUNC_TYPES[st.func] || window.FUNC_TYPES.other;
  return f.color;
}

function markerSize(st) {
  const cap = st.capacity || 30;
  return Math.max(26, Math.min(46, 22 + cap * 0.28));
}

function renderMarkers() {
  const AMap = window.AMap;
  markers.forEach(m => m.setMap(null));
  markers.clear();

  stations.forEach(st => {
    const size = markerSize(st);
    const color = markerColor(st);
    const text = st.count != null ? String(st.count) : (st.capacity || '');

    const html = `
      <div class="p-marker ${st.id === selectedId ? 'selected' : ''}"
           style="width:${size}px;height:${size}px;background:${color};font-size:${size > 34 ? 13 : 11}px;">
        ${text}
      </div>
      <div class="p-label" style="margin-top:2px;text-align:center;">${st.id}</div>
    `;

    const marker = new AMap.Marker({
      position: [st.lng, st.lat],
      content: `<div style="display:flex;flex-direction:column;align-items:center;">${html}</div>`,
      offset: new AMap.Pixel(-size / 2, -size / 2),
      zIndex: 100,
      map: map
    });

    marker.on('click', () => {
      suppressMapClick = true;
      selectStation(st.id, true);
      setTimeout(() => { suppressMapClick = false; }, 50);
    });

    markers.set(st.id, marker);
  });
}

function renderSidebar() {
  const list = $('station-list');
  if (!stations.length) {
    list.innerHTML = `<div id="empty-hint">暂无点位。<br />点击「标定模式」后，<br />在地图上逐个点出 P 点即可。</div>`;
    return;
  }

  list.innerHTML = stations.map(st => {
    const f = window.FUNC_TYPES[st.func] || window.FUNC_TYPES.other;
    const s = statusOf(st);
    const sText = s === 'low' ? '缺车' : s === 'high' ? '淤积' : s === 'normal' ? '正常' : '—';
    const sColor = s === 'low' ? '#c9302c' : s === 'high' ? '#e08a1e' : s === 'normal' ? '#185FA5' : '#a8a69c';
    return `
      <div class="station-item ${st.id === selectedId ? 'selected' : ''}" data-id="${st.id}">
        <div class="row1">
          <span class="nm">${st.id} · ${escapeHtml(st.name)}</span>
          <span class="tag" style="background:${f.color}">${f.label}</span>
        </div>
        <div class="meta">
          ${st.lng.toFixed(5)}, ${st.lat.toFixed(5)} ｜ 容量 ${st.capacity ?? '—'}
          ｜ <span style="color:${sColor};font-weight:600;">${sText}</span>
        </div>
        <div style="margin-top:5px;display:flex;gap:6px;">
          <button data-act="edit" data-id="${st.id}" style="padding:2px 8px;font-size:11px;">编辑</button>
          <button data-act="del" data-id="${st.id}" style="padding:2px 8px;font-size:11px;">删除</button>
        </div>
      </div>
    `;
  }).join('');

  list.querySelectorAll('.station-item').forEach(el => {
    el.onclick = (ev) => {
      if (ev.target.tagName === 'BUTTON') return;
      selectStation(el.dataset.id, true);
    };
  });
  list.querySelectorAll('button[data-act="edit"]').forEach(btn => {
    btn.onclick = (ev) => { ev.stopPropagation(); editStation(btn.dataset.id); };
  });
  list.querySelectorAll('button[data-act="del"]').forEach(btn => {
    btn.onclick = (ev) => { ev.stopPropagation(); deleteStation(btn.dataset.id); };
  });
}

function selectStation(id, pan) {
  selectedId = id;
  renderAll();
  const st = stations.find(s => s.id === id);
  if (!st) return;
  if (pan && map) map.panTo([st.lng, st.lat]);
  showInfo(st);
}

function showInfo(st) {
  if (!infoWindow || !window.AMap) return;
  const f = window.FUNC_TYPES[st.func] || window.FUNC_TYPES.other;
  const s = statusOf(st);
  const sText = s === 'low' ? '缺车' : s === 'high' ? '淤积' : s === 'normal' ? '正常' : '未观测';
  infoWindow.setContent(`
    <div style="padding:10px 12px;min-width:200px;font-family:'Microsoft YaHei',sans-serif;">
      <div style="font-weight:600;color:#0d3b66;margin-bottom:6px;">${st.id} · ${escapeHtml(st.name)}</div>
      <div style="font-size:12px;color:#5f5e5a;line-height:1.9;">
        功能类别：${f.label}<br/>
        容量：${st.capacity ?? '—'} 辆<br/>
        在点车辆：${st.count ?? '—'} 辆（${sText}）<br/>
        坐标：${st.lng.toFixed(6)}, ${st.lat.toFixed(6)}
      </div>
    </div>
  `);
  infoWindow.open(map, [st.lng, st.lat]);
}

function editStation(id) {
  const st = stations.find(s => s.id === id);
  if (!st) return;
  const name = prompt('点位名称：', st.name);
  if (name === null) return;
  st.name = name.trim() || st.name;

  const cap = prompt('容量（辆）：', st.capacity ?? '');
  if (cap !== null) st.capacity = parseInt(cap, 10) || null;

  const funcKeys = Object.keys(window.FUNC_TYPES);
  const funcHint = funcKeys.map(k => `${k}=${window.FUNC_TYPES[k].label}`).join('，');
  const fk = prompt('功能类别（' + funcHint + '）：', st.func);
  if (fk !== null && window.FUNC_TYPES[fk.trim()]) st.func = fk.trim();

  const cnt = prompt('当前在点车辆数（留空表示未观测）：', st.count ?? '');
  if (cnt !== null) st.count = cnt.trim() === '' ? null : (parseInt(cnt, 10) || 0);

  saveToStorage();
  renderAll();
  setStatus(`已更新 ${id}`);
}

function deleteStation(id) {
  const st = stations.find(s => s.id === id);
  if (!st) return;
  if (!confirm(`确定删除 ${id} · ${st.name} ？`)) return;
  stations = stations.filter(s => s.id !== id);
  if (selectedId === id) selectedId = null;
  saveToStorage();
  renderAll();
  setStatus(`已删除 ${id}，剩余 ${stations.length} 个点位`);
}

function clearAll() {
  if (!stations.length) return;
  if (!confirm(`确定清空全部 ${stations.length} 个点位？（不可恢复）`)) return;
  stations = [];
  selectedId = null;
  markers.forEach(m => m.setMap(null));
  markers.clear();
  saveToStorage();
  renderAll();
  setStatus('已清空');
}

/* ============================ 视图 ============================ */

function switchView(mode) {
  if (!map) return;
  if (viewMode === mode) { updateViewButtons(mode); return; }

  // 销毁重建：2D / 3D 各自使用对应的地图引擎，避免运行时切换失效
  buildMap(mode);
  updateViewButtons(mode);
  setStatus('视图：' + mode + (mode === '3D' ? '（俯仰 ' + window.CAMPUS.pitch + '°）' : ''));
}

function updateViewButtons(mode) {
  $('btn-2d').classList.toggle('active', mode === '2D');
  $('btn-3d').classList.toggle('active', mode === '3D');
}

function toggleSatellite() {
  if (!map || !window.AMap) return;
  satelliteOn = !satelliteOn;
  // 重建以套用/移除卫星图层，避免底图还原不确定
  buildMap(viewMode);
  $('btn-sat').classList.toggle('active', satelliteOn);
  setStatus(satelliteOn ? '已切换为卫星底图' : '已切换为标准底图');
}

function fitView() {
  if (!map) return;
  if (!stations.length) {
    map.setZoomAndCenter(window.CAMPUS.zoom, window.CAMPUS.center);
    return;
  }
  const AMap = window.AMap;
  const pts = stations.map(st => new AMap.Marker({ position: [st.lng, st.lat] }));
  map.setFitView(pts, false, [80, 80, 80, 80], 18);
}

/* ============================ 存储 ============================ */

function saveToStorage() {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(stations));
  } catch (e) { console.warn('本地保存失败', e); }
}

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) stations = arr;
    }
  } catch (e) { console.warn('本地读取失败', e); }
}

/* ============================ 导出 / 导入 ============================ */

function exportJSON() {
  if (!stations.length) { alert('还没有点位可导出。'); return; }
  const payload = {
    meta: {
      campus: window.CAMPUS.name,
      exportedAt: new Date().toISOString(),
      count: stations.length,
      coordSys: 'GCJ-02（高德坐标系）'
    },
    stations: stations
  };
  downloadJSON(payload, `stations_${stamp()}.json`);
  setStatus('已导出 JSON');
}

function downloadJSON(obj, filename) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function importJSON(ev) {
  const file = ev.target.files && ev.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const obj = JSON.parse(reader.result);
      const arr = Array.isArray(obj) ? obj : obj.stations;
      if (!Array.isArray(arr)) throw new Error('文件中未找到 stations 数组');
      stations = arr;
      selectedId = null;
      saveToStorage();
      renderAll();
      fitView();
      setStatus(`已导入 ${stations.length} 个点位`);
    } catch (e) {
      alert('导入失败：' + e.message);
    }
    ev.target.value = '';
  };
  reader.readAsText(file, 'utf-8');
}

function stamp() {
  const d = new Date();
  const p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}`;
}

/* ============================ 工具 ============================ */

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}
