import { QRCodeCanvas } from 'qrcode.react';
import { Image as ImageIcon } from 'lucide-react';
import { Training } from '../../types';

interface QRCodeCardProps {
  training: Training;
  qrCodeUrl: string;
}

export default function QRCodeCard({ training, qrCodeUrl }: QRCodeCardProps) {
  const downloadQRCode = () => {
    const canvas = document.getElementById('qr-code-canvas') as HTMLCanvasElement;
    if (canvas) {
      const url = canvas.toDataURL('image/png');
      const link = document.createElement('a');
      link.download = `QR_${training?.title || 'Training'}.png`;
      link.href = url;
      link.click();
    }
  };

  return (
    <div className="bg-white shadow overflow-hidden sm:rounded-lg">
      <div className="px-4 py-5 sm:px-6 border-b border-gray-200">
        <h3 className="text-lg leading-6 font-medium text-gray-900 text-center">Assessment QR Code</h3>
      </div>
      <div className="p-6 flex flex-col items-center justify-center space-y-4">
        <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-100">
          <QRCodeCanvas id="qr-code-canvas" value={qrCodeUrl} size={200} />
        </div>
        <button
          onClick={downloadQRCode}
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-brand-blue hover:bg-blue-700 focus:outline-none"
        >
          <ImageIcon className="-ml-1 mr-2 h-4 w-4" />
          Save QR Code as Image
        </button>
        <p className="text-sm text-center text-gray-500 mt-2">
          Scan this code to fill out the assessment form.
        </p>
        <a 
          href={qrCodeUrl} 
          target="_blank" 
          rel="noreferrer"
          className="text-brand-blue text-sm hover:underline break-all text-center"
        >
          {qrCodeUrl}
        </a>
      </div>
    </div>
  );
}
