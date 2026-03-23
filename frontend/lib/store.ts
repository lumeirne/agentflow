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
}));
