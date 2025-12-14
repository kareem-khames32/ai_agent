"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { SkeletonCard } from "@/components/ui/loading";
import {
  Plus,
  Search,
  Bot,
  MoreVertical,
  Pencil,
  Copy,
  Trash2,
  Phone,
  Clock,
  DollarSign,
  Zap,
} from "lucide-react";
import type { Assistant, ModelProvider, VoiceProvider } from "@/types";

// Mock data
const mockAssistants: (Assistant & { costPerMin: number; latencyMs: number })[] = [
  {
    id: "1",
    organizationId: "org1",
    name: "Sales Agent",
    modelProvider: "anthropic",
    modelName: "claude-sonnet-4-20250514",
    systemPrompt: "You are a sales agent...",
    firstMessage: "مرحبا! كيف يمكنني مساعدتك اليوم؟",
    firstMessageMode: "assistant-speaks-first",
    temperature: 0.7,
    maxTokens: 1024,
    voiceProvider: "elevenlabs",
    voiceId: "voice1",
    voiceSettings: {},
    transcriberProvider: "deepgram",
    transcriberLanguage: "ar-SA",
    transcriberSettings: {},
    tools: [],
    summaryPrompt: "",
    successEvaluationPrompt: "",
    structuredDataSchema: {},
    advancedSettings: {},
    createdAt: "2024-01-15T10:00:00Z",
    updatedAt: "2024-01-20T14:30:00Z",
    costPerMin: 0.15,
    latencyMs: 450,
  },
  {
    id: "2",
    organizationId: "org1",
    name: "Support Agent",
    modelProvider: "openai",
    modelName: "gpt-4o",
    systemPrompt: "You are a support agent...",
    firstMessage: "Hello! How can I help you today?",
    firstMessageMode: "assistant-speaks-first",
    temperature: 0.5,
    maxTokens: 2048,
    voiceProvider: "azure",
    voiceId: "voice2",
    voiceSettings: {},
    transcriberProvider: "azure",
    transcriberLanguage: "en-US",
    transcriberSettings: {},
    tools: [],
    summaryPrompt: "",
    successEvaluationPrompt: "",
    structuredDataSchema: {},
    advancedSettings: {},
    createdAt: "2024-01-10T08:00:00Z",
    updatedAt: "2024-01-18T11:00:00Z",
    costPerMin: 0.18,
    latencyMs: 380,
  },
  {
    id: "3",
    organizationId: "org1",
    name: "Collection Agent - Arabic",
    modelProvider: "anthropic",
    modelName: "claude-haiku",
    systemPrompt: "أنت وكيل تحصيل ديون...",
    firstMessage: "السلام عليكم، معك من شركة...",
    firstMessageMode: "assistant-speaks-first",
    temperature: 0.6,
    maxTokens: 1024,
    voiceProvider: "elevenlabs",
    voiceId: "voice3",
    voiceSettings: {},
    transcriberProvider: "deepgram",
    transcriberLanguage: "ar-SA",
    transcriberSettings: {},
    tools: [],
    summaryPrompt: "",
    successEvaluationPrompt: "",
    structuredDataSchema: {},
    advancedSettings: {},
    createdAt: "2024-01-05T09:00:00Z",
    updatedAt: "2024-01-22T16:00:00Z",
    costPerMin: 0.12,
    latencyMs: 520,
  },
];

const providerIcons: Record<ModelProvider, string> = {
  anthropic: "🤖",
  openai: "🧠",
  google: "🔮",
  azure: "☁️",
  groq: "⚡",
  together: "🔗",
};

const voiceProviderBadges: Record<VoiceProvider, { label: string; color: string }> = {
  elevenlabs: { label: "11Labs", color: "bg-purple-500" },
  azure: { label: "Azure", color: "bg-blue-500" },
  google: { label: "Google", color: "bg-green-500" },
  openai: { label: "OpenAI", color: "bg-gray-500" },
  deepgram: { label: "Deepgram", color: "bg-teal-500" },
  cartesia: { label: "Cartesia", color: "bg-orange-500" },
  lmnt: { label: "LMNT", color: "bg-pink-500" },
  rime: { label: "Rime", color: "bg-indigo-500" },
  playht: { label: "PlayHT", color: "bg-yellow-500" },
  neuphonic: { label: "Neuphonic", color: "bg-red-500" },
};

