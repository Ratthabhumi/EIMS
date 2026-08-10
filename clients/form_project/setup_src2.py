import os

files = {
    'src/pages/admin/AdminDashboard.tsx': '''import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Users } from 'lucide-react';
import { fetchTrainings } from '../../utils/api';
import { Training } from '../../types';

export default function AdminDashboard() {
  const [trainings, setTrainings] = useState<Training[]>([]);

  useEffect(() => {
    fetchTrainings().then(setTrainings).catch(console.error);
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-gray-900">Training Sessions</h1>
        <Link
          to="/admin/trainings/new"
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-microsoft-blue hover:bg-blue-700"
        >
          <Plus className="-ml-1 mr-2 h-5 w-5" />
          Create Training
        </Link>
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-md">
        <ul className="divide-y divide-gray-200">
          {trainings.map((training) => (
            <li key={training.id}>
              <Link to={`/admin/trainings/${training.id}`} className="block hover:bg-gray-50">
                <div className="px-4 py-4 sm:px-6">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-microsoft-blue truncate">{training.title}</p>
                    <div className="ml-2 flex-shrink-0 flex">
                      <p className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                        {training.date}
                      </p>
                    </div>
                  </div>
                  <div className="mt-2 sm:flex sm:justify-between">
                    <div className="sm:flex">
                      <p className="flex items-center text-sm text-gray-500">
                        <Users className="flex-shrink-0 mr-1.5 h-5 w-5 text-gray-400" />
                        Trainer: {training.trainer}
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
          {trainings.length === 0 && (
            <li className="px-4 py-8 text-center text-gray-500">
              No training sessions found. Click "Create Training" to add one.
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}
''',

    'src/pages/admin/CreateTraining.tsx': '''import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createTraining } from '../../utils/api';

export default function CreateTraining() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    
    const formData = new FormData(e.currentTarget);
    const data = {
      id: crypto.randomUUID(),
      title: formData.get('title'),
      description: formData.get('description'),
      trainer: formData.get('trainer'),
      location: formData.get('location'),
      date: formData.get('date'),
    };

    try {
      const res = await createTraining(data);
      navigate(`/admin/trainings/${res.id}`);
    } catch (err) {
      console.error(err);
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="md:flex md:items-center md:justify-between mb-6">
        <div className="flex-1 min-w-0">
          <h2 className="text-2xl font-bold leading-7 text-gray-900 sm:text-3xl sm:truncate">
            Create New Training
          </h2>
        </div>
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-lg p-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="title" className="block text-sm font-medium text-gray-700">Training Title</label>
            <input required type="text" name="title" id="title" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm" />
          </div>

          <div>
            <label htmlFor="description" className="block text-sm font-medium text-gray-700">Description</label>
            <textarea name="description" id="description" rows={3} className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm"></textarea>
          </div>

          <div className="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2">
            <div>
              <label htmlFor="trainer" className="block text-sm font-medium text-gray-700">Trainer Name</label>
              <input required type="text" name="trainer" id="trainer" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm" />
            </div>

            <div>
              <label htmlFor="location" className="block text-sm font-medium text-gray-700">Location / Room</label>
              <input required type="text" name="location" id="location" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm" />
            </div>
            
            <div>
              <label htmlFor="date" className="block text-sm font-medium text-gray-700">Date</label>
              <input required type="date" name="date" id="date" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm" />
            </div>
          </div>

          <div className="flex justify-end mt-6 pt-5 border-t border-gray-200">
            <button
              type="button"
              onClick={() => navigate('/admin')}
              className="bg-white py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-microsoft-blue"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="ml-3 inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-microsoft-blue hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-microsoft-blue"
            >
              {loading ? 'Saving...' : 'Save Training'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
''',

    'src/pages/admin/TrainingDetails.tsx': '''import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { QRCodeSVG } from 'qrcode.react';
import { Download, ArrowLeft } from 'lucide-react';
import { fetchTraining, fetchResponses, API_URL } from '../../utils/api';
import { Training, Response } from '../../types';

export default function TrainingDetails() {
  const { id } = useParams<{ id: string }>();
  const [training, setTraining] = useState<Training | null>(null);
  const [responses, setResponses] = useState<Response[]>([]);

  useEffect(() => {
    if (id) {
      fetchTraining(id).then(setTraining).catch(console.error);
      fetchResponses(id).then(setResponses).catch(console.error);
    }
  }, [id]);

  if (!training) return <div className="text-center py-12">Loading...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center">
          <Link to="/admin" className="mr-4 text-gray-400 hover:text-gray-600">
            <ArrowLeft className="h-6 w-6" />
          </Link>
          <h1 className="text-2xl font-semibold text-gray-900">{training.title}</h1>
        </div>
        <a
          href={`${API_URL}/trainings/${id}/export`}
          className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
        >
          <Download className="-ml-1 mr-2 h-5 w-5 text-gray-400" />
          Export to Excel
        </a>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-6">
          <div className="bg-white shadow overflow-hidden sm:rounded-lg">
            <div className="px-4 py-5 sm:px-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900">Training Information</h3>
            </div>
            <div className="border-t border-gray-200 px-4 py-5 sm:p-0">
              <dl className="sm:divide-y sm:divide-gray-200">
                <div className="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                  <dt className="text-sm font-medium text-gray-500">Trainer</dt>
                  <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">{training.trainer}</dd>
                </div>
                <div className="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                  <dt className="text-sm font-medium text-gray-500">Location</dt>
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
            <div className="px-4 py-5 sm:px-6 flex justify-between items-center">
              <h3 className="text-lg leading-6 font-medium text-gray-900">Recent Responses ({responses.length})</h3>
            </div>
            <div className="border-t border-gray-200">
              {responses.length > 0 ? (
                <ul className="divide-y divide-gray-200">
                  {responses.map((res) => (
                    <li key={res.id} className="px-4 py-4 sm:px-6">
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-sm font-medium text-microsoft-blue">{res.fullName} ({res.employeeId})</p>
                        <div className="ml-2 flex-shrink-0 flex">
                          <p className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                            Avg Score: {((res.q1 + res.q2 + res.q3 + res.q4 + res.q5) / 5).toFixed(1)}
                          </p>
                        </div>
                      </div>
                      <div className="text-sm text-gray-500">
                        <p>Department: {res.department}</p>
                        {res.comment && <p className="mt-1 italic">"{res.comment}"</p>}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="px-4 py-8 text-center text-gray-500">No responses yet.</div>
              )}
            </div>
          </div>
        </div>

        <div className="md:col-span-1">
          <div className="bg-white shadow overflow-hidden sm:rounded-lg">
            <div className="px-4 py-5 sm:px-6 border-b border-gray-200">
              <h3 className="text-lg leading-6 font-medium text-gray-900 text-center">Assessment QR Code</h3>
            </div>
            <div className="p-6 flex flex-col items-center justify-center space-y-4">
              <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-100">
                <QRCodeSVG value={training.qrCode || ''} size={200} />
              </div>
              <p className="text-sm text-center text-gray-500 mt-4">
                Scan this code to fill out the assessment form.
              </p>
              <a 
                href={training.qrCode} 
                target="_blank" 
                rel="noreferrer"
                className="text-microsoft-blue text-sm hover:underline break-all text-center"
              >
                {training.qrCode}
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
''',

    'src/pages/employee/AssessmentForm.tsx': '''import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchTraining, submitAssessment } from '../../utils/api';
import { Training } from '../../types';

const questions = [
  { id: 'q1', label: '1. Training Content Quality' },
  { id: 'q2', label: '2. Trainer Performance & Knowledge' },
  { id: 'q3', label: '3. Knowledge and Skills Gained' },
  { id: 'q4', label: '4. Training Materials and Resources' },
  { id: 'q5', label: '5. Overall Satisfaction' },
];

export default function AssessmentForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [training, setTraining] = useState<Training | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (id) {
      fetchTraining(id).then(setTraining).catch(() => setError('Training session not found.'));
    }
  }, [id]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    
    const formData = new FormData(e.currentTarget);
    
    const data = {
      id: crypto.randomUUID(),
      trainingId: id,
      employeeId: formData.get('employeeId'),
      fullName: formData.get('fullName'),
      department: formData.get('department'),
      q1: Number(formData.get('q1')),
      q2: Number(formData.get('q2')),
      q3: Number(formData.get('q3')),
      q4: Number(formData.get('q4')),
      q5: Number(formData.get('q5')),
      comment: formData.get('comment'),
      submittedAt: new Date().toISOString()
    };

    try {
      await submitAssessment(data);
      navigate('/success');
    } catch (err) {
      console.error(err);
      setError('Failed to submit. Please try again.');
      setLoading(false);
    }
  };

  if (error) {
    return (
      <div className="max-w-xl mx-auto mt-12 bg-red-50 border border-red-200 text-red-700 p-6 rounded-lg shadow-sm text-center">
        <h2 className="text-xl font-bold mb-2">Error</h2>
        <p>{error}</p>
      </div>
    );
  }

  if (!training) {
    return <div className="text-center py-12">Loading form...</div>;
  }

  return (
    <div className="max-w-2xl mx-auto bg-white shadow overflow-hidden sm:rounded-lg">
      <div className="px-4 py-5 sm:px-6 bg-microsoft-blue text-white">
        <h3 className="text-xl leading-6 font-semibold">Training Assessment Form</h3>
        <p className="mt-1 max-w-2xl text-sm opacity-90">Please fill out the evaluation for this session.</p>
      </div>
      
      <div className="border-t border-gray-200 px-4 py-5 sm:p-6 bg-gray-50">
        <div className="mb-4 pb-4 border-b border-gray-200">
          <p className="text-sm font-medium text-gray-500">Training Session</p>
          <p className="text-lg font-bold text-gray-900">{training.title}</p>
          <p className="text-sm text-gray-600">Date: {training.date}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2">
            <div>
              <label htmlFor="employeeId" className="block text-sm font-medium text-gray-700">Employee ID *</label>
              <input required type="text" name="employeeId" id="employeeId" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm" />
            </div>
            <div>
              <label htmlFor="fullName" className="block text-sm font-medium text-gray-700">Full Name *</label>
              <input required type="text" name="fullName" id="fullName" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm" />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="department" className="block text-sm font-medium text-gray-700">Department *</label>
              <input required type="text" name="department" id="department" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm" />
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-gray-200">
            <h4 className="text-lg font-medium text-gray-900 mb-4">Evaluation (1 = Poor, 5 = Excellent)</h4>
            <div className="space-y-6">
              {questions.map((q) => (
                <div key={q.id}>
                  <label className="block text-sm font-medium text-gray-700 mb-2">{q.label} *</label>
                  <div className="flex items-center space-x-6">
                    {[1, 2, 3, 4, 5].map((rating) => (
                      <label key={rating} className="flex items-center cursor-pointer">
                        <input required type="radio" name={q.id} value={rating} className="h-4 w-4 text-microsoft-blue border-gray-300 focus:ring-microsoft-blue" />
                        <span className="ml-2 text-sm text-gray-700">{rating}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-6 border-t border-gray-200">
            <label htmlFor="comment" className="block text-sm font-medium text-gray-700">Additional Comments (Optional)</label>
            <textarea name="comment" id="comment" rows={4} className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm"></textarea>
          </div>

          <div className="pt-4">
            <button
              type="submit"
              disabled={loading}
              className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-microsoft-blue hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-microsoft-blue"
            >
              {loading ? 'Submitting...' : 'Submit Assessment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
''',

    'src/pages/employee/SuccessPage.tsx': '''import { CheckCircle } from 'lucide-react';

export default function SuccessPage() {
  return (
    <div className="max-w-md mx-auto mt-12 bg-white p-8 rounded-lg shadow-sm text-center">
      <CheckCircle className="mx-auto h-16 w-16 text-green-500 mb-4" />
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Thank You!</h2>
      <p className="text-gray-600 mb-6">
        Your assessment has been successfully submitted. We appreciate your feedback to help us improve our future training sessions.
      </p>
      <p className="text-sm text-gray-500">You may now close this window.</p>
    </div>
  );
}
'''
}

for filepath, content in files.items():
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print('Frontend pages created')
