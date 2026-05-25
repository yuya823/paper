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

    // Scroll the other panel to the highlighted block
    const targetPanel = sourcePanel === 'ja' ? 'en' : 'ja';
    const targetBlock = document.querySelector(`.panel--${targetPanel} [data-block-id="${blockId}"]`);
    if (targetBlock) {
      targetBlock.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  /** 文単位ホバー - 日本語の文にホバーで英語側の対応範囲をハイライト */
  highlightSentenceHover(blockId, sentenceIdx, totalSentences) {
    if (!this.enabled) return;
    this.clearHoverHighlights();
    this._hoverBlockId = blockId;

    // 英語パネルのテキストレイヤー内の全spanを取得
    const enPanel = document.querySelector('.panel--en');
    if (!enPanel) return;
    const textSpans = enPanel.querySelectorAll('.pdf-text-span');
    if (!textSpans.length) return;

    // 対応するブロックのsource-highlight要素から位置を特定
    const enBlock = enPanel.querySelector(`[data-block-id="${blockId}"]`);

    // ブロック位置情報を使って、その範囲内のテキストspanを検索
    if (enBlock) {
      const blockTop = parseFloat(enBlock.style.top);
      const blockLeft = parseFloat(enBlock.style.left);
      const blockWidth = parseFloat(enBlock.style.width);
      const blockHeight = parseFloat(enBlock.style.height);
      const blockBottom = blockTop + blockHeight;
      const blockRight = blockLeft + blockWidth;

      // ブロック内のspanを収集
      const spansInBlock = [];
      textSpans.forEach(span => {
        const spanTop = parseFloat(span.style.top);
        const spanLeft = parseFloat(span.style.left);
        if (spanTop >= blockTop - 2 && spanTop <= blockBottom + 2 &&
            spanLeft >= blockLeft - 5 && spanLeft <= blockRight + 5) {
          spansInBlock.push(span);
        }
      });

      // 文インデックスに基づいてspanの範囲を按分
      if (spansInBlock.length > 0) {
        const startIdx = Math.floor(spansInBlock.length * sentenceIdx / totalSentences);
        const endIdx = Math.floor(spansInBlock.length * (sentenceIdx + 1) / totalSentences);
        for (let i = startIdx; i < Math.max(endIdx, startIdx + 1) && i < spansInBlock.length; i++) {
          spansInBlock[i].classList.add('pdf-text-span--hover');
        }
        return;
      }
    }

    // フォールバック: ブロック位置がない場合、全spanの按分
    const startIdx = Math.floor(textSpans.length * sentenceIdx / totalSentences);
    const endIdx = Math.floor(textSpans.length * (sentenceIdx + 1) / totalSentences);
    for (let i = startIdx; i < Math.max(endIdx, startIdx + 1) && i < textSpans.length; i++) {
      textSpans[i].classList.add('pdf-text-span--hover');
    }
  }

  clearHoverHighlights() {
    document.querySelectorAll('.pdf-text-span--hover').forEach(el =>
      el.classList.remove('pdf-text-span--hover')
    );
    document.querySelectorAll('.source-sentence-hover').forEach(el => el.remove());
    this._hoverBlockId = null;
  }

  clearHighlights() {
    document.querySelectorAll('.translation-block--highlighted').forEach(el => el.classList.remove('translation-block--highlighted'));
    this._activeBlockId = null;
  }

  setEnabled(enabled) { this.enabled = enabled; }
}

