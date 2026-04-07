import React from 'react';

interface ConnectionStatusProps {
  connected: boolean;
}

export const ConnectionStatus: React.FC<ConnectionStatusProps> = ({ connected }) => {
  return (
    <div style={styles.wrapper}>
      <div
        style={{
          ...styles.dot,
          backgroundColor: connected ? '#22c55e' : '#ef4444',
          boxShadow: connected
            ? '0 0 8px #22c55e88'
            : '0 0 8px #ef444488',
          animation: connected ? 'none' : 'pulse 1.4s infinite',
        }}
      />
      <span style={{ ...styles.text, color: connected ? '#86efac' : '#fca5a5' }}>
        {connected ? 'Connected' : 'Disconnected'}
      </span>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: 'flex',
    alignItems: 'center',
    gap: 7,
    background: 'rgba(0,0,0,0.55)',
    backdropFilter: 'blur(10px)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 20,
    padding: '4px 12px',
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: 0.5,
    userSelect: 'none',
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    flexShrink: 0,
    transition: 'background-color 0.3s',
  },
  text: {
    transition: 'color 0.3s',
  },
};

export default ConnectionStatus;
