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
import { Spinner } from "@/components/ui/loading";
import {
  ArrowLeft,
  Save,
  Play,
  Phone,
  Bot,
  Mic,
  Wrench,
  BarChart3,
  Settings,
  Shield,
  Code,
  Volume2,
  Maximize2,
} from "lucide-react";

// Provider options
const modelProviders = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "google", label: "Google" },
  { value: "azure", label: "Azure OpenAI" },
  { value: "groq", label: "Groq" },
];

const modelsByProvider: Record<string, { value: string; label: string }[]> = {
  anthropic: [
    { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
    { value: "claude-haiku", label: "Claude Haiku" },
  ],
  openai: [
    { value: "gpt-4o", label: "GPT-4o" },
    { value: "gpt-4o-mini", label: "GPT-4o Mini" },
  ],
  google: [
    { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
    { value: "gemini-pro", label: "Gemini Pro" },
  ],
  azure: [
    { value: "gpt-4", label: "GPT-4" },
    { value: "gpt-35-turbo", label: "GPT-3.5 Turbo" },
  ],
  groq: [
    { value: "llama-3.3-70b", label: "Llama 3.3 70B" },
    { value: "mixtral-8x7b", label: "Mixtral 8x7B" },
  ],
};

const voiceProviders = [
  { value: "elevenlabs", label: "ElevenLabs" },
  { value: "azure", label: "Azure TTS" },
  { value: "google", label: "Google TTS" },
  { value: "openai", label: "OpenAI TTS" },
  { value: "deepgram", label: "Deepgram" },
  { value: "cartesia", label: "Cartesia" },
  { value: "playht", label: "PlayHT" },
];

const transcriberProviders = [
  { value: "deepgram", label: "Deepgram" },
  { value: "azure", label: "Azure Speech" },
  { value: "google", label: "Google Speech" },
  { value: "assemblyai", label: "AssemblyAI" },
  { value: "openai", label: "OpenAI Whisper" },
];

const languages = [
  { value: "ar-SA", label: "Arabic (Saudi)" },
  { value: "ar-EG", label: "Arabic (Egypt)" },
  { value: "ar-AE", label: "Arabic (UAE)" },
  { value: "en-US", label: "English (US)" },
  { value: "en-GB", label: "English (UK)" },
  { value: "fr-FR", label: "French" },
  { value: "de-DE", label: "German" },
  { value: "es-ES", label: "Spanish" },
];

const firstMessageModes = [
  { value: "assistant-speaks-first", label: "Assistant Speaks First" },
  { value: "user-speaks-first", label: "User Speaks First" },
  { value: "assistant-waits", label: "Assistant Waits for Greeting" },
];

export default function AssistantEditorPage() {
  const params = useParams();
  const router = useRouter();
  const isNew = params.id === "new";
  const [activeTab, setActiveTab] = React.useState("model");
  const [isSaving, setIsSaving] = React.useState(false);
  const [isExpandedPrompt, setIsExpandedPrompt] = React.useState(false);

  // Form state
  const [formData, setFormData] = React.useState({
    name: isNew ? "" : "Sales Agent",
    modelProvider: "anthropic",
    modelName: "claude-sonnet-4-20250514",
    temperature: 0.7,
    maxTokens: 1024,
    firstMessageMode: "assistant-speaks-first",
    firstMessage: "مرحبا! كيف يمكنني مساعدتك اليوم؟",
    systemPrompt: `أنت وكيل مبيعات محترف تعمل لصالح شركة متخصصة. مهمتك هي:

1. الترحيب بالعميل بطريقة ودية ومهنية
2. فهم احتياجات العميل بدقة
3. تقديم الحلول المناسبة
4. الإجابة على جميع الاستفسارات
5. المساعدة في إتمام عملية البيع

قواعد مهمة:
- تحدث بالعربية الفصحى السعودية
- كن مختصراً ومفيداً
- لا تقدم وعوداً كاذبة
- احترم خصوصية العميل`,
    voiceProvider: "elevenlabs",
    voiceId: "EXAVITQu4vr4xnSDxMaL",
    voiceSpeed: 1.0,
    voicePitch: 1.0,
    transcriberProvider: "deepgram",
    transcriberLanguage: "ar-SA",
    endpointingMs: 500,
    summaryPrompt: "",
    successEvaluationPrompt: "",
    privacyEnabled: false,
    hipaaEnabled: false,
    voicemailDetection: true,
    maxDuration: 1800,
    silenceTimeout: 30,
  });

  const updateFormData = (field: string, value: unknown) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsSaving(false);
    router.push("/assistants");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => router.push("/assistants")}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <Input
              value={formData.name}
              onChange={(e) => updateFormData("name", e.target.value)}
              placeholder="Assistant Name"
              className="text-xl font-semibold border-0 bg-transparent p-0 h-auto focus:ring-0"
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline">
            <Phone className="h-4 w-4 mr-2" />
            Test Call
          </Button>
          <Button onClick={handleSave} isLoading={isSaving}>
            <Save className="h-4 w-4 mr-2" />
            Save
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full justify-start overflow-x-auto">
          <TabsTrigger value="model">
            <Bot className="h-4 w-4 mr-2" />
            Model
          </TabsTrigger>
          <TabsTrigger value="voice">
            <Volume2 className="h-4 w-4 mr-2" />
            Voice
          </TabsTrigger>
          <TabsTrigger value="transcriber">
            <Mic className="h-4 w-4 mr-2" />
            Transcriber
          </TabsTrigger>
          <TabsTrigger value="tools">
            <Wrench className="h-4 w-4 mr-2" />
            Tools
          </TabsTrigger>
          <TabsTrigger value="analysis">
            <BarChart3 className="h-4 w-4 mr-2" />
            Analysis
          </TabsTrigger>
          <TabsTrigger value="advanced">
            <Settings className="h-4 w-4 mr-2" />
            Advanced
          </TabsTrigger>
          <TabsTrigger value="compliance">
            <Shield className="h-4 w-4 mr-2" />
            Compliance
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
                    options={modelsByProvider[formData.modelProvider] || []}
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
                <CardDescription>How the conversation starts</CardDescription>
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
                  <label className="text-sm font-medium">First Message</label>
                  <Textarea
                    value={formData.firstMessage}
                    onChange={(e) => updateFormData("firstMessage", e.target.value)}
                    placeholder="Enter the assistant's first message..."
                    className="min-h-[100px]"
                  />
                </div>
              </CardContent>
            </Card>

            <Card className="md:col-span-2">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>System Prompt</CardTitle>
                    <CardDescription>Instructions for the assistant</CardDescription>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setIsExpandedPrompt(!isExpandedPrompt)}
                  >
                    <Maximize2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <Textarea
                  value={formData.systemPrompt}
                  onChange={(e) => updateFormData("systemPrompt", e.target.value)}
                  placeholder="Enter the system prompt..."
                  className={isExpandedPrompt ? "min-h-[400px]" : "min-h-[200px]"}
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
                <CardTitle>Voice Provider</CardTitle>
                <CardDescription>Select the TTS provider and voice</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Provider</label>
                  <Select
                    value={formData.voiceProvider}
                    onChange={(v) => updateFormData("voiceProvider", v)}
                    options={voiceProviders}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Voice ID</label>
                  <div className="flex gap-2">
                    <Input
                      value={formData.voiceId}
                      onChange={(e) => updateFormData("voiceId", e.target.value)}
                      placeholder="Enter voice ID or select from library"
                    />
                    <Button variant="outline">
                      <Play className="h-4 w-4" />
                    </Button>
                  </div>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Browse the <a href="/voice-library" className="text-[var(--primary)] hover:underline">Voice Library</a> to find voices
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Voice Settings</CardTitle>
                <CardDescription>Fine-tune voice output</CardDescription>
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

                <Slider
                  label="Pitch"
                  value={formData.voicePitch}
                  onChange={(v) => updateFormData("voicePitch", v)}
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
                <CardTitle>Speech-to-Text</CardTitle>
                <CardDescription>Configure the transcription service</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Provider</label>
                  <Select
                    value={formData.transcriberProvider}
                    onChange={(v) => updateFormData("transcriberProvider", v)}
                    options={transcriberProviders}
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
                <CardTitle>Timing Settings</CardTitle>
                <CardDescription>Configure speech detection</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Endpointing (ms)</label>
                  <Input
                    type="number"
                    value={formData.endpointingMs}
                    onChange={(e) => updateFormData("endpointingMs", parseInt(e.target.value))}
                  />
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Time to wait before considering speech ended
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Tools Tab */}
        <TabsContent value="tools">
          <Card>
            <CardHeader>
              <CardTitle>Tools</CardTitle>
              <CardDescription>Add tools for the assistant to use during calls</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Wrench className="h-12 w-12 text-[var(--muted-foreground)] mb-4" />
                <h3 className="text-lg font-semibold mb-2">No tools added</h3>
                <p className="text-[var(--muted-foreground)] mb-4">
                  Add tools from the library or create custom ones
                </p>
                <Button>
                  Add Tool
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Analysis Tab */}
        <TabsContent value="analysis">
          <div className="grid gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Call Summary</CardTitle>
                <CardDescription>Prompt to generate call summaries</CardDescription>
              </CardHeader>
              <CardContent>
                <Textarea
                  value={formData.summaryPrompt}
                  onChange={(e) => updateFormData("summaryPrompt", e.target.value)}
                  placeholder="Enter a prompt to generate call summaries..."
                  className="min-h-[150px]"
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Success Evaluation</CardTitle>
                <CardDescription>Prompt to evaluate call success</CardDescription>
              </CardHeader>
              <CardContent>
                <Textarea
                  value={formData.successEvaluationPrompt}
                  onChange={(e) => updateFormData("successEvaluationPrompt", e.target.value)}
                  placeholder="Enter a prompt to evaluate if the call was successful..."
                  className="min-h-[150px]"
                />
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

                <Switch
                  checked={formData.voicemailDetection}
                  onCheckedChange={(v) => updateFormData("voicemailDetection", v)}
                  label="Voicemail Detection"
                  description="Detect and handle voicemail greetings"
                />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Compliance Tab */}
        <TabsContent value="compliance">
          <Card>
            <CardHeader>
              <CardTitle>Compliance Settings</CardTitle>
              <CardDescription>Configure privacy and compliance options</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Switch
                checked={formData.privacyEnabled}
                onCheckedChange={(v) => updateFormData("privacyEnabled", v)}
                label="Privacy Mode"
                description="Redact sensitive information from transcripts and logs"
              />

              <Switch
                checked={formData.hipaaEnabled}
                onCheckedChange={(v) => updateFormData("hipaaEnabled", v)}
                label="HIPAA Compliance"
                description="Enable HIPAA-compliant data handling"
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
