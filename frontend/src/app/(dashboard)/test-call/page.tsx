"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  Mic,
  MicOff,
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
  Send,
} from "lucide-react";

interface TranscriptEntry {
  role: "user" | "assistant";
  text: string;
  timestamp: Date;
}

interface LatencyData {
  total_ms: number;
  stt_ms: number;
  llm_ms: number;
  tts_ms: number;
}

type ConnectionStatus = "disconnected" | "connecting" | "connected" | "error";

const DEFAULT_PROMPT = `أنت مساعد صوتي ذكي لشركة تحصيل ديون.
تتحدث باللغة العربية الفصحى.
كن مهذباً ومحترفاً.
ردودك يجب أن تكون مختصرة ومباشرة (جملة أو جملتين فقط).
عرف نفسك في البداية.`;

export default function TestCallPage() {
  const { addToast } = useToast();

  // Hydration fix - wait for client mount
  const [mounted, setMounted] = React.useState(false);

  // Connection state
  const [status, setStatus] = React.useState<ConnectionStatus>("disconnected");
  const [isRecording, setIsRecording] = React.useState(false);
  const [isSpeakerMuted, setIsSpeakerMuted] = React.useState(false);
  const [isProcessing, setIsProcessing] = React.useState(false);

  // Prompt
  const [systemPrompt, setSystemPrompt] = React.useState(DEFAULT_PROMPT);

  // Transcript
  const [transcript, setTranscript] = React.useState<TranscriptEntry[]>([]);

  // Latency metrics
  const [latency, setLatency] = React.useState<LatencyData | null>(null);

  // Refs
  const wsRef = React.useRef<WebSocket | null>(null);
  const mediaRecorderRef = React.useRef<MediaRecorder | null>(null);
  const chunksRef = React.useRef<Blob[]>([]);
  const transcriptEndRef = React.useRef<HTMLDivElement>(null);
  const listeningRef = React.useRef(false);
  const audioRef = React.useRef<HTMLAudioElement | null>(null);

  // Set mounted on client
  React.useEffect(() => {
    setMounted(true);
  }, []);

  // Auto-scroll transcript
  React.useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  // Get credentials from localStorage
  const getCredentials = () => {
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

  // Check if required credentials are configured
  const checkCredentials = () => {
    const creds = getCredentials();
    const hasSTT = creds.deepgram?.api_key || creds.azure_speech?.api_key;
    const hasLLM = creds.anthropic?.api_key || creds.openai?.api_key || creds.google?.api_key;
    const hasTTS = creds.elevenlabs?.api_key || creds.azure_tts?.api_key || creds.openai_tts?.api_key;

    return { hasSTT, hasLLM, hasTTS, isComplete: hasSTT && hasLLM && hasTTS };
  };

  // Connect to WebSocket
  const connect = async () => {
    const callId = `test-${Date.now()}`;
    const creds = getCredentials();

    const sttProvider = creds.deepgram?.api_key ? "deepgram" : "azure";
    const sttApiKey = creds.deepgram?.api_key || creds.azure_speech?.api_key;
    const sttRegion = creds.azure_speech?.region;

    const llmProvider = creds.anthropic?.api_key ? "anthropic" :
                        creds.openai?.api_key ? "openai" : "google";
    const llmApiKey = creds.anthropic?.api_key || creds.openai?.api_key || creds.google?.api_key;

    const ttsProvider = creds.elevenlabs?.api_key ? "elevenlabs" :
                        creds.azure_tts?.api_key ? "azure" : "openai";
    const ttsApiKey = creds.elevenlabs?.api_key || creds.azure_tts?.api_key || creds.openai_tts?.api_key;
    const ttsRegion = creds.azure_tts?.region;

    setStatus("connecting");

    try {
      const ws = new WebSocket(`ws://localhost:8000/api/realtime/realtime/${callId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("WebSocket connected");
        ws.send(JSON.stringify({
          type: "config",
          data: {
            stt_provider: sttProvider,
            stt_api_key: sttApiKey,
            stt_region: sttRegion,
            language: "ar",
            llm_provider: llmProvider,
            llm_api_key: llmApiKey,
            tts_provider: ttsProvider,
            tts_api_key: ttsApiKey,
            tts_region: ttsRegion,
            system_prompt: systemPrompt,
          },
        }));
      };

      ws.onmessage = async (event) => {
        const message = JSON.parse(event.data);
        console.log("Received:", message.type);

        switch (message.type) {
          case "ready":
            setStatus("connected");
            addToast({
              type: "success",
              title: "متصل!",
              description: "جاهز - اضغط على المايك وتكلم",
            });
            break;

          case "transcript":
            setTranscript(prev => [...prev, {
              role: message.role,
              text: message.text,
              timestamp: new Date(),
            }]);
            setIsProcessing(false);
            break;

          case "audio":
            setIsProcessing(false);
            if (!isSpeakerMuted) {
              playAudioBase64(message.data);
            }
            // Auto-start listening after response
            if (listeningRef.current) {
              setTimeout(() => startRecording(), 500);
            }
            break;

          case "latency":
            setLatency(message.data);
            break;

          case "error":
            setIsProcessing(false);
            addToast({
              type: "error",
              title: "خطأ",
              description: message.message,
            });
            break;
        }
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        setStatus("error");
      };

      ws.onclose = () => {
        console.log("WebSocket closed");
        setStatus("disconnected");
        stopRecording();
        listeningRef.current = false;
      };

    } catch (error) {
      console.error("Connection error:", error);
      setStatus("error");
    }
  };

  // Disconnect
  const disconnect = () => {
    listeningRef.current = false;
    stopRecording();
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: "end" }));
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus("disconnected");
  };

  // Start recording
  const startRecording = async () => {
    if (isRecording || isProcessing) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        }
      });

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
      });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());

        if (chunksRef.current.length > 0) {
          const blob = new Blob(chunksRef.current, { type: "audio/webm" });
          console.log("Audio blob size:", blob.size);

          if (blob.size > 1000) {
            setIsProcessing(true);
            const arrayBuffer = await blob.arrayBuffer();
            const base64 = arrayBufferToBase64(arrayBuffer);

            if (wsRef.current?.readyState === WebSocket.OPEN) {
              console.log("Sending audio to server...");
              wsRef.current.send(JSON.stringify({
                type: "audio",
                data: base64,
                encoding: "webm",
                sample_rate: 16000,
              }));
            }
          }
        }
        chunksRef.current = [];
      };

      mediaRecorder.start();
      setIsRecording(true);
      console.log("Recording started");

    } catch (error) {
      console.error("Failed to start recording:", error);
      addToast({
        type: "error",
        title: "خطأ في المايكروفون",
        description: "تأكد من السماح بالوصول للمايكروفون",
      });
    }
  };

  // Stop recording
  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      console.log("Stopping recording...");
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  // Toggle continuous listening
  const toggleListening = () => {
    if (listeningRef.current) {
      listeningRef.current = false;
      stopRecording();
    } else {
      listeningRef.current = true;
      startRecording();
    }
  };

  // Play audio from base64
  const playAudioBase64 = (base64Audio: string) => {
    try {
      const byteCharacters = atob(base64Audio);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: 'audio/mpeg' });
      const url = URL.createObjectURL(blob);

      if (audioRef.current) {
        audioRef.current.pause();
      }

      const audio = new Audio(url);
      audioRef.current = audio;
      audio.play().catch(e => console.error("Audio play error:", e));
      audio.onended = () => URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Failed to play audio:", error);
    }
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

  // Reset conversation
  const resetConversation = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "reset" }));
    }
    setTranscript([]);
    setLatency(null);
  };

  const { hasSTT, hasLLM, hasTTS, isComplete } = checkCredentials();

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
        <div>
          <h2 className="text-2xl font-bold">اختبار المكالمة الصوتية</h2>
          <p className="text-[var(--muted-foreground)]">
            اضغط على المايك وتكلم - اضغط مرة تانية لإرسال
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isProcessing && (
            <Badge variant="warning" className="animate-pulse">
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              جاري المعالجة...
            </Badge>
          )}
          <Badge
            variant={status === "connected" ? "success" :
                    status === "connecting" ? "warning" :
                    status === "error" ? "destructive" : "secondary"}
          >
            {status === "connected" && <CheckCircle className="h-3 w-3 mr-1" />}
            {status === "connecting" && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
            {status === "error" && <AlertCircle className="h-3 w-3 mr-1" />}
            {status === "connected" ? "متصل" :
             status === "connecting" ? "جاري الاتصال..." :
             status === "error" ? "خطأ" : "غير متصل"}
          </Badge>
        </div>
      </div>

      {/* Credentials Check */}
      {!isComplete && (
        <Card className="border-[var(--warning)] bg-[var(--warning)]/10">
          <CardContent className="pt-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-[var(--warning)] mt-0.5" />
              <div className="flex-1">
                <p className="font-medium">اعدادات API Keys ناقصة</p>
                <div className="flex gap-2 mt-2">
                  <Badge variant={hasSTT ? "success" : "destructive"}>
                    STT: {hasSTT ? "OK" : "ناقص"}
                  </Badge>
                  <Badge variant={hasLLM ? "success" : "destructive"}>
                    LLM: {hasLLM ? "OK" : "ناقص"}
                  </Badge>
                  <Badge variant={hasTTS ? "success" : "destructive"}>
                    TTS: {hasTTS ? "OK" : "ناقص"}
                  </Badge>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3"
                  onClick={() => window.location.href = "/settings"}
                >
                  <Settings className="h-4 w-4 mr-2" />
                  اذهب للإعدادات
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Controls & Prompt */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>إعدادات المكالمة</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
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
                  disabled={!isComplete}
                >
                  <Phone className="h-5 w-5 mr-2" />
                  ابدأ المكالمة
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

            {/* Recording Button */}
            {status === "connected" && (
              <div className="flex flex-col items-center gap-3 pt-4">
                <Button
                  size="lg"
                  variant={isRecording ? "destructive" : "default"}
                  className={`w-24 h-24 rounded-full ${isRecording ? "animate-pulse" : ""}`}
                  onClick={isRecording ? stopRecording : startRecording}
                  disabled={isProcessing}
                >
                  {isRecording ? (
                    <Send className="h-10 w-10" />
                  ) : (
                    <Mic className="h-10 w-10" />
                  )}
                </Button>
                <p className="text-sm text-[var(--muted-foreground)]">
                  {isRecording ? "اضغط للإرسال" : "اضغط للتسجيل"}
                </p>

                {/* Audio Controls */}
                <div className="flex gap-2 pt-2">
                  <Button
                    variant={isSpeakerMuted ? "destructive" : "outline"}
                    size="icon"
                    onClick={() => setIsSpeakerMuted(!isSpeakerMuted)}
                  >
                    {isSpeakerMuted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={resetConversation}
                  >
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}

            {/* Latency Metrics */}
            {latency && (
              <div className="space-y-2 pt-4 border-t">
                <h4 className="font-medium text-sm">مقاييس السرعة</h4>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="bg-[var(--muted)] p-2 rounded text-center">
                    <div className="text-[var(--muted-foreground)] text-xs">الإجمالي</div>
                    <div className="font-mono font-bold">{latency.total_ms}ms</div>
                  </div>
                  <div className="bg-[var(--muted)] p-2 rounded text-center">
                    <div className="text-[var(--muted-foreground)] text-xs">STT</div>
                    <div className="font-mono">{latency.stt_ms}ms</div>
                  </div>
                  <div className="bg-[var(--muted)] p-2 rounded text-center">
                    <div className="text-[var(--muted-foreground)] text-xs">LLM</div>
                    <div className="font-mono">{latency.llm_ms}ms</div>
                  </div>
                  <div className="bg-[var(--muted)] p-2 rounded text-center">
                    <div className="text-[var(--muted-foreground)] text-xs">TTS</div>
                    <div className="font-mono">{latency.tts_ms}ms</div>
                  </div>
                </div>
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
              {transcript.length === 0 && status !== "connected" && (
                <div className="text-center text-[var(--muted-foreground)] py-20">
                  <Phone className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>اضغط "ابدأ المكالمة" للبدء</p>
                </div>
              )}

              {transcript.length === 0 && status === "connected" && !isProcessing && (
                <div className="text-center text-[var(--muted-foreground)] py-20">
                  <Mic className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>اضغط على زر المايك وتكلم</p>
                </div>
              )}

              {transcript.map((entry, index) => (
                <div
                  key={index}
                  className={`flex ${entry.role === "user" ? "justify-end" : "justify-start"}`}
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
                    <div className="text-base" dir="rtl">{entry.text}</div>
                    <div className="text-xs opacity-50 mt-1">
                      {entry.timestamp.toLocaleTimeString("ar-EG")}
                    </div>
                  </div>
                </div>
              ))}

              {isProcessing && (
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
