import { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import { ContactShadows, useGLTF, useTexture } from '@react-three/drei';
import { createPortal, useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { heroScroll } from '../scrollState';
import { COMPARTMENTS, compartmentTargets } from '../scene3d';
import { FLOOR, FoodItems } from '../food/Foods';
import logoSrc from '../../assets/lightlogo.png';

/*
 * Lid choreography (scene-local units, driven by heroScroll.rawProgress 0 → 1):
 *   unseal  — lifts straight up off the rim
 *   arc     — rises, swings over to the right while tilting like a page turning
 *   land    — comes down flat on the table beside the box, with a soft settle
 * A smooth spline + easing replaces the linear Blender clip, so it reads as one motion
 * and plays back identically when the lid closes again.
 */
const LOGO_ASPECT = 1441 / 388; // lightlogo.png
const LID_REST_Y = 0.082;
const TABLE_Y = -0.582; // underside of the tray
const LID_HALF_THICKNESS = 0.089;
const LID_LAND = new THREE.Vector3(4.45, TABLE_Y + LID_HALF_THICKNESS, -0.12);

const lidPath = new THREE.CatmullRomCurve3(
  [
    new THREE.Vector3(0, LID_REST_Y, 0),
    new THREE.Vector3(0.02, 0.62, 0.02),
    new THREE.Vector3(1.5, 1.7, -0.05),
    new THREE.Vector3(3.55, 1.25, -0.12),
    new THREE.Vector3(4.4, 0.05, -0.12),
    LID_LAND,
  ],
  false,
  'centripetal',
);

const smootherstep = (t: number) => t * t * t * (t * (t * 6 - 15) + 10);
const clamp01 = (t: number) => Math.min(1, Math.max(0, t));
const bump = (t: number, a: number, b: number) => {
  const u = clamp01((t - a) / (b - a));
  return Math.sin(u * Math.PI);
};

const _q = new THREE.Quaternion();
const _e = new THREE.Euler();

/** `ajar` poses the lid half open (login page) instead of following the landing page's scroll. */
export function BentoModel({ ajar = false }: { ajar?: boolean } = {}) {
  const { scene } = useGLTF('/models/bento.glb');
  const logoTexture = useTexture(logoSrc);
  const lidRef = useRef<THREE.Object3D | null>(null);
  const trayRef = useRef<THREE.Object3D | null>(null);

  // Captured before the food is portalled into the tray, so materials only touch Blender's meshes.
  const { lid, tray, boxMeshes } = useMemo(() => {
    let lid: THREE.Object3D | null = null;
    let tray: THREE.Object3D | null = null;
    const boxMeshes: THREE.Mesh[] = [];
    scene.traverse((child) => {
      const n = child.name.toLowerCase();
      if (n === 'lid') lid = child;
      if (n === 'trey' || n === 'tray') tray = child;
      if ((child as THREE.Mesh).isMesh) boxMeshes.push(child as THREE.Mesh);
    });
    return { lid: lid as THREE.Object3D | null, tray: tray as THREE.Object3D | null, boxMeshes };
  }, [scene]);

  // Lacquerware: deep red tray, near-black lid, both with a clear lacquer coat.
  useEffect(() => {
    const trayMat = new THREE.MeshPhysicalMaterial({ color: '#6e1f08', roughness: 0.5, clearcoat: 0.55, clearcoatRoughness: 0.3, envMapIntensity: 0.55 });
    const lidMat = new THREE.MeshPhysicalMaterial({ color: '#1b1917', roughness: 0.34, clearcoat: 1, clearcoatRoughness: 0.14, envMapIntensity: 0.8 });
    for (const mesh of boxMeshes) {
      const isLid = mesh === lid || mesh.parent === lid;
      mesh.material = isLid ? lidMat : trayMat;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
    }
    lidRef.current = lid;
    trayRef.current = tray;
    return () => {
      trayMat.dispose();
      lidMat.dispose();
    };
  }, [boxMeshes, lid, tray]);

  // Publish where each compartment is in world space, for the camera's close-ups.
  const groupRef = useRef<THREE.Group>(null);
  useLayoutEffect(() => {
    if (!tray || !groupRef.current) return;
    groupRef.current.updateWorldMatrix(true, true);
    const scale = new THREE.Vector3();
    tray.getWorldScale(scale);
    COMPARTMENTS.forEach((c, i) => {
      compartmentTargets[i].center.set(c.x, FLOOR + 0.16, c.z);
      tray.localToWorld(compartmentTargets[i].center);
      compartmentTargets[i].size = Math.max(c.w, c.d) * scale.x;
    });
  }, [tray]);

  useFrame(({ clock }) => {
    const lidObj = lidRef.current;
    if (!lidObj) return;
    if (ajar) {
      // hinged up on the far-left edge, breathing a little so it feels alive
      const breathe = Math.sin(clock.elapsedTime * 0.9) * 0.025;
      lidObj.position.set(0.55, LID_REST_Y + 0.85 + breathe, 0.05);
      _e.set(0.06, -0.1, -0.55 - breathe, 'YXZ');
      lidObj.quaternion.copy(_q.setFromEuler(_e));
      return;
    }
    const p = clamp01(heroScroll.rawProgress);
    const t = smootherstep(p);

    lidObj.position.copy(lidPath.getPoint(t));
    // settle: a small, fast-decaying bounce as it touches down
    const land = clamp01((p - 0.9) / 0.1);
    if (land > 0) lidObj.position.y += Math.sin(land * Math.PI) * 0.035 * (1 - land);

    const tiltZ = -0.62 * bump(t, 0.12, 0.92); // page-turn tilt toward the landing side
    const tiltX = 0.08 * bump(t, 0.2, 0.75); // a breath of lift at the near edge
    const yaw = -0.16 * smootherstep(clamp01((t - 0.35) / 0.65)); // comes to rest slightly turned
    _e.set(tiltX, yaw, tiltZ, 'YXZ');
    lidObj.quaternion.copy(_q.setFromEuler(_e));
  });

  return (
    <group ref={groupRef} position={[0, 0.8, 0]} rotation={[0, Math.PI / 6, 0]} scale={1.8}>
      <primitive object={scene} />
      {tray && createPortal(<FoodItems />, tray)}
      {lid &&
        createPortal(
          // The logo PNG is white-on-black: use it as an alpha mask so only the lettering is printed.
          <mesh position={[0, 0.0875, 0]} rotation={[-Math.PI / 2, 0, 0]} renderOrder={1}>
            <planeGeometry args={[1.7, 1.7 / LOGO_ASPECT]} />
            <meshStandardMaterial color="#e9e1d4" alphaMap={logoTexture} transparent depthWrite={false} polygonOffset polygonOffsetFactor={-2} roughness={0.55} />
          </mesh>,
          lid,
        )}
      {ajar ? (
        <ContactShadows position={[0, TABLE_Y - 0.002, 0]} scale={4.6} resolution={512} blur={3} opacity={0.35} far={0.8} color="#3a0f00" />
      ) : (
        <ContactShadows position={[1.4, TABLE_Y - 0.002, 0]} width={13} height={8} scale={[13, 8]} resolution={512} blur={2.6} opacity={0.5} far={2.2} color="#3a0f00" />
      )}
    </group>
  );
}

useGLTF.preload('/models/bento.glb');
