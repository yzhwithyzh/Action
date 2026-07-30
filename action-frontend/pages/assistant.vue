<script setup lang="ts">
/**
 * assistant.html 迁移而来。
 * 模板与样式保持原状；样式已加 .page-assistant 命名空间，避免 SPA 路由切换时跨页污染。
 */
const { t } = useI18n()

interface StudyTypeStat { textZh: string | null; textEn: string | null }
interface StudyTypeRow {
  typeId: number
  typeKey: string
  nameZh: string | null
  nameEn: string | null
  hotGuideline: string | null
  guidelines: string[]
  stats: StudyTypeStat[]
}

useHead({
  title: t('assistant._title'),
  meta: [{ name: 'description', content: t('assistant._desc') }],
})

const { pick } = useBilingual()

const { data: stRes } = await useSiteObject<StudyTypeRow[]>('/study-types', 'assistant-types')
const types = computed<StudyTypeRow[]>(() => stRes.value?.data ?? [])

/** 三个问题的当前答案，默认值与原页面一致（type=trial / rand=y / sham=y） */
const ans = ref<{ type: string; rand: string; sham: string }>({ type: 'trial', rand: 'y', sham: 'y' })

/** 是否显示「随机化 / 假针」两个子问题 —— 仅试验类才问 */
const showSubQ = computed(() => ans.value.type === 'trial')

/** 把答案解析成 action_study_type.type_key */
const resolvedKey = computed(() => {
  const a = ans.value
  if (a.type === 'case' || a.type === 'sr' || a.type === 'obs') return a.type

  return a.rand === 'y' ? 'rct' : 'nrct'
})

const matched = computed<StudyTypeRow | null>(
  () => types.value.find((x) => x.typeKey === resolvedKey.value) ?? null,
)

useReveal()
</script>

