/* Progressive enhancements. Forms and navigation also work without JavaScript. */
(() => {
  "use strict";
  const body = document.body;
  const menu = document.querySelector(".menu-toggle");
  const sidebar = document.querySelector(".app-sidebar");
  const backdrop = document.querySelector(".nav-backdrop");
  const mobile = window.matchMedia("(max-width: 64rem)");
  if (menu && sidebar && backdrop) {
    body.classList.add("nav-enhanced");
    menu.hidden = false;
    const setMenu = (open, restoreFocus = false) => {
      body.classList.toggle("nav-open", open);
      menu.setAttribute("aria-expanded", String(open));
      menu.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
      backdrop.hidden = !open;
      sidebar.inert = mobile.matches && !open;
      if (open) sidebar.querySelector("a")?.focus();
      if (restoreFocus) menu.focus();
    };
    menu.addEventListener("click", () => setMenu(!body.classList.contains("nav-open")));
    backdrop.addEventListener("click", () => setMenu(false, true));
    document.addEventListener("keydown", (event) => {
      if (!body.classList.contains("nav-open")) return;
      if (event.key === "Escape") setMenu(false, true);
      if (event.key === "Tab") {
        const controls = [...sidebar.querySelectorAll("a[href], button")];
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault(); last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first.focus();
        }
      }
    });
    mobile.addEventListener("change", () => setMenu(false));
    setMenu(false);
  }
  document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    const input = document.getElementById(button.getAttribute("aria-controls"));
    if (!input) return;
    button.hidden = false;
    button.addEventListener("click", () => {
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      button.textContent = show ? "Ocultar" : "Mostrar";
      button.setAttribute("aria-pressed", String(show));
    });
  });
})();
