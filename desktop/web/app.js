"use strict";

const form = document.querySelector("#optimizerForm");
const startButton = document.querySelector("#startButton");
const stopButton = document.querySelector("#stopButton");
const statusBadge = document.querySelector("#statusBadge");
const stageName = document.querySelector("#stageName");
const stageCounter = document.querySelector("#stageCounter");
const stageProgress = document.querySelector("#stageProgress");
const stageDetail = document.querySelector("#stageDetail");
const logOutput = document.querySelector("#logOutput");
const errorBox = document.querySelector("#errorBox");
const resultSection = document.querySelector("#resultSection");
const familyTabs = document.querySelector("#familyTabs");
const winnerCard = document.querySelector("#winnerCard");
const resultRows = document.querySelector("#resultRows");
const toast = document.querySelector("#toast");
const langToggle = document.querySelector("#langToggle");
const customSourcePanel = document.querySelector("#customSourcePanel");
const scopeFieldset = document.querySelector("#scopeFieldset");
const domainInput = document.querySelector("#domainInput");
const domainFile = document.querySelector("#domainFile");
const domainSourceStatus = document.querySelector("#domainSourceStatus");
const subscriptionUrl = document.querySelector("#subscriptionUrl");
const cnameForm = document.querySelector("#cnameForm");
const cnameTarget = document.querySelector("#cnameTarget");
const cnameStatus = document.querySelector("#cnameStatus");
const saveCnameButton = document.querySelector("#saveCnameButton");

let lastResultStamp = "";
let latestResult = null;
let activeFamily = "";
let toastTimer = 0;
let lastState = null;
let domainCount = 0;
let requestToken = "";
let maxSourceBytes = 1024 * 1024;
let customDomains = [];
let customSourceFormat = "";
let parsedInputText = "";
let sourceMessageKey = "sourceWaiting";
let sourceMessageValues = {};
let sourceMessageError = false;
let currentLang = localStorage.getItem("rr-domain-language") === "en" ? "en" : "zh";