export default function AssistantsPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = React.useState("");
  const [isLoading, setIsLoading] = React.useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [assistantToDelete, setAssistantToDelete] = React.useState<string | null>(null);
  const [assistants, setAssistants] = React.useState<(typeof mockAssistants)>(mockAssistants);

  // Load assistants from localStorage on mount
  React.useEffect(() => {
    const saved = localStorage.getItem("assistants");
    if (saved) {
      try {
        const savedAssistants = JSON.parse(saved);
        const savedList = Object.values(savedAssistants)
          .filter((a): a is Record<string, unknown> => a !== null && typeof a === 'object' && 'id' in a)
          .map((assistant) => {
          return {
            id: assistant.id as string,
            organizationId: "org1",
            name: assistant.name as string || "Unnamed",
            modelProvider: (assistant.modelProvider as string) || "anthropic",
            modelName: (assistant.modelName as string) || "claude-sonnet-4-20250514",
            systemPrompt: (assistant.systemPrompt as string) || "",
            firstMessage: (assistant.firstMessage as string) || "",
            firstMessageMode: (assistant.firstMessageMode as string) || "assistant-speaks-first",
            temperature: (assistant.temperature as number) || 0.7,
            maxTokens: (assistant.maxTokens as number) || 1024,
            voiceProvider: (assistant.voiceProvider as string) || "elevenlabs",
            voiceId: (assistant.voiceId as string) || "",
            voiceSettings: {},
            transcriberProvider: (assistant.transcriberProvider as string) || "deepgram",
            transcriberLanguage: (assistant.transcriberLanguage as string) || "ar-SA",
            transcriberSettings: {},
            tools: [],
            summaryPrompt: "",
            successEvaluationPrompt: "",
            structuredDataSchema: {},
            advancedSettings: {},
            createdAt: (assistant.createdAt as string) || new Date().toISOString(),
            updatedAt: (assistant.updatedAt as string) || new Date().toISOString(),
            costPerMin: 0.15,
            latencyMs: 450,
          };
        });

        // Create a map of saved assistants by ID for quick lookup
        const savedById = new Map(savedList.map((s: { id: string }) => [s.id, s]));

        // Merge: use saved data if available, otherwise use mock data
        const mergedMock = mockAssistants.map(mock => {
          const savedVersion = savedById.get(mock.id);
          if (savedVersion) {
            // Use saved version but keep mock's costPerMin and latencyMs
            return {
              ...savedVersion,
              costPerMin: mock.costPerMin,
              latencyMs: mock.latencyMs,
            };
          }
          return mock;
        });

        // Add any saved assistants that are NOT in mock (user-created)
        const mockIds = mockAssistants.map(m => m.id);
        const userCreated = savedList.filter((s: { id: string }) => !mockIds.includes(s.id));

        setAssistants([...mergedMock, ...userCreated] as typeof mockAssistants);
        console.log("✅ Loaded assistants:", mergedMock.length, "mock/edited +", userCreated.length, "user-created");
      } catch (e) {
        console.error("Failed to load saved assistants:", e);
      }
    }
  }, []);

  const filteredAssistants = assistants.filter((assistant) =>
    assistant.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleCreateAssistant = () => {
    router.push("/assistants/new");
  };

  const handleDeleteAssistant = (id: string) => {
    setAssistantToDelete(id);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = () => {
    if (assistantToDelete) {
      // Delete from localStorage
      const saved = localStorage.getItem("assistants");
      if (saved) {
        try {
          const savedAssistants = JSON.parse(saved);
          delete savedAssistants[assistantToDelete];
          localStorage.setItem("assistants", JSON.stringify(savedAssistants));
        } catch (e) {
          console.error("Failed to delete assistant:", e);
        }
      }
      // Remove from state
      setAssistants(prev => prev.filter(a => a.id !== assistantToDelete));
      console.log("Deleted assistant:", assistantToDelete);
    }
    setDeleteDialogOpen(false);
    setAssistantToDelete(null);
  };

  const handleDuplicate = (assistant: (typeof mockAssistants)[0]) => {
    console.log("Duplicating assistant:", assistant.name);
    // API call to duplicate
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 flex-1">
          <Input
            placeholder="Search assistants..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="max-w-sm"
            leftIcon={<Search className="h-4 w-4" />}
          />
        </div>
        <Button onClick={handleCreateAssistant}>
          <Plus className="h-4 w-4 mr-2" />
          Create Assistant
        </Button>
      </div>

      {/* Assistants Grid */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : filteredAssistants.length === 0 ? (
        <Card className="py-12">
          <CardContent className="flex flex-col items-center justify-center text-center">
            <Bot className="h-12 w-12 text-[var(--muted-foreground)] mb-4" />
            <h3 className="text-lg font-semibold mb-2">No assistants found</h3>
            <p className="text-[var(--muted-foreground)] mb-4">
              {searchQuery
                ? "Try a different search term"
                : "Create your first assistant to get started"}
            </p>
            {!searchQuery && (
              <Button onClick={handleCreateAssistant}>
                <Plus className="h-4 w-4 mr-2" />
                Create Assistant
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredAssistants.map((assistant) => (
            <Card key={assistant.id} className="group relative">
              <Link href={`/assistants/${assistant.id}`}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--primary)]/10">
                        <span className="text-xl">
                          {providerIcons[assistant.modelProvider]}
                        </span>
                      </div>
                      <div>
                        <CardTitle className="text-base">{assistant.name}</CardTitle>
                        <p className="text-sm text-[var(--muted-foreground)]">
                          {assistant.modelName}
                        </p>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {/* Voice Provider Badge */}
                  <div className="flex items-center gap-2 mb-4">
                    <Badge
                      variant="outline"
                      className={`${voiceProviderBadges[assistant.voiceProvider]?.color} text-white border-0`}
                    >
                      {voiceProviderBadges[assistant.voiceProvider]?.label}
                    </Badge>
                    <Badge variant="outline">{assistant.transcriberLanguage}</Badge>
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div className="flex items-center gap-2 text-[var(--muted-foreground)]">
                      <DollarSign className="h-4 w-4" />
                      <span>${assistant.costPerMin}/min</span>
                    </div>
                    <div className="flex items-center gap-2 text-[var(--muted-foreground)]">
                      <Zap className="h-4 w-4" />
                      <span>{assistant.latencyMs}ms</span>
                    </div>
                  </div>

                  {/* Updated date */}
                  <p className="text-xs text-[var(--muted-foreground)] mt-4">
                    Updated {new Date(assistant.updatedAt).toLocaleDateString()}
                  </p>
                </CardContent>
              </Link>

              {/* Actions Dropdown */}
              <div className="absolute top-4 right-4">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      className="flex h-8 w-8 items-center justify-center rounded-md opacity-0 group-hover:opacity-100 hover:bg-[var(--secondary)] transition-opacity"
                      onClick={(e) => e.preventDefault()}
                    >
                      <MoreVertical className="h-4 w-4" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onClick={() => router.push(`/assistants/${assistant.id}`)}
                    >
                      <Pencil className="h-4 w-4 mr-2" />
                      Edit
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleDuplicate(assistant)}>
                      <Copy className="h-4 w-4 mr-2" />
                      Duplicate
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        // Save assistant config for live-call to use
                        localStorage.setItem("test_assistant", JSON.stringify({
                          id: assistant.id,
                          name: assistant.name,
                          modelProvider: assistant.modelProvider,
                          modelName: assistant.modelName,
                          systemPrompt: assistant.systemPrompt,
                          firstMessage: assistant.firstMessage,
                          firstMessageMode: assistant.firstMessageMode,
                          temperature: assistant.temperature,
                          voiceProvider: assistant.voiceProvider,
                          voiceId: assistant.voiceId,
                          transcriberProvider: assistant.transcriberProvider,
                          transcriberLanguage: assistant.transcriberLanguage,
                        }));
                        router.push(`/live-call?assistant=${assistant.id}`);
                      }}
                    >
                      <Phone className="h-4 w-4 mr-2" />
                      Test Call
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      destructive
                      onClick={() => handleDeleteAssistant(assistant.id)}
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent onClose={() => setDeleteDialogOpen(false)}>
          <DialogHeader>
            <DialogTitle>Delete Assistant</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this assistant? This action cannot be
              undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
