"use client";

import { useState, useEffect } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Plus, X, Share2, Star, Download, Search, CheckCircle } from "lucide-react";

interface ServiceSession {
  session_id: string;
  title: string;
  description: string;
  customer_name: string;
  engineer_name: string;
  created_at: string;
}

export default function EvaluationAdmin() {
  const [sessions, setSessions] = useState<ServiceSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedSession, setSelectedSession] = useState<ServiceSession | null>(null);

  // Form State
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [customer, setCustomer] = useState("");
  const [engineer, setEngineer] = useState("");

  const fetchSessions = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/evaluations/sessions");
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  const handleCreateSession = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch("http://localhost:8000/api/v1/evaluations/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          description: desc,
          customer_name: customer,
          engineer_name: engineer
        })
      });
      if (res.ok) {
        setIsModalOpen(false);
        setTitle(""); setDesc(""); setCustomer(""); setEngineer("");
        fetchSessions();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const generateEvalLink = (sessionId: string) => {
    return `${window.location.origin}/evaluate/${sessionId}`;
  };

  return (
    <div className="animate-fade-in flex flex-col gap-8 pb-12">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-[28px] font-semibold tracking-tight text-eims-text mb-1">Service Evaluations</h1>
          <p className="text-eims-text-secondary text-sm">Generate QR codes and track post-service customer satisfaction.</p>
        </div>
        <button 
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 bg-eims-accent text-white px-4 py-2 rounded-md text-sm font-medium hover:opacity-90 transition-opacity"
        >
          <Plus className="w-4 h-4" /> New Session
        </button>
      </header>

      {/* Main List */}
      <div className="surface-card overflow-hidden">
        <div className="p-4 border-b border-eims-border flex justify-between items-center bg-eims-surface/50">
          <div className="relative w-72">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-eims-text-muted" />
            <input 
              type="text" 
              placeholder="Search sessions..." 
              className="w-full pl-9 pr-4 py-1.5 text-sm border border-eims-border rounded-md bg-eims-bg focus:outline-none focus:border-eims-accent transition-colors"
            />
          </div>
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
              {sessions.map(session => (
                <tr key={session.session_id} className="hover:bg-eims-surface-subtle/50 transition-colors">
                  <td className="py-4 px-5">
                    <div className="font-medium text-eims-text">{session.title}</div>
                    <div className="text-xs text-eims-text-muted mt-0.5 truncate max-w-[250px]">{session.description}</div>
                  </td>
                  <td className="py-4 px-5 text-eims-text-secondary">{session.customer_name || "-"}</td>
                  <td className="py-4 px-5 text-eims-text-secondary">{session.engineer_name || "-"}</td>
                  <td className="py-4 px-5 text-eims-text-secondary">
                    {new Date(session.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-4 px-5 text-right">
                    <button 
                      onClick={() => setSelectedSession(session)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-eims-surface-subtle text-eims-text border border-eims-border hover:bg-eims-border/40 transition-colors text-xs font-medium"
                    >
                      <Share2 className="w-3.5 h-3.5" /> Get QR
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* New Session Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in p-4">
          <div className="bg-eims-surface border border-eims-border rounded-lg shadow-xl w-full max-w-md overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-eims-border flex justify-between items-center">
              <h2 className="font-semibold text-eims-text">Create Service Session</h2>
              <button onClick={() => setIsModalOpen(false)} className="text-eims-text-muted hover:text-eims-text">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateSession} className="p-6 flex flex-col gap-4">
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
                  <label className="block text-xs font-medium text-eims-text-secondary mb-1.5">Engineer Name</label>
                  <input value={engineer} onChange={e => setEngineer(e.target.value)} type="text" className="w-full px-3 py-2 border border-eims-border rounded bg-eims-bg focus:outline-none focus:border-eims-accent text-sm" />
                </div>
              </div>
              <div className="mt-4 flex justify-end gap-3">
                <button type="button" onClick={() => setIsModalOpen(false)} className="px-4 py-2 text-sm font-medium text-eims-text-secondary hover:bg-eims-surface-subtle rounded transition-colors">Cancel</button>
                <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-eims-accent rounded hover:opacity-90 transition-opacity">Create Session</button>
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
