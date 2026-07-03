import { useMemo } from 'react';
import { useTexture } from '@react-three/drei';
import * as THREE from 'three';

import comp1Svg from '../../assets/compartment1.svg';
import comp2Svg from '../../assets/compartment2.svg';
import comp3Svg from '../../assets/compartment3.svg';
import comp4Svg from '../../assets/compartment4.svg';
import comp5Svg from '../../assets/compartment5.svg';

interface TargetBounds {
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
  floorY: number;
}

interface FoodItemSVGProps {
  svgUrl: string;
  name: string;
  targetBounds: TargetBounds;
  count?: number;
  innerRef?: React.Ref<THREE.Group>;
}

function useVisibleBounds(image: HTMLImageElement | undefined) {
  return useMemo(() => {
    if (!image || !image.width || !image.height) return null;
    
    const canvas = document.createElement('canvas');
    canvas.width = image.width;
    canvas.height = image.height;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return null;
    
    // Draw the image to read its pixels
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    
    try {
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const data = imageData.data;
      
      let minX = canvas.width, minY = canvas.height, maxX = 0, maxY = 0;
      let found = false;
      
      for (let y = 0; y < canvas.height; y++) {
        for (let x = 0; x < canvas.width; x++) {
          const alpha = data[(y * canvas.width + x) * 4 + 3];
          if (alpha > 5) { // Threshold for visibility
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
            found = true;
          }
        }
      }
      
      if (!found) return null;
      
      return {
        width: maxX - minX,
        height: maxY - minY,
        centerX: (minX + maxX) / 2,
        centerY: (minY + maxY) / 2,
        imgW: canvas.width,
        imgH: canvas.height
      };
    } catch (e) {
      console.warn("Could not read image data for bounds calculation:", e);
      return null;
    }
  }, [image]);
}

const FOOD_CONFIGS: Record<string, { pos: [number, number, number]; rot: [number, number, number]; scale: [number, number] }> = {
  'Compartment 1': {
    pos: [0.02, 0.25, -0.01],
    rot: [-89, 180, -157],
    scale: [1.27, 1.46]
  },
  'Compartment 2': {
    pos: [0.00, 0.03, 0.03],
    rot: [93, 180, -157],
    scale: [1.18, 1.25]
  },
  'Compartment 3': {
    pos: [-0.01, 0.16, 0.05],
    rot: [-86, 2, 27],
    scale: [1.21, 1.45]
  },
  'Compartment 4': {
    pos: [-0.01, 0.11, -0.01],
    rot: [-90, 0, 22],
    scale: [1.12, 1.34]
  },
  'Compartment 5': {
    pos: [0.01, 0.09, 0.16],
    rot: [-84, 2, 22],
    scale: [1.23, 1.44]
  }
};

