/**
 * ==============================================================================
 * Cloudflare Worker: Zero-Render-Screen Edge Proxy for PhysioRehab Clinic SaaS
 * ==============================================================================
 * Purpose:
 * Intercepts Render's free-tier "SERVICE WAKING UP" page before it reaches visitors.
 * Streams the luxury, branded Dr. Dhvani Patalia Physio Rehab loading screen instead.
 * 
 * Deployment:
 * 1. Create a free Cloudflare Worker at https://dash.cloudflare.com.
 * 2. Paste this file into the Worker editor.
 * 3. Set the BACKEND_ORIGIN environment variable or update the fallback below.
 * 4. Route your custom domain (e.g., clinic.example.com/*) to this Worker.
 * ==============================================================================
 */

const BACKEND_ORIGIN = "https://physio-rehab-app.onrender.com";

export default {
  async fetch(request, env) {
    const origin = env.BACKEND_ORIGIN || BACKEND_ORIGIN;
    const url = new URL(request.url);
    const targetUrl = new URL(url.pathname + url.search, origin);

    // Pass non-GET requests directly to origin (POST, PUT, DELETE, etc.)
    if (request.method !== "GET" && request.method !== "HEAD") {
      return fetch(targetUrl.toString(), request);
    }

    try {
      // Forward the request to Render with a 4-second timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 4000);

      const response = await fetch(targetUrl.toString(), {
        method: request.method,
        headers: request.headers,
        redirect: "manual",
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      // Inspect if Render returned a cold-start waking up response
      // Render free tier sends 502/503 or HTML containing "Service Waking Up"
      const status = response.status;
      const contentType = response.headers.get("content-type") || "";

      if (status === 502 || status === 503 || status === 504) {
        return serveBrandedLoader(targetUrl.toString(), url.pathname);
      }

      if (contentType.includes("text/html") && status === 200) {
        // Peek at the beginning of the body to see if it's Render's wake-up page
        const text = await response.clone().text();
        if (text.includes("SERVICE WAKING UP") || text.includes("Your free instance is spinning up") || text.includes("APPLICATION LOADING")) {
          return serveBrandedLoader(targetUrl.toString(), url.pathname);
        }
      }

      // Normal response from Django
      return response;

    } catch (err) {
      // If Render timed out or container is unreachable, stream the branded loader
      return serveBrandedLoader(targetUrl.toString(), url.pathname);
    }
  }
};

/**
 * Generates the self-contained luxury branded loading page
 */
function serveBrandedLoader(backendUrl, requestedPath) {
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Dr. Dhvani Patalia | Physio Rehab Clinic</title>
  <style>
    :root {
      --cp-gold: #F5C518;
      --cp-gold-dark: #dfb00d;
      --cp-gold-glow: rgba(245, 197, 24, 0.35);
      --cp-dark-bg: #12151b;
      --cp-text-main: #f8fafc;
      --cp-text-muted: #94a3b8;
      --cp-border: rgba(245, 197, 24, 0.22);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body {
      width: 100%; height: 100%; height: 100dvh; overflow: hidden;
      background-color: var(--cp-dark-bg);
      background-image: radial-gradient(circle at 50% 38%, rgba(36, 43, 58, 0.95) 0%, rgba(18, 21, 27, 0.98) 60%, rgba(10, 12, 16, 1) 100%);
      color: var(--cp-text-main);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex; align-items: center; justify-content: center; text-align: center;
    }
    #wrap { max-width: 440px; width: 90%; padding: 24px; transition: opacity 0.35s ease; }
    #wrap.fade-out { opacity: 0; }
    .emblem { position: relative; width: 92px; height: 92px; margin: 0 auto 22px; display: flex; align-items: center; justify-content: center; }
    .ring {
      position: absolute; inset: 0; border-radius: 50%; border: 2.5px solid transparent;
      border-top-color: var(--cp-gold); border-right-color: rgba(245, 197, 24, 0.4);
      filter: drop-shadow(0 0 6px var(--cp-gold-glow));
      animation: spin 1.25s cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite;
    }
    .badge {
      width: 66px; height: 66px; border-radius: 50%;
      background: linear-gradient(145deg, #1f2533 0%, #151922 100%);
      border: 1.5px solid var(--cp-border);
      display: flex; align-items: center; justify-content: center;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.45);
    }
    .svg-icon {
      width: 34px; height: 34px; fill: none; stroke: var(--cp-gold); stroke-width: 2;
      stroke-linecap: round; stroke-linejoin: round;
      animation: pulse 2.2s ease-in-out infinite;
    }
    .title { font-size: 1.2rem; font-weight: 700; color: #fff; margin-bottom: 4px; }
    .subtitle { font-size: 0.8rem; font-weight: 600; color: var(--cp-gold); text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 18px; }
    .status-row { display: inline-flex; align-items: center; gap: 8px; margin-bottom: 14px; }
    .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--cp-gold); box-shadow: 0 0 8px var(--cp-gold); animation: blink 1.4s infinite; }
    .dot.ready { background: #10b981; box-shadow: 0 0 8px #10b981; animation: none; }
    .status-text { font-size: 0.86rem; color: var(--cp-text-muted); font-weight: 500; }
    .progress-track { width: 140px; height: 3px; background: rgba(255, 255, 255, 0.08); border-radius: 99px; overflow: hidden; position: relative; margin: 0 auto; }
    .progress-bar { position: absolute; inset: 0; width: 45%; border-radius: 99px; background: linear-gradient(90deg, transparent 0%, var(--cp-gold) 50%, transparent 100%); animation: shimmer 1.5s infinite; }
    .btn-retry { margin-top: 18px; display: none; padding: 7px 16px; background: var(--cp-gold); color: #12151b; font-weight: 600; border: none; border-radius: 6px; cursor: pointer; font-size: 0.82rem; }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.06); } }
    @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
    @keyframes shimmer { 0% { transform: translateX(-120%); } 100% { transform: translateX(250%); } }
    @media (prefers-reduced-motion: reduce) { .ring, .svg-icon, .dot, .progress-bar { animation: none !important; } }
  </style>
</head>
<body>
  <div id="wrap" role="status" aria-live="polite">
    <div class="emblem">
      <div class="ring" aria-hidden="true"></div>
      <div class="badge">
        <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <circle cx="12" cy="4" r="2" />
          <path d="M12 7v3" /><path d="M9 10h6" />
          <circle cx="12" cy="13" r="1.5" /><path d="M7 13c1-2 4-2 5-2s4 0 5 2" />
          <circle cx="12" cy="18" r="1.5" /><path d="M8 18c1-1.5 3-1.5 4-1.5s3 0 4 1.5" />
          <path d="M12 19.5v2" />
        </svg>
      </div>
    </div>
    <h1 class="title">Dr. Dhvani Patalia</h1>
    <div class="subtitle">Physio Rehab &amp; Sports Medicine</div>
    <div class="status-row">
      <span class="dot" id="dot" aria-hidden="true"></span>
      <p class="status-text" id="status">Preparing your clinic workspace&hellip;</p>
    </div>
    <div class="progress-track" aria-hidden="true"><div class="progress-bar"></div></div>
    <button type="button" class="btn-retry" id="btn-retry" onclick="window.location.reload()">Retry Now</button>
  </div>
  <script>
    (function() {
      var isReady = false;
      var dot = document.getElementById('dot');
      var status = document.getElementById('status');
      var btn = document.getElementById('btn-retry');
      var wrap = document.getElementById('wrap');
      var elapsed = 0;

      var timer = setInterval(function() {
        elapsed += 2.5;
        if (elapsed > 45 && btn) btn.style.display = 'inline-block';
        if (elapsed > 12 && status) status.textContent = 'Waking up clinical database\u2026';

        fetch('/healthz', { cache: 'no-store' })
          .then(function(res) { return res.status === 200 ? res.json() : null; })
          .then(function(data) {
            if (data && data.status === 'ok') {
              clearInterval(timer);
              if (dot) dot.classList.add('ready');
              if (status) status.textContent = 'Clinic ready! Loading\u2026';
              setTimeout(function() {
                if (wrap) wrap.classList.add('fade-out');
                setTimeout(function() { window.location.reload(); }, 300);
              }, 200);
            }
          })
          .catch(function() {});
      }, 2500);
    })();
  </script>
</body>
</html>`;

  return new Response(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-cache, no-store, must-revalidate"
    }
  });
}
