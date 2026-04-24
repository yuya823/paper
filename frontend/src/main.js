/**
 * Paper Translator - Main Application Entry Point
 * 英語論文PDF対訳ビューア
 */
import './index.css';
import { apiClient } from './core/api-client.js';
import { PdfRenderer } from './core/pdf-renderer.js';
import { SyncManager } from './core/sync-manager.js';
import { HighlightManager } from './core/highlight.js';
import { SearchEngine } from './core/search.js';
import { icons } from './utils/icons.js';
import { IS_LOCAL_DEV, getCurrentUser, signIn, signUp, signInWithGoogle, signOut, onAuthStateChange } from './core/supabase-auth.js';

class App {
  constructor() {
    this.currentDoc = null;
    this.currentPage = 1;
    this.totalPages = 0;
    this.blocks = {};          // { pageNum: [blocks] }
    this.jaRenderer = null;
    this.enRenderer = null;
    this.syncManager = new SyncManager();
    this.highlightManager = new HighlightManager();
    this.searchEngine = new SearchEngine(apiClient);
    this.showThumbnails = false;
    this.showSearch = false;
    this.scale = 1.2;
    this.screen = 'loading';   // 'loading' | 'login' | 'upload' | 'viewer'
    this.user = null;
    this.prefs = {
      sync_scroll: true, sync_zoom: true, show_highlight_link: true,
      font_size_ja: 10, font_family_ja: 'Noto Sans JP',
      layout_mode: 'layout_priority', view_mode: 'single',
    };
    console.log('[Paper Translator] Constructor done, calling init...');
    this.init();
  }

  async init() {
    console.log('[Paper Translator] init() called');
    this.render(); // show loading screen

    if (IS_LOCAL_DEV) {
      // Skip auth in local dev
      this.user = { email: 'dev@local' };
      this.screen = 'upload';
    } else {
      // Check existing session
      const user = await getCurrentUser();
      if (user) {
        this.user = user;
        this.screen = 'upload';
      } else {
        this.screen = 'login';
      }
      // Listen for auth changes
      onAuthStateChange((event, session) => {
        if (event === 'SIGNED_IN' && session?.user) {
          this.user = session.user;
          this.screen = 'upload';
          this.render();
          this._loadAfterAuth();
        } else if (event === 'SIGNED_OUT') {
          this.user = null;
          this.screen = 'login';
          this.render();
        }
      });
    }

    this.render();
    if (this.user) this._loadAfterAuth();
  }

  async _loadAfterAuth() {
    try {
      this.prefs = await apiClient.getPreferences();
    } catch (e) {
      console.log('[Paper Translator] Using default preferences');
    }
    this.syncManager.setSyncScroll(this.prefs.sync_scroll);
    this.highlightManager.setEnabled(this.prefs.show_highlight_link);
  }

  render() {
    const app = document.getElementById('app');
    app.innerHTML = '';
    if (this.screen === 'loading') {
      app.innerHTML = '<div style="flex:1;display:flex;align-items:center;justify-content:center;"><div class="spinner"></div></div>';
    } else if (this.screen === 'login') {
      app.appendChild(this._buildLoginScreen());
    } else if (this.screen === 'upload') {
      app.appendChild(this._buildHeader(false));
      app.appendChild(this._buildUploadScreen());
    } else {
      app.appendChild(this._buildHeader(true));
      app.appendChild(this._buildViewer());
    }
  }

