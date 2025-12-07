"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import {
  Eye,
  EyeOff,
  Save,
  Check,
  X,
  ExternalLink,
  Brain,
  Mic,
  Volume2,
  Phone,
  Key,
} from "lucide-react";

interface ProviderConfig {
  id: string;
  name: string;
  description: string;
  website: string;
  fields: {
    key: string;
    label: string;
    placeholder: string;
    type?: string;
  }[];
  category: "llm" | "stt" | "tts" | "telephony";
  freeCredit?: string;
}

const providers: ProviderConfig[] = [
  // LLM Providers
  {
    id: "anthropic",
    name: "Anthropic",
    description: "Claude models - Best for Arabic understanding",
    website: "https://console.anthropic.com/settings/keys",
    category: "llm",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "sk-ant-..." },
    ],
  },
  {
    id: "openai",
    name: "OpenAI",
    description: "GPT-4o and GPT-4o-mini models",
    website: "https://platform.openai.com/api-keys",
    category: "llm",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "sk-..." },
    ],
  },
  {
    id: "google",
    name: "Google AI",
    description: "Gemini models",
    website: "https://aistudio.google.com/app/apikey",
    category: "llm",
    freeCredit: "Free tier available",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "AIza..." },
    ],
  },
  {
    id: "groq",
    name: "Groq",
    description: "Ultra-fast Llama & Mixtral (fastest inference)",
    website: "https://console.groq.com/keys",
    category: "llm",
    freeCredit: "Free tier available",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "gsk_..." },
    ],
  },
  {
    id: "together",
    name: "Together AI",
    description: "Cost-effective open source models",
    website: "https://api.together.xyz/settings/api-keys",
    category: "llm",
    freeCredit: "$25 free credit",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "..." },
    ],
  },
  // STT Providers
  {
    id: "deepgram",
    name: "Deepgram",
    description: "Fast & accurate speech-to-text",
    website: "https://console.deepgram.com/",
    category: "stt",
    freeCredit: "$200 free credit",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "..." },
    ],
  },
  {
    id: "azure_speech",
    name: "Azure Speech",
    description: "Best Arabic dialect support",
    website: "https://portal.azure.com/#create/Microsoft.CognitiveServicesSpeechServices",
    category: "stt",
    freeCredit: "5 hours free/month",
    fields: [
      { key: "api_key", label: "Speech Key", placeholder: "..." },
      { key: "region", label: "Region", placeholder: "eastus" },
    ],
  },
  {
    id: "openai_whisper",
    name: "OpenAI Whisper",
    description: "High accuracy multilingual STT",
    website: "https://platform.openai.com/api-keys",
    category: "stt",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "sk-..." },
    ],
  },
  {
    id: "groq_whisper",
    name: "Groq Whisper",
    description: "FASTEST STT - whisper-large-v3-turbo",
    website: "https://console.groq.com/keys",
    category: "stt",
    freeCredit: "Free tier available",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "gsk_..." },
    ],
  },
  {
    id: "munsit",
    name: "Munsit (CNTXT)",
    description: "BEST Arabic STT - 25+ dialects support",
    website: "https://munsit.cntxt.tech/",
    category: "stt",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "..." },
    ],
  },
  // TTS Providers
  {
    id: "elevenlabs",
    name: "ElevenLabs",
    description: "Most natural voices",
    website: "https://elevenlabs.io/app/settings/api-keys",
    category: "tts",
    freeCredit: "10K characters free",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "..." },
    ],
  },
  {
    id: "azure_tts",
    name: "Azure TTS",
    description: "Great Arabic voices (Hamed, Zariyah)",
    website: "https://portal.azure.com/#create/Microsoft.CognitiveServicesSpeechServices",
    category: "tts",
    freeCredit: "500K characters free/month",
    fields: [
      { key: "api_key", label: "Speech Key", placeholder: "..." },
      { key: "region", label: "Region", placeholder: "eastus" },
    ],
  },
  {
    id: "openai_tts",
    name: "OpenAI TTS",
    description: "Simple and fast",
    website: "https://platform.openai.com/api-keys",
    category: "tts",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "sk-..." },
    ],
  },
  {
    id: "deepgram_tts",
    name: "Deepgram Aura",
    description: "FASTEST TTS - great for real-time",
    website: "https://console.deepgram.com/",
    category: "tts",
    freeCredit: "$200 free credit",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "..." },
    ],
  },
  {
    id: "google_tts",
    name: "Google Cloud TTS",
    description: "WaveNet voices - High quality Arabic (ar-XA)",
    website: "https://console.cloud.google.com/apis/credentials",
    category: "tts",
    freeCredit: "$300 free credit (90 days)",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "AIza..." },
    ],
  },
  {
    id: "cartesia",
    name: "Cartesia Sonic",
    description: "Ultra-low latency TTS (90ms) - Custom Voice ID required",
    website: "https://play.cartesia.ai/",
    category: "tts",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "..." },
    ],
  },
  // Telephony
  {
    id: "twilio",
    name: "Twilio",
    description: "Phone calls & SMS",
    website: "https://console.twilio.com/",
    category: "telephony",
    freeCredit: "Free trial available",
    fields: [
      { key: "account_sid", label: "Account SID", placeholder: "AC..." },
      { key: "auth_token", label: "Auth Token", placeholder: "..." },
    ],
  },
];

