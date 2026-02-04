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
  Workflow,
  Bot,
} from "lucide-react";

interface TranscriptEntry {
  role: "user" | "assistant";
  text: string;
  timestamp: Date;
}

interface LiveMetrics {
  durationSec: number;
  responseCount: number;
  avgLatencyMs: number;
}

type ConnectionStatus = "disconnected" | "connecting" | "connected" | "error";
type AgentState = "idle" | "listening" | "processing" | "speaking";

export default function PipelineCallPage() {
  const { addToast } = useToast();
  const searchParams = useSearchParams();

  const [mounted, setMounted] = React.useState(false);
  const [status, setStatus] = React.useState<ConnectionStatus>("disconnected");
  const [agentState, setAgentState] = React.useState<AgentState>("idle");
  const [isMicMuted, setIsMicMuted] = React.useState(false);
  const [isSpeakerMuted, setIsSpeakerMuted] = React.useState(false);
  const [transcript, setTranscript] = React.useState<TranscriptEntry[]>([]);
  const [interimText, setInterimText] = React.useState<string>("");
  const [liveMetrics, setLiveMetrics] = React.useState<LiveMetrics | null>(null);
  const [assistantName, setAssistantName] = React.useState("Pipeline Assistant");

  const wsRef = React.useRef<WebSocket | null>(null);
  const audioContextRef = React.useRef<AudioContext | null>(null);
  const mediaStreamRef = React.useRef<MediaStream | null>(null);
  const processorRef = React.useRef<ScriptProcessorNode | null>(null);
  const transcriptEndRef = React.useRef<HTMLDivElement>(null);
  const callStartTimeRef = React.useRef<number>(0);
  const durationIntervalRef = React.useRef<NodeJS.Timeout | null>(null);
  const nextPlayTimeRef = React.useRef(0);

  // Refs for values accessed in callbacks (to avoid stale closures)
  const isConnectedRef = React.useRef(false);
  const isMicMutedRef = React.useRef(false);
  const isSpeakerMutedRef = React.useRef(false);

  // Ref for message handler (so WebSocket always uses latest)
  const handleMessageRef = React.useRef<(message: any) => void>(() => {});

  React.useEffect(() => {
    setMounted(true);
    // Load assistant from localStorage
    const saved = localStorage.getItem("test_pipeline_assistant");
    if (saved) {
      try {
        const assistant = JSON.parse(saved);
        setAssistantName(assistant.name || "Pipeline Assistant");
      } catch (e) {
        console.error("Failed to load assistant:", e);
      }
    }
  }, []);

  React.useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript, interimText]);

  React.useEffect(() => {
    return () => disconnect();
  }, []);

  // Keep refs in sync with state
  React.useEffect(() => {
    isConnectedRef.current = status === "connected";
  }, [status]);

  React.useEffect(() => {
    isMicMutedRef.current = isMicMuted;
  }, [isMicMuted]);

  React.useEffect(() => {
    isSpeakerMutedRef.current = isSpeakerMuted;
  }, [isSpeakerMuted]);

  const startDurationTimer = () => {
    callStartTimeRef.current = Date.now();
    durationIntervalRef.current = setInterval(() => {
      const durationSec = (Date.now() - callStartTimeRef.current) / 1000;
      setLiveMetrics(prev => ({
        durationSec,
        responseCount: prev?.responseCount || 0,
        avgLatencyMs: prev?.avgLatencyMs || 0,
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
      audioContextRef.current = new AudioContext({ sampleRate: 24000 });
      nextPlayTimeRef.current = 0;

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

      const wsUrl = `ws://localhost:8000/api/voice/ws`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("Pipeline WebSocket connected");

        // Load assistant config and credentials
        let assistant: any = {};
        let credentials: Record<string, Record<string, string>> = {};

        try {
          const saved = localStorage.getItem("test_pipeline_assistant");
          if (saved) assistant = JSON.parse(saved);
          const creds = localStorage.getItem("provider_credentials");
          if (creds) credentials = JSON.parse(creds);
        } catch (e) {
          console.error("Failed to load config:", e);
        }

        ws.send(JSON.stringify({
          type: "config",
          system_prompt: assistant.system_prompt || "",
          assistant: {
            id: assistant.id,
            model_provider: assistant.model_provider || "openai",
            model_name: assistant.model_name || "gpt-4o-mini",
            voice_provider: assistant.voice_provider || "openai",
            voice_id: assistant.voice_id || "alloy",
            transcriber_provider: assistant.transcriber_provider || "deepgram",
            transcriber_language: assistant.transcriber_language || "ar",
            temperature: assistant.temperature || 0.7,
            max_tokens: assistant.max_tokens || 200,
            stop_speaking_plan: assistant.stop_speaking_plan || {
              enable_interruption: true,
              interruption_words: 2,
            },
            voice_mode: "pipeline",
          },
          credentials,
        }));
      };

      ws.onmessage = async (event) => {
        try {
          const message = JSON.parse(event.data);
          // Use ref to always call latest handler
          handleMessageRef.current(message);
        } catch (e) {
          console.error("Error parsing message:", e);
        }
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        setStatus("error");
        addToast({ type: "error", title: "Connection Error", description: "Failed to connect" });
      };

      ws.onclose = () => {
        setStatus("disconnected");
        stopAudioCapture();
        stopDurationTimer();
      };
    } catch (error) {
      console.error("Connection error:", error);
      setStatus("error");
      addToast({ type: "error", title: "Error", description: "Microphone access denied" });
    }
  };

  // Update the message handler ref on every render
  handleMessageRef.current = (message: any) => {
    switch (message.type) {
      case "ready":
        isConnectedRef.current = true;  // Set immediately for audio callback
        setStatus("connected");
        startDurationTimer();
        startAudioCapture();
        addToast({ type: "success", title: "Connected", description: `Pipeline call started (${message.call_id})` });
        break;

      case "transcript":
        if (message.is_final) {
          setTranscript(prev => [...prev, {
            role: message.role,
            text: message.text,
            timestamp: new Date(),
          }]);
          setInterimText("");
          if (message.role === "assistant") {
            setLiveMetrics(prev => ({
              ...prev!,
              responseCount: (prev?.responseCount || 0) + 1,
            }));
          }
        } else {
          setInterimText(message.text);
        }
        break;

      case "audio":
        console.log("Received audio chunk, speaker muted:", isSpeakerMutedRef.current);
        if (!isSpeakerMutedRef.current) {
          playAudio(message.data);
        }
        break;

      case "state":
        setAgentState(message.state);
        break;

      case "metrics":
        setLiveMetrics(prev => ({
          ...prev!,
          avgLatencyMs: message.latency_ms || prev?.avgLatencyMs || 0,
        }));
        break;

      case "response":
        // Assistant response text (pipeline mode)
        console.log("Assistant response:", message.text);
        setTranscript(prev => [...prev, {
          role: "assistant",
          text: message.text,
          timestamp: new Date(),
        }]);
        setLiveMetrics(prev => ({
          ...prev!,
          responseCount: (prev?.responseCount || 0) + 1,
        }));
        break;

      case "error":
        addToast({ type: "error", title: "Error", description: message.message });
        break;
    }
  };

  const startAudioCapture = () => {
    if (!audioContextRef.current || !mediaStreamRef.current || !wsRef.current) {
      console.error("Missing refs for audio capture:", {
        audioContext: !!audioContextRef.current,
        mediaStream: !!mediaStreamRef.current,
        ws: !!wsRef.current,
      });
      return;
    }

    console.log("Starting audio capture, sample rate:", audioContextRef.current.sampleRate);

    const source = audioContextRef.current.createMediaStreamSource(mediaStreamRef.current);
    const processor = audioContextRef.current.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;

    let audioSentCount = 0;

    processor.onaudioprocess = (e) => {
      // Use refs to avoid stale closure problem
      if (isMicMutedRef.current || !isConnectedRef.current) return;

      const inputData = e.inputBuffer.getChannelData(0);
      const targetSampleRate = 16000;
      const ratio = audioContextRef.current!.sampleRate / targetSampleRate;
      const targetLength = Math.floor(inputData.length / ratio);
      const resampled = new Float32Array(targetLength);

      for (let i = 0; i < targetLength; i++) {
        resampled[i] = inputData[Math.floor(i * ratio)];
      }

      const pcm16 = new Int16Array(resampled.length);
      for (let i = 0; i < resampled.length; i++) {
        pcm16[i] = Math.max(-32768, Math.min(32767, resampled[i] * 32767));
      }

      const base64 = btoa(String.fromCharCode(...new Uint8Array(pcm16.buffer)));
      wsRef.current?.send(JSON.stringify({ type: "audio", data: base64 }));

      audioSentCount++;
      if (audioSentCount % 50 === 0) {
        console.log(`Audio sent: ${audioSentCount} chunks`);
      }
    };

    source.connect(processor);
    processor.connect(audioContextRef.current.destination);
    console.log("Audio capture started");
  };

  const stopAudioCapture = () => {
    processorRef.current?.disconnect();
    mediaStreamRef.current?.getTracks().forEach(t => t.stop());
  };

  const playAudio = (base64Audio: string) => {
    if (!audioContextRef.current) {
      console.error("No audio context for playback");
      return;
    }

    try {
      const binaryString = atob(base64Audio);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      const pcm16 = new Int16Array(bytes.buffer);
      const floatData = new Float32Array(pcm16.length);
      for (let i = 0; i < pcm16.length; i++) {
        floatData[i] = pcm16[i] / 32768;
      }

      const buffer = audioContextRef.current.createBuffer(1, floatData.length, 24000);
      buffer.getChannelData(0).set(floatData);

      const source = audioContextRef.current.createBufferSource();
      source.buffer = buffer;
      source.connect(audioContextRef.current.destination);

      const currentTime = audioContextRef.current.currentTime;
      const startTime = Math.max(currentTime, nextPlayTimeRef.current);
      source.start(startTime);
      nextPlayTimeRef.current = startTime + buffer.duration;

      console.log(`Playing audio: ${floatData.length} samples, duration: ${buffer.duration.toFixed(2)}s`);
    } catch (e) {
      console.error("Error playing audio:", e);
    }
  };

  const disconnect = () => {
    isConnectedRef.current = false;
    wsRef.current?.close();
    stopAudioCapture();
    stopDurationTimer();
    audioContextRef.current?.close();
    setStatus("disconnected");
    setAgentState("idle");
  };

  const resetCall = () => {
    setTranscript([]);
    setInterimText("");
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Workflow className="h-6 w-6 text-blue-500" />
            Pipeline Call
          </h1>
          <p className="text-muted-foreground">VAD → STT → LLM → TTS</p>
        </div>
        <Badge variant="outline" className="bg-blue-500/10 text-blue-500">
          {assistantName}
        </Badge>
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
                <Phone className="h-4 w-4 mr-2" />
                Start Call
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
                onClick={() => setIsMicMuted(!isMicMuted)}
                disabled={status !== "connected"}
              >
                {isMicMuted ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              </Button>
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setIsSpeakerMuted(!isSpeakerMuted)}
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
                <span className="text-muted-foreground">Avg Latency</span>
                <span>{liveMetrics?.avgLatencyMs || 0}ms</span>
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
            {transcript.length === 0 && !interimText ? (
              <div className="text-center text-muted-foreground py-8">
                Start a call to see the transcript
              </div>
            ) : (
              <>
                {transcript.map((entry, i) => (
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
                ))}
                {interimText && (
                  <div className="flex justify-end">
                    <div className="max-w-[80%] p-3 rounded-lg bg-primary/50 text-primary-foreground">
                      <p dir="auto" className="italic">{interimText}...</p>
                    </div>
                  </div>
                )}
              </>
            )}
            <div ref={transcriptEndRef} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
