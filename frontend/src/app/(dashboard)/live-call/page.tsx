"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  Mic,
  MicOff,
  Phone,
  PhoneOff,
  Volume2,
  VolumeX,
  RefreshCw,
  Loader2,
  AlertCircle,
  CheckCircle,
  Radio,
  Bot,
  Settings,
  Clock,
  DollarSign,
  Zap,
  MessageSquare,
  Sparkles,
} from "lucide-react";
import {
  GeminiLiveService,
  createGeminiLiveService,
  ARABIC_VOICE_SYSTEM_PROMPT,
} from "@/lib/geminiLiveService";

interface TranscriptEntry {
  role: "user" | "assistant";
  text: string;
  timestamp: Date;
  isFinal?: boolean;
}

interface LiveMetrics {
  durationSec: number;
  responseCount: number;
  avgLatencyMs: number;
  lastLatencyMs: number;
  cost: {
    total: number;
    stt: number;
    llm: number;
    tts: number;
  };
  tokens: {
    input: number;
    output: number;
  };
}

interface StopSpeakingPlan {
  enable_interruption: boolean;
  interruption_words: number;
}

interface Assistant {
  id: string;
  name: string;
  system_prompt: string;
  model_provider: string;
  model_name: string;
  voice_provider: string;
  voice_id: string;
  transcriber_provider: string;
  transcriber_language: string;
  temperature?: number;
  max_tokens?: number;
  stop_speaking_plan?: StopSpeakingPlan;
  voice_mode?: string;
  realtime_provider?: string;
  realtime_model?: string;
  realtime_voice?: string;
}

type ConnectionStatus = "disconnected" | "connecting" | "connected" | "error";
type AgentState = "idle" | "listening" | "processing" | "speaking";

const DEFAULT_PROMPT = `أنت مساعد صوتي ذكي.
تتحدث باللغة العربية.
كن مهذباً ومحترفاً.
ردودك يجب أن تكون مختصرة ومباشرة (جملة أو جملتين فقط).`;

// Default assistants for testing
const DEFAULT_ASSISTANTS: Assistant[] = [
  {
    id: "gemini-direct",
    name: "Gemini مباشر (سريع جداً)",
    system_prompt: ARABIC_VOICE_SYSTEM_PROMPT,
    model_provider: "google",
    model_name: "gemini-2.0-flash-exp",
    voice_provider: "google",
    voice_id: "Kore",
    transcriber_provider: "google",
    transcriber_language: "ar",
    voice_mode: "realtime",
    realtime_provider: "google",
  },
  {
    id: "default",
    name: "المساعد الافتراضي",
    system_prompt: DEFAULT_PROMPT,
    model_provider: "openai",
    model_name: "gpt-4o-mini",
    voice_provider: "openai",
    voice_id: "alloy",
    transcriber_provider: "deepgram",
    transcriber_language: "ar",
  },
  {
    id: "customer-service",
    name: "خدمة العملاء",
    system_prompt: `أنت موظف خدمة عملاء محترف.
تتحدث العربية بطلاقة.
ساعد العميل بحل مشاكله بأدب واحترافية.
ردودك مختصرة ومباشرة.`,
    model_provider: "openai",
    model_name: "gpt-4o-mini",
    voice_provider: "elevenlabs",
    voice_id: "21m00Tcm4TlvDq8ikWAM",
    transcriber_provider: "deepgram",
    transcriber_language: "ar",
  },
];

