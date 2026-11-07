import { FaceData } from './hologram-face-data.js';

export class FaceGeometry {
    static generate(count) {
        // Grid-based Sampling for Viki-style ordered look
        // Instead of pure random sampling, we'll use a structured approach

        const positions = new Float32Array(count * 3);
        const types = new Float32Array(count);

        const indices = FaceData.indices;
        const verts = FaceData.vertices;

        // Calculate bounding box
        let minX = Infinity, maxX = -Infinity;
        let minY = Infinity, maxY = -Infinity;
        let minZ = Infinity, maxZ = -Infinity;

        for (let i = 0; i < verts.length; i++) {
            minX = Math.min(minX, verts[i][0]);
            maxX = Math.max(maxX, verts[i][0]);
            minY = Math.min(minY, verts[i][1]);
            maxY = Math.max(maxY, verts[i][1]);
            minZ = Math.min(minZ, verts[i][2]);
            maxZ = Math.max(maxZ, verts[i][2]);
        }

        // Calculate Triangle Areas for weighted sampling
        const areas = [];
        let totalArea = 0;

        for (let i = 0; i < indices.length; i++) {
            const [i1, i2, i3] = indices[i];
            const v1 = verts[i1];
            const v2 = verts[i2];
            const v3 = verts[i3];

            const ax = v2[0] - v1[0], ay = v2[1] - v1[1], az = v2[2] - v1[2];
            const bx = v3[0] - v1[0], by = v3[1] - v1[1], bz = v3[2] - v1[2];

            const cx = ay * bz - az * by;
            const cy = az * bx - ax * bz;
            const cz = ax * by - ay * bx;

            const area = 0.5 * Math.sqrt(cx * cx + cy * cy + cz * cz);
            areas.push(area);
            totalArea += area;
        }

        // Generate Points with structured randomness
        for (let i = 0; i < count; i++) {
            const i3 = i * 3;

            // Pick a triangle weighted by area
            let r = Math.random() * totalArea;
            let triIndex = 0;
            for (let j = 0; j < areas.length; j++) {
                r -= areas[j];
                if (r <= 0) {
                    triIndex = j;
                    break;
                }
            }

            const [id1, id2, id3, type] = indices[triIndex];
            const v1 = verts[id1];
            const v2 = verts[id2];
            const v3 = verts[id3];

            // Use structured barycentric coordinates instead of pure random
            // This creates a more regular grid-like pattern
            const gridSize = Math.ceil(Math.sqrt(count / indices.length));
            const localIndex = i % (gridSize * gridSize);
            const gridX = (localIndex % gridSize) / gridSize;
            const gridY = Math.floor(localIndex / gridSize) / gridSize;

            // Add small random offset for natural look
            const r1 = Math.min(0.95, gridX + (Math.random() - 0.5) * 0.15);
            const r2 = Math.min(0.95, gridY + (Math.random() - 0.5) * 0.15);

            // Ensure valid barycentric coordinates
            let b1 = Math.max(0, Math.min(1, r1));
            let b2 = Math.max(0, Math.min(1, r2));

            if (b1 + b2 > 1) {
                b1 = 1 - b1;
                b2 = 1 - b2;
            }

            const b3 = 1 - b1 - b2;

            const x = b1 * v1[0] + b2 * v2[0] + b3 * v3[0];
            const y = b1 * v1[1] + b2 * v2[1] + b3 * v3[1];
            const z = b1 * v1[2] + b2 * v2[2] + b3 * v3[2];

            positions[i3] = x;
            positions[i3 + 1] = y;
            positions[i3 + 2] = z;
            types[i] = type;
        }

        // The canonical FaceData is only ~16 units tall, whereas the
        // camera-tracked face spans ~500 units (scale 1000). Without matching
        // them, the idle/neutral face renders as a tiny cluster in the centre.
        // Normalise: centre on origin and scale so the face is ~500 units tall.
        // Preserve the original orientation (no axis negation) — negating axes
        // turns the face inside-out / inverts it.
        const cx = (minX + maxX) / 2;
        const cy = (minY + maxY) / 2;
        const cz = (minZ + maxZ) / 2;
        const height = (maxY - minY) || 1;
        const norm = 500 / height;
        for (let i = 0; i < count; i++) {
            const i3 = i * 3;
            positions[i3]     = (positions[i3] - cx) * norm;
            positions[i3 + 1] = (positions[i3 + 1] - cy) * norm;
            positions[i3 + 2] = (positions[i3 + 2] - cz) * norm;
        }

        return { positions, types };
    }
}
