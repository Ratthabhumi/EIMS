"use client";

import { useState, useEffect } from "react";
import { AppSettings } from "@/lib/types";
import { fetchUsers, createUser, deleteUser, fetchLeaderboard } from "@/lib/api";
import { t } from "@/lib/i18n";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Trash2, UserPlus, Trophy } from "lucide-react";

interface AdminPanelProps {
  settings: AppSettings;
}

export function AdminPanel({ settings }: AdminPanelProps) {
  const [users, setUsers] = useState<any[]>([]);
  const [leaderboard, setLeaderboard] = useState<any[]>([]);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("user");
  const [loading, setLoading] = useState(false);
  const lang = settings.language;

  useEffect(() => {
    loadData();
  }, [settings]);

  const loadData = async () => {
    try {
      const [usersData, leaderboardData] = await Promise.all([
        fetchUsers(settings),
        fetchLeaderboard(settings)
      ]);
      setUsers(usersData);
      setLeaderboard(leaderboardData);
    } catch (error) {
      console.error("Failed to load admin data", error);
    }
  };

  const handleCreateUser = async () => {
    if (!newUsername || !newPassword) return;
    setLoading(true);
    try {
      await createUser(settings, { username: newUsername, password: newPassword, role: newRole });
      setNewUsername("");
      setNewPassword("");
      loadData();
    } catch (error: any) {
      alert(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteUser = async (id: number) => {
    if (!confirm(lang === 'th' ? "ลบผู้ใช้นี้แน่ใจหรือไม่?" : "Are you sure you want to delete this user?")) return;
    try {
      await deleteUser(settings, id);
      loadData();
    } catch (error: any) {
      alert(error.message);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserPlus className="w-5 h-5 text-blue-600" />
            {lang === 'th' ? "จัดการผู้ใช้งาน (User Management)" : "User Management"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2 mb-4">
            <Input 
              placeholder={lang === 'th' ? "ชื่อผู้ใช้" : "Username"} 
              value={newUsername} 
              onChange={e => setNewUsername(e.target.value)} 
            />
            <Input 
              placeholder={lang === 'th' ? "รหัสผ่าน" : "Password"} 
              type="password" 
              value={newPassword} 
              onChange={e => setNewPassword(e.target.value)} 
            />
            <select 
              className="border border-gray-300 rounded-md px-2"
              value={newRole}
              onChange={e => setNewRole(e.target.value)}
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
            <Button onClick={handleCreateUser} disabled={loading || !newUsername || !newPassword}>
              {lang === 'th' ? "เพิ่ม" : "Add"}
            </Button>
          </div>
          
          <div className="space-y-2">
            {users.map(u => (
              <div key={u.id} className="flex justify-between items-center p-3 bg-gray-50 dark:bg-gray-800 rounded-md border border-gray-100 dark:border-gray-700">
                <div className="flex items-center gap-3">
                  <span className="font-semibold">{u.username}</span>
                  <span className={`text-xs px-2 py-1 rounded-full ${u.role === 'admin' ? 'bg-red-100 text-red-800' : 'bg-blue-100 text-blue-800'}`}>
                    {u.role}
                  </span>
                </div>
                <Button variant="ghost" size="sm" onClick={() => handleDeleteUser(u.id)} className="text-red-500 hover:text-red-700 hover:bg-red-50">
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trophy className="w-5 h-5 text-yellow-500" />
            {lang === 'th' ? "ตารางผู้นำ (Leaderboard)" : "Leaderboard"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {leaderboard.map((entry, idx) => (
              <div key={entry.username} className="flex justify-between items-center p-3 bg-white dark:bg-gray-800 rounded-md border border-gray-200 dark:border-gray-700 shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center font-bold text-lg bg-gray-100 dark:bg-gray-700">
                    {idx === 0 ? "🥇" : idx === 1 ? "🥈" : idx === 2 ? "🥉" : `${idx + 1}`}
                  </div>
                  <span className="font-semibold text-gray-800 dark:text-gray-200">{entry.username}</span>
                </div>
                <div className="text-sm font-medium text-gray-500 dark:text-gray-400">
                  {entry.analyses_count} {lang === 'th' ? "รายการ" : "analyses"}
                </div>
              </div>
            ))}
            {leaderboard.length === 0 && (
              <div className="text-center text-gray-500 py-4">
                {lang === 'th' ? "ยังไม่มีข้อมูล" : "No data yet"}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
