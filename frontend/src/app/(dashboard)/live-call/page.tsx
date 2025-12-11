"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { saveCallLog as saveCallLogToDB, migrateFromLocalStorage, CallLogEntry } from "@/lib/callLogsDB";
import {
  Mic,
  Phone,
  PhoneOff,
  Volume2,
  VolumeX,
  Settings,
  RefreshCw,
  Loader2,
  AlertCircle,
  CheckCircle,
  Radio,
  Bot,
  ArrowLeft,
  Zap,
} from "lucide-react";
import Link from "next/link";

interface TranscriptEntry {
  role: "user" | "assistant";
  text: string;
  timestamp: Date;
}

interface WaveformPoint {
  time: number;
  amplitude: number;
  source: "user" | "ai";
}

interface CostBreakdown {
  stt: { minutes: number; provider: string; cost: number };
  llm: { input_tokens: number; output_tokens: number; provider: string; model: string; cost: number };
  tts: { characters: number; provider: string; cost: number };
  total_cost: number;
  recording_id?: string;
  waveform?: WaveformPoint[];
  call_duration?: number;
}

interface CallLog {
  id: string;
  assistantId: string;
  assistantName: string;
  startTime: string;
  endTime: string;
  duration: number;
  status: "completed" | "failed" | "interrupted" | "no_speech";
  transcript: {
    role: "user" | "assistant";
    text: string;
    timestamp: string;
  }[];
  metadata?: {
    llmProvider?: string;
    llmModel?: string;
    ttsProvider?: string;
    sttProvider?: string;
    language?: string;
  };
  cost?: CostBreakdown;
  latency?: {
    avgResponseTime: number; // Average time from user speech end to AI audio start (ms)
    sttLatency: number; // Average STT processing time (ms)
    llmLatency: number; // Average LLM response time (ms)
    ttsLatency: number; // Average TTS generation time (ms)
  };
  waveform?: WaveformPoint[];
}

interface Assistant {
  id: string;
  name: string;
  modelProvider: string;
  modelName: string;
  systemPrompt: string;
  firstMessage: string;
  firstMessageMode?: string;
  voiceProvider: string;
  voiceId: string;
  // Voice settings
  voiceSpeed?: number;
  voiceStability?: number;
  // Transcriber settings
  transcriberProvider?: string;
  transcriberLanguage: string;
  temperature: number;
  // Interruption settings
  interruptionEnabled?: boolean;
  interruptionWordsThreshold?: number;  // 0 = immediate, 1-10 = wait for N words
  stopOnHangup?: boolean;
}

type CallStatus = "idle" | "connecting" | "active" | "error";

const DEFAULT_PROMPT = `أنت مساعد صوتي ذكي لشركة تحصيل ديون.
تتحدث باللغة العربية.
كن مهذباً ومحترفاً ومختصراً.
عرف نفسك في البداية.`;

