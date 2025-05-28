import React from 'react';

type ErrorMessageProps = {
  message: string;
};

const ErrorMessage: React.FC<ErrorMessageProps> = ({ message }) => (
  <div className="text-red-600 bg-red-100 border border-red-400 rounded px-4 py-2 mt-2">
    {message}
  </div>
);

export default ErrorMessage; 