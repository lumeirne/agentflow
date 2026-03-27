/**
 * Zustand store — global state for AgentFlow frontend.
 */
import { create } from "zustand";

export interface UserProfile {
  id: string;
  email: string;
  name: string | null;
  auth0_user_id: string;
}

export interface ConnectedService {
  id: string;
  provider: string;
  status: string;
  external_account_id?: string;
}

export interface WorkflowStep {
  id: string;
  run_id: string;
  step_key: string;
  step_type: string;
  risk_tier: string;
  status: string;
  input_json?: string;
  output_json?: string;
  error_text?: string;
  started_at?: string;
  completed_at?: string;
}

export interface WorkflowRun {
  id: string;
  prompt: string;
  status: string;
  result_summary?: string;
  created_at: string;
  updated_at: string;
  steps?: WorkflowStep[];
}

export interface PendingApproval {
  id: string;
  run_id: string;
  step_id: string;
  approval_type: string;
  preview_json?: string;
  status: string;
}

export interface ClarificationPrompt {
  type: "repo_selection" | "other";
  originalPrompt: string;
  runId: string;
  message: string;
}

/** State for an in-progress provider reconnect triggered from a run page. */
export interface ProviderRecoveryState {
  /** The run that is waiting for the connection. */
  runId: string;
  /** Logical provider key: 'github' | 'google' | 'slack' */
  provider: string;
  /** Step that failed and needs to be retried. */
  stepId: string;
  stepKey: string;
  /**
   * UI phase:
   *  missing_provider     — action_required event received, prompt shown
   *  connecting_provider  — user clicked Connect, redirect in progress
   *  connection_restored  — callback returned success, about to resume
   *  resuming_step        — POST /resume sent, waiting for executor
   *  resume_failed        — resume call failed
   */
  phase:
    | "missing_provider"
    | "connecting_provider"
    | "connection_restored"
    | "resuming_step"
    | "resume_failed";
}

interface AppState {
  // User
  currentUser: UserProfile | null;
  setCurrentUser: (user: UserProfile | null) => void;

  // Connected services
  connectedServices: ConnectedService[];
  setConnectedServices: (services: ConnectedService[]) => void;

  // Active run
  activeRun: WorkflowRun | null;
  setActiveRun: (run: WorkflowRun | null) => void;

  // Active run steps (updated in real time)
  activeSteps: WorkflowStep[];
  setActiveSteps: (steps: WorkflowStep[]) => void;
  updateStep: (stepId: string, updates: Partial<WorkflowStep>) => void;

  // Pending approvals
  pendingApprovals: PendingApproval[];
  setPendingApprovals: (approvals: PendingApproval[]) => void;
  addApproval: (approval: PendingApproval) => void;
  removeApproval: (approvalId: string) => void;

  // Runs history
  runs: WorkflowRun[];
  setRuns: (runs: WorkflowRun[]) => void;

  // Clarification prompts (e.g., repo selection needed)
  clarification: ClarificationPrompt | null;
  setClarification: (clarification: ClarificationPrompt | null) => void;

  // Provider recovery (in-run connect flow)
  providerRecovery: ProviderRecoveryState | null;
  setProviderRecovery: (state: ProviderRecoveryState | null) => void;
  updateProviderRecoveryPhase: (phase: ProviderRecoveryState["phase"]) => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentUser: null,
  setCurrentUser: (user) => set({ currentUser: user }),

  connectedServices: [],
  setConnectedServices: (services) => set({ connectedServices: services }),

  activeRun: null,
  setActiveRun: (run) => set({ activeRun: run }),

  activeSteps: [],
  setActiveSteps: (steps) => set({ activeSteps: steps }),
  updateStep: (stepId, updates) =>
    set((state) => ({
      activeSteps: state.activeSteps.map((s) =>
        s.id === stepId ? { ...s, ...updates } : s
      ),
    })),

  pendingApprovals: [],
  setPendingApprovals: (approvals) => set({ pendingApprovals: approvals }),
  addApproval: (approval) =>
    set((state) => ({
      pendingApprovals: [...state.pendingApprovals, approval],
    })),
  removeApproval: (approvalId) =>
    set((state) => ({
      pendingApprovals: state.pendingApprovals.filter((a) => a.id !== approvalId),
    })),

  runs: [],
  setRuns: (runs) => set({ runs }),

  clarification: null,
  setClarification: (clarification) => set({ clarification }),

  providerRecovery: null,
  setProviderRecovery: (state) => set({ providerRecovery: state }),
  updateProviderRecoveryPhase: (phase) =>
    set((state) =>
      state.providerRecovery
        ? { providerRecovery: { ...state.providerRecovery, phase } }
        : {}
    ),
}));
