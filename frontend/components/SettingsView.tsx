import React, { useState, useEffect } from 'react';
import { 
  User, 
  Lock, 
  ShieldCheck, 
  Building, 
  Users, 
  BookOpen, 
  DoorOpen, 
  Share2, 
  Plus, 
  Camera, 
  Mail, 
  Phone,
  Pencil,
  Trash2,
  Globe,
  Instagram,
  Facebook,
  MessageCircle,
  ChevronLeft,
  MapPin,
  Coins,
  ArrowRight,
  ExternalLink,
  Inbox,
  Loader2
} from 'lucide-react';
import { useTranslation } from '../contexts/LanguageContext';

interface SettingsViewProps {
  user: any;
}

interface Center {
  id: string;
  name: string;
  address: string;
  phone: string;
  currency: string;
  staffCount: number;
}

interface StaffMember {
  id: string;
  name: string;
  email: string;
  role: string;
}

export const SettingsView: React.FC<SettingsViewProps> = ({ user }) => {
  const { t } = useTranslation();
  const isAdmin = user.role === 'admin' || user.role === 'owner'; // Розширена перевірка прав
  const [activeMainTab, setActiveMainTab] = useState<'profile' | 'admin'>(isAdmin ? 'admin' : 'profile');
  const [activeProfileSubTab, setActiveProfileSubTab] = useState<'info' | 'security'>('info');
  
  // Admin State
  const [selectedCenter, setSelectedCenter] = useState<Center | null>(null);
  const [activeAdminSubTab, setActiveAdminSubTab] = useState<'info' | 'staff' | 'courses' | 'rooms' | 'sources'>('info');
  const [isLoading, setIsLoading] = useState(false);

  // Data States
  const [centers, setCenters] = useState<Center[]>([]);
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [courses, setCourses] = useState<any[]>([]);
  const [rooms, setRooms] = useState<any[]>([]);
  const [sources, setSources] = useState<any[]>([]);

  // 1. Fetch Centers when Admin tab is active
  useEffect(() => {
    if (activeMainTab === 'admin') {
      const fetchCenters = async () => {
        setIsLoading(true);
        try {
          const res = await fetch('/api/pb/lc');
          if (res.ok) {
            const data = await res.json();
            // Мапимо дані з БД у наш інтерфейс
            // Враховуємо нову схему Pydantic (clean names) та fallback на старі назви
            const mappedCenters = (data.items || []).map((item: any) => ({
              id: item.id,
              name: item.name || item.lc_name || 'Unnamed Center',
              address: item.address || item.lc_address || '',
              phone: item.phone || item.lc_phone || '',
              currency: item.currency || 'UAH',
              staffCount: item.staff_count || 0 
            }));
            setCenters(mappedCenters);
          }
        } catch (error) {
          console.error("Error fetching centers:", error);
        } finally {
          setIsLoading(false);
        }
      };
      fetchCenters();
    }
  }, [activeMainTab]);

  // 2. Fetch Staff/Data when a Center is selected
  useEffect(() => {
    if (selectedCenter && activeAdminSubTab === 'staff') {
      const fetchStaff = async () => {
        try {
          // Використовуємо універсальний фільтр: col:op:val
          // Бекенд очікує lc_id або center_id в залежності від схеми
          const res = await fetch(`/api/pb/user_staff?filters=lc_id:eq:${selectedCenter.id}`); 
          if (res.ok) {
            const data = await res.json();
            const mappedStaff = (data.items || []).map((item: any) => ({
              id: item.id,
              // Новий бекенд повертає чисті імена (name, email), старий (user_name, user_mail)
              name: item.name || item.user_name || 'Unknown',
              email: item.email || item.user_mail || '',
              role: item.role || item.user_role || 'staff'
            }));
            setStaff(mappedStaff);
          }
        } catch (error) {
          console.error("Error fetching staff:", error);
        }
      };
      fetchStaff();
    }
    // Тут можна додати запити для courses, rooms, sources за аналогією
  }, [selectedCenter, activeAdminSubTab]);

  const EmptyState = ({ message, actionLabel, onAction, icon: Icon = Inbox }: any) => (
    <div className="flex flex-col items-center justify-center py-20 text-center animate-in fade-in zoom-in duration-500">
      <div className="w-20 h-20 bg-slate-50 rounded-[2rem] flex items-center justify-center text-slate-200 mb-6 shadow-inner">
        <Icon size={40} />
      </div>
      <h3 className="text-lg font-black text-hd-navy uppercase tracking-tight">{message}</h3>
      <p className="text-slate-400 text-xs font-bold uppercase tracking-widest mt-2 mb-8">Дані відсутні або ще не завантажені</p>
      {onAction && (
        <button 
          onClick={onAction}
          className="flex items-center gap-2 bg-hd-gold text-hd-navy px-8 py-3.5 rounded-2xl font-black text-xs uppercase tracking-widest shadow-xl shadow-hd-gold/20 hover:scale-105 transition-all"
        >
          <Plus size={18} /> {actionLabel}
        </button>
      )}
    </div>
  );

  return (
    <div className="flex flex-col h-full animate-in fade-in duration-500">
      {/* Settings Navigation */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-8">
        <div className="flex bg-slate-100 p-1.5 rounded-2xl w-fit border border-slate-200/50">
          <button 
            onClick={() => setActiveMainTab('profile')}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${activeMainTab === 'profile' ? 'bg-white text-hd-navy shadow-md' : 'text-slate-400 hover:text-slate-600'}`}
          >
            <User size={16} />
            {t('settings.profile')}
          </button>
          {isAdmin && (
            <button 
              onClick={() => setActiveMainTab('admin')}
              className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${activeMainTab === 'admin' ? 'bg-hd-navy text-hd-gold shadow-lg shadow-hd-navy/20' : 'text-slate-400 hover:text-slate-600'}`}
            >
              <ShieldCheck size={16} />
              {t('settings.admin_panel')}
            </button>
          )}
        </div>

        <div className="flex gap-2">
          {activeMainTab === 'profile' && [
            { id: 'info', label: t('settings.personal_info'), icon: User },
            { id: 'security', label: t('settings.security'), icon: Lock },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveProfileSubTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-wider transition-all border ${
                activeProfileSubTab === tab.id 
                ? 'bg-hd-navy text-white shadow-md' 
                : 'bg-white border-slate-200 text-slate-500 hover:border-slate-400'
              }`}
            >
              <tab.icon size={14} />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-grow">
        {activeMainTab === 'profile' ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-1">
              <div className="bg-white rounded-[2.5rem] p-8 border border-slate-100 shadow-sm flex flex-col items-center">
                <div className="relative group cursor-pointer">
                  <div className="w-40 h-40 rounded-[2.5rem] bg-hd-navy flex items-center justify-center text-hd-gold text-5xl font-black shadow-2xl border-4 border-white transform transition-transform group-hover:scale-105 overflow-hidden">
                    {user.name?.charAt(0) || 'U'}
                  </div>
                  <div className="absolute inset-0 bg-black/40 rounded-[2.5rem] opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                    <div className="flex flex-col items-center gap-2">
                      <Camera className="text-white" size={32} />
                      <span className="text-[10px] text-white font-black uppercase tracking-widest">Змінити</span>
                    </div>
                  </div>
                </div>
                <h3 className="mt-6 text-xl font-black text-hd-navy uppercase tracking-tight text-center">{user.name}</h3>
                <p className="text-hd-gold text-[10px] font-black uppercase tracking-[0.2em] mt-1">{user.role}</p>
                <div className="mt-8 w-full h-px bg-slate-100"></div>
                <div className="mt-6 w-full space-y-4">
                   <div className="flex items-center gap-3 text-slate-500">
                      <Mail size={16} className="text-hd-navy/30" />
                      <span className="text-xs font-medium">{user.email}</span>
                   </div>
                   <div className="flex items-center gap-3 text-slate-500">
                      <Phone size={16} className="text-hd-navy/30" />
                      <span className="text-xs font-medium">Вкажіть телефон</span>
                   </div>
                </div>
              </div>
            </div>

            <div className="lg:col-span-2">
              {activeProfileSubTab === 'info' ? (
                <div className="bg-white rounded-[2.5rem] p-8 border border-slate-100 shadow-sm space-y-8">
                  <h2 className="text-xl font-black text-hd-navy uppercase tracking-tight flex items-center gap-3">
                    <User className="text-hd-gold" size={24} />
                    {t('settings.personal_info')}
                  </h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">Ім'я та Прізвище</label>
                      <input type="text" defaultValue={user.name} className="w-full px-5 py-3.5 bg-slate-50 border border-slate-200 rounded-2xl text-sm focus:ring-4 focus:ring-hd-gold/10 focus:border-hd-gold/30 outline-none transition-all font-bold text-hd-navy" />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">Телефон</label>
                      <input type="tel" placeholder="+380..." className="w-full px-5 py-3.5 bg-slate-50 border border-slate-200 rounded-2xl text-sm focus:ring-4 focus:ring-hd-gold/10 focus:border-hd-gold/30 outline-none transition-all font-bold text-hd-navy" />
                    </div>
                    <div className="space-y-1.5 md:col-span-2 opacity-60">
                      <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">Email (Тільки читання)</label>
                      <div className="relative">
                        <input type="email" readOnly value={user.email} className="w-full px-5 py-3.5 bg-slate-100 border border-slate-200 rounded-2xl text-sm cursor-not-allowed outline-none font-bold text-slate-500" />
                        <Lock className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-300" size={16} />
                      </div>
                    </div>
                  </div>
                  <button className="bg-hd-gold text-hd-navy px-10 py-4 rounded-2xl font-black text-xs uppercase tracking-widest shadow-xl shadow-hd-gold/20 hover:shadow-hd-gold/40 hover:-translate-y-0.5 transition-all">
                    {t('settings.save_changes')}
                  </button>
                </div>
              ) : (
                <div className="bg-white rounded-[2.5rem] p-8 border border-slate-100 shadow-sm space-y-8">
                  <h2 className="text-xl font-black text-hd-navy uppercase tracking-tight flex items-center gap-3">
                    <Lock className="text-hd-red" size={24} />
                    {t('settings.security')}
                  </h2>
                  <div className="max-w-md space-y-6">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">{t('settings.old_password')}</label>
                      <input type="password" placeholder="••••••••" className="w-full px-5 py-3.5 bg-slate-50 border border-slate-200 rounded-2xl text-sm focus:ring-4 focus:ring-hd-red/10 focus:border-hd-red/30 outline-none transition-all font-bold text-hd-navy" />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">{t('settings.new_password')}</label>
                      <input type="password" placeholder="••••••••" className="w-full px-5 py-3.5 bg-slate-50 border border-slate-200 rounded-2xl text-sm focus:ring-4 focus:ring-hd-green/10 focus:border-hd-green/30 outline-none transition-all font-bold text-hd-navy" />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">{t('settings.confirm_password')}</label>
                      <input type="password" placeholder="••••••••" className="w-full px-5 py-3.5 bg-slate-50 border border-slate-200 rounded-2xl text-sm focus:ring-4 focus:ring-hd-green/10 focus:border-hd-green/30 outline-none transition-all font-bold text-hd-navy" />
                    </div>
                  </div>
                  <button className="bg-hd-navy text-white px-10 py-4 rounded-2xl font-black text-xs uppercase tracking-widest shadow-xl shadow-hd-navy/20 hover:shadow-hd-navy/40 hover:-translate-y-0.5 transition-all">
                    {t('settings.change_password')}
                  </button>
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Admin Panel - Center Centric */
          <div className="space-y-6">
            {!selectedCenter ? (
              <div className="space-y-8 animate-in fade-in duration-500">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-3xl font-black text-hd-navy uppercase tracking-tight">Навчальні центри</h2>
                    <p className="text-slate-400 text-xs font-bold uppercase tracking-widest mt-1">Керування підрозділами мережі</p>
                  </div>
                  <button className="flex items-center gap-2 bg-hd-navy text-hd-gold px-6 py-3 rounded-2xl font-black text-xs uppercase tracking-widest shadow-xl hover:-translate-y-1 transition-all">
                    <Plus size={18} /> Додати центр
                  </button>
                </div>

                {isLoading ? (
                  <div className="flex justify-center py-20"><Loader2 className="animate-spin text-hd-navy" size={40} /></div>
                ) : centers.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
                    {centers.map((center) => (
                      <div 
                        key={center.id} 
                        onClick={() => setSelectedCenter(center)}
                        className="group bg-white rounded-3xl border border-slate-100 p-5 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all duration-300 cursor-pointer flex flex-col justify-between"
                      >
                        <div>
                          <div className="flex items-start justify-between mb-4">
                            <div className="w-10 h-10 bg-slate-50 rounded-xl flex items-center justify-center text-hd-navy group-hover:bg-hd-gold transition-colors duration-300 shadow-inner">
                              <Building size={20} />
                            </div>
                            <div className="px-2 py-1 bg-hd-navy/5 rounded-lg text-[8px] font-black uppercase text-hd-navy tracking-wider">
                              {center.currency}
                            </div>
                          </div>
                          <h3 className="text-md font-black text-hd-navy uppercase tracking-tight leading-tight group-hover:text-hd-gold transition-colors">{center.name}</h3>
                          <div className="mt-4 space-y-2">
                            <div className="flex items-start gap-2 text-slate-400">
                              <MapPin size={12} className="mt-0.5 flex-shrink-0" />
                              <span className="text-[10px] font-bold line-clamp-1">{center.address || 'Адресу не вказано'}</span>
                            </div>
                          </div>
                        </div>
                        <div className="mt-5 pt-4 border-t border-slate-50 flex items-center justify-between">
                           <div className="flex gap-3">
                              <div className="flex flex-col">
                                 <span className="text-[8px] font-black uppercase text-slate-300 tracking-tighter">Співробітники</span>
                                 <span className="text-xs font-black text-hd-navy">{center.staffCount || '-'}</span>
                              </div>
                           </div>
                           <div className="w-8 h-8 rounded-xl bg-slate-50 flex items-center justify-center text-slate-300 group-hover:bg-hd-navy group-hover:text-hd-gold transition-all">
                              <ArrowRight size={16} />
                           </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="bg-white rounded-[3rem] p-12 border border-slate-100 shadow-sm">
                    <EmptyState message="У вас ще немає створених центрів" actionLabel="Створити перший центр" onAction={() => {}} icon={Building} />
                  </div>
                )}
              </div>
            ) : (
              <div className="animate-in slide-in-from-right duration-500">
                <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-8 bg-white p-6 md:p-8 rounded-[2.5rem] border border-slate-100 shadow-sm relative overflow-hidden">
                   <div className="absolute top-0 right-0 p-8 opacity-5"><Building size={120} className="text-hd-navy" /></div>
                   <div className="flex items-center gap-6 relative z-10">
                      <button onClick={() => setSelectedCenter(null)} className="w-12 h-12 rounded-2xl bg-slate-50 flex items-center justify-center text-slate-400 hover:bg-hd-navy hover:text-white transition-all shadow-inner border border-slate-100"><ChevronLeft size={24} /></button>
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                           <span className="text-[9px] font-black uppercase text-hd-gold tracking-[0.2em]">Навчальний центр</span>
                           <div className="w-1 h-1 rounded-full bg-slate-200"></div>
                           <span className="text-[9px] font-black uppercase text-slate-400 tracking-[0.2em]">{selectedCenter.id}</span>
                        </div>
                        <h2 className="text-3xl font-black text-hd-navy uppercase tracking-tight">{selectedCenter.name}</h2>
                        <div className="flex flex-wrap gap-4 mt-2">
                           <span className="text-[10px] font-bold text-slate-500 flex items-center gap-1.5"><MapPin size={12} className="text-hd-gold" /> {selectedCenter.address}</span>
                           <span className="text-[10px] font-bold text-slate-500 flex items-center gap-1.5"><Phone size={12} className="text-hd-gold" /> {selectedCenter.phone}</span>
                           <span className="text-[10px] font-bold text-slate-500 flex items-center gap-1.5"><Coins size={12} className="text-hd-gold" /> {selectedCenter.currency}</span>
                        </div>
                      </div>
                   </div>
                   <div className="flex gap-1.5 overflow-x-auto pb-2 md:pb-0 custom-scrollbar relative z-10">
                      {[
                        { id: 'info', label: 'Інфо', icon: Building },
                        { id: 'staff', label: t('settings.staff'), icon: Users },
                        { id: 'courses', label: t('settings.courses'), icon: BookOpen },
                        { id: 'rooms', label: t('settings.rooms'), icon: DoorOpen },
                        { id: 'sources', label: t('settings.sources'), icon: Share2 },
                      ].map((tab) => (
                        <button key={tab.id} onClick={() => setActiveAdminSubTab(tab.id as any)} className={`flex items-center gap-2 px-5 py-3 rounded-2xl text-[10px] font-black uppercase tracking-wider transition-all border shadow-sm ${activeAdminSubTab === tab.id ? 'bg-hd-gold text-hd-navy border-hd-gold shadow-hd-gold/20' : 'bg-white border-slate-100 text-slate-400 hover:bg-slate-50 hover:border-slate-300'}`}>
                          <tab.icon size={14} /> {tab.label}
                        </button>
                      ))}
                   </div>
                </div>

                <div className="bg-white rounded-[3rem] p-8 md:p-12 border border-slate-100 shadow-sm min-h-[450px]">
                   {activeAdminSubTab === 'info' && (
                     <div className="max-w-4xl space-y-10 animate-in fade-in duration-300">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                           <div className="space-y-2">
                              <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Назва центру (LCF)</label>
                              <div className="relative">
                                 <Building className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-300" size={18} />
                                 <input type="text" defaultValue={selectedCenter.name} className="w-full pl-14 pr-6 py-4 bg-slate-50 border border-slate-100 rounded-2xl font-bold text-hd-navy focus:ring-4 focus:ring-hd-gold/10 outline-none transition-all" />
                              </div>
                           </div>
                           <div className="space-y-2">
                              <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Валюта розрахунків</label>
                              <div className="relative">
                                 <Coins className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-300" size={18} />
                                 <select className="w-full pl-14 pr-6 py-4 bg-slate-50 border border-slate-100 rounded-2xl font-bold text-hd-navy outline-none appearance-none cursor-pointer">
                                    <option>UAH (Українська гривня)</option>
                                    <option>USD (Долар США)</option>
                                    <option>EUR (Євро)</option>
                                 </select>
                              </div>
                           </div>
                           <div className="space-y-2 md:col-span-2">
                              <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Адреса</label>
                              <div className="relative">
                                 <MapPin className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-300" size={18} />
                                 <input type="text" defaultValue={selectedCenter.address} className="w-full pl-14 pr-6 py-4 bg-slate-50 border border-slate-100 rounded-2xl font-bold text-hd-navy outline-none" />
                              </div>
                           </div>
                        </div>
                        <div className="pt-6 border-t border-slate-50 flex items-center justify-between">
                           <button className="bg-hd-navy text-white px-10 py-4 rounded-2xl font-black text-xs uppercase tracking-widest shadow-xl shadow-hd-navy/20 hover:shadow-hd-navy/40 hover:-translate-y-1 transition-all">Зберегти зміни</button>
                           <button className="text-hd-red/60 hover:text-hd-red text-[10px] font-black uppercase tracking-widest flex items-center gap-2 transition-colors"><Trash2 size={16} /> Видалити центр</button>
                        </div>
                     </div>
                   )}

                   {activeAdminSubTab === 'staff' && (
                     <div className="space-y-8 animate-in fade-in duration-300">
                        {staff.length > 0 ? (
                           <div className="overflow-x-auto custom-scrollbar">
                              <table className="w-full border-separate border-spacing-y-3">
                                 <thead>
                                    <tr className="text-[9px] font-black text-slate-300 uppercase tracking-[0.2em] text-left">
                                       <th className="px-6 py-2">Співробітник</th>
                                       <th className="px-6 py-2">Роль</th>
                                       <th className="px-6 py-2 text-right">Дії</th>
                                    </tr>
                                 </thead>
                                 <tbody>
                                    {staff.map((s, i) => (
                                       <tr key={i} className="group bg-slate-50/40 hover:bg-slate-50 transition-colors">
                                          <td className="px-6 py-4 rounded-l-2xl">
                                             <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 rounded-xl bg-hd-navy text-hd-gold flex items-center justify-center font-black shadow-sm group-hover:scale-105 transition-transform">{s.name.charAt(0)}</div>
                                                <div>
                                                   <p className="text-sm font-black text-hd-navy">{s.name}</p>
                                                   <p className="text-[10px] text-slate-400 font-medium">{s.email}</p>
                                                </div>
                                             </div>
                                          </td>
                                          <td className="px-6 py-4">
                                             <span className="px-2 py-1 bg-slate-200 rounded text-[10px] font-bold text-slate-600 uppercase">{s.role}</span>
                                          </td>
                                          <td className="px-6 py-4 text-right rounded-r-2xl">
                                             <button className="p-2 text-slate-300 hover:text-hd-navy"><Pencil size={16} /></button>
                                          </td>
                                       </tr>
                                    ))}
                                 </tbody>
                              </table>
                           </div>
                        ) : (
                           <EmptyState message="У цьому центрі ще немає співробітників" actionLabel="Додати першого співробітника" onAction={() => {}} icon={Users} />
                        )}
                     </div>
                   )}

                   {activeAdminSubTab === 'courses' && (
                     <div className="space-y-8 animate-in fade-in duration-300">
                        {courses.length > 0 ? (
                           <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                              {courses.map((c, i) => (
                                 <div key={i} className="p-7 bg-slate-50 border border-slate-100 rounded-[2.5rem] hover:border-hd-gold transition-all group relative overflow-hidden">
                                    <h4 className="text-lg font-black text-hd-navy uppercase tracking-tight mb-6">{c.name}</h4>
                                 </div>
                              ))}
                           </div>
                        ) : (
                           <EmptyState message="У вас ще немає доданих курсів" actionLabel="Додати перший курс" onAction={() => {}} icon={BookOpen} />
                        )}
                     </div>
                   )}

                   {activeAdminSubTab === 'rooms' && (
                     <div className="space-y-8 animate-in fade-in duration-300">
                        {rooms.length > 0 ? (
                           <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-6">
                              {rooms.map((room, i) => (
                                 <div key={i} className="group aspect-square bg-slate-50 rounded-[2.5rem] border border-slate-100 p-6 flex flex-col items-center justify-center gap-3 hover:border-hd-gold hover:bg-white transition-all cursor-pointer relative shadow-sm duration-300">
                                    <div className="text-center"><span className="block text-[10px] font-black uppercase tracking-[0.2em] text-hd-navy">{room.name}</span></div>
                                 </div>
                              ))}
                           </div>
                        ) : (
                           <EmptyState message="Кімнати ще не створені" actionLabel="Створити першу локацію" onAction={() => {}} icon={DoorOpen} />
                        )}
                     </div>
                   )}

                   {activeAdminSubTab === 'sources' && (
                     <div className="space-y-8 animate-in fade-in duration-300">
                        {sources.length > 0 ? (
                           <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                              {sources.map((s, i) => (
                                 <div key={i} className="p-6 bg-slate-50 rounded-[2.5rem] border border-slate-100 flex items-center justify-between group hover:border-hd-navy transition-all">
                                    <span className="text-[10px] font-black uppercase tracking-widest text-hd-navy">{s.n}</span>
                                 </div>
                              ))}
                           </div>
                        ) : (
                           <EmptyState message="Джерела лідів не налаштовані" actionLabel="Налаштувати джерела" onAction={() => {}} icon={Share2} />
                        )}
                     </div>
                   )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
