"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ArrowLeft,
  Save,
  Play,
  Square,
  Phone,
  Bot,
  Mic,
  Volume2,
  Settings,
  Workflow,
} from "lucide-react";

// LLM Providers
const modelProviders = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "google", label: "Google Gemini" },
  { value: "groq", label: "Groq (Fastest!)" },
  { value: "together", label: "Together AI" },
];

const modelsByProvider: Record<string, { value: string; label: string; price?: string }[]> = {
  openai: [
    { value: "gpt-4o", label: "GPT-4o", price: "$2.50/$10 per 1M" },
    { value: "gpt-4o-mini", label: "GPT-4o Mini", price: "$0.15/$0.60 per 1M" },
    { value: "gpt-4-turbo", label: "GPT-4 Turbo", price: "$10/$30 per 1M" },
  ],
  anthropic: [
    { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4", price: "$3/$15 per 1M" },
    { value: "claude-3-5-sonnet-20241022", label: "Claude 3.5 Sonnet", price: "$3/$15 per 1M" },
    { value: "claude-3-5-haiku-20241022", label: "Claude 3.5 Haiku", price: "$0.80/$4 per 1M" },
  ],
  google: [
    { value: "gemini-2.0-flash-exp", label: "Gemini 2.0 Flash", price: "$0.10/$0.40 per 1M" },
    { value: "gemini-1.5-pro", label: "Gemini 1.5 Pro", price: "$1.25/$5 per 1M" },
    { value: "gemini-1.5-flash", label: "Gemini 1.5 Flash", price: "$0.075/$0.30 per 1M" },
  ],
  groq: [
    { value: "llama-3.3-70b-versatile", label: "Llama 3.3 70B", price: "$0.59/$0.79 per 1M" },
    { value: "llama-3.1-8b-instant", label: "Llama 3.1 8B", price: "$0.05/$0.08 per 1M" },
    { value: "mixtral-8x7b-32768", label: "Mixtral 8x7B", price: "$0.24/$0.24 per 1M" },
  ],
  together: [
    { value: "meta-llama/Llama-3.3-70B-Instruct-Turbo", label: "Llama 3.3 70B Turbo" },
    { value: "Qwen/Qwen2.5-72B-Instruct-Turbo", label: "Qwen 2.5 72B" },
  ],
};

// TTS Providers
const voiceProviders = [
  { value: "azure", label: "Azure TTS (Best Arabic)" },
  { value: "elevenlabs", label: "ElevenLabs (Best Quality)" },
  { value: "openai", label: "OpenAI TTS" },
  { value: "deepgram", label: "Deepgram Aura (Fastest)" },
];

const voicesByProvider: Record<string, { value: string; label: string }[]> = {
  azure: [
    { value: "ar-SA-HamedNeural", label: "Hamed (سعودي)" },
    { value: "ar-SA-ZariyahNeural", label: "Zariyah (سعودي)" },
    { value: "ar-EG-SalmaNeural", label: "Salma (مصري)" },
    { value: "ar-EG-ShakirNeural", label: "Shakir (مصري)" },
    { value: "en-US-JennyNeural", label: "Jenny (US)" },
    { value: "en-US-GuyNeural", label: "Guy (US)" },
  ],
  elevenlabs: [
    { value: "EXAVITQu4vr4xnSDxMaL", label: "Rachel" },
    { value: "pNInz6obpgDQGcFmaJgB", label: "Adam" },
    { value: "21m00Tcm4TlvDq8ikWAM", label: "Drew" },
  ],
  openai: [
    { value: "alloy", label: "Alloy" },
    { value: "echo", label: "Echo" },
    { value: "shimmer", label: "Shimmer" },
    { value: "nova", label: "Nova" },
    { value: "onyx", label: "Onyx" },
  ],
  deepgram: [
    { value: "aura-asteria-en", label: "Asteria" },
    { value: "aura-luna-en", label: "Luna" },
    { value: "aura-orion-en", label: "Orion" },
  ],
};

// STT Providers
const transcriberProviders = [
  { value: "deepgram", label: "Deepgram (Best English)" },
  { value: "groq", label: "Groq Whisper (Fastest)" },
  { value: "openai", label: "OpenAI Whisper" },
  { value: "azure", label: "Azure Speech" },
];

const sttModelsByProvider: Record<string, { value: string; label: string }[]> = {
  deepgram: [
    { value: "nova-3", label: "Nova-3 (Latest)" },
    { value: "nova-2", label: "Nova-2" },
    { value: "whisper-large", label: "Whisper Large" },
  ],
  groq: [
    { value: "whisper-large-v3", label: "Whisper Large V3" },
    { value: "whisper-large-v3-turbo", label: "Whisper Turbo" },
  ],
  openai: [
    { value: "whisper-1", label: "Whisper-1" },
  ],
  azure: [
    { value: "default", label: "Universal" },
  ],
};

const languages = [
  { value: "ar-SA", label: "العربية (سعودي)" },
  { value: "ar-EG", label: "العربية (مصري)" },
  { value: "ar-AE", label: "العربية (إماراتي)" },
  { value: "en-US", label: "English (US)" },
  { value: "en-GB", label: "English (UK)" },
];

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

export default function PipelineAssistantEditorPage() {
  const params = useParams();
  const router = useRouter();
  const isNew = params.id === "new";
  const [activeTab, setActiveTab] = React.useState("model");
  const [isSaving, setIsSaving] = React.useState(false);

  const [formData, setFormData] = React.useState({
    name: "",
    modelProvider: "anthropic",
    modelName: "claude-sonnet-4-20250514",
    temperature: 0.7,
    maxTokens: 1024,
    firstMessageMode: "assistant-speaks-first",
    firstMessage: "مرحبا! كيف يمكنني مساعدتك؟",
    systemPrompt: "",
    voiceProvider: "elevenlabs",
    voiceId: "EXAVITQu4vr4xnSDxMaL",
    voiceSpeed: 1.0,
    transcriberProvider: "deepgram",
    transcriberModel: "nova-2",
    transcriberLanguage: "ar-SA",
    endpointingMs: 500,
    interruptionEnabled: true,
    interruptionWordsThreshold: 2,
    maxDuration: 1800,
    silenceTimeout: 30,
  });

  const updateFormData = (field: string, value: unknown) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  // Load assistant data
  React.useEffect(() => {
    if (!isNew && params.id) {
      const saved = localStorage.getItem("pipeline_assistants");
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
      const saved = localStorage.getItem("pipeline_assistants");
      const assistants = saved ? JSON.parse(saved) : {};
      const assistantId = isNew ? `pipeline-${Date.now()}` : params.id;

      assistants[assistantId as string] = {
        ...formData,
        id: assistantId,
        updatedAt: new Date().toISOString(),
        createdAt: assistants[assistantId as string]?.createdAt || new Date().toISOString(),
      };

      localStorage.setItem("pipeline_assistants", JSON.stringify(assistants));

      // Save for test call
      localStorage.setItem("test_pipeline_assistant", JSON.stringify({
        id: assistantId,
        name: formData.name,
        model_provider: formData.modelProvider,
        model_name: formData.modelName,
        system_prompt: formData.systemPrompt,
        first_message: formData.firstMessage,
        first_message_mode: formData.firstMessageMode,
        temperature: formData.temperature,
        max_tokens: formData.maxTokens,
        voice_provider: formData.voiceProvider,
        voice_id: formData.voiceId,
        voice_speed: formData.voiceSpeed,
        transcriber_provider: formData.transcriberProvider,
        transcriber_model: formData.transcriberModel,
        transcriber_language: formData.transcriberLanguage,
        stop_speaking_plan: {
          enable_interruption: formData.interruptionEnabled,
          interruption_words: formData.interruptionWordsThreshold,
        },
      }));

      router.push("/pipeline-assistants");
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
          <Button variant="ghost" onClick={() => router.push("/pipeline-assistants")}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div className="flex items-center gap-2">
            <Workflow className="h-5 w-5 text-blue-500" />
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
              localStorage.setItem("test_pipeline_assistant", JSON.stringify({
                ...formData,
                id: params.id,
                model_provider: formData.modelProvider,
                model_name: formData.modelName,
                system_prompt: formData.systemPrompt,
                first_message: formData.firstMessage,
                first_message_mode: formData.firstMessageMode,
                voice_provider: formData.voiceProvider,
                voice_id: formData.voiceId,
                transcriber_provider: formData.transcriberProvider,
                transcriber_model: formData.transcriberModel,
                transcriber_language: formData.transcriberLanguage,
                stop_speaking_plan: {
                  enable_interruption: formData.interruptionEnabled,
                  interruption_words: formData.interruptionWordsThreshold,
                },
              }));
              router.push(`/pipeline-call?assistant=${params.id}`);
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
        <Badge variant="outline" className="bg-blue-500/10 text-blue-500 border-blue-500/20">
          <Workflow className="h-3 w-3 mr-1" />
          Pipeline Mode
        </Badge>
        <span className="text-sm text-muted-foreground">VAD → STT → LLM → TTS</span>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="model">
            <Bot className="h-4 w-4 mr-2" />
            Model
          </TabsTrigger>
          <TabsTrigger value="voice">
            <Volume2 className="h-4 w-4 mr-2" />
            Voice (TTS)
          </TabsTrigger>
          <TabsTrigger value="transcriber">
            <Mic className="h-4 w-4 mr-2" />
            Transcriber (STT)
          </TabsTrigger>
          <TabsTrigger value="advanced">
            <Settings className="h-4 w-4 mr-2" />
            Advanced
          </TabsTrigger>
        </TabsList>

        {/* Model Tab */}
        <TabsContent value="model">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>LLM Configuration</CardTitle>
                <CardDescription>Configure the language model</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Provider</label>
                  <Select
                    value={formData.modelProvider}
                    onChange={(v) => {
                      updateFormData("modelProvider", v);
                      updateFormData("modelName", modelsByProvider[v]?.[0]?.value || "");
                    }}
                    options={modelProviders}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Model</label>
                  <Select
                    value={formData.modelName}
                    onChange={(v) => updateFormData("modelName", v)}
                    options={(modelsByProvider[formData.modelProvider] || []).map(m => ({
                      value: m.value,
                      label: m.label,
                    }))}
                  />
                </div>

                <Slider
                  label="Temperature"
                  value={formData.temperature}
                  onChange={(v) => updateFormData("temperature", v)}
                  min={0}
                  max={1}
                  step={0.1}
                />

                <div className="space-y-2">
                  <label className="text-sm font-medium">Max Tokens</label>
                  <Input
                    type="number"
                    value={formData.maxTokens}
                    onChange={(e) => updateFormData("maxTokens", parseInt(e.target.value))}
                  />
                </div>
              </CardContent>
            </Card>

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
        </TabsContent>

        {/* Voice Tab */}
        <TabsContent value="voice">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>TTS Provider</CardTitle>
                <CardDescription>Text-to-Speech configuration</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Provider</label>
                  <Select
                    value={formData.voiceProvider}
                    onChange={(v) => {
                      updateFormData("voiceProvider", v);
                      const voices = voicesByProvider[v] || [];
                      if (voices.length > 0) updateFormData("voiceId", voices[0].value);
                    }}
                    options={voiceProviders}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Voice</label>
                  <Select
                    value={formData.voiceId}
                    onChange={(v) => updateFormData("voiceId", v)}
                    options={(voicesByProvider[formData.voiceProvider] || []).map(v => ({
                      value: v.value,
                      label: v.label,
                    }))}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Custom Voice ID</label>
                  <Input
                    value={formData.voiceId}
                    onChange={(e) => updateFormData("voiceId", e.target.value)}
                    placeholder="Or enter custom voice ID"
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Voice Settings</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Slider
                  label="Speed"
                  value={formData.voiceSpeed}
                  onChange={(v) => updateFormData("voiceSpeed", v)}
                  min={0.5}
                  max={2}
                  step={0.1}
                />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Transcriber Tab */}
        <TabsContent value="transcriber">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>STT Provider</CardTitle>
                <CardDescription>Speech-to-Text configuration</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Provider</label>
                  <Select
                    value={formData.transcriberProvider}
                    onChange={(v) => {
                      updateFormData("transcriberProvider", v);
                      const models = sttModelsByProvider[v] || [];
                      if (models.length > 0) updateFormData("transcriberModel", models[0].value);
                    }}
                    options={transcriberProviders}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Model</label>
                  <Select
                    value={formData.transcriberModel}
                    onChange={(v) => updateFormData("transcriberModel", v)}
                    options={(sttModelsByProvider[formData.transcriberProvider] || []).map(m => ({
                      value: m.value,
                      label: m.label,
                    }))}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Language</label>
                  <Select
                    value={formData.transcriberLanguage}
                    onChange={(v) => updateFormData("transcriberLanguage", v)}
                    options={languages}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Timing</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Endpointing (ms)</label>
                  <Input
                    type="number"
                    value={formData.endpointingMs}
                    onChange={(e) => updateFormData("endpointingMs", parseInt(e.target.value))}
                  />
                  <p className="text-xs text-muted-foreground">
                    Time to wait before considering speech ended
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Advanced Tab */}
        <TabsContent value="advanced">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Call Settings</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Max Duration (seconds)</label>
                  <Input
                    type="number"
                    value={formData.maxDuration}
                    onChange={(e) => updateFormData("maxDuration", parseInt(e.target.value))}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Silence Timeout (seconds)</label>
                  <Input
                    type="number"
                    value={formData.silenceTimeout}
                    onChange={(e) => updateFormData("silenceTimeout", parseInt(e.target.value))}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Interruption (Barge-in)</CardTitle>
                <CardDescription>When assistant stops speaking</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Switch
                  checked={formData.interruptionEnabled}
                  onCheckedChange={(v) => updateFormData("interruptionEnabled", v)}
                  label="Enable Interruption"
                  description="Allow customer to interrupt"
                />

                {formData.interruptionEnabled && (
                  <div className="space-y-3">
                    <label className="text-sm font-medium">Words threshold</label>
                    <div className="flex items-center gap-4">
                      <div className="flex-1">
                        <Slider
                          value={formData.interruptionWordsThreshold}
                          onChange={(v) => updateFormData("interruptionWordsThreshold", v)}
                          min={0}
                          max={10}
                          step={1}
                        />
                      </div>
                      <div className="w-12 h-10 flex items-center justify-center border rounded-md bg-muted text-sm font-medium">
                        {formData.interruptionWordsThreshold}
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {formData.interruptionWordsThreshold === 0
                        ? "Immediate: stops as soon as customer speaks"
                        : `Wait for ${formData.interruptionWordsThreshold} words`
                      }
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
