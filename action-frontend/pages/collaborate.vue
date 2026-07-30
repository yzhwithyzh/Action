<script setup lang="ts">
/**
 * collaborate.html 迁移而来。
 * 模板与样式保持原状；样式已加 .page-collaborate 命名空间，避免 SPA 路由切换时跨页污染。
 */
const { t } = useI18n()

useHead({
  title: t('collaborate._title'),
  meta: [{ name: 'description', content: t('collaborate._desc') }],
})

const { locale } = useI18n()
const api = useSiteRequest()

const form = ref({ area: '方法学与设计', type: '', subject: '', question: '', name: '', email: '', org: '' })
const submitting = ref(false)
const msg = ref('')
const msgOk = ref(true)

/** 后端 CollabRequestSubmitModel 的长度上限，前端同步限制以免被 422 挡回 */
const MAXLEN = { applicant: 100, organization: 300, topic: 300, content: 5000 }

const submit = async () => {
  msg.value = ''
  if (!form.value.name.trim() || !form.value.email.trim()) {
    msgOk.value = false
    msg.value = t('collaborate.requiredHint')

    return
  }
  // content 在后端是 min_length=1 的必填字段，留空会被 422 挡回
  if (!form.value.question.trim()) {
    msgOk.value = false
    msg.value = t('collaborate.contentRequired')

    return
  }
  if (!form.value.area) {
    msgOk.value = false
    msg.value = t('collaborate.areaRequired')

    return
  }

  submitting.value = true
  try {
    // 「咨询领域」与「研究类型」在提交模型里都没有对应字段，按带标签的行并入正文而不是丢掉。
    // 用 data-v 的固定中文键与 option 的固定 value，避免后台同一字段收到中英两套词面。
    const head = [
      `${t('collaborate.lblArea')}: ${form.value.area}`,
      form.value.type ? `${t('collaborate.lblStudyType')}: ${form.value.type}` : '',
    ].filter(Boolean).join('\n')
    const content = `${head}\n${form.value.question}`.slice(0, MAXLEN.content)

    const res = await api.post('/collaborate', {
      requestType: 'consult',
      applicant: form.value.name.trim(),
      email: form.value.email.trim(),
      organization: form.value.org.trim() || null,
      topic: form.value.subject.trim() || null,
      content: content.trim() || null,
      sourceLang: locale.value,
    })

    if (res?.code === 200) {
      msgOk.value = true
      msg.value = t('collaborate.submitOk')
      form.value = { area: '方法学与设计', type: '', subject: '', question: '', name: '', email: '', org: '' }
    } else {
      msgOk.value = false
      msg.value = res?.msg || t('collaborate.submitFail')
    }
  } catch (err: unknown) {
    msgOk.value = false
    // FastAPI 的 422 响应体是 {"detail":[{loc:[...], msg:...}]}，不是本站的 {code,msg} 信封，
    // $fetch 会直接抛。这里取第一条校验错误告诉用户是哪个字段，而不是笼统一句「提交失败」。
    const detail = (err as { data?: { detail?: Array<{ loc?: unknown[]; msg?: string }> } })?.data?.detail
    const first = Array.isArray(detail) ? detail[0] : undefined
    if (first?.msg) {
      const field = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1]) : ''
      msg.value = `${t('collaborate.fieldError')}${field ? field + ' — ' : ''}${first.msg}`
    } else {
      msg.value = t('collaborate.submitFail')
    }
  } finally {
    submitting.value = false
  }
}

useReveal()
</script>