  // ─── Login Screen ──────────────────────────────
  _buildLoginScreen() {
    const s = document.createElement('div');
    s.className = 'login-screen';
    s.innerHTML = `
      <div class="login-orb login-orb--1"></div>
      <div class="login-orb login-orb--2"></div>
      <div class="login-orb login-orb--3"></div>

      <div class="login-content">
        <div class="login-logo">
          <div class="login-logo__icon">📄</div>
          <div class="login-logo__title">Paper Translator</div>
          <div class="login-logo__subtitle">英語の学術論文PDFを日本語に翻訳し<br>左右に並べて対訳で読めます</div>
        </div>

        <div class="auth-card">
          <div class="auth-tabs">
            <button class="auth-tab auth-tab--active" data-tab="login">ログイン</button>
            <button class="auth-tab" data-tab="signup">新規登録</button>
          </div>
          <form class="auth-form" id="authForm">
            <div class="auth-input-group">
              <input type="email" id="authEmail" class="auth-input" placeholder="メールアドレス" required autocomplete="email" />
            </div>
            <div class="auth-input-group">
              <input type="password" id="authPassword" class="auth-input auth-input--has-toggle" placeholder="パスワード（6文字以上）" required minlength="6" autocomplete="current-password" />
              <button type="button" class="password-toggle" id="passwordToggle" tabindex="-1" aria-label="パスワードを表示">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" id="eyePath"/>
                  <circle cx="12" cy="12" r="3" id="eyeCircle"/>
                </svg>
              </button>
            </div>
            <button type="submit" class="auth-submit" id="authSubmit">
              <span class="auth-submit__text">ログイン</span>
            </button>
          </form>
          <div class="auth-divider">または</div>
          <button class="auth-google" id="btnGoogle">
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Googleでログイン
          </button>
          <div id="authMessage" class="auth-message" style="display:none;"></div>
        </div>

        <div class="login-footer">
          ログインすることで、翻訳データがクラウドに<br>安全に保存されます。
        </div>
      </div>
    `;

    setTimeout(() => {
      let isLogin = true;
      const tabs = s.querySelectorAll('.auth-tab');
      const submitBtn = s.querySelector('#authSubmit');
      const submitText = s.querySelector('.auth-submit__text');
      const passwordInput = s.querySelector('#authPassword');
      const passwordToggle = s.querySelector('#passwordToggle');

      // Tab switching
      tabs.forEach(tab => {
        tab.addEventListener('click', () => {
          isLogin = tab.dataset.tab === 'login';
          tabs.forEach(t => t.classList.toggle('auth-tab--active', t === tab));
          submitText.textContent = isLogin ? 'ログイン' : '新規登録';
          passwordInput.autocomplete = isLogin ? 'current-password' : 'new-password';
          // Clear any messages
          this._hideAuthMessage(s);
        });
      });

      // Password visibility toggle
      passwordToggle.addEventListener('click', () => {
        const isPassword = passwordInput.type === 'password';
        passwordInput.type = isPassword ? 'text' : 'password';
        // Swap icon (eye open ↔ eye with slash)
        const svg = passwordToggle.querySelector('svg');
        if (isPassword) {
          svg.innerHTML = `
            <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/>
            <line x1="1" y1="1" x2="23" y2="23"/>
          `;
        } else {
          svg.innerHTML = `
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
          `;
        }
      });

      // Form submission
      s.querySelector('#authForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = s.querySelector('#authEmail').value;
        const password = s.querySelector('#authPassword').value;
        this._hideAuthMessage(s);

        // Show loading state
        submitBtn.classList.add('auth-submit--loading');

        try {
          if (isLogin) {
            await signIn(email, password);
          } else {
            await signUp(email, password);
            submitBtn.classList.remove('auth-submit--loading');
            this._showAuthMessage(s, '確認メールを送信しました。メールを確認してください。', 'success');
            return;
          }
        } catch (err) {
          submitBtn.classList.remove('auth-submit--loading');
          this._showAuthMessage(s, err.message, 'error');
        }
      });

      // Google OAuth
      s.querySelector('#btnGoogle').addEventListener('click', async () => {
        try {
          await signInWithGoogle();
        } catch (err) {
          this._showAuthMessage(s, err.message, 'error');
        }
      });
    });
    return s;
  }

  _showAuthMessage(container, text, type = 'error') {
    const el = container.querySelector('#authMessage');
    if (!el) return;
    el.textContent = text;
    el.className = `auth-message auth-message--${type}`;
    el.style.display = 'block';
  }

  _hideAuthMessage(container) {
    const el = container.querySelector('#authMessage');
    if (el) el.style.display = 'none';
  }

  // ─── Header ────────────────────────────────────
  _buildHeader(isViewer) {
    const h = document.createElement('header');
    h.className = 'header';
    h.innerHTML = `
      <div class="header__logo">Paper Translator<span>β</span></div>
      ${isViewer ? `<div class="header__doc-title" id="headerTitle">${this.currentDoc?.title || ''}</div>` : ''}
      <div class="header__actions">
        ${isViewer ? `
          <button class="btn btn--ghost btn--icon" id="btnHome" title="ホーム">${icons.home}</button>
          <button class="btn btn--ghost btn--icon" id="btnSidebar" title="サムネイル">${icons.sidebar}</button>
          <button class="btn btn--ghost btn--icon" id="btnSearch" title="検索">${icons.search}</button>
          <button class="btn btn--ghost btn--icon" id="btnSettings" title="設定">${icons.settings}</button>
          <button class="btn btn--ghost btn--icon" id="btnDownload" title="ダウンロード">${icons.download}</button>
        ` : ''}
        <span style="font-size:0.75rem;color:var(--c-text-muted);margin-left:8px;">${this.user?.email || ''}</span>
        ${!IS_LOCAL_DEV ? '<button class="btn btn--ghost btn--sm" id="btnLogout">ログアウト</button>' : ''}
      </div>
    `;

    setTimeout(() => {
      h.querySelector('#btnHome')?.addEventListener('click', () => { this.screen = 'upload'; this.render(); });
      h.querySelector('#btnSidebar')?.addEventListener('click', () => this._toggleThumbnails());
      h.querySelector('#btnSearch')?.addEventListener('click', () => this._toggleSearch());
      h.querySelector('#btnSettings')?.addEventListener('click', () => this._showSettings());
      h.querySelector('#btnDownload')?.addEventListener('click', () => this._downloadPdf());
      h.querySelector('#btnLogout')?.addEventListener('click', async () => { await signOut(); });
    });
    return h;
  }

  // ─── Upload Screen ─────────────────────────────
  _buildUploadScreen() {
    const s = document.createElement('div');
    s.className = 'upload-screen';
    s.innerHTML = `
      <div class="upload-hero">
        <h1>Paper Translator</h1>
        <p>英語の学術論文PDFをアップロードすると、日本語翻訳を生成し<br>左右に並べて対訳で読めます。</p>
      </div>
      <div class="dropzone" id="dropzone">
        <div class="dropzone__icon">📄</div>
        <div class="dropzone__text"><strong>クリックまたはドラッグ&ドロップ</strong><br>でPDFをアップロード (最大50MB)</div>
        <input type="file" id="fileInput" accept=".pdf" />
      </div>
      <div class="doc-list" id="docList"></div>
    `;

    setTimeout(() => this._setupUpload(s));
    return s;
  }

  async _setupUpload(container) {
    const dropzone = container.querySelector('#dropzone');
    const fileInput = container.querySelector('#fileInput');

    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dropzone--active'); });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dropzone--active'));
    dropzone.addEventListener('drop', e => {
      e.preventDefault(); dropzone.classList.remove('dropzone--active');
      const file = e.dataTransfer.files[0];
      if (file?.type === 'application/pdf') this._handleUpload(file);
    });
    fileInput.addEventListener('change', () => {
      if (fileInput.files[0]) this._handleUpload(fileInput.files[0]);
    });

    // Load document list
    try {
      const docs = await apiClient.listDocuments();
      this._renderDocList(container.querySelector('#docList'), docs);
    } catch (e) { /* backend might not be running */ }
  }

  _renderDocList(container, docs) {
    if (!docs.length) { container.innerHTML = ''; return; }
    container.innerHTML = `<h3>📚 過去の論文</h3>`;
    docs.forEach(doc => {
      const item = document.createElement('div');
      item.className = 'doc-item';
      const statusClass = doc.status === 'completed' ? 'completed' : doc.status === 'error' ? 'error' : 'uploaded';
      const statusLabel = { completed: '翻訳済み', uploaded: '未翻訳', error: 'エラー', analyzing: '解析中', translating: '翻訳中' }[doc.status] || doc.status;
      item.innerHTML = `
        <div class="doc-item__icon">📄</div>
        <div class="doc-item__info">
          <div class="doc-item__title">${doc.title || doc.original_filename}</div>
          <div class="doc-item__meta">${doc.total_pages || '?'}ページ${doc.authors ? ' · ' + doc.authors : ''}</div>
        </div>
        <span class="doc-item__status doc-item__status--${statusClass}">${statusLabel}</span>
        <button class="doc-item__delete btn--icon" data-id="${doc.id}" title="削除">${icons.trash}</button>
      `;
      item.addEventListener('click', (e) => {
        if (e.target.closest('.doc-item__delete')) return;
        this._openDocument(doc);
      });
      item.querySelector('.doc-item__delete').addEventListener('click', async (e) => {
        e.stopPropagation();
        if (confirm('この論文を削除しますか？')) {
          await apiClient.deleteDocument(doc.id);
          item.remove();
        }
      });
      container.appendChild(item);
    });
  }

  async _handleUpload(file) {
    this._showProgress('アップロード中', 'PDFをアップロードしています...', 0.1);
    try {
      const doc = await apiClient.uploadPdf(file);
      this._showProgress('PDF解析開始', '翻訳を開始しています...', 0.15);
      await apiClient.startTranslation(doc.id);
      await this._pollProgress(doc.id);
      this._hideProgress();
      await this._openDocument(doc);
    } catch (e) {
      this._hideProgress();
      alert('エラー: ' + e.message);
    }
  }

  async _pollProgress(docId) {
    while (true) {
      const p = await apiClient.getProgress(docId);
      this._showProgress(p.current_step, p.message, p.progress);
      if (p.status === 'completed' || p.status === 'error') break;
      await new Promise(r => setTimeout(r, 500));
    }
  }

  async _openDocument(doc) {
    this.currentDoc = await apiClient.getDocument(doc.id);
    this.totalPages = this.currentDoc.total_pages;
    this.currentPage = 1;
    this.screen = 'viewer';
    this.render();

    // Create renderers lazily
    this.jaRenderer = new PdfRenderer();
    this.enRenderer = new PdfRenderer();

    const pdfUrl = apiClient.getPdfUrl(doc.id);
    await Promise.all([
      this.jaRenderer.loadDocument(pdfUrl),
      this.enRenderer.loadDocument(pdfUrl),
    ]);

    // Load all blocks
    if (this.currentDoc.status === 'completed') {
      const allBlocks = await apiClient.getBlocks(doc.id);
      this.blocks = {};
      allBlocks.forEach(b => {
        if (!this.blocks[b.page_number]) this.blocks[b.page_number] = [];
        this.blocks[b.page_number].push(b);
      });
    }

    this._renderPages();
    this._initSync();
  }

  // ─── Viewer ────────────────────────────────────
  _buildViewer() {
    const v = document.createElement('div');
    v.className = 'viewer';
    v.innerHTML = `
      <div class="viewer__toolbar">
        <div class="viewer__toolbar-group">
          <button class="btn btn--ghost btn--icon btn--sm" id="btnPrev">${icons.chevLeft}</button>
          <span class="viewer__page-info" id="pageInfo">1 / ${this.totalPages}</span>
          <button class="btn btn--ghost btn--icon btn--sm" id="btnNext">${icons.chevRight}</button>
        </div>
        <div class="viewer__toolbar-divider"></div>
        <div class="viewer__toolbar-group">
          <button class="btn btn--ghost btn--icon btn--sm" id="btnZoomOut">${icons.zoomOut}</button>
          <span class="viewer__page-info" id="zoomInfo">${Math.round(this.scale * 100)}%</span>
          <button class="btn btn--ghost btn--icon btn--sm" id="btnZoomIn">${icons.zoomIn}</button>
        </div>
        <div class="viewer__toolbar-divider"></div>
        <div class="viewer__toolbar-group">
          <button class="btn btn--ghost btn--sm ${this.syncManager.syncScroll ? 'btn--active' : ''}" id="btnSyncScroll">${icons.sync} 同期スクロール</button>
        </div>
        ${this.currentDoc?.status !== 'completed' ? `
          <button class="btn btn--primary btn--sm" id="btnTranslate" style="margin-left:auto;">${icons.translate} 翻訳開始</button>
        ` : ''}
      </div>
      <div class="viewer__main">
        <div class="thumbnail-panel ${this.showThumbnails ? '' : 'hidden'}" id="thumbnailPanel"></div>
        <div class="panel panel--ja" id="panelJa"><div class="panel__label">🇯🇵 日本語</div><div class="panel__pages" id="pagesJa"></div></div>
        <div class="resize-handle" id="resizeHandle"></div>
        <div class="panel panel--en" id="panelEn"><div class="panel__label">🇬🇧 English</div><div class="panel__pages" id="pagesEn"></div></div>
        <div class="search-panel hidden" id="searchPanel">
          <div class="search-panel__input">
            <input type="text" id="searchInput" placeholder="検索..." />
            <button class="btn btn--icon btn--sm" id="btnSearchClose">${icons.x}</button>
          </div>
          <div class="search-panel__results" id="searchResults"></div>
        </div>
      </div>
    `;

    setTimeout(() => {
      v.querySelector('#btnPrev')?.addEventListener('click', () => this._changePage(-1));
      v.querySelector('#btnNext')?.addEventListener('click', () => this._changePage(1));
      v.querySelector('#btnZoomIn')?.addEventListener('click', () => this._changeZoom(0.2));
      v.querySelector('#btnZoomOut')?.addEventListener('click', () => this._changeZoom(-0.2));
      v.querySelector('#btnSyncScroll')?.addEventListener('click', (e) => {
        this.syncManager.syncScroll = !this.syncManager.syncScroll;
        e.currentTarget.classList.toggle('btn--active');
      });
      v.querySelector('#btnTranslate')?.addEventListener('click', () => this._startTranslation());
      v.querySelector('#btnSearchClose')?.addEventListener('click', () => this._toggleSearch());

      const searchInput = v.querySelector('#searchInput');
      let searchTimer;
      searchInput?.addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => this._doSearch(searchInput.value), 300);
      });

      this._setupResize(v);
    });
    return v;
  }

  _initSync() {
    const ja = document.getElementById('panelJa');
    const en = document.getElementById('panelEn');
    if (ja && en) this.syncManager.init(ja, en);
  }

  async _renderPages() {
    const jaContainer = document.getElementById('pagesJa');
    const enContainer = document.getElementById('pagesEn');
    if (!jaContainer || !enContainer) return;

    jaContainer.innerHTML = '';
    enContainer.innerHTML = '';

    for (let i = 1; i <= this.totalPages; i++) {
      // Japanese panel page
      const jaPage = document.createElement('div');
      jaPage.className = 'page-container';
      jaPage.setAttribute('data-page', i);
      const jaCanvas = document.createElement('canvas');
      jaPage.appendChild(jaCanvas);
      jaContainer.appendChild(jaPage);

      // English panel page
      const enPage = document.createElement('div');
      enPage.className = 'page-container';
      enPage.setAttribute('data-page', i);
      const enCanvas = document.createElement('canvas');
      enPage.appendChild(enCanvas);
      enContainer.appendChild(enPage);

      // Render canvases
      const panelWidth = document.getElementById('panelJa')?.clientWidth;
      const [jaInfo] = await Promise.all([
        this.jaRenderer.renderPage(i, jaCanvas, panelWidth),
        this.enRenderer.renderPage(i, enCanvas, panelWidth),
      ]);

      // Add translation overlay to JA panel
      if (this.blocks[i - 1]) {
        this._addTranslationOverlay(jaPage, this.blocks[i - 1], jaInfo);
        this._addSourceHighlights(enPage, this.blocks[i - 1], jaInfo);
      }
    }

    // Render thumbnails
    if (this.showThumbnails) this._renderThumbnails();
  }

  _addTranslationOverlay(container, blocks, renderInfo) {
    if (!renderInfo) return;
    const overlay = document.createElement('div');
    overlay.className = 'translation-overlay';

    const scaleX = renderInfo.width / renderInfo.origWidth;
    const scaleY = renderInfo.height / renderInfo.origHeight;

    blocks.forEach(block => {
      if (!block.translated_text) return;
      const div = document.createElement('div');
      div.className = 'translation-block';
      div.setAttribute('data-block-id', block.id);

      const x = block.bbox.x0 * scaleX;
      const y = block.bbox.y0 * scaleY;
      const w = (block.bbox.x1 - block.bbox.x0) * scaleX;
      const h = (block.bbox.y1 - block.bbox.y0) * scaleY;

      div.style.left = x + 'px';
      div.style.top = y + 'px';
      div.style.width = w + 'px';
      div.style.height = h + 'px';

      // Auto font size to fit
      const area = w * h;
      const textLen = block.translated_text.length;
      let fontSize = Math.min(Math.sqrt(area / textLen) * 0.85, this.prefs?.font_size_ja || 10);
      fontSize = Math.max(fontSize, 5);
      div.style.fontSize = fontSize + 'px';
      div.style.fontFamily = this.prefs?.font_family_ja || 'Noto Sans JP';

      div.textContent = block.translated_text;
      div.title = block.translated_text;

      div.addEventListener('click', () => {
        this.highlightManager.highlightBlock(block.id, 'ja');
      });

      overlay.appendChild(div);
    });

    container.appendChild(overlay);
  }

  _addSourceHighlights(container, blocks, renderInfo) {
    if (!renderInfo) return;
    const scaleX = renderInfo.width / renderInfo.origWidth;
    const scaleY = renderInfo.height / renderInfo.origHeight;

    blocks.forEach(block => {
      const div = document.createElement('div');
      div.className = 'source-highlight';
      div.setAttribute('data-block-id', block.id);
      div.style.left = (block.bbox.x0 * scaleX) + 'px';
      div.style.top = (block.bbox.y0 * scaleY) + 'px';
      div.style.width = ((block.bbox.x1 - block.bbox.x0) * scaleX) + 'px';
      div.style.height = ((block.bbox.y1 - block.bbox.y0) * scaleY) + 'px';
      div.style.opacity = '0';
      div.style.transition = 'opacity 0.2s';

      div.addEventListener('mouseenter', () => { div.style.opacity = '1'; });
      div.addEventListener('mouseleave', () => {
        if (!div.classList.contains('source-highlight--active')) div.style.opacity = '0';
      });
      div.addEventListener('click', () => {
        this.highlightManager.highlightBlock(block.id, 'en');
        div.style.opacity = '1';
      });

      container.appendChild(div);
    });
  }

  // ─── Toolbar Actions ───────────────────────────
  _changePage(delta) {
    const newPage = this.currentPage + delta;
    if (newPage < 1 || newPage > this.totalPages) return;
    this.currentPage = newPage;
    document.getElementById('pageInfo').textContent = `${this.currentPage} / ${this.totalPages}`;
    this.syncManager.scrollToPage(this.currentPage);
  }

  _changeZoom(delta) {
    this.scale = Math.max(0.4, Math.min(3, this.scale + delta));
    this.jaRenderer.setScale(this.scale);
    this.enRenderer.setScale(this.scale);
    document.getElementById('zoomInfo').textContent = Math.round(this.scale * 100) + '%';
    this._renderPages();
  }

  _toggleThumbnails() {
    this.showThumbnails = !this.showThumbnails;
    const panel = document.getElementById('thumbnailPanel');
    if (panel) {
      panel.classList.toggle('hidden');
      if (this.showThumbnails) this._renderThumbnails();
    }
  }

  async _renderThumbnails() {
    const panel = document.getElementById('thumbnailPanel');
    if (!panel) return;
    panel.innerHTML = '';
    const thumbRenderer = new PdfRenderer();
    await thumbRenderer.loadDocument(apiClient.getPdfUrl(this.currentDoc.id));

    for (let i = 1; i <= this.totalPages; i++) {
      const item = document.createElement('div');
      item.className = `thumbnail-item ${i === this.currentPage ? 'thumbnail-item--active' : ''}`;
      const canvas = document.createElement('canvas');
      item.appendChild(canvas);
      item.innerHTML += `<span class="thumbnail-item__num">${i}</span>`;
      item.addEventListener('click', () => {
        this.currentPage = i;
        document.getElementById('pageInfo').textContent = `${i} / ${this.totalPages}`;
        this.syncManager.scrollToPage(i);
        document.querySelectorAll('.thumbnail-item').forEach(t => t.classList.remove('thumbnail-item--active'));
        item.classList.add('thumbnail-item--active');
      });
      panel.appendChild(item);
      thumbRenderer.renderThumbnail(i, canvas, 120);
    }
  }

  _toggleSearch() {
    this.showSearch = !this.showSearch;
    const panel = document.getElementById('searchPanel');
    if (panel) {
      panel.classList.toggle('hidden');
      if (this.showSearch) panel.querySelector('input')?.focus();
    }
  }

  async _doSearch(query) {
    if (!this.currentDoc || !query) {
      document.getElementById('searchResults').innerHTML = '';
      return;
    }
    const { results } = await this.searchEngine.search(this.currentDoc.id, query);
    const container = document.getElementById('searchResults');
    container.innerHTML = results.length
      ? results.map(r => `
        <div class="search-result-item" data-page="${r.page_number}" data-block="${r.block_id}">
          <div class="search-result-item__page">ページ ${r.page_number + 1} · ${r.field === 'source' ? '英語' : '日本語'}</div>
          <div class="search-result-item__snippet">${r.snippet.replace(new RegExp(`(${query})`, 'gi'), '<mark>$1</mark>')}</div>
        </div>
      `).join('')
      : '<div style="padding:20px;text-align:center;color:var(--c-text-muted);font-size:0.85rem;">検索結果なし</div>';

    container.querySelectorAll('.search-result-item').forEach(item => {
      item.addEventListener('click', () => {
        const pageNum = parseInt(item.dataset.page) + 1;
        this.syncManager.scrollToPage(pageNum);
        this.highlightManager.highlightBlock(item.dataset.block, 'ja');
      });
    });
  }

  async _startTranslation() {
    if (!this.currentDoc) return;
    try {
      await apiClient.startTranslation(this.currentDoc.id);
      this._showProgress('翻訳開始', '処理を開始しています...', 0.05);
      await this._pollProgress(this.currentDoc.id);
      this._hideProgress();
      this.currentDoc = await apiClient.getDocument(this.currentDoc.id);
      const allBlocks = await apiClient.getBlocks(this.currentDoc.id);
      this.blocks = {};
      allBlocks.forEach(b => {
        if (!this.blocks[b.page_number]) this.blocks[b.page_number] = [];
        this.blocks[b.page_number].push(b);
      });
      this._renderPages();
      this.render();
    } catch (e) {
      this._hideProgress();
      alert('翻訳エラー: ' + e.message);
    }
  }

  _showSettings() {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal">
        <h2>⚙️ 設定</h2>
        <div class="modal__row"><div class="modal__label">同期スクロール</div><label class="toggle"><input type="checkbox" id="prefSyncScroll" ${this.prefs.sync_scroll ? 'checked' : ''} /><span class="toggle__slider"></span></label></div>
        <div class="modal__row"><div class="modal__label">同期ズーム</div><label class="toggle"><input type="checkbox" id="prefSyncZoom" ${this.prefs.sync_zoom ? 'checked' : ''} /><span class="toggle__slider"></span></label></div>
        <div class="modal__row"><div class="modal__label">ハイライトリンク</div><label class="toggle"><input type="checkbox" id="prefHighlight" ${this.prefs.show_highlight_link ? 'checked' : ''} /><span class="toggle__slider"></span></label></div>
        <div class="modal__row"><div class="modal__label">参考文献を翻訳</div><label class="toggle"><input type="checkbox" id="prefTransRef" ${this.prefs.translate_references ? 'checked' : ''} /><span class="toggle__slider"></span></label></div>
        <div class="modal__row"><div class="modal__label">日本語フォントサイズ</div><input type="number" id="prefFontSize" value="${this.prefs.font_size_ja}" min="6" max="20" step="0.5" style="width:60px;background:var(--c-bg);border:1px solid var(--c-border);border-radius:var(--radius-sm);padding:4px 8px;color:var(--c-text);"/></div>
        <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:20px;">
          <button class="btn btn--ghost" id="settingsCancel">キャンセル</button>
          <button class="btn btn--primary" id="settingsSave">保存</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#settingsCancel').addEventListener('click', () => overlay.remove());
    overlay.querySelector('#settingsSave').addEventListener('click', async () => {
      const newPrefs = {
        sync_scroll: overlay.querySelector('#prefSyncScroll').checked,
        sync_zoom: overlay.querySelector('#prefSyncZoom').checked,
        show_highlight_link: overlay.querySelector('#prefHighlight').checked,
        translate_references: overlay.querySelector('#prefTransRef').checked,
        font_size_ja: parseFloat(overlay.querySelector('#prefFontSize').value),
      };
      this.prefs = { ...this.prefs, ...newPrefs };
      this.syncManager.setSyncScroll(newPrefs.sync_scroll);
      this.highlightManager.setEnabled(newPrefs.show_highlight_link);
      await apiClient.updatePreferences(newPrefs).catch(() => {});
      overlay.remove();
      if (this.screen === 'viewer') this._renderPages();
    });
  }

  _downloadPdf() {
    if (!this.currentDoc) return;
    const url = apiClient.getPdfUrl(this.currentDoc.id);
    const a = document.createElement('a');
    a.href = url; a.download = this.currentDoc.original_filename;
    a.click();
  }

  _setupResize(container) {
    const handle = container.querySelector('#resizeHandle');
    if (!handle) return;
    let startX, startWidthJa;
    handle.addEventListener('mousedown', (e) => {
      startX = e.clientX;
      startWidthJa = document.getElementById('panelJa').offsetWidth;
      const onMove = (e) => {
        const delta = e.clientX - startX;
        document.getElementById('panelJa').style.flex = `0 0 ${startWidthJa + delta}px`;
      };
      const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    });
  }

  // ─── Progress ──────────────────────────────────
  _showProgress(step, message, progress) {
    let overlay = document.getElementById('progressOverlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'progressOverlay';
      overlay.className = 'progress-overlay';
      document.body.appendChild(overlay);
    }
    overlay.innerHTML = `
      <div class="progress-card">
        <div class="spinner"></div>
        <h3>${step}</h3>
        <p>${message}</p>
        <div class="progress-bar"><div class="progress-bar__fill" style="width:${Math.round(progress * 100)}%"></div></div>
        <div class="progress-step">${Math.round(progress * 100)}%</div>
      </div>
    `;
  }

  _hideProgress() {
    document.getElementById('progressOverlay')?.remove();
  }
}

// Start - handle both cases: DOM already loaded or not yet
function startApp() {
  try {
    console.log('[Paper Translator] Starting app...');
    window.__app = new App();
    console.log('[Paper Translator] App created successfully');
  } catch (e) {
    console.error('[Paper Translator] Init error:', e);
    document.getElementById('app').innerHTML = `
      <div style="padding:40px;text-align:center;color:#f87171;">
        <h2>起動エラー</h2><p>${e.message}</p>
      </div>`;
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startApp);
} else {
  startApp();
}

