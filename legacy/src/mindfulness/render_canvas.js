/**
 * Generative Art Renderer using pure node-canvas
 * Renders particle flow fields for Mindfulness videos
 * 
 * Usage: node render_canvas.js <output_dir> <duration_seconds> <mood> [audio_data_path]
 */

const fs = require('fs');
const path = require('path');
const { createCanvas } = require('canvas');

// --- Argument Parsing ---
const args = process.argv.slice(2);
const outputDir = args[0] || './temp/frames';
const duration = parseFloat(args[1] || 5.0);
const mood = args[2] || 'calm';
const audioDataPath = args[3];

const fps = 30;
const width = 1080;
const height = 1920;
const totalFrames = Math.floor(duration * fps);

// Load audio reactivity data
let audioData = [];
if (audioDataPath && fs.existsSync(audioDataPath)) {
    const raw = fs.readFileSync(audioDataPath);
    audioData = JSON.parse(raw);
}

// Ensure output directory
if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
}

// --- Color Palettes ---
const palettes = {
    calm: {
        bg: [10, 20, 35],
        colors: [
            [100, 200, 255, 1.0],
            [0, 180, 220, 0.9],
            [200, 255, 255, 0.8]
        ]
    },
    deep: {
        bg: [8, 5, 20],
        colors: [
            [140, 80, 200, 1.0],
            [80, 40, 150, 0.9],
            [220, 120, 255, 0.8]
        ]
    },
    nature: {
        bg: [10, 30, 15],
        colors: [
            [120, 255, 120, 1.0],
            [80, 220, 160, 0.9],
            [180, 255, 180, 0.8]
        ]
    },
    sunset: {
        bg: [30, 15, 20],
        colors: [
            [255, 180, 80, 1.0],
            [255, 120, 100, 0.9],
            [255, 220, 120, 0.8]
        ]
    },
    ocean: {
        bg: [8, 20, 35],
        colors: [
            [0, 220, 220, 1.0],
            [60, 180, 220, 0.9],
            [120, 255, 255, 0.8]
        ]
    },
    cosmic: {
        bg: [10, 5, 20],
        colors: [
            [255, 120, 220, 1.0],
            [140, 80, 255, 0.9],
            [255, 255, 140, 0.8]
        ]
    },
    warm: {
        bg: [30, 20, 15],
        colors: [
            [255, 220, 180, 1.0],
            [255, 180, 120, 0.9],
            [220, 140, 80, 0.8]
        ]
    },
    minimal: {
        bg: [20, 20, 25],
        colors: [
            [220, 220, 230, 0.9],
            [180, 180, 190, 0.8],
            [255, 255, 255, 0.7]
        ]
    }
};

const palette = palettes[mood] || palettes.calm;

// --- Particle System ---
class Particle {
    constructor() {
        this.x = Math.random() * width;
        this.y = Math.random() * height;
        this.vx = 0;
        this.vy = 0;
        this.maxSpeed = 2 + Math.random() * 3;
        this.color = palette.colors[Math.floor(Math.random() * palette.colors.length)];
        this.size = 5 + Math.random() * 12;  // Much bigger particles!
    }

    update(flowField, reactivity) {
        // Get flow angle from noise
        const col = Math.floor(this.x / 20);
        const row = Math.floor(this.y / 20);
        const index = col + row * Math.ceil(width / 20);
        const angle = flowField[index] || 0;

        // Apply flow force with reactivity
        const force = 0.1 * reactivity;
        this.vx += Math.cos(angle) * force;
        this.vy += Math.sin(angle) * force;

        // Limit speed
        const speed = Math.sqrt(this.vx * this.vx + this.vy * this.vy);
        if (speed > this.maxSpeed) {
            this.vx = (this.vx / speed) * this.maxSpeed;
            this.vy = (this.vy / speed) * this.maxSpeed;
        }

        // Update position
        this.x += this.vx;
        this.y += this.vy;

        // Wrap edges
        if (this.x < 0) this.x = width;
        if (this.x > width) this.x = 0;
        if (this.y < 0) this.y = height;
        if (this.y > height) this.y = 0;
    }

    draw(ctx, reactivity) {
        const [r, g, b, a] = this.color;
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${a * (0.8 + reactivity * 0.4)})`;
        const size = this.size * (0.8 + reactivity * 0.3);
        ctx.beginPath();
        ctx.arc(this.x, this.y, size, 0, Math.PI * 2);
        ctx.fill();
    }
}

// --- Noise Function (Simple Perlin-like) ---
function noise2D(x, y, t) {
    const n = Math.sin(x * 0.01 + t * 0.001) *
        Math.cos(y * 0.01 - t * 0.0015) *
        Math.sin((x + y) * 0.005 + t * 0.002);
    return (n + 1) / 2; // Normalize 0-1
}

// --- Generate Flow Field ---
function generateFlowField(t) {
    const cols = Math.ceil(width / 20);
    const rows = Math.ceil(height / 20);
    const field = [];

    for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols; x++) {
            const n = noise2D(x * 20, y * 20, t);
            field.push(n * Math.PI * 4);
        }
    }
    return field;
}

// --- Main Render Loop ---
const canvas = createCanvas(width, height);
const ctx = canvas.getContext('2d');

// Initialize particles - MORE particles for denser effect
const particleCount = 4000;
const particles = [];
for (let i = 0; i < particleCount; i++) {
    particles.push(new Particle());
}

// Draw background once
ctx.fillStyle = `rgb(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]})`;
ctx.fillRect(0, 0, width, height);

console.log(`Starting render: ${totalFrames} frames at ${fps}fps`);

for (let frame = 1; frame <= totalFrames; frame++) {
    // Get audio reactivity
    let reactivity = 0.5;
    if (audioData[frame]) {
        reactivity = 0.3 + audioData[frame];
    }

    // Semi-transparent overlay for trails (less fade = more visible particles)
    ctx.fillStyle = `rgba(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]}, 0.02)`;
    ctx.fillRect(0, 0, width, height);

    // Generate flow field for this frame
    const flowField = generateFlowField(frame);

    // Update and draw particles
    for (const p of particles) {
        p.update(flowField, reactivity);
        p.draw(ctx, reactivity);
    }

    // Save frame
    const paddedNum = String(frame).padStart(4, '0');
    const filePath = path.join(outputDir, `frame_${paddedNum}.png`);
    const buffer = canvas.toBuffer('image/png');
    fs.writeFileSync(filePath, buffer);

    if (frame % 30 === 0) {
        console.log(`Frame ${frame}/${totalFrames}`);
    }
}

console.log(`Render complete: ${totalFrames} frames saved to ${outputDir}`);
