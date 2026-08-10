import { X } from 'lucide-react';
import { Response } from '../../types';

interface EditResponseModalProps {
  response: Response;
  onClose: () => void;
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
}

export default function EditResponseModal({ response, onClose, onSubmit }: EditResponseModalProps) {
  return (
    <div className="fixed z-10 inset-0 overflow-y-auto">
      <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
        <div className="fixed inset-0 transition-opacity" aria-hidden="true">
          <div className="absolute inset-0 bg-gray-500 opacity-75" onClick={onClose}></div>
        </div>
        <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
        <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
          <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg leading-6 font-medium text-gray-900">Edit Response</h3>
              <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
                <X className="h-6 w-6" />
              </button>
            </div>
            <form id="edit-response-form" onSubmit={onSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">KEL Case ID</label>
                <input type="text" required name="kelCaseId" defaultValue={response.kelCaseId} className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 sm:text-sm focus:ring-brand-blue focus:border-brand-blue" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Full Name</label>
                <input type="text" required name="fullName" defaultValue={response.fullName} className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 sm:text-sm focus:ring-brand-blue focus:border-brand-blue" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Department</label>
                <input type="text" required name="department" defaultValue={response.department} className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 sm:text-sm focus:ring-brand-blue focus:border-brand-blue" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Position</label>
                <input type="text" required name="position" defaultValue={response.position} className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 sm:text-sm focus:ring-brand-blue focus:border-brand-blue" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Comment</label>
                <textarea name="comment" defaultValue={response.comment} rows={3} className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 sm:text-sm focus:ring-brand-blue focus:border-brand-blue"></textarea>
              </div>
            </form>
          </div>
          <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
            <button type="submit" form="edit-response-form" className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-brand-blue text-base font-medium text-white hover:bg-blue-700 sm:ml-3 sm:w-auto sm:text-sm">Save Changes</button>
            <button type="button" onClick={onClose} className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm">Cancel</button>
          </div>
        </div>
      </div>
    </div>
  );
}
