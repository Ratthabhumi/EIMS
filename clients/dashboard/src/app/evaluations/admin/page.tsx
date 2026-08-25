"use client";

import { useState, useEffect } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Plus, X, Share2, Star, Search, ArrowLeft, Trash2, Edit2 } from "lucide-react";
import Link from "next/link";
import toast from "react-hot-toast";

interface ServiceSession {
  session_id: string;
  title: string;
  description: string;
  customer_name: string;
  engineer_name: string;
  evaluation_questions?: Question[];
  created_at: string;
}

interface Question {
  id: string;
  label: string;
  category: string;
}

const DEFAULT_QUESTIONS: Question[] = [
  { id: 'q1', label: 'ความรวดเร็วในการแก้ไขปัญหา (Resolution Time & Efficiency)', category: 'Support' },
  { id: 'q2', label: 'ความเป็นมืออาชีพและการให้บริการ (Professionalism & Service Quality)', category: 'Support' },
  { id: 'q3', label: 'การแก้ไขปัญหาได้สำเร็จและครบถ้วน (Resolution Quality)', category: 'Support' },
  { id: 'q4', label: 'ความตรงต่อเวลาในการส่งมอบงาน (Punctuality)', category: 'Implement' },
  { id: 'q5', label: 'คุณภาพของการติดตั้งระบบ (Implementation Quality)', category: 'Implement' },
  { id: 'q6', label: 'การถ่ายทอดความรู้และการสอนใช้งาน (Knowledge Transfer)', category: 'Implement' },
  { id: 'q7', label: 'ความพึงพอใจโดยรวมต่อการให้บริการ (Overall Satisfaction)', category: 'General' }
];

