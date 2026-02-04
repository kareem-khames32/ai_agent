"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import {
  Mic,
  MicOff,
  Phone,
  PhoneOff,
  Volume2,
  VolumeX,
  RefreshCw,
  Loader2,
  Clock,
  Zap,
  Bot,
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
}

interface LiveMetrics {
  durationSec: number;
  responseCount: number;
}

type ConnectionStatus = "disconnected" | "connecting" | "connected" | "error";
type AgentState = "idle" | "listening" | "processing" | "speaking";

export default function RealtimeCallPage() {
  const { addToast } = useToast();
  const searchParams = useSearchParams();

  const [mounted, setMounted] = React.useState(false);
  const [status, setStatus] = React.useState<ConnectionStatus>("disconnected");
  const [agentState, setAgentState] = React.useState<AgentState>("idle");
  const [isMicMuted, setIsMicMuted] = React.useState(false);
  const [isSpeakerMuted, setIsSpeakerMuted] = React.useState(false);
  const [transcript, setTranscript] = React.useState<TranscriptEntry[]>([]);
  const [liveMetrics, setLiveMetrics] = React.useState<LiveMetrics | null>(null);
  const [assistantName, setAssistantName] = React.useState("Realtime Assistant");
  const [provider, setProvider] = React.useState("google");

  const geminiServiceRef = React.useRef<GeminiLiveService | null>(null);
  const transcriptEndRef = React.useRef<HTMLDivElement>(null);
  const callStartTimeRef = React.useRef<number>(0);
  const durationIntervalRef = React.useRef<NodeJS.Timeout | null>(null);

  React.useEffect(() => {
    setMounted(true);
    // Load assistant from localStorage
    const saved = localStorage.getItem("test_realtime_assistant");
    if (saved) {
      try {
        const assistant = JSON.parse(saved);
        setAssistantName(assistant.name || "Realtime Assistant");
        setProvider(assistant.realtime_provider || assistant.realtimeProvider || "google");
      } catch (e) {
        console.error("Failed to load assistant:", e);
      }
    }
  }, []);

  React.useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  React.useEffect(() => {
    return () => disconnect();
  }, []);

  const startDurationTimer = () => {
    callStartTimeRef.current = Date.now();
    durationIntervalRef.current = setInterval(() => {
      const durationSec = (Date.now() - callStartTimeRef.current) / 1000;
      setLiveMetrics(prev => ({
        durationSec,
        responseCount: prev?.responseCount || 0,
      }));
    }, 1000);
  };

  const stopDurationTimer = () => {
    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current);
      durationIntervalRef.current = null;
    }
  };

  const connect = async () => {
    setStatus("connecting");

    try {
      // Load assistant config
      let assistant: any = {};
      try {
        const saved = localStorage.getItem("test_realtime_assistant");
        if (saved) assistant = JSON.parse(saved);
      } catch (e) {
        console.error("Failed to load assistant:", e);
      }

      const realtimeProvider = assistant.realtime_provider || assistant.realtimeProvider || "google";

      if (realtimeProvider === "google") {
        await connectGemini(assistant);
      } else if (realtimeProvider === "openai") {
        // TODO: Implement OpenAI Realtime connection
        addToast({
          type: "info",
          title: "Coming Soon",
          description: "OpenAI Realtime integration coming soon",
        });
        setStatus("disconnected");
      } else {
        addToast({
          type: "error",
          title: "Unsupported Provider",
          description: `${realtimeProvider} is not yet supported`,
        });
        setStatus("disconnected");
      }
    } catch (error: any) {
      console.error("Connection error:", error);
      setStatus("error");
      addToast({
        type: "error",
        title: "Connection Error",
        description: error.message || "Failed to connect",
      });
    }
  };

  const connectGemini = async (assistant: any) => {
    // Get Google API key
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
      throw new Error("Google API Key not found. Go to Settings and add your API Key.");
    }

    const systemPrompt = assistant.system_prompt || assistant.systemPrompt || ARABIC_VOICE_SYSTEM_PROMPT;
    const voiceName = assistant.realtime_voice || assistant.realtimeVoice || "Kore";
    const model = assistant.realtime_model || assistant.realtimeModel || "gemini-2.0-flash-exp";

    geminiServiceRef.current = createGeminiLiveService(
      {
        apiKey: googleApiKey,
        model,
        voiceName,
        language: "ar",
        systemPrompt,
        temperature: 0.7,
      },
      {
        onReady: () => {
          setStatus("connected");
          startDurationTimer();
          addToast({
            type: "success",
            title: "Connected to Gemini!",
            description: "Direct connection - lowest latency ~300ms",
          });
        },
        onStateChange: (state) => {
          setAgentState(state);
        },
        onUserTranscript: (text) => {
          setTranscript(prev => [...prev, {
            role: "user",
            text,
            timestamp: new Date(),
          }]);
        },
        onAssistantTranscript: (text) => {
          setTranscript(prev => [...prev, {
            role: "assistant",
            text,
            timestamp: new Date(),
          }]);
          setLiveMetrics(prev => ({
            ...prev!,
            responseCount: (prev?.responseCount || 0) + 1,
          }));
        },
        onError: (error) => {
          addToast({ type: "error", title: "Error", description: error });
        },
        onDisconnect: () => {
          setStatus("disconnected");
          stopDurationTimer();
        },
      }
    );

    await geminiServiceRef.current.connect();
  };

  const disconnect = () => {
    geminiServiceRef.current?.disconnect();
    stopDurationTimer();
    setStatus("disconnected");
    setAgentState("idle");
  };

  const toggleMic = () => {
    setIsMicMuted(!isMicMuted);
    geminiServiceRef.current?.setMicMuted(!isMicMuted);
  };

  const toggleSpeaker = () => {
    setIsSpeakerMuted(!isSpeakerMuted);
    geminiServiceRef.current?.setSpeakerMuted(!isSpeakerMuted);
  };

  const resetCall = () => {
    setTranscript([]);
    setLiveMetrics(null);
  };

  if (!mounted) return null;

  const formatDuration = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const getStateColor = () => {
    switch (agentState) {
      case "listening": return "bg-green-500";
      case "processing": return "bg-yellow-500";
      case "speaking": return "bg-blue-500";
      default: return "bg-gray-500";
    }
  };

  const getProviderLabel = () => {
    switch (provider) {
      case "google": return "Gemini Live";
      case "openai": return "OpenAI Realtime";
      case "elevenlabs": return "ElevenLabs";
      default: return provider;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Zap className="h-6 w-6 text-yellow-500" />
            Realtime Call
          </h1>
          <p className="text-muted-foreground">Direct speech-to-speech ~300ms latency</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="bg-yellow-500/10 text-yellow-600">
            {getProviderLabel()}
          </Badge>
          <Badge variant="outline">
            {assistantName}
          </Badge>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        {/* Controls */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Phone className="h-5 w-5" />
              Controls
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {status === "disconnected" ? (
              <Button className="w-full" onClick={connect}>
                <Zap className="h-4 w-4 mr-2" />
                Start Realtime Call
              </Button>
            ) : status === "connecting" ? (
              <Button className="w-full" disabled>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Connecting...
              </Button>
            ) : (
              <Button className="w-full" variant="destructive" onClick={disconnect}>
                <PhoneOff className="h-4 w-4 mr-2" />
                End Call
              </Button>
            )}

            <div className="flex gap-2">
              <Button
                variant="outline"
                className="flex-1"
                onClick={toggleMic}
                disabled={status !== "connected"}
              >
                {isMicMuted ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              </Button>
              <Button
                variant="outline"
                className="flex-1"
                onClick={toggleSpeaker}
                disabled={status !== "connected"}
              >
                {isSpeakerMuted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
              </Button>
              <Button variant="outline" className="flex-1" onClick={resetCall}>
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>

            {/* Agent State */}
            {status === "connected" && (
              <div className="flex items-center gap-2 p-3 bg-muted rounded-lg">
                <div className={`w-3 h-3 rounded-full ${getStateColor()} animate-pulse`} />
                <span className="text-sm capitalize">{agentState}</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Metrics */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Metrics
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Duration</span>
                <span className="font-mono">{formatDuration(liveMetrics?.durationSec || 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Responses</span>
                <span>{liveMetrics?.responseCount || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Latency</span>
                <span className="text-green-500">~300ms</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Status */}
        <Card>
          <CardHeader>
            <CardTitle>Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${
                status === "connected" ? "bg-green-500" :
                status === "connecting" ? "bg-yellow-500" :
                status === "error" ? "bg-red-500" : "bg-gray-500"
              }`} />
              <span className="capitalize">{status}</span>
            </div>
            {status === "connected" && (
              <p className="text-xs text-muted-foreground mt-2">
                Direct {getProviderLabel()} connection
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Transcript */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            Transcript
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[400px] overflow-y-auto space-y-3 p-4 bg-muted/50 rounded-lg">
            {transcript.length === 0 ? (
              <div className="text-center text-muted-foreground py-8">
                Start a call to see the transcript
              </div>
            ) : (
              transcript.map((entry, i) => (
                <div
                  key={i}
                  className={`flex ${entry.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] p-3 rounded-lg ${
                      entry.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-secondary"
                    }`}
                  >
                    <p dir="auto">{entry.text}</p>
                    <p className="text-xs opacity-70 mt-1">
                      {entry.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))
            )}
            <div ref={transcriptEndRef} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
