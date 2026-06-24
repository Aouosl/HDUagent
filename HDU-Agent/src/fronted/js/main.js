import Dashboard from './components/Dashboard.js';
import ChatTerminal from './components/ChatTerminal.js';
import VulnList from './components/VulnList.js';
import TaskScheduler from './components/TaskScheduler.js';
import SkeletonLoader from './components/SkeletonLoader.js';

const { createApp, ref, onMounted, onBeforeUnmount } = window.Vue;

const app = createApp({
    setup() {
        const username = ref(Security.plainGet('username') || 'Operator');
        const token = ref(Security.plainGet('token'));
        
        if (!token.value) {
            Security.clearAll();
            window.location.href = 'login.html';
        }

        // 固定暗色主题
        document.documentElement.classList.add('dark');
        document.body.style.backgroundColor = '#0b0f19';

        const mobileMenuOpen = ref(false);
        const showApiKey = ref(false);

        const toasts = ref([]);
        let toastId = 0;
        
        const showToast = (message, type = 'info') => {
            const id = toastId++;
            toasts.value.push({ id, message, type });
            setTimeout(() => {
                toasts.value = toasts.value.filter(t => t.id !== id);
            }, 3000);
        };
        window.$toast = showToast;

        const generateId = () => Utils.generateId('chat');
        const currentSessionId = ref(Security.plainGet('session_id') || generateId());
        const sessionsList = ref([]);
        const currentTab = ref('dashboard');
        
        // Hash-based routing
        const syncTabFromHash = () => {
            const hash = window.location.hash.replace('#', '');
            if (['dashboard', 'chat', 'vulns', 'schedule'].includes(hash)) {
                currentTab.value = hash;
            }
        };
        syncTabFromHash();
        window.addEventListener('hashchange', syncTabFromHash);
        
        const isConnected = ref(false);
        const statusText = ref('离线');

        const showConfigModal = ref(false);
        const activeConfigTab = ref('global'); 
        
        const agentTabs = [
            { id: 'global', name: '主控节点 (Global)', desc: '负责任务拆解与全局调度' },
            { id: 'pentest_agent', name: 'IronAgent (沙箱)', desc: '执行底层系统命令与扫描' },
            { id: 'pentagi', name: 'GSAgent 核心', desc: '高级 Web 漏洞自动化挖掘' },
            { id: 'ctf_agent', name: 'YYYAgent', desc: '靶场与特定题型解题引擎' }
        ];

        const agentConfigs = ref({
            global: { 
                provider: Security.plainGet('provider_' + username.value) || 'deepseek', 
                model: Security.plainGet('model_' + username.value) || 'deepseek-chat', 
                apiKey: ''
            },
            pentest_agent: { provider: 'openai', model: 'gpt-4o', apiKey: '' },
            pentagi: { provider: 'openai', model: 'gpt-4-turbo', apiKey: '' },
            ctf_agent: { provider: 'openai', model: 'gpt-4o', apiKey: '' }
        });

        // Config modal state
        const configSaving = ref(false);
        const configSaved = ref(false);
        const configError = ref('');

        const switchConfigTab = async (tabId) => {
            activeConfigTab.value = tabId;
            showApiKey.value = false;
            configSaved.value = false;
            configError.value = '';
            if (tabId === 'global') {
                var key = await Security.secureGet('api_key_' + username.value);
                if (key) agentConfigs.value.global.apiKey = key;
            } else {
                try {
                    var res = await window.axios.get('/api/agents/config/' + tabId, {
                        headers: { 'Authorization': 'Bearer ' + token.value }
                    });
                    if (res.data) {
                        agentConfigs.value[tabId].model = res.data.model || agentConfigs.value[tabId].model;
                        agentConfigs.value[tabId].apiKey = res.data.api_key || '';
                        agentConfigs.value[tabId].provider = res.data.provider || agentConfigs.value[tabId].provider;
                    }
                } catch (error) {
                    // Server config not available, use defaults silently
                }
            }
        };

        const openConfigModal = () => {
            showConfigModal.value = true;
            configSaved.value = false;
            configError.value = '';
            switchConfigTab('global');
        };

        const saveCurrentConfig = async () => {
            var tabId = activeConfigTab.value;
            var config = agentConfigs.value[tabId];
            configSaving.value = true;
            configSaved.value = false;
            configError.value = '';

            try {
                if (tabId === 'global') {
                    Security.plainSet('provider_' + username.value, config.provider);
                    Security.plainSet('model_' + username.value, config.model);
                    await Security.secureSet('api_key_' + username.value, config.apiKey);
                } else {
                    await window.axios.post('/api/agents/config', {
                        agent_name: tabId,
                        model: config.model,
                        api_key: config.apiKey,
                        provider: config.provider
                    }, { headers: { 'Authorization': 'Bearer ' + token.value } });
                }
                configSaved.value = true;
                setTimeout(function() { configSaved.value = false; }, 3000);
            } catch (error) {
                var msg = error.response?.data?.detail || error.message || 'Network error';
                configError.value = '保存失败: ' + msg;
                console.error('配置保存失败:', error);
            } finally {
                configSaving.value = false;
            }
        };

        const closeConfigModal = () => { showConfigModal.value = false; };

        const handleConnectionUpdate = (payload) => { 
            isConnected.value = payload.status; 
            statusText.value = payload.text; 
        };

        const fetchSessions = async () => {
            try {
                const res = await window.axios.get('/api/chat/sessions', {
                    headers: { 'Authorization': `Bearer ${token.value}` }
                });
                sessionsList.value = res.data.sessions || [];
            } catch (error) {
                console.warn('拉取会话列表失败:', error);
            }
        };

                const formatSessionTime = (ts) => {
            if (!ts) return '';
            var d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
            var now = new Date();
            var diff = now - d;
            if (diff < 60000) return '刚刚';
            if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前';
            if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前';
            return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
        };

        const createNewChat = () => {
            currentSessionId.value = generateId();
            Security.plainSet('session_id', currentSessionId.value);
            currentTab.value = 'chat';
            sessionsList.value.unshift({
                session_id: currentSessionId.value,
                title: '新对话',
                updated_at: Date.now() / 1000
            });
        };

        const switchSession = (id) => {
            currentSessionId.value = id;
            Security.plainSet('session_id', id);
            currentTab.value = 'chat';
        };

        const switchTab = (tab) => { window.location.hash = tab; };

        // Keyboard shortcuts
        const handleKeydown = (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch (e.key) {
                    case '1': e.preventDefault(); switchTab('dashboard'); break;
                    case '2': e.preventDefault(); switchTab('chat'); break;
                    case '3': e.preventDefault(); switchTab('vulns'); break;
                    case '4': e.preventDefault(); switchTab('schedule'); break;
                }
            }
        };
        window.addEventListener('keydown', handleKeydown);

        const handleLogout = () => {
            Security.clearAll();
            window.location.href = 'login.html';
        };

        onMounted(() => {
            fetchSessions();
            syncTabFromHash();
        });
        onBeforeUnmount(() => {
            window.removeEventListener('hashchange', syncTabFromHash);
            window.removeEventListener('keydown', handleKeydown);
        });

        return {
            token, username, currentTab, currentSessionId, sessionsList,
            isConnected, statusText, handleConnectionUpdate,
            switchTab, switchSession, createNewChat, fetchSessions, handleLogout, formatSessionTime,
            
            showConfigModal, activeConfigTab, agentTabs, agentConfigs,
            openConfigModal, switchConfigTab, saveCurrentConfig, closeConfigModal,

            mobileMenuOpen, showApiKey, toasts,
            configSaving, configSaved, configError
        };
    }
});

app.component('dashboard', Dashboard);
app.component('chat-terminal', ChatTerminal);
app.component('vuln-list', VulnList);
app.component('task-scheduler', TaskScheduler);
app.component('skeleton-loader', SkeletonLoader);

app.mount('#app');
