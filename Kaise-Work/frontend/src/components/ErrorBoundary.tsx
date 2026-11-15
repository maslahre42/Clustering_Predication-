import { Component, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Panel name shown in the fallback so operators know which view failed. */
  label: string;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Containment for render errors (blank-page bug, 2026-11-14): a view that
 * throws degrades to a visible, retryable message on that view only — the
 * rest of the dashboard stays interactive. Retry clears the error and
 * re-renders the subtree; if it throws again the fallback returns (never a
 * blank page).
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error): void {
    // Visible in devtools; never swallowed silently.
    console.error(`View "${this.props.label}" failed to render:`, error);
  }

  handleRetry = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    const { error } = this.state;
    if (error === null) {
      return this.props.children;
    }
    return (
      <div
        className="rounded-md border border-red-300 bg-red-50 px-4 py-3"
        data-testid="error-boundary"
        role="alert"
      >
        <p className="text-sm font-semibold text-red-800">
          View “{this.props.label}” failed to render — the rest of the dashboard is unaffected.
        </p>
        <p className="mt-1 break-words font-mono text-xs text-red-700">{error.message}</p>
        <button
          type="button"
          onClick={this.handleRetry}
          className="mt-2 rounded bg-red-700 px-3 py-1 text-xs font-medium text-white hover:bg-red-800"
          data-testid="error-boundary-retry"
        >
          Retry
        </button>
      </div>
    );
  }
}