export default function LiveCallPage() {
  const { addToast } = useToast();
  const searchParams = useSearchParams();
  const assistantId = searchParams.get("assistant");

  // Hydration fix - wait for client mount
  const [mounted, setMounted] = React.useState(false);

  // Assistant config
  const [assistant, setAssistant] = React.useState<Assistant | null>(null);

  // Call state
  const [status, setStatus] = React.useState<CallStatus>("idle");
  const [isSpeaking, setIsSpeaking] = React.useState(false);
  const [isThinking, setIsThinking] = React.useState(false);
  const [isAISpeaking, setIsAISpeaking] = React.useState(false);
  const [isMuted, setIsMuted] = React.useState(false);

  // Prompt
  const [systemPrompt, setSystemPrompt] = React.useState(DEFAULT_PROMPT);

  // Transcript
  const [transcript, setTranscript] = React.useState<TranscriptEntry[]>([]);
  const [interimText, setInterimText] = React.useState("");
  const [streamingText, setStreamingText] = React.useState("");  // Live AI text as it generates
  const transcriptRef = React.useRef<TranscriptEntry[]>([]);

  // Call tracking
  const [callStartTime, setCallStartTime] = React.useState<Date | null>(null);
  const callStartTimeRef = React.useRef<Date | null>(null);
  const callStatusRef = React.useRef<"completed" | "failed" | "interrupted" | "no_speech">("completed");
  const [callCost, setCallCost] = React.useState<CostBreakdown | null>(null);
  const costSummaryReceivedRef = React.useRef<boolean>(false);

  // Real-time latency display
  const [currentLatency, setCurrentLatency] = React.useState<{
    stt: number | null;
    llm: number | null;
    tts: number | null;
    total: number | null;
  }>({ stt: null, llm: null, tts: null, total: null });

  // Refs
  const wsRef = React.useRef<WebSocket | null>(null);
  const streamRef = React.useRef<MediaStream | null>(null);
  const audioContextRef = React.useRef<AudioContext | null>(null);
  const processorRef = React.useRef<ScriptProcessorNode | null>(null);
  const audioRef = React.useRef<HTMLAudioElement | null>(null);
  const transcriptEndRef = React.useRef<HTMLDivElement>(null);
  const isMutedRef = React.useRef(false);
  const saveCallLogRef = React.useRef<(status: "completed" | "failed" | "interrupted" | "no_speech", cost?: CostBreakdown) => void>(() => {});
  const callSavedRef = React.useRef(false); // Track if call was already saved

  // 🔊 Audio Queue for gapless playback
  const audioQueueRef = React.useRef<{url: string, sequence: number}[]>([]);
  const isPlayingRef = React.useRef(false);
  const audioInterruptedRef = React.useRef(false);  // Flag to block audio after interrupt
  const isAISpeakingRef = React.useRef(false);  // Track AI speaking for barge-in
  const lastBargeInTimeRef = React.useRef(0);  // Debounce barge-in signals
  const interruptionSettingsRef = React.useRef({ enabled: true, wordsThreshold: 0 });  // Interruption settings

  // Latency tracking refs
  const speechEndTimeRef = React.useRef<number | null>(null); // When user stops speaking
  const latencyMeasurementsRef = React.useRef<{
    responseTimes: number[]; // Full round-trip: speech end to audio start
    sttLatencies: number[]; // Speech end to transcript received
    llmLatencies: number[]; // Transcript to AI response text
    ttsLatencies: number[]; // AI text to audio start
  }>({ responseTimes: [], sttLatencies: [], llmLatencies: [], ttsLatencies: [] });
  const lastTranscriptTimeRef = React.useRef<number | null>(null);
  const lastAITextTimeRef = React.useRef<number | null>(null);
  const pendingCostRef = React.useRef<CostBreakdown | null>(null); // Store cost from cost_summary

  // Set mounted on client
  React.useEffect(() => {
    setMounted(true);
  }, []);

  // Load assistant from localStorage (always load last used or specific assistant)
  React.useEffect(() => {
    if (!mounted) return;

    let loaded = false;

    // If assistantId is specified, try to load from assistants storage first
    if (assistantId) {
      const assistants = localStorage.getItem("assistants");
      if (assistants) {
        try {
          const parsed = JSON.parse(assistants);
          if (parsed[assistantId]) {
            setAssistant(parsed[assistantId]);
            setSystemPrompt(parsed[assistantId].systemPrompt || DEFAULT_PROMPT);
            // Update interruption settings ref
            interruptionSettingsRef.current = {
              enabled: parsed[assistantId].interruptionEnabled ?? true,
              wordsThreshold: parsed[assistantId].interruptionWordsThreshold ?? 0,
            };
            console.log("✅ Loaded assistant from assistants storage:", parsed[assistantId].name);
            console.log("⚙️ Interruption settings:", interruptionSettingsRef.current);
            loaded = true;
          }
        } catch {
          console.error("Failed to load from assistants storage");
        }
      }
    }

    // Always try to load from test_assistant (last used / fallback)
    if (!loaded) {
      const saved = localStorage.getItem("test_assistant");
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          setAssistant(parsed);
          setSystemPrompt(parsed.systemPrompt || DEFAULT_PROMPT);
          // Update interruption settings ref
          interruptionSettingsRef.current = {
            enabled: parsed.interruptionEnabled ?? true,
            wordsThreshold: parsed.interruptionWordsThreshold ?? 0,
          };
          console.log("✅ Loaded assistant from test_assistant:", parsed.name);
          console.log("⚙️ Interruption settings:", interruptionSettingsRef.current);
          loaded = true;
        } catch {
          console.error("Failed to load assistant config");
        }
      }
    }

    if (!loaded) {
      console.log("ℹ️ No saved assistant found, using defaults");
    }
  }, [assistantId, mounted]);

  // Keep refs in sync with state
  React.useEffect(() => {
    isMutedRef.current = isMuted;
  }, [isMuted]);

  React.useEffect(() => {
    isAISpeakingRef.current = isAISpeaking;
  }, [isAISpeaking]);

  React.useEffect(() => {
    transcriptRef.current = transcript;
  }, [transcript]);

  React.useEffect(() => {
    callStartTimeRef.current = callStartTime;
  }, [callStartTime]);

  // Auto-scroll
  React.useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript, interimText]);

  // Migrate old localStorage data to IndexedDB on first load
  React.useEffect(() => {
    migrateFromLocalStorage().then((count) => {
      if (count > 0) {
        console.log(`✅ Migrated ${count} old call logs to IndexedDB`);
      }
    });
  }, []);

  // Cleanup
  React.useEffect(() => {
    return () => {
      // Clear audio queue on unmount
      audioQueueRef.current.forEach(item => URL.revokeObjectURL(item.url));
      audioQueueRef.current = [];
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      endCall();
    };
  }, []);

  // Get credentials
  const getCredentials = () => {
    if (typeof window === "undefined") return {};
    const saved = localStorage.getItem("provider_credentials");
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        return {};
      }
    }
    return {};
  };

  // Check credentials
  const checkCredentials = () => {
    const creds = getCredentials();
    const hasSTT = creds.deepgram?.api_key || creds.azure_speech?.api_key || creds.openai_whisper?.api_key || creds.groq_whisper?.api_key || creds.groq?.api_key || creds.munsit?.api_key;
    const hasLLM = creds.anthropic?.api_key || creds.openai?.api_key || creds.google?.api_key || creds.groq?.api_key || creds.together?.api_key;
    const hasTTS = creds.elevenlabs?.api_key || creds.openai_tts?.api_key || creds.azure_tts?.api_key || creds.deepgram_tts?.api_key || creds.deepgram?.api_key || creds.cartesia?.api_key;
    return { hasSTT, hasLLM, hasTTS, isComplete: hasSTT && hasLLM && hasTTS };
  };

  // Get STT config based on assistant settings
  const getSTTConfig = () => {
    const creds = getCredentials();

    if (assistant?.transcriberProvider) {
      const provider = assistant.transcriberProvider;
      let apiKey = "";
      let region = "";

      switch (provider) {
        case "deepgram":
          apiKey = creds.deepgram?.api_key || "";
          break;
        case "azure":
          apiKey = creds.azure_speech?.api_key || "";
          region = creds.azure_speech?.region || "eastus";
          break;
        case "openai":
          apiKey = creds.openai_whisper?.api_key || creds.openai?.api_key || "";
          break;
        case "groq":
          apiKey = creds.groq_whisper?.api_key || creds.groq?.api_key || "";
          break;
        case "munsit":
          apiKey = creds.munsit?.api_key || "";
          break;
        default:
          apiKey = creds.deepgram?.api_key || "";
      }

      return { provider, apiKey, region };
    }

    // Default: use first available STT provider (priority: Munsit > Groq > Azure > Deepgram > OpenAI)
    if (creds.munsit?.api_key) {
      return { provider: "munsit", apiKey: creds.munsit.api_key, region: "" };
    }
    if (creds.groq_whisper?.api_key || creds.groq?.api_key) {
      return { provider: "groq", apiKey: creds.groq_whisper?.api_key || creds.groq?.api_key, region: "" };
    }
    if (creds.azure_speech?.api_key) {
      return { provider: "azure", apiKey: creds.azure_speech.api_key, region: creds.azure_speech.region || "eastus" };
    }
    if (creds.deepgram?.api_key) {
      return { provider: "deepgram", apiKey: creds.deepgram.api_key, region: "" };
    }
    if (creds.openai_whisper?.api_key || creds.openai?.api_key) {
      return { provider: "openai", apiKey: creds.openai_whisper?.api_key || creds.openai?.api_key, region: "" };
    }

    return { provider: "deepgram", apiKey: "", region: "" };
  };

  // Get the LLM config based on assistant settings or defaults
  const getLLMConfig = () => {
    const creds = getCredentials();

    if (assistant) {
      // Use assistant's configured provider
      const provider = assistant.modelProvider;
      let apiKey = "";

      switch (provider) {
        case "anthropic":
          apiKey = creds.anthropic?.api_key || "";
          break;
        case "openai":
          apiKey = creds.openai?.api_key || "";
          break;
        case "google":
          apiKey = creds.google?.api_key || "";
          break;
        case "groq":
          apiKey = creds.groq?.api_key || "";
          break;
        case "together":
          apiKey = creds.together?.api_key || "";
          break;
        default:
          apiKey = creds.anthropic?.api_key || creds.openai?.api_key || "";
      }

      return {
        provider,
        apiKey,
        model: assistant.modelName,
        temperature: assistant.temperature,
      };
    }

    // Default: use first available provider
    if (creds.anthropic?.api_key) {
      return { provider: "anthropic", apiKey: creds.anthropic.api_key, model: "claude-sonnet-4-20250514", temperature: 0.7 };
    }
    if (creds.openai?.api_key) {
      return { provider: "openai", apiKey: creds.openai.api_key, model: "gpt-4o", temperature: 0.7 };
    }
    if (creds.google?.api_key) {
      return { provider: "google", apiKey: creds.google.api_key, model: "gemini-2.0-flash", temperature: 0.7 };
    }
    if (creds.groq?.api_key) {
      return { provider: "groq", apiKey: creds.groq.api_key, model: "llama-3.3-70b-versatile", temperature: 0.7 };
    }

    return { provider: "", apiKey: "", model: "", temperature: 0.7 };
  };

  // Get TTS config based on assistant settings
  const getTTSConfig = () => {
    const creds = getCredentials();

    if (assistant) {
      const provider = assistant.voiceProvider;
      let apiKey = "";
      let region = "";

      switch (provider) {
        case "elevenlabs":
          apiKey = creds.elevenlabs?.api_key || "";
          break;
        case "openai":
          apiKey = creds.openai_tts?.api_key || creds.openai?.api_key || "";
          break;
        case "azure":
          apiKey = creds.azure_tts?.api_key || "";
          region = creds.azure_tts?.region || "eastus";
          break;
        case "deepgram":
          apiKey = creds.deepgram_tts?.api_key || creds.deepgram?.api_key || "";
          break;
        case "cartesia":
          apiKey = creds.cartesia?.api_key || "";
          break;
        default:
          apiKey = creds.elevenlabs?.api_key || "";
      }

      return {
        provider,
        apiKey,
        region,
        voiceId: assistant.voiceId,
        voiceSpeed: assistant.voiceSpeed || 1.0,
        voiceStability: assistant.voiceStability || 0.5,
      };
    }

    // Default priority: ElevenLabs > Cartesia > Deepgram > OpenAI > Azure
    if (creds.elevenlabs?.api_key) {
      return { provider: "elevenlabs", apiKey: creds.elevenlabs.api_key, region: "", voiceId: "EXAVITQu4vr4xnSDxMaL", voiceSpeed: 1.0, voiceStability: 0.5 };
    }
    if (creds.cartesia?.api_key) {
      return { provider: "cartesia", apiKey: creds.cartesia.api_key, region: "", voiceId: "694f9389-aac1-45b6-b726-9d9369183238", voiceSpeed: 1.0, voiceStability: 0.5 };
    }
    if (creds.deepgram_tts?.api_key || creds.deepgram?.api_key) {
      return { provider: "deepgram", apiKey: creds.deepgram_tts?.api_key || creds.deepgram?.api_key, region: "", voiceId: "aura-asteria-en", voiceSpeed: 1.0, voiceStability: 0.5 };
    }
    if (creds.openai_tts?.api_key || creds.openai?.api_key) {
      return { provider: "openai", apiKey: creds.openai_tts?.api_key || creds.openai?.api_key, region: "", voiceId: "alloy", voiceSpeed: 1.0, voiceStability: 0.5 };
    }
    if (creds.azure_tts?.api_key) {
      return { provider: "azure", apiKey: creds.azure_tts.api_key, region: creds.azure_tts?.region || "eastus", voiceId: "ar-SA-HamedNeural", voiceSpeed: 1.0, voiceStability: 0.5 };
    }

    return { provider: "", apiKey: "", region: "", voiceId: "", voiceSpeed: 1.0, voiceStability: 0.5 };
  };

  // Save call log to localStorage
  const saveCallLog = (status: "completed" | "failed" | "interrupted" | "no_speech", cost?: CostBreakdown) => {
    console.log("📝 saveCallLog called with status:", status, "cost:", cost?.total_cost);

    // Check if already saved to prevent double-save
    if (callSavedRef.current) {
      console.log("⚠️ Call already saved, skipping duplicate save");
      return;
    }

    // Use ref for callStartTime to get the latest value in the callback
    const startTime = callStartTimeRef.current;
    console.log("   startTime from ref:", startTime);

    if (!startTime) {
      console.log("❌ No call start time, skipping save");
      return;
    }

    const endTime = new Date();
    const duration = Math.round((endTime.getTime() - startTime.getTime()) / 1000);
    console.log("   duration:", duration, "seconds");

    // Don't save if call was too short (less than 2 seconds)
    if (duration < 2) {
      console.log("❌ Call too short, skipping save");
      return;
    }

    const llmConfig = getLLMConfig();
    const ttsConfig = getTTSConfig();
    const sttConfig = getSTTConfig();

    // Use ref for transcript to get the latest value
    const currentTranscript = transcriptRef.current;

    // Get waveform data from cost summary
    const costData = cost || callCost || undefined;
    const waveformData = costData?.waveform;

    const callLog: CallLog = {
      id: `call-${Date.now()}`,
      assistantId: assistant?.id || "default",
      assistantName: assistant?.name || "مكالمة سريعة",
      startTime: startTime.toISOString(),
      endTime: endTime.toISOString(),
      duration: costData?.call_duration || duration,
      status: currentTranscript.length === 0 ? "no_speech" : status,
      transcript: currentTranscript.map((t) => ({
        role: t.role,
        text: t.text,
        timestamp: t.timestamp.toISOString(),
      })),
      metadata: {
        llmProvider: llmConfig.provider,
        llmModel: llmConfig.model,
        ttsProvider: ttsConfig.provider,
        sttProvider: sttConfig.provider,
        language: assistant?.transcriberLanguage || "ar",
      },
      cost: costData ? { ...costData, waveform: undefined } : undefined,
      // Limit waveform to 100 points
      waveform: waveformData ? waveformData.slice(0, 100) : undefined,
    };

    // Save to IndexedDB (unlimited storage!)
    if (typeof window === "undefined") {
      console.log("❌ IndexedDB not available (SSR)");
      return;
    }

    saveCallLogToDB(callLog as CallLogEntry)
      .then(() => {
        callSavedRef.current = true;
        console.log("✅ Call log saved to IndexedDB!");
        addToast({
          type: "success",
          title: "تم حفظ المكالمة",
          description: `المدة: ${duration} ثانية${cost?.total_cost ? ` | التكلفة: $${cost.total_cost.toFixed(4)}` : ""}`,
        });
      })
      .catch((e) => {
        console.error("❌ Failed to save call log:", e);
        addToast({
          type: "error",
          title: "فشل حفظ المكالمة",
          description: String(e),
        });
      });
  };

  // Keep saveCallLogRef in sync with saveCallLog
  React.useEffect(() => {
    saveCallLogRef.current = saveCallLog;
  });

  // Start call
  const startCall = async () => {
    const sessionId = `live-${Date.now()}`;
    const sttConfig = getSTTConfig();
    const llmConfig = getLLMConfig();
    const ttsConfig = getTTSConfig();

    const startTime = new Date();
    setStatus("connecting");
    setCallStartTime(startTime);
    callStartTimeRef.current = startTime; // Set ref directly to avoid timing issues
    setCallCost(null);
    callStatusRef.current = "completed";
    costSummaryReceivedRef.current = false;
    callSavedRef.current = false; // Reset saved flag for new call
    pendingCostRef.current = null; // Reset cost ref
    latencyMeasurementsRef.current = { responseTimes: [], sttLatencies: [], llmLatencies: [], ttsLatencies: [] }; // Reset latency measurements
    setCurrentLatency({ stt: null, llm: null, tts: null, total: null }); // Reset real-time latency display

    try {
      // Connect WebSocket
      const ws = new WebSocket(`ws://localhost:8000/api/realtime/realtime/${sessionId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("WebSocket connected");
        console.log("🎙️ STT Config:", sttConfig.provider, "| API Key:", sttConfig.apiKey ? "✅ Present" : "❌ Missing");
        console.log("🤖 LLM Config:", llmConfig.provider, llmConfig.model, "| API Key:", llmConfig.apiKey ? "✅ Present" : "❌ Missing");
        console.log("🔊 TTS Config:", ttsConfig.provider, "| API Key:", ttsConfig.apiKey ? "✅ Present" : "❌ Missing", "| Region:", ttsConfig.region || "N/A");

        // Send config with assistant settings
        ws.send(JSON.stringify({
          type: "config",
          data: {
            // STT config
            stt_provider: sttConfig.provider,
            stt_api_key: sttConfig.apiKey,
            stt_region: sttConfig.region,
            // LLM config
            llm_provider: llmConfig.provider,
            llm_api_key: llmConfig.apiKey,
            llm_model: llmConfig.model,
            llm_temperature: llmConfig.temperature,
            // TTS config
            tts_provider: ttsConfig.provider,
            tts_api_key: ttsConfig.apiKey,
            tts_region: ttsConfig.region,
            tts_voice_id: ttsConfig.voiceId,
            tts_voice_speed: ttsConfig.voiceSpeed,
            tts_voice_stability: ttsConfig.voiceStability,
            // Other
            system_prompt: systemPrompt,
            language: assistant?.transcriberLanguage || "ar",
            // First message settings
            first_message: assistant?.firstMessage || "",
            first_message_mode: assistant?.firstMessageMode || "assistant-speaks-first",
            // Interruption settings
            interruption_enabled: assistant?.interruptionEnabled ?? true,
            interruption_words_threshold: assistant?.interruptionWordsThreshold ?? 0,
            stop_on_hangup: assistant?.stopOnHangup ?? true,
          },
        }));

        // 🔍 Debug: Log interruption settings being sent
        console.log("⚙️ Interruption config sent:", {
          enabled: assistant?.interruptionEnabled ?? true,
          wordsThreshold: assistant?.interruptionWordsThreshold ?? 0,
          fromAssistant: assistant?.name || "default",
        });
      };

      ws.onmessage = async (event) => {
        const message = JSON.parse(event.data);
        console.log("Received:", message.type);

        switch (message.type) {
          case "ready":
            setStatus("active");
            addToast({ type: "success", title: "متصل!", description: "ابدأ تكلم..." });
            startAudioStream();
            break;

          case "speech_started":
            setIsSpeaking(true);
            break;

          case "speech_ended":
            setIsSpeaking(false);
            // Track when user stops speaking for latency measurement
            speechEndTimeRef.current = Date.now();
            break;

          case "interim_transcript":
            setInterimText(message.text);
            break;

          case "transcript":
            setInterimText("");
            const now = Date.now();
            const newEntry = {
              role: message.role as "user" | "assistant",
              text: message.text,
              timestamp: new Date(),
            };
            setTranscript(prev => {
              // 🎯 If replace flag is true, replace the last user message instead of adding
              if (message.replace && message.role === "user") {
                // Find and replace the last user message
                const newTranscript = [...prev];
                for (let i = newTranscript.length - 1; i >= 0; i--) {
                  if (newTranscript[i].role === "user") {
                    console.log(`🔄 Replacing user message: "${newTranscript[i].text.substring(0, 30)}..." with "${message.text.substring(0, 30)}..."`);
                    newTranscript[i] = newEntry;
                    transcriptRef.current = newTranscript;
                    return newTranscript;
                  }
                }
                // No user message found, just add it
                console.log(`➕ No user message to replace, adding new: "${message.text.substring(0, 30)}..."`);
              }
              const newTranscript = [...prev, newEntry];
              transcriptRef.current = newTranscript; // Update ref directly
              return newTranscript;
            });

            // Track latencies
            if (message.role === "user" && speechEndTimeRef.current) {
              // STT latency: time from speech end to transcript
              const sttLatency = now - speechEndTimeRef.current;
              latencyMeasurementsRef.current.sttLatencies.push(sttLatency);
              lastTranscriptTimeRef.current = now;
              setCurrentLatency(prev => ({ ...prev, stt: sttLatency }));
              console.log(`⏱️ STT Latency: ${sttLatency}ms`);
            } else if (message.role === "assistant" && lastTranscriptTimeRef.current) {
              // LLM latency: time from user transcript to AI response
              const llmLatency = now - lastTranscriptTimeRef.current;
              latencyMeasurementsRef.current.llmLatencies.push(llmLatency);
              lastAITextTimeRef.current = now;
              setCurrentLatency(prev => ({ ...prev, llm: llmLatency }));
              console.log(`⏱️ LLM Latency: ${llmLatency}ms`);
            }
            break;

          case "thinking":
            setIsThinking(true);
            setStreamingText("");  // Clear previous streaming text
            // Reset interrupted flag - AI is starting new response
            audioInterruptedRef.current = false;
            break;

          case "speaking":
            setIsThinking(false);
            setIsAISpeaking(true);
            // Reset interrupted flag - AI is speaking
            audioInterruptedRef.current = false;
            break;

          case "text_stream":
            // 📝 Live text streaming - shows AI response character by character (like VAPI)
            if (message.delta) {
              // Append new characters for smooth typewriter effect
              setStreamingText(prev => prev + message.delta);
            } else {
              // Fallback to full text if no delta
              setStreamingText(message.text);
            }
            if (message.final) {
              // When final, clear streaming text (transcript will have the final version)
              setStreamingText("");
            }
            break;

          case "audio":
            // Note: isAISpeaking is now managed by the audio queue
            // Track TTS latency and total response time
            const audioNow = Date.now();
            if (lastAITextTimeRef.current) {
              // TTS latency: time from AI text to audio start
              const ttsLatency = audioNow - lastAITextTimeRef.current;
              latencyMeasurementsRef.current.ttsLatencies.push(ttsLatency);
              setCurrentLatency(prev => ({ ...prev, tts: ttsLatency }));
              console.log(`⏱️ TTS Latency: ${ttsLatency}ms`);
            }
            if (speechEndTimeRef.current) {
              // Total response time: from user speech end to audio start
              const totalLatency = audioNow - speechEndTimeRef.current;
              latencyMeasurementsRef.current.responseTimes.push(totalLatency);
              setCurrentLatency(prev => ({ ...prev, total: totalLatency }));
              console.log(`⏱️ Total Response Time: ${totalLatency}ms`);
              // Reset for next turn
              speechEndTimeRef.current = null;
            }
            playAudio(message.data, message.sequence || 0);
            break;

          case "interrupted":
          case "stop_audio":
            // User interrupted the AI - STOP EVERYTHING NOW!
            console.log("🛑🛑🛑 STOPPING ALL AUDIO - USER INTERRUPTED!");
            clearAudioQueue();
            setIsAISpeaking(false);
            if (message.type === "interrupted") {
              callStatusRef.current = "interrupted";
            }
            break;

          case "speech_cancelled":
            // Speech was cancelled due to interruption
            clearAudioQueue();
            setIsAISpeaking(false);
            console.log("🔇 Speech cancelled");
            break;

          case "error":
            callStatusRef.current = "failed";
            addToast({ type: "error", title: "خطأ", description: message.message });
            break;

          case "cost_summary":
            // Received cost summary from backend - store in ref for endCall to use
            const cost = message.data as CostBreakdown;
            setCallCost(cost);
            pendingCostRef.current = cost; // Store for endCall
            costSummaryReceivedRef.current = true;
            console.log("💰 Received cost_summary from backend:");
            console.log("   Total cost:", cost.total_cost);
            console.log("   Recording ID:", cost.recording_id);
            console.log("   Waveform points:", cost.waveform?.length || 0);
            console.log("   Call duration:", cost.call_duration || 0);
            // Don't save here - let endCall handle it with latency data
            console.log("✅ cost_summary stored, waiting for endCall to save...");
            if (wsRef.current) {
              wsRef.current.close();
              wsRef.current = null;
            }
            break;
        }
      };

      ws.onerror = () => {
        callStatusRef.current = "failed";
        setStatus("error");
        addToast({ type: "error", title: "خطأ في الاتصال" });
      };

      ws.onclose = () => {
        console.log("🔌 WebSocket closed");
        setStatus("idle");
        stopAudioStream();
        // CRITICAL: Save call log as fallback if not already saved
        // This handles the case where WebSocket closes before cost_summary arrives
        if (!callSavedRef.current && callStartTimeRef.current) {
          console.log("⚠️ WebSocket closed before save - saving now as fallback");
          // Small delay to allow any pending cost_summary to be processed
          setTimeout(() => {
            if (!callSavedRef.current && callStartTimeRef.current) {
              console.log("📝 Fallback save triggered from onclose");
              saveCallLogRef.current(callStatusRef.current);
            }
          }, 500);
        }
      };

    } catch (error) {
      setStatus("error");
      console.error("Connection error:", error);
    }
  };

  // End call
  const endCall = () => {
    console.log("🔚 endCall called");

    // Capture everything NOW before any async stuff
    const startTime = callStartTimeRef.current;
    const currentTranscript = [...transcriptRef.current];
    const status = callStatusRef.current;

    // Send end message
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ type: "end" }));
      } catch {}
    }

    // Stop everything immediately
    clearAudioQueue();  // Clear audio queue on call end
    stopAudioStream();
    setStatus("idle");
    setIsSpeaking(false);
    setIsThinking(false);
    setIsAISpeaking(false);

    // Save function - will be called after delay to get cost
    const doSave = () => {
      // Read latency measurements fresh from ref (not captured earlier)
      const measurements = latencyMeasurementsRef.current;
      console.log("📝 doSave called");
      console.log("   callSavedRef:", callSavedRef.current);
      console.log("   startTime:", startTime);
      console.log("   pendingCostRef:", pendingCostRef.current);
      console.log("   latency measurements:", measurements);
      if (callSavedRef.current || !startTime) {
        console.log("   Skipping save - already saved or no start time");
        return;
      }

      const endTime = new Date();
      const duration = Math.round((endTime.getTime() - startTime.getTime()) / 1000);
      if (duration < 2) return;

      const cost = pendingCostRef.current;
      const avgResponseTime = measurements.responseTimes.length > 0
        ? Math.round(measurements.responseTimes.reduce((a, b) => a + b, 0) / measurements.responseTimes.length) : 0;
      const avgSttLatency = measurements.sttLatencies.length > 0
        ? Math.round(measurements.sttLatencies.reduce((a, b) => a + b, 0) / measurements.sttLatencies.length) : 0;
      const avgLlmLatency = measurements.llmLatencies.length > 0
        ? Math.round(measurements.llmLatencies.reduce((a, b) => a + b, 0) / measurements.llmLatencies.length) : 0;
      const avgTtsLatency = measurements.ttsLatencies.length > 0
        ? Math.round(measurements.ttsLatencies.reduce((a, b) => a + b, 0) / measurements.ttsLatencies.length) : 0;

      const callLog = {
        id: `call-${Date.now()}`,
        assistantId: assistant?.id || "default",
        assistantName: assistant?.name || "مكالمة سريعة",
        startTime: startTime.toISOString(),
        endTime: endTime.toISOString(),
        duration: cost?.call_duration || duration,
        status: currentTranscript.length === 0 ? "no_speech" : status,
        transcript: currentTranscript.map((t) => ({
          role: t.role, text: t.text, timestamp: t.timestamp.toISOString(),
        })),
        metadata: {
          llmProvider: getLLMConfig().provider,
          llmModel: getLLMConfig().model,
          ttsProvider: getTTSConfig().provider,
          sttProvider: getSTTConfig().provider,
          language: assistant?.transcriberLanguage || "ar",
        },
        cost: cost ? {
          ...cost,
          waveform: undefined, // Don't store waveform in logs (too large)
        } : undefined,
        // Save latency if we have any data (not just if avgResponseTime > 0)
        latency: (avgSttLatency > 0 || avgLlmLatency > 0 || avgTtsLatency > 0 || avgResponseTime > 0)
          ? { avgResponseTime, sttLatency: avgSttLatency, llmLatency: avgLlmLatency, ttsLatency: avgTtsLatency }
          : undefined,
        // Limit waveform to 100 points max to save space
        waveform: cost?.waveform ? cost.waveform.slice(0, 100) : undefined,
      };

      // Save to IndexedDB (unlimited storage!)
      saveCallLogToDB(callLog as CallLogEntry)
        .then(() => {
          callSavedRef.current = true;
          console.log("✅ SAVED to IndexedDB!", callLog.id);
          addToast({
            type: "success",
            title: "تم حفظ المكالمة",
            description: `${duration}s${cost?.total_cost ? ` | $${cost.total_cost.toFixed(4)}` : ""}${avgResponseTime ? ` | ${avgResponseTime}ms` : ""}`,
          });
        })
        .catch((e) => {
          console.error("Save error:", e);
          addToast({
            type: "error",
            title: "فشل حفظ المكالمة",
            description: String(e),
          });
        })
    };

    // Wait 2s for cost_summary, then save
    setTimeout(doSave, 2000);

    // Cleanup - give more time for cost_summary to arrive
    setTimeout(() => {
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
      callStartTimeRef.current = null;
      pendingCostRef.current = null;
    }, 3500);
  };

  // Start audio streaming
  const startAudioStream = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,  // Better audio levels
        }
      });

      streamRef.current = stream;

      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      let chunkCount = 0;
      let silenceStart = 0;
      let isSpeakingNow = false;
      const SILENCE_THRESHOLD = 0.03; // Audio level threshold for VAD (lower = more sensitive)
      const SILENCE_DURATION = 600; // ms of silence before marking end of speech (faster response)

      processor.onaudioprocess = (e) => {
        if (wsRef.current?.readyState === WebSocket.OPEN && !isMutedRef.current) {
          const inputData = e.inputBuffer.getChannelData(0);

          // Calculate RMS (Root Mean Square) for Voice Activity Detection
          let sum = 0;
          for (let i = 0; i < inputData.length; i++) {
            sum += inputData[i] * inputData[i];
          }
          const rms = Math.sqrt(sum / inputData.length);
          const hasVoice = rms > SILENCE_THRESHOLD;

          // Convert float32 to int16
          const pcmData = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            const s = Math.max(-1, Math.min(1, inputData[i]));
            pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }

          // 🛑 BARGE-IN DETECTION: User speaking while AI is playing = INTERRUPT!
          // Only send immediate barge-in if:
          // 1. Interruption is enabled
          // 2. Word threshold is 0 (immediate mode)
          // If threshold > 0, let backend handle it based on word count
          const { enabled, wordsThreshold } = interruptionSettingsRef.current;
          if (hasVoice && isAISpeakingRef.current && enabled && wordsThreshold === 0) {
            const now = Date.now();
            // Debounce: only send barge-in once per second
            if (now - lastBargeInTimeRef.current > 1000) {
              console.log("🛑🛑🛑 BARGE-IN DETECTED! User speaking while AI playing! 🛑🛑🛑");
              lastBargeInTimeRef.current = now;
              // Send barge-in signal to backend
              wsRef.current.send(JSON.stringify({ type: "barge_in" }));
              // Immediately stop audio on frontend
              clearAudioQueue();
            }
          }

          // ALWAYS send audio when AI is speaking (for barge-in detection) or when user has voice
          if (hasVoice || isAISpeakingRef.current) {
            // Send as base64
            const base64 = btoa(String.fromCharCode(...new Uint8Array(pcmData.buffer)));
            wsRef.current.send(JSON.stringify({
              type: "audio",
              data: base64,
            }));

            if (hasVoice) {
              // Voice detected
              silenceStart = 0;
              if (!isSpeakingNow) {
                isSpeakingNow = true;
                setIsSpeaking(true);
                console.log("🎤 Speech started");
              }

              chunkCount++;
              if (chunkCount % 50 === 0) {
                console.log(`Sent ${chunkCount} audio chunks, RMS: ${rms.toFixed(4)}`);
              }
            }
          }

          if (!hasVoice) {
            // Silence detected
            if (isSpeakingNow) {
              if (silenceStart === 0) {
                silenceStart = Date.now();
              } else if (Date.now() - silenceStart > SILENCE_DURATION) {
                // Enough silence - notify server to process
                isSpeakingNow = false;
                setIsSpeaking(false);
                console.log("🔇 Speech ended - notifying server");
                wsRef.current.send(JSON.stringify({ type: "speech_end" }));
              }
            }
          }
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      console.log("Audio streaming started");

    } catch (error) {
      console.error("Failed to start audio:", error);
      addToast({ type: "error", title: "خطأ في المايكروفون" });
    }
  };

  // Stop audio streaming
  const stopAudioStream = () => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
  };

  // 🔊 Play next audio from queue
  const playNextFromQueue = () => {
    // Check if interrupted - stop playing
    if (audioInterruptedRef.current) {
      console.log("🚫 Playback blocked - user interrupted");
      isPlayingRef.current = false;
      setIsAISpeaking(false);
      return;
    }

    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false;
      setIsAISpeaking(false);
      return;
    }

    const item = audioQueueRef.current.shift()!;
    isPlayingRef.current = true;
    setIsAISpeaking(true);

    // 🎯 Tell backend this audio chunk is NOW playing (for accurate history)
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: "audio_playing",
        sequence: item.sequence,
      }));
      console.log(`▶️ Playing audio sequence ${item.sequence}`);
    }

    const audio = new Audio(item.url);
    audioRef.current = audio;

    audio.onended = () => {
      URL.revokeObjectURL(item.url);
      // Play next in queue (if not interrupted)
      if (!audioInterruptedRef.current) {
        playNextFromQueue();
      }
    };

    audio.onerror = () => {
      URL.revokeObjectURL(item.url);
      console.error("Audio playback error");
      // Try next in queue (if not interrupted)
      if (!audioInterruptedRef.current) {
        playNextFromQueue();
      }
    };

    audio.play().catch(err => {
      console.error("Audio play failed:", err);
      if (!audioInterruptedRef.current) {
        playNextFromQueue();
      }
    });
  };

  // 🔊 Queue audio for gapless playback
  const playAudio = (base64Audio: string, sequence: number = 0) => {
    // Check if interrupted - don't queue new audio
    if (audioInterruptedRef.current) {
      console.log("🚫 Audio blocked - user interrupted");
      return;
    }

    try {
      const byteChars = atob(base64Audio);
      const byteNums = new Array(byteChars.length);
      for (let i = 0; i < byteChars.length; i++) {
        byteNums[i] = byteChars.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNums);
      const blob = new Blob([byteArray], { type: 'audio/mpeg' });
      const url = URL.createObjectURL(blob);

      // Add to queue with sequence number
      audioQueueRef.current.push({ url, sequence });
      console.log(`🔊 Audio queued (seq ${sequence}). Queue size: ${audioQueueRef.current.length}`);

      // Start playing if not already playing
      if (!isPlayingRef.current) {
        playNextFromQueue();
      }
    } catch (error) {
      console.error("Audio queue error:", error);
    }
  };

  // 🔇 Clear audio queue (for interruption) - STOP IMMEDIATELY
  const clearAudioQueue = () => {
    console.log("🛑 STOPPING ALL AUDIO NOW!");

    // 🛑 SET INTERRUPTED FLAG FIRST - blocks any new audio from being queued/played
    audioInterruptedRef.current = true;

    // Stop current audio FIRST
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current.src = "";  // Clear source
      audioRef.current.onended = null;  // Remove callback
      audioRef.current.onerror = null;
      audioRef.current = null;
    }

    // Revoke all URLs in queue
    audioQueueRef.current.forEach(item => URL.revokeObjectURL(item.url));
    audioQueueRef.current = [];
    isPlayingRef.current = false;
    setIsAISpeaking(false);

    console.log("🔇 Audio queue cleared, playback stopped, interrupted flag set");
  };

  // Reset
  const resetConversation = () => {
    setTranscript([]);
    setInterimText("");
  };

  const { hasSTT, hasLLM, hasTTS, isComplete } = checkCredentials();
  const llmConfig = getLLMConfig();

  // Prevent hydration mismatch - wait for client mount
  if (!mounted) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--muted-foreground)]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {assistant && (
            <Link href="/assistants">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
            </Link>
          )}
          <div>
            <h2 className="text-2xl font-bold flex items-center gap-2">
              {assistant ? (
                <>
                  <Bot className="h-6 w-6" />
                  Test: {assistant.name}
                </>
              ) : (
                "مكالمة لايف 🎙️"
              )}
            </h2>
            <div className="text-[var(--muted-foreground)]">
              {assistant ? (
                <span className="flex items-center gap-2">
                  <Badge variant="outline">{assistant.modelProvider}</Badge>
                  <Badge variant="outline">{assistant.modelName}</Badge>
                  <Badge variant="outline">{assistant.voiceProvider}</Badge>
                </span>
              ) : (
                "محادثة صوتية في الوقت الحقيقي - اتكلم وهيرد عليك فوراً"
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isSpeaking && (
            <Badge variant="destructive" className="animate-pulse">
              <Radio className="h-3 w-3 mr-1" />
              بيسمعك...
            </Badge>
          )}
          {isThinking && (
            <Badge variant="warning" className="animate-pulse">
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              بيفكر...
            </Badge>
          )}
          {isAISpeaking && (
            <Badge variant="success" className="animate-pulse">
              <Volume2 className="h-3 w-3 mr-1" />
              بيتكلم...
            </Badge>
          )}
          <Badge
            variant={status === "active" ? "success" :
                    status === "connecting" ? "warning" :
                    status === "error" ? "destructive" : "secondary"}
          >
            {status === "active" ? "متصل" :
             status === "connecting" ? "جاري الاتصال..." :
             status === "error" ? "خطأ" : "غير متصل"}
          </Badge>
        </div>
      </div>

      {/* Credentials Warning */}
      {!isComplete && (
        <Card className="border-[var(--warning)] bg-[var(--warning)]/10">
          <CardContent className="pt-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-[var(--warning)]" />
              <div>
                <p className="font-medium">API Keys ناقصة</p>
                <div className="flex gap-2 mt-2">
                  <Badge variant={hasSTT ? "success" : "destructive"}>Deepgram</Badge>
                  <Badge variant={hasLLM ? "success" : "destructive"}>LLM</Badge>
                  <Badge variant={hasTTS ? "success" : "destructive"}>TTS</Badge>
                </div>
                <Button variant="outline" size="sm" className="mt-3" onClick={() => window.location.href = "/settings"}>
                  <Settings className="h-4 w-4 mr-2" />
                  الإعدادات
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* LLM Provider Info - when testing assistant */}
      {assistant && llmConfig.provider && (
        <Card className="border-blue-500/50 bg-blue-500/10">
          <CardContent className="pt-4">
            <div className="flex items-center gap-3">
              <Bot className="h-5 w-5 text-blue-500" />
              <div>
                <p className="font-medium">Using: {llmConfig.provider.toUpperCase()} - {llmConfig.model}</p>
                <p className="text-sm text-[var(--muted-foreground)]">Temperature: {llmConfig.temperature}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Real-time Latency Display - visible during call */}
      {status === "active" && (currentLatency.total !== null || currentLatency.stt !== null) && (
        <Card className="border-purple-500/50 bg-purple-500/10">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="h-5 w-5 text-purple-500" />
                <span className="font-medium">⏱️ التأخير الحالي</span>
              </div>
              <div className="flex items-center gap-4 text-sm">
                {currentLatency.stt !== null && (
                  <div className="flex items-center gap-1">
                    <span className="text-[var(--muted-foreground)]">STT:</span>
                    <span className={`font-bold ${currentLatency.stt > 1000 ? "text-red-500" : currentLatency.stt > 500 ? "text-yellow-500" : "text-green-500"}`}>
                      {currentLatency.stt}ms
                    </span>
                  </div>
                )}
                {currentLatency.llm !== null && (
                  <div className="flex items-center gap-1">
                    <span className="text-[var(--muted-foreground)]">LLM:</span>
                    <span className={`font-bold ${currentLatency.llm > 2000 ? "text-red-500" : currentLatency.llm > 1000 ? "text-yellow-500" : "text-green-500"}`}>
                      {currentLatency.llm}ms
                    </span>
                  </div>
                )}
                {currentLatency.tts !== null && (
                  <div className="flex items-center gap-1">
                    <span className="text-[var(--muted-foreground)]">TTS:</span>
                    <span className={`font-bold ${currentLatency.tts > 1000 ? "text-red-500" : currentLatency.tts > 500 ? "text-yellow-500" : "text-green-500"}`}>
                      {currentLatency.tts}ms
                    </span>
                  </div>
                )}
                {currentLatency.total !== null && (
                  <div className="flex items-center gap-1 border-l border-[var(--border)] pl-4">
                    <span className="text-[var(--muted-foreground)]">إجمالي:</span>
                    <span className={`font-bold text-lg ${currentLatency.total > 3000 ? "text-red-500" : currentLatency.total > 2000 ? "text-yellow-500" : "text-green-500"}`}>
                      {currentLatency.total}ms
                    </span>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Controls */}
        <Card>
          <CardHeader>
            <CardTitle>التحكم</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Prompt */}
            <div className="space-y-2">
              <label className="text-sm font-medium">System Prompt</label>
              <Textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className="min-h-[100px] text-sm"
                dir="rtl"
                disabled={status === "active"}
              />
            </div>

            {/* Call Controls */}
            <div className="flex flex-col items-center gap-4 pt-4">
              {status === "idle" || status === "error" ? (
                <Button
                  size="lg"
                  className="w-full h-16 text-xl bg-green-600 hover:bg-green-700"
                  onClick={startCall}
                  disabled={!isComplete}
                >
                  <Phone className="h-6 w-6 mr-2" />
                  ابدأ المكالمة
                </Button>
              ) : (
                <Button
                  size="lg"
                  variant="destructive"
                  className="w-full h-16 text-xl"
                  onClick={endCall}
                >
                  <PhoneOff className="h-6 w-6 mr-2" />
                  انهي المكالمة
                </Button>
              )}

              {status === "active" && (
                <>
                  {/* Live indicator */}
                  <div className={`w-20 h-20 rounded-full flex items-center justify-center ${
                    isSpeaking ? "bg-red-500 animate-pulse" : "bg-green-500"
                  }`}>
                    <Mic className="h-10 w-10 text-white" />
                  </div>
                  <p className="text-sm text-center">
                    {isSpeaking ? "🎤 بيسمعك دلوقتي..." : "✅ اتكلم عادي"}
                  </p>

                  {/* Mute & Reset */}
                  <div className="flex gap-2">
                    <Button
                      variant={isMuted ? "destructive" : "outline"}
                      onClick={() => setIsMuted(!isMuted)}
                    >
                      {isMuted ? "🔇 Muted" : "🎙️ Active"}
                    </Button>
                    <Button variant="outline" onClick={resetConversation}>
                      <RefreshCw className="h-4 w-4" />
                    </Button>
                  </div>
                </>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Transcript */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>المحادثة</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[500px] overflow-y-auto space-y-4 p-4 bg-[var(--muted)] rounded-lg">
              {transcript.length === 0 && !interimText && status !== "active" && (
                <div className="text-center text-[var(--muted-foreground)] py-20">
                  <Phone className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>ابدأ المكالمة وتكلم</p>
                </div>
              )}

              {transcript.length === 0 && !interimText && status === "active" && (
                <div className="text-center text-[var(--muted-foreground)] py-20">
                  <Mic className="h-12 w-12 mx-auto mb-4 opacity-50 animate-pulse" />
                  <p>اتكلم دلوقتي - بيسمعك!</p>
                </div>
              )}

              {transcript.map((entry, i) => (
                <div key={i} className={`flex ${entry.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[80%] p-3 rounded-lg ${
                    entry.role === "user"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 border border-gray-300 text-gray-900"
                  }`}>
                    <div className="text-xs opacity-70 mb-1">
                      {entry.role === "user" ? "أنت" : "المساعد"}
                    </div>
                    <div dir="rtl">{entry.text}</div>
                  </div>
                </div>
              ))}

              {/* Interim transcript (user speaking) */}
              {interimText && (
                <div className="flex justify-end">
                  <div className="max-w-[80%] p-3 rounded-lg bg-blue-400 text-white opacity-70">
                    <div className="text-xs mb-1">بيسمع...</div>
                    <div dir="rtl">{interimText}</div>
                  </div>
                </div>
              )}

              {/* 📝 Live streaming text - AI response building up in real-time (like VAPI) */}
              {streamingText && (
                <div className="flex justify-start">
                  <div className="max-w-[80%] p-3 rounded-lg bg-gray-100 border border-gray-300 text-gray-900">
                    <div className="text-xs opacity-70 mb-1 flex items-center gap-2">
                      المساعد
                      <span className="inline-block w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    </div>
                    <div dir="rtl">{streamingText}</div>
                  </div>
                </div>
              )}

              {/* Thinking indicator (only show if no streaming text yet) */}
              {isThinking && !streamingText && (
                <div className="flex justify-start">
                  <div className="p-3 rounded-lg bg-white border">
                    <Loader2 className="h-5 w-5 animate-spin" />
                  </div>
                </div>
              )}

              <div ref={transcriptEndRef} />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
