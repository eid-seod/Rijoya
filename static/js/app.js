(() => {
  const toggle = document.querySelector('[data-menu-toggle]');
  const menu = document.querySelector('[data-menu]');
  if (toggle && menu) toggle.addEventListener('click', () => menu.classList.toggle('is-open'));

  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
  window.rijoyaFetch = (url, options = {}) => fetch(url, {
    ...options,
    headers: { ...(options.headers || {}), ...(csrf ? { 'X-CSRFToken': csrf } : {}) },
  });

  document.querySelectorAll('input[type="number"]').forEach((input) => {
    input.addEventListener('change', () => {
      const min = Number(input.min || 0);
      const max = Number(input.max || 999);
      input.value = Math.min(max, Math.max(min, Number(input.value || min)));
    });
  });
})();
