import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Integrations from './pages/Integrations';
import Parsing from './pages/Parsing';
import PrivateRoute from './PrivateRoute';
import { UserProvider } from './UserContext';

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
