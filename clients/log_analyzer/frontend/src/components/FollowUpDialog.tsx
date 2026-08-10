"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MessageSquare } from "lucide-react";
import { AppSettings } from "@/lib/types";
import { askFollowUp } from "@/lib/api";
import { t } from "@/lib/i18n";

interface FollowUpDialogProps {
  settings: AppSettings;
  report: {
    eventId: string;
    provider: string;
    solutionSummary?: { overview: string; causes: string[]; steps: string[] };
    searchResults?: { title: string; link: string }[];
  };
}

export function FollowUpDialog({ settings, report }: FollowUpDialogProps) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const lang = settings.language;

  const handleAsk = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setError("");
    setAnswer("");

    try {
      const response = await askFollowUp(settings, {
        question,
        eventId: report.eventId,
        provider: report.provider,
        language: lang,
      });
      setAnswer(response.answer);
    } catch (err) {
      console.error(err);
      setError(t(lang, "followUpError"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 p-4 rounded-lg shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <MessageSquare className="w-5 h-5 text-[#0078d4]" />
          <h4 className="font-semibold text-gray-800 dark:text-gray-200">{t(lang, "followUpTitle")}</h4>
        </div>
        <Input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={t(lang, "followUpPlaceholder")}
          className="bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-700"
        />
        <div className="flex gap-2 mt-3">
          <Button
            className="flex-1 bg-[#0078d4] hover:bg-[#006cbd]"
            onClick={handleAsk}
            disabled={loading}
          >
            {loading ? t(lang, "searching") : t(lang, "followUpButton")}
          </Button>
        </div>
      </div>

      {error && (
        <div className="text-sm text-red-600 dark:text-red-300 bg-red-50 dark:bg-red-900/20 p-3 rounded">
          {error}
        </div>
      )}

      {answer && (
        <div className="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 p-4 rounded-lg">
          <h5 className="font-medium text-gray-800 dark:text-gray-200 mb-2">{t(lang, "followUpAnswer")}</h5>
          <pre className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300">{answer}</pre>
        </div>
      )}
    </div>
  );
}
