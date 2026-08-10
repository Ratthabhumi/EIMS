import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { createTraining, fetchQuestions } from '../../utils/api';
import { Question } from '../../types';
import { Plus, Trash2, X } from 'lucide-react';

export default function CreateTraining() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [newLabel, setNewLabel] = useState('');
  
  const generateId = () => Math.random().toString(36).substring(2, 9) + Date.now().toString(36);

  const [questions, setQuestions] = useState<Question[]>([]);
  const [newCategory, setNewCategory] = useState('General');

  const [engineers, setEngineers] = useState<string[]>([]);
  const [newEngineer, setNewEngineer] = useState('');

  const addEngineer = () => {
    if (newEngineer.trim() && !engineers.includes(newEngineer.trim())) {
      setEngineers([...engineers, newEngineer.trim()]);
      setNewEngineer('');
    }
  };

  const removeEngineer = (eng: string) => {
    setEngineers(engineers.filter(e => e !== eng));
  };

  // Fetch default questions from DB
  useEffect(() => {
    fetchQuestions().then(qs => {
      if (qs && qs.length > 0) {
        setQuestions(qs);
      }
    }).catch(console.error);
  }, []);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (engineers.length === 0) {
      alert('Please add at least one engineer.');
      return;
    }
    setLoading(true);
    
    const formData = new FormData(e.currentTarget);
    const data = {
      title: formData.get('title'),
      description: formData.get('description'),
      trainer: engineers.join(', '),
      location: formData.get('location'),
      date: formData.get('date'),
      origin: window.location.origin,
      questions: questions
    };

    try {
      const res = await createTraining(data);
      navigate(`/admin/trainings/${res.id}`);
    } catch (err) {
      console.error(err);
      setLoading(false);
    }
  };

  const addQuestion = () => {
    if (!newLabel.trim()) return;
    setQuestions([...questions, {
      id: generateId(),
      label: newLabel.trim(),
      isActive: 1,
      orderIndex: questions.length,
      category: newCategory
    }]);
    setNewLabel('');
  };

  const removeQuestion = (qId: string) => {
    setQuestions(questions.filter(q => q.id !== qId));
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="md:flex md:items-center md:justify-between mb-6">
        <div className="flex-1 min-w-0">
          <h2 className="text-2xl font-bold leading-7 text-gray-900 sm:text-3xl sm:truncate">
            Create New Assessment
          </h2>
        </div>
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-lg p-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          <h3 className="text-lg font-medium text-gray-900 border-b pb-2">Project Details</h3>

          <div>
            <label htmlFor="title" className="block text-sm font-medium text-gray-700">Project / Ticket Name</label>
            <input required type="text" name="title" id="title" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
          </div>

          <div>
            <label htmlFor="description" className="block text-sm font-medium text-gray-700">Description</label>
            <textarea name="description" id="description" rows={3} className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm"></textarea>
          </div>

          <div className="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-gray-700">Engineer(s) / Support Staff *</label>
              <div className="mt-1 flex gap-2">
                <input 
                  type="text" 
                  value={newEngineer}
                  onChange={e => setNewEngineer(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addEngineer(); } }}
                  placeholder="Type name and press Enter"
                  className="flex-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm" 
                />
                <button type="button" onClick={addEngineer} className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-blue-700">
                  Add
                </button>
              </div>
              {engineers.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {engineers.map((eng, idx) => (
                    <span key={idx} className="inline-flex items-center px-2.5 py-1.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      {eng}
                      <button type="button" onClick={() => removeEngineer(eng)} className="flex-shrink-0 ml-1.5 inline-flex text-blue-500 hover:text-blue-800">
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                </div>
              )}
              {engineers.length === 0 && <p className="mt-1 text-xs text-red-500">Please add at least one engineer.</p>}
            </div>

            <div>
              <label htmlFor="location" className="block text-sm font-medium text-gray-700">System / Site</label>
              <input required type="text" name="location" id="location" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
            </div>
            
            <div>
              <label htmlFor="date" className="block text-sm font-medium text-gray-700">Date</label>
              <input required type="date" name="date" id="date" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
            </div>
          </div>

          <div className="mt-8">
            <h3 className="text-lg font-medium text-gray-900 border-b pb-2 mb-4">Evaluation Topics</h3>
            <p className="text-sm text-gray-500 mb-4">You can customize the questions specifically for this session.</p>
            
            <ul className="space-y-3 mb-4">
              {questions.map((q, idx) => (
                <li key={q.id} className="flex items-center justify-between bg-gray-50 p-3 rounded-md border border-gray-200">
                  <span className="text-sm text-gray-900">
                    <span className="font-semibold text-brand-blue mr-2">[{q.category || 'General'}]</span>
                    {idx + 1}. {q.label}
                  </span>
                  <button type="button" onClick={() => removeQuestion(q.id)} className="text-red-500 hover:text-red-700 p-1">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
              {questions.length === 0 && (
                <li className="text-sm text-gray-500 italic">No questions added yet.</li>
              )}
            </ul>

            <div className="flex gap-2">
              <select 
                value={newCategory} 
                onChange={e => setNewCategory(e.target.value)}
                className="border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
              >
                <option value="General">General</option>
                <option value="Support">Support</option>
                <option value="Implement">Implement</option>
              </select>
              <input 
                type="text" 
                value={newLabel}
                onChange={e => setNewLabel(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    addQuestion();
                  }
                }}
                placeholder="Add a new question..."
                className="flex-1 border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm" 
              />
              <button
                type="button"
                onClick={addQuestion}
                className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700"
              >
                <Plus className="-ml-1 mr-1 h-5 w-5" /> Add
              </button>
            </div>
          </div>

          <div className="flex justify-end mt-6 pt-5 border-t border-gray-200">
            <button
              type="button"
              onClick={() => navigate('/admin')}
              className="bg-white py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="ml-3 inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue"
            >
              {loading ? 'Saving...' : 'Save Assessment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
