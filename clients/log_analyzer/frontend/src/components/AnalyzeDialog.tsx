"use client";

import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Plus, UploadCloud, Code, Image as ImageIcon, FileText, Layers } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { AnalysisResult } from "@/components/AnalysisResult";
import { BatchResult } from "@/components/BatchResult";
import { AnalysisReport, AppSettings } from "@/lib/types";
import { analyzeLog } from "@/lib/api";
import { t } from "@/lib/i18n";

interface AnalyzeDialogProps {
  settings: AppSettings;
  onComplete: () => void;
}

const LOADING_STAGES = [
  { pct: 10, labelEn: "Parsing log data...", labelTh: "กำลังอ่าน Log..." },
  { pct: 30, labelEn: "Searching knowledge base...", labelTh: "ค้นหาข้อมูล..." },
  { pct: 55, labelEn: "Querying web sources...", labelTh: "ดึงข้อมูลจากอินเทอร์เน็ต..." },
  { pct: 75, labelEn: "Analyzing with AI...", labelTh: "วิเคราะห์ด้วย AI..." },
  { pct: 90, labelEn: "Building solution...", labelTh: "สร้างวิธีแก้ไข..." },
  { pct: 98, labelEn: "Almost done...", labelTh: "เกือบเสร็จแล้ว..." },
];