const COPY = {
  zh: {
    documentTitle: "RR Cloudflare 域名优选", homeAria: "RR Edge Atlas 首页", brandName: "Edge Atlas", brandSub: "RR Cloudflare Optimizer", localOnly: "原生固定 IP 探测",
    eyebrow: "与 Android 2.7.1 同源算法", heroTitle: "找到这条网络上，", heroSubtitle: "真正稳定的 Cloudflare 域名。",
    heroLead: "固定候选 IP、保持 speed.cloudflare.com 的 SNI 与证书校验，经过 Pre、Micro、Full 三层筛选。排名首先看最差地址底线，失败测速按 0 计。",
    pillPool: "1000 域名池", pillStack: "IPv4 / IPv6", pillLocal: "三网可用", pillExport: "POP 漂移复核",
    signalTitle: "LIVE ROUTE MODEL", signalLocal: "READY", signalSelect: "EDGE", localSample: "Address Floor", ready: "Priority 01",
    preferencesKicker: "RUN CONFIGURATION", preferencesTitle: "开始一轮优选", networkLegend: "当前网络", operatorAuto: "自动",
    operatorMobile: "移动", operatorTelecom: "电信", operatorUnicom: "联通",
    operatorNote: "标签只用于历史记录，不会人为修改排名。请在需要使用域名的同一条网络上测试。",
    stackLegend: "协议栈", stackDual: "双栈", modeLegend: "测速策略", balancedTitle: "均衡模式", recommended: "推荐",
    balancedDesc: "适合三网日常优选，5 个域名进入最终决赛。", regionTitle: "亚洲入口狩猎",
    regionDesc: "优先 HKG、NRT、SIN，扩大到 20 个决赛名额。", sourceLegend: "候选来源", sourceBuiltin: "内置域名池", sourceCustom: "我的域名",
    manualDomains: "单个或多个域名", domainPlaceholder: "example.com\ncdn.example.net", parseDomains: "识别输入", chooseFile: "导入文件",
    subscriptionPlaceholder: "https://example.com/domains.txt", fetchSubscription: "读取订阅", sourceWaiting: "等待识别域名。支持 TXT、CSV、TSV、JSON 和 Base64 文本。",
    sourceDirty: "输入已改变，请重新识别", sourceLoading: "正在读取并识别…", sourceReady: "已识别 {count} 个域名 · {format}", sourceFailed: "域名源识别失败", fileTooLarge: "文件不能超过 1 MiB",
    scopeLegend: "候选规模",
    scopeFull: "完整 1000 域名 · 正式测试", scope200: "前 200 域名 · 快速预览", scope50: "前 50 域名 · 调试检查",
    trafficTitle: "流量提醒", trafficNote: "：DNS 初筛不下载文件；进入 Pre、Micro、Full 后才产生流量。双栈与亚洲狩猎耗时和流量更高。",
    start: "开始原生优选", stop: "停止", progressKicker: "MEASUREMENT CONSOLE", progressTitle: "实时状态", idle: "待命",
    running: "测速中", stopping: "停止中", completed: "已完成", cancelled: "已停止", error: "错误",
    waitingStart: "等待开始", stageIdle: "选择参数后开始，浏览器关闭不会改变测速算法。", stageRunning: "正在执行原生网络探测…",
    runLocation: "探测方式", onDevice: "固定 IP + SNI", compareMethod: "连接模型", stagedTest: "HTTP/1.1 冷连接", integrity: "完整性",
    waitingTask: "等待测速任务…", resultsKicker: "FINAL ADDRESS FLOOR RANKING", resultsTitle: "本轮结果",
    resultsDesc: "第一排序键是域名所有 Full 地址中最差的成绩；任一地址失败，底线直接为 0。", exportCsv: "导出 CSV", exportJson: "导出 JSON",
    thDomain: "排名 / 域名", thFloor: "地址底线", thAverage: "平均速度", thSuccess: "成功率", thVariation: "波动", thAddress: "地址",
    resultNote: "结果只代表本轮、当前网络与当前出口。更换 Wi-Fi、运营商、VPN 或出口后请重新测试。",
    method1Title: "冻结 DNS 快照", method1Desc: "1000 个域名只解析一次，过滤非 Cloudflare 地址并按 IP 去重，后续阶段不重新解析。",
    method2Title: "三层真实下载", method2Desc: "Pre 快速淘汰，Micro 小流量复核，Full 完整测速覆盖晋级域名的每个地址。",
    method3Title: "最差地址优先", method3Desc: "失败按 0 计，先比较地址底线，再比较成功率、最低速度、平均速度、波动和 TTFB。",
    legalTitle: "使用边界 · 非官方独立工具",
    legalText: "本工具仅用于个人在自有或获授权网络中的质量评估与域名选择，不提供端口扫描、漏洞探测、压力测试或绕过访问控制能力。测试对象仅为公开可访问的域名与公开测试端点。请遵守所在地法律和相关服务条款；Cloudflare 等名称与商标归其权利人所有，本工具与相关服务商不存在隶属、合作、赞助或背书关系。",
    footerBrand: "RR Edge Atlas · Local only", footerPrivacy: "数据保存在本机，不上传测速结果", poolCount: "{count} 个候选域名", poolUnavailable: "域名池不可用",
    fullScopeShort: "完整 1000 域名", limitedScope: "前 {count} 个域名", customScope: "自定义 {count} 个域名（仅测试这批）", dual: "双栈", balanced: "均衡模式", region: "亚洲入口狩猎",
    confirm: "将使用 {scope}、{stack}、{mode}开始真实下载测速。\n\n请确认当前网络就是最终使用域名的网络，并暂时关闭 VPN/代理。",
    started: "测速已开始", stopSent: "停止信号已发送", noResult: "本协议族没有有效结果", retryHint: "请查看日志后换网络或协议栈重试。",
    currentBest: "01 · 本轮冠军", regionResult: "亚洲入口榜", unknownPop: "POP 未知", stability: "稳定性", compareInsufficient: "参考对比数据不足",
    bestAddress: "最佳地址", floor: "地址底线", average: "完整平均", successVariation: "成功 / 波动", worstAddress: "最差地址",
    copyDomain: "复制域名", setCname: "设为 CNAME", copied: "域名已复制", copyFailed: "复制失败，请手动选择域名", serviceError: "无法连接本地服务",
    cnameKicker: "CLOUDFLARE DNS", cnameTitle: "把优选域名写入自己的 CNAME", cnameDesc: "可手动填写目标，也可在测速结果中点“设为 CNAME”。同名 CNAME 会安全更新；遇到 A、AAAA 等冲突记录会停止。",
    tokenLocal: "Token 仅在本机当次使用", zoneNameLabel: "Cloudflare 区域域名", zoneIdLabel: "Zone ID（可选）", recordNameLabel: "自己的 CNAME 域名",
    zoneNamePlaceholder: "example.com", zoneIdPlaceholder: "32 位 Zone ID", recordNamePlaceholder: "edge.example.com", targetPlaceholder: "preferred.example.net", tokenPlaceholder: "仅需目标区域 DNS 编辑权限",
    targetLabel: "优选目标域名", tokenLabel: "Cloudflare API Token", proxyLabel: "启用橙云代理", proxyWarning: "优选 CNAME 默认建议保持 DNS only；橙云可能改变实际入口，跨账号目标还可能触发 1014。",
    saveCname: "新增 / 更新 CNAME", tokenPermission: "建议新建最小权限 Token：仅目标区域 DNS Edit。若不填 Zone ID、让工具按区域域名自动查找，还需 Zone Read。",
    cnameSelected: "已选中 {domain}，请填写自己的记录名和 Token", cnameSaving: "正在写入 Cloudflare DNS…", cnameCreated: "CNAME 已创建：{name} → {target}", cnameUpdated: "CNAME 已更新：{name} → {target}", cnameUnchanged: "CNAME 已是目标值，无需修改：{name} → {target}",
    stableReference: "参考域名表现稳定，继续保留", suggestCandidate: "建议改用当前候选", observeCandidate: "候选略有领先，建议继续观察", keepReference: "继续保留参考域名",
    excellent: "优秀", good: "良好", fair: "一般", poor: "较差"
  },
  en: {
    documentTitle: "RR Cloudflare Domain Optimizer", homeAria: "RR Edge Atlas home", brandName: "Edge Atlas", brandSub: "RR CLOUDFLARE OPTIMIZER", localOnly: "Native fixed-IP probing",
    eyebrow: "SAME CORE LOGIC AS ANDROID 2.7.1", heroTitle: "Find the Cloudflare domain", heroSubtitle: "that stays stable on this network.",
    heroLead: "Pin candidate IPs, preserve speed.cloudflare.com SNI and certificate validation, then run Pre, Micro, and Full stages. The worst-address floor ranks first, and failed transfers count as zero.",
    pillPool: "1,000-domain pool", pillStack: "IPv4 / IPv6", pillLocal: "Three carriers", pillExport: "POP drift review",
    signalTitle: "LIVE ROUTE MODEL", signalLocal: "READY", signalSelect: "EDGE", localSample: "Address Floor", ready: "Priority 01",
    preferencesKicker: "RUN CONFIGURATION", preferencesTitle: "Start a benchmark", networkLegend: "Current network", operatorAuto: "Auto",
    operatorMobile: "China Mobile", operatorTelecom: "China Telecom", operatorUnicom: "China Unicom",
    operatorNote: "The carrier label is stored with history only and never changes ranking. Test on the same network where the domain will be used.",
    stackLegend: "IP stack", stackDual: "Dual stack", modeLegend: "Benchmark strategy", balancedTitle: "Balanced mode", recommended: "Recommended",
    balancedDesc: "Designed for routine three-carrier testing; five domains reach the final.", regionTitle: "Asia entry hunt",
    regionDesc: "Prioritizes HKG, NRT, and SIN, with twenty final slots.", sourceLegend: "Candidate source", sourceBuiltin: "Built-in pool", sourceCustom: "My domains",
    manualDomains: "One or more domains", domainPlaceholder: "example.com\ncdn.example.net", parseDomains: "Parse input", chooseFile: "Import file",
    subscriptionPlaceholder: "https://example.com/domains.txt", fetchSubscription: "Load subscription", sourceWaiting: "Waiting for domains. Supports TXT, CSV, TSV, JSON, and Base64 text.",
    sourceDirty: "Input changed; parse it again", sourceLoading: "Loading and parsing…", sourceReady: "Parsed {count} domains · {format}", sourceFailed: "Could not parse the domain source", fileTooLarge: "The file must not exceed 1 MiB",
    scopeLegend: "Candidate scope",
    scopeFull: "Full 1,000 domains · Formal run", scope200: "First 200 domains · Quick preview", scope50: "First 50 domains · Diagnostic",
    trafficTitle: "Traffic note", trafficNote: ": DNS screening downloads nothing. Pre, Micro, and Full use traffic; dual stack and Asia hunt require more time and data.",
    start: "Start native benchmark", stop: "Stop", progressKicker: "MEASUREMENT CONSOLE", progressTitle: "Live Status", idle: "Idle",
    running: "Benchmarking", stopping: "Stopping", completed: "Completed", cancelled: "Stopped", error: "Error",
    waitingStart: "Waiting to start", stageIdle: "Choose settings to begin. Closing the browser does not change the benchmark algorithm.", stageRunning: "Running native network probes…",
    runLocation: "Probe method", onDevice: "Fixed IP + SNI", compareMethod: "Connection model", stagedTest: "HTTP/1.1 cold connection", integrity: "Integrity",
    waitingTask: "Waiting for a benchmark…", resultsKicker: "FINAL ADDRESS FLOOR RANKING", resultsTitle: "Run Results",
    resultsDesc: "The first ranking key is the worst Full result across every address; one failed address sets the floor to zero.", exportCsv: "Export CSV", exportJson: "Export JSON",
    thDomain: "Rank / Domain", thFloor: "Address floor", thAverage: "Average", thSuccess: "Success", thVariation: "Variation", thAddress: "Addresses",
    resultNote: "Results represent only this run, network, and egress. Run again after changing Wi-Fi, carrier, VPN, or egress.",
    method1Title: "Freeze the DNS snapshot", method1Desc: "Resolve 1,000 domains once, remove non-Cloudflare addresses, and deduplicate by IP. Later stages never resolve again.",
    method2Title: "Three real download stages", method2Desc: "Pre eliminates quickly, Micro reviews with light traffic, and Full covers every address of each finalist.",
    method3Title: "Worst address first", method3Desc: "Failures count as zero. Rank by address floor, success rate, minimum speed, average speed, variation, then TTFB.",
    legalTitle: "Usage boundary · Independent, unofficial tool",
    legalText: "This tool is only for personal network-quality evaluation and domain selection on networks you own or are authorized to test. It does not provide port scanning, vulnerability testing, stress testing, or access-control bypass features. Test targets are publicly reachable domains and public test endpoints. Follow applicable laws and service terms. Cloudflare and other names and marks belong to their owners; this tool is not affiliated with, partnered with, sponsored by, or endorsed by those providers.",
    footerBrand: "RR Edge Atlas · Local only", footerPrivacy: "Data stays on this device · No benchmark results uploaded", poolCount: "{count} candidate domains", poolUnavailable: "Domain pool unavailable",
    fullScopeShort: "all 1,000 domains", limitedScope: "the first {count} domains", customScope: "{count} custom domains (only this set)", dual: "Dual stack", balanced: "Balanced mode", region: "Asia entry hunt",
    confirm: "Start real download benchmarking using {scope}, {stack}, and {mode}?\n\nMake sure this is the network where you will use the domain, and temporarily disable VPN/proxy services.",
    started: "Benchmark started", stopSent: "Stop request sent", noResult: "No valid result for this IP family", retryHint: "Review the log, then try another network or IP stack.",
    currentBest: "01 · RUN CHAMPION", regionResult: "Asia entry ranking", unknownPop: "POP unknown", stability: "Stability", compareInsufficient: "Not enough reference data",
    bestAddress: "Best address", floor: "Address floor", average: "Full average", successVariation: "Success / variation", worstAddress: "Worst address",
    copyDomain: "Copy domain", setCname: "Set as CNAME", copied: "Domain copied", copyFailed: "Copy failed. Select the domain manually.", serviceError: "Cannot connect to the local service",
    cnameKicker: "CLOUDFLARE DNS", cnameTitle: "Point your own CNAME to a preferred domain", cnameDesc: "Enter a target manually or choose Set as CNAME in the results. Existing CNAMEs are updated safely; conflicting A or AAAA records stop the operation.",
    tokenLocal: "Token is used once on this device", zoneNameLabel: "Cloudflare zone name", zoneIdLabel: "Zone ID (optional)", recordNameLabel: "Your CNAME hostname",
    zoneNamePlaceholder: "example.com", zoneIdPlaceholder: "32-character Zone ID", recordNamePlaceholder: "edge.example.com", targetPlaceholder: "preferred.example.net", tokenPlaceholder: "DNS Edit for the target zone only",
    targetLabel: "Preferred target domain", tokenLabel: "Cloudflare API Token", proxyLabel: "Enable Cloudflare proxy", proxyWarning: "DNS only is recommended for a preferred-domain CNAME. Proxying may change the actual entry point, and cross-account targets may trigger error 1014.",
    saveCname: "Create / update CNAME", tokenPermission: "Use a least-privilege token with DNS Edit for only the target zone. Zone Read is also needed when the Zone ID is omitted and the zone is looked up by name.",
    cnameSelected: "Selected {domain}. Enter your hostname and Token.", cnameSaving: "Updating Cloudflare DNS…", cnameCreated: "CNAME created: {name} → {target}", cnameUpdated: "CNAME updated: {name} → {target}", cnameUnchanged: "CNAME already matches: {name} → {target}",
    stableReference: "The reference domain remains stable", suggestCandidate: "Suggested candidate", observeCandidate: "Candidate is slightly ahead; keep observing", keepReference: "Keep the reference domain",
    excellent: "Excellent", good: "Good", fair: "Fair", poor: "Poor"
  }
};

