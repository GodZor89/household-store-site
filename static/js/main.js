/* ============================================================
   ДомашнийУют — основной JavaScript
   Функции: переключение темы, слайдер, поиск AJAX, корзина, меню
   ============================================================ */

'use strict';

/* ─── ПЕРЕКЛЮЧАТЕЛЬ ТЕМЫ (стандартная / для слабовидящих) ─── */

function toggleTheme() {
  const body    = document.body;
  const mainCss = document.getElementById('main-css');
  const accCss  = document.getElementById('access-css');
  const btn     = document.getElementById('themeToggle');
  const isAcc   = body.classList.contains('accessibility-theme');

  if (isAcc) {
    // Переключение на стандартную тему
    body.classList.remove('accessibility-theme');
    body.classList.add('standard-theme');
    if (accCss)  accCss.disabled = true;
    if (mainCss) mainCss.disabled = false;
    if (btn) btn.innerHTML = '<i class="bi bi-eye"></i><span class="toggle-text">Для слабовидящих</span>';
    localStorage.setItem('theme', 'standard');
  } else {
    // Переключение на тему для слабовидящих (ГОСТ Р 52872-2012)
    body.classList.remove('standard-theme');
    body.classList.add('accessibility-theme');
    if (accCss)  accCss.disabled = false;
    if (mainCss) mainCss.disabled = false;
    if (btn) btn.innerHTML = '<i class="bi bi-eye-slash"></i><span class="toggle-text">Стандартная тема</span>';
    localStorage.setItem('theme', 'accessibility');
  }
}

/* Восстановление темы при загрузке страницы */
(function initTheme() {
  const saved = localStorage.getItem('theme');
  if (saved === 'accessibility') {
    const body   = document.body;
    const accCss = document.getElementById('access-css');
    const btn    = document.getElementById('themeToggle');
    body.classList.remove('standard-theme');
    body.classList.add('accessibility-theme');
    if (accCss) accCss.disabled = false;
    if (btn) btn.innerHTML = '<i class="bi bi-eye-slash"></i><span class="toggle-text">Стандартная тема</span>';
  }
})();


/* ─── СЛАЙДЕР БАННЕРОВ ─── */

(function initSlider() {
  const track    = document.querySelector('.slider-track');
  const slides   = document.querySelectorAll('.slide');
  const dotsWrap = document.querySelector('.slider-controls');
  const prevBtn  = document.querySelector('.slider-prev');
  const nextBtn  = document.querySelector('.slider-next');

  if (!track || slides.length === 0) return;

  let current  = 0;
  let autoPlay = null;

  // Создаём точки
  if (dotsWrap) {
    slides.forEach((_, i) => {
      const dot = document.createElement('button');
      dot.className = 'slider-dot' + (i === 0 ? ' active' : '');
      dot.setAttribute('aria-label', `Слайд ${i + 1}`);
      dot.addEventListener('click', () => goTo(i));
      dotsWrap.appendChild(dot);
    });
  }

  function goTo(index) {
    current = (index + slides.length) % slides.length;
    track.style.transform = `translateX(-${current * 100}%)`;
    document.querySelectorAll('.slider-dot').forEach((d, i) => {
      d.classList.toggle('active', i === current);
    });
  }

  function next() { goTo(current + 1); }
  function prev() { goTo(current - 1); }

  if (prevBtn) prevBtn.addEventListener('click', () => { prev(); resetAuto(); });
  if (nextBtn) nextBtn.addEventListener('click', () => { next(); resetAuto(); });

  function startAuto() {
    autoPlay = setInterval(next, 5000);
  }
  function resetAuto() {
    clearInterval(autoPlay);
    startAuto();
  }

  // Свайп (сенсорный экран)
  let touchX = 0;
  track.addEventListener('touchstart', e => { touchX = e.touches[0].clientX; }, { passive: true });
  track.addEventListener('touchend', e => {
    const diff = touchX - e.changedTouches[0].clientX;
    if (Math.abs(diff) > 40) { diff > 0 ? next() : prev(); resetAuto(); }
  });

  startAuto();
})();


/* ─── ЖИВОЙ ПОИСК (AJAX) ─── */

