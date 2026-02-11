import React, { useState } from 'react';
import { Mail, Lock, Eye, EyeOff, ArrowRight, Loader2, Building2, UserPlus } from 'lucide-react';
import { useTranslation } from '../contexts/LanguageContext';

export const LoginPage = () => {
  const { t, language, setLanguage } = useTranslation();
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [center, setCenter] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const LOGO_URL = "https://enguide.ua/image.php?width=300&height=168&crop&image=/s/public/upload/images/7b30/5c3c/e544/04d2/ed8b/256b/35b0/b74c.png";

  const centers: {id: string, name: string}[] = [];

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!center && centers.length > 0) {
        alert("Please select a learning center");
        return;
    }
    setIsLoading(true);
    // Simulate login
    setTimeout(() => setIsLoading(false), 2000);
  };

  const handleImageError = (e: React.SyntheticEvent<HTMLImageElement, Event>) => {
    // Try local file as fallback if external fails
    if (e.currentTarget.src !== window.location.origin + "/img/hd_logo.webp") {
        e.currentTarget.src = "img/hd_logo.webp";
    }
    e.currentTarget.onerror = null;
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center relative overflow-hidden bg-hd-navy">
      
      {/* Background Animated Elements */}
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
          {/* Main Rotating Logo Background */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] md:w-[1200px] md:h-[1200px] opacity-10 animate-spin-slow">
            <img 
              src={LOGO_URL} 
              onError={handleImageError}
              alt="" 
              className="w-full h-full object-contain filter blur-sm opacity-50" 
            />
          </div>
          
          {/* Floating Color Orbs */}
          <div className="absolute top-[-10%] left-[-5%] w-96 h-96 bg-hd-gold/20 rounded-full blur-[100px] animate-pulse-glow" />
          <div className="absolute bottom-[-10%] right-[-5%] w-96 h-96 bg-hd-red/20 rounded-full blur-[100px] animate-pulse-glow" style={{animationDelay: '2s'}} />
          <div className="absolute top-[40%] right-[10%] w-64 h-64 bg-hd-green/20 rounded-full blur-[80px] animate-float" />
          
          {/* Overlay Texture */}
          <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.04]"></div>
      </div>

      {/* Main Content */}
      <div className="relative z-10 w-full max-w-[450px] px-4">
        <div className="glass-panel p-8 md:p-12 rounded-3xl shadow-2xl relative overflow-hidden">
            
            {/* Top accent line */}
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-hd-red via-hd-gold to-hd-green"></div>

            {/* Language Switcher */}
            <div className="absolute top-6 right-6 flex items-center gap-1 bg-black/20 rounded-full p-1 border border-white/10">
                <button 
                    onClick={() => setLanguage('uk')}
                    className={`px-2 py-1 text-xs font-bold rounded-full transition-all ${language === 'uk' ? 'bg-hd-gold text-hd-navy' : 'text-slate-400 hover:text-white'}`}
                >
                    UA
                </button>
                <button 
                    onClick={() => setLanguage('en')}
                    className={`px-2 py-1 text-xs font-bold rounded-full transition-all ${language === 'en' ? 'bg-hd-gold text-hd-navy' : 'text-slate-400 hover:text-white'}`}
                >
                    EN
                </button>
            </div>

            {/* Logo Area */}
            <div className="flex flex-col items-center justify-center mb-8 mt-2">
                <div className="w-full max-w-[220px] mb-6 relative group">
                   {/* Ambient glow */}
                   <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[120%] bg-white/10 blur-2xl rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-700"></div>
                   
                   <img 
                     src={LOGO_URL} 
                     onError={handleImageError}
                     alt="Helen Doron English" 
                     className="w-full h-auto object-contain transform group-hover:scale-105 transition-transform duration-500 drop-shadow-2xl" 
                   />
                </div>
                <h1 className="text-2xl font-bold text-white text-center leading-tight">
                    Helen Doron English
                </h1>
            </div>

            <form onSubmit={handleLogin} className="space-y-5">
                
                {/* Learning Center Selection */}
                <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-slate-300 uppercase tracking-widest ml-1 opacity-80">{t('login.center')}</label>
                    <div className="relative group/input">
                        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within/input:text-hd-gold transition-colors">
                            <Building2 size={18} />
                        </div>
                        <div className="absolute inset-y-0 right-4 flex items-center pointer-events-none">
                            <div className="border-t-[4px] border-t-slate-400 border-l-[4px] border-l-transparent border-r-[4px] border-r-transparent"></div>
                        </div>
                        <select
                            value={center}
                            onChange={(e) => setCenter(e.target.value)}
                            className="block w-full pl-11 pr-10 py-3.5 input-glass rounded-xl text-white appearance-none cursor-pointer focus:ring-0 transition-all text-sm opacity-50 cursor-not-allowed"
                            required={centers.length > 0}
                            disabled={centers.length === 0}
                        >
                            <option value="" disabled className="bg-hd-navy text-slate-400">{t('login.centerPlaceholder')}</option>
                            {centers.map(c => (
                                <option key={c.id} value={c.id} className="bg-hd-navy text-white py-2">
                                    {c.name}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                {/* Email */}
                <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-slate-300 uppercase tracking-widest ml-1 opacity-80">{t('login.email')}</label>
                    <div className="relative group/input">
                        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within/input:text-hd-gold transition-colors">
                            <Mail size={18} />
                        </div>
                        <input 
                            type="email" 
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="block w-full pl-11 pr-4 py-3.5 input-glass rounded-xl text-white placeholder-slate-500 transition-all text-sm"
                            placeholder="username@helendoron.com"
                            required 
                        />
                    </div>
                </div>

                {/* Password */}
                <div className="space-y-1.5">
                    <div className="flex items-center justify-between ml-1">
                        <label className="text-[10px] font-bold text-slate-300 uppercase tracking-widest opacity-80">{t('login.password')}</label>
                        <a href="#" className="text-[10px] font-bold text-hd-gold hover:text-hd-gold/80 transition-colors uppercase tracking-wider">{t('login.forgotPassword')}</a>
                    </div>
                    <div className="relative group/input">
                        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within/input:text-hd-gold transition-colors">
                            <Lock size={18} />
                        </div>
                        <input 
                            type={showPassword ? "text" : "password"}
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="block w-full pl-11 pr-11 py-3.5 input-glass rounded-xl text-white placeholder-slate-500 transition-all text-sm"
                            placeholder="••••••••"
                            required 
                        />
                        <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 hover:text-white transition-colors"
                        >
                            {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                        </button>
                    </div>
                </div>

                <button 
                    type="submit" 
                    disabled={isLoading}
                    className="w-full relative overflow-hidden h-12 rounded-xl bg-gradient-to-r from-hd-gold to-[#e6c245] text-hd-navy font-bold text-sm uppercase tracking-wider shadow-lg hover:shadow-hd-gold/20 transform transition-all active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed group mt-2"
                >
                    <span className={`flex items-center justify-center gap-2 ${isLoading ? 'opacity-0' : 'opacity-100'}`}>
                        {t('login.submit')} <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                    </span>
                    
                    {isLoading && (
                        <div className="absolute inset-0 flex items-center justify-center text-hd-navy font-bold flex gap-2">
                             <Loader2 className="animate-spin" size={18} /> {t('login.loading')}
                        </div>
                    )}
                </button>

                {/* Registration Section */}
                <div className="mt-8 pt-6 border-t border-white/10 text-center">
                    <p className="text-slate-400 text-xs mb-3 uppercase tracking-widest opacity-70">{t('login.noAccount')}</p>
                    <button 
                        type="button"
                        className="w-full py-3 rounded-xl border border-white/10 hover:border-hd-gold/30 bg-white/5 hover:bg-white/10 text-white font-bold text-sm uppercase tracking-wider transition-all flex items-center justify-center gap-2 group shadow-lg hover:shadow-hd-gold/5"
                    >
                        <UserPlus size={16} className="text-hd-gold group-hover:scale-110 transition-transform" />
                        {t('login.register')}
                    </button>
                </div>
            </form>

            <div className="mt-8 text-center px-4">
                <p className="text-slate-500 text-[10px] leading-relaxed">
                    {t('login.footer_protected')} 
                    <a href="#" className="text-slate-400 hover:text-white underline decoration-slate-600 underline-offset-2 ml-1 transition-colors">{t('login.privacy')}</a>
                </p>
            </div>
        </div>
        
        {/* Footer info */}
        <div className="mt-8 text-center animate-fade-in-up">
            <p className="text-slate-500/60 text-[10px] tracking-[0.2em] font-light uppercase">
                {t('login.copyright')} {new Date().getFullYear()}
            </p>
        </div>
      </div>
    </div>
  );
};