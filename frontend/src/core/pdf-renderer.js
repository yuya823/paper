/** PDF Renderer - PDF.js wrapper for rendering pages */

let pdfjsLib = null;

async function ensurePdfJs() {
  if (pdfjsLib) return pdfjsLib;
  pdfjsLib = await import('pdfjs-dist');
  pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.min.mjs',
    import.meta.url
  ).toString();
  return pdfjsLib;
}

export class PdfRenderer {
  constructor() {
    this.pdfDoc = null;
    this.scale = 1.2;
  }

  async loadDocument(url) {
    const lib = await ensurePdfJs();
    this.pdfDoc = await lib.getDocument(url).promise;
    return this.pdfDoc.numPages;
  }

  async renderPage(pageNum, canvas, containerWidth = null) {
    if (!this.pdfDoc) return null;
    const page = await this.pdfDoc.getPage(pageNum);
    let viewport = page.getViewport({ scale: this.scale });

    if (containerWidth && containerWidth > 0) {
      const fitScale = (containerWidth - 4) / viewport.width;
      if (fitScale < this.scale) {
        viewport = page.getViewport({ scale: fitScale });
      }
    }

    const ctx = canvas.getContext('2d');
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.width = viewport.width + 'px';
    canvas.style.height = viewport.height + 'px';

    await page.render({ canvasContext: ctx, viewport }).promise;

    const origViewport = page.getViewport({ scale: 1 });
    return {
      width: viewport.width,
      height: viewport.height,
      scale: viewport.scale,
      origWidth: origViewport.width,
      origHeight: origViewport.height,
    };
  }

  async renderThumbnail(pageNum, canvas, width = 120) {
    if (!this.pdfDoc) return;
    const page = await this.pdfDoc.getPage(pageNum);
    const origViewport = page.getViewport({ scale: 1 });
    const scale = width / origViewport.width;
    const viewport = page.getViewport({ scale });

    canvas.width = viewport.width;
    canvas.height = viewport.height;
    const ctx = canvas.getContext('2d');
    await page.render({ canvasContext: ctx, viewport }).promise;
  }

  setScale(scale) { this.scale = scale; }
  getNumPages() { return this.pdfDoc?.numPages || 0; }
}
