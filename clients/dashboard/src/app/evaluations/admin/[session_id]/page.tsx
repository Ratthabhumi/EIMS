"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Star, Search, Filter, Trash2 } from "lucide-react";
import Link from "next/link";
import toast from "react-hot-toast";

interface SessionDetails {
  session_id: string;
  title: string;
  description: string;
  customer_name: string;
  engineer_name: string;
  evaluation_questions: { id: string; label: string; category: string }[];
  created_at: string;
}

interface EvaluationResponse {
  evaluation_id: string;
  session_id: string;
  responder_name: string | null;
  department: string | null;
  rating_scores: { question_id: string; score: number }[];
  average_score: number;
  feedback_comments: string | null;
  submitted_at: string;
}

export default function EvaluationDetails() {
  const params = useParams();
  const sessionId = params.session_id as string;

  const [session, setSession] = useState<SessionDetails | null>(null);
  const [responses, setResponses] = useState<EvaluationResponse[]>([]);
  const [loading, setLoading] = useState(true);

  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("date-desc");
  const [departmentFilter, setDepartmentFilter] = useState("All");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [sessionRes, responsesRes] = await Promise.all([
          fetch(`http://localhost:8000/api/v1/evaluations/sessions/${sessionId}`),
          fetch(`http://localhost:8000/api/v1/evaluations/sessions/${sessionId}/responses`)
        ]);

        if (sessionRes.ok) setSession(await sessionRes.json());
        if (responsesRes.ok) setResponses(await responsesRes.json());
      } catch (err) {
        console.error(err);
        toast.error("Failed to load details");
      } finally {
        setLoading(false);
      }
    };

    if (sessionId) fetchData();
  }, [sessionId]);

  const handleDeleteResponse = async (evaluationId: string) => {
    if (!confirm("Are you sure you want to delete this response?")) return;
    const toastId = toast.loading("Deleting response...");
    try {
      const res = await fetch(`http://localhost:8000/api/v1/evaluations/responses/${evaluationId}`, {
        method: "DELETE",
        headers: {
          "Authorization": "Bearer EIMS-ADMIN-TOKEN"
        }
      });
      if (res.ok) {
        toast.success("Response deleted successfully", { id: toastId });
        setResponses(prev => prev.filter(r => r.evaluation_id !== evaluationId));
      } else {
        toast.error("Failed to delete response", { id: toastId });
      }
    } catch (err) {
      console.error(err);
      toast.error("Network error occurred", { id: toastId });
    }
  };

  const departments = Array.from(new Set(responses.map(r => r.department))).filter(Boolean).sort();

  const filteredResponses = responses.filter(r => {
    const matchesSearch = 
      (r.responder_name?.toLowerCase().includes(searchQuery.toLowerCase()) || "") || 
      (r.department?.toLowerCase().includes(searchQuery.toLowerCase()) || "") ||
      (r.feedback_comments?.toLowerCase().includes(searchQuery.toLowerCase()) || "");
    
    const matchesDept = departmentFilter === "All" || r.department === departmentFilter;

    return matchesSearch && matchesDept;
  });

  const sortedResponses = [...filteredResponses].sort((a, b) => {
    if (sortBy === "avg-desc") return (b.average_score || 0) - (a.average_score || 0);
    if (sortBy === "avg-asc") return (a.average_score || 0) - (b.average_score || 0);
    if (sortBy === "date-desc") return new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime();
    if (sortBy === "date-asc") return new Date(a.submitted_at).getTime() - new Date(b.submitted_at).getTime();
    if (sortBy === "name-asc") return (a.responder_name || "Anonymous").localeCompare(b.responder_name || "Anonymous");
    return 0;
  });

  const averageScore = responses.length > 0 
    ? (responses.reduce((acc, curr) => acc + (curr.average_score || 0), 0) / responses.length).toFixed(1)
    : "0.0";

  if (loading) {
    return <div className="p-12 text-center text-eims-text-muted">Loading details...</div>;
  }

  if (!session) {
    return <div className="p-12 text-center text-red-400">Session not found.</div>;
  }

  return (
    <div className="animate-fade-in flex flex-col gap-8 pb-12">
      <header className="flex items-center gap-4">
        <Link href="/evaluations/admin" className="p-2 rounded-full hover:bg-eims-surface-subtle text-eims-text-secondary hover:text-eims-text transition-colors shrink-0">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-[28px] font-semibold tracking-tight text-eims-text">{session.title}</h1>
          <p className="text-eims-text-secondary text-sm mt-1">Detailed evaluation responses and analytics.</p>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {/* Analytics Sidebar */}
        <div className="md:col-span-1 space-y-6">
          <div className="surface-card p-6 flex flex-col items-center text-center">
            <h3 className="text-sm font-medium text-eims-text-secondary mb-2">Average Score</h3>
            <div className="text-4xl font-bold text-eims-accent mb-2">{averageScore}</div>
            <div className="flex gap-1 text-yellow-400 mb-2">
              {[1, 2, 3, 4, 5].map((star) => (
                <Star key={star} className={`w-5 h-5 ${parseFloat(averageScore) >= star ? "fill-yellow-400" : "fill-transparent text-eims-border"}`} />
              ))}
            </div>
            <p className="text-xs text-eims-text-muted">Based on {responses.length} responses</p>
          </div>
          
          <div className="surface-card p-6">
            <h3 className="text-sm font-medium text-eims-text mb-4">Session Info</h3>
            <dl className="space-y-4 text-sm">
              <div>
                <dt className="text-eims-text-muted text-xs">Engineers</dt>
                <dd className="text-eims-text font-medium mt-0.5">{session.engineer_name || "N/A"}</dd>
              </div>
              <div>
                <dt className="text-eims-text-muted text-xs">Target Customer</dt>
                <dd className="text-eims-text font-medium mt-0.5">{session.customer_name || "N/A"}</dd>
              </div>
              <div>
                <dt className="text-eims-text-muted text-xs">Created At</dt>
                <dd className="text-eims-text font-medium mt-0.5">{new Date(session.created_at).toLocaleDateString()}</dd>
              </div>
            </dl>
          </div>
        </div>

        {/* Responses Main List */}
        <div className="md:col-span-3 surface-card flex flex-col">
          <div className="p-4 border-b border-eims-border flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-eims-surface/50">
            <h3 className="font-medium text-eims-text">Recent Responses</h3>
            <div className="flex gap-3 w-full sm:w-auto">
              <div className="relative flex-1 sm:w-64">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-eims-text-muted" />
                <input 
                  type="text" 
                  placeholder="Search name, comment..." 
                  className="w-full pl-9 pr-4 py-1.5 text-sm border border-eims-border rounded-md bg-eims-bg focus:outline-none focus:border-eims-accent"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <select 
                value={departmentFilter}
                onChange={(e) => setDepartmentFilter(e.target.value)}
                className="py-1.5 px-3 text-sm border border-eims-border rounded-md bg-eims-bg focus:outline-none focus:border-eims-accent"
              >
                <option value="All">All Depts</option>
                {departments.map(d => <option key={d as string} value={d as string}>{d}</option>)}
              </select>
              <select 
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="py-1.5 px-3 text-sm border border-eims-border rounded-md bg-eims-bg focus:outline-none focus:border-eims-accent"
              >
                <option value="date-desc">Newest First</option>
                <option value="date-asc">Oldest First</option>
                <option value="avg-desc">Highest Rating</option>
                <option value="avg-asc">Lowest Rating</option>
              </select>
            </div>
          </div>

          <div className="flex-1">
            {sortedResponses.length > 0 ? (
              <ul className="divide-y divide-eims-border">
                {sortedResponses.map((res) => (
                  <li key={res.evaluation_id} className="p-5 hover:bg-eims-surface-subtle/30 transition-colors">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <div className="font-medium text-eims-text flex items-center gap-2">
                          {res.responder_name || "Anonymous"}
                          {res.department && <span className="px-2 py-0.5 bg-eims-surface border border-eims-border rounded text-[10px] text-eims-text-secondary uppercase">{res.department}</span>}
                        </div>
                        <div className="text-xs text-eims-text-muted mt-1">{new Date(res.submitted_at).toLocaleString()}</div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="flex text-yellow-400">
                          {[1, 2, 3, 4, 5].map((star) => (
                            <Star key={star} className={`w-4 h-4 ${Math.round(res.average_score) >= star ? "fill-yellow-400 text-yellow-400" : "fill-transparent text-eims-border"}`} />
                          ))}
                          <span className="ml-2 text-xs font-semibold text-eims-text">{res.average_score?.toFixed(1)}</span>
                        </div>
                        <button 
                          onClick={() => handleDeleteResponse(res.evaluation_id)}
                          className="text-eims-text-muted hover:text-red-400 transition-colors p-1 rounded hover:bg-eims-surface-subtle"
                          title="Delete Response"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                    {res.rating_scores && session.evaluation_questions && (
                      <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-[11px] bg-eims-bg border border-eims-border/50 rounded p-3">
                        {res.rating_scores.map(rs => {
                          const q = session.evaluation_questions.find(x => x.id === rs.question_id);
                          return (
                            <div key={rs.question_id} className="flex justify-between items-center">
                              <span className="text-eims-text-secondary truncate pr-2">{q ? q.label : rs.question_id}</span>
                              <div className="flex gap-0.5 text-yellow-400 shrink-0">
                                {[1, 2, 3, 4, 5].map((star) => (
                                  <Star key={star} className={`w-2.5 h-2.5 ${rs.score >= star ? "fill-yellow-400 text-yellow-400" : "fill-transparent text-eims-border"}`} />
                                ))}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                    {res.feedback_comments && (
                      <p className="mt-3 text-sm text-eims-text-secondary bg-eims-bg border border-eims-border/50 rounded-lg p-3 italic">
                        "{res.feedback_comments}"
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="p-12 text-center text-eims-text-muted text-sm">
                No responses found matching criteria.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
