/**
 * 鍑岄渼 楠ㄦ灦灞忓姞杞藉崰浣嶇粍浠?
 * 
 * 鐢ㄦ硶: <skeleton-loader type="table" :rows="5"></skeleton-loader>
 * type: 'table' | 'card' | 'text' | 'chart'
 */
const SkeletonLoader = {
    name: 'SkeletonLoader',
    props: {
        type: { type: String, default: 'text' },
        rows: { type: Number, default: 3 },
        cols: { type: Number, default: 4 }
    },
    template: `
    <div class="animate-pulse">
        <!-- Table skeleton -->
        <div v-if="type === 'table'" class="space-y-3 p-4">
            <div class="flex gap-4 mb-4">
                <div v-for="i in cols" :key="i" class="h-6 rounded-lg flex-1" 
                     :class="i === cols ? 'bg-slate-700/60 w-24' : 'bg-slate-700/40'"></div>
            </div>
            <div v-for="r in rows" :key="r" class="flex gap-4">
                <div v-for="c in cols" :key="c" class="h-5 rounded bg-slate-700/40" 
                     :style="{ flex: c === 1 ? 0.5 : 1 }"></div>
            </div>
        </div>

        <!-- Card grid skeleton -->
        <div v-else-if="type === 'card'" class="grid grid-cols-2 lg:grid-cols-4 gap-4 p-4">
            <div v-for="i in rows" :key="i" class="p-5 rounded-2xl bg-slate-800/40 border border-slate-700/50 space-y-3">
                <div class="h-4 rounded bg-slate-700/60 w-2/3"></div>
                <div class="h-8 rounded bg-slate-700/40 w-1/2"></div>
            </div>
        </div>

        <!-- Chart skeleton -->
        <div v-else-if="type === 'chart'" class="p-5 rounded-2xl bg-slate-800/40 border border-slate-700/50 h-[400px] flex items-center justify-center">
            <div class="text-slate-500 text-sm">鏁版嵁鍔犺浇涓?..</div>
        </div>

        <!-- Text skeleton -->
        <div v-else class="space-y-3 p-4">
            <div v-for="i in rows" :key="i" class="h-4 rounded bg-slate-700/40" 
                 :style="{ width: (90 - i * 10) + '%' }"></div>
        </div>
    </div>
    `
};

export default SkeletonLoader;
