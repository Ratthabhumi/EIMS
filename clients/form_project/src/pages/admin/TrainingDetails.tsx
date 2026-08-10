import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Download, ArrowLeft, Edit, Trash2, Search, Filter } from 'lucide-react';
import { fetchTraining, fetchResponses, API_URL, deleteResponse, updateResponse } from '../../utils/api';
import { Training, Response, Answer } from '../../types';
import QRCodeCard from '../../components/admin/QRCodeCard';
import ViewResponseModal from '../../components/admin/ViewResponseModal';
import EditResponseModal from '../../components/admin/EditResponseModal';

export default function TrainingDetails() {
  const { id } = useParams<{ id: string }>();
  const [training, setTraining] = useState<Training | null>(null);
  const [responses, setResponses] = useState<Response[]>([]);
  const [editingResponse, setEditingResponse] = useState<Response | null>(null);
  const [viewingResponse, setViewingResponse] = useState<Response | null>(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('date-desc');
  const [departmentFilter, setDepartmentFilter] = useState('All');

  useEffect(() => {
    if (id) {
      fetchTraining(id).then(setTraining).catch(console.error);
      fetchResponses(id).then(setResponses).catch(console.error);
    }
  }, [id]);

  const handleDeleteResponse = async (responseId: string) => {
    if (window.confirm('Are you sure you want to delete this response?')) {
      try {
        await deleteResponse(responseId);
        setResponses(responses.filter(r => r.id !== responseId));
      } catch (err) {
        console.error(err);
        alert('Failed to delete response');
      }
    }
  };

  const handleUpdateResponse = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!editingResponse) return;
    
    const formData = new FormData(e.currentTarget);
    const updatedData = {
      ...editingResponse,
      kelCaseId: formData.get('kelCaseId') as string,
      fullName: formData.get('fullName') as string,
      department: formData.get('department') as string,
      position: formData.get('position') as string,
      comment: formData.get('comment') as string,
    };

    try {
      await updateResponse(editingResponse.id, updatedData);
      setResponses(responses.map(r => r.id === editingResponse.id ? updatedData as Response : r));
      setEditingResponse(null);
    } catch (err) {
      console.error(err);
      alert('Failed to update response');
    }
  };

  const calculateAvg = (answersStr: string) => {
    try {
      const answers: Answer[] = JSON.parse(answersStr);
      if (answers.length === 0) return 0;
      const sum = answers.reduce((acc, curr) => acc + Number(curr.score), 0);
      return (sum / answers.length).toFixed(1);
    } catch {
      return 0;
    }
  };

  const departments = Array.from(new Set(responses.map(r => r.department))).filter(Boolean).sort();

  const filteredResponses = responses.filter(r => {
    const matchesSearch = 
      r.fullName.toLowerCase().includes(searchQuery.toLowerCase()) || 
      r.kelCaseId.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.department.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesDept = departmentFilter === 'All' || r.department === departmentFilter;

    return matchesSearch && matchesDept;
  });

  const sortedResponses = [...filteredResponses].sort((a, b) => {
    const avgA = Number(calculateAvg(a.answers));
    const avgB = Number(calculateAvg(b.answers));
    
    if (sortBy === 'avg-desc') {
      return avgB - avgA;
    } else if (sortBy === 'avg-asc') {
      return avgA - avgB;
    } else if (sortBy === 'date-desc') {
      return new Date(b.submittedAt || 0).getTime() - new Date(a.submittedAt || 0).getTime();
    } else if (sortBy === 'date-asc') {
      return new Date(a.submittedAt || 0).getTime() - new Date(b.submittedAt || 0).getTime();
    } else if (sortBy === 'name-asc') {
      return a.fullName.localeCompare(b.fullName);
    }
    return 0;
  });

  if (!training) return <div className="text-center py-12">Loading...</div>;

  const qrCodeUrl = `${window.location.origin}/assessment/${id}`;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center">
          <Link to="/admin" className="mr-4 text-gray-400 hover:text-gray-600">
            <ArrowLeft className="h-6 w-6" />
          </Link>
          <h1 className="text-2xl font-semibold text-gray-900">{training.title}</h1>
        </div>
        <div className="flex space-x-3">
          <Link
            to={`/admin/trainings/${id}/edit`}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            <Edit className="-ml-1 mr-2 h-5 w-5 text-gray-400" />
            Edit Assessment
          </Link>
          <a
            href={`${API_URL}/trainings/${id}/export`}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700"
          >
            <Download className="-ml-1 mr-2 h-5 w-5" />
            Export to Excel
          </a>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-6">
          <div className="bg-white shadow overflow-hidden sm:rounded-lg">
            <div className="px-4 py-5 sm:px-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900">Assessment Information</h3>
            </div>
            <div className="border-t border-gray-200 px-4 py-5 sm:p-0">
              <dl className="sm:divide-y sm:divide-gray-200">
                <div className="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                  <dt className="text-sm font-medium text-gray-500">Engineer</dt>
                  <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">{training.trainer}</dd>
                </div>
                <div className="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                  <dt className="text-sm font-medium text-gray-500">System / Site</dt>
                  <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">{training.location}</dd>
                </div>
                <div className="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                  <dt className="text-sm font-medium text-gray-500">Date</dt>
                  <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">{training.date}</dd>
                </div>
              </dl>
            </div>
          </div>

          <div className="bg-white shadow overflow-hidden sm:rounded-lg">
            <div className="px-4 py-5 sm:px-6 flex flex-col space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="text-lg leading-6 font-medium text-gray-900">Recent Responses ({responses.length})</h3>
              </div>
              
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="relative flex-1">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Search className="h-4 w-4 text-gray-400" />
                  </div>
                  <input
                    type="text"
                    className="block w-full pl-9 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                    placeholder="Search by name, ID, or dept..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                
                <div className="flex gap-2">
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-2 flex items-center pointer-events-none">
                      <Filter className="h-4 w-4 text-gray-400" />
                    </div>
                    <select
                      value={departmentFilter}
                      onChange={(e) => setDepartmentFilter(e.target.value)}
                      className="block w-full pl-8 pr-8 py-2 text-base border-gray-300 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm rounded-md"
                    >
                      <option value="All">All Departments</option>
                      {departments.map(dept => (
                        <option key={dept} value={dept}>{dept}</option>
                      ))}
                    </select>
                  </div>
                  
                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                    className="block w-full pl-3 pr-8 py-2 text-base border-gray-300 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm rounded-md"
                  >
                    <option value="date-desc">Newest First</option>
                    <option value="date-asc">Oldest First</option>
                    <option value="avg-desc">Highest Score</option>
                    <option value="avg-asc">Lowest Score</option>
                    <option value="name-asc">Name (A-Z)</option>
                  </select>
                </div>
              </div>
            </div>
            <div className="border-t border-gray-200">
              {sortedResponses.length > 0 ? (
                <ul className="divide-y divide-gray-200">
                  {sortedResponses.map((res) => (
                    <li key={res.id} className="px-4 py-4 sm:px-6">
                      <div className="flex items-center justify-between mb-1">
                        <button 
                          onClick={() => setViewingResponse(res)}
                          className="text-sm font-medium text-brand-blue hover:underline text-left"
                        >
                          {res.fullName} ({res.kelCaseId})
                        </button>
                        <div className="ml-2 flex-shrink-0 flex items-center space-x-2">
                          <p className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                            Avg Score: {calculateAvg(res.answers)}
                          </p>
                          <button onClick={() => setEditingResponse(res)} className="text-gray-400 hover:text-brand-blue" title="Edit Response">
                            <Edit className="w-4 h-4" />
                          </button>
                          <button onClick={() => handleDeleteResponse(res.id)} className="text-gray-400 hover:text-red-600" title="Delete Response">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                      <div className="text-sm text-gray-500">
                        <p>Department: {res.department} | Position: {res.position}</p>
                        {res.comment && <p className="mt-1 italic">"{res.comment}"</p>}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="px-4 py-8 text-center text-gray-500">
                  {responses.length > 0 ? 'No results match your search or filters.' : 'No responses yet.'}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="md:col-span-1">
          <QRCodeCard training={training} qrCodeUrl={qrCodeUrl} />
        </div>
      </div>

      {editingResponse && (
        <EditResponseModal
          response={editingResponse}
          onClose={() => setEditingResponse(null)}
          onSubmit={handleUpdateResponse}
        />
      )}

      {viewingResponse && (
        <ViewResponseModal
          response={viewingResponse}
          training={training}
          onClose={() => setViewingResponse(null)}
        />
      )}
    </div>
  );
}
