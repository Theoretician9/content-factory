import React from 'react';

type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

const Input: React.FC<InputProps> = (props) => {
  return (
    <input
      className="border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
      {...props}
    />
  );
};

export default Input; 