function t(key, values = {}) {
  let value = COPY[currentLang][key] ?? COPY.zh[key] ?? key;
  Object.entries(values).forEach(([name, replacement]) => {
    value = value.replaceAll(`{${name}}`, String(replacement));
  });
  return value;
}

function translateRuntime(value) {
  if (!value || currentLang === "zh") return value || "";
  const replacements = [
    ["等待开始", "Waiting to start"], ["准备优选", "Preparing selection"], ["优选完成", "Selection completed"],
    ["正在停止", "Stopping"], ["已停止", "Stopped"], ["发生错误", "An error occurred"],
    ["DNS 快照", "Domain snapshot"], ["候选快照", "Candidate snapshot"], ["POP 发现", "Region check"],
    ["初筛", "Initial screening"], ["小流量筛选", "Light screening"], ["最终复核", "Final review"], ["排名", "Ranking"],
    ["有效域名", "valid domains"], ["去重地址", "unique addresses"], ["去重 IP", "unique IPs"],
    ["安全预计流量上限", "estimated traffic ceiling"], ["当前晋级组合理论流量", "estimated traffic for selected set"],
    ["没有可用候选地址，已跳过", "No usable candidate addresses; skipped"], ["优选已停止", "Selection stopped"],
    ["最终候选", "Final candidates"], ["入围小流量筛选", "Selected for light screening"],
    ["个域名", " domains"], ["可用", " available"], ["完成", " completed"], ["失败", " failed"],
    ["含参考域名", "includes reference domain"], ["共享 IP 自动复用", "shared IPs reused"],
    ["本轮未发现", "Not found in this run:"], ["区域入口", "regional entry"], ["网络出口已变化，本轮结果作废", "Network egress changed; this run is invalid"]
  ];
  return replacements.reduce((text, [from, to]) => text.replaceAll(from, to), String(value));
}

