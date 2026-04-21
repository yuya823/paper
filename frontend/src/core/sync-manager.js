/** Sync Manager - Synchronized scrolling and zooming between panels */
export class SyncManager {
  constructor() {
    this.syncScroll = true;
    this.syncZoom = true;
    this.panels = { ja: null, en: null };
    this._scrolling = false;
    this._handleScroll = {};
  }

  init(jaPanel, enPanel) {
    this.panels.ja = jaPanel;
    this.panels.en = enPanel;
    this._attachScrollListeners();
  }

  _attachScrollListeners() {
    ['ja', 'en'].forEach(key => {
      const otherKey = key === 'ja' ? 'en' : 'ja';
      this._handleScroll[key] = () => {
        if (!this.syncScroll || this._scrolling) return;
        this._scrolling = true;

        const src = this.panels[key];
        const tgt = this.panels[otherKey];
        if (!src || !tgt) { this._scrolling = false; return; }

        const ratio = src.scrollTop / (src.scrollHeight - src.clientHeight || 1);
        tgt.scrollTop = ratio * (tgt.scrollHeight - tgt.clientHeight);

        requestAnimationFrame(() => { this._scrolling = false; });
      };
      this.panels[key]?.addEventListener('scroll', this._handleScroll[key], { passive: true });
    });
  }

  setSyncScroll(enabled) { this.syncScroll = enabled; }
  setSyncZoom(enabled) { this.syncZoom = enabled; }

  scrollToPage(pageNum) {
    ['ja', 'en'].forEach(key => {
      const panel = this.panels[key];
      if (!panel) return;
      const pageEl = panel.querySelector(`[data-page="${pageNum}"]`);
      if (pageEl) pageEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  destroy() {
    ['ja', 'en'].forEach(key => {
      if (this.panels[key] && this._handleScroll[key]) {
        this.panels[key].removeEventListener('scroll', this._handleScroll[key]);
      }
    });
  }
}
