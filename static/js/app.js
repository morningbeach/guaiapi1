/**
 * 台灣公眾人物前科查詢機 - 前端 JavaScript
 */

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("searchForm");
    const nameInput = document.getElementById("nameInput");
    const searchBtn = document.getElementById("searchBtn");

    const loadingSection = document.getElementById("loadingSection");
    const errorSection = document.getElementById("errorSection");
    const resultsSection = document.getElementById("resultsSection");

    // ─── 表單送出 ───
    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const name = nameInput.value.trim();
        if (!name) return;

        // 清除舊結果
        hideAll();
        showLoading();

        try {
            const payload = {
                name,
                search_relatives: document.getElementById("searchRelatives").checked,
                case_type: document.getElementById("caseType").value,
            };

            // 模擬步驟進度
            simulateSteps();

            const resp = await fetch("/api/search", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            const result = await resp.json();

            hideLoading();

            if (!result.success) {
                showError(result.error || "查詢失敗");
                return;
            }

            renderResults(result.data);

        } catch (err) {
            hideLoading();
            showError("網路連線錯誤，請稍後再試。" + (err.message || ""));
        }
    });

    // ─── 顯示/隱藏控制 ───
    function hideAll() {
        loadingSection.classList.add("d-none");
        errorSection.classList.add("d-none");
        resultsSection.classList.add("d-none");
    }

    function showLoading() {
        loadingSection.classList.remove("d-none");
        searchBtn.disabled = true;
        searchBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> 查詢中...';
    }

    function hideLoading() {
        loadingSection.classList.add("d-none");
        searchBtn.disabled = false;
        searchBtn.innerHTML = '<i class="fas fa-search me-1"></i> 開始查詢';
    }

    function showError(msg) {
        errorSection.classList.remove("d-none");
        document.getElementById("errorMessage").textContent = msg;
    }

    // ─── 步驟動畫 ───
    function simulateSteps() {
        const steps = ["step1", "step2", "step3", "step4"];
        let i = 0;
        const interval = setInterval(() => {
            if (i > 0) {
                const prev = document.getElementById(steps[i - 1]);
                prev.classList.remove("active");
                prev.classList.add("done");
                prev.innerHTML = `<i class="fas fa-check-circle me-2"></i>${prev.textContent}`;
            }
            if (i < steps.length) {
                const curr = document.getElementById(steps[i]);
                curr.classList.remove("text-muted");
                curr.classList.add("active");
                curr.innerHTML = `<i class="fas fa-circle-notch fa-spin me-2"></i>${curr.textContent}`;
            } else {
                clearInterval(interval);
            }
            i++;
        }, 2500);

        // 儲存 interval 以便清除
        window._stepInterval = interval;
    }

    // ─── 渲染結果 ───
    function renderResults(data) {
        if (window._stepInterval) clearInterval(window._stepInterval);

        const { name, court_cases, relatives, news_results, risk_assessment } = data;

        // 風險卡片
        renderRiskCard(name, risk_assessment, court_cases.length, relatives.length, court_cases);

        // 關鍵發現
        renderFindings(risk_assessment);

        // 法院記錄
        renderCourtCases(court_cases);

        // 近親
        renderRelatives(relatives);

        // 新聞
        renderNews(news_results);

        // 免責聲明
        if (risk_assessment.disclaimer) {
            document.getElementById("disclaimer").textContent = risk_assessment.disclaimer;
        }

        // 顯示近親高風險警告
        const relativeCrimeCount = court_cases.filter(c => c.related_person && c.case_type === "刑事").length;
        const relativeWarningAlert = document.getElementById("relativeWarningAlert");
        if (relativeCrimeCount > 0) {
            relativeWarningAlert.classList.remove("d-none");
            relativeWarningAlert.classList.add("d-flex");
        } else {
            relativeWarningAlert.classList.add("d-none");
            relativeWarningAlert.classList.remove("d-flex");
        }

        // 顯示結果
        resultsSection.classList.remove("d-none");
        resultsSection.classList.add("animate-in");
        resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    // ─── 風險卡片 ───
    function renderRiskCard(name, risk, caseCount, relCount, courtCases) {
        const card = document.getElementById("riskCard");
        const gauge = document.getElementById("riskGauge");
        const score = document.getElementById("riskScore");
        const label = document.getElementById("riskLabel");

        // 計算近親案件數量
        const relativeCrimeCount = courtCases.filter(c => c.related_person).length;

        document.getElementById("resultName").textContent = name;
        document.getElementById("riskSummary").textContent = risk.summary || "無摘要";
        document.getElementById("criminalCount").textContent = risk.criminal_count || 0;
        document.getElementById("civilCount").textContent = risk.civil_count || 0;

        let relativeCrimeEl = document.getElementById("relativeCrimeCount");
        relativeCrimeEl.textContent = relativeCrimeCount;
        if (relativeCrimeCount > 0) {
            relativeCrimeEl.classList.add("text-danger");
            relativeCrimeEl.classList.add("pulse");
        } else {
            relativeCrimeEl.classList.remove("text-danger");
            relativeCrimeEl.classList.remove("pulse");
        }
        document.getElementById("relativeCount").textContent = relCount;
        document.getElementById("caseBadge").textContent = caseCount;
        document.getElementById("relativeBadge").textContent = relCount;

        // 統計並顯示涉案法院
        const courts = {};
        courtCases.forEach(c => {
            const courtName = c.court || "未知法院";
            courts[courtName] = (courts[courtName] || 0) + 1;
        });

        const courtsSection = document.getElementById("involvedCourtsSection");
        const courtsTags = document.getElementById("involvedCourtsTags");

        if (Object.keys(courts).length > 0) {
            courtsSection.classList.remove("d-none");

            // 依案件數量降序排序
            const sortedCourts = Object.entries(courts).sort((a, b) => b[1] - a[1]);

            courtsTags.innerHTML = sortedCourts.map(([court, count]) => `
                <span class="badge bg-secondary opacity-75 fw-normal rounded-pill px-2 py-1" style="font-size: 0.8rem;">
                    ${escHtml(court)} <span class="badge bg-white text-dark ms-1 rounded-circle" style="padding: 0.15rem 0.35rem;">${count}</span>
                </span>
            `).join("");
        } else {
            courtsSection.classList.add("d-none");
            courtsTags.innerHTML = "";
        }

        // 風險等級對應
        const riskMap = {
            "極高": { cls: "extreme", cardCls: "risk-extreme", color: "#f85149" },
            "高": { cls: "high", cardCls: "risk-high", color: "#f0883e" },
            "中": { cls: "medium", cardCls: "risk-medium", color: "#d29922" },
            "低": { cls: "low", cardCls: "risk-low", color: "#3fb950" },
            "極低": { cls: "very-low", cardCls: "risk-very-low", color: "#388bfd" },
        };

        const riskInfo = riskMap[risk.overall_risk] || riskMap["極低"];

        // 清除舊 class
        card.className = "card risk-card " + riskInfo.cardCls;
        gauge.className = "risk-gauge " + riskInfo.cls;

        // 動畫分數
        animateNumber(score, risk.risk_score || 0);
        score.style.color = riskInfo.color;
        label.textContent = risk.overall_risk || "未知";
        label.style.color = riskInfo.color;
    }

    function animateNumber(el, target) {
        let current = 0;
        const step = Math.max(1, Math.floor(target / 30));
        const timer = setInterval(() => {
            current += step;
            if (current >= target) {
                current = target;
                clearInterval(timer);
            }
            el.textContent = current;
        }, 30);
    }

    // ─── 關鍵發現 ───
    function renderFindings(risk) {
        const container = document.getElementById("keyFindings");
        const findings = risk.key_findings || [];

        if (findings.length === 0) {
            container.innerHTML = '<p class="text-muted">無關鍵發現</p>';
        } else {
            container.innerHTML = "<h5 class='mb-3'><i class='fas fa-lightbulb text-warning me-2'></i>關鍵發現</h5>" +
                findings.map(f => `
                    <div class="finding-item">
                        <span class="finding-icon">⚠️</span>
                        <span class="finding-text">${escHtml(f)}</span>
                    </div>
                `).join("");
        }

        // 案件類別
        const catSection = document.getElementById("categoriesSection");
        const cats = risk.categories || [];
        if (cats.length > 0) {
            catSection.innerHTML = "<h6 class='mb-2'>涉及類別</h6>" +
                cats.map(c => `<span class="category-tag">${escHtml(c)}</span>`).join("");
        } else {
            catSection.innerHTML = "";
        }

        // 建議
        const recSection = document.getElementById("recommendationsSection");
        if (risk.recommendations) {
            recSection.innerHTML = `
                <h6 class="mb-2"><i class="fas fa-clipboard-check me-1"></i>建議</h6>
                <div class="recommendation-box">${escHtml(risk.recommendations)}</div>
            `;
        } else {
            recSection.innerHTML = "";
        }

        // 近親風險
        const relRiskSection = document.getElementById("relativeRisks");
        const relRisks = risk.relative_risks || [];
        if (relRisks.length > 0) {
            relRiskSection.innerHTML = "<h6 class='mb-2'><i class='fas fa-user-friends me-1'></i>近親風險</h6>" +
                relRisks.map(r => `
                    <div class="relative-risk-item">
                        <strong>${escHtml(r.name || "")}</strong>
                        <span class="text-muted">（${escHtml(r.relation || "")}）</span>
                        <span class="ms-2">${escHtml(r.risk_note || "")}</span>
                    </div>
                `).join("");
        } else {
            relRiskSection.innerHTML = "";
        }
    }

    // ─── 法院記錄 ───
    function renderCourtCases(cases) {
        const container = document.getElementById("courtCasesList");

        if (!cases || cases.length === 0) {
            container.innerHTML = `
                <div class="text-center py-5 text-muted">
                    <i class="fas fa-search fa-3x mb-3"></i>
                    <p>未找到相關法院裁判書記錄</p>
                    <small>這可能表示此人無公開的法院訴訟記錄，或姓名不夠精確</small>
                </div>`;
            return;
        }

        container.innerHTML = cases.map((c, i) => {
            const badgeClass = {
                "刑事": "badge-criminal",
                "民事": "badge-civil",
                "行政": "badge-admin",
            }[c.case_type] || "badge-other";

            const relatedTag = c.related_person
                ? `<span class="badge bg-info ms-2">近親：${escHtml(c.related_person)}（${escHtml(c.relation || "")}）</span>`
                : "";

            return `
                <div class="case-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <span class="case-type-badge ${badgeClass}">${escHtml(c.case_type || "其他")}</span>
                            ${relatedTag}
                            <span class="text-muted ms-2 small">${escHtml(c.date || "")}</span>
                        </div>
                        <span class="text-muted small">#${i + 1}</span>
                    </div>
                    <div class="mt-2">
                        <strong>${escHtml(c.case_number || "案號未知")}</strong>
                        ${c.court ? ` <span class="text-muted">— ${escHtml(c.court)}</span>` : ""}
                    </div>
                    ${c.title ? `<div class="mt-1 text-info fw-bold">${escHtml(c.title)}</div>` : ""}
                    ${c.verdict ? `<div class="mt-2 p-2 bg-light border-start border-4 border-primary small"><strong>💡 判決主文：</strong><br>${escHtml(c.verdict)}</div>` : ""}
                    ${c.summary ? `<div class="mt-2 p-2 bg-light border-start border-4 border-secondary small text-muted"><strong>📄 判決重點節錄：</strong><br>${escHtml(c.summary)}</div>` : ""}
                    ${c.url ? `<a href="${escHtml(c.url)}" target="_blank" class="btn btn-sm btn-outline-primary mt-3"><i class="fas fa-external-link-alt me-1"></i>查看完整原始判決書</a>` : ""}
                </div>
            `;
        }).join("");
    }

    // ─── 近親資料 ───
    function renderRelatives(relatives) {
        const container = document.getElementById("relativesList");

        if (!relatives || relatives.length === 0) {
            container.innerHTML = `
                <div class="text-center py-5 text-muted">
                    <i class="fas fa-users fa-3x mb-3"></i>
                    <p>未找到公開的近親資訊</p>
                    <small>此功能透過維基百科和公開報導搜尋，非所有公眾人物都有公開的親屬資料</small>
                </div>`;
            return;
        }

        const icons = {
            "配偶": "💑", "父母": "👨‍👩‍👦", "子女": "👶",
            "兄弟姊妹": "👫", "其他親屬": "👥",
        };

        container.innerHTML = '<div class="row g-3">' +
            relatives.map(r => {
                const icon = icons[r.relation_category] || "👤";
                const confClass = {
                    "高": "confidence-high",
                    "中": "confidence-medium",
                    "低": "confidence-low",
                }[r.confidence] || "confidence-low";

                return `
                    <div class="col-6 col-md-4 col-lg-3">
                        <div class="relative-card">
                            <div class="relative-avatar">${icon}</div>
                            <div class="relative-name">${escHtml(r.name)}</div>
                            <div class="relative-relation">${escHtml(r.relation)}</div>
                            <div class="confidence-tag ${confClass}">${escHtml(r.confidence || "低")} 可信度</div>
                            <div class="small text-muted mt-1">${escHtml(r.source || "")}</div>
                        </div>
                    </div>
                `;
            }).join("") + "</div>";
    }

    // ─── 新聞報導 ───
    function renderNews(news) {
        const container = document.getElementById("newsList");

        if (!news || news.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-newspaper"></i>
                    <p>未找到相關報導</p>
                    <small>系統會自動搜尋公開新聞與法院資料</small>
                </div>`;
            return;
        }

        // 統計負面新聞數量
        const negativeCount = news.filter(n => n.is_negative).length;

        let headerHtml = '';
        if (negativeCount > 0) {
            headerHtml = `
                <div class="mb-3 p-3" style="background: rgba(224,49,49,.05); border-radius: 10px; border: 1px solid rgba(224,49,49,.1);">
                    <i class="fas fa-exclamation-triangle me-2" style="color: #e03131;"></i>
                    <strong style="color: #e03131;">發現 ${negativeCount} 則負面相關報導</strong>
                    <small class="ms-2" style="color: #868e96;">（含爭議、訴訟、違法等關鍵字）</small>
                </div>
            `;
        }

        const newsHtml = news.map((n, i) => {
            const negativeTag = n.is_negative
                ? `<span class="news-negative-tag"><i class="fas fa-exclamation-circle me-1"></i>負面</span>`
                : '';

            return `
                <div class="news-item">
                    <div>
                        <span style="color: #868e96; font-size: .75rem;">#${i + 1}</span>
                        <a href="${escHtml(n.url || '#')}" target="_blank" class="ms-2">
                            ${escHtml(n.title || "無標題")}
                        </a>
                        ${negativeTag}
                    </div>
                    ${n.snippet ? `<div class="news-snippet">${escHtml(n.snippet)}</div>` : ""}
                </div>
            `;
        }).join("");

        container.innerHTML = headerHtml + newsHtml;
    }

    // ─── 工具函式 ───
    function escHtml(str) {
        if (!str) return "";
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }
});
