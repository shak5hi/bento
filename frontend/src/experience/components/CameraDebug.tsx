import { useFrame, useThree } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import { useState } from 'react';

export function CameraDebug() {
  const { camera } = useThree();
  const [info, setInfo] = useState('');

  useFrame(() => {
    setInfo(
      `Camera Position:\n` +
      `x: ${camera.position.x.toFixed(3)}\n` +
      `y: ${camera.position.y.toFixed(3)}\n` +
      `z: ${camera.position.z.toFixed(3)}\n\n` +
      `Camera Rotation:\n` +
      `x: ${camera.rotation.x.toFixed(3)}\n` +
      `y: ${camera.rotation.y.toFixed(3)}\n` +
      `z: ${camera.rotation.z.toFixed(3)}`
    );
  });

  return (
    <Html
      as="div"
      style={{
        position: 'absolute',
        top: '20px',
        left: '20px',
        backgroundColor: 'rgba(0, 0, 0, 0.85)',
        color: '#00ffcc',
        padding: '15px',
        borderRadius: '8px',
        fontFamily: 'monospace',
        fontSize: '14px',
        lineHeight: '1.5',
        whiteSpace: 'pre-wrap',
        pointerEvents: 'none',
        zIndex: 9999,
        border: '1px solid #333'
      }}
    >
      {info}
    </Html>
  );
}
