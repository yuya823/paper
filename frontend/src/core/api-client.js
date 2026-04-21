/** API Client - REST API wrapper with auth token support */
import { getAccessToken, IS_LOCAL_DEV } from './supabase-auth.js';

const API_BASE = '/api';

class ApiClient {
  async _getHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    if (!IS_LOCAL_DEV) {
      const token = await getAccessToken();
      if (token) headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  async request(path, options = {}) {
    const url = `${API_BASE}${path}`;
    const headers = await this._getHeaders();
    // Don't override content-type for FormData
    if (options.body instanceof FormData) delete headers['Content-Type'];
    const res = await fetch(url, { headers, ...options });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'API Error');
    }
    return res;
  }

  async uploadPdf(file) {
    const form = new FormData();
    form.append('file', file);
    const headers = {};
    if (!IS_LOCAL_DEV) {
      const token = await getAccessToken();
      if (token) headers['Authorization'] = `Bearer ${token}`;
    }
    const res = await fetch(`${API_BASE}/documents/upload`, {
      method: 'POST', body: form, headers,
    });
    if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || 'Upload failed'); }
    return res.json();
  }

  async listDocuments() {
    const res = await this.request('/documents/');
    return res.json();
  }

  async getDocument(id) {
    const res = await this.request(`/documents/${id}`);
    return res.json();
  }

  async deleteDocument(id) {
    await this.request(`/documents/${id}`, { method: 'DELETE' });
  }

  getPdfUrl(id) {
    return `${API_BASE}/documents/${id}/pdf`;
  }

  async getDimensions(id) {
    const res = await this.request(`/documents/${id}/dimensions`);
    return res.json();
  }

  async startTranslation(id, options = {}) {
    const res = await this.request(`/translation/${id}/start`, {
      method: 'POST', body: JSON.stringify(options),
    });
    return res.json();
  }

  async getProgress(id) {
    const res = await this.request(`/translation/${id}/progress`);
    return res.json();
  }

  async getBlocks(id, page = null) {
    const query = page !== null ? `?page=${page}` : '';
    const res = await this.request(`/translation/${id}/blocks${query}`);
    return res.json();
  }

  async searchBlocks(id, query, searchIn = 'both') {
    const res = await this.request(
      `/translation/${id}/search?query=${encodeURIComponent(query)}&search_in=${searchIn}`,
      { method: 'POST' },
    );
    return res.json();
  }

  async getPreferences() {
    const res = await this.request('/preferences/');
    return res.json();
  }

  async updatePreferences(prefs) {
    const res = await this.request('/preferences/', {
      method: 'PUT', body: JSON.stringify(prefs),
    });
    return res.json();
  }
}

export const apiClient = new ApiClient();
