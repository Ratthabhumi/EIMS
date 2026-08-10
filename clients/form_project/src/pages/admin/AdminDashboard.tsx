import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Users, Trash2, Search, FileText, Activity } from 'lucide-react';
import { fetchTrainings, deleteTraining, fetchAnalytics } from '../../utils/api';
import { Training } from '../../types';
import { DashboardSkeleton } from '../../components/common/Skeleton';

export default function AdminDashboard() {
  const [trainings, setTrainings] = useState<Training[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('date-desc');
  const [loading, setLoading] = useState(true);
  
  const [stats, setStats] = useState({
    totalProjects: 0,
    totalResponses: 0,
    averageScore: 0
  });

  const filteredTrainings = trainings.filter(t => 
    t.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
    t.trainer.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const sortedTrainings = [...filteredTrainings].sort((a, b) => {
    if (sortBy === 'date-desc') {
      return new Date(b.date).getTime() - new Date(a.date).getTime();
    } else if (sortBy === 'date-asc') {
      return new Date(a.date).getTime() - new Date(b.date).getTime();
    } else if (sortBy === 'title-asc') {
      return a.title.localeCompare(b.title);
    } else if (sortBy === 'title-desc') {
      return b.title.localeCompare(a.title);
    }
    return 0;
  });

  useEffect(() => {
    const loadData = async () => {
      try {
        const [trainingsData, analyticsData] = await Promise.all([
          fetchTrainings(),
          fetchAnalytics()
        ]);
        setTrainings(trainingsData);
        setStats(analyticsData);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm('Are you sure you want to delete this training session and all its responses?')) {
      try {
        await deleteTraining(id);
        setTrainings(trainings.filter(t => t.id !== id));
        // Optionally refresh stats here
        fetchAnalytics().then(setStats);
      } catch (err) {
        console.error('Failed to delete training', err);
      }
    }
  };

  if (loading) {
    return <DashboardSkeleton />;
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-gray-900">Assessment Projects</h1>
        <Link
          to="/admin/trainings/new"
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-brand-blue hover:bg-blue-700 transition-colors"
        >
          <Plus className="-ml-1 mr-2 h-5 w-5" />
          Create Assessment
        </Link>
      </div>

      {/* Analytics Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-500 mb-1">Total Projects</p>
            <p className="text-3xl font-bold text-gray-900">{stats.totalProjects}</p>
          </div>
          <div className="p-3 bg-blue-50 rounded-full">
            <FileText className="h-6 w-6 text-brand-blue" />
          </div>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-500 mb-1">Total Responses</p>
            <p className="text-3xl font-bold text-gray-900">{stats.totalResponses}</p>
          </div>
          <div className="p-3 bg-green-50 rounded-full">
            <Users className="h-6 w-6 text-green-600" />
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-500 mb-1">Company Avg Score</p>
            <p className="text-3xl font-bold text-gray-900">
              {stats.averageScore} <span className="text-lg font-normal text-gray-500">/ 5</span>
            </p>
          </div>
          <div className="p-3 bg-yellow-50 rounded-full">
            <Activity className="h-6 w-6 text-yellow-500" />
          </div>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row justify-between items-center bg-white p-4 shadow sm:rounded-md gap-4">
        <div className="relative w-full sm:w-96">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-5 w-5 text-gray-400" />
          </div>
          <input
            type="text"
            className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-brand-blue focus:border-brand-blue sm:text-sm transition-shadow"
            placeholder="Search by project name or engineer..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="flex items-center w-full sm:w-auto space-x-2">
          <span className="text-sm text-gray-500 whitespace-nowrap">Sort by:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="block w-full sm:w-auto pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm rounded-md"
          >
            <option value="date-desc">Newest First</option>
            <option value="date-asc">Oldest First</option>
            <option value="title-asc">Project Name (A-Z)</option>
            <option value="title-desc">Project Name (Z-A)</option>
          </select>
        </div>
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-md">
        <ul className="divide-y divide-gray-200">
          {sortedTrainings.map((training) => (
            <li key={training.id} className="transition-colors hover:bg-gray-50">
              <Link to={`/admin/trainings/${training.id}`} className="block">
                <div className="px-4 py-4 sm:px-6">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-brand-blue truncate">{training.title}</p>
                    <div className="ml-2 flex-shrink-0 flex items-center space-x-4">
                      <p className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                        {training.date}
                      </p>
                      <button
                        onClick={(e) => handleDelete(training.id, e)}
                        className="text-red-500 hover:text-red-700 p-1 rounded-full hover:bg-red-50 transition-colors"
                        title="Delete Training"
                      >
                        <Trash2 className="h-5 w-5" />
                      </button>
                    </div>
                  </div>
                  <div className="mt-2 sm:flex sm:justify-between">
                    <div className="sm:flex">
                      <p className="flex items-center text-sm text-gray-500">
                        <Users className="flex-shrink-0 mr-1.5 h-5 w-5 text-gray-400" />
                        Engineer: {training.trainer}
                      </p>
                    </div>
                    <div className="mt-2 flex items-center text-sm text-gray-500 sm:mt-0">
                      <p>{training.location}</p>
                    </div>
                  </div>
                </div>
              </Link>
            </li>
          ))}
          {sortedTrainings.length === 0 && trainings.length > 0 && (
            <li className="px-4 py-8 text-center text-gray-500">
              No results found for "{searchQuery}".
            </li>
          )}
          {trainings.length === 0 && (
            <li className="px-4 py-8 text-center text-gray-500">
              No assessments found. Click "Create Assessment" to add one.
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}