function stabilityText(value) {
  const map = { "优秀": "excellent", "良好": "good", "一般": "fair", "较差": "poor" };
  return map[value] ? t(map[value]) : value || "—";
}

function verdictText(family) {
  const comparison = family?.baseline_comparison;
  if (!comparison) return t("compareInsufficient");
  if (currentLang === "zh" && comparison.message) return comparison.message;
  if (comparison.decision === "REPLACE") return `${t("suggestCandidate")} → ${comparison.challenger || "—"}`;
  if (comparison.decision === "OBSERVE") return t("observeCandidate");
  return comparison.challenger ? t("keepReference") : t("stableReference");
}

function updatePoolLabel() {
  const custom = form.querySelector('input[name="domainSource"]:checked')?.value === "custom";
  document.querySelector("#poolCount").textContent = custom
    ? (customDomains.length ? t("customScope", { count: customDomains.length }) : t("sourceCustom"))
    : (domainCount ? t("poolCount", { count: domainCount }) : t("poolUnavailable"));
}

function renderSourceStatus() {
  domainSourceStatus.textContent = t(sourceMessageKey, sourceMessageValues);
  domainSourceStatus.classList.toggle("error", sourceMessageError);
  domainSourceStatus.classList.toggle("ready", sourceMessageKey === "sourceReady");
}

