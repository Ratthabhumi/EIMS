import { useState, useEffect } from "react";
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell
} from "recharts";
import { FileText, AlertTriangle, Clock } from "lucide-react";

const COLORS = ["#7B8F9F", "#6B9B7B", "#C2856E", "#8A997B", "#BF6B6A", "#9C9993", "#6E6B65"];

interface Stats {
  totalLogs: number;
  criticalErrors: number;
  avgSearchTimeSec: number;
  dailyTrends: { date: string; count: number }[];
  categoryStats?: { name: string; value: number }[];
  providerStats?: { name: string; value: number }[];
}

interface AnalyzerDashboardProps {
  refreshTrigger?: number;
  avgSearchTimeMs?: number | null;
}

export default function AnalyzerDashboard({ refreshTrigger = 0, avgSearchTimeMs }: AnalyzerDashboardProps) {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/v1/history/stats");
        if (res.ok) {
          const data = await res.json();
          setStats(data);
        }
      } catch (e) {
        console.error("Failed to fetch stats", e);
      }
    };
    fetchStats();
  }, [refreshTrigger]);

  if (!stats) return null;

  const categories = (stats.categoryStats && stats.categoryStats.length > 0)
    ? stats.categoryStats
    : (stats.providerStats || []);

  return (
    <div className="w-full space-y-4">
      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-eims-surface border border-eims-border rounded-xl p-5 flex items-center justify-between shadow-sm">
          <div>
            <p className="text-eims-text-secondary text-xs font-medium uppercase tracking-wider mb-1">Total Logs Analyzed</p>
            <h3 className="text-2xl font-bold text-eims-text">{stats.totalLogs}</h3>
          </div>
          <div className="p-2.5 bg-sky-500/10 border border-sky-500/20 text-sky-500/80 dark:text-[#7EA8BE] rounded-lg">
            <FileText size={20} />
          </div>
        </div>

        <div className="bg-eims-surface border border-eims-border rounded-xl p-5 flex items-center justify-between shadow-sm">
          <div>
            <p className="text-eims-text-secondary text-xs font-medium uppercase tracking-wider mb-1">Critical Errors</p>
            <h3 className="text-2xl font-bold text-eims-text">{stats.criticalErrors}</h3>
          </div>
          <div className="p-2.5 bg-rose-500/10 border border-rose-500/20 text-rose-500/80 dark:text-[#D9777F] rounded-lg">
            <AlertTriangle size={20} />
          </div>
        </div>

        <div className="bg-eims-surface border border-eims-border rounded-xl p-5 flex items-center justify-between shadow-sm">
          <div>
            <p className="text-eims-text-secondary text-xs font-medium uppercase tracking-wider mb-1">Avg Search Time</p>
            <h3 className="text-2xl font-bold text-eims-text">
              {avgSearchTimeMs !== null && avgSearchTimeMs !== undefined
                ? `${avgSearchTimeMs < 1 ? avgSearchTimeMs.toFixed(1) : Math.round(avgSearchTimeMs)} ms`
                : "—"}
            </h3>
          </div>
          <div className="p-2.5 bg-teal-500/10 border border-teal-500/20 text-teal-500/80 dark:text-[#78B096] rounded-lg">
            <Clock size={20} />
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-eims-surface border border-eims-border rounded-xl p-5 shadow-sm h-72">
          <h3 className="text-xs font-semibold text-eims-text uppercase tracking-wider mb-4">Daily Trends (Last 7 Days)</h3>
          <ResponsiveContainer width="100%" height="80%">
            <LineChart data={stats.dailyTrends}>
              <CartesianGrid strokeDasharray="3 3" stroke="#3A3834" opacity={0.25} />
              <XAxis dataKey="date" stroke="#716E66" fontSize={11} tickLine={false} />
              <YAxis stroke="#716E66" fontSize={11} tickLine={false} allowDecimals={false} />
              <Tooltip 
                contentStyle={{ backgroundColor: "#1C1B19", borderColor: "#3A3834", color: "#F1EFEB", borderRadius: '8px', fontSize: '12px' }}
                itemStyle={{ color: "#7B8F9F" }}
              />
              <Line type="monotone" dataKey="count" stroke="#7B8F9F" strokeWidth={2.5} dot={{ r: 3.5, fill: "#7B8F9F" }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-eims-surface border border-eims-border rounded-xl p-5 shadow-sm h-72 flex flex-col justify-between overflow-hidden relative">
          <div className="flex items-center justify-between mb-1 shrink-0">
            <h3 className="text-xs font-semibold text-eims-text uppercase tracking-wider">Event Types by Category</h3>
            <span className="text-[11px] text-eims-text-muted font-medium">
              {categories.length} Categories · {stats.totalLogs} Analyzed
            </span>
          </div>
          
          <div className="flex-1 min-h-0 w-full flex items-center justify-center">
            {categories.length > 0 ? (
              <ResponsiveContainer width="100%" height="95%">
                <BarChart
                  layout="vertical"
                  data={categories}
                  margin={{ top: 4, right: 20, left: 10, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#3A3834" opacity={0.25} />
                  <XAxis type="number" stroke="#716E66" fontSize={10} tickLine={false} allowDecimals={false} domain={[0, 'dataMax + 1']} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    stroke="#A5A29A"
                    fontSize={11}
                    tickLine={false}
                    width={130}
                    tick={{ fill: "#A5A29A" }}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#1C1B19", borderColor: "#3A3834", color: "#F1EFEB", borderRadius: '8px', fontSize: '11px', padding: '6px 10px' }}
                    itemStyle={{ color: "#F1EFEB" }}
                    formatter={(value: any) => [`${value} logs`, "Analyzed"]}
                  />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={13}>
                    {categories.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-xs text-eims-text-muted">No data available</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