<template>
  <div class="page-collaborate">
    <!-- ===================== ① 专家咨询通道 ===================== -->
    <section class="sec" id="consult">
      <div class="wrap">
        <div class="sec-head">
          <span class="sh-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M8 10h8M8 14h5" /><path d="M4 5h16v12H9l-4 4V5z" /></svg></span>
          <div><span class="sh-num">{{ t('collaborate.s001') }}</span><h2 class="title reveal">{{ t('collaborate.s002') }}</h2></div>
        </div>
        <p class="lead reveal">{{ t('collaborate.s003') }}</p>

        <div class="consult">
          <div class="reveal">
            <div class="subh">{{ t('collaborate.s004') }}</div>
            <div class="dom-list">
              <div class="dom"><span class="di" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 5h16M4 5v14M4 19h16" /><path d="M8 15l3-4 2 2 3-5" /></svg></span><span><b>{{ t('collaborate.s005') }}</b><span>{{ t('collaborate.s006') }}</span></span></div>
              <div class="dom"><span class="di" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></svg></span><span><b>{{ t('collaborate.s007') }}</b><span>{{ t('collaborate.s008') }}</span></span></div>
              <div class="dom"><span class="di" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 2v20M12 2l3 3M12 2 9 5" /><circle cx="12" cy="14" r="3" /></svg></span><span><b>{{ t('collaborate.s009') }}</b><span>{{ t('collaborate.s010') }}</span></span></div>
              <div class="dom"><span class="di" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4" /><path d="M10 13h4M10 16h4" /></svg></span><span><b>{{ t('collaborate.s011') }}</b><span>{{ t('collaborate.s012') }}</span></span></div>
              <div class="dom"><span class="di" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="8" /><path d="M12 4v8l5 3" /></svg></span><span><b>{{ t('collaborate.s013') }}</b><span>{{ t('collaborate.s014') }}</span></span></div>
            </div>
            <p class="board-note" v-html="t('collaborate.s015')"></p>
          </div>

          <form class="cform reveal" id="cform" novalidate @submit.prevent="submit">
            <div class="subh">{{ t('collaborate.s016') }}</div>
            <div class="frow">
              <label v-html="t('collaborate.s017')"></label>
              <div class="catchips" id="cat" role="group" aria-label="咨询领域">
                <button type="button" :class="{ on: form.area === '方法学与设计' }" :aria-pressed="form.area === '方法学与设计'" data-v="方法学与设计" @click="form.area = '方法学与设计'">{{ t('collaborate.s018') }}</button>
                <button type="button" :class="{ on: form.area === '统计分析' }" :aria-pressed="form.area === '统计分析'" data-v="统计分析" @click="form.area = '统计分析'">{{ t('collaborate.s019') }}</button>
                <button type="button" :class="{ on: form.area === '针灸临床' }" :aria-pressed="form.area === '针灸临床'" data-v="针灸临床" @click="form.area = '针灸临床'">{{ t('collaborate.s020') }}</button>
                <button type="button" :class="{ on: form.area === '报告规范' }" :aria-pressed="form.area === '报告规范'" data-v="报告规范" @click="form.area = '报告规范'">{{ t('collaborate.s021') }}</button>
                <button type="button" :class="{ on: form.area === '实施科学' }" :aria-pressed="form.area === '实施科学'" data-v="实施科学" @click="form.area = '实施科学'">{{ t('collaborate.s022') }}</button>
                <button type="button" :class="{ on: form.area === '其他' }" :aria-pressed="form.area === '其他'" data-v="其他" @click="form.area = '其他'">{{ t('collaborate.s023') }}</button>
              </div>
            </div>
            <div class="frow two-col">
              <div>
                <label for="cf-type">{{ t('collaborate.s024') }}</label>
                <select v-model="form.type" class="sel" id="cf-type" aria-label="研究类型">
                  <option value="">{{ t('collaborate.s025') }}</option>
                  <option value="rct">{{ t('collaborate.s026') }}</option>
                  <option value="nrct">{{ t('collaborate.s027') }}</option>
                  <option value="case">{{ t('collaborate.s028') }}</option>
                  <option value="sr">{{ t('collaborate.s029') }}</option>
                  <option value="obs">{{ t('collaborate.s030') }}</option>
                  <option value="other">{{ t('collaborate.s031') }}</option>
                </select>
              </div>
              <div>
                <label for="cf-subject" v-html="t('collaborate.s032')"></label>
                <input v-model="form.subject" class="inp" id="cf-subject" data-en-ph="e.g. How to report sham-needle parameters" placeholder="例如：假针参数应如何报告" aria-label="咨询主题" :maxlength="MAXLEN.topic" />
              </div>
            </div>
            <div class="frow">
              <label for="cf-q" v-html="t('collaborate.s033')"></label>
              <textarea v-model="form.question" class="ta" id="cf-q" data-en-ph="Describe your study background and the specific question you need help with…" placeholder="请描述你的研究背景与需要协助的具体问题……" aria-label="详细描述" :maxlength="MAXLEN.content" required></textarea>
            </div>
            <div class="frow two-col">
              <div><label for="cf-name">{{ t('collaborate.s034') }}</label><input v-model="form.name" class="inp" id="cf-name" aria-label="姓名" required :maxlength="MAXLEN.applicant" /></div>
              <div><label for="cf-email" v-html="t('collaborate.s035')"></label><input v-model="form.email" class="inp" id="cf-email" type="email" placeholder="you@example.com" aria-label="邮箱" required /></div>
            </div>
            <div class="frow" style="margin-bottom:14px"><label for="cf-org">{{ t('collaborate.s036') }}</label><input v-model="form.org" class="inp" id="cf-org" aria-label="单位" :maxlength="MAXLEN.organization" /></div>
            <div class="cform-foot">
              <span class="fn">{{ t('collaborate.s037') }}</span>
              <button type="submit" class="btn btn-primary" :disabled="submitting" v-html="submitting ? t('collaborate.submitting') : t('collaborate.s038')"></button>
            </div>
            <div class="fmsg" :class="{ show: !!msg }" id="fmsg" :style="msgOk ? undefined : { color: 'var(--cinnabar)', background: 'rgba(192,54,44,.08)', borderColor: '#e7b0aa' }"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><path v-if="msgOk" d="M20 6 9 17l-5-5" /><path v-else d="M12 8v5M12 16h.01" /></svg><span>{{ msg }}</span></div>
          </form>
        </div>
      </div>
    </section>

    <!-- ===================== ② 用户交流论坛 ===================== -->
    <section class="sec is-hidden" id="forum" style="background:var(--paper-2)">
      <div class="wrap">
        <div class="sec-head forum">
          <span class="sh-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M21 11.5a8.38 8.38 0 0 1-9 8.35 8.5 8.5 0 0 1-3.8-.9L3 20l1.05-4.2A8.38 8.38 0 0 1 3 11.5 8.5 8.5 0 0 1 11.5 3 8.38 8.38 0 0 1 21 11.5z" /></svg></span>
          <div><span class="sh-num">{{ t('collaborate.s040') }}</span><h2 class="title reveal">{{ t('collaborate.s041') }}</h2></div>
        </div>
        <p class="lead reveal">{{ t('collaborate.s042') }}</p>

        <div class="subh reveal" style="margin-top:clamp(24px,3vw,32px)">{{ t('collaborate.s043') }}</div>
        <div class="board-grid">
          <button type="button" class="board reveal"><span class="bi" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4" /><path d="M10 13h4M10 16h4" /></svg></span><span class="bx"><b>{{ t('collaborate.s044') }}</b><p>{{ t('collaborate.s045') }}</p><span class="bstat"><b>128</b> <span>{{ t('collaborate.s046') }}</span></span></span></button>
          <button type="button" class="board reveal"><span class="bi" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></svg></span><span class="bx"><b>{{ t('collaborate.s047') }}</b><p>{{ t('collaborate.s048') }}</p><span class="bstat"><b>96</b> <span>{{ t('collaborate.s049') }}</span></span></span></button>
          <button type="button" class="board reveal"><span class="bi" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 2v20M12 2l3 3M12 2 9 5" /><circle cx="12" cy="14" r="3" /></svg></span><span class="bx"><b>{{ t('collaborate.s050') }}</b><p>{{ t('collaborate.s051') }}</p><span class="bstat"><b>154</b> <span>{{ t('collaborate.s052') }}</span></span></span></button>
          <button type="button" class="board reveal"><span class="bi" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="7" y="9" width="34" height="30" rx="3" transform="scale(.6)" /><rect x="4" y="6" width="16" height="13" rx="2" /><path d="M8 22h8M8 10h5" /></svg></span><span class="bx"><b>{{ t('collaborate.s053') }}</b><p>{{ t('collaborate.s054') }}</p><span class="bstat"><b>73</b> <span>{{ t('collaborate.s055') }}</span></span></span></button>
          <button type="button" class="board reveal"><span class="bi" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="8" /><path d="M12 4v8l5 3" /></svg></span><span class="bx"><b>{{ t('collaborate.s056') }}</b><p>{{ t('collaborate.s057') }}</p><span class="bstat"><b>41</b> <span>{{ t('collaborate.s058') }}</span></span></span></button>
          <button type="button" class="board reveal"><span class="bi" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="9" cy="8" r="3" /><circle cx="17" cy="10" r="2.5" /><path d="M4 19c0-3 2.5-5 5-5s5 2 5 5M15 19c0-2 1.5-3.5 3-3.5" /></svg></span><span class="bx"><b>{{ t('collaborate.s059') }}</b><p>{{ t('collaborate.s060') }}</p><span class="bstat"><b>210</b> <span>{{ t('collaborate.s061') }}</span></span></span></button>
        </div>

        <div class="thread-head">
          <h3>{{ t('collaborate.s062') }}</h3>
          <button type="button" class="btn btn-ink btn-sm" id="newThread" v-html="t('collaborate.s063')"></button>
        </div>
        <div class="threads">
          <div class="thread"><div class="th-main"><div class="tt">{{ t('collaborate.s064') }}</div><div class="th-meta"><span class="btag hot">{{ t('collaborate.s065') }}</span><span class="au">{{ t('collaborate.s066') }}</span></div></div><div class="th-reply"><b>12</b><span>{{ t('collaborate.s067') }}</span></div><div class="th-time">{{ t('collaborate.s068') }}</div></div>
          <div class="thread"><div class="th-main"><div class="tt">{{ t('collaborate.s069') }}</div><div class="th-meta"><span class="btag">{{ t('collaborate.s070') }}</span><span class="au">{{ t('collaborate.s071') }}</span></div></div><div class="th-reply"><b>8</b><span>{{ t('collaborate.s072') }}</span></div><div class="th-time">{{ t('collaborate.s073') }}</div></div>
          <div class="thread"><div class="th-main"><div class="tt">{{ t('collaborate.s074') }}</div><div class="th-meta"><span class="btag">{{ t('collaborate.s075') }}</span><span class="au">{{ t('collaborate.s076') }}</span></div></div><div class="th-reply"><b>21</b><span>{{ t('collaborate.s077') }}</span></div><div class="th-time">{{ t('collaborate.s078') }}</div></div>
          <div class="thread"><div class="th-main"><div class="tt">{{ t('collaborate.s079') }}</div><div class="th-meta"><span class="btag">{{ t('collaborate.s080') }}</span><span class="au">{{ t('collaborate.s081') }}</span></div></div><div class="th-reply"><b>5</b><span>{{ t('collaborate.s082') }}</span></div><div class="th-time">{{ t('collaborate.s083') }}</div></div>
          <div class="thread"><div class="th-main"><div class="tt">{{ t('collaborate.s084') }}</div><div class="th-meta"><span class="btag">{{ t('collaborate.s085') }}</span><span class="au">{{ t('collaborate.s086') }}</span></div></div><div class="th-reply"><b>9</b><span>{{ t('collaborate.s087') }}</span></div><div class="th-time">{{ t('collaborate.s088') }}</div></div>
        </div>
        <div class="forum-note"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /></svg><span>{{ t('collaborate.s089') }}</span></div>
      </div>
    </section>

    <!-- ===================== 参与方式 band ===================== -->
    <section class="sec ways" id="ways">
      <div class="wrap">
        <span class="kicker reveal">{{ t('collaborate.s090') }}</span>
        <h2 class="title reveal">{{ t('collaborate.s091') }}</h2>
        <p class="lead reveal">{{ t('collaborate.s092') }}</p>
        <div class="ways-grid">
          <div class="way reveal"><span class="wi" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M20 6 9 17l-5-5" /></svg></span><b>{{ t('collaborate.s093') }}</b><p>{{ t('collaborate.s094') }}</p></div>
          <div class="way reveal"><span class="wi" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="9" cy="8" r="3" /><path d="M4 20c0-3 2-5 5-5s5 2 5 5M16 6h5M18.5 3.5v5" /></svg></span><b>{{ t('collaborate.s095') }}</b><p>{{ t('collaborate.s096') }}</p></div>
          <div class="way reveal"><span class="wi" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M8 10h8M8 14h5" /><path d="M4 5h16v12H9l-4 4V5z" /></svg></span><b>{{ t('collaborate.s097') }}</b><p>{{ t('collaborate.s098') }}</p></div>
          <div class="way reveal"><span class="wi" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M3 21h18M5 21V9l7-5 7 5v12M9 21v-6h6v6" /></svg></span><b>{{ t('collaborate.s099') }}</b><p>{{ t('collaborate.s100') }}</p></div>
        </div>
        <div style="margin-top:clamp(26px,3.5vw,36px)">
          <a href="mailto:action@gztcm-action.cn?subject=ACTION 机构合作 / 参与咨询" class="btn btn-primary btn-lg" v-html="t('collaborate.s101')"></a>
        </div>
      </div>
    </section>
  </div>