function setSourceStatus(key, values = {}, error = false) {
  sourceMessageKey = key;
  sourceMessageValues = values;
  sourceMessageError = error;
  renderSourceStatus();
}

function applyLanguage() {
  document.documentElement.lang = currentLang === "zh" ? "zh-CN" : "en";
  document.title = t("documentTitle");
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAria));
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.setAttribute("placeholder", t(element.dataset.i18nPlaceholder));
  });
  langToggle.textContent = currentLang === "zh" ? "EN" : "中";
  langToggle.setAttribute("aria-label", currentLang === "zh" ? "Switch to English" : "切换到中文");
  updatePoolLabel();
  renderSourceStatus();
  if (lastState) updateStatus(lastState);
  if (latestResult) renderResults();
}

langToggle.addEventListener("click", () => {
  currentLang = currentLang === "zh" ? "en" : "zh";
  localStorage.setItem("rr-domain-language", currentLang);
  applyLanguage();
});

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function fmt(value, digits = 1) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "—";
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("show"), 1800);
}

async function request(url, options = {}) {
  const requestOptions = { ...options };
  const method = String(requestOptions.method || "GET").toUpperCase();
  if (method !== "GET") {
    const headers = new Headers(requestOptions.headers || {});
    headers.set("Content-Type", "application/json");
    if (requestToken) headers.set("X-RR-Request-Token", requestToken);
    requestOptions.headers = headers;
    if (requestOptions.body === undefined) requestOptions.body = "{}";
  }
  const response = await fetch(url, requestOptions);
  const body = await response.json();
  if (!response.ok) throw new Error(body.message || body.error || `HTTP ${response.status}`);
  return body;
}

