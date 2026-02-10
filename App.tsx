import React from 'react';
import { LoginPage } from './components/LoginPage';
import { LanguageProvider } from './contexts/LanguageContext';

function App() {
  return (
    <LanguageProvider>
      <div className="min-h-screen font-sans selection:bg-hd-gold/30 selection:text-hd-navy">
        <LoginPage />
      </div>
    </LanguageProvider>
  );
}

export default App;