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
      <div id="userMenu" style="display:none;position:absolute;top:52px;right:16px;background:#fff;border:1px solid #eee;border-radius:10px;box-shadow:0 4px 16px rgba(0,0,0,0.1);z-index:200;padding:8px 0;min-width:140px">
        <div style="padding:10px 16px;font-size:13px;color:#888;border-bottom:1px solid #f0f0f0">${user.email}</div>
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

document.addEventListener('click', e => {
  const menu = document.getElementById('userMenu');
  if (menu && !e.target.closest('#authArea')) menu.style.display = 'none';
});

// 서버 → 로컬 덮어쓰기 (계정별 독립)
async function syncBookmarks() {
  const token = getToken();
  if (!token) return;
  try {
    const res = await fetch('/api/auth/bookmarks', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
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
    await fetch('/api/auth/bookmarks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ bookmarks }),
    });
  } catch {}
}

async function syncVisited() {
  const token = getToken();
  if (!token) return;
  try {
    const res = await fetch('/api/auth/visited', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
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
    await fetch('/api/auth/visited', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ visited }),
    });
  } catch {}
}