function FoodItemSVG({ svgUrl, name, targetBounds, count = 1, innerRef }: FoodItemSVGProps) {
  const texture = useTexture(svgUrl);
  // Ensure proper color rendering
  texture.colorSpace = THREE.SRGBColorSpace;
  const visibleBounds = useVisibleBounds(texture.image as HTMLImageElement);
  
  const transforms = useMemo(() => {
    if (!texture.image || !visibleBounds) return [];
    
    const config = FOOD_CONFIGS[name] || { pos: [0,0,0], rot: [-90,0,0], scale: [1,1] };
    
    const img = texture.image as HTMLImageElement;
    const aspect = img.width / img.height;
    
    // Plane geometry uses aspect as width and 1 as depth (height in 2D)
    const rawW = aspect;
    const rawD = 1;

    // Available space
    const compW = targetBounds.maxX - targetBounds.minX;
    const compD = targetBounds.maxZ - targetBounds.minZ;
    
    // 95% of the compartment area
    const usableW = compW * 0.95;
    const usableD = compD * 0.95;

    // Calculate how much of the raw plane is actually visible
    const visibleWorldW = rawW * (visibleBounds.width / visibleBounds.imgW);
    const visibleWorldD = rawD * (visibleBounds.height / visibleBounds.imgH);

    // Grid layout calculation
    let cols = 1;
    let rows = 1;
    
    if (count > 1) {
      let bestFitScore = -1;
      const visibleAspect = visibleWorldW / visibleWorldD;
      
      for (let c = 1; c <= count; c++) {
        const r = Math.ceil(count / c);
        const cellW = usableW / c;
        const cellD = usableD / r;
        const cellAspect = cellW / cellD;
        
        const score = cellAspect > visibleAspect ? visibleAspect / cellAspect : cellAspect / visibleAspect;
        
        if (score > bestFitScore) {
          bestFitScore = score;
          cols = c;
          rows = r;
        }
      }
    }

    const cellW = usableW / cols;
    const cellD = usableD / rows;
    
    // Scale image so its VISIBLE bounds fit precisely inside its assigned grid cell
    const scaleX = cellW / visibleWorldW;
    const scaleZ = cellD / visibleWorldD;
    const scale = Math.min(scaleX, scaleZ);

    // Calculate offset required to center the visible artwork (not the raw canvas)
    const uvOffsetX = (visibleBounds.centerX / visibleBounds.imgW) - 0.5;
    const uvOffsetY = (visibleBounds.centerY / visibleBounds.imgH) - 0.5;
    
    const localOffsetX = uvOffsetX * rawW;
    // On a plane rotated -90 on X, local Y maps to world -Z (since bottom of image is +Z)
    const localOffsetZ = uvOffsetY * rawD;

    const scaledOffsetX = localOffsetX * scale;
    const scaledOffsetZ = localOffsetZ * scale;

    const compCenterX = (targetBounds.maxX + targetBounds.minX) / 2;
    const compCenterZ = (targetBounds.maxZ + targetBounds.minZ) / 2;
    const posY = targetBounds.floorY + 0.005;
    
    const startX = compCenterX - usableW / 2 + cellW / 2;
    const startZ = compCenterZ - usableD / 2 + cellD / 2;

    const items = [];
    for (let i = 0; i < count; i++) {
      const col = i % cols;
      const row = Math.floor(i / cols);
      
      // Target center of the cell
      const targetX = startX + col * cellW;
      const targetZ = startZ + row * cellD;
      
      // Subtract the artwork's center offset so the visible center lands exactly on the target
      // Apply config offsets
      const posX = targetX - scaledOffsetX + config.pos[0];
      const posZ = targetZ - scaledOffsetZ + config.pos[2];
      const finalPosY = posY + config.pos[1];
      
      const finalRotX = config.rot[0] * (Math.PI / 180);
      const finalRotY = config.rot[1] * (Math.PI / 180);
      const finalRotZ = config.rot[2] * (Math.PI / 180);

      items.push({
        scale: [scale * config.scale[0], scale * config.scale[1], 1] as [number, number, number],
        position: [posX, finalPosY, posZ] as [number, number, number],
        rotation: [finalRotX, finalRotY, finalRotZ] as [number, number, number]
      });
    }

    return items;
  }, [texture, targetBounds, count, visibleBounds, name]);

  if (!texture.image || transforms.length === 0) return null;

  return (
    <group ref={innerRef}>
      {transforms.map((transform, i) => (
        <mesh key={i} name={`food_${name}_${i}`} position={transform.position} scale={transform.scale} rotation={transform.rotation}>
          <planeGeometry args={[(texture.image as HTMLImageElement).width / (texture.image as HTMLImageElement).height, 1]} />
          <meshBasicMaterial 
            map={texture} 
            transparent 
            alphaTest={0.5}
            side={THREE.DoubleSide} 
            depthWrite={false} 
            toneMapped={false} 
          />
        </mesh>
      ))}
    </group>
  );
}

export interface FoodItemsProps {
  refs?: {
    comp1?: React.RefObject<THREE.Group>;
    comp2?: React.RefObject<THREE.Group>;
    comp3?: React.RefObject<THREE.Group>;
    comp4?: React.RefObject<THREE.Group>;
    comp5?: React.RefObject<THREE.Group>;
  };
}

export function FoodItems({ refs }: FoodItemsProps) {
  const comp1Bounds = useMemo(() => ({ minX: -1.84, maxX: 0.26, minZ: 0.02, maxZ: 1.48, floorY: -0.29 }), []);
  const comp2Bounds = useMemo(() => ({ minX: 0.31, maxX: 1.84, minZ: 0.02, maxZ: 1.48, floorY: -0.29 }), []);
  const comp3Bounds = useMemo(() => ({ minX: -0.39, maxX: 0.60, minZ: -1.48, maxZ: 0.00, floorY: -0.29 }), []);
  const comp4Bounds = useMemo(() => ({ minX: -1.84, maxX: -0.44, minZ: -1.48, maxZ: 0.00, floorY: -0.29 }), []);
  const comp5Bounds = useMemo(() => ({ minX: 0.65, maxX: 1.84, minZ: -1.48, maxZ: 0.00, floorY: -0.29 }), []);

  return (
    <group name="FoodItems">
      <FoodItemSVG name="Compartment 1" svgUrl={comp1Svg} targetBounds={comp1Bounds} innerRef={refs?.comp1} />
      <FoodItemSVG name="Compartment 2" svgUrl={comp2Svg} targetBounds={comp2Bounds} innerRef={refs?.comp2} />
      <FoodItemSVG name="Compartment 3" svgUrl={comp3Svg} targetBounds={comp3Bounds} innerRef={refs?.comp3} />
      <FoodItemSVG name="Compartment 4" svgUrl={comp4Svg} targetBounds={comp4Bounds} innerRef={refs?.comp4} />
      <FoodItemSVG name="Compartment 5" svgUrl={comp5Svg} targetBounds={comp5Bounds} innerRef={refs?.comp5} />
    </group>
  );
}

useTexture.preload(comp1Svg);
useTexture.preload(comp2Svg);
useTexture.preload(comp3Svg);
useTexture.preload(comp4Svg);
useTexture.preload(comp5Svg);
