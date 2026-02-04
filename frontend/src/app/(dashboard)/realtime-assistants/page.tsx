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
  MoreVertical,
  Pencil,
  Trash2,
  Phone,
  Zap,
} from "lucide-react";

interface RealtimeAssistant {
  id: string;
  name: string;
  realtimeProvider: string;
  realtimeModel: string;
  realtimeVoice: string;
  createdAt: string;
  updatedAt: string;
}

const providerInfo: Record<string, { icon: string; label: string; color: string }> = {
  openai: { icon: "🧠", label: "OpenAI Realtime", color: "bg-green-500" },
  google: { icon: "🔮", label: "Gemini Live", color: "bg-blue-500" },
  groq: { icon: "⚡", label: "Groq", color: "bg-orange-500" },
  elevenlabs: { icon: "🎤", label: "ElevenLabs", color: "bg-purple-500" },
};

export default function RealtimeAssistantsPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = React.useState("");
  const [isLoading, setIsLoading] = React.useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [assistantToDelete, setAssistantToDelete] = React.useState<string | null>(null);
  const [assistants, setAssistants] = React.useState<RealtimeAssistant[]>([]);

  // Load realtime assistants from localStorage
  React.useEffect(() => {
    const saved = localStorage.getItem("realtime_assistants");
    if (saved) {
      try {
        const savedAssistants = JSON.parse(saved);
        const assistantList = Object.values(savedAssistants).filter(
          (a): a is RealtimeAssistant => a !== null && typeof a === 'object' && 'id' in a
        );
        setAssistants(assistantList);
      } catch (e) {
        console.error("Failed to load realtime assistants:", e);
      }
    }
  }, []);

  const filteredAssistants = assistants.filter((assistant) =>
    assistant.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleCreateAssistant = () => {
    router.push("/realtime-assistants/new");
  };

  const handleDeleteAssistant = (id: string) => {
    setAssistantToDelete(id);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = () => {
    if (assistantToDelete) {
      const saved = localStorage.getItem("realtime_assistants");
      if (saved) {
        try {
          const savedAssistants = JSON.parse(saved);
          delete savedAssistants[assistantToDelete];
          localStorage.setItem("realtime_assistants", JSON.stringify(savedAssistants));
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
            <Zap className="h-6 w-6 text-yellow-500" />
            Realtime Assistants
          </h1>
          <p className="text-muted-foreground mt-1">
            Direct speech-to-speech APIs with lowest latency (~300ms)
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
          Create Realtime Assistant
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
            <Zap className="h-12 w-12 text-yellow-500/50 mb-4" />
            <h3 className="text-lg font-semibold mb-2">No realtime assistants</h3>
            <p className="text-muted-foreground mb-4">
              {searchQuery
                ? "Try a different search term"
                : "Create your first realtime assistant"}
            </p>
            {!searchQuery && (
              <Button onClick={handleCreateAssistant}>
                <Plus className="h-4 w-4 mr-2" />
                Create Realtime Assistant
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredAssistants.map((assistant) => (
            <Card key={assistant.id} className="group relative">
              <Link href={`/realtime-assistants/${assistant.id}`}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-yellow-500/10">
                        <span className="text-xl">
                          {providerInfo[assistant.realtimeProvider]?.icon || "⚡"}
                        </span>
                      </div>
                      <div>
                        <CardTitle className="text-base">{assistant.name}</CardTitle>
                        <p className="text-sm text-muted-foreground">
                          {assistant.realtimeModel}
                        </p>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2 mb-4 flex-wrap">
                    <Badge variant="outline" className="bg-yellow-500/10 text-yellow-600 border-yellow-500/20">
                      <Zap className="h-3 w-3 mr-1" />
                      Realtime
                    </Badge>
                    {providerInfo[assistant.realtimeProvider] && (
                      <Badge
                        variant="outline"
                        className={`${providerInfo[assistant.realtimeProvider].color} text-white border-0`}
                      >
                        {providerInfo[assistant.realtimeProvider].label}
                      </Badge>
                    )}
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
                      onClick={() => router.push(`/realtime-assistants/${assistant.id}`)}
                    >
                      <Pencil className="h-4 w-4 mr-2" />
                      Edit
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        localStorage.setItem("test_realtime_assistant", JSON.stringify(assistant));
                        router.push(`/realtime-call?assistant=${assistant.id}`);
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
