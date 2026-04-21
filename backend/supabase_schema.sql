-- =============================================
-- Paper Translator - Supabase Database Schema
-- SupabaseのSQL Editorで実行してください
-- =============================================

-- 1. Documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    storage_path TEXT,
    title TEXT,
    authors TEXT,
    total_pages INTEGER,
    status TEXT DEFAULT 'uploaded'
        CHECK (status IN ('uploaded', 'analyzing', 'translating', 'completed', 'error')),
    source_lang TEXT DEFAULT 'en',
    target_lang TEXT DEFAULT 'ja',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 2. Page blocks table
CREATE TABLE IF NOT EXISTS page_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    block_index INTEGER NOT NULL,
    bbox_x0 REAL,
    bbox_y0 REAL,
    bbox_x1 REAL,
    bbox_y1 REAL,
    source_text TEXT,
    translated_text TEXT,
    block_type TEXT DEFAULT 'body'
        CHECK (block_type IN ('body', 'heading', 'caption', 'table', 'formula', 'footer', 'reference')),
    reading_order INTEGER,
    font_size REAL,
    font_name TEXT,
    is_translated BOOLEAN DEFAULT false
);

-- 3. User preferences table
CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    sync_scroll BOOLEAN DEFAULT true,
    sync_zoom BOOLEAN DEFAULT true,
    show_highlight_link BOOLEAN DEFAULT true,
    font_size_ja REAL DEFAULT 10.0,
    font_family_ja TEXT DEFAULT 'Noto Sans JP',
    layout_mode TEXT DEFAULT 'layout_priority',
    translate_references BOOLEAN DEFAULT false,
    translate_captions BOOLEAN DEFAULT true,
    translate_formulas BOOLEAN DEFAULT false,
    view_mode TEXT DEFAULT 'single'
);

-- 4. Indexes
CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_page_blocks_doc ON page_blocks(document_id);
CREATE INDEX IF NOT EXISTS idx_page_blocks_page ON page_blocks(document_id, page_number);

-- 5. Updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- 6. Row Level Security (RLS)
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE page_blocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

-- Documents: users can only access their own
CREATE POLICY "Users can view own documents"
    ON documents FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own documents"
    ON documents FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own documents"
    ON documents FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own documents"
    ON documents FOR DELETE
    USING (auth.uid() = user_id);

-- Page blocks: users can access blocks of their documents
CREATE POLICY "Users can view blocks of own documents"
    ON page_blocks FOR SELECT
    USING (document_id IN (SELECT id FROM documents WHERE user_id = auth.uid()));

CREATE POLICY "Users can insert blocks for own documents"
    ON page_blocks FOR INSERT
    WITH CHECK (document_id IN (SELECT id FROM documents WHERE user_id = auth.uid()));

CREATE POLICY "Users can update blocks of own documents"
    ON page_blocks FOR UPDATE
    USING (document_id IN (SELECT id FROM documents WHERE user_id = auth.uid()));

CREATE POLICY "Users can delete blocks of own documents"
    ON page_blocks FOR DELETE
    USING (document_id IN (SELECT id FROM documents WHERE user_id = auth.uid()));

-- User preferences: users can only access their own
CREATE POLICY "Users can view own preferences"
    ON user_preferences FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own preferences"
    ON user_preferences FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own preferences"
    ON user_preferences FOR UPDATE
    USING (auth.uid() = user_id);

-- 7. Storage bucket for PDFs
INSERT INTO storage.buckets (id, name, public)
VALUES ('papers', 'papers', false)
ON CONFLICT (id) DO NOTHING;

-- Storage policies
CREATE POLICY "Users can upload own PDFs"
    ON storage.objects FOR INSERT
    WITH CHECK (bucket_id = 'papers' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can view own PDFs"
    ON storage.objects FOR SELECT
    USING (bucket_id = 'papers' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can delete own PDFs"
    ON storage.objects FOR DELETE
    USING (bucket_id = 'papers' AND auth.uid()::text = (storage.foldername(name))[1]);

-- 8. Service role policies (for backend API)
-- The backend uses the service_role key, which bypasses RLS
-- This is intentional for server-side operations
