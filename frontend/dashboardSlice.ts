import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface Task {
  id: number;
  date: string;
  task: string;
  status: string;
  priority: string;
  completed_at: string;
  owner: string;
  shared_with: string;
  comment?: string;
}

interface DashboardState {
  tasks: Task[];
  newTaskText: string;
  newTaskPriority: string;
  editTaskId: number | null;
  editTaskData: { task: string; priority: string; comment: string };
  shareInputs: Record<number, string>;
  revealedTasks: Record<number, boolean>;
  searchQuery: string;
  isListening: boolean;
}

const initialState: DashboardState = {
  tasks: [],
  newTaskText: '',
  newTaskPriority: 'High',
  editTaskId: null,
  editTaskData: { task: '', priority: 'Medium', comment: '' },
  shareInputs: {},
  revealedTasks: {},
  searchQuery: '',
  isListening: false,
};

const dashboardSlice = createSlice({
  name: 'dashboard',
  initialState,
  reducers: {
    setTasks: (state, action: PayloadAction<Task[]>) => { state.tasks = action.payload; },
    setNewTaskText: (state, action: PayloadAction<string>) => { state.newTaskText = action.payload; },
    appendNewTaskText: (state, action: PayloadAction<string>) => { state.newTaskText = (state.newTaskText + " " + action.payload).trim(); },
    setNewTaskPriority: (state, action: PayloadAction<string>) => { state.newTaskPriority = action.payload; },
    setEditTaskId: (state, action: PayloadAction<number | null>) => { state.editTaskId = action.payload; },
    setEditTaskData: (state, action: PayloadAction<{ task: string; priority: string; comment: string }>) => { state.editTaskData = action.payload; },
    setShareInput: (state, action: PayloadAction<{ id: number; value: string }>) => { state.shareInputs[action.payload.id] = action.payload.value; },
    toggleRevealedTask: (state, action: PayloadAction<number>) => { state.revealedTasks[action.payload] = !state.revealedTasks[action.payload]; },
    setSearchQuery: (state, action: PayloadAction<string>) => { state.searchQuery = action.payload; },
    setIsListening: (state, action: PayloadAction<boolean>) => { state.isListening = action.payload; },
  },
});

export const {
  setTasks, setNewTaskText, appendNewTaskText, setNewTaskPriority,
  setEditTaskId, setEditTaskData, setShareInput, toggleRevealedTask,
  setSearchQuery, setIsListening
} = dashboardSlice.actions;

export default dashboardSlice.reducer;