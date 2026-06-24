/**
 * 凌霄 粒子背景动画
 * 使用方式：Particles.init() 即可启动
 * 
 * 性能优化：
 * - visibilitychange 暂停/恢复（降低后台 CPU 消耗）
 * - resize 防抖（避免频繁重建粒子）
 * - 空间网格加速连线检测（O(n²) → 近似 O(n)）
 * - prefers-reduced-motion 自动禁用
 */
window.Particles = (function() {
    let canvas, ctx, width, height, particles = [];
    let animFrameId = null;
    let running = false;
    let resizeTimer = null;
    // 空间网格用于连线检测加速
    let gridCellSize = 120;
    let gridCols, gridRows, grid;

    // 检查用户是否偏好减少动画
    function prefersReducedMotion() {
        return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    function buildGrid() {
        gridCols = Math.ceil(width / gridCellSize);
        gridRows = Math.ceil(height / gridCellSize);
        grid = new Array(gridCols * gridRows);
        for (let i = 0; i < grid.length; i++) grid[i] = [];
        particles.forEach(function(p, idx) {
            const col = Math.floor(p.x / gridCellSize);
            const row = Math.floor(p.y / gridCellSize);
            if (col >= 0 && col < gridCols && row >= 0 && row < gridRows) {
                grid[row * gridCols + col].push(idx);
            }
        });
    }

    function initParticles() {
        // 根据屏幕面积动态计算粒子数，同时设置上限避免低端设备卡顿
        const area = width * height;
        const count = Math.min(Math.floor(area / 12000), 200);
        particles = [];
        for (let i = 0; i < count; i++) {
            particles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                radius: Math.random() * 2 + 1,
                speedX: (Math.random() - 0.5) * 0.3,
                speedY: (Math.random() - 0.5) * 0.3,
                color: "rgba(" + (99 + Math.floor(Math.random() * 156)) + ", " + (102 + Math.floor(Math.random() * 100)) + ", " + (241 + Math.floor(Math.random() * 14)) + ", " + (0.2 + Math.random() * 0.3) + ")"
            });
        }
    }

    function drawParticles() {
        if (!running) return;
        ctx.clearRect(0, 0, width, height);
        // 更新粒子位置并绘制
        particles.forEach(function(p) {
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
            ctx.fillStyle = p.color;
            ctx.fill();
            p.x += p.speedX;
            p.y += p.speedY;
            if (p.x < 0 || p.x > width) p.speedX *= -1;
            if (p.y < 0 || p.y > height) p.speedY *= -1;
        });

        // 重建空间网格
        buildGrid();

        const maxDist = 120; // sqrt(14400) ≈ 120
        const maxDistSq = maxDist * maxDist;
        ctx.strokeStyle = "rgba(139, 92, 246, 0.08)";
        ctx.lineWidth = 0.5;
        // 仅检查相邻网格单元内的粒子对，避免 O(n²) 全量遍历
        const checked = new Set();
        for (let i = 0; i < particles.length; i++) {
            const col = Math.floor(particles[i].x / gridCellSize);
            const row = Math.floor(particles[i].y / gridCellSize);
            // 检查当前格及相邻 8 格
            for (let dr = -1; dr <= 1; dr++) {
                for (let dc = -1; dc <= 1; dc++) {
                    const nc = col + dc;
                    const nr = row + dr;
                    if (nc < 0 || nc >= gridCols || nr < 0 || nr >= gridRows) continue;
                    const neighbors = grid[nr * gridCols + nc];
                    for (let k = 0; k < neighbors.length; k++) {
                        const j = neighbors[k];
                        if (j <= i) continue;
                        const key = i + '_' + j;
                        if (checked.has(key)) continue;
                        checked.add(key);
                        const dx = particles[i].x - particles[j].x;
                        const dy = particles[i].y - particles[j].y;
                        if (dx * dx + dy * dy < maxDistSq) {
                            ctx.beginPath();
                            ctx.moveTo(particles[i].x, particles[i].y);
                            ctx.lineTo(particles[j].x, particles[j].y);
                            ctx.stroke();
                        }
                    }
                }
            }
        }
        animFrameId = requestAnimationFrame(drawParticles);
    }

    function resizeCanvas() {
        // 防抖 resize：避免拖拽窗口时频繁重建
        if (resizeTimer) clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            doResize();
            resizeTimer = null;
        }, 150);
    }

    function doResize() {
        width = window.innerWidth;
        height = window.innerHeight;
        canvas.width = width;
        canvas.height = height;
        gridCellSize = Math.max(80, Math.min(120, Math.sqrt(width * height) / 12));
        initParticles();
    }

    return {
        init: function() {
            if (running) return;
            if (prefersReducedMotion()) {
                console.log('[Particles] 检测到 prefers-reduced-motion，跳过粒子动画');
                return;
            }
            canvas = document.getElementById("particle-canvas");
            if (!canvas) return;
            ctx = canvas.getContext("2d");
            doResize();
            running = true;
            drawParticles();
            window.addEventListener("resize", resizeCanvas, { passive: true });
            document.addEventListener("visibilitychange", function() {
                if (document.hidden) {
                    running = false;
                    if (animFrameId) cancelAnimationFrame(animFrameId);
                } else {
                    if (!running) { running = true; drawParticles(); }
                }
            });
            // 监听 reduced-motion 变化
            window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', function(e) {
                if (e.matches) {
                    running = false;
                    if (animFrameId) cancelAnimationFrame(animFrameId);
                    if (canvas) canvas.style.display = 'none';
                }
            });
        },
        pause: function() {
            running = false;
            if (animFrameId) cancelAnimationFrame(animFrameId);
        },
        resume: function() {
            if (running) return;
            running = true;
            drawParticles();
        }
    };
})();
