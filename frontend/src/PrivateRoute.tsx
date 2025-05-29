import React from 'react';
import { Navigate } from 'react-router-dom';
import { useUser } from './UserContext';

interface Props {
  children: React.ReactNode;
}

const PrivateRoute: React.FC<Props> = ({ children }) => {
  const { user, loading, error } = useUser();
  if (loading) {
    return <div className="flex flex-col items-center justify-center min-h-screen text-lg">Загрузка...</div>;
  }
  if (error) {
    return <Navigate to="/login" replace state={{ error }} />;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

export default PrivateRoute; 