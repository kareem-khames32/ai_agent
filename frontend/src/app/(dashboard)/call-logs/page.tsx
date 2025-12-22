"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  getAllCallLogs,
  deleteCallLog as deleteCallLogFromDB,
  clearAllCallLogs as clearAllCallLogsFromDB,
  migrateFromLocalStorage,
  getCallLogsCount,
} from "@/lib/callLogsDB";
import {
  Phone,
  PhoneOff,
  Clock,
  Calendar,
  Search,
  ChevronRight,
  ChevronLeft,
  MessageSquare,
  User,
  Bot,
  Trash2,
  Download,
  RefreshCw,
  DollarSign,
  Mic,
  Brain,
  Volume2,
  Play,
  Pause,
  Square,
  Disc,
  Zap,
  X,
  FileText,
  BarChart3,
  Code,
  Activity,
} from "lucide-react";

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

export interface CallLog {
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
    avgResponseTime: number;
    sttLatency: number;
    llmLatency: number;
    ttsLatency: number;
  };
  waveform?: WaveformPoint[];
}

function formatCost(cost: number): string {
  if (cost < 0.01) {
    return `$${cost.toFixed(6)}`;
  }
  return `$${cost.toFixed(4)}`;
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatTime(dateString: string, startTime: string): string {
  const date = new Date(dateString);
  const start = new Date(startTime);
  const diff = (date.getTime() - start.getTime()) / 1000;
  const mins = Math.floor(diff / 60);
  const secs = Math.floor(diff % 60);
  const ms = Math.floor((diff % 1) * 100);
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}.${ms.toString().padStart(2, "0")}`;
}

function getStatusBadge(status: CallLog["status"]) {
  switch (status) {
    case "completed":
      return <Badge variant="success">Completed</Badge>;
    case "failed":
      return <Badge variant="destructive">Failed</Badge>;
    case "interrupted":
      return <Badge variant="warning">Interrupted</Badge>;
    case "no_speech":
      return <Badge variant="secondary">No Speech</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

// Waveform Visualization Component
function WaveformVisualization({
  waveform,
  duration,
  currentTime,
  onSeek,
  isPlaying
}: {
  waveform?: WaveformPoint[];
  duration: number;
  currentTime: number;
  onSeek: (time: number) => void;
  isPlaying: boolean;
}) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const containerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set canvas size
    const rect = container.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = 120;

    // Clear canvas
    ctx.fillStyle = "#1a1a2e";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw center line
    ctx.strokeStyle = "#333";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, canvas.height / 2);
    ctx.lineTo(canvas.width, canvas.height / 2);
    ctx.stroke();

    // Draw time markers
    ctx.fillStyle = "#666";
    ctx.font = "10px monospace";
    const markers = Math.ceil(duration / 30);
    for (let i = 0; i <= markers; i++) {
      const time = i * 30;
      const x = (time / duration) * canvas.width;
      ctx.fillText(formatDuration(time), x + 2, canvas.height - 5);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.strokeStyle = "#333";
      ctx.stroke();
    }

    if (!waveform || waveform.length === 0) {
      ctx.fillStyle = "#666";
      ctx.font = "14px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("No waveform data available", canvas.width / 2, canvas.height / 2);
      return;
    }

    // Draw waveform
    const maxTime = Math.max(...waveform.map(w => w.time), duration);

    waveform.forEach((point, i) => {
      const x = (point.time / maxTime) * canvas.width;
      const barWidth = Math.max(2, (canvas.width / waveform.length) * 0.8);
      const barHeight = point.amplitude * (canvas.height * 0.4);

      // User = orange, AI = teal
      ctx.fillStyle = point.source === "user" ? "#f59e0b" : "#14b8a6";

      // Draw bar above center line
      ctx.fillRect(x, canvas.height / 2 - barHeight, barWidth, barHeight);
      // Mirror below center line
      ctx.fillRect(x, canvas.height / 2, barWidth, barHeight);
    });

    // Draw playback position
    if (currentTime > 0) {
      const x = (currentTime / maxTime) * canvas.width;
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
  }, [waveform, duration, currentTime]);

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const time = (x / rect.width) * duration;
    onSeek(time);
  };

  return (
    <div ref={containerRef} className="w-full bg-[#1a1a2e] rounded-lg overflow-hidden">
      <canvas
        ref={canvasRef}
        className="w-full cursor-pointer"
        onClick={handleClick}
      />
    </div>
  );
}

// Tab Button Component
function TabButton({
  active,
  onClick,
  icon: Icon,
  label
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ElementType;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
        active
          ? "border-[var(--primary)] text-[var(--primary)]"
          : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
      }`}
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  );
}

