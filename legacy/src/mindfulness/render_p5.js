const fs = require('fs');
const path = require('path');
const { createCanvas } = require('canvas');
const { JSDOM } = require('jsdom'); // Mock DOM for p5.js in headless mode

// --- Argument Parsing ---
const args = process.argv.slice(2);
const outputDir = args[0] || './temp/frames';
const duration = parseFloat(args[1] || 5.0);
const fps = 30; // 30fps is enough for this
const mood = args[2] || 'calm'; // calm, energy, deep
const audioDataPath = args[3];
const totalFrames = Math.floor(duration * fps);

let audioData = [];
if (audioDataPath && fs.existsSync(audioDataPath)) {
    const raw = fs.readFileSync(audioDataPath);
    audioData = JSON.parse(raw);
}


// Ensure output directory exists
if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
}

// --- Setup Headless Environment ---
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>');
global.window = dom.window;
global.document = dom.window.document;
global.screen = dom.window.screen;
global.navigator = dom.window.navigator;
global.Image = dom.window.Image; // Important for p5
global.HTMLCanvasElement = dom.window.HTMLCanvasElement; // JSDOM should expose this if canvas is working

// Polyfill requestAnimationFrame
global.requestAnimationFrame = (callback) => setTimeout(callback, 1000 / 60);
global.cancelAnimationFrame = (id) => clearTimeout(id);
dom.window.requestAnimationFrame = global.requestAnimationFrame;
dom.window.cancelAnimationFrame = global.cancelAnimationFrame;

// Mock dispatchEvent to avoid JSDOM strictness
dom.window.dispatchEvent = (event) => true;
dom.window.document.dispatchEvent = (event) => true;

// Polyfill minimal style for p5
dom.window.HTMLCanvasElement.prototype.getContext = function (type) {
    if (type === '2d') return createCanvas(1080, 1920).getContext('2d');
};

// Load p5 AFTER globals are set
const p5 = require('p5');

// --- p5.js Instance Mode ---
new p5((p) => {

    let particles = [];
    const flowFieldScale = 0.005; // Scale for Perlin noise
    const w = 1080;
    const h = 1920;

    // Palette configuration (Dark & Immersive - NO WHITE BACKGROUNDS)
    const palettes = {
        calm: {
            bg: [10, 20, 30], // Deep Blue/Black
            colors: [[100, 200, 255, 50], [0, 150, 200, 30], [200, 255, 255, 20]] // Cyan/Blue translucents
        },
        deep: {
            bg: [5, 5, 10], // Almost Black
            colors: [[100, 50, 150, 40], [50, 20, 80, 20], [200, 100, 255, 15]] // Purple/Violet
        },
        nature: {
            bg: [15, 25, 15], // Deep Forest Green
            colors: [[100, 255, 100, 30], [50, 200, 150, 20], [200, 255, 200, 10]] // Green/Emerald
        }
    };

    const palette = palettes[mood] || palettes.calm;

    p.setup = () => {
        // Create canvas using node-canvas
        let canvas = createCanvas(w, h);

        // Mock p5's canvas creation
        p.createCanvas(w, h);
        // Replace p5's canvas with our node-canvas instance
        p.drawingContext = canvas.getContext('2d');
        p.canvas = canvas;

        p.noStroke();
        p.background(palette.bg);

        // Initialize particles
        const particleCount = 2000;
        for (let i = 0; i < particleCount; i++) {
            particles.push(new Particle(p));
        }
    };

    p.draw = () => {
        // Semi-transparent background for trail effect (Immersive feel)
        // Never clear completely to maintain organic flow
        p.fill(palette.bg[0], palette.bg[1], palette.bg[2], 10);
        p.rect(0, 0, w, h);

        // Update Flow Field & Particles
        // Get audio reactivity for this frame
        let reactivity = 0.5; // default base energy
        if (audioData[p.frameCount]) {
            reactivity = 0.2 + audioData[p.frameCount]; // Base + Audio Energy
        }

        particles.forEach(particle => {
            particle.follow(flowFieldScale, p.frameCount, reactivity);
            particle.update();
            particle.edges();
            particle.show();
        });


        // Save frame
        saveFrame(p.frameCount);

        // Stop after duration
        if (p.frameCount >= totalFrames) {
            console.log(`Render complete: ${totalFrames} frames saved.`);
            process.exit(0);
        }
    };

    // --- Particle Class ---
    class Particle {
        constructor(p) {
            this.p = p;
            this.pos = p.createVector(p.random(w), p.random(h));
            this.vel = p.createVector(0, 0);
            this.acc = p.createVector(0, 0);
            this.maxSpeed = p.random(1, 2.5); // Slow, organic movement

            // Assign random color from palette
            this.color = p.random(palette.colors);
            this.size = p.random(1, 3);
        }

        follow(scale, t, reactivity) {
            // Perlin Noise Flow Field
            // 3D noise (x, y, time) for evolving fields
            let angle = this.p.noise(this.pos.x * scale, this.pos.y * scale, t * 0.002) * this.p.TWO_PI * 4;
            let v = p5.Vector.fromAngle(angle);

            // Reactivity: Audio makes particles move faster and more erratically
            v.setMag(0.1 * reactivity);
            this.applyForce(v);

            // Pulse size with audio
            this.currentSize = this.size * (0.8 + reactivity);
        }

        applyForce(force) {
            this.acc.add(force);
        }

        update() {
            this.vel.add(this.acc);
            this.vel.limit(this.maxSpeed);
            this.pos.add(this.vel);
            this.acc.mult(0); // Reset accel
        }

        edges() {
            if (this.pos.x > w) { this.pos.x = 0; this.updatePrev(); }
            if (this.pos.x < 0) { this.pos.x = w; this.updatePrev(); }
            if (this.pos.y > h) { this.pos.y = 0; this.updatePrev(); }
            if (this.pos.y < 0) { this.pos.y = h; this.updatePrev(); }
        }

        updatePrev() {
            // Optional: reset trails if wrapping
        }

        show() {
            this.p.fill(this.color);
            this.p.ellipse(this.pos.x, this.pos.y, this.currentSize || this.size);
        }
    }

    // --- Helper to save frames ---
    function saveFrame(frameNum) {
        const paddedNum = String(frameNum).padStart(4, '0');
        const fileName = `frame_${paddedNum}.png`;
        const filePath = path.join(outputDir, fileName);

        // Use node-canvas to save
        const buffer = p.canvas.toBuffer('image/png');
        fs.writeFileSync(filePath, buffer);

        if (frameNum % 30 === 0) {
            console.log(`Saved frame ${frameNum}/${totalFrames}`);
        }
    }
});
