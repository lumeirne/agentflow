/**
 * WebSocket client for real-time workflow step updates.
 *
 * Connects directly to the backend WS server (bypasses Next.js proxy since
 * HTTP upgrade can't be proxied via Next.js route handlers).
 */

const WS_BASE =
  (process.env.NEXT_PUBLIC_WS_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/^http/, "ws") ||
    "ws://localhost:8000");

export interface StepUpdateEvent {
  event: "step_update";
  run_id: string;
  step_id: string | null;
  status: string | null;
  data: Record<string, unknown>;
}

export interface ApprovalEvent {
  event: "approval_required";
  run_id: string;
  step_id: string;
  status: string;
  data: {
    approval_id: string;
    action: string;
    risk_tier: string;
    preview: Record<string, unknown>;
  };
}

export interface RunCompleteEvent {
  event: "run_complete";
  run_id: string;
  status: string;
  data: { summary: string };
}

export interface ErrorEvent {
  event: "error";
  run_id: string;
  data: { message: string };
}

export interface ProviderActionRequiredEvent {
  event: "provider_action_required";
  run_id: string;
  step_id: string;
  status: string;
  data: {
    provider: string;
    step_id: string;
    step_key: string;
    error: string;
    recoverable: boolean;
    resume_run_id: string;
  };
}

export type WSEvent =
  | StepUpdateEvent
  | ApprovalEvent
  | RunCompleteEvent
  | ErrorEvent
  | ProviderActionRequiredEvent;

const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 2000;

export class RunWebSocket {
  private ws: WebSocket | null = null;
  private runId: string | null = null;
  private retryCount = 0;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionalClose = false;

  private callbacks: {
    onStepUpdate?: (event: StepUpdateEvent) => void;
    onApprovalRequired?: (event: ApprovalEvent) => void;
    onRunComplete?: (event: RunCompleteEvent) => void;
    onError?: (event: ErrorEvent) => void;
    onProviderActionRequired?: (event: ProviderActionRequiredEvent) => void;
    onConnectionError?: (msg: string) => void;
  } = {};

  connect(runId: string): void {
    this.runId = runId;
    this.intentionalClose = false;
    this._open();
  }

  private _open(): void {
    if (!this.runId) return;

    try {
      this.ws = new WebSocket(`${WS_BASE}/ws/runs/${this.runId}`);
    } catch {
      // WebSocket constructor can throw if URL is invalid
      this.callbacks.onConnectionError?.("Invalid WebSocket URL");
      return;
    }

    this.ws.onopen = () => {
      this.retryCount = 0; // reset on successful connection
    };

    this.ws.onmessage = (msg) => {
      try {
        const event: WSEvent = JSON.parse(msg.data);
        switch (event.event) {
          case "step_update":
            this.callbacks.onStepUpdate?.(event as StepUpdateEvent);
            break;
          case "approval_required":
            this.callbacks.onApprovalRequired?.(event as ApprovalEvent);
            break;
          case "run_complete":
            this.callbacks.onRunComplete?.(event as RunCompleteEvent);
            break;
          case "error":
            this.callbacks.onError?.(event as ErrorEvent);
            break;
          case "provider_action_required":
            this.callbacks.onProviderActionRequired?.(event as ProviderActionRequiredEvent);
            break;
        }
      } catch {
        // Silently ignore malformed messages
      }
    };

    this.ws.onerror = () => {
      // onerror is always followed by onclose — handle retry there
      // Only log at debug level to avoid console flooding
      if (process.env.NODE_ENV === "development") {
        console.debug(
          `[WebSocket] Connection error for run ${this.runId} (attempt ${this.retryCount + 1}/${MAX_RETRIES + 1})`
        );
      }
    };

    this.ws.onclose = (ev) => {
      if (this.intentionalClose) return;

      // Normal closure codes (1000, 1001) — don't retry
      if (ev.code === 1000 || ev.code === 1001) return;

      if (this.retryCount < MAX_RETRIES) {
        this.retryCount++;
        const delay = RETRY_DELAY_MS * this.retryCount;
        if (process.env.NODE_ENV === "development") {
          console.debug(
            `[WebSocket] Retrying in ${delay}ms (attempt ${this.retryCount}/${MAX_RETRIES})…`
          );
        }
        this.retryTimer = setTimeout(() => this._open(), delay);
      } else {
        // All retries exhausted — notify consumer silently
        this.callbacks.onConnectionError?.(
          "Could not connect to the backend. Make sure the backend server is running."
        );
      }
    };
  }

  disconnect(): void {
    this.intentionalClose = true;
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    if (this.ws) {
      this.ws.close(1000, "Component unmounted");
      this.ws = null;
    }
  }

  onStepUpdate(cb: (event: StepUpdateEvent) => void): void {
    this.callbacks.onStepUpdate = cb;
  }

  onApprovalRequired(cb: (event: ApprovalEvent) => void): void {
    this.callbacks.onApprovalRequired = cb;
  }

  onRunComplete(cb: (event: RunCompleteEvent) => void): void {
    this.callbacks.onRunComplete = cb;
  }

  onError(cb: (event: ErrorEvent) => void): void {
    this.callbacks.onError = cb;
  }

  onProviderActionRequired(cb: (event: ProviderActionRequiredEvent) => void): void {
    this.callbacks.onProviderActionRequired = cb;
  }

  /** Called when all retries are exhausted or when connection can't be established. */
  onConnectionError(cb: (msg: string) => void): void {
    this.callbacks.onConnectionError = cb;
  }
}
