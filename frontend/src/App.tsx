import React from 'react';
import { I18nextProvider } from 'react-i18next';
import i18n from './i18n';

const App = () => (
  <I18nextProvider i18n={i18n}>
    <div>i18n test</div>
  </I18nextProvider>
);

export default App;
