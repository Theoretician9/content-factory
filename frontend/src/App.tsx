import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Integrations from './pages/Integrations';
import PrivateRoute from './PrivateRoute';
import { UserProvider } from './UserContext';

// Временная заглушка для страницы парсинга
const Parsing = () => {
  return (
    <div className="flex min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="flex items-center justify-center w-full">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">Парсинг</h1>
          <p>Страница парсинга в разработке</p>
        </div>
      </div>
    </div>
  );
};

const App = () => (
  <UserProvider>
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/dashboard" element={
        <PrivateRoute>
          <Dashboard />
        </PrivateRoute>
      } />
      <Route path="/integrations" element={
        <PrivateRoute>
          <Integrations />
        </PrivateRoute>
      } />
      <Route path="/parsing" element={
        <PrivateRoute>
          <Parsing />
        </PrivateRoute>
      } />
    </Routes>
  </UserProvider>
);

export default App;
