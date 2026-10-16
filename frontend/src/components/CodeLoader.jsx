import React from 'react';

// Original, self-contained code animation. No licensed Lottie file or remote player.
export const CodeLoader = ({ testId = 'loading-code-animation' }) => (
  <svg className="code-loader" viewBox="0 0 240 166" fill="none" aria-hidden="true" focusable="false" data-testid={testId}>
    <path d="M36 144H204" stroke="#dce6f6" strokeWidth="2" strokeLinecap="round" />
    <g className="code-loader-window">
      <rect x="43" y="28" width="154" height="108" rx="8" fill="#dde9fc" opacity=".55" transform="translate(0 5)" />
      <rect x="43" y="28" width="154" height="108" rx="8" fill="#fbfdff" stroke="#b9cdee" strokeWidth="1.5" />
      <path d="M43 51H197" stroke="#d5e2f5" strokeWidth="1.5" />
      <circle cx="55" cy="40" r="2.5" fill="#2c63e8" />
      <circle cx="65" cy="40" r="2.5" fill="#38aaa8" />
      <circle cx="75" cy="40" r="2.5" fill="#b8cbe9" />
      <path d="M166 39H184" stroke="#d5e2f5" strokeWidth="3" strokeLinecap="round" />
      <path className="code-loader-bracket left" d="M69 73L59 83L69 93" stroke="#2c63e8" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
      <path className="code-loader-bracket right" d="M171 73L181 83L171 93" stroke="#2c63e8" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
      <g strokeLinecap="round" strokeWidth="4" className="code-loader-lines">
        <path className="code-loader-line line-one" pathLength="1" d="M87 71H122" stroke="#2c63e8" />
        <path className="code-loader-line line-two" pathLength="1" d="M131 71H151" stroke="#8cacde" />
        <path className="code-loader-line line-three" pathLength="1" d="M94 83H147" stroke="#2da7a0" />
        <path className="code-loader-line line-four" pathLength="1" d="M87 95H116" stroke="#8cacde" />
        <path className="code-loader-line line-five" pathLength="1" d="M125 95H140" stroke="#2c63e8" />
      </g>
      <path className="code-loader-caret" d="M151 92V100" stroke="#2da7a0" strokeWidth="2.5" strokeLinecap="round" />
      <rect x="60" y="115" width="80" height="3" rx="1.5" fill="#e5edf9" />
      <rect className="code-loader-track" x="60" y="115" width="24" height="3" rx="1.5" fill="#4e84ec" />
    </g>
    <g className="code-loader-terminal">
      <rect x="165" y="110" width="48" height="32" rx="7" fill="#2c63e8" />
      <path d="M176 120L182 126L176 132" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path className="code-loader-terminal-caret" d="M189 132H199" stroke="#b4f2e9" strokeWidth="2" strokeLinecap="round" />
    </g>
  </svg>
);