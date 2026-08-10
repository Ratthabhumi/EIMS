import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchTrainingPublic, submitAssessment } from '../../utils/api';
import { Training, Question, Answer } from '../../types';

export default function AssessmentForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [training, setTraining] = useState<Training | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (id) {
      fetchTrainingPublic(id).then(data => {
        setTraining(data);
        if (data.questions) {
            try {
                // Parse questions from training JSON string
                const qs: Question[] = JSON.parse(data.questions);
                setQuestions(qs.filter(q => q.isActive === 1));
            } catch (e) {
                console.error(e);
            }
        }
      }).catch(() => setError('Assessment not found.'));
    }
  }, [id]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (loading) return; // Prevent double submission before React re-renders
    setLoading(true);
    
    const formData = new FormData(e.currentTarget);
    
    const answers: Answer[] = questions.map(q => ({
      questionId: q.id,
      label: q.label,
      score: Number(formData.get(q.id))
    }));

    const data = {
      id: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(),
      trainingId: id,
      kelCaseId: formData.get('kelCaseId'),
      fullName: formData.get('fullName'),
      department: formData.get('department'),
      position: formData.get('position'),
      answers: answers,
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
    <div className="max-w-2xl mx-auto bg-white shadow overflow-hidden sm:rounded-lg mb-12">
      <div className="px-4 py-5 sm:px-6 bg-brand-blue text-white">
        <h3 className="text-xl leading-6 font-semibold">Support & Implementation Assessment Form</h3>
        <p className="mt-1 max-w-2xl text-sm opacity-90">Please fill out the evaluation for this session.</p>
      </div>
      
      <div className="border-t border-gray-200 px-4 py-5 sm:p-6 bg-gray-50">
        <div className="mb-4 pb-4 border-b border-gray-200">
          <p className="text-sm font-medium text-gray-500">Project / Ticket</p>
          <p className="text-lg font-bold text-gray-900">{training.title}</p>
          <p className="text-sm text-gray-600">Date: {training.date}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2">
            <div>
              <label htmlFor="kelCaseId" className="block text-sm font-medium text-gray-700">KEL Case ID *</label>
              <input required type="text" name="kelCaseId" id="kelCaseId" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
            </div>
            <div>
              <label htmlFor="fullName" className="block text-sm font-medium text-gray-700">Full Name *</label>
              <input required type="text" name="fullName" id="fullName" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
            </div>
            <div>
              <label htmlFor="department" className="block text-sm font-medium text-gray-700">Department *</label>
              <input required type="text" name="department" id="department" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
            </div>
            <div>
              <label htmlFor="position" className="block text-sm font-medium text-gray-700">Position *</label>
              <input required type="text" name="position" id="position" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-gray-200">
            <h4 className="text-lg font-medium text-gray-900 mb-4">Evaluation (1 = Poor, 5 = Excellent)</h4>
            <div className="space-y-8">
              {questions.length === 0 && (
                <p className="text-sm text-gray-500 italic">No evaluation topics have been configured yet.</p>
              )}
              {Object.entries(
                questions.reduce((acc, q) => {
                  const cat = q.category || 'General';
                  if (!acc[cat]) acc[cat] = [];
                  acc[cat].push(q);
                  return acc;
                }, {} as Record<string, Question[]>)
              ).map(([category, catsQs]) => (
                <div key={category} className="bg-white p-4 rounded-lg shadow-sm border border-gray-100">
                  <h5 className="text-md font-bold text-brand-blue mb-4 border-b pb-2">{category}</h5>
                  <div className="space-y-6">
                    {catsQs.map((q, index) => (
                      <div key={q.id}>
                        <label className="block text-sm font-medium text-gray-700 mb-2">{index + 1}. {q.label} *</label>
                        <div className="flex items-center space-x-6">
                          {[1, 2, 3, 4, 5].map((rating) => (
                            <label key={rating} className="flex items-center cursor-pointer hover:bg-gray-100 p-1 rounded-md">
                              <input required type="radio" name={q.id} value={rating} className="h-4 w-4 text-brand-blue border-gray-300 focus:ring-brand-blue" />
                              <span className="ml-2 text-sm text-gray-700 font-medium">{rating}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-6 border-t border-gray-200">
            <label htmlFor="comment" className="block text-sm font-medium text-gray-700">Additional Comments (Optional)</label>
            <textarea name="comment" id="comment" rows={4} className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-brand-blue focus:border-brand-blue sm:text-sm"></textarea>
          </div>

          <div className="pt-4">
            <button
              type="submit"
              disabled={loading || questions.length === 0}
              className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-brand-blue hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Submitting...' : 'Submit Assessment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