export default function EvaluationAdmin() {
  const [sessions, setSessions] = useState<ServiceSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editSessionId, setEditSessionId] = useState<string | null>(null);
  const [selectedSession, setSelectedSession] = useState<ServiceSession | null>(null);

  // Search & Sort State
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("date-desc");

  // Form State
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [customer, setCustomer] = useState("");
  const [engineers, setEngineers] = useState<string[]>([]);
  const [engineerInput, setEngineerInput] = useState("");
  const [questions, setQuestions] = useState<Question[]>(DEFAULT_QUESTIONS);
  const [newQuestionLabel, setNewQuestionLabel] = useState("");
  const [newQuestionCategory, setNewQuestionCategory] = useState("General");

  const fetchSessions = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/evaluations/sessions?limit=100");
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
      }
    } catch (err) {
      console.error(err);
      toast.error("Failed to fetch sessions");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  const openCreateModal = () => {
    setEditSessionId(null);
    setTitle(""); setDesc(""); setCustomer(""); setEngineers([]); setEngineerInput(""); setQuestions(DEFAULT_QUESTIONS);
    setIsModalOpen(true);
  };

  const openEditModal = (session: ServiceSession) => {
    setEditSessionId(session.session_id);
    setTitle(session.title);
    setDesc(session.description);
    setCustomer(session.customer_name);
    setEngineers(session.engineer_name ? session.engineer_name.split(', ') : []);
    setEngineerInput("");
    setQuestions(session.evaluation_questions || DEFAULT_QUESTIONS);
    setIsModalOpen(true);
  };

  const handleSaveSession = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const isEdit = editSessionId !== null;
      const url = isEdit ? `http://localhost:8000/api/v1/evaluations/sessions/${editSessionId}` : "http://localhost:8000/api/v1/evaluations/sessions";
      const method = isEdit ? "PUT" : "POST";
      const toastId = toast.loading(isEdit ? "Updating session..." : "Creating session...");
      
      const res = await fetch(url, {
        method,
        headers: { 
          "Content-Type": "application/json",
          "Authorization": "Bearer EIMS-ADMIN-TOKEN"
        },
        body: JSON.stringify({
          title,
          description: desc,
          customer_name: customer,
          engineer_name: [...engineers, ...(engineerInput.trim() ? [engineerInput.trim()] : [])].join(", ") || "",
          evaluation_questions: questions
        })
      });
      if (res.ok) {
        toast.success(isEdit ? "Session updated successfully" : "Session created successfully", { id: toastId });
        setIsModalOpen(false);
        fetchSessions();
      } else {
        toast.error("Failed to save session", { id: toastId });
      }
    } catch (err) {
      console.error(err);
      toast.error("Network error occurred");
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    if (!confirm("Are you sure you want to delete this session? This will also delete all of its evaluation responses.")) return;
    const toastId = toast.loading("Deleting session...");
    try {
      const res = await fetch(`http://localhost:8000/api/v1/evaluations/sessions/${sessionId}`, {
        method: "DELETE",
        headers: {
          "Authorization": "Bearer EIMS-ADMIN-TOKEN"
        }
      });
      if (res.ok) {
        toast.success("Session deleted successfully", { id: toastId });
        fetchSessions();
      } else {
        toast.error("Failed to delete session", { id: toastId });
      }
    } catch (err) {
      console.error(err);
      toast.error("Network error occurred", { id: toastId });
    }
  };

  const generateEvalLink = (sessionId: string) => {
    return `${window.location.origin}/evaluate/${sessionId}`;
  };

  return (
    <div className="animate-fade-in flex flex-col gap-8 pb-12">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/" className="p-2 rounded-full hover:bg-eims-surface-subtle text-eims-text-secondary hover:text-eims-text transition-colors shrink-0">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-[28px] font-semibold tracking-tight text-eims-text">Service Evaluations</h1>
            <p className="text-eims-text-secondary text-sm mt-1">Generate QR codes and track post-service customer satisfaction.</p>
          </div>
        </div>
        <button 
          onClick={openCreateModal}
          className="flex items-center gap-2 bg-eims-accent text-white px-4 py-2 rounded-md text-sm font-medium hover:opacity-90 transition-opacity"
        >
          <Plus className="w-4 h-4" /> New Session
        </button>
      </header>

      {/* Main List */}
      <div className="surface-card overflow-hidden">
        <div className="p-4 border-b border-eims-border flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-eims-surface/50">
          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-eims-text-muted" />
            <input 
              type="text" 
              placeholder="Search sessions..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-1.5 text-sm border border-eims-border rounded-md bg-eims-bg focus:outline-none focus:border-eims-accent transition-colors"
            />
          </div>
          <select 
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="py-1.5 px-3 text-sm border border-eims-border rounded-md bg-eims-bg focus:outline-none focus:border-eims-accent w-full sm:w-auto"
          >
            <option value="date-desc">Newest First</option>
            <option value="date-asc">Oldest First</option>
            <option value="title-asc">Title (A-Z)</option>
            <option value="title-desc">Title (Z-A)</option>
          </select>
        </div>

        {loading ? (
          <div className="p-12 text-center text-eims-text-muted text-sm">Loading sessions...</div>
        ) : sessions.length === 0 ? (
          <div className="p-16 text-center flex flex-col items-center justify-center">
            <Star className="w-8 h-8 text-eims-text-muted mb-4 opacity-50" />
            <h3 className="text-eims-text font-medium mb-1">No Service Sessions</h3>
            <p className="text-eims-text-secondary text-sm">Create a session to generate a QR code for customer evaluation.</p>
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-eims-border text-eims-text-muted bg-eims-surface-subtle/30">
                <th className="font-medium py-3 px-5">Title</th>
                <th className="font-medium py-3 px-5">Customer</th>
                <th className="font-medium py-3 px-5">Engineer</th>
                <th className="font-medium py-3 px-5">Date</th>
                <th className="font-medium py-3 px-5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-eims-border">
              {(() => {
                const filteredAndSorted = sessions
                  .filter(s => 
                    s.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
                    (s.customer_name && s.customer_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
                    (s.engineer_name && s.engineer_name.toLowerCase().includes(searchQuery.toLowerCase()))
                  )
                  .sort((a, b) => {
                    if (sortBy === "date-desc") return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
                    if (sortBy === "date-asc") return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
                    if (sortBy === "title-asc") return a.title.localeCompare(b.title);
                    if (sortBy === "title-desc") return b.title.localeCompare(a.title);
                    return 0;
                  });

                if (filteredAndSorted.length === 0) {
                  return (
                    <tr>
                      <td colSpan={5} className="py-12 text-center text-eims-text-muted text-sm">
                        No sessions match your search criteria.
                      </td>
                    </tr>
                  );
                }

                return filteredAndSorted.map(session => (
                  <tr key={session.session_id} className="hover:bg-eims-surface-subtle/50 transition-colors">
                    <td className="py-4 px-5">
                      <Link href={`/evaluations/admin/${session.session_id}`} className="font-medium text-eims-accent hover:underline block">
                        {session.title}
                      </Link>
                      <div className="text-xs text-eims-text-muted mt-0.5 truncate max-w-[250px]">{session.description}</div>
                    </td>
                    <td className="py-4 px-5 text-eims-text-secondary">{session.customer_name || "-"}</td>
                    <td className="py-4 px-5 text-eims-text-secondary">{session.engineer_name || "-"}</td>
                    <td className="py-4 px-5 text-eims-text-secondary">
                      {new Date(session.created_at).toLocaleDateString()}
                    </td>
                  <td className="py-4 px-5">
                    <div className="flex items-center justify-end gap-2">
                      <button 
                        onClick={() => openEditModal(session)}
                        className="inline-flex items-center justify-center p-1.5 rounded bg-eims-surface-subtle text-eims-text border border-eims-border hover:bg-eims-border/40 hover:text-blue-400 transition-colors"
                        title="Edit Session"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button 
                        onClick={() => handleDeleteSession(session.session_id)}
                        className="inline-flex items-center justify-center p-1.5 rounded bg-eims-surface-subtle text-eims-text border border-eims-border hover:bg-eims-border/40 hover:text-red-400 transition-colors"
                        title="Delete Session"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                      <button 
                        onClick={() => setSelectedSession(session)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-eims-surface-subtle text-eims-text border border-eims-border hover:bg-eims-border/40 transition-colors text-xs font-medium ml-1"
                      >
                        <Share2 className="w-3.5 h-3.5" /> Get QR
                      </button>
                    </div>
                  </td>
                </tr>
                ));
              })()}
            </tbody>
          </table>
        )}
      </div>

      {/* New Session Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in p-4">
          <div className="bg-eims-surface border border-eims-border rounded-lg shadow-xl w-full max-w-md overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-eims-border flex justify-between items-center">
              <h2 className="font-semibold text-eims-text">{editSessionId ? "Edit Service Session" : "Create Service Session"}</h2>
              <button onClick={() => setIsModalOpen(false)} className="text-eims-text-muted hover:text-eims-text">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSaveSession} className="p-6 flex flex-col gap-4">
              <div>
                <label className="block text-xs font-medium text-eims-text-secondary mb-1.5">Service Title *</label>
                <input required value={title} onChange={e => setTitle(e.target.value)} type="text" className="w-full px-3 py-2 border border-eims-border rounded bg-eims-bg focus:outline-none focus:border-eims-accent text-sm" placeholder="e.g. Network Troubleshooting" />
              </div>
              <div>
                <label className="block text-xs font-medium text-eims-text-secondary mb-1.5">Description</label>
                <textarea value={desc} onChange={e => setDesc(e.target.value)} className="w-full px-3 py-2 border border-eims-border rounded bg-eims-bg focus:outline-none focus:border-eims-accent text-sm min-h-[80px]" placeholder="Brief details about what was done..." />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-eims-text-secondary mb-1.5">Customer Name</label>
                  <input value={customer} onChange={e => setCustomer(e.target.value)} type="text" className="w-full px-3 py-2 border border-eims-border rounded bg-eims-bg focus:outline-none focus:border-eims-accent text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-eims-text-secondary mb-1.5">Engineer Names (Press Enter)</label>
                  <div className="flex flex-col gap-2">
                    {engineers.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {engineers.map(eng => (
                          <span key={eng} className="inline-flex items-center gap-1 px-2 py-1 bg-eims-surface-subtle text-eims-text-secondary text-xs rounded border border-eims-border">
                            {eng}
                            <X className="w-3 h-3 cursor-pointer hover:text-red-400" onClick={() => setEngineers(engineers.filter(e => e !== eng))} />
                          </span>
                        ))}
                      </div>
                    )}
                    <input 
                      value={engineerInput} 
                      onChange={e => setEngineerInput(e.target.value)} 
                      onKeyDown={e => {
                        if (e.key === 'Enter' || e.key === ',') {
                          e.preventDefault();
                          const val = engineerInput.trim().replace(/,/g, '');
                          if (val && !engineers.includes(val)) {
                            setEngineers([...engineers, val]);
                            setEngineerInput("");
                          }
                        }
                      }}
                      type="text" 
                      className="w-full px-3 py-2 border border-eims-border rounded bg-eims-bg focus:outline-none focus:border-eims-accent text-sm" 
                      placeholder="Type name & press Enter"
                    />
                  </div>
                </div>
              </div>
              
              <div className="pt-4 border-t border-eims-border">
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-xs font-medium text-eims-text-secondary">Evaluation Topics</label>
                  <span className="text-[10px] text-eims-text-muted">{questions.length} questions</span>
                </div>
                <div className="flex flex-col gap-2 max-h-48 overflow-y-auto pr-1">
                  {questions.map((q, idx) => (
                    <div key={q.id} className="flex items-start justify-between bg-eims-surface-subtle p-2 rounded border border-eims-border gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="text-[10px] text-eims-accent font-medium mb-0.5 uppercase tracking-wider">{q.category}</div>
                        <div className="text-xs text-eims-text truncate">{idx + 1}. {q.label}</div>
                      </div>
                      <button type="button" onClick={() => setQuestions(questions.filter(x => x.id !== q.id))} className="text-eims-text-muted hover:text-red-400 p-1">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                  {questions.length === 0 && <div className="text-xs text-eims-text-muted italic py-2 text-center">No questions added.</div>}
                </div>
                
                <div className="mt-3 flex gap-2">
                  <select 
                    value={newQuestionCategory} 
                    onChange={e => setNewQuestionCategory(e.target.value)}
                    className="w-24 px-2 py-1.5 border border-eims-border rounded bg-eims-bg focus:outline-none focus:border-eims-accent text-xs"
                  >
                    <option value="General">General</option>
                    <option value="Support">Support</option>
                    <option value="Implement">Implement</option>
                  </select>
                  <input 
                    type="text" 
                    value={newQuestionLabel}
                    onChange={e => setNewQuestionLabel(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        if (newQuestionLabel.trim()) {
                          setQuestions([...questions, { id: `q${Date.now()}`, label: newQuestionLabel.trim(), category: newQuestionCategory }]);
                          setNewQuestionLabel("");
                        }
                      }
                    }}
                    placeholder="Add a new question..."
                    className="flex-1 px-2 py-1.5 border border-eims-border rounded bg-eims-bg focus:outline-none focus:border-eims-accent text-xs"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      if (newQuestionLabel.trim()) {
                        setQuestions([...questions, { id: `q${Date.now()}`, label: newQuestionLabel.trim(), category: newQuestionCategory }]);
                        setNewQuestionLabel("");
                      }
                    }}
                    className="px-3 py-1.5 bg-eims-surface-subtle border border-eims-border text-eims-text-secondary text-xs rounded hover:bg-eims-border transition-colors"
                  >
                    Add
                  </button>
                </div>
              </div>

              <div className="mt-4 flex justify-end gap-3 pt-4 border-t border-eims-border">
                <button type="button" onClick={() => setIsModalOpen(false)} className="px-4 py-2 text-sm font-medium text-eims-text-secondary hover:bg-eims-surface-subtle rounded transition-colors">Cancel</button>
                <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-eims-accent rounded hover:opacity-90 transition-opacity">
                  {editSessionId ? "Save Changes" : "Create Session"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* QR Code Modal */}
      {selectedSession && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in p-4">
          <div className="bg-eims-surface border border-eims-border rounded-lg shadow-xl w-full max-w-sm overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-eims-border flex justify-between items-center bg-eims-surface-subtle/50">
              <h2 className="font-semibold text-eims-text text-sm">Customer Evaluation QR</h2>
              <button onClick={() => setSelectedSession(null)} className="text-eims-text-muted hover:text-eims-text">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-8 flex flex-col items-center text-center">
              <div className="bg-white p-4 rounded-xl shadow-sm border border-eims-border mb-6">
                <QRCodeSVG value={generateEvalLink(selectedSession.session_id)} size={200} level="H" />
              </div>
              <h3 className="font-medium text-eims-text">{selectedSession.title}</h3>
              <p className="text-xs text-eims-text-muted mt-1 mb-6 break-all max-w-[280px]">
                {generateEvalLink(selectedSession.session_id)}
              </p>
              
              <button 
                onClick={() => {
                  navigator.clipboard.writeText(generateEvalLink(selectedSession.session_id));
                  alert("Link copied to clipboard!");
                }}
                className="w-full py-2.5 rounded-md border border-eims-border bg-eims-bg text-eims-text text-sm font-medium hover:bg-eims-surface-subtle transition-colors flex items-center justify-center gap-2"
              >
                <Share2 className="w-4 h-4" /> Copy Link
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
