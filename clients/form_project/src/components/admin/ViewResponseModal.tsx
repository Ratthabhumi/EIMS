import { X } from 'lucide-react';
import { Training, Response, Answer, Question } from '../../types';

interface ViewResponseModalProps {
  response: Response;
  training: Training;
  onClose: () => void;
}

export default function ViewResponseModal({ response, training, onClose }: ViewResponseModalProps) {
  return (
    <div className="fixed z-10 inset-0 overflow-y-auto">
      <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
        <div className="fixed inset-0 transition-opacity" aria-hidden="true">
          <div className="absolute inset-0 bg-gray-500 opacity-75" onClick={onClose}></div>
        </div>
        <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
        <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-2xl sm:w-full">
          <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
            <div className="flex justify-between items-center mb-4 border-b pb-2">
              <h3 className="text-lg leading-6 font-medium text-gray-900">Assessment Details</h3>
              <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
                <X className="h-6 w-6" />
              </button>
            </div>
            
            <div className="mb-4 grid grid-cols-2 gap-4 text-sm text-gray-600 bg-gray-50 p-4 rounded-md">
              <div><span className="font-semibold text-gray-900">Full Name:</span> {response.fullName}</div>
              <div><span className="font-semibold text-gray-900">KEL Case ID:</span> {response.kelCaseId}</div>
              <div><span className="font-semibold text-gray-900">Department:</span> {response.department}</div>
              <div><span className="font-semibold text-gray-900">Position:</span> {response.position}</div>
            </div>

            <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
              <h4 className="font-medium text-gray-900">Scores</h4>
              <ul className="divide-y divide-gray-100">
                {(() => {
                  let parsedAnswers: Answer[] = [];
                  let parsedQuestions: Question[] = [];
                  try { parsedAnswers = JSON.parse(response.answers); } catch (e) {}
                  try { parsedQuestions = JSON.parse(training.questions || '[]'); } catch (e) {}
                  
                  return parsedQuestions.map((q, idx) => {
                    const answer = parsedAnswers.find(a => a.questionId === q.id);
                    return (
                      <li key={q.id} className="py-3 flex justify-between items-start">
                        <span className="text-sm text-gray-700 max-w-[80%]">
                          {idx + 1}. {q.label}
                        </span>
                        <span className={`px-2.5 py-0.5 rounded-full text-sm font-medium ${
                          Number(answer?.score) >= 4 ? 'bg-green-100 text-green-800' :
                          Number(answer?.score) === 3 ? 'bg-yellow-100 text-yellow-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {answer?.score || '-'} / 5
                        </span>
                      </li>
                    );
                  });
                })()}
              </ul>
              
              {response.comment && (
                <div className="mt-4 pt-4 border-t border-gray-100">
                  <h4 className="font-medium text-gray-900 mb-1">Additional Comment</h4>
                  <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded-md italic">"{response.comment}"</p>
                </div>
              )}
            </div>
          </div>
          <div className="bg-gray-50 px-4 py-3 sm:px-6 flex justify-end">
            <button type="button" onClick={onClose} className="w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 sm:w-auto sm:text-sm">Close</button>
          </div>
        </div>
      </div>
    </div>
  );
}
