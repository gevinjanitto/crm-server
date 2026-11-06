import React from 'react';
import { CodeLoader } from './CodeLoader';

export const LoadingState = () => (
  <div className="content-loading workspace-loading code-loading-state" data-testid="content-loading" role="status" aria-live="polite" aria-busy="true">
    <CodeLoader />
    <div className="loading-caption">
      <span data-testid="loading-caption">Memuat data...</span>
    </div>
    <div className="code-loading-trail" aria-hidden="true"><i /><i /><i /></div>
  </div>
);