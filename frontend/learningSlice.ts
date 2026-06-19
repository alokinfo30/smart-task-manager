import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface LearningState {
  topic: string;
  language: string;
  content: string;
  isLoading: boolean;
}

const initialState: LearningState = {
  topic: '',
  language: 'English',
  content: '',
  isLoading: false,
};

const learningSlice = createSlice({
  name: 'learning',
  initialState,
  reducers: {
    setTopic: (state, action: PayloadAction<string>) => { state.topic = action.payload; },
    setLanguage: (state, action: PayloadAction<string>) => { state.language = action.payload; },
    setContent: (state, action: PayloadAction<string>) => { state.content = action.payload; },
    setIsLoading: (state, action: PayloadAction<boolean>) => { state.isLoading = action.payload; },
  },
});

export const { setTopic, setLanguage, setContent, setIsLoading } = learningSlice.actions;
export default learningSlice.reducer;