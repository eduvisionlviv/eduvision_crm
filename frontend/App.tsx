import React, { useState } from 'react';
import { LoginPage } from './components/LoginPage';
import { Dashboard } from './components/Dashboard';
import { LanguageProvider } from './contexts/LanguageContext';

interface User {
  name: string;
  email: string;
  role: string;
}

function App() {
  const [user, setUser] = useState<User | null>(null);

  // This function will be called when login is successful.
  // Later, you can easily replace the contents with a real API call.
  const handleLoginSuccess = (userData: User) => {
    setUser(userData);
  };

  const handleLogout = () => {
    setUser(null);
  };

  return (
    <LanguageProvider>
      <div className="min-h-screen font-sans selection:bg-hd-gold/30 selection:text-hd-navy">
        {!user ? (
          <LoginPage onLoginSuccess={handleLoginSuccess} />
        ) : (
          <Dashboard user={user} onLogout={handleLogout} />
        )}
      </div>
    </LanguageProvider>
  );
}

export default App;