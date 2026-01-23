/**
 * Generative Art Renderer - Modular Architecture
 * Supports multiple art styles for Mindfulness videos
 * 
 * Usage: node render_art.js <output_dir> <duration> <style> <palette> [audio_data_path]
 * 
 * Styles: particles, blob, ink, smoke, marble, mandala, hexgrid, rings, 
 *         voronoi, starfield, nebula, aurora, gradient, singleline, breathing
 */

const fs = require('fs');
const path = require('path');
const { createCanvas } = require('canvas');

// --- Argument Parsing ---
const args = process.argv.slice(2);
const outputDir = args[0] || './temp/frames';
const duration = parseFloat(args[1] || 5.0);
const style = args[2] || 'particles';
const paletteName = args[3] || 'calm';
const audioDataPath = args[4];

const fps = 30;
const width = 1080;
const height = 1920;
const totalFrames = Math.floor(duration * fps);

// Load audio reactivity data
let audioData = [];
if (audioDataPath && fs.existsSync(audioDataPath)) {
    audioData = JSON.parse(fs.readFileSync(audioDataPath));
}

// Ensure output directory
if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
}

// --- Color Palettes ---
const palettes = {
    calm: { bg: [10, 20, 35], colors: [[100, 200, 255], [0, 180, 220], [200, 255, 255]] },
    deep: { bg: [8, 5, 20], colors: [[140, 80, 200], [80, 40, 150], [220, 120, 255]] },
    nature: { bg: [10, 30, 15], colors: [[120, 255, 120], [80, 220, 160], [180, 255, 180]] },
    sunset: { bg: [30, 15, 20], colors: [[255, 180, 80], [255, 120, 100], [255, 220, 120]] },
    ocean: { bg: [8, 20, 35], colors: [[0, 220, 220], [60, 180, 220], [120, 255, 255]] },
    cosmic: { bg: [10, 5, 20], colors: [[255, 120, 220], [140, 80, 255], [255, 255, 140]] },
    warm: { bg: [30, 20, 15], colors: [[255, 220, 180], [255, 180, 120], [220, 140, 80]] },
    minimal: { bg: [20, 20, 25], colors: [[220, 220, 230], [180, 180, 190], [255, 255, 255]] }
};

const palette = palettes[paletteName] || palettes.calm;

// --- Canvas Setup ---
const canvas = createCanvas(width, height);
const ctx = canvas.getContext('2d');

// --- Utility Functions ---
function noise2D(x, y, t, scale = 0.01) {
    return (Math.sin(x * scale + t * 0.001) *
        Math.cos(y * scale - t * 0.0015) *
        Math.sin((x + y) * scale * 0.5 + t * 0.002) + 1) / 2;
}

function lerp(a, b, t) { return a + (b - a) * t; }

function lerpColor(c1, c2, t) {
    return [
        Math.floor(lerp(c1[0], c2[0], t)),
        Math.floor(lerp(c1[1], c2[1], t)),
        Math.floor(lerp(c1[2], c2[2], t))
    ];
}

function getReactivity(frame) {
    return audioData[frame] ? 0.3 + audioData[frame] : 0.5;
}

function saveFrame(frame) {
    const paddedNum = String(frame).padStart(4, '0');
    const filePath = path.join(outputDir, `frame_${paddedNum}.png`);
    fs.writeFileSync(filePath, canvas.toBuffer('image/png'));
}

// --- ART STYLE: Particles (Original) ---
function initParticles() {
    const particles = [];
    for (let i = 0; i < 4000; i++) {
        particles.push({
            x: Math.random() * width,
            y: Math.random() * height,
            vx: 0, vy: 0,
            size: 5 + Math.random() * 12,
            color: palette.colors[Math.floor(Math.random() * palette.colors.length)]
        });
    }
    return particles;
}

