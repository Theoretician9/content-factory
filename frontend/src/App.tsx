import React from 'react';
import { Routes, Route } from 'react-router-dom';

const App = () => (
  <Routes>
    <Route path="/" element={<div>Test route</div>} />
  </Routes>
);

export default App;
