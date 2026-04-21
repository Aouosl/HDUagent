import Dashboard from './components/Dashboard.js';
import ChatTerminal from './components/ChatTerminal.js';
import VulnList from './components/VulnList.js';

const { createApp, ref, onMounted } = window.Vue;

const app = createApp({
    setup() {
        const username = ref(localStorage.getItem('hdu_username') || 'Operator');
        const token = ref(localStorage.getItem('hdu_token'));
        
        if (!token.value) {
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

        const generateId = () => `chat_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
        const currentSessionId = ref(localStorage.getItem('hdu_session_id') || generateId());
        const sessionsList = ref([]);
        const currentTab = ref('dashboard');
        
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
                provider: localStorage.getItem(`hdu_provider_${username.value}`) || 'deepseek', 
                model: localStorage.getItem(`hdu_model_${username.value}`) || 'deepseek-chat', 
                apiKey: localStorage.getItem(`hdu_api_key_${username.value}`) || '' 
            },
            pentest_agent: { provider: 'openai', model: 'gpt-4o', apiKey: '' },
            pentagi: { provider: 'openai', model: 'gpt-4-turbo', apiKey: '' },
            ctf_agent: { provider: 'openai', model: 'gpt-4o', apiKey: '' }
        });

        const switchConfigTab = async (tabId) => {
            activeConfigTab.value = tabId;
            showApiKey.value = false;
            if (tabId !== 'global') {
                try {
                    const res = await window.axios.get(`/api/agents/config/${tabId}`, {
                        headers: { 'Authorization': `Bearer ${token.value}` }
                    });
                    if (res.data) {
                        agentConfigs.value[tabId].model = res.data.model || agentConfigs.value[tabId].model;
                        agentConfigs.value[tabId].apiKey = res.data.api_key || agentConfigs.value[tabId].apiKey;
                    }
                } catch (error) {
                    console.warn(`未拉取到 ${tabId} 的历史配置，使用默认值`);
                }
            }
        };

        const openConfigModal = () => {
            showConfigModal.value = true;
            switchConfigTab('global'); 
        };

        const saveCurrentConfig = async () => {
            const tabId = activeConfigTab.value;
            const config = agentConfigs.value[tabId];

            if (tabId === 'global') {
                localStorage.setItem(`hdu_provider_${username.value}`, config.provider);
                localStorage.setItem(`hdu_model_${username.value}`, config.model);
                localStorage.setItem(`hdu_api_key_${username.value}`, config.apiKey);
                showToast('主控节点配置已保存至本地缓存！', 'success');
            } else {
                try {
                    await window.axios.post('/api/agents/config', {
                        agent_name: tabId,
                        model: config.model,
                        api_key: config.apiKey
                    }, { headers: { 'Authorization': `Bearer ${token.value}` } });
                    showToast(`[${agentTabs.find(t=>t.id===tabId).name}] 配置已同步至服务端！`, 'success');
                } catch (error) {
                    showToast(`保存 ${tabId} 配置失败，请检查网络`, 'error');
                }
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

        const createNewChat = () => {
            currentSessionId.value = generateId();
            localStorage.setItem('hdu_session_id', currentSessionId.value);
            currentTab.value = 'chat';
            sessionsList.value.unshift({
                session_id: currentSessionId.value,
                title: '新对话',
                updated_at: Date.now() / 1000
            });
        };

        const switchSession = (id) => {
            currentSessionId.value = id;
            localStorage.setItem('hdu_session_id', id);
            currentTab.value = 'chat';
        };

        const switchTab = (tab) => { currentTab.value = tab; };

        const handleLogout = () => {
            localStorage.clear();
            window.location.href = 'login.html';
        };

        onMounted(() => { fetchSessions(); });

        return {
            token, username, currentTab, currentSessionId, sessionsList,
            isConnected, statusText, handleConnectionUpdate,
            switchTab, switchSession, createNewChat, fetchSessions, handleLogout,
            
            showConfigModal, activeConfigTab, agentTabs, agentConfigs,
            openConfigModal, switchConfigTab, saveCurrentConfig, closeConfigModal,

            mobileMenuOpen, showApiKey, toasts
        };
    }
});

app.component('dashboard', Dashboard);
app.component('chat-terminal', ChatTerminal);
app.component('vuln-list', VulnList);

app.mount('#app');
