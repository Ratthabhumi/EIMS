import { CheckCircle } from 'lucide-react';

export default function SuccessPage() {
  return (
    <div className="max-w-md mx-auto mt-12 bg-white p-8 rounded-lg shadow-sm text-center">
      <CheckCircle className="mx-auto h-16 w-16 text-green-500 mb-4" />
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Thank You!</h2>
      <p className="text-gray-600 mb-6">
        Your assessment has been successfully submitted. We appreciate your feedback to help us improve our future services.
      </p>
      <p className="text-sm text-gray-500">You may now close this window.</p>
    </div>
  );
}
