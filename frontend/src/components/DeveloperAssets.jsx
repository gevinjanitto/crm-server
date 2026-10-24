import React from 'react';
import { Code2, GitBranch, Terminal, Check } from 'lucide-react';
import './developer-assets.css';

export const DeveloperAssets = () => (
  <div className="developer-assets" aria-hidden="true" data-testid="login-developer-assets">
    <div className="developer-terminal" data-testid="login-developer-terminal">
      <div className="developer-terminal-top"><Terminal size={13}/><span>maiharta.dev</span><i/><i/><i/></div>
      <code><span className="dev-code-muted">$</span> build something<br/><span className="dev-code-accent">great.</span><b className="dev-cursor">_</b></code>
      <div className="developer-terminal-bottom"><Check size={12}/><span>ideas → digital experiences</span></div>
    </div>
    <div className="developer-branch" data-testid="login-developer-branch"><GitBranch size={16}/><span>idea<span className="dev-code-muted"> / </span>develop<span className="dev-code-muted"> / </span>deliver</span></div>
    <div className="developer-code-mark" data-testid="login-developer-code"><Code2 size={23}/><span>crafting software</span></div>
  </div>
);