"use client";

import React, { useState, useEffect, useCallback } from "react";
import { ChevronDownIcon } from "@/components/ui/icons";
import { apiFetch, API_BASE } from "@/lib/api";

// =============================================================================
// TYPES
// =============================================================================

interface AgentLLMConfig {
  llm_model?: string | null;
  llm_temperature?: number | null;
  llm_max_tokens?: number | null;
  system_prompt?: string | null;
}

interface AttorneyPersona extends AgentLLMConfig {
  id?: string;
  role: "opening" | "direct_cross" | "closing";
  name: string;
  style: string;
  skill_level: string;
  description: string;
  objection_frequency: number;
  risk_tolerance: number;
  speaking_pace: number;
  formality: number;
}

interface WitnessPersona extends AgentLLMConfig {
  id?: string;
  name: string;
  witness_type: string;
  demeanor: string;
  nervousness: number;
  difficulty: number;
  description: string;
  verbosity?: number;
  evasiveness?: number;
}

interface JudgePersona extends AgentLLMConfig {
  id?: string;
  role: "presiding" | "scoring";
  name: string;
  temperament: string;
  scoring_style: string;
  authority_level: number;
  description: string;
  years_on_bench: number;
}

interface ModelOption {
  id: string;
  label: string;
  provider: string;
  description: string;
}

interface TeamConfig {
  prosecution_attorneys: AttorneyPersona[];
  defense_attorneys: AttorneyPersona[];
  prosecution_witnesses: WitnessPersona[];
  defense_witnesses: WitnessPersona[];
  judges: JudgePersona[];
  using_defaults: boolean;
}

interface PersonaCustomizerProps {
  sessionId: string;
  onClose?: () => void;
  humanRole?: string | null;
  attorneySubRole?: string | null;
}

// =============================================================================
// ICONS
// =============================================================================

const UserIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2M12 11a4 4 0 100-8 4 4 0 000 8z" />
  </svg>
);

const GavelIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M14 3L20 9M8 14L3 19M10 12L14.5 7.5M12 14L7.5 18.5M21 21H3" />
  </svg>
);

const ScalesIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 3v18M3 7l9-4 9 4M3 7v4c0 1.5 2 3 4 3s4-1.5 4-3V7M14 7v4c0 1.5 2 3 4 3s4-1.5 4-3V7" />
  </svg>
);

const ShieldIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </svg>
);

const CheckIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

// =============================================================================
// SLIDER
// =============================================================================

const SliderInput = ({
  label,
  value,
  onChange,
  min = 0,
  max = 1,
  step = 0.1,
  leftLabel = "Low",
  rightLabel = "High",
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  leftLabel?: string;
  rightLabel?: string;
}) => (
  <div className="space-y-1">
    <div className="flex justify-between text-sm">
      <span className="text-slate-300">{label}</span>
      <span className="text-slate-500">{Math.round(value * 100)}%</span>
    </div>
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onChange(parseFloat(e.target.value))}
      className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-indigo-500"
    />
    <div className="flex justify-between text-xs text-slate-500">
      <span>{leftLabel}</span>
      <span>{rightLabel}</span>
    </div>
  </div>
);

// =============================================================================
// ROLE LABELS
// =============================================================================

const ATTORNEY_ROLE_LABELS: Record<string, { label: string; badge: string }> = {
  opening: { label: "Opening Attorney", badge: "Opening" },
  direct_cross: { label: "Direct/Cross Attorney", badge: "Direct/Cross" },
  closing: { label: "Closing Attorney", badge: "Closing" },
};

const ATTORNEY_ROLE_DESCRIPTIONS: Record<string, string> = {
  opening: "Gives the opening statement. Tells the story of the case.",
  direct_cross: "Conducts direct/cross examinations, makes objections.",
  closing: "Argues the case. Connects evidence to legal standards.",
};

// =============================================================================
// PER-AGENT LLM CONFIG SECTION (reused across all agent cards)
// =============================================================================

