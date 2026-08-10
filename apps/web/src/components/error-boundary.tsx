'use client';

import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Button } from '@researchforge/ui';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('UI error boundary', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="mx-auto flex min-h-[50vh] max-w-lg flex-col items-center justify-center gap-4 px-4 text-center">
          <h2 className="rf-display text-3xl">Something went wrong</h2>
          <p className="text-[var(--rf-muted)]">
            Reload the page to continue. Your guest draft remains in this browser if it was saved
            locally.
          </p>
          <Button type="button" onClick={() => this.setState({ hasError: false })}>
            Try again
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
