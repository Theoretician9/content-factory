import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

const App = () => {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<div>Landing route</div>} />
        <Route path="/login" element={<div>Login route</div>} />
        <Route path="/register" element={<div>Register route</div>} />
        <Route path="/dashboard" element={<div>Dashboard route</div>} />
      </Routes>
    </Router>
  );
};

export default App;