function selected(name) {
  return form.querySelector(`input[name="${name}"]:checked`).value;
}

function useCustomSource() {
  const customRadio = form.querySelector('input[name="domainSource"][value="custom"]');
  customRadio.checked = true;
  customSourcePanel.hidden = false;
  scopeFieldset.hidden = true;
  updatePoolLabel();
}

function syncSourceMode() {
  const custom = selected("domainSource") === "custom";
  customSourcePanel.hidden = !custom;
  scopeFieldset.hidden = custom;
  updatePoolLabel();
}

async function parseCustomText(text, filename = "manual.txt") {
  if (!String(text).trim()) throw new Error(t("sourceWaiting"));
  setSourceStatus("sourceLoading");
  const answer = await request("/api/domains/parse", {
    method: "POST",
    body: JSON.stringify({ text, filename })
  });
  customDomains = Array.isArray(answer.domains) ? answer.domains : [];
  customSourceFormat = String(answer.format || "TXT");
  domainInput.value = customDomains.join("\n");
  parsedInputText = domainInput.value;
  useCustomSource();
  setSourceStatus("sourceReady", { count: customDomains.length, format: customSourceFormat });
  if (answer.warnings?.length) showToast(answer.warnings.join(" · "));
  return customDomains;
}

async function ensureCustomDomains() {
  if (customDomains.length && parsedInputText === domainInput.value) return customDomains;
  return parseCustomText(domainInput.value);
}

form.querySelectorAll('input[name="domainSource"]').forEach((radio) => radio.addEventListener("change", syncSourceMode));

domainInput.addEventListener("input", () => {
  customDomains = [];
  parsedInputText = "";
  setSourceStatus("sourceDirty");
  updatePoolLabel();
});

document.querySelector("#parseDomainsButton").addEventListener("click", async () => {
  try {
    await parseCustomText(domainInput.value);
  } catch (error) {
    setSourceStatus("sourceFailed", {}, true);
    showToast(error.message);
  }
});

document.querySelector("#chooseDomainFile").addEventListener("click", () => domainFile.click());

domainFile.addEventListener("change", async () => {
  const file = domainFile.files?.[0];
  if (!file) return;
  try {
    if (file.size > maxSourceBytes) throw new Error(t("fileTooLarge"));
    await parseCustomText(await file.text(), file.name);
  } catch (error) {
    setSourceStatus("sourceFailed", {}, true);
    showToast(error.message);
  } finally {
    domainFile.value = "";
  }
});

