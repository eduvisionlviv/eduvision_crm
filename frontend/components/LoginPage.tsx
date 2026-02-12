import React, { useState, useEffect } from 'react';
import { Mail, Lock, Eye, EyeOff, ArrowRight, Loader2, Building2, UserPlus, ArrowLeft, User, Phone, ChevronDown, Globe } from 'lucide-react';
import { useTranslation } from '../contexts/LanguageContext';

type ViewState = 'login' | 'register' | 'forgot';

interface LoginPageProps {
  onLoginSuccess: (user: any) => void;
}

const HD_COUNTRY_CODES = [
  { code: '+380', flag: '🇺🇦', country: 'Ukraine' },
  { code: '+355', flag: '🇦🇱', country: 'Albania' },
  { code: '+43', flag: '🇦🇹', country: 'Austria' },
  { code: '+387', flag: '🇧🇦', country: 'Bosnia & Herz.' },
  { code: '+359', flag: '🇧🇬', country: 'Bulgaria' },
  { code: '+56', flag: '🇨🇱', country: 'Chile' },
  { code: '+86', flag: '🇨🇳', country: 'China' },
  { code: '+385', flag: '🇭🇷', country: 'Croatia' },
  { code: '+357', flag: '🇨🇾', country: 'Cyprus' },
  { code: '+420', flag: '🇨🇿', country: 'Czech Republic' },
  { code: '+593', flag: '🇪🇨', country: 'Ecuador' },
  { code: '+372', flag: '🇪🇪', country: 'Estonia' },
  { code: '+33', flag: '🇫🇷', country: 'France' },
  { code: '+49', flag: '🇩🇪', country: 'Germany' },
  { code: '+30', flag: '🇬🇷', country: 'Greece' },
  { code: '+36', flag: '🇭🇺', country: 'Hungary' },
  { code: '+972', flag: '🇮🇱', country: 'Israel' },
  { code: '+39', flag: '🇮🇹', country: 'Italy' },
  { code: '+7', flag: '🇰🇿', country: 'Kazakhstan' },
  { code: '+389', flag: '🇲🇰', country: 'Macedonia' },
  { code: '+52', flag: '🇲🇽', country: 'Mexico' },
  { code: '+382', flag: '🇲🇪', country: 'Montenegro' },
  { code: '+507', flag: '🇵🇦', country: 'Panama' },
  { code: '+51', flag: '🇵🇪', country: 'Peru' },
  { code: '+48', flag: '🇵🇱', country: 'Poland' },
  { code: '+351', flag: '🇵🇹', country: 'Portugal' },
  { code: '+40', flag: '🇷🇴', country: 'Romania' },
  { code: '+381', flag: '🇷🇸', country: 'Serbia' },
  { code: '+421', flag: '🇸🇰', country: 'Slovakia' },
  { code: '+386', flag: '🇸🇮', country: 'Slovenia' },
  { code: '+82', flag: '🇰🇷', country: 'South Korea' },
  { code: '+34', flag: '🇪🇸', country: 'Spain' },
  { code: '+41', flag: '🇨🇭', country: 'Switzerland' },
  { code: '+66', flag: '🇹🇭', country: 'Thailand' },
  { code: '+90', flag: '🇹🇷', country: 'Turkey' },
  { code: '+84', flag: '🇻🇳', country: 'Vietnam' },
].sort((a, b) => a.country.localeCompare(b.country));

const COUNTRY_CODES = [
  { code: '+380', flag: '🇺🇦', country: 'Ukraine' },
  ...HD_COUNTRY_CODES.filter(c => c.code !== '+380')
];