<template>
  <div class="page-assistant">
    <section class="wz" id="wizard">
      <div class="wrap">
        <span class="kicker reveal">{{ t('assistant.s001') }}</span>

        <!-- 步骤条 -->
        <div class="stepper" id="stepper" role="tablist" aria-label="五步向导">
          <button class="step on" data-step="1" role="tab"><span class="sn">1</span><span class="stx"><b>{{ t('assistant.s002') }}</b><span>{{ t('assistant.s003') }}</span></span></button>
          <button class="step" data-step="2" role="tab"><span class="sn">2</span><span class="stx"><b>{{ t('assistant.s004') }}</b><span>{{ t('assistant.s005') }}</span></span></button>
          <button class="step" data-step="3" role="tab"><span class="sn">3</span><span class="stx"><b>{{ t('assistant.s006') }}</b><span>{{ t('assistant.s007') }}</span></span></button>
          <button class="step" data-step="4" role="tab"><span class="sn">4</span><span class="stx"><b>{{ t('assistant.s008') }}</b><span>{{ t('assistant.s009') }}</span></span></button>
          <button class="step" data-step="5" role="tab"><span class="sn">5</span><span class="stx"><b>{{ t('assistant.s010') }}</b><span>{{ t('assistant.s011') }}</span></span></button>
        </div>

        <!-- 面板 1：研究类型智能匹配 -->
        <div class="panel" data-panel="1">
          <div class="p-head">
            <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /><path d="M8 11h6M11 8v6" /></svg></span>
            <div><span class="p-num">{{ t('assistant.s012') }}</span><h2>{{ t('assistant.s013') }}</h2></div>
          </div>
          <p class="p-desc" v-html="t('assistant.s014')"></p>
          <div class="two">
            <div>
              <div class="subh">{{ t('assistant.s015') }}</div>
              <div class="q-group">
                <label>{{ t('assistant.s016') }}</label>
                <div class="opts" data-q="type">
                  <button class="opt" :class="{ on: ans.type === 'trial' }" data-v="trial" @click="ans.type = 'trial'">{{ t('assistant.s017') }}</button>
                  <button class="opt" :class="{ on: ans.type === 'case' }" data-v="case" @click="ans.type = 'case'">{{ t('assistant.s018') }}</button>
                  <button class="opt" :class="{ on: ans.type === 'sr' }" data-v="sr" @click="ans.type = 'sr'">{{ t('assistant.s019') }}</button>
                  <button class="opt" :class="{ on: ans.type === 'obs' }" data-v="obs" @click="ans.type = 'obs'">{{ t('assistant.s020') }}</button>
                </div>
              </div>
              <div class="q-group sub-q" :class="{ 'is-hidden': !showSubQ }" data-subq="trial">
                <label>{{ t('assistant.s021') }}</label>
                <div class="opts" data-q="rand">
                  <button class="opt" :class="{ on: ans.rand === 'y' }" data-v="y" @click="ans.rand = 'y'">{{ t('assistant.s022') }}</button>
                  <button class="opt" :class="{ on: ans.rand === 'n' }" data-v="n" @click="ans.rand = 'n'">{{ t('assistant.s023') }}</button>
                </div>
              </div>
              <div class="q-group sub-q" :class="{ 'is-hidden': !showSubQ }" data-subq="trial">
                <label>{{ t('assistant.s024') }}</label>
                <div class="opts" data-q="sham">
                  <button class="opt" :class="{ on: ans.sham === 'y' }" data-v="y" @click="ans.sham = 'y'">{{ t('assistant.s025') }}</button>
                  <button class="opt" :class="{ on: ans.sham === 'n' }" data-v="n" @click="ans.sham = 'n'">{{ t('assistant.s026') }}</button>
                </div>
              </div>
            </div>
            <div>
              <div class="subh">{{ t('assistant.s027') }}</div>
              <div class="match" id="matchBox">
                <template v-if="matched">
                  <span class="ml">{{ t('assistant.mlLabel') }}</span>
                  <div class="mt">{{ pick(matched, 'name') }}</div>
                  <div class="mrow">
                    <span>{{ t('assistant.mountGuidelines') }}</span>
                    <div class="gchips">
                      <b v-for="g in matched.guidelines" :key="g" :class="{ hot: g === matched.hotGuideline }">{{ g }}</b>
                    </div>
                  </div>
                  <div class="mrow" style="margin-bottom:0">
                    <span>{{ t('assistant.recStats') }}</span>
                    <ul class="statlist">
                      <li v-for="(st, k) in matched.stats" :key="k">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M20 6 9 17l-5-5" /></svg>
                        <span>{{ pick(st, 'text') }}</span>
                      </li>
                    </ul>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>

        <!-- 面板 2：在线报告模板 -->
        <div class="panel is-hidden" data-panel="2">
          <div class="p-head">
            <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 8h8M8 12h8M8 16h5" /></svg></span>
            <div><span class="p-num">{{ t('assistant.s028') }}</span><h2>{{ t('assistant.s029') }}</h2></div>
          </div>
          <p class="p-desc" v-html="t('assistant.s030')"></p>
          <div class="two">
            <div>
              <div class="subh">{{ t('assistant.s031') }}</div>
              <div class="tmpl">
                <div class="tmpl-row"><span class="tnum">1</span><span class="tnm">{{ t('assistant.s032') }}</span><span class="req must">{{ t('assistant.s033') }}</span></div>
                <div class="tmpl-row"><span class="tnum">2</span><span class="tnm">{{ t('assistant.s034') }}</span><span class="req must">{{ t('assistant.s035') }}</span></div>
                <div class="tmpl-row"><span class="tnum">3</span><span class="tnm">{{ t('assistant.s036') }}</span><span class="req must">{{ t('assistant.s037') }}</span></div>
                <div class="tmpl-row"><span class="tnum">4</span><span class="tnm">{{ t('assistant.s038') }}</span><span class="req must">{{ t('assistant.s039') }}</span></div>
                <div class="tmpl-row"><span class="tnum">5</span><span class="tnm">{{ t('assistant.s040') }}</span><span class="req must">{{ t('assistant.s041') }}</span></div>
                <div class="tmpl-row"><span class="tnum">6</span><span class="tnm">{{ t('assistant.s042') }}</span><span class="req must">{{ t('assistant.s043') }}</span></div>
                <div class="tmpl-row"><span class="tnum">7</span><span class="tnm">{{ t('assistant.s044') }}</span><span class="req opt">{{ t('assistant.s045') }}</span></div>
                <div class="tmpl-row"><span class="tnum">8</span><span class="tnm">{{ t('assistant.s046') }}</span><span class="req opt">{{ t('assistant.s047') }}</span></div>
              </div>
              <p class="tmpl-note" v-html="t('assistant.s048')"></p>
            </div>
            <div>
              <div class="subh">{{ t('assistant.s049') }}</div>
              <div class="acu">
                <div class="ah"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2v20M12 2l3 3M12 2 9 5" /></svg><span>{{ t('assistant.s050') }}</span></div>
                <div class="afield">
                  <label>{{ t('assistant.s051') }}</label>
                  <div class="segp"><span class="on">{{ t('assistant.s052') }}</span><span>{{ t('assistant.s053') }}</span><span>{{ t('assistant.s054') }}</span></div>
                </div>
                <div class="afield">
                  <label>{{ t('assistant.s055') }}</label>
                  <input class="inp" value="直刺 25–30 mm，捻转提插得气" data-en-val="Perpendicular 25–30 mm, twirling &amp; lifting-thrusting" readonly aria-label="进针手法" />
                </div>
                <div class="afield">
                  <label>{{ t('assistant.s056') }}</label>
                  <input class="inp" value="酸、麻、胀、重" data-en-val="Soreness, numbness, distension, heaviness" readonly aria-label="得气感应" />
                </div>
                <div class="afield" style="margin-bottom:0">
                  <label>{{ t('assistant.s057') }}</label>
                  <input class="inp" value="非穴位浅刺 + 假电针（无电流输出）" data-en-val="Non-acupoint shallow needling + sham EA (no current)" readonly aria-label="对照设置" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 面板 3：报告内容智能校验 -->
        <div class="panel is-hidden" data-panel="3">
          <div class="p-head">
            <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M9 12l2 2 4-4" /><path d="M12 3l7 3v6c0 4.5-3 7-7 8-4-1-7-3.5-7-8V6z" /></svg></span>
            <div><span class="p-num">{{ t('assistant.s058') }}</span><h2>{{ t('assistant.s059') }}</h2></div>
          </div>
          <p class="p-desc" v-html="t('assistant.s060')"></p>
          <div class="meter-box">
            <span class="subh" style="margin:0;white-space:nowrap">{{ t('assistant.s061') }}</span>
            <span class="meter" aria-hidden="true"><i></i></span>
            <b>82%</b>
          </div>
          <div class="two">
            <div>
              <div class="subh">{{ t('assistant.s062') }}</div>
              <ul class="chk">
                <li class="ok"><span class="ci"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M20 6 9 17l-5-5" /></svg></span><span class="ctext"><b>{{ t('assistant.s063') }}</b></span><span class="cstat">{{ t('assistant.s064') }}</span></li>
                <li class="ok"><span class="ci"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M20 6 9 17l-5-5" /></svg></span><span class="ctext"><b>{{ t('assistant.s065') }}</b></span><span class="cstat">{{ t('assistant.s066') }}</span></li>
                <li class="warn"><span class="ci"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 8v5M12 16h.01" /></svg></span><span class="ctext"><b>{{ t('assistant.s067') }}</b><span>{{ t('assistant.s068') }}</span></span><span class="cstat">{{ t('assistant.s069') }}</span></li>
                <li class="miss"><span class="ci"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M18 6 6 18M6 6l12 12" /></svg></span><span class="ctext"><b>{{ t('assistant.s070') }}</b><span>{{ t('assistant.s071') }}</span></span><span class="cstat">{{ t('assistant.s072') }}</span></li>
              </ul>
            </div>
            <div>
              <div class="subh">{{ t('assistant.s073') }}</div>
              <ul class="chk">
                <li class="warn"><span class="ci"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 8v5M12 16h.01" /></svg></span><span class="ctext"><b>{{ t('assistant.s074') }}</b><span>{{ t('assistant.s075') }}</span></span><span class="cstat">{{ t('assistant.s076') }}</span></li>
                <li class="miss"><span class="ci"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M18 6 6 18M6 6l12 12" /></svg></span><span class="ctext"><b>{{ t('assistant.s077') }}</b><span>{{ t('assistant.s078') }}</span></span><span class="cstat">{{ t('assistant.s079') }}</span></li>
                <li class="warn"><span class="ci"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 8v5M12 16h.01" /></svg></span><span class="ctext"><b>{{ t('assistant.s080') }}</b><span>{{ t('assistant.s081') }}</span></span><span class="cstat">{{ t('assistant.s082') }}</span></li>
                <li class="ok"><span class="ci"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M20 6 9 17l-5-5" /></svg></span><span class="ctext"><b>{{ t('assistant.s083') }}</b></span><span class="cstat">{{ t('assistant.s084') }}</span></li>
              </ul>
            </div>
          </div>
        </div>

        <!-- 面板 4：AI 辅助撰写建议 -->
        <div class="panel is-hidden" data-panel="4">
          <div class="p-head">
            <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3v3M12 18v3M3 12h3M18 12h3M6 6l2 2M16 16l2 2M18 6l-2 2M8 16l-2 2" /><circle cx="12" cy="12" r="3.5" /></svg></span>
            <div><span class="p-num">{{ t('assistant.s085') }}</span><h2>{{ t('assistant.s086') }}</h2></div>
          </div>
          <p class="p-desc">{{ t('assistant.s087') }}</p>
          <div class="two">
            <div>
              <div class="subh">{{ t('assistant.s088') }}</div>
              <div class="ai-box">
                <div class="ai-top"><span class="dot"></span><span>{{ t('assistant.s089') }}</span></div>
                <div class="ai-inp" v-html="t('assistant.s090')"></div>
                <div class="ai-out" v-html="t('assistant.s091')"></div>
              </div>
              <div class="style-chips" role="group" aria-label="润色风格">
                <button class="on">{{ t('assistant.s092') }}</button>
                <button>{{ t('assistant.s093') }}</button>
                <button>{{ t('assistant.s094') }}</button>
                <button>{{ t('assistant.s095') }}</button>
              </div>
            </div>
            <div>
              <div class="subh">{{ t('assistant.s096') }}</div>
              <ul class="ref-list">
                <li><em>1</em><span v-html="t('assistant.s097')"></span></li>
                <li><em>2</em><span v-html="t('assistant.s098')"></span></li>
                <li><em>3</em><span v-html="t('assistant.s099')"></span></li>
                <li><em>4</em><span v-html="t('assistant.s100')"></span></li>
              </ul>
              <p class="tmpl-note">{{ t('assistant.s101') }}</p>
            </div>
          </div>
        </div>

        <!-- 面板 5：报告导出与分享 -->
        <div class="panel is-hidden" data-panel="5">
          <div class="p-head">
            <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3v12m0 0 4-4m-4 4-4-4" /><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" /></svg></span>
            <div><span class="p-num">{{ t('assistant.s102') }}</span><h2>{{ t('assistant.s103') }}</h2></div>
          </div>
          <p class="p-desc">{{ t('assistant.s104') }}</p>
          <div class="subh">{{ t('assistant.s105') }}</div>
          <div class="exp-btns">
            <button class="exp" data-fmt="docx"><span class="ei" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4" /><path d="M9 13h6M9 16h4" /></svg></span><span><b>Word (.docx)</b><span>{{ t('assistant.s106') }}</span></span></button>
            <button class="exp" data-fmt="pdf"><span class="ei" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4" /><path d="M9 14h1.5a1.5 1.5 0 0 0 0-3H9v6" /></svg></span><span><b>{{ t('assistant.s107') }}</b><span>{{ t('assistant.s108') }}</span></span></button>
            <button class="exp" data-fmt="xml"><span class="ei" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M9 8l-4 4 4 4M15 8l4 4-4 4" /></svg></span><span><b>XML / JSON</b><span>{{ t('assistant.s109') }}</span></span></button>
          </div>
          <div class="share">
            <div class="subh">{{ t('assistant.s110') }}</div>
            <div class="share-row">
              <span class="share-link"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M9 15l6-6M8 13l-2 2a3 3 0 0 0 4 4l2-2M16 11l2-2a3 3 0 0 0-4-4l-2 2" /></svg><span id="shareUrl">https://action.gztcm.cn/r/9f3a…c7</span></span>
              <span class="share-perm" role="group" aria-label="分享权限">
                <button class="on">{{ t('assistant.s111') }}</button>
                <button>{{ t('assistant.s112') }}</button>
              </span>
              <button class="btn btn-ink btn-sm" id="copyLink">{{ t('assistant.s113') }}</button>
            </div>
          </div>
          <div class="subh" style="margin-top:22px">{{ t('assistant.s114') }}</div>
          <ul class="ver-list">
            <li><span class="vt">v3</span><span class="vn">{{ t('assistant.s115') }}</span><span class="vtag">{{ t('assistant.s116') }}</span></li>
            <li><span class="vt">v2</span><span class="vn">{{ t('assistant.s117') }}</span><span class="vtag">2026-07-20</span></li>
            <li><span class="vt">v1</span><span class="vn">{{ t('assistant.s118') }}</span><span class="vtag">2026-07-18</span></li>
          </ul>
          <div class="beta-note"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /></svg><span>{{ t('assistant.s119') }}</span></div>
        </div>

        <!-- 向导底部导航 -->
        <div class="wz-nav">
          <span class="wz-prog"><span>{{ t('assistant.s120') }}</span> <b id="curStep">1</b> / 5 <span>{{ t('assistant.s121') }}</span></span>
          <div class="wz-btns">
            <button class="btn btn-ghost" id="prevBtn" disabled>{{ t('assistant.s122') }}</button>
            <button class="btn btn-primary" id="nextBtn">下一步 <span class="arrow" aria-hidden="true">→</span></button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style>
