/**
 * CaseMaterialsModal - View Case Facts, Witnesses, and Exhibits
 * 
 * Provides a modal interface for reviewing case materials during preparation
 * and trial phases.
 */

"use client";

import React, { useState, useEffect } from "react";
import { ChevronDownIcon } from "@/components/ui/icons";

// =============================================================================
// SVG ICONS
// =============================================================================

const CloseIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const DocumentIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
  </svg>
);

const UserIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

const FolderIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
  </svg>
);

const BookOpenIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
  </svg>
);

const ScaleIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 3v18M5 8l7-5 7 5M5 8l-1 8h4M19 8l1 8h-4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const FileIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
    <polyline points="13 2 13 9 20 9" />
  </svg>
);

const DownloadIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="7 10 12 15 17 10" />
    <line x1="12" y1="15" x2="12" y2="3" />
  </svg>
);

const ExternalLinkIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    <polyline points="15 3 21 3 21 9" />
    <line x1="10" y1="14" x2="21" y2="3" />
  </svg>
);

const ImageIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
    <circle cx="8.5" cy="8.5" r="1.5" />
    <polyline points="21 15 16 10 5 21" />
  </svg>
);

const ShieldIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </svg>
);

const GavelIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M14 3L20 9M8 14L3 19M10 12L14.5 7.5M12 14L7.5 18.5M21 21H3" />
  </svg>
);

// =============================================================================
// TYPES
// =============================================================================

export type ModalTab = "overview" | "witnesses" | "exhibits" | "facts" | "rules" | "legal" | "files";

interface Fact {
  id: string;
  content: string;
  source: string;
}

interface CaseFile {
  filename: string;
  type: string;
  size: number;
  url: string;
  section?: string;
}

type FileCategory = "pdf" | "image" | "text" | "word" | "excel" | "unsupported";

function getFileCategory(mimeType: string, filename: string): FileCategory {
  if (mimeType === "application/pdf") return "pdf";
  if (mimeType.startsWith("image/")) return "image";
  if (mimeType.startsWith("text/") || 
      filename.endsWith(".txt") || 
      filename.endsWith(".md") ||
      filename.endsWith(".json") ||
      filename.endsWith(".csv")) return "text";
  if (mimeType.includes("word") || 
      mimeType === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
      filename.endsWith(".doc") || 
      filename.endsWith(".docx")) return "word";
  if (mimeType.includes("excel") || 
      mimeType.includes("spreadsheet") ||
      mimeType === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
      filename.endsWith(".xls") || 
      filename.endsWith(".xlsx")) return "excel";
  return "unsupported";
}

interface FactsByType {
  background: Fact[];
  evidence: Fact[];
  stipulation: Fact[];
  legal_standard: Fact[];
}

interface Witness {
  id: string;
  name: string;
  called_by: "plaintiff" | "defense" | "either" | "unknown";
  role_description: string;
  affidavit: string;
  key_facts: string[];
}

interface Exhibit {
  id: string;
  title: string;
  description: string;
  content: string;
  exhibit_type: string;
}

interface SpecialInstruction {
  number: number;
  title: string;
  content: string;
}

interface JuryInstruction {
  id: string;
  number: number;
  title: string;
  content: string;
}

interface MotionInLimine {
  id: string;
  letter: string;
  title: string;
  ruling: string;
}

interface Indictment {
  charge: string;
  charge_detail: string;
  full_text: string;
}

interface Statute {
  id: string;
  title: string;
  content: string;
}

interface CaseLawEntry {
  id: string;
  citation: string;
  content: string;
}

interface RelevantLaw {
  statutes: Statute[];
  cases: CaseLawEntry[];
}

interface WitnessCallingRestrictions {
  prosecution_only: string[];
  defense_only: string[];
  either_side: string[];
}

interface Stipulation {
  id: string;
  number?: number;
  content: string;
}

interface LegalStandard {
  id: string;
  content: string;
  source: string;
}

export interface CaseMaterials {
  session_id: string;
  case_id: string;
  case_name: string;
  case_type: string;
  description: string;
  summary: string;
  charge?: string;
  plaintiff?: string;
  defendant?: string;
  witnesses: Witness[];
  exhibits: Exhibit[];
  facts: FactsByType;
  stipulations: Stipulation[];
  legal_standards: LegalStandard[];
  special_instructions: SpecialInstruction[];
  jury_instructions: JuryInstruction[];
  motions_in_limine: MotionInLimine[];
  indictment: Indictment;
  relevant_law: RelevantLaw;
  witness_calling_restrictions: WitnessCallingRestrictions;
}

interface CaseMaterialsModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId: string;
  initialTab?: ModalTab;
}

// =============================================================================
// API
// =============================================================================

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchCaseMaterials(sessionId: string): Promise<CaseMaterials> {
  const url = `${API_BASE}/api/session/${sessionId}/case-materials`;
  console.log("[CaseMaterialsModal] Fetching case materials from:", url);
  
  const response = await fetch(url);
  if (!response.ok) {
    const text = await response.text();
    console.error("[CaseMaterialsModal] Error fetching materials:", response.status, text);
    throw new Error(`Failed to fetch case materials: ${response.status}`);
  }
  
  const data = await response.json();
  console.log("[CaseMaterialsModal] Received materials:", data);
  return data;
}

