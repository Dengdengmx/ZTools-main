<template>
  <div class="mtools-setting-panel about-panel">
    <h2>ℹ️ 关于 Mtools</h2>
    <div class="about-card">
      <div class="logo">🧬</div>
      <h1 class="title">Mtools BioEngine</h1>
      <div class="version">Version: 1.0.0 (Local Stealth Edition)</div>
      
      <div class="tech-stack">
        <span class="tag">Electron</span>
        <span class="tag">Vue 3</span>
        <span class="tag">FastAPI</span>
        <span class="tag">Python 3</span>
      </div>
      
      <p class="copyright">
        双轨制科研算力工作站。<br>
        前端极致交互，后端无限算力。
      </p>
    </div>
  </div>
</template>

<style scoped>
.mtools-setting-panel { padding: 20px; height: 100%; display: flex; flex-direction: column; }
h2 { color: #cdd6f4; margin-top: 0; border-bottom: 1px solid #313244; padding-bottom: 15px; }
.about-card { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
.logo { font-size: 80px; margin-bottom: 10px; filter: drop-shadow(0 0 20px rgba(137, 180, 250, 0.4)); }
.title { color: #89b4fa; font-size: 28px; margin: 0 0 10px 0; letter-spacing: 1px; }
.version { color: #a6e3a1; font-family: monospace; background: #181825; padding: 6px 15px; border-radius: 20px; border: 1px solid #313244; margin-bottom: 30px; }
.tech-stack { display: flex; gap: 10px; justify-content: center; margin-bottom: 30px; }
.tag { background: #1e1e2e; color: #bac2de; padding: 5px 12px; border-radius: 6px; font-size: 12px; border: 1px solid #45475a; }
.copyright { color: #6c7086; font-size: 14px; line-height: 1.8; }
</style>