.page-assistant .skip-link{position:absolute;left:12px;top:-60px;z-index:var(--z-toast);background:var(--indigo-700);color:#fff;font-weight:600;font-size:15px;padding:12px 20px;border-radius:10px;transition:top .2s var(--ease)}
.page-assistant .btn{display:inline-flex;align-items:center;justify-content:center;gap:9px;padding:13px 24px;border-radius:999px;font-weight:600;font-size:15px;border:1.5px solid transparent;cursor:pointer;white-space:nowrap;transition:transform .25s var(--ease),background-color .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
.page-assistant .btn-primary:disabled{background:var(--indigo-300);box-shadow:none;cursor:not-allowed;transform:none}
.page-assistant .btn-ghost:disabled{opacity:.45;cursor:not-allowed}
.page-assistant .btn-lg{padding:15px 30px;font-size:16px}
.page-assistant .phero{position:relative;overflow:hidden;background:var(--indigo-900);color:#fff;isolation:isolate}
.page-assistant .phero::before{content:"";position:absolute;inset:0;z-index:-1;background:radial-gradient(1000px 560px at 88% 0%,rgba(44,127,114,.5),transparent 60%),radial-gradient(680px 460px at 2% 100%,rgba(24,48,41,.7),transparent 65%),linear-gradient(160deg,#0d1a17 0%,#12211d 44%,#183029 100%)}
.page-assistant .phero .wrap{padding:clamp(28px,3.6vw,42px) clamp(20px,4vw,44px) clamp(40px,5.5vw,58px)}
.page-assistant .crumb{display:flex;align-items:center;gap:9px;font-size:13.5px;color:rgba(233,238,247,.66);margin-bottom:22px;flex-wrap:wrap}
.page-assistant .phero-tag{display:inline-flex;align-items:center;gap:10px;font-size:13px;font-weight:600;letter-spacing:.02em;color:var(--indigo-200);background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.16);padding:8px 16px;border-radius:999px;backdrop-filter:blur(4px)}
.page-assistant .phero h1{font-size:clamp(1.9rem,3.9vw,3rem);font-weight:700;letter-spacing:-.025em;margin:18px 0 0;text-wrap:balance;line-height:1.14}
.page-assistant .phero .psub{margin-top:18px;font-size:clamp(1rem,1.4vw,1.16rem);color:rgba(233,238,247,.9);max-width:64ch;line-height:1.7;text-wrap:pretty}
.page-assistant .phero-cta{display:flex;gap:14px;flex-wrap:wrap;margin-top:28px}
.page-assistant .wz{padding:clamp(34px,5vw,60px) 0}
.page-assistant .stepper{display:flex;gap:6px;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:10px;overflow-x:auto;scrollbar-width:none}
.page-assistant .stepper::-webkit-scrollbar{display:none}
.page-assistant .step{flex:1;min-width:150px;display:flex;align-items:center;gap:11px;padding:12px 14px;border-radius:12px;cursor:pointer;background:transparent;border:none;font-family:inherit;text-align:left;transition:background .2s}
.page-assistant .step:hover{background:var(--paper-2)}
.page-assistant .step.on{background:var(--indigo-100)}
.page-assistant .step .sn{width:30px;height:30px;flex-shrink:0;border-radius:9px;background:var(--paper-2);color:var(--muted);display:flex;align-items:center;justify-content:center;font-family:"Spectral",serif;font-weight:700;font-size:15px;transition:.2s}
.page-assistant .step.on .sn{background:var(--cinnabar);color:#fff}
.page-assistant .step.done .sn{background:var(--indigo-600);color:#fff}
.page-assistant .step .stx{min-width:0}
.page-assistant .step .stx b{display:block;font-size:13.5px;font-weight:700;color:var(--indigo-900);font-family:"Source Sans 3","Noto Sans SC",sans-serif;line-height:1.2}
.page-assistant .step .stx span{display:block;font-size:11px;color:var(--muted);margin-top:1px}
.page-assistant .step.on .stx b{color:var(--cinnabar-d)}
.page-assistant .panel{margin-top:20px;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);padding:clamp(22px,3.2vw,38px)}
.page-assistant .panel.is-hidden{display:none}
.page-assistant .p-head{display:flex;align-items:flex-start;gap:15px;margin-bottom:6px}
.page-assistant .p-ic{width:48px;height:48px;flex-shrink:0;border-radius:13px;background:var(--indigo-700);color:#fff;display:flex;align-items:center;justify-content:center}
.page-assistant .p-ic svg{width:26px;height:26px}
.page-assistant .p-num{font-size:12px;font-weight:700;color:var(--indigo-500);letter-spacing:.03em}
.page-assistant .panel h2{font-size:clamp(1.4rem,2.5vw,1.9rem);color:var(--indigo-900);letter-spacing:-.01em;line-height:1.2}
.page-assistant .p-desc{font-size:14.5px;color:var(--muted);line-height:1.65;max-width:74ch;margin:14px 0 22px}
.page-assistant .p-desc b{color:var(--indigo-700)}
.page-assistant .two{display:grid;grid-template-columns:1fr 1fr;gap:clamp(20px,3vw,32px)}
.page-assistant .subh{font-size:12.5px;font-weight:700;color:var(--indigo-900);text-transform:uppercase;letter-spacing:.03em;margin-bottom:12px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-assistant .q-group{margin-bottom:18px}
.page-assistant .q-group>label{display:block;font-size:14px;font-weight:600;color:var(--ink);margin-bottom:9px}
.page-assistant .opts{display:flex;flex-wrap:wrap;gap:9px}
.page-assistant .opt{font-family:inherit;font-size:13.5px;font-weight:600;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);border-radius:10px;padding:10px 16px;cursor:pointer;transition:.18s}
.page-assistant .opt:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-assistant .opt.on{background:var(--indigo-700);border-color:var(--indigo-700);color:#fff}
.page-assistant .sub-q.is-hidden{display:none}
.page-assistant .match{background:var(--indigo-900);color:#fff;border-radius:16px;padding:24px;position:relative;overflow:hidden;isolation:isolate}
.page-assistant .match::before{content:"";position:absolute;inset:0;z-index:-1;background:radial-gradient(500px 240px at 100% 0,rgba(44,127,114,.4),transparent 60%)}
.page-assistant .match .ml{font-size:12px;font-weight:700;color:var(--indigo-200);letter-spacing:.03em}
.page-assistant .match .mt{font-family:"Spectral","Noto Serif SC",serif;font-weight:700;font-size:1.5rem;margin:5px 0 16px;color:#fff}
.page-assistant .match .mrow{margin-bottom:15px}
.page-assistant .match .mrow>span{font-size:12px;color:rgba(233,238,247,.7);display:block;margin-bottom:7px}
.page-assistant .gchips{display:flex;flex-wrap:wrap;gap:7px}
.page-assistant .gchips b{font-size:12.5px;font-weight:700;padding:5px 12px;border-radius:999px;background:rgba(255,255,255,.1);color:#fff}
.page-assistant .gchips b.hot{background:var(--cinnabar);color:#fff}
.page-assistant .statlist{list-style:none;display:flex;flex-direction:column;gap:7px}
.page-assistant .statlist li{display:flex;align-items:flex-start;gap:9px;font-size:13px;color:rgba(233,238,247,.92);line-height:1.45}
.page-assistant .statlist li svg{width:16px;height:16px;flex-shrink:0;margin-top:2px;color:var(--indigo-200)}
.page-assistant .tmpl{border:1px solid var(--line);border-radius:14px;overflow:hidden}
.page-assistant .tmpl-row{display:flex;align-items:center;gap:12px;padding:12px 16px;border-top:1px solid var(--line);font-size:14px}
.page-assistant .tmpl-row:first-child{border-top:none}
.page-assistant .tmpl-row .tnum{font-family:"Spectral",serif;font-weight:700;color:var(--indigo-500);width:24px;flex-shrink:0}
.page-assistant .tmpl-row .tnm{flex:1;color:var(--ink);font-weight:600}
.page-assistant .req{font-size:11px;font-weight:700;padding:2px 9px;border-radius:999px}
.page-assistant .req.must{color:var(--cinnabar-d);background:rgba(192,54,44,.09)}
.page-assistant .req.opt{color:var(--muted);background:var(--paper-2)}
.page-assistant .acu{background:linear-gradient(180deg,#fff,var(--indigo-100));border:1px solid var(--indigo-200);border-radius:14px;padding:18px}
.page-assistant .acu .ah{display:flex;align-items:center;gap:8px;font-weight:700;color:var(--indigo-800);margin-bottom:14px}
.page-assistant .acu .ah svg{width:18px;height:18px;color:var(--cinnabar)}
.page-assistant .afield{margin-bottom:14px}
.page-assistant .afield>label{display:block;font-size:12.5px;font-weight:700;color:var(--indigo-700);margin-bottom:6px}
.page-assistant .afield .inp{width:100%;border:1.5px solid var(--line);border-radius:9px;padding:9px 12px;font-family:inherit;font-size:13.5px;color:var(--ink);background:var(--surface)}
.page-assistant .afield .segp{display:flex;flex-wrap:wrap;gap:6px}
.page-assistant .afield .segp span{font-size:12.5px;font-weight:600;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);border-radius:8px;padding:6px 12px;cursor:default}
.page-assistant .afield .segp span.on{background:var(--cinnabar);border-color:var(--cinnabar);color:#fff}
.page-assistant .tmpl-note{margin-top:14px;font-size:12.5px;color:var(--muted);line-height:1.55}
.page-assistant .tmpl-note b{color:var(--indigo-700)}
.page-assistant .meter-box{display:flex;align-items:center;gap:16px;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:16px 20px;margin-bottom:20px}
.page-assistant .meter{flex:1;height:10px;border-radius:999px;background:var(--paper-2);overflow:hidden}
.page-assistant .meter i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--indigo-500),var(--indigo-600));width:82%}
.page-assistant .meter-box b{font-family:"Spectral",serif;font-weight:700;font-size:1.3rem;color:var(--indigo-700)}
.page-assistant .chk{list-style:none;display:flex;flex-direction:column;gap:8px}
.page-assistant .chk li{display:flex;align-items:flex-start;gap:11px;font-size:14px;padding:11px 14px;border:1px solid var(--line);border-radius:11px;background:var(--surface);line-height:1.5}
.page-assistant .chk .ci{width:22px;height:22px;flex-shrink:0;border-radius:50%;display:flex;align-items:center;justify-content:center;margin-top:1px}
.page-assistant .chk .ci svg{width:14px;height:14px}
.page-assistant .chk .ok .ci{background:var(--info-bg);color:var(--info)}
.page-assistant .chk .warn .ci{background:var(--amber-bg);color:var(--amber)}
.page-assistant .chk .miss .ci{background:rgba(192,54,44,.09);color:var(--cinnabar-d)}
.page-assistant .chk .ctext b{color:var(--indigo-900)}
.page-assistant .chk .ctext span{display:block;font-size:12.5px;color:var(--muted);margin-top:2px}
.page-assistant .chk .cstat{margin-left:auto;flex-shrink:0;font-size:11.5px;font-weight:700;padding:3px 10px;border-radius:999px;white-space:nowrap}
.page-assistant .chk .ok .cstat{color:var(--info);background:var(--info-bg)}
.page-assistant .chk .warn .cstat{color:var(--amber);background:var(--amber-bg)}
.page-assistant .chk .miss .cstat{color:var(--cinnabar-d);background:rgba(192,54,44,.09)}
.page-assistant .ai-box{border:1px solid var(--line);border-radius:14px;overflow:hidden}
.page-assistant .ai-top{display:flex;align-items:center;gap:8px;padding:12px 16px;background:var(--paper-2);border-bottom:1px solid var(--line);font-size:13px;font-weight:700;color:var(--indigo-800)}
.page-assistant .ai-top .dot{width:8px;height:8px;border-radius:50%;background:var(--cinnabar)}
.page-assistant .ai-inp{padding:14px 16px;border-bottom:1px dashed var(--line);font-size:13.5px;color:var(--muted)}
.page-assistant .ai-inp b{color:var(--indigo-700)}
.page-assistant .ai-out{padding:16px;font-size:14px;color:var(--ink);line-height:1.7}
.page-assistant .ai-out .hl{background:var(--indigo-100);border-radius:3px;padding:0 2px}
.page-assistant .style-chips{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}
.page-assistant .style-chips button{font-family:inherit;font-size:13px;font-weight:600;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);border-radius:999px;padding:7px 15px;cursor:pointer;transition:.18s}
.page-assistant .style-chips button:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-assistant .style-chips button.on{background:var(--info);border-color:var(--info);color:#fff}
.page-assistant .ref-list{list-style:none;display:flex;flex-direction:column;gap:9px}
.page-assistant .ref-list li{display:flex;gap:11px;font-size:13px;color:var(--muted);line-height:1.5;padding:11px 14px;border:1px solid var(--line);border-radius:11px;background:var(--paper)}
.page-assistant .ref-list li em{font-style:normal;font-family:"Spectral",serif;font-weight:700;color:var(--indigo-500);flex-shrink:0}
.page-assistant .exp-btns{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.page-assistant .exp{display:flex;align-items:center;gap:13px;padding:16px 18px;border:1.5px solid var(--line);border-radius:14px;background:var(--surface);cursor:pointer;text-align:left;font-family:inherit;transition:.2s var(--ease)}
.page-assistant .exp:hover{border-color:var(--indigo-300);background:var(--indigo-100);transform:translateY(-2px)}
.page-assistant .exp .ei{width:40px;height:40px;flex-shrink:0;border-radius:11px;background:var(--indigo-100);color:var(--indigo-700);display:flex;align-items:center;justify-content:center}
.page-assistant .exp .ei svg{width:21px;height:21px}
.page-assistant .exp b{display:block;font-size:14px;color:var(--indigo-900)}
.page-assistant .exp span{font-size:12px;color:var(--muted)}
.page-assistant .share{margin-top:20px;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:18px}
.page-assistant .share-row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.page-assistant .share-link{flex:1;min-width:200px;display:flex;align-items:center;gap:10px;background:var(--surface);border:1.5px solid var(--line);border-radius:10px;padding:10px 14px;font-size:13px;color:var(--muted);font-family:"Spectral",monospace}
.page-assistant .share-perm{display:inline-flex;background:var(--paper-2);border:1px solid var(--line);border-radius:9px;padding:3px;gap:2px}
.page-assistant .share-perm button{border:none;background:transparent;font-family:inherit;font-size:12.5px;font-weight:600;color:var(--muted);padding:6px 12px;border-radius:7px;cursor:pointer}
.page-assistant .share-perm button.on{background:var(--surface);color:var(--indigo-800);box-shadow:var(--shadow-sm)}
.page-assistant .ver-list{list-style:none;margin-top:18px;display:flex;flex-direction:column;gap:8px}
.page-assistant .ver-list li{display:flex;align-items:center;gap:12px;font-size:13px;padding:11px 14px;border:1px solid var(--line);border-radius:11px;background:var(--surface)}
.page-assistant .ver-list .vt{font-family:"Spectral",serif;font-weight:700;color:var(--indigo-700);font-variant-numeric:tabular-nums}
.page-assistant .ver-list .vn{flex:1;color:var(--ink)}
.page-assistant .ver-list .vtag{font-size:11px;font-weight:700;color:var(--muted);background:var(--paper-2);border-radius:999px;padding:3px 10px}
.page-assistant .wz-nav{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-top:22px;flex-wrap:wrap}
.page-assistant .wz-nav .wz-prog{font-size:13px;color:var(--muted)}
.page-assistant .wz-nav .wz-prog b{color:var(--indigo-700)}
.page-assistant .wz-nav .wz-btns{display:flex;gap:10px}
.page-assistant .beta-note{display:inline-flex;align-items:center;gap:9px;font-size:12.5px;font-weight:600;color:var(--amber);background:var(--amber-bg);border:1px solid #e7d39a;padding:7px 14px;border-radius:999px;margin-top:20px}
@media(max-width:900px){
.page-assistant .two{grid-template-columns:1fr}
}
</style>
