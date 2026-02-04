"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ArrowLeft,
  Save,
  Phone,
  Zap,
} from "lucide-react";

// Realtime Providers
const realtimeProviders = [
  { value: "openai", label: "OpenAI Realtime", description: "gpt-4o-realtime - Native audio I/O" },
  { value: "google", label: "Google Gemini Live", description: "gemini-2.0-flash - Multimodal live" },
  { value: "groq", label: "Groq Ultra-Fast", description: "Fastest LLM + STT/TTS" },
  { value: "elevenlabs", label: "ElevenLabs Conversational", description: "Best voice quality" },
];

// Realtime models by provider
const realtimeModelsByProvider: Record<string, { value: string; label: string; description: string }[]> = {
  openai: [
    { value: "gpt-4o-realtime-preview-2024-12-17", label: "GPT-4o Realtime (Dec 2024)", description: "$0.30/min" },
    { value: "gpt-4o-realtime-preview", label: "GPT-4o Realtime Preview", description: "$0.30/min" },
    { value: "gpt-4o-mini-realtime-preview", label: "GPT-4o Mini Realtime", description: "$0.018/min" },
  ],
  google: [
    { value: "gemini-2.0-flash-exp", label: "Gemini 2.0 Flash (Exp)", description: "$0.0225/min" },
    { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash", description: "$0.0225/min" },
  ],
  groq: [
    { value: "llama-3.3-70b-versatile", label: "Llama 3.3 70B", description: "Best quality" },
    { value: "llama-3.1-8b-instant", label: "Llama 3.1 8B Instant", description: "Ultra fast" },
    { value: "mixtral-8x7b-32768", label: "Mixtral 8x7B", description: "Balanced" },
  ],
  elevenlabs: [
    { value: "eleven_turbo_v2_5", label: "Turbo v2.5", description: "Lowest latency" },
    { value: "eleven_multilingual_v2", label: "Multilingual v2", description: "Best for Arabic" },
  ],
};

// Realtime voices by provider
const realtimeVoicesByProvider: Record<string, { value: string; label: string }[]> = {
  openai: [
    { value: "alloy", label: "Alloy" },
    { value: "echo", label: "Echo" },
    { value: "shimmer", label: "Shimmer" },
    { value: "ash", label: "Ash" },
    { value: "coral", label: "Coral" },
    { value: "sage", label: "Sage" },
  ],
  google: [
    { value: "Puck", label: "Puck (Default)" },
    { value: "Charon", label: "Charon" },
    { value: "Kore", label: "Kore" },
    { value: "Fenrir", label: "Fenrir" },
    { value: "Aoede", label: "Aoede" },
  ],
  groq: [],
  elevenlabs: [
    { value: "EXAVITQu4vr4xnSDxMaL", label: "Bella" },
    { value: "21m00Tcm4TlvDq8ikWAM", label: "Rachel" },
    { value: "pNInz6obpgDQGcFmaJgB", label: "Adam" },
  ],
};

const firstMessageModes = [
  { value: "assistant-speaks-first", label: "Assistant Speaks First" },
  { value: "user-speaks-first", label: "User Speaks First" },
  { value: "assistant-waits", label: "Assistant Waits" },
];

const systemPromptTemplates = [
  {
    value: "phone_call_ar",
    label: "مكالمة هاتفية (عربي)",
    prompt: `أنت موظف خدمة عملاء محترف. تحدث بشكل طبيعي ومختصر.
- ردودك قصيرة (جملة أو جملتين)
- انتظر رد العميل
- إذا قاطعك توقف واستمع`
  },
  {
    value: "phone_call_en",
    label: "Phone Call (English)",
    prompt: `You are a professional customer service agent. Speak naturally and briefly.
- Keep responses short (1-2 sentences)
- Wait for customer response
- If interrupted, stop and listen`
  },
  { value: "custom", label: "Custom", prompt: "" }
];

export default function RealtimeAssistantEditorPage() {
  const params = useParams();
  const router = useRouter();
  const isNew = params.id === "new";
  const [isSaving, setIsSaving] = React.useState(false);

  const [formData, setFormData] = React.useState({
    name: "",
    realtimeProvider: "openai",
    realtimeModel: "gpt-4o-realtime-preview-2024-12-17",
    realtimeVoice: "alloy",
    firstMessageMode: "assistant-speaks-first",
    firstMessage: "مرحبا! كيف يمكنني مساعدتك؟",
    systemPrompt: "",
  });

  const updateFormData = (field: string, value: unknown) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  // Load assistant data
  React.useEffect(() => {
    if (!isNew && params.id) {
      const saved = localStorage.getItem("realtime_assistants");
      if (saved) {
        try {
          const assistants = JSON.parse(saved);
          const assistant = assistants[params.id as string];
          if (assistant) {
            setFormData(prev => ({ ...prev, ...assistant }));
          }
        } catch (e) {
          console.error("Failed to load assistant:", e);
        }
      }
    }
  }, [isNew, params.id]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const saved = localStorage.getItem("realtime_assistants");
      const assistants = saved ? JSON.parse(saved) : {};
      const assistantId = isNew ? `realtime-${Date.now()}` : params.id;

      assistants[assistantId as string] = {
        ...formData,
        id: assistantId,
        updatedAt: new Date().toISOString(),
        createdAt: assistants[assistantId as string]?.createdAt || new Date().toISOString(),
      };

      localStorage.setItem("realtime_assistants", JSON.stringify(assistants));

      // Save for test call
      localStorage.setItem("test_realtime_assistant", JSON.stringify({
        id: assistantId,
        name: formData.name,
        realtime_provider: formData.realtimeProvider,
        realtime_model: formData.realtimeModel,
        realtime_voice: formData.realtimeVoice,
        system_prompt: formData.systemPrompt,
        first_message: formData.firstMessage,
        first_message_mode: formData.firstMessageMode,
      }));

      router.push("/realtime-assistants");
    } catch (e) {
      console.error("Failed to save:", e);
    }
    setIsSaving(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => router.push("/realtime-assistants")}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-yellow-500" />
            <Input
              value={formData.name}
              onChange={(e) => updateFormData("name", e.target.value)}
              placeholder="Assistant Name"
              className="text-xl font-semibold border-0 bg-transparent p-0 h-auto focus:ring-0"
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => {
              localStorage.setItem("test_realtime_assistant", JSON.stringify({
                ...formData,
                id: params.id,
                realtime_provider: formData.realtimeProvider,
                realtime_model: formData.realtimeModel,
                realtime_voice: formData.realtimeVoice,
                system_prompt: formData.systemPrompt,
                first_message: formData.firstMessage,
                first_message_mode: formData.firstMessageMode,
              }));
              router.push(`/realtime-call?assistant=${params.id}`);
            }}
          >
            <Phone className="h-4 w-4 mr-2" />
            Test Call
          </Button>
          <Button onClick={handleSave} isLoading={isSaving}>
            <Save className="h-4 w-4 mr-2" />
            Save
          </Button>
        </div>
      </div>

      {/* Mode Badge */}
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="bg-yellow-500/10 text-yellow-600 border-yellow-500/20">
          <Zap className="h-3 w-3 mr-1" />
          Realtime Mode
        </Badge>
        <span className="text-sm text-muted-foreground">Direct speech-to-speech ~300ms latency</span>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Provider Selection */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>Realtime Provider</CardTitle>
            <CardDescription>Choose your speech-to-speech API</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {realtimeProviders.map((provider) => (
                <div
                  key={provider.value}
                  onClick={() => {
                    updateFormData("realtimeProvider", provider.value);
                    const models = realtimeModelsByProvider[provider.value] || [];
                    if (models.length > 0) updateFormData("realtimeModel", models[0].value);
                    const voices = realtimeVoicesByProvider[provider.value] || [];
                    if (voices.length > 0) updateFormData("realtimeVoice", voices[0].value);
                  }}
                  className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                    formData.realtimeProvider === provider.value
                      ? "border-yellow-500 bg-yellow-500/10 shadow-lg"
                      : "border-border hover:border-yellow-500/50"
                  }`}
                >
                  <div className="font-semibold text-sm">{provider.label}</div>
                  <div className="text-xs text-muted-foreground mt-1">{provider.description}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Model & Voice */}
        <Card>
          <CardHeader>
            <CardTitle>Model & Voice</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Model</label>
              <Select
                value={formData.realtimeModel}
                onChange={(v) => updateFormData("realtimeModel", v)}
                options={(realtimeModelsByProvider[formData.realtimeProvider] || []).map(m => ({
                  value: m.value,
                  label: m.label,
                }))}
              />
              {(() => {
                const model = (realtimeModelsByProvider[formData.realtimeProvider] || []).find(m => m.value === formData.realtimeModel);
                return model ? <div className="text-xs text-muted-foreground">{model.description}</div> : null;
              })()}
            </div>

            {(realtimeVoicesByProvider[formData.realtimeProvider] || []).length > 0 && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Voice</label>
                <Select
                  value={formData.realtimeVoice}
                  onChange={(v) => updateFormData("realtimeVoice", v)}
                  options={(realtimeVoicesByProvider[formData.realtimeProvider] || []).map(v => ({
                    value: v.value,
                    label: v.label,
                  }))}
                />
              </div>
            )}

            {formData.realtimeProvider === "groq" && (
              <div className="p-3 bg-yellow-500/10 rounded-lg border border-yellow-500/20">
                <div className="text-sm text-yellow-600 dark:text-yellow-400">
                  Groq uses ultra-fast LLM with separate TTS
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* First Message */}
        <Card>
          <CardHeader>
            <CardTitle>First Message</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Mode</label>
              <Select
                value={formData.firstMessageMode}
                onChange={(v) => updateFormData("firstMessageMode", v)}
                options={firstMessageModes}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Message</label>
              <Textarea
                value={formData.firstMessage}
                onChange={(e) => updateFormData("firstMessage", e.target.value)}
                className="min-h-[100px]"
              />
            </div>
          </CardContent>
        </Card>

        {/* System Prompt */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>System Prompt</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Template</label>
              <Select
                value="custom"
                onChange={(v) => {
                  const template = systemPromptTemplates.find(t => t.value === v);
                  if (template?.prompt) updateFormData("systemPrompt", template.prompt);
                }}
                options={systemPromptTemplates.map(t => ({ value: t.value, label: t.label }))}
              />
            </div>
            <Textarea
              value={formData.systemPrompt}
              onChange={(e) => updateFormData("systemPrompt", e.target.value)}
              className="min-h-[200px]"
              dir="auto"
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