// Call Detail Modal
function CallDetailModal({
  call,
  onClose,
  onPrevious,
  onNext,
  hasPrevious,
  hasNext
}: {
  call: CallLog;
  onClose: () => void;
  onPrevious: () => void;
  onNext: () => void;
  hasPrevious: boolean;
  hasNext: boolean;
}) {
  const [activeTab, setActiveTab] = React.useState<"transcripts" | "logs" | "analysis" | "messages" | "cost" | "latency">("transcripts");
  const [isPlaying, setIsPlaying] = React.useState(false);
  const [currentTime, setCurrentTime] = React.useState(0);
  const audioRef = React.useRef<HTMLAudioElement | null>(null);

  const playRecording = async () => {
    console.log("🎵 Play button clicked");
    console.log("   recording_id:", call.cost?.recording_id);

    if (!call.cost?.recording_id) {
      console.error("No recording ID available");
      return;
    }

    // If already playing, pause
    if (isPlaying && audioRef.current) {
      console.log("   Pausing playback");
      audioRef.current.pause();
      setIsPlaying(false);
      return;
    }

    // Stop any existing audio
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    const url = `http://localhost:8000/api/realtime/recordings/${call.cost.recording_id}`;
    console.log("   Loading audio from:", url);

    try {
      const audio = new Audio();
      audioRef.current = audio;

      // Set up event handlers before setting src
      audio.ontimeupdate = () => {
        setCurrentTime(audio.currentTime);
      };

      audio.onended = () => {
        console.log("   Playback ended");
        setIsPlaying(false);
        setCurrentTime(0);
      };

      audio.onerror = (e) => {
        console.error("   Audio error:", e);
        setIsPlaying(false);
        audioRef.current = null;
      };

      audio.oncanplaythrough = () => {
        console.log("   Audio ready to play");
      };

      // Load the audio
      audio.src = url;
      audio.load();

      // Wait for audio to be ready then play
      await audio.play();
      console.log("   Playback started");
      setIsPlaying(true);

    } catch (e) {
      console.error("   Playback error:", e);
      setIsPlaying(false);
      audioRef.current = null;
    }
  };

  const seekTo = (time: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const downloadRecording = () => {
    if (!call.cost?.recording_id) return;
    const url = `http://localhost:8000/api/realtime/recordings/${call.cost.recording_id}`;
    const a = document.createElement("a");
    a.href = url;
    a.download = `recording-${call.id}.wav`;
    a.click();
  };

  // Cleanup audio on unmount
  React.useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const waveformData = call.waveform || call.cost?.waveform;

  return (
    <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4">
      <div className="bg-[var(--card)] rounded-xl w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--border)]">
          <div className="flex items-center gap-4">
            <div>
              <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
                <span>{formatDate(call.startTime)}</span>
                <span>•</span>
                <span>inboundPhoneCall</span>
                <Badge variant="outline">{call.assistantName}</Badge>
              </div>
              <div className="flex items-center gap-2 mt-1 text-xs text-[var(--muted-foreground)]">
                <Phone className="h-3 w-3" />
                <span>Customer: {call.id}</span>
                <span>•</span>
                <span>Ended: {call.status === "completed" ? "Customer Ended Call" : call.status}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="flex items-center gap-1">
              <DollarSign className="h-3 w-3" />
              Cost: {formatCost(call.cost?.total_cost || 0)}
            </Badge>
            <span className="text-sm text-[var(--muted-foreground)]">{formatDuration(call.duration)}</span>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon" onClick={onPrevious} disabled={!hasPrevious}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="icon" onClick={onNext} disabled={!hasNext}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Recording Section */}
        <div className="p-4 border-b border-[var(--border)]">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold flex items-center gap-2">
              <Disc className="h-4 w-4 text-red-500" />
              Recording
            </h3>
            <div className="flex items-center gap-2">
              <span className="text-sm text-[var(--muted-foreground)]">
                {formatDuration(currentTime)} / {formatDuration(call.duration)}
              </span>
              {call.cost?.recording_id && (
                <Button variant="outline" size="sm" onClick={downloadRecording}>
                  <Download className="h-4 w-4 mr-1" />
                  Audio
                </Button>
              )}
            </div>
          </div>

          <WaveformVisualization
            waveform={waveformData}
            duration={call.duration}
            currentTime={currentTime}
            onSeek={seekTo}
            isPlaying={isPlaying}
          />

          {call.cost?.recording_id && (
            <div className="mt-3 flex items-center gap-2">
              <Button
                variant={isPlaying ? "destructive" : "default"}
                size="sm"
                onClick={playRecording}
              >
                {isPlaying ? (
                  <>
                    <Pause className="h-4 w-4 mr-1" />
                    Pause
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-1" />
                    Play
                  </>
                )}
              </Button>
              <div className="flex items-center gap-4 text-xs text-[var(--muted-foreground)]">
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded bg-[#f59e0b]"></span>
                  User
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded bg-[#14b8a6]"></span>
                  Assistant
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[var(--border)] overflow-x-auto">
          <TabButton
            active={activeTab === "transcripts"}
            onClick={() => setActiveTab("transcripts")}
            icon={MessageSquare}
            label="Transcripts"
          />
          <TabButton
            active={activeTab === "logs"}
            onClick={() => setActiveTab("logs")}
            icon={FileText}
            label="Logs"
          />
          <TabButton
            active={activeTab === "analysis"}
            onClick={() => setActiveTab("analysis")}
            icon={BarChart3}
            label="Analysis"
          />
          <TabButton
            active={activeTab === "messages"}
            onClick={() => setActiveTab("messages")}
            icon={Code}
            label="Messages"
          />
          <TabButton
            active={activeTab === "cost"}
            onClick={() => setActiveTab("cost")}
            icon={DollarSign}
            label="Call Cost"
          />
          <TabButton
            active={activeTab === "latency"}
            onClick={() => setActiveTab("latency")}
            icon={Activity}
            label="Latency Summary"
          />
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {activeTab === "transcripts" && (
            <div className="space-y-4">
              {call.transcript.length === 0 ? (
                <p className="text-[var(--muted-foreground)] text-center py-8">
                  No transcripts available
                </p>
              ) : (
                call.transcript.map((message, idx) => (
                  <div key={idx} className="flex gap-3">
                    <div className={`flex-shrink-0 w-24 ${message.role === "assistant" ? "text-teal-500" : "text-orange-500"}`}>
                      <div className="font-medium text-sm">
                        {message.role === "assistant" ? "Assistant" : "User"}
                      </div>
                    </div>
                    <div className="flex-1">
                      <div className={`p-3 rounded-lg ${
                        message.role === "assistant"
                          ? "bg-teal-500/10 border border-teal-500/20"
                          : "bg-orange-500/10 border border-orange-500/20"
                      }`}>
                        {message.text}
                      </div>
                      <div className="text-xs text-[var(--muted-foreground)] mt-1 flex items-center gap-2">
                        <Clock className="h-3 w-3" />
                        {new Date(message.timestamp).toLocaleTimeString()} (+{formatTime(message.timestamp, call.startTime)})
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === "logs" && (
            <div className="space-y-2 font-mono text-sm">
              <div className="text-[var(--muted-foreground)]">
                [{new Date(call.startTime).toLocaleTimeString()}] Call started
              </div>
              {call.transcript.map((msg, idx) => (
                <div key={idx} className="text-[var(--muted-foreground)]">
                  [{new Date(msg.timestamp).toLocaleTimeString()}] {msg.role === "user" ? "User spoke" : "Assistant responded"}: {msg.text.substring(0, 50)}...
                </div>
              ))}
              <div className="text-[var(--muted-foreground)]">
                [{new Date(call.endTime).toLocaleTimeString()}] Call ended - {call.status}
              </div>
            </div>
          )}

          {activeTab === "analysis" && (
            <div className="space-y-6">
              <div>
                <h4 className="font-semibold mb-3">Call Summary</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-lg bg-[var(--muted)]">
                    <div className="text-2xl font-bold">{call.transcript.length}</div>
                    <div className="text-sm text-[var(--muted-foreground)]">Total Messages</div>
                  </div>
                  <div className="p-4 rounded-lg bg-[var(--muted)]">
                    <div className="text-2xl font-bold">{formatDuration(call.duration)}</div>
                    <div className="text-sm text-[var(--muted-foreground)]">Duration</div>
                  </div>
                  <div className="p-4 rounded-lg bg-[var(--muted)]">
                    <div className="text-2xl font-bold">{call.transcript.filter(t => t.role === "user").length}</div>
                    <div className="text-sm text-[var(--muted-foreground)]">User Turns</div>
                  </div>
                  <div className="p-4 rounded-lg bg-[var(--muted)]">
                    <div className="text-2xl font-bold">{call.transcript.filter(t => t.role === "assistant").length}</div>
                    <div className="text-sm text-[var(--muted-foreground)]">Assistant Turns</div>
                  </div>
                </div>
              </div>
              <div>
                <h4 className="font-semibold mb-3">Configuration</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">LLM Provider</span>
                    <span>{call.metadata?.llmProvider || "N/A"} / {call.metadata?.llmModel || "N/A"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">STT Provider</span>
                    <span>{call.metadata?.sttProvider || "N/A"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">TTS Provider</span>
                    <span>{call.metadata?.ttsProvider || "N/A"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">Language</span>
                    <span>{call.metadata?.language || "N/A"}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "messages" && (
            <div className="space-y-2">
              <pre className="p-4 bg-[var(--muted)] rounded-lg overflow-x-auto text-sm">
                {JSON.stringify(call.transcript, null, 2)}
              </pre>
            </div>
          )}

          {activeTab === "cost" && (
            <div className="space-y-4">
              {call.cost ? (
                <>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-4 rounded-lg bg-[var(--muted)]">
                      <div className="flex items-center gap-2 mb-2">
                        <Mic className="h-4 w-4 text-blue-500" />
                        <span className="font-medium">STT</span>
                      </div>
                      <div className="text-2xl font-bold">{formatCost(call.cost.stt.cost)}</div>
                      <div className="text-xs text-[var(--muted-foreground)]">
                        {call.cost.stt.minutes.toFixed(2)} min • {call.cost.stt.provider}
                      </div>
                    </div>
                    <div className="p-4 rounded-lg bg-[var(--muted)]">
                      <div className="flex items-center gap-2 mb-2">
                        <Brain className="h-4 w-4 text-purple-500" />
                        <span className="font-medium">LLM</span>
                      </div>
                      <div className="text-2xl font-bold">{formatCost(call.cost.llm.cost)}</div>
                      <div className="text-xs text-[var(--muted-foreground)]">
                        {call.cost.llm.input_tokens + call.cost.llm.output_tokens} tokens • {call.cost.llm.provider}
                      </div>
                    </div>
                    <div className="p-4 rounded-lg bg-[var(--muted)]">
                      <div className="flex items-center gap-2 mb-2">
                        <Volume2 className="h-4 w-4 text-green-500" />
                        <span className="font-medium">TTS</span>
                      </div>
                      <div className="text-2xl font-bold">{formatCost(call.cost.tts.cost)}</div>
                      <div className="text-xs text-[var(--muted-foreground)]">
                        {call.cost.tts.characters} chars • {call.cost.tts.provider}
                      </div>
                    </div>
                  </div>
                  <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/20">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold">Total Cost</span>
                      <span className="text-2xl font-bold text-green-500">{formatCost(call.cost.total_cost)}</span>
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-[var(--muted-foreground)] text-center py-8">
                  No cost data available
                </p>
              )}
            </div>
          )}

          {activeTab === "latency" && (
            <div className="space-y-4">
              {call.latency ? (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 rounded-lg bg-[var(--muted)]">
                      <div className="flex items-center gap-2 mb-2">
                        <Mic className="h-4 w-4 text-blue-500" />
                        <span className="font-medium">STT Latency</span>
                      </div>
                      <div className="text-2xl font-bold">{call.latency.sttLatency}ms</div>
                      <div className="text-xs text-[var(--muted-foreground)]">Speech to Text conversion</div>
                    </div>
                    <div className="p-4 rounded-lg bg-[var(--muted)]">
                      <div className="flex items-center gap-2 mb-2">
                        <Brain className="h-4 w-4 text-purple-500" />
                        <span className="font-medium">LLM Latency</span>
                      </div>
                      <div className="text-2xl font-bold">{call.latency.llmLatency}ms</div>
                      <div className="text-xs text-[var(--muted-foreground)]">AI response generation</div>
                    </div>
                    <div className="p-4 rounded-lg bg-[var(--muted)]">
                      <div className="flex items-center gap-2 mb-2">
                        <Volume2 className="h-4 w-4 text-green-500" />
                        <span className="font-medium">TTS Latency</span>
                      </div>
                      <div className="text-2xl font-bold">{call.latency.ttsLatency}ms</div>
                      <div className="text-xs text-[var(--muted-foreground)]">Text to Speech generation</div>
                    </div>
                    <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
                      <div className="flex items-center gap-2 mb-2">
                        <Zap className="h-4 w-4 text-blue-500" />
                        <span className="font-medium">Total Response Time</span>
                      </div>
                      <div className="text-2xl font-bold text-blue-500">{call.latency.avgResponseTime}ms</div>
                      <div className="text-xs text-[var(--muted-foreground)]">Average end-to-end latency</div>
                    </div>
                  </div>
                  <div className="p-4 rounded-lg bg-[var(--muted)]">
                    <h4 className="font-semibold mb-3">Latency Breakdown</h4>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <div className="w-24 text-sm text-[var(--muted-foreground)]">STT</div>
                        <div className="flex-1 h-4 bg-[var(--background)] rounded overflow-hidden">
                          <div
                            className="h-full bg-blue-500"
                            style={{ width: `${(call.latency.sttLatency / call.latency.avgResponseTime) * 100}%` }}
                          />
                        </div>
                        <div className="w-20 text-right text-sm">{call.latency.sttLatency}ms</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-24 text-sm text-[var(--muted-foreground)]">LLM</div>
                        <div className="flex-1 h-4 bg-[var(--background)] rounded overflow-hidden">
                          <div
                            className="h-full bg-purple-500"
                            style={{ width: `${(call.latency.llmLatency / call.latency.avgResponseTime) * 100}%` }}
                          />
                        </div>
                        <div className="w-20 text-right text-sm">{call.latency.llmLatency}ms</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-24 text-sm text-[var(--muted-foreground)]">TTS</div>
                        <div className="flex-1 h-4 bg-[var(--background)] rounded overflow-hidden">
                          <div
                            className="h-full bg-green-500"
                            style={{ width: `${(call.latency.ttsLatency / call.latency.avgResponseTime) * 100}%` }}
                          />
                        </div>
                        <div className="w-20 text-right text-sm">{call.latency.ttsLatency}ms</div>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-[var(--muted-foreground)] text-center py-8">
                  No latency data available
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function CallLogsPage() {
  const router = useRouter();
  const [callLogs, setCallLogs] = React.useState<CallLog[]>([]);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [filterStatus, setFilterStatus] = React.useState<string>("all");
  const [selectedCallIndex, setSelectedCallIndex] = React.useState<number | null>(null);
  const [loading, setLoading] = React.useState(true);

  // Load call logs from both IndexedDB and Server API
  React.useEffect(() => {
    // First migrate any old localStorage data
    migrateFromLocalStorage().then((migrated) => {
      if (migrated > 0) {
        console.log(`✅ Migrated ${migrated} logs from localStorage`);
      }
      loadCallLogs();
    });
  }, []);

  const loadCallLogs = async () => {
    setLoading(true);
    try {
      // Load from IndexedDB (client-side)
      const localLogs = await getAllCallLogs() as CallLog[];
      console.log(`📊 Loaded ${localLogs.length} call logs from IndexedDB`);

      // Load from Server API (server-side recordings)
      let serverLogs: CallLog[] = [];
      try {
        const response = await fetch("http://localhost:8000/api/call-logs");
        if (response.ok) {
          const data = await response.json();
          // Convert server format to local format
          serverLogs = (data.calls || []).map((call: any) => ({
            id: call.call_id,
            assistantId: call.assistant_id || "",
            assistantName: call.assistant_name || "Unknown",
            startTime: call.started_at,
            endTime: call.ended_at || call.started_at,
            duration: call.duration_sec || 0,
            status: call.status === "completed" ? "completed" : "failed",
            transcript: [],
            metadata: {
              llmProvider: call.voice_mode,
              llmModel: call.realtime_provider || "pipeline",
            },
            cost: {
              stt: { minutes: 0, provider: "", cost: 0 },
              llm: { input_tokens: 0, output_tokens: 0, provider: "", model: "", cost: 0 },
              tts: { characters: 0, provider: "", cost: 0 },
              total_cost: call.total_cost || 0,
            },
            _isServerLog: true,  // Mark as server log for special handling
          }));
          console.log(`📊 Loaded ${serverLogs.length} call logs from Server API`);
        }
      } catch (e) {
        console.log("Server API not available, using local logs only");
      }

      // Merge and deduplicate (prefer local logs if same ID)
      const localIds = new Set(localLogs.map(l => l.id));
      const mergedLogs = [
        ...localLogs,
        ...serverLogs.filter(s => !localIds.has(s.id))
      ].sort((a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime());

      setCallLogs(mergedLogs);
    } catch (e) {
      console.error("Failed to load call logs:", e);
      setCallLogs([]);
    } finally {
      setLoading(false);
    }
  };

  const deleteCallLog = async (id: string) => {
    try {
      // Delete from IndexedDB
      await deleteCallLogFromDB(id);

      // Also try to delete from server
      try {
        await fetch(`http://localhost:8000/api/call-logs/${id}`, {
          method: "DELETE",
        });
      } catch (e) {
        // Server delete failed, that's ok
      }

      const updated = callLogs.filter((log) => log.id !== id);
      setCallLogs(updated);
      if (selectedCallIndex !== null && filteredLogs[selectedCallIndex]?.id === id) {
        setSelectedCallIndex(null);
      }
    } catch (e) {
      console.error("Failed to delete call log:", e);
    }
  };

  const clearAllLogs = async () => {
    if (confirm("هل أنت متأكد من حذف جميع سجلات المكالمات؟")) {
      try {
        await clearAllCallLogsFromDB();
        setCallLogs([]);
        setSelectedCallIndex(null);
        console.log("✅ All call logs cleared");
      } catch (e) {
        console.error("Failed to clear call logs:", e);
      }
    }
  };

  const exportLogs = () => {
    const dataStr = JSON.stringify(callLogs, null, 2);
    const blob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `call-logs-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Filter logs
  const filteredLogs = callLogs.filter((log) => {
    const matchesSearch =
      searchQuery === "" ||
      log.assistantName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.transcript.some((t) => t.text.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesStatus = filterStatus === "all" || log.status === filterStatus;

    return matchesSearch && matchesStatus;
  });

  // Stats
  const totalCalls = callLogs.length;
  const completedCalls = callLogs.filter((l) => l.status === "completed").length;
  const totalDuration = callLogs.reduce((sum, log) => sum + log.duration, 0);
  const avgDuration = totalCalls > 0 ? Math.round(totalDuration / totalCalls) : 0;
  const totalCost = callLogs.reduce((sum, log) => sum + (log.cost?.total_cost || 0), 0);

  const selectedCall = selectedCallIndex !== null ? filteredLogs[selectedCallIndex] : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Call Logs</h2>
          <p className="text-[var(--muted-foreground)]">
            View and manage all previous calls
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={loadCallLogs}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline" onClick={exportLogs} disabled={callLogs.length === 0}>
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
          <Button variant="destructive" onClick={clearAllLogs} disabled={callLogs.length === 0}>
            <Trash2 className="h-4 w-4 mr-2" />
            Clear All
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-5 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Phone className="h-5 w-5 text-[var(--primary)]" />
              <div>
                <p className="text-2xl font-bold">{totalCalls}</p>
                <p className="text-sm text-[var(--muted-foreground)]">Total Calls</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <PhoneOff className="h-5 w-5 text-green-500" />
              <div>
                <p className="text-2xl font-bold">{completedCalls}</p>
                <p className="text-sm text-[var(--muted-foreground)]">Completed</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-orange-500" />
              <div>
                <p className="text-2xl font-bold">{formatDuration(totalDuration)}</p>
                <p className="text-sm text-[var(--muted-foreground)]">Total Duration</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-blue-500" />
              <div>
                <p className="text-2xl font-bold">{formatDuration(avgDuration)}</p>
                <p className="text-sm text-[var(--muted-foreground)]">Avg Duration</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-green-500" />
              <div>
                <p className="text-2xl font-bold">{formatCost(totalCost)}</p>
                <p className="text-sm text-[var(--muted-foreground)]">Total Cost</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search and Filter */}
      <div className="flex gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted-foreground)]" />
          <Input
            placeholder="Search calls..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--card)]"
        >
          <option value="all">All Status</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="interrupted">Interrupted</option>
          <option value="no_speech">No Speech</option>
        </select>
      </div>

      {/* Call List */}
      <div className="space-y-2">
        {loading ? (
          <Card>
            <CardContent className="py-12 text-center">
              <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4 text-[var(--muted-foreground)]" />
              <p className="text-[var(--muted-foreground)]">Loading...</p>
            </CardContent>
          </Card>
        ) : filteredLogs.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <Phone className="h-12 w-12 mx-auto mb-4 text-[var(--muted-foreground)]" />
              <h3 className="text-lg font-semibold mb-2">No calls found</h3>
              <p className="text-[var(--muted-foreground)] mb-4">
                {callLogs.length === 0
                  ? "Start a new call to see logs here"
                  : "No results match your search"}
              </p>
              <Button onClick={() => router.push("/test-call")}>
                <Phone className="h-4 w-4 mr-2" />
                Start New Call
              </Button>
            </CardContent>
          </Card>
        ) : (
          filteredLogs.map((log, index) => (
            <Card
              key={log.id}
              className="cursor-pointer transition-colors hover:bg-[var(--card-hover)]"
              onClick={() => setSelectedCallIndex(index)}
            >
              <CardContent className="py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="p-2 rounded-full bg-[var(--primary)]/10">
                      <Phone className="h-5 w-5 text-[var(--primary)]" />
                    </div>
                    <div>
                      <h4 className="font-semibold">{log.assistantName}</h4>
                      <div className="flex items-center gap-3 text-sm text-[var(--muted-foreground)]">
                        <span className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {formatDate(log.startTime)}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatDuration(log.duration)}
                        </span>
                        <span className="flex items-center gap-1">
                          <MessageSquare className="h-3 w-3" />
                          {log.transcript.length} messages
                        </span>
                        {log.cost && (
                          <span className="flex items-center gap-1 text-green-600">
                            <DollarSign className="h-3 w-3" />
                            {formatCost(log.cost.total_cost)}
                          </span>
                        )}
                        {log.latency && (
                          <span className="flex items-center gap-1 text-blue-500">
                            <Zap className="h-3 w-3" />
                            {log.latency.avgResponseTime}ms
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {getStatusBadge(log.status)}
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteCallLog(log.id);
                      }}
                    >
                      <Trash2 className="h-4 w-4 text-[var(--destructive)]" />
                    </Button>
                    <ChevronRight className="h-5 w-5 text-[var(--muted-foreground)]" />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Call Detail Modal */}
      {selectedCall && (
        <CallDetailModal
          call={selectedCall}
          onClose={() => setSelectedCallIndex(null)}
          onPrevious={() => setSelectedCallIndex(Math.max(0, (selectedCallIndex || 0) - 1))}
          onNext={() => setSelectedCallIndex(Math.min(filteredLogs.length - 1, (selectedCallIndex || 0) + 1))}
          hasPrevious={(selectedCallIndex || 0) > 0}
          hasNext={(selectedCallIndex || 0) < filteredLogs.length - 1}
        />
      )}
    </div>
  );
}
