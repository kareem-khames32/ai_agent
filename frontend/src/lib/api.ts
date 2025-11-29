import axios, { type AxiosError, type AxiosResponse } from "axios";
import type {
  Assistant,
  Tool,
  PhoneNumber,
  Squad,
  Call,
  Voice,
  ApiKey,
  MetricsSummary,
  PaginatedResponse,
  ProviderCredentials,
  CredentialsInput,
} from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Create axios instance
const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor for adding auth token
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("auth-storage");
    if (token) {
      try {
        const parsed = JSON.parse(token);
        if (parsed.state?.token) {
          config.headers.Authorization = `Bearer ${parsed.state.token}`;
        }
      } catch {
        // Invalid token
      }
    }
  }
  return config;
});

// Response interceptor for handling errors
api.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Redirect to login on unauthorized
      if (typeof window !== "undefined") {
        localStorage.removeItem("auth-storage");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// ============================================
// Auth API
// ============================================
export const authApi = {
  login: async (email: string, password: string) => {
    const response = await api.post("/auth/login", { email, password });
    return response.data;
  },

  register: async (data: { email: string; password: string; name: string }) => {
    const response = await api.post("/auth/register", data);
    return response.data;
  },

  logout: async () => {
    const response = await api.post("/auth/logout");
    return response.data;
  },

  getProfile: async () => {
    const response = await api.get("/auth/me");
    return response.data;
  },

  forgotPassword: async (email: string) => {
    const response = await api.post("/auth/forgot-password", { email });
    return response.data;
  },

  resetPassword: async (token: string, password: string) => {
    const response = await api.post("/auth/reset-password", { token, password });
    return response.data;
  },
};

// ============================================
// Assistants API
// ============================================
export const assistantsApi = {
  list: async (): Promise<Assistant[]> => {
    const response = await api.get("/assistants");
    return response.data;
  },

  get: async (id: string): Promise<Assistant> => {
    const response = await api.get(`/assistants/${id}`);
    return response.data;
  },

  create: async (data: Partial<Assistant>): Promise<Assistant> => {
    const response = await api.post("/assistants", data);
    return response.data;
  },

  update: async (id: string, data: Partial<Assistant>): Promise<Assistant> => {
    const response = await api.patch(`/assistants/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/assistants/${id}`);
  },

  test: async (id: string): Promise<{ callId: string }> => {
    const response = await api.post(`/assistants/${id}/test`);
    return response.data;
  },
};

// ============================================
// Tools API
// ============================================
export const toolsApi = {
  list: async (): Promise<Tool[]> => {
    const response = await api.get("/tools");
    return response.data;
  },

  get: async (id: string): Promise<Tool> => {
    const response = await api.get(`/tools/${id}`);
    return response.data;
  },

  create: async (data: Partial<Tool>): Promise<Tool> => {
    const response = await api.post("/tools", data);
    return response.data;
  },

  update: async (id: string, data: Partial<Tool>): Promise<Tool> => {
    const response = await api.patch(`/tools/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/tools/${id}`);
  },
};

// ============================================
// Phone Numbers API
// ============================================
export const phoneNumbersApi = {
  list: async (): Promise<PhoneNumber[]> => {
    const response = await api.get("/phone-numbers");
    return response.data;
  },

  get: async (id: string): Promise<PhoneNumber> => {
    const response = await api.get(`/phone-numbers/${id}`);
    return response.data;
  },

  create: async (data: Partial<PhoneNumber>): Promise<PhoneNumber> => {
    const response = await api.post("/phone-numbers", data);
    return response.data;
  },

  update: async (id: string, data: Partial<PhoneNumber>): Promise<PhoneNumber> => {
    const response = await api.patch(`/phone-numbers/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/phone-numbers/${id}`);
  },

  import: async (provider: string, credentials: Record<string, string>): Promise<PhoneNumber[]> => {
    const response = await api.post("/phone-numbers/import", { provider, credentials });
    return response.data;
  },
};

// ============================================
// Squads API
// ============================================
export const squadsApi = {
  list: async (): Promise<Squad[]> => {
    const response = await api.get("/squads");
    return response.data;
  },

  get: async (id: string): Promise<Squad> => {
    const response = await api.get(`/squads/${id}`);
    return response.data;
  },

  create: async (data: Partial<Squad>): Promise<Squad> => {
    const response = await api.post("/squads", data);
    return response.data;
  },

  update: async (id: string, data: Partial<Squad>): Promise<Squad> => {
    const response = await api.patch(`/squads/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/squads/${id}`);
  },
};

// ============================================
// Calls API
// ============================================
export const callsApi = {
  list: async (params?: {
    page?: number;
    pageSize?: number;
    assistantId?: string;
    type?: string;
    status?: string;
    fromDate?: string;
    toDate?: string;
  }): Promise<PaginatedResponse<Call>> => {
    const response = await api.get("/calls", { params });
    return response.data;
  },

  get: async (id: string): Promise<Call> => {
    const response = await api.get(`/calls/${id}`);
    return response.data;
  },

  getTranscript: async (id: string): Promise<{ transcript: string }> => {
    const response = await api.get(`/calls/${id}/transcript`);
    return response.data;
  },

  getRecording: async (id: string): Promise<{ url: string }> => {
    const response = await api.get(`/calls/${id}/recording`);
    return response.data;
  },

  createOutbound: async (data: {
    assistantId?: string;
    squadId?: string;
    phoneNumberId: string;
    customerPhoneNumber: string;
    metadata?: Record<string, unknown>;
  }): Promise<Call> => {
    const response = await api.post("/calls/outbound", data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/calls/${id}`);
  },
};

// ============================================
// Voices API
// ============================================
export const voicesApi = {
  list: async (params?: {
    provider?: string;
    language?: string;
    gender?: string;
  }): Promise<Voice[]> => {
    const response = await api.get("/voices", { params });
    return response.data;
  },

  listByProvider: async (provider: string): Promise<Voice[]> => {
    const response = await api.get(`/voices/${provider}`);
    return response.data;
  },

  clone: async (data: {
    name: string;
    provider: string;
    audioFile: File;
    description?: string;
  }): Promise<Voice> => {
    const formData = new FormData();
    formData.append("name", data.name);
    formData.append("provider", data.provider);
    formData.append("audioFile", data.audioFile);
    if (data.description) {
      formData.append("description", data.description);
    }
    const response = await api.post("/voices/clone", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },

  sync: async (provider: string): Promise<{ count: number }> => {
    const response = await api.post("/voices/sync", { provider });
    return response.data;
  },
};

// ============================================
// Analytics API
// ============================================
export const analyticsApi = {
  getMetrics: async (params?: {
    fromDate?: string;
    toDate?: string;
    assistantId?: string;
  }): Promise<MetricsSummary> => {
    const response = await api.get("/analytics/metrics", { params });
    return response.data;
  },

  getUsage: async (params?: {
    fromDate?: string;
    toDate?: string;
    groupBy?: "day" | "hour" | "week" | "month";
  }) => {
    const response = await api.get("/analytics/usage", { params });
    return response.data;
  },

  getCosts: async (params?: {
    fromDate?: string;
    toDate?: string;
  }) => {
    const response = await api.get("/analytics/costs", { params });
    return response.data;
  },
};

// ============================================
// API Keys API
// ============================================
export const apiKeysApi = {
  list: async (): Promise<ApiKey[]> => {
    const response = await api.get("/api-keys");
    return response.data;
  },

  create: async (data: { name: string; permissions?: string[] }): Promise<{ key: string; apiKey: ApiKey }> => {
    const response = await api.post("/api-keys", data);
    return response.data;
  },

  revoke: async (id: string): Promise<void> => {
    await api.delete(`/api-keys/${id}`);
  },
};

// ============================================
// Settings API
// ============================================
export const settingsApi = {
  get: async () => {
    const response = await api.get("/settings");
    return response.data;
  },

  update: async (data: Record<string, unknown>) => {
    const response = await api.patch("/settings", data);
    return response.data;
  },

  getCredentials: async (): Promise<ProviderCredentials[]> => {
    const response = await api.get("/settings/credentials");
    return response.data;
  },

  updateCredentials: async (data: CredentialsInput): Promise<void> => {
    await api.patch("/settings/credentials", data);
  },
};

export default api;
