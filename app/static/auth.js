// 공통 인증 유틸

function getToken() { return localStorage.getItem('jwt'); }
function getUser() {
  try { return JSON.parse(localStorage.getItem('user')); } catch { return null; }
}

function logout() {
  localStorage.removeItem('jwt');
  localStorage.removeItem('user');
  localStorage.removeItem('bookmarks');
  localStorage.removeItem('visited');
  localStorage.removeItem('myCollections');
  location.href = '/login';
}

// 헤더에 유저 아바타 삽입
function renderUserBadge(containerId) {
  const user = getUser();
  const el = document.getElementById(containerId);
  if (!el) return;
  if (user) {
    el.innerHTML = `
      <img src="${user.picture}" style="width:100%;height:100%;border-radius:50%;object-fit:cover;cursor:pointer" onclick="toggleUserMenu()" onerror="this.src=''">
      <div id="userMenu" style="display:none;position:absolute;top:52px;right:16px;background:#fff;border:1px solid #eee;border-radius:10px;box-shadow:0 4px 16px rgba(0,0,0,0.1);z-index:200;padding:8px 0;min-width:150px">
        <div style="padding:10px 16px;font-size:13px;color:#888;border-bottom:1px solid #f0f0f0">${user.email}</div>
        <div onclick="openMyReviews()" style="padding:10px 16px;font-size:13px;color:#333;cursor:pointer;border-bottom:1px solid #f0f0f0">내가 쓴 댓글</div>
        <div onclick="openMyCollections()" style="padding:10px 16px;font-size:13px;color:#333;cursor:pointer;border-bottom:1px solid #f0f0f0">내 컬렉션</div>
        <div onclick="logout()" style="padding:10px 16px;font-size:13px;color:#e74c3c;cursor:pointer">로그아웃</div>
      </div>`;
  } else {
    el.innerHTML = `<a href="/login" style="display:flex;width:100%;height:100%;align-items:center;justify-content:center"><img src="/static/images/icon-account.svg" alt="로그인" style="width:24px;height:24px"></a>`;
  }
}

function toggleUserMenu() {
  const menu = document.getElementById('userMenu');
  if (menu) menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
}

/* ── 내가 쓴 댓글 모아보기 팝업 ── */
const MR_CSS = `
  .mr-overlay { display:none; position:fixed; inset:0; background:rgba(0,30,60,0.45); z-index:1300; align-items:center; justify-content:center; }
  .mr-overlay.open { display:flex; }
  .mr-sheet { width:340px; max-height:75vh; display:flex; flex-direction:column; background:#fff; border-radius:24px; padding:26px 22px 18px; position:relative; box-shadow:0 12px 40px rgba(0,40,80,0.25); animation:mrPop .4s cubic-bezier(.34,1.56,.64,1); }
  @keyframes mrPop { from { transform:scale(.75) translateY(20px); opacity:0; } to { transform:scale(1) translateY(0); opacity:1; } }
  .mr-close { position:absolute; top:14px; right:14px; width:28px; height:28px; border:none; border-radius:50%; background:#f4f4f4; color:#999; font-size:13px; cursor:pointer; display:flex; align-items:center; justify-content:center; }
  .mr-close:active { background:#e8e8e8; }
  .mr-title { font-family:'Poppins','Apple SD Gothic Neo',sans-serif; font-size:17px; font-weight:700; color:#005ba9; text-align:center; letter-spacing:-0.3px; margin-bottom:14px; }
  .mr-list { overflow-y:auto; scrollbar-width:none; min-height:80px; }
  .mr-list::-webkit-scrollbar { display:none; }
  .mr-item { padding:12px 2px; border-bottom:1px solid #eee; }
  .mr-item:last-child { border-bottom:none; }
  .mr-item-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:4px; gap:8px; }
  .mr-item-rest { font-family:'Poppins','Apple SD Gothic Neo',sans-serif; font-size:13px; font-weight:700; color:#191919; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .mr-item-stars { font-size:12px; color:#005ba9; letter-spacing:1px; flex-shrink:0; }
  .mr-item-text { font-family:'Inter','Apple SD Gothic Neo',sans-serif; font-size:13px; color:#444; line-height:1.6; margin-bottom:4px; white-space:pre-wrap; }
  .mr-item-foot { display:flex; align-items:center; justify-content:space-between; }
  .mr-item-date { font-family:'Inter',sans-serif; font-size:11px; color:#aaa; }
  .mr-item-del { font-size:11px; color:#aaa; background:none; border:none; cursor:pointer; padding:0; text-decoration:underline; }
  .mr-empty { font-family:'Inter','Apple SD Gothic Neo',sans-serif; font-size:12px; color:#aaa; text-align:center; padding:30px 0; line-height:1.6; }
`;

