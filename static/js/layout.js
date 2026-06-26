// ============================
// GLOBAL LAYOUT CONTROLLER
// ============================

document.addEventListener("DOMContentLoaded", function () {

    const sidebar = document.querySelector(".sidebar");
    const menuBtn = document.getElementById("menuToggle");
    const collapseBtn = document.getElementById("collapseSidebar");
    const overlay = document.getElementById("sidebarOverlay");

    // ----------------------------
    // MOBILE SIDEBAR OPEN/CLOSE
    // ----------------------------
    if (menuBtn && sidebar && overlay) {
        menuBtn.addEventListener("click", () => {
            sidebar.classList.toggle("show");
            overlay.classList.toggle("show");
        });

        overlay.addEventListener("click", () => {
            sidebar.classList.remove("show");
            overlay.classList.remove("show");
        });
    }

    // ----------------------------
    // DESKTOP COLLAPSE SIDEBAR
    // ----------------------------
    if (collapseBtn && sidebar) {
        collapseBtn.addEventListener("click", () => {
            if (window.innerWidth > 768) {
                sidebar.classList.toggle("collapsed");
            }
        });
    }

    // ----------------------------
    // AUTO CLOSE SIDEBAR ON RESIZE
    // ----------------------------
    window.addEventListener("resize", () => {
        if (window.innerWidth > 768) {
            sidebar?.classList.remove("show");
            overlay?.classList.remove("show");
        }
    });

});