export default function SettingsPage() {
  const { addToast } = useToast();
  const [activeTab, setActiveTab] = React.useState("llm");
  const [credentials, setCredentials] = React.useState<Record<string, Record<string, string>>>({});
  const [showKeys, setShowKeys] = React.useState<Record<string, boolean>>({});
  const [saving, setSaving] = React.useState<string | null>(null);
  const [configured, setConfigured] = React.useState<Record<string, boolean>>({});

  // Load saved credentials status on mount
  React.useEffect(() => {
    // In real app, fetch from API
    // For now, check localStorage
    const saved = localStorage.getItem("provider_credentials");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setCredentials(parsed);
        // Mark as configured if has values
        const configuredMap: Record<string, boolean> = {};
        Object.keys(parsed).forEach(key => {
          configuredMap[key] = Object.values(parsed[key]).some(v => v && String(v).length > 0);
        });
        setConfigured(configuredMap);
      } catch (e) {
        console.error("Failed to parse saved credentials");
      }
    }
  }, []);

  const handleInputChange = (providerId: string, fieldKey: string, value: string) => {
    setCredentials(prev => ({
      ...prev,
      [providerId]: {
        ...prev[providerId],
        [fieldKey]: value,
      },
    }));
  };

  const handleSave = async (providerId: string) => {
    setSaving(providerId);

    try {
      // Save to localStorage (in real app, send to backend API)
      const allCreds = { ...credentials };
      localStorage.setItem("provider_credentials", JSON.stringify(allCreds));

      // Also send to backend
      const providerCreds = credentials[providerId] || {};
      await fetch("http://localhost:8000/api/settings/credentials", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: providerId,
          ...providerCreds,
        }),
      }).catch(() => {
        // Backend might not be running, that's ok for now
      });

      setConfigured(prev => ({ ...prev, [providerId]: true }));
      addToast({
        type: "success",
        title: "Saved!",
        description: `${providers.find(p => p.id === providerId)?.name} credentials saved`,
      });
    } catch (error) {
      addToast({
        type: "error",
        title: "Error",
        description: "Failed to save credentials",
      });
    } finally {
      setSaving(null);
    }
  };

  const toggleShowKey = (providerId: string) => {
    setShowKeys(prev => ({ ...prev, [providerId]: !prev[providerId] }));
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case "llm": return <Brain className="h-5 w-5" />;
      case "stt": return <Mic className="h-5 w-5" />;
      case "tts": return <Volume2 className="h-5 w-5" />;
      case "telephony": return <Phone className="h-5 w-5" />;
      default: return <Key className="h-5 w-5" />;
    }
  };

  const getCategoryProviders = (category: string) =>
    providers.filter(p => p.category === category);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold">Provider Settings</h2>
        <p className="text-[var(--muted-foreground)]">
          Configure your AI provider API keys to enable voice calls
        </p>
      </div>

      {/* Quick Status */}
      <div className="grid grid-cols-4 gap-4">
        {["llm", "stt", "tts", "telephony"].map((cat) => {
          const catProviders = getCategoryProviders(cat);
          const configuredCount = catProviders.filter(p => configured[p.id]).length;
          return (
            <Card key={cat} className="cursor-pointer hover:bg-[var(--card-hover)]" onClick={() => setActiveTab(cat)}>
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {getCategoryIcon(cat)}
                    <span className="font-medium capitalize">{cat === "llm" ? "LLM" : cat === "stt" ? "STT" : cat === "tts" ? "TTS" : "Telephony"}</span>
                  </div>
                  {configuredCount > 0 ? (
                    <Badge variant="success">{configuredCount} connected</Badge>
                  ) : (
                    <Badge variant="secondary">Not configured</Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Provider Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="llm">
            <Brain className="h-4 w-4 mr-2" />
            LLM
          </TabsTrigger>
          <TabsTrigger value="stt">
            <Mic className="h-4 w-4 mr-2" />
            Speech-to-Text
          </TabsTrigger>
          <TabsTrigger value="tts">
            <Volume2 className="h-4 w-4 mr-2" />
            Text-to-Speech
          </TabsTrigger>
          <TabsTrigger value="telephony">
            <Phone className="h-4 w-4 mr-2" />
            Telephony
          </TabsTrigger>
        </TabsList>

        {["llm", "stt", "tts", "telephony"].map((category) => (
          <TabsContent key={category} value={category}>
            <div className="grid gap-4 md:grid-cols-2">
              {getCategoryProviders(category).map((provider) => (
                <Card key={provider.id}>
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          {provider.name}
                          {configured[provider.id] && (
                            <Check className="h-4 w-4 text-[var(--success)]" />
                          )}
                        </CardTitle>
                        <CardDescription>{provider.description}</CardDescription>
                      </div>
                      {provider.freeCredit && (
                        <Badge variant="success">{provider.freeCredit}</Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {provider.fields.map((field) => (
                      <div key={field.key} className="space-y-2">
                        <label className="text-sm font-medium">{field.label}</label>
                        <div className="flex gap-2">
                          <Input
                            type={showKeys[provider.id] ? "text" : "password"}
                            placeholder={field.placeholder}
                            value={credentials[provider.id]?.[field.key] || ""}
                            onChange={(e) => handleInputChange(provider.id, field.key, e.target.value)}
                          />
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => toggleShowKey(provider.id)}
                          >
                            {showKeys[provider.id] ? (
                              <EyeOff className="h-4 w-4" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </Button>
                        </div>
                      </div>
                    ))}

                    <div className="flex items-center justify-between pt-2">
                      <a
                        href={provider.website}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-[var(--primary)] hover:underline flex items-center gap-1"
                      >
                        Get API Key <ExternalLink className="h-3 w-3" />
                      </a>
                      <Button
                        onClick={() => handleSave(provider.id)}
                        isLoading={saving === provider.id}
                      >
                        <Save className="h-4 w-4 mr-2" />
                        Save
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
