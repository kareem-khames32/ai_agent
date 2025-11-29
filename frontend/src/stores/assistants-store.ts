import { create } from "zustand";
import type { Assistant } from "@/types";

interface AssistantsState {
  assistants: Assistant[];
  selectedAssistant: Assistant | null;
  isLoading: boolean;
  error: string | null;

  setAssistants: (assistants: Assistant[]) => void;
  addAssistant: (assistant: Assistant) => void;
  updateAssistant: (id: string, updates: Partial<Assistant>) => void;
  deleteAssistant: (id: string) => void;
  selectAssistant: (assistant: Assistant | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useAssistantsStore = create<AssistantsState>((set) => ({
  assistants: [],
  selectedAssistant: null,
  isLoading: false,
  error: null,

  setAssistants: (assistants) => set({ assistants }),

  addAssistant: (assistant) =>
    set((state) => ({
      assistants: [...state.assistants, assistant],
    })),

  updateAssistant: (id, updates) =>
    set((state) => ({
      assistants: state.assistants.map((a) =>
        a.id === id ? { ...a, ...updates } : a
      ),
      selectedAssistant:
        state.selectedAssistant?.id === id
          ? { ...state.selectedAssistant, ...updates }
          : state.selectedAssistant,
    })),

  deleteAssistant: (id) =>
    set((state) => ({
      assistants: state.assistants.filter((a) => a.id !== id),
      selectedAssistant:
        state.selectedAssistant?.id === id ? null : state.selectedAssistant,
    })),

  selectAssistant: (assistant) => set({ selectedAssistant: assistant }),

  setLoading: (isLoading) => set({ isLoading }),

  setError: (error) => set({ error }),
}));
