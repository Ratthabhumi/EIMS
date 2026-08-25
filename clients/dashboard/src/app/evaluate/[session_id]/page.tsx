"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Star, CheckCircle, Loader2 } from "lucide-react";

interface SessionDetails {
  session_id: string;
  title: string;
  description: string;
  customer_name: string;
  engineer_name: string;
  evaluation_questions: { id: string; label: string; category: string }[];
}

export default function MobileEvaluationForm() {
  const params = useParams();
  const sessionId = params.session_id as string;

  const [session, setSession] = useState<SessionDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [hoverRatings, setHoverRatings] = useState<Record<string, number>>({});
  const [responderName, setResponderName] = useState("");
  const [department, setDepartment] = useState("");
  const [comments, setComments] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  useEffect(() => {
    const fetchSession = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/v1/evaluations/sessions/${sessionId}`);
        if (!res.ok) {
          if (res.status === 404) throw new Error("This service session does not exist or has been removed.");
          throw new Error("Failed to load session details.");
        }
        const data = await res.json();
        setSession(data);
      } catch (err: any) {
        setError(err.message || "An unexpected error occurred.");
      } finally {
        setLoading(false);
      }
    };

    if (sessionId) fetchSession();
  }, [sessionId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session?.evaluation_questions || Object.keys(ratings).length !== session.evaluation_questions.length) {
      alert("Please provide a rating for all questions before submitting.");
      return;
    }

    setIsSubmitting(true);
    
    const ratingScoresArray = Object.entries(ratings).map(([question_id, score]) => ({
      question_id,
      score
    }));

    try {
      const res = await fetch(`http://localhost:8000/api/v1/evaluations/sessions/${sessionId}/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          responder_name: responderName.trim() || null,
          department: department.trim() || null,
          rating_scores: ratingScoresArray,
          feedback_comments: comments.trim() || null
        })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to submit evaluation.");
      }

      setIsSuccess(true);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-eims-bg">
        <Loader2 className="w-8 h-8 text-eims-accent animate-spin" />
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-eims-bg p-6 text-center">
        <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
          <Star className="w-8 h-8 text-red-500 opacity-50" />
        </div>
        <h1 className="text-xl font-semibold text-eims-text mb-2">Invalid Link</h1>
        <p className="text-eims-text-secondary text-sm">{error}</p>
      </div>
    );
  }

  if (isSuccess) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-eims-bg p-6 text-center animate-fade-in">
        <div className="w-20 h-20 rounded-full bg-green-500/10 flex items-center justify-center mb-6">
          <CheckCircle className="w-10 h-10 text-green-500" />
        </div>
        <h1 className="text-2xl font-semibold text-eims-text mb-2">Thank You!</h1>
        <p className="text-eims-text-secondary text-sm max-w-xs mx-auto">
          Your feedback for <span className="font-medium text-eims-text">{session.title}</span> has been received. We appreciate your time!
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-eims-bg flex flex-col">
      <div className="max-w-md md:max-w-2xl lg:max-w-3xl w-full mx-auto flex-1 flex flex-col my-0 md:my-10">
        {/* Header Section */}
        <div className="pt-12 pb-8 px-6 text-center">
          <h1 className="text-2xl font-semibold text-eims-text tracking-tight mb-2">Service Evaluation</h1>
          <p className="text-eims-text-secondary text-sm">Please rate your recent experience.</p>
        </div>

        {/* Form Card */}
        <div className="bg-eims-surface border border-eims-border rounded-t-3xl sm:rounded-2xl flex-1 sm:flex-none p-6 sm:p-8 shadow-sm flex flex-col">
          <div className="mb-8">
            <h2 className="font-medium text-eims-text text-lg">{session.title}</h2>
            {session.engineer_name && (
              <p className="text-sm text-eims-text-secondary mt-1">Engineer: {session.engineer_name}</p>
            )}
            {session.description && (
              <p className="text-sm text-eims-text-muted mt-3 p-3 bg-eims-surface-subtle rounded-lg border border-eims-border/50">
                {session.description}
              </p>
            )}
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col flex-1">
            {/* Responder Details */}
            <div className="mb-6 grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-eims-text-secondary mb-1.5">Your Name (Optional)</label>
                <input 
                  type="text" 
                  value={responderName}
                  onChange={(e) => setResponderName(e.target.value)}
                  className="w-full px-3 py-2.5 bg-eims-bg border border-eims-border rounded-lg focus:outline-none focus:border-eims-accent text-sm transition-colors"
                  placeholder="e.g. Somchai"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-eims-text-secondary mb-1.5">Department (Optional)</label>
                <input 
                  type="text" 
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  className="w-full px-3 py-2.5 bg-eims-bg border border-eims-border rounded-lg focus:outline-none focus:border-eims-accent text-sm transition-colors"
                  placeholder="e.g. HR"
                />
              </div>
            </div>

            {/* Dynamic Star Rating Components */}
            <div className="flex flex-col gap-6 mb-8">
              {session?.evaluation_questions && (() => {
                const groupedQs = session.evaluation_questions.reduce((acc, q) => {
                  if (!acc[q.category]) acc[q.category] = [];
                  acc[q.category].push(q);
                  return acc;
                }, {} as Record<string, typeof session.evaluation_questions>);

                return Object.entries(groupedQs).map(([category, qs]) => (
                  <div key={category} className="bg-eims-bg border border-eims-border/50 rounded-xl p-4">
                    <h3 className="text-[11px] uppercase tracking-wider font-semibold text-eims-accent mb-4 border-b border-eims-border/50 pb-2">{category}</h3>
                    <div className="flex flex-col gap-5">
                      {qs.map((q, idx) => (
                        <div key={q.id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                          <label className="text-sm font-medium text-eims-text-secondary leading-snug">
                            {idx + 1}. {q.label} <span className="text-red-400">*</span>
                          </label>
                          <div className="flex items-center gap-1.5 shrink-0">
                            {[1, 2, 3, 4, 5].map((star) => (
                              <button
                                key={star}
                                type="button"
                                onClick={() => setRatings(prev => ({ ...prev, [q.id]: star }))}
                                onMouseEnter={() => setHoverRatings(prev => ({ ...prev, [q.id]: star }))}
                                onMouseLeave={() => setHoverRatings(prev => ({ ...prev, [q.id]: 0 }))}
                                className="p-1 focus:outline-none transition-transform hover:scale-110 active:scale-95"
                              >
                                <Star
                                  className={`w-7 h-7 sm:w-6 sm:h-6 transition-colors ${
                                    ((hoverRatings[q.id] || ratings[q.id] || 0)) >= star
                                      ? "fill-yellow-400 text-yellow-400"
                                      : "fill-transparent text-eims-border hover:text-eims-text-muted"
                                  }`}
                                />
                              </button>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ));
              })()}
            </div>

            {/* Comments Area */}
            <div className="mb-8">
              <label className="block text-sm font-medium text-eims-text-secondary mb-2">
                Additional Comments (Optional)
              </label>
              <textarea
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                placeholder="Tell us what went well or what could be improved..."
                className="w-full px-4 py-3 bg-eims-bg border border-eims-border rounded-xl focus:outline-none focus:border-eims-accent focus:ring-1 focus:ring-eims-accent/50 text-sm min-h-[120px] transition-all"
              />
            </div>

            <div className="mt-auto pt-4">
              <button
                type="submit"
                disabled={isSubmitting || (session?.evaluation_questions ? Object.keys(ratings).length !== session.evaluation_questions.length : true)}
                className="w-full bg-eims-accent text-white font-medium py-3.5 rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center"
              >
                {isSubmitting ? <Loader2 className="w-5 h-5 animate-spin" /> : "Submit Evaluation"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