function AgentLLMConfigSection({
  config,
  models,
  onChange,
  defaultPrompt,
}: {
  config: AgentLLMConfig;
  models: ModelOption[];
  onChange: (patch: Partial<AgentLLMConfig>) => void;
  defaultPrompt?: string;
}) {
  const [showSection, setShowSection] = useState(false);
  const [showDefaultPrompt, setShowDefaultPrompt] = useState(false);
  const hasOverrides = !!(config.llm_model || config.llm_temperature != null || config.llm_max_tokens != null || config.system_prompt);

  const groupedModels = React.useMemo(() => {
    const groups: Record<string, ModelOption[]> = {};
    for (const m of models) {
      const p = m.provider || "openai";
      if (!groups[p]) groups[p] = [];
      groups[p].push(m);
    }
    return groups;
  }, [models]);

  const providerLabels: Record<string, string> = {
    openai: "OpenAI",
    anthropic: "Anthropic (Claude)",
    google: "Google (Gemini)",
    xai: "xAI (Grok)",
  };

  return (
    <div className="mt-2 border-t border-slate-600/50 pt-2">
      <button
        onClick={() => setShowSection(!showSection)}
        className="flex items-center justify-between text-xs text-slate-400 hover:text-slate-200 transition-colors w-full"
      >
        <span className="flex items-center gap-2">
          Agent LLM Config
          {hasOverrides && <span className="px-1.5 py-0.5 text-[10px] rounded bg-indigo-500/30 text-indigo-300">Custom</span>}
        </span>
        <ChevronDownIcon className={`w-5 h-5 text-slate-400 transition-transform ${showSection ? "rotate-180" : ""}`} />
      </button>

      {showSection && (
        <div className="mt-2 space-y-3 bg-slate-800/50 rounded-lg p-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Model</label>
            <select
              value={config.llm_model || ""}
              onChange={(e) => onChange({ llm_model: e.target.value || null })}
              className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
            >
              <option value="">Global Default</option>
              {Object.entries(groupedModels).map(([provider, provModels]) => (
                <optgroup key={provider} label={providerLabels[provider] || provider}>
                  {provModels.map((m) => (
                    <option key={m.id} value={m.id}>{m.label}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1">
                Temperature {config.llm_temperature != null ? `(${config.llm_temperature.toFixed(2)})` : "(default)"}
              </label>
              <input
                type="range"
                min={0}
                max={2}
                step={0.05}
                value={config.llm_temperature ?? 0.7}
                onChange={(e) => onChange({ llm_temperature: parseFloat(e.target.value) })}
                className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-indigo-500"
              />
              <div className="flex justify-between text-[10px] text-slate-500">
                <span>Precise</span>
                <span>Creative</span>
              </div>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">
                Max Tokens {config.llm_max_tokens != null ? `(${config.llm_max_tokens})` : "(default)"}
              </label>
              <input
                type="range"
                min={50}
                max={4000}
                step={50}
                value={config.llm_max_tokens ?? 500}
                onChange={(e) => onChange({ llm_max_tokens: parseInt(e.target.value) })}
                className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-indigo-500"
              />
              <div className="flex justify-between text-[10px] text-slate-500">
                <span>Short</span>
                <span>Long</span>
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Custom System Prompt</label>
            <textarea
              rows={3}
              value={config.system_prompt || ""}
              onChange={(e) => onChange({ system_prompt: e.target.value || null })}
              placeholder="Leave empty for default persona prompt. Adds instructions to the beginning of the agent's system prompt."
              className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm placeholder-slate-500 resize-y"
            />
          </div>

          {defaultPrompt && (
            <div>
              <button
                onClick={() => setShowDefaultPrompt(!showDefaultPrompt)}
                className="flex items-center justify-between text-xs text-slate-400 hover:text-slate-200 transition-colors w-full"
              >
                <span>View Built-in System Prompt</span>
                <ChevronDownIcon className={`w-5 h-5 text-slate-400 transition-transform ${showDefaultPrompt ? "rotate-180" : ""}`} />
              </button>
              {showDefaultPrompt && (
                <pre className="mt-1.5 p-2.5 bg-slate-900/80 border border-slate-700 rounded-lg text-[11px] text-slate-400 max-h-48 overflow-y-auto whitespace-pre-wrap font-mono leading-relaxed">
                  {defaultPrompt}
                </pre>
              )}
            </div>
          )}

          {hasOverrides && (
            <button
              onClick={() => onChange({ llm_model: null, llm_temperature: null, llm_max_tokens: null, system_prompt: null })}
              className="text-xs text-red-400 hover:text-red-300 transition-colors"
            >
              Reset to Defaults
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

function AttorneyCard({
  attorney,
  index,
  side,
  expanded,
  onToggle,
  onChange,
  onSave,
  isSaving,
  isHuman,
  models = [],
  defaultPrompt,
}: {
  attorney: AttorneyPersona;
  index: number;
  side: "prosecution" | "defense";
  expanded: boolean;
  onToggle: () => void;
  onChange: (a: AttorneyPersona) => void;
  onSave: () => void;
  isSaving: boolean;
  isHuman?: boolean;
  models?: ModelOption[];
  defaultPrompt?: string;
}) {
  const roleInfo = ATTORNEY_ROLE_LABELS[attorney.role] || { label: attorney.role, badge: attorney.role };
  const sideColor = side === "prosecution" ? "blue" : "emerald";

  return (
    <div className={`bg-slate-700/30 border rounded-xl overflow-hidden ${isHuman ? "border-amber-500/50 ring-1 ring-amber-500/20" : "border-slate-700"}`}>
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg ${isHuman ? "bg-amber-500/20" : `bg-${sideColor}-500/20`} flex items-center justify-center`}>
            {isHuman
              ? <UserIcon className="w-5 h-5 text-amber-400" />
              : <ScalesIcon className={`w-5 h-5 text-${sideColor}-400`} />
            }
          </div>
          <div className="text-left">
            <div className="flex items-center gap-2">
              <span className="font-medium text-white">{isHuman ? "You" : attorney.name}</span>
              <span className={`px-2 py-0.5 text-xs rounded-full bg-${sideColor}-500/20 text-${sideColor}-400`}>
                {roleInfo.badge}
              </span>
              {isHuman && (
                <span className="px-2 py-0.5 text-xs rounded-full bg-amber-500/20 text-amber-400 font-semibold">
                  Your Role
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400">
              {isHuman ? "Human Player" : `${attorney.style} / ${attorney.skill_level}`}
            </p>
          </div>
        </div>
        {!isHuman && (
          <ChevronDownIcon className={`w-5 h-5 text-slate-400 transition-transform ${expanded ? "rotate-180" : ""}`} />
        )}
      </button>

      {expanded && !isHuman && (
        <div className="px-4 pb-4 space-y-3 border-t border-slate-700/50 pt-3">
          <p className="text-xs text-slate-500 italic">{ATTORNEY_ROLE_DESCRIPTIONS[attorney.role]}</p>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Name</label>
            <input
              type="text"
              value={attorney.name}
              onChange={(e) => onChange({ ...attorney, name: e.target.value })}
              className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Style</label>
              <select
                value={attorney.style}
                onChange={(e) => onChange({ ...attorney, style: e.target.value })}
                className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
              >
                <option value="aggressive">Aggressive</option>
                <option value="methodical">Methodical</option>
                <option value="charismatic">Charismatic</option>
                <option value="technical">Technical</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Skill Level</label>
              <select
                value={attorney.skill_level}
                onChange={(e) => onChange({ ...attorney, skill_level: e.target.value })}
                className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
              >
                <option value="novice">Novice</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
                <option value="expert">Expert</option>
              </select>
            </div>
          </div>

          <SliderInput
            label="Objection Frequency"
            value={attorney.objection_frequency}
            onChange={(v) => onChange({ ...attorney, objection_frequency: v })}
            leftLabel="Rarely"
            rightLabel="Often"
          />
          <SliderInput
            label="Risk Tolerance"
            value={attorney.risk_tolerance}
            onChange={(v) => onChange({ ...attorney, risk_tolerance: v })}
            leftLabel="Conservative"
            rightLabel="Aggressive"
          />

          <AgentLLMConfigSection
            config={attorney}
            models={models}
            onChange={(patch) => onChange({ ...attorney, ...patch })}
            defaultPrompt={defaultPrompt}
          />

          <button
            onClick={onSave}
            disabled={isSaving}
            className="w-full py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm transition-colors disabled:opacity-50"
          >
            {isSaving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      )}
    </div>
  );
}

function WitnessCard({
  witness,
  index,
  side,
  expanded,
  onToggle,
  onChange,
  onSave,
  isSaving,
  models = [],
  defaultPrompt,
}: {
  witness: WitnessPersona;
  index: number;
  side: "prosecution" | "defense";
  expanded: boolean;
  onToggle: () => void;
  onChange: (w: WitnessPersona) => void;
  onSave: () => void;
  isSaving: boolean;
  models?: ModelOption[];
  defaultPrompt?: string;
}) {
  const sideColor = side === "prosecution" ? "blue" : "emerald";

  return (
    <div className="bg-slate-700/30 border border-slate-700 rounded-xl overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg bg-${sideColor}-500/20 flex items-center justify-center`}>
            <UserIcon className={`w-5 h-5 text-${sideColor}-400`} />
          </div>
          <div className="text-left">
            <div className="flex items-center gap-2">
              <span className="font-medium text-white">{witness.name || `Witness ${index + 1}`}</span>
              <span className="px-2 py-0.5 text-xs rounded-full bg-slate-600 text-slate-300 capitalize">
                {witness.witness_type.replace("_", " ")}
              </span>
            </div>
            <p className="text-xs text-slate-400 capitalize">{witness.demeanor} / nervousness {Math.round(witness.nervousness * 100)}%</p>
          </div>
        </div>
        <ChevronDownIcon className={`w-5 h-5 text-slate-400 transition-transform ${expanded ? "rotate-180" : ""}`} />
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-slate-700/50 pt-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Type</label>
              <select
                value={witness.witness_type}
                onChange={(e) => onChange({ ...witness, witness_type: e.target.value })}
                className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
              >
                <option value="fact_witness">Fact Witness</option>
                <option value="expert_witness">Expert Witness</option>
                <option value="character_witness">Character Witness</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Demeanor</label>
              <select
                value={witness.demeanor}
                onChange={(e) => onChange({ ...witness, demeanor: e.target.value })}
                className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
              >
                <option value="calm">Calm</option>
                <option value="nervous">Nervous</option>
                <option value="defensive">Defensive</option>
                <option value="eager">Eager</option>
                <option value="hostile">Hostile</option>
              </select>
            </div>
          </div>

          <SliderInput
            label="Nervousness"
            value={witness.nervousness}
            onChange={(v) => onChange({ ...witness, nervousness: v })}
            leftLabel="Calm"
            rightLabel="Very Nervous"
          />
          <SliderInput
            label="Difficulty"
            value={witness.difficulty}
            onChange={(v) => onChange({ ...witness, difficulty: v })}
            leftLabel="Cooperative"
            rightLabel="Very Difficult"
          />

          <AgentLLMConfigSection
            config={witness}
            models={models}
            onChange={(patch) => onChange({ ...witness, ...patch })}
            defaultPrompt={defaultPrompt}
          />

          <button
            onClick={onSave}
            disabled={isSaving}
            className="w-full py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm transition-colors disabled:opacity-50"
          >
            {isSaving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      )}
    </div>
  );
}

function JudgeCard({
  judge,
  index,
  expanded,
  onToggle,
  onChange,
  onSave,
  isSaving,
  models = [],
  defaultPrompt,
}: {
  judge: JudgePersona;
  index: number;
  expanded: boolean;
  onToggle: () => void;
  onChange: (j: JudgePersona) => void;
  onSave: () => void;
  isSaving: boolean;
  models?: ModelOption[];
  defaultPrompt?: string;
}) {
  return (
    <div className="bg-slate-700/30 border border-slate-700 rounded-xl overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center">
            <GavelIcon className="w-5 h-5 text-amber-400" />
          </div>
          <div className="text-left">
            <div className="flex items-center gap-2">
              <span className="font-medium text-white">{judge.name}</span>
              <span className="px-2 py-0.5 text-xs rounded-full bg-amber-500/20 text-amber-400 capitalize">
                {judge.role}
              </span>
            </div>
            <p className="text-xs text-slate-400 capitalize">{judge.temperament} / {judge.scoring_style}</p>
          </div>
        </div>
        <ChevronDownIcon className={`w-5 h-5 text-slate-400 transition-transform ${expanded ? "rotate-180" : ""}`} />
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-slate-700/50 pt-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Name</label>
            <input
              type="text"
              value={judge.name}
              onChange={(e) => onChange({ ...judge, name: e.target.value })}
              className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Temperament</label>
              <select
                value={judge.temperament}
                onChange={(e) => onChange({ ...judge, temperament: e.target.value })}
                className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
              >
                <option value="stern">Stern</option>
                <option value="patient">Patient</option>
                <option value="formal">Formal</option>
                <option value="pragmatic">Pragmatic</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Scoring Style</label>
              <select
                value={judge.scoring_style}
                onChange={(e) => onChange({ ...judge, scoring_style: e.target.value })}
                className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
              >
                <option value="strict">Strict</option>
                <option value="balanced">Balanced</option>
                <option value="generous">Generous</option>
              </select>
            </div>
          </div>

          <SliderInput
            label="Authority Level"
            value={judge.authority_level}
            onChange={(v) => onChange({ ...judge, authority_level: v })}
            leftLabel="Permissive"
            rightLabel="Very Strict"
          />

          <AgentLLMConfigSection
            config={judge}
            models={models}
            onChange={(patch) => onChange({ ...judge, ...patch })}
            defaultPrompt={defaultPrompt}
          />

          <button
            onClick={onSave}
            disabled={isSaving}
            className="w-full py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm transition-colors disabled:opacity-50"
          >
            {isSaving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

type TabId = "prosecution" | "defense" | "judges" | "settings";

export default function PersonaCustomizer({ sessionId, onClose, humanRole, attorneySubRole }: PersonaCustomizerProps) {
  const humanSide: "prosecution" | "defense" | null =
    humanRole === "attorney_plaintiff" ? "prosecution" :
    humanRole === "attorney_defense" ? "defense" : null;

  const [activeTab, setActiveTab] = useState<TabId>("prosecution");
  const [team, setTeam] = useState<TeamConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [expandedCard, setExpandedCard] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [availableModels, setAvailableModels] = useState<ModelOption[]>([]);
  const [agentDefaultPrompts, setAgentDefaultPrompts] = useState<Record<string, string>>({});

  const [llmConfig, setLlmConfig] = useState<{
    model: string;
    temperature: number;
    max_tokens: number;
    tts_model: string;
    tts_voice: string;
    available_models: { id: string; label: string; description: string }[];
    available_tts_voices: { id: string; label: string }[];
  } | null>(null);

  const loadTeam = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await apiFetch(`${API_BASE}/api/persona/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        setTeam(data);
        if (data.available_models) setAvailableModels(data.available_models);
      }
    } catch (err) {
      console.error("Failed to load team personas:", err);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  const loadLlmConfig = useCallback(async () => {
    try {
      const res = await apiFetch(`${API_BASE}/api/persona/${sessionId}/llm-config`);
      if (res.ok) {
        const data = await res.json();
        setLlmConfig(data);
      }
    } catch (err) {
      console.error("Failed to load LLM config:", err);
    }
  }, [sessionId]);

  const loadAgentConfigs = useCallback(async () => {
    try {
      const res = await apiFetch(`${API_BASE}/api/persona/${sessionId}/agent-configs`);
      if (res.ok) {
        const data = await res.json();
        const prompts: Record<string, string> = {};
        for (const a of data.agents || []) {
          const key = `${a.type}:${a.name}`;
          if (a.default_system_prompt) prompts[key] = a.default_system_prompt;
        }
        setAgentDefaultPrompts(prompts);
      }
    } catch { /* non-critical */ }
  }, [sessionId]);

  const saveLlmConfig = async (updates: Record<string, any>) => {
    setIsSaving(true);
    try {
      const res = await apiFetch(`${API_BASE}/api/persona/${sessionId}/llm-config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      if (res.ok) {
        const data = await res.json();
        setLlmConfig((prev) => prev ? { ...prev, ...data.config } : prev);
        setSaveMessage("LLM config saved");
        setTimeout(() => setSaveMessage(null), 2000);
      }
    } catch (err) {
      console.error("Failed to save LLM config:", err);
    } finally {
      setIsSaving(false);
    }
  };

  useEffect(() => {
    loadTeam();
    loadLlmConfig();
    loadAgentConfigs();
  }, [loadTeam, loadLlmConfig, loadAgentConfigs]);

  const showSaved = () => {
    setSaveMessage("Saved");
    setTimeout(() => setSaveMessage(null), 2000);
  };

  const saveAttorney = async (side: "prosecution" | "defense", index: number, attorney: AttorneyPersona) => {
    setIsSaving(true);
    try {
      const res = await apiFetch(`${API_BASE}/api/persona/${sessionId}/${side}/attorney/${index}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(attorney),
      });
      if (res.ok) showSaved();
    } catch (err) {
      console.error("Failed to save attorney:", err);
    } finally {
      setIsSaving(false);
    }
  };

  const saveWitness = async (side: "prosecution" | "defense", index: number, witness: WitnessPersona) => {
    setIsSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/persona/${sessionId}/${side}/witness/${index}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(witness),
      });
      if (res.ok) showSaved();
    } catch (err) {
      console.error("Failed to save witness:", err);
    } finally {
      setIsSaving(false);
    }
  };

  const saveJudge = async (index: number, judge: JudgePersona) => {
    setIsSaving(true);
    try {
      const res = await apiFetch(`${API_BASE}/api/persona/${sessionId}/judge/${index}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(judge),
      });
      if (res.ok) showSaved();
    } catch (err) {
      console.error("Failed to save judge:", err);
    } finally {
      setIsSaving(false);
    }
  };

  const resetAll = async () => {
    setIsSaving(true);
    try {
      await apiFetch(`${API_BASE}/api/persona/${sessionId}`, { method: "DELETE" });
      await loadTeam();
      showSaved();
    } catch (err) {
      console.error("Failed to reset:", err);
    } finally {
      setIsSaving(false);
    }
  };

  const updateLocalAttorney = (side: "prosecution" | "defense", index: number, attorney: AttorneyPersona) => {
    if (!team) return;
    const key = side === "prosecution" ? "prosecution_attorneys" : "defense_attorneys";
    const updated = [...team[key]];
    updated[index] = attorney;
    setTeam({ ...team, [key]: updated });
  };

  const updateLocalWitness = (side: "prosecution" | "defense", index: number, witness: WitnessPersona) => {
    if (!team) return;
    const key = side === "prosecution" ? "prosecution_witnesses" : "defense_witnesses";
    const updated = [...team[key]];
    updated[index] = witness;
    setTeam({ ...team, [key]: updated });
  };

  const updateLocalJudge = (index: number, judge: JudgePersona) => {
    if (!team) return;
    const updated = [...team.judges];
    updated[index] = judge;
    setTeam({ ...team, judges: updated });
  };

  const tabs: { id: TabId; label: string; icon: React.ReactNode; activeClass: string }[] = [
    { id: "prosecution", label: "Prosecution", icon: <ScalesIcon className="w-4 h-4" />, activeClass: "text-blue-400 border-b-2 border-blue-400 bg-slate-700/30" },
    { id: "defense", label: "Defense", icon: <ShieldIcon className="w-4 h-4" />, activeClass: "text-emerald-400 border-b-2 border-emerald-400 bg-slate-700/30" },
    { id: "judges", label: "Judges", icon: <GavelIcon className="w-4 h-4" />, activeClass: "text-amber-400 border-b-2 border-amber-400 bg-slate-700/30" },
    { id: "settings", label: "LLM Config", icon: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>, activeClass: "text-purple-400 border-b-2 border-purple-400 bg-slate-700/30" },
  ];

  return (
    <div className="bg-slate-800 rounded-2xl border border-slate-700 overflow-hidden max-w-4xl w-full max-h-[90vh] flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-slate-700 flex items-center justify-between bg-slate-800/80">
        <div>
          <h2 className="text-xl font-bold text-white">Customize AI Team Personas</h2>
          <p className="text-sm text-slate-400">Configure attorneys, witnesses, and judges for the mock trial</p>
        </div>
        <div className="flex items-center gap-2">
          {saveMessage && (
            <span className="flex items-center gap-1 text-sm text-emerald-400">
              <CheckIcon className="w-4 h-4" />
              {saveMessage}
            </span>
          )}
          {onClose && (
            <button onClick={onClose} className="p-2 text-slate-400 hover:text-white transition-colors">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-700 bg-slate-800/50">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 px-4 py-3 flex items-center justify-center gap-2 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? tab.activeClass
                : "text-slate-400 hover:text-white"
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading || !team ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {/* Prosecution Tab */}
            {activeTab === "prosecution" && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-sm font-semibold text-blue-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-blue-400" />
                    Prosecution Attorneys (3)
                  </h3>
                  <div className="space-y-2">
                    {team.prosecution_attorneys.map((attorney, i) => (
                      <AttorneyCard
                        key={`pros-att-${i}`}
                        attorney={attorney}
                        index={i}
                        side="prosecution"
                        expanded={expandedCard === `pros-att-${i}`}
                        onToggle={() => setExpandedCard(expandedCard === `pros-att-${i}` ? null : `pros-att-${i}`)}
                        onChange={(a) => updateLocalAttorney("prosecution", i, a)}
                        onSave={() => saveAttorney("prosecution", i, team.prosecution_attorneys[i])}
                        isSaving={isSaving}
                        isHuman={humanSide === "prosecution" && attorney.role === attorneySubRole}
                        models={availableModels}
                        defaultPrompt={agentDefaultPrompts[`attorney:${attorney.name}`]}
                      />
                    ))}
                  </div>
                </div>

                <div>
                  <h3 className="text-sm font-semibold text-blue-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-blue-400" />
                    Prosecution Witnesses ({team.prosecution_witnesses.length})
                  </h3>
                  <div className="space-y-2">
                    {team.prosecution_witnesses.map((witness, i) => (
                      <WitnessCard
                        key={`pros-wit-${i}`}
                        witness={witness}
                        index={i}
                        side="prosecution"
                        expanded={expandedCard === `pros-wit-${i}`}
                        onToggle={() => setExpandedCard(expandedCard === `pros-wit-${i}` ? null : `pros-wit-${i}`)}
                        onChange={(w) => updateLocalWitness("prosecution", i, w)}
                        onSave={() => saveWitness("prosecution", i, team.prosecution_witnesses[i])}
                        isSaving={isSaving}
                        models={availableModels}
                        defaultPrompt={agentDefaultPrompts[`witness:${witness.name}`]}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Defense Tab */}
            {activeTab === "defense" && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-sm font-semibold text-emerald-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    Defense Attorneys (3)
                  </h3>
                  <div className="space-y-2">
                    {team.defense_attorneys.map((attorney, i) => (
                      <AttorneyCard
                        key={`def-att-${i}`}
                        attorney={attorney}
                        index={i}
                        side="defense"
                        expanded={expandedCard === `def-att-${i}`}
                        onToggle={() => setExpandedCard(expandedCard === `def-att-${i}` ? null : `def-att-${i}`)}
                        onChange={(a) => updateLocalAttorney("defense", i, a)}
                        onSave={() => saveAttorney("defense", i, team.defense_attorneys[i])}
                        isSaving={isSaving}
                        isHuman={humanSide === "defense" && attorney.role === attorneySubRole}
                        models={availableModels}
                        defaultPrompt={agentDefaultPrompts[`attorney:${attorney.name}`]}
                      />
                    ))}
                  </div>
                </div>

                <div>
                  <h3 className="text-sm font-semibold text-emerald-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    Defense Witnesses ({team.defense_witnesses.length})
                  </h3>
                  <div className="space-y-2">
                    {team.defense_witnesses.map((witness, i) => (
                      <WitnessCard
                        key={`def-wit-${i}`}
                        witness={witness}
                        index={i}
                        side="defense"
                        expanded={expandedCard === `def-wit-${i}`}
                        onToggle={() => setExpandedCard(expandedCard === `def-wit-${i}` ? null : `def-wit-${i}`)}
                        onChange={(w) => updateLocalWitness("defense", i, w)}
                        onSave={() => saveWitness("defense", i, team.defense_witnesses[i])}
                        isSaving={isSaving}
                        models={availableModels}
                        defaultPrompt={agentDefaultPrompts[`witness:${witness.name}`]}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Judges Tab */}
            {activeTab === "judges" && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-sm font-semibold text-amber-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-amber-400" />
                    Judges (2)
                  </h3>
                  <div className="space-y-2">
                    {team.judges.map((judge, i) => (
                      <JudgeCard
                        key={`judge-${i}`}
                        judge={judge}
                        index={i}
                        expanded={expandedCard === `judge-${i}`}
                        onToggle={() => setExpandedCard(expandedCard === `judge-${i}` ? null : `judge-${i}`)}
                        onChange={(j) => updateLocalJudge(i, j)}
                        onSave={() => saveJudge(i, team.judges[i])}
                        isSaving={isSaving}
                        models={availableModels}
                        defaultPrompt={agentDefaultPrompts[`judge:${judge.name}`]}
                      />
                    ))}
                  </div>
                </div>

                <div className="bg-slate-700/30 rounded-xl p-4 border border-slate-700">
                  <h4 className="text-sm font-medium text-white mb-2">About Judges</h4>
                  <ul className="text-xs text-slate-400 space-y-1">
                    <li><strong className="text-amber-400">Presiding Judge</strong> - Runs the courtroom: swears witnesses, rules on objections, enforces procedure.</li>
                    <li><strong className="text-amber-400">Scoring Judge</strong> - Observes and evaluates performance across all scoring categories.</li>
                  </ul>
                </div>
              </div>
            )}

            {activeTab === "settings" && (
              <div className="space-y-6">
                {!llmConfig ? (
                  <div className="flex items-center justify-center py-12">
                    <div className="w-8 h-8 border-3 border-purple-500/30 border-t-purple-500 rounded-full animate-spin" />
                  </div>
                ) : (
                  <>
                    <div>
                      <h3 className="text-sm font-semibold text-purple-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-purple-400" />
                        Language Model
                      </h3>
                      <div className="space-y-4">
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Global Default Model</label>
                          {(() => {
                            const providerLabels: Record<string, string> = {
                              openai: "OpenAI",
                              anthropic: "Anthropic (Claude)",
                              google: "Google (Gemini)",
                              xai: "xAI (Grok)",
                            };
                            const providerColors: Record<string, string> = {
                              openai: "text-emerald-400",
                              anthropic: "text-orange-400",
                              google: "text-blue-400",
                              xai: "text-red-400",
                            };
                            const grouped: Record<string, typeof llmConfig.available_models> = {};
                            for (const m of llmConfig.available_models) {
                              const p = (m as Record<string, string>).provider || "openai";
                              if (!grouped[p]) grouped[p] = [];
                              grouped[p].push(m);
                            }
                            return Object.entries(grouped).map(([provider, models]) => (
                              <div key={provider} className="mb-3">
                                <p className={`text-xs font-semibold mb-1.5 ${providerColors[provider] || "text-slate-400"}`}>
                                  {providerLabels[provider] || provider}
                                </p>
                                <div className="grid grid-cols-1 gap-1.5">
                                  {models.map((m) => (
                                    <button
                                      key={m.id}
                                      onClick={() => saveLlmConfig({ model: m.id })}
                                      className={`w-full text-left px-3 py-2 rounded-lg border transition-all ${
                                        llmConfig.model === m.id
                                          ? "border-purple-500 bg-purple-500/10 text-white"
                                          : "border-slate-700 bg-slate-800/50 text-slate-300 hover:border-slate-600"
                                      }`}
                                    >
                                      <div className="flex items-center justify-between">
                                        <div>
                                          <span className="text-sm font-medium">{m.label}</span>
                                          <p className="text-xs text-slate-500 mt-0.5">{m.description}</p>
                                        </div>
                                        {llmConfig.model === m.id && (
                                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400">ACTIVE</span>
                                        )}
                                      </div>
                                    </button>
                                  ))}
                                </div>
                              </div>
                            ));
                          })()}
                          <p className="text-xs text-slate-500 mt-2">
                            Per-agent model overrides are available in each agent&apos;s expanded card above.
                          </p>
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            Temperature: <span className="text-white font-mono">{llmConfig.temperature.toFixed(1)}</span>
                          </label>
                          <input
                            type="range"
                            min="0"
                            max="2"
                            step="0.1"
                            value={llmConfig.temperature}
                            onChange={(e) => {
                              const val = parseFloat(e.target.value);
                              setLlmConfig((prev) => prev ? { ...prev, temperature: val } : prev);
                            }}
                            onMouseUp={(e) => saveLlmConfig({ temperature: parseFloat((e.target as HTMLInputElement).value) })}
                            onTouchEnd={(e) => saveLlmConfig({ temperature: parseFloat((e.target as HTMLInputElement).value) })}
                            className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-purple-500"
                          />
                          <div className="flex justify-between text-[10px] text-slate-600 mt-1">
                            <span>Precise (0.0)</span>
                            <span>Balanced (0.7)</span>
                            <span>Creative (2.0)</span>
                          </div>
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            Max Tokens: <span className="text-white font-mono">{llmConfig.max_tokens}</span>
                          </label>
                          <input
                            type="range"
                            min="100"
                            max="4000"
                            step="100"
                            value={llmConfig.max_tokens}
                            onChange={(e) => {
                              const val = parseInt(e.target.value);
                              setLlmConfig((prev) => prev ? { ...prev, max_tokens: val } : prev);
                            }}
                            onMouseUp={(e) => saveLlmConfig({ max_tokens: parseInt((e.target as HTMLInputElement).value) })}
                            onTouchEnd={(e) => saveLlmConfig({ max_tokens: parseInt((e.target as HTMLInputElement).value) })}
                            className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-purple-500"
                          />
                          <div className="flex justify-between text-[10px] text-slate-600 mt-1">
                            <span>Short (100)</span>
                            <span>Medium (500)</span>
                            <span>Long (4000)</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div>
                      <h3 className="text-sm font-semibold text-purple-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-purple-400" />
                        Text-to-Speech
                      </h3>
                      <div className="space-y-4">
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Voice</label>
                          <div className="grid grid-cols-2 gap-2">
                            {llmConfig.available_tts_voices.map((v) => (
                              <button
                                key={v.id}
                                onClick={() => saveLlmConfig({ tts_voice: v.id })}
                                className={`px-3 py-2 rounded-lg border text-sm transition-all ${
                                  llmConfig.tts_voice === v.id
                                    ? "border-purple-500 bg-purple-500/10 text-white"
                                    : "border-slate-700 bg-slate-800/50 text-slate-300 hover:border-slate-600"
                                }`}
                              >
                                {v.label}
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="bg-slate-700/30 rounded-xl p-4 border border-slate-700">
                      <h4 className="text-sm font-medium text-white mb-2">About LLM Settings</h4>
                      <ul className="text-xs text-slate-400 space-y-1">
                        <li><strong className="text-purple-400">Model</strong> - Controls the AI model used for all agent responses. Higher-quality models produce better arguments but cost more.</li>
                        <li><strong className="text-purple-400">Temperature</strong> - Controls randomness. Lower = more focused and consistent; higher = more creative and varied.</li>
                        <li><strong className="text-purple-400">Max Tokens</strong> - Maximum length of each AI response. Higher values allow longer, more detailed responses.</li>
                        <li><strong className="text-purple-400">Voice</strong> - The TTS voice used for courtroom audio playback.</li>
                      </ul>
                    </div>
                  </>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer */}
      <div className="px-6 py-3 border-t border-slate-700/50 bg-slate-800/50 flex items-center justify-between">
        <button
          onClick={resetAll}
          disabled={isSaving}
          className="px-4 py-1.5 text-sm text-slate-400 hover:text-red-400 transition-colors disabled:opacity-50"
        >
          Reset All to Defaults
        </button>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>
            {team
              ? `3 attorneys + ${team.prosecution_witnesses.length} pros / ${team.defense_witnesses.length} def witnesses, ${team.judges.length} judges`
              : "Loading..."}
          </span>
        </div>
      </div>
    </div>
  );
}