document.querySelector("#fetchSubscriptionButton").addEventListener("click", async () => {
  const url = subscriptionUrl.value.trim();
  try {
    setSourceStatus("sourceLoading");
    const answer = await request("/api/domains/fetch", {
      method: "POST",
      body: JSON.stringify({ url })
    });
    customDomains = Array.isArray(answer.domains) ? answer.domains : [];
    customSourceFormat = String(answer.format || "TXT");
    domainInput.value = customDomains.join("\n");
    parsedInputText = domainInput.value;
    useCustomSource();
    setSourceStatus("sourceReady", { count: customDomains.length, format: customSourceFormat });
    if (answer.warnings?.length) showToast(answer.warnings.join(" · "));
  } catch (error) {
    setSourceStatus("sourceFailed", {}, true);
    showToast(error.message);
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const limit = Number(document.querySelector("#limitSelect").value);
  const family = selected("family");
  const mode = selected("mode");
  const source = selected("domainSource");
  let domains = [];
  if (source === "custom") {
    try {
      domains = await ensureCustomDomains();
    } catch (error) {
      setSourceStatus("sourceFailed", {}, true);
      showToast(error.message);
      return;
    }
  }
  const scope = source === "custom"
    ? t("customScope", { count: domains.length })
    : (limit === 0 ? t("fullScopeShort") : t("limitedScope", { count: limit }));
  const stack = family === "dual" ? t("dual") : family.toUpperCase();
  const strategy = mode === "asia" ? t("region") : t("balanced");
  if (!window.confirm(t("confirm", { scope, stack, mode: strategy }))) return;
  try {
    const body = {
      operator: selected("operator"),
      family,
      mode,
      limit,
      source,
      domains
    };
    const answer = await request("/api/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    showToast(answer.ok ? t("started") : translateRuntime(answer.message));
    lastResultStamp = "";
    resultSection.hidden = true;
  } catch (error) {
    showToast(translateRuntime(error.message));
  }
});

stopButton.addEventListener("click", async () => {
  try {
    const answer = await request("/api/stop", { method: "POST" });
    showToast(answer.ok ? t("stopSent") : translateRuntime(answer.message));
  } catch (error) {
    showToast(translateRuntime(error.message));
  }
});

function updateStatus(state) {
  lastState = state;
  const running = state.status === "running" || state.status === "stopping";
  startButton.disabled = running;
  stopButton.disabled = state.status !== "running";
  statusBadge.className = `status-badge ${state.status}`;
  statusBadge.innerHTML = `<i></i><b>${escapeHtml(t(state.status) || state.status)}</b>`;
  stageName.textContent = translateRuntime(state.stage) || t("waitingStart");
  stageCounter.textContent = state.total ? `${state.current} / ${state.total}` : "—";
  stageProgress.max = Math.max(1, Number(state.total) || 1);
  stageProgress.value = Math.min(stageProgress.max, Number(state.current) || 0);
  stageDetail.textContent = state.detail ? translateRuntime(state.detail) : (running ? t("stageRunning") : t("stageIdle"));
  logOutput.textContent = state.logs?.length ? state.logs.map(translateRuntime).join("\n") : t("waitingTask");
  logOutput.scrollTop = logOutput.scrollHeight;
  errorBox.hidden = !state.error;
  errorBox.textContent = translateRuntime(state.error) || "";
  if (state.result) {
    const stamp = `${state.result.created_at}:${state.status}`;
    if (stamp !== lastResultStamp) {
      lastResultStamp = stamp;
      latestResult = state.result;
      activeFamily = latestResult.families?.[0]?.family || "";
      renderResults();
    }
  }
}

function resultFamily() {
  return latestResult?.families?.find((item) => item.family === activeFamily) || null;
}

function rankRows(family) {
  return latestResult.mode === "asia" ? family.asia_ranked : family.ranked;
}

function renderResults() {
  if (!latestResult?.families?.length) return;
  resultSection.hidden = false;
  familyTabs.innerHTML = latestResult.families.map((family) => (
    `<button type="button" class="${family.family === activeFamily ? "active" : ""}" data-family="${escapeHtml(family.family)}">${escapeHtml(family.family)}</button>`
  )).join("");
  familyTabs.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      activeFamily = button.dataset.family;
      renderResults();
    });
  });
  const family = resultFamily();
  const rows = family ? rankRows(family) : [];
  const winner = rows?.[0];
  if (!winner) {
    winnerCard.innerHTML = `<div class="winner-domain"><small>NO VALID RESULT</small><h3>${escapeHtml(t("noResult"))}</h3><p>${escapeHtml(t("retryHint"))}</p></div>`;
    resultRows.innerHTML = "";
    return;
  }
  const verdict = verdictText(family);
  const modeNote = latestResult.mode === "asia"
    ? `${t("regionResult")} · ${winner.primary_pop || t("unknownPop")} · ${verdict}`
    : `${t("stability")} ${stabilityText(winner.stability)} · ${verdict}`;
  winnerCard.innerHTML = `
    <div class="winner-domain">
      <small>${escapeHtml(t("currentBest"))}</small>
      <h3>${escapeHtml(winner.domain)}</h3>
      <p>${escapeHtml(modeNote)} · ${escapeHtml(t("bestAddress"))} ${escapeHtml(winner.best_ip || "—")}</p>
    </div>
    <div class="winner-stat"><small>${escapeHtml(t("floor"))}</small><strong>${fmt(winner.address_floor_mbps)}</strong><em>Mbps</em></div>
    <div class="winner-stat"><small>${escapeHtml(t("average"))}</small><strong>${fmt(winner.avg_complete_mbps)}</strong><em>${fmt(winner.mb_per_sec, 2)} MB/s</em></div>
    <div class="winner-stat"><small>${escapeHtml(t("successVariation"))}</small><strong>${fmt(winner.success_rate_pct, 0)}%</strong><em>${fmt(winner.variation_pct)}% variation</em></div>`;
  resultRows.innerHTML = rows.map((row, index) => {
    const pop = row.primary_pop || "—";
    const ips = row.current_ips?.join(" · ") || "—";
    return `<tr>
      <td><div class="rank-domain"><span class="rank-number">${index + 1}</span><div><strong>${escapeHtml(row.domain)}</strong><small>TTFB ${fmt(row.median_ttfb_ms)} ms · ${escapeHtml(stabilityText(row.stability))}</small><div class="row-actions"><button class="copy-button" type="button" data-copy="${escapeHtml(row.domain)}">${escapeHtml(t("copyDomain"))}</button><button class="copy-button cname-button" type="button" data-cname="${escapeHtml(row.domain)}">${escapeHtml(t("setCname"))}</button></div></div></div></td>
      <td class="speed-cell"><strong>${fmt(row.address_floor_mbps)} Mbps</strong><small>${escapeHtml(t("worstAddress"))}</small></td>
      <td class="speed-cell"><strong>${fmt(row.avg_complete_mbps)} Mbps</strong><small>${fmt(row.mb_per_sec, 2)} MB/s</small></td>
      <td><span class="quality-pill">${fmt(row.success_rate_pct, 0)}%</span></td>
      <td>${fmt(row.variation_pct)}%</td>
      <td><span class="pop-pill">${escapeHtml(pop)}</span></td>
      <td class="address-cell">${escapeHtml(ips)}</td>
    </tr>`;
  }).join("");
  resultRows.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(button.dataset.copy);
        showToast(t("copied"));
      } catch (_error) {
        showToast(t("copyFailed"));
      }
    });
  });
  resultRows.querySelectorAll("[data-cname]").forEach((button) => {
    button.addEventListener("click", () => selectCnameTarget(button.dataset.cname));
  });
}

