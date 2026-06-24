const { ref, onMounted } = window.Vue;

export default {
    name: "TaskScheduler",
    props: ["token"],
    template: `
        <main class="flex-1 overflow-y-auto p-4 md:p-6 transition-colors duration-300 bg-transparent">
            <div class="rounded-2xl shadow-sm border flex flex-col h-full transition-all backdrop-blur-md bg-slate-800/40 border-slate-700/50">
                <div class="p-5 border-b flex justify-between items-center border-slate-700/50">
                    <div>
                        <h2 class="text-lg font-bold text-slate-100">任务调度中心</h2>
                        <p class="text-xs mt-1 text-slate-400">管理渗透测试任务的创建、执行与监控</p>
                    </div>
                    <div class="flex gap-3 items-center">
                        <select v-model="filterStatus" @change="fetchTasks(1)" class="py-1.5 px-3 text-xs rounded-lg bg-slate-700/50 border border-slate-600 text-slate-200 focus:outline-none focus:border-indigo-500/50">
                            <option value="">全部状态</option>
                            <option value="pending">待执行</option>
                            <option value="running">运行中</option>
                            <option value="completed">已完成</option>
                            <option value="failed">失败</option>
                        </select>
                        <select v-model="filterAgent" @change="fetchTasks(1)" class="py-1.5 px-3 text-xs rounded-lg bg-slate-700/50 border border-slate-600 text-slate-200 focus:outline-none focus:border-indigo-500/50">
                            <option value="">全部Agent</option>
                            <option value="pentest_agent">IronAgent</option>
                            <option value="pentagi">GSAgent</option>
                            <option value="ctf_agent">YYYAgent</option>
                        </select>
                        <button @click="openCreateModal" class="px-4 py-2 text-xs font-medium bg-indigo-600 hover:bg-indigo-700 text-white shadow-md shadow-indigo-500/20 rounded-xl transition-all flex items-center gap-1.5">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
                            新建任务
                        </button>
                        <button @click="fetchTasks(currentPage)" class="p-2 rounded-lg transition-colors hover:bg-indigo-500/10 text-slate-300 hover:text-indigo-300">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                        </button>
                    </div>
                </div>

                <div class="flex-1 overflow-auto p-0">
                    <table class="w-full text-sm text-left">
                        <thead class="text-xs uppercase sticky top-0 z-10 border-b backdrop-blur-md bg-slate-800/80 text-slate-300 border-slate-700/50">
                            <tr>
                                <th class="px-6 py-4 font-medium">ID</th>
                                <th class="px-6 py-4 font-medium">执行Agent</th>
                                <th class="px-6 py-4 font-medium">目标</th>
                                <th class="px-6 py-4 font-medium">状态</th>
                                <th class="px-6 py-4 font-medium">Token消耗</th>
                                <th class="px-6 py-4 font-medium">创建时间</th>
                                <th class="px-6 py-4 font-medium text-right">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-if="loading" class="border-b border-slate-700/50">
                                <td colspan="7" class="px-6 py-8 text-center text-slate-400">加载数据中...</td>
                            </tr>
                            <tr v-else-if="tasks.length === 0" class="border-b border-slate-700/50">
                                <td colspan="7" class="px-6 py-8 text-center text-slate-400">暂无调度任务，点击"新建任务"开始</td>
                            </tr>
                            <tr v-else v-for="task in tasks" :key="task.id" class="border-b transition-colors hover:bg-slate-700/10 border-slate-700/50 text-slate-200">
                                <td class="px-6 py-4 font-mono text-xs text-indigo-300">#{{ task.id }}</td>
                                <td class="px-6 py-4">
                                    <span class="px-2.5 py-1 rounded-md text-xs font-semibold backdrop-blur-sm" :class="getAgentClass(task.agent_name)">{{ getAgentLabel(task.agent_name) }}</span>
                                </td>
                                <td class="px-6 py-4 font-mono text-xs text-slate-200 max-w-[200px] truncate" :title="task.target">{{ task.target }}</td>
                                <td class="px-6 py-4">
                                    <span class="px-2.5 py-1 rounded-full text-xs border backdrop-blur-sm" :class="getStatusClass(task.status)">
                                        {{ getStatusLabel(task.status) }}
                                    </span>
                                </td>
                                <td class="px-6 py-4 font-mono text-xs text-amber-300">{{ formatTokens(task.token_consumption) }}</td>
                                <td class="px-6 py-4 font-mono text-xs text-slate-400">{{ formatDate(task.created_at) }}</td>
                                <td class="px-6 py-4 text-right space-x-3">
                                    <button @click="viewTaskGraph(task)" v-if="task.attack_graph_data" class="text-xs font-medium hover:underline text-indigo-300">攻击图</button>
                                    <button @click="confirmDelete(task)" class="text-xs font-medium hover:underline text-rose-400">删除</button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <div v-if="total > 0" class="flex justify-center items-center gap-2 my-4 py-2">
                    <button @click="fetchTasks(currentPage - 1)" :disabled="currentPage <= 1" class="px-3 py-1.5 text-xs rounded-lg border transition-colors" :class="currentPage <= 1 ? 'border-slate-700 text-slate-600 cursor-not-allowed' : 'border-slate-600 text-slate-300 hover:bg-slate-700'">&laquo; 上一页</button>
                    <span class="text-xs text-slate-400">第 {{ currentPage }} / {{ totalPages }} 页 (共 {{ total }} 条)</span>
                    <button @click="fetchTasks(currentPage + 1)" :disabled="currentPage >= totalPages" class="px-3 py-1.5 text-xs rounded-lg border transition-colors" :class="currentPage >= totalPages ? 'border-slate-700 text-slate-600 cursor-not-allowed' : 'border-slate-600 text-slate-300 hover:bg-slate-700'">下一页 &raquo;</button>
                </div>
            </div>

            <!-- 新建任务弹窗 -->
            <div v-if="showCreateModal" class="fixed inset-0 z-[200] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
                <div class="rounded-2xl w-full max-w-lg shadow-2xl backdrop-blur-md bg-slate-900/90 border border-slate-700/50">
                    <div class="px-6 py-4 border-b flex justify-between items-center border-slate-700/50 bg-slate-800/50">
                        <h3 class="font-bold text-lg text-slate-100">新建渗透测试任务</h3>
                        <button @click="showCreateModal = false" class="p-1 rounded-lg transition-colors hover:bg-rose-500/10 text-slate-400 hover:text-rose-400">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                        </button>
                    </div>
                    <div class="p-6 space-y-5">
                        <div>
                            <label class="block text-sm font-medium text-gray-300 mb-1.5">执行Agent</label>
                            <select v-model="newTask.agent_name" class="w-full py-2.5 px-4 text-sm rounded-xl bg-slate-800 border border-slate-600 text-slate-200 focus:outline-none focus:border-indigo-500/50">
                                <option value="">-- 选择Agent --</option>
                                <option value="pentest_agent">IronAgent (沙箱扫描)</option>
                                <option value="pentagi">GSAgent 核心 (Web漏洞挖掘)</option>
                                <option value="ctf_agent">YYYAgent (靶场解题)</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-300 mb-1.5">攻击目标</label>
                            <input v-model="newTask.target" type="text" placeholder="example.com / 192.168.1.1 / https://target" class="w-full py-2.5 px-4 text-sm rounded-xl bg-slate-800 border border-slate-600 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500/50">
                        </div>
                        <div v-if="createError" class="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-sm text-center">{{ createError }}</div>
                    </div>
                    <div class="p-4 border-t flex justify-end gap-3 bg-slate-900 border-slate-700">
                        <button @click="showCreateModal = false" class="px-5 py-2.5 text-sm font-medium rounded-xl transition-all text-slate-300 hover:bg-slate-800">取消</button>
                        <button @click="handleCreateTask" :disabled="creating" class="px-6 py-2.5 text-sm font-medium bg-indigo-600 hover:bg-indigo-700 text-white shadow-md shadow-indigo-500/20 rounded-xl transition-all flex items-center gap-2">
                            <svg v-if="creating" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                            {{ creating ? "创建中..." : "创建任务" }}
                        </button>
                    </div>
                </div>
            </div>

            <!-- 攻击链路图弹窗 -->
            <div v-if="graphTask" class="fixed inset-0 z-[200] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
                <div class="rounded-2xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl backdrop-blur-md bg-slate-900/90 border border-slate-700/50">
                    <div class="px-6 py-4 border-b flex justify-between items-center border-slate-700/50 bg-slate-800/50">
                        <div class="flex items-center gap-3">
                            <span class="font-bold text-lg text-slate-100">攻击链路图</span>
                            <span class="text-sm text-slate-400">#{{ graphTask.id }} - {{ graphTask.target }}</span>
                        </div>
                        <button @click="graphTask = null" class="p-1 rounded-lg transition-colors hover:bg-rose-500/10 text-slate-400 hover:text-rose-400">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                        </button>
                    </div>
                    <div class="flex-1 min-h-[400px] p-4" id="graph-modal-chart"></div>
                </div>
            </div>

            <!-- 删除确认弹窗 -->
            <div v-if="deleteTarget" class="fixed inset-0 z-[200] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
                <div class="rounded-2xl w-full max-w-sm shadow-2xl backdrop-blur-md bg-slate-900/90 border border-slate-700/50 p-6 text-center">
                    <div class="w-12 h-12 mx-auto mb-4 rounded-full bg-rose-500/20 flex items-center justify-center">
                        <svg class="w-6 h-6 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                    </div>
                    <p class="text-slate-100 font-medium mb-1">确认删除任务 #{{ deleteTarget.id }}？</p>
                    <p class="text-sm text-slate-400 mb-6">目标: {{ deleteTarget.target }}<br>该操作将同时删除关联的漏洞数据，不可恢复</p>
                    <div class="flex justify-center gap-3">
                        <button @click="deleteTarget = null" class="px-5 py-2 text-sm font-medium rounded-xl text-slate-300 hover:bg-slate-800 transition-all">取消</button>
                        <button @click="handleDelete" class="px-5 py-2 text-sm font-medium bg-rose-600 hover:bg-rose-700 text-white rounded-xl transition-all">确认删除</button>
                    </div>
                </div>
            </div>
        </main>
    `,
    setup(props) {
        const tasks = ref([]);
        const loading = ref(true);
        const total = ref(0);
        const currentPage = ref(1);
        const pageSize = ref(20);
        const totalPages = ref(1);
        const filterStatus = ref("");
        const filterAgent = ref("");

        const showCreateModal = ref(false);
        const creating = ref(false);
        const createError = ref("");
        const newTask = ref({ agent_name: "", target: "" });

        const graphTask = ref(null);
        const deleteTarget = ref(null);

        let graphChartInstance = null;

        const fetchTasks = async (page = 1) => {
            loading.value = true;
            currentPage.value = page;
            try {
                const params = { page, page_size: pageSize.value };
                if (filterStatus.value) params.status = filterStatus.value;
                if (filterAgent.value) params.agent_name = filterAgent.value;
                const res = await window.axios.get("/api/tasks/", {
                    params,
                    headers: { "Authorization": `Bearer ${props.token}` }
                });
                tasks.value = res.data.items || [];
                total.value = res.data.total || 0;
                totalPages.value = Math.max(1, Math.ceil(total.value / pageSize.value));
            } catch (error) {
                console.error("获取任务列表失败:", error);
                if (window.$toast) window.$toast("获取任务列表失败", "error");
                tasks.value = [];
                total.value = 0;
            } finally {
                loading.value = false;
            }
        };

        const openCreateModal = () => {
            newTask.value = { agent_name: "", target: "" };
            createError.value = "";
            showCreateModal.value = true;
        };

        const handleCreateTask = async () => {
            if (!newTask.value.agent_name || !newTask.value.target.trim()) {
                createError.value = "请填写Agent和目标";
                return;
            }
            creating.value = true;
            createError.value = "";
            try {
                await window.axios.post("/api/tasks/", newTask.value, {
                    headers: { "Authorization": `Bearer ${props.token}` }
                });
                showCreateModal.value = false;
                if (window.$toast) window.$toast("任务创建成功！", "success");
                fetchTasks(1);
            } catch (error) {
                console.error("创建任务失败:", error);
                createError.value = error.response?.data?.detail || "创建失败，请检查网络";
            } finally {
                creating.value = false;
            }
        };

        const viewTaskGraph = (task) => {
            graphTask.value = task;
            setTimeout(renderGraph, 100);
        };

        const renderGraph = () => {
            const dom = document.getElementById("graph-modal-chart");
            if (!dom || !graphTask.value?.attack_graph_data) return;
            if (graphChartInstance) graphChartInstance.dispose();
            graphChartInstance = echarts.init(dom, "dark");
            graphChartInstance.setOption({
                backgroundColor: "transparent",
                tooltip: {},
                series: [{
                    type: "graph",
                    layout: "force",
                    force: { repulsion: 200, edgeLength: 80 },
                    roam: true,
                    label: { show: true, position: "bottom", fontSize: 10, color: "#e2e8f0" },
                    data: (graphTask.value.attack_graph_data.nodes || []).map(n => ({ ...n, symbolSize: 40 })),
                    links: (graphTask.value.attack_graph_data.edges || []).map(e => ({
                        ...e,
                        lineStyle: { width: 2, color: "#475569" }
                    }))
                }]
            });
        };

        const confirmDelete = (task) => { deleteTarget.value = task; };
        const handleDelete = async () => {
            if (!deleteTarget.value) return;
            try {
                await window.axios.delete(`/api/tasks/${deleteTarget.value.id}`, {
                    headers: { "Authorization": `Bearer ${props.token}` }
                });
                if (window.$toast) window.$toast(`任务 #${deleteTarget.value.id} 已删除`, "success");
                deleteTarget.value = null;
                fetchTasks(currentPage.value);
            } catch (error) {
                console.error("删除任务失败:", error);
                if (window.$toast) window.$toast("删除失败", "error");
            }
        };

        const getAgentLabel = (name) => Utils.getAgentLabel(name);

        const getAgentClass = (name) => Utils.getAgentClass(name);

        const getStatusLabel = (status) => {
            const map = { pending: "待执行", running: "运行中", completed: "已完成", failed: "失败" };
            return map[status] || status;
        };

        const getStatusClass = (status) => Utils.getStatusClass(status);

        const formatTokens = (count) => Utils.formatTokens(count);

        const formatDate = (dateStr) => Utils.formatDate(dateStr);

        onMounted(() => { if (props.token) fetchTasks(); });

        return {
            tasks, loading, total, currentPage, totalPages,
            filterStatus, filterAgent,
            showCreateModal, creating, createError, newTask,
            graphTask, deleteTarget,
            fetchTasks, openCreateModal, handleCreateTask,
            viewTaskGraph, confirmDelete, handleDelete,
            getAgentLabel, getAgentClass, getStatusLabel, getStatusClass,
            formatTokens, formatDate
        };
    }
};