export function AnalyzeDialog({ settings, onComplete }: AnalyzeDialogProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadPct, setLoadPct] = useState(0);
  const [loadStage, setLoadStage] = useState("");
  const [elapsedSec, setElapsedSec] = useState(0);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [pastedImage, setPastedImage] = useState<File | null>(null);
  const [sourceText, setSourceText] = useState<string | null>(null);
  const [tab, setTab] = useState("text");
  // Batch state
  const [batchResults, setBatchResults] = useState<{ filename: string; report: AnalysisReport | null; error?: string }[] | null>(null);
  const [batchProgress, setBatchProgress] = useState<{ current: number; total: number } | null>(null);
  const loadTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);
  const lang = settings.language;

  useEffect(() => {
    if (!open || report) return;

    const handlePaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;

      for (let i = 0; i < items.length; i++) {
        if (items[i].type.indexOf("image") !== -1) {
          const file = items[i].getAsFile();
          if (file) {
            setPastedImage(file);
            setTab("image");
          }
          break;
        }
      }
    };

    window.addEventListener("paste", handlePaste as EventListener);
    return () => window.removeEventListener("paste", handlePaste as EventListener);
  }, [open, report]);

  const startLoadingProgress = () => {
    setLoadPct(0);
    setElapsedSec(0);
    startTimeRef.current = Date.now();
    let stageIdx = 0;
    setLoadStage(lang === 'th' ? LOADING_STAGES[0].labelTh : LOADING_STAGES[0].labelEn);
    setLoadPct(LOADING_STAGES[0].pct);
    loadTimerRef.current = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000);
      setElapsedSec(elapsed);
      const nextIdx = Math.min(stageIdx + 1, LOADING_STAGES.length - 1);
      if (nextIdx !== stageIdx) {
        stageIdx = nextIdx;
        const stage = LOADING_STAGES[stageIdx];
        setLoadPct(stage.pct);
        setLoadStage(lang === 'th' ? stage.labelTh : stage.labelEn);
      }
    }, 2500);
  };

  const stopLoadingProgress = () => {
    if (loadTimerRef.current) {
      clearInterval(loadTimerRef.current);
      loadTimerRef.current = null;
    }
    setLoadPct(100);
    setLoadStage(lang === 'th' ? 'เสร็จสิ้น!' : 'Done!');
  };

  const handleAnalyze = async () => {
    setLoading(true);
    startLoadingProgress();
    try {
      const formData = new FormData();
      const textVal = (document.getElementById("event-text") as HTMLTextAreaElement)?.value;
      const imageInput = document.getElementById("image-upload") as HTMLInputElement;
      const fileInput = document.getElementById("file-upload") as HTMLInputElement;

      if (textVal) {
        setSourceText(textVal);
        formData.append("text", textVal);
      } else {
        setSourceText(null);
      }

      if (pastedImage) {
        formData.append("file", pastedImage);
      } else if (imageInput?.files?.[0]) {
        formData.append("file", imageInput.files[0]);
      } else if (fileInput?.files?.[0]) {
        formData.append("file", fileInput.files[0]);
      }

      const data = await analyzeLog(settings, formData);
      stopLoadingProgress();
      setReport(data);
      onComplete();
    } catch {
      stopLoadingProgress();
      alert(t(lang, "backendError"));
    } finally {
      setLoading(false);
    }
  };

  const handleOpenChange = (value: boolean) => {
    setOpen(value);
    if (!value) {
      setReport(null);
      setPastedImage(null);
      setSourceText(null);
      setTab("text");
      setBatchResults(null);
      setBatchProgress(null);
    }
  };

  const handleBatchAnalyze = async () => {
    const batchInput = document.getElementById("batch-upload") as HTMLInputElement;
    const files = batchInput?.files;
    if (!files || files.length === 0) {
      alert(lang === 'th' ? 'กรุณาเลือกไฟล์ก่อน' : 'Please select files first.');
      return;
    }
    setLoading(true);
    const total = files.length;
    const results: { filename: string; report: AnalysisReport | null; error?: string }[] = [];
    for (let i = 0; i < total; i++) {
      const file = files[i];
      setBatchProgress({ current: i + 1, total });
      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("language", settings.language);
        const data = await analyzeLog(settings, formData);
        results.push({ filename: file.name, report: data });
      } catch (e) {
        results.push({ filename: file.name, report: null, error: String(e) });
      }
    }
    setLoading(false);
    setBatchProgress(null);
    setBatchResults(results);
    onComplete();
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        className="bg-[#0078d4] hover:bg-[#006cbd] text-white flex items-center gap-2 px-4 py-2 rounded-md font-medium text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        onClick={() => { setReport(null); setPastedImage(null); setTab("text"); }}
      >
        <Plus className="w-4 h-4" /> {t(lang, "analyzeNewLog")}
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl bg-white dark:bg-gray-800 overflow-hidden max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold text-gray-800 dark:text-gray-100">
            {t(lang, "submitEventLog")}
          </DialogTitle>
        </DialogHeader>

        {!report ? (
          <div className="mt-4 w-full">
            {loading ? (
              /* ─────────── Loading Screen ─────────── */
              <div className="flex flex-col items-center justify-center py-12 gap-6">
                <div className="relative w-28 h-28">
                  <svg className="w-28 h-28 -rotate-90" viewBox="0 0 100 100">
                    <circle cx="50" cy="50" r="44" fill="none" stroke="#e5e7eb" strokeWidth="8" />
                    <circle
                      cx="50" cy="50" r="44" fill="none"
                      stroke="#0078d4" strokeWidth="8"
                      strokeLinecap="round"
                      strokeDasharray={`${2 * Math.PI * 44}`}
                      strokeDashoffset={`${2 * Math.PI * 44 * (1 - loadPct / 100)}`}
                      style={{ transition: 'stroke-dashoffset 1s ease' }}
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-2xl font-bold text-[#0078d4]">{loadPct}%</span>
                  </div>
                </div>
                <div className="text-center space-y-1">
                  <p className="text-base font-semibold text-gray-700 dark:text-gray-200 animate-pulse">{loadStage}</p>
                  <p className="text-sm text-gray-400">
                    {lang === 'th' ? `ผ่านไปแล้ว ${elapsedSec} วินาที` : `Elapsed: ${elapsedSec}s`}
                  </p>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div
                    className="bg-[#0078d4] h-2 rounded-full transition-all duration-1000"
                    style={{ width: `${loadPct}%` }}
                  />
                </div>
                <p className="text-xs text-gray-400">
                  {lang === 'th' ? '⚠️ อาจใช้เวลา 15–60 วินาที ขึ้นอยู่กับความซับซ้อนของ Log' : '⚠️ This may take 15–60 seconds depending on log complexity'}
                </p>
              </div>
            ) : (
            <Tabs value={tab} onValueChange={setTab} className="w-full">
              <TabsList className="grid w-full grid-cols-4 mb-4 bg-gray-100 dark:bg-gray-900">
                <TabsTrigger value="text" className="flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5" />{t(lang, "tabText")}
                </TabsTrigger>
                <TabsTrigger value="image" className="flex items-center gap-1.5">
                  <ImageIcon className="w-3.5 h-3.5" />{t(lang, "tabImage")}
                </TabsTrigger>
                <TabsTrigger value="file" className="flex items-center gap-1.5">
                  <Code className="w-3.5 h-3.5" />{t(lang, "tabFile")}
                </TabsTrigger>
                <TabsTrigger value="batch" className="flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5" />{lang === 'th' ? 'Batch' : 'Batch'}
                </TabsTrigger>
              </TabsList>
              <TabsContent value="text">
                <Textarea
                  id="event-text"
                  placeholder={t(lang, "pastePlaceholder")}
                  className="min-h-[200px] bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-600 w-full"
                />
              </TabsContent>
              <TabsContent value="image">
                {pastedImage ? (
                  <div className="relative border-2 border-dashed border-[#0078d4] rounded-lg p-4 flex flex-col items-center justify-center space-y-4">
                    <img src={URL.createObjectURL(pastedImage)} alt="Pasted" className="max-h-[200px] object-contain rounded-md" />
                    <p className="text-xs text-gray-500">{pastedImage.name || 'pasted-image'}</p>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" onClick={() => setPastedImage(null)}>
                        {t(lang, "clearImage") || "Clear Image"}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <label
                    htmlFor="image-upload"
                    className="border-2 border-dashed border-gray-200 dark:border-gray-600 rounded-lg p-10 flex flex-col items-center justify-center text-center space-y-2 hover:bg-gray-50 dark:hover:bg-gray-900 cursor-pointer block w-full"
                    onPaste={(e) => {
                      const items = e.clipboardData?.items;
                      if (!items) return;
                      for (let i = 0; i < items.length; i++) {
                        if (items[i].type.indexOf('image') !== -1) {
                          const f = items[i].getAsFile();
                          if (f) { setPastedImage(f); e.preventDefault(); }
                          break;
                        }
                      }
                    }}
                  >
                    <UploadCloud className="w-8 h-8 text-gray-400" />
                    <p className="text-sm text-gray-600 dark:text-gray-300 font-medium">{t(lang, "uploadImage")}</p>
                    <p className="text-xs text-[#0078d4] font-medium">
                      📋 {lang === 'th' ? 'กด Ctrl+V เพื่อวางรูปจาก Excel / Screenshot ได้เลย!' : 'Press Ctrl+V to paste from Excel / Screenshot!'}
                    </p>
                    <p className="text-xs text-gray-400">PNG, JPG, BMP accepted</p>
                    <Input id="image-upload" type="file" accept="image/*" className="hidden" onChange={(e) => {
                      if (e.target.files?.[0]) setPastedImage(e.target.files[0]);
                    }} />
                  </label>
                )}
              </TabsContent>
              <TabsContent value="file">
                <label htmlFor="file-upload" className="border-2 border-dashed border-gray-200 dark:border-gray-600 rounded-lg p-10 flex flex-col items-center justify-center text-center space-y-2 hover:bg-gray-50 dark:hover:bg-gray-900 cursor-pointer block w-full">
                  <Code className="w-8 h-8 text-gray-400" />
                  <p className="text-sm text-gray-600 dark:text-gray-300 font-medium">{t(lang, "uploadFile")}</p>
                  <p className="text-xs text-gray-400">.evtx, .xml, .txt, .csv, .log</p>
                  <Input id="file-upload" type="file" accept=".evtx,.xml,.txt,.csv,.log" className="hidden" />
                </label>
              </TabsContent>
              <TabsContent value="batch">
                <label htmlFor="batch-upload" className="border-2 border-dashed border-[#0078d4]/40 rounded-lg p-8 flex flex-col items-center justify-center text-center space-y-2 hover:bg-blue-50/30 dark:hover:bg-blue-900/10 cursor-pointer block w-full">
                  <Layers className="w-8 h-8 text-[#0078d4]" />
                  <p className="text-sm text-gray-700 dark:text-gray-200 font-medium">
                    {lang === 'th' ? 'เลือกหลายไฟล์พร้อมกัน' : 'Select multiple files at once'}
                  </p>
                  <p className="text-xs text-gray-400">.evtx, .xml, .txt, .csv, .log — {lang === 'th' ? 'สูงสุด 20 ไฟล์' : 'up to 20 files'}</p>
                  <Input id="batch-upload" type="file" multiple accept=".evtx,.xml,.txt,.csv,.log" className="hidden" />
                </label>
                {batchProgress && (
                  <div className="mt-3 text-sm text-center text-gray-500">
                    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mb-1">
                      <div
                        className="bg-[#0078d4] h-1.5 rounded-full transition-all"
                        style={{ width: `${(batchProgress.current / batchProgress.total) * 100}%` }}
                      />
                    </div>
                    {lang === 'th' ? `กำลังวิเคราะห์ไฟล์ที่ ${batchProgress.current} / ${batchProgress.total}` : `Analyzing file ${batchProgress.current} / ${batchProgress.total}`}
                  </div>
                )}
              </TabsContent>
            </Tabs>
            )}
            {!loading && (
            <Button
              onClick={tab === 'batch' ? handleBatchAnalyze : handleAnalyze}
              className="w-full bg-[#0078d4] hover:bg-[#006cbd] mt-4"
              disabled={loading}
            >
              {tab === 'batch'
                ? (lang === 'th' ? '🚀 วิเคราะห์ทั้งหมด' : '🚀 Analyze All')
                : t(lang, "searchAnalyze")}
            </Button>
            )}
          </div>
        ) : batchResults ? (
          <div className="mt-4">
            <BatchResult
              results={batchResults}
              language={lang}
              onClose={() => { setBatchResults(null); setTab("batch"); }}
            />
          </div>
        ) : (
          <AnalysisResult
            report={report!}
            settings={settings}
            language={lang}
            sourceImage={pastedImage}
            sourceText={sourceText}
            onAnalyzeAnother={() => { setReport(null); setPastedImage(null); setSourceText(null); setTab("text"); }}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

