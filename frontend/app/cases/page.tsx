"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, API_BASE } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

interface CaseMetadata {
  id: string;
  title: string;
  description: string;
  year: number;
  difficulty: "beginner" | "intermediate" | "advanced";
  case_type: string;
  witness_count?: number;
  exhibit_count?: number;
  featured?: boolean;
  popularity?: number;
  source?: string;
  source_url?: string;
  requires_upload?: boolean;
  has_uploads?: boolean;
  sections_uploaded?: number;
  is_favorite?: boolean;
  is_uploaded?: boolean;
}

interface UploadedCase {
  case_id: string;
  name: string;
  source_type: string;
  source_filename: string;
  processed: boolean;
  fact_count: number;
  witness_count: number;
  exhibit_count: number;
}

const ScalesIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 3v18M3 7l9-4 9 4M3 7v4c0 1.5 2 3 4 3s4-1.5 4-3V7M14 7v4c0 1.5 2 3 4 3s4-1.5 4-3V7" />
  </svg>
);

const GavelIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M14 3L20 9M8 14L3 19M10 12L14.5 7.5M12 14L7.5 18.5M21 21H3" />
  </svg>
);

const UploadIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
  </svg>
);

const BackIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M19 12H5M12 19l-7-7 7-7" />
  </svg>
);

const ExternalLinkIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" />
  </svg>
);

const FolderIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
  </svg>
);

const StarIcon = ({ className = "", filled = false }: { className?: string; filled?: boolean }) => (
  <svg className={className} viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2">
    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
  </svg>
);

const TrashIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2M10 11v6M14 11v6" />
  </svg>
);

const PlayIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polygon points="5 3 19 12 5 21 5 3" />
  </svg>
);

const CheckIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

