/** Highlight Manager - Cross-panel block highlighting */
export class HighlightManager {
  constructor() {
    this.enabled = true;
    this._activeBlockId = null;
  }

  highlightBlock(blockId, sourcePanel) {
    if (!this.enabled) return;
    this.clearHighlights();
    this._activeBlockId = blockId;

    // Highlight in Japanese panel
    const jaBlock = document.querySelector(`.panel--ja [data-block-id="${blockId}"]`);
    if (jaBlock) jaBlock.classList.add('translation-block--highlighted');

    // Highlight in English panel
    const enBlock = document.querySelector(`.panel--en [data-block-id="${blockId}"]`);
    if (enBlock) enBlock.classList.add('source-highlight--active');

    // Scroll the other panel to the highlighted block
    const targetPanel = sourcePanel === 'ja' ? 'en' : 'ja';
    const targetBlock = document.querySelector(`.panel--${targetPanel} [data-block-id="${blockId}"]`);
    if (targetBlock) {
      targetBlock.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  clearHighlights() {
    document.querySelectorAll('.translation-block--highlighted').forEach(el => el.classList.remove('translation-block--highlighted'));
    document.querySelectorAll('.source-highlight--active').forEach(el => el.classList.remove('source-highlight--active'));
    this._activeBlockId = null;
  }

  setEnabled(enabled) { this.enabled = enabled; }
}
