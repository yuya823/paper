/** Highlight Manager - Cross-panel block highlighting */
export class HighlightManager {
  constructor() {
    this.enabled = true;
    this._activeBlockId = null;
    this._hoverBlockId = null;
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

  /** 文単位ホバー - 日本語の文にホバーで英語側の対応範囲だけにハイライト */
  highlightSentenceHover(blockId, sentenceIdx, totalSentences) {
    if (!this.enabled) return;
    this.clearHoverHighlights();
    this._hoverBlockId = blockId;

    const enBlock = document.querySelector(`.panel--en [data-block-id="${blockId}"]`);
    if (!enBlock || !enBlock.parentElement) return;

    // ブロックの位置とサイズを取得
    const top = parseFloat(enBlock.style.top);
    const left = parseFloat(enBlock.style.left);
    const width = parseFloat(enBlock.style.width);
    const height = parseFloat(enBlock.style.height);

    // 文の位置を按分計算
    const sentenceH = height / totalSentences;
    const sentenceTop = top + sentenceIdx * sentenceH;

    // 一時的なハイライト要素を生成
    const el = document.createElement('div');
    el.className = 'source-sentence-hover';
    el.style.left = left + 'px';
    el.style.top = sentenceTop + 'px';
    el.style.width = width + 'px';
    el.style.height = sentenceH + 'px';

    enBlock.parentElement.appendChild(el);
  }

  clearHoverHighlights() {
    document.querySelectorAll('.source-sentence-hover').forEach(el => el.remove());
    this._hoverBlockId = null;
  }

  clearHighlights() {
    document.querySelectorAll('.translation-block--highlighted').forEach(el => el.classList.remove('translation-block--highlighted'));
    document.querySelectorAll('.source-highlight--active').forEach(el => el.classList.remove('source-highlight--active'));
    this._activeBlockId = null;
  }

  setEnabled(enabled) { this.enabled = enabled; }
}
