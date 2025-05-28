import React from 'react';
import { HashRouter, Routes, Route } from 'react-router-dom';

const App = () => (
  <HashRouter>
    <Routes>
      <Route path="/" element={<div>Landing route</div>} />
      <Route path="/login" element={<div>Login route</div>} />
      <Route path="/register" element={<div>Register route</div>} />
      <Route path="/dashboard" element={<div>Dashboard route</div>} />
    </Routes>
  </HashRouter>
);

export default App;
