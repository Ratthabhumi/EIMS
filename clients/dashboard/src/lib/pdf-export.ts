type PdfDependencies = {
  jsPDF: typeof import("jspdf").default;
  html2canvas: typeof import("html2canvas").default;
};

let dependencies: Promise<PdfDependencies> | null = null;

export function preloadPdfExport(): Promise<PdfDependencies> {
  if (!dependencies) {
    dependencies = Promise.all([import("jspdf"), import("html2canvas")])
      .then(([pdfModule, canvasModule]) => ({
        jsPDF: pdfModule.default,
        html2canvas: canvasModule.default,
      }))
      .catch((error) => {
        dependencies = null;
        throw error;
      });
  }
  return dependencies;
}

function safeFilename(filename: string): string {
  return filename.replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_").slice(0, 128);
}

/** Render a prepared, sanitized HTML report and trigger a normal Blob download. */
export async function downloadHtmlAsPdf(
  element: HTMLElement,
  filename: string,
): Promise<{ pages: number; bytes: number }> {
  const { jsPDF, html2canvas } = await preloadPdfExport();
  const canvas = await html2canvas(element, {
    scale: 1.5,
    useCORS: true,
    backgroundColor: "#fff",
    logging: false,
    scrollX: 0,
    scrollY: 0,
    windowWidth: Math.max(window.innerWidth, element.scrollWidth),
    windowHeight: Math.max(window.innerHeight, element.scrollHeight),
    onclone: (clonedDocument) => {
      const cloned = clonedDocument.querySelector<HTMLElement>("[data-eims-pdf-export='true']");
      if (cloned) {
        cloned.style.opacity = "1";
        cloned.style.zIndex = "2147483647";
        cloned.style.left = "0";
        cloned.style.top = "0";
      }
    },
  });
  if (canvas.width === 0 || canvas.height === 0) {
    throw new Error("PDF renderer produced an empty page");
  }

  const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const imageHeight = (canvas.height * pageWidth) / canvas.width;
  const imageData = canvas.toDataURL("image/png");
  let y = 0;
  let pages = 0;
  while (y < imageHeight) {
    if (pages > 0) pdf.addPage();
    pdf.addImage(imageData, "PNG", 0, -y, pageWidth, imageHeight, undefined, "FAST");
    y += pageHeight;
    pages += 1;
  }

  const blob = pdf.output("blob") as Blob;
  if (blob.size === 0) throw new Error("PDF renderer produced an empty file");
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = safeFilename(filename);
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
  return { pages, bytes: blob.size };
}
