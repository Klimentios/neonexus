/* Stable portraits from a single locally served 4×4 image atlas. */
(function () {
  const portraits = {
    user: 15, claude: 1, codex: 2, gemini: 3,
    antigravity: 4, kimi: 5, qwen: 6, kilo: 7,
    codebuddy: 8, copilot: 9,
    claudechat: 11, gptchat: 12, geminichat: 13,
    'claude-chat': 11, 'gpt-chat': 12, 'gemini-chat': 13,
  };
  // Gemini gets its own sparkle mark instead of a portrait.
  const geminiKeys = new Set(['gemini', 'geminichat', 'gemini-chat']);
  const geminiSvg = '<svg class="agent-face" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><defs><linearGradient id="gemini-mark" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#1c7df2"/><stop offset=".55" stop-color="#7a6cf0"/><stop offset="1" stop-color="#e36fa6"/></linearGradient></defs><rect width="100" height="100" fill="#11131c"/><path fill="url(#gemini-mark)" d="M50 14C52 34 66 48 86 50C66 52 52 66 50 86C48 66 34 52 14 50C34 48 48 34 50 14Z"/></svg>';
  function faceSvg(name) {
    const key = String(name || '').toLowerCase().trim().replace(/\s+/g, '-').replace(/-\d+$/, '');
    if (geminiKeys.has(key)) return geminiSvg;
    const index = portraits[key] ?? 14;
    const x = -(index % 4) * 100;
    const y = -Math.floor(index / 4) * 100;
    return `<svg class="agent-face" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><image href="/static/agent-portraits.webp" x="${x}" y="${y}" width="400" height="400" preserveAspectRatio="none"/></svg>`;
  }
  window.agentFaceSvg = faceSvg;
})();
