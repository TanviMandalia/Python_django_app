/**
 * GLOBAL LAYOUT CONTROLLER - PRODUCTION GRADE
 * Supports responsive desktop collapse, mobile off-canvas drawer,
 * overlay backdrop, keyboard (ESC), modal/dropdown handling, and half-screen resizing.
 */

(function () {
  "use strict";

  // Dynamic selector helpers
  function getSidebar() {
    return document.querySelector(".sidebar, aside.sidebar, #adminSidebar, #clientSidebar, #staffSidebar, #superAdminSidebar");
  }

  function getOverlay() {
    let overlay = document.querySelector("#sidebarOverlay, .sidebar-overlay, .overlay");
    if (!overlay && getSidebar()) {
      overlay = document.createElement("div");
      overlay.id = "sidebarOverlay";
      overlay.className = "sidebar-overlay";
      document.body.appendChild(overlay);
    }
    return overlay;
  }

  function getContentWrappers() {
    return document.querySelectorAll(".main, .main-wrapper, .app-main, .staff-main-panel, .main-content, .client-main, .client-main-wrapper, .sa-main-wrapper");
  }

  function updateAriaStates(isOpen) {
    const menuButtons = document.querySelectorAll(
      "#menuToggle, #mobileMenuBtn, .menu-toggle, .menu-btn, .sidebar-toggle-btn, .hamburger:not(#publicNavToggle), .mobile-menu-btn, .sidebar-toggle, [data-toggle='sidebar'], [data-action='toggle-sidebar']"
    );
    menuButtons.forEach((btn) => {
      btn.setAttribute("aria-expanded", isOpen ? "true" : "false");
      const label = isOpen ? "Collapse sidebar navigation" : "Expand sidebar navigation";
      btn.setAttribute("aria-label", label);
      btn.setAttribute("title", label);
    });
  }

  // ── DESKTOP COLLAPSE ───────────────────────────────────────
  function toggleDesktopCollapse() {
    const sidebar = getSidebar();
    if (!sidebar) return;

    const isCollapsed = sidebar.classList.toggle("collapsed");
    document.body.classList.toggle("sidebar-collapsed", isCollapsed);

    getContentWrappers().forEach((wrapper) => {
      wrapper.classList.toggle("sidebar-collapsed", isCollapsed);
    });

    updateAriaStates(!isCollapsed);

    try {
      localStorage.setItem("sidebar_collapsed", isCollapsed ? "true" : "false");
    } catch (e) {}
  }

  // ── MOBILE / HALF-SCREEN OFF-CANVAS DRAWER ─────────────────
  function openMobileDrawer() {
    const sidebar = getSidebar();
    const overlay = getOverlay();
    if (!sidebar) return;

    sidebar.classList.add("show", "active", "open");
    if (overlay) overlay.classList.add("show", "active");
    document.body.classList.add("sidebar-open");
    updateAriaStates(true);
  }

  function closeMobileDrawer() {
    const sidebar = getSidebar();
    const overlay = getOverlay();
    if (sidebar) sidebar.classList.remove("show", "active", "open");
    if (overlay) overlay.classList.remove("show", "active");
    document.body.classList.remove("sidebar-open");
    updateAriaStates(false);
  }

  function toggleMobileDrawer() {
    const sidebar = getSidebar();
    if (!sidebar) return;

    if (
      sidebar.classList.contains("show") ||
      sidebar.classList.contains("active") ||
      sidebar.classList.contains("open")
    ) {
      closeMobileDrawer();
    } else {
      openMobileDrawer();
    }
  }

  // ── GLOBAL EXPORTS (Available immediately) ──────────────────
  window.toggleSidebar = function (e) {
    const sidebar = getSidebar();
    if (!sidebar) return;
    if (e && e.preventDefault) e.preventDefault();
    if (e && e.stopPropagation) e.stopPropagation();

    if (window.innerWidth < 992) {
      toggleMobileDrawer();
    } else {
      toggleDesktopCollapse();
    }
  };

  window.closeSidebar = function (e) {
    if (e && e.preventDefault) e.preventDefault();
    closeMobileDrawer();
  };

  window.openSidebar = function (e) {
    if (e && e.preventDefault) e.preventDefault();
    if (window.innerWidth < 992) {
      openMobileDrawer();
    } else {
      const sidebar = getSidebar();
      if (sidebar && sidebar.classList.contains("collapsed")) {
        toggleDesktopCollapse();
      }
    }
  };

  // ── INITIALIZATION ON DOM READY ─────────────────────────────
  function initLayout() {
    const sidebar = getSidebar();
    const overlay = getOverlay();

    // 1. Restore desktop collapse preference
    try {
      const savedCollapseState = localStorage.getItem("sidebar_collapsed");
      if (savedCollapseState === "true" && window.innerWidth >= 992 && sidebar) {
        sidebar.classList.add("collapsed");
        document.body.classList.add("sidebar-collapsed");
        getContentWrappers().forEach((wrapper) => wrapper.classList.add("sidebar-collapsed"));
      }
    } catch (e) {}

    // 2. Attach click handlers to all toggle buttons
    const menuButtons = document.querySelectorAll(
      "#menuToggle, #mobileMenuBtn, .menu-toggle, .menu-btn, .sidebar-toggle-btn, .hamburger:not(#publicNavToggle), .mobile-menu-btn, .sidebar-toggle, [data-toggle='sidebar'], [data-action='toggle-sidebar']"
    );
    menuButtons.forEach((btn) => {
      btn.removeEventListener("click", window.toggleSidebar);
      btn.addEventListener("click", window.toggleSidebar);
    });

    // 3. Attach click handlers to close buttons
    const closeButtons = document.querySelectorAll(
      "#closeSidebar, .sidebar-close-btn, [data-close='sidebar']"
    );
    closeButtons.forEach((btn) => {
      btn.removeEventListener("click", window.closeSidebar);
      btn.addEventListener("click", window.closeSidebar);
    });

    // 4. Attach click handler to overlay
    if (overlay) {
      overlay.removeEventListener("click", window.closeSidebar);
      overlay.addEventListener("click", window.closeSidebar);
    }

    // 5. Navigation item click closes mobile drawer
    if (sidebar) {
      const navLinks = sidebar.querySelectorAll(".nav-item, nav a");
      navLinks.forEach((link) => {
        link.addEventListener("click", function () {
          if (window.innerWidth < 992) {
            closeMobileDrawer();
          }
        });
      });
    }

    // 5b. Outside click closes mobile drawer
    document.addEventListener("click", function (e) {
      if (window.innerWidth < 992) {
        const s = getSidebar();
        if (s && (s.classList.contains("show") || s.classList.contains("active") || s.classList.contains("open"))) {
          const isTrigger = e.target.closest(
            "#menuToggle, #mobileMenuBtn, .menu-toggle, .menu-btn, .sidebar-toggle-btn, .hamburger:not(#publicNavToggle), .mobile-menu-btn, .sidebar-toggle, [data-toggle='sidebar'], [data-action='toggle-sidebar']"
          );
          if (!s.contains(e.target) && !isTrigger) {
            closeMobileDrawer();
          }
        }
      }
    });

    // 6. Escape key handler
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" || e.keyCode === 27) {
        closeMobileDrawer();
        document.querySelectorAll(".modal.show, .modal.active, .modal-backdrop.show").forEach((el) => {
          el.classList.remove("show", "active");
          if (el.style.display === "flex" || el.style.display === "block") {
            el.style.display = "none";
          }
        });
        document.querySelectorAll(".dropdown.show, .dropdown-menu.show").forEach((el) => el.classList.remove("show"));
      }
    });

    // 7. Window resize handler (Smooth transition between full-screen, half-screen, and mobile)
    let resizeTimer;
    window.addEventListener("resize", function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        const sidebar = getSidebar();
        if (window.innerWidth >= 992) {
          closeMobileDrawer();
          try {
            const isCol = localStorage.getItem("sidebar_collapsed") === "true";
            if (sidebar) sidebar.classList.toggle("collapsed", isCol);
            document.body.classList.toggle("sidebar-collapsed", isCol);
            getContentWrappers().forEach((w) => w.classList.toggle("sidebar-collapsed", isCol));
          } catch (e) {}
        } else {
          if (sidebar) sidebar.classList.remove("collapsed");
          document.body.classList.remove("sidebar-collapsed");
          getContentWrappers().forEach((w) => w.classList.remove("sidebar-collapsed"));
        }
      }, 50);
    });

    // 8. Auto-dismiss flash messages after 5 seconds
    document.querySelectorAll(".admin-alert, .alert-dismissible, .toast-alert").forEach((alert) => {
      setTimeout(() => {
        alert.style.transition = "opacity 0.4s ease, transform 0.4s ease";
        alert.style.opacity = "0";
        alert.style.transform = "translateY(-6px)";
        setTimeout(() => alert.remove(), 400);
      }, 5000);
    });
  }

  // ── CSRF PROTECTION & RESYNCHRONIZATION (PRODUCTION GRADE) ───────────────
  function getCsrfCookie() {
    if (!document.cookie) return null;
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const c = cookies[i].trim();
      if (c.indexOf("csrftoken=") === 0) {
        return decodeURIComponent(c.substring("csrftoken=".length));
      }
    }
    return null;
  }
  window.getCsrfToken = getCsrfCookie;

  // Intercept form submissions on document level (capture phase)
  // Ensures that if the CSRF token was rotated by login in another tab or session timeout,
  // the submitted form dynamically adopts the current valid cookie token.
  document.addEventListener("submit", function (e) {
    const form = e.target;
    if (form && form.tagName === "FORM" && form.method && form.method.toUpperCase() === "POST") {
      const csrfInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
      const cookieToken = getCsrfCookie();
      if (csrfInput && cookieToken && csrfInput.value !== cookieToken) {
        csrfInput.value = cookieToken;
      }
    }
  }, true);

  // Synchronize token when page is restored from bfcache (Back/Forward navigation)
  window.addEventListener("pageshow", function () {
    const cookieToken = getCsrfCookie();
    if (cookieToken) {
      document.querySelectorAll('input[name="csrfmiddlewaretoken"]').forEach(function (input) {
        input.value = cookieToken;
      });
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initLayout);
  } else {
    initLayout();
  }
})();