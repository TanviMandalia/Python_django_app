/**
 * CLINIC PRELOADER & ASYNC COMPONENT LOADER CONTROLLER
 * Dr. Dhvani Patalia Physio Rehab - Enterprise Frontend Module
 *
 * Provides:
 * 1. Global Preloader Coordination (lifecycle events, fallback triggers, bfcache)
 * 2. Asynchronous Component Loading States (spinners, skeletons, error handling, retry actions)
 * 3. Safe Service Worker registration (caching critical assets without touching private patient data)
 */

(function (window, document) {
  "use strict";

  const ClinicPreloader = {
    version: "1.0.0",

    /**
     * Dismiss the global full-screen preloader manually if needed.
     * @param {boolean} immediate - If true, dismisses immediately without animation
     */
    dismiss: function (immediate) {
      if (typeof window.dismissClinicPreloader === "function") {
        window.dismissClinicPreloader(immediate);
      }
    },

    /**
     * Attach a branded localized loading indicator inside a specific component container
     * (e.g. for charts, analytics tables, asynchronous data fetches).
     * @param {HTMLElement|string} container - Target DOM element or CSS selector
     * @param {Object} options - Configuration options { message: string, minHeight: string }
     */
    showComponentLoader: function (container, options) {
      const el = typeof container === "string" ? document.querySelector(container) : container;
      if (!el) return null;

      const opts = Object.assign(
        {
          message: "Loading data...",
          minHeight: "180px",
          id: "comp-loader-" + Math.random().toString(36).substring(2, 9),
        },
        options || {}
      );

      // Prevent duplicate loaders
      const existing = el.querySelector(".clinic-component-loader");
      if (existing) return existing;

      // Ensure container is positioned
      const prevPosition = window.getComputedStyle(el).position;
      if (prevPosition === "static") {
        el.style.position = "relative";
      }

      const loaderDiv = document.createElement("div");
      loaderDiv.className = "clinic-component-loader";
      loaderDiv.id = opts.id;
      loaderDiv.setAttribute("role", "status");
      loaderDiv.setAttribute("aria-live", "polite");
      loaderDiv.style.cssText = `
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: ${opts.minHeight};
        padding: 24px;
        background: rgba(255, 255, 255, 0.88);
        backdrop-filter: blur(4px);
        border-radius: 12px;
        z-index: 20;
        width: 100%;
        box-sizing: border-box;
      `;

      loaderDiv.innerHTML = `
        <div style="position: relative; width: 44px; height: 44px; margin-bottom: 12px;">
          <div style="position: absolute; inset: 0; border-radius: 50%; border: 2.5px solid rgba(245, 197, 24, 0.2); border-top-color: #F5C518; animation: cp-spin 1s linear infinite;"></div>
        </div>
        <p style="margin: 0; font-size: 0.86rem; font-weight: 600; color: #2C2C2C;">${opts.message}</p>
      `;

      el.appendChild(loaderDiv);
      return loaderDiv;
    },

    /**
     * Remove a localized component loader.
     * @param {HTMLElement|string} container - Target container
     */
    hideComponentLoader: function (container) {
      const el = typeof container === "string" ? document.querySelector(container) : container;
      if (!el) return;

      const loader = el.querySelector(".clinic-component-loader");
      if (loader) {
        loader.style.opacity = "0";
        loader.style.transition = "opacity 0.25s ease";
        setTimeout(() => {
          if (loader.parentNode) loader.parentNode.removeChild(loader);
        }, 260);
      }
    },

    /**
     * Show an accessible, actionable error state with a Retry button inside a component.
     * @param {HTMLElement|string} container - Target container
     * @param {Object} options - { message: string, onRetry: Function }
     */
    showComponentError: function (container, options) {
      const el = typeof container === "string" ? document.querySelector(container) : container;
      if (!el) return;

      this.hideComponentLoader(el);

      const opts = Object.assign(
        {
          message: "Unable to load content. Please check your connection.",
          onRetry: null,
          minHeight: "160px",
        },
        options || {}
      );

      const errorDiv = document.createElement("div");
      errorDiv.className = "clinic-component-error-state";
      errorDiv.setAttribute("role", "alert");
      errorDiv.style.cssText = `
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        min-height: ${opts.minHeight};
        padding: 24px;
        background: #fff8f8;
        border: 1px dashed #fca5a5;
        border-radius: 12px;
        margin: 12px 0;
      `;

      const msg = document.createElement("p");
      msg.style.cssText = "margin: 0 0 12px 0; font-size: 0.88rem; color: #b91c1c; font-weight: 500;";
      msg.textContent = opts.message;
      errorDiv.appendChild(msg);

      if (typeof opts.onRetry === "function") {
        const retryBtn = document.createElement("button");
        retryBtn.type = "button";
        retryBtn.className = "btn btn-sm";
        retryBtn.style.cssText = `
          background: #F5C518;
          color: #2C2C2C;
          border: none;
          font-weight: 600;
          font-size: 0.82rem;
          padding: 6px 16px;
          border-radius: 6px;
          cursor: pointer;
        `;
        retryBtn.innerHTML = '<i class="fas fa-redo-alt" style="margin-right: 6px;"></i> Retry';
        retryBtn.addEventListener("click", function () {
          errorDiv.remove();
          opts.onRetry();
        });
        errorDiv.appendChild(retryBtn);
      }

      el.appendChild(errorDiv);
    },

    /**
     * Register a lightweight progressive Service Worker to cache static preloader assets
     * and critical styles for instant subsequent visits (handling Render cold start shell).
     * Strictly avoids caching private user data, cookies, or dynamic views.
     */
    registerServiceWorker: function () {
      if ("serviceWorker" in navigator && window.location.protocol === "https:") {
        window.addEventListener("load", function () {
          navigator.serviceWorker
            .register("/static/sw.js", { scope: "/" })
            .then(function (reg) {
              // Service Worker successfully registered for static asset caching
            })
            .catch(function () {
              // Silently ignore if worker registration fails
            });
        });
      }
    },
  };

  // Expose to window
  window.ClinicPreloader = ClinicPreloader;

  // Initialize service worker if enabled
  try {
    ClinicPreloader.registerServiceWorker();
  } catch (e) {}
})(window, document);
