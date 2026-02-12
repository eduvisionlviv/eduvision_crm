import React, { useState, useEffect } from 'react';
import { 
  LayoutDashboard, 
  BarChart3, 
  Settings, 
  LogOut, 
  Search, 
  Bell, 
  Menu, 
  X,
  User,
  ChevronRight
} from 'lucide-react';
import { useTranslation } from '../contexts/LanguageContext';
import { SettingsView } from './SettingsView';

interface DashboardProps {
  user: {
    name: string;
    email: string;
    role: string;
    token?: string;
  };
  onLogout: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ user, onLogout }) => {
  const { t, language, setLanguage } = useTranslation();
  const [isSidebarOpen, setIsSidebarOpen] = useState(window.innerWidth > 1024);
  const [activeTab, setActiveTab] = useState('dashboard');

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth <= 1024) {
        setIsSidebarOpen(false);
      } else {
        setIsSidebarOpen(true);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const menuItems = [
    { id: 'dashboard', label: t('nav.dashboard'), icon: LayoutDashboard },
    { id: 'reports', label: t('nav.reports'), icon: BarChart3 },
    { id: 'settings', label: t('nav.settings'), icon: Settings },
  ];

  const LOGO_URL = "https://enguide.ua/image.php?width=300&height=168&crop&image=/s/public/upload/images/7b30/5c3c/e544/04d2/ed8b/256b/35b0/b74c.png";

  const renderContent = () => {
    switch (activeTab) {
      case 'settings':
        return <SettingsView user={user} />;
      case 'reports':
        return (
            <div className="flex flex-col items-center justify-center h-[60vh] text-center p-8 bg-white rounded-[2.5rem] border border-slate-100 shadow-sm">
                <div className="w-20 h-20 bg-hd-gold/10 rounded-full flex items-center justify-center text-hd-gold mb-6">
                    <BarChart3 size={40} />
                </div>
                <h2 className="text-2xl font-black text-hd-navy uppercase tracking-tight mb-2">{t('nav.reports')}</h2>
                <p className="text-slate-500 font-medium max-w-md">Analytics module is under development.</p>
            </div>
        );
      case 'dashboard':
      default:
        return (
          <div className="space-y-12">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-10">
               {[
                 { title: t('nav.students') || 'Students', icon: User, color: 'bg-hd-green', tab: 'students' }, // Placeholder tab
                 { title: t('nav.reports'), icon: BarChart3, color: 'bg-hd-gold', tab: 'reports' },
                 { title: t('nav.settings'), icon: Settings, color: 'bg-hd-navy', tab: 'settings' }
               ].map((card, i) => (
                <div 
                  key={i} 
                  onClick={() => card.tab && setActiveTab(card.tab === 'students' ? 'dashboard' : card.tab)} // Prevent navigation to non-existent tabs for now
                  className="group relative aspect-video bg-white rounded-[2.5rem] border border-slate-100 p-8 flex flex-col justify-between shadow-sm hover:shadow-2xl hover:-translate-y-2 transition-all duration-500 overflow-hidden cursor-pointer"
                >
                  <div className={`w-14 h-14 ${card.color} rounded-2xl flex items-center justify-center text-white shadow-xl transform group-hover:rotate-6 transition-transform duration-500`}>
                    <card.icon size={28} />
                  </div>
                  <div>
                    <h3 className="text-xl font-black text-hd-navy uppercase tracking-tight">{card.title}</h3>
                    <div className="w-10 h-1.5 bg-hd-gold mt-3 rounded-full group-hover:w-full transition-all duration-500"></div>
                  </div>
                </div>
               ))}
            </div>

            <div className="p-12 bg-white rounded-[3rem] border border-dashed border-slate-200 flex flex-col items-center justify-center text-center animate-in fade-in zoom-in duration-1000">
               <div className="w-32 h-32 mb-8 relative">
                  <div className="absolute inset-0 bg-hd-gold/20 rounded-full animate-ping"></div>
                  <div className="relative z-10 w-full h-full bg-slate-50 rounded-full flex items-center justify-center border-4 border-white shadow-inner">
                    <img src={LOGO_URL} alt="HD" className="w-20 grayscale opacity-40" />
                  </div>
               </div>
               <h2 className="text-2xl font-black text-hd-navy uppercase tracking-tight">System Ready</h2>
               <p className="text-slate-500 mt-4 max-w-md font-bold text-xs uppercase tracking-widest">
                   Please proceed to settings to configure your center.
               </p>
               <button 
                onClick={() => setActiveTab('settings')}
                className="mt-8 flex items-center gap-2 bg-hd-navy text-hd-gold px-8 py-3.5 rounded-2xl font-black text-xs uppercase tracking-widest shadow-xl shadow-hd-navy/20 hover:scale-105 transition-all"
               >
                 {t('nav.settings')}
               </button>
            </div>
          </div>
        );
    }
  };

  return (
    <div className="flex h-screen bg-[#F8FAFC] text-slate-800 overflow-hidden font-sans">
      
      {/* Mobile Sidebar Overlay */}
      {isSidebarOpen && window.innerWidth <= 1024 && (
        <div 
          className="fixed inset-0 bg-hd-navy/60 backdrop-blur-sm z-[60] transition-opacity duration-300"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-[70] bg-hd-navy text-white transition-all duration-500 ease-in-out
        ${isSidebarOpen ? 'w-72 translate-x-0' : 'w-24 -translate-x-full lg:translate-x-0'}
        flex flex-col shadow-[10px_0_40px_rgba(0,33,71,0.2)]
      `}>
        {/* Logo Section */}
        <div className="p-4 flex flex-col items-center border-b border-white/5 h-36 justify-center overflow-hidden relative group cursor-default">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[80%] h-[80%] bg-white/5 blur-3xl rounded-full opacity-50"></div>
          
          <div className="relative flex items-center justify-center transition-all duration-500">
             <img 
               src={LOGO_URL} 
               alt="Helen Doron English" 
               className={`${isSidebarOpen ? 'w-24' : 'w-14'} h-auto object-contain transform group-hover:scale-105 transition-transform duration-500 drop-shadow-2xl`} 
             />
          </div>
          
          {isSidebarOpen && (
            <div className="mt-3 text-center animate-in fade-in duration-700 relative z-10">
               <div className="font-black text-[11px] tracking-[0.1em] uppercase text-white leading-none mb-1">
                 Helen Doron
               </div>
               <div className="font-black text-[13px] tracking-[0.2em] uppercase text-hd-gold leading-none">
                 English
               </div>
            </div>
          )}
          
          {window.innerWidth <= 1024 && isSidebarOpen && (
            <button onClick={() => setIsSidebarOpen(false)} className="absolute top-4 right-4 p-2 text-white/50 hover:text-white z-20">
              <X size={20} />
            </button>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-grow py-8 space-y-2 px-4 overflow-y-auto custom-scrollbar">
          {menuItems.map((item) => (
            <button
              key={item.id}
              onClick={() => {
                setActiveTab(item.id);
                if (window.innerWidth <= 1024) setIsSidebarOpen(false);
              }}
              className={`w-full flex items-center gap-4 px-4 py-4 rounded-2xl transition-all duration-300 group ${
                activeTab === item.id 
                ? 'bg-hd-gold text-hd-navy shadow-lg shadow-hd-gold/20' 
                : 'text-slate-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <item.icon size={22} className={`${activeTab === item.id ? '' : 'group-hover:scale-110 transition-transform duration-300'}`} />
              <span className={`font-black text-xs uppercase tracking-widest whitespace-nowrap transition-opacity duration-300 ${isSidebarOpen ? 'opacity-100' : 'hidden lg:hidden'}`}>
                {item.label}
              </span>
            </button>
          ))}
        </nav>

        {/* Footer Sidebar */}
        <div className="p-4 border-t border-white/5">
          <button 
            onClick={onLogout}
            className="w-full flex items-center gap-4 px-4 py-4 rounded-2xl text-hd-red/80 hover:bg-hd-red/10 hover:text-hd-red transition-all group font-black text-xs uppercase tracking-widest"
          >
            <LogOut size={22} className="group-hover:-translate-x-1 transition-transform" />
            <span className={`transition-opacity duration-300 ${isSidebarOpen ? 'opacity-100' : 'hidden lg:hidden'}`}>{t('nav.logout')}</span>
          </button>
        </div>
      </aside>

      {/* Main Area */}
      <main className={`flex-grow transition-all duration-500 ease-in-out ${isSidebarOpen && window.innerWidth > 1024 ? 'ml-72' : 'ml-0 lg:ml-24'} flex flex-col h-full relative`}>
        
        {/* Watermark Branding */}
        <div className="absolute bottom-[-5%] right-[-5%] w-[40%] max-w-[500px] opacity-[0.03] pointer-events-none select-none z-0">
            <img src={LOGO_URL} alt="" className="w-full h-auto grayscale" />
        </div>

        {/* Header */}
        <header className="h-20 bg-white/80 backdrop-blur-md border-b border-slate-200/50 flex items-center justify-between px-4 md:px-8 sticky top-0 z-[55]">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => setIsSidebarOpen(!isSidebarOpen)} 
              className="p-3 hover:bg-slate-100 rounded-2xl text-hd-navy transition-all"
            >
              <Menu size={20} />
            </button>
            
            <div className="relative hidden md:flex items-center">
              <Search className="absolute left-4 text-slate-400" size={18} />
              <input 
                type="text" 
                placeholder="Global Search..." 
                className="pl-12 pr-6 py-2.5 bg-slate-50 border border-transparent rounded-2xl text-sm w-48 lg:w-80 focus:bg-white focus:ring-4 focus:ring-hd-gold/10 focus:border-hd-gold/30 outline-none transition-all"
              />
            </div>
          </div>

          <div className="flex items-center gap-2 md:gap-5">
             <div className="flex items-center gap-1 bg-slate-100 p-1.5 rounded-2xl border border-slate-200/50">
                <button 
                  onClick={() => setLanguage('uk')} 
                  className={`px-3 py-1.5 text-[10px] font-black rounded-xl transition-all ${language === 'uk' ? 'bg-white text-hd-navy shadow-md' : 'text-slate-400'}`}
                >
                  UA
                </button>
                <button 
                  onClick={() => setLanguage('en')} 
                  className={`px-3 py-1.5 text-[10px] font-black rounded-xl transition-all ${language === 'en' ? 'bg-white text-hd-navy shadow-md' : 'text-slate-400'}`}
                >
                  EN
                </button>
             </div>

            <button className="relative p-3 text-slate-500 hover:bg-slate-50 rounded-2xl transition-all">
              <Bell size={20} />
              <span className="absolute top-3 right-3 w-2.5 h-2.5 bg-hd-red border-2 border-white rounded-full"></span>
            </button>
            
            <div className="h-8 w-px bg-slate-200 mx-1 hidden sm:block"></div>

            <div className="flex items-center gap-3 pl-2 group cursor-pointer">
              <div className="text-right hidden xl:block">
                <p className="text-xs font-black text-slate-900 leading-none uppercase tracking-tighter">{user.name}</p>
                <p className="text-[9px] text-hd-gold mt-1 uppercase tracking-[0.2em] font-black">{user.role}</p>
              </div>
              <div className="w-10 h-10 rounded-2xl bg-hd-navy flex items-center justify-center text-hd-gold font-black text-sm shadow-xl shadow-hd-navy/20 transform group-hover:scale-105 transition-all border-2 border-white">
                {user.name?.charAt(0) || 'U'}
              </div>
            </div>
          </div>
        </header>

        {/* Content */}
        <div className="p-4 md:p-8 lg:p-12 overflow-y-auto custom-scrollbar flex-grow z-10">
          <div className="max-w-7xl mx-auto">
            
            <div className="mb-10 animate-in fade-in slide-in-from-bottom-6 duration-700">
              <div className="flex items-center gap-2 text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">
                <span>Helen Doron English</span>
                <ChevronRight size={10} />
                <span className="text-hd-gold">{activeTab}</span>
              </div>
              <h1 className="text-3xl md:text-4xl font-black text-hd-navy tracking-tight uppercase">
                {activeTab === 'dashboard' ? t('nav.dashboard') : 
                 activeTab === 'reports' ? t('nav.reports') : 
                 t(`nav.${activeTab}`)}
              </h1>
              {activeTab === 'dashboard' && (
                <p className="text-slate-500 text-sm md:text-base mt-2 font-medium max-w-2xl">
                  {t('dashboard.welcome')} {user.name}. 
                </p>
              )}
            </div>

            {renderContent()}

          </div>
        </div>
        
        <footer className="h-12 border-t border-slate-100 bg-white/50 px-8 flex items-center justify-between text-[9px] font-black uppercase tracking-[0.3em] text-slate-400">
          <span className="hidden sm:inline">Helen Doron Educational Group</span>
          <span>CRM Production v1.0.0 • {new Date().getFullYear()}</span>
        </footer>

      </main>
    </div>
  );
};
