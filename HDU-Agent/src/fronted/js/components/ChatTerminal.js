const { ref, onMounted, nextTick, watch } = window.Vue;

export default {
    name: 'ChatTerminal',
    props: ['token', 'sessionId', 'config', 'isConnected'],
    emits: ['update-connection', 'refresh-sessions'],
    template: `
        <div class="flex-1 flex flex-col h-full overflow-hidden">
            <main class="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 scroll-smooth" id="chat-container">
                <div v-if="messages.length === 0" class="text-center mt-20 text-slate-400">
                    <div class="inline-block p-6 rounded-2xl mb-4 backdrop-blur-md bg-slate-800/40 border border-slate-700/50">
                        <svg class="w-10 h-10 mx-auto opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg>
                    </div>
                    <p class="text-sm text-slate-300">系统已就绪。当前主模型：<span class="font-bold text-indigo-300">{{ config.provider }} ({{ config.model }})</span></p>
                    <p class="text-xs mt-2 text-slate-400">尝试输入: "调用 IronAgent 对 www.aouos.top 进行常规端口扫描"</p>
                </div>

                <transition-group name="chat-bubble" tag="div" class="space-y-6">
                    <div v-for="(msg, index) in messages" :key="'msg-'+index" class="flex flex-col" :class="msg.sender === 'user' ? 'items-end' : 'items-start'">
                        <div class="flex items-center gap-2 mb-1.5 px-2 text-xs font-medium text-slate-300" :class="msg.sender === 'user' ? 'flex-row-reverse' : ''">
                            <span>{{ msg.sender === 'user' ? '我' : (msg.sender === 'manager' ? '凌霄 主控' : (msg.sender === 'pentest_agent' || msg.isLiveLog ? 'IronAgent 沙箱' : '系统')) }}</span>
                        </div>
                        
                        <template v-if="msg.isLiveLog">
                            <div class="max-w-[95%] w-full bg-[#0d1117]/90 backdrop-blur-sm rounded-xl shadow-inner border border-slate-700 overflow-hidden flex flex-col">
                                <div class="flex items-center gap-2 px-4 py-2.5 border-b border-slate-700 bg-[#010409]/80 text-slate-400 z-10">
                                    <div class="flex gap-1.5">
                                        <span class="w-3 h-3 rounded-full bg-rose-500/90 border border-rose-600/50"></span>
                                        <span class="w-3 h-3 rounded-full bg-amber-500/90 border border-amber-600/50"></span>
                                        <span class="w-3 h-3 rounded-full bg-emerald-500/90 border border-emerald-600/50"></span>
                                    </div>
                                    <span class="ml-2 uppercase tracking-widest text-[10px] font-semibold">IronAgent Sandbox</span>
                                </div>
                                <div class="p-4 text-[#c9d1d9] font-mono text-[13px] leading-relaxed terminal-box whitespace-pre-wrap">
                                    <span v-html="formatLiveLog(msg.content)"></span>
                                    <span v-if="index === messages.length - 1" class="inline-block w-2 h-3 bg-[#58a6ff] cursor-blink ml-1 align-middle"></span>
                                </div>
                            </div>
                        </template>
                        <template v-else>
                           <div class="max-w-[85%] md:max-w-[80%] p-4 rounded-2xl relative transition-all backdrop-blur-sm" :class="{
                                'bg-indigo-600/90 text-white rounded-tr-sm shadow-md shadow-indigo-500/20': msg.sender === 'user',
                                'bg-slate-800/60 border border-slate-700/50 text-slate-200 rounded-tl-sm shadow-sm': (msg.sender === 'manager' || msg.sender === 'system'),
                                'bg-emerald-900/30 border border-emerald-800/50 text-emerald-200 rounded-tl-sm': msg.sender === 'pentest_agent',
                                'bg-rose-900/30 border border-rose-800/50 text-rose-200 rounded-tl-sm': msg.sender === 'error',
                            }">
                                <div class="markdown-body leading-relaxed break-words" :class="msg.sender === 'user' ? 'text-white/95' : ''" v-html="renderMarkdown(msg.content)"></div>
                            </div>
                        </template>
                    </div>
                </transition-group>
                
                <div class="scroll-anchor"></div>
            </main>

            <footer class="p-4 border-t transition-colors backdrop-blur-md bg-slate-900/60 border-slate-700/50">
                <div class="max-w-4xl mx-auto flex items-end gap-3 p-2 rounded-2xl focus-within:ring-4 transition-all shadow-sm border backdrop-blur-md bg-slate-800/40 border-slate-700/50 focus-within:border-indigo-500 focus-within:ring-indigo-500/20">
                    <textarea v-model="inputText" @keydown.enter.prevent="handleEnter"
                           placeholder="输入指令，要求 凌霄 调度渗透工具进行测试..." 
                           class="flex-1 bg-transparent px-3 py-2 focus:outline-none resize-none min-h-[44px] max-h-[120px] text-slate-200 placeholder-slate-500"
                           :disabled="!isConnected" rows="1"></textarea>
                    
                    <button @click="sendMessage" :disabled="!isConnected || !inputText.trim()"
                            class="p-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl transition-all disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0 shadow-md shadow-indigo-500/20">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
                    </button>
                </div>
            </footer>
        </div>
    `,
    setup(props, { emit }) {
        const messages = ref([]);
        const inputText = ref('');
        let ws = null;

        if (typeof window.marked !== 'undefined' && typeof window.hljs !== 'undefined') {
            window.marked.setOptions({
                highlight: function (code, lang) {
                    const language = window.hljs.getLanguage(lang) ? lang : 'plaintext';
                    return window.hljs.highlight(code, { language }).value;
                },
                langPrefix: 'hljs language-'
            });
        }
        
        let ansiUp = null;
        try {
            if (typeof window.AnsiUp !== 'undefined') {
                ansiUp = new window.AnsiUp();
            } else if (window.ansi_up && window.ansi_up.AnsiUp) {
                ansiUp = new window.ansi_up.AnsiUp();
            }
        } catch (error) {
            console.warn("AnsiUp 库加载失败，回退到普通文本显示");
        }

        const cleanContentStr = (str) => {
            if (!str) return '';
            return str.replace(/\\n/g, '\n').replace(/\[LIVE\] ?/g, '');
        };

        const formatLiveLog = (text) => {
            if (!text) return '';
            let formatted = text;
            if (ansiUp) {
                formatted = ansiUp.ansi_to_html(formatted);
            }
            formatted = formatted.replace(/✅/g, '<span class="text-emerald-400">✅</span>');
            formatted = formatted.replace(/💥|❌|严重错误/g, '<span class="text-rose-400">$&</span>');
            formatted = formatted.replace(/⚠️/g, '<span class="text-amber-400">⚠️</span>');
            formatted = formatted.replace(/🐳|🚀|🛡️|🤖/g, '<span class="text-[#58a6ff]">$&</span>');
            return formatted;
        };

        const renderMarkdown = (text) => {
            if (!text) return '';
            return typeof marked !== 'undefined' ? marked.parse(text) : text;
        };

        const scrollToBottom = () => {
            nextTick(() => {
                const container = document.getElementById('chat-container');
                if (container) container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
            });
        };

        const fetchChatHistory = async () => {
            if (!props.sessionId) return;
            try {
                const res = await axios.get('/api/chat/history?session_id=' + props.sessionId, {
                    headers: { 'Authorization': `Bearer ${props.token}` }
                });
                
                if (res.data && res.data.messages) {
                    const rawMessages = res.data.messages;
                    const mergedMessages = [];

                    rawMessages.forEach(msg => {
                        let contentStr = msg.content || '';
                        const isLive = contentStr.includes('[LIVE]') || msg.isLiveLog || msg.sender === 'pentest_agent';
                        
                        if (isLive) {
                            msg.isLiveLog = true;
                            contentStr = cleanContentStr(contentStr);
                            
                            const lastMsg = mergedMessages[mergedMessages.length - 1];
                            if (lastMsg && lastMsg.isLiveLog) {
                                lastMsg.content += '\n' + contentStr;
                            } else {
                                msg.content = contentStr;
                                mergedMessages.push(msg);
                            }
                        } else {
                            mergedMessages.push(msg);
                        }
                    });

                    messages.value = mergedMessages;
                    nextTick(() => scrollToBottom());
                }
            } catch (error) {
                console.warn('拉取历史记录失败:', error);
            }
        };

        const connectWs = () => {
            emit('update-connection', { status: false, text: '连接中...' });
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/chat?token=${props.token}`);

            ws.onopen = () => emit('update-connection', { status: true, text: '在线就绪' });

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'status') {
                    emit('update-connection', { status: true, text: data.content });
                } else {
                    let contentStr = data.content || '';
                    const isLive = contentStr.includes('[LIVE]') || data.isLiveLog;

                    if (isLive) {
                        contentStr = cleanContentStr(contentStr);
                        const lastMsg = messages.value[messages.value.length - 1];
                        
                        if (lastMsg && lastMsg.isLiveLog) {
                            lastMsg.content += '\n' + contentStr;
                        } else {
                            messages.value.push({ sender: 'pentest_agent', content: contentStr, isLiveLog: true });
                        }
                    } else {
                        messages.value.push({ sender: data.sender || 'system', content: contentStr, isLiveLog: false });
                        scrollToBottom();
                    }
                }
            };

            ws.onclose = (e) => {
                emit('update-connection', { status: false, text: e.code === 1008 ? '鉴权失败' : '断开连接' });
                if (e.code === 1008) {
                    if(window.$toast) window.$toast('登录已过期，正在重定向...', 'error');
                    setTimeout(() => window.location.href = 'login.html', 1500);
                } else {
                    setTimeout(connectWs, 3000);
                }
            };
        };

        const sendMessage = () => {
            if (!inputText.value.trim() || !props.isConnected) return;
            const text = inputText.value;
            const isFirstMessage = messages.value.length === 0;

            messages.value.push({ sender: 'user', content: text, isLiveLog: false });

            ws.send(JSON.stringify({
                session_id: props.sessionId,
                content: text,
                provider: props.config.provider,
                model: props.config.model,
                api_key: props.config.apiKey
            }));

            inputText.value = '';
            scrollToBottom();

            if (isFirstMessage) setTimeout(() => emit('refresh-sessions'), 1000);
        };

        const handleEnter = (e) => {
            if (!e.shiftKey) sendMessage();
        };

        watch(() => props.sessionId, (newId) => {
            messages.value = [];
            if (newId) fetchChatHistory();
        });

        watch(inputText, () => {
            nextTick(() => {
                const textarea = document.querySelector('textarea');
                if (textarea) {
                    textarea.style.height = 'auto';
                    textarea.style.height = textarea.scrollHeight + 'px';
                }
            });
        });

        onMounted(() => {
            connectWs();
            fetchChatHistory();
        });

        return {
            messages, inputText, sendMessage, handleEnter,
            formatLiveLog, renderMarkdown
        };
    }
}