(function initSearch() {
  const input   = document.getElementById('searchInput');
  const suggest = document.getElementById('searchSuggestions');
  if (!input || !suggest) return;

  let debounceTimer;

  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const q = input.value.trim();

    if (q.length < 2) {
      suggest.innerHTML = '';
      suggest.classList.remove('show');
      return;
    }

    debounceTimer = setTimeout(() => {
      fetch(`/api/search?q=${encodeURIComponent(q)}`)
        .then(r => r.json())
        .then(results => {
          if (!results.length) {
            suggest.innerHTML = '';
            suggest.classList.remove('show');
            return;
          }

          suggest.innerHTML = results.map(r => `
            <a class="suggestion-item" href="${r.url}">
              ${r.image
                ? `<img src="${r.image}" alt="${r.name}" loading="lazy">`
                : `<div style="width:40px;height:40px;background:var(--bg-muted);display:flex;align-items:center;justify-content:center;"><i class="bi bi-box"></i></div>`
              }
              <div>
                <div class="s-name">${r.name}
                  <span class="s-type">${r.type === 'product' ? 'Товар' : 'Статья'}</span>
                </div>
                ${r.price ? `<div class="s-price">${r.price}</div>` : ''}
              </div>
            </a>
          `).join('');

          suggest.classList.add('show');
        })
        .catch(() => { suggest.classList.remove('show'); });
    }, 300);
  });

  // Закрыть подсказки при клике вне
  document.addEventListener('click', e => {
    if (!input.contains(e.target) && !suggest.contains(e.target)) {
      suggest.classList.remove('show');
    }
  });

  // Навигация по подсказкам стрелками
  input.addEventListener('keydown', e => {
    const items = suggest.querySelectorAll('.suggestion-item');
    let active  = suggest.querySelector('.suggestion-item:focus');

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!active && items.length) {
        items[0].focus();
      } else {
        const idx = Array.from(items).indexOf(active);
        if (idx < items.length - 1) items[idx + 1].focus();
      }
    } else if (e.key === 'Escape') {
      suggest.classList.remove('show');
      input.focus();
    }
  });
})();


/* ─── ДРОПДАУН ПОЛЬЗОВАТЕЛЯ (клик, не hover) ─── */

(function initUserMenu() {
  const wrap     = document.getElementById('userMenuWrap');
  const btn      = document.getElementById('userMenuBtn');
  const dropdown = document.getElementById('userDropdown');
  if (!wrap || !btn || !dropdown) return;

  function openMenu()  { dropdown.classList.add('open');    btn.setAttribute('aria-expanded', 'true');  }
  function closeMenu() { dropdown.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); }
  function isOpen()    { return dropdown.classList.contains('open'); }

  // Клик по кнопке (или иконке внутри неё) — переключаем
  btn.addEventListener('click', () => {
    isOpen() ? closeMenu() : openMenu();
  });

  // Единый обработчик на document — закрываем если клик вне всего блока
  document.addEventListener('click', e => {
    if (!wrap.contains(e.target)) {
      closeMenu();
    }
  });

  // Закрытие по Escape
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && isOpen()) {
      closeMenu();
      btn.focus();
    }
  });
})();


/* ─── БУРГЕР-МЕНЮ (мобильная навигация) ─── */

(function initBurger() {
  const btn = document.getElementById('burgerBtn');
  const nav = document.getElementById('categoryNav');
  if (!btn || !nav) return;

  btn.addEventListener('click', () => {
    nav.classList.toggle('open');
    btn.setAttribute('aria-expanded', nav.classList.contains('open'));
    const [s1, s2, s3] = btn.querySelectorAll('span');
    if (nav.classList.contains('open')) {
      if (s1) s1.style.transform = 'rotate(45deg) translate(5px,5px)';
      if (s2) s2.style.opacity = '0';
      if (s3) s3.style.transform = 'rotate(-45deg) translate(5px,-5px)';
    } else {
      [s1,s2,s3].forEach(s => { if(s) { s.style.transform = ''; s.style.opacity = ''; } });
    }
  });
})();


/* ─── ДОБАВЛЕНИЕ В КОРЗИНУ (AJAX) ─── */

document.addEventListener('click', e => {
  const btn = e.target.closest('[data-cart-add]');
  if (!btn) return;

  e.preventDefault();
  const productId = btn.dataset.cartAdd;
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = `/cart/add/${productId}`;

  const csrf = document.querySelector('meta[name="csrf-token"]');
  if (csrf) {
    const inp = document.createElement('input');
    inp.type = 'hidden'; inp.name = 'csrf_token'; inp.value = csrf.content;
    form.appendChild(inp);
  }
  document.body.appendChild(form);

  fetch(form.action, {
    method: 'POST',
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
    body: new FormData(form),
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      // Обновляем счётчик корзины
      document.querySelectorAll('.action-badge').forEach(badge => {
        badge.textContent = data.count;
        badge.style.display = 'flex';
      });
      if (!document.querySelector('.action-badge')) {
        const cartLink = document.querySelector('a[href="/cart"]');
        if (cartLink) {
          const b = document.createElement('span');
          b.className = 'action-badge';
          b.textContent = data.count;
          cartLink.appendChild(b);
        }
      }
      showToast(`«${data.name}» добавлен в корзину`);

      // Анимация кнопки
      btn.classList.add('btn-added');
      const orig = btn.innerHTML;
      btn.innerHTML = '<i class="bi bi-check-lg"></i> Добавлено!';
      setTimeout(() => { btn.innerHTML = orig; btn.classList.remove('btn-added'); }, 2000);
    }
    document.body.removeChild(form);
  })
  .catch(() => { form.submit(); });
});


