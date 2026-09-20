document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".flash").forEach((message) => {
    window.setTimeout(() => {
      message.style.opacity = "0";
      message.style.transition = "opacity .3s ease";
      window.setTimeout(() => message.remove(), 300);
    }, 4500);
  });
});

document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});
