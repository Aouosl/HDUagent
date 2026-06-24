/**
 * 凌霄 公共工具函数
 */
window.Utils = {
    formatDate(dateStr, withSeconds) {
        const d = new Date(dateStr);
        const opts = { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" };
        if (withSeconds) opts.second = "2-digit";
        return d.toLocaleString("zh-CN", opts);
    },

    getSeverityLabel(severity) {
        const map = { critical: "致命", high: "高危", medium: "中危", low: "低危" };
        return map[(severity || "").toLowerCase()] || severity || "未知";
    },

    getSeverityClass(severity) {
        const s = (severity || "").toLowerCase();
        if (s === "critical") return "bg-rose-500/20 text-rose-300 border-rose-700/50";
        if (s === "high") return "bg-orange-500/20 text-orange-300 border-orange-700/50";
        if (s === "medium") return "bg-amber-500/20 text-amber-300 border-amber-700/50";
        return "bg-blue-500/20 text-blue-300 border-blue-700/50";
    },

    getAgentLabel(name) {
        const map = { pentest_agent: "IronAgent", pentagi: "GSAgent", ctf_agent: "YYYAgent" };
        return map[name] || name;
    },

    getAgentClass(name) {
        if (name === "pentest_agent") return "bg-emerald-500/20 text-emerald-300";
        if (name === "pentagi") return "bg-purple-500/20 text-purple-300";
        if (name === "ctf_agent") return "bg-amber-500/20 text-amber-300";
        return "bg-slate-500/20 text-slate-300";
    },

    getStatusLabel(status) {
        const map = { pending: "待执行", running: "运行中", completed: "已完成", failed: "失败" };
        return map[status] || status || "未知";
    },

    getStatusClass(status) {
        if (status === "pending") return "bg-blue-500/20 text-blue-300 border-blue-700/50";
        if (status === "running") return "bg-indigo-500/20 text-indigo-300 border-indigo-700/50 animate-pulse";
        if (status === "completed") return "bg-emerald-500/20 text-emerald-300 border-emerald-700/50";
        if (status === "failed") return "bg-rose-500/20 text-rose-300 border-rose-700/50";
        return "bg-slate-500/20 text-slate-300 border-slate-700/50";
    },

    formatTokens(count) {
        if (!count) return "0";
        if (count >= 1000000) return (count / 1000000).toFixed(1) + "M";
        if (count >= 1000) return (count / 1000).toFixed(1) + "K";
        return count.toString();
    },

    renderMarkdown(text) {
        if (!text) return '<p class="text-center opacity-50 my-10">暂无详细报告内容</p>';
        if (window.marked) return window.marked.parse(text);
        return text.replace(/\n/g, "<br>");
    },

    generateId(prefix) {
        return (prefix || "id") + "_" + Date.now() + "_" + Math.random().toString(36).substr(2, 6);
    }
};