let _mrBuilt = false;
function _mrBuild() {
  if (_mrBuilt) return;
  _mrBuilt = true;
  const style = document.createElement('style');
  style.textContent = MR_CSS;
  document.head.appendChild(style);
  const overlay = document.createElement('div');
  overlay.className = 'mr-overlay';
  overlay.id = 'mrOverlay';
  overlay.innerHTML = `
    <div class="mr-sheet" onclick="event.stopPropagation()">
      <button class="mr-close" onclick="closeMyReviews()" aria-label="닫기">✕</button>
      <div class="mr-title">내가 쓴 댓글</div>
      <div class="mr-list" id="mrList"></div>
    </div>`;
  overlay.addEventListener('click', e => { if (e.target === overlay) closeMyReviews(); });
  document.body.appendChild(overlay);
}

function _mrEscape(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function _mrLoad() {
  const list = document.getElementById('mrList');
  list.innerHTML = '<div class="mr-empty">불러오는 중...</div>';
  try {
    const res = await fetch('/api/reviews/mine', {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    if (!res.ok) throw new Error();
    const reviews = await res.json();
    if (!reviews.length) {
      list.innerHTML = '<div class="mr-empty">아직 쓴 댓글이 없어요.<br>식당 상세에서 첫 리뷰를 남겨보세요!</div>';
      return;
    }
    list.innerHTML = reviews.map(r => {
      const stars = '★'.repeat(r.rating) + '☆'.repeat(5 - r.rating);
      return `
        <div class="mr-item">
          <div class="mr-item-head">
            <span class="mr-item-rest">${_mrEscape(r.restaurant)}</span>
            <span class="mr-item-stars">${stars}</span>
          </div>
          <div class="mr-item-text">${_mrEscape(r.text)}</div>
          <div class="mr-item-foot">
            <span class="mr-item-date">${r.created_at.slice(0, 10)}</span>
            <button class="mr-item-del" onclick="deleteMyReview('${r.id}')">삭제</button>
          </div>
        </div>`;
    }).join('');
  } catch {
    list.innerHTML = '<div class="mr-empty">댓글을 불러오지 못했어요.</div>';
  }
}

function openMyReviews() {
  if (!getToken()) { location.href = '/login'; return; }
  const menu = document.getElementById('userMenu');
  if (menu) menu.style.display = 'none';
  _mrBuild();
  document.getElementById('mrOverlay').classList.add('open');
  _mrLoad();
}

function closeMyReviews() {
  document.getElementById('mrOverlay')?.classList.remove('open');
}

async function deleteMyReview(id) {
  if (!confirm('리뷰를 삭제할까요?')) return;
  try {
    await fetch(`/api/reviews/${id}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${getToken()}` },
    });
    _mrLoad();
    // 상세 페이지가 열려 있으면 리뷰 목록도 갱신
    if (typeof loadReviews === 'function') loadReviews();
  } catch {}
}

document.addEventListener('click', e => {
  const menu = document.getElementById('userMenu');
  if (menu && !e.target.closest('#authArea')) menu.style.display = 'none';
});

// 토큰 만료/무효(401) 시 세션 정리 — 로그인된 척하며 서버 저장만 조용히 실패하는 상태 방지
function handleAuthExpired(res) {
  if (res && res.status === 401) {
    localStorage.removeItem('jwt');
    localStorage.removeItem('user');
    if (typeof renderUserBadge === 'function') renderUserBadge('authArea');
    return true;
  }
  return false;
}

// 서버 → 로컬 덮어쓰기 (계정별 독립)
async function syncBookmarks() {
  const token = getToken();
  if (!token) return;
  try {
    const res = await fetch('/api/auth/bookmarks', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (handleAuthExpired(res)) return;
    if (res.ok) {
      const serverBookmarks = await res.json();
      localStorage.setItem('bookmarks', JSON.stringify(serverBookmarks));
    }
  } catch {}
}

async function pushBookmarks(bookmarks) {
  const token = getToken();
  if (!token) return;
  try {
    const res = await fetch('/api/auth/bookmarks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ bookmarks }),
    });
    handleAuthExpired(res);
  } catch {}
}

async function syncVisited() {
  const token = getToken();
  if (!token) return;
  try {
    const res = await fetch('/api/auth/visited', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (handleAuthExpired(res)) return;
    if (res.ok) {
      const serverVisited = await res.json();
      localStorage.setItem('visited', JSON.stringify(serverVisited));
    }
  } catch {}
}

async function pushVisited(visited) {
  const token = getToken();
  if (!token) return;
  try {
    const res = await fetch('/api/auth/visited', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ visited }),
    });
    handleAuthExpired(res);
  } catch {}
}

// 내 컬렉션 — 유저 정보(users.json)에 저장, 브라우저가 달라도 유지
async function syncCollections() {
  const token = getToken();
  if (!token) return;
  try {
    const res = await fetch('/api/auth/collections', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (handleAuthExpired(res)) return;
    if (res.ok) {
      const serverCols = await res.json();
      localStorage.setItem('myCollections', JSON.stringify(serverCols));
    }
  } catch {}
}

async function pushCollections(collections) {
  const token = getToken();
  if (!token) return;
  try {
    const res = await fetch('/api/auth/collections', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ collections }),
    });
    handleAuthExpired(res);
  } catch {}
}