function renderParticles(frame, particles, reactivity) {
    // Trail fade
    ctx.fillStyle = `rgba(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]}, 0.02)`;
    ctx.fillRect(0, 0, width, height);

    // Update and draw particles
    for (const p of particles) {
        const angle = noise2D(p.x, p.y, frame) * Math.PI * 4;
        p.vx += Math.cos(angle) * 0.1 * reactivity;
        p.vy += Math.sin(angle) * 0.1 * reactivity;
        const speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
        if (speed > 3) { p.vx *= 3 / speed; p.vy *= 3 / speed; }
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0) p.x = width; if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height; if (p.y > height) p.y = 0;

        ctx.fillStyle = `rgba(${p.color[0]}, ${p.color[1]}, ${p.color[2]}, ${0.8 + reactivity * 0.2})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * (0.8 + reactivity * 0.3), 0, Math.PI * 2);
        ctx.fill();
    }
}

// --- ART STYLE: Blob Morph ---
function initBlob() {
    return {
        centerX: width / 2,
        centerY: height / 2,
        baseRadius: 300,
        points: 12,
        phase: 0
    };
}

function renderBlob(frame, blob, reactivity) {
    // Fade background
    ctx.fillStyle = `rgba(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]}, 0.05)`;
    ctx.fillRect(0, 0, width, height);

    blob.phase += 0.02 * reactivity;

    // Draw multiple layered blobs
    for (let layer = 3; layer >= 0; layer--) {
        const radius = blob.baseRadius + layer * 80 + Math.sin(blob.phase) * 50 * reactivity;
        const color = palette.colors[layer % palette.colors.length];
        const alpha = 0.3 - layer * 0.05;

        ctx.beginPath();
        for (let i = 0; i <= blob.points; i++) {
            const angle = (i / blob.points) * Math.PI * 2;
            const noise = noise2D(Math.cos(angle) * 100, Math.sin(angle) * 100, frame + layer * 50);
            const r = radius + noise * 150 * reactivity;
            const x = blob.centerX + Math.cos(angle) * r;
            const y = blob.centerY + Math.sin(angle) * r;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.closePath();

        const gradient = ctx.createRadialGradient(
            blob.centerX, blob.centerY, 0,
            blob.centerX, blob.centerY, radius * 1.5
        );
        gradient.addColorStop(0, `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${alpha})`);
        gradient.addColorStop(1, `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0)`);
        ctx.fillStyle = gradient;
        ctx.fill();
    }
}

// --- ART STYLE: Ink Diffusion ---
function initInk() {
    const drops = [];
    for (let i = 0; i < 5; i++) {
        drops.push({
            x: width * 0.3 + Math.random() * width * 0.4,
            y: height * 0.3 + Math.random() * height * 0.4,
            radius: 50 + Math.random() * 100,
            color: palette.colors[i % palette.colors.length],
            phase: Math.random() * Math.PI * 2
        });
    }
    return { drops, tendrils: [] };
}

function renderInk(frame, ink, reactivity) {
    // Slow fade
    ctx.fillStyle = `rgba(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]}, 0.01)`;
    ctx.fillRect(0, 0, width, height);

    for (const drop of ink.drops) {
        drop.phase += 0.01;
        drop.radius += 0.5 * reactivity;
        if (drop.radius > 600) drop.radius = 50 + Math.random() * 100;

        // Draw diffusing ink with noise
        const segments = 60;
        ctx.beginPath();
        for (let i = 0; i <= segments; i++) {
            const angle = (i / segments) * Math.PI * 2;
            const noise = noise2D(
                drop.x + Math.cos(angle) * 100,
                drop.y + Math.sin(angle) * 100,
                frame
            );
            const r = drop.radius * (0.8 + noise * 0.4);
            const x = drop.x + Math.cos(angle + drop.phase * 0.1) * r;
            const y = drop.y + Math.sin(angle + drop.phase * 0.1) * r;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.closePath();

        const gradient = ctx.createRadialGradient(
            drop.x, drop.y, 0,
            drop.x, drop.y, drop.radius
        );
        gradient.addColorStop(0, `rgba(${drop.color[0]}, ${drop.color[1]}, ${drop.color[2]}, 0.15)`);
        gradient.addColorStop(0.5, `rgba(${drop.color[0]}, ${drop.color[1]}, ${drop.color[2]}, 0.08)`);
        gradient.addColorStop(1, `rgba(${drop.color[0]}, ${drop.color[1]}, ${drop.color[2]}, 0)`);
        ctx.fillStyle = gradient;
        ctx.fill();
    }
}

// --- ART STYLE: Smoke/Fog ---
function initSmoke() {
    const layers = [];
    for (let i = 0; i < 6; i++) {
        layers.push({
            offsetX: 0,
            offsetY: 0,
            scale: 0.005 + i * 0.002,
            speed: 0.3 + i * 0.1,
            alpha: 0.15 - i * 0.02,
            color: palette.colors[i % palette.colors.length]
        });
    }
    return { layers };
}

function renderSmoke(frame, smoke, reactivity) {
    // Clear with slight fade
    ctx.fillStyle = `rgba(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]}, 0.03)`;
    ctx.fillRect(0, 0, width, height);

    for (const layer of smoke.layers) {
        layer.offsetX += layer.speed * reactivity;
        layer.offsetY += layer.speed * 0.5 * reactivity;

        // Draw smoke using noise-based opacity
        const imageData = ctx.getImageData(0, 0, width, height);
        const step = 8; // Performance optimization

        for (let y = 0; y < height; y += step) {
            for (let x = 0; x < width; x += step) {
                const n = noise2D(x + layer.offsetX, y + layer.offsetY, frame, layer.scale);
                if (n > 0.4) {
                    const alpha = (n - 0.4) * layer.alpha * 2 * reactivity;
                    ctx.fillStyle = `rgba(${layer.color[0]}, ${layer.color[1]}, ${layer.color[2]}, ${alpha})`;
                    ctx.fillRect(x, y, step, step);
                }
            }
        }
    }
}

// --- ART STYLE: Liquid Marble ---
function initMarble() {
    return {
        time: 0,
        layers: 4
    };
}

function renderMarble(frame, marble, reactivity) {
    marble.time += 0.02 * reactivity;

    // Draw marble pattern
    const step = 4;
    for (let y = 0; y < height; y += step) {
        for (let x = 0; x < width; x += step) {
            // Multiple noise layers for marble effect
            let n = 0;
            for (let i = 0; i < marble.layers; i++) {
                const scale = 0.003 * (i + 1);
                const offset = marble.time * (i + 1) * 10;
                n += noise2D(x + offset, y + offset * 0.7, frame, scale) / marble.layers;
            }

            // Add swirl distortion
            const angle = n * Math.PI * 4;
            const swirl = Math.sin(angle) * 0.5 + 0.5;

            // Color mapping
            const colorIdx = Math.floor(swirl * (palette.colors.length - 0.01));
            const colorT = (swirl * palette.colors.length) % 1;
            const c1 = palette.colors[colorIdx];
            const c2 = palette.colors[(colorIdx + 1) % palette.colors.length];
            const color = lerpColor(c1, c2, colorT);

            const brightness = 0.3 + n * 0.7;
            ctx.fillStyle = `rgb(${Math.floor(color[0] * brightness)}, ${Math.floor(color[1] * brightness)}, ${Math.floor(color[2] * brightness)})`;
            ctx.fillRect(x, y, step, step);
        }
    }
}

// --- ART STYLE: Mandala (Sacred Geometry) ---
function initMandala() {
    return { rotation: 0 };
}

function renderMandala(frame, mandala, reactivity) {
    // Deep fade for trails
    ctx.fillStyle = `rgba(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]}, 0.1)`;
    ctx.fillRect(0, 0, width, height);

    mandala.rotation += 0.005 * reactivity;
    const centerX = width / 2;
    const centerY = height / 2;

    ctx.lineWidth = 2;
    // Draw multiple layers
    for (let i = 1; i <= 6; i++) {
        const radius = i * 120 + Math.sin(frame * 0.02) * 50 * reactivity;
        const color = palette.colors[i % palette.colors.length];
        const points = 8 + i * 4;

        ctx.strokeStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0.6)`;
        ctx.beginPath();
        for (let j = 0; j <= points; j++) {
            const angle = (j / points) * Math.PI * 2 + mandala.rotation * (i % 2 === 0 ? 1 : -1);
            const x = centerX + Math.cos(angle) * radius;
            const y = centerY + Math.sin(angle) * radius;

            // Sacred geometry petal shape
            const cX = centerX + Math.cos(angle) * (radius * 0.5);
            const cY = centerY + Math.sin(angle) * (radius * 0.5);

            if (j === 0) ctx.moveTo(x, y);
            else ctx.quadraticCurveTo(cX, cY, x, y);
        }
        ctx.stroke();
    }
}

