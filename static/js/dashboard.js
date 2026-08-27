document.addEventListener("DOMContentLoaded", function () {
  const sidebar = document.querySelector(".app-sidebar");
  const overlay = document.querySelector(".sidebar-overlay");
  const toggleMobileBtn = document.getElementById("toggleSidebarMobile");
  const toggleDesktopBtn = document.getElementById("toggleSidebarDesktop");

  // Mobile drawer toggle
  if (toggleMobileBtn && sidebar && overlay) {
    toggleMobileBtn.addEventListener("click", function () {
      sidebar.classList.toggle("show-mobile");
      overlay.classList.toggle("active");
    });

    overlay.addEventListener("click", function () {
      sidebar.classList.remove("show-mobile");
      overlay.classList.remove("active");
    });
  }

  // Desktop sidebar collapse toggle
  if (toggleDesktopBtn) {
    toggleDesktopBtn.addEventListener("click", function () {
      document.body.classList.toggle("sidebar-collapsed");
      const isCollapsed = document.body.classList.contains("sidebar-collapsed");
      localStorage.setItem("physio_sidebar_collapsed", isCollapsed);
    });

    // Restore desktop state from localStorage
    if (localStorage.getItem("physio_sidebar_collapsed") === "true") {
      document.body.classList.add("sidebar-collapsed");
    }
  }

  // Auto-dismiss Django message alerts after 5s
  const alerts = document.querySelectorAll(".auto-dismiss-alert");
  alerts.forEach(function (alert) {
    setTimeout(function () {
      alert.style.transition = "opacity 0.5s ease";
      alert.style.opacity = "0";
      setTimeout(function () {
        alert.remove();
      }, 500);
    }, 5000);
  });
});

