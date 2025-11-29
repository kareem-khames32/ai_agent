// ============================================
// Organization & User Types
// ============================================
export interface Organization {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
}

export interface User {
  id: string;
  organizationId: string;
  email: string;
  name: string;
  role: "owner" | "admin" | "member";
  createdAt: string;
}

// ============================================
// Assistant Types
// ============================================
export interface Assistant {
  id: string;
  organizationId: string;
  name: string;

  // Model Configuration
  modelProvider: ModelProvider;
  modelName: string;
  systemPrompt: string;
  firstMessage: string;
  firstMessageMode: FirstMessageMode;
  temperature: number;
  maxTokens: number;

  // Voice Configuration
  voiceProvider: VoiceProvider;
  voiceId: string;
  voiceSettings: VoiceSettings;

  // Transcriber Configuration
  transcriberProvider: TranscriberProvider;
  transcriberLanguage: string;
  transcriberSettings: TranscriberSettings;

  // Tools
  tools: string[]; // Tool IDs

  // Analysis
  summaryPrompt: string;
  successEvaluationPrompt: string;
  structuredDataSchema: Record<string, unknown>;

  // Advanced
  advancedSettings: AdvancedSettings;

  createdAt: string;
  updatedAt: string;
}

export type ModelProvider = "openai" | "anthropic" | "google" | "azure" | "groq" | "together";
export type VoiceProvider = "elevenlabs" | "azure" | "google" | "openai" | "deepgram" | "cartesia" | "lmnt" | "rime" | "playht" | "neuphonic";
export type TranscriberProvider = "deepgram" | "azure" | "google" | "assemblyai" | "openai";
export type FirstMessageMode = "assistant-speaks-first" | "user-speaks-first" | "assistant-waits";

export interface VoiceSettings {
  stability?: number;
  similarityBoost?: number;
  style?: number;
  speed?: number;
  pitch?: number;
}

export interface TranscriberSettings {
  timeoutMs?: number;
  endpointingMs?: number;
  segmentationStrategy?: "default" | "time" | "semantic";
  smartFormat?: boolean;
  vadEnabled?: boolean;
}

export interface AdvancedSettings {
  privacyEnabled?: boolean;
  hipaaEnabled?: boolean;
  pciEnabled?: boolean;
  voicemailDetectionEnabled?: boolean;
  voicemailMessage?: string;
  callTimeoutSeconds?: number;
  silenceTimeoutSeconds?: number;
  maxDurationSeconds?: number;
  keypadInputEnabled?: boolean;
  backgroundSound?: string;
  backgroundDenoisingEnabled?: boolean;
}

// ============================================
// Tool Types
// ============================================
export interface Tool {
  id: string;
  organizationId: string;
  name: string;
  type: ToolType;
  description: string;
  parameters: ToolParameter[];
  serverUrl?: string;
  headers?: Record<string, string>;
  isAsync: boolean;
  isStrict: boolean;
  createdAt: string;
}

export type ToolType = "api_request" | "function" | "handoff" | "end_call" | "transfer";

export interface ToolParameter {
  name: string;
  type: "string" | "number" | "boolean" | "object" | "array";
  description: string;
  required: boolean;
  enum?: string[];
  default?: unknown;
}

// ============================================
// Phone Number Types
// ============================================
export interface PhoneNumber {
  id: string;
  organizationId: string;
  number: string;
  label: string;
  provider: TelephonyProvider;
  serverUrl?: string;
  timeoutSeconds: number;
  credentials?: Record<string, string>;
  assignedAssistantId?: string;
  assignedSquadId?: string;
  settings: PhoneNumberSettings;
  createdAt: string;
}

export type TelephonyProvider = "twilio" | "vonage" | "sip" | "telnyx";

export interface PhoneNumberSettings {
  inboundEnabled: boolean;
  outboundEnabled: boolean;
  recordingEnabled: boolean;
}

// ============================================
// Squad Types
// ============================================
export interface Squad {
  id: string;
  organizationId: string;
  name: string;
  members: SquadMember[];
  createdAt: string;
  updatedAt: string;
}