/* ── 내 컬렉션 관리 팝업 (삭제 가능) ── */
const MC_CSS = `
  .mc-overlay { display:none; position:fixed; inset:0; background:rgba(0,30,60,0.45); z-index:1300; align-items:center; justify-content:center; }
  .mc-overlay.open { display:flex; }
  .mc-sheet { width:340px; max-height:75vh; display:flex; flex-direction:column; background:#fff; border-radius:24px; padding:26px 22px 18px; position:relative; box-shadow:0 12px 40px rgba(0,40,80,0.25); animation:mrPop .4s cubic-bezier(.34,1.56,.64,1); }
  .mc-close { position:absolute; top:14px; right:14px; width:28px; height:28px; border:none; border-radius:50%; background:#f4f4f4; color:#999; font-size:13px; cursor:pointer; display:flex; align-items:center; justify-content:center; }
  .mc-close:active { background:#e8e8e8; }
  .mc-title { font-family:'Poppins','Apple SD Gothic Neo',sans-serif; font-size:17px; font-weight:700; color:#005ba9; text-align:center; letter-spacing:-0.3px; margin-bottom:14px; }
  .mc-list { overflow-y:auto; scrollbar-width:none; min-height:60px; }
  .mc-list::-webkit-scrollbar { display:none; }
  .mc-item { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:12px 2px; border-bottom:1px solid #eee; }
  .mc-item:last-child { border-bottom:none; }
  .mc-item-name { font-family:'Poppins','Apple SD Gothic Neo',sans-serif; font-size:13px; font-weight:700; color:#191919; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .mc-item-count { font-family:'Inter',sans-serif; font-size:11px; color:#5888b2; margin-left:6px; font-weight:500; }
  .mc-item-del { font-family:'Inter','Apple SD Gothic Neo',sans-serif; font-size:11px; color:#d6453d; background:#fff; border:1px solid #f3c9c6; border-radius:14px; padding:4px 12px; cursor:pointer; flex-shrink:0; }
  .mc-item-del:active { background:#fdf0ef; }
  .mc-empty { font-family:'Inter','Apple SD Gothic Neo',sans-serif; font-size:12px; color:#aaa; text-align:center; padding:30px 0; line-height:1.6; }
`;

let _mcBuilt = false;
function _mcBuild() {
  if (_mcBuilt) return;
  _mcBuilt = true;
  const style = document.createElement('style');
  style.textContent = MC_CSS;
  document.head.appendChild(style);
  const overlay = document.createElement('div');
  overlay.className = 'mc-overlay';
  overlay.id = 'mcOverlay';
  overlay.innerHTML = `
    <div class="mc-sheet" onclick="event.stopPropagation()">
      <button class="mc-close" onclick="closeMyCollections()" aria-label="닫기">✕</button>
      <div class="mc-title">내 컬렉션</div>
      <div class="mc-list" id="mcList"></div>
    </div>`;
  overlay.addEventListener('click', e => { if (e.target === overlay) closeMyCollections(); });
  document.body.appendChild(overlay);
}

function _mcRender() {
  const cols = JSON.parse(localStorage.getItem('myCollections') || '[]');
  const list = document.getElementById('mcList');
  if (!cols.length) {
    list.innerHTML = '<div class="mc-empty">아직 만든 컬렉션이 없어요.<br>내 목록이나 저장 팝업에서 만들 수 있어요!</div>';
    return;
  }
  list.innerHTML = cols.map(c => `
    <div class="mc-item">
      <div style="min-width:0">
        <span class="mc-item-name">${c.name.replace(/&/g,'&amp;').replace(/</g,'&lt;')}</span>
        <span class="mc-item-count">${(c.items || []).length}곳</span>
      </div>
      <button class="mc-item-del" onclick="deleteMyCollection('${c.name.replace(/'/g, "\\'")}')">삭제</button>
    </div>`).join('');
}

function openMyCollections() {
  const menu = document.getElementById('userMenu');
  if (menu) menu.style.display = 'none';
  _mcBuild();
  document.getElementById('mcOverlay').classList.add('open');
  // 서버 최신본 동기화 후 렌더
  _mcRender();
  syncCollections().then(_mcRender);
}

function closeMyCollections() {
  document.getElementById('mcOverlay')?.classList.remove('open');
}

function deleteMyCollection(name) {
  if (!confirm(`'${name}' 컬렉션을 삭제할까요?`)) return;
  const cols = JSON.parse(localStorage.getItem('myCollections') || '[]').filter(c => c.name !== name);
  localStorage.setItem('myCollections', JSON.stringify(cols));
  pushCollections(cols);
  _mcRender();
  // 내 목록 페이지가 열려 있으면 칩 갱신
  if (typeof render === 'function') { try { render(); } catch {} }
}
