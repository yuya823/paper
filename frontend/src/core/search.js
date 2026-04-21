/** Search module */
export class SearchEngine {
  constructor(apiClient) {
    this.api = apiClient;
  }

  async search(docId, query, searchIn = 'both') {
    if (!query || query.length < 2) return { results: [], total: 0 };
    return this.api.searchBlocks(docId, query, searchIn);
  }
}
