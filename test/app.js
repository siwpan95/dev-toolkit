/**
 * app.js — 原型人格洞察 · 每日一测 主逻辑
 * 依赖：questions.js（须先于本文件加载）
 * 修复清单：
 *   - seededRandom 改用 xorshift32 高质量伪随机
 *   - 修复 maxFunc 为 null 时 prototypeMap[null] 崩溃
 *   - 结果页展示八功能得分条形图
 *   - 选中选项后 400ms 自动进入下一题（T4）
 *   - 使用 pickArchetype() 从45原型中选取结果
 *   - 修复脚注文案
 */

(function () {
    'use strict';

    // ========== 存储 & 每日限制 ==========
    const STORAGE_KEY  = 'ppi_test_result';   // ppi = prototype personality insight
    const DAILY_KEY    = 'ppi_last_date';
    const DAILY_COUNT  = 13;
    const FUNC_ORDER   = ['Te','Fe','Se','Ne','Ti','Fi','Si','Ni'];
    const FUNC_LABELS  = { Te:'Te 外倾思维', Fe:'Fe 外倾情感', Se:'Se 外倾感觉', Ne:'Ne 外倾直觉',
                           Ti:'Ti 内倾思维', Fi:'Fi 内倾情感', Si:'Si 内倾感觉', Ni:'Ni 内倾直觉' };
    const FUNC_COLORS  = { Te:'#f4a261', Fe:'#2a9d8', Se:'#e76f51', Ne:'#06d6a0',
                           Ti:'#8338ec', Fi:'#ff006e', Si:'#3a86ff', Ni:'#ffbe0b' };

    // ========== 高质量日期种子伪随机数 ==========
    // 字符串哈希 → xorshift32 PRNG（周期 2³²−1，分布均匀）
    function seededRandom(seed) {
        // 阶段1：将任意长度字符串哈希为一个 32-bit 种子
        let h = 0x9e3779b9;                       // golden ratio 相关初始值
        for (let i = 0; i < seed.length; i++) {
            h = Math.imul(h ^ seed.charCodeAt(i), 0x5bd1e995);
        }
        h = (h ^ (h >>> 13)) >>> 0;

        // 阶段2：返回 xorshift32 闭包
        let state = h | 1;                      // 保证奇数
        return function () {
            state ^= state << 13;
            state ^= state >>> 17;
            state ^= state << 5;
            return (state >>> 0) / 0x100000000;    // [0, 1)
        };
    }

    // ========== 每日分层抽样选题 ==========
    // 策略：先从每功能组各抽至少1题，剩余名额随机分配
    function getDailyQuestions() {
        const today    = getTodayStr();
        const rng      = seededRandom(today);
        const indices  = questions.map((_, i) => i);

        // 按功能分组索引：一道题的 options 中出现哪些功能，就归入哪几个组
        // 这样能避免「只看 options[0]」导致 Ti/Fi/Si/Ni 桶为空的 bug
        const byFunc = {};
        FUNC_ORDER.forEach(f => byFunc[f] = []);
        indices.forEach(i => {
            const funcsInQuestion = new Set(questions[i].options.map(o => o.func));
            funcsInQuestion.forEach(f => {
                if (byFunc[f]) byFunc[f].push(i);
            });
        });

        const picked = new Set();
        // 每功能先各抽 1 题，优先保证八功能都有覆盖
        FUNC_ORDER.forEach(f => {
            const pool = byFunc[f].filter(i => !picked.has(i));
            if (pool.length === 0) return;
            shuffle(pool, rng);
            picked.add(pool[0]);
        });

        // 剩余名额从全题库（排除已选）随机补足，直到达到 DAILY_COUNT
        const remaining = indices.filter(i => !picked.has(i));
        shuffle(remaining, rng);
        for (let i = 0; picked.size < DAILY_COUNT && i < remaining.length; i++) {
            picked.add(remaining[i]);
        }

        // 最终洗牌，返回题目对象数组
        const pickedArr = Array.from(picked);
        shuffle(pickedArr, rng);
        return pickedArr.map(i => questions[i]);
    }

    function shuffle(arr, rng) {
        for (let i = arr.length - 1; i > 0; i--) {
            const j = Math.floor(rng() * (i + 1));
            [arr[i], arr[j]] = [arr[j], arr[i]];
        }
        return arr;
    }

    function getTodayStr() {
        return new Date().toISOString().slice(0, 10);
    }

    function isTodayTested() {
        return localStorage.getItem(DAILY_KEY) === getTodayStr();
    }
    function markTodayTested() {
        localStorage.setItem(DAILY_KEY, getTodayStr());
    }
    function saveResult(scores, archetypeName) {
        localStorage.setItem(STORAGE_KEY,
            JSON.stringify({ scores, archetypeName, date: getTodayStr() }));
    }
    function getStoredResult() {
        try { return JSON.parse(localStorage.getItem(STORAGE_KEY)); } catch { return null; }
    }

    // ========== 应用状态 ==========
    let currentQuestionIndex = 0;
    let scoreMap   = { Te:0, Fe:0, Se:0, Ne:0, Ti:0, Fi:0, Si:0, Ni:0 };
    let answersGiven  = 0;
    let isResultMode  = false;
    let resultArchetype = null;      // 存完整原型对象（来自 archetypeList）
    let autoTimer  = null;

    const appDiv = document.getElementById('app');

    // ========== 渲染入口 ==========
    function render() {
        if (isResultMode) { renderResult(); return; }

        if (isTodayTested() && answersGiven === 0) {
            const stored = getStoredResult();
            if (stored && stored.archetypeName) {
                // 从 archetypeList 找完整对象
                resultArchetype = archetypeList.find(a => a.name === stored.archetypeName) || null;
                isResultMode = true;
                renderResult();
            } else {
                renderBlocked();
            }
            return;
        }

        if (answersGiven >= dailyQuestions.length) {
            finishTest();
            return;
        }
        renderQuestion();
    }

    // ========== 从45原型中选取结果 ==========
    function pickArchetype(scoreMap) {
        const sorted = Object.entries(scoreMap).sort((a, b) => b[1] - a[1]);
        const topFunc = sorted[0][0];
        const subFunc = sorted[1] ? sorted[1][0] : null;
        const topScore = sorted[0][1];
        const subScore = sorted[1] ? sorted[1][1] : 0;

        // 从最高分功能对应的原型列表中挑选
        let candidates = archetypeList.filter(a => a.func === topFunc);

        // 如果次高分与最高分差距 ≤ 1，且次高分功能也有对应原型，则考虑跨功能匹配
        if (subFunc && topScore - subScore <= 1) {
            const subCandidates = archetypeList.filter(a => a.func === subFunc);
            candidates = candidates.concat(subCandidates);
        }

        // 用日期种子从候选原型中稳定地选一个（同一天同一得分分布得到同一结果）
        const seed = new Date().toISOString().slice(0, 10).split('-').join('');
        let h = 0;
        for (let i = 0; i < seed.length; i++) { h = ((h << 5) - h + seed.charCodeAt(i)) | 0; }
        h = (h >>> 0);
        const idx = h % candidates.length;
        return candidates[idx];
    }

    // ========== 完成测试，计算结果 ==========
    function finishTest() {
        // 防 null：所有分都是 0 时默认取第一个功能
        let maxFunc = null, maxCount = -1;
        for (const [func, val] of Object.entries(scoreMap)) {
            if (val > maxCount) { maxCount = val; maxFunc = func; }
        }
        if (maxFunc === null) maxFunc = FUNC_ORDER[0];

        // 用 pickArchetype 从45原型中选取结果
        resultArchetype = pickArchetype(scoreMap);

        saveResult(scoreMap, resultArchetype.name);
        markTodayTested();
        isResultMode = true;
        renderResult();
    }

    // ========== 拦截页（今日已测）==========
    function renderBlocked() {
        appDiv.innerHTML = `
            <div class="card" style="text-align:center">
                <div class="stats-bar">
                    <span class="badge">✨ 原型人格洞察</span>
                    <span class="daily-status">📅 今日已完成一测</span>
                </div>
                <div style="padding:30px 0">
                    <span style="font-size:3rem;">🌙</span>
                    <h2 style="color:#ffbc6e">每日仅限一次</h2>
                    <p style="margin:20px 0">你已经测过了！明天再来探索你的内在原型吧~<br>梦境与现实之间，再给自己一点时间。</p>
                    <button class="share-btn" id="viewLastResultBtn">📖 查看今日结果</button>
                    <div class="footnote">基于荣格八功能 × 经典人物原型45种 · 每日随机13题</div>
                </div>
            </div>`;
        document.getElementById('viewLastResultBtn')?.addEventListener('click', () => {
            const stored = getStoredResult();
            if (stored && stored.archetypeName) {
                resultArchetype = archetypeList.find(a => a.name === stored.archetypeName) || null;
                if (!resultArchetype && stored.scores) {
                    resultArchetype = pickArchetype(stored.scores);
                }
                isResultMode = true;
                renderResult();
            } else {
                alert('没有找到历史记录，请明天再测~');
            }
        });
    }

    // ========== 题目页 ==========
    function renderQuestion() {
        const q = dailyQuestions[currentQuestionIndex];
        const progressPercent = Math.floor((answersGiven / dailyQuestions.length) * 100);
        const optionsHtml = q.options.map((opt, idx) =>
            `<button class="option-btn" data-func="${opt.func}">${String.fromCharCode(65+idx)}. ${opt.text}</button>`
        ).join('');

        appDiv.innerHTML = `
            <div class="card">
                <div class="stats-bar">
                    <span class="badge">🧠 原型人格洞察</span>
                    <span class="progress">📋 ${answersGiven+1} / ${dailyQuestions.length}</span>
                    <span class="daily-status">🎲 每日13题 · 独属你的神话</span>
                </div>
                <div class="question-text">${q.text}</div>
                <div class="options-grid" id="optionsGrid">
                    ${optionsHtml}
                </div>
                <div class="footnote">选你所想，解锁你的神话原型</div>
            </div>`;

        let selectedFunc = null;
        const btns = appDiv.querySelectorAll('.option-btn');
        btns.forEach(btn => {
            btn.addEventListener('click', () => {
                btns.forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                selectedFunc = btn.dataset.func;

                // T4：选中后 400ms 自动进入下一题
                clearTimeout(autoTimer);
                autoTimer = setTimeout(() => {
                    if (selectedFunc) advance(selectedFunc);
                }, 400);
            });
        });

        function advance(func) {
            clearTimeout(autoTimer);
            scoreMap[func] = (scoreMap[func] || 0) + 1;
            answersGiven++;
            currentQuestionIndex++;
            render();
        }
    }

    // ========== 结果页（含八功能得分条形图）==========
    function renderResult() {
        // 防御：resultArchetype 为 null 时使用降级对象
        if (!resultArchetype) {
            resultArchetype = archetypeList[0] || { name: '神秘原型', desc: '继续探索，答案在途中。' };
        }

        const proto = resultArchetype;
        const maxScore = Math.max(...FUNC_ORDER.map(f => scoreMap[f] || 0), 1);

        // 构建八功能得分条 HTML
        let barsHtml = '<div class="score-bars">';
        FUNC_ORDER.forEach(f => {
            const val   = scoreMap[f] || 0;
            const pct   = Math.round((val / maxScore) * 100);
            const color = FUNC_COLORS[f] || '#888';
            barsHtml += `
                <div class="score-row">
                    <span class="score-label">${f}</span>
                    <div class="score-track">
                        <div class="score-fill" style="width:${pct}%;background:${color}"></div>
                    </div>
                    <span class="score-val">${val}</span>
                </div>`;
        });
        barsHtml += '</div>';

        const shareText = `【原型人格洞察】今日我的核心原型是：${proto.name} —— ${proto.desc.substring(0,50)}... 快来测测你的神话人格！`;

        appDiv.innerHTML = `
            <div class="card result-container">
                <div class="stats-bar">
                    <span class="badge">🏛️ 原型揭晓</span>
                    <span class="daily-status">✨ 今日独家结果</span>
                </div>
                <div style="font-size:3rem;">🎭</div>
                <div class="prototype-name">${proto.name}</div>
                <div class="prototype-desc">${proto.desc}</div>
                ${barsHtml}
                <button class="share-btn" id="shareResultBtn">📤 分享结果 · 赛博铭文</button>
                <button class="reset-btn" id="resetBtn">🔄 明日再来（每日一测）</button>
                <hr>
                <div class="footnote">
                    基于荣格心理功能 · Victoria Lynn Schmidt 45种经典人物原型<br>
                    测试结果仅限今日，明日重启新篇章
                </div>
            </div>`;

        document.getElementById('shareResultBtn')?.addEventListener('click', () => {
            if (navigator.share) {
                navigator.share({ title: '我的原型人格', text: shareText }).catch(()=>{});
            } else {
                navigator.clipboard.writeText(shareText).then(() => {
                    alert('结果已复制，快分享给朋友吧！');
                }).catch(() => {
                    alert('分享失败，请手动复制结果~');
                });
            }
        });

        document.getElementById('resetBtn')?.addEventListener('click', () => {
            isResultMode   = false;
            answersGiven  = 0;
            currentQuestionIndex = 0;
            scoreMap = { Te:0, Fe:0, Se:0, Ne:0, Ti:0, Fi:0, Si:0, Ni:0 };
            if (isTodayTested()) {
                renderBlocked();
            } else {
                window.location.reload();
            }
        });
    }

    // ========== 初始化 ==========
    let dailyQuestions = [];
    function init() {
        dailyQuestions = getDailyQuestions();
        if (isTodayTested()) {
            const stored = getStoredResult();
            if (stored && stored.archetypeName) {
                resultArchetype = archetypeList.find(a => a.name === stored.archetypeName) || null;
                isResultMode = true;
            }
        }
        render();
    }

    init();
})();
