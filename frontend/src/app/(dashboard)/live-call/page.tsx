"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { Select } from "@/components/ui/select";
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
} from "lucide-react";

interface TranscriptEntry {
  role: "user" | "assistant";
  text: string;
  timestamp: Date;
  isFinal?: boolean;
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
}

type ConnectionStatus = "disconnected" | "connecting" | "connected" | "error";
type AgentState = "idle" | "listening" | "processing" | "speaking";

const DEFAULT_PROMPT = `أنت مساعد صوتي ذكي.
تتحدث باللغة العربية.
كن مهذباً ومحترفاً.
ردودك يجب أن تكون مختصرة ومباشرة (جملة أو جملتين فقط).`;

// Default assistants for testing (in real app, fetch from API)
const DEFAULT_ASSISTANTS: Assistant[] = [
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
  {
    id: "sales-agent",
    name: "وكيل المبيعات",
    system_prompt: `أنت وكيل مبيعات ذكي.
تتحدث العربية بطلاقة.
ساعد العميل في اختيار المنتجات المناسبة.
كن ودوداً ومقنعاً.`,
    model_provider: "anthropic",
    model_name: "claude-3-5-sonnet-20241022",
    voice_provider: "azure",
    voice_id: "ar-SA-HamedNeural",
    transcriber_provider: "azure",
    transcriber_language: "ar-SA",
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

  // Assistant selection
  const [assistants, setAssistants] = React.useState<Assistant[]>(DEFAULT_ASSISTANTS);
  const [selectedAssistantId, setSelectedAssistantId] = React.useState<string>("default");
  const selectedAssistant = assistants.find(a => a.id === selectedAssistantId) || assistants[0];

  // Prompt (from selected assistant)
  const [systemPrompt, setSystemPrompt] = React.useState(DEFAULT_PROMPT);

  // Load assistant from URL params / localStorage
  React.useEffect(() => {
    const assistantId = searchParams.get("assistant");
    if (assistantId) {
      // Try to load from test_assistant in localStorage
      try {
        const saved = localStorage.getItem("test_assistant");
        if (saved) {
          const testAssistant = JSON.parse(saved);
          if (testAssistant.id === assistantId || testAssistant) {
            // Create assistant object from saved data
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
              // Load stop_speaking_plan (barge-in settings)
              stop_speaking_plan: testAssistant.stop_speaking_plan || testAssistant.stopSpeakingPlan || {
                enable_interruption: true,
                interruption_words: 2,
              },
            };

            // Add to assistants list if not already there
            setAssistants(prev => {
              const exists = prev.find(a => a.id === loadedAssistant.id);
              if (exists) return prev;
              return [loadedAssistant, ...prev];
            });

            // Select this assistant
            setSelectedAssistantId(loadedAssistant.id);
            setSystemPrompt(loadedAssistant.system_prompt);

            console.log("📋 Loaded assistant from localStorage:", loadedAssistant);
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
    }
  }, [selectedAssistant]);

  // Transcript
  const [transcript, setTranscript] = React.useState<TranscriptEntry[]>([]);
  const [interimText, setInterimText] = React.useState<string>("");

  // Refs
  const wsRef = React.useRef<WebSocket | null>(null);
  const audioContextRef = React.useRef<AudioContext | null>(null);
  const mediaStreamRef = React.useRef<MediaStream | null>(null);
  const processorRef = React.useRef<ScriptProcessorNode | null>(null);
  const transcriptEndRef = React.useRef<HTMLDivElement>(null);
  const audioQueueRef = React.useRef<Float32Array[]>([]);
  const isPlayingRef = React.useRef(false);
  const nextPlayTimeRef = React.useRef(0);

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

  // Connect to WebSocket
  const connect = async () => {
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
              // Barge-in (interruption) settings
              stop_speaking_plan: selectedAssistant.stop_speaking_plan || {
                enable_interruption: true,
                interruption_words: 2,
              },
            },
            credentials: credentials,
          })
        );
      };

      ws.onmessage = async (event) => {
        try {
          const message = JSON.parse(event.data);
          handleMessage(message);
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

  // Handle incoming messages
  const handleMessage = (message: any) => {
    switch (message.type) {
      case "ready":
        setStatus("connected");
        setCallId(message.call_id);
        startAudioCapture();
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
        if (message.is_final) {
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

  // Start capturing audio from microphone
  const startAudioCapture = () => {
    if (!mediaStreamRef.current || !audioContextRef.current) return;

    const audioContext = audioContextRef.current;
    const source = audioContext.createMediaStreamSource(mediaStreamRef.current);

    // Use ScriptProcessor for audio capture (deprecated but widely supported)
    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (e) => {
      if (isMicMuted || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        return;
      }

      // Get audio data
      const inputData = e.inputBuffer.getChannelData(0);

      // Resample from AudioContext sample rate to 16000
      const targetSampleRate = 16000;
      const ratio = audioContext.sampleRate / targetSampleRate;
      const newLength = Math.round(inputData.length / ratio);
      const resampledData = new Float32Array(newLength);

      for (let i = 0; i < newLength; i++) {
        const srcIndex = Math.round(i * ratio);
        resampledData[i] = inputData[srcIndex] || 0;
      }

      // Convert to 16-bit PCM
      const pcmData = new Int16Array(resampledData.length);
      for (let i = 0; i < resampledData.length; i++) {
        const s = Math.max(-1, Math.min(1, resampledData[i]));
        pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }

      // Send as base64
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

    console.log("Audio capture started");
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

  // Play received audio with proper queuing
  const playAudio = async (base64Audio: string) => {
    if (!audioContextRef.current) return;

    try {
      // Decode base64 to PCM
      const binaryString = atob(base64Audio);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      // Convert to Float32 for Web Audio API
      const pcmData = new Int16Array(bytes.buffer);
      const floatData = new Float32Array(pcmData.length);
      for (let i = 0; i < pcmData.length; i++) {
        floatData[i] = pcmData[i] / 32768;
      }

      // Create audio buffer
      const audioBuffer = audioContextRef.current.createBuffer(
        1,
        floatData.length,
        24000
      );
      audioBuffer.getChannelData(0).set(floatData);

      // Schedule audio to play in sequence (not overlapping)
      const currentTime = audioContextRef.current.currentTime;
      const startTime = Math.max(currentTime, nextPlayTimeRef.current);

      // Create and play source
      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);
      source.start(startTime);

      // Update next play time (add buffer duration)
      nextPlayTimeRef.current = startTime + audioBuffer.duration;

    } catch (error) {
      console.error("Error playing audio:", error);
    }
  };

  // Disconnect
  const disconnect = () => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: "stop" }));
      wsRef.current.close();
      wsRef.current = null;
    }

    stopAudioCapture();
    setStatus("disconnected");
    setAgentState("idle");
    setCallId(null);
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
            محادثة صوتية فورية مع الذكاء الاصطناعي
          </p>
        </div>

        <div className="flex items-center gap-2">
          {getStateBadge()}
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

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Controls */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>إعدادات المكالمة</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
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
                  <Badge variant="outline" className="text-xs">
                    <Mic className="h-3 w-3 mr-1" />
                    {selectedAssistant.transcriber_provider}
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
                  className="w-full h-12 bg-green-600 hover:bg-green-700"
                  onClick={connect}
                >
                  <Phone className="h-5 w-5 mr-2" />
                  ابدأ المكالمة
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

              {/* Interim transcript */}
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

              {/* Processing indicator */}
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
