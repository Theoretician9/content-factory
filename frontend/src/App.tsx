import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';

const App = () => (
  <BrowserRouter>
    <Routes>
      <Route path="/" element={<div>Test route</div>} />
    </Routes>
  </BrowserRouter>
);

export default App;
