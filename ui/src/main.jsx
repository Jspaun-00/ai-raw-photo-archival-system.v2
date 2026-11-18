import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';

class RootErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('RootErrorBoundary caught unhandled application error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReset = () => {
    try {
      localStorage.removeItem('mr_darkroom_active_catalog');
      localStorage.removeItem('mrdarkroom_guide_width');
      localStorage.removeItem('mrdarkroom_guide_scale');
    } catch (_) {}
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            minHeight: '100vh',
            width: '100vw',
            backgroundColor: '#090b10',
            color: '#f87171',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            padding: '36px',
            boxSizing: 'border-box',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 999999,
          }}
        >
          <div
            style={{
              maxWidth: '800px',
              width: '100%',
              background: '#111827',
              border: '2px solid #ef4444',
              borderRadius: '16px',
              padding: '28px',
              boxShadow: '0 25px 60px rgba(0, 0, 0, 0.85)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
              <span style={{ fontSize: '28px' }}>⚠️</span>
              <div>
                <h1 style={{ margin: 0, fontSize: '20px', fontWeight: 800, color: '#fbbf24' }}>
                  MR Darkroom Studio — Recovery Screen
                </h1>
                <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: '#94a3b8' }}>
                  An unexpected render exception was caught by the studio root boundary.
                </p>
              </div>
            </div>

            <div
              style={{
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: '8px',
                padding: '12px 16px',
                color: '#fca5a5',
                fontSize: '14px',
                fontWeight: 700,
                marginBottom: '16px',
              }}
            >
              {String(this.state.error?.message || this.state.error)}
            </div>

            {this.state.error?.stack && (
              <pre
                style={{
                  background: '#0a0d14',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '8px',
                  padding: '12px 14px',
                  fontSize: '11px',
                  color: '#cbd5e1',
                  overflowX: 'auto',
                  maxHeight: '260px',
                  whiteSpace: 'pre-wrap',
                  marginBottom: '20px',
                }}
              >
                {this.state.error.stack}
              </pre>
            )}

            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                type="button"
                onClick={() => window.location.reload()}
                style={{
                  padding: '10px 20px',
                  background: '#3b82f6',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '8px',
                  fontWeight: 700,
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
              >
                🔄 Reload App
              </button>
              <button
                type="button"
                onClick={this.handleReset}
                style={{
                  padding: '10px 20px',
                  background: 'rgba(255, 255, 255, 0.1)',
                  color: '#fbbf24',
                  border: '1px solid rgba(251, 191, 36, 0.4)',
                  borderRadius: '8px',
                  fontWeight: 700,
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
              >
                🧹 Reset Preferences &amp; Reload
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function mount() {
  const rootEl = document.getElementById('root');
  if (!rootEl) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', mount);
    } else {
      setTimeout(mount, 10);
    }
    return;
  }
  try {
    const root = ReactDOM.createRoot(rootEl);
    root.render(
      <React.StrictMode>
        <RootErrorBoundary>
          <App />
        </RootErrorBoundary>
      </React.StrictMode>
    );
  } catch (err) {
    console.error('Failed to render MR Darkroom root:', err);
    rootEl.innerHTML = `<div style="padding: 24px; color: #f87171; font-family: monospace; background: #0f172a; height: 100%;"><h2 style="color: #fbbf24;">MR Darkroom Studio - Startup Error</h2><pre>${String(err?.stack || err)}</pre></div>`;
  }
}

mount();
