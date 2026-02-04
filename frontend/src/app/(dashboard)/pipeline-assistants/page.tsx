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
  DollarSign,
  Zap,
  Workflow,
} from "lucide-react";

interface PipelineAssistant {
  id: string;
  name: string;
  modelProvider: string;
  modelName: string;
  voiceProvider: string;
  transcriberProvider: string;
  transcriberLanguage: string;
  createdAt: string;
  updatedAt: string;
}

const providerIcons: Record<string, string> = {
  anthropic: "🤖",
  openai: "🧠",
  google: "🔮",
  azure: "☁️",
  groq: "⚡",
  together: "🔗",
};

const voiceProviderBadges: Record<string, { label: string; color: string }> = {
  elevenlabs: { label: "11Labs", color: "bg-purple-500" },
  azure: { label: "Azure", color: "bg-blue-500" },
  google: { label: "Google", color: "bg-green-500" },
  openai: { label: "OpenAI", color: "bg-gray-500" },
  deepgram: { label: "Deepgram", color: "bg-teal-500" },
  cartesia: { label: "Cartesia", color: "bg-orange-500" },
};

export default function PipelineAssistantsPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = React.useState("");
  const [isLoading, setIsLoading] = React.useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [assistantToDelete, setAssistantToDelete] = React.useState<string | null>(null);
  const [assistants, setAssistants] = React.useState<PipelineAssistant[]>([]);

  // Load pipeline assistants from localStorage on mount
  React.useEffect(() => {
    const saved = localStorage.getItem("pipeline_assistants");
    if (saved) {
      try {
        const savedAssistants = JSON.parse(saved);
        const assistantList = Object.values(savedAssistants).filter(
          (a): a is PipelineAssistant => a !== null && typeof a === 'object' && 'id' in a
        );
        setAssistants(assistantList);
      } catch (e) {
        console.error("Failed to load pipeline assistants:", e);
      }
    }
  }, []);

  const filteredAssistants = assistants.filter((assistant) =>
    assistant.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleCreateAssistant = () => {
    router.push("/pipeline-assistants/new");
  };

  const handleDeleteAssistant = (id: string) => {
    setAssistantToDelete(id);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = () => {
    if (assistantToDelete) {
      const saved = localStorage.getItem("pipeline_assistants");
      if (saved) {
        try {
          const savedAssistants = JSON.parse(saved);
          delete savedAssistants[assistantToDelete];
          localStorage.setItem("pipeline_assistants", JSON.stringify(savedAssistants));
        } catch (e) {
          console.error("Failed to delete assistant:", e);
        }
      }
      setAssistants(prev => prev.filter(a => a.id !== assistantToDelete));
    }
    setDeleteDialogOpen(false);
    setAssistantToDelete(null);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Workflow className="h-6 w-6" />
            Pipeline Assistants
          </h1>
          <p className="text-muted-foreground mt-1">
            VAD → STT → LLM → TTS pipeline with full control
          </p>
        </div>
      </div>

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
          Create Pipeline Assistant
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
            <Workflow className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No pipeline assistants</h3>
            <p className="text-muted-foreground mb-4">
              {searchQuery
                ? "Try a different search term"
                : "Create your first pipeline assistant"}
            </p>
            {!searchQuery && (
              <Button onClick={handleCreateAssistant}>
                <Plus className="h-4 w-4 mr-2" />
                Create Pipeline Assistant
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredAssistants.map((assistant) => (
            <Card key={assistant.id} className="group relative">
              <Link href={`/pipeline-assistants/${assistant.id}`}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                        <span className="text-xl">
                          {providerIcons[assistant.modelProvider] || "🤖"}
                        </span>
                      </div>
                      <div>
                        <CardTitle className="text-base">{assistant.name}</CardTitle>
                        <p className="text-sm text-muted-foreground">
                          {assistant.modelName}
                        </p>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2 mb-4 flex-wrap">
                    <Badge variant="outline" className="bg-blue-500/10 text-blue-500 border-blue-500/20">
                      Pipeline
                    </Badge>
                    {voiceProviderBadges[assistant.voiceProvider] && (
                      <Badge
                        variant="outline"
                        className={`${voiceProviderBadges[assistant.voiceProvider].color} text-white border-0`}
                      >
                        {voiceProviderBadges[assistant.voiceProvider].label}
                      </Badge>
                    )}
                    <Badge variant="outline">{assistant.transcriberLanguage}</Badge>
                  </div>

                  <p className="text-xs text-muted-foreground mt-4">
                    Updated {new Date(assistant.updatedAt).toLocaleDateString()}
                  </p>
                </CardContent>
              </Link>

              {/* Actions Dropdown */}
              <div className="absolute top-4 right-4">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      className="flex h-8 w-8 items-center justify-center rounded-md opacity-0 group-hover:opacity-100 hover:bg-secondary transition-opacity"
                      onClick={(e) => e.preventDefault()}
                    >
                      <MoreVertical className="h-4 w-4" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onClick={() => router.push(`/pipeline-assistants/${assistant.id}`)}
                    >
                      <Pencil className="h-4 w-4 mr-2" />
                      Edit
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        localStorage.setItem("test_pipeline_assistant", JSON.stringify(assistant));
                        router.push(`/pipeline-call?assistant=${assistant.id}`);
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
              Are you sure you want to delete this assistant? This action cannot be undone.
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
