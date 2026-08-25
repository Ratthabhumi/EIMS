import { useState, useEffect } from "react";
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from "recharts";
import { FileText, AlertTriangle, Clock } from "lucide-react";

const COLORS = ["#7B8F9F", "#55A868", "#C78A70", "#8A997B", "#C96B68", "#A5A29A", "#6E6B65"];

interface Stats {
  totalLogs: number;
  criticalErrors: number;
  avgSearchTimeSec: number;
  dailyTrends: { date: string; count: number }[];
  providerStats: { name: string; value: number }[];
}

interface AnalyzerDashboardProps {
  refreshTrigger?: number;
}

export default function AnalyzerDashboard({ refreshTrigger = 0 }: AnalyzerDashboardProps) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [showAllProviders, setShowAllProviders] = useState(false);

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

  return (
    <div className="w-full space-y-4">
      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-eims-surface border border-eims-border rounded-xl p-5 flex items-center justify-between shadow-sm">
          <div>
            <p className="text-eims-text-secondary text-xs font-medium uppercase tracking-wider mb-1">Total Logs Analyzed</p>
            <h3 className="text-2xl font-bold text-eims-text">{stats.totalLogs}</h3>
          </div>
          <div className="p-2.5 bg-eims-info/10 border border-eims-info/20 text-eims-info dark:text-sky-400 rounded-lg">
            <FileText size={20} />
          </div>
        </div>

        <div className="bg-eims-surface border border-eims-border rounded-xl p-5 flex items-center justify-between shadow-sm">
          <div>
            <p className="text-eims-text-secondary text-xs font-medium uppercase tracking-wider mb-1">Critical Errors</p>
            <h3 className="text-2xl font-bold text-eims-text">{stats.criticalErrors}</h3>
          </div>
          <div className="p-2.5 bg-rose-500/10 border border-rose-500/20 text-rose-500/90 rounded-lg">
            <AlertTriangle size={20} />
          </div>
        </div>

        <div className="bg-eims-surface border border-eims-border rounded-xl p-5 flex items-center justify-between shadow-sm">
          <div>
            <p className="text-eims-text-secondary text-xs font-medium uppercase tracking-wider mb-1">Avg Search Time</p>
            <h3 className="text-2xl font-bold text-eims-text">{stats.avgSearchTimeSec.toFixed(2)}s</h3>
          </div>
          <div className="p-2.5 bg-teal-500/10 border border-teal-500/20 text-teal-500 rounded-lg">
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
              <YAxis stroke="#716E66" fontSize={11} tickLine={false} />
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
            <h3 className="text-xs font-semibold text-eims-text uppercase tracking-wider">Error Types by Provider</h3>
            {stats.providerStats && stats.providerStats.length > 5 && (
              <button
                onClick={() => setShowAllProviders(!showAllProviders)}
                className="text-[11px] text-eims-info dark:text-sky-400 hover:underline font-medium"
              >
                {showAllProviders ? "Show Top 5" : "View All"}
              </button>
            )}
          </div>
          
          <div className="flex-1 min-h-0 flex items-center justify-center">
            {stats.providerStats && stats.providerStats.length > 0 ? (
              <div className="w-full h-full flex items-center gap-3">
                {/* Donut Chart */}
                <div className="w-1/2 h-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={stats.providerStats}
                        cx="50%"
                        cy="50%"
                        innerRadius={42}
                        outerRadius={58}
                        paddingAngle={2}
                        dataKey="value"
                      >
                        {stats.providerStats.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} stroke="transparent" />
                        ))}
                      </Pie>
                      <Tooltip 
                        contentStyle={{ backgroundColor: "#1C1B19", borderColor: "#3A3834", color: "#F1EFEB", borderRadius: '8px', fontSize: '11px', padding: '6px 10px' }}
                        itemStyle={{ color: "#F1EFEB" }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>

                {/* Scrollable Legend showing All or Top 5 with Toggle */}
                <div className="w-1/2 flex flex-col gap-1 pr-1 overflow-y-auto max-h-[200px] custom-scrollbar py-1">
                  {(showAllProviders ? stats.providerStats : stats.providerStats.slice(0, 5)).map((entry, index) => (
                    <div key={entry.name} className="flex items-center justify-between text-[11px] gap-2 py-0.5 border-b border-eims-border/20 last:border-0 hover:bg-eims-surface-subtle/50 px-1 rounded transition-colors">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span 
                          className="w-2 h-2 rounded-full shrink-0" 
                          style={{ backgroundColor: COLORS[index % COLORS.length] }} 
                        />
                        <span className="text-eims-text truncate" title={entry.name}>
                          {entry.name.length > 18 ? entry.name.replace("Microsoft-Windows-", "MS-") : entry.name}
                        </span>
                      </div>
                      <span className="text-eims-text-secondary font-mono font-medium shrink-0">{entry.value}</span>
                    </div>
                  ))}
                  {!showAllProviders && stats.providerStats.length > 5 && (
                    <button
                      onClick={() => setShowAllProviders(true)}
                      className="text-[10px] text-eims-info dark:text-sky-400 text-right pt-1 hover:underline cursor-pointer"
                    >
                      +{stats.providerStats.length - 5} more (click to view)
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-xs text-eims-text-muted">No data available</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