export interface SquadMember {
  assistantId: string;
  handoffTools: string[];
  position: { x: number; y: number };
  isStartNode: boolean;
  overrides?: Partial<Assistant>;
}

// ============================================
// Call Types
// ============================================
export interface Call {
  id: string;
  organizationId: string;
  assistantId?: string;
  squadId?: string;

  type: "inbound" | "outbound";
  status: CallStatus;

  phoneNumberId?: string;
  customerPhoneNumber: string;

  startedAt: string;
  endedAt?: string;
  durationSeconds: number;

  endedReason: EndedReason;
  successEvaluation?: "success" | "failure" | "unknown";
  score?: number;

  transcript: TranscriptMessage[];
  messages: Message[];
  toolCalls: ToolCall[];
  recordingUrl?: string;

  costBreakdown: CostBreakdown;
  totalCost: number;

  summary?: string;
  structuredData?: Record<string, unknown>;

  metadata?: Record<string, unknown>;
  createdAt: string;
}

export type CallStatus = "queued" | "ringing" | "in-progress" | "ended" | "failed";
export type EndedReason =
  | "customer-ended"
  | "assistant-ended"
  | "voicemail"
  | "timeout"
  | "error"
  | "transfer"
  | "hangup"
  | "silence-timeout"
  | "max-duration";

export interface TranscriptMessage {
  role: "user" | "assistant";
  text: string;
  timestamp: string;
  durationMs: number;
}

export interface Message {
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  timestamp: string;
  toolCallId?: string;
}

export interface ToolCall {
  id: string;
  toolId: string;
  toolName: string;
  arguments: Record<string, unknown>;
  result?: unknown;
  status: "pending" | "success" | "error";
  timestamp: string;
  durationMs: number;
}

export interface CostBreakdown {
  llm: number;
  stt: number;
  tts: number;
  telephony: number;
}

// ============================================
// Voice Types
// ============================================
export interface Voice {
  id: string;
  provider: VoiceProvider;
  voiceId: string;
  name: string;
  description?: string;
  previewUrl?: string;
  accent?: string;
  gender: "male" | "female" | "neutral";
  language: string;
  costPerMinute: number;
  latencyMs: number;
  tags: string[];
  isCustom: boolean;
  organizationId?: string;
}

// ============================================
// Analytics Types
// ============================================
export interface MetricsSummary {
  totalCallMinutes: number;
  numberOfCalls: number;
  totalSpent: number;
  averageCostPerCall: number;
  averageCallDuration: number;
}

export interface CallsByReason {
  reason: EndedReason;
  count: number;
}

export interface CallsByAssistant {
  assistantId: string;
  assistantName: string;
  count: number;
  averageDuration: number;
  totalCost: number;
}

export interface DailyCostBreakdown {
  date: string;
  llm: number;
  stt: number;
  tts: number;
  telephony: number;
}

// ============================================
// API Types
// ============================================
export interface ApiKey {
  id: string;
  organizationId: string;
  name: string;
  keyPrefix: string;
  permissions: string[];
  lastUsedAt?: string;
  expiresAt?: string;
  createdAt: string;
}

export interface Webhook {
  id: string;
  organizationId: string;
  url: string;
  events: WebhookEvent[];
  secret?: string;
  isActive: boolean;
  createdAt: string;
}

export type WebhookEvent =
  | "call.started"
  | "call.ended"
  | "transcript.ready"
  | "tool.called"
  | "assistant.error";

// ============================================
// Provider Credentials Types
// ============================================
export interface ProviderCredentials {
  provider: string;
  isConfigured: boolean;
  lastUpdated?: string;
}

export interface CredentialsInput {
  provider: string;
  apiKey?: string;
  apiSecret?: string;
  region?: string;
  projectId?: string;
}

// ============================================
// Common Types
// ============================================
export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ApiError {
  message: string;
  code: string;
  details?: Record<string, unknown>;
}

export interface DateRange {
  from: Date;
  to: Date;
}