/* ─── ТОСТ-УВЕДОМЛЕНИЯ ─── */

function showToast(message, type = 'success') {
  const container = getOrCreateToastContainer();
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', 'alert');
  toast.setAttribute('aria-live', 'polite');
  toast.innerHTML = `
    <i class="bi bi-${type === 'success' ? 'check-circle-fill' : 'exclamation-circle-fill'}"></i>
    <span>${message}</span>
  `;
  container.appendChild(toast);

  // Появление
  requestAnimationFrame(() => toast.classList.add('show'));

  // Авто-скрытие через 3 секунды
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 350);
  }, 3000);
}

function getOrCreateToastContainer() {
  let c = document.getElementById('toast-container');
  if (!c) {
    c = document.createElement('div');
    c.id = 'toast-container';
    document.body.appendChild(c);
  }
  return c;
}


/* ─── ИЗМЕНЕНИЕ КОЛИЧЕСТВА В КОРЗИНЕ ─── */

document.addEventListener('click', e => {
  const btn = e.target.closest('.qty-btn');
  if (!btn) return;

  const input = btn.closest('.qty-control')?.querySelector('.qty-input');
  if (!input) return;

  let val = parseInt(input.value) || 1;
  if (btn.classList.contains('qty-plus'))  val = Math.min(val + 1, 99);
  if (btn.classList.contains('qty-minus')) val = Math.max(val - 1, 1);
  input.value = val;
});


/* ─── КОПИРОВАНИЕ ПРОМОКОДА ─── */

document.addEventListener('click', e => {
  const codeEl = e.target.closest('.promo-code');
  if (!codeEl) return;

  const code = codeEl.dataset.code || codeEl.textContent.trim();
  navigator.clipboard?.writeText(code).then(() => {
    showToast(`Промокод «${code}» скопирован!`);
  }).catch(() => {
    showToast(`Промокод: ${code}`);
  });
});


/* ─── РАЗМЕТКА FLASH-СООБЩЕНИЙ (авто-скрытие через 6 с) ─── */

(function autoHideFlash() {
  document.querySelectorAll('.flash').forEach(msg => {
    setTimeout(() => {
      msg.style.opacity = '0';
      msg.style.transform = 'translateY(-10px)';
      msg.style.transition = 'opacity .4s, transform .4s';
      setTimeout(() => msg.remove(), 400);
    }, 6000);
  });
})();


/* ─── ОТМЕТКА СООБЩЕНИЯ ПРОЧИТАННЫМ (AJAX) ─── */

document.addEventListener('click', e => {
  const btn = e.target.closest('[data-mark-read]');
  if (!btn) return;

  const msgId = btn.dataset.markRead;
  fetch(`/admin/messages/${msgId}/read`, { method: 'POST' })
    .then(r => r.json())
    .then(d => {
      if (d.success) {
        const row = btn.closest('tr') || btn.closest('.msg-row');
        if (row) row.classList.remove('unread');
        btn.remove();
      }
    });
});


/* ─── ПОДСВЕТКА АКТИВНОЙ ССЫЛКИ МЕНЮ ─── */

(function highlightActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.category-menu a').forEach(link => {
    try {
      const linkPath = new URL(link.href).pathname;
      if (path === linkPath || (path.startsWith(linkPath) && linkPath !== '/')) {
        link.classList.add('active');
      }
    } catch {}
  });
})();


/* ─── ПЛАВНАЯ ПРОКРУТКА ЯКОРЕЙ ─── */

document.addEventListener('click', e => {
  const a = e.target.closest('a[href^="#"]');
  if (!a) return;
  const target = document.querySelector(a.getAttribute('href'));
  if (target) {
    e.preventDefault();
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
});


/* ─── ТОСТЫ: CSS в <head> ─── */

(function injectToastStyles() {
  if (document.getElementById('toast-styles')) return;
  const style = document.createElement('style');
  style.id = 'toast-styles';
  style.textContent = `
    #toast-container {
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      gap: 8px;
      pointer-events: none;
    }
    .toast {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 20px;
      border-radius: 8px;
      background: #2D2D2D;
      color: #fff;
      font-size: .88rem;
      font-weight: 500;
      box-shadow: 0 6px 24px rgba(0,0,0,.25);
      transform: translateX(120%);
      opacity: 0;
      transition: transform .35s cubic-bezier(.4,0,.2,1), opacity .35s;
      max-width: 340px;
      pointer-events: auto;
    }
    .toast.show { transform: translateX(0); opacity: 1; }
    .toast-success { background: #2E7D32; }
    .toast-danger  { background: #C62828; }
    .toast i { font-size: 1.1rem; flex-shrink: 0; }
    @media (max-width: 480px) {
      #toast-container { bottom: 16px; right: 16px; left: 16px; }
      .toast { max-width: 100%; }
    }
  `;
  document.head.appendChild(style);
})();
