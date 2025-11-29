import { create } from "zustand";
import type { Call, DateRange } from "@/types";

interface CallFilters {
  dateRange?: DateRange;
  assistantId?: string;
  squadId?: string;
  type?: "inbound" | "outbound";
  status?: string;
  endedReason?: string;
  successEvaluation?: string;
  search?: string;
}

interface CallsState {
  calls: Call[];
  selectedCall: Call | null;
  filters: CallFilters;
  isLoading: boolean;
  error: string | null;
  totalCalls: number;
  currentPage: number;
  pageSize: number;

  setCalls: (calls: Call[]) => void;
  addCall: (call: Call) => void;
  updateCall: (id: string, updates: Partial<Call>) => void;
  selectCall: (call: Call | null) => void;
  setFilters: (filters: Partial<CallFilters>) => void;
  resetFilters: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setPagination: (total: number, page: number, pageSize: number) => void;
}

const defaultFilters: CallFilters = {};

export const useCallsStore = create<CallsState>((set) => ({
  calls: [],
  selectedCall: null,
  filters: defaultFilters,
  isLoading: false,
  error: null,
  totalCalls: 0,
  currentPage: 1,
  pageSize: 20,

  setCalls: (calls) => set({ calls }),

  addCall: (call) =>
    set((state) => ({
      calls: [call, ...state.calls],
      totalCalls: state.totalCalls + 1,
    })),

  updateCall: (id, updates) =>
    set((state) => ({
      calls: state.calls.map((c) => (c.id === id ? { ...c, ...updates } : c)),
      selectedCall:
        state.selectedCall?.id === id
          ? { ...state.selectedCall, ...updates }
          : state.selectedCall,
    })),

  selectCall: (call) => set({ selectedCall: call }),

  setFilters: (filters) =>
    set((state) => ({
      filters: { ...state.filters, ...filters },
      currentPage: 1, // Reset to first page when filters change
    })),

  resetFilters: () => set({ filters: defaultFilters, currentPage: 1 }),

  setLoading: (isLoading) => set({ isLoading }),

  setError: (error) => set({ error }),

  setPagination: (totalCalls, currentPage, pageSize) =>
    set({ totalCalls, currentPage, pageSize }),
}));