export const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess }) => {
  const { t, language, setLanguage } = useTranslation();
  
  const [view, setView] = useState<ViewState>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [center, setCenter] = useState(''); // Stores center ID
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [availableCenters, setAvailableCenters] = useState<{id: string, name: string}[]>([]);

  const [regData, setRegData] = useState({
    centerId: '',
    adminName: '',
    email: '',
    phonePrefix: '+380',
    phoneNumber: '',
  });

  const LOGO_URL = "https://enguide.ua/image.php?width=300&height=168&crop&image=/s/public/upload/images/7b30/5c3c/e544/04d2/ed8b/256b/35b0/b74c.png";

  // Fetch centers on component mount
  useEffect(() => {
    const fetchCenters = async () => {
      try {
        const response = await fetch('/api/pb/lc');
        if (response.ok) {
          const data = await response.json();
          // Universal API with Pydantic Schema returns 'name', not 'lc_name'
          const items = data.items || [];
          const centers = items.map((item: any) => ({
            id: item.id,
            name: item.name || item.lc_name || 'Unnamed Center' // Fallback to lc_name just in case, but prefer name
          }));
          setAvailableCenters(centers);
        }
      } catch (error) {
        console.error("Failed to load centers:", error);
      }
    };
    fetchCenters();
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    
    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          center: center,
          email: email.trim().toLowerCase(),
          password: password
        }),
      });

      const result = await response.json();

      if (response.ok && result.status === 'ok') {
        onLoginSuccess({
          // Backend Schema mappings: user_name -> name, user_mail -> email, etc.
          // Adjusting to accept both new cleaned format and potential raw format
          name: result.user.name || result.user.user_name || 'User',
          email: result.user.email || result.user.user_mail,
          role: result.user.role || 'staff',
          token: result.token
        });
      } else {
        alert(result.detail || "Login failed");
      }
    } catch (error) {
      console.error("Login error:", error);
      alert("Connection error. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    
    // Preparing data for the 'reg' table
    // Ensure keys match what Universal API expects (usually Snake Case matching DB or Pydantic Alias)
    const requestData = {
      center_id: regData.centerId,
      admin_name: regData.adminName.trim(),
      email: regData.email.trim().toLowerCase(),
      phone: `${regData.phonePrefix}${regData.phoneNumber.replace(/\D/g, '')}`,
      status: 'pending'
    };

    try {
      const response = await fetch('/api/pb/reg', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData)
      });

      if (response.ok) {
        alert(t('register.success'));
        setView('login');
        // Reset form
        setRegData({ ...regData, adminName: '', email: '', phoneNumber: '' });
      } else {
        const errorData = await response.json();
        alert(`Registration failed: ${errorData.detail || "Unknown error"}`);
      }
    } catch (error) {
       console.error(error);
       alert("Network error during registration.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleForgot = (e: React.FormEvent) => {
    e.preventDefault();
    // Placeholder for password reset logic
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      alert("Functionality coming soon. Please contact administrator.");
      setView('login');
    }, 1000);
  };

  const handleImageError = (e: React.SyntheticEvent<HTMLImageElement, Event>) => {
    if (e.currentTarget.src !== window.location.origin + "/img/hd_logo.webp") {
        e.currentTarget.src = "img/hd_logo.webp";
    }
    e.currentTarget.onerror = null;
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center relative overflow-hidden bg-hd-navy">
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] md:w-[1200px] md:h-[1200px] opacity-10 animate-spin-slow">
            <img 
              src={LOGO_URL} 
              onError={handleImageError}
              alt="" 
              className="w-full h-full object-contain filter blur-sm opacity-50" 
            />
          </div>
          <div className="absolute top-[-10%] left-[-5%] w-96 h-96 bg-hd-gold/20 rounded-full blur-[100px] animate-pulse-glow" />
          <div className="absolute bottom-[-10%] right-[-5%] w-96 h-96 bg-hd-red/20 rounded-full blur-[100px] animate-pulse-glow" style={{animationDelay: '2s'}} />
          <div className="absolute top-[40%] right-[10%] w-64 h-64 bg-hd-green/20 rounded-full blur-[80px] animate-float" />
          <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.04]"></div>
      </div>

      <div className="relative z-10 w-full max-w-[480px] px-4 py-8">
        <div className="glass-panel p-8 md:p-10 rounded-3xl shadow-2xl relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-hd-red via-hd-gold to-hd-green"></div>
            <div className="absolute top-6 right-6 flex items-center gap-1 bg-black/20 rounded-full p-1 border border-white/10">
                <button onClick={() => setLanguage('uk')} className={`px-2 py-1 text-xs font-bold rounded-full transition-all ${language === 'uk' ? 'bg-hd-gold text-hd-navy' : 'text-slate-400 hover:text-white'}`}>UA</button>
                <button onClick={() => setLanguage('en')} className={`px-2 py-1 text-xs font-bold rounded-full transition-all ${language === 'en' ? 'bg-hd-gold text-hd-navy' : 'text-slate-400 hover:text-white'}`}>EN</button>
            </div>

            <div className="flex flex-col items-center justify-center mb-8 mt-2">
                <div className="w-full max-w-[150px] mb-4 relative group cursor-pointer" onClick={() => setView('login')}>
                   <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[120%] bg-white/10 blur-2xl rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-700"></div>
                   <img src={LOGO_URL} onError={handleImageError} alt="Helen Doron English" className="w-full h-auto object-contain transform group-hover:scale-105 transition-transform duration-500 drop-shadow-2xl" />
                </div>
                <h1 className="text-xl font-extrabold text-white text-center leading-tight tracking-tight uppercase">
                    {view === 'login' ? 'Helen Doron English' : view === 'register' ? t('register.title') : t('forgot.title')}
                </h1>
            </div>

            {view === 'login' && (
              <form onSubmit={handleLogin} className="space-y-5 animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-300 uppercase tracking-widest ml-1 opacity-80">{t('login.center')}</label>
                      <div className="relative group/input">
                          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within/input:text-hd-gold transition-colors"><Building2 size={18} /></div>
                          <select value={center} onChange={(e) => setCenter(e.target.value)} className="block w-full pl-11 pr-10 py-3.5 input-glass rounded-xl text-white appearance-none cursor-pointer focus:ring-2 focus:ring-hd-gold/50 transition-all text-sm">
                              <option value="" className="bg-hd-navy text-slate-400">{t('login.centerPlaceholder')}</option>
                              {availableCenters.map(c => (
                                <option key={c.id} value={c.id} className="bg-hd-navy text-white">{c.name}</option>
                              ))}
                              {availableCenters.length === 0 && <option disabled className="bg-hd-navy text-slate-500">Loading centers...</option>}
                          </select>
                          <div className="absolute inset-y-0 right-4 flex items-center pointer-events-none text-slate-400"><ChevronDown size={16} /></div>
                      </div>
                  </div>

                  <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-300 uppercase tracking-widest ml-1 opacity-80">{t('login.email')}</label>
                      <div className="relative group/input">
                          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within/input:text-hd-gold transition-colors"><Mail size={18} /></div>
                          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="block w-full pl-11 pr-4 py-3.5 input-glass rounded-xl text-white placeholder-slate-500 transition-all text-sm focus:ring-2 focus:ring-hd-gold/50" placeholder="username@helendoron.com" required />
                      </div>
                  </div>

                  <div className="space-y-1.5">
                      <div className="flex items-center justify-between ml-1">
                          <label className="text-[10px] font-bold text-slate-300 uppercase tracking-widest opacity-80">{t('login.password')}</label>
                          <button type="button" onClick={() => setView('forgot')} className="text-[10px] font-bold text-hd-gold hover:text-hd-gold/80 transition-colors uppercase tracking-wider">{t('login.forgotPassword')}</button>
                      </div>
                      <div className="relative group/input">
                          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within/input:text-hd-gold transition-colors"><Lock size={18} /></div>
                          <input type={showPassword ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} className="block w-full pl-11 pr-11 py-3.5 input-glass rounded-xl text-white placeholder-slate-500 transition-all text-sm focus:ring-2 focus:ring-hd-gold/50" placeholder="••••••••" required />
                          <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 hover:text-white transition-colors">
                              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                          </button>
                      </div>
                  </div>

                  <button type="submit" disabled={isLoading} className="w-full relative overflow-hidden h-12 rounded-xl bg-gradient-to-r from-hd-gold to-[#e6c245] text-hd-navy font-black text-sm uppercase tracking-widest shadow-lg hover:shadow-hd-gold/40 transform transition-all active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed group mt-2">
                      <span className={`flex items-center justify-center gap-2 ${isLoading ? 'opacity-0' : 'opacity-100'}`}>
                          {t('login.submit')} <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                      </span>
                      {isLoading && <div className="absolute inset-0 flex items-center justify-center text-hd-navy font-bold flex gap-2"><Loader2 className="animate-spin" size={18} /> {t('login.loading')}</div>}
                  </button>

                  <div className="mt-8 pt-6 border-t border-white/10 text-center">
                      <p className="text-slate-400 text-[10px] mb-4 uppercase tracking-[0.2em] font-bold opacity-60">{t('login.noAccount')}</p>
                      <button type="button" onClick={() => setView('register')} className="w-full py-3.5 rounded-xl border border-white/10 hover:border-hd-gold/40 bg-white/5 hover:bg-white/10 text-white font-bold text-xs uppercase tracking-widest transition-all flex items-center justify-center gap-2 group shadow-xl">
                          <UserPlus size={16} className="text-hd-gold group-hover:scale-110 transition-transform" />
                          {t('login.register')}
                      </button>
                  </div>
              </form>
            )}

            {view === 'register' && (
              <form onSubmit={handleRegister} className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-500">
                  <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-300 uppercase tracking-widest ml-1 opacity-80">{t('register.centerName')}</label>
                      <div className="relative group/input">
                          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within/input:text-hd-gold transition-colors"><Building2 size={18} /></div>
                          <select required value={regData.centerId} onChange={(e) => setRegData({...regData, centerId: e.target.value})} className="block w-full pl-11 pr-10 py-3 input-glass rounded-xl text-white appearance-none cursor-pointer focus:ring-2 focus:ring-hd-gold/50 transition-all text-sm">
                              <option value="" disabled className="bg-hd-navy text-slate-400">{t('login.centerPlaceholder')}</option>
                              {availableCenters.map(c => (<option key={c.id} value={c.id} className="bg-hd-navy text-white">{c.name}</option>))}
                              {availableCenters.length === 0 && (<option disabled className="bg-hd-navy text-slate-500 italic">No centers available</option>)}
                          </select>
                          <div className="absolute inset-y-0 right-4 flex items-center pointer-events-none text-slate-400"><ChevronDown size={16} /></div>
                      </div>
                  </div>

                  <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-300 uppercase tracking-widest ml-1 opacity-80">{t('register.adminName')}</label>
                      <div className="relative group/input">
                          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within/input:text-hd-gold transition-colors"><User size={18} /></div>
                          <input type="text" required value={regData.adminName} onChange={(e) => setRegData({...regData, adminName: e.target.value})} className="block w-full pl-11 pr-4 py-3 input-glass rounded-xl text-white text-sm focus:ring-2 focus:ring-hd-gold/50 transition-all" placeholder="John Smith" />
                      </div>
                  </div>

                  <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-300 uppercase tracking-widest ml-1 opacity-80">{t('login.email')}</label>
                      <div className="relative group/input">
                          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within/input:text-hd-gold transition-colors"><Mail size={18} /></div>
                          <input type="email" required value={regData.email} onChange={(e) => setRegData({...regData, email: e.target.value})} className="block w-full pl-11 pr-4 py-3 input-glass rounded-xl text-white text-sm focus:ring-2 focus:ring-hd-gold/50 transition-all" placeholder="admin@helendoron.com" />
                      </div>
                  </div>

                  <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-300 uppercase tracking-widest ml-1 opacity-80">{t('register.phone')}</label>
                      <div className="flex gap-2">
                          <div className="relative w-[130px] flex-shrink-0 group/prefix">
                              <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none text-slate-400 group-focus-within/prefix:text-hd-gold transition-colors"><Globe size={14} /></div>
                              <select value={regData.phonePrefix} onChange={(e) => setRegData({...regData, phonePrefix: e.target.value})} className="w-full pl-9 pr-6 py-3 input-glass rounded-xl text-white text-sm appearance-none cursor-pointer focus:ring-2 focus:ring-hd-gold/50 transition-all">
                                {COUNTRY_CODES.map(c => (<option key={`${c.country}-${c.code}`} value={c.code} className="bg-hd-navy text-white">{c.flag} {c.code}</option>))}
                              </select>
                              <div className="absolute inset-y-0 right-2 flex items-center pointer-events-none text-slate-400"><ChevronDown size={14} /></div>
                          </div>
                          <div className="relative flex-grow group/input">
                              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within/input:text-hd-gold transition-colors"><Phone size={16} /></div>
                              <input type="tel" required value={regData.phoneNumber} onChange={(e) => setRegData({...regData, phoneNumber: e.target.value})} className="block w-full pl-11 pr-4 py-3 input-glass rounded-xl text-white text-sm focus:ring-2 focus:ring-hd-gold/50 transition-all" placeholder="990001122" />
                          </div>
                      </div>
                  </div>

                  <button type="submit" disabled={isLoading} className="w-full relative overflow-hidden h-12 rounded-xl bg-gradient-to-r from-hd-gold to-[#e6c245] text-hd-navy font-black text-sm uppercase tracking-widest shadow-lg transform transition-all active:scale-[0.98] mt-2">
                      {isLoading ? <Loader2 className="animate-spin mx-auto" size={20} /> : t('register.submit')}
                  </button>

                  <button type="button" onClick={() => setView('login')} className="w-full py-2 text-slate-400 hover:text-white text-[10px] font-black uppercase tracking-[0.2em] transition-colors flex items-center justify-center gap-2"><ArrowLeft size={14} /> {t('register.back')}</button>
              </form>
            )}

            {view === 'forgot' && (
              <form onSubmit={handleForgot} className="space-y-5 animate-in fade-in slide-in-from-left-4 duration-500">
                  <div className="text-center mb-2 px-2"><p className="text-slate-300 text-sm leading-relaxed opacity-80 font-medium italic">{t('forgot.description')}</p></div>
                  <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-300 uppercase tracking-widest ml-1 opacity-80">{t('login.email')}</label>
                      <div className="relative group/input">
                          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within/input:text-hd-gold transition-colors"><Mail size={18} /></div>
                          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="block w-full pl-11 pr-4 py-3.5 input-glass rounded-xl text-white placeholder-slate-500 transition-all text-sm focus:ring-2 focus:ring-hd-gold/50" placeholder="username@helendoron.com" required />
                      </div>
                  </div>
                  <button type="submit" disabled={isLoading} className="w-full relative overflow-hidden h-12 rounded-xl bg-gradient-to-r from-hd-gold to-[#e6c245] text-hd-navy font-black text-sm uppercase tracking-widest shadow-lg transform transition-all active:scale-[0.98] mt-2">
                      {isLoading ? <Loader2 className="animate-spin mx-auto" size={20} /> : t('forgot.submit')}
                  </button>
                  <button type="button" onClick={() => setView('login')} className="w-full py-2 text-slate-400 hover:text-white text-[10px] font-black uppercase tracking-[0.2em] transition-colors flex items-center justify-center gap-2"><ArrowLeft size={14} /> {t('forgot.back')}</button>
              </form>
            )}

            <div className="mt-8 text-center px-4">
                <p className="text-slate-500 text-[10px] leading-relaxed font-bold uppercase tracking-wider opacity-60">
                    {t('login.footer_protected')} 
                    <a href="#" className="text-hd-gold/80 hover:text-hd-gold underline decoration-hd-gold/40 underline-offset-4 ml-1 transition-colors">{t('login.privacy')}</a>
                </p>
            </div>
        </div>
        
        <div className="mt-8 text-center animate-fade-in-up">
            <p className="text-slate-500/40 text-[9px] tracking-[0.3em] font-black uppercase">
                {t('login.copyright')} {new Date().getFullYear()}
            </p>
        </div>
      </div>
    </div>
  );
};