async function fetchCaseFiles(caseId: string): Promise<CaseFile[]> {
  const url = `${API_BASE}/api/case/${caseId}/storage/files`;
  console.log("[CaseMaterialsModal] Fetching case files from:", url);
  
  const response = await fetch(url);
  if (!response.ok) {
    console.warn("[CaseMaterialsModal] No case files found");
    return [];
  }
  
  const data = await response.json();
  const storageFiles = data.files || [];
  
  // Convert storage files to CaseFile format with signed URLs
  const caseFiles: CaseFile[] = [];
  for (const f of storageFiles) {
    // Get a signed URL for each file
    try {
      const urlRes = await fetch(
        `${API_BASE}/api/case/${caseId}/storage/files/${f.section}/${f.name}/url`
      );
      if (urlRes.ok) {
        const urlData = await urlRes.json();
        caseFiles.push({
          filename: f.name,
          type: f.name.endsWith(".pdf") ? "application/pdf" 
              : f.name.endsWith(".txt") ? "text/plain"
              : f.name.endsWith(".png") ? "image/png"
              : f.name.endsWith(".jpg") || f.name.endsWith(".jpeg") ? "image/jpeg"
              : f.name.endsWith(".doc") || f.name.endsWith(".docx") ? "application/msword"
              : "application/octet-stream",
          size: f.size || 0,
          url: urlData.url || "",
          section: f.section,
        });
      }
    } catch {
      // Skip files we can't get URLs for
    }
  }
  
  return caseFiles;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function CaseMaterialsModal({
  isOpen,
  onClose,
  sessionId,
  initialTab = "overview",
}: CaseMaterialsModalProps) {
  const [activeTab, setActiveTab] = useState<ModalTab>(initialTab);
  const [materials, setMaterials] = useState<CaseMaterials | null>(null);
  const [caseFiles, setCaseFiles] = useState<CaseFile[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedWitness, setExpandedWitness] = useState<string | null>(null);
  const [expandedExhibit, setExpandedExhibit] = useState<string | null>(null);
  const [viewingFile, setViewingFile] = useState<CaseFile | null>(null);

  // Reset tab when initialTab changes (e.g., from quick action buttons)
  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab);
    }
  }, [isOpen, initialTab]);

  // Fetch materials when modal opens - always fetch fresh data
  useEffect(() => {
    if (!isOpen) return;

    // Reset state when opening
    setMaterials(null);
    setCaseFiles([]);
    setError(null);
    setExpandedWitness(null);
    setExpandedExhibit(null);
    setViewingFile(null);

    async function load() {
      setIsLoading(true);
      try {
        const data = await fetchCaseMaterials(sessionId);
        setMaterials(data);
        
        // Also fetch case files if we have a case_id
        if (data.case_id) {
          const files = await fetchCaseFiles(data.case_id);
          setCaseFiles(files);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load case materials");
      } finally {
        setIsLoading(false);
      }
    }

    load();
  }, [isOpen, sessionId]);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.body.style.overflow = "";
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const tabs: { id: ModalTab; label: string; icon: React.ReactNode; badge?: number }[] = [
    { id: "overview", label: "Overview", icon: <BookOpenIcon className="w-4 h-4" /> },
    { id: "files", label: "Case Files", icon: <FileIcon className="w-4 h-4" />, badge: caseFiles.length },
    { id: "witnesses", label: "Witnesses", icon: <UserIcon className="w-4 h-4" /> },
    { id: "exhibits", label: "Exhibits", icon: <FolderIcon className="w-4 h-4" /> },
    { id: "facts", label: "Facts", icon: <ScaleIcon className="w-4 h-4" /> },
    { id: "rules", label: "Rules", icon: <ShieldIcon className="w-4 h-4" />, badge: materials?.special_instructions?.length },
    { id: "legal", label: "Legal", icon: <GavelIcon className="w-4 h-4" /> },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-4xl max-h-[90vh] mx-4 bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
              <DocumentIcon className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Case Materials</h2>
              {materials && (
                <p className="text-sm text-slate-400">{materials.case_name}</p>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
          >
            <CloseIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-700/50 px-6 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px whitespace-nowrap ${
                activeTab === tab.id
                  ? "text-amber-400 border-amber-400"
                  : "text-slate-400 border-transparent hover:text-white"
              }`}
            >
              {tab.icon}
              {tab.label}
              {tab.badge !== undefined && tab.badge > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-amber-500/20 text-amber-400 rounded-full">
                  {tab.badge}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-16">
              <div className="w-12 h-12 border-4 border-amber-500/30 border-t-amber-500 rounded-full animate-spin mb-4" />
              <p className="text-slate-400">Loading case materials...</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center mb-4">
                <span className="text-2xl">⚠️</span>
              </div>
              <p className="text-red-400 mb-2">Failed to load materials</p>
              <p className="text-slate-500 text-sm mb-4">{error}</p>
              <p className="text-slate-600 text-xs mb-4">
                This can happen if the session expired or the backend restarted. Try starting a new trial from the home page.
              </p>
              <button
                onClick={() => {
                  setError(null);
                  setIsLoading(true);
                  fetchCaseMaterials(sessionId)
                    .then(data => {
                      setMaterials(data);
                      if (data.case_id) {
                        fetchCaseFiles(data.case_id).then(setCaseFiles);
                      }
                    })
                    .catch(err => setError(err instanceof Error ? err.message : "Failed to load"))
                    .finally(() => setIsLoading(false));
                }}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg transition-colors"
              >
                Retry
              </button>
            </div>
          ) : materials ? (
            <>
              {/* Overview Tab */}
              {activeTab === "overview" && (
                <div className="space-y-6">
                  {/* Case Type & Parties */}
                  <div className="flex flex-wrap items-center gap-3">
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                      materials.case_type === "criminal" 
                        ? "bg-red-500/20 text-red-400" 
                        : "bg-blue-500/20 text-blue-400"
                    }`}>
                      {materials.case_type === "criminal" ? "Criminal Case" : "Civil Case"}
                    </span>
                    {materials.charge && (
                      <span className="px-3 py-1 rounded-full text-sm font-medium bg-orange-500/20 text-orange-400">
                        Charge: {materials.charge}
                      </span>
                    )}
                  </div>

                  {/* Parties */}
                  {(materials.plaintiff || materials.defendant) && (
                    <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
                      <div className="flex items-center justify-between">
                        <div className="text-center flex-1">
                          <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">
                            {materials.case_type === "criminal" ? "Prosecution" : "Plaintiff"}
                          </div>
                          <div className="text-white font-semibold">{materials.plaintiff || "Unknown"}</div>
                        </div>
                        <div className="text-slate-600 font-bold text-lg px-4">v.</div>
                        <div className="text-center flex-1">
                          <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Defendant</div>
                          <div className="text-white font-semibold">{materials.defendant || "Unknown"}</div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Indictment */}
                  {materials.indictment?.charge_detail && (
                    <div>
                      <h3 className="text-lg font-semibold text-white mb-2">Indictment</h3>
                      <div className="bg-red-500/5 rounded-xl p-4 border border-red-500/20">
                        <p className="text-slate-300 leading-relaxed text-sm">{materials.indictment.charge_detail}</p>
                      </div>
                    </div>
                  )}

                  {/* Synopsis */}
                  {(materials.summary || materials.description) && (
                    <div>
                      <h3 className="text-lg font-semibold text-white mb-2">Case Synopsis</h3>
                      <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
                        <p className="text-slate-300 leading-relaxed whitespace-pre-line">
                          {materials.summary || materials.description}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Quick Stats */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 text-center">
                      <div className="text-2xl font-bold text-amber-400">{materials.witnesses.length}</div>
                      <div className="text-sm text-slate-400">Witnesses</div>
                    </div>
                    <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 text-center">
                      <div className="text-2xl font-bold text-blue-400">{materials.exhibits.length}</div>
                      <div className="text-sm text-slate-400">Exhibits</div>
                    </div>
                    <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 text-center">
                      <div className="text-2xl font-bold text-emerald-400">
                        {Object.values(materials.facts).flat().length}
                      </div>
                      <div className="text-sm text-slate-400">Facts</div>
                    </div>
                  </div>

                  {/* Witness Calling Restrictions Summary */}
                  {materials.witness_calling_restrictions && (
                    Object.values(materials.witness_calling_restrictions).some(a => a?.length > 0)
                  ) && (
                    <div>
                      <h3 className="text-lg font-semibold text-white mb-2">Witness Calling Restrictions</h3>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        {materials.witness_calling_restrictions.prosecution_only?.length > 0 && (
                          <div className="bg-blue-500/10 rounded-xl p-3 border border-blue-500/20">
                            <div className="text-xs text-blue-400 uppercase tracking-wider mb-2 font-semibold">Prosecution Only</div>
                            {materials.witness_calling_restrictions.prosecution_only.map((n, i) => (
                              <div key={i} className="text-sm text-slate-300">{n}</div>
                            ))}
                          </div>
                        )}
                        {materials.witness_calling_restrictions.defense_only?.length > 0 && (
                          <div className="bg-emerald-500/10 rounded-xl p-3 border border-emerald-500/20">
                            <div className="text-xs text-emerald-400 uppercase tracking-wider mb-2 font-semibold">Defense Only</div>
                            {materials.witness_calling_restrictions.defense_only.map((n, i) => (
                              <div key={i} className="text-sm text-slate-300">{n}</div>
                            ))}
                          </div>
                        )}
                        {materials.witness_calling_restrictions.either_side?.length > 0 && (
                          <div className="bg-amber-500/10 rounded-xl p-3 border border-amber-500/20">
                            <div className="text-xs text-amber-400 uppercase tracking-wider mb-2 font-semibold">Either Side</div>
                            {materials.witness_calling_restrictions.either_side.map((n, i) => (
                              <div key={i} className="text-sm text-slate-300">{n}</div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Witnesses Tab */}
              {activeTab === "witnesses" && (
                <div className="space-y-4">
                  {materials.witnesses.length === 0 ? (
                    <div className="text-center py-12 text-slate-400">
                      <UserIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>No witnesses in this case</p>
                    </div>
                  ) : (
                    <>
                      {/* Prosecution / Plaintiff Witnesses */}
                      <div>
                        <h3 className="text-sm font-semibold text-blue-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-blue-400" />
                          {materials.case_type === "criminal" ? "Prosecution" : "Plaintiff"} Witnesses
                          <span className="ml-1 px-1.5 py-0.5 text-xs bg-blue-500/20 text-blue-400 rounded-full">
                            {materials.witnesses.filter((w) => w.called_by === "plaintiff" || w.called_by === "prosecution").length}
                          </span>
                        </h3>
                        <div className="space-y-3">
                          {materials.witnesses
                            .filter((w) => w.called_by === "plaintiff" || w.called_by === "prosecution")
                            .map((witness) => (
                              <WitnessCard
                                key={witness.id}
                                witness={witness}
                                isExpanded={expandedWitness === witness.id}
                                onToggle={() =>
                                  setExpandedWitness(
                                    expandedWitness === witness.id ? null : witness.id
                                  )
                                }
                              />
                            ))}
                        </div>
                      </div>

                      {/* Defense Witnesses */}
                      <div className="mt-6">
                        <h3 className="text-sm font-semibold text-emerald-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-emerald-400" />
                          Defense Witnesses
                          <span className="ml-1 px-1.5 py-0.5 text-xs bg-emerald-500/20 text-emerald-400 rounded-full">
                            {materials.witnesses.filter((w) => w.called_by === "defense").length}
                          </span>
                        </h3>
                        <div className="space-y-3">
                          {materials.witnesses
                            .filter((w) => w.called_by === "defense")
                            .map((witness) => (
                              <WitnessCard
                                key={witness.id}
                                witness={witness}
                                isExpanded={expandedWitness === witness.id}
                                onToggle={() =>
                                  setExpandedWitness(
                                    expandedWitness === witness.id ? null : witness.id
                                  )
                                }
                              />
                            ))}
                        </div>
                      </div>

                      {/* Either Side Witnesses */}
                      {materials.witnesses.filter((w) => w.called_by === "either" || w.called_by === "unknown").length > 0 && (
                        <div className="mt-6">
                          <h3 className="text-sm font-semibold text-amber-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-amber-400" />
                            Either Side May Call
                          </h3>
                          <div className="space-y-3">
                            {materials.witnesses
                              .filter((w) => w.called_by === "either" || w.called_by === "unknown")
                              .map((witness) => (
                                <WitnessCard
                                  key={witness.id}
                                  witness={witness}
                                  isExpanded={expandedWitness === witness.id}
                                  onToggle={() =>
                                    setExpandedWitness(
                                      expandedWitness === witness.id ? null : witness.id
                                    )
                                  }
                                />
                              ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* Exhibits Tab */}
              {activeTab === "exhibits" && (
                <div className="space-y-4">
                  {materials.exhibits.length === 0 ? (
                    <div className="text-center py-12 text-slate-400">
                      <FolderIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>No exhibits in this case</p>
                    </div>
                  ) : (
                    materials.exhibits.map((exhibit) => (
                      <ExhibitCard
                        key={exhibit.id}
                        exhibit={exhibit}
                        isExpanded={expandedExhibit === exhibit.id}
                        onToggle={() =>
                          setExpandedExhibit(
                            expandedExhibit === exhibit.id ? null : exhibit.id
                          )
                        }
                      />
                    ))
                  )}
                </div>
              )}

              {/* Facts Tab */}
              {activeTab === "facts" && (
                <div className="space-y-6">
                  {/* Background Facts */}
                  {materials.facts.background.length > 0 && (
                    <FactSection
                      title="Background Facts"
                      facts={materials.facts.background}
                      color="text-slate-400"
                      bgColor="bg-slate-800/50"
                    />
                  )}

                  {/* Evidence */}
                  {materials.facts.evidence.length > 0 && (
                    <FactSection
                      title="Evidence"
                      facts={materials.facts.evidence}
                      color="text-amber-400"
                      bgColor="bg-amber-500/10"
                    />
                  )}

                  {/* Stipulations */}
                  {materials.facts.stipulation.length > 0 && (
                    <FactSection
                      title="Stipulations"
                      facts={materials.facts.stipulation}
                      color="text-blue-400"
                      bgColor="bg-blue-500/10"
                    />
                  )}

                  {/* Legal Standards */}
                  {materials.facts.legal_standard.length > 0 && (
                    <FactSection
                      title="Legal Standards"
                      facts={materials.facts.legal_standard}
                      color="text-purple-400"
                      bgColor="bg-purple-500/10"
                    />
                  )}
                </div>
              )}

              {/* Rules Tab */}
              {activeTab === "rules" && (
                <div className="space-y-6">
                  {/* Special Instructions */}
                  {materials.special_instructions?.length > 0 && (
                    <div>
                      <h3 className="text-lg font-semibold text-white mb-3">Special Instructions</h3>
                      <div className="space-y-3">
                        {materials.special_instructions.map((si) => (
                          <div
                            key={si.number}
                            className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50"
                          >
                            <div className="flex items-start gap-3">
                              <span className="flex-shrink-0 w-7 h-7 rounded-lg bg-amber-500/20 text-amber-400 flex items-center justify-center text-xs font-bold">
                                {si.number}
                              </span>
                              <div className="flex-1 min-w-0">
                                {si.title && (
                                  <h4 className="text-sm font-semibold text-white mb-1">{si.title}</h4>
                                )}
                                <p className="text-sm text-slate-300 leading-relaxed">{si.content}</p>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Witness Calling Restrictions */}
                  {materials.witness_calling_restrictions && (
                    Object.values(materials.witness_calling_restrictions).some(a => a?.length > 0)
                  ) && (
                    <div>
                      <h3 className="text-lg font-semibold text-white mb-3">Witness Calling Restrictions</h3>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {materials.witness_calling_restrictions.prosecution_only?.length > 0 && (
                          <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-500/20">
                            <div className="text-xs text-blue-400 uppercase tracking-wider mb-3 font-semibold">Prosecution Only</div>
                            <div className="space-y-1">
                              {materials.witness_calling_restrictions.prosecution_only.map((n, i) => (
                                <div key={i} className="text-sm text-slate-300 flex items-center gap-2">
                                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0" />
                                  {n}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {materials.witness_calling_restrictions.defense_only?.length > 0 && (
                          <div className="bg-emerald-500/10 rounded-xl p-4 border border-emerald-500/20">
                            <div className="text-xs text-emerald-400 uppercase tracking-wider mb-3 font-semibold">Defense Only</div>
                            <div className="space-y-1">
                              {materials.witness_calling_restrictions.defense_only.map((n, i) => (
                                <div key={i} className="text-sm text-slate-300 flex items-center gap-2">
                                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
                                  {n}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {materials.witness_calling_restrictions.either_side?.length > 0 && (
                          <div className="bg-amber-500/10 rounded-xl p-4 border border-amber-500/20">
                            <div className="text-xs text-amber-400 uppercase tracking-wider mb-3 font-semibold">Either Side</div>
                            <div className="space-y-1">
                              {materials.witness_calling_restrictions.either_side.map((n, i) => (
                                <div key={i} className="text-sm text-slate-300 flex items-center gap-2">
                                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                                  {n}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Empty state */}
                  {(!materials.special_instructions || materials.special_instructions.length === 0) &&
                   (!materials.witness_calling_restrictions || !Object.values(materials.witness_calling_restrictions).some(a => a?.length > 0)) && (
                    <div className="text-center py-12 text-slate-400">
                      <ShieldIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>No special instructions or rules available for this case</p>
                    </div>
                  )}
                </div>
              )}

              {/* Legal Tab */}
              {activeTab === "legal" && (
                <div className="space-y-6">
                  {/* Jury Instructions */}
                  {materials.jury_instructions?.length > 0 && (
                    <div>
                      <h3 className="text-lg font-semibold text-white mb-3">Jury Instructions</h3>
                      <div className="space-y-3">
                        {materials.jury_instructions.map((ji) => (
                          <div
                            key={ji.id}
                            className="bg-purple-500/5 rounded-xl p-4 border border-purple-500/20"
                          >
                            <div className="flex items-start gap-3">
                              <span className="flex-shrink-0 w-7 h-7 rounded-lg bg-purple-500/20 text-purple-400 flex items-center justify-center text-xs font-bold">
                                {ji.number}
                              </span>
                              <div className="flex-1 min-w-0">
                                {ji.title && (
                                  <h4 className="text-sm font-semibold text-purple-300 mb-1">{ji.title}</h4>
                                )}
                                <p className="text-sm text-slate-300 leading-relaxed">{ji.content}</p>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Relevant Statutes */}
                  {materials.relevant_law?.statutes?.length > 0 && (
                    <div>
                      <h3 className="text-lg font-semibold text-white mb-3">Relevant Statutes</h3>
                      <div className="space-y-3">
                        {materials.relevant_law.statutes.map((statute) => (
                          <div
                            key={statute.id}
                            className="bg-blue-500/5 rounded-xl p-4 border border-blue-500/20"
                          >
                            <h4 className="text-sm font-semibold text-blue-300 mb-2">{statute.title}</h4>
                            <p className="text-sm text-slate-300 leading-relaxed">{statute.content}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Relevant Case Law */}
                  {materials.relevant_law?.cases?.length > 0 && (
                    <div>
                      <h3 className="text-lg font-semibold text-white mb-3">Relevant Case Law</h3>
                      <div className="space-y-3">
                        {materials.relevant_law.cases.map((caseItem) => (
                          <div
                            key={caseItem.id}
                            className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50"
                          >
                            <h4 className="text-sm font-semibold text-amber-300 mb-2">{caseItem.citation}</h4>
                            <p className="text-sm text-slate-300 leading-relaxed">{caseItem.content}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Motions in Limine */}
                  {materials.motions_in_limine?.length > 0 && (
                    <div>
                      <h3 className="text-lg font-semibold text-white mb-3">Motions in Limine Rulings</h3>
                      <div className="space-y-3">
                        {materials.motions_in_limine.map((motion) => (
                          <div
                            key={motion.id}
                            className="bg-rose-500/5 rounded-xl p-4 border border-rose-500/20"
                          >
                            <div className="flex items-start gap-3">
                              <span className="flex-shrink-0 w-7 h-7 rounded-lg bg-rose-500/20 text-rose-400 flex items-center justify-center text-xs font-bold">
                                {motion.letter}
                              </span>
                              <div className="flex-1 min-w-0">
                                <h4 className="text-sm font-semibold text-rose-300 mb-2">{motion.title}</h4>
                                <p className="text-sm text-slate-300 leading-relaxed">{motion.ruling}</p>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Empty state */}
                  {(!materials.jury_instructions || materials.jury_instructions.length === 0) &&
                   (!materials.relevant_law?.statutes || materials.relevant_law.statutes.length === 0) &&
                   (!materials.relevant_law?.cases || materials.relevant_law.cases.length === 0) &&
                   (!materials.motions_in_limine || materials.motions_in_limine.length === 0) && (
                    <div className="text-center py-12 text-slate-400">
                      <GavelIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>No legal materials available for this case</p>
                    </div>
                  )}
                </div>
              )}

              {/* Files Tab */}
              {activeTab === "files" && (
                <div className="space-y-4">
                  {caseFiles.length === 0 ? (
                    <div className="text-center py-12">
                      <FileIcon className="w-16 h-16 mx-auto mb-4 text-slate-600" />
                      <h3 className="text-lg font-medium text-slate-400 mb-2">No Case Files Yet</h3>
                      <p className="text-slate-500 text-sm max-w-md mx-auto mb-4">
                        Upload case materials (PDFs, images, documents) from the Cases page to view them here.
                      </p>
                    </div>
                  ) : (() => {
                    const sectionLabels: Record<string, string> = {
                      summary: "Case Summary",
                      witnesses_plaintiff: "Plaintiff Witnesses",
                      witnesses_defense: "Defense Witnesses",
                      exhibits: "Exhibits",
                      stipulations: "Stipulations",
                      jury_instructions: "Jury Instructions",
                      rules: "Rules & Procedures",
                    };
                    const grouped: Record<string, CaseFile[]> = {};
                    for (const f of caseFiles) {
                      const sec = f.section || "other";
                      if (!grouped[sec]) grouped[sec] = [];
                      grouped[sec].push(f);
                    }
                    return (
                      <>
                        <p className="text-sm text-slate-400 mb-4">
                          {caseFiles.length} file{caseFiles.length !== 1 ? "s" : ""} stored in Supabase. Click to view.
                        </p>
                        {Object.entries(grouped).map(([section, files]) => (
                          <div key={section}>
                            <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                              {sectionLabels[section] || section}
                            </h4>
                            <div className="grid gap-2 mb-4">
                              {files.map((file) => (
                                <FileCard
                                  key={file.filename}
                                  file={file}
                                  onOpen={() => setViewingFile(file)}
                                />
                              ))}
                            </div>
                          </div>
                        ))}
                      </>
                    );
                  })()}
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-700/50 bg-slate-800/50">
          <div className="flex justify-between items-center">
            <p className="text-sm text-slate-500">
              Press <kbd className="px-1.5 py-0.5 bg-slate-700 rounded text-xs">Esc</kbd> to close
            </p>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
      
      {/* File Viewer Modal (nested) */}
      {viewingFile && (
        <FileViewerModal 
          file={viewingFile} 
          onClose={() => setViewingFile(null)} 
        />
      )}
    </div>
  );
}

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

// =============================================================================
// FILE VIEWER MODAL
// =============================================================================

function FileViewerModal({ 
  file, 
  onClose 
}: { 
  file: CaseFile; 
  onClose: () => void;
}) {
  // Signed URLs from Supabase Storage are already absolute
  const fileUrl = file.url.startsWith("http") ? file.url : `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}${file.url}`;
  const [textContent, setTextContent] = useState<string | null>(null);
  const [isLoadingText, setIsLoadingText] = useState(false);
  const [textError, setTextError] = useState<string | null>(null);
  
  const fileCategory = getFileCategory(file.type, file.filename);
  
  // Load text content for text files
  useEffect(() => {
    if (fileCategory === "text") {
      setIsLoadingText(true);
      setTextError(null);
      fetch(fileUrl)
        .then(res => {
          if (!res.ok) throw new Error("Failed to load file");
          return res.text();
        })
        .then(text => setTextContent(text))
        .catch(err => setTextError(err.message))
        .finally(() => setIsLoadingText(false));
    }
  }, [fileUrl, fileCategory]);
  
  // Close on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [onClose]);
  
  const getFileIcon = () => {
    switch (fileCategory) {
      case "pdf": return <FileIcon className="w-5 h-5 text-red-400" />;
      case "image": return <ImageIcon className="w-5 h-5 text-emerald-400" />;
      case "word": return <DocumentIcon className="w-5 h-5 text-blue-400" />;
      case "excel": return <DocumentIcon className="w-5 h-5 text-green-400" />;
      default: return <DocumentIcon className="w-5 h-5 text-slate-400" />;
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-5xl max-h-[95vh] mx-4 bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/50 bg-slate-800/50">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-slate-700/50 flex items-center justify-center">
              {getFileIcon()}
            </div>
            <div>
              <h3 className="font-medium text-white text-sm">{file.filename}</h3>
              <p className="text-xs text-slate-400">{file.type}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={fileUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg transition-colors"
            >
              <ExternalLinkIcon className="w-3.5 h-3.5" />
              Open in New Tab
            </a>
            <a
              href={fileUrl}
              download={file.filename}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg transition-colors"
            >
              <DownloadIcon className="w-3.5 h-3.5" />
              Download
            </a>
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
            >
              <CloseIcon className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-auto bg-slate-950">
          {fileCategory === "pdf" && (
            <iframe
              src={`${fileUrl}#toolbar=1&navpanes=1`}
              className="w-full h-full min-h-[70vh]"
              title={file.filename}
            />
          )}
          
          {fileCategory === "image" && (
            <div className="flex items-center justify-center p-8 min-h-[70vh]">
              <img
                src={fileUrl}
                alt={file.filename}
                className="max-w-full max-h-[80vh] object-contain rounded-lg shadow-lg"
              />
            </div>
          )}
          
          {fileCategory === "text" && (
            <div className="p-6 min-h-[70vh]">
              {isLoadingText ? (
                <div className="flex items-center justify-center py-16">
                  <div className="w-8 h-8 border-3 border-amber-500/30 border-t-amber-500 rounded-full animate-spin" />
                </div>
              ) : textError ? (
                <div className="text-center py-16">
                  <p className="text-red-400">Failed to load file content</p>
                  <p className="text-slate-500 text-sm mt-1">{textError}</p>
                </div>
              ) : (
                <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono leading-relaxed bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
                  {textContent}
                </pre>
              )}
            </div>
          )}
          
          {fileCategory === "word" && (
            <div className="flex flex-col items-center justify-center p-8 min-h-[70vh] text-center">
              <div className="w-20 h-20 rounded-2xl bg-blue-500/20 flex items-center justify-center mb-4">
                <DocumentIcon className="w-10 h-10 text-blue-400" />
              </div>
              <h4 className="text-lg font-medium text-white mb-2">Word Document</h4>
              <p className="text-slate-400 mb-6 max-w-md">
                Word documents cannot be previewed directly in the browser. 
                Use the buttons below to open or download the file.
              </p>
              <div className="flex gap-3">
                <a
                  href={`https://view.officeapps.live.com/op/view.aspx?src=${encodeURIComponent(fileUrl)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors"
                >
                  <ExternalLinkIcon className="w-4 h-4" />
                  Open in Microsoft Viewer
                </a>
                <a
                  href={fileUrl}
                  download={file.filename}
                  className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                >
                  <DownloadIcon className="w-4 h-4" />
                  Download
                </a>
              </div>
            </div>
          )}
          
          {fileCategory === "excel" && (
            <div className="flex flex-col items-center justify-center p-8 min-h-[70vh] text-center">
              <div className="w-20 h-20 rounded-2xl bg-green-500/20 flex items-center justify-center mb-4">
                <DocumentIcon className="w-10 h-10 text-green-400" />
              </div>
              <h4 className="text-lg font-medium text-white mb-2">Excel Spreadsheet</h4>
              <p className="text-slate-400 mb-6 max-w-md">
                Excel files cannot be previewed directly in the browser. 
                Use the buttons below to open or download the file.
              </p>
              <div className="flex gap-3">
                <a
                  href={`https://view.officeapps.live.com/op/view.aspx?src=${encodeURIComponent(fileUrl)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg transition-colors"
                >
                  <ExternalLinkIcon className="w-4 h-4" />
                  Open in Microsoft Viewer
                </a>
                <a
                  href={fileUrl}
                  download={file.filename}
                  className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                >
                  <DownloadIcon className="w-4 h-4" />
                  Download
                </a>
              </div>
            </div>
          )}
          
          {fileCategory === "unsupported" && (
            <div className="flex flex-col items-center justify-center p-8 min-h-[70vh] text-center">
              <div className="w-20 h-20 rounded-2xl bg-slate-700/50 flex items-center justify-center mb-4">
                <FileIcon className="w-10 h-10 text-slate-400" />
              </div>
              <h4 className="text-lg font-medium text-white mb-2">Preview Not Available</h4>
              <p className="text-slate-400 mb-6 max-w-md">
                This file type ({file.type}) cannot be previewed in the browser.
                Download the file to view it with the appropriate application.
              </p>
              <a
                href={fileUrl}
                download={file.filename}
                className="flex items-center gap-2 px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg transition-colors"
              >
                <DownloadIcon className="w-4 h-4" />
                Download File
              </a>
            </div>
          )}
        </div>
        
        {/* Footer hint */}
        <div className="px-4 py-2 border-t border-slate-700/50 bg-slate-800/30">
          <p className="text-xs text-slate-500 text-center">
            Press <kbd className="px-1 py-0.5 bg-slate-700 rounded text-xs">Esc</kbd> to close
          </p>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// FILE CARD
// =============================================================================

function FileCard({ file, onOpen }: { file: CaseFile; onOpen: () => void }) {
  const fileCategory = getFileCategory(file.type, file.filename);
  
  const getFileIcon = () => {
    switch (fileCategory) {
      case "pdf": return <FileIcon className="w-6 h-6 text-red-400" />;
      case "image": return <ImageIcon className="w-6 h-6 text-emerald-400" />;
      case "word": return <DocumentIcon className="w-6 h-6 text-blue-400" />;
      case "excel": return <DocumentIcon className="w-6 h-6 text-green-400" />;
      default: return <DocumentIcon className="w-6 h-6 text-slate-400" />;
    }
  };
  
  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };
  
  const getFileTypeLabel = () => {
    switch (fileCategory) {
      case "pdf": return "PDF Document";
      case "image": return "Image";
      case "word": return "Word Document";
      case "excel": return "Excel Spreadsheet";
      case "text": return "Text File";
      default: return "Document";
    }
  };

  return (
    <button
      onClick={onOpen}
      className="w-full bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 hover:bg-slate-700/50 hover:border-amber-500/30 transition-all text-left group"
    >
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-lg bg-slate-700/50 flex items-center justify-center group-hover:bg-slate-600/50 transition-colors">
          {getFileIcon()}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-white truncate group-hover:text-amber-400 transition-colors">
            {file.filename}
          </h4>
          <p className="text-sm text-slate-400">
            {getFileTypeLabel()} • {formatSize(file.size)}
          </p>
        </div>
        <div className="flex items-center gap-2 text-slate-400 group-hover:text-amber-400 transition-colors">
          <span className="text-sm">View</span>
          <ExternalLinkIcon className="w-4 h-4" />
        </div>
      </div>
    </button>
  );
}

function WitnessCard({
  witness,
  isExpanded,
  onToggle,
}: {
  witness: Witness;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
            (witness.called_by === "plaintiff" || witness.called_by === "prosecution") ? "bg-blue-500/20" : "bg-emerald-500/20"
          }`}>
            <UserIcon className={`w-5 h-5 ${
              (witness.called_by === "plaintiff" || witness.called_by === "prosecution") ? "text-blue-400" : "text-emerald-400"
            }`} />
          </div>
          <div className="text-left">
            <h4 className="font-medium text-white">{witness.name}</h4>
            {witness.role_description && (
              <p className="text-sm text-slate-400 line-clamp-1">{witness.role_description}</p>
            )}
          </div>
        </div>
        <ChevronDownIcon
          className={`w-5 h-5 text-slate-400 transition-transform ${
            isExpanded ? "rotate-180" : ""
          }`}
        />
      </button>

      {isExpanded && witness.affidavit && (
        <div className="px-4 pb-4 pt-0">
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-600/30">
            <h5 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Affidavit / Statement
            </h5>
            <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">
              {witness.affidavit}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function ExhibitCard({
  exhibit,
  isExpanded,
  onToggle,
}: {
  exhibit: Exhibit;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center">
            <FolderIcon className="w-5 h-5 text-amber-400" />
          </div>
          <div className="text-left">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 bg-slate-700 rounded text-xs font-medium text-slate-300">
                {exhibit.id}
              </span>
              <h4 className="font-medium text-white">{exhibit.title}</h4>
            </div>
            {exhibit.description && (
              <p className="text-sm text-slate-400 line-clamp-1">{exhibit.description}</p>
            )}
          </div>
        </div>
        <ChevronDownIcon
          className={`w-5 h-5 text-slate-400 transition-transform ${
            isExpanded ? "rotate-180" : ""
          }`}
        />
      </button>

      {isExpanded && exhibit.content && (
        <div className="px-4 pb-4 pt-0">
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-600/30">
            <h5 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Exhibit Content
            </h5>
            <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">
              {exhibit.content}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function FactSection({
  title,
  facts,
  color,
  bgColor,
}: {
  title: string;
  facts: Fact[];
  color: string;
  bgColor: string;
}) {
  return (
    <div>
      <h3 className={`text-sm font-semibold ${color} uppercase tracking-wider mb-3`}>
        {title}
      </h3>
      <div className="space-y-2">
        {facts.map((fact, index) => (
          <div
            key={fact.id || index}
            className={`${bgColor} rounded-lg p-3 border border-slate-700/30`}
          >
            <p className="text-slate-300 text-sm">{fact.content}</p>
            {fact.source && (
              <p className="text-xs text-slate-500 mt-1">Source: {fact.source}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default CaseMaterialsModal;
