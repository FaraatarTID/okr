import React from 'react';

interface SimpleModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export function SimpleModal({ isOpen, onClose }: SimpleModalProps) {
    if (!isOpen) return null;

    return (
        <div 
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                width: '100vw',
                height: '100vh',
                backgroundColor: 'rgba(0, 0, 0, 0.5)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 9999
            }}
            onClick={onClose}
        >
            <div 
                style={{
                    backgroundColor: 'white',
                    padding: '20px',
                    borderRadius: '8px',
                    minWidth: '300px',
                    color: 'black'
                }}
                onClick={e => e.stopPropagation()}
            >
                <h2 style={{ fontSize: '20px', fontWeight: 'bold', marginBottom: '10px' }}>Test Modal</h2>
                <p>If you can see this, the modal logic is working.</p>
                <button 
                    onClick={onClose}
                    style={{
                        marginTop: '20px',
                        padding: '8px 16px',
                        backgroundColor: 'blue',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer'
                    }}
                >
                    Close
                </button>
            </div>
        </div>
    );
}