// --- ART STYLE: Hexagonal Grid (Tech Zen) ---
function initHex() {
    return { time: 0 };
}

function drawHexagon(x, y, radius) {
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i;
        const hx = x + Math.cos(angle) * radius;
        const hy = y + Math.sin(angle) * radius;
        if (i === 0) ctx.moveTo(hx, hy);
        else ctx.lineTo(hx, hy);
    }
    ctx.closePath();
}

function renderHex(frame, hex, reactivity) {
    hex.time += 0.02;
    // Clear canvas
    ctx.fillStyle = `rgb(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]})`;
    ctx.fillRect(0, 0, width, height);

    const hexSize = 60;
    const w = Math.sqrt(3) * hexSize;
    const h = 2 * hexSize;

    for (let y = -h; y < height + h; y += h * 0.75) {
        for (let x = -w; x < width + w; x += w) {
            const offsetX = (Math.floor(y / (h * 0.75)) % 2 === 0) ? 0 : w / 2;
            const finalX = x + offsetX;

            const dist = Math.sqrt(Math.pow(finalX - width / 2, 2) + Math.pow(y - height / 2, 2));
            const n = noise2D(finalX, y, frame, 0.005);

            // Pulse effect
            const size = hexSize * (0.5 + n * 0.5 * reactivity);
            const colorIdx = Math.floor(n * palette.colors.length) % palette.colors.length;
            const color = palette.colors[colorIdx];

            ctx.strokeStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${0.3 + n * 0.5})`;
            ctx.lineWidth = 2 * reactivity;
            drawHexagon(finalX, y, size);
            ctx.stroke();

            if (n > 0.7) {
                ctx.fillStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0.2)`;
                ctx.fill();
            }
        }
    }
}

