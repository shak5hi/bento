import * as THREE from 'three';
import React from 'react';

// Shared lid ref — lives outside the component so GSAP can access it
// from any file without circular deps
export const lidRef = React.createRef<THREE.Group>();
