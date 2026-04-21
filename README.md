# Paper Translator - 英語論文PDF対訳ビューア

英語の学術論文PDFをアップロードし、日本語翻訳を生成して左右に並べて対訳で読めるWebアプリ。

## クイックスタート

### 1. バックエンド起動
```bash
cd backend
source venv/bin/activate
python -m uvicorn main:app --reload --port 8000
```

### 2. フロントエンド起動
```bash
cd frontend
npm run dev
```

### 3. ブラウザで開く
http://localhost:5173/

## 機能
- 📄 英語PDFアップロード（ドラッグ&ドロップ対応）
- 🔄 テキストブロック単位の日本語翻訳
- 📖 左：日本語版 / 右：英語版の2カラム表示
- 🔗 同期スクロール
- 🔍 ブロッククリックで対応箇所ハイライト
- 🔎 全文検索（日英両方）
- 📑 サムネイルナビゲーション
- ⚙️ 各種設定（フォント、同期、翻訳オプション）
- 💾 論文一覧の保存・復元

## 技術スタック
- **フロントエンド**: Vite + Vanilla JS + PDF.js
- **バックエンド**: Python FastAPI + PyMuPDF
- **データベース**: SQLite
- **翻訳**: モック翻訳（DeepL API切替可能）

## 翻訳APIの切替
`.env`ファイルをbackendフォルダに作成:
```
TRANSLATION_MODE=deepl
DEEPL_API_KEY=your-api-key-here
```