// --- ART STYLE: Concentric Rings (Sound Waves) ---
function initRings() {
    return { phase: 0 };
}

function renderRings(frame, rings, reactivity) {
    ctx.fillStyle = `rgba(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]}, 0.2)`;
    ctx.fillRect(0, 0, width, height);

    rings.phase += 0.05 * reactivity;
    const centerX = width / 2;
    const centerY = height / 2;

    for (let i = 0; i < 20; i++) {
        const baseR = i * 80;
        const offset = Math.sin(rings.phase - i * 0.5) * 40 * reactivity;
        const radius = baseR + offset;
        if (radius < 0) continue;

        const color = palette.colors[i % palette.colors.length];
        const alpha = Math.max(0, 1 - radius / (width * 0.8));

        ctx.strokeStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${alpha})`;
        ctx.lineWidth = 5 * reactivity;
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.stroke();
    }
}

// --- ART STYLE: Voronoi Cells ---
function initVoronoi() {
    const points = [];
    for (let i = 0; i < 50; i++) {
        points.push({
            x: Math.random() * width,
            y: Math.random() * height,
            vx: (Math.random() - 0.5) * 2,
            vy: (Math.random() - 0.5) * 2,
            color: palette.colors[Math.floor(Math.random() * palette.colors.length)]
        });
    }
    return { points };
}

function renderVoronoi(frame, voronoi, reactivity) {
    // Voronoi computation is expensive, so we approximate or use nearest neighbor simply
    // For performance in node-canvas, we'll use a bubble-like effect instead

    ctx.fillStyle = `rgb(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]})`;
    ctx.fillRect(0, 0, width, height);

    // Update points
    for (const p of voronoi.points) {
        p.x += p.vx * reactivity;
        p.y += p.vy * reactivity;

        // Bounce
        if (p.x < 0 || p.x > width) p.vx *= -1;
        if (p.y < 0 || p.y > height) p.vy *= -1;

        // Draw large soft gradients for "cell" effect
        const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, 300);
        gradient.addColorStop(0, `rgba(${p.color[0]}, ${p.color[1]}, ${p.color[2]}, 0.4)`);
        gradient.addColorStop(1, `rgba(${p.color[0]}, ${p.color[1]}, ${p.color[2]}, 0)`);

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 300, 0, Math.PI * 2);
        ctx.fill();
    }
}


// --- ART STYLE: Starfield (Cosmic Deep) ---
function initStarfield() {
    const stars = [];
    for (let i = 0; i < 600; i++) {
        stars.push({
            x: Math.random() * width,
            y: Math.random() * height,
            z: Math.random() * width, // depth
            size: Math.random() * 2,
            color: palette.colors[Math.floor(Math.random() * palette.colors.length)]
        });
    }
    return { stars };
}

function renderStarfield(frame, starfield, reactivity) {
    // Clear with trails
    ctx.fillStyle = `rgba(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]}, 0.3)`;
    ctx.fillRect(0, 0, width, height);

    const cx = width / 2;
    const cy = height / 2;

    for (const star of starfield.stars) {
        // Move star towards camera (z decreases)
        const speed = 15 * reactivity;
        star.z -= speed;

        // Reset if too close
        if (star.z <= 0) {
            star.z = width;
            star.x = Math.random() * width;
            star.y = Math.random() * height;
        }

        // Project 3D to 2D
        const k = 128.0 / star.z;
        const px = (star.x - cx) * k + cx;
        const py = (star.y - cy) * k + cy;

        if (px >= 0 && px <= width && py >= 0 && py <= height) {
            const size = (1 - star.z / width) * 4 * star.size;
            const alpha = (1 - star.z / width);

            ctx.fillStyle = `rgba(${star.color[0]}, ${star.color[1]}, ${star.color[2]}, ${alpha})`;
            ctx.beginPath();
            ctx.arc(px, py, size, 0, Math.PI * 2);
            ctx.fill();
        }
    }
}

// --- ART STYLE: Nebula (Cosmic Gas) ---
function initNebula() {
    return { offset: 0 };
}

function renderNebula(frame, nebula, reactivity) {
    nebula.offset += 0.01 * reactivity;

    // Pixel-based rendering usually too slow for canvas, using large radial gradients instead for "clouds"
    if (frame === 1) {
        ctx.fillStyle = `rgb(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]})`;
        ctx.fillRect(0, 0, width, height);
    }

    // Semi-transparent fade
    ctx.fillStyle = `rgba(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]}, 0.05)`;
    ctx.fillRect(0, 0, width, height);

    ctx.globalCompositeOperation = 'lighter'; // Additive blending for glowing effect

    for (let i = 0; i < 5; i++) {
        const time = frame * 0.005;
        const x = width * (0.5 + 0.4 * noise2D(i * 100, time, 0));
        const y = height * (0.5 + 0.4 * noise2D(time, i * 100 + 50, 0));
        const radius = 300 + 100 * reactivity + noise2D(x, y, time) * 200;

        const color = palette.colors[i % palette.colors.length];

        const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
        gradient.addColorStop(0, `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0.1)`);
        gradient.addColorStop(0.5, `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0.05)`);
        gradient.addColorStop(1, `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0)`);

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();
    }
    ctx.globalCompositeOperation = 'source-over'; // Reset blending
}

// --- ART STYLE: Aurora (Northern Lights) ---
function initAurora() {
    return { t: 0 };
}

function renderAurora(frame, aurora, reactivity) {
    aurora.t += 0.02 * reactivity;

    ctx.fillStyle = `rgba(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]}, 0.1)`;
    ctx.fillRect(0, 0, width, height);

    ctx.globalCompositeOperation = 'lighter'; // Glow

    for (let i = 0; i < 3; i++) {
        ctx.beginPath();
        const color = palette.colors[i % palette.colors.length];
        ctx.fillStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0.1)`;

        for (let x = 0; x <= width; x += 10) {
            const yOffset = height / 2 + (i - 1) * 200;
            const noiseVal = noise2D(x, yOffset, frame * 10, 0.002);
            const y = yOffset + Math.sin(x * 0.005 + aurora.t + i) * 100 + noiseVal * 200 * reactivity;

            if (x === 0) ctx.moveTo(x, height);
            ctx.lineTo(x, y);
        }
        ctx.lineTo(width, height);
        ctx.closePath();
        ctx.fill();

        // Add a top stroke for definition
        ctx.strokeStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0.2)`;
        ctx.lineWidth = 2;
        ctx.stroke();
    }
    ctx.globalCompositeOperation = 'source-over';
}

// --- ART STYLE: Gradient Shift ---
function initGradient() {
    return { t: 0 };
}

function renderGradient(frame, gradient, reactivity) {
    gradient.t += 0.01 * reactivity;

    // Create soft moving gradient
    const angle = gradient.t * 0.5;
    const x1 = width / 2 + Math.cos(angle) * width / 2;
    const y1 = height / 2 + Math.sin(angle) * height / 2;
    const x2 = width / 2 + Math.cos(angle + Math.PI) * width / 2;
    const y2 = height / 2 + Math.sin(angle + Math.PI) * height / 2;

    const grad = ctx.createLinearGradient(x1, y1, x2, y2);

    // Smoothly interpolate colors over time
    for (let i = 0; i < 3; i++) {
        const colorIdx = (Math.floor(gradient.t + i) % palette.colors.length);
        const nextIdx = (colorIdx + 1) % palette.colors.length;
        const t = (gradient.t + i) % 1;

        const c1 = palette.colors[colorIdx];
        const c2 = palette.colors[nextIdx];
        const color = lerpColor(c1, c2, t);

        grad.addColorStop(i * 0.5, `rgb(${color[0]}, ${color[1]}, ${color[2]})`);
    }

    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, width, height);

    // Add subtle noise overlay for texture
    if (frame === 1) {
        // Just once ideally, but canvas clears every frame in this architecture
    }
}

// --- ART STYLE: Single Line (Focus) ---
function initSingleLine() {
    return {
        points: Array(20).fill(0).map((_, i) => ({
            x: width * 0.5,
            y: (height / 20) * i
        })),
        t: 0
    };
}

function renderSingleLine(frame, line, reactivity) {
    // Fade very slowly
    ctx.fillStyle = `rgba(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]}, 0.05)`;
    ctx.fillRect(0, 0, width, height);

    line.t += 0.05 * reactivity;

    ctx.beginPath();
    ctx.lineWidth = 4 + reactivity * 4;
    ctx.strokeStyle = `rgba(${palette.colors[0][0]}, ${palette.colors[0][1]}, ${palette.colors[0][2]}, 0.8)`;

    for (let i = 0; i < line.points.length; i++) {
        const p = line.points[i];
        const targetX = width * 0.5 + Math.sin(line.t + i * 0.3) * 300 * reactivity;

        // Smooth follow
        p.x += (targetX - p.x) * 0.1;

        if (i === 0) ctx.moveTo(p.x, p.y + height * 0.05); // Start slightly offset
        else {
            // Catmull-Rom like curve
            const prev = line.points[i - 1];
            const cp1x = prev.x;
            const cp1y = prev.y + (p.y - prev.y) * 0.5;
            const cp2x = p.x;
            const cp2y = p.y - (p.y - prev.y) * 0.5;
            ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p.x, p.y + height * 0.05);
        }
    }
    ctx.stroke();
}

// --- ART STYLE: Breathing Circle ---
function initBreathing() {
    return { size: 100, phase: 0 };
}

function renderBreathing(frame, breath, reactivity) {
    ctx.fillStyle = `rgba(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]}, 0.1)`;
    ctx.fillRect(0, 0, width, height);

    // Simulate 4-7-8 breathing pattern roughly or just sine wave
    breath.phase += 0.03; // Steady breath

    // Expansion/Contraction
    const scale = 1 + Math.sin(breath.phase) * 0.3 + reactivity * 0.2;
    const radius = 300 * scale;

    const cx = width / 2;
    const cy = height / 2;

    // Outer glow
    const gradient = ctx.createRadialGradient(cx, cy, radius * 0.8, cx, cy, radius * 1.5);
    const color = palette.colors[0];
    gradient.addColorStop(0, `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0.4)`);
    gradient.addColorStop(1, `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0)`);

    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(cx, cy, radius * 1.5, 0, Math.PI * 2);
    ctx.fill();

    // Inner solid circle
    ctx.fillStyle = `rgba(${palette.colors[1][0]}, ${palette.colors[1][1]}, ${palette.colors[1][2]}, 0.8)`;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fill();
}

// --- Main Render Loop ---
console.log(`Starting render: ${totalFrames} frames, style: ${style}, palette: ${paletteName}`);

// Initialize state based on style
let state;
switch (style) {
    case 'blob': state = initBlob(); break;
    case 'ink': state = initInk(); break;
    case 'smoke': state = initSmoke(); break;
    case 'marble': state = initMarble(); break;
    case 'mandala': state = initMandala(); break;
    case 'hex': state = initHex(); break;
    case 'rings': state = initRings(); break;
    case 'voronoi': state = initVoronoi(); break;
    case 'starfield': state = initStarfield(); break;
    case 'nebula': state = initNebula(); break;
    case 'aurora': state = initAurora(); break;
    case 'gradient': state = initGradient(); break;
    case 'singleline': state = initSingleLine(); break;
    case 'breathing': state = initBreathing(); break;
    default: state = initParticles();
}

// Initial background
ctx.fillStyle = `rgb(${palette.bg[0]}, ${palette.bg[1]}, ${palette.bg[2]})`;
ctx.fillRect(0, 0, width, height);

// Render frames
for (let frame = 1; frame <= totalFrames; frame++) {
    const reactivity = getReactivity(frame);

    switch (style) {
        case 'blob': renderBlob(frame, state, reactivity); break;
        case 'ink': renderInk(frame, state, reactivity); break;
        case 'smoke': renderSmoke(frame, state, reactivity); break;
        case 'marble': renderMarble(frame, state, reactivity); break;
        case 'mandala': renderMandala(frame, state, reactivity); break;
        case 'hex': renderHex(frame, state, reactivity); break;
        case 'rings': renderRings(frame, state, reactivity); break;
        case 'voronoi': renderVoronoi(frame, state, reactivity); break;
        case 'starfield': renderStarfield(frame, state, reactivity); break;
        case 'nebula': renderNebula(frame, state, reactivity); break;
        case 'aurora': renderAurora(frame, state, reactivity); break;
        case 'gradient': renderGradient(frame, state, reactivity); break;
        case 'singleline': renderSingleLine(frame, state, reactivity); break;
        case 'breathing': renderBreathing(frame, state, reactivity); break;
        default: renderParticles(frame, state, reactivity);
    }

    saveFrame(frame);

    if (frame % 30 === 0) {
        console.log(`Frame ${frame}/${totalFrames}`);
    }
}

console.log(`Render complete: ${totalFrames} frames saved to ${outputDir}`);
