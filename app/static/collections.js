/* ── 컬렉션 선택 팝업 공용 모듈 ──
 * 하트로 저장할 때 커스텀 컬렉션이 있으면 "어디에 저장할까요?" 팝업을 띄운다.
 * 컬렉션이 하나도 없으면 팝업 없이 기존 저장 동작 그대로.
 * window.CollectionPicker.open(itemName, onDone) / .removeFromAll(itemName)
 */
(function () {
  const KEY = 'myCollections';

  function getCollections() {
    return JSON.parse(localStorage.getItem(KEY) || '[]');
  }
  function saveCollections(cols) {
    localStorage.setItem(KEY, JSON.stringify(cols));
  }
  function addToCollection(colName, itemName) {
    const cols = getCollections();
    const col = cols.find(c => c.name === colName);
    if (col && !col.items.includes(itemName)) {
      col.items.push(itemName);
      saveCollections(cols);
    }
  }
  function removeFromAll(itemName) {
    const cols = getCollections();
    let changed = false;
    cols.forEach(c => {
      const i = c.items.indexOf(itemName);
      if (i !== -1) { c.items.splice(i, 1); changed = true; }
    });
    if (changed) saveCollections(cols);
  }

  const CSS = `
    .cp-overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 30, 60, 0.45);
      z-index: 1200;
      align-items: center;
      justify-content: center;
    }
    .cp-overlay.open { display: flex; }
    .cp-sheet {
      width: 330px;
      max-height: 80vh;
      overflow-y: auto;
      background: #fff;
      border-radius: 24px;
      padding: 26px 24px 20px;
      position: relative;
      text-align: center;
      box-shadow: 0 12px 40px rgba(0, 40, 80, 0.25);
      animation: cpPop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
      scrollbar-width: none;
    }
    .cp-sheet::-webkit-scrollbar { display: none; }
    @keyframes cpPop {
      from { transform: scale(0.75) translateY(20px); opacity: 0; }
      to   { transform: scale(1) translateY(0); opacity: 1; }
    }
    .cp-close {
      position: absolute;
      top: 14px; right: 14px;
      width: 28px; height: 28px;
      border: none; border-radius: 50%;
      background: #f4f4f4; color: #999;
      font-size: 13px; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
    }
    .cp-close:active { background: #e8e8e8; }
    .cp-title {
      font-family: 'Poppins', 'Apple SD Gothic Neo', sans-serif;
      font-size: 17px;
      font-weight: 700;
      color: #005ba9;
      letter-spacing: -0.3px;
    }
    .cp-desc {
      font-family: 'Inter', 'Apple SD Gothic Neo', sans-serif;
      font-size: 12px;
      color: #888;
      line-height: 1.6;
      margin: 8px 0 16px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .cp-desc b { color: #191919; font-weight: 700; }
    .cp-list { display: flex; flex-direction: column; gap: 8px; }
    .cp-option {
      width: 100%;
      height: 44px;
      border: 1px solid #dcdcdc;
      border-radius: 12px;
      background: #fff;
      font-family: 'Inter', 'Apple SD Gothic Neo', sans-serif;
      font-size: 13px;
      font-weight: 500;
      color: #333;
      text-align: left;
      padding: 0 16px;
      cursor: pointer;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .cp-option:active { background: #ddf0ff; border-color: #005ba9; }
    .cp-new-toggle {
      width: 100%;
      height: 44px;
      border: 1.5px dashed #b9cfe3;
      border-radius: 12px;
      background: #fff;
      font-family: 'Inter', 'Apple SD Gothic Neo', sans-serif;
      font-size: 13px;
      font-weight: 700;
      color: #005ba9;
      cursor: pointer;
      margin-top: 8px;
    }
    .cp-new-toggle:active { background: #f0f7ff; }
    .cp-new-row { display: none; gap: 8px; margin-top: 8px; }
    .cp-new-row.show { display: flex; }
    .cp-input {
      flex: 1;
      height: 44px;
      border: 1px solid #dcdcdc;
      border-radius: 22px;
      background: #f4f4f4;
      padding: 0 16px;
      font-family: 'Inter', 'Apple SD Gothic Neo', sans-serif;
      font-size: 13px;
      color: #333;
      outline: none;
      min-width: 0;
    }
    .cp-input:focus { border-color: #005ba9; background: #fff; }
    .cp-create {
      height: 44px;
      padding: 0 18px;
      border: none;
      border-radius: 22px;
      background: #005ba9;
      color: #fff;
      font-family: 'Inter', 'Apple SD Gothic Neo', sans-serif;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
      flex-shrink: 0;
    }
    .cp-create:active { opacity: 0.85; }
    .cp-error {
      display: none;
      font-family: 'Inter', 'Apple SD Gothic Neo', sans-serif;
      font-size: 11px;
      color: #d6453d;
      text-align: left;
      margin: 6px 4px 0;
    }
    .cp-error.show { display: block; }
    .cp-skip {
      width: 100%;
      margin-top: 14px;
      background: none;
      border: none;
      font-family: 'Inter', 'Apple SD Gothic Neo', sans-serif;
      font-size: 12px;
      color: #aaa;
      text-decoration: underline;
      cursor: pointer;
    }
  `;

  let built = false;
  let currentItem = null;
  let onDoneCb = null;

  function build() {
    if (built) return;
    built = true;

    const style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);

    const overlay = document.createElement('div');
    overlay.className = 'cp-overlay';
    overlay.id = 'cpOverlay';
    overlay.innerHTML = `
      <div class="cp-sheet" id="cpSheet">
        <button class="cp-close" id="cpClose" aria-label="닫기">✕</button>
        <div class="cp-title">어디에 저장할까요?</div>
        <div class="cp-desc" id="cpDesc"></div>
        <div class="cp-list" id="cpList"></div>
        <button class="cp-new-toggle" id="cpNewToggle">+ 새 컬렉션 만들기</button>
        <div class="cp-new-row" id="cpNewRow">
          <input class="cp-input" id="cpInput" type="text" maxlength="12" placeholder="컬렉션 이름 (최대 12자)" />
          <button class="cp-create" id="cpCreate">만들기</button>
        </div>
        <div class="cp-error" id="cpError"></div>
        <button class="cp-skip" id="cpSkip">따로 분류 안 할래요</button>
      </div>`;
    document.body.appendChild(overlay);

    overlay.addEventListener('click', e => { if (e.target === overlay) finish(null); });
    document.getElementById('cpSheet').addEventListener('click', e => e.stopPropagation());
    document.getElementById('cpClose').addEventListener('click', () => finish(null));
    document.getElementById('cpSkip').addEventListener('click', () => finish(null));
    document.getElementById('cpNewToggle').addEventListener('click', () => {
      document.getElementById('cpNewRow').classList.add('show');
      document.getElementById('cpNewToggle').style.display = 'none';
      document.getElementById('cpInput').focus();
    });
    document.getElementById('cpCreate').addEventListener('click', createAndPick);
    document.getElementById('cpInput').addEventListener('keydown', e => {
      if (e.key === 'Enter') createAndPick();
    });
  }

  function renderOptions() {
    const list = document.getElementById('cpList');
    list.innerHTML = getCollections().map(c =>
      `<button class="cp-option" data-name="${c.name.replace(/"/g, '&quot;')}">${c.name}</button>`
    ).join('');
    list.querySelectorAll('.cp-option').forEach(btn => {
      btn.addEventListener('click', () => {
        addToCollection(btn.dataset.name, currentItem);
        finish(btn.dataset.name);
      });
    });
  }

  function createAndPick() {
    const input = document.getElementById('cpInput');
    const error = document.getElementById('cpError');
    const name = input.value.trim();
    if (!name) {
      error.textContent = '컬렉션 이름을 입력해주세요';
      error.classList.add('show');
      return;
    }
    const reserved = ['전체', '밥.zip', '커피.zip'];
    if (reserved.includes(name) || getCollections().some(c => c.name === name)) {
      error.textContent = '이미 있는 이름이에요';
      error.classList.add('show');
      return;
    }
    const cols = getCollections();
    cols.push({ name, items: [] });
    saveCollections(cols);
    addToCollection(name, currentItem);
    finish(name);
  }

  function finish(colName) {
    document.getElementById('cpOverlay').classList.remove('open');
    const cb = onDoneCb;
    onDoneCb = null;
    currentItem = null;
    if (cb) cb(colName);
  }

  function open(itemName, onDone) {
    // 만든 컬렉션이 없으면 팝업 없이 기존 동작 유지
    if (!getCollections().length) {
      if (onDone) onDone(null);
      return;
    }
    build();
    currentItem = itemName;
    onDoneCb = onDone || null;
    document.getElementById('cpDesc').innerHTML = `<b>${itemName}</b> 을(를) 컬렉션에 담아보세요`;
    document.getElementById('cpError').classList.remove('show');
    document.getElementById('cpNewRow').classList.remove('show');
    document.getElementById('cpNewToggle').style.display = 'block';
    document.getElementById('cpInput').value = '';
    renderOptions();
    document.getElementById('cpOverlay').classList.add('open');
  }

  window.CollectionPicker = { open, removeFromAll, getCollections };
})();
