"use client";

import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  label?: string;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="glass rounded-none p-6 text-center">
          <div className="mono text-xs text-[var(--red)] mb-2">
            RENDER ERROR{this.props.label ? ` in ${this.props.label}` : ""}
          </div>
          <div className="mono text-[10px] text-[var(--green-dark)] mb-4 max-w-md mx-auto break-all">
            {this.state.error?.message}
          </div>
          <button
            onClick={() => this.setState({ hasError: false })}
            className="mono text-[10px] text-[var(--green-dark)] hover:text-[var(--green)] border border-[var(--panel-border)] hover:border-[var(--green)] px-4 py-1.5 transition-colors"
          >
            [ RETRY ]
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
