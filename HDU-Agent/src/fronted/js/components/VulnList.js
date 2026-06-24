const { ref, onMounted, watch } = window.Vue;

export default {
    name: "VulnList",
    props: ["token"],
    emits: ["show-toast"],
    template: `
        <main class="flex-1 overflow-y-auto p-4 md:p-6 transition-colors duration-300 bg-transparent">
            <div class="rounded-2xl shadow-sm border flex flex-col h-full transition-all backdrop-blur-md bg-slate-800/40 border-slate-700/50">
                <div class="p-5 border-b flex justify-between items-center border-slate-700/50">
                    <div>
                        <h2 class="text-lg font-bold text-slate-100">全局漏洞情报中心</h2>
                        <p class="text-xs mt-1 text-slate-400">展示所有用户、所有节点发现的安全漏洞数据</p>
                    </div>
                    <div class="flex gap-3 items-center">
                        <select v-model="filterSeverity" @change="fetchVulns(1)" class="py-1.5 px-3 text-xs rounded-lg bg-slate-700/50 border border-slate-600 text-slate-200 focus:outline-none focus:border-indigo-500/50">
                            <option value="">全部等级</option>
                            <option value="critical">致命</option>
                            <option value="high">高危</option>
                            <option value="medium">中危</option>
                            <option value="low">低危</option>
                        </select>
                        <button @click="fetchVulns(currentPage)" class="p-2 rounded-lg transition-colors hover:bg-indigo-500/10 text-slate-300 hover:text-indigo-300">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                        </button>
                    </div>
                </div>
                
                <div class="flex-1 overflow-auto p-0">
                    <table class="w-full text-sm text-left">
                        <thead class="text-xs uppercase sticky top-0 z-10 border-b backdrop-blur-md bg-slate-800/80 text-slate-300 border-slate-700/50">
                            <tr>
                                <th class="px-6 py-4 font-medium">发现时间</th>
                                <th class="px-6 py-4 font-medium">白帽子(用户)</th>
                                <th class="px-6 py-4 font-medium">攻击目标</th>
                                <th class="px-6 py-4 font-medium">漏洞名称</th>
                                <th class="px-6 py-4 font-medium">危险等级</th>
                                <th class="px-6 py-4 font-medium text-right">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-if="loading" class="border-b border-slate-700/50">
                                <td colspan="6" class="px-6 py-8 text-center text-slate-400">加载数据中...</td>
                            </tr>
                            <tr v-else-if="vulns.length === 0" class="border-b border-slate-700/50">
                                <td colspan="6" class="px-6 py-8 text-center text-slate-400">暂无漏洞情报</td>
                            </tr>
                            <tr v-else v-for="vuln in vulns" :key="vuln.id" class="border-b transition-colors hover:bg-slate-700/10 border-slate-700/50 text-slate-200">
                                <td class="px-6 py-4 font-mono text-xs">{{ formatDate(vuln.created_at) }}</td>
                                <td class="px-6 py-4">
                                    <span class="px-2.5 py-1 rounded-md text-xs font-semibold backdrop-blur-sm bg-indigo-500/30 text-indigo-200">@{{ vuln.username }}</span>
                                </td>
                                <td class="px-6 py-4 font-mono text-xs">{{ vuln.target }}</td>
                                <td class="px-6 py-4 font-medium text-slate-100">{{ vuln.vuln_name }}</td>
                                <td class="px-6 py-4">
                                    <span class="px-2.5 py-1 rounded-full text-xs border backdrop-blur-sm" :class="getSeverityClass(vuln.severity)">
                                        {{ getSeverityLabel(vuln.severity) }}
                                    </span>
                                </td>
                                <td class="px-6 py-4 text-right">
                                    <button @click="viewReport(vuln)" class="text-xs font-medium hover:underline text-indigo-300 hover:text-indigo-200">查看报告</button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                
                <div v-if="total > 0" class="flex justify-center items-center gap-2 my-4 py-2">
                    <button @click="fetchVulns(currentPage - 1)" :disabled="currentPage <= 1" class="px-3 py-1.5 text-xs rounded-lg border transition-colors" :class="currentPage <= 1 ? 'border-slate-700 text-slate-600 cursor-not-allowed' : 'border-slate-600 text-slate-300 hover:bg-slate-700'">&laquo; 上一页</button>
                    <span class="text-xs text-slate-400">第 {{ currentPage }} / {{ totalPages }} 页 (共 {{ total }} 条)</span>
                    <button @click="fetchVulns(currentPage + 1)" :disabled="currentPage >= totalPages" class="px-3 py-1.5 text-xs rounded-lg border transition-colors" :class="currentPage >= totalPages ? 'border-slate-700 text-slate-600 cursor-not-allowed' : 'border-slate-600 text-slate-300 hover:bg-slate-700'">下一页 &raquo;</button>
                </div>
            </div>

            <div v-if="selectedVuln" class="fixed inset-0 z-[200] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
                <div class="rounded-2xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl backdrop-blur-md bg-slate-900/90 border border-slate-700/50">
                    <div class="px-6 py-4 border-b flex justify-between items-center border-slate-700/50 bg-slate-800/50">
                        <div class="flex items-center gap-3">
                            <span class="px-2.5 py-1 rounded text-xs font-bold" :class="getSeverityClass(selectedVuln.severity)">{{ getSeverityLabel(selectedVuln.severity) }}</span>
                            <h3 class="font-bold text-lg text-slate-100">{{ selectedVuln.vuln_name }}</h3>
                        </div>
                        <button @click="selectedVuln = null" class="p-1 rounded-lg transition-colors hover:bg-rose-500/10 text-slate-400 hover:text-rose-400">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                        </button>
                    </div>
                    
                    <div class="px-6 py-3 border-b flex gap-6 text-sm border-slate-700/50 text-slate-300">
                        <div><span class="opacity-70">目标：</span> <span class="font-mono">{{ selectedVuln.target }}</span></div>
                        <div><span class="opacity-70">发现者：</span> @{{ selectedVuln.username }}</div>
                        <div><span class="opacity-70">时间：</span> {{ formatDate(selectedVuln.created_at) }}</div>
                    </div>

                    <div class="flex-1 overflow-y-auto p-6 markdown-body text-slate-200" v-html="renderMarkdown(selectedVuln.description)">
                    </div>
                </div>
            </div>
        </main>
    `,
    setup(props) {
        const vulns = ref([]);
        const loading = ref(true);
        const total = ref(0);
        const currentPage = ref(1);
        const pageSize = ref(20);
        const totalPages = ref(1);
        const filterSeverity = ref("");
        const selectedVuln = ref(null);

        const fetchVulns = async (page = 1) => {
            loading.value = true;
            currentPage.value = page;
            try {
                const params = { page, page_size: pageSize.value };
                if (filterSeverity.value) params.severity = filterSeverity.value;
                const res = await window.axios.get("/api/dashboard/vulnerabilities", {
                    params,
                    headers: { "Authorization": `Bearer ${props.token}` }
                });
                vulns.value = res.data.items || [];
                total.value = res.data.total || 0;
                totalPages.value = Math.max(1, Math.ceil(total.value / pageSize.value));
            } catch (error) {
                console.error("获取漏洞列表失败:", error);
                if(window.$toast) window.$toast("获取漏洞情报失败", "error");
                vulns.value = [];
                total.value = 0;
            } finally {
                loading.value = false;
            }
        };

        const formatDate = (dateStr) => Utils.formatDate(dateStr, true);

        const getSeverityLabel = (severity) => {
            const map = { critical: "致命", high: "高危", medium: "中危", low: "低危" };
            return map[severity.toLowerCase()] || severity;
        };

        const getSeverityClass = (severity) => Utils.getSeverityClass(severity);

        const viewReport = (vuln) => {
            selectedVuln.value = vuln;
        };

        const renderMarkdown = (text) => {
            if (!text) return "<p class=\"text-center opacity-50 my-10\">暂无详细报告内容</p>";
            return window.marked.parse(text);
        };

        watch(() => props.token, (newVal) => {
            if (newVal) fetchVulns();
        });

        onMounted(() => {
            if (props.token) fetchVulns();
        });

        return { 
            vulns, 
            loading, 
            total,
            currentPage,
            totalPages,
            filterSeverity,
            selectedVuln, 
            fetchVulns, 
            formatDate, 
            getSeverityLabel, 
            getSeverityClass, 
            viewReport, 
            renderMarkdown 
        };
    }
}
