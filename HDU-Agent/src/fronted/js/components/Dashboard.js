const { ref, onMounted, onBeforeUnmount } = window.Vue;

export default {
    name: 'Dashboard',
    props: ['token'],
    template: `
        <main class="flex-1 overflow-y-auto p-4 md:p-6 transition-colors duration-300 bg-transparent" id="dashboard-container">
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <div class="p-5 rounded-2xl shadow-sm border flex flex-col justify-center transition-all backdrop-blur-md bg-slate-800/40 border-slate-700/50">
                    <span class="text-sm font-medium text-slate-300">安全态势评分</span>
                    <span class="text-3xl font-bold text-emerald-400 mt-2">{{ dashboardStats.summary?.security_score || '-' }}<span class="text-lg font-normal ml-1 text-slate-400">/100</span></span>
                </div>
                <div class="p-5 rounded-2xl shadow-sm border flex flex-col justify-center transition-all backdrop-blur-md bg-slate-800/40 border-slate-700/50">
                    <span class="text-sm font-medium text-slate-300">今日发现漏洞</span>
                    <span class="text-3xl font-bold text-rose-400 mt-2">{{ dashboardStats.summary?.vulns_today || '-' }}</span>
                </div>
                <div class="p-5 rounded-2xl shadow-sm border flex flex-col justify-center transition-all backdrop-blur-md bg-slate-800/40 border-slate-700/50">
                    <span class="text-sm font-medium text-slate-300">活跃 Agent 节点</span>
                    <span class="text-3xl font-bold text-indigo-400 mt-2">{{ dashboardStats.summary?.active_agents || '-' }}</span>
                </div>
                <div class="p-5 rounded-2xl shadow-sm border flex flex-col justify-center transition-all backdrop-blur-md bg-slate-800/40 border-slate-700/50">
                    <span class="text-sm font-medium text-slate-300">大模型 Token 消耗</span>
                    <span class="text-3xl font-bold text-amber-400 mt-2">{{ dashboardStats.summary?.token_usage || '-' }}</span>
                </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div class="col-span-1 p-5 rounded-2xl shadow-sm border h-[400px] transition-all flex flex-col backdrop-blur-md bg-slate-800/40 border-slate-700/50">
                    <h3 class="font-bold mb-4 text-slate-100">漏洞等级分布</h3>
                    <div id="pieChart" class="w-full flex-1"></div>
                </div>
                <div class="lg:col-span-2 p-5 rounded-2xl shadow-sm border h-[400px] transition-all flex flex-col backdrop-blur-md bg-slate-800/40 border-slate-700/50">
                    <h3 class="font-bold mb-4 text-slate-100">最新自动化攻击链路追踪</h3>
                    <div id="graphChart" class="w-full flex-1"></div>
                </div>
            </div>
        </main>
    `,
    setup(props) {
        const dashboardStats = ref({});
        let pieChartInstance = null;
        let graphChartInstance = null;
        let resizeObserver = null;

        const initCharts = async () => {
            try {
                const res = await window.axios.get('/api/dashboard/stats', {
                    headers: { 'Authorization': `Bearer ${props.token}` }
                });
                dashboardStats.value = res.data;

                const pieDom = document.getElementById('pieChart');
                if (!pieDom) return;
                if (!pieChartInstance) pieChartInstance = echarts.init(pieDom, 'dark');
                pieChartInstance.setOption({
                    backgroundColor: 'transparent',
                    tooltip: { trigger: 'item' },
                    color: ['#f43f5e', '#f97316', '#eab308', '#3b82f6'],
                    series: [{
                        type: 'pie',
                        radius: ['40%', '70%'],
                        itemStyle: { 
                            borderRadius: 10, 
                            borderColor: '#1e293b', 
                            borderWidth: 2 
                        },
                        label: { color: '#e2e8f0', fontSize: 12 },
                        data: res.data.vuln_distribution || []
                    }]
                });

                const graphDom = document.getElementById('graphChart');
                if (!graphDom) return;
                if (!graphChartInstance) graphChartInstance = echarts.init(graphDom, 'dark');
                graphChartInstance.setOption({
                    backgroundColor: 'transparent',
                    tooltip: {},
                    color: ['#94a3b8', '#3b82f6', '#eab308', '#ef4444'],
                    series: [{
                        type: 'graph',
                        layout: 'force',
                        force: { repulsion: 200, edgeLength: 80 },
                        roam: true,
                        label: { 
                            show: true, 
                            position: 'bottom', 
                            fontSize: 10, 
                            color: '#e2e8f0' 
                        },
                        data: res.data.attack_graph?.nodes?.map(n => ({...n, symbolSize: 40})) || [],
                        links: res.data.attack_graph?.edges?.map(e => ({
                            ...e, 
                            lineStyle: { width: 2, color: '#475569' }
                        })) || []
                    }]
                });
            } catch (error) {
                console.error('获取大盘数据失败:', error);
                if(window.$toast) window.$toast('拉取大盘数据失败', 'error');
            }
        };

        onMounted(() => {
            initCharts();
            const container = document.getElementById('dashboard-container');
            if (container) {
                resizeObserver = new ResizeObserver(() => {
                    if (pieChartInstance) pieChartInstance.resize();
                    if (graphChartInstance) graphChartInstance.resize();
                });
                resizeObserver.observe(container);
            }
        });

        onBeforeUnmount(() => {
            if (resizeObserver) resizeObserver.disconnect();
            if (pieChartInstance) pieChartInstance.dispose();
            if (graphChartInstance) graphChartInstance.dispose();
        });

        return { dashboardStats };
    }
}