export default function CasesPage() {
  const router = useRouter();
  const [userInitial, setUserInitial] = useState("U");
  const [allCases, setAllCases] = useState<CaseMetadata[]>([]);
  const [uploadedCases, setUploadedCases] = useState<UploadedCase[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "criminal" | "civil">("all");
  const [difficulty, setDifficulty] = useState<"all" | "beginner" | "intermediate" | "advanced">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState("");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [selectedCaseForUpload, setSelectedCaseForUpload] = useState<CaseMetadata | null>(null);
  const [uploadSection, setUploadSection] = useState<string>("summary");
  const [newCaseName, setNewCaseName] = useState<string>("");
  const [uploadSuccess, setUploadSuccess] = useState<{ caseId: string; title: string } | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null);
  const [showRoleSelect, setShowRoleSelect] = useState<{ caseId: string; caseItem?: CaseMetadata } | null>(null);
  const [selectedMode, setSelectedMode] = useState<"participate" | "spectator">("participate");
  const [selectedSide, setSelectedSide] = useState<"prosecution" | "defense">("prosecution");
  const [selectedSubRole, setSelectedSubRole] = useState<"opening" | "direct_cross" | "closing">("direct_cross");
  const [isStartingTrial, setIsStartingTrial] = useState(false);
  const [viewingFilesFor, setViewingFilesFor] = useState<CaseMetadata | null>(null);
  const [caseFiles, setCaseFiles] = useState<Array<{ name: string; section: string; size: number; url?: string }>>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);

  useEffect(() => {
    createClient().auth.getUser().then(({ data }) => {
      if (data.user?.email) setUserInitial(data.user.email[0].toUpperCase());
    });
  }, []);

  const handleViewFiles = async (caseItem: CaseMetadata) => {
    setViewingFilesFor(caseItem);
    setLoadingFiles(true);
    setCaseFiles([]);
    try {
      const res = await apiFetch(`${API_BASE}/api/case/${caseItem.id}/storage/files`);
      if (res.ok) {
        const data = await res.json();
        const files = data.files || [];
        const filesWithUrls = await Promise.all(
          files.map(async (f: { name: string; section: string; size: number }) => {
            try {
              const urlRes = await apiFetch(
                `${API_BASE}/api/case/${caseItem.id}/storage/files/${f.section}/${f.name}/url`
              );
              if (urlRes.ok) {
                const urlData = await urlRes.json();
                return { ...f, url: urlData.url };
              }
            } catch { /* skip */ }
            return f;
          })
        );
        setCaseFiles(filesWithUrls);
      }
    } catch (err) {
      console.error("Failed to load files:", err);
    } finally {
      setLoadingFiles(false);
    }
  };

  const loadCases = useCallback(async () => {
    setIsLoading(true);
    try {
      const [demoRes, uploadedRes] = await Promise.all([
        apiFetch(`${API_BASE}/api/case/demo`),
        apiFetch(`${API_BASE}/api/case/?include_demo=false`),
      ]);

      if (demoRes.ok) {
        const demoCases = await demoRes.json();
        setAllCases(demoCases || []);
      }

      if (uploadedRes.ok) {
        const uploaded = await uploadedRes.json();
        setUploadedCases(uploaded || []);
      }
    } catch (err) {
      console.error("Failed to load cases:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCases();
  }, [loadCases]);

  const handleUpload = async (file: File) => {
    setIsUploading(true);
    setUploadError(null);
    setUploadProgress("Uploading file...");

    const formData = new FormData();
    formData.append("file", file);

    try {
      let uploadedCaseId = "";
      let uploadedTitle = "";

      if (uploadSection !== "summary" || newCaseName) {
        const caseId = newCaseName 
          ? `custom_${newCaseName.toLowerCase().replace(/[^a-z0-9]+/g, '_').substring(0, 30)}_${Date.now()}`
          : `custom_${file.name.replace(/\.[^/.]+$/, '').toLowerCase().replace(/[^a-z0-9]+/g, '_').substring(0, 30)}_${Date.now()}`;
        
        if (newCaseName) {
          formData.append("title", newCaseName);
        }

        setUploadProgress("Parsing PDF with AI — this may take up to a minute...");
        const response = await apiFetch(`${API_BASE}/api/case/${caseId}/sections/${uploadSection}`, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || "Upload failed");
        }

        uploadedCaseId = caseId;
        uploadedTitle = newCaseName || file.name.replace(/\.[^/.]+$/, '');
      } else {
        const endpoint = file.name.endsWith(".json")
          ? `${API_BASE}/api/case/upload/json`
          : `${API_BASE}/api/case/upload/pdf`;

        setUploadProgress("Parsing PDF with AI — this may take up to a minute...");
        const response = await apiFetch(endpoint, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || "Upload failed");
        }

        const data = await response.json();
        uploadedCaseId = data.case_id;
        uploadedTitle = data.name || file.name.replace(/\.[^/.]+$/, '');
      }

      setUploadProgress("Finalizing...");
      await loadCases();
      
      setUploadSuccess({ caseId: uploadedCaseId, title: uploadedTitle });
      setNewCaseName("");
      setUploadSection("summary");
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
      setUploadProgress("");
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleUpload(file);
    }
  };

  const handleStartCase = async (caseId: string, caseItem?: CaseMetadata) => {
    if (caseItem?.requires_upload) {
      setSelectedCaseForUpload(caseItem);
      setShowUploadModal(true);
      return;
    }

    setShowRoleSelect({ caseId, caseItem });
  };

  const handleConfirmRole = async () => {
    if (!showRoleSelect) return;
    setIsStartingTrial(true);
    const { caseId } = showRoleSelect;
    const humanRole = selectedMode === "spectator"
      ? "spectator"
      : selectedSide === "prosecution" ? "attorney_plaintiff" : "attorney_defense";

    try {
      const response = await apiFetch(`${API_BASE}/api/session/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: caseId,
          human_role: humanRole,
          ...(selectedMode !== "spectator" && { attorney_sub_role: selectedSubRole }),
        }),
      });

      if (!response.ok) throw new Error("Failed to create session");

      const data = await response.json();
      const sessionId = data.session_id;

      await apiFetch(`${API_BASE}/api/session/${sessionId}/initialize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      setShowRoleSelect(null);
      router.push(`/courtroom/${sessionId}`);
    } catch (err) {
      console.error("Failed to start case:", err);
    } finally {
      setIsStartingTrial(false);
    }
  };

  const handleToggleFavorite = async (caseId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const response = await apiFetch(`${API_BASE}/api/case/${caseId}/favorite`, {
        method: "POST",
      });
      if (response.ok) {
        // Update local state
        setAllCases((prev) =>
          prev.map((c) => (c.id === caseId ? { ...c, is_favorite: !c.is_favorite } : c))
        );
      }
    } catch (err) {
      console.error("Failed to toggle favorite:", err);
    }
  };

  const handleDeleteCase = async (caseId: string) => {
    try {
      await apiFetch(`${API_BASE}/api/case/${caseId}/materials`, { method: "DELETE" }).catch(() => {});
      const res = await apiFetch(`${API_BASE}/api/case/${caseId}`, { method: "DELETE" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setUploadError(data.detail || "Failed to delete case. Please try again.");
      }
      await loadCases();
      setShowDeleteConfirm(null);
    } catch (err) {
      console.error("Failed to delete case:", err);
      setUploadError("Failed to delete case. Please try again.");
      setShowDeleteConfirm(null);
    }
  };

  const handleSectionUpload = async (file: File, caseId: string, section: string) => {
    setIsUploading(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await apiFetch(`${API_BASE}/api/case/${caseId}/sections/${section}`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Upload failed");
      }

      await loadCases();
      // Keep modal open to allow more section uploads
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  const handleSectionFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && selectedCaseForUpload) {
      handleSectionUpload(file, selectedCaseForUpload.id, uploadSection);
    }
  };

  const filteredCases = allCases.filter((c) => {
    const matchesFilter = filter === "all" || c.case_type === filter;
    const matchesDifficulty = difficulty === "all" || c.difficulty === difficulty;
    const matchesSearch =
      searchQuery === "" ||
      c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesDifficulty && matchesSearch;
  });

  const difficultyColors = {
    beginner: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    intermediate: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    advanced: "bg-rose-500/20 text-rose-400 border-rose-500/30",
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-800 to-indigo-950">
      {/* Header */}
      <header className="border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-0">
          <div className="flex items-center justify-between h-16">
            <button onClick={() => router.push("/")} className="flex items-center gap-2.5 text-white hover:opacity-90 transition-opacity">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
                <ScalesIcon className="w-5 h-5" />
              </div>
              <div className="flex flex-col leading-tight">
                <span className="text-base font-bold tracking-tight">MockPrep<span className="text-amber-400">AI</span></span>
              </div>
            </button>
            <nav className="hidden md:flex items-center gap-1">
              <button onClick={() => router.push("/")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Dashboard</button>
              <button className="px-4 py-2 text-sm font-medium text-white bg-slate-800/60 rounded-lg transition-colors">Case Library</button>
              <button onClick={() => router.push("/about")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Who We Are</button>
              <button onClick={() => router.push("/contact")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Contact</button>
            </nav>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowUploadModal(true)}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors text-sm font-medium"
              >
                <UploadIcon className="w-4 h-4" />
                <span className="hidden sm:inline">Upload Case</span>
              </button>
              <button onClick={() => router.push("/profile")} className="hidden sm:flex items-center justify-center w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white text-xs font-bold hover:opacity-80 transition-opacity" title="Profile">{userInitial}</button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Filters */}
        <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4 mb-8">
          <div className="flex flex-wrap items-center gap-4">
            {/* Search */}
            <div className="flex-1 min-w-[200px]">
              <input
                type="text"
                placeholder="Search cases..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full px-4 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* Case Type Filter */}
            <div className="flex items-center gap-2">
              <span className="text-slate-400 text-sm">Type:</span>
              <div className="flex gap-1">
                {(["all", "criminal", "civil"] as const).map((type) => (
                  <button
                    key={type}
                    onClick={() => setFilter(type)}
                    className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                      filter === type
                        ? "bg-indigo-600 text-white"
                        : "bg-slate-700/50 text-slate-400 hover:text-white"
                    }`}
                  >
                    {type === "all" ? "All" : type.charAt(0).toUpperCase() + type.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            {/* Difficulty Filter */}
            <div className="flex items-center gap-2">
              <span className="text-slate-400 text-sm">Level:</span>
              <div className="flex gap-1">
                {(["all", "beginner", "intermediate", "advanced"] as const).map((level) => (
                  <button
                    key={level}
                    onClick={() => setDifficulty(level)}
                    className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                      difficulty === level
                        ? "bg-indigo-600 text-white"
                        : "bg-slate-700/50 text-slate-400 hover:text-white"
                    }`}
                  >
                    {level === "all" ? "All" : level.charAt(0).toUpperCase() + level.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            {/* Favorites Filter */}
            <button
              onClick={() => setFilter(filter === "all" ? "all" : "all")}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                allCases.some((c) => c.is_favorite)
                  ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                  : "bg-slate-700/50 text-slate-400"
              }`}
            >
              <StarIcon className="w-4 h-4" filled={allCases.some((c) => c.is_favorite)} />
              {allCases.filter((c) => c.is_favorite).length} Favorites
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 mb-8">
          <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4 text-center">
            <div className="text-3xl font-bold text-white">{allCases.length}</div>
            <div className="text-slate-400 text-sm">Practice Cases</div>
          </div>
          <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4 text-center">
            <div className="text-3xl font-bold text-red-400">{allCases.filter((c) => c.case_type === "criminal").length}</div>
            <div className="text-slate-400 text-sm">Criminal</div>
          </div>
          <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4 text-center">
            <div className="text-3xl font-bold text-blue-400">{allCases.filter((c) => c.case_type === "civil").length}</div>
            <div className="text-slate-400 text-sm">Civil</div>
          </div>
          <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4 text-center">
            <div className="text-3xl font-bold text-purple-400">{allCases.filter((c) => c.is_uploaded).length}</div>
            <div className="text-slate-400 text-sm">Your Uploads</div>
          </div>
          <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4 text-center">
            <div className="text-3xl font-bold text-amber-400">{allCases.filter((c) => c.is_favorite).length}</div>
            <div className="text-slate-400 text-sm">Favorites</div>
          </div>
        </div>

        {/* Case Grid */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filteredCases.length > 0 ? (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredCases.map((caseItem) => (
              <div
                key={caseItem.id}
                className="group bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden hover:border-indigo-500/50 transition-all"
              >
                {/* Case Header */}
                <div
                  className={`p-4 ${
                    caseItem.case_type === "criminal"
                      ? "bg-gradient-to-r from-red-900/30 to-transparent"
                      : "bg-gradient-to-r from-blue-900/30 to-transparent"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                          caseItem.case_type === "criminal" ? "bg-red-500/20" : "bg-blue-500/20"
                        }`}
                      >
                        {caseItem.case_type === "criminal" ? (
                          <GavelIcon className="w-5 h-5 text-red-400" />
                        ) : (
                          <ScalesIcon className="w-5 h-5 text-blue-400" />
                        )}
                      </div>
                      <div>
                        <h3 className="font-semibold text-white group-hover:text-indigo-300 transition-colors text-sm">
                          {caseItem.title}
                        </h3>
                        <span
                          className={`px-2 py-0.5 text-xs rounded border ${
                            caseItem.case_type === "criminal"
                              ? "bg-red-500/20 text-red-300 border-red-500/30"
                              : "bg-blue-500/20 text-blue-300 border-blue-500/30"
                          }`}
                        >
                          {caseItem.case_type}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      {/* Favorite Button */}
                      <button
                        onClick={(e) => handleToggleFavorite(caseItem.id, e)}
                        className={`p-1.5 rounded-lg transition-colors ${
                          caseItem.is_favorite
                            ? "text-amber-400 bg-amber-500/20"
                            : "text-slate-500 hover:text-amber-400 hover:bg-slate-700"
                        }`}
                        title={caseItem.is_favorite ? "Remove from favorites" : "Add to favorites"}
                      >
                        <StarIcon className="w-4 h-4" filled={caseItem.is_favorite} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setShowDeleteConfirm(caseItem.id);
                        }}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-slate-700 transition-colors"
                        title="Delete case"
                      >
                        <TrashIcon className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Case Body */}
                <div className="p-4">
                  <p className="text-slate-400 text-sm line-clamp-3 mb-4">{caseItem.description}</p>

                  <div className="flex flex-wrap gap-2 mb-4">
                    <span className={`px-2 py-1 text-xs rounded border ${difficultyColors[caseItem.difficulty]}`}>
                      {caseItem.difficulty}
                    </span>
                    <span className="px-2 py-1 bg-slate-700/50 text-slate-400 text-xs rounded">
                      {caseItem.witness_count || 0} witnesses
                    </span>
                    <span className="px-2 py-1 bg-slate-700/50 text-slate-400 text-xs rounded">
                      {caseItem.exhibit_count || 0} exhibits
                    </span>
                    <span className="px-2 py-1 bg-slate-700/50 text-slate-400 text-xs rounded">{caseItem.year}</span>
                  </div>

                  {caseItem.has_uploads ? (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <CheckIcon className="w-3.5 h-3.5 text-emerald-400" />
                          <span className="text-xs text-emerald-400 font-medium">
                            {caseItem.sections_uploaded || 0} section{(caseItem.sections_uploaded || 0) !== 1 ? "s" : ""} uploaded
                          </span>
                        </div>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleViewFiles(caseItem); }}
                          className="text-xs text-amber-400 hover:text-amber-300 font-medium"
                        >
                          View Files
                        </button>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleStartCase(caseItem.id)}
                          className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors font-medium flex items-center justify-center gap-1 text-sm"
                        >
                          <PlayIcon className="w-4 h-4" />
                          Practice
                        </button>
                        <button
                          onClick={() => handleStartCase(caseItem.id, { ...caseItem, requires_upload: true })}
                          className="flex-1 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors font-medium flex items-center justify-center gap-1 text-sm"
                        >
                          <UploadIcon className="w-4 h-4" />
                          Add More
                        </button>
                      </div>
                    </div>
                  ) : caseItem.requires_upload ? (
                    <div className="space-y-2">
                      <p className="text-xs text-slate-500 mb-1">
                        Download PDF from MYLaw, then upload here:
                      </p>
                      <div className="flex gap-2">
                        {caseItem.source_url && (
                          <a
                            href={caseItem.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex-1 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors font-medium flex items-center justify-center gap-1 text-sm"
                          >
                            <ExternalLinkIcon className="w-4 h-4" />
                            1. Get PDF
                          </a>
                        )}
                        <button
                          onClick={() => handleStartCase(caseItem.id, caseItem)}
                          className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors font-medium flex items-center justify-center gap-1 text-sm"
                        >
                          <UploadIcon className="w-4 h-4" />
                          2. Upload
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => handleStartCase(caseItem.id)}
                      className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors font-medium"
                    >
                      Start Practice
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-20">
            <ScalesIcon className="w-16 h-16 mx-auto text-slate-600 mb-4" />
            <h3 className="text-xl font-semibold text-slate-300 mb-2">No cases found</h3>
            <p className="text-slate-500">Try adjusting your filters or search query</p>
          </div>
        )}

        {/* Uploaded Cases Section */}
        {uploadedCases.length > 0 && (
          <div className="mt-12">
            <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
              <UploadIcon className="w-5 h-5 text-indigo-400" />
              Your Uploaded Cases
            </h2>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {uploadedCases.map((uploaded) => (
                <div
                  key={uploaded.case_id}
                  className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4 hover:border-indigo-500/50 transition-all"
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <h3 className="font-semibold text-white">{uploaded.name}</h3>
                    <button
                      onClick={() => setShowDeleteConfirm(uploaded.case_id)}
                      className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-slate-700 transition-colors shrink-0"
                      title="Delete case"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </div>
                  <p className="text-slate-500 text-sm mb-3">From: {uploaded.source_filename}</p>
                  <div className="flex flex-wrap gap-2 mb-4">
                    <span
                      className={`px-2 py-1 text-xs rounded ${
                        uploaded.processed ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400"
                      }`}
                    >
                      {uploaded.processed ? "Ready" : "Processing..."}
                    </span>
                    <span className="px-2 py-1 bg-slate-700/50 text-slate-400 text-xs rounded">
                      {uploaded.witness_count} witnesses
                    </span>
                  </div>
                  <button
                    onClick={() => handleStartCase(uploaded.case_id)}
                    disabled={!uploaded.processed}
                    className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-lg transition-colors"
                  >
                    {uploaded.processed ? "Start Practice" : "Processing..."}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* Role Selection Modal */}
      {showRoleSelect && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-2xl border border-slate-700 max-w-lg w-full p-6 shadow-2xl">
            <h3 className="text-xl font-bold text-white mb-1">Choose Your Role</h3>
            <p className="text-slate-400 text-sm mb-5">Select how you want to experience the trial.</p>

            {/* Mode selection: Participate vs Spectator */}
            <div className="mb-5">
              <label className="text-sm font-medium text-slate-300 mb-2 block">Mode</label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => setSelectedMode("participate")}
                  className={`p-3 rounded-xl border-2 transition-all text-center ${
                    selectedMode === "participate"
                      ? "border-emerald-500 bg-emerald-500/10 text-emerald-300"
                      : "border-slate-600 bg-slate-700/50 text-slate-300 hover:border-slate-500"
                  }`}
                >
                  <div className="text-2xl mb-1">&#9878;</div>
                  <div className="font-semibold text-sm">Participate</div>
                  <div className="text-xs text-slate-400 mt-0.5">Play as an attorney</div>
                </button>
                <button
                  onClick={() => setSelectedMode("spectator")}
                  className={`p-3 rounded-xl border-2 transition-all text-center ${
                    selectedMode === "spectator"
                      ? "border-amber-500 bg-amber-500/10 text-amber-300"
                      : "border-slate-600 bg-slate-700/50 text-slate-300 hover:border-slate-500"
                  }`}
                >
                  <div className="text-2xl mb-1">&#128065;</div>
                  <div className="font-semibold text-sm">Spectator</div>
                  <div className="text-xs text-slate-400 mt-0.5">Watch AI vs AI trial</div>
                </button>
              </div>
            </div>

            {selectedMode === "participate" && (
              <>
                <div className="mb-5">
                  <label className="text-sm font-medium text-slate-300 mb-2 block">Side</label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      onClick={() => setSelectedSide("prosecution")}
                      className={`p-3 rounded-xl border-2 transition-all text-center ${
                        selectedSide === "prosecution"
                          ? "border-red-500 bg-red-500/10 text-red-300"
                          : "border-slate-600 bg-slate-700/50 text-slate-300 hover:border-slate-500"
                      }`}
                    >
                      <div className="text-2xl mb-1">&#9878;</div>
                      <div className="font-semibold text-sm">Prosecution</div>
                      <div className="text-xs text-slate-400 mt-0.5">Plaintiff&apos;s side</div>
                    </button>
                    <button
                      onClick={() => setSelectedSide("defense")}
                      className={`p-3 rounded-xl border-2 transition-all text-center ${
                        selectedSide === "defense"
                          ? "border-blue-500 bg-blue-500/10 text-blue-300"
                          : "border-slate-600 bg-slate-700/50 text-slate-300 hover:border-slate-500"
                      }`}
                    >
                      <div className="text-2xl mb-1">&#128737;</div>
                      <div className="font-semibold text-sm">Defense</div>
                      <div className="text-xs text-slate-400 mt-0.5">Defendant&apos;s side</div>
                    </button>
                  </div>
                </div>

                <div className="mb-6">
                  <label className="text-sm font-medium text-slate-300 mb-2 block">Attorney Role</label>
                  <div className="space-y-2">
                    {[
                      {
                        value: "opening" as const,
                        label: "Opening Attorney",
                        desc: "Delivers the opening statement.",
                      },
                      {
                        value: "direct_cross" as const,
                        label: "Direct & Cross-Examination Attorney",
                        desc: "Conducts examinations and makes objections.",
                      },
                      {
                        value: "closing" as const,
                        label: "Closing Attorney",
                        desc: "Delivers the closing argument.",
                      },
                    ].map((role) => (
                      <button
                        key={role.value}
                        onClick={() => setSelectedSubRole(role.value)}
                        className={`w-full text-left p-3 rounded-xl border-2 transition-all ${
                          selectedSubRole === role.value
                            ? "border-emerald-500 bg-emerald-500/10"
                            : "border-slate-600 bg-slate-700/50 hover:border-slate-500"
                        }`}
                      >
                        <div className={`font-semibold text-sm ${selectedSubRole === role.value ? "text-emerald-300" : "text-slate-200"}`}>
                          {role.label}
                        </div>
                        <div className="text-xs text-slate-400 mt-0.5">{role.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="bg-slate-700/50 rounded-lg p-3 mb-5 text-xs text-slate-400">
                  <span className="text-slate-300 font-medium">Your AI teammates</span> will handle the other attorney roles on your side.
                  The opposing team is fully AI-controlled.
                </div>
              </>
            )}

            {selectedMode === "spectator" && (
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4 mb-5">
                <div className="text-sm text-amber-300 font-medium mb-1">Spectator Mode</div>
                <div className="text-xs text-slate-400">
                  All roles will be handled by AI agents. You will watch the entire trial proceeding
                  without participating -- both prosecution and defense teams are fully AI-controlled.
                </div>
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={() => setShowRoleSelect(null)}
                disabled={isStartingTrial}
                className="flex-1 py-2.5 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white rounded-lg transition-colors font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmRole}
                disabled={isStartingTrial}
                className="flex-1 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white rounded-lg transition-colors font-medium flex items-center justify-center gap-2"
              >
                {isStartingTrial ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Setting up trial...
                  </>
                ) : (
                  "Start Trial"
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* View Files Modal */}
      {viewingFilesFor && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-2xl border border-slate-700 max-w-2xl w-full max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between p-6 border-b border-slate-700">
              <div>
                <h2 className="text-lg font-bold text-white">Uploaded Files</h2>
                <p className="text-sm text-slate-400">{viewingFilesFor.title}</p>
              </div>
              <button
                onClick={() => setViewingFilesFor(null)}
                className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg"
              >
                <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-6">
              {loadingFiles ? (
                <div className="flex flex-col items-center justify-center py-12">
                  <div className="w-10 h-10 border-4 border-amber-500/30 border-t-amber-500 rounded-full animate-spin mb-3" />
                  <p className="text-slate-400 text-sm">Loading files...</p>
                </div>
              ) : caseFiles.length === 0 ? (
                <div className="text-center py-12 text-slate-400">
                  <p>No files found in storage.</p>
                </div>
              ) : (() => {
                const sectionLabels: Record<string, string> = {
                  summary: "Case Summary", witnesses_plaintiff: "Plaintiff Witnesses",
                  witnesses_defense: "Defense Witnesses", exhibits: "Exhibits",
                  stipulations: "Stipulations", jury_instructions: "Jury Instructions",
                  rules: "Rules & Procedures",
                };
                const grouped: Record<string, typeof caseFiles> = {};
                for (const f of caseFiles) {
                  const sec = f.section || "other";
                  if (!grouped[sec]) grouped[sec] = [];
                  grouped[sec].push(f);
                }
                const formatSize = (bytes: number) => {
                  if (!bytes) return "";
                  if (bytes < 1024) return `${bytes} B`;
                  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
                  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
                };
                return (
                  <div className="space-y-4">
                    <p className="text-sm text-slate-400">{caseFiles.length} file{caseFiles.length !== 1 ? "s" : ""} uploaded</p>
                    {Object.entries(grouped).map(([section, files]) => (
                      <div key={section}>
                        <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                          {sectionLabels[section] || section}
                        </h4>
                        <div className="space-y-2">
                          {files.map((file) => (
                            <div key={file.name} className="flex items-center gap-3 bg-slate-700/30 rounded-lg p-3 border border-slate-700/50">
                              <div className="w-10 h-10 rounded-lg bg-slate-600/50 flex items-center justify-center shrink-0">
                                <svg viewBox="0 0 24 24" className={`w-5 h-5 ${file.name.endsWith('.pdf') ? 'text-red-400' : 'text-slate-400'}`} fill="none" stroke="currentColor" strokeWidth="2">
                                  <path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z" />
                                  <polyline points="13 2 13 9 20 9" />
                                </svg>
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-white truncate">{file.name}</p>
                                <p className="text-xs text-slate-500">{formatSize(file.size)}</p>
                              </div>
                              {file.url ? (
                                <a
                                  href={file.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="px-3 py-1.5 text-xs bg-amber-600 hover:bg-amber-500 text-white rounded-lg transition-colors font-medium"
                                >
                                  Open
                                </a>
                              ) : (
                                <span className="text-xs text-slate-500">No URL</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                );
              })()}
            </div>
            <div className="p-4 border-t border-slate-700 flex justify-end">
              <button
                onClick={() => setViewingFilesFor(null)}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-2xl border border-slate-700 p-6 max-w-md w-full">
            <h2 className="text-xl font-bold text-white mb-4">Delete Case?</h2>
            <p className="text-slate-400 mb-6">
              This will permanently delete the case, its uploaded materials, and all associated data. This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowDeleteConfirm(null)}
                className="flex-1 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDeleteCase(showDeleteConfirm)}
                className="flex-1 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                <TrashIcon className="w-4 h-4" />
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-2xl border border-slate-700 p-6 max-w-lg w-full max-h-[90vh] overflow-y-auto">
            {/* Upload Success State */}
            {uploadSuccess ? (
              <>
                <div className="text-center mb-6">
                  <div className="w-16 h-16 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                    <CheckIcon className="w-8 h-8 text-emerald-400" />
                  </div>
                  <h2 className="text-xl font-bold text-white mb-2">Case Uploaded Successfully!</h2>
                  <p className="text-slate-400">{uploadSuccess.title}</p>
                </div>

                <div className="space-y-3">
                  <button
                    onClick={() => {
                      handleStartCase(uploadSuccess.caseId);
                      setUploadSuccess(null);
                      setShowUploadModal(false);
                    }}
                    className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors font-medium flex items-center justify-center gap-2"
                  >
                    <PlayIcon className="w-5 h-5" />
                    Start Practicing Now
                  </button>
                  <button
                    onClick={() => {
                      handleToggleFavorite(uploadSuccess.caseId, { stopPropagation: () => {} } as React.MouseEvent);
                    }}
                    className="w-full py-2 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/30 rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    <StarIcon className="w-4 h-4" />
                    Add to Favorites
                  </button>
                  <button
                    onClick={() => {
                      setUploadSuccess(null);
                      setShowUploadModal(false);
                    }}
                    className="w-full py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                  >
                    Back to Case Library
                  </button>
                </div>
              </>
            ) : selectedCaseForUpload ? (
              <>
                <h2 className="text-xl font-bold text-white mb-2">Import Case: {selectedCaseForUpload.title}</h2>
                <p className="text-slate-400 text-sm mb-4">{selectedCaseForUpload.year} • {selectedCaseForUpload.case_type}</p>
                
                {/* Step-by-step Instructions */}
                <div className="bg-slate-700/50 rounded-lg p-4 mb-4">
                  <h4 className="text-white font-medium mb-3">How to Import This Case:</h4>
                  <ol className="text-slate-300 text-sm space-y-2">
                    <li className="flex gap-2">
                      <span className="bg-indigo-600 text-white w-5 h-5 rounded-full flex items-center justify-center text-xs flex-shrink-0">1</span>
                      <span>
                        <a
                          href={selectedCaseForUpload.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-indigo-400 hover:text-indigo-300 underline"
                        >
                          Visit MYLaw Case Archive
                        </a>
                        {" "}and find "{selectedCaseForUpload.title}"
                      </span>
                    </li>
                    <li className="flex gap-2">
                      <span className="bg-indigo-600 text-white w-5 h-5 rounded-full flex items-center justify-center text-xs flex-shrink-0">2</span>
                      <span>Click the download link to save the PDF to your computer</span>
                    </li>
                    <li className="flex gap-2">
                      <span className="bg-indigo-600 text-white w-5 h-5 rounded-full flex items-center justify-center text-xs flex-shrink-0">3</span>
                      <span>Upload the PDF below (we'll parse it automatically)</span>
                    </li>
                  </ol>
                </div>
                
                {/* Copyright Notice */}
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 mb-4">
                  <p className="text-amber-300 text-sm">
                    <strong>Copyright:</strong> Case materials are copyrighted by MYLaw. For personal practice only.
                  </p>
                </div>

                {/* Upload Option: Full PDF or by Section */}
                <div className="mb-4">
                  <label className="block text-slate-400 text-sm mb-2">Upload Option:</label>
                  <select
                    value={uploadSection}
                    onChange={(e) => setUploadSection(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-indigo-500"
                  >
                    <option value="summary">📄 Full Case PDF (recommended)</option>
                    <option value="witnesses_plaintiff">Plaintiff/Prosecution Witnesses Only</option>
                    <option value="witnesses_defense">Defense Witnesses Only</option>
                    <option value="exhibits">Exhibits Only</option>
                    <option value="stipulations">Stipulations Only</option>
                    <option value="jury_instructions">Jury Instructions Only</option>
                    <option value="rules">Rules & Procedures Only</option>
                  </select>
                </div>

                {uploadError && (
                  <div className="bg-red-500/10 border border-red-500/30 text-red-300 rounded-lg p-3 mb-4">{uploadError}</div>
                )}

                <div className="border-2 border-dashed border-slate-600 rounded-xl p-6 text-center mb-4">
                  {isUploading ? (
                    <div className="flex flex-col items-center gap-3 py-2">
                      <div className="w-10 h-10 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                      <span className="text-slate-300 font-medium">{uploadProgress || "Processing..."}</span>
                      <span className="text-slate-500 text-xs">Please don&apos;t close this window</span>
                    </div>
                  ) : (
                    <>
                      <FolderIcon className="w-10 h-10 mx-auto text-slate-500 mb-3" />
                      <p className="text-slate-400 mb-3 text-sm">Drop your downloaded PDF here</p>
                      <label className="cursor-pointer">
                        <input
                          type="file"
                          accept=".pdf,.txt,.doc,.docx"
                          onChange={handleSectionFileSelect}
                          className="hidden"
                          disabled={isUploading}
                        />
                        <span className="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg inline-block transition-colors">
                          Select PDF File
                        </span>
                      </label>
                    </>
                  )}
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      setSelectedCaseForUpload(null);
                      setShowUploadModal(false);
                      setUploadError(null);
                    }}
                    className="flex-1 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <a
                    href={selectedCaseForUpload.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors text-center flex items-center justify-center gap-2"
                  >
                    <ExternalLinkIcon className="w-4 h-4" />
                    Open MYLaw
                  </a>
                </div>
              </>
            ) : (
              <>
                <h2 className="text-xl font-bold text-white mb-4">Upload Case Materials</h2>
                <p className="text-slate-400 mb-4">
                  Upload case materials from MYLaw or other mock trial sources. You can upload a complete case PDF
                  or individual sections.
                </p>

                {/* Info about MYLaw */}
                <div className="bg-slate-700/50 rounded-lg p-4 mb-4">
                  <h4 className="text-white font-medium mb-2">Get Official Cases from MYLaw</h4>
                  <p className="text-slate-400 text-sm mb-2">
                    Download official mock trial cases from MYLaw, then upload the PDF here.
                  </p>
                  <a
                    href="https://www.mylaw.org/mock-trial-cases-and-resources"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm rounded-lg transition-colors"
                  >
                    <ExternalLinkIcon className="w-4 h-4" />
                    Open MYLaw Case Archive
                  </a>
                </div>

                {/* Section Selector */}
                <div className="mb-4">
                  <label className="block text-slate-300 text-sm font-medium mb-2">What are you uploading?</label>
                  <select
                    value={uploadSection}
                    onChange={(e) => setUploadSection(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-indigo-500"
                  >
                    <option value="summary">📄 Complete Case PDF (all materials)</option>
                    <option value="witnesses_plaintiff">👤 Plaintiff/Prosecution Witness Affidavits</option>
                    <option value="witnesses_defense">👤 Defense Witness Affidavits</option>
                    <option value="exhibits">📎 Exhibits (documents, photos, evidence)</option>
                    <option value="stipulations">📋 Stipulations (agreed facts)</option>
                    <option value="jury_instructions">⚖️ Jury Instructions / Legal Standards</option>
                    <option value="rules">📖 Rules & Procedures</option>
                  </select>
                  <p className="text-slate-500 text-xs mt-1">
                    {uploadSection === "summary" 
                      ? "Upload the complete case PDF - we'll parse all sections automatically"
                      : "Upload just this section of the case materials"}
                  </p>
                </div>

                {/* Case Name Input (for new uploads) */}
                <div className="mb-4">
                  <label className="block text-slate-300 text-sm font-medium mb-2">Case Name</label>
                  <input
                    type="text"
                    value={newCaseName}
                    onChange={(e) => setNewCaseName(e.target.value)}
                    placeholder="e.g., State v. Luna (2024)"
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                {uploadError && (
                  <div className="bg-red-500/10 border border-red-500/30 text-red-300 rounded-lg p-3 mb-4">{uploadError}</div>
                )}

                <div className="border-2 border-dashed border-slate-600 rounded-xl p-6 text-center mb-4">
                  {isUploading ? (
                    <div className="flex flex-col items-center gap-3 py-2">
                      <div className="w-10 h-10 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                      <span className="text-slate-300 font-medium">{uploadProgress || "Processing..."}</span>
                      <span className="text-slate-500 text-xs">Please don&apos;t close this window</span>
                    </div>
                  ) : (
                    <>
                      <UploadIcon className="w-10 h-10 mx-auto text-slate-500 mb-3" />
                      <p className="text-slate-400 mb-3 text-sm">Drop your case PDF here or click to select</p>
                      <label className="cursor-pointer">
                        <input
                          type="file"
                          accept=".pdf,.json,.txt,.doc,.docx"
                          onChange={handleFileSelect}
                          className="hidden"
                          disabled={isUploading}
                        />
                        <span className="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg inline-block transition-colors">
                          Select File
                        </span>
                      </label>
                      <p className="text-slate-500 text-xs mt-2">Supports PDF, JSON, TXT, DOC files</p>
                    </>
                  )}
                </div>

                {/* Copyright Notice */}
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 mb-4">
                  <p className="text-amber-300 text-xs">
                    <strong>Copyright:</strong> Case materials are copyrighted by their publishers (MYLaw, AMTA, etc.). 
                    Upload for personal practice use only.
                  </p>
                </div>

                <button
                  onClick={() => setShowUploadModal(false)}
                  className="w-full py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                >
                  Cancel
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
