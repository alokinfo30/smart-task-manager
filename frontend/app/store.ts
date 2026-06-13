import { create } from 'zustand';

type Lang = 'en' | 'hi';

interface AppState {
  currentUser: string | null;
  setCurrentUser: (user: string | null) => void;
  authMode: 'login' | 'register';
  setAuthMode: (mode: 'login' | 'register') => void;
  ssoEmail: string;
  setSsoEmail: (email: string) => void;
  
  lang: Lang;
  setLang: (lang: Lang) => void;
  currencySym: string;
  setCurrencySym: (sym: string) => void;
  revealMobiles: boolean;
  setRevealMobiles: (reveal: boolean) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  
  newTaskName: string;
  setNewTaskName: (name: string) => void;
  newTaskPriority: string;
  setNewTaskPriority: (prio: string) => void;

  editTaskId: number | null;
  setEditTaskId: (id: number | null) => void;
  editTaskData: { task: string; priority: string };
  setEditTaskData: (data: { task: string; priority: string }) => void;

  editExpenseId: number | null;
  setEditExpenseId: (id: number | null) => void;
  editExpenseData: { amount: number; category: string; description: string; date: string };
  setEditExpenseData: (data: { amount: number; category: string; description: string; date: string }) => void;

  newExpAmount: number;
  setNewExpAmount: (amount: number) => void;
  newExpCat: string;
  setNewExpCat: (cat: string) => void;
  newExpDesc: string;
  setNewExpDesc: (desc: string) => void;
  newExpDate: string;
  setNewExpDate: (date: string) => void;

  editRoutineId: string | null;
  setEditRoutineId: (id: string | null) => void;
  editRoutineData: { name: string; start: string; end: string };
  setEditRoutineData: (data: { name: string; start: string; end: string }) => void;

  resName: string; setResName: (val: string) => void;
  resPhone: string; setResPhone: (val: string) => void;
  resEmail: string; setResEmail: (val: string) => void;
  resLinkedin: string; setResLinkedin: (val: string) => void;
  resGithub: string; setResGithub: (val: string) => void;
  resQual: string; setResQual: (val: string) => void;
  resSkills: string; setResSkills: (val: string) => void;
  resExp: string; setResExp: (val: string) => void;
  resProj: string; setResProj: (val: string) => void;
  resFileText: string; setResFileText: (val: string) => void;
  resPhoto: string; setResPhoto: (val: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentUser: null,
  setCurrentUser: (user) => set({ currentUser: user }),
  authMode: 'login',
  setAuthMode: (mode) => set({ authMode: mode }),
  ssoEmail: '',
  setSsoEmail: (email) => set({ ssoEmail: email }),
  
  lang: 'en',
  setLang: (lang) => set({ lang }),
  currencySym: '$',
  setCurrencySym: (sym) => set({ currencySym: sym }),
  revealMobiles: false,
  setRevealMobiles: (reveal) => set({ revealMobiles: reveal }),
  searchQuery: '',
  setSearchQuery: (query) => set({ searchQuery: query }),

  newTaskName: '',
  setNewTaskName: (name) => set({ newTaskName: name }),
  newTaskPriority: 'High',
  setNewTaskPriority: (prio) => set({ newTaskPriority: prio }),

  editTaskId: null,
  setEditTaskId: (id) => set({ editTaskId: id }),
  editTaskData: { task: '', priority: '' },
  setEditTaskData: (data) => set({ editTaskData: data }),

  editExpenseId: null,
  setEditExpenseId: (id) => set({ editExpenseId: id }),
  editExpenseData: { amount: 0, category: '', description: '', date: '' },
  setEditExpenseData: (data) => set({ editExpenseData: data }),

  newExpAmount: 0,
  setNewExpAmount: (amount) => set({ newExpAmount: amount }),
  newExpCat: 'Food',
  setNewExpCat: (cat) => set({ newExpCat: cat }),
  newExpDesc: '',
  setNewExpDesc: (desc) => set({ newExpDesc: desc }),
  newExpDate: new Date().toISOString().split('T')[0],
  setNewExpDate: (date) => set({ newExpDate: date }),

  editRoutineId: null,
  setEditRoutineId: (id) => set({ editRoutineId: id }),
  editRoutineData: { name: '', start: '', end: '' },
  setEditRoutineData: (data) => set({ editRoutineData: data }),

  resName: '', setResName: (val) => set({ resName: val }),
  resPhone: '', setResPhone: (val) => set({ resPhone: val }),
  resEmail: '', setResEmail: (val) => set({ resEmail: val }),
  resLinkedin: '', setResLinkedin: (val) => set({ resLinkedin: val }),
  resGithub: '', setResGithub: (val) => set({ resGithub: val }),
  resQual: '', setResQual: (val) => set({ resQual: val }),
  resSkills: '', setResSkills: (val) => set({ resSkills: val }),
  resExp: '', setResExp: (val) => set({ resExp: val }),
  resProj: '', setResProj: (val) => set({ resProj: val }),
  resFileText: '', setResFileText: (val) => set({ resFileText: val }),
  resPhoto: '', setResPhoto: (val) => set({ resPhoto: val }),
}));