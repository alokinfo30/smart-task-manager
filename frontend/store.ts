import { configureStore } from '@reduxjs/toolkit';
import dashboardReducer from './dashboardSlice';
import learningReducer from './learningSlice';

export const store = configureStore({
  reducer: {
    dashboard: dashboardReducer,
    learning: learningReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;