function setCnameStatus(message, error = false) {
  cnameStatus.hidden = false;
  cnameStatus.textContent = message;
  cnameStatus.classList.toggle("error", error);
}

function selectCnameTarget(domain) {
  cnameTarget.value = domain || "";
  setCnameStatus(t("cnameSelected", { domain }));
  document.querySelector("#cloudflareSection").scrollIntoView({ behavior: "smooth", block: "center" });
  window.setTimeout(() => document.querySelector("#recordName").focus(), 350);
}

cnameForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  saveCnameButton.disabled = true;
  setCnameStatus(t("cnameSaving"));
  try {
    const answer = await request("/api/cloudflare/cname", {
      method: "POST",
      body: JSON.stringify({
        api_token: document.querySelector("#apiToken").value,
        zone_name: document.querySelector("#zoneName").value,
        zone_id: document.querySelector("#zoneId").value,
        record_name: document.querySelector("#recordName").value,
        target: cnameTarget.value,
        proxied: document.querySelector("#proxiedToggle").checked
      })
    });
    const key = answer.operation === "created" ? "cnameCreated" : (answer.operation === "updated" ? "cnameUpdated" : "cnameUnchanged");
    setCnameStatus(t(key, { name: answer.name, target: answer.target }));
    document.querySelector("#apiToken").value = "";
  } catch (error) {
    setCnameStatus(error.message, true);
  } finally {
    saveCnameButton.disabled = false;
  }
});

async function poll() {
  try {
    updateStatus(await request("/api/status"));
  } catch (error) {
    errorBox.hidden = false;
    errorBox.textContent = `${t("serviceError")}：${error.message}`;
  } finally {
    window.setTimeout(poll, 700);
  }
}

async function initialize() {
  applyLanguage();
  syncSourceMode();
  try {
    const config = await request("/api/config");
    document.querySelector("#versionLabel").textContent = `Desktop ${config.version}`;
    domainCount = Number(config.domain_count) || 0;
    requestToken = String(config.request_token || "");
    maxSourceBytes = Number(config.max_source_bytes) || maxSourceBytes;
    updatePoolLabel();
  } catch (_error) {
    domainCount = 0;
    updatePoolLabel();
  }
  poll();
}

initialize();