export default function LiveCallPage() {
  const { addToast } = useToast();
  const searchParams = useSearchParams();

  // Hydration fix
  const [mounted, setMounted] = React.useState(false);

  // Connection state
  const [status, setStatus] = React.useState<ConnectionStatus>("disconnected");
  const [agentState, setAgentState] = React.useState<AgentState>("idle");
  const [isMicMuted, setIsMicMuted] = React.useState(false);
  const [isSpeakerMuted, setIsSpeakerMuted] = React.useState(false);
  const [callId, setCallId] = React.useState<string | null>(null);

  // Direct Gemini mode
  const [useDirectGemini, setUseDirectGemini] = React.useState(false);
  const geminiServiceRef = React.useRef<GeminiLiveService | null>(null);

  // Assistant selection
  const [assistants, setAssistants] = React.useState<Assistant[]>(DEFAULT_ASSISTANTS);
  const [selectedAssistantId, setSelectedAssistantId] = React.useState<string>("gemini-direct");
  const selectedAssistant = assistants.find(a => a.id === selectedAssistantId) || assistants[0];

  // Prompt (from selected assistant)
  const [systemPrompt, setSystemPrompt] = React.useState(ARABIC_VOICE_SYSTEM_PROMPT);

  // Call start time for duration tracking
  const callStartTimeRef = React.useRef<number>(0);

  // Load assistant from URL params / localStorage
  React.useEffect(() => {
    const assistantId = searchParams.get("assistant");
    if (assistantId) {
      try {
        const saved = localStorage.getItem("test_assistant");
        if (saved) {
          const testAssistant = JSON.parse(saved);
          if (testAssistant.id === assistantId || testAssistant) {
            const loadedAssistant: Assistant = {
              id: testAssistant.id || assistantId,
              name: testAssistant.name || "وكيل محمل",
              system_prompt: testAssistant.system_prompt || testAssistant.systemPrompt || DEFAULT_PROMPT,
              model_provider: testAssistant.model_provider || testAssistant.modelProvider || "openai",
              model_name: testAssistant.model_name || testAssistant.modelName || "gpt-4o-mini",
              voice_provider: testAssistant.voice_provider || testAssistant.voiceProvider || "openai",
              voice_id: testAssistant.voice_id || testAssistant.voiceId || "alloy",
              transcriber_provider: testAssistant.transcriber_provider || testAssistant.transcriberProvider || "deepgram",
              transcriber_language: testAssistant.transcriber_language || testAssistant.transcriberLanguage || "ar",
              temperature: testAssistant.temperature || 0.7,
              max_tokens: testAssistant.max_tokens || testAssistant.maxTokens || 1024,
              stop_speaking_plan: testAssistant.stop_speaking_plan || testAssistant.stopSpeakingPlan || {
                enable_interruption: true,
                interruption_words: 2,
              },
              voice_mode: testAssistant.voice_mode || "pipeline",
              realtime_provider: testAssistant.realtime_provider || "openai",
              realtime_model: testAssistant.realtime_model || "gpt-4o-realtime-preview",
              realtime_voice: testAssistant.realtime_voice || "alloy",
            };

            setAssistants(prev => {
              const exists = prev.find(a => a.id === loadedAssistant.id);
              if (exists) return prev;
              return [loadedAssistant, ...prev];
            });

            setSelectedAssistantId(loadedAssistant.id);
            setSystemPrompt(loadedAssistant.system_prompt);
          }
        }
      } catch (e) {
        console.error("Failed to load assistant:", e);
      }
    }
  }, [searchParams]);

  // Update prompt when assistant changes
  React.useEffect(() => {
    if (selectedAssistant) {
      setSystemPrompt(selectedAssistant.system_prompt);
      // Auto-enable direct Gemini for gemini-direct assistant
      if (selectedAssistant.id === "gemini-direct") {
        setUseDirectGemini(true);
      }
    }
  }, [selectedAssistant]);

  // Transcript
  const [transcript, setTranscript] = React.useState<TranscriptEntry[]>([]);
  const [interimText, setInterimText] = React.useState<string>("");

  // Live metrics
  const [liveMetrics, setLiveMetrics] = React.useState<LiveMetrics | null>(null);

  // Refs for backend WebSocket mode
  const wsRef = React.useRef<WebSocket | null>(null);
  const audioContextRef = React.useRef<AudioContext | null>(null);
  const mediaStreamRef = React.useRef<MediaStream | null>(null);
  const processorRef = React.useRef<ScriptProcessorNode | null>(null);
  const transcriptEndRef = React.useRef<HTMLDivElement>(null);
  const audioQueueRef = React.useRef<Float32Array[]>([]);
  const isPlayingRef = React.useRef(false);
  const nextPlayTimeRef = React.useRef(0);

  // Duration timer
  const durationIntervalRef = React.useRef<NodeJS.Timeout | null>(null);

  // Set mounted on client
  React.useEffect(() => {
    setMounted(true);
  }, []);

  // Auto-scroll transcript
  React.useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript, interimText]);

  // Cleanup on unmount
  React.useEffect(() => {
    return () => {
      disconnect();
    };
  }, []);

  // Start duration timer
  const startDurationTimer = () => {
    callStartTimeRef.current = Date.now();
    durationIntervalRef.current = setInterval(() => {
      const durationSec = (Date.now() - callStartTimeRef.current) / 1000;
      setLiveMetrics(prev => ({
        ...prev,
        durationSec,
        responseCount: prev?.responseCount || 0,
        avgLatencyMs: prev?.avgLatencyMs || 0,
        lastLatencyMs: prev?.lastLatencyMs || 0,
        cost: prev?.cost || { total: 0, stt: 0, llm: 0, tts: 0 },
        tokens: prev?.tokens || { input: 0, output: 0 },
      }));
    }, 1000);
  };

  // Stop duration timer
  const stopDurationTimer = () => {
    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current);
      durationIntervalRef.current = null;
    }
  };

  // Connect - choose between direct Gemini or backend WebSocket
  const connect = async () => {
    if (useDirectGemini) {
      await connectDirectGemini();
    } else {
      await connectBackendWebSocket();
    }
  };

  // Connect directly to Gemini Live API
  const connectDirectGemini = async () => {
    setStatus("connecting");

    try {
      // Get Google API key from localStorage
      let googleApiKey = "";
      try {
        const saved = localStorage.getItem("provider_credentials");
        if (saved) {
          const credentials = JSON.parse(saved);
          googleApiKey = credentials.google?.api_key || "";
        }
      } catch (e) {
        console.error("Failed to load credentials:", e);
      }

      if (!googleApiKey) {
        throw new Error("Google API Key غير موجود. اذهب للإعدادات وأضف الـ API Key.");
      }

      // Create Gemini Live service
      geminiServiceRef.current = createGeminiLiveService(
        {
          apiKey: googleApiKey,
          model: "gemini-2.0-flash-exp",
          voiceName: "Kore",
          language: "ar",
          systemPrompt: systemPrompt,
          temperature: 0.7,
        },
        {
          onReady: () => {
            setStatus("connected");
            setCallId("gemini-" + Date.now().toString(36));
            startDurationTimer();
            addToast({
              type: "success",
              title: "متصل بـ Gemini!",
              description: "اتصال مباشر - أقل زمن استجابة",
            });
          },
          onStateChange: (state) => {
            setAgentState(state);
          },
          onUserTranscript: (text) => {
            setTranscript(prev => [
              ...prev,
              {
                role: "user",
                text,
                timestamp: new Date(),
                isFinal: true,
              },
            ]);
            setInterimText("");
          },
          onAssistantTranscript: (text) => {
            setTranscript(prev => [
              ...prev,
              {
                role: "assistant",
                text,
                timestamp: new Date(),
                isFinal: true,
              },
            ]);
            // Update response count
            setLiveMetrics(prev => ({
              ...prev!,
              responseCount: (prev?.responseCount || 0) + 1,
            }));
          },
          onError: (error) => {
            addToast({
              type: "error",
              title: "خطأ",
              description: error,
            });
          },
          onDisconnect: () => {
            setStatus("disconnected");
            stopDurationTimer();
          },
        }
      );

      await geminiServiceRef.current.connect();

    } catch (error: any) {
      console.error("Direct Gemini connection error:", error);
      setStatus("error");
      addToast({
        type: "error",
        title: "خطأ في الاتصال",
        description: error.message || "فشل الاتصال بـ Gemini",
      });
    }
  };

  // Connect via backend WebSocket
  const connectBackendWebSocket = async () => {
    setStatus("connecting");

    try {
      // Initialize audio context and reset play time
      audioContextRef.current = new AudioContext({ sampleRate: 24000 });
      nextPlayTimeRef.current = 0;

      // Get microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      // Connect to WebSocket
      const wsUrl = `ws://localhost:8000/api/voice/ws`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("WebSocket connected");

        // Get credentials from localStorage
        let credentials: Record<string, Record<string, string>> = {};
        try {
          const saved = localStorage.getItem("provider_credentials");
          if (saved) {
            credentials = JSON.parse(saved);
          }
        } catch (e) {
          console.error("Failed to load credentials:", e);
        }

        // Send config with assistant settings and credentials
        ws.send(
          JSON.stringify({
            type: "config",
            system_prompt: systemPrompt,
            assistant: {
              id: selectedAssistant.id,
              model_provider: selectedAssistant.model_provider,
              model_name: selectedAssistant.model_name,
              voice_provider: selectedAssistant.voice_provider,
              voice_id: selectedAssistant.voice_id,
              transcriber_provider: selectedAssistant.transcriber_provider,
              transcriber_language: selectedAssistant.transcriber_language,
              temperature: selectedAssistant.temperature || 0.7,
              max_tokens: selectedAssistant.max_tokens || 200,
              stop_speaking_plan: selectedAssistant.stop_speaking_plan || {
                enable_interruption: true,
                interruption_words: 2,
              },
              voice_mode: selectedAssistant.voice_mode || "pipeline",
              realtime_provider: selectedAssistant.realtime_provider || "openai",
              realtime_model: selectedAssistant.realtime_model || "gpt-4o-realtime-preview",
              realtime_voice: selectedAssistant.realtime_voice || "alloy",
            },
            credentials: credentials,
          })
        );
      };

      ws.onmessage = async (event) => {
        try {
          const message = JSON.parse(event.data);
          handleBackendMessage(message);
        } catch (e) {
          console.error("Error parsing message:", e);
        }
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        setStatus("error");
        addToast({
          type: "error",
          title: "خطأ في الاتصال",
          description: "فشل الاتصال بالخادم",
        });
      };

      ws.onclose = () => {
        console.log("WebSocket closed");
        setStatus("disconnected");
        stopAudioCapture();
        stopDurationTimer();
      };
    } catch (error) {
      console.error("Connection error:", error);
      setStatus("error");
      addToast({
        type: "error",
        title: "خطأ",
        description: "فشل في الحصول على إذن المايكروفون",
      });
    }
  };

  // Handle incoming messages from backend
  const handleBackendMessage = (message: any) => {
    switch (message.type) {
      case "ready":
        setStatus("connected");
        setCallId(message.call_id);
        startAudioCapture();
        startDurationTimer();
        addToast({
          type: "success",
          title: "متصل!",
          description: `معرف المكالمة: ${message.call_id}`,
        });
        break;

      case "state":
        setAgentState(message.state as AgentState);
        break;

      case "transcript":
        if (message.role === "assistant") {
          // Realtime mode sends role
          setTranscript((prev) => [
            ...prev,
            {
              role: "assistant",
              text: message.text,
              timestamp: new Date(),
              isFinal: true,
            },
          ]);
        } else if (message.is_final) {
          setTranscript((prev) => [
            ...prev,
            {
              role: "user",
              text: message.text,
              timestamp: new Date(),
              isFinal: true,
            },
          ]);
          setInterimText("");
        } else {
          setInterimText(message.text);
        }
        break;

      case "response":
        setTranscript((prev) => [
          ...prev,
          {
            role: "assistant",
            text: message.text,
            timestamp: new Date(),
            isFinal: true,
          },
        ]);
        break;

      case "audio":
        if (!isSpeakerMuted) {
          playAudio(message.data);
        }
        break;

      case "metrics":
        setLiveMetrics({
          durationSec: message.duration_sec || 0,
          responseCount: message.response_count || 0,
          avgLatencyMs: message.avg_latency_ms || 0,
          lastLatencyMs: message.last_latency_ms || 0,
          cost: message.cost || { total: 0, stt: 0, llm: 0, tts: 0 },
          tokens: message.tokens || { input: 0, output: 0 },
        });
        break;

      case "error":
        addToast({
          type: "error",
          title: "خطأ",
          description: message.message,
        });
        break;

      case "ping":
        wsRef.current?.send(JSON.stringify({ type: "pong" }));
        break;
    }
  };

  // Start capturing audio from microphone (for backend mode)
  const startAudioCapture = () => {
    if (!mediaStreamRef.current || !audioContextRef.current) return;

    const audioContext = audioContextRef.current;
    const source = audioContext.createMediaStreamSource(mediaStreamRef.current);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (e) => {
      if (isMicMuted || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        return;
      }

      const inputData = e.inputBuffer.getChannelData(0);
      const targetSampleRate = 16000;
      const ratio = audioContext.sampleRate / targetSampleRate;
      const newLength = Math.round(inputData.length / ratio);
      const resampledData = new Float32Array(newLength);

      for (let i = 0; i < newLength; i++) {
        const srcIndex = Math.round(i * ratio);
        resampledData[i] = inputData[srcIndex] || 0;
      }

      const pcmData = new Int16Array(resampledData.length);
      for (let i = 0; i < resampledData.length; i++) {
        const s = Math.max(-1, Math.min(1, resampledData[i]));
        pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }

      const base64 = arrayBufferToBase64(pcmData.buffer);
      wsRef.current.send(
        JSON.stringify({
          type: "audio",
          data: base64,
        })
      );
    };

    source.connect(processor);
    processor.connect(audioContext.destination);
  };

  // Stop audio capture
  const stopAudioCapture = () => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
  };

  // Play received audio
  const playAudio = async (base64Audio: string) => {
    if (!audioContextRef.current) return;

    try {
      const binaryString = atob(base64Audio);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      const pcmData = new Int16Array(bytes.buffer);
      const floatData = new Float32Array(pcmData.length);
      for (let i = 0; i < pcmData.length; i++) {
        floatData[i] = pcmData[i] / 32768;
      }

      const audioBuffer = audioContextRef.current.createBuffer(
        1,
        floatData.length,
        24000
      );
      audioBuffer.getChannelData(0).set(floatData);

      const currentTime = audioContextRef.current.currentTime;
      const startTime = Math.max(currentTime, nextPlayTimeRef.current);

      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);
      source.start(startTime);

      nextPlayTimeRef.current = startTime + audioBuffer.duration;

    } catch (error) {
      console.error("Error playing audio:", error);
    }
  };

  // Disconnect
  const disconnect = () => {
    // Disconnect Gemini if using direct mode
    if (geminiServiceRef.current) {
      geminiServiceRef.current.disconnect();
      geminiServiceRef.current = null;
    }

    // Disconnect backend WebSocket
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: "stop" }));
      wsRef.current.close();
      wsRef.current = null;
    }

    stopAudioCapture();
    stopDurationTimer();
    setStatus("disconnected");
    setAgentState("idle");
    setCallId(null);
    setLiveMetrics(null);
    nextPlayTimeRef.current = 0;
    audioQueueRef.current = [];
  };

  // Toggle mic mute
  const toggleMic = () => {
    setIsMicMuted(!isMicMuted);
  };

  // Toggle speaker mute
  const toggleSpeaker = () => {
    setIsSpeakerMuted(!isSpeakerMuted);
  };

  // Reset conversation
  const resetConversation = () => {
    setTranscript([]);
    setInterimText("");
  };

  // Base64 utilities
  const arrayBufferToBase64 = (buffer: ArrayBuffer): string => {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  };

  // Get state badge
  const getStateBadge = () => {
    switch (agentState) {
      case "listening":
        return (
          <Badge variant="success" className="animate-pulse">
            <Radio className="h-3 w-3 mr-1" />
            يستمع...
          </Badge>
        );
      case "processing":
        return (
          <Badge variant="warning" className="animate-pulse">
            <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            يفكر...
          </Badge>
        );
      case "speaking":
        return (
          <Badge variant="info" className="animate-pulse">
            <Volume2 className="h-3 w-3 mr-1" />
            يتكلم...
          </Badge>
        );
      default:
        return null;
    }
  };

  // Prevent hydration mismatch
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
        <div>
          <h2 className="text-2xl font-bold">مكالمة صوتية مباشرة</h2>
          <p className="text-[var(--muted-foreground)]">
            {useDirectGemini
              ? "اتصال مباشر بـ Gemini - أسرع استجابة!"
              : "محادثة صوتية عبر الخادم"}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {getStateBadge()}
          {useDirectGemini && status === "connected" && (
            <Badge variant="outline" className="bg-gradient-to-r from-blue-500/10 to-purple-500/10">
              <Sparkles className="h-3 w-3 mr-1 text-purple-500" />
              Gemini Direct
            </Badge>
          )}
          <Badge
            variant={
              status === "connected"
                ? "success"
                : status === "connecting"
                ? "warning"
                : status === "error"
                ? "destructive"
                : "secondary"
            }
          >
            {status === "connected" && <CheckCircle className="h-3 w-3 mr-1" />}
            {status === "connecting" && (
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            )}
            {status === "error" && <AlertCircle className="h-3 w-3 mr-1" />}
            {status === "connected"
              ? "متصل"
              : status === "connecting"
              ? "جاري الاتصال..."
              : status === "error"
              ? "خطأ"
              : "غير متصل"}
          </Badge>
          {callId && (
            <Badge variant="outline" className="font-mono text-xs">
              {callId}
            </Badge>
          )}
        </div>
      </div>

      {/* Live Metrics Panel */}
      {status === "connected" && liveMetrics && (
        <Card className="bg-gradient-to-r from-[var(--card)] to-[var(--muted)]">
          <CardContent className="py-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-blue-500/10">
                  <Clock className="h-5 w-5 text-blue-500" />
                </div>
                <div>
                  <p className="text-xs text-[var(--muted-foreground)]">المدة</p>
                  <p className="text-lg font-semibold">
                    {Math.floor(liveMetrics.durationSec / 60)}:{String(Math.floor(liveMetrics.durationSec % 60)).padStart(2, '0')}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-yellow-500/10">
                  <Zap className="h-5 w-5 text-yellow-500" />
                </div>
                <div>
                  <p className="text-xs text-[var(--muted-foreground)]">زمن الاستجابة</p>
                  <p className="text-lg font-semibold">
                    {useDirectGemini ? "~300ms" : (liveMetrics.lastLatencyMs > 0 ? `${liveMetrics.lastLatencyMs}ms` : '-')}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-green-500/10">
                  <DollarSign className="h-5 w-5 text-green-500" />
                </div>
                <div>
                  <p className="text-xs text-[var(--muted-foreground)]">التكلفة</p>
                  <p className="text-lg font-semibold">
                    ${liveMetrics.cost.total.toFixed(4)}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-purple-500/10">
                  <MessageSquare className="h-5 w-5 text-purple-500" />
                </div>
                <div>
                  <p className="text-xs text-[var(--muted-foreground)]">الردود</p>
                  <p className="text-lg font-semibold">{liveMetrics.responseCount}</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Controls */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>إعدادات المكالمة</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Direct Gemini Toggle */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-purple-500/20">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-purple-500" />
                <div>
                  <p className="text-sm font-medium">Gemini مباشر</p>
                  <p className="text-xs text-[var(--muted-foreground)]">أسرع استجابة (~300ms)</p>
                </div>
              </div>
              <Switch
                checked={useDirectGemini}
                onCheckedChange={setUseDirectGemini}
                disabled={status === "connected"}
              />
            </div>

            {/* Assistant Selector */}
            <div className="space-y-2">
              <label className="text-sm font-medium flex items-center gap-2">
                <Bot className="h-4 w-4" />
                اختر المساعد
              </label>
              <Select
                value={selectedAssistantId}
                onChange={setSelectedAssistantId}
                disabled={status === "connected"}
                placeholder="اختر مساعد..."
                options={assistants.map((assistant) => ({
                  value: assistant.id,
                  label: `${assistant.name} (${assistant.model_provider})`,
                }))}
              />
              {selectedAssistant && (
                <div className="flex flex-wrap gap-1 mt-2">
                  <Badge variant="outline" className="text-xs">
                    <Settings className="h-3 w-3 mr-1" />
                    {selectedAssistant.model_provider}: {selectedAssistant.model_name}
                  </Badge>
                  <Badge variant="outline" className="text-xs">
                    <Volume2 className="h-3 w-3 mr-1" />
                    {selectedAssistant.voice_provider}
                  </Badge>
                </div>
              )}
            </div>

            {/* System Prompt */}
            <div className="space-y-2">
              <label className="text-sm font-medium">System Prompt</label>
              <Textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder="اكتب تعليمات الـ Assistant..."
                className="min-h-[120px] text-sm"
                dir="rtl"
                disabled={status === "connected"}
              />
            </div>

            {/* Call Button */}
            <div className="pt-2">
              {status === "disconnected" || status === "error" ? (
                <Button
                  size="lg"
                  className={`w-full h-12 ${useDirectGemini ? 'bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700' : 'bg-green-600 hover:bg-green-700'}`}
                  onClick={connect}
                >
                  {useDirectGemini ? (
                    <>
                      <Sparkles className="h-5 w-5 mr-2" />
                      ابدأ مع Gemini
                    </>
                  ) : (
                    <>
                      <Phone className="h-5 w-5 mr-2" />
                      ابدأ المكالمة
                    </>
                  )}
                </Button>
              ) : status === "connecting" ? (
                <Button size="lg" className="w-full h-12" disabled>
                  <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                  جاري الاتصال...
                </Button>
              ) : (
                <Button
                  size="lg"
                  variant="destructive"
                  className="w-full h-12"
                  onClick={disconnect}
                >
                  <PhoneOff className="h-5 w-5 mr-2" />
                  انهي المكالمة
                </Button>
              )}
            </div>

            {/* Audio Controls */}
            {status === "connected" && (
              <div className="flex justify-center gap-4 pt-4">
                <Button
                  size="lg"
                  variant={isMicMuted ? "destructive" : "outline"}
                  className="w-16 h-16 rounded-full"
                  onClick={toggleMic}
                >
                  {isMicMuted ? (
                    <MicOff className="h-6 w-6" />
                  ) : (
                    <Mic className="h-6 w-6" />
                  )}
                </Button>

                <Button
                  size="lg"
                  variant={isSpeakerMuted ? "destructive" : "outline"}
                  className="w-16 h-16 rounded-full"
                  onClick={toggleSpeaker}
                >
                  {isSpeakerMuted ? (
                    <VolumeX className="h-6 w-6" />
                  ) : (
                    <Volume2 className="h-6 w-6" />
                  )}
                </Button>

                <Button
                  size="lg"
                  variant="outline"
                  className="w-16 h-16 rounded-full"
                  onClick={resetConversation}
                >
                  <RefreshCw className="h-6 w-6" />
                </Button>
              </div>
            )}

            {/* State Info */}
            {status === "connected" && (
              <div className="pt-4 border-t text-center">
                <p className="text-sm text-[var(--muted-foreground)]">
                  {agentState === "listening" && "تكلم الآن..."}
                  {agentState === "processing" && "جاري المعالجة..."}
                  {agentState === "speaking" && "المساعد يتكلم..."}
                  {agentState === "idle" && "جاهز للاستماع"}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Transcript */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>المحادثة</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[500px] overflow-y-auto space-y-4 p-4 bg-[var(--muted)] rounded-lg">
              {transcript.length === 0 && !interimText && status !== "connected" && (
                <div className="text-center text-[var(--muted-foreground)] py-20">
                  <Phone className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>اضغط "ابدأ المكالمة" للبدء</p>
                </div>
              )}

              {transcript.length === 0 && !interimText && status === "connected" && (
                <div className="text-center text-[var(--muted-foreground)] py-20">
                  <Mic className="h-12 w-12 mx-auto mb-4 opacity-50 animate-pulse" />
                  <p>تكلم الآن - المايكروفون مفعل</p>
                </div>
              )}

              {transcript.map((entry, index) => (
                <div
                  key={index}
                  className={`flex ${
                    entry.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[80%] p-3 rounded-lg ${
                      entry.role === "user"
                        ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                        : "bg-[var(--card)] border"
                    }`}
                  >
                    <div className="text-xs opacity-70 mb-1">
                      {entry.role === "user" ? "أنت" : "المساعد"}
                    </div>
                    <div className="text-base" dir="rtl">
                      {entry.text}
                    </div>
                    <div className="text-xs opacity-50 mt-1">
                      {entry.timestamp.toLocaleTimeString("ar-EG")}
                    </div>
                  </div>
                </div>
              ))}

              {interimText && (
                <div className="flex justify-end">
                  <div className="max-w-[80%] p-3 rounded-lg bg-[var(--primary)]/50 text-[var(--primary-foreground)]">
                    <div className="text-xs opacity-70 mb-1">أنت</div>
                    <div className="text-base italic" dir="rtl">
                      {interimText}...
                    </div>
                  </div>
                </div>
              )}

              {agentState === "processing" && (
                <div className="flex justify-start">
                  <div className="max-w-[80%] p-3 rounded-lg bg-[var(--card)] border">
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>جاري التفكير...</span>
                    </div>
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
