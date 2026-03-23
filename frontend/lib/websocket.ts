/**
 * WebSocket client for real-time workflow step updates.
 */

const WS_BASE = process.env.NEXT_PUBLIC_API_BASE_URL?.replace("http", "ws") || "ws://localhost:8000";

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

export type WSEvent = StepUpdateEvent | ApprovalEvent | RunCompleteEvent | ErrorEvent;

export class RunWebSocket {
  private ws: WebSocket | null = null;
  private callbacks: {
    onStepUpdate?: (event: StepUpdateEvent) => void;
    onApprovalRequired?: (event: ApprovalEvent) => void;
    onRunComplete?: (event: RunCompleteEvent) => void;
    onError?: (event: ErrorEvent) => void;
  } = {};

  connect(runId: string): void {
    if (this.ws) {
      this.disconnect();
    }

    this.ws = new WebSocket(`${WS_BASE}/ws/runs/${runId}`);

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
        }
      } catch (err) {
        console.error("Failed to parse WebSocket message:", err);
      }
    };

    this.ws.onerror = (err) => {
      console.error("WebSocket error:", err);
    };

    this.ws.onclose = () => {
      console.log("WebSocket closed for run:", runId);
    };
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
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
}
