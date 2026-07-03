import fs from 'fs';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

// Setup mock browser environment for GLTFLoader
global.self = global;
global.window = global;
global.document = {
  createElementNS: () => {
    return {
      style: {},
      getContext: () => null
    };
  }
};

async function parse() {
  const data = fs.readFileSync('public/models/bentocomponents.glb');
  const buffer = new Uint8Array(data).buffer;
  
  // We can't easily parse binary GLB in node without a dedicated loader that supports Node.js
  // Let's just search for strings inside the binary to see what node names are there
  const text = data.toString('utf-8');
  
  // Extract all strings that look like typical node names
  const matches = text.match(/[A-Za-z0-9_]{3,20}/g);
  
  const names = [...new Set(matches)];
  console.log("Found strings in GLB:");
  const interesting = names.filter(n => 
    n.toLowerCase().includes('cucu') || 
    n.toLowerCase().includes('sushi') || 
    n.toLowerCase().includes('egg') || 
    n.toLowerCase().includes('fish') ||
    n.toLowerCase().includes('skew') ||
    n.toLowerCase().includes('mesh') ||
    n.toLowerCase().includes('node')
  );
  console.log(interesting);
}

parse();