</template>

<style>
.page-collaborate .skip-link{position:absolute;left:12px;top:-60px;z-index:var(--z-toast);background:var(--indigo-700);color:#fff;font-weight:600;font-size:15px;padding:12px 20px;border-radius:10px;transition:top .2s var(--ease)}
.page-collaborate .sec{padding:clamp(44px,6vw,80px) 0;scroll-margin-top:130px}
.page-collaborate h2.title{font-size:clamp(1.65rem,3.2vw,2.35rem);color:var(--indigo-900);letter-spacing:-.02em;text-wrap:balance;max-width:26ch}
.page-collaborate .lead{color:var(--muted);font-size:clamp(1rem,1.4vw,1.14rem);max-width:68ch;margin-top:16px;text-wrap:pretty}
.page-collaborate .sec-head{display:flex;align-items:flex-start;gap:15px;margin-bottom:6px}
.page-collaborate .sh-ic{width:52px;height:52px;flex-shrink:0;border-radius:14px;background:var(--indigo-700);color:#fff;display:flex;align-items:center;justify-content:center}
.page-collaborate .sec-head.forum .sh-ic{background:var(--info)}
.page-collaborate .sh-ic svg{width:28px;height:28px}
.page-collaborate .sh-num{font-size:12px;font-weight:700;color:var(--indigo-500);letter-spacing:.03em}
.page-collaborate .btn{display:inline-flex;align-items:center;justify-content:center;gap:9px;padding:13px 24px;border-radius:999px;font-weight:600;font-size:15px;border:1.5px solid transparent;cursor:pointer;white-space:nowrap;transition:transform .25s var(--ease),background-color .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
.page-collaborate .btn-lg{padding:15px 30px;font-size:16px}
.page-collaborate .phero::before{content:"";position:absolute;inset:0;z-index:-1;background:radial-gradient(1000px 560px at 90% 0%,rgba(44,127,114,.5),transparent 60%),radial-gradient(680px 460px at 2% 100%,rgba(15,111,106,.26),transparent 65%),linear-gradient(160deg,#0d1a17 0%,#12211d 44%,#183029 100%)}
.page-collaborate .phero .wrap{padding:clamp(28px,3.6vw,42px) clamp(20px,4vw,44px) clamp(40px,5.5vw,58px)}
.page-collaborate .crumb{display:flex;align-items:center;gap:9px;font-size:13.5px;color:rgba(233,238,247,.66);margin-bottom:22px;flex-wrap:wrap}
.page-collaborate .phero-tag{display:inline-flex;align-items:center;gap:10px;font-size:13px;font-weight:600;letter-spacing:.02em;color:var(--indigo-200);background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.16);padding:8px 16px;border-radius:999px;backdrop-filter:blur(4px)}
.page-collaborate .phero h1{font-size:clamp(1.9rem,3.9vw,3rem);font-weight:700;letter-spacing:-.025em;margin:18px 0 0;text-wrap:balance;line-height:1.14}
.page-collaborate .phero .psub{margin-top:18px;font-size:clamp(1rem,1.4vw,1.16rem);color:rgba(233,238,247,.9);max-width:60ch;line-height:1.7;text-wrap:pretty}
.page-collaborate .phero-main{min-width:0}
.page-collaborate .subnav{position:sticky;top:72px;z-index:var(--z-subnav);background:rgba(242,246,244,.9);backdrop-filter:blur(12px) saturate(1.3);border-bottom:1px solid var(--line)}
.page-collaborate .subnav-in{display:flex;align-items:center;gap:4px;overflow-x:auto;scrollbar-width:none}
.page-collaborate .subnav-in::-webkit-scrollbar{display:none}
.page-collaborate .subnav a{position:relative;flex-shrink:0;padding:15px 15px 13px;font-size:14.5px;font-weight:600;color:var(--muted);white-space:nowrap;transition:color .2s}
.page-collaborate .subnav a .n{display:inline-flex;align-items:center;justify-content:center;width:19px;height:19px;margin-right:7px;border-radius:6px;background:var(--indigo-100);color:var(--indigo-600);font-size:11.5px;font-weight:700;font-family:"Spectral",serif}
.page-collaborate .subnav a::after{content:"";position:absolute;left:15px;right:15px;bottom:-1px;height:2px;background:var(--cinnabar);transform:scaleX(0);transform-origin:left;transition:transform .3s var(--ease)}
.page-collaborate .subnav a:hover,.page-collaborate .subnav a.active{color:var(--indigo-900)}
.page-collaborate .subnav a.active .n{background:var(--cinnabar);color:#fff}
.page-collaborate .subnav a.active::after{transform:scaleX(1)}
.page-collaborate .consult{display:grid;grid-template-columns:1fr 1.1fr;gap:clamp(24px,3.5vw,44px);margin-top:clamp(26px,3.5vw,38px);align-items:start}
.page-collaborate .subh{font-size:12.5px;font-weight:700;color:var(--indigo-900);text-transform:uppercase;letter-spacing:.03em;margin-bottom:14px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-collaborate .dom-list{display:flex;flex-direction:column;gap:10px}
.page-collaborate .dom{display:flex;align-items:flex-start;gap:13px;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px 18px;transition:.2s var(--ease)}
.page-collaborate .dom:hover{border-color:var(--indigo-200);box-shadow:var(--shadow-sm)}
.page-collaborate .dom .di{width:38px;height:38px;flex-shrink:0;border-radius:10px;background:var(--indigo-100);color:var(--indigo-600);display:flex;align-items:center;justify-content:center}
.page-collaborate .dom .di svg{width:20px;height:20px}
.page-collaborate .dom b{display:block;font-size:14.5px;color:var(--indigo-900);font-family:"Source Sans 3","Noto Sans SC",sans-serif;font-weight:700}
.page-collaborate .dom span{display:block;font-size:12.5px;color:var(--muted);line-height:1.5;margin-top:2px}
.page-collaborate .board-note{margin-top:16px;background:linear-gradient(180deg,#fff,var(--indigo-100));border:1px solid var(--indigo-200);border-radius:14px;padding:16px 18px;font-size:13px;color:var(--ink);line-height:1.6}
.page-collaborate .board-note b{color:var(--indigo-700)}
.page-collaborate .cform{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);padding:clamp(20px,3vw,30px)}
.page-collaborate .frow{margin-bottom:16px}
.page-collaborate .frow.two-col{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.page-collaborate .frow label{display:block;font-size:12.5px;font-weight:700;color:var(--indigo-800);margin-bottom:7px}
.page-collaborate .frow label .rq{color:var(--cinnabar)}
.page-collaborate .catchips{display:flex;flex-wrap:wrap;gap:8px}
.page-collaborate .catchips button{font-family:inherit;font-size:13px;font-weight:600;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);border-radius:999px;padding:8px 14px;cursor:pointer;transition:.18s}
.page-collaborate .catchips button:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-collaborate .catchips button.on{background:var(--indigo-700);border-color:var(--indigo-700);color:#fff}
.page-collaborate .inp,.page-collaborate .ta,.page-collaborate .sel{width:100%;border:1.5px solid var(--line);border-radius:10px;padding:11px 13px;font-family:inherit;font-size:14px;color:var(--ink);background:var(--paper)}
.page-collaborate .ta{min-height:120px;resize:vertical;line-height:1.6}
.page-collaborate .inp:focus,.page-collaborate .ta:focus,.page-collaborate .sel:focus{outline:none;border-color:var(--indigo-500);box-shadow:0 0 0 4px var(--indigo-100);background:var(--surface)}
.page-collaborate .inp::placeholder,.page-collaborate .ta::placeholder{color:#8895a8}
.page-collaborate .cform-foot{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-top:6px}
.page-collaborate .cform-foot .fn{font-size:12px;color:var(--muted);max-width:42ch;line-height:1.5}
.page-collaborate .fmsg{display:none;align-items:center;gap:9px;font-size:13px;font-weight:600;color:var(--info);background:var(--info-bg);border:1px solid #bcd4f0;border-radius:10px;padding:10px 14px;margin-top:14px}
.page-collaborate .fmsg.show{display:flex}
.page-collaborate .board-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin-top:clamp(24px,3vw,32px)}
.page-collaborate .board{display:flex;align-items:flex-start;gap:13px;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:20px;cursor:pointer;transition:.22s var(--ease)}
.page-collaborate .board:hover{transform:translateY(-3px);box-shadow:var(--shadow-md);border-color:var(--info)}
.page-collaborate .board .bi{width:44px;height:44px;flex-shrink:0;border-radius:12px;background:var(--info-bg);color:var(--info);display:flex;align-items:center;justify-content:center}
.page-collaborate .board .bi svg{width:23px;height:23px}
.page-collaborate .board .bx{min-width:0}
.page-collaborate .board b{display:block;font-family:"Spectral","Noto Serif SC",serif;font-weight:600;font-size:1.06rem;color:var(--indigo-900)}
.page-collaborate .board p{font-size:12.5px;color:var(--muted);line-height:1.5;margin:3px 0 8px}
.page-collaborate .board .bstat{font-size:12px;color:var(--indigo-600);font-weight:600}
.page-collaborate .board .bstat b{display:inline;font-family:inherit;color:var(--cinnabar-d)}
.page-collaborate .thread-head{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin:clamp(30px,4vw,44px) 0 14px}
.page-collaborate .thread-head h3{font-size:1.2rem;color:var(--indigo-900)}
.page-collaborate .threads{border:1px solid var(--line);border-radius:16px;overflow:hidden;background:var(--surface)}
.page-collaborate .thread{display:grid;grid-template-columns:1fr auto auto;gap:18px;align-items:center;padding:16px 20px;border-top:1px solid var(--line);cursor:pointer;transition:background .18s}
.page-collaborate .thread:first-child{border-top:none}
.page-collaborate .thread:hover{background:var(--paper)}
.page-collaborate .th-main{min-width:0}
.page-collaborate .th-main .tt{font-size:14.5px;font-weight:600;color:var(--indigo-900);line-height:1.4}
.page-collaborate .th-meta{display:flex;align-items:center;gap:10px;margin-top:5px;flex-wrap:wrap}
.page-collaborate .btag{font-size:11px;font-weight:700;color:var(--info);background:var(--info-bg);border-radius:6px;padding:2px 9px}
.page-collaborate .btag.hot{color:var(--cinnabar-d);background:rgba(192,54,44,.08)}
.page-collaborate .th-meta .au{font-size:12px;color:var(--muted)}
.page-collaborate .th-reply{text-align:center;min-width:56px}
.page-collaborate .th-reply b{display:block;font-family:"Spectral",serif;font-weight:700;font-size:1.1rem;color:var(--indigo-700);line-height:1}
.page-collaborate .th-reply span{font-size:11px;color:var(--muted)}
.page-collaborate .th-time{font-size:12.5px;color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}
.page-collaborate .forum-note{display:inline-flex;align-items:center;gap:9px;font-size:12.5px;font-weight:600;color:var(--amber);background:var(--amber-bg);border:1px solid #e7d39a;padding:7px 14px;border-radius:999px;margin-top:18px}
.page-collaborate .ways{background:var(--indigo-900);color:#fff;isolation:isolate;position:relative;overflow:hidden}
.page-collaborate .ways::before{content:"";position:absolute;inset:0;z-index:-1;background:radial-gradient(700px 340px at 88% 0,rgba(44,127,114,.4),transparent 60%)}
.page-collaborate .ways .kicker{color:var(--indigo-200)}
.page-collaborate .ways h2.title{color:#fff}
.page-collaborate .ways .lead{color:rgba(233,238,247,.84)}
.page-collaborate .ways-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px;margin-top:clamp(26px,3.5vw,36px)}
.page-collaborate .way{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.14);border-radius:16px;padding:22px}
.page-collaborate .way .wi{width:38px;height:38px;border-radius:10px;background:rgba(255,255,255,.1);color:var(--indigo-200);display:flex;align-items:center;justify-content:center;margin-bottom:13px}
.page-collaborate .way .wi svg{width:20px;height:20px}
.page-collaborate .way b{display:block;font-family:"Spectral","Noto Serif SC",serif;font-weight:600;font-size:1.08rem;color:#fff;margin-bottom:6px}
.page-collaborate .way p{font-size:13px;color:rgba(233,238,247,.78);line-height:1.55}
@media(max-width:900px){
.page-collaborate .consult{grid-template-columns:1fr}
}
@media(max-width:640px){
.page-collaborate .frow.two-col{grid-template-columns:1fr}
.page-collaborate .thread{grid-template-columns:1fr auto;gap:12px}
.page-collaborate .th-reply{display:none}
}
</style>
